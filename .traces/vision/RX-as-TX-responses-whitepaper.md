# :page_facing_up: Reactive TX Responses Applied: A Technical Whitepaper

> *How principles from reactive extensions can reshape N3TX's actor messaging --
> and where they cannot.*
> *Companion to the [propositions document](RX-as-TX-responses-propositions.md).*

---

## Abstract

N3TX's actor system routes every external request through a TX message envelope
and resolves responses via `asyncio.Future` correlation -- a pattern that works
cleanly for single-response CRUD operations. But three emerging capabilities
expose its ceiling: **agent progress reporting** (multi-step LLM workflows that
take seconds and produce no intermediate visibility), **real-time list updates**
(polling is the only path from initial load to live data), and **lifecycle event
management** (the `_subscribers` list has no backpressure, no unsubscribe, and
no error isolation). Reactive extensions address all three gaps through
Observable streams that support zero-to-many emissions with typed completion and
error signals. This whitepaper argues that N3TX should adopt reactive patterns
**at the adapter boundary only** -- specifically `aioreactive` AsyncSubjects for
lifecycle multicasting and a new `request_stream()` method for multi-value
responses -- while preserving TX as the core messaging primitive. The recommended
path is a three-phase rollout: lifecycle subjects (days), streaming adapter
(weeks), and agent progress streaming (weeks), with a total investment of ~40
engineering hours for the first two phases.

---

## 1. Introduction: Why This Matters Now

N3TX v0.9 has crossed a threshold. The framework is no longer just a CRUD
generator -- it is an **agent platform**. The `AgentActor` class
(`agents/actor.py`) creates LLM-powered agents whose instances are data, not
code. These agents discover tools from the Matrix, execute multi-step reasoning
loops, and return structured results. But the entire execution happens behind a
single `await agent_run()` call that resolves minutes later with no intermediate
signal.

This is the forcing function. When a CRUD operation takes 50ms, a single Future
is elegant. When an agent run takes 30 seconds with 5 tool calls and 3 LLM
iterations, a single Future is a **black box**. The user sees a spinner. The
developer sees a timeout risk. The system has no way to communicate progress.

Simultaneously, the WebSocket lifecycle system (`network_ws.py:200-235`)
broadcasts real-time mutations to all connected clients -- but the subscription
mechanism is a `ClassVar[list]` of string addresses with no lifecycle management.
As the number of adapters grows (WS, AP, future MCP event streams, agent
watchers), this pattern will accumulate dead subscribers and offer no backpressure.

The question is not whether N3TX needs multi-value response patterns. It does.
The question is **how to introduce them** without violating the "transparent, not
magical" principle that makes the framework trustworthy.

---

## 2. Principles Worth Importing

The research identified dozens of reactive patterns across Akka, Orleans,
Vert.x, and Project Reactor. Three principles are directly applicable to N3TX.

### 2.1 Streams at the Boundary, Messages in the Core

Every mature actor framework that added reactive streams made the same
architectural decision: **the actor system's internal messaging stays simple**.
Akka's Ask pattern returns a Future, not a stream. Erlang's `GenServer.call/3`
returns a single value. Orleans grain methods return `Task<T>`. Streams are
introduced as a **separate, complementary subsystem** that bridges actors to
external consumers.

N3TX already partially implements this principle. The `NetworkAdapter` class
(`network_adapter.py`) is the boundary between external protocols and the actor
system. HTTP routes call `request()`, which creates a Future, sends a TX,
and awaits the correlated reply. The actor system (Matrix, Actor, ActorModel)
only speaks TX. This boundary is the right place to introduce Observables --
not inside the actor dispatch chain.

Where we partially implement this: the `_pending` dict in NetworkAdapter is a
clean correlation map. Where we do not: lifecycle events (`_publish_lifecycle`)
bypass the adapter boundary entirely, firing directly from ActorModel to
subscriber addresses via `asyncio.create_task`.

### 2.2 Explicit Response Cardinality

RxJava's type hierarchy -- `Single` (exactly one), `Maybe` (zero or one),
`Completable` (zero, success or error), `Observable` (zero to many) -- makes
the number of expected responses part of the contract. Python's `asyncio.Future`
conflates all of these into one type.

N3TX's `tx.reply()` always produces exactly one response TX. The handler
dispatch in `actor.py:321-358` wraps every handler return into a single reply.
There is no way for a handler to say "I will send three replies" and for the
adapter to collect all three before returning to the HTTP caller.

