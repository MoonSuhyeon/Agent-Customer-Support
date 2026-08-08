# Agent-Customer-Support

Airbnb형 숙박 플랫폼의 **예약·취소·환불·숙소 이용 문의를 자동화하는 AI Agent 시스템**입니다.

고객 문의에 단순히 답변하는 챗봇이 아니라, 고객의 요청을 업무 단위로 분해하고 숙소·예약·정책 데이터를 조회하여 필요한 후속 업무까지 연결하는 **Agent 기반 Customer Support Workflow**를 설계합니다.

## 프로젝트 개요

본 프로젝트는 숙박 플랫폼의 실제 고객응대 프로세스를 가정하여, 반복적인 CS 업무를 AI Agent가 처리할 수 있도록 설계한 프로젝트입니다.

고객의 자연어 문의를 분석한 뒤 예약 상태, 숙소 정보, 이용 정책, 환불 규정 등을 조회하고, 문의 유형에 따라 응대·취소·환불 등의 후속 업무를 수행합니다.

```text
고객 문의
   ↓
문의 의도 분석
   ↓
업무 단위 분해
   ↓
┌─────────────────────────────┐
│ Agent Workflow              │
│                             │
│ 숙소 조회                   │
│ 예약 조회                   │
│ 정책 조회                   │
│ 환불 조건 확인              │
│ 취소/환불 가능 여부 판단    │
└─────────────────────────────┘
   ↓
Tool / API 실행
   ↓
결과 검증
   ↓
┌───────────────┬───────────────┐
│ 정상 처리      │ 예외 상황     │
│               │               │
│ 자동 응대      │ Fallback      │
│ 업무 실행      │ Human Escalation
└───────────────┴───────────────┘
```

## 주요 업무

### 1. 고객 응대 시나리오 및 Agent 업무 설계

예약·취소·환불·숙소 이용 문의 등 주요 CS 시나리오를 기능 단위로 분해하고, 각 시나리오에서 Agent가 수행해야 할 업무 범위를 정의합니다.

```text
예약 문의
→ 예약 조회
→ 예약 상태 확인
→ 숙소 정보 확인
→ 고객에게 결과 안내

예약 취소
→ 예약 조회
→ 취소 가능 여부 확인
→ 환불 정책 조회
→ 환불 금액 계산
→ 고객 확인
→ 취소 처리
→ 환불 처리
```

### 2. Agent 데이터 및 지식 구조 설계

Agent가 정확한 업무 판단을 수행할 수 있도록 숙소·예약·고객·정책 데이터를 업무 목적에 맞게 구조화합니다.

주요 데이터 영역:

* 숙소 정보
* 객실 정보
* 예약 정보
* 고객 정보
* 체크인·체크아웃 정보
* 숙소 이용 규칙
* 취소 정책
* 환불 정책
* 결제 정보

Agent가 임의의 정보를 생성하지 않고 **서비스의 실제 데이터를 기준으로 판단할 수 있도록 데이터와 지식의 기준점(SSoT)을 명확하게 구성**합니다.

### 3. Agent Tool 및 API 연동

Agent가 실제 업무에 필요한 정보를 조회하고 후속 업무를 수행할 수 있도록 기능별 Tool을 설계합니다.

```text
get_property()
→ 숙소 정보 조회

get_booking()
→ 예약 정보 조회

get_customer()
→ 고객 정보 조회

get_cancellation_policy()
→ 취소 정책 조회

calculate_refund()
→ 환불 가능 여부 및 금액 계산

cancel_booking()
→ 예약 취소

process_refund()
→ 환불 처리
```

Agent는 필요한 Tool을 선택하고 호출한 뒤 결과를 다음 단계의 판단에 활용합니다.

### 4. Agent Workflow 및 업무 오케스트레이션

고객의 복합적인 요청을 여러 단계의 작업으로 분해하고, Tool 호출 순서와 업무 의존성을 관리하는 Agent Workflow를 구축합니다.

예를 들어:

