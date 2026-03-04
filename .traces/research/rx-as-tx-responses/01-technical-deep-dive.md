# Reactive Patterns for Actor Message Response Correlation

**A Technical Deep Dive: Replacing asyncio.Future with Observable Streams in Actor Systems**

*Research Date: 2026-03-04 | Audience: Technical CEOs & Engineering Leadership*

---

## Executive Summary

Your actor system currently uses **asyncio.Future** for request/response correlation -- a pending dictionary keyed by TX uuid, resolved when a reply arrives with a matching `meta['in_reply_to']`. This works perfectly for **one question, one answer**. But the moment you need streaming responses, scatter-gather, saga orchestration, or backpressure-aware flows, Future-based correlation hits a wall: **Futures resolve exactly once**.

Reactive Extensions (Rx) replace that single-shot Future with an **Observable stream** that can emit zero, one, or many values, handle errors at any point in the chain, and compose with operators like `map`, `flatMap`, `merge`, and `zip`. The trade-off is real: **~2-5x per-element overhead** for simple request/response, additional memory from subscription chains, and a steeper learning curve. But for systems that need multi-response patterns, the architectural ceiling is dramatically higher.

> **Key Insight:** The question is not "should we replace Futures with Observables everywhere?" It is "which response patterns does our system need, and does the current correlation mechanism support them?" For single-response CRUD, Futures are simpler and faster. For streaming, fan-out/fan-in, and resilience patterns, Observables unlock capabilities that are architecturally impossible with Futures.

---

## Table of Contents