Where this matters: `AgentActor.run()` returns a single JSON string. If it
could return a `Stream[dict]`, the adapter would know to open an SSE connection
instead of holding a single Future. The cardinality is implicit today (always
one); it should be **declared** so the framework can choose the right transport.

### 2.3 Backpressure as a First-Class Concept

The Reactive Streams specification defines a protocol where the subscriber tells
the publisher how many items it can accept (`Subscription.request(n)`). Without
this, a fast producer overwhelms a slow consumer.

N3TX has two places where backpressure matters. First, the `_pending` dict in
NetworkAdapter is an unbounded buffer of in-flight requests -- each Future
consumes ~200 bytes, but under extreme concurrency there is no mechanism to
reject new requests. Second, `_publish_lifecycle` fires events into
`asyncio.create_task` without checking whether subscribers have processed
previous events. The WebSocket broadcast in `network_ws.py:227-229` sends
sequentially to all clients, but if one client is slow, all subsequent clients
wait.

Where we do not need backpressure: CRUD handlers. A GET request produces one
response. There is nothing to back-pressure. The overhead of reactive
backpressure on single-response flows is pure cost. This is why the
"streams at the boundary" principle matters -- apply backpressure only where
streams exist.

---

## 3. Our Architecture Through This Lens

When we examine N3TX's actor system through the reactive lens, a clear
picture emerges: the **1:1 messaging core is solid**, but the **1:N edges
are hand-rolled and fragile**.

### 3.1 Current Response Flow

```
                    N3TX Response Architecture (Current)

  External Protocol          Adapter Boundary              Actor Core
  ==================    =========================    ====================

  HTTP Client               NetworkAPI                 ActorModel
    |                         |                          |
    |-- POST /products -->    |                          |
    |                    request(tx)                     |
    |                    _pending[uuid] = Future         |
    |                    send(tx) ------>  Matrix -----> handler_crud()
    |                                                    |
    |                                                 tx.reply(data)
    |                                                    |
    |                    inbox(reply_tx)  <--- Matrix <--|
    |                    Future.set_result(reply_tx)     |
    |  <-- JSON response |                              |
    |                    |                              |

  WS Client                 NetworkWS                  ActorModel
    |                         |                          |
    |  (lifecycle push) <---- | <-- LIFECYCLE TX <--  _publish_lifecycle()
    |                    for client:                  for addr in _subscribers:
    |                      ws.send_json(broadcast)     create_task(send(TX))
    |                    dead_clients cleanup              |
```

The top half (HTTP) is clean: one request, one Future, one response, proper
timeout handling. The bottom half (WebSocket lifecycle) is the problem area:
a flat list of string addresses, fire-and-forget sends, manual dead-client
cleanup in the WS adapter.

### 3.2 Annotated Architecture: Reactive Opportunities

```
                    Reactive Overlay (Proposed)

  External Protocol          Adapter Boundary              Actor Core
  ==================    =========================    ====================

  HTTP Client               NetworkAPI                 ActorModel
    |                         |                          |
    |  (CRUD: unchanged)      | request() [Future]       | handler_crud()
    |  <-- single response    |                          | tx.reply()
    |                         |                          |
    |  (SSE stream)           | request_stream() [Subj]  | handler emits N
    |  <-- event: snapshot    |   or subscribe to        |   replies with
    |  <-- event: update      |   lifecycle$ subject     |   meta.complete
    |  <-- event: update      |                          |   on last
    |                         |                          |

  WS Client                 NetworkWS                  ActorModel
    |                         |                          |
    |  (lifecycle push)  <--- | subscribe_async(         | _lifecycle$
    |                         |   _lifecycle$)           |   .asend(event)
    |                         | [disposal handle]        |
    |                         |                          |
  AP Server                 NetworkAP                     |
    |                         |                          |
    |  (federation push) <--- | subscribe_async(         |
    |                         |   _lifecycle$)           |
    |                         | [disposal handle]        |
```

Three changes are visible:

1. **Lifecycle events flow through AsyncSubject** instead of string-addressed
   fire-and-forget sends. Subscribers hold disposal handles.

2. **SSE streaming** uses `request_stream()` which holds an AsyncSubject
   instead of a Future. The handler emits multiple replies.

3. **CRUD is completely unchanged.** `request()` and `tx.reply()` work
   exactly as they do today.

---

## 4. The Synthesis: Where Two Worlds Meet

