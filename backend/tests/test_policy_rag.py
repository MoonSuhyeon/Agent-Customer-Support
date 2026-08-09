"""정책 RAG 검증 — 검색을 붙여도 안전 속성이 유지되는가.

순진하게 RAG를 붙이면 **검색은 언제나 무언가를 돌려준다.**
그러면 정책이 없는 숙소에도 비슷한 다른 규정이 걸려서, 잘못된 환불 금액을
고객에게 안내하게 된다. `Silent Fallback 금지`가 조용히 깨지는 경로다.

그래서 기권(abstain) 경로가 있고, 이 파일이 그것을 고정한다.
"""
from __future__ import annotations

from datetime import date

import pytest
from langgraph.checkpoint.memory import MemorySaver

from retrieval import Doc, assess

from app.agent.graph import build_graph
from app.agent.policy_rag import PolicyRetriever, policy_documents
from app.agent.tools import ReadTools
from app.domain import BookingStatus, CancellationPolicy, Property, seed

TODAY = date(2025, 6, 10)


@pytest.fixture
def store():
    return seed(today=TODAY)


@pytest.fixture
def retriever(store):
    return PolicyRetriever(store)


# ============================================================ 색인
def test_only_properties_with_policy_are_indexed(store, retriever):
    """정책이 없는 숙소는 색인하지 않는다.

    색인해두면 검색이 무언가를 돌려주게 되고, 그게 곧 추측이 된다.
    """
    ids = {d.metadata["property_id"] for d in policy_documents(store)}
    assert "P001" in ids and "P002" in ids
    assert "P999" not in ids, "정책 미등록 숙소가 색인됐다"


def test_policy_document_carries_property_context(store):
    """숙소명·지역을 함께 넣는다. 실제 문의가 그 형태로 오기 때문이다."""
    doc = next(d for d in policy_documents(store) if d.metadata["property_id"] == "P001")
    assert "제주 오션 스테이" in doc.text
    assert "Jeju" in doc.text


# ============================================================ 검색
def test_lookup_returns_correct_policy(retriever):
    r = retriever.lookup("P001")
    assert r.found
    assert r.policy.policy_id == "FLEX"
    assert r.top_score > 0


def test_lookup_distinguishes_between_properties(retriever):
    """서로 다른 숙소가 서로 다른 정책으로 해석되어야 한다."""
    a = retriever.lookup("P001")
    b = retriever.lookup("P002")
    assert a.found and b.found
    assert a.policy.policy_id != b.policy.policy_id


def test_lookup_abstains_for_unindexed_property(retriever):
    """정책 문서가 없는 숙소는 **비슷한 문서를 가져오지 않고** 기권한다."""
    r = retriever.lookup("P999")
    assert not r.found
    assert r.policy is None
    assert "색인" in r.reason


def test_lookup_abstains_for_unknown_property(retriever):
    r = retriever.lookup("P404")
    assert not r.found


def test_score_threshold_can_force_abstain(store):
    """임계값을 올리면 근거가 충분치 않다고 판정한다.

    임계값이 자동화율과 오응대 위험을 맞바꾸는 손잡이라는 것을 고정한다.
    """
    strict = PolicyRetriever(store, min_score=99.0)
    r = strict.lookup("P001")
    assert not r.found
    assert "확신할 수 없다" in r.reason


# ==================================================== 기권 판정 로직
def test_assess_rejects_empty():
    g = assess([], min_score=0.0)
    assert not g and "결과가 없다" in g.reason


def test_assess_rejects_low_margin():
    """1·2위가 붙어 있으면 어느 것이 답인지 모른다는 뜻이다."""
    from retrieval import Hit

    hits = [Hit(Doc("a", "x"), 0.05), Hit(Doc("b", "y"), 0.0499)]
    g = assess(hits, min_score=0.0, min_margin=0.01)
    assert not g and "격차" in g.reason


def test_assess_accepts_clear_winner():
    from retrieval import Hit

    hits = [Hit(Doc("a", "x"), 0.05), Hit(Doc("b", "y"), 0.001)]
    assert assess(hits, min_score=0.0, min_margin=0.01)


# ============================================== 도구·그래프 통합
def test_tool_reports_retrieval_score(store, retriever):
    tools = ReadTools(store, today=TODAY, policy_retriever=retriever)
    r = tools.get_cancellation_policy("P001")
    assert r.ok
    assert "retrieval_score" in r.data


def test_refund_calculation_uses_retrieved_policy(store, retriever):
    """검색으로 찾은 정책으로 금액이 계산된다. FLEX, 체크인 10일 전 → 전액."""
    tools = ReadTools(store, today=TODAY, policy_retriever=retriever)
    r = tools.calculate_refund("B1002")
    assert r.ok
    assert r.data["refund_ratio"] == 1.0
    assert r.data["refund_amount"] == 240_000


def test_abstain_propagates_to_escalation(store):
    """기권이 그래프 끝까지 전달되어 이관으로 이어진다.

    검색을 붙였다고 해서 추측 답변이 생기면 안 된다.
    """
    agent = build_graph(store, today=TODAY, checkpointer=MemorySaver())
    out = agent.invoke(
        {"message": "B1004 취소하고 환불받고 싶어요", "request_id": "r", "trace": []},
        {"configurable": {"thread_id": "esc"}},
    )
    assert out["escalated"] is True
    assert "전액 환불" not in out["response"]
    assert store.get_booking("B1004").status is BookingStatus.CONFIRMED


def test_added_policy_becomes_searchable_after_reindex(store):
    """정책을 등록하고 재색인하면 그때부터 찾을 수 있다."""
    r = PolicyRetriever(store)
    assert not r.lookup("P999")

    store.policies["MISSING"] = CancellationPolicy("MISSING", "표준", [(7, 1.0)])
    r.reindex()

    found = r.lookup("P999")
    assert found and found.policy.policy_id == "MISSING"


def test_free_text_search_abstains_when_ambiguous(retriever):
    """숙소를 특정하지 않은 질의는 후보가 비슷하게 걸리면 기권한다."""
    hits, ground = retriever.search_free_text("취소 환불 규정")
    if ground:
        # 명확한 승자가 있으면 통과. 없으면 기권해야 한다.
        assert hits[0].score - hits[1].score >= retriever.min_margin
    else:
        assert "격차" in ground.reason or "임계" in ground.reason
