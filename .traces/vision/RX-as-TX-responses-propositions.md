# :wrench: Reactive TX Responses x PyBend: Technical Propositions

> *How reactive observable patterns can extend PyBend's actor messaging --
> without breaking the model-is-the-app philosophy.*
> *Based on research in `.traces/research/rx-as-tx-responses/` and codebase analysis.*

---

## :dart: The Bridge

PyBend's actor system already embodies a key reactive principle: **message-driven
asynchronous communication**. TX messages flow through Matrix routing, interceptor
pipelines transform them sequentially, and `_publish_lifecycle` broadcasts events
to multiple subscribers. The system is reactive in spirit -- it just lacks the
vocabulary and primitives to express multi-value responses.

The fundamental connection is this: **TX is already half an Observable**. A TX
has a data payload (`onNext`), an error channel (`tx.error()` / `is_error` which
maps to `onError`), and a reply mechanism (`tx.reply()`). What it lacks is
**cardinality awareness** -- the ability for a handler to say "I will send you
multiple replies" and for the adapter to collect them. The `asyncio.Future` in
`NetworkAdapter._pending` resolves exactly once. That is the ceiling.

The propositions below are not about replacing TX with Observables. They are about
**adding a streaming layer at the edges** -- the NetworkAdapter boundary and the
lifecycle pub/sub system -- while preserving TX as the core messaging primitive.
This mirrors exactly what Akka, Erlang/OTP, and Orleans all concluded: keep the
actor core simple, add streams alongside.

---

## :bulb: Propositions

### Proposition 1: Replace `_subscribers` List with AsyncSubject Multicast

> :wrench: **Proposition:** Replace `ActorModel._subscribers: ClassVar[list]`
> with an `AsyncSubject`-based lifecycle event bus that provides proper
> subscription lifecycle, backpressure, and error isolation.

**From the research:** Orleans' `IAsyncObservable<T>` pattern and Akka's
"streams at the boundary, actors in the core" principle both show that lifecycle
event broadcasting is the **highest-value, lowest-risk** place to introduce
reactive patterns. The research doc (`02-our-stack-relevance.md`, Section 2.3)
identifies three specific weaknesses in the current `_subscribers` list: no
backpressure, no unsubscribe, and no error isolation.

**In our system:** `actor_model.py:54` declares `_subscribers: ClassVar[list] = []`.
`_publish_lifecycle` at line 280 iterates this list, wrapping each `send()` in
`asyncio.create_task`. Dead subscribers accumulate silently -- there is no cleanup.
The `app.py:246` wiring (`model_cls._subscribers.append('ws')`) is stringly-typed
and has no disposal mechanism.

**The idea:** Introduce a per-class `AsyncSubject` that replaces the `_subscribers`
list. Subscribers register via an async subscription that returns a disposable
handle. The WebSocket adapter and ActivityPub adapter subscribe to this subject
instead of being added to a flat list.

```
BEFORE:
  ActorModel._subscribers = ['ws', 'ap']     # strings, no lifecycle
  _publish_lifecycle() -> for addr: create_task(send(TX))

AFTER:
  ActorModel._lifecycle$ = AsyncSubject()     # typed, disposable
  _publish_lifecycle() -> _lifecycle$.asend(event_data)
  ws_adapter subscribes -> gets disposal handle
  ap_adapter subscribes -> gets disposal handle
```

The critical constraint: this change must be **invisible to handler_crud**.
CRUD handlers (`actor_model.py:184-275`) continue to call `_publish_lifecycle`
with the same signature. Only the internal broadcast mechanism changes.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- ~6 hours. Modify `actor_model.py` (8 lines), `app.py` (subscription wiring), update 2 adapter LIFECYCLE handlers. |
| Impact | **High** -- Fixes dead subscriber accumulation, adds backpressure, enables per-subscriber error isolation. Foundation for all other reactive features. |
| Risk | **Low** -- Additive change. All 77 `tx.reply()` call sites unchanged. Falls back gracefully if subject has no subscribers. |
| Timeline | **Days** (1-2 days including tests) |

---

### Proposition 2: Add `request_stream()` to NetworkAdapter

> :wrench: **Proposition:** Add an optional `request_stream()` method to
> `NetworkAdapter` that returns an async iterable of response TXs, enabling
> multi-value responses alongside the existing single-shot `request()`.

**From the research:** The deep dive (`01-technical-deep-dive.md`, Pattern B)
describes an Observable Correlation Map where a `ReplaySubject` replaces the
single Future. Vert.x uses a similar "temporary address" pattern for streaming
over its event bus. The key insight: `request()` continues to work for CRUD;
`request_stream()` is additive.