### 4.1 Integration Point: Lifecycle Multicasting

**Current state.** `ActorModel._publish_lifecycle` (`actor_model.py:280-293`)
iterates `_subscribers` (a `ClassVar[list]` of string addresses) and wraps each
`send()` in `asyncio.create_task`. The `app.py:246-247` wiring appends `'ws'`
to each model's `_subscribers`. The WebSocket adapter's `LIFECYCLE` handler
(`network_ws.py:200-235`) manually iterates `_connections` and cleans up dead
clients.

Problems: (1) No unsubscribe -- if an adapter is removed, its string stays in
the list. (2) No backpressure -- events fire regardless of subscriber capacity.
(3) No error isolation -- if one subscriber's processing throws, the event is
lost for that subscriber with no retry or notification. (4) The WS adapter
reinvents multicast with manual dead-letter cleanup.

**Proposed state.** Each ActorModel subclass gets a `_lifecycle$: ClassVar`
that is an AsyncSubject. `_publish_lifecycle` calls `_lifecycle$.asend(event)`.
Adapters subscribe via `subscribe_async()` and receive a disposal handle.

```python
# actor_model.py -- proposed
class ActorModel(Actor, ProtoModel):
    _lifecycle$: ClassVar = None  # AsyncSubject, initialized per subclass

    @classmethod
    def _init_lifecycle(cls):
        from aioreactive import AsyncSubject
        if cls._lifecycle$ is None:
            cls._lifecycle$ = AsyncSubject()

    @classmethod
    def _publish_lifecycle(cls, event: str, data: dict):
        if cls._lifecycle$ is not None:
            import asyncio
            asyncio.create_task(cls._lifecycle$.asend({
                'event': event, 'entity': data, 'source': cls.__addr__,
            }))
```

**Migration path.** (1) Add `_init_lifecycle()` call to `apply_registration()`
in `registrar.py`. (2) Replace `_subscribers.append('ws')` in `app.py` with
`subscribe_async()` call. (3) Update `NetworkWebSocket.LIFECYCLE` and
`NetworkAP.LIFECYCLE` to be observer callbacks rather than TX handlers.
(4) Remove `_subscribers` ClassVar.

**Expected outcomes.** Dead subscriber accumulation eliminated. Adapter
disconnection triggers disposal. Backpressure implicit via asyncio's await
semantics. Error in one subscriber does not affect others.

### 4.2 Integration Point: Multi-Value Response Correlation

**Current state.** `NetworkAdapter.request()` (`network_adapter.py:71-106`)
creates an `asyncio.Future`, stores it in `_pending[tx.uuid]`, sends the TX,
and awaits the Future. The `inbox()` override resolves the Future when a reply
TX arrives with matching `meta['in_reply_to']`. One request, one Future, one
response.

**Proposed state.** Add `_streams: dict` alongside `_pending`. New
`request_stream()` method creates an AsyncSubject instead of a Future.
The `inbox()` override checks `_streams` after `_pending`.

```python
# network_adapter.py -- proposed (additive)
class NetworkAdapter(Actor, auto_register=False):
    _pending: dict = PrivateAttr(default_factory=dict)
    _streams: dict = PrivateAttr(default_factory=dict)   # NEW

    async def request_stream(self, tx: TX, timeout: float = 30.0):
        """Multi-value response. Returns AsyncSubject."""
        from aioreactive import AsyncSubject
        interceptors = Actor._get_interceptors(self, 'request')
        if interceptors:
            tx = await Actor._run_interceptors(interceptors, tx)
            if tx.is_error:
                raise TXError(tx)
        subject = AsyncSubject()
        self._streams[tx.uuid] = subject
        await self.send(tx)
        return subject

    async def inbox(self, tx: TX) -> None:
        reply_to = tx.meta.get('in_reply_to')
        if reply_to and reply_to in self._pending:
            self._pending.pop(reply_to).set_result(tx)
            return
        if reply_to and reply_to in self._streams:       # NEW
            subject = self._streams[reply_to]
            if tx.meta.get('complete'):
                await subject.aclose()
                self._streams.pop(reply_to, None)
            elif tx.is_error:
                await subject.athrow(Exception(tx.data.get('message', 'Error')))
                self._streams.pop(reply_to, None)
            else:
                await subject.asend(tx)
            return
        await super().inbox(tx)
```

