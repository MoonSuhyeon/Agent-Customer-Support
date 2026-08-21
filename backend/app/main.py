"""FastAPI — Agent API.

그래프는 ``confirm`` 다음에서 멈춘다. 그래서 대화 API 와 **승인 API 가 분리**된다.
클라이언트는 승인 화면을 띄우고, 고객이 누르면 ``/support/confirm`` 을 호출한다.

    POST /support/messages        문의 전송 → 확인 대기 또는 완료
    POST /support/confirm         고객 승인 → 상태 변경 실행
    GET  /support/sessions/{id}   현재 상태와 트레이스

    GET  /orchestration/summary   결정 분포, 정책 통과율, 사람 채택률
    GET  /orchestration/recent    최근 결정 — **거절 사유까지**
    GET  /orchestration/pending   사람 승인 대기
    POST /orchestration/review    사람의 판단을 받는다

화면은 이 저장소에 없다. 운영 콘솔이 이 API 를 호출한다 — 저장소마다 화면을 따로
두면 같은 규칙이 여러 곳으로 갈라지기 때문이다.
"""
from __future__ import annotations

from datetime import date

from fastapi import FastAPI, HTTPException
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, ConfigDict, Field

from app.agent.graph import build_graph
from app.domain import seed
from app.orchestration.console import Console
from app.orchestration.ledger import Decision, Ledger

app = FastAPI(title="Agent Customer Support", version="0.1.0")

_store = seed()
_checkpointer = MemorySaver()
_agent = build_graph(_store, today=date.today(), checkpointer=_checkpointer)

# 개입 원장은 상담 상태와 **다른 저장소**다. 콘솔은 그걸 읽기만 한다 —
# 결정은 조정자가 하고, 여기서 규칙을 한 벌 더 쓰면 두 곳이 어긋난다.
_console = Console(Ledger())


