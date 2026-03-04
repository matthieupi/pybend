# TX Sagas x PyBend: Technical Propositions

> *How transaction composition, causal tracing, and saga patterns can
> extend PyBend's actor system -- without breaking anything it already does well.*
> *Based on research in `.traces/research/tx-sagas/` and codebase analysis of
> `actors/tx.py`, `actors/actor.py`, `actors/matrix.py`, `models/actor_model.py`,
> and `api/network_adapter.py`.*

---

## The Bridge

PyBend's actor system and the saga pattern share a deep structural
affinity. Both are built on **asynchronous message passing** with
**fire-and-forget delivery** -- the exact model where sagas, rather
than two-phase commit, are the theoretically correct composition
strategy. This is a consequence of the actor model's foundations in
the asynchronous pi-calculus, not a surface-level analogy.

PyBend already has **seven of fourteen saga building blocks** in
production code. `TX.reply()` / `TX.error()` implement the two-track
railway. `NetworkAdapter.request()` implements correlated
request-response -- the same mechanism Temporal uses for activity
invocation. `Actor.use()` interceptors provide cross-cutting concern
injection. `_publish_lifecycle()` provides event choreography.

The missing pieces are **composition of existing primitives**: a way
to chain TXs into named workflows, trace causal lineage, and record
history. The bridge is narrow -- and sized accordingly.

---

## Propositions

### Proposition 1: Add Causal Tracing Fields to TX

> **Proposition:** Add `correlation_id` and `causation_id` as first-class
> fields on TX, with propagation in `reply()`, `error()`, and new `spawn()`.

**From the research:** Greg Young's three-ID formulation is the industry
standard (Rails Event Store, Confluent, OpenTelemetry). Correlation +
causation reconstruct the **full causal DAG** of any distributed
operation. Uber, Netflix, and Stripe treat these as table-stakes.

**In our system:** `TX` at `actors/tx.py` carries `uuid` and
`meta['in_reply_to']` (one-hop only). When actor A triggers B triggers
C, there is no link from C back to A.

**The idea:** Two new fields with empty-string defaults (zero breaking
changes). A `spawn()` method for creating child TXs in the same chain:

```python
@dataclass
class TX:
    # ... existing fields ...
    correlation_id: str = ''   # Root operation's uuid
    causation_id: str = ''     # Direct parent TX's uuid

    def spawn(self, name: str, target: str, data=None) -> 'TX':
        """Create a new TX in the same causal chain."""
        return TX(name=name, source=self.target, target=target,
                  data=data or {},
                  correlation_id=self.correlation_id or self.uuid,
                  causation_id=self.uuid)
```

| Dimension | Assessment |
|-----------|-----------|
| Effort    | **Low** -- ~20 lines changed in `tx.py` |
| Impact    | **High** -- unlocks all downstream tracing, debugging, journaling |
| Risk      | **Very Low** -- backward compatible |
| Timeline  | **Hours** |

---

### Proposition 2: TX Journal via Interceptor

> **Proposition:** Build an append-only TX log as an interceptor that
> plugs into `Matrix.use()`, recording every message with zero changes
> to existing code.

**From the research:** Akka Persistence, EventStoreDB, and Temporal all
treat the event journal as foundational infrastructure. An append-only
log gives audit trail, replay foundation, and debugging power.

**In our system:** `Actor.use()` (lines 247-299 in `actor.py`)
supports registering `async (TX) -> TX` functions. The auth interceptor
at `auth_interceptor.py` proves this works in production.

**The idea:** A `TXJournal` class (~80 lines, new file `actors/journal.py`):

```python
class TXJournal:
    def __init__(self):
        self._log = []

    def append(self, tx: TX, direction: str):
        self._log.append({
            'uuid': tx.uuid, 'name': tx.name,
            'correlation_id': tx.correlation_id,
            'causation_id': tx.causation_id,
            'timestamp': tx.timestamp, 'is_error': tx.is_error,
        })

    def by_correlation(self, cid: str) -> list:
        return [e for e in self._log if e['correlation_id'] == cid]

    def interceptor(self, direction='inbox'):
        async def _log(tx: TX) -> TX:
            self.append(tx, direction)
            return tx  # Pass-through
        return _log
```

Opt-in wiring: `matrix.use(journal.interceptor('inbox'), on='inbox')`.

| Dimension | Assessment |
|-----------|-----------|
| Effort    | **Low** -- ~80 lines new file, ~5 lines wiring |
| Impact    | **High** -- audit trail, correlation queries, debugging |
| Risk      | **Very Low** -- opt-in, pass-through, no behavior change |
| Timeline  | **Days** |

