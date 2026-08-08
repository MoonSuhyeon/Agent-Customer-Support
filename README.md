# Agent-Customer-Support

> Airbnb형 숙박 플랫폼의 **예약·취소·환불·숙소 이용 문의를 자동화하는 AI Agent 시스템**

고객 문의에 답변만 하는 챗봇이 아니라, 요청을 업무 단위로 분해하고
숙소·예약·정책 데이터를 조회하여 **실제 취소·환불 처리까지 수행하는 Agent**입니다.

---

## 문서 성격

이 문서는 **구현 명세(Spec)** 입니다. 완성된 결과물이 아니라 만들어 가는 목표 상태를 기술합니다.
각 항목의 진행 상태는 다음 표기로 구분합니다.

| 표기 | 의미 |
|------|------|
| ✅ | 구현 완료 |
| 🔨 | 진행 중 |
| 🆕 | 예정 |

현재는 Next.js 기반 클라이언트가 구현되어 있고, **Python / FastAPI / LangGraph 기반 Agent 백엔드**가 이 명세의 주 구현 대상입니다.

---

## 1. 목적

```text
고객 문의
   ↓
의도 분석 · 업무 단위 분해
   ↓
숙소 / 예약 / 정책 조회
   ↓
조건 판단 (취소 가능 여부 · 환불 금액)
   ↓
고객 최종 확인
   ↓
Tool 실행 (취소 · 환불)
   ↓
결과 검증
   ↓
고객 안내 · 예외는 상담원 이관
```

목표는 **정상 업무의 자동화율을 올리고, 예외만 사람이 처리하는 구조**입니다.

---

## 2. 문제 정의

취소·환불은 **상태를 바꾸는 업무**입니다. 조회형 챗봇과 근본적으로 다릅니다.

| 위험 | 결과 |
|------|------|
| 중복 실행 | 환불 두 번 지급 |
| 부분 실행 | 예약은 취소됐는데 환불이 안 됨 |
| 잘못된 판단 | 환불 불가 건을 환불 |
| 근거 없는 답변 | 존재하지 않는 정책 안내 |

따라서 이 프로젝트의 설계는 **"LLM이 똑똑한가"가 아니라 "틀렸을 때 안전한가"** 를 중심으로 구성합니다.

---

## 3. 아키텍처

```text
        [ Next.js ] Support UI                    🔨
                  │  SSE
                  ↓
        [ FastAPI ] Agent API                     🆕
          POST /support/messages
          GET  /support/sessions/{id}
          POST /support/confirm      (HITL)
                  │
                  ↓
        [ LangGraph ] Agent Orchestrator          🆕
          ┌──────────────────────────────┐
          │  intent      의도 분석         │
          │  plan        업무 분해         │
          │  retrieve    조회 Tool 실행    │
          │  decide      조건 판단         │
          │  confirm     고객 확인 (중단)  │
          │  execute     상태 변경 Tool    │
          │  verify      결과 검증         │
          │  respond     응답 생성         │
          │  escalate    상담원 이관       │
          └──────────────────────────────┘
                  │
        ┌─────────┼──────────┐
        ↓         ↓          ↓
    Read Tools  Policy RAG  Write Tools
        │           │           │
        ↓           ↓           ↓
   PostgreSQL   FAISS       PostgreSQL
   (예약/숙소)  (정책 문서)  (트랜잭션)
```

**Policy RAG는 RAG-Marketing의 검색 엔진을 재사용합니다.**

---

## 4. 기술 범위

### 4-1. LangGraph 상태 그래프 🆕

```text
        intent
          ↓
        plan
          ↓
      retrieve  ←──────┐
          ↓            │ 정보 부족
        decide ────────┘
          ↓
    ┌─────┴─────┬──────────┐
    ↓           ↓          ↓
  respond    confirm    escalate
 (조회만)      ↓
            execute
              ↓
            verify
              ↓
       ┌──────┴──────┐
       ↓             ↓
    respond      escalate
                (검증 실패)
```