**Migration path.** (1) Add `_streams` and `request_stream()` to
`NetworkAdapter`. (2) Extend `inbox()` with the stream check. (3) Build first
consumer: SSE endpoint in `network_api.py` for agent progress. (4) Modify
`agent_run()` to emit progress TXs via the transient adapter.

**Expected outcomes.** Agent runs become observable. Frontend can show
progress. Future SSE consumers get the same API. Existing `request()` callers
are completely unaffected.

---

## 5. Boundaries: Where This Does Not Apply

### 5.1 CRUD Handler Dispatch

The handler dispatch chain (`actor.py:321-358`, `actor_model.py:59-147`)
returns a single value per call. A `GET /products/1` should return one product,
not a stream. Wrapping CRUD responses in Observables adds ceremony with zero
benefit -- the Akka community confirmed this: "actors are better for managing
concurrent access to shared state, streams are better for processing a feed."

### 5.2 Interceptor Chains

The interceptor pipeline (`actor.py:288-299`) processes 1-3 functions
sequentially on the **security-critical auth hot path**. Converting to Rx
operators would add per-message allocation overhead for operator wrappers,
obscure stack traces (Rx chains are notoriously hard to debug), and provide
composition features that 99% of use cases do not need. If a future interceptor
genuinely needs Rx-style time windowing (e.g., rate limiting), it should use Rx
**internally** as a single interceptor function, not by converting the entire
mechanism.

### 5.3 Matrix Routing

The Matrix (`matrix.py`) routes TXs by address prefix matching. This is a
synchronous dispatch operation. Making it reactive would add latency to every
message in the system for no benefit -- routing is not a stream operation.

### 5.4 Schema Pipeline

The schema pipeline (`proto_schema.py`) runs composable `dict -> dict` stages
at server startup. It is a synchronous transformation chain, not a reactive
stream. The data does not arrive over time -- it is computed once.

### 5.5 The Frontend (Phase 1)

Backend reactive changes should not leak to the frontend in Phase 1. The
WebSocket wire format remains unchanged. SSE is a new endpoint, not a
modification of existing ones. RxJS on the frontend is a separate decision
with its own tradeoffs (bundle size vs. the "vanilla JS" philosophy).

---

## 6. A Path Forward

### Phase 1: Lifecycle Subjects (1-2 days)

**Scope:** Replace `_subscribers` list with `AsyncSubject` on `ActorModel`.

**Changes:**
- `actor_model.py`: Add `_lifecycle$` ClassVar, modify `_publish_lifecycle`
- `app.py`: Replace `_subscribers.append('ws')` with `subscribe_async()`
- `network_ws.py`: Update `LIFECYCLE` handler to be observer callback
- `network_ap.py`: Update `LIFECYCLE` handler to be observer callback
- `pyproject.toml`: Add `aioreactive` dependency

**Success criteria:**
- WebSocket lifecycle broadcasts work identically (same wire format)
- Dead subscriber cleanup is automatic (disposal on adapter disconnect)
- New test: subscribe, disconnect, verify no events leak

**Decision gate:** If lifecycle subjects work cleanly and the aioreactive
dependency is stable, proceed to Phase 2. If the library causes asyncio
integration issues, evaluate vendoring or building a minimal Subject class
(~80 lines) with the same interface.

### Phase 2: Streaming Adapter (1 week)

**Scope:** Add `request_stream()` to `NetworkAdapter`. Build SSE endpoint.

**Changes:**
- `network_adapter.py`: Add `_streams` dict, extend `inbox()`, add
  `request_stream()`
- New `network_sse.py`: SSE endpoint factory (or add SSE routes to
  `network_api.py`)
- `agents/mixin.py`: Emit progress TXs during `agent_run()`

**Success criteria:**
- `request()` callers pass all existing tests (zero regression)
- New test: `request_stream()` collects 3 responses from a handler that
  emits 3 replies
- Agent SSE endpoint streams progress events in real-time

**Decision gate:** If streaming works for agent progress, evaluate expanding
to list-view SSE (Proposition 5 from the propositions document). If the
asyncio Subject management proves error-prone, consider the per-session child
actor pattern (Proposition 6) as a non-Rx alternative.

### Phase 3: Expand and Harden (2-3 weeks)

**Scope:** SSE list subscriptions, ResponseHandle resilience, documentation.

**Changes:**
- SSE endpoint for `GET /{tablename}/stream` (initial snapshot + live updates)
- `ResponseHandle` wrapper for declarative retry/timeout/fallback
- Update `CLAUDE.md` with reactive patterns documentation
- Update frontend docs if SSE consumers are added

