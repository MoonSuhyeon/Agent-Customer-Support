"""고객이 문의를 여는 경로.

그동안 이 에이전트를 부르는 곳은 운영 콘솔 하나뿐이었다. 직원이 고객 문장을
직접 타이핑하는 화면이라, 이름은 "상담 승인" 인데 **승인할 대기 건 자체가
생기지 않았다.**

여기서 두 가지를 고정한다.

1. 문의를 **예약에서** 시작할 수 있는가 — 고객에게 예약번호를 외워서 적으라고
   할 수는 없다. 오타 하나면 남의 예약을 조회한다.
2. 그렇게 열린 세션이 **콘솔의 대기 목록에 뜨는가** — 안 뜨면 승인하는 쪽에서
   문의가 들어온 줄 모른다.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _sid() -> str:
    return f"t-{uuid.uuid4().hex[:8]}"


def open_inquiry(booking_id: str | None, message: str, session_id: str | None = None):
    sid = session_id or _sid()
    body = {"session_id": sid, "message": message, "request_id": uuid.uuid4().hex}
    if booking_id:
        body["booking_id"] = booking_id
    r = client.post("/support/messages", json=body)
    assert r.status_code == 200, r.text
    return sid, r.json()


# ─────────────────────────────────────── 예약에서 시작한다
def test_a_booking_id_can_come_from_the_screen_not_the_sentence():
    """**고객은 예약번호를 타이핑하지 않는다.**

    문장에는 예약번호가 없고 `booking_id` 만 실려 있다. 그래도 에이전트가
    그 예약을 집어야 한다.
    """
    _, out = open_inquiry("B1002", "예약을 취소하고 싶어요")

    assert out["decision"] is not None, "예약을 못 찾으면 판단이 안 나온다"
    assert out["decision"]["proceed"] is True


def test_the_sentence_still_works_for_the_console():
    """직원이 콘솔에서 문장에 번호를 적는 길도 남아 있어야 한다."""
    _, out = open_inquiry(None, "B1003 예약을 취소하고 싶어요")

    assert out["decision"] is not None


def test_an_inquiry_without_any_booking_does_not_pretend():
    """예약을 못 집으면 환불 금액을 지어내지 않는다."""
    _, out = open_inquiry(None, "예약을 취소하고 싶어요")

    assert out["decision"] is None or out["decision"].get("proceed") is False


def test_the_screen_wins_over_the_sentence():
    """둘 다 있으면 화면이 준 것을 쓴다.

    문장은 고객이 자유롭게 적은 글이고 `booking_id` 는 화면이 실은 사실이다.
    사실이 이겨야 한다.
    """
    sid, _ = open_inquiry("B1002", "B9999 예약 취소해 주세요")

    row = next(r for r in client.get("/support/sessions").json()
               if r["session_id"] == sid)
    assert row["booking_id"] == "B1002"


# ─────────────────────────────────────── 콘솔이 볼 수 있다
def test_an_opened_inquiry_shows_up_in_the_list():
    sid, _ = open_inquiry("B1002", "예약을 취소하고 싶어요")

    rows = client.get("/support/sessions").json()
    assert any(r["session_id"] == sid for r in rows)


def test_the_list_carries_what_the_console_needs_to_decide():
    sid, _ = open_inquiry("B1002", "예약을 취소하고 싶어요")

    row = next(r for r in client.get("/support/sessions").json() if r["session_id"] == sid)
    assert row["booking_id"] == "B1002"
    assert row["last_message"] == "예약을 취소하고 싶어요"
    # 무엇을 승인할지 모르면 승인 화면이 아니다
    assert row["response"]


def test_awaiting_filter_shows_only_what_needs_a_human():
    """**이 필터가 "상담 승인" 이라는 이름을 성립시킨다.**"""
    sid, out = open_inquiry("B1002", "예약을 취소하고 싶어요")
    assert out["awaiting_confirmation"] is True

    waiting = client.get("/support/sessions", params={"awaiting": True}).json()
    assert any(r["session_id"] == sid for r in waiting)

    # 승인하면 대기 목록에서 빠진다
    assert client.post("/support/confirm", json={"session_id": sid, "approved": True}).status_code == 200
    after = client.get("/support/sessions", params={"awaiting": True}).json()
    assert not any(r["session_id"] == sid for r in after)


def test_a_continued_conversation_keeps_its_opened_time():
    """대기 순서를 매기려면 **연 시각이 처음 그대로**여야 한다."""
    sid, _ = open_inquiry("B1002", "예약을 취소하고 싶어요")
    first = next(r for r in client.get("/support/sessions").json()
                 if r["session_id"] == sid)["opened_at"]

    open_inquiry("B1002", "다시 물어볼게요", session_id=sid)
    again = next(r for r in client.get("/support/sessions").json()
                 if r["session_id"] == sid)
    assert again["opened_at"] == first
    assert again["last_message"] == "다시 물어볼게요", "마지막 문장은 갱신돼야 한다"
