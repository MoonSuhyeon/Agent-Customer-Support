"""실제 예약을 읽어 오는 경로.

이 에이전트는 자기 store 에 데모 예약 네 건을 하드코딩해 두고 있었다. 고객
화면에서 오는 것은 `BK2608190016` 같은 실제 번호라, 그대로 두면 **실제 예약
100% 에서 실패하는 버튼**이 된다.

여기서 고정하는 것 셋.

1. 실제 번호로 조회가 되는가
2. **남의 예약을 못 보는가** — 권한 검사를 따로 짜서 지키는 것이 아니라,
   `/bookings/me` 만 보므로 구조적으로 볼 수 없어야 한다
3. 아직 안 되는 것(쓰기)이 **조용히 성공한 척하지 않는가**
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.remote import RemoteBookingUnavailable, RemoteStore, caller_token

client = TestClient(app)

CHECK_IN = (date.today() + timedelta(days=10)).isoformat() + "T15:00:00"

#: 예약 서비스가 돌려주는 모양. 실제 응답에서 그대로 가져왔다.
MY_BOOKINGS = [
    {"id": "11111111-1111-1111-1111-111111111111",
     "booking_number": "BK2608190016", "status": "CONFIRMED",
     "total_price": 90000, "check_in": CHECK_IN},
    {"id": "22222222-2222-2222-2222-222222222222",
     "booking_number": "BK2608160042", "status": "CANCELLED",
     "total_price": 120000, "check_in": CHECK_IN},
]

#: 견적. **에이전트는 이 값을 그대로 쓴다** — 자기가 계산하지 않는다.
QUOTE = {
    "booking_id": MY_BOOKINGS[0]["id"],
    "total_price": 90000,
    "days_until_check_in": 10,
    "refund_ratio": 1.0,
    "refund_amount": 90000,
    "policy_name": "표준 취소 정책",
    "policy_description": "체크인 7일 전까지 100% 환불, 이후 환불 불가",
    "refundable": True,
    "reason": None,
}


@pytest.fixture
def booking_api(monkeypatch):
    """예약 서비스를 가로챈다. **토큰별로 다른 목록을 준다** —
    "남의 예약을 못 본다" 를 검사하려면 남의 목록도 있어야 한다."""
    calls: list[str | None] = []

    def fake_get(url, headers=None, timeout=None):
        token = (headers or {}).get("Authorization", "").removeprefix("Bearer ")
        if token == "bad":
            return httpx.Response(401, json={"detail": "Unauthorized"})
        if "refund-quote" in url:
            return httpx.Response(200, json=QUOTE)
        calls.append(token)
        if token == "other":
            return httpx.Response(200, json=[])      # 다른 고객 — 목록이 비어 있다
        return httpx.Response(200, json=MY_BOOKINGS)

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(200, json={"refund_amount": QUOTE["refund_amount"]})

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "post", fake_post)
    return calls


def ask(booking_id: str, token: str = "mine", message: str = "예약을 취소하고 싶어요"):
    sid = f"t-{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/support/messages",
        json={"session_id": sid, "message": message,
              "request_id": uuid.uuid4().hex, "booking_id": booking_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    return sid, r


# ─────────────────────────────────────── 1. 실제 번호로 조회된다
def test_a_real_booking_number_is_found(booking_api):
    _, r = ask("BK2608190016")

    assert r.status_code == 200, r.text
    out = r.json()
    assert out["decision"] is not None, "실제 예약을 못 찾으면 판단이 안 나온다"
    assert out["decision"]["proceed"] is True


def test_the_amount_comes_from_the_booking_service(booking_api):
    """**에이전트가 금액을 계산하지 않는다.**

    돈을 소유한 쪽이 정책을 갖고 있고, 승인 뒤 실제로 깎는 것도 같은 규칙이다.
    여기서 한 번 더 계산하면 한쪽 구간만 고쳤을 때 설명과 집행이 조용히 갈린다.
    """
    _, r = ask("BK2608190016")

    assert r.json()["decision"]["refund_amount"] == QUOTE["refund_amount"]


def test_a_cancelled_booking_is_refused(booking_api):
    """이미 취소된 예약. 상태도 실제 값을 따라야 한다."""
    _, r = ask("BK2608160042")

    d = r.json()["decision"]
    assert d["proceed"] is False
    assert d["refund_amount"] is None, "0원과 '없음' 은 다른 뜻이다"


def test_demo_bookings_do_not_touch_the_booking_service(booking_api):
    """`B1002` 는 여전히 이 서비스의 자기 store 로 간다.

    **판단 결과로는 확인하지 않는다.** 데모 store 는 전역이고 앞선 테스트가
    같은 예약을 취소해 둘 수 있어서, `proceed` 를 단언하면 실행 순서에 기댄
    테스트가 된다 — 혼자 돌리면 통과하고 전체로 돌리면 깨진다.
    여기서 볼 것은 **어느 store 로 갔는가** 하나다.
    """
    _, r = ask("B1002")

    assert r.status_code == 200
    assert booking_api == [], "데모 예약인데 예약 서비스를 불렀다"


# ─────────────────────────────────────── 2. 남의 예약을 못 본다
def test_another_customers_booking_is_not_visible(booking_api):
    """**권한 검사를 따로 짜지 않았다.**

    `/bookings/me` 만 보므로 다른 고객의 토큰으로는 그 번호가 목록에 없다.
    못 보게 막은 것이 아니라 **볼 수 있는 범위가 애초에 좁다.**
    """
    _, r = ask("BK2608190016", token="other")

    assert r.status_code == 200
    out = r.json()
    assert out["escalated"] is True, "못 찾았으면 사람에게 넘겨야 한다"
    assert out["decision"] is None


def test_the_caller_token_is_what_reaches_the_booking_service(booking_api):
    ask("BK2608190016", token="mine")
    assert booking_api == ["mine"]


def test_a_rejected_token_is_not_reported_as_a_missing_booking(booking_api):
    """**인증 실패와 "예약 없음" 은 다른 사실이다.**"""
    _, r = ask("BK2608190016", token="bad")

    assert r.status_code == 503
    assert "인증" in r.json()["detail"]


def test_an_unreachable_service_is_not_a_missing_booking(monkeypatch):
    def boom(url, headers=None, timeout=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", boom)
    _, r = ask("BK2608190016")

    assert r.status_code == 503
    assert "닿지 못했다" in r.json()["detail"]


# ─────────────────────────────────────── 3. 아직 안 되는 것은 소리 내어 막는다
def test_approving_actually_refunds(booking_api):
    """승인하면 예약 서비스에 실제로 환불이 들어간다."""
    sid, r = ask("BK2608190016")
    assert r.json()["awaiting_confirmation"] is True

    done = client.post("/support/confirm",
                       json={"session_id": sid, "approved": True},
                       headers={"Authorization": "Bearer mine"})
    assert done.status_code == 200, done.text
    assert done.json()["awaiting_confirmation"] is False


def test_the_agent_never_sends_the_amount(booking_api, monkeypatch):
    """**금액을 보내면 호출자가 환불액을 정하게 된다.**

    고객 브라우저도 같은 엔드포인트를 부를 수 있으므로, 금액을 실어 보내는
    구조는 그 자체로 위조 통로다.
    """
    sent: list[dict] = []

    def capture(url, headers=None, json=None, timeout=None):
        sent.append(json or {})
        return httpx.Response(200, json={"refund_amount": QUOTE["refund_amount"]})

    monkeypatch.setattr(httpx, "post", capture)
    sid, _ = ask("BK2608190016")
    client.post("/support/confirm", json={"session_id": sid, "approved": True},
                headers={"Authorization": "Bearer mine"})

    assert sent, "환불이 안 나갔다"
    assert "amount" not in sent[0] and "refund_amount" not in sent[0]


def test_a_store_without_a_token_says_so():
    """토큰이 없으면 "예약 없음" 이 아니라 **아무것도 못 본다** 다."""
    store = RemoteStore()
    caller_token.set(None)
    with pytest.raises(RemoteBookingUnavailable, match="인증 정보"):
        store.get_booking("BK2608190016")
