"""시나리오 회귀 하네스 — 정상 · 경계 · 예외.

    python scripts/run_agent_demo.py

각 시나리오의 기대 결과를 미리 적어두고, 실제 동작과 대조한다.
**오응대율 0%** 가 배포 조건이므로, 이 스크립트가 CI 품질 게이트 역할을 한다.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from langgraph.checkpoint.memory import MemorySaver          # noqa: E402

from app.agent.graph import build_graph                      # noqa: E402
from app.domain import BookingStatus, seed                   # noqa: E402

TODAY = date(2025, 6, 10)
BAR = "=" * 72


def cfg(tid):
    return {"configurable": {"thread_id": tid}}


# (이름, 구분, 메시지, 승인여부, 기대)
SCENARIOS = [
    ("전액 환불 취소", "정상", "B1002 예약 취소하고 환불받고 싶어요", True,
     {"halted": True, "final_status": "CANCELLED", "refund": 240_000, "escalated": False}),
    ("예약 조회", "정상", "B1001 예약 상태 확인해주세요", False,
     {"halted": False, "final_status": "CONFIRMED", "escalated": False}),
    ("고객이 승인하지 않음", "경계", "B1003 취소해주세요", False,
     {"halted": True, "final_status": "CONFIRMED", "escalated": False}),
    ("임박 취소 — 부분 환불", "경계", "내일 체크인인데 B1001 취소하고 환불받고 싶어요", True,
     {"halted": True, "final_status": "CANCELLED", "refund": 36_000, "escalated": False}),
    ("환불 불가 구간", "경계", "B1003 취소하고 환불", True,
     {"halted": True, "final_status": "CANCELLED", "refund": 0, "escalated": False}),
    ("정책 미등록 숙소", "예외", "B1004 취소하고 환불받고 싶어요", False,
     {"halted": False, "final_status": "CONFIRMED", "escalated": True}),
    ("존재하지 않는 예약", "예외", "B9999 취소해주세요", False,
     {"halted": False, "escalated": True}),
    ("의도 불명", "예외", "그냥 궁금한 게 있는데요", False,
     {"halted": False, "escalated": True}),
]


def run_one(idx, name, kind, message, approve, expect):
    store = seed(today=TODAY)
    agent = build_graph(store, today=TODAY, checkpointer=MemorySaver())
    tid = f"s{idx}"

    out = agent.invoke({"message": message, "request_id": f"REQ-{idx}", "trace": []}, cfg(tid))
    halted = agent.get_state(cfg(tid)).next == ("execute",)

    if halted and approve:
        out = agent.invoke(None, cfg(tid))

    bid = out.get("booking_id")
    booking = store.get_booking(bid) if bid else None

    checks = {"halted": halted, "escalated": bool(out.get("escalated"))}
    if booking:
        checks["final_status"] = booking.status.value
        checks["refund"] = booking.refunded_amount

    ok = all(checks.get(k) == v for k, v in expect.items())
    return ok, checks, out, store


def main() -> int:
    print(BAR)
    print("시나리오 회귀 — 정상 · 경계 · 예외")
    print(BAR)

    passed = 0
    misinformed = 0
    for i, (name, kind, msg, approve, expect) in enumerate(SCENARIOS, 1):
        ok, checks, out, store = run_one(i, name, kind, msg, approve, expect)
        passed += ok
        mark = "PASS" if ok else "FAIL"
        print(f"\n[{kind}] {name}  … {mark}")
        print(f"  입력   {msg}")
        print(f"  응답   {out.get('response', '')}")
        print(f"  상태   중단={checks['halted']} 이관={checks['escalated']}"
              + (f" 예약={checks.get('final_status')}" if 'final_status' in checks else "")
              + (f" 환불={checks.get('refund'):,}원" if 'refund' in checks else ""))
        if not ok:
            print(f"  기대   {expect}")
            print(f"  실제   {checks}")

        # 오응대 판정: 이관했는데 단정적 안내를 했거나, 실행 없이 완료를 말한 경우
        resp = out.get("response", "")
        if out.get("escalated") and ("환불 처리되었습니다" in resp or "전액 환불" in resp):
            misinformed += 1
        if (not out.get("verified")) and "환불 처리되었습니다" in resp:
            misinformed += 1

    print()
    print(BAR)
    print("안전장치 별도 검증")

    # 멱등성
    store = seed(today=TODAY)
    from app.agent.tools import WriteTools, idempotency_key
    w = WriteTools(store)
    k = idempotency_key("B1002", "cancel_and_refund", "REQ-X")
    w.cancel_and_refund("B1002", 240_000, k)
    second = w.cancel_and_refund("B1002", 240_000, k)
    n_refund = len([a for a in store.audit if a["action"] == "process_refund"])
    print(f"  멱등성        같은 키로 2회 호출 → 환불 실행 {n_refund}회 "
          f"(재생 응답={second.data.get('idempotent_replay')})")

    # 보상 트랜잭션
    store = seed(today=TODAY)
    store.pg_should_fail = True
    agent = build_graph(store, today=TODAY, checkpointer=MemorySaver())
    agent.invoke({"message": "B1002 취소하고 환불", "request_id": "R", "trace": []}, cfg("saga"))
    out = agent.invoke(None, cfg("saga"))
    print(f"  보상 트랜잭션  환불 실패 → 예약 상태 {store.get_booking('B1002').status.value} "
          f"(이관={out['escalated']})")

    # 보상까지 실패
    store = seed(today=TODAY)
    store.pg_should_fail = store.compensation_should_fail = True
    agent = build_graph(store, today=TODAY, checkpointer=MemorySaver())
    agent.invoke({"message": "B1002 취소하고 환불", "request_id": "R", "trace": []}, cfg("saga2"))
    out = agent.invoke(None, cfg("saga2"))
    print(f"  보상 실패      needs_human={out['executed'].get('needs_human')} "
          f"→ 사람에게 이관")

    print()
    print(BAR)
    print("요약")
    print(f"  시나리오       {passed}/{len(SCENARIOS)} 통과")
    print(f"  오응대율       {misinformed / len(SCENARIOS):.1%}  (목표 0%)")
    print(f"  자동 완결      {sum(1 for s in SCENARIOS if not s[4].get('escalated'))}"
          f"/{len(SCENARIOS)}")
    print(f"  이관           {sum(1 for s in SCENARIOS if s[4].get('escalated'))}"
          f"/{len(SCENARIOS)}")
    return 0 if passed == len(SCENARIOS) and misinformed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
