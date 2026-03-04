# TX Composition Applied: A Technical Whitepaper

> *How saga patterns, causal tracing, and transaction composition can
> reshape PyBend's actor architecture -- and where they should not.*
> *Companion to the [propositions document](TX-sagas-propositions.md).*

---

## Abstract

PyBend's actor system routes individual TX messages through a Matrix to
ActorModel handlers. This works well for independent CRUD operations but
hits a ceiling when workflows span multiple actors -- creating an order,
reserving inventory, and charging payment must either succeed together or
undo together. Today, developers hand-code compensation logic inside
`@expose_route` methods, creating fragile, untestable rollback paths.

The saga pattern -- a sequence of local transactions with compensating
actions on failure -- is the theoretically correct composition strategy
for asynchronous actor systems. Our codebase already contains seven of
the fourteen building blocks that mature saga frameworks use: TX
envelopes, error signaling, request-response correlation, interceptors,
lifecycle events, timeout handling, and idempotency keys. The missing
pieces are composition glue, not new foundations.

This paper argues for a phased approach: (1) add causal tracing fields
to TX for debugging; (2) build an interceptor-based TX journal for
audit; (3) introduce a Saga class that chains `NetworkAdapter.request()`
calls with co-located compensation. Each phase delivers standalone
value. The total investment is approximately 300 lines of new code
across three new files, with zero changes to existing production code.

---

## 1. Introduction: Why This Matters Now

PyBend v0.9 ships three routing levels, an agent system, and protocol
adapters for HTTP, WebSocket, MCP, and ActivityPub. The framework has
reached the inflection point where **multi-actor coordination** becomes
a recurring need rather than an edge case.

Three forces make transaction composition timely:

**Agent workflows demand multi-step reliability.** The `AgentActor`
system (v0.10 planning) will execute tool calls that span multiple
models -- an agent discovering and calling `products_create` followed
by `comments_create` followed by `notifications_send`. If step 2 fails,
step 1's effects persist as orphaned data. Today there is no framework
mechanism to undo completed steps.

**The `@expose_route` compensation problem is already visible.** The
research document's anti-pattern example -- a `purchase()` method with
manual `Order.delete()` and `Product.update()` rollback code -- is
exactly the pattern that emerges when developers build multi-step
operations on single-TX primitives. This code is fragile, untestable
in isolation, and invisible to the framework (no logging, no tracing,
no retry semantics).

**Production debugging needs causal chains.** When a user reports
"my order went through but my inventory wasn't updated," the current
system offers no way to trace the chain of TXs that constituted the
operation. Each TX is fire-and-forget with no lineage. Debugging
requires cross-referencing timestamps in server logs -- a process that
scales poorly.

---

## 2. Principles Worth Importing

### 2.1 Causal Tracing (Correlation + Causation IDs)

Every message in a distributed system should carry three identifiers:
its own ID, the ID of the root operation it belongs to (correlation),
and the ID of the message that directly caused it (causation). This
formulation, attributed to Greg Young and adopted by Rails Event Store,
Confluent, and OpenTelemetry, creates two navigable dimensions:
"everything in this operation" and "what caused what."

**Why it matters for us:** `TX.uuid` provides message identity.
`TX.meta['in_reply_to']` provides one-hop causation. But there is no
correlation ID to group all TXs in a multi-step operation, and
`in_reply_to` does not chain transitively. Adding two fields to the
TX dataclass -- `correlation_id` and `causation_id` -- with automatic
propagation in `reply()` and `error()` would give us both dimensions
at near-zero cost.

**Where we already partially implement it:** `NetworkAdapter.request()`
at `/workspace/src/pybend/core/api/network_adapter.py` stores pending
Futures keyed by `tx.uuid` and resolves them when a reply arrives with
`meta['in_reply_to']` matching. This is one-hop correlation. Extending
it to multi-hop requires only that child TXs inherit the root's
correlation ID.

### 2.2 Saga Composition (Orchestration over Choreography)

Sagas break a multi-step operation into local transactions, each with
a compensating action that undoes its effects on failure. Orchestrated
sagas use a central coordinator (the saga runner) that knows the full
workflow and manages compensations. Choreographed sagas let each
service react independently to events.

**Why it matters for us:** Our `_publish_lifecycle()` mechanism in
`ActorModel` is event choreography -- it publishes LIFECYCLE TXs to
subscribers after CRUD operations. But choreography makes failure
handling distributed and hard to trace. For multi-step workflows where
rollback order matters, orchestration is simpler to reason about and
debug.

**Where we already partially implement it:** `NetworkAdapter.request()`
is a saga step executor -- it sends a TX, awaits the correlated response,
and handles timeout. Chaining multiple `request()` calls with error
checking and reverse-order compensation on failure is the orchestrated
saga pattern. We have the step executor; we lack the orchestrator.

