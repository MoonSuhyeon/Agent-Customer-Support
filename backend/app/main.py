"""FastAPI — Agent API.

그래프는 ``confirm`` 다음에서 멈춘다. 그래서 대화 API 와 **승인 API 가 분리**된다.
클라이언트는 승인 화면을 띄우고, 고객이 누르면 ``/support/confirm`` 을 호출한다.

    POST /support/messages        문의 전송 → 확인 대기 또는 완료
    POST /support/confirm         고객 승인 → 상태 변경 실행
    GET  /support/sessions/{id}   현재 상태와 트레이스

상담 콘솔(``/``)은 같은 프로세스에서 서버 렌더링으로 붙는다. 그래프를 실행하는
함수를 콘솔에 넘겨주므로, 화면과 API 가 서로 다른 경로로 갈라지지 않는다.
"""
from __future__ import annotations

from datetime import date

from fastapi import FastAPI, HTTPException
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field

from app.agent.graph import build_graph
from app.console import build_router as build_console_router
from app.domain import seed

app = FastAPI(title="Agent Customer Support", version="0.1.0")

_store = seed()
_checkpointer = MemorySaver()
_agent = build_graph(_store, today=date.today(), checkpointer=_checkpointer)


def _cfg(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def _awaiting(session_id: str) -> bool:
    return _agent.get_state(_cfg(session_id)).next == ("execute",)


def _invoke(session_id: str, message: str, request_id: str) -> dict:
    return _agent.invoke(
        {"message": message, "request_id": request_id, "trace": []}, _cfg(session_id)
    )


def _resume(session_id: str, approved: bool) -> dict:
    """승인이면 멈춘 지점에서 이어서, 거절이면 그대로 둔다."""
    snap = _agent.get_state(_cfg(session_id))
    if not _awaiting(session_id) or not approved:
        return snap.values
    return _agent.invoke(None, _cfg(session_id))


class MessageIn(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    request_id: str = Field(min_length=1)


class ConfirmIn(BaseModel):
    session_id: str
    approved: bool = True


class AgentOut(BaseModel):
    session_id: str
    response: str
    awaiting_confirmation: bool
    escalated: bool
    verified: bool = False
    decision: dict | None = None


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


@app.get("/support/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    snap = _agent.get_state(_cfg(session_id))
    if not snap.values:
        raise HTTPException(404, "세션을 찾을 수 없습니다")
    return {
        "session_id": session_id,
        "awaiting_confirmation": snap.next == ("execute",),
        "next_nodes": list(snap.next),
        "response": snap.values.get("response", ""),
        "escalated": bool(snap.values.get("escalated")),
        "trace": snap.values.get("trace", []),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "bookings": len(_store.bookings)}


# 상담 콘솔. API 와 같은 그래프·같은 체크포인터를 쓴다.
app.include_router(build_console_router(_agent, _store, invoke=_invoke, resume=_resume))
