"""안전장치 검증 — 이 저장소의 핵심.

README 의 DoD 를 그대로 테스트로 옮긴 것이다.

- 상태 변경 전 반드시 고객 확인을 거친다
- 같은 취소 요청을 두 번 보내도 환불은 한 번만
- 환불 실패 시 취소가 롤백되거나 에스컬레이션된다
- 정책 조회 실패 시 추측 답변 대신 이관된다
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.agent.graph import build_graph, classify_intent
from app.domain import BookingStatus, RefundStatus, seed

TODAY = date(2025, 6, 10)


@pytest.fixture
def store():
    return seed(today=TODAY)


@pytest.fixture
def agent(store):
    return build_graph(store, today=TODAY, checkpointer=MemorySaver())


def cfg(tid: str) -> dict:
    return {"configurable": {"thread_id": tid}}


def start(agent, message: str, tid: str, request_id: str = "r1") -> dict:
    return agent.invoke(
        {"message": message, "request_id": request_id, "trace": []}, cfg(tid)
    )


# =============================================== ① 고객 확인 없이는 실행 불가
def test_graph_halts_before_state_change(agent, store):
    """confirm 다음에서 멈춰야 한다. 예약 상태는 그대로여야 한다."""
    out = start(agent, "B1002 예약 취소하고 환불받고 싶어요", "t1")
    state = agent.get_state(cfg("t1"))

    assert state.next == ("execute",), f"멈추지 않았다: {state.next}"
    assert store.get_booking("B1002").status is BookingStatus.CONFIRMED
    assert "환불됩니다" in out["response"]
    assert not out.get("executed")


def test_resume_after_confirmation_executes(agent, store):
    """고객이 승인해야 비로소 실행된다."""
    start(agent, "B1002 취소하고 환불해주세요", "t2")
    out = agent.invoke(None, cfg("t2"))          # ← 고객 승인

    b = store.get_booking("B1002")
    assert b.status is BookingStatus.CANCELLED
    assert b.refund_status is RefundStatus.REFUNDED
    assert out["verified"] is True
    assert "환불 처리되었습니다" in out["response"]


def test_no_path_reaches_execute_without_confirm(agent):
    """confirm 을 거치지 않고 execute 에 닿는 경로가 없어야 한다."""
    start(agent, "B1002 취소해주세요", "t3")
    trace_nodes = [t["node"] for t in agent.get_state(cfg("t3")).values["trace"]]
    assert "confirm" in trace_nodes
    assert "execute" not in trace_nodes


# ====================================================== ② 멱등성 — 환불 1회
def test_duplicate_write_refunds_only_once(store):
    """같은 멱등성 키로 쓰기 도구를 두 번 불러도 환불은 한 번.

    더블 클릭·네트워크 재시도처럼 **같은 요청이 두 번 도착하는** 상황이다.
    조회 후 실행 사이에 두 번째 요청이 끼어드는 경합을 저장소 제약이 막는다.
    """
    from app.agent.tools import WriteTools, idempotency_key

    write = WriteTools(store)
    key = idempotency_key("B1002", "cancel_and_refund", "REQ-1")

    first = write.cancel_and_refund("B1002", 240_000, key)
    second = write.cancel_and_refund("B1002", 240_000, key)

    assert first.ok and second.ok
    assert first.data.get("idempotent_replay") is not True
    assert second.data["idempotent_replay"] is True
    assert second.data["refund_amount"] == first.data["refund_amount"]

    refunds = [a for a in store.audit if a["action"] == "process_refund"]
    assert len(refunds) == 1, f"환불이 {len(refunds)}회 실행됐다"
    assert store.get_booking("B1002").refunded_amount == 240_000


def test_repeat_conversation_after_completion_is_blocked(store):
    """처리가 끝난 뒤 같은 요청이 다시 들어오면 재처리하지 않는다.

    멱등성 키 이전에, 상태 판단에서 먼저 걸러진다 (방어선이 두 겹).
    """
    agent = build_graph(store, today=TODAY, checkpointer=MemorySaver())
    start(agent, "B1002 취소", "d1", request_id="REQ-1")
    agent.invoke(None, cfg("d1"))
    assert store.get_booking("B1002").status is BookingStatus.CANCELLED

    agent2 = build_graph(store, today=TODAY, checkpointer=MemorySaver())
    out = start(agent2, "B1002 취소", "d2", request_id="REQ-2")

    assert out["decision"]["proceed"] is False
    assert agent2.get_state(cfg("d2")).next == ()   # execute 에 도달하지 않는다
    assert len([a for a in store.audit if a["action"] == "process_refund"]) == 1


# ============================================ ③ 환불 실패 → 롤백 / 에스컬레이션
def test_refund_failure_rolls_back_cancellation(store):
    """외부 PG 가 거절하면 취소를 되돌린다."""
    store.pg_should_fail = True
    agent = build_graph(store, today=TODAY, checkpointer=MemorySaver())

    start(agent, "B1002 취소하고 환불", "f1")
    out = agent.invoke(None, cfg("f1"))

    assert store.get_booking("B1002").status is BookingStatus.CONFIRMED, "롤백되지 않았다"
    assert out["escalated"] is True
    assert "상담원" in out["response"]


def test_compensation_failure_escalates_and_flags_human(store):
    """보상까지 실패하면 부분 상태를 남기고 사람에게 넘긴다."""
    store.pg_should_fail = True
    store.compensation_should_fail = True
    agent = build_graph(store, today=TODAY, checkpointer=MemorySaver())

    start(agent, "B1002 취소하고 환불", "f2")
    out = agent.invoke(None, cfg("f2"))

    assert out["escalated"] is True
    assert out["executed"]["needs_human"] is True


# ================================================ ④ 정책 조회 실패 → 추측 금지
def test_missing_policy_escalates_instead_of_guessing(agent, store):
    """B1004 는 정책이 등록되지 않은 숙소다."""
    out = start(agent, "B1004 취소하고 환불받고 싶어요", "p1")

    assert out["escalated"] is True
    assert "취소 정책" in out["escalation_reason"]
    # 추측성 안내 문구가 나오면 안 된다
    assert "전액 환불" not in out["response"]
    assert store.get_booking("B1004").status is BookingStatus.CONFIRMED


def test_unknown_booking_escalates(agent):
    out = start(agent, "B9999 취소해주세요", "p2")
    assert out["escalated"] is True


def test_unclear_intent_escalates(agent):
    """의도가 모호하면 지어내지 않고 넘긴다."""
    out = start(agent, "그냥 궁금한 게 있는데요", "p3")
    assert out["escalated"] is True


# =========================================================== ⑤ 판단 정확성
def test_refund_amount_follows_policy(agent, store):
    """FLEX 정책: 체크인 10일 전 → 전액 환불."""
    out = start(agent, "B1002 취소", "c1")
    assert out["decision"]["refund_amount"] == 240_000
    assert out["decision"]["refund_ratio"] == 1.0


def test_imminent_check_in_gets_partial_refund(agent, store):
    """B1001 은 내일 체크인 → FLEX 하위 구간(20%)."""
    out = start(agent, "B1001 취소하고 환불받고 싶어요", "c2")
    assert out["decision"]["refund_ratio"] == 0.2
    assert out["decision"]["refund_amount"] == 36_000


def test_strict_policy_differs(agent):
    """B1003 은 STRICT 정책, 체크인 5일 전 → 환불 불가."""
    out = start(agent, "B1003 취소", "c3")
    assert out["decision"]["refund_amount"] == 0


def test_already_cancelled_booking_is_not_reprocessed(agent, store):
    store.cancel("B1002")
    out = start(agent, "B1002 취소해주세요", "c4")
    assert out["decision"]["proceed"] is False


# ------------------------------------------------------------- 의도 분류
@pytest.mark.parametrize("msg,expected", [
    ("내일 체크인인데 취소하고 환불받고 싶어요", "CANCEL_REFUND"),
    ("예약 상태 확인해주세요", "LOOKUP"),
    ("체크인 언제인가요", "LOOKUP"),
    ("날씨가 좋네요", "UNKNOWN"),
])
def test_intent_classification(msg, expected):
    assert classify_intent(msg) == expected
