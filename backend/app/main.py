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

from dataclasses import dataclass
from datetime import date, datetime, timezone

from fastapi import FastAPI, Header, HTTPException
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, ConfigDict, Field

from app.agent.graph import build_graph
from app.domain import seed
from app.remote import (RemoteBookingUnavailable, RemoteStore, begin_request,
                        end_request)
from app.orchestration.console import Console
from app.orchestration.ledger import Decision, Ledger

app = FastAPI(title="Agent Customer Support", version="0.1.0")

_store = seed()
_checkpointer = MemorySaver()
_agent = build_graph(_store, today=date.today(), checkpointer=_checkpointer)

# 실제 예약(예약 서비스가 가진 것)을 다루는 그래프.
#
# 그래프를 둘로 나눈 이유가 있다. `Store` 는 그래프를 만들 때 묶이는데, 요청마다
# 어느 store 를 쓸지 갈라야 한다. 매 요청 그래프를 새로 만들면 체크포인터가
# 붙는 자리가 흔들린다 — 같은 체크포인터를 공유하되 store 만 다른 그래프를
# 두 개 두는 편이 단순하다.
_remote_store = RemoteStore()
_remote_agent = build_graph(_remote_store, today=date.today(), checkpointer=_checkpointer)


def _pick_agent(booking_id: str | None):
    """어느 store 로 볼 것인가.

    데모 예약은 `B1002`, 실제 예약은 `BK2608190016` 이다. 접두사로 가른다 —
    **번호 체계가 다르다는 사실 자체가 두 저장소가 다르다는 뜻**이라, 여기서
    굳이 감출 이유가 없다.
    """
    if booking_id and booking_id.startswith("BK"):
        return _remote_agent
    return _agent

# 개입 원장은 상담 상태와 **다른 저장소**다. 콘솔은 그걸 읽기만 한다 —
# 결정은 조정자가 하고, 여기서 규칙을 한 벌 더 쓰면 두 곳이 어긋난다.
_console = Console(Ledger())


