"""예약 서비스에서 진짜 예약을 읽어 온다.

## 왜 필요한가

이 에이전트는 자기 `Store` 에 데모 예약 네 건(B1001~B1004)을 하드코딩해 두고
있었다. 고객 화면에서 문의를 열면 `BK2608190016` 같은 **실제 예약번호**가 오는데,
그 store 는 그런 예약을 영영 못 찾는다. 실제 예약 100% 에서 실패하는 셈이라
버튼을 만들어도 죽은 버튼이 된다.

## 무엇을 누가 소유하는가

**예약은 예약 서비스가, 취소 정책은 이 에이전트가 소유한다.**

예약 서비스에는 취소 정책이라는 개념이 아예 없다 — 환불하면 늘 전액이다.
정책을 해석하고 "체크인이 이틀 남았으니 20% 입니다" 라고 설명하는 것이 이
에이전트의 존재 이유이므로, 정책은 여기 남는다.

## 남의 예약을 못 읽는다 — 구조로

`/bookings/{id}` 로 직접 조회하지 않고 **`/bookings/me` 를 호출자의 토큰으로**
부른 뒤 그 목록에서 번호로 찾는다. 한 번 더 도는 대신, 에이전트가 볼 수 있는
범위가 **호출자 본인의 예약으로 좁혀진다.** 권한 검사를 따로 짜서 지키는 것보다
애초에 볼 수 없게 만드는 편이 낫다.

## 지금은 읽기만 한다

취소·환불 쓰기는 아직 이 경로로 안 간다. 조회만으로도 "정책과 환불 예상액을
확인하는" 상담은 성립하고, 쓰기에는 멱등성·보상 트랜잭션이 따라붙어 따로 다뤄야
한다. **그래서 쓰기는 조용히 실패하지 않고 소리 내어 막는다** — 아무 일도 안
일어났는데 취소됐다고 답하는 것이 최악이다.
"""
from __future__ import annotations

import os
from contextvars import ContextVar
from datetime import date, datetime

import httpx

from app.domain import (
    Booking, BookingStatus, CancellationPolicy, PaymentGatewayError, Property, Store,
)

#: 예약 서비스 주소.
BOOKING_API_URL = os.getenv("BOOKING_API_URL", "http://127.0.0.1:8000")

#: 호출자의 토큰. 요청마다 다르고 그래프는 한 번만 만들어지므로, 인자로 넘길
#: 자리가 없다. **그래프 상태에 넣지는 않는다** — 상태는 체크포인터에 저장되고,
#: 거기 자격증명이 들어가면 대화 기록이 곧 토큰 보관소가 된다.
caller_token: ContextVar[str | None] = ContextVar("caller_token", default=None)

#: 요청 하나 안에서의 조회 결과.
#:
#: 그래프는 한 번 도는 동안 같은 예약을 두 번 읽는다 — `get_booking` 으로 한 번,
#: 환불 계산이 안에서 또 한 번. 메모리 store 였을 땐 공짜였지만 이제는 **네트워크
#: 왕복이 두 배**가 된다.
#:
#: 요청 범위로 둔다. 오래 들고 있으면 취소된 예약을 취소 전 상태로 계속 보게
#: 되고, 그건 캐시가 아니라 거짓말이다.
_request_cache: ContextVar[dict | None] = ContextVar("_request_cache", default=None)

#: 이 에이전트가 적용하는 취소 정책.
#:
#: 예약 서비스가 숙소별 정책을 아직 안 들고 있어서 **모든 숙소에 같은 것**이
#: 적용된다. 숨기지 않는다 — 숙소마다 다른 정책이 필요해지면 예약 서비스가
#: 그 값을 갖는 것이 맞고, 그때 이 상수는 기본값으로 물러난다.
STANDARD_POLICY = CancellationPolicy(
    policy_id="STANDARD",
    name="표준 취소 정책",
    tiers=[(7, 1.0), (3, 0.5), (1, 0.2)],
)

#: 원격 예약이 가리키는 가상의 숙소 id. 정책이 숙소별로 갈리지 않으므로 하나면 된다.
REMOTE_PROPERTY_ID = "REMOTE"


class RemoteBookingUnavailable(RuntimeError):
    """예약 서비스에 못 닿았다. **'예약이 없다' 와 다른 사실이다.**"""


