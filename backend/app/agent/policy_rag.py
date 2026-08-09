"""정책 문서 검색 — RAG-Marketing 의 검색 코어를 재사용한다.

정책 조회를 왜 RAG로 바꾸나:
숙소마다 취소 규정이 자연어 문서로 흩어져 있고, 문구가 조금씩 다르다.
`policy_id` 로 정확히 찾을 수 있는 세계라면 검색이 필요 없지만, 실제 운영에서는
"이 숙소 규정이 어느 문서에 있는지"부터 찾아야 한다.

**다만 이 소비자는 틀리면 안 된다.**
검색은 언제나 무언가를 돌려준다. 그래서 그대로 쓰면 `Silent Fallback 금지` 원칙이 깨진다.
정책을 못 찾았는데 비슷한 다른 숙소 규정을 가져와 환불 금액을 계산하면
잘못된 금액을 고객에게 안내하게 된다.

그래서 검색 결과를 **근거로 써도 되는지 따로 판정**하고(`assess`),
기권하면 도구가 실패를 반환해 그래프가 에스컬레이션으로 빠진다.
"""
from __future__ import annotations

from dataclasses import dataclass

from retrieval import Doc, Embedder, HybridIndex, assess

from app.domain import CancellationPolicy, Store

# 근거 충분성 임계값.
# 낮추면 자동화율이 오르고 오응대 위험이 오른다. 이 프로젝트는 오응대 0% 가 우선이라
# 보수적으로 잡는다.
MIN_SCORE = 0.016
MIN_MARGIN = 0.0005


@dataclass
class PolicyLookup:
    """정책 조회 결과. 실패를 값으로 표현한다."""

    found: bool
    policy: CancellationPolicy | None = None
    property_id: str | None = None
    reason: str = ""
    top_score: float = 0.0

    def __bool__(self) -> bool:
        return self.found


def policy_documents(store: Store) -> list[Doc]:
    """숙소별 취소 규정을 문서로 만든다.

    정책을 그대로 넣지 않고 **숙소 이름·지역과 함께** 넣는다.
    실제 문의가 "제주 오션 스테이 취소하면 얼마 돌려받나요" 같은 형태로 오기 때문이다.
    """
    docs: list[Doc] = []
    for prop in store.properties.values():
        pol = store.policies.get(prop.policy_id)
        if pol is None:
            # 정책이 없는 숙소는 색인하지 않는다.
            # 색인해두면 검색이 무언가를 돌려주게 되고, 그게 곧 추측이 된다.
            continue
        text = (
            f"{prop.name} ({prop.region}) 취소 및 환불 규정. "
            f"{pol.name} 정책이 적용됩니다. {pol.describe()}"
        )
        docs.append(
            Doc(
                doc_id=f"{prop.property_id}:policy",
                text=text,
                metadata={
                    "property_id": prop.property_id,
                    "policy_id": pol.policy_id,
                    "property_name": prop.name,
                    "region": prop.region,
                },
            )
        )
    return docs


class PolicyRetriever:
    """정책 문서에 대한 하이브리드 검색 + 기권."""

    def __init__(self, store: Store, embedder: Embedder | None = None,
                 min_score: float = MIN_SCORE, min_margin: float = MIN_MARGIN):
        self.store = store
        self.embedder = embedder or Embedder()
        self.index = HybridIndex(dim=self.embedder.dim)
        self.min_score = min_score
        self.min_margin = min_margin
        self.reindex()

    def reindex(self) -> int:
        docs = policy_documents(self.store)
        if not docs:
            self.index = HybridIndex(dim=self.embedder.dim)
            return 0
        vecs = self.embedder.embed([d.text for d in docs])
        self.index.build(docs, vecs)
        return len(docs)

    # ------------------------------------------------------------------
    def lookup(self, property_id: str) -> PolicyLookup:
        """숙소의 취소 정책을 검색으로 찾는다.

        메타데이터로 후보를 그 숙소에 한정한 뒤 검색한다.
        후보가 없으면(= 정책 문서가 색인되지 않았으면) **기권**한다.
        """
        prop = self.store.get_property(property_id)
        if prop is None:
            return PolicyLookup(False, reason=f"숙소 {property_id} 을 찾을 수 없다")

        query = f"{prop.name} {prop.region} 취소 환불 규정"
        qv = self.embedder.embed_one(query)
        hits, stats = self.index.search(
            query, qv, where=lambda d: d.metadata["property_id"] == property_id, top_k=3
        )

        if stats.after_filter == 0:
            return PolicyLookup(
                False, property_id=property_id,
                reason=f"숙소 {property_id} 의 취소 정책 문서가 색인되어 있지 않다",
            )

        # 후보를 한 숙소로 좁혔으므로 격차 조건은 적용하지 않는다.
        ground = assess(hits, min_score=self.min_score, min_margin=0.0)
        if not ground:
            return PolicyLookup(
                False, property_id=property_id,
                reason=f"정책 문서를 확신할 수 없다 ({ground.reason})",
                top_score=ground.top_score,
            )

        policy_id = hits[0].doc.metadata["policy_id"]
        policy = self.store.policies.get(policy_id)
        if policy is None:
            return PolicyLookup(
                False, property_id=property_id,
                reason=f"검색된 정책 {policy_id} 의 본문을 찾을 수 없다",
            )
        return PolicyLookup(True, policy=policy, property_id=property_id,
                            top_score=ground.top_score)

    def search_free_text(self, query: str, top_k: int = 3):
        """자연어 질의로 정책을 찾는다 (숙소 지정 없이).

        여기서는 **격차 조건을 켠다.** 여러 숙소 규정이 비슷하게 걸리면
        어느 것이 답인지 모른다는 뜻이므로 기권해야 한다.
        """
        qv = self.embedder.embed_one(query)
        hits, _ = self.index.search(query, qv, top_k=top_k)
        ground = assess(hits, min_score=self.min_score, min_margin=self.min_margin)
        return hits, ground


__all__ = ["MIN_MARGIN", "MIN_SCORE", "PolicyLookup", "PolicyRetriever", "policy_documents"]
