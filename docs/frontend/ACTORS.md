# Browser actors and NTT entities

This reference describes the JavaScript runtime, not the Python actor package.
Start with [frontend architecture](ARCHITECTURE.md) for app setup.

## Runtime map

| Module in core `static/core/` | Responsibility |
|---|---|
| `Actor.js` (default export) | Addressed inbox/send and class/instance wiring |
| `Matrix.js` (`Matrix`, `matrix`) | Singleton local router and network gateway |
| `TX.js` (default or named `TX`) | Message envelope |
| `Observable.js` (default export) | Signal/property subscriptions |
| `NTT.js` (`NTT`) | Runtime schema registry, entity base, internal DynamicClass factory |
| `Router.js` | Navigation state, separate from entity state |
| `Component.js` | HTMLElement/actor bridge |

```text
matrix singleton
  +-- NTT (schema registry)
  +-- Issue (runtime DynamicClass)
  |     +-- "1", "2", ... (cached entity actors)
  +-- Component (bridge and registered component instances)
  +-- Router / named router instances
  +-- remote NetworkAdapter -> HTTP or configured WebSocket
```

## Actor and Matrix

`Actor.subclass(Type, ...Mixins)` equips a type with static/instance routing and
applies mixins exposing `apply(Type)`. Framework initialization already wires
Component; do not repeat it in visual subclasses. Importing Matrix creates the
root singleton; do not instantiate a second root for an app page.

| Existing surface | Meaning |
|---|---|
| `actor.addr`, `actor.children` | Routing identity and child registry |
| `actor.send(event)`, `actor.inbox(event)` | Send/receive a TX-shaped message |
| `actor.register(child)`, `actor.spawn(addr,Type,...args)` | Child management |
| `Actor.root`, `Actor.registerRoot(actor)` | Root identity/initialization |
| `Actor.isActor(value)` | Actor marker/instance check |
| `matrix.dispatch(event)`, `matrix.inbox(event)` | Local routing entry |
| `matrix.has(addr)` | First-segment membership, not remote existence |

Type-level send first checks local children, then its own address prefix, then
prefixes the source and delegates to Matrix. Matrix routes known first segments
locally and unknown targets through transport. Handler dispatch uses the message
name: `this[tx.name](tx.data, tx)`. Runtime handlers conventionally use uppercase
names; do not confuse that convention with lower-case domain method names.
Missing handlers are logged/ignored, and caught handler failures are logged;
`send()` is not an acknowledged RPC promise.

## NTT registry and DynamicClass

```text
registry entry absent -> queue attachment and request schema
registry entry null   -> schema already in flight; queue
registry entry class  -> attach to existing type/entity
```

`SCHEMA` registers compatible `$defs`, creates the main DynamicClass when absent,
and replays waiting callbacks/TXs. Classes contain schema accessors, method proxies,
an instance Map, and collection handlers. Consumers initiate reads; merely loading
a schema does not load the collection.

| Surface | Contract |
|---|---|
| `NTT.get('Issue')` | Loaded DynamicClass or undefined |
| `NTT.get('Issue/1')` | Cached entity or undefined; no network request |
| `NTT.has(model)` | Registry membership, including a pending null entry |
| `NTT.attach(model,callback)` | Callback when class is ready; return may be undefined while pending |
| `DC.schema`, `DC.href` | Runtime schema and class-name API base |
| `DC.instances` / `DC.children` | Same Map, keyed by string IDs |
| `DC.call(method,data={},meta={})` | Dispatch collection TX; target starts as `/Model/_` |
| `DC.observe('UPDATE',callback)` | Address-list changes; returns unsubscribe |
| `entity.value`, `entity.schema`, `entity.href` | Values, schema and authoritative entity URL |
| `entity.pull()` | Refresh entity, returns the entity immediately |
| `entity.call(method,data={},meta={})` | Dispatch member TX; no persistence promise |

### Read the model without duplicating it

Browser-module example for a registered readable Issue model:

```javascript
import { NTT } from '/core/NTT.js';

let stopObserving;
const stopAttaching = NTT.attach('Issue', Issue => {
  stopObserving?.();
  console.log('Fields:', Object.keys(Issue.schema.properties));
  stopObserving = Issue.observe('UPDATE', addresses => {
    console.log(addresses.map(address => NTT.get(address)?.value));
  });
  Issue.call('READ', {limit: 20, offset: 0});
});
window.addEventListener('pagehide', () => {
  stopObserving?.();
  stopAttaching?.();
}, {once: true});
```

Pending attach does not currently return a universal cancellation handle. Prefer
component lifecycle helpers for mounted UI and guard app callbacks that outlive
their host. `NTT.attach` readiness must not be treated as record readiness.

## Entity identity and state

`DC.href` is derived from schema `$id`'s API base and model name. Collection reads
append `/_`; member URLs append an ID. Responses' `$id` take precedence for entity
hrefs. `value` exposes `$schema` and `$id` for self-description.

`READ` upserts cached instances and preserves object identity for existing IDs.
Collection responses retain pagination metadata and notify all cached addresses;
the cache is not a separate filtered-result set per list. Missing member ATTACHes
queue until an individual READ succeeds. Failed reads must not be interpreted as
an empty successful collection.

Local hydrated child objects can be registered in related classes without changing
their flat identity. Explicit pointer handling differs from owned collections;
see [model relationships](../MODELS.md), not older nested-URL examples.

Field setters provide limited runtime type/readOnly checks, not complete Pydantic
validation, and do not persist automatically. For domain actions prefer
`entity.call(methodName, payload, {inbox: '_response_'})` or `ntx-method`, rather
than assuming generated positional proxies provide a complete typed RPC API.
`_response_` applies recognized toggle results, updates same-entity responses, or
pulls authoritative state for ambiguous/child responses.

## Observable

| Method | Behavior |
|---|---|
| `signal(callback, wait=false)` | Subscribe to entity signal; immediate callback unless waiting |
| `signal()` | Notify signal callbacks |
| `observe(property,callback)` | Subscribe to a property; returns unsubscribe |
| `notify(property,newValue,oldValue)` | Notify property observers |

DynamicClass has explicit class-level signal/observe implementations in addition
to instance Observable behavior. Unsubscribe during cleanup. Local signals are
not a database transaction, rollback mechanism, or remote push subscription.

## Sources

[Actor](../../packages/n3tx-core/src/n3tx_core/static/core/Actor.js) ·
[Matrix](../../packages/n3tx-core/src/n3tx_core/static/core/Matrix.js) ·
[NTT](../../packages/n3tx-core/src/n3tx_core/static/core/NTT.js) ·
[Observable](../../packages/n3tx-core/src/n3tx_core/static/core/Observable.js) ·
[schema bootstrap tests](../../tests/frontend/tests/integration/schema-bootstrap.test.js).
