"""간섭 — **에이전트가 서로를 모른 채 같은 단위를 흔든다.**

`docs/multi-agent-orchestration.md` 의 B3.

## 재현하려는 사고

상담 에이전트는 자기 일만 한다. 고객이 취소를 요청하면 취소하고 환불한다. 그건
상담 도메인 안에서 완결된 옳은 행동이다.

그런데 그 취소는 **그 숙소·그 날짜의 재고를 바꾼다.** 마침 그 단위에 저수요
에이전트의 할인이 걸려 있었다면, 점유율은 오르는데 그중 얼마가 할인 때문이고
얼마가 "방이 하나 다시 나왔기 때문" 인지 갈 수 없다.

아무도 잘못하지 않았다. 조정자의 규칙 1(한 단위 한 개입)도 안 깨졌다 — 상담은
개입을 신청한 적이 없으니까. **그런데 측정은 깨졌다.**

## 그래서 무엇을 하는가

되돌리지 않는다. 취소는 고객이 요청한 것이고 측정을 위해 막을 일이 아니다.
대신 **그 단위에 흔들림이 있었다는 사실을 남긴다.** 남기지 않으면 그 단위는
멀쩡한 표본인 척 평균에 섞이고, 효과 추정이 이유 없이 흐려진다.

## 홀드아웃도 흔들린다

놓치기 쉬운 쪽이다. 홀드아웃은 "아무도 손대지 않은 단위" 가 아니라 **"개입
에이전트가 손대지 않은 단위"** 다. 상담 취소는 대조군에도 똑같이 들어오고,
그러면 대조군이 조용히 다른 집단이 된다. 여기서는 양쪽 모두 흔들림으로 센다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Column, DateTime, Index, Integer, String, Text, select,
)
from sqlalchemy.orm import Session

from app.orchestration.ledger import Base, Decision, Ledger, Unit


class ChangeKind(str, Enum):
    """다른 도메인이 만든 사실. **개입이 아니다** — 신청도 승인도 없었다."""

    CANCELLATION = "CANCELLATION"    # 예약이 빠졌다 — 재고가 늘었다
    REBOOKING = "REBOOKING"          # 다른 날짜로 옮겨 갔다
    BLOCKED = "BLOCKED"              # 호스트가 날짜를 닫았다


@dataclass(frozen=True)
class StateChange:
    """상담 도메인에서 넘어온 사건."""

    unit: Unit
    kind: ChangeKind
    source: str = "support"
    detail: str = ""


class Disturbance(Base):
    """흔들린 단위. **개입 원장과 다른 표다.**

    같은 표에 넣고 싶어지지만 그러면 "무엇을 하려 했나" 와 "무엇이 일어났나" 가
    섞인다. 원장은 조정자의 결정을 남기는 곳이고, 여기는 그 결정과 무관하게
    벌어진 일을 남기는 곳이다.
    """

    __tablename__ = "disturbances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(String(64), nullable=False, index=True)
    stay_date = Column(String(10), nullable=False, index=True)

    kind = Column(String(20), nullable=False)
    source = Column(String(40), nullable=False)
    #: 흔들린 시점에 이 단위가 어느 군이었나. 나중에 원장을 다시 뒤지면 그 사이
    #: 결정이 바뀌었을 수 있어서, **그때의 사실**을 여기 박아 둔다.
    arm_at_the_time = Column(String(16), nullable=False, default="")
    detail = Column(Text, nullable=False, default="")
    at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_disturbance_unit", "property_id", "stay_date"),
    )


class Interference:
    """다른 도메인의 사건을 받아 측정에 미치는 영향을 남긴다."""

    def __init__(self, ledger: Ledger):
        self.ledger = ledger
        Base.metadata.create_all(ledger.engine)

    # ------------------------------------------------------------ 기록
    def record(self, change: StateChange) -> dict:
        """사건을 남긴다. **막지 않는다.**

        취소는 고객이 요청한 것이다. 측정을 위해 막는 순간 이 시스템은 사업을
        방해하는 물건이 된다. 남기는 것과 막는 것은 다르다.
        """
        claim = self.ledger.claimed_on(change.unit)
        arm = ""
        if claim is not None:
            arm = ("treated" if claim.decision == Decision.APPROVED.value
                   else "holdout" if claim.decision == Decision.HELD_OUT.value else "")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with Session(self.ledger.engine) as s:
            row = Disturbance(
                property_id=change.unit.property_id,
                stay_date=change.unit.stay_date.isoformat(),
                kind=change.kind.value, source=change.source,
                arm_at_the_time=arm, detail=change.detail, at=now,
            )
            s.add(row)
            s.commit()

        return {
            "unit": str(change.unit), "kind": change.kind.value,
            "arm": arm or None,
            # 어느 군에도 안 든 단위의 흔들림은 그냥 재고 소식이다. 측정에 영향이
            # 없으므로 표본에서 뺄 이유도 없다.
            "affects_measurement": bool(arm),
            "note": ("대조군이 흔들렸다 — 홀드아웃은 '아무도 손대지 않은 단위' 가 "
                     "아니라 '개입 에이전트가 손대지 않은 단위' 다"
                     if arm == "holdout" else ""),
        }

    # ------------------------------------------------------------ 조회
    def disturbed(self) -> set[tuple[str, str]]:
        """측정에 영향을 주는 흔들림이 있었던 단위.

        효과를 잴 때 이 단위들을 **빼거나 따로 봐야 한다.** 그냥 섞으면 멀쩡한
        표본인 척 평균에 들어가고, 추정이 이유 없이 흐려진다.
        """
        with Session(self.ledger.engine) as s:
            rows = s.execute(
                select(Disturbance.property_id, Disturbance.stay_date)
                .where(Disturbance.arm_at_the_time != "")
            ).all()
        return {(r.property_id, r.stay_date) for r in rows}

    def counts_by_arm(self) -> dict[str, int]:
        """군별 흔들림 건수.

        **한쪽만 흔들렸으면 그 자체가 신호다.** 개입군에만 취소가 몰렸다면 할인이
        취소를 유발했을 수도 있고, 그건 효과가 아니라 부작용이다.
        """
        with Session(self.ledger.engine) as s:
            rows = s.execute(select(Disturbance.arm_at_the_time)).scalars().all()
        out: dict[str, int] = {}
        for arm in rows:
            out[arm or "unassigned"] = out.get(arm or "unassigned", 0) + 1
        return out

    def history(self, unit: Unit) -> list[dict]:
        with Session(self.ledger.engine) as s:
            rows = s.execute(
                select(Disturbance)
                .where(Disturbance.property_id == unit.property_id,
                       Disturbance.stay_date == unit.stay_date.isoformat())
                .order_by(Disturbance.id)
            ).scalars().all()
            return [{"kind": r.kind, "source": r.source, "arm": r.arm_at_the_time or None,
                     "detail": r.detail, "at": r.at.isoformat()} for r in rows]

    # ------------------------------------------------------------ 재판정
    def needs_reappraisal(self, changes: list[StateChange]) -> list[Unit]:
        """다시 판단해야 하는 단위.

        재고가 늘었으면 수요 예측의 전제가 바뀌었다. 그런데 **여기서 다시 승인하지
        않는다.** 조정자에게 돌려보낼 뿐이다 — 예산·자율성·홀드아웃이 그대로 걸려야
        하고, 특히 홀드아웃 군은 재판정으로도 바뀌지 않아야 한다. 배정이 결정적
        해시라 그 성질은 공짜로 따라온다.
        """
        return [c.unit for c in changes if c.kind is ChangeKind.CANCELLATION]


__all__ = ["ChangeKind", "Disturbance", "Interference", "StateChange"]
