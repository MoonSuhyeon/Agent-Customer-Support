"""FastAPI — Agent API.

그래프는 ``confirm`` 다음에서 멈춘다. 그래서 대화 API 와 **승인 API 가 분리**된다.
클라이언트는 승인 화면을 띄우고, 고객이 누르면 ``/support/confirm`` 을 호출한다.

    POST /support/messages        문의 전송 → 확인 대기 또는 완료
    POST /support/confirm         고객 승인 → 상태 변경 실행
    GET  /support/sessions/{id}   현재 상태와 트레이스

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

app = FastAPI(title="Agent Customer Support", version="0.1.0")

_store = seed()
_checkpointer = MemorySaver()
_agent = build_graph(_store, today=date.today(), checkpointer=_checkpointer)


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


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "bookings": len(_store.bookings)}