---

### Proposition 3: Saga Builder with Co-Located Compensation

> **Proposition:** Create a `Saga` class that chains TX steps with
> adjacent compensation, using `NetworkAdapter.request()` for execution
> and automatic reverse-order rollback on failure.

**From the research:** Elixir's Sage library scored highest on the
composition matrix. Its key insight: compensation declared **adjacent**
to the transaction eliminates the "forgot to compensate" bug class.

**In our system:** `NetworkAdapter.request()` (lines 71-106 in
`network_adapter.py`) already implements correlated request-response
with timeout -- each saga step is a `request()` call.

**The idea:** A ~100-line `actors/saga.py` with fluent builder API:

```python
result = await (
    Saga("purchase")
    .step("create_order",
          TX(name='create', target='orders', data={...}),
          compensate=TX(name='delete', target='orders', data={...}))
    .step("reserve_stock",
          TX(name='update', target='products', data={...}),
          compensate=TX(name='update', target='products', data={...}))
    .step("charge_payment",
          TX(name='charge', target='payments', data={...}),
          compensate=TX(name='refund', target='payments', data={...}))
    .execute(adapter)
)
```

On failure at any step, completed steps compensate in reverse order.
The journal (P2) captures every step including compensations.

| Dimension | Assessment |
|-----------|-----------|
| Effort    | **Medium** -- ~100 lines, no changes to existing code |
| Impact    | **High** -- eliminates manual compensation bugs |
| Risk      | **Low** -- uses existing `request()`, additive-only |
| Timeline  | **Weeks** |

---

### Proposition 4: Decorator-Based Saga Definition

> **Proposition:** Create `@saga`, `@step`, and `@compensates` decorators
> mirroring `@expose_route`, allowing sagas as classes with testable methods.

**From the research:** Code-first decorator approaches (Prefect,
Temporal, Cloudflare) achieve fastest adoption. Prefect's learning
curve: "basically zero for Python developers."

**In our system:** `@expose_route` at `utils/decorators.py` sets
`__endpoint__` metadata. The same pattern works: `@step` sets
`__saga_step__`, `@saga` collects them.

**The idea:**

```python
@saga("order_fulfillment")
class OrderFulfillment:
    @step("reserve", order=2)
    async def reserve(self, ctx: SagaContext) -> dict:
        Product.update(ctx.data["product_id"], {"stock": ...})
        return {"reserved": ctx.data["qty"]}

    @compensates("reserve")
    async def unreserve(self, ctx: SagaContext, effect: dict):
        Product.update(ctx.data["product_id"], {"stock": ...})
```

Steps are independently testable: `await saga.reserve(mock_ctx)`.

| Dimension | Assessment |
|-----------|-----------|
| Effort    | **Medium** -- ~200 lines (decorators + runner + context) |
| Impact    | **High** -- developer-friendly, testable |
| Risk      | **Low** -- additive |
| Timeline  | **Weeks** |

---

### Proposition 5: Schema-Derivable Saga Definitions

> **Proposition:** Make saga definitions inspectable as JSON Schema for
> frontend step progress rendering and API workflow discovery.

**From the research:** Saga-as-data scored 5/5 on debuggability and
introspectability. Aligns with "model is the app" philosophy.

**In our system:** The schema pipeline at `proto_schema.py` transforms
models into JSON Schema through composable stages. A `saga` stage
would expose step structure at runtime.

**The idea:** `GET /OrderFulfillment/saga` returns step graph,
compensation relationships, timeout policies. Frontend renders
step-progress for long workflows.

| Dimension | Assessment |
|-----------|-----------|
| Effort    | **Medium-High** -- schema extension + endpoint + frontend |
| Impact    | **Medium** -- workflow visibility, philosophy alignment |
| Risk      | **Medium** -- design decisions about saga-schema contract |
| Timeline  | **Months** |

---

### Proposition 6: Persistent TX Journal with SQLite

> **Proposition:** Persist the TX journal to SQLite with indexed
> correlation/causation columns for production audit trails.

**From the research:** EventStoreDB achieves 15K+ writes/second
append-only. Our SQLite layer already handles all storage.

**The idea:** An `tx_journal` table with indexed `correlation_id`,
`causation_id`, `timestamp`. Retention policies prevent unbounded
growth. Configurable: `create_app(journal='sqlite')` vs `'memory'`.

