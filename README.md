# LangGraph HITL Workflow for Support Automation

*Personal project*

![Agent Engineering](https://img.shields.io/badge/Agent%20Engineering-0B1220?style=for-the-badge)

![LangGraph](https://img.shields.io/badge/LangGraph-7C3AED?style=for-the-badge) ![tool calling](https://img.shields.io/badge/tool%20calling-7C3AED?style=for-the-badge) ![HITL](https://img.shields.io/badge/HITL-BE123C?style=for-the-badge) ![idempotency](https://img.shields.io/badge/idempotency-BE123C?style=for-the-badge) ![compensation](https://img.shields.io/badge/compensation-BE123C?style=for-the-badge) ![state management](https://img.shields.io/badge/state%20management-475569?style=for-the-badge)

Most support questions are lookups. **Cancellation and refund are not** — they
move money and change booking state, and the guest is usually asking the day
before check-in, when the refund tier is about to change.

That makes automation attractive and dangerous at the same time. A chatbot that
answers wrongly produces a bad reply. An agent that acts wrongly produces a
double refund, or a booking that is cancelled while the money never came back.
Retries and double-clicks make both of those routine failure modes rather than
edge cases.

So the design question is not "how smart is the model" but **"how much can be
automated when being wrong costs real money, and what happens the moment it is
wrong?"**

I built an agent that **halts before every state change and waits for the
customer, blocks duplicate execution at the database constraint rather than in
application logic, rolls back cancellation when the refund fails, re-reads state
after acting to confirm what it told the customer, and escalates instead of
guessing whenever the policy cannot be confirmed.**

Policy lookup reuses the retrieval core from
[RAG-Marketing](https://github.com/MoonSuhyeon/RAG-Marketing). Search always
returns *something*, so that core also carries an abstain path — otherwise
attaching retrieval would have quietly broken the no-guessing rule.

**8/8 scenarios** · **0% misinformation** · duplicate requests refund **once** · **33 tests**

---

## Architecture

```
              ┌────────────────────────────────────────────────┐
              │  OPERATOR CONSOLE  — lives in Data-Growth      │
              │      request  →  ⏸ approve  →  result          │
              │  amount and policy shown before approval       │
              │  one console for four services, not four UIs   │
              └───────────────────────┬────────────────────────┘
                                      │  HTTP
                                      ▼
        ┌──────────────────────────────────────────────────────────┐
        │                    AGENT API  (FastAPI)                  │
        │                                                          │
        │  POST /support/messages      start or continue           │
        │  POST /support/confirm       customer approval  ← gate   │
        │  GET  /support/sessions/{id} state and full trace        │
        │                                                          │
        │  confirm is a separate endpoint because the graph        │
        │  is suspended, not because the UI needs two screens      │
        └───────────────────────────┬──────────────────────────────┘
                                    │
                                    ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │                    LANGGRAPH ORCHESTRATOR                        │
    │                                                                  │
    │    intent ──▶ plan ──▶ retrieve ──▶ decide                       │
    │      │                    │            │                         │
    │      │ unclear            │ missing    │ already cancelled       │
    │      ▼                    ▼            ▼                         │
    │   escalate            escalate      respond                      │
    │                                        ▲                         │
    │                            confirm ⏸───┘  interrupt_before       │
    │                               │                                  │
    │                    ═══════════╪═══════════  customer approval    │
    │                               │                                  │
    │                            execute ──▶ verify ──▶ respond        │
    │                               │           │                      │
    │                               ▼           ▼                      │
    │                          escalate     escalate                   │
    │                                                                  │
    │  CHECKPOINTER (PostgreSQL)                                       │
    │  the graph can sit at confirm for days and still resume          │
    │  state lives in the store, so API instances scale out            │
    └──────────────────────┬───────────────────────┬───────────────────┘
                           │                       │
                           ▼                       ▼
    ┌────────────────────────────────┐  ┌────────────────────────────────┐
    │        READ TOOLS   LOW        │  │       WRITE TOOLS   HIGH       │
    │        auto-executed           │  │    customer approval required  │
    │                                │  │                                │
    │  get_booking                   │  │  cancel_and_refund             │
    │  get_property                  │  │                                │
    │  get_cancellation_policy ──┐   │  │  1 claim idempotency key       │
    │  calculate_refund   MEDIUM │   │  │  2 cancel booking              │
    │    advisory only           │   │  │  3 refund via PG               │
    └────────────────────────────┼───┘  │  4 on failure → restore        │
                                 │      │  5 on restore failure →        │
                                 │      │       needs_human, stop        │
                                 │      └───────────────┬────────────────┘
                                 ▼                      │
    ┌────────────────────────────────────────────┐      │
    │      POLICY RETRIEVAL                      │      │
    │      retrieval  (shared package)           │      │
    │                                            │      │
    │  policy docs indexed per property          │      │
    │  properties without a policy are NOT       │      │
    │  indexed — an index entry would become     │      │
    │  a guess                                   │      │
    │                                            │      │
    │  metadata filter → dense + BM25 → RRF      │      │
    │            ↓                               │      │
    │  assess(hits, min_score, min_margin)       │      │
    │            ↓                               │      │
    │    ┌──────────────┬──────────────────┐     │      │
    │    │ grounded     │ abstain          │     │      │
    │    │ use policy   │ tool fails →     │     │      │
    │    │              │ escalate         │     │      │
    │    └──────────────┴──────────────────┘     │      │
    └────────────────────────────────────────────┘      │
                                                        ▼
        ┌──────────────────────────────────────────────────────────┐
        │                        STORE                             │
        │                                                          │
        │  Booking · Property · CancellationPolicy                 │
        │                                                          │
        │  IDEMPOTENCY TABLE   UNIQUE(key)                         │
        │    second identical request replays the stored result    │
        │    the race cannot form, because it is not a read-       │
        │    then-write in application code                        │
        │                                                          │
        │  AUDIT LOG   every write tool call, with amount          │
        └──────────────────────────────────────────────────────────┘

        ┌──────────────────────────────────────────────────────────┐
        │                    EVALUATION HARNESS                    │
        │                                                          │
        │  scenarios   normal · boundary · exception               │
        │  expected outcome declared per scenario, then compared   │
        │                                                          │
        │  misinformation rate is the release gate — automation    │
        │  rate is only meaningful while it stays at zero          │
        └──────────────────────────────────────────────────────────┘
```

---

## Stack

| | |
|---|---|
| Language | Python 3.11 |
| Orchestration | LangGraph — interrupt + checkpointer |
| API | FastAPI · Pydantic v2 · SSE |
| Retrieval | `marketplace-retrieval` (from RAG-Marketing) |
| Storage | PostgreSQL (domain + graph checkpoints) |
| Testing | pytest — 33 tests |

Runs without an API key. Intent classification defaults to deterministic rules —
in a path where a wrong classification costs money, the rule is the baseline and
the LLM is the substitutable part.

---

## Trade-offs

| | |
|---|---|
| Scenarios | **8/8** — normal, boundary, exception |
| **Misinformation rate** | **0.0%** |
| Duplicate request | refund executes **once** |
| PG failure | booking restored to `CONFIRMED`, escalated |
| Compensation failure | `needs_human`, partial state left visible |
| Policy not indexed | abstains — no similar policy substituted |

### The graph halts before every state change

**Buys** — no wrong refund is possible without a human saying yes.
Misinformation stays at **0.0%** across all eight scenarios, and no path reaches
`execute` without passing `confirm` — asserted by test, not by convention.
**Costs** — a ceiling on full automation. Three of eight scenarios escalate, and
that number cannot go to zero by design.

Lowering escalation is not the goal. Raising automation **while misinformation
stays at zero** is. When a policy cannot be confirmed, escalating is the correct
answer, not a failure.

### A database constraint instead of an application-level duplicate check

Reading "was this already processed?" and then acting leaves a window for a
second request to enter it.

**Buys** — the race cannot form. Calling the write tool twice with the same key
executes the refund **once** and replays the stored result the second time.
**Costs** — every write path must carry an idempotency key. It is a discipline
imposed on all future write tools, not a local fix.

This is also where a real bug surfaced: the idempotency record was stored as
`{"status": "DONE", **result}`, and `result` carried its own `status`
(`"CANCELLED"`), overwriting the record state. Retries were then judged still in
progress and the replay path never fired. Idempotency does not fail visibly — it
fails the second time.

### Checkpoints in PostgreSQL instead of process memory

**Buys** — the graph can sit at `confirm` for days and still resume, and API
instances scale horizontally because no session lives in a process.
**Costs** — a database write at each node boundary, and graph state becomes
schema that has to be migrated.

### Compensation instead of a distributed transaction

**Buys** — no partial state survives. When the payment gateway rejects a refund,
the cancellation is rolled back and the case escalates; when the rollback itself
fails, the state is left visible and flagged `needs_human` rather than quietly
repaired.
**Costs** — eventual consistency. A brief window exists where the booking is
cancelled and the refund has not landed.

### Deterministic rules as the intent baseline

**Buys** — no model call on the classification path, so no token cost and no
latency there, and the same input always routes the same way. Ambiguous input
returns `UNKNOWN` and escalates rather than guessing.
**Costs** — narrow phrasing coverage. Requests worded outside the rule set
escalate that would not need to, which shows up as a higher escalation rate.

### No UI in this repository

The approval gate is the point of this project, so it needs a screen. That screen
lives in the operator console instead of here.

**Buys** — one console serves four services, so the design system, the navigation
and the build exist once rather than four times. This repository stays what it is:
a graph, a safety contract, and an API. Nothing here needs Node.
**Costs** — you cannot clone this repository and see the approval screen. The gate
is still demonstrable without it — `scripts/run_agent_demo.py` walks the whole loop
and `/docs` lets you drive it by hand — but the visual proof is one repository away.

### Retrieval with an abstain path

Search always returns something. Attaching it naively would have broken the
no-guessing rule without any test failing.

**Buys** — `get_cancellation_policy` moved from a dictionary lookup to hybrid
document search and **all 18 pre-existing tests passed unchanged**, including the
one requiring escalation when a policy is missing. The safety contract was
written against behaviour, so the implementation could be replaced under it.
**Costs** — retrieval quality now caps the automation rate. A threshold that is
too strict escalates good cases; too loose and it guesses. That threshold is the
dial, and it is set conservatively.

## Run locally

```bash
pip install -r backend/requirements.txt
cd backend
pytest                          # 33 tests
python scripts/run_agent_demo.py

uvicorn app.main:app --reload   # API docs at /docs
```

Runs without an API key and without Node. `run_agent_demo.py` walks the full loop
in the terminal; `/docs` lets you drive the approval gate by hand.

## Docs

| | |
|---|---|
| `backend/app/agent/graph.py` | Node graph and the interrupt point |
| `backend/app/agent/tools.py` | Read/write split and risk levels |
| `backend/app/agent/policy_rag.py` | Retrieval with an abstain gate |
| `backend/app/domain.py` | Idempotency and compensation at the store |
| `backend/tests/test_agent_safety.py` | Each guarantee, pinned |