| 요소 | 설계 |
|------|------|
| State | `AgentState` (TypedDict) — 문의·수집정보·판단결과·실행이력 |
| Checkpointer | PostgreSQL — 세션 중단/재개 지원 |
| 조건부 엣지 | 위험도 · 정보 충분성 · 검증 결과로 분기 |
| Interrupt | `confirm` 노드에서 그래프 중단 → 고객 응답 대기 |

### 4-2. Tool 설계 — 읽기와 쓰기를 분리 🆕

| Tool | 유형 | 위험도 | 자동 실행 |
|------|------|--------|----------|
| `get_property` | Read | 낮음 | ✅ |
| `get_booking` | Read | 낮음 | ✅ |
| `get_customer` | Read | 낮음 | ✅ |
| `get_cancellation_policy` | Read (RAG) | 낮음 | ✅ |
| `calculate_refund` | Read (계산) | 중간 | ✅ (안내만) |
| `cancel_booking` | **Write** | 높음 | ❌ 고객 확인 필수 |
| `process_refund` | **Write** | 높음 | ❌ 고객 확인 필수 |

각 Tool은 Pydantic 스키마로 입출력을 정의하고, **Agent가 DB를 직접 다루지 않습니다.**

### 4-3. 멱등성 🆕

같은 요청이 반복돼도 중복 처리되지 않아야 합니다.

```text
취소 요청
   ↓
idempotency_key = hash(booking_id + action + request_id)
   ↓
┌────────────────────┬─────────────────────┐
│ 최초 요청           │ 중복 요청            │
│ 실행 후 결과 저장    │ 저장된 결과 그대로 반환│
└────────────────────┴─────────────────────┘
```

DB에 `UNIQUE(idempotency_key)` 제약을 걸어 **애플리케이션 로직이 아니라 DB 레벨에서** 중복을 차단합니다.

> 애플리케이션 로직으로 "이미 처리됐나?"를 조회한 뒤 실행하면 그 사이에 두 번째 요청이 끼어들 수 있습니다. **제약으로 막으면 경합 자체가 성립하지 않습니다.**

### 4-4. 원자성 — 취소와 환불은 함께 🆕

```text
cancel_booking + process_refund
        ↓
┌───────────────────────────────┐
│ 같은 트랜잭션으로 처리          │
│                               │
│ 외부 PG 호출이 끼면            │
│   → Saga + 보상 트랜잭션       │
│   → 환불 실패 시 취소 롤백      │
│   → 롤백 불가 시 즉시 에스컬레이션│
└───────────────────────────────┘
```

부분 처리 상태로 방치하지 않는 것이 원칙입니다.

### 4-5. Human-in-the-Loop 게이트 🆕

```text
단순 문의 (체크인 시간?)          → 자동 응대
예약 조회                        → 자동 처리
취소 가능 여부 · 환불 금액 안내    → 자동 판단
─────────────────────────────────────────────
실제 취소 / 환불 실행             → 고객 최종 확인 필수
정책 조회 실패 / 데이터 불일치     → 자동 실행 중단
분쟁 · 판단 불가                  → 상담원 이관
```

> UI는 **요청 → 확인 → 결과** 3단계로 구성합니다. 금액과 조건을 확인 화면에서 명시적으로 보여주고, 고객이 승인한 뒤에야 상태 변경 Tool이 실행됩니다. **돈이 움직이기 전에 사람이 한 번 멈춘다**는 것이 이 게이트의 목적입니다.

### 4-6. Silent Fallback 금지 🆕

정보를 확인하지 못했을 때 그럴듯한 답을 만들지 않습니다.

```text
정책 조회 실패
   ↓
❌ "일반적으로 7일 전까지는 전액 환불됩니다"   (추측)
✅ "해당 숙소의 취소 정책을 확인하지 못했습니다.
    상담원에게 연결해 드리겠습니다."          (명시적 실패)
```