**In our system:** `network_adapter.py:55` stores `_pending: dict` mapping
`tx.uuid -> Future`. The `inbox()` override at line 57 resolves Futures by
matching `meta['in_reply_to']`. This pattern is clean but fundamentally 1:1.

**The idea:** Add a parallel `_streams: dict` mapping `tx.uuid -> AsyncSubject`.
When a reply TX arrives with a matching `in_reply_to`, check `_streams` after
`_pending`. If found, push to the subject. A `meta['complete']` flag signals
stream end. The existing `request()` is unchanged -- it can even be reimplemented
as `request_stream().take(1)` internally.

```python
# network_adapter.py -- additive
async def request_stream(self, tx: TX, timeout: float = 30.0):
    """Return an async iterator of response TXs."""
    subject = AsyncSubject()
    self._streams[tx.uuid] = subject
    await self.send(tx)
    return subject  # caller iterates: async for response in stream: ...
```

The `inbox()` override gains a second check after the existing Future resolution:

```
inbox(tx):
  if in_reply_to in _pending:  -> resolve Future (existing)
  if in_reply_to in _streams:  -> push to subject (new)
  else: super().inbox(tx)      -> normal dispatch (existing)
```

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low-Medium** -- ~15 hours. Add `_streams` dict, extend `inbox()`, add `request_stream()` method, write SSE adapter proof-of-concept. |
| Impact | **Medium** -- Enables agent progress reporting, SSE streaming, future scatter-gather. No value until consumers exist. |
| Risk | **Low** -- Completely additive. Zero changes to existing `request()` callers. New `_streams` dict is empty by default. |
| Timeline | **Weeks** (1 week including first consumer) |

---

### Proposition 3: Agent Progress Streaming via `request_stream()`

> :wrench: **Proposition:** Make `AgentActor.run()` emit progress events
> (tool discovery, each LLM iteration, tool execution) as a stream of TX
> replies, so the frontend can display real-time agent activity.

**From the research:** The relevance doc (`02-our-stack-relevance.md`, Section 3.2)
identifies agent workflow orchestration as a concrete multi-response use case:
"A single request could return an observable that emits progress events."

**In our system:** `agents/mixin.py:39` implements `agent_run()` which creates a
transient `NetworkAdapter` (line 88-95), discovers tools, and runs the Pydantic AI
loop. Currently this returns a single dict after the entire run completes. There
is no way for the frontend to know what step the agent is on.

**The idea:** Instead of returning a single result, `agent_run()` emits progress
TXs through its transient adapter at each stage:

```
Frontend                       Agent System
   |                               |
   |-- POST /agents/1/run ------->|
   |<-- {step: 'discovering'} ----|  (progress)
   |<-- {step: 'running', i: 1} -|  (LLM iteration 1)
   |<-- {step: 'tool_call', ...} |  (tool execution)
   |<-- {step: 'running', i: 2} -|  (LLM iteration 2)
   |<-- {result: {...}}          -|  (final, meta.complete=true)
```

This requires Proposition 2 (`request_stream()`) as a prerequisite. The HTTP
layer would use Server-Sent Events (SSE) to stream progress to the frontend.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- ~20 hours. Modify `agent_run()` to emit progress TXs, add SSE endpoint in `network_api.py`, frontend SSE consumer. |
| Impact | **High** -- Dramatically improves UX for long-running agent tasks. Agent runs currently feel like black boxes. |
| Risk | **Medium** -- Requires Proposition 2. SSE adds a new HTTP pattern. Frontend needs EventSource handling. |
| Timeline | **Weeks** (2-3 weeks) |

---

### Proposition 4: ResponseHandle Wrapper for Declarative Resilience

> :wrench: **Proposition:** Wrap `NetworkAdapter.request()` return value in a
> `ResponseHandle` that supports `.retry()`, `.timeout()`, and `.fallback()`
> without introducing a full Rx dependency.

**From the research:** The deep dive (`01-technical-deep-dive.md`, Phase 1 of the
migration strategy) recommends a thin abstraction that wraps Future with composable
resilience operators. The error handling comparison table shows that `TX.error()`
has no built-in retry, exponential backoff, or fallback.

**In our system:** Every `NetworkAPI` route handler calls `await api_adapter.request(tx, timeout=30.0)` followed by `_response_or_raise(response)`. There are ~12 such
call sites in `network_api.py` alone. Retry logic would need to be duplicated at
each call site.

**The idea:** A `ResponseHandle` class wraps the Future and provides chainable
methods. This is not Rx -- it is a focused fluent API over `asyncio.Future`:

