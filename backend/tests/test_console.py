"""콘솔(A6) — 제안·거절 사유·승인 대기·결과.

계획에는 **"거절률 = AI 권고 채택률"** 이라고 적혀 있었다. 여기 테스트들은 그게
두 개의 다른 숫자였다는 것을 고정한다.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.orchestration.console import Console
from app.orchestration.coordinator import Coordinator, Policy, Proposal
from app.orchestration.ledger import Decision, Ledger, Unit

D = date(2025, 7, 10)
U = Unit("P0001", D)


@pytest.fixture
def ledger():
    return Ledger("sqlite://")


@pytest.fixture
def console(ledger):
    return Console(ledger)


def decide(ledger, proposals, **policy):
    base = dict(budget=1_000_000, autonomy_uncertainty_max=0.35, holdout_rate=0.0)
    base.update(policy)
    return Coordinator(ledger, Policy(**base)).decide(proposals)


def prop(unit=U, agent="promotion", cost=10_000, gain=1.0, unc=0.1, rid="r1"):
    return Proposal(agent=agent, unit=unit, action="discount", cost=cost,
                    expected_gain=gain, uncertainty=unc, request_id=rid)


# ─────────────────────────────────────────── 보여야 할 것이 보인다
def test_rejections_are_visible_with_their_reason(ledger, console):
    """실행된 것만 보면 통제가 안 보인다."""
    decide(ledger, [prop(cost=999_999_999)], budget=1_000)
    rows = console.recent()
    assert rows and rows[0]["decision"] == Decision.REJECTED.value
    assert "예산 초과" in rows[0]["reason"]


def test_pending_shows_what_waits_for_a_human(ledger, console):
    decide(ledger, [prop(unc=0.9)])
    pend = console.pending()
    assert len(pend) == 1
    assert pend[0]["decision"] == Decision.DEFERRED.value
    assert "사람이 봐야 한다" in pend[0]["reason"]


def test_a_judged_item_leaves_the_pending_list(ledger, console):
    """판단한 건이 목록에 남으면 사람은 목록을 안 믿게 된다."""
    decide(ledger, [prop(unc=0.9)])
    console.review(console.pending()[0]["id"], "reviewer-1", approve=True)
    assert console.pending() == []


# ─────────────────────────────────────────── 사람의 판단
def test_a_human_approval_executes(ledger, console):
    decide(ledger, [prop(unc=0.9)])
    r = console.review(console.pending()[0]["id"], "sh", approve=True, reason="성수기 직전")

    assert r["ok"] and r["executed"] is True
    assert r["final_decision"] == Decision.APPROVED.value
    assert ledger.approved_on(U) is not None


def test_a_human_rejection_is_recorded_with_the_reason(ledger, console):
    decide(ledger, [prop(unc=0.9)])
    console.review(console.pending()[0]["id"], "sh", approve=False, reason="이미 만실이다")
    row = console.recent()[0]
    assert row["decision"] == Decision.REJECTED.value
    assert row["human_decision"] == Decision.REJECTED.value
    assert "이미 만실이다" in row["reason"]


def test_the_same_item_cannot_be_judged_twice(ledger, console):
    decide(ledger, [prop(unc=0.9)])
    iid = console.pending()[0]["id"]
    console.review(iid, "sh", approve=True)
    again = console.review(iid, "other", approve=False)
    assert not again["ok"]
    assert "이미 판단된" in again["error"]


def test_only_deferred_items_can_be_judged(ledger, console):
    decide(ledger, [prop()])
    r = console.review(console.recent()[0]["id"], "sh", approve=True)
    assert not r["ok"]


def test_a_human_approval_still_obeys_one_unit_one_intervention(ledger, console):
    """**사람의 손을 거친 건이 측정을 깨는 통로가 되면 안 된다.**

    대기 건은 하루 이틀 묵는다. 그 사이 다른 에이전트가 그 단위를 가져갔다면,
    사람이 승인했다는 이유로 한 단위 한 개입을 건너뛸 수는 없다.

    그래도 **사람의 판단은 남긴다.** 안 남기면 채택률이 거짓이 된다 — 사람은
    분명히 승인했고, 막힌 건 규칙이다.
    """
    decide(ledger, [prop(unc=0.9, rid="r1")])
    iid = console.pending()[0]["id"]

    # 그 사이 다른 에이전트가 같은 단위를 가져간다
    decide(ledger, [prop(agent="content", unc=0.1, rid="r2")])
    assert ledger.approved_on(U) is not None

    r = console.review(iid, "sh", approve=True)
    assert r["ok"]
    assert r["human_decision"] == Decision.APPROVED.value, "사람은 승인했다"
    assert r["executed"] is False, "그런데 실행되지 않았다"
    assert r["final_decision"] == Decision.SUPERSEDED.value
    assert "다른 개입이 가져갔다" in r["blocked"]

    # 채택률은 사람의 판단을 센다 — 규칙이 막은 것은 사람이 거절한 게 아니다
    assert console.adoption().accepted == 1


# ─────────────────────────────────────────── 채택률은 거절률이 아니다
def test_policy_rejections_do_not_count_against_the_adoption_rate(ledger, console):
    """**계획의 문장을 고치는 테스트.**

    예산이 모자라 거절된 제안은 "사람이 AI 를 안 믿었다" 가 아니다. 섞으면 예산을
    줄이는 것만으로 채택률이 떨어지고, 그 숫자를 보고 모델을 의심하게 된다.
    """
    units = [Unit(f"P{i:04d}", D) for i in range(20)]
    decide(ledger, [prop(unit=u, cost=100_000, rid=f"r{i}") for i, u in enumerate(units)],
           budget=300_000)

    counts = ledger.counts()
    assert counts[Decision.REJECTED.value] > 0, "예산에서 거절이 나와야 한다"
    assert console.adoption().reviewed == 0, "사람은 아무것도 안 봤다"
    assert console.adoption().rate is None


def test_an_empty_adoption_rate_is_not_zero(console):
    """`None` 은 '아직 말할 수 없음' 이다. 0 으로 그리면 사람이 전부 거절한 것처럼 보인다."""
    a = console.adoption()
    assert a.rate is None
    assert "아직 판단된 건이 없다" in str(a)


def test_pending_items_are_not_in_the_denominator(ledger, console):
    """안 본 것은 거절이 아니다."""
    units = [Unit(f"P{i:04d}", D) for i in range(5)]
    decide(ledger, [prop(unit=u, unc=0.9, rid=f"r{i}") for i, u in enumerate(units)])
    console.review(console.pending()[0]["id"], "sh", approve=True)

    a = console.adoption()
    assert a.reviewed == 1 and a.accepted == 1 and a.pending == 4
    assert a.rate == 1.0


def test_adoption_can_be_split_by_agent(ledger, console):
    """누구의 권고가 잘 받아들여지나 — 에이전트별로 갈려야 의미가 있다."""
    ua = [Unit(f"A{i:04d}", D) for i in range(4)]
    ub = [Unit(f"B{i:04d}", D) for i in range(4)]
    decide(ledger, [prop(unit=u, agent="promotion", unc=0.9, rid=f"a{i}")
                    for i, u in enumerate(ua)]
                 + [prop(unit=u, agent="content", unc=0.9, rid=f"b{i}")
                    for i, u in enumerate(ub)])

    for row in console.pending():
        console.review(row["id"], "sh", approve=row["agent"] == "promotion")

    assert console.adoption("promotion").rate == 1.0
    assert console.adoption("content").rate == 0.0
    assert console.adoption().rate == 0.5


# ─────────────────────────────────────────── 요약
def test_the_holdout_is_neither_a_pass_failure_nor_a_rejection(ledger, console):
    """홀드아웃은 정책을 통과했고 사람은 본 적이 없다.

    거절로 세면 채택률이 홀드아웃 비율만큼 망가지고, 통과율에서 빼면 정책이
    실제보다 빡빡해 보인다.
    """
    units = [Unit(f"P{i:04d}", D) for i in range(200)]
    decide(ledger, [prop(unit=u, cost=1_000, rid=f"r{i}") for i, u in enumerate(units)],
           budget=10_000_000, holdout_rate=0.3)

    s = console.summary()
    assert s.counts[Decision.HELD_OUT.value] > 0
    assert s.policy_pass_rate == 1.0, "전부 통과했다 — 홀드아웃도 통과한 것이다"
    assert s.adoption.reviewed == 0


def test_the_summary_separates_the_two_rates(ledger, console):
    """**한 화면에 두 숫자가 따로 있어야 한다.**"""
    units = [Unit(f"P{i:04d}", D) for i in range(10)]
    decide(ledger, [prop(unit=u, cost=200_000, unc=0.9 if i < 3 else 0.1, rid=f"r{i}")
                    for i, u in enumerate(units)], budget=400_000)
    console.review(console.pending()[0]["id"], "sh", approve=True)

    s = console.summary()
    assert s.policy_pass_rate is not None
    assert s.adoption.rate is not None
    assert s.policy_pass_rate != s.adoption.rate
    assert "정책 통과율" in str(s) and "채택률" in str(s)


def test_the_summary_reports_what_was_actually_spent(ledger, console):
    decide(ledger, [prop(cost=50_000)])
    assert console.summary().spent == 50_000


# ─────────────────────────────────────────── API 면 (콘솔이 실제로 부르는 것)
@pytest.fixture
def api(monkeypatch, tmp_path):
    """모듈 전역 콘솔을 임시 파일 DB 로 갈아 끼운다.

    기본값은 저장소 옆의 `interventions.db` 라 테스트가 실행 환경을 더럽힌다.
    더럽혀진 상태는 다음 테스트의 숫자를 바꾼다 — 채택률처럼 누적으로 세는
    지표에서는 특히 그렇다.

    **인메모리(`sqlite://`)를 쓰면 안 된다.** TestClient 는 앱을 다른 스레드에서
    돌리고, SQLAlchemy 는 인메모리 sqlite 에 스레드마다 다른 연결을 준다 — 그
    연결에는 테이블이 없다.
    """
    from fastapi.testclient import TestClient

    from app import main

    ledger = Ledger(f"sqlite:///{tmp_path / 'led.db'}")
    monkeypatch.setattr(main, "_console", Console(ledger))
    return TestClient(main.app), ledger


def test_the_console_api_exposes_rejections_with_reasons(api):
    client, ledger = api
    decide(ledger, [prop(cost=999_999_999)], budget=1_000)

    rows = client.get("/orchestration/recent").json()
    assert rows and rows[0]["decision"] == Decision.REJECTED.value
    assert rows[0]["reason"], "이유 없는 거절은 콘솔에서 쓸모가 없다"


def test_the_console_api_separates_the_two_rates(api):
    client, ledger = api
    units = [Unit(f"P{i:04d}", D) for i in range(10)]
    decide(ledger, [prop(unit=u, cost=200_000, unc=0.9 if i < 3 else 0.1, rid=f"r{i}")
                    for i, u in enumerate(units)], budget=400_000)

    body = client.get("/orchestration/summary").json()
    assert "policy_pass_rate" in body
    assert "rate" in body["adoption"]
    assert body["adoption"]["rate"] is None, "아무도 안 봤으면 null 이다 — 0 이 아니다"
    assert body["adoption"]["pending"] == 3


def test_the_review_endpoint_closes_the_loop(api):
    client, ledger = api
    decide(ledger, [prop(unc=0.9)])
    iid = client.get("/orchestration/pending").json()[0]["id"]

    r = client.post("/orchestration/review", json={
        "intervention_id": iid, "reviewer": "sh", "approve": True, "reason": "성수기 직전",
    }).json()
    assert r["ok"] and r["executed"] is True

    assert client.get("/orchestration/pending").json() == []
    assert client.get("/orchestration/summary").json()["adoption"]["rate"] == 1.0


def test_the_review_endpoint_reports_a_blocked_approval(api):
    """사람은 승인했는데 규칙이 막은 경우가 응답에서 구분돼야 한다."""
    client, ledger = api
    decide(ledger, [prop(unc=0.9, rid="r1")])
    iid = client.get("/orchestration/pending").json()[0]["id"]
    decide(ledger, [prop(agent="content", unc=0.1, rid="r2")])

    r = client.post("/orchestration/review", json={
        "intervention_id": iid, "reviewer": "sh", "approve": True,
    }).json()
    assert r["human_decision"] == Decision.APPROVED.value
    assert r["executed"] is False
    assert r["blocked"]


def test_an_unknown_decision_filter_is_a_400_not_an_empty_list(api):
    """빈 목록으로 답하면 "그런 결정이 없다" 와 "그런 상태가 없다" 가 구분되지 않는다."""
    client, _ = api
    assert client.get("/orchestration/recent", params={"decision": "MAYBE"}).status_code == 400
    assert client.get("/orchestration/recent",
                      params={"decision": "APPROVED"}).status_code == 200