### 4-7. 결과 검증 🆕

Tool 실행 후 **실제 상태**를 다시 읽어 응답과 대조합니다.

| 검증 항목 |
|-----------|
| 예약 상태가 실제로 `CANCELLED`인가 |
| 환불 금액이 정책 계산 결과와 일치하는가 |
| 고객에게 안내한 금액과 실제 처리 금액이 같은가 |
| 중복 실행이 발생하지 않았는가 |

### 4-8. 평가 지표 🆕

Agent는 "잘 동작하는 것 같다"로 끝내지 않습니다.

| 지표 | 정의 |
|------|------|
| **자동화율** | 상담원 개입 없이 완결된 문의 비율 |
| **태스크 성공률** | 의도한 업무가 정확히 수행된 비율 |
| **오응대율** | 잘못된 정보를 안내한 비율 (가장 중요) |
| **에스컬레이션율** | 상담원 이관 비율 (낮다고 좋은 것 아님) |
| **Tool 호출 정확도** | 올바른 Tool을 올바른 인자로 호출한 비율 |
| **평균 처리 시간** | 문의 접수 → 완결 |

시나리오 기반 회귀 테스트셋(정상 · 경계 · 예외 각 N건)으로 매 변경마다 측정합니다.

---

## 5. 구현 로드맵

| Phase | 산출물 | 착수 조건 |
|-------|--------|-----------|
| **0** | CS 시나리오 정의 (정상 · 경계 · 예외) + ERD | — |
| **1** | FastAPI 백엔드 스켈레톤 + 숙박 도메인 모델 | Phase 0 |
| **2** | Read Tools 4종 (`get_booking` / `get_property` / `get_customer` / 정책) | Phase 1 |
| **3** | `calculate_refund` — 정책 기반 환불 금액 계산 | Phase 2 |
| **4** | LangGraph 그래프 — intent / plan / retrieve / decide / respond | Phase 3 |
| **5** | HITL — `confirm` 노드 + interrupt + 프론트 확인 화면 | Phase 4 |
| **6** | Write Tools + 멱등성 키 + 원자적 취소·환불 | Phase 5 |
| **7** | `verify` 노드 — 실행 결과 검증 | Phase 6 |
| **8** | Policy RAG 연결 (RAG-Marketing 엔진 재사용) | Phase 2 |
| **9** | 에스컬레이션 + 실패 로깅 | Phase 7 |
| **10** | 평가 하네스 — 시나리오 회귀 테스트 + 지표 측정 | Phase 9 |

**Phase 7까지가 최소 완성선**입니다. 조회 → 판단 → 확인 → 실행 → 검증이 한 바퀴 돌면 프로젝트로서 성립합니다.

---

## 6. 완료 정의 (DoD)

- [ ] "내일 체크인인데 취소하고 환불받고 싶어요"가 끝까지 처리된다
- [ ] 상태 변경 전 반드시 고객 확인 단계를 거친다 (테스트로 증명)
- [ ] 같은 취소 요청을 두 번 보내도 환불이 한 번만 발생한다
- [ ] 환불 실패 시 예약 취소가 롤백되거나 에스컬레이션된다
- [ ] 정책 조회 실패 시 추측 답변 대신 이관된다
- [ ] 시나리오 회귀 테스트셋에서 **오응대율 0%** 를 유지한다
- [ ] 자동화율 / 에스컬레이션율이 수치로 보고된다

---

## 7. 기술 스택

### 핵심 (Python / FastAPI)

