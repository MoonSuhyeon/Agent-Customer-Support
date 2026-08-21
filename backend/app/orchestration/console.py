"""콘솔 — **무엇을 하려 했고, 무엇이 막혔고, 사람은 뭐라 했나.**

`docs/multi-agent-orchestration.md` 의 A6.

## 문서가 적어 둔 문장을 여기서 고친다

계획에는 **"거절률 = AI 권고 채택률"** 이라고 적혀 있다. 만들어 보니 그건 두 개의
다른 숫자를 하나로 부른 것이었다.

| 숫자 | 무엇인가 | 무엇이 아닌가 |
|---|---|---|
| **정책 통과율** | 조정자가 자동으로 통과시킨 비율 | 사람의 판단이 아니다. 예산·자율성 규칙이 낸 결과다 |
| **사람 채택률** | 사람에게 넘어간 것 중 사람이 승인한 비율 | **이게 AI 권고 채택률이다** |

예산이 모자라 거절된 제안은 "사람이 AI 를 안 믿었다" 가 아니다. 둘을 섞으면 예산을
줄이는 것만으로 채택률이 떨어지고, 그 숫자를 보고 모델을 의심하게 된다.

그리고 `HELD_OUT` 은 **어느 쪽도 아니다.** 정책은 통과했고 사람은 본 적이 없다.
거절로 세면 채택률이 홀드아웃 비율만큼 망가진다.

## 사람의 결정을 원장에 섞지 않는다

`Intervention` 은 조정자의 결정을 남기는 표다. 사람의 결정을 같은 행에 덮어쓰면
"기계가 뭘 하려 했나" 와 "사람이 뭐라 했나" 가 섞이고, 그 둘의 차이가 곧 채택률이라
섞이는 순간 잴 수 없게 된다. 별도 표로 둔다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from sqlalchemy import (
    Column, DateTime, Integer, String, Text, func, select,
)
from sqlalchemy.orm import Session

from app.orchestration.ledger import Base, Decision, Intervention, Ledger, Unit


class HumanReview(Base):
    """사람이 내린 판단. **조정자의 결정과 다른 표다.**"""

    __tablename__ = "human_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    #: 어느 제안에 대한 판단인가. 한 제안에 한 번만 — 번복은 새 제안으로 한다.
    intervention_id = Column(Integer, nullable=False, unique=True, index=True)
    reviewer = Column(String(64), nullable=False)
    #: APPROVED 또는 REJECTED. 사람은 보류하지 않는다 — 보류는 판단이 아니라 미판단이고,
    #: 미판단은 행을 안 쓰는 것으로 표현된다.
    decision = Column(String(16), nullable=False)
    reason = Column(Text, nullable=False, default="")
    at = Column(DateTime, nullable=False)


@dataclass
class Adoption:
    """AI 권고 채택률. **사람이 실제로 판단한 것만 센다.**"""

    reviewed: int
    accepted: int
    #: 아직 아무도 안 본 것. 분모에 넣으면 안 된다 — 안 본 것은 거절이 아니다.
    pending: int

    @property
    def rate(self) -> float | None:
        """`None` 은 0 이 아니라 '아직 말할 수 없음' 이다."""
        return self.accepted / self.reviewed if self.reviewed else None

    def __str__(self) -> str:
        if self.rate is None:
            return f"채택률 — 아직 판단된 건이 없다 (대기 {self.pending}건)"
        return (f"채택률 {self.rate:.0%} ({self.accepted}/{self.reviewed}) · "
                f"대기 {self.pending}건")


@dataclass
class Summary:
    """콘솔 첫 화면이 보여야 하는 것."""

    counts: dict[str, int] = field(default_factory=dict)
    by_agent: dict[str, dict[str, int]] = field(default_factory=dict)
    spent: int = 0
    #: 조정자가 자동으로 통과시킨 비율. **사람 채택률과 다른 숫자다.**
    policy_pass_rate: float | None = None
    adoption: Adoption | None = None

    def __str__(self) -> str:
        pol = f"{self.policy_pass_rate:.0%}" if self.policy_pass_rate is not None else "—"
        return f"정책 통과율 {pol} · {self.adoption} · 집행 {self.spent:,}원"


class Console:
    """원장을 읽고, 대기 중인 것을 사람에게 넘기고, 사람의 답을 받는다."""

    def __init__(self, ledger: Ledger):
        self.ledger = ledger
        Base.metadata.create_all(ledger.engine)

    # ------------------------------------------------------------ 읽기
    def recent(self, limit: int = 50, decision: Decision | None = None) -> list[dict]:
        """최근 결정. **거절도 보인다** — 실행된 것만 보면 통제가 안 보인다."""
        with Session(self.ledger.engine) as s:
            stmt = select(Intervention).order_by(Intervention.id.desc())
            if decision is not None:
                stmt = stmt.where(Intervention.decision == decision.value)
            rows = s.execute(stmt.limit(limit)).scalars().all()
            reviews = self._reviews_for(s, [r.id for r in rows])
            return [self._view(r, reviews.get(r.id)) for r in rows]

    def pending(self, limit: int = 100) -> list[dict]:
        """사람 승인 대기. **아직 아무도 안 본 것만.**

        이미 판단한 건이 계속 대기 목록에 남으면 사람은 목록을 믿지 않게 되고,
        믿지 않는 목록은 안 보게 된다.
        """
        with Session(self.ledger.engine) as s:
            reviewed = select(HumanReview.intervention_id)
            rows = s.execute(
                select(Intervention)
                .where(Intervention.decision == Decision.DEFERRED.value,
                       Intervention.id.not_in(reviewed))
                .order_by(Intervention.id)
                .limit(limit)
            ).scalars().all()
            return [self._view(r, None) for r in rows]

    # ------------------------------------------------------------ 사람의 판단
    def review(self, intervention_id: int, reviewer: str, approve: bool,
               reason: str = "") -> dict:
        """사람이 대기 건을 처리한다.

        **승인해도 규칙은 그대로 걸린다.** 대기 건은 하루 이틀 묵을 수 있고, 그 사이
        다른 에이전트가 그 단위를 가져갔을 수 있다. 사람이 승인했다는 이유로 한 단위
        한 개입을 건너뛰면, 사람의 손을 거친 건이 오히려 측정을 깨는 통로가 된다.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with Session(self.ledger.engine) as s:
            row = s.get(Intervention, intervention_id)
            if row is None:
                return {"ok": False, "error": f"제안 {intervention_id} 이 없다"}
            # **판단 여부를 먼저 본다.** 판단하면 `decision` 이 바뀌므로, 순서를
            # 뒤집으면 이미 처리한 건에 대해 "대기 중이 아니다" 라는 덜 정확한
            # 이유가 돌아간다 — 막히는 건 같지만 콘솔이 사람에게 거짓말을 한다.
            if self._reviews_for(s, [intervention_id]):
                return {"ok": False, "error": "이미 판단된 건이다 — 번복은 새 제안으로 한다"}
            if row.decision != Decision.DEFERRED.value:
                return {"ok": False,
                        "error": f"대기 중인 건이 아니다 ({row.decision})"}

            verdict = Decision.APPROVED if approve else Decision.REJECTED
            blocked = None
            if approve:
                unit = Unit(row.property_id, row.stay_date)
                claim = self.ledger.claimed_on(unit)
                if claim is not None and claim.id != row.id:
                    # 사람이 승인했지만 그 사이 단위가 넘어갔다. **사람의 판단은
                    # 기록하고, 실행은 막는다.** 판단을 안 남기면 채택률이 거짓이 되고,
                    # 실행을 허용하면 한 단위 두 개입이 된다.
                    blocked = ("이 단위는 그 사이 다른 개입이 가져갔다 "
                               f"({claim.agent}/{claim.decision})")
                    verdict = Decision.SUPERSEDED

            s.add(HumanReview(
                intervention_id=intervention_id, reviewer=reviewer,
                decision=(Decision.APPROVED if approve else Decision.REJECTED).value,
                reason=reason, at=now,
            ))
            row.decision = verdict.value
            row.reason = (f"{reviewer}: {reason}" if reason else f"{reviewer} 판단")
            if blocked:
                row.reason += f" — {blocked}"
            s.commit()

            return {"ok": True, "intervention_id": intervention_id,
                    "human_decision": (Decision.APPROVED if approve else Decision.REJECTED).value,
                    "final_decision": verdict.value,
                    "executed": verdict is Decision.APPROVED,
                    "blocked": blocked}

    # ------------------------------------------------------------ 지표
    def adoption(self, agent: str | None = None) -> Adoption:
        """**AI 권고 채택률.** 사람이 실제로 판단한 것만 분모에 넣는다.

        정책이 막은 것은 여기 안 들어간다. 예산이 모자라 거절된 제안은 "사람이
        AI 를 안 믿었다" 가 아니고, 섞으면 예산을 줄이는 것만으로 채택률이 떨어진다.
        """
        with Session(self.ledger.engine) as s:
            stmt = select(HumanReview.decision, func.count(HumanReview.id))
            if agent is not None:
                stmt = stmt.join(Intervention, Intervention.id == HumanReview.intervention_id)
                stmt = stmt.where(Intervention.agent == agent)
            rows = s.execute(stmt.group_by(HumanReview.decision)).all()
            counted = {d: int(n) for d, n in rows}

            pend = select(func.count(Intervention.id)).where(
                Intervention.decision == Decision.DEFERRED.value,
                Intervention.id.not_in(select(HumanReview.intervention_id)),
            )
            if agent is not None:
                pend = pend.where(Intervention.agent == agent)
            pending = int(s.execute(pend).scalar() or 0)

        accepted = counted.get(Decision.APPROVED.value, 0)
        return Adoption(reviewed=sum(counted.values()), accepted=accepted, pending=pending)

    def summary(self) -> Summary:
        counts = self.ledger.counts()
        # 정책 통과율의 분모: 조정자가 **판정한** 것. 홀드아웃은 통과한 것으로 센다 —
        # 정책을 다 통과했고 측정을 위해 실행만 안 한 것이다.
        passed = (counts.get(Decision.APPROVED.value, 0)
                  + counts.get(Decision.HELD_OUT.value, 0))
        judged = passed + counts.get(Decision.REJECTED.value, 0)
        return Summary(
            counts=counts,
            by_agent=self.ledger.by_agent(),
            spent=self.ledger.spent(),
            policy_pass_rate=(passed / judged if judged else None),
            adoption=self.adoption(),
        )

    # ------------------------------------------------------------ 내부
    @staticmethod
    def _reviews_for(s: Session, ids: list[int]) -> dict[int, HumanReview]:
        if not ids:
            return {}
        rows = s.execute(
            select(HumanReview).where(HumanReview.intervention_id.in_(ids))
        ).scalars().all()
        return {r.intervention_id: r for r in rows}

    @staticmethod
    def _view(row: Intervention, review: HumanReview | None) -> dict:
        return {
            "id": row.id,
            "unit": f"{row.property_id}@{row.stay_date.isoformat()}",
            "agent": row.agent, "action": row.action, "cost": row.cost,
            "decision": row.decision,
            # 왜 그렇게 됐는지. 이유 없는 거절은 콘솔에서 아무 도움이 안 된다.
            "reason": row.reason,
            "reviewed_by": review.reviewer if review else None,
            "human_decision": review.decision if review else None,
        }


__all__ = ["Adoption", "Console", "HumanReview", "Summary"]
