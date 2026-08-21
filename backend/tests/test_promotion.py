"""프로모션 쓰기 도구(A3).

멱등성은 이 도구의 절반이다. 나머지 절반은 **원장의 결정 없이는 아무것도 하지
않는다** 는 것이고, 그게 홀드아웃을 권고에서 강제로 바꾼다.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.orchestration.coordinator import Coordinator, Policy, Proposal
from app.orchestration.ledger import Decision, Ledger, Unit
from app.orchestration.promotion import PromotionTools, promotion_key

D = date(2025, 7, 10)
U = Unit("P0001", D)


@pytest.fixture
def ledger():
    return Ledger("sqlite://")     # 인메모리


@pytest.fixture
def tools(ledger):
    return PromotionTools(ledger)


def approve(ledger, unit=U, agent="promotion"):
    """조정자를 거쳐 승인 상태를 만든다.

    원장에 직접 행을 쓰지 않는다. 그러면 조정자가 실제로 그런 결정을 내는지와
    무관하게 테스트가 통과하고, 두 쪽이 어긋나도 아무 데서도 안 걸린다.
    """
    plan = Coordinator(ledger, Policy(budget=1_000_000, holdout_rate=0.0)).decide([
        Proposal(agent=agent, unit=unit, action="discount", cost=10_000,
                 expected_gain=1.0, uncertainty=0.1, request_id=f"c-{unit}-{agent}")
    ])
    assert plan.approved
    return plan


# ─────────────────────────────────────────────── 멱등성
def test_the_same_request_twice_discounts_once(ledger, tools):
    """**A3 의 검증선.** 재시도는 정상 동작이지 오류가 아니다."""
    approve(ledger)
    first = tools.apply(U, "promotion", 20, "req-1")
    second = tools.apply(U, "promotion", 20, "req-1")

    assert first.ok and second.ok
    assert second.data["idempotent_replay"] is True
    assert first.data["key"] == second.data["key"]
    assert len(tools.history(U)) == 1, "같은 요청이 두 행을 만들면 안 된다"


def test_a_replay_does_not_change_the_discount(ledger, tools):
    """두 번째 호출의 할인율이 달라도 첫 번째가 이긴다.

    멱등성은 "같은 결과를 돌려준다" 이지 "다시 실행한다" 가 아니다. 여기서
    덮어쓰면 재시도가 조용히 값을 바꾸는 통로가 된다.
    """
    approve(ledger)
    tools.apply(U, "promotion", 20, "req-1")
    again = tools.apply(U, "promotion", 50, "req-1")
    assert again.data["discount_pct"] == 20


def test_a_different_request_id_is_a_different_request(ledger, tools):
    """다른 요청은 멱등성으로 막지 않는다 — 살아 있는 프로모션이 막는다."""
    approve(ledger)
    tools.apply(U, "promotion", 20, "req-1")
    other = tools.apply(U, "promotion", 30, "req-2")
    assert not other.ok
    assert "이미 살아 있는" in other.error


def test_the_key_binds_the_unit_and_the_agent():
    """`request_id` 만 쓰면 한쪽 결과가 다른 쪽으로 샌다."""
    k = promotion_key(U, "promotion", "r")
    assert k != promotion_key(U, "content", "r")
    assert k != promotion_key(Unit("P0002", D), "promotion", "r")
    assert k != promotion_key(Unit("P0001", date(2025, 7, 11)), "promotion", "r")


# ─────────────────────────────────────────────── 원장이 통제한다
def test_a_unit_the_coordinator_never_saw_is_refused(tools):
    """조정자를 거치지 않은 호출은 실행되지 않는다."""
    r = tools.apply(U, "promotion", 20, "req-1")
    assert not r.ok
    assert "조정자의 결정이 없는" in r.error
    assert tools.live(U) is None


def test_a_held_out_unit_cannot_be_discounted(ledger, tools):
    """**홀드아웃을 권고에서 강제로 바꾸는 테스트.**

    이게 없으면 재시도 스크립트 하나로 대조군이 오염되고, 그 사실이 아무 데도
    안 남는다.
    """
    units = [Unit(f"P{i:04d}", D) for i in range(200)]
    plan = Coordinator(ledger, Policy(budget=10_000_000, holdout_rate=0.3)).decide([
        Proposal(agent="promotion", unit=u, action="discount", cost=1_000,
                 expected_gain=1.0, uncertainty=0.1, request_id=f"c{i}")
        for i, u in enumerate(units)
    ])
    held = [o.proposal.unit for o in plan.held_out]
    assert held

    r = tools.apply(held[0], "promotion", 20, "req-1")
    assert not r.ok
    assert r.data["held_out"] is True
    assert tools.live(held[0]) is None


def test_a_deferred_unit_waits_for_the_human(ledger, tools):
    """사람 승인 대기는 승인이 아니다."""
    Coordinator(ledger, Policy(budget=1_000_000, autonomy_uncertainty_max=0.1,
                               holdout_rate=0.0)).decide([
        Proposal(agent="promotion", unit=U, action="discount", cost=10_000,
                 expected_gain=1.0, uncertainty=0.9, request_id="c1")
    ])
    r = tools.apply(U, "promotion", 20, "req-1")
    assert not r.ok
    assert tools.live(U) is None


def test_an_agent_cannot_execute_another_agents_approval(ledger, tools):
    """남의 승인으로 실행하면 원장의 "누가" 가 거짓이 된다."""
    approve(ledger, agent="promotion")
    r = tools.apply(U, "content", 20, "req-1")
    assert not r.ok
    assert "promotion 에게 났다" in r.error


# ─────────────────────────────────────────────── 되돌리기는 원상복구가 아니다
def test_revert_keeps_the_row(ledger, tools):
    """지우면 걸려 있던 구간이 사라지고, 그 구간의 예약이 아무 데도 안 붙는다."""
    approve(ledger)
    tools.apply(U, "promotion", 20, "req-1")
    r = tools.revert(U, "req-2", reason="수요가 회복됐다")

    assert r.ok
    assert r.data["live"] is False
    assert r.data["reverted_at"] is not None
    assert r.data["exposed_seconds"] >= 0
    assert len(tools.history(U)) == 1, "행이 지워졌다"
    assert tools.live(U) is None


def test_revert_reports_that_it_is_not_an_undo(ledger, tools):
    approve(ledger)
    tools.apply(U, "promotion", 20, "req-1")
    r = tools.revert(U, "req-2")
    assert "원상복구가 아니다" in r.data["note"]


def test_reverting_twice_is_not_an_error(ledger, tools):
    approve(ledger)
    tools.apply(U, "promotion", 20, "req-1")
    tools.revert(U, "req-2")
    again = tools.revert(U, "req-3")
    assert again.ok
    assert again.data["already_reverted"] is True


def test_reverting_what_was_never_applied_is_a_failure(tools):
    """이미 내린 것과 애초에 없던 것은 **다른 사실이다.**"""
    r = tools.revert(U, "req-1")
    assert not r.ok
    assert "걸린 프로모션이 없다" in r.error


def test_a_unit_can_be_discounted_again_after_a_revert(ledger, tools):
    """살아 있는 것만 하나여야 한다 — 내린 것이 다음을 막으면 안 된다."""
    approve(ledger)
    tools.apply(U, "promotion", 20, "req-1")
    tools.revert(U, "req-2")
    again = tools.apply(U, "promotion", 30, "req-3")

    assert again.ok
    assert again.data["discount_pct"] == 30
    hist = tools.history(U)
    assert len(hist) == 2
    assert [h["live"] for h in hist] == [False, True]


# ─────────────────────────────────────────────── 입력
def test_a_nonsense_discount_is_refused(ledger, tools):
    approve(ledger)
    assert not tools.apply(U, "promotion", 0, "r").ok
    assert not tools.apply(U, "promotion", 101, "r").ok
    assert not tools.apply(U, "promotion", -5, "r").ok
    assert tools.live(U) is None


def test_promotions_survive_a_restart(tmp_path):
    """프로세스가 죽어도 걸린 할인은 걸린 채다. 원장과 같은 요구다."""
    url = f"sqlite:///{tmp_path / 'led.db'}"
    l1 = Ledger(url)
    approve(l1)
    PromotionTools(l1).apply(U, "promotion", 20, "req-1")

    live = PromotionTools(Ledger(url)).live(U)
    assert live is not None and live["discount_pct"] == 20