| Dimension | Assessment |
|-----------|-----------|
| Effort    | **Medium** -- SQLite table + migration + retention |
| Impact    | **High** -- production debugging, compliance |
| Risk      | **Low-Medium** -- ~0.1ms write overhead per TX |
| Timeline  | **Weeks** |

---

### Proposition 7: CRUD Auto-Compensation Registry

> **Proposition:** Auto-register compensation TXs for CRUD operations
> so sagas get rollback semantics without explicit compensation TXs.

**From the research:** CRUD has natural compensation pairs:
create/delete, update/restore-previous, delete/recreate-snapshot.

**In our system:** `ActorModel.handler_crud()` knows each operation's
shape. A `__compensations__` ClassVar could map actions to auto-generated
compensation TXs that the saga runner uses when no explicit
`compensate=` is provided.

| Dimension | Assessment |
|-----------|-----------|
| Effort    | **Medium** -- snapshot capture + compensation registry |
| Impact    | **Medium** -- reduces CRUD saga boilerplate |
| Risk      | **Medium** -- snapshot accuracy needs careful design |
| Timeline  | **Weeks** |

---

### Proposition 8: TX Idempotency Guard

> **Proposition:** Add an idempotency interceptor using `tx.uuid` as
> dedup key, preventing duplicate effects during retries.

**From the research:** Every saga library pushes idempotency onto
developers. An interceptor-based guard shifts this to a cross-cutting
concern.

**In our system:** `tx.uuid` is already unique. An interceptor on
`Matrix.inbox()` checks a seen-set before dispatching:

```python
class IdempotencyGuard:
    def __init__(self, ttl=300):
        self._seen = {}
    def interceptor(self):
        async def _dedup(tx: TX) -> TX:
            if tx.uuid in self._seen:
                return tx.error("Duplicate TX", code=409)
            self._seen[tx.uuid] = tx.timestamp
            return tx
        return _dedup
```

| Dimension | Assessment |
|-----------|-----------|
| Effort    | **Low** -- ~30 lines + TTL cleanup |
| Impact    | **Medium** -- prevents duplicates in retry scenarios |
| Risk      | **Low** -- opt-in, no change for unique TXs |
| Timeline  | **Days** |

---

## Proposition Map

```
                        HIGH IMPACT
                            |
     [P1 Causal Tracing]    |    [P3 Saga Builder]
          *                 |         *
     [P2 TX Journal]        |    [P4 Decorator Sagas]
          *                 |         *
     [P8 Idempotency]      |    [P6 Persistent Journal]
          *                 |         *
  ─────────────────────────+──────────────────────────
     LOW EFFORT             |              HIGH EFFORT
                            |    [P7 Auto-Compensation]
                            |         *
                            |    [P5 Schema Sagas]
                            |         *
                        LOW IMPACT
```

| Category | Propositions |
|----------|-------------|
| **Quick Wins** (days) | P1 Causal Tracing, P2 TX Journal, P8 Idempotency |
| **Strategic Investments** (weeks) | P3 Saga Builder, P4 Decorator Sagas, P6 Persistent Journal, P7 Auto-Compensation |
| **Moonshots** (months) | P5 Schema-Derivable Sagas |

---

## What NOT to Do

**1. Do not implement two-phase commit (2PC).** The research is
unambiguous: 2PC creates coordinator bottlenecks, has 2-10x latency
overhead, and is fundamentally incompatible with async actor messaging.

**2. Do not pursue deterministic replay initially.** Temporal's replay
requires separating pure workflow logic from side effects -- a
fundamental change. Our handlers freely mix logic and effects. The
journal gives audit value without replay's complexity.

**3. Do not store full TX payloads in the journal by default.** TX data
carries user information and secrets. Store metadata only (uuid, name,
correlation, causation, timestamp, is_error). Add opt-in payload
logging per actor.

---

## Recommended Starting Point

**Start with P1 (Causal Tracing) and P2 (TX Journal).** Together they
deliver **80% of the observability value for ~10% of the total effort**.
P1 is ~20 lines in one file. P2 is ~80 lines in a new file. Neither
touches existing production paths.

**Validation approach:**
1. Implement P1 -- run existing tests to confirm zero regressions
2. Implement P2 -- wire to Matrix in a test
3. Trace a multi-step operation through `by_correlation()` query
4. If the causal chain reconstructs cleanly, proceed to P3
5. P3 validates saga demand before investing in P4-P7

This follows PyBend's philosophy: **zero to working, then customize**.
