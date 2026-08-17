"""응답 계약을 고정한다.

이 API 는 화면이 없다. 운영 콘솔이 소비자이고 저장소가 다르다. 그래서 응답 모양이
바뀌면 **여기서 알아야 한다** — 소비자 쪽에서 나중에 조용히 깨지는 대신.

특히 `/support/sessions/{id}` 는 오래도록 `dict` 를 그대로 돌려줬다. 그러면
OpenAPI 에 모양이 안 실리고, 콘솔은 응답 모양을 손으로 적을 수밖에 없다. 손으로
적힌 것은 서비스가 바뀌어도 아무 데서도 안 걸린다.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _new_session(message: str = "예약 취소하고 싶어요 B1001") -> str:
    sid = f"t-{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/support/messages",
        json={"session_id": sid, "message": message, "request_id": uuid.uuid4().hex},
    )
    assert r.status_code == 200, r.text
    return sid


# ─────────────────────────────── 세션 응답
def test_session_response_has_a_schema():
    """`dict` 가 아니라 모양이 있는 응답이어야 한다."""
    schema = app.openapi()["paths"]["/support/sessions/{session_id}"]["get"]
    ref = schema["responses"]["200"]["content"]["application/json"]["schema"]
    assert "$ref" in ref, "응답에 스키마가 없으면 소비자가 모양을 손으로 적게 된다"
    assert ref["$ref"].endswith("SessionOut")


def test_session_returns_the_pinned_fields():
    sid = _new_session()
    body = client.get(f"/support/sessions/{sid}").json()
    assert set(body) >= {
        "session_id", "awaiting_confirmation", "next_nodes",
        "response", "escalated", "decision", "trace",
    }


def test_trace_guarantees_node_and_keeps_the_rest():
    """`node` 만 보장하고 나머지는 열어 둔다.

    전부 열거하면 노드를 하나 추가할 때마다 스키마가 따라 움직여야 하고, 통째로
    `dict` 로 두면 소비자가 `node` 조차 믿을 수 없다.
    """
    sid = _new_session()
    trace = client.get(f"/support/sessions/{sid}").json()["trace"]
    assert trace, "트레이스가 비어 있으면 무엇이 일어났는지 볼 방법이 없다"
    assert all("node" in row for row in trace)
    # 노드별 추가 키가 살아 있어야 한다 — 모델이 걸러내면 트레이스가 무의미해진다
    intent = next(r for r in trace if r["node"] == "intent")
    assert "intent" in intent


def test_missing_session_is_404_not_an_empty_shape():
    r = client.get("/support/sessions/does-not-exist")
    assert r.status_code == 404


# ─────────────────────────────── 판단 결과
def test_decision_shape_splits_on_proceed():
    """진행이면 환불 정보가, 거절이면 사유가 실린다.

    `dict` 로 두면 이 갈림이 스키마에서 사라지고, 화면은 환불 금액이 항상 있다고
    가정하게 된다 — 그리고 거절 응답에서 0원을 그린다.
    """
    sid = _new_session()
    d = client.get(f"/support/sessions/{sid}").json()["decision"]
    assert d is not None
    assert d["proceed"] is True
    assert d["refund_amount"] is not None
    assert d["refund_ratio"] is not None


def test_a_rejected_decision_carries_a_reason_and_no_refund():
    """이미 취소된 예약을 또 취소하려는 경우.

    환불 금액이 **없다** — 0 원이 아니라 없다. 그 둘을 응답이 구분하지 못하면
    화면도 구분하지 못하고, 거절을 "0 원 환불 승인"처럼 그리게 된다.

    시드를 뒤지지 않고 **실제로 한 번 취소해서** 그 상태를 만든다. 시드에 의존하면
    시드가 바뀔 때 조용히 skip 되고, skip 된 테스트는 없는 테스트다.
    """
    sid = _new_session()
    assert client.post("/support/confirm", json={"session_id": sid, "approved": True}).status_code == 200

    # 같은 예약을 다시 취소해 달라고 한다 — 이제 상태가 CANCELLED 다
    again = _new_session()
    d = client.get(f"/support/sessions/{again}").json()["decision"]
    assert d["proceed"] is False
    assert d["reason"], "왜 거절인지 없으면 화면이 설명할 수 없다"
    assert d["refund_amount"] is None, "0 원과 '없음' 은 다른 뜻이다"


# ─────────────────────────────── 커밋된 스키마와 코드가 같은가
def test_committed_openapi_matches_the_app():
    """`openapi.json` 이 낡으면 소비자가 낡은 계약으로 타입을 만든다."""
    import json
    from pathlib import Path

    committed = json.loads(
        (Path(__file__).resolve().parents[2] / "openapi.json").read_text(encoding="utf-8")
    )
    assert committed == json.loads(json.dumps(app.openapi())), (
        "scripts/export_openapi.py 를 다시 돌려야 한다"
    )