### 2.3 Co-Located Compensation (Sage Pattern)

Elixir's Sage library co-locates compensation with its forward
operation: `run(:step, &do_thing, &undo_thing)`. This eliminates the
"forgot to compensate" bug class that Temporal's manual
`compensations.append()` pattern creates.

**Why it matters for us:** PyBend's philosophy is "make invalid states
unrepresentable." Co-located compensation makes it structurally
difficult to define a step without considering its rollback -- the API
forces you to think about undo at the moment you define the do.

**Where we can apply it:** Our `@expose_route` decorator at
`/workspace/src/pybend/core/utils/decorators.py` proves that metadata
decorators are a natural pattern in the codebase. A `@step`/`@compensates`
pair follows the same principle.

### 2.4 Interceptor-Based Cross-Cutting Concerns

Saga coordinators need logging, tracing, timeout enforcement, and
authorization at every step. These are cross-cutting concerns that
should not be embedded in step logic.

**Why it matters for us:** `Actor.use()` interceptors already solve
this problem for individual actors. The auth interceptor at
`/workspace/src/pybend/core/api/auth_interceptor.py` demonstrates the
pattern: inspect the TX, modify or reject it, pass through. Saga
journaling, timeout enforcement, and retry logic are all interceptors.

---

## 3. Our Architecture Through This Lens

Viewed through the saga lens, PyBend's current architecture reveals
both hidden strengths and clear gaps.

```
    CURRENT ARCHITECTURE (Saga-Annotated)

    +------------------+
    |   HTTP Request   |  (Initiating event -- no correlation ID)
    +--------+---------+
             |
    +--------v---------+
    |   NetworkAPI     |  STEP EXECUTOR: request() correlates
    |   .request(tx)   |  via uuid/in_reply_to (one-hop only)
    +--------+---------+
             |
    [request interceptors]
    |  auth_interceptor   <-- Cross-cutting: EXISTS
    |  journal?           <-- Cross-cutting: MISSING
    |  tracing?           <-- Cross-cutting: MISSING
             |
    +--------v---------+
    |     Matrix       |  ROUTER: routes to child actors
    |   .inbox(tx)     |  (no saga awareness)
    +--------+---------+
             |
       /     |     \
      v      v      v
  [Product] [Order] [Payment]   <-- SAGA PARTICIPANTS
      |      |       |              Each handles ONE TX independently
  handler_crud()                    No cross-TX coordination
      |      |       |
  _publish_lifecycle()          <-- CHOREOGRAPHY: exists but
      |      |       |              no failure handling
      v      v       v
  [WS] [AP] [???]              <-- No saga subscriber
```

**Strengths revealed:**
- The request/response correlation in `NetworkAdapter` is
  architecturally identical to Temporal's activity invocation
- The interceptor chain is the right place for saga cross-cutting
  concerns (the two-tier auth pattern proves this)
- The `TX.error()` / `is_error` mechanism provides the failure
  signaling that saga coordinators need

**Gaps revealed:**
- No multi-hop causal tracking (correlation dies at reply)
- No TX persistence (fire-and-forget, no history)
- No compensation mechanism (errors signal failure but do not
  undo previous successes)