> "내일 체크인인데 일정이 바뀌어서 예약 취소하고 환불받고 싶어요."

```text
Intent Detection
      ↓
Booking 조회
      ↓
Booking 상태 확인
      ↓
Cancellation Policy 조회
      ↓
Refund 조건 확인
      ↓
환불 금액 계산
      ↓
고객 최종 확인
      ↓
Cancel Booking
      ↓
Process Refund
      ↓
결과 검증
      ↓
고객에게 결과 안내
```

이를 통해 단순한 질의응답을 넘어 **조회 → 판단 → 실행 → 결과 확인**으로 이어지는 업무 자동화를 구현합니다.

### 5. 예외 처리 및 안전한 업무 실행

금융·예약·환불과 같이 실제 상태가 변경되는 업무는 Agent의 판단만으로 무조건 실행하지 않고, 업무 위험도와 조건에 따라 실행 여부를 제어합니다.

```text
정상적인 단순 문의
→ Agent 자동 응대

예약 정보 조회
→ Agent 자동 처리

취소 가능 여부 확인
→ 정책 기반 자동 판단

실제 취소/환불
→ 고객 최종 확인

정책 조회 실패 / 데이터 불일치
→ 자동 실행 중단
→ Fallback

복합 분쟁 / 판단 불가능한 요청
→ Human Escalation
```

Agent가 필요한 정보를 확인하지 못한 상황에서 임의로 답변하는 **Silent Fallback을 방지**하고, 판단 근거가 부족한 경우 명시적으로 예외 처리합니다.

### 6. Agent 응답 및 업무 결과 검증

Agent가 생성한 응답뿐 아니라 실제 업무 처리 결과까지 검증합니다.

검증 기준:

* 예약 상태와 응답 내용의 일치 여부
* 숙소 정책과 안내 내용의 일치 여부
* 환불 정책과 계산 결과의 일치 여부
* Tool 실행 결과와 고객 안내 내용의 일치 여부
* 중복 업무 실행 여부
* 예외 상황에서의 Fallback 여부

특히 예약 취소·환불과 같은 상태 변경 작업에서는 **멱등성을 고려하여 동일 요청이 반복되어도 중복 처리가 발생하지 않도록 설계**합니다.

---

## 핵심 Agent Architecture

```text
                         Customer
                            │
                            ↓
                    Customer Support Agent
                            │
                  Intent / Task Analysis
                            │
                            ↓
                    Agent Orchestrator
                            │
             ┌──────────────┼──────────────┐
             ↓              ↓              ↓
       Booking Tool    Property Tool   Policy Tool
             │              │              │
             ↓              ↓              ↓
       예약 데이터       숙소 데이터       정책 데이터
             │              │              │
             └──────────────┼──────────────┘
                            ↓
                     Decision / Action
                            │
                  ┌─────────┴─────────┐
                  ↓                   ↓
              Auto Process       HITL / Escalation
                  │                   │
                  ↓                   ↓
             Result Verify       Human Review
                  │
                  ↓
             Customer Response
```

## 기술 스택

* **Frontend**: Next.js 14, TypeScript
* **Backend**: Python, FastAPI
* **AI Agent**: LangGraph / LLM
* **Validation**: Pydantic
* **Data Fetching**: REST API
* **Database**: PostgreSQL
* **Vector Search**: Vector DB
* **UI**: Tailwind CSS, shadcn/ui
* **State / API**: TanStack Query
* **Mock / Test**: MSW
* **Documentation**: Markdown

## 주요 도메인

```text
User
 └── 고객 계정

Host
 └── 숙소 호스트

Property
 └── 숙소

Room
 └── 객실 / 숙박 공간

Booking
 └── 예약

Payment
 └── 결제 / 환불

Policy
 └── 취소 / 환불 / 이용 정책

Support
 └── 고객 문의 / CS 처리
```

## Agent Tool 구조

