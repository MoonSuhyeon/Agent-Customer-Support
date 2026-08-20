"""개입 원장(B1)과 조정자(B2).

`docs/multi-agent-orchestration.md` 가 바꾼 문장을 코드로 고정한다 —
**오케스트레이터는 에이전트를 부르는 라우터가 아니라 개입을 배분하는 조정자다.**

라우터는 "이 요청은 누구 담당?" 을 답하고 그건 if 문이다. 조정자는 "둘 다 하고
싶어 하는데 누가 하나?" 를 답한다.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.orchestration.coordinator import Coordinator, Policy, Proposal
from app.orchestration.ledger import Decision, Ledger, Unit

D = date(2025, 7, 10)
U1, U2 = Unit("P0001", D), Unit("P0002", D)


@pytest.fixture
def ledger(tmp_path):
    return Ledger(f"sqlite:///{tmp_path / 'led.db'}")


def prop(agent="promotion", unit=U1, cost=10_000, gain=1.0, unc=0.1, rid=None,
         action="discount") -> Proposal:
    return Proposal(agent=agent, unit=unit, action=action, cost=cost,
                    expected_gain=gain, uncertainty=unc,
                    request_id=rid or f"{agent}-{unit}-{action}")


def coord(ledger, **policy) -> Coordinator:
    base = dict(budget=1_000_000, autonomy_uncertainty_max=0.35, min_efficiency=0.0)
    base.update(policy)
    return Coordinator(ledger, Policy(**base))


# ─────────────────────────────── 규칙 1: 한 단위 한 개입
def test_two_agents_wanting_the_same_unit_do_not_both_get_it():
    """**이 한 줄이 홀드아웃 설계를 살린다.**

    같은 숙소·날짜에 할인과 콘텐츠가 동시에 들어가면 점유율이 올라도 어느 쪽
    때문인지 모른다.
    """
    l = Ledger("sqlite://")     # 인메모리
    plan = coord(l).decide([
        prop(agent="promotion", gain=1.0, rid="a"),
        prop(agent="content", gain=0.5, rid="b"),
    ])
    assert len(plan.approved) == 1
    assert plan.approved[0].proposal.agent == "promotion"
    loser = next(o for o in plan.outcomes if o.proposal.agent == "content")
    assert loser.decision is Decision.SUPERSEDED


def test_a_contested_unit_goes_to_the_biggest_effect_not_the_cheapest():
    """**경합과 예산은 다른 질문이다.**

    둘 다 효율(1원당 효과)로 세우면 공짜 개입의 효율이 무한대라 기대 효과 0.05 가
    2.0 을 이긴다. 그리고 규칙 1 때문에 이긴 쪽이 그 단위를 **막으므로**, 가장
    값싼 개입이 가장 값진 개입을 밀어낸다. 시연을 돌려 보고서야 드러난 결함이다.

    단위 하나에서는 "그 단위에서 가장 좋은 결과" 를 원하는 것이지 싼 걸 원하는
    게 아니다.
    """
    l = Ledger("sqlite://")
    plan = coord(l).decide([
        prop(agent="content", unit=U1, cost=0, gain=0.05, rid="cheap"),
        prop(agent="promotion", unit=U1, cost=10_000, gain=2.0, rid="valuable"),
    ])
    assert [o.proposal.agent for o in plan.approved] == ["promotion"]
    loser = next(o for o in plan.outcomes if o.proposal.agent == "content")
    assert "기대 효과가 큰 제안이 가져갔다" in loser.reason


def test_different_units_do_not_collide():
    l = Ledger("sqlite://")
    plan = coord(l).decide([prop(unit=U1, rid="a"), prop(unit=U2, rid="b")])
    assert len(plan.approved) == 2


def test_a_unit_already_taken_in_an_earlier_batch_stays_taken(ledger):
    """회차가 달라도 마찬가지다. 원장이 프로세스를 넘어 기억한다."""
    coord(ledger).decide([prop(rid="first")])
    plan = coord(ledger).decide([prop(agent="content", rid="second")])
    assert not plan.approved
    assert plan.outcomes[0].decision is Decision.SUPERSEDED


def test_the_database_enforces_it_not_the_application(ledger):
    """애플리케이션 검사는 경합에서 진다. 부분 유니크 인덱스가 최종 보루다."""
    assert ledger.write(U1, "promotion", "discount", Decision.APPROVED, "", "r1", 100)
    # 검사를 건너뛰고 직접 두 번째 승인을 넣어 본다
    assert not ledger.write(U1, "content", "copy", Decision.APPROVED, "", "r2", 100)
    # 거절·보류는 여럿이어도 된다 — 조건부 인덱스인 이유다
    assert ledger.write(U1, "content", "copy", Decision.REJECTED, "예산", "r3", 0)
    assert ledger.write(U1, "content", "copy", Decision.DEFERRED, "불확실", "r4", 0)


# ─────────────────────────────── 규칙 2: 공유 예산
def test_budget_is_shared_across_agents():
    """에이전트마다 지갑이 따로면 총액을 통제할 수 없다."""
    l = Ledger("sqlite://")
    plan = coord(l, budget=25_000).decide([
        prop(agent="promotion", unit=U1, cost=10_000, gain=1.0, rid="a"),
        prop(agent="content", unit=U2, cost=10_000, gain=1.0, rid="b"),
        prop(agent="promotion", unit=Unit("P0003", D), cost=10_000, gain=1.0, rid="c"),
    ])
    assert len(plan.approved) == 2
    assert plan.spent == 20_000
    rejected = [o for o in plan.outcomes if o.decision is Decision.REJECTED]
    assert rejected and "예산 초과" in rejected[0].reason


def test_efficiency_decides_the_budget_across_different_units():
    """**서로 다른 단위** 사이에서 돈을 나눌 때는 효율이 맞는 기준이다.

    경합(같은 단위)과 달리 여기서는 1원당 얼마를 얻느냐를 물어야 한다.
    그리고 선착순이 아니다 — 먼저 온 제안이 예산을 다 쓰면 더 좋은 게 밀린다.
    """
    l = Ledger("sqlite://")
    plan = coord(l, budget=10_000).decide([
        prop(agent="content", unit=U1, cost=10_000, gain=1.0, rid="first"),   # 효율 0.0001
        prop(agent="promotion", unit=U2, cost=1_000, gain=1.0, rid="second"),  # 효율 0.001
    ])
    assert [o.proposal.agent for o in plan.approved] == ["promotion"]


def test_spending_from_earlier_batches_counts(ledger):
    """예산은 회차가 아니라 기간에 걸린다. 회차마다 초기화되면 상한이 없다."""
    coord(ledger, budget=20_000).decide([prop(unit=U1, cost=15_000, rid="a")])
    plan = coord(ledger, budget=20_000).decide([prop(unit=U2, cost=15_000, rid="b")])
    assert not plan.approved
    assert "예산 초과" in plan.outcomes[0].reason


def test_a_rejected_proposal_does_not_spend(ledger):
    """안 쓴 돈은 안 센다. 세면 거절이 예산을 갉아먹는다."""
    coord(ledger, budget=5_000).decide([prop(cost=10_000, rid="a")])
    assert ledger.spent() == 0


# ─────────────────────────────── 규칙 3: 자율성은 조정자가 정한다
def test_an_uncertain_prediction_goes_to_a_human():
    """`ML 의 구간별 오차가 자율성 수준을 정한다` — 그 문장의 구현이다."""
    l = Ledger("sqlite://")
    plan = coord(l, autonomy_uncertainty_max=0.30).decide([prop(unc=0.52, rid="a")])
    assert not plan.approved
    o = plan.outcomes[0]
    assert o.decision is Decision.DEFERRED
    assert "사람이 봐야 한다" in o.reason


def test_a_confident_prediction_runs_itself():
    l = Ledger("sqlite://")
    plan = coord(l, autonomy_uncertainty_max=0.30).decide([prop(unc=0.10, rid="a")])
    assert len(plan.approved) == 1


def test_the_agent_does_not_set_its_own_autonomy():
    """제안에 '나는 자동 실행해도 된다' 는 필드가 없다.

    각 에이전트가 자기 권한을 주장하면 통제가 없다 — 구조로 막는다.
    """
    assert "autonomous" not in Proposal.__dataclass_fields__
    assert "approve" not in dir(Proposal)


# ─────────────────────────────── 거절도 남긴다
def test_rejections_are_recorded_with_a_reason(ledger):
    """실행된 것만 남기면 "AI 가 뭘 하려 했는데 정책이 막았나" 를 못 본다."""
    coord(ledger, budget=1_000).decide([prop(cost=10_000, rid="a")])
    counts = ledger.counts()
    assert counts.get("REJECTED") == 1
    assert ledger.by_agent()["promotion"]["REJECTED"] == 1


def test_the_same_request_twice_is_recorded_once(ledger):
    """재시도는 정상 동작이다. 두 번 세면 거절률이 부풀고 예산도 틀어진다."""
    assert ledger.write(U1, "promotion", "discount", Decision.REJECTED, "r", "same")
    assert not ledger.write(U1, "promotion", "discount", Decision.REJECTED, "r", "same")


def test_ordering_is_deterministic():
    """같은 입력에 같은 답이 나와야 한다. 아니면 재현할 수 없는 배분이 된다."""
    props = [prop(agent=f"a{i}", unit=Unit(f"P{i:04d}", D), gain=1.0, rid=f"r{i}")
             for i in range(6)]
    first = [o.proposal.request_id for o in coord(Ledger("sqlite://")).decide(props).outcomes]
    second = [o.proposal.request_id for o in coord(Ledger("sqlite://")).decide(list(reversed(props))).outcomes]
    assert first == second