def _cfg(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


@dataclass
class SessionRecord:
    """누가 어느 예약으로 문의를 열었나.

    체크포인터(`MemorySaver`)는 세션 **상태**를 들고 있지만 "어떤 세션들이
    있는가" 는 답하지 못한다. 콘솔이 승인 대기 목록을 그리려면 그 질문에 답할
    곳이 필요하다.

    **메모리에 둔다.** 체크포인터 자체가 메모리라, 이것만 파일에 남기면 재시작
    뒤에 "세션은 목록에 있는데 열면 없는" 상태가 된다. 두 저장소의 수명이
    어긋나는 것이 목록이 비는 것보다 나쁘다.
    """

    session_id: str
    booking_id: str | None
    opened_at: datetime
    last_message: str


_sessions: dict[str, SessionRecord] = {}


def _awaiting(session_id: str) -> bool:
    return _agent.get_state(_cfg(session_id)).next == ("execute",)


class MessageIn(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    #: 어느 예약에 대한 문의인가. **고객 화면에서 시작하면 이게 실린다.**
    #:
    #: 없으면 그래프가 문장에서 `B1002` 같은 패턴을 찾아낸다(`extract_booking_id`).
    #: 그 방식은 직원이 콘솔에서 타이핑할 때는 쓸 수 있지만, 고객에게 예약번호를
    #: 외워서 적으라고 할 수는 없다 — 오타 하나면 남의 예약을 조회하게 된다.
    booking_id: str | None = None


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
def send_message(body: MessageIn, authorization: str | None = Header(None)) -> AgentOut:
    payload: dict = {"message": body.message, "request_id": body.request_id, "trace": []}
    if body.booking_id:
        payload["booking_id"] = body.booking_id

    # 호출자의 토큰을 문맥에 싣는다. 원격 store 가 `/bookings/me` 를 부를 때
    # 이걸 쓴다 — **그래서 에이전트가 볼 수 있는 범위가 호출자 본인의 예약으로
    # 좁혀진다.** 권한 검사를 따로 짜는 것보다 애초에 못 보게 하는 편이 낫다.
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    scope = begin_request(token)
    try:
        state = _pick_agent(body.booking_id).invoke(payload, _cfg(body.session_id))
    except RemoteBookingUnavailable as e:
        # **"예약이 없다" 와 "예약 서비스에 못 닿았다" 는 다른 사실이다.**
        # 500 으로 흘리면 화면이 둘을 구분하지 못하고, 고객은 자기 예약이
        # 사라진 줄 안다.
        raise HTTPException(status_code=503, detail=str(e)) from e
    finally:
        end_request(scope)

    # 장부를 남긴다. 이미 있으면 마지막 문장만 갱신한다 — 대화가 이어져도
    # **연 시각은 처음 그대로**여야 대기 순서를 매길 수 있다.
    prev = _sessions.get(body.session_id)
    _sessions[body.session_id] = SessionRecord(
        session_id=body.session_id,
        booking_id=body.booking_id or (prev.booking_id if prev else None)
                   or state.get("booking_id"),
        opened_at=prev.opened_at if prev else datetime.now(timezone.utc),
        last_message=body.message,
    )
    return _out(body.session_id, state)


@app.post("/support/confirm", response_model=AgentOut)
def confirm(body: ConfirmIn, authorization: str | None = Header(None)) -> AgentOut:
    """고객 승인. **이 호출 없이는 상태 변경이 일어나지 않는다.**"""
    if not _awaiting(body.session_id):
        raise HTTPException(409, "확인 대기 중인 요청이 없습니다")
    if not body.approved:
        snap = _agent.get_state(_cfg(body.session_id)).values
        return AgentOut(session_id=body.session_id,
                        response="요청을 취소했습니다. 예약은 그대로 유지됩니다.",
                        awaiting_confirmation=False, escalated=False,
                        decision=snap.get("decision"))

    # 실행할 때도 **연 그래프와 같은 store** 여야 한다. 다른 store 로 재개하면
    # 조회는 실제 예약을 보고 취소는 데모 예약을 건드리게 된다.
    rec = _sessions.get(body.session_id)
    agent = _pick_agent(rec.booking_id if rec else None)

    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    scope = begin_request(token)
    try:
        state = agent.invoke(None, _cfg(body.session_id))
    except RemoteBookingUnavailable as e:
        # 아직 쓰기가 연결되지 않았다. **아무 일도 안 일어났는데 취소됐다고
        # 답하는 것이 최악이므로** 소리 내어 막는다.
        raise HTTPException(status_code=501, detail=str(e)) from e
    finally:
        end_request(scope)
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


class SessionSummary(BaseModel):
    """세션 한 줄. 콘솔의 대기 목록이 쓴다."""

    session_id: str
    booking_id: str | None = None
    opened_at: datetime
    last_message: str
    #: 사람 승인을 기다리는가. **이게 이 목록의 존재 이유다.**
    awaiting_confirmation: bool
    escalated: bool
    response: str


@app.get("/support/sessions", response_model=list[SessionSummary])
def list_sessions(awaiting: bool = False) -> list[SessionSummary]:
    """열린 문의 목록.

    `awaiting=true` 면 **사람 승인을 기다리는 것만** 준다. 콘솔의 "상담 승인"
    화면이 그리는 것이 그것이다 — 그 전까지는 승인할 대기 건 자체가 없어서
    화면 이름이 하는 말과 실제가 어긋나 있었다.

    최근에 열린 것이 위로 온다. 오래 기다린 것을 아래에 두는 건 이상해 보이지만,
    대기 목록은 보통 **새로 들어온 것부터** 처리하는 화면이 아니라 훑는
    화면이라 그렇다. 순서를 바꿔야 할 이유가 생기면 그때 바꾼다.
    """
    out: list[SessionSummary] = []
    for rec in _sessions.values():
        snap = _agent.get_state(_cfg(rec.session_id))
        if not snap.values:
            # 체크포인터에는 없는데 장부에만 있다 — 재시작 뒤에나 생기는 일이다.
            # 목록에 넣으면 열었을 때 404 가 난다.
            continue
        waiting = snap.next == ("execute",)
        if awaiting and not waiting:
            continue
        out.append(SessionSummary(
            session_id=rec.session_id,
            booking_id=rec.booking_id or snap.values.get("booking_id"),
            opened_at=rec.opened_at,
            last_message=rec.last_message,
            awaiting_confirmation=waiting,
            escalated=bool(snap.values.get("escalated")),
            response=snap.values.get("response", ""),
        ))
    return sorted(out, key=lambda r: r.opened_at, reverse=True)


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