- No saga coordinator (no way to define "do A, then B, then C;
  if C fails, undo B then A")

---

## 4. The Synthesis: Where Two Worlds Meet

### 4.1 Integration Point: TX Envelope Extension

**Current state:** TX carries `uuid`, `meta['in_reply_to']`, and
nothing else for lineage tracking.

**Proposed state:** TX carries `correlation_id` and `causation_id` as
first-class fields, propagated automatically through `reply()`,
`error()`, and a new `spawn()` method.

```
    BEFORE                          AFTER

    TX(uuid=A)                      TX(uuid=A, corr=A, cause='')
       |                               |
    TX(uuid=B,                      TX(uuid=B, corr=A, cause=A)
       meta={in_reply_to: A})          |
       |                            TX(uuid=C, corr=A, cause=B)
    TX(uuid=C)   <-- NO LINK           |
       |                            TX(uuid=D, corr=A, cause=C)
    TX(uuid=D)   <-- NO LINK
                                    Query: by_correlation(A) -> [A,B,C,D]
                                    Query: by_causation(B) -> [C]
```

**Migration path:** Add two fields with empty-string defaults. Existing
code produces TXs without causal fields -- they work identically. New
code uses `tx.spawn()` or manual field setting. Over time, all TX
creation points adopt the pattern. Zero breaking changes.

**Expected outcome:** Any multi-step operation becomes traceable from
trigger to completion. Debugging time for multi-actor issues drops from
"hours of log archaeology" to "one query."

### 4.2 Integration Point: Interceptor-Based Journaling

**Current state:** TXs leave no trace after processing. The only record
of what happened is the resulting database state.

**Proposed state:** An opt-in `TXJournal` interceptor logs every TX that
passes through the Matrix, queryable by correlation, causation, actor,
and time range.

```
    BEFORE                          AFTER

    TX -> Matrix -> Actor           TX -> Matrix -> Actor
           |                              |
           v                              v
       (nothing)                    [TXJournal interceptor]
                                          |
                                    +-----v------+
                                    | tx_journal  |
                                    | uuid, name  |
                                    | corr, cause |
                                    | timestamp   |
                                    +-------------+
```

**Migration path:** Wire in `create_app()` behind a config flag:
`create_app(..., journal=True)`. Default off. In-memory for dev, SQLite
for production. The journal interceptor is registered on `Matrix.inbox`
-- the same wiring point as auth interceptors.

**Expected outcome:** Full audit trail. Post-mortem debugging. Compliance
for sensitive domains. Foundation for future replay capabilities.

### 4.3 Integration Point: Saga Orchestrator

**Current state:** Multi-step operations are hand-coded in
`@expose_route` methods with manual error handling and cleanup.

**Proposed state:** A `Saga` class chains `request()` calls with
co-located compensation. On failure, compensations execute in reverse
order automatically.

```
    BEFORE                              AFTER

    @expose_route('/purchase')          @expose_route('/purchase')
    def purchase(self, user):           async def purchase(self, user):
        order = Order.create(...)           result = await (
        self.stock -= 1                         Saga("purchase")
        Product.update(...)                     .step("order",
        charge = Payment.charge(...)                tx_create_order,
        if not charge:                              compensate=tx_delete_order)
            Order.delete(order.id)              .step("stock",
            self.stock += 1                         tx_update_stock,
            Product.update(...)                     compensate=tx_restore_stock)
            raise MethodError(...)              .step("charge",
        return ...                                  tx_charge_payment,
                                                    compensate=tx_refund)
    # Manual, fragile, untestable           .execute(adapter)
    # No logging, no tracing            )
    # Compensation easily forgotten      # Automatic, traceable, testable
                                         # Compensation co-located
                                         # Journal captures every step
```

**Migration path:** New `actors/saga.py` file. No changes to Actor,
Matrix, TX, or ActorModel. Sagas are opt-in -- developers create them
when they need multi-step coordination. Existing single-TX operations
continue working unchanged.

**Expected outcome:** Reliable multi-step workflows. Eliminable
compensation bugs. Testable saga logic. Foundation for agent workflow
orchestration in v0.10.

---

## 5. Boundaries: Where This Does Not Apply

**Single-model CRUD operations do not need sagas.** Creating a Product,
updating a User, deleting a Comment -- these are atomic database
operations. Adding saga overhead to single-step operations would violate
"zero to working, then customize." The framework's strength for CRUD
apps must remain untouched.

**Level 1/2 (direct routes) should remain saga-free.** Sagas require
actor routing because they depend on `NetworkAdapter.request()` for
correlated step execution. Level 1/2 uses `routes_fastapi.py` with
direct StorableMixin calls -- no TX messaging, no actor routing. Adding
saga support to Level 1/2 would require either (a) forcing actor routing
or (b) a parallel saga mechanism. Neither is desirable. Sagas are a
Level 3 capability.

**Deterministic replay should not be attempted.** Temporal's replay
model requires that workflow code be deterministic -- no random numbers,
no current time, no non-deterministic operations. PyBend's handlers
freely mix logic and side effects. Imposing determinism constraints
would fundamentally conflict with the "transparent, not magical"
philosophy. The TX journal provides audit and debugging value without
replay's architectural constraints.

**Full event sourcing is not justified.** Event sourcing (storing all
state changes as events, rebuilding state by replaying them) is
powerful but adds significant complexity. Our SQLite storage stores
current state directly. For a schema-driven CRUD framework, current
state storage is the right default. The TX journal records messages
for audit, not for state reconstruction.

---

## 6. A Path Forward

### Phase 1: Causal Foundation (1-2 days)

Add `correlation_id` and `causation_id` to the TX dataclass. Update
`reply()` and `error()` to propagate them. Add `spawn()` for creating
child TXs in the same causal chain.

**Success criteria:** All existing tests pass. New tests verify
correlation propagation through reply chains. Manual test confirms
that a multi-actor operation (create Product with Comments) produces
TXs that share a correlation ID.

**Decision gate:** If correlation IDs do not propagate correctly
through the Matrix routing layer, investigate whether `Actor.send()`
needs to preserve causal context when bubbling to parent.

### Phase 2: Observability (3-5 days)

Build `TXJournal` with in-memory storage and interceptor factory.
Wire into `create_app()` behind `journal=True`. Add query methods:
`by_correlation()`, `by_causation()`, `by_actor()`, `by_timerange()`.

**Success criteria:** After running a multi-step operation, querying
`journal.by_correlation(root_id)` returns the complete ordered list
of TXs. Integration test verifies journal captures inbox and request
events.

**Decision gate:** If the in-memory journal shows clear debugging
value, proceed to SQLite persistence. If not, reassess whether the
journal granularity is right (too noisy? not enough detail?).

### Phase 3: Composition (1-2 weeks)

Build the `Saga` class with step registration, `execute()`, and
reverse-order compensation. Integrate with `NetworkAdapter.request()`
for step execution. Add `SagaResult` type with `.ok`, `.effects`,
`.error`.

**Success criteria:** A saga with three steps executes successfully.
A saga where step 2 fails compensates step 1. Journal shows the
complete saga trace including compensation TXs. All compensation
TXs carry `meta['compensation'] = True` for filtering.

**Decision gate:** If the Saga class is used by real application
code (agent workflows, multi-model operations), proceed to decorator
API (Proposition 4). If sagas are not needed, stop here -- the
primitives (causal tracing + journal) still provide standalone value.

---

## 7. Conclusion

PyBend's actor system is closer to saga-ready than it appears. The
TX envelope, request-response correlation, interceptor chains, and
lifecycle events are the exact building blocks that Akka, Orleans,
and Temporal use for multi-step workflows. What separates "collection
of independent TXs" from "composable TX workflows" is a narrow
bridge: two fields on the dataclass, one interceptor for logging,
one class for orchestration.

The recommended path adds approximately 300 lines of code across
three new files, with **zero changes to existing production code**.
Every phase delivers standalone value: Phase 1 improves debugging,
Phase 2 adds audit trails, Phase 3 enables reliable multi-step
workflows. Each phase is a natural decision gate -- proceed only if
the previous phase proves its value in practice.

This approach reinforces rather than challenges PyBend's core
philosophy. Causal tracing makes the system more **transparent**
("trace any behavior in under a minute"). The journal makes the
system more **inspectable** ("nothing is hidden behind abstractions
you can't see through"). The saga builder provides **primitives,
not opinions** -- a composable building block, not a rigid workflow
engine. And everything works **zero to working, then customize** --
opt-in, additive, backward compatible.

The competitive positioning is clear: frameworks like Temporal,
Prefect, and Dagster prove that workflow composition is a massive
market (Temporal alone raised $246M). But these are heavyweight
infrastructure requiring separate servers and new mental models.
PyBend can offer 30% of Temporal's value at 1% of its complexity --
exactly the leverage ratio that schema-driven frameworks should
target. The model is still the app. The saga just makes sure that
when the app spans multiple models, it stays consistent.

---

## References

**Research Documents:**
- `.traces/research/tx-sagas/01-technical-deep-dive.md` -- Industry patterns, production systems, theoretical foundations
- `.traces/research/tx-sagas/02-our-stack-relevance.md` -- PyBend gap analysis, primitives inventory, extension points
- `.traces/research/tx-sagas/03-composition-ergonomics.md` -- API design patterns, DX comparison matrix

**Codebase Files Referenced:**
- `/workspace/src/pybend/core/actors/tx.py` -- TX message envelope (84 lines)
- `/workspace/src/pybend/core/actors/actor.py` -- Actor base with interceptors (446 lines)
- `/workspace/src/pybend/core/actors/matrix.py` -- Matrix root actor and router (95 lines)
- `/workspace/src/pybend/core/models/actor_model.py` -- ActorModel bridge class (294 lines)
- `/workspace/src/pybend/core/api/network_adapter.py` -- NetworkAdapter with request/response correlation (107 lines)
- `/workspace/src/pybend/core/api/auth_interceptor.py` -- Auth interceptor pattern (109 lines)
- `/workspace/src/pybend/core/utils/decorators.py` -- @expose_route decorator (20 lines)
- `/workspace/src/pybend/core/app.py` -- Application builder and factory (329 lines)

**External Sources:**
- Garcia-Molina & Salem, "Sagas" (1987) -- Original saga pattern paper
- Greg Young -- Correlation ID and Causation ID formulation
- Temporal.io -- Durable workflow execution ($1.5B valuation, 12B+ executions/month at Uber)
- Nebo15/Sage -- Elixir saga library with co-located compensation
- Akka Persistence -- Actor-native event sourcing with journal + snapshots
- OpenTelemetry -- W3C TraceContext standard for distributed tracing
- Chris Richardson, microservices.io -- Saga pattern, transactional outbox
