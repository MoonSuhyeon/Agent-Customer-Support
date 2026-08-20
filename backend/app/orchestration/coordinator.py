"""조정자 — **에이전트를 부르는 라우터가 아니라 개입을 배분하는 자리.**

`docs/multi-agent-orchestration.md` 의 B2. 그 문서가 바꾼 문장이 이것이다.

라우터는 "이 요청은 누구 담당?" 을 답한다. 그건 ``if`` 문이고 아무도 안 물어본다.
조정자는 **"둘 다 하고 싶어 하는데 누가 하나?"** 를 답한다.

## 강제하는 규칙 셋

1. **한 단위에는 한 번만 개입한다.**
   측정 요구에서 바로 나온다 — 같은 숙소·날짜에 할인과 콘텐츠가 동시에 들어가면
   점유율이 올라도 어느 쪽 때문인지 모른다. 홀드아웃이 "개입 있음/없음" 은 갈라도
   "무엇이 효과였나" 는 영영 못 가른다.

2. **예산은 공유된다.**
   선착순이 아니라 **기대 효과 대비 비용**으로 배분한다. 먼저 온 제안이 예산을
   다 쓰면, 뒤에 온 더 좋은 제안이 밀린다.

3. **자율성은 제안자가 아니라 조정자가 정한다.**
   각 에이전트가 자기 권한을 주장하면 통제가 없다. 예측이 못 미더운 구간은 사람
   승인으로 돌린다 — `ML 의 구간별 오차가 자율성 수준을 정한다`.

## 무엇을 안 하는가

에이전트를 실행하지 않는다. **결정만 한다.** 실행은 승인을 받은 에이전트가 자기
도구로 하고, 그 도구는 여전히 `interrupt_before=["execute"]` 뒤에 있다. 조정자가
실행까지 쥐면 단일 장애점이 하나 더 생긴다.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from app.orchestration.ledger import Decision, Ledger, Unit

#: 홀드아웃 배정에 쓰는 실험 ID. **Data-Growth 와 같은 값이어야 한다.**
HOLDOUT_EXPERIMENT = "intervention_holdout"

#: 두 저장소가 같은 답을 내는지 고정하는 골든 벡터.
#:
#: 배정 규칙이 두 서비스에 걸쳐 있다. 여기서 계산하고 Data-Growth 가 그 결과를
#: 읽어 효과를 잰다 — 두 쪽이 어긋나면 "이 단위가 어느 군인가" 에 답이 두 개가
#: 되고, 그러면 홀드아웃 자체가 무의미해진다.
#:
#: 같은 파일이 양쪽에 커밋돼 있고 양쪽 테스트가 각자 검사한다. 커밋된
#: `openapi.json` 을 CI 가 대조하는 것과 같은 방식이다.
HOLDOUT_VECTORS = Path(__file__).with_name("holdout_vectors.json")


def holdout_arm(unit: Unit, holdout_rate: float,
                experiment_id: str = HOLDOUT_EXPERIMENT) -> bool:
    """이 단위를 손대는가. `True` 면 개입, `False` 면 홀드아웃.

    난수가 아니라 **결정적 해시**다. 난수를 쓰면 같은 단위가 회차마다 다른 군에
    들어가고, 그러면 한 단위의 결과가 두 군에 흩어져 둘 다 못 읽는다.

    Data-Growth 의 `analytics.experiments.stats.assign()` 과 **같은 식**이다.
    variants 는 `("holdout", "treated")`, weights 는 `(rate, 1 - rate)`.
    """
    unit_id = f"{unit.property_id}:{unit.stay_date.isoformat()}"
    h = hashlib.md5(f"{experiment_id}:{unit_id}".encode("utf-8")).hexdigest()
    bucket = int(h[:8], 16) / 0xFFFFFFFF
    return bucket >= holdout_rate


@dataclass(frozen=True)
class Proposal:
    """에이전트가 내는 제안. **실행이 아니라 신청이다.**"""

    agent: str
    unit: Unit
    action: str
    cost: int
    #: 이 개입이 얼마나 좋아질 것으로 보는가. 예산 배분의 기준이다.
    expected_gain: float
    #: 이 구간에서 예측이 얼마나 믿을 만한가(WAPE 등). 자율성이 여기서 갈린다.
    uncertainty: float
    request_id: str
    reason: str = ""

    @property
    def efficiency(self) -> float:
        """비용 1원당 기대 효과. **예산을 나눌 때만** 쓴다.

        경합을 이걸로 판정하면 안 된다 — 공짜 개입의 효율이 무한대라 기대 효과가
        0.05 인 제안이 2.0 인 제안을 이긴다. 그리고 규칙 1(한 단위 한 개입) 때문에
        이긴 쪽이 그 단위를 **막으므로**, 가장 값싼 개입이 가장 값진 개입을
        밀어내는 결과가 된다. 두 규칙이 서로를 망치는 자리다.
        """
        return self.expected_gain / self.cost if self.cost else float("inf")


@dataclass
class Outcome:
    proposal: Proposal
    decision: Decision
    reason: str

    def __str__(self) -> str:
        return f"[{self.decision.value}] {self.proposal.agent} → {self.proposal.unit} — {self.reason}"


@dataclass
class Policy:
    """조정자가 따르는 선. 코드가 아니라 값이라 바꾸면 커밋이 남는다."""

    budget: int
    #: 이 값을 넘으면 사람 승인으로 돌린다. 자율성의 경계다.
    autonomy_uncertainty_max: float = 0.35
    #: 이보다 효율이 낮으면 애초에 안 한다. 예산이 남아도 마찬가지다.
    min_efficiency: float = 0.0
    #: 정책을 통과한 것 중 이 비율만큼은 **일부러 실행하지 않는다.**
    #:
    #: 낭비처럼 보이지만 이걸 빼면 효과를 잴 수 없다. 저수요 후보는 "예측이 가장
    #: 낮은 것" 으로 고르므로 아무것도 안 해도 다음 회차에 오른다(평균 회귀).
    #: 홀드아웃이 없으면 그 상승이 전부 개입 공로로 잡히고, 에이전트는 실패해도
    #: 성공한 것처럼 보인다.
    #:
    #: 0 으로 두면 홀드아웃이 꺼진다 — **효과를 측정하지 않겠다는 뜻이다.**
    holdout_rate: float = 0.3


@dataclass
class Plan:
    outcomes: list[Outcome] = field(default_factory=list)
    spent: int = 0
    budget: int = 0

    @property
    def approved(self) -> list[Outcome]:
        return [o for o in self.outcomes if o.decision is Decision.APPROVED]

    @property
    def deferred(self) -> list[Outcome]:
        return [o for o in self.outcomes if o.decision is Decision.DEFERRED]

    @property
    def held_out(self) -> list[Outcome]:
        """실행하지 않은 대조군. **거절이 아니다** — 정책은 통과했다."""
        return [o for o in self.outcomes if o.decision is Decision.HELD_OUT]

    def __str__(self) -> str:
        c: dict[str, int] = {}
        for o in self.outcomes:
            c[o.decision.value] = c.get(o.decision.value, 0) + 1
        parts = " · ".join(f"{k} {v}" for k, v in sorted(c.items()))
        return f"{parts} · 예산 {self.spent:,}/{self.budget:,}"


class Coordinator:
    def __init__(self, ledger: Ledger, policy: Policy):
        self.ledger = ledger
        self.policy = policy

    def decide(self, proposals: list[Proposal]) -> Plan:
        """제안을 모아 한 번에 배분한다.

        **한 건씩 처리하지 않는 이유가 있다.** 하나씩 보면 먼저 온 것이 무조건
        이기고, 그건 배분이 아니라 선착순이다.

        그리고 두 질문을 **다른 기준으로** 답한다. 하나로 묶으면 규칙끼리 부딪힌다.

          경합 — "이 단위는 누가 가져가나"  → **기대 효과**가 큰 쪽.
                 그 단위에서 가장 좋은 결과를 원하는 것이지, 싼 걸 원하는 게 아니다.
          예산 — "돈을 어디에 쓰나"          → **효율**이 높은 순.
                 여기서는 1원당 얼마를 얻느냐가 맞는 질문이다.

        처음엔 둘 다 효율로 세웠는데, 공짜 개입의 효율이 무한대라 기대 효과 0.05 가
        2.0 을 이겼다. 규칙 1 때문에 이긴 쪽이 그 단위를 막으므로, 가장 값싼 개입이
        가장 값진 개입을 밀어냈다. 시연을 돌려 보고서야 드러났다.
        """
        plan = Plan(budget=self.policy.budget, spent=self.ledger.spent())

        # ── 1단계: 단위별 경합. 기대 효과가 큰 쪽이 그 단위를 가져간다.
        by_unit: dict[Unit, list[Proposal]] = {}
        for p in proposals:
            by_unit.setdefault(p.unit, []).append(p)

        winners: list[Proposal] = []
        for unit, group in by_unit.items():
            ranked = sorted(group, key=lambda p: (-p.expected_gain, p.agent, p.request_id))
            winners.append(ranked[0])
            for loser in ranked[1:]:
                self.ledger.write(
                    loser.unit, loser.agent, loser.action, Decision.SUPERSEDED,
                    "같은 단위를 기대 효과가 큰 제안이 가져갔다",
                    loser.request_id, loser.cost,
                )
                plan.outcomes.append(Outcome(
                    loser, Decision.SUPERSEDED,
                    "같은 단위를 기대 효과가 큰 제안이 가져갔다",
                ))

        # ── 2단계: 예산 배분. 여기서는 효율이 맞는 기준이다.
        ordered = sorted(winners, key=lambda p: (-p.efficiency, -p.expected_gain,
                                                 p.agent, p.request_id))
        # DB 제약이 최종 보루지만, 같은 배치 안에서는 여기서 먼저 걸러야
        # **왜 밀렸는지**를 이유로 남길 수 있다.
        taken: set[Unit] = set()

        for p in ordered:
            decision, reason = self._judge(p, plan, taken)
            written = self.ledger.write(
                p.unit, p.agent, p.action, decision, reason, p.request_id, p.cost,
            )
            if not written and decision in (Decision.APPROVED, Decision.HELD_OUT):
                # DB 가 막았다 — 다른 프로세스가 같은 단위를 먼저 잡았다.
                # **애플리케이션 검사를 통과했어도 여기서 진다.** 그게 제약을
                # DB 에 둔 이유다.
                decision, reason = Decision.SUPERSEDED, "다른 프로세스가 같은 단위를 먼저 잡았다"
                self.ledger.write(p.unit, p.agent, p.action, decision, reason,
                                  p.request_id + ":superseded", p.cost)

            if decision in (Decision.APPROVED, Decision.HELD_OUT):
                # 홀드아웃도 단위를 잡는다. 예산은 안 쓴다 — 실행하지 않으니까.
                taken.add(p.unit)
            if decision is Decision.APPROVED:
                plan.spent += p.cost
            plan.outcomes.append(Outcome(p, decision, reason))

        return plan

    def _judge(self, p: Proposal, plan: Plan, taken: set[Unit]) -> tuple[Decision, str]:
        # ── 규칙 1. 한 단위 한 개입
        if p.unit in taken:
            return Decision.SUPERSEDED, "같은 단위를 더 효율 높은 제안이 먼저 잡았다"
        claimed = self.ledger.claimed_on(p.unit)
        if claimed is not None:
            if claimed.decision == Decision.HELD_OUT.value:
                return Decision.SUPERSEDED, "이 단위는 홀드아웃이다 — 손대면 대조군이 오염된다"
            return Decision.SUPERSEDED, "이 단위에는 이미 승인된 개입이 있다"

        # ── 효율. 예산이 남아도 밑지는 개입은 안 한다.
        if p.efficiency < self.policy.min_efficiency:
            return Decision.REJECTED, (
                f"효율 {p.efficiency:.3g} < 최소 {self.policy.min_efficiency:.3g}"
            )

        # ── 규칙 2. 공유 예산
        if plan.spent + p.cost > plan.budget:
            return Decision.REJECTED, (
                f"예산 초과 ({plan.spent:,}+{p.cost:,} > {plan.budget:,})"
            )

        # ── 규칙 3. 자율성은 조정자가 정한다
        if p.uncertainty > self.policy.autonomy_uncertainty_max:
            return Decision.DEFERRED, (
                f"예측 불확실성 {p.uncertainty:.3g} > "
                f"{self.policy.autonomy_uncertainty_max:.3g} — 사람이 봐야 한다"
            )

        # ── 마지막. 통과한 것 중 일부를 일부러 놔둔다.
        #
        # **순서가 중요하다.** 홀드아웃을 앞에서 뽑으면 예산이나 자율성에서 어차피
        # 밀렸을 단위가 대조군에 섞인다. 그러면 두 군이 "정책을 통과한 정도" 부터
        # 다르고, 차이를 개입 때문이라고 말할 수 없다. 대조군은 **승인됐을 것들**
        # 중에서만 나와야 한다.
        if self.policy.holdout_rate and not holdout_arm(p.unit, self.policy.holdout_rate):
            return Decision.HELD_OUT, (
                f"홀드아웃 — 정책을 통과했지만 효과 측정을 위해 실행하지 않는다 "
                f"(비율 {self.policy.holdout_rate:.0%})"
            )

        return Decision.APPROVED, p.reason or "정책을 통과했다"


__all__ = ["Coordinator", "HOLDOUT_EXPERIMENT", "HOLDOUT_VECTORS", "Outcome",
           "Plan", "Policy", "Proposal", "holdout_arm"]
