"""프로모션 쓰기 도구 — **결정과 실행 사이를 잇는다.**

`docs/multi-agent-orchestration.md` 의 A3. 조정자가 정한 것을 실제로 거는 자리다.

## 이 도구가 실제로 막는 것

멱등성만 있는 쓰기 도구는 흔하다. 여기서 중요한 건 그게 아니다.

**원장이 승인하지 않은 개입은 실행되지 않는다.** 조정자가 `HELD_OUT` 으로 남긴
단위에 이 도구가 할인을 걸 수 있으면, 홀드아웃은 강제가 아니라 권고다. 그리고
권고는 언젠가 어겨진다 — 재시도 스크립트 하나, 손으로 돌린 배치 하나면 충분하다.
그때 그 단위는 대조군도 개입군도 아닌 게 되고, **그 사실은 아무 데도 안 남는다.**

그래서 실행 전에 원장을 묻는다. 조정자를 거치지 않은 호출은 거절된다.

## 되돌리기가 원상복구가 아닌 이유

할인을 내려도 **그동안 들어온 예약은 그대로 남는다.** 5시간 동안 20% 할인이 걸려
있었다면 그 5시간은 일어난 일이고, 되돌린다고 없던 일이 되지 않는다.

그러므로 행을 지우지 않는다. `applied_at` 과 `reverted_at` 을 남겨서 **노출 구간**을
남긴다. 지워 버리면 그 구간에 들어온 예약이 아무 개입에도 귀속되지 않고, 홀드아웃
대비 효과가 조용히 희석된다.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Index, Integer, String, Text, select, text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.orchestration.ledger import Base, Decision, Ledger, Unit


def promotion_key(unit: Unit, agent: str, request_id: str) -> str:
    """멱등성 키. **단위와 요청을 함께 묶는다.**

    `request_id` 만 쓰면 서로 다른 에이전트가 같은 문자열을 만들었을 때 한쪽 결과가
    다른 쪽으로 새어 나간다.
    """
    raw = f"{unit.property_id}:{unit.stay_date.isoformat()}:{agent}:{request_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class Promotion(Base):
    __tablename__ = "promotions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    property_id = Column(String(64), nullable=False, index=True)
    stay_date = Column(String(10), nullable=False, index=True)
    agent = Column(String(40), nullable=False)
    discount_pct = Column(Integer, nullable=False)

    #: 멱등성 키. 같은 요청이 두 번 오면 같은 행을 본다.
    key = Column(String(64), nullable=False, unique=True)

    applied_at = Column(DateTime, nullable=False)
    #: 내린 시각. **행을 지우지 않는 이유가 이 컬럼이다** — 걸려 있던 구간이
    #: 남아야 그동안 들어온 예약을 어느 개입에 귀속할지 말할 수 있다.
    reverted_at = Column(DateTime, nullable=True)
    reverted_reason = Column(Text, nullable=False, default="")

    __table_args__ = (
        # 한 단위에 살아 있는 프로모션은 하나뿐이다. 내려간 것은 세지 않는다 —
        # 그래야 내렸다가 다시 거는 것이 가능하다.
        Index("uq_live_promotion_per_unit", "property_id", "stay_date",
              unique=True,
              sqlite_where=text("reverted_at IS NULL"),
              postgresql_where=text("reverted_at IS NULL")),
    )


@dataclass
class PromoResult:
    ok: bool
    data: dict
    error: str | None = None

    def __str__(self) -> str:
        head = "OK" if self.ok else "FAIL"
        return f"{head} {self.data or self.error}"


class PromotionTools:
    """상태를 바꾼다. **원장의 승인 없이는 아무것도 안 한다.**"""

    def __init__(self, ledger: Ledger):
        self.ledger = ledger
        Base.metadata.create_all(ledger.engine)

    # ------------------------------------------------------------ 걸기
    def apply(self, unit: Unit, agent: str, discount_pct: int,
              request_id: str) -> PromoResult:
        """할인을 건다.

        같은 `request_id` 로 두 번 부르면 **두 번째는 아무것도 하지 않고** 첫
        번째 결과를 그대로 돌려준다. 재시도는 정상 동작이지 오류가 아니다.
        """
        if not 0 < discount_pct <= 100:
            return PromoResult(False, {}, "할인율은 0 초과 100 이하여야 한다")

        key = promotion_key(unit, agent, request_id)

        # 1) 멱등성 — 이미 처리한 요청인가
        existing = self._by_key(key)
        if existing is not None:
            return PromoResult(True, {**existing, "idempotent_replay": True})

        # 2) 원장에 승인이 있는가. **이 검사가 이 도구의 존재 이유다.**
        claim = self.ledger.claimed_on(unit)
        if claim is None:
            return PromoResult(False, {}, (
                "조정자의 결정이 없는 단위다 — 원장을 거치지 않은 개입은 실행하지 않는다"))
        if claim.decision == Decision.HELD_OUT.value:
            return PromoResult(False, {"held_out": True}, (
                "이 단위는 홀드아웃이다 — 손대면 대조군이 오염되고, "
                "홀드아웃 대비 효과라는 숫자가 뜻을 잃는다"))
        if claim.decision != Decision.APPROVED.value:
            return PromoResult(False, {}, f"승인되지 않은 단위다 ({claim.decision})")
        if claim.agent != agent:
            # 승인은 에이전트마다 난다. 남의 승인으로 실행하면 원장의 "누가" 가
            # 거짓이 되고, 에이전트별 채택률이 엉뚱한 쪽에 붙는다.
            return PromoResult(False, {}, (
                f"이 단위의 승인은 {claim.agent} 에게 났다 — {agent} 가 실행할 수 없다"))

        # 3) 쓴다. 동시에 들어온 같은 단위는 **DB 가 막는다.**
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with Session(self.ledger.engine) as s:
            row = Promotion(
                property_id=unit.property_id, stay_date=unit.stay_date.isoformat(),
                agent=agent, discount_pct=discount_pct, key=key, applied_at=now,
            )
            s.add(row)
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
                live = self._live(unit)
                if live is not None:
                    return PromoResult(False, {"live_key": live["key"]},
                                       "이 단위에는 이미 살아 있는 프로모션이 있다")
                return PromoResult(False, {}, "같은 요청이 동시에 처리됐다")
            return PromoResult(True, self._view(row))

    # ---------------------------------------------------------- 되돌리기
    def revert(self, unit: Unit, request_id: str, reason: str = "") -> PromoResult:
        """할인을 내린다. **원상복구가 아니다.**

        걸려 있던 구간(`applied_at` ~ `reverted_at`)은 남는다. 그동안 들어온 예약은
        그 개입 때문에 들어왔을 수 있고, 행을 지우면 그 예약들이 아무 개입에도
        귀속되지 않는다.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with Session(self.ledger.engine) as s:
            row = s.execute(
                select(Promotion).where(
                    Promotion.property_id == unit.property_id,
                    Promotion.stay_date == unit.stay_date.isoformat(),
                    Promotion.reverted_at.is_(None),
                )
            ).scalars().first()

            if row is None:
                # 이미 내렸는가, 아니면 애초에 없었는가. **다른 사실이다.**
                last = s.execute(
                    select(Promotion)
                    .where(Promotion.property_id == unit.property_id,
                           Promotion.stay_date == unit.stay_date.isoformat())
                    .order_by(Promotion.id.desc())
                ).scalars().first()
                if last is not None:
                    return PromoResult(True, {**self._view(last), "already_reverted": True})
                return PromoResult(False, {}, "이 단위에 걸린 프로모션이 없다")

            applied_at = row.applied_at
            row.reverted_at = now
            row.reverted_reason = reason or f"revert:{request_id}"
            s.commit()
            view = self._view(row)

        return PromoResult(True, {
            **view,
            # 되돌렸어도 노출은 일어났다. 이 숫자가 없으면 "걸었다가 내렸으니
            # 없던 일" 이라고 읽게 된다.
            "exposed_seconds": round((now - applied_at).total_seconds(), 3),
            "note": "이 구간에 들어온 예약은 그대로 남는다 — 되돌리기는 원상복구가 아니다",
        })

    # ------------------------------------------------------------ 조회
    def live(self, unit: Unit) -> dict | None:
        """지금 걸려 있는 프로모션."""
        return self._live(unit)

    def history(self, unit: Unit) -> list[dict]:
        """건 것과 내린 것을 시간순으로. 지우지 않으므로 전부 남는다."""
        with Session(self.ledger.engine) as s:
            rows = s.execute(
                select(Promotion)
                .where(Promotion.property_id == unit.property_id,
                       Promotion.stay_date == unit.stay_date.isoformat())
                .order_by(Promotion.id)
            ).scalars().all()
            return [self._view(r) for r in rows]

    # ------------------------------------------------------------ 내부
    def _by_key(self, key: str) -> dict | None:
        with Session(self.ledger.engine) as s:
            row = s.execute(
                select(Promotion).where(Promotion.key == key)
            ).scalars().first()
            return self._view(row) if row is not None else None

    def _live(self, unit: Unit) -> dict | None:
        with Session(self.ledger.engine) as s:
            row = s.execute(
                select(Promotion).where(
                    Promotion.property_id == unit.property_id,
                    Promotion.stay_date == unit.stay_date.isoformat(),
                    Promotion.reverted_at.is_(None),
                )
            ).scalars().first()
            return self._view(row) if row is not None else None

    @staticmethod
    def _view(row: Promotion) -> dict:
        return {
            "property_id": row.property_id, "stay_date": row.stay_date,
            "agent": row.agent, "discount_pct": row.discount_pct, "key": row.key,
            "applied_at": row.applied_at.isoformat(),
            "reverted_at": row.reverted_at.isoformat() if row.reverted_at else None,
            "live": row.reverted_at is None,
        }


__all__ = ["PromoResult", "Promotion", "PromotionTools", "promotion_key"]
