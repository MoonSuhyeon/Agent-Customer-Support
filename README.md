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

**8/8 scenarios** · **0% misinformation** · duplicate requests refund **once** · **126 tests**

---

## Architecture

```
   ┌──────────────────────────────┐  ┌──────────────────────────────┐
   │  CUSTOMER — in Data-Growth   │  │  OPERATOR — in Data-Growth   │
   │  my bookings → ask to cancel │  │  waiting queue → approve     │
   │  the booking id rides along  │  │  amount + policy shown first │
   │  nobody types it             │  │  one console, four services  │
   └───────────────┬──────────────┘  └───────────────┬──────────────┘
                   │      HTTP + the caller's token  │
                   └──────────────┬──────────────────┘
                                  ▼
        ┌──────────────────────────────────────────────────────────┐
        │                    AGENT API  (FastAPI)                  │
        │                                                          │
        │  POST /support/messages      start or continue           │
        │       + booking_id           what the screen already     │
        │                              knows. A typo here would    │
        │                              point at someone else's     │
        │  POST /support/confirm       customer approval  ← gate   │
        │  GET  /support/sessions      the waiting queue           │
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
| Testing | pytest — 126 tests |

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

This applies to the in-memory store, where cancelling and refunding are two steps.
Against the booking service they are **one atomic request**, so the in-between
state never exists and there is nothing to compensate. `RemoteStore.cancel` is
therefore a no-op that returns the booking — writing a separate call order for the
remote path would give `cancel_and_refund` two implementations, and one of them
would eventually be fixed alone.

### Deterministic rules as the intent baseline

**Buys** — no model call on the classification path, so no token cost and no
latency there, and the same input always routes the same way. Ambiguous input
returns `UNKNOWN` and escalates rather than guessing.
**Costs** — narrow phrasing coverage. Requests worded outside the rule set
escalate that would not need to, which shows up as a higher escalation rate.

### The agent does not own the bookings it acts on

This service shipped with four hardcoded demo bookings. A customer opening an
inquiry brings a real booking number, and that store would never find it — a
button that fails on 100% of real bookings.

**Buys** — `RemoteStore` reads from the booking service instead, so the agent works
on real reservations. Authorisation came free: it calls **`/bookings/me` with the
caller's token** rather than `/bookings/{id}`, so the range it can see is the
caller's own bookings. Nothing had to be written to keep it out of other people's
data; it simply cannot reach them. When a number is not in that list, the answer
does not distinguish "no such booking" from "not yours" — telling them apart lets
someone probe for the existence of other people's reservations.
**Costs** — a network hop inside the graph, and a second failure mode. "The booking
service is unreachable" is not "the booking does not exist", so it answers 503
rather than escalating as if the reservation were missing.

### The refund amount is not this service's to compute

The agent explained a policy and quoted an amount. The booking service refunded
`total_price` regardless of when you cancelled. So the agent would say *0원 환불*
and 90,000원 would leave — the explanation, which is this agent's whole reason to
exist, became a lie.

The other repair was to let the caller pass the amount. That opens forgery: the
customer's browser can call the same endpoint.

**Buys** — the policy moved to the service that owns the money, and the agent asks
for the number instead of deriving it (`store.refund_quote`). Quote and charge run
the same function, so they cannot drift. The write call sends **no amount at all**.
**Costs** — this repository no longer explains cancellation rules on its own; it
needs the booking service up to say anything about money. The trade is that
explanation and execution can no longer disagree.

### No UI in this repository

The approval gate is the point of this project, so it needs a screen. There are
now two — the customer opening an inquiry and the operator approving it — and both
live in Data-Growth rather than here.

**Buys** — one console serves four services, so the design system, the navigation
and the build exist once rather than four times. This repository stays what it is:
a graph, a safety contract, and an API. Nothing here needs Node.
**Costs** — you cannot clone this repository and see either screen. The gate is
still demonstrable without them — `scripts/run_agent_demo.py` walks the whole loop
and `/docs` lets you drive it by hand — but the visual proof is one repository away.

For a long time only the operator screen existed, and it worked by having staff
type the customer's sentence themselves. The page was called *approvals* while
**nothing ever arrived to approve**: no path existed for a customer to open a
session. `GET /support/sessions?awaiting=true` and the entry point in
`/my/bookings` are what made the name true.

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
pytest                          # 126 tests
python scripts/run_agent_demo.py

uvicorn app.main:app --reload   # API docs at /docs
```

Runs without an API key and without Node. `run_agent_demo.py` walks the full loop
in the terminal; `/docs` lets you drive the approval gate by hand.

Real reservations need the booking service alongside it:

```bash
BOOKING_API_URL=http://127.0.0.1:8000 uvicorn app.main:app --reload
```

Without it the demo bookings (`B1001`–`B1004`) still work — they live in this
service. Numbers starting with `BK` are routed to the booking service instead, so
the two paths are told apart by the shape of the id, which is exactly what makes
them two stores.

The console that calls this API lives in
[Data-Growth](https://github.com/MoonSuhyeon/Data-Growth) — one operator screen for four services rather than four
separate UIs. It generates its TypeScript types from the `openapi.json` committed
here, so a change to this schema breaks its build instead of silently rendering a
wrong value.


## Docs

| | |
|---|---|
| `backend/app/agent/graph.py` | Node graph and the interrupt point |
| `backend/app/agent/tools.py` | Read/write split and risk levels |
| `backend/app/agent/policy_rag.py` | Retrieval with an abstain gate |
| `backend/app/domain.py` | Idempotency and compensation at the store |
| `backend/tests/test_agent_safety.py` | Each guarantee, pinned |