def _to_status(raw: str) -> BookingStatus:
    if raw in ("CANCELLED", "REFUNDED"):
        return BookingStatus.CANCELLED
    return BookingStatus.CONFIRMED


def _to_date(raw: str) -> date:
    # `2026-08-19T15:00:00` 처럼 시각이 붙어 온다. 정책은 날짜 단위다.
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()


class RemoteStore(Store):
    """조회는 예약 서비스에서, 정책은 여기서.

    `Store` 를 상속한다 — 도구(`ReadTools`)와 그래프는 이미 이 인터페이스만
    알고 있으므로, 이 클래스를 끼우면 그 위쪽은 바뀔 것이 없다.
    """

    def __init__(self, base_url: str | None = None, timeout: float = 5.0):
        super().__init__()
        self.base_url = (base_url or BOOKING_API_URL).rstrip("/")
        self.timeout = timeout
        self.policies[STANDARD_POLICY.policy_id] = STANDARD_POLICY
        self.properties[REMOTE_PROPERTY_ID] = Property(
            property_id=REMOTE_PROPERTY_ID, name="", region="",
            policy_id=STANDARD_POLICY.policy_id,
        )

    # ------------------------------------------------------------ 조회
    def get_booking(self, booking_id: str) -> Booking | None:
        cache = _request_cache.get()
        if cache is not None and booking_id in cache:
            return cache[booking_id]

        found = self._fetch_booking(booking_id)
        if cache is not None:
            cache[booking_id] = found
        return found

    def _uuid_of(self, booking_id: str) -> str | None:
        """예약번호 → UUID.

        예약 서비스의 환불·견적 경로는 UUID 로 받는데 에이전트가 아는 것은
        `BK...` 번호다. 목록을 읽을 때 같이 기억해 둔다.
        """
        cache = _request_cache.get()
        if cache is None or f"uuid:{booking_id}" not in cache:
            self.get_booking(booking_id)     # 목록을 읽으면서 채워진다
            cache = _request_cache.get()
        return (cache or {}).get(f"uuid:{booking_id}")

    def refund_quote(self, booking_id: str) -> dict | None:
        """환불 예상액을 **예약 서비스에 묻는다.**

        여기서 직접 계산하지 않는다. 돈을 소유한 쪽이 정책을 갖고 있고, 승인
        뒤 실제로 깎는 것도 같은 규칙이다 — 물어보면 설명과 집행이 어긋날 수 없다.
        """
        uid = self._uuid_of(booking_id)
        if uid is None:
            return None
        data = self._get(f"/api/v1/bookings/{uid}/refund-quote")
        return {
            "original_amount": data["total_price"],
            "days_until_check_in": data["days_until_check_in"],
            "refund_ratio": data["refund_ratio"],
            "refund_amount": data["refund_amount"],
            "policy": data["policy_description"],
        }

    def _get(self, path: str) -> dict:
        token = caller_token.get()
        if not token:
            raise RemoteBookingUnavailable("호출자 인증 정보가 없어 예약을 조회할 수 없다")
        try:
            r = httpx.get(f"{self.base_url}{path}",
                          headers={"Authorization": f"Bearer {token}"},
                          timeout=self.timeout)
        except httpx.HTTPError as e:
            raise RemoteBookingUnavailable(f"예약 서비스에 닿지 못했다: {e}") from e
        if r.status_code == 401:
            raise RemoteBookingUnavailable("예약 서비스가 인증을 거절했다")
        if r.status_code >= 400:
            raise RemoteBookingUnavailable(f"예약 서비스가 {r.status_code} 로 답했다")
        return r.json()

    def _fetch_booking(self, booking_id: str) -> Booking | None:
        token = caller_token.get()
        if not token:
            # 토큰이 없으면 남의 예약을 볼 수 없는 것이 아니라 **아무 예약도**
            # 볼 수 없다. 조용히 None 을 주면 "그런 예약 없음" 으로 읽힌다.
            raise RemoteBookingUnavailable("호출자 인증 정보가 없어 예약을 조회할 수 없다")

        try:
            r = httpx.get(
                f"{self.base_url}/api/v1/bookings/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as e:
            raise RemoteBookingUnavailable(f"예약 서비스에 닿지 못했다: {e}") from e

        if r.status_code == 401:
            raise RemoteBookingUnavailable("예약 서비스가 인증을 거절했다")
        if r.status_code >= 400:
            raise RemoteBookingUnavailable(f"예약 서비스가 {r.status_code} 로 답했다")

        cache = _request_cache.get()
        for row in r.json():
            if cache is not None and row.get("id"):
                cache[f"uuid:{row['booking_number']}"] = row["id"]
            if row.get("booking_number") != booking_id:
                continue
            return Booking(
                booking_id=booking_id,
                # 목록 자체가 호출자의 것이라, 누구 예약인지는 더 물을 필요가 없다.
                customer_id="self",
                property_id=REMOTE_PROPERTY_ID,
                check_in=_to_date(row["check_in"]),
                amount=int(row["total_price"]),
                status=_to_status(str(row.get("status", ""))),
            )
        # 목록에 없다 = 내 예약이 아니거나 없는 번호다. **둘을 구분해 알려주지
        # 않는다** — 남의 예약이 존재하는지를 번호로 떠볼 수 있게 되기 때문이다.
        return None

    # ------------------------------------------------------------ 쓰기
    def cancel(self, booking_id: str) -> Booking:
        """아무것도 하지 않는다. **취소는 환불과 한 번에 일어난다.**

        메모리 store 에서는 취소와 환불이 두 단계라 그 사이에 실패할 수 있고,
        그래서 보상 트랜잭션(`restore`)이 있다. 예약 서비스는 둘을 한 요청에서
        원자적으로 처리하므로 **그 사이 상태가 아예 안 생긴다** — 보상할 것도
        없다.

        여기서 예외를 던지지 않는 것도 의도다. 호출부(`cancel_and_refund`)의
        순서를 원격용으로 따로 짜면 두 벌이 되고, 한쪽만 고치는 날이 온다.
        """
        b = self.get_booking(booking_id)
        if b is None:
            raise KeyError(booking_id)
        return b

    def refund(self, booking_id: str, amount: int) -> Booking:
        """실제로 취소하고 환불한다.

        `amount` 를 **보내지 않는다.** 보내면 호출자가 환불액을 정하게 되고,
        고객 브라우저도 같은 엔드포인트를 부를 수 있다. 금액은 예약 서비스가
        자기 정책으로 다시 계산한다 — 에이전트가 설명한 값과 같은 규칙이다.
        """
        uid = self._uuid_of(booking_id)
        if uid is None:
            raise KeyError(booking_id)

        token = caller_token.get()
        if not token:
            raise RemoteBookingUnavailable("호출자 인증 정보가 없어 환불할 수 없다")
        try:
            r = httpx.post(
                f"{self.base_url}/api/v1/bookings/{uid}/refund",
                headers={"Authorization": f"Bearer {token}"},
                json={"reason": "상담 에이전트를 통한 취소 요청"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as e:
            raise RemoteBookingUnavailable(f"예약 서비스에 닿지 못했다: {e}") from e

        if r.status_code == 400:
            # 이미 환불됐거나 확정 상태가 아니다. **장애가 아니라 사실이다.**
            raise PaymentGatewayError(r.json().get("detail", "환불할 수 없는 예약이다"))
        if r.status_code >= 400:
            raise RemoteBookingUnavailable(f"예약 서비스가 {r.status_code} 로 답했다")

        # 이 요청 안의 캐시는 이제 낡았다. 취소 전 상태를 계속 보게 된다.
        cache = _request_cache.get()
        if cache is not None:
            cache.pop(booking_id, None)

        b = Booking(
            booking_id=booking_id, customer_id="self",
            property_id=REMOTE_PROPERTY_ID,
            check_in=date.today(), amount=int(r.json()["refund_amount"]),
            status=BookingStatus.CANCELLED,
        )
        return b


def begin_request(token: str | None):
    """요청 범위를 연다. 토큰과 조회 캐시를 같이 세운다.

    두 개를 따로 세우면 한쪽만 정리하는 실수가 생긴다 — 캐시가 요청을 넘어
    살아남으면 다음 고객이 앞 고객의 예약을 보게 된다.
    """
    return caller_token.set(token), _request_cache.set({})


def end_request(tokens) -> None:
    t, c = tokens
    caller_token.reset(t)
    _request_cache.reset(c)


__all__ = [
    "BOOKING_API_URL", "REMOTE_PROPERTY_ID", "RemoteBookingUnavailable",
    "RemoteStore", "STANDARD_POLICY", "begin_request", "caller_token", "end_request",
]
