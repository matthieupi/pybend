# Actor Framework Precedents: How Actors Relate to Domain/Data Models

**Domain:** Actor-model frameworks and their relationship to domain/data models
**Researched:** 2026-02-26
**Overall confidence:** HIGH (multiple authoritative sources, official documentation, cross-verified)

---

## Executive Summary

Every major actor framework solves the same fundamental tension: actors are behavioral (receive messages, maintain state, route) while data models are structural (fields, validation, serialization, persistence). The universal answer across all mature frameworks is: **data models never inherit from actor base classes**. State is always a separate, plain data type -- a case class, POCO, struct, or dict -- that the actor contains, manages, or wraps.

Five distinct patterns emerge, with "Actor-manages-entity" being the dominant pattern and "Actor-IS-entity" being the aspirational DDD pattern. No production framework merges the data model class with the actor class through inheritance. N3TX's current architecture (where `ProtoModel` is a Pydantic `BaseModel` and `Actor` is a separate JS class) already follows the industry consensus. The question for N3TX is which *relationship* pattern to adopt between its actors and its models.

---

## 1. Akka (Scala/Java)

**Confidence:** HIGH (official Akka documentation, Lightbend/Akka guides)

### How Actors Relate to Domain Models

Akka enforces a strict **three-type separation**: Commands, Events, and State are all plain case classes / sealed traits. None of them inherit from any actor class. The actor itself is defined as a `Behavior[Command]` (in Akka Typed) or extends `AbstractActor` (classic Akka).

```scala
// STATE: Plain case class, no actor inheritance
final case class Customer(name: String, address: String) {
  def withName(newName: String): Customer = copy(name = newName)
}

// COMMANDS: Plain case class hierarchy
sealed trait Command
final case class ChangeName(name: String) extends Command

// EVENTS: Plain case class hierarchy
sealed trait Event
final case class NameChanged(name: String) extends Event

// ACTOR: Separate from all of the above
object CustomerEntity {
  def apply(entityId: String): Behavior[Command] =
    EventSourcedBehavior[Command, Event, Customer](
      persistenceId = PersistenceId("Customer", entityId),
      emptyState = Customer("", ""),
      commandHandler = (state, cmd) => ...,
      eventHandler = (state, evt) => ...
    )
}
```

### Pattern: Actor-Manages-Entity (with Event Sourcing)

The actor **manages** the domain model as its state parameter. The `Customer` case class is pure data; `CustomerEntity` is the behavioral wrapper. The entity actor uses `EventSourcedBehavior` which takes the state type `Customer` as a type parameter but never requires `Customer` to extend any actor trait.

### Does the domain model inherit from the actor?

**No.** The domain model (case class) is a type parameter to the behavior, never a subclass. The separation is enforced by the type system: `EventSourcedBehavior[Command, Event, State]` takes three independent types.

### Akka Persistence and Event Sourcing

Akka Persistence stores **events** (not state). State is reconstructed by replaying events through the `eventHandler`. This means the state object must be:
- Serializable (for snapshots)
- Immutable (for deterministic replay)
- Pure data (no actor references, no side effects)

This design makes it impossible for the state to be an actor, because actors have identity, lifecycle, and side effects -- all things that conflict with serialization and replay.

### The Behavioral vs Data Split

| Concern | Where It Lives |
|---------|---------------|
| Data structure | Case class (`Customer`) |
| Validation | Case class constructors / smart constructors |
| Business rules | Command handler (in the actor behavior) |
| Persistence | Event handler + event store (managed by actor runtime) |
| Serialization | Case class serializers (Jackson, Protobuf, etc.) |
| Message routing | Actor system (supervisors, routers) |

### DDD with Akka: "Actor IS Entity" Conceptually

While the *code* follows Actor-manages-entity, the *conceptual model* in DDD-with-Akka treats the actor as the aggregate root. As described in DDD literature for Akka: "Rather than just seeing an actor as a mediator sitting in front of a database, you see the actor conceptually as the entity." But even in this conceptual framing, the *data* is still a separate case class. The actor IS the entity in terms of identity and behavior, but it CONTAINS the data as a separate type.