```text
tools/
├── booking/
│   ├── get_booking
│   ├── cancel_booking
│   └── update_booking
│
├── property/
│   ├── get_property
│   └── get_amenities
│
├── customer/
│   └── get_customer
│
├── policy/
│   ├── get_cancellation_policy
│   └── get_refund_policy
│
└── payment/
    ├── calculate_refund
    └── process_refund
```

각 Tool은 하나의 명확한 책임을 갖도록 구성하고, Agent가 직접 DB를 조작하기보다 **명시된 Tool/API를 통해 업무를 수행하도록 설계합니다.**

## 데이터 및 지식 구조

Agent의 업무 판단에 필요한 정보를 데이터 영역별로 분리합니다.

```text
숙소 데이터
    ↓
Property / Room / Amenity

예약 데이터
    ↓
Booking / Check-in / Check-out

고객 데이터
    ↓
Customer / Guest

정책 데이터
    ↓
Cancellation / Refund / House Rules

        ↓

     Agent Tools
        ↓
  Agent Workflow
```

정책과 숙소 정보처럼 변경 가능성이 있는 정보는 별도의 지식 구조로 관리하여 Agent가 최신 정보를 조회한 후 응답하도록 구성합니다.

## 디렉토리 구조

```text
app/
├── api/
│   ├── bookings/
│   ├── properties/
│   ├── customers/
│   ├── payments/
│   └── support/
│
├── agent/
│   ├── graph/
│   ├── nodes/
│   ├── tools/
│   ├── prompts/
│   └── policies/
│
├── models/
├── schemas/
├── services/
└── repositories/

frontend/
├── app/
│   ├── properties/
│   ├── bookings/
│   └── support/
│
└── components/

docs/
├── architecture.md
├── agent-workflow.md
├── tool-spec.md
├── policy.md
└── erd-notes.md
```

## 핵심 설계 원칙

### SSoT

숙소·예약·정책 정보의 원천을 명확히 정의하고 Agent가 임의로 정보를 생성하지 않도록 합니다.

### SRP

각 Tool과 Agent Node가 하나의 명확한 책임을 갖도록 분리합니다.

### Idempotency

예약 취소·환불 등 상태를 변경하는 작업에서 동일 요청이 반복되어도 중복 처리가 발생하지 않도록 합니다.

### Atomicity

예약 취소와 환불 등 연관된 상태 변경 과정에서 부분 처리로 인한 데이터 불일치가 발생하지 않도록 처리 흐름을 관리합니다.

### Silent Fallback 금지

필요한 데이터나 정책을 확인하지 못한 경우 임의의 답변을 생성하지 않고 Fallback 또는 Human Escalation으로 전환합니다.

### Human-in-the-Loop

고객의 최종 승인이 필요한 업무나 Agent가 판단하기 어려운 예외 상황에서만 사람의 개입을 요청하여 **정상 업무의 자동화율을 높이고 예외 업무만 사람이 처리하는 구조**를 지향합니다.

## 기대 효과

```text
기존 CS
고객 문의
  ↓
상담원 확인
  ↓
예약 조회
  ↓
정책 확인
  ↓
취소/환불 처리
  ↓
고객 응답


Agent 기반 CS
고객 문의
  ↓
Agent
  ├─ 예약 조회
  ├─ 숙소 조회
  ├─ 정책 조회
  ├─ 조건 판단
  ├─ Tool 실행
  └─ 결과 검증
  ↓
자동 응대 / 업무 처리
  ↓
예외 상황만 Human Escalation
```

본 프로젝트의 목표는 단순한 **AI 고객상담 챗봇 구현**이 아니라, 숙박 플랫폼의 실제 CS 업무를 기능 단위로 분해하고 **Agent가 데이터 조회·정책 판단·Tool 실행·결과 검증까지 수행하는 업무 자동화 시스템**을 구축하는 것입니다.

## 실행 방법

```bash
npm install
npm run dev
```

FastAPI 서버 실행:

```bash
uvicorn app.main:app --reload
```

API 문서:

```text
/docs
```
