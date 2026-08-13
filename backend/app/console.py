"""상담 콘솔 — FastAPI + Jinja2 + HTMX.

에이전트가 멈추는 지점(``interrupt_before=["execute"]``)을 사람이 보는 화면으로
만든 것이다. 이 저장소가 보여주려는 장면이 그것 하나라 화면도 그것만 한다.

**JS 프레임워크를 쓰지 않는다.** 승인 엔드포인트가 이미 이 프로세스 안에 있어서,
별도 앱을 세우면 빌드·CORS·인증을 한 번 더 만들어야 한다.

**HTMX 없이도 동작한다.** 폼은 평범한 ``POST`` 이고, 라우트는 ``HX-Request``
헤더가 있을 때만 조각을 돌려준다. 없으면 전체 페이지를 다시 그린다. CDN 이
막힌 환경에서도 콘솔이 죽지 않는다.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _thread(agent, session_id: str) -> dict[str, Any]:
    """현재 세션 상태를 화면에 필요한 모양으로 정리한다."""
    snap = agent.get_state({"configurable": {"thread_id": session_id}})
    values = snap.values or {}
    return {
        "session_id": session_id,
        "started": bool(values),
        "response": values.get("response", ""),
        "awaiting": snap.next == ("execute",),
        "escalated": bool(values.get("escalated")),
        "verified": bool(values.get("verified")),
        "decision": values.get("decision") or {},
        "trace": values.get("trace", []),
    }


def build_router(agent, store, *, invoke: Callable, resume: Callable) -> APIRouter:
    """콘솔 라우터.

    에이전트 호출은 ``main`` 이 넘겨준 함수를 쓴다. 콘솔이 그래프 실행 규칙을
    따로 갖고 있으면 API 와 콘솔이 서로 다르게 동작할 수 있다.
    """
    router = APIRouter(tags=["Console"])

    def _render(request: Request, session_id: str) -> HTMLResponse:
        ctx = {
            "request": request,
            "bookings": sorted(store.bookings.values(), key=lambda b: b.booking_id),
            "properties": store.properties,
            **_thread(agent, session_id),
        }
        # HTMX 요청이면 바뀐 부분만, 아니면 전체 페이지
        name = "_thread.html" if request.headers.get("HX-Request") else "console.html"
        return TEMPLATES.TemplateResponse(request, name, ctx)

    @router.get("/", include_in_schema=False)
    def home() -> RedirectResponse:
        return RedirectResponse(f"/console/{uuid.uuid4().hex[:8]}", status_code=303)

    @router.get("/console/{session_id}", response_class=HTMLResponse, include_in_schema=False)
    def console(request: Request, session_id: str) -> HTMLResponse:
        return _render(request, session_id)

    @router.post("/console/{session_id}/send", response_class=HTMLResponse, include_in_schema=False)
    def send(request: Request, session_id: str, message: str = Form(...)) -> HTMLResponse:
        # 요청마다 새 멱등성 키. 같은 문의를 두 번 보내면 두 건으로 취급된다 —
        # 중복 방지는 '실행' 단계에서 저장소 유일성으로 막는다.
        invoke(session_id, message, uuid.uuid4().hex)
        return _render(request, session_id)

    @router.post("/console/{session_id}/decide", response_class=HTMLResponse, include_in_schema=False)
    def decide(request: Request, session_id: str, approved: str = Form(...)) -> HTMLResponse:
        resume(session_id, approved == "yes")
        return _render(request, session_id)

    return router
