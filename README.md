# LangGraph HITL Workflow for Support Automation

*Personal project*

![Agent Engineering](https://img.shields.io/badge/Agent%20Engineering-0E1725?style=flat-square)
![LangGraph](https://img.shields.io/badge/LangGraph-41506A?style=flat-square) ![HITL](https://img.shields.io/badge/HITL-41506A?style=flat-square) ![tool calling](https://img.shields.io/badge/tool%20calling-41506A?style=flat-square) ![state management](https://img.shields.io/badge/state%20management-41506A?style=flat-square) ![idempotency](https://img.shields.io/badge/idempotency-41506A?style=flat-square) ![compensation](https://img.shields.io/badge/compensation-41506A?style=flat-square)

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

---

## Architecture

```
              ┌────────────────────────────────────────────────┐
              │            SUPPORT UI  (Next.js)               │
              │      request  →  confirm  →  result            │
              │  amount and policy shown before approval       │
              └───────────────────────┬────────────────────────┘
                                      │  SSE
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

## Results

| | |
|---|---|
| Scenarios | **8/8** — normal, boundary, exception |
| **Misinformation rate** | **0.0%** |
| Duplicate request | refund executes **once** |
| PG failure | booking restored to `CONFIRMED`, escalated |
| Compensation failure | `needs_human`, partial state left visible |
| Policy not indexed | abstains — no similar policy substituted |
| Tests | **33** |

Refund amounts follow the policy tier, not a heuristic: a booking ten days out
under a flexible policy returns 240,000원 in full; the same request one day
before check-in returns 36,000원, which is the 20% tier.

**A real bug surfaced here.** The idempotency record was stored as
`{"status": "DONE", **result}` — and `result` also carried a `status`
(`"CANCELLED"`), which overwrote the record state. Retries were then judged
"still in progress" and the replay path never fired. It was caught only because
a test called the write tool twice. Idempotency does not fail visibly; it fails
the second time.

**Adding retrieval did not weaken the guarantees.**
`get_cancellation_policy` moved from a dictionary lookup to hybrid document
search, and all 18 pre-existing tests still passed unchanged — including the one
that requires escalation when a policy is missing. The safety contract was
written against behavior, not implementation.

Escalation runs at 3/8. Lowering that is not the goal; **raising automation
while misinformation stays at 0% is.** When the policy cannot be confirmed,
escalating is the correct answer.

## Stack

| | |
|---|---|
| Language | Python 3.11 |
| Orchestration | LangGraph — interrupt + checkpointer |
| API | FastAPI · Pydantic v2 · SSE |
| Retrieval | `marketplace-retrieval` (from RAG-Marketing) |
| Storage | PostgreSQL (domain + graph checkpoints) |
| Frontend | Next.js 14 · TypeScript · Tailwind · shadcn/ui |
| Testing | pytest — 33 tests |

Runs without an API key. Intent classification defaults to deterministic rules —
in a path where a wrong classification costs money, the rule is the baseline and
the LLM is the substitutable part.

## Run locally

```bash
pip install -r backend/requirements.txt
cd backend
pytest                          # 33 tests
python scripts/run_agent_demo.py

uvicorn app.main:app --reload   # /docs
```

## Docs

| | |
|---|---|
| `backend/app/agent/graph.py` | Node graph and the interrupt point |
| `backend/app/agent/tools.py` | Read/write split and risk levels |
| `backend/app/agent/policy_rag.py` | Retrieval with an abstain gate |
| `backend/app/domain.py` | Idempotency and compensation at the store |
| `backend/tests/test_agent_safety.py` | Each guarantee, pinned |