| 영역 | 기술 |
|------|------|
| 언어 | Python 3.11 |
| API | **FastAPI**, Pydantic v2, Uvicorn, SSE |
| Agent | **LangGraph** |
| LLM | OpenAI SDK (`gpt-4o-mini`) |
| ORM | SQLAlchemy 2.0 (async), asyncpg |
| 마이그레이션 | Alembic |
| DB | PostgreSQL (도메인 + LangGraph Checkpointer) |
| 정책 검색 | FAISS + BM25 (RAG-Marketing 엔진 재사용) |
| 테스트 | pytest, pytest-asyncio |
| 관측 | structlog, 자체 Tracer |

### 클라이언트

Next.js 14 + TypeScript + Tailwind + shadcn/ui + TanStack Query

---

## 8. 프로젝트 구조 (목표)

```text
Agent-Customer-Support/
├── backend/                          🆕
│   ├── app/
│   │   ├── main.py                   FastAPI 진입점
│   │   ├── api/v1/
│   │   │   ├── support.py            대화 · HITL 확인
│   │   │   ├── bookings.py
│   │   │   ├── properties.py
│   │   │   └── policies.py
│   │   ├── agent/
│   │   │   ├── graph.py              LangGraph 정의
│   │   │   ├── state.py              AgentState
│   │   │   ├── nodes/
│   │   │   │   ├── intent.py
│   │   │   │   ├── plan.py
│   │   │   │   ├── retrieve.py
│   │   │   │   ├── decide.py
│   │   │   │   ├── confirm.py
│   │   │   │   ├── execute.py
│   │   │   │   ├── verify.py
│   │   │   │   └── escalate.py
│   │   │   ├── tools/
│   │   │   │   ├── booking.py
│   │   │   │   ├── property.py
│   │   │   │   ├── customer.py
│   │   │   │   ├── policy.py         RAG 검색
│   │   │   │   └── payment.py
│   │   │   └── prompts/
│   │   ├── services/
│   │   │   ├── refund.py             환불 금액 계산
│   │   │   ├── idempotency.py
│   │   │   └── saga.py               보상 트랜잭션
│   │   ├── models/
│   │   └── schemas/
│   ├── alembic/
│   └── tests/
│       └── scenarios/                시나리오 회귀 테스트
├── frontend/                         🔨  Next.js 클라이언트
│   ├── app/(main)/
│   │   ├── bookings/
│   │   ├── support/
│   │   └── settings/
│   ├── components/
│   └── lib/
├── eval/                             🆕
│   ├── testset.jsonl
│   └── run_eval.py
├── docs/
│   ├── architecture.md
│   ├── agent-workflow.md
│   ├── tool-spec.md
│   ├── policy.md
│   ├── naming-convention.md          ✅ 스키마·명명 규약
│   └── erd.dbml
└── requirements.txt
```

---

## 9. 핵심 설계 원칙

1. **SSoT** — 예약·정책의 원천은 DB. Agent가 정보를 만들어내지 않는다
2. **SRP** — Tool 하나, Agent 노드 하나가 각각 하나의 책임만 갖는다
3. **Read / Write 분리** — 조회는 자유롭게, 상태 변경은 게이트를 거쳐서
4. **Idempotency** — 같은 요청이 반복돼도 결과는 한 번만
5. **Atomicity** — 취소와 환불은 함께 성공하거나 함께 되돌린다
6. **No Silent Fallback** — 모르면 모른다고 하고 사람에게 넘긴다
7. **Human-in-the-Loop** — 돈이 움직이기 전에 사람이 확인한다
8. **Verify After Execute** — 실행했다고 믿지 않고 다시 읽어 확인한다

---

## 10. 다른 레포와의 연결

| 방향 | 내용 |
|------|------|
| **RAG-Marketing →** | 검색 엔진을 정책 문서 조회에 재사용 |
| **→ Data-Growth** | 문의·취소 이벤트를 이탈 원인 분석에 제공 |
| **→ ML-Product** | 취소 패턴을 수요 예측의 보정 신호로 제공 |

플랫폼 전체 구성은 [프로필 README](https://github.com/MoonSuhyeon)를 참고하세요.
