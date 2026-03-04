# Transaction Composition, Causal Tracing & Saga Patterns for Actor Systems

**A Technical Deep Dive for Engineering Leadership**

> This document examines how production systems implement multi-step TX workflows,
> transaction lineage, and replay capabilities -- and what these patterns mean for
> an actor-based messaging framework. Every pattern is grounded in real production
> data from companies operating at scale.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Saga Patterns: Orchestration vs Choreography](#-saga-patterns-orchestration-vs-choreography)
3. [Process Managers & Workflow Engines](#-process-managers--workflow-engines)
4. [Causal Tracing & Correlation](#-causal-tracing--correlation)
5. [Event Replay & Event Sourcing](#-event-replay--event-sourcing)
6. [Compensating Transactions & Failure Handling](#-compensating-transactions--failure-handling)
7. [Distributed Transaction Alternatives](#-distributed-transaction-alternatives)
8. [Theoretical Foundations](#-theoretical-foundations)
9. [Production Systems at Scale](#-production-systems-at-scale)
10. [Mapping to Actor-Based TX Systems](#-mapping-to-actor-based-tx-systems)
11. [Sources](#-sources)

---

## Executive Summary

**The business question:** When your system needs to coordinate work across multiple actors -- create an order, reserve inventory, charge payment, send confirmation -- how do you make that reliable? What happens when step 3 fails after steps 1 and 2 already committed?

**The answer is not a single pattern but a spectrum.** At one end sits the two-phase commit (2PC), offering strong consistency but crippling scalability. At the other end sits pure choreography, maximizing independence but making failures hard to trace. Production systems overwhelmingly land in the middle: **saga-based orchestration with causal tracing and optional event replay**.

The key numbers that should guide the decision:

| Metric | 2PC | Saga (Orchestration) | Saga (Choreography) |
|--------|-----|---------------------|---------------------|
| **Consistency** | Strong (ACID) | Eventual | Eventual |
| **Latency overhead** | 2-10x (lock contention) | ~1x (async) | ~1x (async) |
| **Scalability ceiling** | Low (coordinator bottleneck) | High | Very High |
| **Debuggability** | High (single TX) | High (central log) | Low (scattered) |
| **Failure recovery** | Automatic rollback | Compensating TXs | Compensating TXs |
| **Implementation complexity** | Medium | Medium-High | High (hidden) |

> **Key Insight:** The industry has largely abandoned 2PC for microservice architectures. Uber processes **12 billion workflow executions and 270 billion actions per month** using saga-based orchestration via Cadence/Temporal ([Uber Blog](https://www.uber.com/blog/announcing-cadence/)). Netflix runs **500K+ workflows per day**. The pattern works at scale.

---

## :mag: Saga Patterns: Orchestration vs Choreography

**The "so what?":** A saga is how you do a multi-step transaction without locking everything. Instead of one giant atomic operation, you break it into small steps -- each with its own "undo" button. The two ways to coordinate those steps have dramatically different operational characteristics.

### How Sagas Work

A saga is a sequence of **local transactions** where each step updates one service's database and publishes a message to trigger the next step. If any step fails, **compensating transactions** execute in reverse order to undo previous work. This was [first described by Hector Garcia-Molina and Kenneth Salem in 1987](https://microservices.io/patterns/data/saga.html).

```
                          HAPPY PATH
  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │  Create   │───>│ Reserve  │───>│  Charge  │───>│  Send    │
  │  Order    │    │ Inventory│    │ Payment  │    │ Confirm  │
  └──────────┘    └──────────┘    └──────────┘    └──────────┘

                        FAILURE AT STEP 3
  ┌──────────┐    ┌──────────┐    ┌──────────┐
  │  Cancel   │<───│ Release  │<───│ Payment  │  <-- FAILS
  │  Order    │    │ Inventory│    │ Declined │
  └──────────┘    └──────────┘    └──────────┘
       COMPENSATE      COMPENSATE
```

### Orchestration: Central Coordinator

In the **orchestration** approach, a central **saga orchestrator** (sometimes called a saga execution coordinator or SEC) tells each participant what to do and when. It maintains the state machine, knows the full workflow, and issues compensations on failure.

```
                    ┌─────────────┐
              ┌────>│   Order     │
              │     │   Service   │
              │     └─────────────┘
              │
  ┌───────────┴───┐  ┌─────────────┐
  │    Saga       │──>│  Inventory  │
  │  Orchestrator │  │   Service   │
  │  (state       │  └─────────────┘
  │   machine)    │
  │               │  ┌─────────────┐
  └───────┬───────┘──>│  Payment   │
          │           │   Service   │
          │           └─────────────┘
          │
          └──────────── Knows the FULL workflow
                        Manages ALL compensations
                        Maintains explicit state
```

**Advantages:**
- **Centralized visibility** -- one place to see the entire workflow state
- **Simpler error handling** -- orchestrator manages all compensations
- **Easier testing** -- state machine is testable in isolation
- **Clear control flow** -- new developers can read the orchestrator to understand the whole process

**Disadvantages:**
- Orchestrator can become a **single point of failure** if not designed for HA
- Risk of the orchestrator becoming a **"god object"** that accumulates too much logic
- Participants become somewhat **coupled to the orchestrator** protocol

### Choreography: Event-Driven Dance

In the **choreography** approach, each service listens for events and reacts independently. There is no central controller. Services communicate through **domain events** published to a shared message bus.

```
  ┌──────────┐  OrderCreated  ┌──────────┐  InventoryReserved  ┌──────────┐
  │  Order   │ ─────────────> │ Inventory│ ──────────────────> │ Payment  │
  │  Service │                │  Service │                     │  Service │
  └──────────┘                └──────────┘                     └──────────┘
       ^                                                            │
       │                    PaymentCharged                          │
       └────────────────────────────────────────────────────────────┘
                    Each service reacts to events
                    No central coordinator
                    Logic is distributed
```

**Advantages:**
- **No single point of failure** -- each service is autonomous
- **Loose coupling** -- services only know about events, not each other
- **Better scalability** -- no coordinator bottleneck

**Disadvantages:**
- **Hard to trace** the full workflow path across services
- **Difficult to add cross-cutting concerns** like timeouts, retries, global deadlines
- **Cyclic dependencies** can emerge silently between event chains
- **Testing is harder** -- requires integration tests across multiple services

### Comparison Table: When to Use Which

| Criteria | Orchestration | Choreography |
|----------|--------------|--------------|
| **Number of services** | 4+ services | 2-3 services |
| **Workflow complexity** | Complex, branching | Linear, simple |
| **Team structure** | Central platform team | Independent service teams |
| **Observability needs** | High (compliance, audit) | Lower |
| **Failure handling** | Complex compensations | Simple rollbacks |
| **Scaling priority** | Moderate | Critical |
| **Examples** | Temporal, Axon Sagas, AWS Step Functions | Kafka event streams, RabbitMQ pub/sub |

> **Key Insight:** [Chris Richardson's microservices.io](https://microservices.io/patterns/data/saga.html) notes that "the lack of isolation means there's risk that concurrent execution of multiple sagas can cause data anomalies." This is the fundamental tradeoff -- sagas sacrifice isolation for availability. Your design must account for **interleaved saga executions** through countermeasures like semantic locking, commutative updates, or pessimistic/optimistic concurrency control.

---

## :mag: Process Managers & Workflow Engines

**The "so what?":** A saga handles failures. A process manager handles complex business logic -- branching, parallel execution, human approvals, timers, retries. Many teams conflate the two, but understanding the distinction determines whether you over-engineer a simple rollback or under-engineer a complex workflow.

### Saga vs Process Manager

The terms are often used interchangeably, but they are [fundamentally different](https://event-driven.io/en/saga_process_manager_distributed_transactions/) in their intent and capabilities:

| Aspect | Saga | Process Manager |
|--------|------|-----------------|
| **Primary concern** | Failure recovery / compensation | Business process coordination |
| **State** | Stateless (or minimal) | Stateful (explicit state machine) |
| **Behavior** | Reactive (respond to failures) | Proactive (drive the workflow) |
| **Parallelism** | Sequential compensations | Can fan-out parallel steps |
| **Branching** | Linear (forward/backward) | Decision points, conditional paths |
| **Lifespan** | Duration of one transaction | Can span days/weeks (human approval) |
| **Anti-corruption** | N/A | Acts as boundary between contexts |

As the [Axon Framework community notes](https://discuss.axoniq.io/t/process-manager-vs-saga-ambiguity/2135), "Sagas are great for orchestrating processes between different bounded contexts. You can view them as an anti-corruption layer between them."

### How Process Managers Compose Steps

A process manager is a **state machine** that reacts to events and issues commands. It maintains an explicit state that determines what happens next.

```
  ┌─────────────────────────────────────────────┐
  │           Process Manager (State Machine)    │
  │                                              │
  │  [INITIATED] ──OrderPlaced──> [RESERVING]    │
  │  [RESERVING] ──Reserved────> [CHARGING]      │
  │  [RESERVING] ──OutOfStock──> [CANCELLED]     │
  │  [CHARGING]  ──Charged─────> [CONFIRMING]    │
  │  [CHARGING]  ──Declined────> [COMPENSATING]  │
  │  [CONFIRMING]──Confirmed───> [COMPLETED]     │
  │  [COMPENSATING]────────────> [CANCELLED]     │
  └─────────────────────────────────────────────┘
```

### Workflow Engines in Production

Modern workflow engines provide the process manager pattern as a **platform service**:

| Engine | Approach | Scale | Key Feature |
|--------|----------|-------|-------------|
| **Temporal** | Durable execution | 12B+ executions/mo (Uber) | Code-as-workflow, replay-based recovery |
| **AWS Step Functions** | JSON state machine | Managed, serverless | Visual workflow builder, Express mode for high-throughput |
| **Camunda** | BPMN engine | Enterprise standard | Standards-based (BPMN 2.0), visual modeling |
| **Netflix Conductor** | Task orchestration | Netflix scale | JSON DSL, polling-based workers |
| **Axon Framework** | Event-driven | Enterprise Java | Built-in saga + event sourcing + CQRS |

### MassTransit vs NServiceBus: .NET Ecosystem

For .NET teams, [MassTransit and NServiceBus](https://code-maze.com/aspnetcore-comparison-of-rebus-nservicebus-and-masstransit/) represent two mature approaches to saga implementation:

**MassTransit** integrates the Automatonymous state machine library (now built-in since v8). Sagas are defined as fluent state machines:

```csharp
// MassTransit Saga State Machine (conceptual)
public class OrderStateMachine : MassTransitStateMachine<OrderState>
{
    public State Submitted { get; private set; }
    public State Accepted { get; private set; }
    public Event<OrderSubmitted> OrderSubmitted { get; private set; }

    public OrderStateMachine()
    {
        During(Initial,
            When(OrderSubmitted)
                .Then(ctx => ctx.Saga.OrderDate = DateTime.UtcNow)
                .TransitionTo(Submitted));
    }
}
```

**NServiceBus** takes monitoring further with dedicated tools: [ServicePulse](https://code-maze.com/aspnetcore-comparison-of-rebus-nservicebus-and-masstransit/) for real-time endpoint monitoring and ServiceInsight for visualizing message flows -- invaluable for debugging complex saga interactions in production.

---

## :mag: Causal Tracing & Correlation

**The "so what?":** When a multi-step workflow fails at step 5, you need to know what triggered it, what preceded it, and what was affected. Without causal tracing, debugging distributed transactions becomes a multi-hour archaeological expedition across log files. With it, you answer "what happened and why" in seconds.

### The Three IDs Every Message Needs

[Greg Young's formulation](https://blog.arkency.com/correlation-id-and-causation-id-in-evented-systems/), widely adopted in event-driven architectures, states that **every message carries three identifiers**:

1. **Message ID** (`uuid`) -- the unique identity of this specific message
2. **Correlation ID** (`correlation_id`) -- links all messages in the same logical operation
3. **Causation ID** (`causation_id`) -- points to the message that directly caused this one

```
  User clicks "Place Order"
  │
  ├─ TX: CreateOrder
  │  uuid: "abc-001"
  │  correlation_id: "abc-001"    <-- initiating message IS the correlation root
  │  causation_id: null
  │
  ├──> TX: ReserveInventory
  │    uuid: "abc-002"
  │    correlation_id: "abc-001"  <-- same correlation (same logical operation)
  │    causation_id: "abc-001"   <-- caused by CreateOrder
  │
  ├────> TX: ChargePayment
  │      uuid: "abc-003"
  │      correlation_id: "abc-001"  <-- same correlation
  │      causation_id: "abc-002"   <-- caused by ReserveInventory
  │
  └──────> TX: SendConfirmation
           uuid: "abc-004"
           correlation_id: "abc-001"  <-- same correlation
           causation_id: "abc-003"   <-- caused by ChargePayment
```

### Propagation Rules

The [Rails Event Store implementation](https://railseventstore.org/docs/v2/correlation_causation/) codifies the propagation as:

```ruby
# When reacting to an event, propagate the chain:
correlation_id = event.metadata[:correlation_id] || event.event_id
causation_id   = event.event_id   # my cause is the event I'm reacting to
```

This creates two powerful querying capabilities:

- **Correlation stream** (`WHERE correlation_id = X`): All messages in the same business operation. Like finding all pages of a conversation.
- **Causation stream** (`WHERE causation_id = X`): All messages directly triggered by a specific message. Like finding the children of a tree node.

> **Key Insight:** Correlation gives you the "what happened in this transaction?" view. Causation gives you the "what caused what?" graph. Together they reconstruct **the full causal DAG** of any distributed operation. This is not optional for production saga debugging -- it is essential.

### OpenTelemetry Trace Context Propagation

[OpenTelemetry's context propagation](https://opentelemetry.io/docs/concepts/context-propagation/) extends this concept with the W3C TraceContext standard, using `traceparent` and `tracestate` headers:

```
traceparent: 00-<trace-id>-<parent-span-id>-<trace-flags>
             version │          │                │
                     │          │                └── sampling flags
                     │          └── causation (parent span)
                     └── correlation (trace ID)
```

For message queues, this requires **explicit injection and extraction** since context does not automatically propagate across async boundaries. The pattern is:

1. **Producer** injects trace context into message headers/metadata
2. **Consumer** extracts trace context and creates a child span
3. The trace chain is preserved across **arbitrary time delays** between produce and consume

As [OneUptime's guide on message queue tracing](https://oneuptime.com/blog/post/2026-01-07-opentelemetry-message-queue-tracing/view) notes, "message queues present unique challenges for context propagation because messages may be processed long after they are published, with the producer and consumer running at different times."

### Applying to Actor TX Systems

For an actor system where TX is the message envelope, causal tracing maps directly:

| OTel Concept | Actor TX Equivalent | Purpose |
|-------------|-------------------|---------|
| `trace_id` | `meta.correlation_id` | Group all TXs in one operation |
| `parent_span_id` | `meta.causation_id` | Point to the causing TX |
| `span_id` | `tx.uuid` | Unique TX identity |
| `traceparent` header | `tx.meta` dict | Propagation carrier |
| Span start/end timestamps | `tx.timestamp` + reply timestamp | Latency measurement |

---

## :mag: Event Replay & Event Sourcing

**The "so what?":** Event sourcing means storing **what happened** instead of **where things are now**. Instead of a `balance = 500` row, you store `deposited 1000`, `withdrew 300`, `withdrew 200`. This gives you complete audit history, the ability to replay and debug, and the option to rebuild state from any point in time. The cost is complexity and storage.

### Core Architecture

```
                     TRADITIONAL (State)              EVENT SOURCED
                   ┌──────────────┐                ┌──────────────┐
  Command ───────> │  Update row  │    Command ──> │  Append event│
                   │  balance=500 │                │  Withdrew(200)│
                   └──────────────┘                └──────┬───────┘
                                                          │
                                                   ┌──────┴───────┐
                                                   │  Event Store │
                                                   │  1: Opened   │
                                                   │  2: Dep(1000)│
                                                   │  3: Wdr(300) │
                                                   │  4: Wdr(200) │
                                                   └──────────────┘
                                                          │
                                                   ┌──────┴───────┐
                                                   │  Replay ──>  │
                                                   │  balance=500 │
                                                   └──────────────┘
```

### Performance: The Replay Cost Problem

Event replay is powerful but has a concrete performance ceiling. As aggregates accumulate events, **replay time grows linearly**:

| Events per Aggregate | Approximate Replay Time | Impact |
|---------------------|------------------------|--------|
| 50 | ~1-5ms | Negligible |
| 1,000 | ~20-50ms | Noticeable under load |
| 10,000 | ~200-500ms | Problematic for hot paths |
| 100,000+ | Seconds | Unacceptable for real-time |

([Source: Kurrent/EventStore blog on snapshots](https://www.kurrent.io/blog/snapshots-in-event-sourcing))

### Snapshots: The Optimization

**Snapshots** solve the replay cost by periodically saving the current state alongside the event stream. On replay, load the latest snapshot and apply only events after it.

The [Kurrent blog](https://www.kurrent.io/blog/snapshots-in-event-sourcing) recommends: "Snapshots make sense when replay time exceeds **100ms** for hot aggregates." Common strategies:

| Strategy | When to Snapshot | Tradeoff |
|----------|-----------------|----------|
| **Every N events** | After 100, 500, or 1000 events | Predictable, simple to implement |
| **Time-based** | Every 5 minutes or hourly | Good for steady-stream aggregates |
| **On-demand** | When replay time exceeds threshold | Optimal storage, more complex |
| **Inline** | Same transaction as event append | No lag, slight write overhead |
| **Async** | Background process | No write overhead, eventual staleness |

[Marten](https://martendb.io/events/) (the .NET event sourcing library) supports both **inline snapshots** (created in the same transaction as event append) and **async snapshots** (background process). Marten 8.0 added **stream compacting** to reduce storage while retaining full state.

### EventStoreDB Performance Profile

[EventStoreDB](https://www.eventstore.com/) (now rebranded as Kurrent) claims **15K+ writes/second** and **50K+ reads/second**. It was purpose-built for event sourcing with built-in stream management, but notably does not include built-in snapshotting -- you implement it yourself by appending aggregate snapshots to a separate stream.

The [Moose Code blog](https://moosecode.nl/blog/event_store_optimized) documented making their EventStore implementation **2x to 4x+ faster** through serialization optimization, batch reads, and snapshot strategies.

### Akka Persistence: Actor-Native Event Sourcing

[Akka Persistence](https://doc.akka.io/libraries/akka-core/current/typed/persistence.html) integrates event sourcing directly into the actor model:

- An **event sourced actor** receives commands, validates them, generates events, persists events, then updates state
- On restart, the actor **replays its event journal** to rebuild state
- **Durable State** (alternative mode) persists only the latest state snapshot -- simpler but loses replay capability

Akka's "Remember Me" feature automatically **restarts saga/process manager actors** on cluster restart, so you don't have to track which sagas were running ([Akka documentation](https://doc.akka.io/libraries/akka-core/current/typed/persistence.html)).

> **Key Insight:** For an actor-based TX system, event sourcing means storing every TX that flows through the system. The TX stream **is** the event log. Replay means re-delivering the TX sequence to an actor to rebuild its state. This is architecturally natural -- the TX envelope already carries all the data needed for replay.

---

## :warning: Compensating Transactions & Failure Handling

**The "so what?":** In a distributed system, "undo" is not as simple as `ROLLBACK`. You cannot un-send an email, un-charge a credit card in the same millisecond, or un-ship a package. Compensating transactions are **semantic inverses** -- not rollbacks but new forward-actions that cancel the effect of previous ones.

### The Compensation Model

[Microsoft's Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction) defines the core challenge: "The steps in a compensating transaction must undo the effects of the steps in the original operation. A compensating transaction might not be able to simply replace the current state with the state the system was in at the start of the operation, because that approach could overwrite changes made by other concurrent instances."

### Forward vs Backward Recovery

The [AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga.html) distinguishes two recovery strategies:

| Recovery Type | When to Use | Mechanism |
|--------------|-------------|-----------|
| **Forward (retry)** | Infrastructure failure (timeout, network) | Retry the same step with idempotency |
| **Backward (compensate)** | Business logic failure (insufficient funds) | Execute compensating transactions in reverse |

### Temporal's Compensation Pattern

[Temporal's Python SDK](https://temporal.io/blog/compensating-actions-part-of-a-complete-breakfast-with-sagas) provides an elegant compensation pattern:

```python
class Compensations:
    """Track compensating actions and execute them on failure."""
    def __init__(self, parallel_compensations=False):
        self.parallel_compensations = parallel_compensations
        self.compensations = []

    def add(self, function):
        self.compensations.append(function)

    async def compensate(self):
        if self.parallel_compensations:
            await asyncio.gather(*[run(c) for c in self.compensations])
        else:
            # Execute in REVERSE order
            for f in reversed(self.compensations):
                try:
                    await workflow.execute_activity(f, ...)
                except:
                    workflow.logger.exception("failed to compensate")
```

Key design rules from the Temporal team:

1. **Register compensations BEFORE executing** -- if an activity times out after partial work, the compensation must still be registered
2. **Execute in reverse order** -- undo the most recent change first
3. **Compensations are NOT rollbacks** -- they are new forward-actions ("this is different from rolling the database back to a previous snapshotted state")
4. **Use `asyncio.shield()`** to ensure compensations complete even if the workflow is cancelled
5. **Compensations themselves can fail** -- build in retries and escalation

### Failure Taxonomy

| Failure Type | Example | Recovery Strategy |
|-------------|---------|-------------------|
| **Transient** | Network timeout, 503 | Retry with backoff |
| **Business** | Insufficient credit | Compensate (backward recovery) |
| **Poison** | Invalid data, bug | Dead-letter queue + alerting |
| **Compensation failure** | Refund API down | Retry compensation + human escalation |
| **Irreversible** | Email sent, SMS delivered | Log, notify, accept (no true undo) |

> **Key Insight:** A compensating transaction can **itself fail**. [Microsoft's guidance](https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction) warns that you need "a robust error-handling strategy, such as retrying the compensation, manual intervention by an administrator, or escalating the failure." In practice, this means your compensation logic needs the same retry/idempotency guarantees as your primary logic. It is not a second-class concern.

---

## :bar_chart: Distributed Transaction Alternatives

**The "so what?":** There is no single "right" pattern for distributed transactions. The choice depends on your consistency requirements, scale targets, and operational complexity budget. Here is the full spectrum, with production-proven tradeoffs.

### The Full Spectrum

[Bilgin Ibryam's comparison at Red Hat](https://developers.redhat.com/articles/2021/09/21/distributed-transaction-patterns-microservices-compared) and [Baeldung's analysis](https://www.baeldung.com/cs/two-phase-commit-vs-saga-pattern) inform this decision matrix:

```
  STRONG CONSISTENCY                              HIGH SCALABILITY
  <──────────────────────────────────────────────────────────>

  Modular     Two-Phase     Orchestrated    Choreographed    Parallel
  Monolith    Commit (2PC)  Saga            Saga             Pipelines
  │           │             │               │                │
  │ One DB,   │ XA protocol │ Central       │ Event-driven   │ Independent
  │ one TX    │ coordinator │ orchestrator  │ reactions      │ workers
  │           │             │               │                │
  │ ACID      │ ACID (dist) │ Eventual      │ Eventual       │ Eventual
  └───────────┴─────────────┴───────────────┴────────────────┘
```

### The Outbox Pattern: Reliable Messaging Without 2PC

The **transactional outbox** pattern solves the "dual write" problem -- needing to update a database AND publish a message atomically -- without using 2PC.

```
  ┌─────────────────────────────────────────────┐
  │  Single Database Transaction                │
  │                                              │
  │  1. INSERT INTO orders (...) VALUES (...)   │
  │  2. INSERT INTO outbox (event_type, payload)│
  │                                              │
  │  COMMIT  (atomic -- both or neither)        │
  └─────────────────────────────────────────────┘
            │
            │  Outbox Processor (separate thread/process)
            v
  ┌─────────────────────────┐    ┌──────────────┐
  │  SELECT FROM outbox     │───>│  Message      │
  │  WHERE sent = false     │    │  Broker       │
  │  UPDATE sent = true     │    │  (Kafka, etc.)│
  └─────────────────────────┘    └──────────────┘
```

[Chris Richardson's microservices.io](https://microservices.io/patterns/data/transactional-outbox.html) specifies three critical requirements:
1. Messages **must be sent in the order** they were written
2. Consumers **must be idempotent** (handle duplicate delivery)
3. Old outbox entries **must be cleaned up** to prevent table bloat

An alternative to the polling publisher is **Change Data Capture (CDC)** using tools like Debezium, which tails the database transaction log for outbox table changes.

### Pattern Selection Decision Tree

```
  Do you need STRONG consistency?
  │
  ├── YES ──> Can you use a single database?
  │           ├── YES ──> Modular monolith (local transactions)
  │           └── NO  ──> 2PC (accept the scalability cost)
  │
  └── NO  ──> How many services are involved?
              │
              ├── 2-3 ──> Choreography (events between services)
              │           + Outbox pattern for reliable messaging
              │
              └── 4+  ──> Orchestration (saga orchestrator)
                          + Causal tracing for debugging
                          + Outbox pattern per service
```

### Detailed Comparison

| Pattern | Consistency | Scale | Complexity | Failure Mode | Production Example |
|---------|-------------|-------|------------|-------------|-------------------|
| **2PC** | Strong | Low | Medium | Coordinator failure = blocked TXs | Legacy banking systems |
| **Orchestrated Saga** | Eventual | High | Medium-High | Orchestrator failure (mitigated with durability) | Uber (Cadence), Netflix (Temporal) |
| **Choreographed Saga** | Eventual | Very High | High (hidden) | Lost events, cyclic deps | Amazon event-driven services |
| **Outbox + CDC** | Eventual | High | Medium | Outbox table growth, CDC lag | [Debezium users](https://microservices.io/patterns/data/transactional-outbox.html) |
| **Try-Confirm/Cancel** | Eventual | Medium | High | Timeout on confirm/cancel | Payment processors |

---

## :books: Theoretical Foundations

**The "so what?":** The patterns above are not ad-hoc inventions. They have roots in formal process calculi developed over 40 years. Understanding the theory helps you evaluate whether a new pattern is genuinely novel or a repackaging of solved (or unsolvable) problems.

### Process Calculi and Actor Models

[Process calculi](https://en.wikipedia.org/wiki/Process_calculus) are formal mathematical models for reasoning about concurrent systems. The three major branches, developed between 1973 and 1982, continue to influence modern distributed system design:

| Calculus | Author(s) | Year | Key Idea | Modern Influence |
|----------|-----------|------|----------|-----------------|
| **CCS** | Robin Milner | 1973-80 | Communicating systems, bisimulation | Equivalence checking, model checking |
| **CSP** | Tony Hoare | 1978 | Sequential processes, channels | Go's goroutines/channels, Erlang |
| **ACP** | Bergstra & Klop | 1982 | Algebraic composition | Process algebra verification |
| **Pi-calculus** | Milner | 1992 | Mobile processes, name passing | Actor calculi, session types |
| **Actor Model** | Hewitt, Bishop, Steiger | 1973 | Autonomous agents, async messaging | Akka, Erlang/OTP, Orleans |

The [relationship between actor models and process calculi](https://en.wikipedia.org/wiki/Actor_model_and_process_calculi) is well-studied. Agha's **Actor pi-calculus** is based on a typed version of the asynchronous pi-calculus. The key theoretical distinction:

- **CSP/CCS**: Communication is **synchronous** (sender blocks until receiver accepts)
- **Actor Model**: Communication is **asynchronous** (fire-and-forget to a mailbox)

This distinction matters for transaction composition: CSP-style synchronous channels require something like a **two-phase commit protocol** to implement guarded choice (offering multiple options but committing to only one). Actor-style async messaging naturally leads to **saga-like patterns** where each step commits independently and compensates on failure.

### Why This Matters for TX Composition

The theoretical insight is that **transaction composition in an asynchronous actor system cannot provide ACID isolation** without introducing synchronization points that reduce to 2PC. This is not a limitation to be worked around -- it is a fundamental property of the model. Saga patterns are the **theoretically correct** approach for composing transactions in async messaging systems.

---

## :office: Production Systems at Scale

**The "so what?":** Theory and patterns matter, but what actually works at billion-transaction scale? These are the numbers from companies that bet their business on these patterns.

### Temporal / Cadence (Uber)

[Uber's Cadence platform](https://www.uber.com/blog/announcing-cadence/) (the precursor to Temporal) represents the most battle-tested workflow orchestration at scale:

- **12 billion executions per month** at Uber alone
- **270 billion actions per month** (individual steps within workflows)
- Powers **1,000+ services** from T0 (most critical) to T5
- Scales horizontally across **sharded partitions**
- Built-in **rate limits, hot shard detection, region failover**
- **700+ forks** of the original Cadence project

[Temporal](https://temporal.io/news/temporal-io-raises-usd100-million-series-b-company-valuation-passes-usd1-5) (Cadence's commercial successor) raised $100M at a **$1.5B valuation** and now has **over 2,500 customers and 7 million deployed clusters**. Specific customer numbers:

| Company | Scale | Use Case |
|---------|-------|----------|
| **Netflix** | 500K+ workflows/day (2021), projected 1M/day | [Media processing pipelines (Plato platform)](https://temporal.io/resources/case-studies/netflix-increases-developer-productivity) |
| **Instacart** | 75M+ monthly workflows | Delivery coordination |
| **Datadog** | 3M workflows/month, 100+ users, dozens of teams | [Production readiness checks](https://temporal.io/resources/on-demand/future-of-friction-free-workflow-upgrades) |
| **Stripe** | Undisclosed (critical payment flows) | Payment orchestration |
| **Snapchat** | Undisclosed (high-volume) | Content pipelines |
| **Coinbase** | Undisclosed (crypto transaction flows) | Financial workflows |

**Key architectural decision:** Temporal uses **event sourcing internally** to record each workflow state change as an immutable event. This enables automatic retries and the ability to replay workflows from any point -- the saga pattern built on an event-sourced foundation.

### ANZ Bank & Maersk

[ANZ Bank](https://medium.com/@milinangalia/the-rise-of-temporal-how-netflix-and-leading-tech-companies-are-revolutionizing-workflow-822fbcc736e6) reduced their home loan origination system implementation from **over a year to weeks** using Temporal.

[Maersk](https://medium.com/@milinangalia/the-rise-of-temporal-how-netflix-and-leading-tech-companies-are-revolutionizing-workflow-822fbcc736e6) cut feature delivery times in their logistics operations from **60-80 days down to 5-10 days**.

### Axon Framework

[Axon Framework](https://www.axoniq.io/blog/sagas-in-practice) is the dominant Java ecosystem choice for event-driven architectures combining CQRS + event sourcing + sagas. It provides:

- **`@SagaEventHandler`** for orchestration-based sagas with lifecycle management
- **`@StartSaga`** / **`@EndSaga`** annotations for saga lifecycle control
- **Deadline management** via `DeadlineManager` (with [JobRunr integration](https://www.jobrunr.io/en/blog/axon-framework-jobrunr-pro/) for distributed deadlines)
- Built-in event replay for projection rebuilding
- Support for both [choreography (`@EventHandler`) and orchestration (`@SagaEventHandler`)](https://medium.com/@positiveb16/choreography-based-saga-using-axon-framework-438a2d03b9ab)

---

## :zap: Mapping to Actor-Based TX Systems

**The "so what?":** Given PyBend's existing TX envelope and actor system, here is how these production patterns map onto the current architecture -- what is already supported, what is close, and what would require new primitives.

### Current TX Capabilities (PyBend v0.9)

The existing `TX` dataclass provides:

```python
@dataclass
class TX:
    name: str          # Event type: SCHEMA, READ, CREATE, UPDATE, DELETE, ERROR...
    source: str        # Sender address
    target: str        # Recipient address
    data: dict         # Payload
    meta: dict         # Metadata (extensible)
    timestamp: float   # When created
    uuid: str          # Unique 12-char hex ID

    def reply(self, data, name) -> TX    # Response with in_reply_to tracking
    def error(self, message, code) -> TX # Error response
```

### Gap Analysis: What Is Needed for Each Pattern

| Capability | Current State | Gap | Effort |
|-----------|---------------|-----|--------|
| **Correlation ID** | `meta` dict (ad-hoc) | Need standard `meta.correlation_id` propagation | Small -- convention + helper |
| **Causation ID** | `meta.in_reply_to` (partial) | Rename/extend to explicit `meta.causation_id` | Small -- naming convention |
| **TX History / Event Log** | Not persisted | Need TX store (append-only log) | Medium -- new storage layer |
| **Saga orchestrator** | Not built | Need `SagaActor` base class with state machine | Medium-Large |
| **Compensating TX** | Not built | Need compensation registry pattern | Medium |
| **Replay** | Not built | Need TX log reader + actor state rebuilder | Medium-Large |
| **Snapshots** | Not applicable yet | Need snapshot store alongside TX log | Medium |
| **Outbox pattern** | Not needed (in-process) | Only needed if system goes multi-process | N/A for now |
| **Process manager** | Actor handler is close | Extend with explicit state machine | Medium |

### Proposed TX Extensions

The `meta` dict already provides the extension point. The three critical additions for causal tracing:

```python
# Current TX creation
tx = TX(
    name='CREATE',
    source='api',
    target='products',
    data={'name': 'Widget', 'price': 9.99},
    meta={},  # <-- extension point
)

# With causal tracing
tx = TX(
    name='CREATE',
    source='api',
    target='products',
    data={'name': 'Widget', 'price': 9.99},
    meta={
        'correlation_id': 'saga-abc-001',    # root operation ID
        'causation_id': 'tx-xyz-prev',       # what caused this TX
        'saga_id': 'order-saga-42',          # optional: saga instance
    },
)
```

### Saga Actor Sketch

A minimal saga orchestrator for an actor system:

```
  ┌──────────────────────────────────────────────┐
  │  SagaActor (extends Actor)                   │
  │                                               │
  │  state: INITIATED | STEP_1 | STEP_2 | ...   │
  │  compensations: [fn1, fn2, ...]              │
  │  correlation_id: str                          │
  │                                               │
  │  async def inbox(tx):                        │
  │    if tx.is_error:                           │
  │      await self.compensate()                 │
  │    else:                                      │
  │      self.advance(tx)                        │
  │                                               │
  │  async def advance(tx):                      │
  │    match self.state:                         │
  │      case INITIATED:                         │
  │        compensations.add(cancel_order)       │
  │        await send(TX('CREATE', ...))         │
  │        self.state = RESERVING                │
  │      case RESERVING:                         │
  │        compensations.add(release_inventory)  │
  │        await send(TX('CHARGE', ...))         │
  │        self.state = CHARGING                 │
  │      ...                                      │
  │                                               │
  │  async def compensate():                     │
  │    for fn in reversed(self.compensations):   │
  │      await fn()                              │
  └──────────────────────────────────────────────┘
```

### Architecture: TX Flow with Causal Tracing

```
  User Action
       │
       v
  ┌─────────┐  TX(CREATE, correlation=saga-1)   ┌──────────┐
  │ Network  │ ───────────────────────────────> │  Matrix   │
  │  API     │                                   │  (Router) │
  └─────────┘                                   └────┬─────┘
                                                      │
       ┌──────────────────────────────────────────────┤
       │                                              │
       v                                              v
  ┌──────────┐                                  ┌──────────┐
  │  Saga    │  TX(RESERVE, correlation=saga-1) │  TX Log   │
  │  Actor   │ ──────────────────────────────> │ (Append   │
  │          │  causation=create-tx-uuid        │  Only)    │
  └──────────┘                                  └──────────┘
       │
       │  TX(CHARGE, correlation=saga-1, causation=reserve-tx-uuid)
       v
  ┌──────────┐
  │ Payment  │
  │  Actor   │
  └──────────┘
```

### Incremental Adoption Path

The critical insight from production systems: **you do not need everything at once**. The recommended adoption order, based on value-to-effort ratio:

| Phase | Capability | Value | Effort |
|-------|-----------|-------|--------|
| **1** | Correlation + causation IDs in `meta` | Debugging, tracing | **Low** (convention) |
| **2** | TX append-only log (SQLite table) | Audit trail, replay foundation | **Medium** |
| **3** | Saga base class with compensation | Multi-step workflows | **Medium** |
| **4** | Event replay from TX log | State rebuilding, debugging | **Medium** |
| **5** | Snapshots | Performance optimization for long-lived actors | **Low** (once log exists) |
| **6** | Process manager with state machine | Complex branching workflows | **Medium-High** |

> **Key Insight:** Phase 1 is pure convention -- zero code changes to the TX dataclass, just a documented standard for what goes in `meta`. Phase 2 is a single SQLite table. These two phases give you **80% of the debugging value** for about **10% of the total implementation cost**. Every production system surveyed considers correlation/causation IDs table-stakes infrastructure.

---

## :link: Sources

1. [Saga Pattern - microservices.io (Chris Richardson)](https://microservices.io/patterns/data/saga.html)
2. [Saga Pattern Demystified - ByteByteGo](https://blog.bytebytego.com/p/saga-pattern-demystified-orchestration)
3. [Saga Design Pattern - Microsoft Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/saga)
4. [Compensating Transaction Pattern - Microsoft Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction)
5. [Saga Compensating Transactions - Temporal Blog](https://temporal.io/blog/compensating-actions-part-of-a-complete-breakfast-with-sagas)
6. [Mastering Saga Patterns - Temporal Blog](https://temporal.io/blog/mastering-saga-patterns-for-distributed-transactions-in-microservices)
7. [Announcing Cadence 1.0 - Uber Engineering Blog](https://www.uber.com/blog/announcing-cadence/)
8. [Temporal $100M Series B - Temporal.io](https://temporal.io/news/temporal-io-raises-usd100-million-series-b-company-valuation-passes-usd1-5)
9. [Netflix Developer Productivity with Temporal - Temporal Case Study](https://temporal.io/resources/case-studies/netflix-increases-developer-productivity)
10. [Distributed Transaction Patterns Compared - Red Hat Developer](https://developers.redhat.com/articles/2021/09/21/distributed-transaction-patterns-microservices-compared)
11. [Transactional Outbox Pattern - microservices.io](https://microservices.io/patterns/data/transactional-outbox.html)
12. [Correlation ID and Causation ID - Arkency Blog](https://blog.arkency.com/correlation-id-and-causation-id-in-evented-systems/)
13. [Correlation and Causation - Rails Event Store](https://railseventstore.org/docs/v2/correlation_causation/)
14. [OpenTelemetry Context Propagation](https://opentelemetry.io/docs/concepts/context-propagation/)
15. [Message Queue Tracing with OpenTelemetry - OneUptime](https://oneuptime.com/blog/post/2026-01-07-opentelemetry-message-queue-tracing/view)
16. [Snapshots in Event Sourcing - Kurrent (EventStoreDB)](https://www.kurrent.io/blog/snapshots-in-event-sourcing)
17. [Marten as Event Store](https://martendb.io/events/)
18. [Making Event Sourcing with Marten Faster - Jeremy D. Miller](https://jeremydmiller.com/2025/06/02/making-event-sourcing-with-marten-go-faster/)
19. [Akka Persistence - Event Sourcing](https://doc.akka.io/libraries/akka-core/current/typed/persistence.html)
20. [MassTransit State Machine Sagas](https://masstransit.io/documentation/patterns/saga/state-machine)
21. [Comparison of Rebus, NServiceBus, and MassTransit - Code Maze](https://code-maze.com/aspnetcore-comparison-of-rebus-nservicebus-and-masstransit/)
22. [Sagas in Practice - AxonIQ Blog](https://www.axoniq.io/blog/sagas-in-practice)
23. [Process Calculus - Wikipedia](https://en.wikipedia.org/wiki/Process_calculus)
24. [Actor Model and Process Calculi - Wikipedia](https://en.wikipedia.org/wiki/Actor_model_and_process_calculi)
25. [2PC vs Saga Pattern - Baeldung](https://www.baeldung.com/cs/two-phase-commit-vs-saga-pattern)
26. [Saga and Process Manager - Oskar Dudycz (Event-Driven.io)](https://event-driven.io/en/saga_process_manager_distributed_transactions/)
27. [Saga Choreography Pattern - AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga-choreography.html)
28. [The $100B Bull Case for Temporal - Swyx](https://www.swyx.io/temporal-centicorn)
29. [EventStore Optimization - Moose Code Blog](https://moosecode.nl/blog/event_store_optimized)
30. [Axon Framework + JobRunr: Saga Deadlines](https://www.jobrunr.io/en/blog/axon-framework-jobrunr-pro/)