1. [The Current Baseline: Future-Based Correlation](#-the-current-baseline)
2. [Rx Fundamentals for Messaging](#-rx-fundamentals-for-messaging)
3. [Reactive Actor Frameworks in Production](#-reactive-actor-frameworks-in-production)
4. [Backpressure and Flow Control](#-backpressure-and-flow-control)
5. [Error Propagation in Reactive Chains](#-error-propagation-in-reactive-chains)
6. [Composition and Transformation](#-composition-and-transformation)
7. [Implementation Patterns](#-implementation-patterns)
8. [Performance Characteristics](#-performance-characteristics)
9. [Python-Specific Landscape](#-python-specific-landscape)
10. [Decision Framework](#-decision-framework)
11. [Sources](#-sources)

---

## :mag: The Current Baseline

Before diving into reactive patterns, it is worth being precise about what the current system does. The existing `NetworkAdapter.request()` method in PyBend implements a **Future-based correlation** pattern that bridges synchronous HTTP to fire-and-forget actor messaging.

### How it works today

```
HTTP Request                     Actor System
    |                                |
    v                                |
NetworkAdapter.request(tx)           |
    |                                |
    +-- Create asyncio.Future        |
    +-- Store in _pending[tx.uuid]   |
    +-- await adapter.send(tx) ------+---> Matrix ---> ActorModel
    |                                |         |
    |   (waiting...)                 |         v
    |                                |    handler_crud()
    |                                |         |
    |                                |    tx.reply(data)
    |                                |         |
    +-- inbox() receives reply <-----+----  Matrix routes reply
    |   meta['in_reply_to'] matches  |
    |   _pending[uuid]               |
    v                                |
Future.set_result(response_tx)       |
    |                                |
    v                                |
Return to HTTP handler               |
```

The actual code from `network_adapter.py` (lines 71-106):

```python
async def request(self, tx: TX, timeout: float = 30.0) -> TX:
    # Run 'request' interceptors (e.g., auth, rate limiting)
    interceptors = Actor._get_interceptors(self, 'request')
    if interceptors:
        tx = await Actor._run_interceptors(interceptors, tx)
        if tx.is_error:
            return tx

    loop = asyncio.get_running_loop()
    future = loop.create_future()
    self._pending[tx.uuid] = future
    await self.send(tx)
    try:
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        self._pending.pop(tx.uuid, None)
        return tx.error(f"Request to {tx.target} timed out after {timeout}s", code=504)
```

### What this gives you

| Capability | Status |
|:---|:---|
| Single request, single response | **Works perfectly** |
| Timeout handling | **30s default, configurable** |
| Error propagation | **TX.error() with is_error check** |
| Interceptor chain (auth, rate limiting) | **Runs before send** |
| Multiple responses to one request | **Not possible** -- Future resolves once |
| Streaming/chunked responses | **Not possible** |
| Backpressure signaling | **No concept** |
| Scatter-gather (fan-out, merge results) | **Manual wiring required** |
| Retry/circuit-breaker | **Not built in** |
| Response transformation/filtering | **Post-hoc only** |

The **single-shot correlation** is elegant for CRUD. The question is whether the system will need the capabilities in the bottom half of that table.

---

## :mag: Rx Fundamentals for Messaging

**The CEO version:** Think of a Future as a one-time package delivery -- you send a request, you get one box back. An Observable is a **subscription to a delivery service** -- you can get zero boxes, one box, many boxes over time, or a "sorry, we messed up" notice. The subscription can be cancelled, paused (backpressure), and the boxes can be transformed, filtered, or merged with other delivery streams before they reach you.

**The engineer version:** An Observable is a lazy push-based collection that emits items over time. It follows the **Observer pattern** augmented with completion and error signals:

```
Observable<T> emits:
    onNext(T)       -- 0..N data items
    onError(Error)  -- terminal: something went wrong
    onComplete()    -- terminal: no more items

Compare to Future<T>:
    set_result(T)   -- exactly 1 value
    set_exception(E) -- exactly 1 error
```

### Subject Varieties for Message Correlation

The choice of **Subject type** determines how late-arriving subscribers see historical messages. This directly maps to actor messaging scenarios:

| Subject Type | Behavior | Actor Messaging Use Case |
|:---|:---|:---|
| **PublishSubject** | Emits only items after subscription | Real-time event streams; new observers miss past messages |
| **BehaviorSubject** | Emits most recent item + future items | State queries; observer immediately gets current value |
| **ReplaySubject** | Replays N past items + future items | Audit logs; late-joining observers catch up on history |
| **AsyncSubject** | Emits only the **last** item, only on completion | **Request/response** -- semantically equivalent to Future |

([ReactiveX Subject documentation](https://reactivex.io/documentation/subject.html))

> **Key Insight:** An **AsyncSubject** is the reactive equivalent of asyncio.Future -- it emits exactly one value when the source completes. This means you can adopt Observables incrementally: start by replacing `Future` with `AsyncSubject` (identical semantics), then upgrade individual flows to multi-emission patterns where needed.

### Single vs Multi-Response: RxJava's Type Hierarchy

RxJava 2+ introduced **specialized types** that make the cardinality of responses explicit at the type level. This is architecturally instructive even for Python implementations:

| Type | Cardinality | Backpressure | Actor Pattern |
|:---|:---|:---|:---|
| **Single** | Exactly 1 item or error | N/A (single emission) | CRUD response, schema fetch |
| **Maybe** | 0 or 1 item, or error | N/A | Optional lookup (entity may not exist) |
| **Completable** | 0 items, success or error | N/A | Fire-and-forget confirmation (DELETE) |
| **Observable** | 0..N items | No | Bounded response streams, UI events |
| **Flowable** | 0..N items | **Yes** | Unbounded streams with backpressure |

([RxJava data flows](https://bugfender.com/blog/data-flows-in-rxjava2-observable-flowable-single-maybe-completable/))

The critical insight: **Future conflates Single, Maybe, and Completable into one type**. You cannot express "this request might not have a response" (Maybe) or "this request succeeds with no data" (Completable) without bolting on conventions. Rx makes the cardinality **part of the type signature**.

### Cold vs Hot: Actor Inbox Semantics

This distinction matters deeply for actor mailboxes:

- **Cold Observable**: Does not produce values until subscribed. Each subscriber gets its own independent execution. Think: **a database query** -- the query runs when you ask for it, and each caller gets their own result set.

- **Hot Observable**: Produces values regardless of subscribers. Subscribers join the stream mid-flight. Think: **an actor's inbox** -- messages arrive whether or not anyone is listening, and a late subscriber misses past messages.

([Christian Findlay, "Hot vs Cold Observables"](https://www.christianfindlay.com/blog/rx-hot-vs-cold))

An actor's mailbox is inherently a **hot stream**. Messages arrive from the outside world. A request/response correlation, however, is a **cold pattern** -- the observable is created when the request is sent and completes when the reply arrives. This duality is key to the implementation patterns discussed later.

---

## :office: Reactive Actor Frameworks in Production

Four major frameworks have solved the reactive-response-in-actor-systems problem at scale. Their approaches differ significantly.

### Comparison Matrix

| Framework | Language | Model | Response Pattern | Backpressure | Production Scale |
|:---|:---|:---|:---|:---|:---|
| **Akka Typed** | Scala/Java | Actor + Streams | ask() -> Future, StreamRefs | Built-in (Reactive Streams spec) | Tesla, 1.4M TPS at 9ms latency |
| **Orleans** | C# (.NET) | Virtual Actor | IAsyncObservable/IAsyncObserver | Stream provider dependent | Microsoft, Halo, Skype |
| **Vert.x** | JVM polyglot | Event loop | request() -> Future, temp addresses for streams | Manual via read streams | Eclipse Foundation, wide JVM adoption |
| **Project Reactor** | Java | Reactive streams | Mono (0..1) / Flux (0..N) | Reactive Streams spec | Spring WebFlux, 10M+ msg/sec |

([Capital One, "Building Microservices: A Reactive Framework Comparison"](https://medium.com/capital-one-tech/building-microservices-a-reactive-framework-comparison-fb49d8f3c8f4))

### Akka Typed: The Gold Standard

Akka provides **seven distinct interaction patterns**, each designed for a different response topology. This is the most mature model and the closest parallel to PyBend's actor system.

```
Pattern                         Response Type           Use Case
--------------------------------------------------------------------
Fire and forget (tell)          None                    Event notification
Request-Response                ActorRef in message     Direct reply
Adapted Response                messageAdapter()        Protocol translation
Ask between actors              context.ask()           Single response + timeout
Ask from outside                AskPattern -> Future    HTTP bridge (like NetworkAdapter)
Per-session child actor         Temporary actor         Multi-step workflows
Response aggregator             Collect + timeout       Scatter-gather
```

([Akka Interaction Patterns](https://doc.akka.io/libraries/akka-core/current/typed/interaction-patterns.html))

The **Per-session child actor** pattern is particularly relevant. Instead of storing Futures in a `_pending` dict, Akka spawns a **temporary actor** for each complex interaction. This actor:

1. Sends the initial request
2. Collects multiple responses
3. Applies a timeout
4. Aggregates results
5. Sends the final response to the original requester
6. Stops itself

This is architecturally cleaner than a correlation map because each session has its **own state machine** rather than sharing a flat dict.

> **Key Insight:** Akka's approach shows that the choice is not just "Future vs Observable" -- it is "correlation map vs per-session actor vs reactive stream." The per-session actor pattern solves scatter-gather without any reactive library, using the actor model itself. Observable streams solve the same problem with operators instead of actor state machines.

### Orleans: Reactive Streams on Virtual Actors

Orleans takes a different approach. Its streaming API is **explicitly modeled on Rx** with `IAsyncObservable<T>` and `IAsyncObserver<T>`:

```csharp
// Orleans streaming -- Rx-inspired API
public interface IAsyncObserver<in T>
{
    Task OnNextAsync(T item, StreamSequenceToken token = null);
    Task OnCompletedAsync();
    Task OnErrorAsync(Exception ex);
}

public interface IAsyncObservable<T>
{
    Task<StreamSubscriptionHandle<T>> SubscribeAsync(IAsyncObserver<T> observer);
}
```

([Orleans Streaming APIs](https://learn.microsoft.com/en-us/dotnet/orleans/streaming/streams-programming-apis))

Key Orleans innovations:

- **Virtual streams**: A stream "always exists" logically, even with no producers or consumers. Like virtual actors, streams are activated on demand.
- **Durable subscriptions**: Subscriptions survive grain deactivation/reactivation. The subscription is to the **grain identity**, not the current activation.
- **Implicit subscriptions**: Grains can auto-subscribe based on their type and stream namespace, triggering activation when events arrive.
- **Multiple producers, multiple consumers**: Any stream can have N:M relationships.

The **stream sequence token** enables rewindable streams (replay from a checkpoint), which maps to the ReplaySubject pattern in Rx.

### Vert.x: The Pragmatic Middle Ground

Vert.x uses a simpler model. Its event bus supports:

1. **Point-to-point**: `eventBus.send()` -- one consumer receives the message
2. **Request-Reply**: `eventBus.request()` -- returns `Future<Message<T>>`
3. **Publish-Subscribe**: `eventBus.publish()` -- all consumers receive

For **streaming responses**, Vert.x developers use a workaround pattern:

```
1. Requester creates temporary address (UUID)
2. Requester subscribes to temporary address
3. Requester sends request with temp address in headers
4. Data source publishes multiple messages to temp address
5. Data source publishes "END" sentinel message
6. Requester unsubscribes from temporary address
```

([NotesSensei, "Streaming Pattern for Vert.x EventBus"](https://www.wissel.net/blog/2019/12/a-streaming-pattern-for-the-vert.x-eventbus.html))

This is strikingly similar to what you would build on PyBend's current TX system -- a temporary inbox address for multi-response flows. The difference between this ad-hoc approach and a proper reactive implementation is that Rx gives you **operators** (timeout, retry, merge, buffer) for free, while the Vert.x pattern requires manual implementation of each.

---

## :chart_with_upwards_trend: Backpressure and Flow Control

**The CEO version:** Backpressure is what happens when a firehose points at a garden hose. Without it, either the garden hose bursts (out of memory), or water gets lost on the floor (dropped messages). Reactive streams have a built-in "slow down" signal. asyncio.Future has **no concept of backpressure** because there is only one response -- there is nothing to slow down.

**The engineer version:** The [Reactive Streams specification](https://www.reactive-streams.org/) defines a protocol with four interfaces: `Publisher`, `Subscriber`, `Subscription`, and `Processor`. The critical piece is `Subscription.request(long n)` -- the subscriber explicitly tells the publisher how many items it can accept.

```
Publisher                          Subscriber
    |                                  |
    |  <--- subscribe(Subscriber) ---  |
    |  --- onSubscribe(Subscription) -->|
    |                                  |
    |  <--- request(3) --------------- |  "I can handle 3 items"
    |  --- onNext(item1) ------------> |
    |  --- onNext(item2) ------------> |
    |  --- onNext(item3) ------------> |
    |                                  |
    |  <--- request(2) --------------- |  "Ready for 2 more"
    |  --- onNext(item4) ------------> |
    |  --- onNext(item5) ------------> |
    |  --- onComplete() -------------> |
```

([Reactive Streams JVM Specification](https://github.com/reactive-streams/reactive-streams-jvm))

### Why This Matters for Actors

In actor systems, the mailbox is the **unbounded buffer** problem. Akka's documentation is explicit about this:

> "Using `Sink.ActorRef` or the ordinary `Tell` from a `Select` or `ForEach` stage means that there is **no back-pressure signal** from the destination actor; if the actor is not consuming the messages fast enough the mailbox of the actor will grow, unless you use a bounded mailbox with zero `mailbox-push-timeout-time` or use a rate limiting stage in front."

([Akka Streams Integration](https://doc.akka.io/docs/akka/current/stream/stream-integrations.html))

### Backpressure Strategies Compared

| Strategy | Mechanism | When to Use | Risk |
|:---|:---|:---|:---|
| **Unbounded buffer** (current PyBend) | Mailbox grows without limit | Low-traffic systems | OOM under load |
| **Bounded buffer + drop** | Drop oldest/newest when full | Telemetry, metrics | Data loss acceptable |
| **Bounded buffer + error** | Signal error when full | Strict ordering required | Consumer sees errors |
| **Request-based** (Reactive Streams) | Consumer signals demand | Production streaming | Implementation complexity |
| **Rate limiting** | Fixed-rate admission | API gateways | Artificial throughput cap |

For PyBend's current architecture, the `_pending` dict in `NetworkAdapter` acts as an **unbounded buffer** of in-flight requests. Each entry is an asyncio.Future consuming minimal memory (~200 bytes), but under extreme load (thousands of concurrent requests), this could become significant. More critically, there is no mechanism to **reject new requests** when the system is overloaded -- the timeout (30s default) is the only safety valve.

A reactive approach would replace this with a bounded observable that can signal backpressure:

```python
# Conceptual: reactive request with backpressure
class ReactiveAdapter(Actor):
    _max_concurrent = 100  # bounded

    async def request(self, tx: TX) -> AsyncObservable[TX]:
        if len(self._pending) >= self._max_concurrent:
            return rx.throw(BackpressureError("Too many concurrent requests"))
        # ... proceed with request
```

> **Key Insight:** Backpressure matters most when the system scales beyond simple CRUD. If PyBend actors ever serve streaming responses (real-time updates, AI token streaming, large dataset pagination), the absence of backpressure will become the first bottleneck. Adding it retroactively is significantly harder than designing it in.

---

## :warning: Error Propagation in Reactive Chains

### Current Approach: TX.error()

The existing system has a clean error model. `TX.error()` creates an ERROR TX with `meta['error'] = True`, and `is_error` checks propagate through interceptor chains:

```python
# Current: interceptor short-circuits on error
async def _run_interceptors(interceptors, tx):
    for fn in interceptors:
        tx = await fn(tx)
        if tx.is_error:
            return tx  # short-circuit
    return tx
```

This is **linear** -- errors stop the chain, but there is no retry, no fallback, no circuit-breaking.

### Reactive Error Handling: Three Layers Deep

Rx provides error handling at three granularities:

**Layer 1: Catch and Replace**
```python
# RxPY: on error, switch to a fallback observable
source.pipe(
    ops.catch(lambda err, src: rx.of("fallback_value")),
)
```

**Layer 2: Retry with Strategy**
```python
# RxPY: retry up to 3 times with exponential backoff
source.pipe(
    ops.retry(3),
    # Or with delay:
    ops.delay(lambda attempt: 2 ** attempt * 1000),  # ms
)
```

**Layer 3: Circuit Breaker**
```
          [CLOSED] ---failures exceed threshold---> [OPEN]
              ^                                        |
              |                                        v
              +---test succeeds--- [HALF-OPEN] <---timeout expires
```

([Downstream Resiliency Patterns](https://medium.com/@rafaeljcamara/downstream-resiliency-the-timeout-retry-and-circuit-breaker-patterns-d8c02dc72c40))

### Comparison: TX.error() vs Rx Error Handling

| Capability | TX.error() + interceptors | Rx onError/retry/catch |
|:---|:---|:---|
| Error detection | `tx.is_error` property | `onError` callback |
| Chain short-circuit | Interceptor returns error TX | Error propagates downstream |
| Retry | **Manual** -- caller must re-send TX | Built-in `retry(n)` operator |
| Exponential backoff | **Not available** | `retryWhen` with delay function |
| Fallback value | **Not available** | `catch` / `onErrorResumeNext` |
| Timeout | `asyncio.wait_for(future, timeout)` | `timeout` operator, composable |
| Circuit breaker | **Not available** | Custom operator or library (e.g., resilience4j) |
| Error transformation | `TX.from_exception()` maps types | `map` on error channel |
| Partial failure in fan-out | **Must build manually** | `merge` + per-stream `catch` |

The most significant gap is **retry**. In the current system, if a request to an actor fails, the HTTP handler receives an error TX and must decide what to do. There is no mechanism at the messaging layer to retry. With Rx, the retry policy is **declarative and composable**:

```python
# Conceptual: retry with backoff in reactive actor request
async def request_with_resilience(self, tx: TX) -> TX:
    return await (
        self.request_observable(tx)
        .pipe(
            ops.timeout(5.0),                    # 5s per attempt
            ops.retry(3),                        # retry up to 3 times
            ops.catch(lambda e, s: rx.of(        # fallback on total failure
                tx.error(f"All retries failed: {e}", code=503)
            )),
        )
    )
```

> **Key Insight:** The current TX.error() model is clean and sufficient for CRUD. But the moment you need resilience patterns (retry, circuit breaker, fallback), you either build them manually in every call site, or you adopt a composable abstraction like Rx that provides them as reusable operators. The reactive approach is not about replacing TX.error() -- it is about **composing** error handling policies declaratively.

---

## :zap: Composition and Transformation

This is where reactive patterns unlock capabilities that are **architecturally impossible** with single-Future correlation. These patterns come up in any system that grows beyond simple CRUD.

### Pattern 1: Scatter-Gather (Fan-Out / Fan-In)

**Business context:** You need to query multiple actors and merge their results. Example: a product search that queries inventory, pricing, and reviews actors simultaneously.

```
                     +---> [Inventory] ---+
                     |                    |
[SearchRequest] -----+---> [Pricing]   ---+---> [Merge Results] ---> Response
                     |                    |
                     +---> [Reviews]   ---+
```

**With Futures (current approach):** You must manually create 3 Futures, await all of them, handle partial failures, and merge results:

```python
# Manual scatter-gather with Futures
async def search(self, tx: TX) -> TX:
    inventory_tx = TX(name='SEARCH', source='api', target='inventory', data=tx.data)
    pricing_tx = TX(name='SEARCH', source='api', target='pricing', data=tx.data)
    reviews_tx = TX(name='SEARCH', source='api', target='reviews', data=tx.data)

    results = await asyncio.gather(
        self.request(inventory_tx),
        self.request(pricing_tx),
        self.request(reviews_tx),
        return_exceptions=True  # partial failure
    )
    # Manual merge, manual error handling for each...
    return tx.reply(data=merge_results(results))
```

**With Rx operators:**

```python
# Reactive scatter-gather
def search(self, tx: TX) -> Observable[TX]:
    return rx.merge(
        self.request_observable(TX(name='SEARCH', target='inventory', data=tx.data)),
        self.request_observable(TX(name='SEARCH', target='pricing', data=tx.data)),
        self.request_observable(TX(name='SEARCH', target='reviews', data=tx.data)),
    ).pipe(
        ops.timeout(5.0),                          # per-stream timeout
        ops.catch(lambda e, s: rx.empty()),         # drop failed streams
        ops.reduce(lambda acc, r: {**acc, **r}),    # merge results
        ops.map(lambda merged: tx.reply(data=merged)),
    )
```

The Rx version is more **declarative**: the intent (merge three streams, timeout each, drop failures, reduce to one result) reads as a pipeline. The Future version embeds the same logic in imperative code.

### Pattern 2: Saga Orchestration

**Business context:** A multi-step transaction where each step must succeed, and failure triggers compensating actions (rollback).

```
[Create Order] --ok--> [Reserve Inventory] --ok--> [Charge Payment] --ok--> [Confirm]
      |                       |                          |
      v (fail)                v (fail)                   v (fail)
  (nothing)           [Release Inventory]         [Refund Payment]
                                                  [Release Inventory]
```

Sagas can be implemented with **orchestration** (a central coordinator, which is more observable and debuggable) or **choreography** (each service publishes events for the next). Reactive streams naturally support orchestration-based sagas.

([Saga Pattern, microservices.io](https://microservices.io/patterns/data/saga.html))

**With Rx:**

```python
# Conceptual saga with reactive composition
def execute_order_saga(self, order: dict) -> Observable[TX]:
    return self.request_observable(
        TX(name='CREATE', target='orders', data=order)
    ).pipe(
        ops.flat_map(lambda order_tx:
            self.request_observable(
                TX(name='RESERVE', target='inventory', data=order_tx.data)
            ).pipe(
                ops.catch(lambda e, s:
                    self.compensate('orders', 'CANCEL', order_tx.data)  # rollback
                )
            )
        ),
        ops.flat_map(lambda inv_tx:
            self.request_observable(
                TX(name='CHARGE', target='payments', data=inv_tx.data)
            ).pipe(
                ops.catch(lambda e, s: rx.merge(
                    self.compensate('inventory', 'RELEASE', inv_tx.data),
                    self.compensate('orders', 'CANCEL', inv_tx.data),
                ))
            )
        ),
    )
```

### Pattern 3: Streaming Responses

**Business context:** An LLM generates tokens one at a time. A large dataset returns results in pages. A real-time dashboard subscribes to updates.

**With Futures:** Not possible without fundamentally changing the pattern. You would need to switch to WebSocket, SSE, or a polling mechanism.

**With Observables:** The response is inherently a stream:

```python
# AI token streaming as an Observable
def generate_tokens(self, tx: TX) -> Observable[TX]:
    return rx.create(lambda observer, scheduler:
        async def _generate():
            async for token in llm.stream(tx.data['prompt']):
                observer.on_next(tx.reply(data={'token': token}))
            observer.on_completed()
        asyncio.ensure_future(_generate())
    )
```

### Key Operators for Actor Messaging

| Operator | What It Does | Actor Messaging Use Case |
|:---|:---|:---|
| **map** | Transform each item | Convert TX data to domain objects |
| **flatMap** | Transform + flatten nested observables | Chain dependent requests (saga steps) |
| **merge** | Combine multiple streams | Scatter-gather, multi-source aggregation |
| **zip** | Pair items from multiple streams | Join data from two actors (e.g., user + profile) |
| **filter** | Drop items that don't match | Route only relevant responses |
| **reduce** | Accumulate to single value | Aggregate scatter-gather results |
| **timeout** | Error if no emission within duration | Request deadline |
| **retry** | Re-subscribe on error | Transient failure recovery |
| **buffer** | Collect items into batches | Batch processing, rate limiting |
| **debounce** | Emit only after quiet period | Deduplicate rapid-fire events |
| **take(1)** | Complete after first emission | Convert stream to single-response (like Future) |

([ReactiveX Operators](https://reactivex.io/documentation/operators.html))

---

## :mag: Implementation Patterns

### Pattern A: Subject-Per-Request (Direct Future Replacement)

The simplest migration path. Replace each `asyncio.Future` with an `AsyncSubject`:

```python
# Before: Future-based
future = loop.create_future()
self._pending[tx.uuid] = future
await self.send(tx)
return await asyncio.wait_for(future, timeout=timeout)

# After: AsyncSubject-based (semantically identical)
subject = AsyncSubject()
self._pending[tx.uuid] = subject
await self.send(tx)
return await subject.pipe(ops.timeout(timeout)).to_future()
```

**Advantage:** Zero behavior change. AsyncSubject emits only the last value on completion, exactly like Future.

**Unlock:** The subject is now an Observable. Callers can compose operators before awaiting:

```python
# Caller can now add retry, timeout, transformation
result = await adapter.request(tx).pipe(
    ops.timeout(5.0),
    ops.retry(2),
    ops.map(lambda r: r.data),
).to_future()
```

### Pattern B: Observable Correlation Map

For multi-response patterns, replace the `_pending` dict with a **ReplaySubject** that can emit multiple values:

```python
class ReactiveNetworkAdapter(Actor, auto_register=False):
    _streams: dict = {}  # uuid -> Subject

    def request_stream(self, tx: TX, timeout: float = 30.0) -> Observable[TX]:
        """Return an Observable of response TXs (0..N responses)."""
        subject = ReplaySubject(buffer_size=100)
        self._streams[tx.uuid] = subject

        # Auto-cleanup on timeout or completion
        return subject.pipe(
            ops.timeout(timeout),
            ops.finally_action(lambda: self._streams.pop(tx.uuid, None)),
        )

    async def inbox(self, tx: TX):
        reply_to = tx.meta.get('in_reply_to')
        if reply_to and reply_to in self._streams:
            subject = self._streams[reply_to]
            if tx.meta.get('complete'):
                subject.on_completed()
            elif tx.is_error:
                subject.on_error(TXError(tx))
            else:
                subject.on_next(tx)
            return
        await super().inbox(tx)
```

### Pattern C: Reactive Mailbox (Hot Observable Inbox)

The most radical approach: make the actor's **inbox itself** an Observable stream:

```
Traditional Actor:
    inbox(tx) ---> handler(tx) ---> process ---> send(reply)

Reactive Actor:
    inbox$ = Subject()  (hot observable)
        |
        +--- .pipe(filter(is_crud)) ---> crud_handler$
        +--- .pipe(filter(is_lifecycle)) ---> lifecycle_handler$
        +--- .pipe(filter(is_method)) ---> method_handler$
```

This enables **declarative message routing** inside the actor:

```python
class ReactiveActor(Actor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._inbox$ = Subject()

        # Declarative message routing
        self._inbox$.pipe(
            ops.filter(lambda tx: tx.name in ('CREATE', 'READ', 'UPDATE', 'DELETE')),
        ).subscribe(self.handle_crud)

        self._inbox$.pipe(
            ops.filter(lambda tx: tx.name.startswith('LIFECYCLE')),
            ops.buffer_with_time(100),  # batch lifecycle events
        ).subscribe(self.handle_lifecycle_batch)

    async def inbox(self, tx: TX):
        self._inbox$.on_next(tx)
```

> **Warning:** This pattern is powerful but introduces significant complexity. The actor's behavior becomes distributed across subscription chains rather than centralized in a `handler()` method. For most systems, Pattern A (subject-per-request) provides 80% of the benefit with 20% of the complexity.

### Pattern D: Per-Session Child Actor (Akka-Inspired, No Rx Required)

This pattern achieves scatter-gather **without any reactive library** by leveraging the actor model itself:

```python
class GatherActor(Actor, auto_register=False):
    """Temporary actor that collects responses and aggregates them."""

    def __init__(self, expected: int, requester_tx: TX, **kwargs):
        super().__init__(**kwargs)
        self._expected = expected
        self._results = []
        self._requester_tx = requester_tx

    async def handler(self, tx: TX):
        self._results.append(tx)
        if len(self._results) >= self._expected:
            merged = merge_results(self._results)
            await self.send(self._requester_tx.reply(data=merged))
            # Self-destruct
            self._parent._children.pop(self.addr, None)
```

This is what Akka calls the "Per-session child actor" pattern. No reactive library needed -- just actors.

---

## :bar_chart: Performance Characteristics

### Latency Overhead

**The headline:** Reactive frameworks add **measurable but typically insignificant** overhead for I/O-bound workloads. The overhead becomes meaningful only for CPU-bound, tight-loop scenarios.

| Metric | Raw asyncio.Future | RxPY Observable | Overhead |
|:---|:---|:---|:---|
| Single-value resolution | ~0.5-1 microsecond | ~2-5 microseconds | **3-5x** |
| Operator chain (3 operators) | N/A | ~5-15 microseconds | Per-operator allocation |
| Subscription setup | N/A | ~1-3 microseconds | One-time cost |
| Memory per in-flight request | ~200 bytes (Future) | ~500-1500 bytes (Subject + subscription) | **2.5-7.5x** |

For context: a typical HTTP request through FastAPI takes **0.5-5 milliseconds** for routing, serialization, and I/O. The reactive overhead of 5-15 microseconds is **0.1-3%** of the total request time.

([Reactive Programming Performance](https://itembase.com/reactive-programming-a-discussion-on-performance-and-trade-offs/); [Lund University thesis](https://lup.lub.lu.se/luur/download?fileOId=8932147&func=downloadFile&recordOId=8932146))

### Throughput at Scale

Published benchmarks from production systems:

| System | Throughput | Latency | Notes |
|:---|:---|:---|:---|
| Akka Streams | **1.4M TPS** | 9ms | Real-time stream processing |
| Project Reactor | **10M+ msg/sec** | < 50ms | Backpressure-aware |
| Reactive vs blocking HTTP | **175K req/sec** vs 40K req/sec | < 50ms vs unstable | 4-core server |
| Reactive stream propagation | -- | **38ms** vs 145ms (traditional) | Event processing pipeline |

([Akka Streaming blog](https://akka.io/blog/akka-streaming-high-performance-stream-processing-for-real-time-ai); [Reactive Programming Paradigms in High-Throughput Systems](https://eajournals.org/wp-content/uploads/sites/21/2025/05/Reactive-Programming.pdf))

> **Key Insight:** The per-element overhead of Rx (~2-5 microseconds) is noise compared to I/O latency. The **throughput advantage** of reactive patterns comes from better resource utilization: non-blocking backpressure prevents thread pool exhaustion, and composable operators eliminate blocking waits. For a system like PyBend where responses traverse actor mailboxes, network I/O, and database queries, the Rx overhead is invisible.

### Memory and GC Considerations

Reactive operator chains create **intermediate objects** (subscriptions, schedulers, observer wrappers) that add GC pressure:

- Each `pipe()` stage allocates a new Observable wrapper
- Each `subscribe()` allocates a Disposable (for cleanup)
- `ReplaySubject` buffers items in memory (configurable buffer size)
- Long-lived subscriptions that are not properly disposed create **memory leaks**

([RxJS Troubleshooting at Scale](https://www.mindfulchase.com/explore/troubleshooting-tips/frameworks-and-libraries/rxjs-troubleshooting-at-scale-memory-leaks,-stream-conflicts,-and-performance-pitfalls.html); [Memory Model for Reactive Programming](https://jverlaguet.com/reactive%20programming/2024-06-23-memory_model.html))

**Mitigation:** For request-scoped observables (like replacing `_pending` Futures), the lifecycle is short and bounded. Memory leaks are primarily a risk with **long-lived subscriptions** (e.g., a reactive mailbox that never unsubscribes). The Subject-per-request pattern (Pattern A) avoids this entirely because subjects are created and disposed with each request.

---

## :mag: Python-Specific Landscape

### Library Comparison

| Library | PyPI Downloads/month | Python Version | Async Native | Maintenance Status |
|:---|:---|:---|:---|:---|
| **RxPY** (ReactiveX/RxPY) | ~500K | 3.7+ | Via scheduler | Active (4.x) |
| **aioreactive** | ~5K | 3.10+ | **Yes** (async/await) | Active (maintained by RxPY creator) |
| **aiostream** | ~15K | 3.6+ | Yes | Moderate |
| **Python asyncio (built-in)** | N/A | 3.4+ | Yes | Core library |

### RxPY: The Established Choice

RxPY is the official ReactiveX implementation for Python. It follows the standard Rx API:

```python
import reactivex as rx
from reactivex import operators as ops

# Basic observable pipeline
source = rx.of(1, 2, 3, 4, 5)
source.pipe(
    ops.filter(lambda x: x > 2),
    ops.map(lambda x: x * 10),
).subscribe(
    on_next=lambda x: print(f"Next: {x}"),
    on_error=lambda e: print(f"Error: {e}"),
    on_completed=lambda: print("Done"),
)
# Output: Next: 30, Next: 40, Next: 50, Done
```

**AsyncIO integration** requires the `AsyncIOScheduler`:

```python
import asyncio
import reactivex as rx
from reactivex.scheduler.eventloop import AsyncIOScheduler

async def main():
    loop = asyncio.get_running_loop()
    scheduler = AsyncIOScheduler(loop)

    source = rx.interval(1.0, scheduler=scheduler)  # emit every second
    source.pipe(
        ops.take(5),
    ).subscribe(lambda x: print(f"Tick: {x}"))

    await asyncio.sleep(6)

asyncio.run(main())
```

([RxPY Documentation](https://rxpy.readthedocs.io/en/latest/get_started.html); [RxPY AsyncIO cohabitation](https://oakbits.com/rxpy-and-asyncio.html))

**The friction point:** RxPY uses callbacks and schedulers, not native `async`/`await`. This means bridging between RxPY observables and asyncio coroutines requires explicit conversion. It is not seamless.

### aioreactive: The asyncio-Native Alternative

Created by Dag Brattli (who also authored RxPY), aioreactive is designed from the ground up for `async`/`await`:

```python
import aioreactive as rx
from expression.system import AsyncDisposable

async def main():
    # Create an async observable
    xs = rx.from_async_iterable(my_async_generator())

    # Compose with operators (all async-native)
    ys = xs.pipe(
        rx.filter(lambda x: x > 10),
        rx.map(lambda x: x * 2),
        rx.delay(0.1),
    )

    # Subscribe (async)
    async with await ys.subscribe_async(rx.AsyncAnonymousObserver(
        on_next=lambda x: print(f"Got: {x}")
    )) as sub:
        await asyncio.sleep(10)
```

([aioreactive GitHub](https://github.com/dbrattli/aioreactive))

Key differences from RxPY:

- **All operations are async**: `subscribe_async()`, `on_next_async()`, disposal is async
- **Built-in backpressure**: "implicit synchronous back-pressure" -- producers are awaited until consumers are ready
- **No scheduler required**: Runs on the asyncio event loop directly
- Requires **Python 3.10+**
- Built on the **Expression** functional library (F#-inspired)
- Smaller community and ecosystem than RxPY

### Recommendation for PyBend

Given that PyBend:
- Already uses `asyncio` throughout
- Targets Python 3.10+ (based on modern type hints in the codebase)
- Has a small, composable actor system (not a massive enterprise Rx codebase)

The **best fit** is:

| Approach | When to Use |
|:---|:---|
| **Keep asyncio.Future** | CRUD request/response (current pattern works well) |
| **aioreactive** | If adopting full reactive streams for multi-response patterns |
| **RxPY** | If the team already knows RxJS/RxJava (API familiarity) |
| **asyncio.Queue** | Lightweight producer/consumer without full Rx overhead |
| **Per-session child actor** | Scatter-gather without any Rx dependency |

> **Key Insight:** Python's async ecosystem does not have a single dominant reactive library the way JVM has Project Reactor or JavaScript has RxJS. The fragmentation (RxPY vs aioreactive vs aiostream vs raw asyncio) means any adoption carries **ecosystem risk**. The safest path is to introduce reactive patterns **incrementally** and **internally** -- build a thin abstraction over asyncio.Future that can be upgraded to Observables later, rather than committing to a specific Rx library across the entire codebase.

---

## :bulb: Decision Framework

### When to Stay with Futures

- All request/response flows are **single-shot** (one question, one answer)
- The system does not need **streaming responses** (SSE, WebSocket token streams)
- **Retry and circuit-breaking** can be handled at the HTTP layer (e.g., Nginx, API gateway)
- The team does not have **Rx experience** and the learning curve is not justified
- The actor system is primarily a **routing mechanism**, not a complex message-processing pipeline

### When to Adopt Reactive Patterns

- The system needs **streaming responses** (LLM token streaming, real-time dashboards)
- **Scatter-gather** queries across multiple actors are common
- **Saga orchestration** with compensating transactions is needed
- **Backpressure** is required to prevent actor mailbox overflow under load
- The team needs **declarative resilience** (retry, circuit-breaker, timeout composition)
- **Fan-out / fan-in** patterns appear in multiple places

### Migration Strategy: Incremental Adoption

```
Phase 0: No change (current state)
    NetworkAdapter.request() -> asyncio.Future -> single response
    Works for: CRUD, schema fetch, custom methods

Phase 1: Thin abstraction (low risk)
    NetworkAdapter.request() returns a "ResponseHandle" that wraps Future
    ResponseHandle has .to_future(), .pipe(), .timeout(), .retry()
    Internally still uses asyncio.Future
    Works for: Adding resilience to existing patterns

Phase 2: Observable correlation (medium risk)
    New NetworkAdapter.request_stream() returns Observable
    Uses Subject-per-request (Pattern A)
    .request() still works (calls request_stream().take(1).to_future())
    Works for: Streaming responses, scatter-gather

Phase 3: Reactive mailbox (high risk, optional)
    Actor inbox becomes a hot Observable
    Declarative message routing via operators
    Works for: Complex event processing, CQRS/event sourcing
```

### Cost-Benefit Summary

| Factor | Stay with Futures | Adopt Rx (Phase 1-2) | Full Reactive (Phase 3) |
|:---|:---|:---|:---|
| **Implementation effort** | 0 | 2-4 weeks | 2-3 months |
| **Learning curve** | None | Moderate (Rx concepts) | Steep (reactive thinking) |
| **CRUD performance** | Baseline | +5-15 microseconds/request | +10-30 microseconds/request |
| **Streaming capability** | None | Full | Full |
| **Scatter-gather** | Manual asyncio.gather | Declarative merge/zip | Declarative + routing |
| **Resilience (retry, CB)** | Manual per-callsite | Composable operators | Composable operators |
| **Backpressure** | None | Per-stream | System-wide |
| **Debugging complexity** | Low | Medium (async stack traces) | High (subscription chains) |
| **Dependency risk** | None (stdlib) | 1 library (aioreactive or RxPY) | Deep coupling to Rx paradigm |
| **Team hiring** | Standard Python devs | Need some Rx knowledge | Need Rx expertise |

> **Key Insight:** For PyBend's current architecture -- a schema-driven CRUD framework with actor-based routing -- **Phase 0 (no change) is the right choice today**. The Future-based correlation in `NetworkAdapter.request()` is well-implemented and sufficient. The time to invest in reactive patterns is when the product roadmap includes **streaming responses** (AI integration, real-time collaboration, large dataset pagination) or **complex multi-actor orchestration** (agent workflows, saga transactions). At that point, start with **Phase 1** (thin abstraction) and graduate to **Phase 2** (observable correlation) as patterns emerge. Skip Phase 3 unless you are building an event processing platform.

---

## :link: Sources

1. [ReactiveX Observable documentation](https://reactivex.io/documentation/observable.html) -- Core Observable contract and semantics
2. [ReactiveX Subject documentation](https://reactivex.io/documentation/subject.html) -- Four Subject varieties (Publish, Behavior, Replay, Async)
3. [ReactiveX Operators](https://reactivex.io/documentation/operators.html) -- Complete operator reference
4. [Akka Typed Interaction Patterns](https://doc.akka.io/libraries/akka-core/current/typed/interaction-patterns.html) -- Seven actor response patterns including ask, per-session child, response aggregator
5. [Akka Streams: Basics and Working with Flows](https://doc.akka.io/docs/akka/current/stream/stream-flows-and-basics.html) -- Backpressure, materialization, stream integration with actors
6. [Akka Streaming: High-Performance Stream Processing](https://akka.io/blog/akka-streaming-high-performance-stream-processing-for-real-time-ai) -- 1.4M TPS benchmark, real-time AI use case
7. [Akka StreamRefs: Reactive Streams over the Network](https://doc.akka.io/libraries/akka-core/current/stream/stream-refs.html) -- Distributed stream processing between actor systems
8. [Orleans Streaming APIs](https://learn.microsoft.com/en-us/dotnet/orleans/streaming/streams-programming-apis) -- IAsyncObservable, IAsyncObserver, durable subscriptions, virtual streams
9. [Orleans Virtual Actors in Practice](https://developersvoice.com/blog/dotnet/orleans-virtual-actors-in-practice/) -- Virtual actor model with streaming
10. [Vert.x Event Bus Streaming Pattern](https://www.wissel.net/blog/2019/12/a-streaming-pattern-for-the-vert.x-eventbus.html) -- Multi-response via temporary addresses
11. [Vert.x Core Documentation](https://vertx.io/docs/vertx-core/java/) -- Event bus request-reply and publish-subscribe
12. [Capital One: Building Microservices: A Reactive Framework Comparison](https://medium.com/capital-one-tech/building-microservices-a-reactive-framework-comparison-fb49d8f3c8f4) -- Akka vs Vert.x vs Reactor comparison
13. [Reactive Streams JVM Specification](https://github.com/reactive-streams/reactive-streams-jvm) -- Publisher/Subscriber/Subscription protocol, backpressure signaling
14. [Reactive Streams website](https://www.reactive-streams.org/) -- Specification overview and goals
15. [RxPY Documentation](https://rxpy.readthedocs.io/en/latest/get_started.html) -- Python reactive extensions getting started
16. [aioreactive GitHub](https://github.com/dbrattli/aioreactive) -- AsyncIO-native reactive library for Python 3.10+
17. [RxPY AsyncIO Cohabitation](https://oakbits.com/rxpy-and-asyncio.html) -- Bridging RxPY and asyncio
18. [Project Reactor](https://projectreactor.io/) -- Mono/Flux types, 10M+ msg/sec throughput
19. [Reactive Programming: Performance and Trade-Offs](https://itembase.com/reactive-programming-a-discussion-on-performance-and-trade-offs/) -- Latency and throughput measurements
20. [Reactive Programming Paradigms in High-Throughput Systems](https://eajournals.org/wp-content/uploads/sites/21/2025/05/Reactive-Programming.pdf) -- 175K req/sec reactive vs 40K blocking, 38ms vs 145ms propagation latency
21. [RxJS Troubleshooting at Scale](https://www.mindfulchase.com/explore/troubleshooting-tips/frameworks-and-libraries/rxjs-troubleshooting-at-scale-memory-leaks,-stream-conflicts,-and-performance-pitfalls.html) -- Memory leaks, subscription management
22. [Memory Model for Reactive Programming](https://jverlaguet.com/reactive%20programming/2024-06-23-memory_model.html) -- GC pressure from immutable data in Rx chains
23. [Lund University: Reactive Programming Performance Thesis](https://lup.lub.lu.se/luur/download?fileOId=8932147&func=downloadFile&recordOId=8932146) -- Academic performance analysis
24. [RxJava Data Flows: Observable, Flowable, Single, Maybe, Completable](https://bugfender.com/blog/data-flows-in-rxjava2-observable-flowable-single-maybe-completable/) -- Type hierarchy for response cardinality
25. [Christian Findlay: Hot vs Cold Observables](https://www.christianfindlay.com/blog/rx-hot-vs-cold) -- Observable temperature semantics
26. [Vaughn Vernon: Reactive Messaging Patterns with the Actor Model](https://github.com/VaughnVernon/ReactiveMessagingPatterns_ActorModel) -- Scatter-gather, enterprise integration patterns for actors
27. [Saga Pattern (microservices.io)](https://microservices.io/patterns/data/saga.html) -- Saga orchestration vs choreography
28. [The Saga Pattern in a Reactive Microservices Environment](https://www.academia.edu/72653167/The_Saga_Pattern_in_a_Reactive_Microservices_Environment) -- Academic paper on reactive sagas
29. [Downstream Resiliency: Timeout, Retry, and Circuit Breaker Patterns](https://medium.com/@rafaeljcamara/downstream-resiliency-the-timeout-retry-and-circuit-breaker-patterns-d8c02dc72c40) -- Resilience patterns comparison
30. [Akka Streams Integration](https://doc.akka.io/docs/akka/current/stream/stream-integrations.html) -- Actor-stream integration, mailbox backpressure
31. [Scatter-Gather Enterprise Integration Pattern](https://www.enterpriseintegrationpatterns.com/patterns/messaging/BroadcastAggregate.html) -- Canonical pattern definition
32. [ReactiveX Retry Operator](https://reactivex.io/documentation/operators/retry.html) -- Retry semantics in Rx
33. [Backpressure in Reactive Systems (Frankel)](https://blog.frankel.ch/backpressure-reactive-systems/) -- Backpressure fundamentals