```python
# Instead of:
response = await api_adapter.request(tx, timeout=30.0)

# Optionally:
response = await (
    api_adapter.request(tx)
    .timeout(5.0)
    .retry(3, backoff=2.0)
    .fallback(tx.error("Service unavailable", code=503))
)
```

Internally, `ResponseHandle` is ~50 lines. It stores the TX and adapter reference,
implements retry as "re-send TX with new uuid", and fallback as "return this TX
on total failure." No external dependency. Compatible with existing `.request()`
by making the handle awaitable (implements `__await__`).

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- ~8 hours. ~50 lines of implementation + tests. |
| Impact | **Medium** -- Enables declarative resilience at every adapter call site. Particularly valuable for agent tool calls that hit external services. |
| Risk | **Low** -- Fully backward compatible. `await request(tx)` still works. `ResponseHandle.__await__` delegates to the inner Future. |
| Timeline | **Days** (2-3 days) |

---

### Proposition 5: SSE Adapter for Real-Time List Subscriptions

> :wrench: **Proposition:** Add a `GET /{tablename}/stream` SSE endpoint that
> combines initial READ response with subsequent lifecycle events into one stream.

**From the research:** The relevance doc (`02-our-stack-relevance.md`, Section 3.1)
describes the polling gap: `<ntt-list>` fetches via HTTP while WS pushes lifecycle
events separately. An SSE stream unifies both channels.

**In our system:** `network_ws.py:200-235` broadcasts lifecycle events to WS
clients. Frontend `ntt-list.js` fetches list data via HTTP. Two disconnected
channels for one concern: "give me this collection and keep it updated."

**The idea:** `GET /products/stream` returns SSE. First event is the full list
snapshot. Subsequent events are lifecycle pushes (create/update/delete) via the
model's `_lifecycle$` subject (Proposition 1). Mutations still use POST/PUT/DELETE.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- ~20 hours. SSE endpoint factory + frontend `EventSource` in `ntt-list.js`. |
| Impact | **High** -- Eliminates polling. Real-time UI without WebSocket complexity. |
| Risk | **Medium** -- SSE has browser connection limits (6/domain in HTTP/1.1). Requires P1. |
| Timeline | **Weeks** (2 weeks) |

---

### Proposition 6: Per-Session Gather Actor for Scatter-Gather

> :wrench: **Proposition:** Implement Akka's "per-session child actor" pattern
> for scatter-gather -- no Rx library needed, just existing actor primitives.

**From the research:** The deep dive (`01-technical-deep-dive.md`, Pattern D)
describes spawning a temporary actor that fans out requests, collects N responses,
aggregates, replies, and self-destructs.

**In our system:** `Actor.spawn()` (`actor.py:425`) supports dynamic children.
`agent_run()` (`agents/mixin.py:84-95`) already creates and cleans up transient
adapters. The pattern exists but is not generalized.

**The idea:** A `GatherActor(Actor, auto_register=False)` that takes a list of
targets, fans out the original TX to each, collects responses until `_expected`
count is met, merges via a provided function, replies to the original requester,
and pops itself from `_parent._children`. Useful for cross-model search, agent
tool discovery, and any "ask N actors the same question" pattern.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- ~10 hours. ~40 lines of implementation + timeout + tests. |
| Impact | **Medium** -- Scatter-gather without Rx. Useful for search, cross-model aggregation. |
| Risk | **Low** -- Uses only existing primitives. Self-destructing children proven in `agent_run()`. |
| Timeline | **Days** (2-3 days) |

---

### Proposition 7: Reactive Mailbox for Event-Driven Agents

> :wrench: **Proposition:** Add a `watches` field to `AgentActor` that subscribes
> to lifecycle subjects across the system, enabling autonomous event-driven agents.

**From the research:** The deep dive (`01-technical-deep-dive.md`, Pattern C)
describes the "Reactive Mailbox" with `inbox$` as a Subject. The research warns
this is "powerful but introduces significant complexity."

**In our system:** `AgentActor` (`agents/actor.py`) instances execute only when
`run()` is called. An agent that should "watch for new sources and scan them for
grants" has no way to subscribe to lifecycle events.

**The idea:** Agents gain a `watches: list[str]` field (DB-storable). On
registration, the system subscribes the agent to each watched model's
`_lifecycle$` subject. When a lifecycle event fires, the agent auto-triggers
`agent_run()`. This turns agents from **pull-based** to **push-based**. Requires
Proposition 1 and careful safety bounds (rate limits, depth limits, loop detection).

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **High** -- ~40 hours. Subscription management, auto-trigger, guard rails, tests. |
| Impact | **High** -- Agents become autonomous actors. Event-driven workflows without cron. |
| Risk | **High** -- Feedback loops (agent creates entity, triggers another agent). Needs safety bounds. |
| Timeline | **Months** (3-4 weeks) |

