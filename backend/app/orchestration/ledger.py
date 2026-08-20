"""개입 원장 — **누가 언제 어느 단위에 무엇을 했나.**

`docs/multi-agent-orchestration.md` 의 B1. 화려하지 않아서 계획에서 빠지기 쉬운데,
오케스트레이션의 **첫 번째 비용**이 여기다.

## 왜 필요한가

에이전트가 하나일 때는 프로세스 메모리로 충분했다. 여럿이 **같은 숙소·같은 날짜**를
건드리는 순간 "누가 이미 손댔나" 를 물을 곳이 없고, 그 질문에 답하지 못하면 조정자가
할 수 있는 일이 없다.

이 원장은 소프트웨어 취향이 아니라 **측정 요구**에서 나온다. 한 단위에 두 에이전트가
개입하면 점유율이 올라도 어느 쪽 때문인지 영영 모른다 — 홀드아웃 설계가 통째로
무의미해진다.

## 거절도 남긴다

실행된 것만 남기면 "AI 가 뭘 하려 했는데 정책이 막았나" 를 볼 수 없다. 그게
거버넌스에서 실제로 보는 숫자이고, 이미 있는 **권고 채택률**과 같은 계열이다.

## 왜 파일이 아니라 DB 인가

여러 프로세스가 같이 본다. 조정자가 한 단위를 잡는 동안 다른 에이전트가 같은 단위를
잡으면 "한 단위 한 개입" 이 깨지는데, 그 경합은 애플리케이션 검사로 못 막는다.
**부분 유니크 인덱스로 DB 가 보장한다** — 승인된 개입은 단위마다 하나뿐이다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    Column, Date, DateTime, Index, Integer, String, Text, create_engine, func, select, text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, declarative_base

#: 원장 주소. 상담 에이전트의 상태와 **다른 저장소**다 — 개입은 상담 도메인이
#: 아니고, 같은 DB 에 넣으면 스키마가 서로 묶인다.
LEDGER_URL = os.getenv("INTERVENTION_LEDGER_URL", "sqlite:///./interventions.db")

Base = declarative_base()


class Decision(str, Enum):
    """조정자의 답. **거절도 결정이다.**"""

    APPROVED = "APPROVED"        # 실행해도 된다
    REJECTED = "REJECTED"        # 정책이 막았다
    DEFERRED = "DEFERRED"        # 사람 승인 대기
    SUPERSEDED = "SUPERSEDED"    # 같은 단위를 다른 제안이 먼저 잡았다


class Intervention(Base):
    __tablename__ = "interventions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ── 단위. 이 둘이 "어디에 손댔나" 를 정한다.
    property_id = Column(String(64), nullable=False, index=True)
    stay_date = Column(Date, nullable=False, index=True)

    agent = Column(String(40), nullable=False)      # promotion / content / support
    action = Column(String(40), nullable=False)
    #: 이 개입이 쓰는 돈. 공유 예산을 이 값으로 센다.
    cost = Column(Integer, nullable=False, default=0)

    decision = Column(String(16), nullable=False)
    #: 왜 그렇게 결정했는지. 거절 사유가 없으면 원장이 숫자만 남기고 이유를 잃는다.
    reason = Column(Text, nullable=False, default="")

    #: 같은 제안이 두 번 오면 한 번만 센다. 재시도는 정상 동작이다.
    request_id = Column(String(64), nullable=False, unique=True)

    proposed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        # **한 단위에는 승인된 개입이 하나뿐이다.**
        #
        # 애플리케이션에서 "이미 있나" 를 확인하고 넣으면 두 프로세스가 그 사이에
        # 끼어들 수 있다. 부분 유니크 인덱스는 그 경합을 DB 가 막게 한다 —
        # 거절·보류는 여럿이어도 되므로 조건부다.
        Index(
            "uq_approved_per_unit", "property_id", "stay_date",
            unique=True, sqlite_where=text("decision = 'APPROVED'"),
            postgresql_where=text("decision = 'APPROVED'"),
        ),
    )


@dataclass(frozen=True)
class Unit:
    """개입 단위. 숙소 하나의 하루."""

    property_id: str
    stay_date: date

    def __str__(self) -> str:
        return f"{self.property_id}@{self.stay_date:%Y-%m-%d}"


class Ledger:
    def __init__(self, url: str | None = None):
        self.url = url or LEDGER_URL
        connect_args = {"check_same_thread": False} if self.url.startswith("sqlite") else {}
        self.engine = create_engine(self.url, connect_args=connect_args, future=True)
        Base.metadata.create_all(self.engine)

    # ------------------------------------------------------------ 쓰기
    def write(self, unit: Unit, agent: str, action: str, decision: Decision,
              reason: str, request_id: str, cost: int = 0) -> bool:
        """한 건을 남긴다.

        Returns:
            새로 기록됐으면 ``True``. 이미 같은 단위에 승인이 있거나 같은
            ``request_id`` 가 있으면 ``False`` — **예외가 아니라 사실이다.**
            재시도와 경합은 정상 동작이므로 호출부가 감쌀 일이 아니다.
        """
        row = Intervention(
            property_id=unit.property_id, stay_date=unit.stay_date,
            agent=agent, action=action, cost=cost,
            decision=decision.value, reason=reason, request_id=request_id,
        )
        with Session(self.engine) as s:
            s.add(row)
            try:
                s.commit()
                return True
            except IntegrityError:
                s.rollback()
                return False

    # ------------------------------------------------------------ 읽기
    def approved_on(self, unit: Unit) -> Intervention | None:
        """이 단위에 이미 승인된 개입. 조정자가 가장 먼저 묻는 질문이다."""
        with Session(self.engine) as s:
            return s.execute(
                select(Intervention).where(
                    Intervention.property_id == unit.property_id,
                    Intervention.stay_date == unit.stay_date,
                    Intervention.decision == Decision.APPROVED.value,
                )
            ).scalars().first()

    def spent(self, since: date | None = None, until: date | None = None) -> int:
        """승인된 개입이 쓴 돈. **거절된 것은 안 센다** — 안 쓴 돈이다."""
        stmt = select(func.coalesce(func.sum(Intervention.cost), 0)).where(
            Intervention.decision == Decision.APPROVED.value
        )
        if since:
            stmt = stmt.where(Intervention.stay_date >= since)
        if until:
            stmt = stmt.where(Intervention.stay_date <= until)
        with Session(self.engine) as s:
            return int(s.execute(stmt).scalar() or 0)

    def counts(self) -> dict[str, int]:
        """결정별 건수. 거절률이 여기서 나온다."""
        with Session(self.engine) as s:
            rows = s.execute(
                select(Intervention.decision, func.count(Intervention.id))
                .group_by(Intervention.decision)
            ).all()
        return {d: int(n) for d, n in rows}

    def by_agent(self) -> dict[str, dict[str, int]]:
        """에이전트별 결정 분포. **누가 자주 거절당하는지**를 본다."""
        with Session(self.engine) as s:
            rows = s.execute(
                select(Intervention.agent, Intervention.decision, func.count(Intervention.id))
                .group_by(Intervention.agent, Intervention.decision)
            ).all()
        out: dict[str, dict[str, int]] = {}
        for agent, decision, n in rows:
            out.setdefault(agent, {})[decision] = int(n)
        return out

    def clear(self) -> None:
        with Session(self.engine) as s:
            s.query(Intervention).delete()
            s.commit()


__all__ = ["Decision", "Intervention", "LEDGER_URL", "Ledger", "Unit"]