def _cfg(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def _awaiting(session_id: str) -> bool:
    return _agent.get_state(_cfg(session_id)).next == ("execute",)


class MessageIn(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    request_id: str = Field(min_length=1)


class ConfirmIn(BaseModel):
    session_id: str
    approved: bool = True


class DecisionOut(BaseModel):
    """판단 결과. **`proceed` 에 따라 나머지 필드가 갈린다.**

    거절이면 `reason` 만, 진행이면 환불 정보가 실린다. 한 모델로 두되 서로
    배타적인 필드를 선택으로 남긴다 — 소비자가 `proceed` 를 보고 갈라야 한다는
    사실이 스키마에 드러나야 하기 때문이다. `dict` 로 두면 그 사실이 사라지고,
    화면은 환불 금액이 항상 있다고 가정하게 된다.
    """

    proceed: bool
    #: 거절일 때만 채워진다.
    reason: str | None = None
    #: 진행일 때만 채워진다.
    refund_amount: int | None = None
    refund_ratio: float | None = None
    policy: str | None = None


class TraceEntry(BaseModel):
    """트레이스 한 줄.

    **`node` 만 보장한다.** 나머지 키는 노드마다 다르고, 노드가 늘면 또 달라진다.
    전부 열거하면 노드를 하나 추가할 때마다 스키마가 따라 움직여야 하고, 그렇다고
    통째로 `dict` 로 두면 소비자가 `node` 조차 믿을 수 없다. 보장되는 것만
    보장하고 나머지는 열어 둔다.
    """

    model_config = ConfigDict(extra="allow")

    node: str


class AgentOut(BaseModel):
    session_id: str
    response: str
    awaiting_confirmation: bool
    escalated: bool
    verified: bool = False
    decision: DecisionOut | None = None


def _out(session_id: str, state: dict) -> AgentOut:
    return AgentOut(
        session_id=session_id,
        response=state.get("response", ""),
        awaiting_confirmation=_awaiting(session_id),
        escalated=bool(state.get("escalated")),
        verified=bool(state.get("verified")),
        decision=state.get("decision"),
    )


@app.post("/support/messages", response_model=AgentOut)
def send_message(body: MessageIn) -> AgentOut:
    state = _agent.invoke(
        {"message": body.message, "request_id": body.request_id, "trace": []},
        _cfg(body.session_id),
    )
    return _out(body.session_id, state)


@app.post("/support/confirm", response_model=AgentOut)
def confirm(body: ConfirmIn) -> AgentOut:
    """고객 승인. **이 호출 없이는 상태 변경이 일어나지 않는다.**"""
    if not _awaiting(body.session_id):
        raise HTTPException(409, "확인 대기 중인 요청이 없습니다")
    if not body.approved:
        snap = _agent.get_state(_cfg(body.session_id)).values
        return AgentOut(session_id=body.session_id,
                        response="요청을 취소했습니다. 예약은 그대로 유지됩니다.",
                        awaiting_confirmation=False, escalated=False,
                        decision=snap.get("decision"))
    state = _agent.invoke(None, _cfg(body.session_id))
    return _out(body.session_id, state)


class SessionOut(BaseModel):
    """세션 현재 상태.

    예전에는 `dict` 를 그대로 돌려줬다. 그러면 OpenAPI 에 모양이 안 실리고,
    소비자는 응답 모양을 손으로 적을 수밖에 없다 — 그렇게 적힌 것은 서비스가
    바뀌어도 아무 데서도 안 걸린다.
    """

    session_id: str
    awaiting_confirmation: bool
    #: 다음에 실행될 노드. 비어 있으면 그래프가 끝났다는 뜻이다.
    next_nodes: list[str]
    response: str
    escalated: bool
    decision: DecisionOut | None = None
    trace: list[TraceEntry]


@app.get("/support/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: str) -> SessionOut:
    snap = _agent.get_state(_cfg(session_id))
    if not snap.values:
        raise HTTPException(404, "세션을 찾을 수 없습니다")
    return SessionOut(
        session_id=session_id,
        awaiting_confirmation=snap.next == ("execute",),
        next_nodes=list(snap.next),
        response=snap.values.get("response", ""),
        escalated=bool(snap.values.get("escalated")),
        decision=snap.values.get("decision"),
        trace=snap.values.get("trace", []),
    )


# ─────────────────────────────────────────────────── 콘솔 (A6)
class DecisionRow(BaseModel):
    """원장 한 줄. **거절 사유가 필수다** — 이유 없는 거절은 콘솔에서 쓸모가 없다."""

    id: int
    unit: str
    agent: str
    action: str
    cost: int
    decision: str
    reason: str
    reviewed_by: str | None = None
    human_decision: str | None = None


class AdoptionOut(BaseModel):
    """AI 권고 채택률. **사람이 판단한 것만 센다.**"""

    reviewed: int
    accepted: int
    pending: int
    #: `null` 은 0 이 아니라 "아직 말할 수 없음" 이다. 화면이 0% 로 그리면
    #: 사람이 전부 거절한 것처럼 보인다.
    rate: float | None = None


class SummaryOut(BaseModel):
    counts: dict[str, int]
    by_agent: dict[str, dict[str, int]]
    spent: int
    #: 조정자가 자동으로 통과시킨 비율. **채택률과 다른 숫자다.**
    policy_pass_rate: float | None = None
    adoption: AdoptionOut


class ReviewIn(BaseModel):
    intervention_id: int
    reviewer: str = Field(min_length=1)
    approve: bool
    reason: str = ""


class ReviewOut(BaseModel):
    ok: bool
    error: str | None = None
    intervention_id: int | None = None
    #: 사람이 뭐라 했나.
    human_decision: str | None = None
    #: 규칙까지 통과한 뒤의 최종 상태. **사람의 판단과 다를 수 있다.**
    final_decision: str | None = None
    executed: bool | None = None
    #: 사람은 승인했는데 규칙이 막았다면 그 이유.
    blocked: str | None = None


@app.get("/orchestration/summary", response_model=SummaryOut)
def orchestration_summary() -> SummaryOut:
    """콘솔 첫 화면. **두 비율을 따로 낸다.**

    예산이 모자라 거절된 제안은 "사람이 AI 를 안 믿었다" 가 아니다. 하나로 묶으면
    예산을 줄이는 것만으로 채택률이 떨어지고, 그 숫자를 보고 모델을 의심하게 된다.
    """
    s = _console.summary()
    return SummaryOut(
        counts=s.counts, by_agent=s.by_agent, spent=s.spent,
        policy_pass_rate=s.policy_pass_rate,
        adoption=AdoptionOut(reviewed=s.adoption.reviewed, accepted=s.adoption.accepted,
                             pending=s.adoption.pending, rate=s.adoption.rate),
    )


@app.get("/orchestration/recent", response_model=list[DecisionRow])
def orchestration_recent(limit: int = 50, decision: str | None = None) -> list[DecisionRow]:
    """최근 결정. **실행된 것만 보면 통제가 안 보인다.**"""
    want = None
    if decision is not None:
        try:
            want = Decision(decision)
        except ValueError:
            raise HTTPException(400, f"그런 결정은 없습니다: {decision}")
    return [DecisionRow(**r) for r in _console.recent(limit=limit, decision=want)]


@app.get("/orchestration/pending", response_model=list[DecisionRow])
def orchestration_pending(limit: int = 100) -> list[DecisionRow]:
    """사람 승인 대기. 이미 판단한 건은 빠진다."""
    return [DecisionRow(**r) for r in _console.pending(limit=limit)]


@app.post("/orchestration/review", response_model=ReviewOut)
def orchestration_review(payload: ReviewIn) -> ReviewOut:
    """사람의 판단을 받는다. **승인해도 규칙은 그대로 걸린다.**

    대기 건은 묵는다. 그 사이 다른 에이전트가 그 단위를 가져갔다면 사람이
    승인했다는 이유로 한 단위 한 개입을 건너뛸 수 없다 — 그러면 사람의 손을 거친
    건이 오히려 측정을 깨는 통로가 된다. 그래도 **사람의 판단은 남긴다.**
    """
    return ReviewOut(**_console.review(
        payload.intervention_id, payload.reviewer, payload.approve, payload.reason))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "bookings": len(_store.bookings)}
