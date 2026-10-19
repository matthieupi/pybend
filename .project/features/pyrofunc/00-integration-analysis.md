# Pyrofunc x N3TX Actor — Integration Analysis

**Date:** 2026-03-08
**Status:** Vision / Exploration
**Repo:** https://github.com/matthieupi/pyrofunc
**Package name:** `protofunc` (Monad, Functor, functor, staticfunctor, MonadWithLogs)

---

## Context

Pyrofunc is a Python library for composable, type-safe data transformation
pipelines using functional programming concepts. N3TX has an Actor module
for async message-passing with routing, interceptors, and lifecycle.

Both systems solve the **same structural problem** at different scales:
transforming data through a sequence of typed operations. This document
analyzes the fundamental parallel and proposes three distinct integration
architectures, each with a different center of gravity.

## The Fundamental Parallel

Strip away the names and both systems have identical bones:

| Concept | Pyrofunc | N3TX Actor |
|---|---|---|
| **Wrapped value** | `Monad.__value__` | `TX.data` |
| **Type tag** | `Monad.__dtype__` | `TX.name` |
| **Execution history** | `Monad.__pre__`, `MonadWithLogs.__logs__` | `TX.meta` |
| **Typed transformation** | `Functor.__exec__(value) -> value` | `handler(data, tx) -> result` |
| **Composition** | `f >> g` -> `CompositeFunctor` | `_run_interceptors([f, g], tx)` |
| **Short-circuit** | *(planned: Either monad)* | `tx.is_error` -> skip remaining |
| **Application** | `Monad(5) \| Add(3)` | `await actor.inbox(tx)` |
| **Identity/Address** | *(none)* | `Actor.addr`, routing tree |
| **Async** | *(none)* | `async inbox/handler/send` |
| **Type checking** | Composition-time via annotations | *(none -- runtime errors)* |

Neither system is complete on its own. Pyrofunc has type-safe composition but
no routing, no async, no identity. Actors have routing, async, and lifecycle
but no composition syntax, no type safety on chains.

The gap in each is exactly what the other provides.

## Propositions

Three integration architectures are proposed, each exploring a different
center of gravity for the unified system:

1. **[Reactive](./01-proposition-reactive.md)** -- Actor IS Functor, TX IS Monad. Compose like functors, execute like actors.
2. **[Journey](./02-proposition-journey.md)** -- TX carries its own processing plan. The message knows its own destiny.
3. **[Mesh](./03-proposition-mesh.md)** -- The wiring graph IS the program. Components + connections = application.

### Quick Comparison

| | Reactive | Journey | Mesh |
|---|---|---|---|
| **Core metaphor** | Railroad tracks | Self-driving car | Circuit board |
| **The program is** | The composed pipeline | The message's plan | The wiring graph |
| **Primary operator** | `>>` (compose) | `tx.through()` (plan) | `flow()` / `wire()` (connect) |
| **Who controls processing?** | The pipeline (actor-side) | The message (sender-side) | The topology (graph-side) |
| **Structure** | Linear chain | Carried sequence | Arbitrary graph |
| **Unique strength** | Type-safe linear composition | Self-documenting, replayable, portable | Visual, shared components, non-linear |
| **Best for** | Clean processing stages | Distributed/cross-system, audit trails | Complex applications with many operations |

### What Each Cannot Do Alone

- **Reactive** can't do fan-out, conditional branching, or shared components across pipelines
- **Journey** can't do topology-level reasoning, shared components, or visual introspection
- **Mesh** can't do sender-defined processing, cross-system portability, or replay from checkpoint

### They Are Not Mutually Exclusive

The deepest version combines all three:

```python
# Mesh provides the topology (Prop 3)
products = Mesh('products')
products.node('validate', Validate(ProductSchema))
products.node('persist',  Persist(sqlite))

# Flows are composed pipelines (Prop 1)
products.flow('create', Validate >> Authorize >> Persist >> Notify)

# Messages carry journey metadata (Prop 2)
tx = TX.journey(data={...}, through='products/create')
result = await matrix.dispatch(tx)
result.journal  # full audit trail
```

Each proposition highlights a different center of gravity -- where the
intelligence lives, where the programmer's attention goes, what the system
optimizes for.