**Sources:**
- [Akka Event Sourcing Documentation](https://doc.akka.io/libraries/akka-core/current/typed/persistence.html)
- [Scalac: Akka Domain Model and Entity](https://scalac.io/blog/akka-platform-domain-model-and-entity/)
- [Baeldung: Event Sourcing with Akka](https://www.baeldung.com/scala/akka-event-sourcing)
- [DDD with Akka Actors](https://onurgumus.github.io/2021/01/16/DDD-with-Akka-actors.html)
- [Akka, DDD, CQRS and Me](https://medium.com/@dreweaster/akka-ddd-cqrs-event-sourcing-and-me-dad400ab62d1)

---

## 2. Microsoft Orleans

**Confidence:** HIGH (official Microsoft Learn documentation, updated Feb 2026)

### The Grain Pattern

Orleans grains are "virtual actors" -- logically immortal entities with identity, behavior, and state. A grain IS the domain entity conceptually (a `UserGrain` represents a user), but state is always a **separate POCO class**.

```csharp
// STATE: Plain C# class, no grain inheritance
[Serializable]
public class ProfileState
{
    public string Name { get; set; }
    public DateTime DateOfBirth { get; set; }
}

// GRAIN (ACTOR): Inherits from Grain, contains state via injection
public class UserGrain : Grain, IUserGrain
{
    private readonly IPersistentState<ProfileState> _profile;
    private readonly IPersistentState<CartState> _cart;

    public UserGrain(
        [PersistentState("profile", "profileStore")] IPersistentState<ProfileState> profile,
        [PersistentState("cart", "cartStore")] IPersistentState<CartState> cart)
    {
        _profile = profile;
        _cart = cart;
    }

    public Task<string> GetNameAsync() => Task.FromResult(_profile.State.Name);

    public async Task SetNameAsync(string name)
    {
        _profile.State.Name = name;
        await _profile.WriteStateAsync();
    }
}
```

### Grain State vs Grain Behavior

Orleans makes the split explicit through its API design:

| Concern | Type | Relationship |
|---------|------|-------------|
| Identity | Grain ID (string/guid/int) | Provided by runtime |
| Behavior | Grain class (extends `Grain`) | Developer writes |
| State | POCO class (plain C# object) | Injected via `IPersistentState<T>` |
| Persistence | Storage provider | Configured externally |

### `IPersistentState<T>`: State as a Separate Concern

The modern Orleans pattern (replacing the legacy `Grain<TState>` base class) injects state through constructor injection with `IPersistentState<TState>`. This is a deliberate architectural choice:

- A grain can have **multiple named state objects** (e.g., `_profile` and `_cart`)
- Each state object can use a **different storage provider**
- State is loaded automatically before `OnActivateAsync`
- The developer explicitly calls `WriteStateAsync()` to persist

The legacy approach (`Grain<TState>`) made state an inherited property. Orleans moved away from this toward injection specifically to decouple state from the grain's class hierarchy.

### Virtual Actors: Identity Without Lifecycle

Orleans grains are "logically immortal" -- from the developer's perspective, a grain always exists. The runtime activates it in memory when first messaged and deactivates when idle. This means:

- Grain identity is permanent (the "User-123" grain always exists conceptually)
- Grain activation is ephemeral (the in-memory instance comes and goes)
- State must survive deactivation (hence external persistence)

This pattern directly parallels N3TX's `ProtoModel` entities which have a permanent identity (`id`) and are loaded/stored from SQLite. The model always conceptually exists; the in-memory representation is ephemeral.

### Does the domain model inherit from the grain?

**No.** `ProfileState` is a plain POCO. The grain (`UserGrain`) inherits from `Grain` (the actor base class). State is injected, not inherited.

**Sources:**
- [Orleans Grain Persistence (Microsoft Learn, Feb 2026)](https://learn.microsoft.com/en-us/dotnet/orleans/grains/grain-persistence/)
- [Orleans Overview (Microsoft Learn)](https://learn.microsoft.com/en-us/dotnet/orleans/overview)
- [Orleans Best Practices](https://learn.microsoft.com/en-us/dotnet/orleans/resources/best-practices)
- [Microsoft Orleans Overview: Actors, Grains, Architecture](https://bool.dev/blog/detail/microsoft-orleans-overview)

---

## 3. Erlang/OTP / Elixir (GenServer + Ecto)

**Confidence:** HIGH (official Elixir docs, well-documented community patterns)

### GenServer State vs Data Structs

In Erlang/OTP and Elixir, a GenServer's state is **any Erlang/Elixir term** -- a map, struct, list, tuple, or any combination. There is no state base class, no state interface, no state type parameter. The state is simply whatever you return from `init/1` and pass through `handle_call/3` / `handle_cast/2`.

```elixir
# DATA MODEL: Plain Ecto schema, no GenServer involvement
defmodule BookStore.Book do
  use Ecto.Schema

  schema "books" do
    field :title, :string
    field :author, :string
    field :isbn, :string
    timestamps()
  end
end

# ACTOR: GenServer that contains the Ecto struct as state
defmodule BookStore.BookProcess do
  use GenServer

  def start_link(%Book{} = book) do
    GenServer.start_link(__MODULE__, book,
      name: {:via, Registry, {BookStore.BookRegistry, book.id}})
  end

  def init(%Book{} = book) do
    {:ok, book}  # The Ecto struct IS the state
  end

  def handle_call(:get, _from, book) do
    {:reply, book, book}  # Return the struct directly
  end
end
```

### Phoenix + Ecto + GenServer Integration

The Elixir community has a clear, well-documented pattern:

1. **Ecto schemas** define data structure and validation (changesets)
2. **GenServers** provide concurrent, stateful processes
3. **The GenServer holds an Ecto struct as its state** -- the struct is loaded from the database at initialization and serves as an in-memory cache
4. **Phoenix contexts** provide the public API, abstracting whether data comes from a GenServer or directly from Ecto

This creates a layered architecture:
```
Phoenix Controller
    -> Context module (public API)
        -> GenServer (in-memory state, read-fast path)
        -> Ecto Repo (persistence, write path)
```

### Is There a Standard Pattern?

**Yes, but it is ad-hoc in the sense that it is not enforced by the framework.** The standard community pattern is:

- Ecto schemas are pure data + validation. They know nothing about processes.
- GenServers wrap Ecto structs for runtime state. They use `DynamicSupervisor` + `Registry` for entity-per-process patterns.
- The database is the backup; the GenServer is the authoritative runtime source.

### Critical Anti-Pattern Discovered

A well-documented pitfall: routing ALL database access through GenServers creates bottlenecks. One developer reported pages taking 3 seconds to render because they "built a bottleneck by pushing all database access control to GenServers" -- defeating Ecto's connection pooling because all access happened through a single process.

**The lesson:** Use GenServers for entity-specific stateful operations, not as a universal data access layer. Read-heavy operations should bypass the GenServer and go directly to Ecto/database.

### Does the data model inherit from GenServer?

**No.** Ecto schemas use `use Ecto.Schema` (a compile-time macro). GenServers use `use GenServer`. They are completely independent. The GenServer holds an Ecto struct as state through composition, never inheritance.

**Sources:**
- [GenServer Elixir Documentation](https://hexdocs.pm/elixir/GenServer.html)
- [OTP as the Core of Your Application Part 1](https://akoutmos.com/post/actor-model-genserver-app/)
- [OTP as the Core of Your Application Part 2](https://akoutmos.com/post/actor-model-genserver-app-two/)
- [Elixir GenServer: Concurrent Stateful Process Implementation](https://www.curiosum.com/blog/what-is-elixir-genserver)
- [You May Not Need GenServers](https://pragtob.wordpress.com/2019/04/24/you-may-not-need-genservers-and-supervision-trees/)

---

## 4. Proto.Actor (.NET/Go/Kotlin)

**Confidence:** MEDIUM (official docs, but less detailed than Akka/Orleans)

### Protobuf as the Contract

Proto.Actor's defining characteristic: **Protobuf is the message format**. All messages between actors are defined as Protobuf messages. This is directly analogous to N3TX's JSON Schema as the contract between backend and frontend.

```protobuf
// Messages are plain Protobuf, no actor inheritance
message GetUser { string user_id = 1; }
message UserResponse { string name = 1; string email = 2; }

// Grain interface defined in Protobuf
service UserGrain {
  rpc GetUser(GetUser) returns (UserResponse);
}
```

The Protobuf definitions generate:
- Request/response classes (plain data)
- Base classes for grain logic (actor behavior)
- Client stubs for calling grains

### Actor State and Persistence

Proto.Actor persistence follows the same event-sourcing pattern as Akka:
- Events and snapshots are persisted
- State is reconstructed from events
- The persistence module supports three modes: event sourcing, snapshot-only, and event sourcing + snapshots

State is a separate data type. The actor receives messages (Protobuf types) and maintains state (any serializable type). The persistence layer handles serialization.

### Design Philosophy: "Pass Data, Not Objects"

Proto.Actor's explicit design principle: **"Serialization is an explicit concern, don't try to hide it. Protobuf all the way."** This means:
- Messages are always plain data (Protobuf-generated classes)
- No attempt to make actors look like regular objects
- The serialization boundary is visible and intentional

### Parallel to N3TX's JSON Schema

| Proto.Actor | N3TX |
|-------------|--------|
| Protobuf definitions | Python model definitions |
| Generated message classes | JSON Schema |
| gRPC transport | HTTP/REST transport |
| Protobuf serialization | JSON serialization |
| Grain interface (service) | Route generation |

The parallel is striking: both use a schema/contract definition to generate typed interfaces on both sides of a network boundary.

### Does the domain model inherit from the actor?

**No.** Protobuf messages are generated plain data classes. Grain behavior extends generated base classes. They are completely separate type hierarchies.

**Sources:**
- [Proto.Actor Documentation](https://proto.actor/)
- [Proto.Actor Go GitHub](https://github.com/asynkron/protoactor-go)
- [Proto.Actor .NET GitHub](https://github.com/asynkron/protoactor-dotnet)
- [Getting Started with Virtual Actors in .NET Using Proto.Actor](https://dev.to/actor-dev/getting-started-with-virtual-actors-grains-in-net-using-protoactor-2ij0)

---

## 5. Dapr (Microsoft)

**Confidence:** HIGH (official Dapr docs, Python SDK documentation)

### Dapr Actors vs State Management

Dapr provides two separate building blocks:
1. **State Management** -- key-value store for any service
2. **Actors** -- virtual actors with built-in state management

These are deliberately separate concerns. An actor uses the state management building block internally, but regular services can use state management without actors.

### Python SDK Pattern

```python
from dapr.actor import Actor, ActorInterface, actormethod

# INTERFACE: Defines the actor's public API
class MyActorInterface(ActorInterface):
    @actormethod(name="GetMyData")
    async def get_my_data(self) -> object: ...

    @actormethod(name="SetMyData")
    async def set_my_data(self, data: object) -> None: ...

# ACTOR: Inherits from Actor base class
class MyActor(Actor, MyActorInterface):
    async def get_my_data(self) -> object:
        has_value, val = await self._state_manager.try_get_state("mystate")
        return val if has_value else None

    async def set_my_data(self, data: object) -> None:
        await self._state_manager.set_state("mystate", data)
        await self._state_manager.save_state()
```

### State as Key-Value, Not Typed Object

Unlike Orleans (typed `IPersistentState<T>`) or Akka (typed state parameter), Dapr actors manage state through a **key-value API** (`self._state_manager`). State is stored and retrieved by string keys, with values being any serializable object. This is more flexible but less type-safe.

### Separation of CRUD and Actor Patterns

Dapr documentation explicitly advises: "CRUD-based data can often remain outside actors, while autonomous, behavior-rich components benefit from being implemented as actors." This aligns with the principle that not everything needs to be an actor.

### Does the domain model inherit from the actor?

**No.** The actor inherits from `Actor` base class. State is managed through `self._state_manager` as key-value pairs. Domain data is stored as plain serializable objects, not as part of the actor class hierarchy.

**Sources:**
- [Dapr Actors Overview](https://docs.dapr.io/developing-applications/building-blocks/actors/actors-overview/)
- [Dapr Python Actor SDK](https://docs.dapr.io/developing-applications/sdks/python/python-actor/)
- [Dapr State Management](https://docs.dapr.io/developing-applications/building-blocks/state-management/state-management-overview/)
- [Understanding Dapr Actors (Diagrid)](https://www.diagrid.io/blog/understanding-dapr-actors-for-scalable-workflows-and-ai-agents)

---

## 6. Python-Specific Actor Frameworks

**Confidence:** MEDIUM (official docs for Pykka/Thespian; community sources for Ray integration)

### Pykka

Pykka actors inherit from `ThreadingActor`. State is plain Python attributes on the actor instance. The proxy pattern allows external code to access actor attributes and methods asynchronously.

```python
import pykka

class Calculator(pykka.ThreadingActor):
    def __init__(self):
        super().__init__()
        self.count = 0  # State is just instance attributes

    def increment(self):
        self.count += 1
        return self.count

# Usage via proxy
ref = Calculator.start()
proxy = ref.proxy()
future = proxy.increment()  # Returns a future
```

**No data model integration.** Pykka has no concept of domain models, schemas, or persistence. State is just Python attributes. There is no mechanism to use Pydantic models as the state definition -- you would have to manually hold a Pydantic instance as an attribute.

### Thespian

Thespian actors receive messages that can be "anything that can be pickled." State is instance attributes. The framework focuses on distributed actor systems (multi-node) but has no data model concept.

```python
from thespian.actors import Actor

class Greeter(Actor):
    def receiveMessage(self, message, sender):
        if isinstance(message, str):
            self.send(sender, f"Hello, {message}!")
```

**No data model integration.** Same as Pykka -- pure actor framework with no ORM/schema layer.

### Ray

Ray takes a unique approach: the `@ray.remote` decorator turns **any Python class** into a remote actor. No base class required.

```python
import ray

@ray.remote
class Counter:
    def __init__(self):
        self.value = 0

    def increment(self):
        self.value += 1
        return self.value

# Or without decorator (preserves types for IDE):
Counter = ray.remote(Counter)
```

**Pydantic integration:** Ray has a complex relationship with Pydantic. As of 2025-2026, Ray supports Pydantic v2 but with some friction. You can use Pydantic models as fields on Ray actors, and Ray Serve (the serving layer) works with Pydantic for request/response validation. However, there is no built-in pattern for "define a Pydantic model, get a stateful actor." The integration is incidental, not architectural.

A Ray community discussion titled "Defining an actor with pydantic" (2022) suggests users wanted this but it was never formalized.

### Does any Python framework merge actors and data models?

**No.** None of the Python actor frameworks (Thespian, Pykka, Ray) have any concept of domain models, schemas, persistence, or ORM integration. They are pure concurrency/distribution frameworks. The data model is always whatever Python objects the developer puts inside the actor.

**This is the gap N3TX could fill:** a framework where the data model definition (Pydantic) drives both persistence AND actor behavior.

**Sources:**
- [Pykka Documentation](https://pykka.readthedocs.io/stable/)
- [Pykka Proxy Example](https://pykka.readthedocs.io/stable/examples/proxy/)
- [Thespian Documentation](https://thespianpy.com/doc/in_depth)
- [Ray Actors Documentation](https://docs.ray.io/en/latest/ray-core/actors.html)
- [Ray + Pydantic Discussion](https://discuss.ray.io/t/defining-an-actor-with-pydantic/1574)

---

## 7. Pattern Taxonomy

Based on all frameworks surveyed, five distinct patterns emerge for how actors relate to domain models:

### Pattern A: Actor-Contains-State (Composition)

**The actor holds a plain data object as an instance field.**

```
Actor {
    state: DomainModel    // Actor CONTAINS the model
    handle(cmd) -> ...    // Actor defines behavior
}
```

**Used by:** Akka (state type parameter), Elixir/GenServer (state term), Pykka (instance attributes), Ray (instance attributes)

**Characteristics:**
- Data model is a plain type (case class, struct, dict)
- Actor owns the lifecycle of the state
- State is serializable; actor is not
- Clean separation of concerns
- **Most common pattern overall**

### Pattern B: Actor-Wraps-State (Injection)

**State is injected into the actor, managed externally.**

```
Actor {
    @inject state: PersistentState<DomainModel>  // Injected
    handle(cmd) -> state.write()                 // Explicit persistence
}
```

**Used by:** Orleans (IPersistentState injection), Dapr (state manager)

**Characteristics:**
- State lifecycle managed by the framework, not the actor
- Multiple state objects per actor possible
- Persistence is explicit (call `WriteStateAsync()`)
- Better separation of state storage from actor logic
- **Best for systems with pluggable storage**

### Pattern C: Actor-IS-Entity (Conceptual DDD)

**The actor represents the domain entity. One actor per entity instance.**

```
// Conceptually: Actor IS the Customer
CustomerActor("customer-123") {
    state: CustomerData
    handle(ChangeName) -> persist(NameChanged)
}
```

**Used by:** Akka (in DDD style), Orleans (virtual actors), Proto.Actor (grains)

**Characteristics:**
- One actor instance per domain entity (child-per-entity pattern)
- Actor identity = entity identity
- The actor IS the entity's behavioral representation
- But the data is still a separate type inside the actor
- **Important nuance:** "IS" is conceptual identity, not class inheritance

### Pattern D: Actor-Agnostic-Entity (Adapter Layer)

**Domain objects know nothing about actors. An adapter bridges them.**

```
DomainModel { fields, validation, persistence }  // Knows nothing about actors
ActorAdapter { model: DomainModel }               // Bridges to actor system
```

**Used by:** Elixir/Phoenix (Ecto schemas know nothing about GenServers, contexts bridge them)

**Characteristics:**
- Clean dependency direction (actor depends on model, never reverse)
- Model is testable without actor system
- Adapter layer can be thin or thick
- **Best for adding actors to an existing model layer**

### Pattern E: Schema-Drives-Everything (Contract-First)

**A schema definition generates both the data model and the actor interface.**

```
Schema Definition (Protobuf, JSON Schema, etc.)
    -> Generated Data Classes (messages, state types)
    -> Generated Actor Interfaces (grain interfaces, routes)
    -> Runtime Behavior (developer fills in the logic)
```

**Used by:** Proto.Actor (Protobuf generates both), **N3TX (JSON Schema drives everything)**

**Characteristics:**
- Single source of truth for both data and behavior contracts
- Code generation reduces boilerplate
- Schema evolution is a first-class concern
- **Most aligned with N3TX's philosophy**

### Summary Matrix

| Pattern | Data Inherits Actor? | Actor Inherits Data? | Relationship |
|---------|---------------------|---------------------|-------------|
| A: Contains | No | No | Actor holds data as field |
| B: Wraps/Injection | No | No | Data injected into actor |
| C: IS-Entity | No | No | Conceptual identity, not inheritance |
| D: Agnostic | No | No | Adapter bridges two independent types |
| E: Schema-Driven | No | No | Schema generates both independently |

**Universal finding: NO framework uses inheritance between actors and domain models.** The relationship is always composition, injection, or adaptation.

---

## 8. What Went Wrong: Anti-Patterns and Pitfalls

### Anti-Pattern 1: The God Actor

**What:** Stuffing too much state and behavior into a single actor.

**Symptoms:**
- Actor class is hundreds/thousands of lines
- Multiple unrelated concerns in one actor
- State object grows to include everything about the entity

**From Dapr docs:** "If you find yourself cramming huge structures into an actor, it's often a sign that the actor is doing too much or that some data belongs in a separate database or service."

**Prevention:** Follow the single-responsibility principle. If an actor manages multiple state objects (like Orleans allows), that is a sign it might need to be split.

### Anti-Pattern 2: Serialization Tax

**What:** Excessive serialization overhead from copying data between actors.

**From multiple sources:** "While message passing simplifies concurrency, it can introduce overhead due to serialization and deserialization of messages, as well as network latency."

**Prevention:**
- Pass references (IDs, hrefs) instead of full objects between actors
- Use efficient serialization (Protobuf, MessagePack) not JSON for inter-actor communication
- Proto.Actor's explicit design principle: "Pass data, not objects"

**Relevance to N3TX:** N3TX already uses href arrays for FK relationships, which is the right pattern -- passing references rather than embedded objects.

### Anti-Pattern 3: GenServer-as-Database-Proxy Bottleneck

**What:** Routing ALL data access through GenServer actors, creating a single-threaded bottleneck.

**From Elixir community:** Pushing all database access through GenServers "defeated Ecto connection pools because all access happened through a single process" -- pages took 3 seconds to render.

**Prevention:** Use actors for stateful, entity-specific operations. Read-heavy queries should bypass actors and go directly to the storage layer.

**Relevance to N3TX:** N3TX's `register_routes()` already serves data directly from storage (SQLite), not through an actor system. The frontend actor system (Matrix/N3TX) handles UI state and message routing. This is the correct separation.

### Anti-Pattern 4: Testing Opacity

**What:** Actor behavior is asynchronous and independent, making debugging difficult. "It's not simply a matter of putting some breakpoints in code and running the debugger."

**Prevention:**
- Make state transitions deterministic (pure functions from state + event -> new state)
- Test state transitions independently of the actor system
- Use test probes / test kits (Akka TestKit, Pykka ThreadingFuture)
- Log message flows for debugging

### Anti-Pattern 5: Conflating Actor Identity with Database Identity

**What:** Assuming every database row should be an actor, or every actor should have a database row.

**Prevention:**
- Actors represent behavioral entities that need concurrent access protection
- Database rows represent persistent data
- Not all data needs actor protection; not all actors need persistence
- The mapping between actors and database entities should be intentional, not automatic

### Anti-Pattern 6: Anemic Actor (Inverted Anemic Domain Model)

**What:** Actors that are just message routers with no business logic, delegating everything to the data model.

**Prevention:** If the actor has no behavior beyond CRUD delegation, it might not need to be an actor. Use actors when you need: concurrency control, stateful interactions, event-driven behavior, or supervision hierarchies.

**Sources:**
- [Design Patterns for Building Actor-Based Systems](https://www.geeksforgeeks.org/system-design/design-patterns-for-building-actor-based-systems/)
- [Actor Model in Distributed Systems](https://www.geeksforgeeks.org/system-design/actor-model-in-distributed-systems/)
- [Actix's Actor Model: Panacea or Pitfall?](https://leapcell.io/blog/actix-s-actor-model-a-web-request-panacea-or-pitfall)
- [Akka Serialization](https://getakka.net/articles/serialization/serialization.html)

---

## 9. Implications for N3TX

### Current N3TX Architecture

N3TX already has both sides of this equation:

**Backend (Python):**
- `ProtoModel` extends `PydanticBaseModel` -- pure data model with schema generation
- `StorableMixin` is injected for persistence -- composition, not inheritance
- No actor system on the backend (routes are plain FastAPI handlers)

**Frontend (JavaScript):**
- `Actor` is the base class for the message-passing system
- `N3TX.js` creates `DynamicClass` from JSON Schema -- schema-driven entity creation
- `TT` (Transfer Type) extends `Actor` -- the entity IS an actor
- `Matrix` is the root actor / message bus

### N3TX's Current Pattern

N3TX already follows **Pattern E (Schema-Drives-Everything)** with elements of **Pattern A (Actor-Contains-State)** on the frontend:

```
Python ProtoModel (data + schema)
    -> JSON Schema (contract)
        -> DynamicClass (frontend actor-entity hybrid)
            -> TT extends Actor (message-capable entity)
```

The frontend `DynamicClass` created by `prototype()` is interesting: it creates a class that has both data properties (from schema) and actor capabilities (from TT/Actor). This is the closest any surveyed system comes to merging actors and data models -- but it does it through **runtime composition** (building the class from schema), not through class inheritance of data from actor.

### What the Industry Precedents Suggest

1. **The backend model should NOT become an actor.** ProtoModel should remain a pure Pydantic BaseModel. Adding actor behavior to the Python model class would violate every surveyed framework's design. If N3TX ever adds backend actors (e.g., for real-time features, WebSocket management, background tasks), those actors should CONTAIN ProtoModel instances, not BE ProtoModel instances.

2. **The frontend actor-entity hybrid is fine.** The DynamicClass pattern (building actor-capable entities from schema at runtime) is a novel approach that is consistent with Pattern E. Since the frontend DynamicClass is not a persisted model (it is a runtime representation), merging actor and data capabilities makes sense -- it is analogous to Orleans' virtual actor where the grain IS the entity at runtime.

3. **JSON Schema as universal contract is validated.** Proto.Actor's Protobuf and N3TX's JSON Schema serve identical architectural roles: a single definition that generates typed interfaces on both sides of a boundary. This is a strong and well-validated pattern.

4. **Href arrays are the right FK pattern.** Passing references (URLs/IDs) instead of embedded objects mirrors Proto.Actor's "pass data, not objects" principle and avoids the serialization tax anti-pattern.

5. **If adding Python-side actors, use the Adapter pattern.** The cleanest approach (Pattern D) would be:
   ```python
   # ProtoModel stays pure
   class Product(ProtoModel):
       name: str
       price: float

   # Actor wraps/manages the model (hypothetical)
   class ProductActor(Actor):
       def __init__(self, product: Product):
           self.product = product

       def handle_price_change(self, new_price):
           self.product.price = new_price
           self.product.save()
   ```

6. **Not everything needs to be an actor.** N3TX's CRUD routes work well as stateless request handlers. Actor patterns should be reserved for stateful, concurrent, or event-driven scenarios (real-time updates, collaborative editing, pub/sub).

---

## Appendix: Cross-Framework Comparison Table

| Framework | Language | Data Model Type | Actor Base Class | Relationship | State Persistence | Schema/Contract |
|-----------|----------|----------------|-----------------|-------------|-------------------|----------------|
| Akka | Scala/Java | Case class | `Behavior[Cmd]` / `AbstractActor` | Contains (type param) | Event Sourcing | Serialization formats |
| Orleans | C# | POCO class | `Grain` | Injection (`IPersistentState<T>`) | Explicit write | Interface contracts |
| Erlang/OTP | Erlang/Elixir | Any term / Ecto schema | `GenServer` (use macro) | Contains (init state) | Manual / Ecto Repo | None (ad-hoc) |
| Proto.Actor | .NET/Go/Kotlin | Protobuf message | Generated base class | Contains / Event Sourcing | Event Sourcing | Protobuf definitions |
| Dapr | Any (Python shown) | Any serializable | `Actor` base class | Key-value state manager | Automatic / explicit | Interface + annotations |
| Pykka | Python | Any Python object | `ThreadingActor` | Instance attributes | None built-in | None |
| Thespian | Python | Any picklable | `Actor` | Instance attributes | None built-in | None |
| Ray | Python | Any Python object | None (decorator) | Instance attributes | None built-in | None |
| **N3TX** | **Python + JS** | **Pydantic BaseModel** | **Actor (JS)** | **Schema-driven DynamicClass** | **StorableMixin + SQLite** | **JSON Schema** |

---

## Confidence Assessment

| Finding | Confidence | Basis |
|---------|-----------|-------|
| No framework uses inheritance between actor and data model | HIGH | Verified across 8+ frameworks, all official docs |
| Five pattern taxonomy (A-E) | HIGH | Derived from primary sources across all frameworks |
| Akka Event Sourcing separates Command/Event/State | HIGH | Official Akka documentation |
| Orleans IPersistentState injection pattern | HIGH | Official Microsoft Learn docs (Feb 2026) |
| Elixir GenServer-Ecto separation | HIGH | Official docs + well-documented community patterns |
| Proto.Actor Protobuf parallel to JSON Schema | MEDIUM | Inferred from documentation, not explicitly stated by Proto.Actor |
| Python frameworks lack data model integration | HIGH | Verified in Pykka, Thespian, Ray documentation |
| Anti-pattern catalog | MEDIUM | Aggregated from multiple community sources, not all from primary docs |
| N3TX implications/recommendations | MEDIUM | Derived analysis, not directly validated by external sources |
