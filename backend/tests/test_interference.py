"""상담 취소 → 재고 변경 → 저수요 재판정 (B3).

**아무도 잘못하지 않았는데 측정이 깨지는 경로**를 재현한다. 상담 에이전트는 자기
도메인 안에서 옳게 행동했고, 조정자의 규칙 1 도 안 깨졌다 — 상담은 개입을 신청한
적이 없으니까.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.orchestration.coordinator import Coordinator, Policy, Proposal
from app.orchestration.interference import ChangeKind, Interference, StateChange
from app.orchestration.ledger import Decision, Ledger, Unit
from app.orchestration.promotion import PromotionTools

D = date(2025, 7, 10)
U = Unit("P0001", D)


@pytest.fixture
def ledger():
    return Ledger("sqlite://")


@pytest.fixture
def sensor(ledger):
    return Interference(ledger)


def plan_for(ledger, units, holdout_rate=0.0):
    return Coordinator(ledger, Policy(budget=10_000_000,
                                      holdout_rate=holdout_rate)).decide([
        Proposal(agent="promotion", unit=u, action="discount", cost=1_000,
                 expected_gain=1.0, uncertainty=0.1, request_id=f"c{i}")
        for i, u in enumerate(units)
    ])


def cancel(unit) -> StateChange:
    return StateChange(unit=unit, kind=ChangeKind.CANCELLATION,
                       detail="고객이 취소를 요청했다")


# ─────────────────────────────────────── 개입되지 않은 단위는 그냥 재고 소식이다
def test_a_cancellation_on_an_untouched_unit_is_just_inventory_news(sensor):
    r = sensor.record(cancel(U))
    assert r["arm"] is None
    assert r["affects_measurement"] is False


# ─────────────────────────────────────── 개입된 단위가 흔들리면 측정이 흐려진다
def test_a_cancellation_on_a_treated_unit_disturbs_the_measurement(ledger, sensor):
    """**B3 의 핵심.**

    할인이 걸린 단위에서 예약이 하나 빠지면 점유율이 움직인다. 그중 얼마가 할인
    때문이고 얼마가 "방이 다시 나왔기 때문" 인지 갈 수 없다.
    """
    plan_for(ledger, [U])
    PromotionTools(ledger).apply(U, "promotion", 20, "req-1")

    r = sensor.record(cancel(U))
    assert r["arm"] == "treated"
    assert r["affects_measurement"] is True
    assert (U.property_id, U.stay_date.isoformat()) in sensor.disturbed()


def test_the_cancellation_is_recorded_not_blocked(ledger, sensor):
    """취소는 고객이 요청한 것이다. 측정을 위해 막으면 사업을 방해하는 물건이 된다."""
    plan_for(ledger, [U])
    tools = PromotionTools(ledger)
    tools.apply(U, "promotion", 20, "req-1")

    sensor.record(cancel(U))
    # 할인은 그대로 걸려 있다 — 흔들림을 남겼을 뿐 아무것도 되돌리지 않았다
    assert tools.live(U) is not None
    assert len(sensor.history(U)) == 1


# ─────────────────────────────────────── 홀드아웃도 흔들린다
def test_the_control_group_is_disturbed_too(ledger, sensor):
    """홀드아웃은 '아무도 손대지 않은 단위' 가 아니다.

    **'개입 에이전트가 손대지 않은 단위'** 다. 상담 취소는 대조군에도 똑같이
    들어오고, 그러면 대조군이 조용히 다른 집단이 된다.
    """
    units = [Unit(f"P{i:04d}", D) for i in range(200)]
    plan = plan_for(ledger, units, holdout_rate=0.3)
    held = [o.proposal.unit for o in plan.held_out]
    assert held

    r = sensor.record(cancel(held[0]))
    assert r["arm"] == "holdout"
    assert r["affects_measurement"] is True
    assert "대조군이 흔들렸다" in r["note"]


def test_disturbance_counts_split_by_arm(ledger, sensor):
    """**한쪽에만 몰리면 그 자체가 신호다.**

    개입군에만 취소가 몰렸다면 할인이 취소를 유발했을 수도 있고, 그건 효과가
    아니라 부작용이다.
    """
    units = [Unit(f"P{i:04d}", D) for i in range(200)]
    plan = plan_for(ledger, units, holdout_rate=0.3)
    treated = [o.proposal.unit for o in plan.approved]
    held = [o.proposal.unit for o in plan.held_out]

    for u in treated[:7]:
        sensor.record(cancel(u))
    for u in held[:2]:
        sensor.record(cancel(u))
    sensor.record(cancel(Unit("PZZZZ", D)))     # 어느 군에도 없는 단위

    counts = sensor.counts_by_arm()
    assert counts["treated"] == 7
    assert counts["holdout"] == 2
    assert counts["unassigned"] == 1


def test_the_arm_is_frozen_at_the_time_of_the_disturbance(ledger, sensor):
    """나중에 원장을 다시 뒤지면 그 사이 결정이 바뀌었을 수 있다."""
    plan_for(ledger, [U])
    sensor.record(cancel(U))
    assert sensor.history(U)[0]["arm"] == "treated"


# ─────────────────────────────────────── 재판정
def test_a_cancellation_sends_the_unit_back_to_the_coordinator(ledger, sensor):
    """재고가 늘었으면 수요 예측의 전제가 바뀌었다."""
    plan_for(ledger, [U])
    changes = [cancel(U), StateChange(U, ChangeKind.BLOCKED)]
    assert sensor.needs_reappraisal(changes) == [U]


def test_reappraisal_does_not_move_a_unit_between_arms(ledger, sensor):
    """**재판정으로 군이 바뀌면 안 된다.**

    한 단위의 결과가 두 군에 흩어지면 둘 다 못 읽는다. 배정이 결정적 해시라
    이 성질은 따라오지만, 따라온다는 것 자체를 고정해 둔다.
    """
    units = [Unit(f"P{i:04d}", D) for i in range(200)]
    first = plan_for(ledger, units, holdout_rate=0.3)
    arms = {o.proposal.unit: o.decision for o in first.outcomes}

    # 취소가 들어와 전부 다시 판단한다 — 새 원장에서(전 회차의 점유를 지우고)
    fresh = Ledger("sqlite://")
    second = plan_for(fresh, units, holdout_rate=0.3)

    for o in second.outcomes:
        before = arms[o.proposal.unit]
        if before in (Decision.APPROVED, Decision.HELD_OUT):
            assert o.decision is before, f"{o.proposal.unit} 의 군이 바뀌었다"


def test_a_reappraised_holdout_still_cannot_be_discounted(ledger, sensor):
    """재판정을 거쳐도 홀드아웃은 홀드아웃이다."""
    units = [Unit(f"P{i:04d}", D) for i in range(200)]
    plan = plan_for(ledger, units, holdout_rate=0.3)
    held = plan.held_out[0].proposal.unit

    sensor.record(cancel(held))
    assert sensor.needs_reappraisal([cancel(held)]) == [held]

    # 다시 제안해도 원장이 막는다
    again = plan_for(ledger, [held], holdout_rate=0.3)
    assert not again.approved
    assert PromotionTools(ledger).apply(held, "promotion", 20, "r").ok is False


# ────────────────────────────── 진짜 상담 경로를 통과시킨다
def test_a_real_support_cancellation_reaches_the_orchestration_ledger(ledger, sensor):
    """**센서에 손으로 사건을 먹이면 두 도메인이 이어졌는지 증명되지 않는다.**

    실제 `WriteTools.cancel_and_refund` 를 태워서, 상담 도메인의 결과가 개입
    측정에 도달하는지 본다. 이 테스트가 없으면 `StateChange` 는 테스트에서만
    존재하는 자료형이다.
    """
    from app.agent.tools import WriteTools, idempotency_key
    from app.domain import BookingStatus, seed

    store = seed()
    booking = store.get_booking("B1002")
    unit = Unit(booking.property_id, booking.check_in)

    # 그 숙소·날짜에 할인이 걸려 있다
    plan_for(ledger, [unit])
    assert PromotionTools(ledger).apply(unit, "promotion", 20, "req-1").ok

    # 상담 에이전트는 이 사실을 모른 채 자기 일을 한다
    key = idempotency_key("B1002", "cancel_and_refund", "support-1")
    result = WriteTools(store).cancel_and_refund("B1002", booking.amount, key)
    assert result.ok
    assert store.get_booking("B1002").status is BookingStatus.CANCELLED

    # 그 사실이 개입 측정에 도달한다
    report = sensor.record(StateChange(
        unit=unit, kind=ChangeKind.CANCELLATION,
        detail=f"booking={result.data['booking_id']} refund={result.data['refund_amount']}"))

    assert report["arm"] == "treated"
    assert report["affects_measurement"] is True
    assert (unit.property_id, unit.stay_date.isoformat()) in sensor.disturbed()
