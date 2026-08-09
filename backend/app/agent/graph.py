"""LangGraph 상태 그래프.

    intent → plan → retrieve → decide → confirm ⏸ → execute → verify → respond
                                    ↘ escalate

``confirm`` 다음에서 그래프를 **중단**한다. 고객이 승인해야만 ``execute`` 가 돈다.
중단·재개를 직접 구현하지 않고 프레임워크 기본기로 쓰는 것이 LangGraph 를 택한 이유다.
Checkpointer 가 상태를 들고 있으므로 고객이 며칠 뒤 눌러도 세션이 살아 있다.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Any, Literal, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.tools import ReadTools, WriteTools, idempotency_key
from app.domain import Store


def _append(a: list, b: list) -> list:
    return (a or []) + (b or [])


class AgentState(TypedDict, total=False):
    """그래프가 들고 다니는 상태."""

    message: str
    request_id: str
    booking_id: str | None
    intent_type: str
    task_plan: list[str]
    facts: dict[str, Any]          # 조회로 수집한 사실
    decision: dict[str, Any]       # 판단 결과 (환불 가능 여부·금액)
    executed: dict[str, Any]       # 실행 결과
    verified: bool
    escalated: bool
    escalation_reason: str
    response: str
    trace: Annotated[list, _append]


# ------------------------------------------------------------------ 의도 분석
CANCEL_WORDS = ("취소", "환불", "캔슬")
LOOKUP_WORDS = ("확인", "조회", "언제", "얼마", "알려")


def classify_intent(message: str) -> str:
    """규칙 기반 의도 분류.

    LLM 을 붙일 수 있지만, 분류가 틀렸을 때의 비용이 큰 구간이라
    **결정적인 규칙을 기본값으로** 둔다. 애매하면 UNKNOWN 을 내고 사람에게 넘긴다.
    """
    m = message.strip()
    if any(w in m for w in CANCEL_WORDS):
        return "CANCEL_REFUND"
    if any(w in m for w in LOOKUP_WORDS):
        return "LOOKUP"
    return "UNKNOWN"


def extract_booking_id(message: str) -> str | None:
    m = re.search(r"\bB\d{4,}\b", message)
    return m.group(0) if m else None


# --------------------------------------------------------------------- 노드
def build_graph(store: Store, today: date | None = None, checkpointer=None,
                policy_retriever=None):
    # 정책 검색 색인은 그래프당 한 번만 만든다
    if policy_retriever is None:
        from app.agent.policy_rag import PolicyRetriever
        policy_retriever = PolicyRetriever(store)
    read = ReadTools(store, today=today, policy_retriever=policy_retriever)
    write = WriteTools(store)

    def n_intent(s: AgentState) -> dict:
        intent = classify_intent(s["message"])
        bid = s.get("booking_id") or extract_booking_id(s["message"])
        return {"intent_type": intent, "booking_id": bid,
                "trace": [{"node": "intent", "intent": intent, "booking_id": bid}]}

    def n_plan(s: AgentState) -> dict:
        if s["intent_type"] == "CANCEL_REFUND":
            plan = ["get_booking", "get_cancellation_policy", "calculate_refund",
                    "confirm", "cancel_and_refund", "verify"]
        elif s["intent_type"] == "LOOKUP":
            plan = ["get_booking"]
        else:
            plan = []
        return {"task_plan": plan, "trace": [{"node": "plan", "plan": plan}]}

    def n_retrieve(s: AgentState) -> dict:
        """조회 도구만 실행한다. 실패는 감추지 않는다."""
        facts: dict[str, Any] = {}
        bid = s.get("booking_id")
        if not bid:
            return {"facts": {}, "escalated": True,
                    "escalation_reason": "예약 번호를 확인하지 못했다",
                    "trace": [{"node": "retrieve", "error": "no_booking_id"}]}

        r = read.get_booking(bid)
        if not r.ok:
            return {"facts": {}, "escalated": True, "escalation_reason": r.error,
                    "trace": [{"node": "retrieve", "tool": "get_booking", "ok": False}]}
        facts["booking"] = r.data

        if s["intent_type"] == "CANCEL_REFUND":
            pol = read.get_cancellation_policy(r.data["property_id"])
            if not pol.ok:
                # Silent Fallback 금지 — 정책을 모르면 추측하지 않는다
                return {"facts": facts, "escalated": True,
                        "escalation_reason": pol.error,
                        "trace": [{"node": "retrieve", "tool": "get_cancellation_policy",
                                   "ok": False}]}
            facts["policy"] = pol.data

            calc = read.calculate_refund(bid)
            if not calc.ok:
                return {"facts": facts, "escalated": True,
                        "escalation_reason": calc.error,
                        "trace": [{"node": "retrieve", "tool": "calculate_refund",
                                   "ok": False}]}
            facts["refund"] = calc.data

        return {"facts": facts,
                "trace": [{"node": "retrieve", "tools": list(facts)}]}

    def n_decide(s: AgentState) -> dict:
        f = s.get("facts", {})
        b = f.get("booking", {})
        if b.get("status") == "CANCELLED":
            return {"decision": {"proceed": False, "reason": "이미 취소된 예약이다"},
                    "trace": [{"node": "decide", "proceed": False}]}
        refund = f.get("refund", {})
        decision = {
            "proceed": True,
            "refund_amount": refund.get("refund_amount", 0),
            "refund_ratio": refund.get("refund_ratio", 0.0),
            "policy": refund.get("policy", ""),
        }
        return {"decision": decision, "trace": [{"node": "decide", **decision}]}

    def n_confirm(s: AgentState) -> dict:
        """고객 확인 문구를 만든다. 이 노드 뒤에서 그래프가 멈춘다."""
        d = s.get("decision", {})
        b = s.get("facts", {}).get("booking", {})
        msg = (
            f"예약 {b.get('booking_id')} 을 취소하면 "
            f"{d.get('refund_amount', 0):,}원이 환불됩니다 "
            f"(정책: {d.get('policy', '-')}). 진행할까요?"
        )
        return {"response": msg, "trace": [{"node": "confirm", "awaiting_customer": True}]}

    def n_execute(s: AgentState) -> dict:
        """상태 변경. **고객 승인 이후에만 도달한다.**"""
        bid = s["booking_id"]
        amount = s.get("decision", {}).get("refund_amount", 0)
        key = idempotency_key(bid, "cancel_and_refund", s.get("request_id", "r0"))
        res = write.cancel_and_refund(bid, amount, key)
        if not res.ok:
            return {"executed": {"ok": False, **res.data}, "escalated": True,
                    "escalation_reason": res.error,
                    "trace": [{"node": "execute", "ok": False, "error": res.error}]}
        return {"executed": {"ok": True, **res.data},
                "trace": [{"node": "execute", "ok": True,
                           "replay": res.data.get("idempotent_replay", False)}]}

    def n_verify(s: AgentState) -> dict:
        """실행했다고 믿지 않고 **상태를 다시 읽어** 안내 내용과 대조한다."""
        bid = s["booking_id"]
        told = s.get("decision", {}).get("refund_amount", 0)
        r = read.get_booking(bid)
        actual = store.get_booking(bid)
        ok = (
            r.ok
            and r.data["status"] == "CANCELLED"
            and actual is not None
            and actual.refunded_amount == told
        )
        if not ok:
            return {"verified": False, "escalated": True,
                    "escalation_reason": "실행 결과가 안내 내용과 다르다",
                    "trace": [{"node": "verify", "ok": False}]}
        return {"verified": True, "trace": [{"node": "verify", "ok": True}]}

    def n_respond(s: AgentState) -> dict:
        if s.get("escalated"):
            return {"trace": [{"node": "respond", "skipped": True}]}
        if s.get("verified"):
            amt = s.get("executed", {}).get("refund_amount", 0)
            msg = f"예약이 취소되었고 {amt:,}원이 환불 처리되었습니다."
        elif s["intent_type"] == "LOOKUP":
            b = s.get("facts", {}).get("booking", {})
            msg = (f"예약 {b.get('booking_id')} 은 {b.get('status')} 상태이며 "
                   f"체크인까지 {b.get('days_until_check_in')}일 남았습니다.")
        else:
            msg = s.get("response", "요청을 처리했습니다.")
        return {"response": msg, "trace": [{"node": "respond"}]}

    def n_escalate(s: AgentState) -> dict:
        """근거가 부족하면 **추측하지 않고** 사람에게 넘긴다."""
        reason = s.get("escalation_reason", "판단 근거가 부족하다")
        msg = f"확인이 어려워 상담원에게 연결해 드리겠습니다. (사유: {reason})"
        return {"escalated": True, "response": msg,
                "trace": [{"node": "escalate", "reason": reason}]}

    # ------------------------------------------------------------- 라우팅
    def after_intent(s: AgentState) -> Literal["plan", "escalate"]:
        return "plan" if s["intent_type"] in ("CANCEL_REFUND", "LOOKUP") else "escalate"

    def after_retrieve(s: AgentState) -> Literal["decide", "escalate"]:
        return "escalate" if s.get("escalated") else "decide"

    def after_decide(s: AgentState) -> Literal["confirm", "respond", "escalate"]:
        if s.get("escalated"):
            return "escalate"
        if s["intent_type"] == "LOOKUP":
            return "respond"
        return "confirm" if s.get("decision", {}).get("proceed") else "respond"

    def after_execute(s: AgentState) -> Literal["verify", "escalate"]:
        return "escalate" if s.get("escalated") else "verify"

    def after_verify(s: AgentState) -> Literal["respond", "escalate"]:
        return "escalate" if s.get("escalated") else "respond"

    g = StateGraph(AgentState)
    for name, fn in [
        ("intent", n_intent), ("plan", n_plan), ("retrieve", n_retrieve),
        ("decide", n_decide), ("confirm", n_confirm), ("execute", n_execute),
        ("verify", n_verify), ("respond", n_respond), ("escalate", n_escalate),
    ]:
        g.add_node(name, fn)

    g.add_edge(START, "intent")
    g.add_conditional_edges("intent", after_intent,
                            {"plan": "plan", "escalate": "escalate"})
    g.add_edge("plan", "retrieve")
    g.add_conditional_edges("retrieve", after_retrieve,
                            {"decide": "decide", "escalate": "escalate"})
    g.add_conditional_edges("decide", after_decide,
                            {"confirm": "confirm", "respond": "respond",
                             "escalate": "escalate"})
    g.add_edge("confirm", "execute")
    g.add_conditional_edges("execute", after_execute,
                            {"verify": "verify", "escalate": "escalate"})
    g.add_conditional_edges("verify", after_verify,
                            {"respond": "respond", "escalate": "escalate"})
    g.add_edge("respond", END)
    g.add_edge("escalate", END)

    # ★ 상태 변경 직전에 멈춘다. 고객 승인 없이는 execute 가 돌지 않는다.
    return g.compile(
        checkpointer=checkpointer or MemorySaver(),
        interrupt_before=["execute"],
    )


__all__ = ["AgentState", "build_graph", "classify_intent", "extract_booking_id"]
