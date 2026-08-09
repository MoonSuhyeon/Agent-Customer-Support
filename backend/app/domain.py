"""숙박 CS 도메인 모델과 저장소.

인메모리 구현이지만 **DB 제약을 흉내 낸다.** 특히 멱등성 키는 애플리케이션 로직이
아니라 저장소 수준의 유일성으로 막는다. 조회 후 실행 사이에 두 번째 요청이 끼어드는
경합을 성립시키지 않기 위해서다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum


class BookingStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class RefundStatus(str, Enum):
    NONE = "NONE"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"


@dataclass
class CancellationPolicy:
    """취소 정책. 체크인까지 남은 일수로 환불 비율이 정해진다."""

    policy_id: str
    name: str
    # (체크인까지 남은 최소 일수, 환불 비율)
    tiers: list[tuple[int, float]]

    def refund_ratio(self, days_before: int) -> float:
        for min_days, ratio in sorted(self.tiers, key=lambda t: -t[0]):
            if days_before >= min_days:
                return ratio
        return 0.0

    def describe(self) -> str:
        parts = [f"체크인 {d}일 전까지 {int(r * 100)}% 환불"
                 for d, r in sorted(self.tiers, key=lambda t: -t[0])]
        return ", ".join(parts) + ", 이후 환불 불가"


@dataclass
class Property:
    property_id: str
    name: str
    region: str
    policy_id: str


@dataclass
class Booking:
    booking_id: str
    customer_id: str
    property_id: str
    check_in: date
    amount: int
    status: BookingStatus = BookingStatus.CONFIRMED
    refund_status: RefundStatus = RefundStatus.NONE
    refunded_amount: int = 0

    def days_until_check_in(self, today: date | None = None) -> int:
        return (self.check_in - (today or date.today())).days


class DuplicateRequest(Exception):
    """멱등성 키 충돌. 저장소가 던진다."""

    def __init__(self, key: str, stored: dict):
        super().__init__(f"idempotency key 중복: {key}")
        self.key = key
        self.stored = stored


class PaymentGatewayError(Exception):
    """외부 PG 실패. 보상 트랜잭션 대상."""


@dataclass
class Store:
    """예약·숙소·정책 저장소 + 멱등성 테이블 + 감사 로그."""

    bookings: dict[str, Booking] = field(default_factory=dict)
    properties: dict[str, Property] = field(default_factory=dict)
    policies: dict[str, CancellationPolicy] = field(default_factory=dict)
    _idempotency: dict[str, dict] = field(default_factory=dict)
    audit: list[dict] = field(default_factory=list)

    # 외부 PG 를 실패시키고 싶을 때 (보상 트랜잭션 테스트용)
    pg_should_fail: bool = False
    # 보상까지 실패시키고 싶을 때 (에스컬레이션 테스트용)
    compensation_should_fail: bool = False

    # ------------------------------------------------------------ 조회
    def get_booking(self, booking_id: str) -> Booking | None:
        return self.bookings.get(booking_id)

    def get_property(self, property_id: str) -> Property | None:
        return self.properties.get(property_id)

    def get_policy(self, property_id: str) -> CancellationPolicy | None:
        prop = self.get_property(property_id)
        if prop is None:
            return None
        return self.policies.get(prop.policy_id)

    # -------------------------------------------------- 멱등성 (DB 제약 역할)
    def claim(self, key: str) -> None:
        """멱등성 키를 선점한다. 이미 있으면 예외.

        실제 구현에서는 ``UNIQUE(idempotency_key)`` 제약이 이 역할을 한다.
        """
        if key in self._idempotency:
            raise DuplicateRequest(key, self._idempotency[key])
        self._idempotency[key] = {"_state": "IN_PROGRESS"}

    def complete(self, key: str, result: dict) -> None:
        # 업무 결과를 펼쳐 담지 않고 감싼다.
        # result 에도 status 같은 키가 있어 레코드 상태를 덮어쓸 수 있기 때문이다.
        self._idempotency[key] = {"_state": "DONE", "result": dict(result)}

    def release(self, key: str) -> None:
        """실패해서 되돌릴 때만 쓴다."""
        self._idempotency.pop(key, None)

    def stored_result(self, key: str) -> dict | None:
        r = self._idempotency.get(key)
        return dict(r["result"]) if r and r.get("_state") == "DONE" else None

    # ------------------------------------------------------------ 상태 변경
    def cancel(self, booking_id: str) -> Booking:
        b = self.bookings[booking_id]
        b.status = BookingStatus.CANCELLED
        self._log("cancel_booking", booking_id=booking_id)
        return b

    def restore(self, booking_id: str) -> Booking:
        """보상 트랜잭션 — 취소를 되돌린다."""
        if self.compensation_should_fail:
            raise PaymentGatewayError("보상 트랜잭션 실패")
        b = self.bookings[booking_id]
        b.status = BookingStatus.CONFIRMED
        self._log("restore_booking", booking_id=booking_id)
        return b

    def refund(self, booking_id: str, amount: int) -> Booking:
        if self.pg_should_fail:
            self._log("refund_failed", booking_id=booking_id, amount=amount)
            raise PaymentGatewayError("외부 PG 환불 거절")
        b = self.bookings[booking_id]
        b.refund_status = RefundStatus.REFUNDED
        b.refunded_amount = amount
        self._log("process_refund", booking_id=booking_id, amount=amount)
        return b

    def _log(self, action: str, **kw) -> None:
        self.audit.append({"action": action, "at": datetime.utcnow(), **kw})


def seed(today: date | None = None) -> Store:
    """데모·테스트용 시드 데이터."""
    today = today or date.today()
    s = Store()
    s.policies["FLEX"] = CancellationPolicy(
        "FLEX", "유연", [(7, 1.0), (3, 0.5), (1, 0.2)]
    )
    s.policies["STRICT"] = CancellationPolicy(
        "STRICT", "엄격", [(14, 1.0), (7, 0.5)]
    )
    s.properties["P001"] = Property("P001", "제주 오션 스테이", "Jeju", "FLEX")
    s.properties["P002"] = Property("P002", "부산 하버 호텔", "Busan", "STRICT")
    # 정책이 등록되지 않은 숙소 — 조회 실패 경로 검증용
    s.properties["P999"] = Property("P999", "정책 미등록 숙소", "Seoul", "MISSING")

    s.bookings["B1001"] = Booking("B1001", "C1", "P001", today + timedelta(days=1), 180_000)
    s.bookings["B1002"] = Booking("B1002", "C1", "P001", today + timedelta(days=10), 240_000)
    s.bookings["B1003"] = Booking("B1003", "C2", "P002", today + timedelta(days=5), 300_000)
    s.bookings["B1004"] = Booking("B1004", "C3", "P999", today + timedelta(days=3), 150_000)
    return s


__all__ = [
    "Booking", "BookingStatus", "CancellationPolicy", "DuplicateRequest",
    "PaymentGatewayError", "Property", "RefundStatus", "Store", "seed",
]