**Success criteria:**
- SSE list streams deliver initial data + live updates without polling
- `ResponseHandle.retry(3)` recovers from transient agent tool failures
- All existing tests pass, no performance regression on CRUD benchmarks

**Decision gate:** After Phase 3, the system has a complete reactive edge layer.
Evaluate whether agent "watches" (autonomous event-driven execution) are needed
based on the grants application use cases. If yes, proceed to Proposition 7
from the propositions document with careful safety analysis.

---

## 7. Conclusion

The case for reactive patterns in N3TX is **narrow but compelling**. The core
actor system -- TX messaging, Matrix routing, interceptor chains, CRUD dispatch
-- is well-designed for its purpose and should remain unchanged. The research
across Akka, Erlang, and Orleans confirms that mature actor systems keep their
core simple.

But two specific points in the architecture are operating below their potential.
The lifecycle event system is a hand-rolled pub/sub with known weaknesses (dead
subscribers, no backpressure, no error isolation). The request/response
correlation is limited to single-shot Futures, making multi-value responses
architecturally impossible.

Introducing `aioreactive` AsyncSubjects at these two points -- lifecycle
multicasting and adapter-level streaming -- resolves both weaknesses with
minimal risk. The total investment for Phases 1 and 2 is approximately **40
engineering hours**. The core actor system gains zero new dependencies. Existing
code changes zero lines. The reactive layer is additive, opt-in, and confined
to the adapter boundary.

The strongest near-term payoff is **agent progress visibility**. As N3TX
evolves into an agent platform, the difference between "spinner for 30 seconds"
and "live stream of agent reasoning" is the difference between a tool and an
experience. Reactive TX responses make that experience architecturally native
rather than bolted on.

The recommended action: **implement Phase 1 (lifecycle subjects) this week**.
It is a 6-hour change that fixes a known weakness and validates the aioreactive
dependency. If it works -- and the research strongly suggests it will -- Phase 2
follows naturally, and the agent progress streaming that motivates this entire
investigation becomes achievable.

---

## References

### Research Documents
- `01-technical-deep-dive.md` -- Rx fundamentals, reactive actor frameworks, backpressure, Python Rx landscape
- `02-our-stack-relevance.md` -- N3TX response pattern audit, integration feasibility, implementation roadmap

### Codebase Files
- `src/n3tx/core/actors/tx.py` -- TX message envelope (reply, error, exception, is_error)
- `src/n3tx/core/actors/actor.py` -- Actor base class (inbox, handler, send, interceptors)
- `src/n3tx/core/actors/matrix.py` -- Matrix root actor and message router
- `src/n3tx/core/api/network_adapter.py` -- NetworkAdapter with Future-based request() correlation
- `src/n3tx/core/models/actor_model.py` -- ActorModel bridge class (handler_crud, _publish_lifecycle)
- `src/n3tx/core/api/network_ws.py` -- WebSocket adapter (lifecycle broadcast)
- `src/n3tx/core/api/network_api.py` -- HTTP REST adapter (CRUD routes)
- `src/n3tx/core/api/network_ap.py` -- ActivityPub federation adapter
- `src/n3tx/core/api/auth_interceptor.py` -- Tier 1 auth interceptor
- `src/n3tx/core/app.py` -- Application builder (routing mode, WS wiring)
- `src/n3tx/core/agents/mixin.py` -- AgentMixin with agent_run()
- `src/n3tx/core/agents/actor.py` -- AgentActor data-driven agent model

### External Sources
- [Akka Interaction Patterns](https://doc.akka.io/libraries/akka-core/current/typed/interaction-patterns.html) -- Seven actor response patterns
- [Orleans Streaming APIs](https://learn.microsoft.com/en-us/dotnet/orleans/streaming/streams-programming-apis) -- IAsyncObservable, durable subscriptions
- [aioreactive](https://github.com/dbrattli/aioreactive) -- Async/await reactive tools for Python 3.10+
- [Reactive Streams specification](https://www.reactive-streams.org/) -- Publisher/Subscriber/Subscription protocol
- [Zalando: Comparing Akka Streams, Actors, and Plain Futures](https://engineering.zalando.com/posts/2016/06/comparing-akka-streams-actors-and-plain-futures.html)
- [Colin Breck: Integrating Akka Streams and Akka Actors](https://blog.colinbreck.com/integrating-akka-streams-and-akka-actors-part-i/)
