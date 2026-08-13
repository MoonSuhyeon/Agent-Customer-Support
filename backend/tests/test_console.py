"""상담 콘솔 — 화면이 승인 게이트를 정말로 지키는지.

API 테스트가 이미 그래프를 검증한다. 여기서 확인하는 것은 **화면 경로에서도
같은 규칙이 유지되는가** 다. 콘솔이 별도 실행 경로를 갖게 되면 API 는 막는데
화면은 뚫리는 상황이 생길 수 있다.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _session(client: TestClient) -> str:
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    return r.headers["location"].rsplit("/", 1)[-1]


def test_home_starts_a_session(client):
    sid = _session(client)
    assert sid
    page = client.get(f"/console/{sid}")
    assert page.status_code == 200
    assert "상담 콘솔" in page.text


def test_cancel_request_stops_before_executing(client):
    """문의만으로는 예약이 바뀌지 않는다 — 화면에 승인 카드가 떠야 한다."""
    sid = _session(client)
    r = client.post(f"/console/{sid}/send", data={"message": "B1002 예약을 취소하고 싶어요"})
    assert r.status_code == 200
    assert "승인 대기" in r.text
    assert "아직 아무것도 실행되지 않았다" in r.text

    from app.main import _store
    assert _store.bookings["B1002"].status.value == "CONFIRMED"


def test_approval_executes_and_rejection_does_not(client):
    from app.main import _store

    # 거절 — 예약이 그대로여야 한다
    sid = _session(client)
    client.post(f"/console/{sid}/send", data={"message": "B1003 예약 취소해주세요"})
    client.post(f"/console/{sid}/decide", data={"approved": "no"})
    assert _store.bookings["B1003"].status.value == "CONFIRMED"

    # 승인 — 그때서야 바뀐다
    sid2 = _session(client)
    client.post(f"/console/{sid2}/send", data={"message": "B1003 예약 취소해주세요"})
    r = client.post(f"/console/{sid2}/decide", data={"approved": "yes"})
    assert r.status_code == 200
    assert _store.bookings["B1003"].status.value == "CANCELLED"


def test_htmx_request_returns_only_the_fragment(client):
    """HX-Request 헤더가 있으면 조각만, 없으면 전체 페이지."""
    sid = _session(client)
    full = client.post(f"/console/{sid}/send", data={"message": "B1002 취소"})
    assert "<!doctype html>" in full.text.lower()

    sid2 = _session(client)
    frag = client.post(f"/console/{sid2}/send",
                       data={"message": "B1002 취소"},
                       headers={"HX-Request": "true"})
    assert "<!doctype html>" not in frag.text.lower()
    assert frag.text.strip().startswith('<div id="thread"')


def test_console_page_renders_without_htmx_attributes_being_required(client):
    """폼이 평범한 POST 로도 동작해야 한다 — CDN 이 막혀도 콘솔이 죽지 않는다."""
    sid = _session(client)
    page = client.get(f"/console/{sid}").text
    form = re.search(r'<form class="ask".*?</form>', page, re.S).group(0)
    assert 'method="post"' in form
    assert f'action="/console/{sid}/send"' in form
