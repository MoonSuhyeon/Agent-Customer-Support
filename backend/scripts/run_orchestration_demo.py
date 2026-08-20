"""조정자 시연 — **개수가 아니라 충돌이 값이다.**

두 에이전트가 같은 숙소·날짜를 노린다. 조정자가 없으면 둘 다 손대고, 그러면
점유율이 올라도 **어느 쪽 때문인지 영영 모른다.**

이 스크립트가 보여주는 건 화면이 아니라 그 차이다.
"""
from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from pathlib import Path

# 한국어 Windows(cp949)에서 em dash 하나에 죽는다. 출력 인코딩을 명시한다 —
# CI(리눅스, UTF-8)에서는 안 보이고 개발 기계에서만 깨지는 종류다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.orchestration.coordinator import Coordinator, Policy, Proposal   # noqa: E402
from app.orchestration.ledger import Decision, Ledger, Unit               # noqa: E402

BAR = "=" * 72
RNG = random.Random(20250820)
START = date(2025, 7, 1)


def candidates(n: int = 40) -> list[Unit]:
    """수요 예측이 낮게 본 숙소·날짜. 실제로는 ML-Product 가 준다."""
    return [Unit(f"P{RNG.randrange(1, 30):04d}", START + timedelta(days=RNG.randrange(14)))
            for _ in range(n)]


def proposals(units: list[Unit]) -> list[Proposal]:
    """두 에이전트가 같은 후보 목록을 보고 각자 제안한다.

    **일부러 겹치게 둔다.** 겹치지 않으면 조정할 일이 없고, 조정할 일이 없으면
    오케스트레이터는 라우터일 뿐이다.
    """
    out: list[Proposal] = []
    for i, u in enumerate(units):
        # 프로모션 — 돈이 들고 효과도 크게 본다. 다만 **모든 단위에 넣지는 않는다.**
        # 한 에이전트가 전 단위를 덮으면 다른 쪽은 영영 아무것도 못 한다.
        # 그건 조정자의 결함이 아니라 제안 쪽의 문제인데, 시연에서는 구분이 안 되니
        # 현실처럼 겹치되 서로 다른 부분집합을 노리게 둔다.
        if RNG.random() < 0.65:
            out.append(Proposal(
                agent="promotion", unit=u, action="discount",
                cost=RNG.choice((10_000, 20_000, 30_000)),
                expected_gain=RNG.uniform(0.5, 2.0),
                uncertainty=RNG.uniform(0.10, 0.55),      # 지역별 WAPE 를 흉내
                request_id=f"promo-{i}",
            ))
        # 콘텐츠 — 거의 공짜지만 효과도 작다.
        if RNG.random() < 0.7:
            out.append(Proposal(
                agent="content", unit=u, action="rewrite_listing",
                cost=RNG.choice((0, 1_000)),
                expected_gain=RNG.uniform(0.05, 0.4),
                uncertainty=RNG.uniform(0.05, 0.25),
                request_id=f"content-{i}",
            ))
    return out


def main() -> int:
    units = candidates()
    props = proposals(units)
    overlapping = len(props) - len({p.unit for p in props})

    print(BAR)
    print("조정자 — 둘 다 하고 싶어 하는데 누가 하나")
    print(f"  후보 단위 {len({*units}):,}개 · 제안 {len(props):,}건 "
          f"(같은 단위를 노린 제안 {overlapping:,}건)")

    ledger = Ledger("sqlite://")
    plan = Coordinator(ledger, Policy(budget=300_000,
                                      autonomy_uncertainty_max=0.35)).decide(props)

    print()
    print(BAR)
    print("결정")
    print(f"  {plan}")
    for agent, counts in sorted(ledger.by_agent().items()):
        row = " · ".join(f"{k} {v}" for k, v in sorted(counts.items()))
        print(f"    {agent:10} {row}")

    print()
    print("  거절·보류 사유 (앞 5건)")
    for o in [x for x in plan.outcomes if x.decision is not Decision.APPROVED][:5]:
        print(f"    {o}")

    print()
    print(BAR)
    print("이게 왜 중요한가 — 효과를 귀속할 수 있는가")
    approved_units = {o.proposal.unit for o in plan.approved}
    double = [u for u in approved_units
              if sum(1 for o in plan.approved if o.proposal.unit == u) > 1]
    print(f"  개입된 단위 {len(approved_units):,}개 · "
          f"두 번 이상 개입된 단위 {len(double):,}개")
    if not double:
        print("  → 단위마다 개입이 하나뿐이라, 점유율 변화를 **그 개입에 귀속**할 수 있다.")
        print("     조정자가 없으면 여기서 겹친 제안들이 전부 실행되고, 그러면")
        print("     홀드아웃은 '개입 있음/없음' 만 가르고 '무엇이 효과였나' 는 못 가른다.")
    else:
        print("  → 규칙이 깨졌다. 이 상태로는 효과를 귀속할 수 없다.")
        return 1

    print()
    print(BAR)
    print("남은 것")
    print("  A4 홀드아웃 배정 — 승인된 단위 중 일부를 **일부러 손대지 않는다**")
    print("  A5 홀드아웃 대비 효과 — 평균 회귀와 개입 효과를 가른다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