---

### Proposition 8: TX Cardinality Type Hints

> :wrench: **Proposition:** Add return type annotations (`Single`, `Stream`) to
> `@expose_route` so adapters choose the right correlation mechanism automatically.

**From the research:** RxJava's type hierarchy makes response cardinality explicit.
The deep dive notes "Future conflates Single, Maybe, and Completable into one type."

**In our system:** Every `@expose_route` returns `str`. The adapter cannot know
whether a handler produces one or many responses, forcing `request()` for all.

**The idea:** `@expose_route('/run') -> Stream[dict]` tells the adapter to use
`request_stream()`. `-> Single[str]` (or untyped) uses `request()`. The
annotations also flow into the JSON Schema `methods` section so the frontend
knows whether to expect SSE or a single response.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- ~15 hours. Type aliases, `expose_route` capture, adapter selection, schema update. |
| Impact | **Medium** -- Streaming becomes opt-in and discoverable via schema. |
| Risk | **Low** -- Optional. Untyped defaults to `Single` (current behavior). |
| Timeline | **Weeks** (1-2 weeks) |

---

## :building_construction: Proposition Map

```
                        IMPACT
              Low         Medium         High
         +------------+------------+------------+
  Low    |            | P4: Handle | P1: Lifecy |
         |            | P6: Gather |    Subjects|
  EFFORT +------------+------------+------------+
  Medium |            | P8: Types  | P5: SSE    |
         |            | P2: Stream | P3: Agent  |
         +------------+------------+   Progress |
  High   |            |            | P7: React  |
         |            |            |   Mailbox  |
         +------------+------------+------------+

  Quick Wins:        P1 (Lifecycle Subjects), P4 (ResponseHandle), P6 (Gather)
  Strategic:         P2 (request_stream), P3 (Agent Progress), P5 (SSE)
  Moonshots:         P7 (Reactive Mailbox), P8 (TX Cardinality Types)
```

---

## :warning: What NOT to Do

**1. Do not convert interceptors to Rx operators.**
The interceptor chain (`actor.py:288-299`) is 11 lines of sequential `async (TX) -> TX` functions. It looks like an Rx pipeline but is fundamentally simpler -- it handles 1-3 functions for the auth hot path. Converting to Rx adds operator allocation on every message, obscures stack traces for the most security-critical code, and provides composition features the current codebase does not need. The Zalando engineering team found the same: "plain futures showed minimal runtime performance differences but streams imposed overhead in getting up and running."

**2. Do not make the actor inbox itself an Observable.**
Pattern C from the research (Reactive Mailbox) is architecturally elegant but operationally dangerous for a framework that values "transparent, not magical." The current `inbox() -> handler()` dispatch is traceable in under 30 seconds. A subscription-chain-based inbox distributes behavior across multiple subscription sites, making debugging require understanding the full subscription graph. The one exception is Proposition 7 (agent watches), which is scoped narrowly to agent actors only.

**3. Do not adopt RxPY over aioreactive.**
RxPY requires scheduler bridging with asyncio, which is the source of many subtle bugs in async Python. PyBend is entirely asyncio-native. aioreactive was built for this exact environment -- its `async`/`await` semantics and implicit backpressure align with the single-event-loop model. The smaller operator set (~40 vs 120+) is sufficient for the use cases identified here.

---

## :dart: Recommended Starting Point

**Start with Proposition 1 (Lifecycle Subjects) + Proposition 4 (ResponseHandle).**

These two changes are independent, low-risk, and create the foundation for everything else:

- **P1** replaces a known-fragile pattern (`_subscribers` list with no cleanup) with a proper pub/sub primitive. Every subsequent proposition that involves event broadcasting (P3, P5, P7) builds on this.

- **P4** gives every adapter call site declarative resilience without changing the calling pattern. It is particularly valuable for the agent system where tool calls hit actors that may be slow or temporarily unavailable.

**Validation approach:**

1. Implement P1 in a branch. Verify that WebSocket lifecycle broadcasts work identically. Measure: do dead subscribers get cleaned up? Can we filter lifecycle events per subscriber?

2. Implement P4 in the same or parallel branch. Add retry to one agent tool call in `agents/mixin.py`. Verify that `await request(tx)` still works without `.retry()`.

3. If both validate, merge and proceed to P2 (request_stream) as the next step toward agent progress streaming (P3).
