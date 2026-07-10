# Actor System Reference

Detailed documentation of each class in the Actor/Matrix system.

## Table of Contents

1. [Actor](#actor)
2. [Matrix](#matrix)
3. [Router](#router)
4. [TX](#tx)
5. [Observable](#observable)
6. [TT (Transfer Type)](#tt-transfer-type)
7. [N3TX (Named Transfer Type)](#ntx-named-transfer-type)
8. [DynamicClass (DynClass)](#dynamicclass-dynclass)

---

## Actor

**File:** `core/Actor.js`

The base class for all actors in the system. Provides hierarchical addressing, message passing, child management, and a metaclass helper (`subclass()`) that wires up any class to participate in the Actor system.

### Instance Properties

| Property | Type | Description |
|----------|------|-------------|
| `addr` | `string` | Unique address (set in constructor, immutable) |
| `children` | `Map<string, Actor>` | Child actors spawned by this instance |

### Instance Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `inbox(event)` | `event: object\|TX` | Receives a message. Dispatches to `this[event.name](data, tx)` if the target matches this actor's address. Otherwise forwards via `send()`. |
| `send(event)` | `event: object\|TX` | Delegates to `this.constructor.send()` (static routing). |
| `register(actor)` | `actor: Actor` | Adds actor to `this.children` map. |
| `spawn(addr, ActorClass, ...args)` | | Creates a child actor, registers it, returns it. |

### Static Properties / Methods

| Member | Description |
|--------|-------------|
| `Actor.root` | The global root actor (Matrix singleton). Set once via `Actor.registerRoot()`. |
| `Actor.registerRoot(actor)` | Sets the global root. Throws if already set. |
| `Actor.isActor(obj)` | Returns `true` if obj is an Actor instance or has `__TypeActor` flag. |

### Static Routing: `Actor._send(event)`

The core routing algorithm. Called in the context of a concrete subclass (e.g., `Component.send()` calls `Actor._send.call(Component, event)`).

```
Given tx.target = "A/B/C", parse into [targetParent, targetChild, childTarget]:

Case 1: targetParent is in this.children
  -> Route directly to that child's inbox

Case 2: targetParent === this.addr (e.g., "Component/child-123")
  -> Strip prefix, route to children[targetChild]

Case 3: Neither match
  -> Prefix tx.source with this.addr
  -> Bubble to ROOT_ACTOR.inbox() (the Matrix)
```

### Static Dispatch: `Actor._inbox(event)`

```
If tx.target matches this.addr:
  -> Call this[tx.name](tx.data, tx)  (method lookup by event name)
  -> Falls back to prototype chain lookup
  -> Throws if no handler found

If tx.target doesn't match:
  -> Forward via this.send(event)
```

### `Actor.subclass(ChildClass, ...Mixins)`

The metaclass helper. Mutates `ChildClass` to add Actor capabilities:

**Static additions:**
- `addr` getter (returns `ChildClass.name`)
- `_children` map (own, not inherited)
- `children` getter
- `send(event)` -> `Actor._send.call(Type, event)`
- `inbox(event)` -> `Actor._inbox.call(Type, event)`
- `register(actor)` -> `Actor._register.call(Type, actor)`
- Registers the class in `ROOT_ACTOR.children` (if Matrix is initialized)

**Instance additions:**
- `_children` map on prototype
- `children` getter
- `send(event)` -> `this.constructor.send(event)`
- `inbox(event)` -> `Actor._inbox.call(this, event)`

**Mixin application:**
- Each mixin must have a static `apply(Base)` method
- Called in order: `Mixin.apply(ChildClass)`
- Example: `Actor.subclass(N3TX, Observable)` adds signal/observe/notify to N3TX

**Idempotent:** If `ChildClass.__TypeActor` is already set, skips silently.

---

## Matrix

**File:** `core/Matrix.js`

The singleton root actor. All messages that cannot be resolved locally bubble up here. The Matrix routes locally or delegates to the NetworkAdapter for remote calls.

### Construction

```javascript
Actor.subclass(Matrix)
export const matrix = new Matrix("matrix://root");
```

On construction:
1. Calls `Actor.registerRoot(this)` (sets global root)
2. Creates `this.remote = new NetworkAdapter(this, url)`

### Instance Methods

| Method | Description |
|--------|-------------|
| `inbox(event)` | Main routing hub. See routing logic below. |
| `dispatch(event)` | Alias for `inbox(event)`. |
| `has(addr)` | Checks if the first segment of `addr` is in `children`. |
| `connect(source, target)` | Handles CONNECT events. Parses target into class/addr, routes to the target class's inbox. |

### Routing Logic (`inbox`)

```
1. If tx.name === CONNECT:
   -> this.connect(source, target)

2. If tx.target === this.addr:
   -> Error (Matrix doesn't message itself)

3. If first segment of tx.target is in this.children:
   -> Forward to that child's inbox

4. Otherwise:
   -> this.remote.send(tx)  (send to backend via HTTP/WS)
```

### Children

The Matrix's children map contains **classes and instances**:
- `N3TX` (registered via `Actor.subclass(N3TX)`)
- `Component` (registered via `Actor.subclass(Component)`)
- `TT` (registered via `Actor.subclass(TT)`)
- `Router` (registered via `Actor.subclass(Router)`)
- Each DynClass (e.g., `Product`) is registered when `Actor.subclass(DynClass)` runs inside `prototype()`
- Each Router instance (e.g., `"main"`) is registered via `matrix.register(this)` in the Router constructor

This means a message targeting `"N3TX"` routes to `N3TX.inbox()` (the static method), which handles it at the class level. A message targeting `"Product"` routes to the DynClass's static `inbox()`. A message targeting `"main"` routes to the Router instance's `inbox()`.

---

## Router

**File:** `core/Router.js`

Pure navigation state Actor. Manages the current route, a history stack, and optional `location.hash` synchronization. No DOM — view management is the ntx-router component's responsibility.

### Construction

```javascript
Actor.subclass(Router, Observable)

const router = new Router('main', { hash: true });
```

On construction:
1. Calls `super(addr)` (Actor identity)
2. Calls `matrix.register(this)` (registered as a Matrix child, routable by addr)
3. If `hash: true`, listens for `hashchange` and reads initial hash
4. Registers in module-level `routers` Map for lookup via `getRouter(addr)`

### Instance Properties

| Property | Type | Description |
|----------|------|-------------|
| `current` | `string\|object\|null` | Current route data. `null` = home. |
| `canGoBack` | `boolean` | Whether the history stack has entries. |

### Private State

| Property | Type | Description |
|----------|------|-------------|
| `#current` | `any` | Current route data. |
| `#stack` | `Array` | History stack (previous routes, most recent last). |
| `#hashSync` | `boolean` | Whether to sync string routes to `location.hash`. |

### TX Handlers

| Handler | Data | Behavior |
|---------|------|----------|
| `NAVIGATE(data, tx)` | `string` or `object` | Dedup check (identity + deep equality for objects). Push old route to `#stack`. Set `#current = data`. Update hash if syncing. `notify('route', new, old)`. |
| `BACK(data, tx)` | (ignored) | Guard `canGoBack`. Pop `#stack`. Set `#current = popped`. Update hash. `notify('route', new, old)`. |

### Observable

```javascript
router.observe('route', (newRoute, oldRoute) => {
    console.log('Navigated:', oldRoute, '->', newRoute);
});
```

The `'route'` property is notified on every NAVIGATE and BACK. Callbacks receive `(newValue, oldValue, propertyName, actor)` per the Observable protocol.

### Hash Sync

| Route type | Hash behavior |
|------------|---------------|
| String (`"Product/3"`) | `location.hash = "Product/3"` |
| Object (`{ tag, attrs }`) | No hash representation (programmatic only) |
| `null` (home) | Hash cleared via `history.replaceState` |
| Browser back/forward | `hashchange` triggers `#fromHash()` → updates state + notifies |

### Registry

```javascript
import { getRouter } from './core/Router.js';
const router = getRouter('main');
```

### Routing Path

Router instances are registered in the Matrix's children map via `matrix.register(this)`. Messages targeting the Router's addr (e.g., `"main"`) are routed by the Matrix to the Router's `inbox`, which dispatches to `NAVIGATE` or `BACK`.

### Mixins Applied

```javascript
Actor.subclass(Router, Observable)  // Gets full actor wiring + signal/observe/notify
```

---

## TX

**File:** `core/TX.js`

The transaction/message envelope. Every message in the system is a TX or a plain object with TX fields.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `string` | Event name / method to invoke (e.g., "ATTACH", "READ", "SCHEMA") |
| `source` | `string` | Sender's address |
| `target` | `string` | Recipient's address (can be a class name, instance addr, or URL) |
| `data` | `any` | Payload |
| `meta` | `object` | Metadata (e.g., `{remote: true}`, `{inbox: 'UPDATE'}`) |
| `tst` | `number` | Timestamp (Date.now()) |
| `hash` | `string` | Deterministic hash of the message content |

### Methods

| Method | Description |
|--------|-------------|
| `repr()` | Returns a plain object copy (for serialization / inbox dispatch). |
| `str()` | Returns JSON string. |
| `TX.fromString(str)` | Static factory from JSON string. |

### Event Subclasses

Defined but mostly unused in current code:
- `ConnectEvent(source, target)` - name: CONNECT
- `ReadEvent(source, target)` - name: READ
- Plus `EnableEvent`, `DisableEvent`, `UpdateEvent`, `GetEvent`, `DescribeEvent`

### Event Names (config.E)

All event names are defined in `config.js` under `config.E`. Both lowercase and uppercase keys map to uppercase values:

```
CONNECT, ENABLE, DISABLE, UPDATE, GET, DESCRIBE, CONNECTED, SCHEMA,
CREATE, READ, DELETE, EVOLVE, COMMIT, ROLLBACK, SUBSCRIBE, OBSERVE,
LOAD, ERROR, PING, PONG, HEARTBEAT, LOGIN, LOGOUT, REGISTER, NOTIFY, ALERT,
SELECT, NAVIGATE, BACK
```

---

## Observable

**File:** `core/Observable.js`

A mixin that adds pub/sub reactivity to any Actor subclass. Applied via:

```javascript
Actor.subclass(N3TX, Observable)  // N3TX instances get signal/observe/notify
```

### Applied Methods (on prototype)

| Method | Signature | Description |
|--------|-----------|-------------|
| `signal(callback?, wait?)` | `callback: fn, wait: bool` | Without args: fires all registered callbacks with `this`. With callback: registers it. If `wait=false` (default), calls it immediately. Returns unsubscribe function. |
| `observe(property, callback)` | `property: string, callback: fn` | Registers a callback for a named property. Returns unsubscribe function. |
| `notify(property, newValue, oldValue)` | | Fires all callbacks registered via `observe()` for the given property. |

### Internal Storage

Uses instance properties (not private fields, since it's a mixin):
- `this.__signals` - `Set<Function>` for signal() callbacks
- `this.__observers` - `Map<string, Set<Function>>` for observe() callbacks
- `this._initObservable()` - lazy initializer, called by each method

### Important: Instance vs. Static Observable

`Observable.apply(Base)` only adds methods to `Base.prototype` (instance-level). For DynClass, static-level Observable methods (`signal`, `observe`) are added **manually** inside `prototype()` because:
- DynClass needs to be observable at the **class** level (components subscribe to the class itself)
- `Observable.apply` doesn't handle static properties

---

## TT (Transfer Type)

**File:** `core/N3TX.js` (within the same module)

Base class for data actors. Extends Actor with an `href` (remote endpoint URL) and a watcher notification pattern.

### Instance Properties

| Property | Type | Description |
|----------|------|-------------|
| `href` | `string` | Remote endpoint URL. Validated as URL on set. |
| `#watchers` | `Set<string>` | Addresses of actors watching this TT for changes. |

### Instance Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `watch(addr, immediate?)` | `addr: string, immediate: bool=true` | Adds `addr` to watchers. If `immediate` and `this.value` exists, sends UPDATE to the watcher immediately. |
| `notify(value?)` | `value: any` | Sends UPDATE TX to all watchers. If value is provided, sends it directly. Otherwise maps `this.value` children to their addresses. |
| `call(method, data?, meta?)` | | Sends a TX with `name=method`, `source=this.addr`, `target=this.href`, triggering a remote call via the network. |
| `ATTACH(data, tx)` | | Default ATTACH handler: calls `this.watch(tx.source)`. |

### Mixins Applied

```javascript
Actor.subclass(TT)  // No Observable - TT has its own notify
```

---

## N3TX (Named Transfer Type)

**File:** `core/N3TX.js`

N3TX serves a **dual role**: it is both the **type registry** (static level) and the **entity base class** (instance level). After the PTT merge, N3TX absorbed all of PTT's registry and routing responsibilities.

### Static Level: Type Registry

The static side of N3TX manages DynClass registration, the null-pointer bootstrap, and the universal ATTACH router.

#### Static State

| Property | Type | Description |
|----------|------|-------------|
| `N3TX.#prototypes` | `Map<string, DynClass\|null>` | Registry of all DynClass types. Three states per key: `undefined` (never seen), `null` (schema in flight), `DynClass` (ready). |
| `N3TX.#waiting` | `Map<string, Array>` | Queued TXs and attach callbacks for models whose schema is still in flight. |

#### Static Methods

| Method | Description |
|--------|-------------|
| `N3TX.has(addr)` | Checks if a DynClass is registered for the given model name. |
| `N3TX.get(addr)` | **Dual lookup:** `N3TX.get("Product")` returns DynClass. `N3TX.get("Product/1")` returns N3TX instance. |
| `N3TX.attach(addr, callback)` | Imperative attach with callback. If DynClass exists, fires immediately via `signal()`. If `null` (in flight), queues callback. If `undefined` (never seen), bootstraps schema fetch and queues. |
| `N3TX.ATTACH(data, tx)` | **Universal ATTACH router.** Handles both type-level (`"Product"`) and instance-level (`"Product/1"`) ATTACHes. Routes to DynClass if ready, queues if in flight, bootstraps if never seen. |
| `N3TX.SCHEMA(data, tx)` | **Bootstrap completion handler.** Receives schema from backend, creates DynClass via `prototype()`, stores in `#prototypes`, replays queued messages, triggers initial READ. Also registers `$defs` nested schemas as additional DynClasses. |
| `N3TX.#replayWaiting(addr, DynClass)` | Internal: replays queued TXs and attach callbacks for a model once its DynClass is ready. |

#### Null Pointer Bootstrap

The three-state pattern in `#prototypes` prevents duplicate schema fetches:

```
N3TX.#prototypes.get("Product"):
  undefined  → Never seen → Set null, fetch schema, queue TX
  null       → Schema in flight → Queue TX (will replay when DynClass arrives)
  DynClass   → Ready → Forward TX directly to DynClass
```

This replaces the old PTT lifecycle where a PTT instance existed in a half-initialized state before its schema arrived.

### Instance Level: Entity Data

Each N3TX instance represents a single entity (e.g., Product #1).

#### Instance State

| Property | Type | Description |
|----------|------|-------------|
| `#proto` | `object` | Reference to the DynClass (set via `define()`). |
| `#data` | `object` | The entity's current data. |
| `#meta` | `object` | Metadata (placeholder for future state management). |

#### Instance Methods

| Method | Description |
|--------|-------------|
| `get value()` | Returns `#data`. |
| `set value(val)` | Sets `#data`, calls `signal()`. |
| `get proto()` | Returns `#proto`. |
| `get schema()` | Returns `this.constructor._schema` (from the DynClass). |
| `define(proto)` | Links this N3TX to a DynClass and sets href. |
| `describe(proto, data)` | Calls `define()` + `update()`. |
| `update(data)` | Merges data into value via spread. |
| `pull()` | Sends READ call to backend for this specific entity. |
| `ATTACH(data, event)` | Registers the sender as a watcher (non-immediate), then sends DESCRIBE back with schema + data. |
| `UPDATE(data, event)` | Updates local data. If the event didn't come from backend (source doesn't start with `http`), forwards the update to the backend. This is the **optimistic update** flow. |
| `toJSON()` | Serializes addr, href, data, meta. |

#### Static Instance Handlers

| Method | Description |
|--------|-------------|
| `N3TX.READ(data)` | Static handler: updates the N3TX instance with received data. |
| `N3TX.UPDATE(data)` | Static handler: updates or creates instances from data entries. |

### Mixins Applied

```javascript
Actor.subclass(N3TX, Observable)  // N3TX gets signal/observe/notify at instance level
```

---

## DynamicClass (DynClass)

**File:** `core/N3TX.js` (`prototype()` function)

When `N3TX.SCHEMA()` receives a model's schema from the backend, it calls `prototype(addr, schema, href)` to generate a runtime N3TX subclass. The DynClass **is** the type: it holds the schema, manages instances, handles CRUD, and provides Observable reactivity at the class level.

DynClasses are **born complete** — they never exist in a half-initialized state. The `prototype()` function returns a fully wired class with schema properties, methods, static CRUD handlers, and Actor/Observable integration.

### `prototype(addr, schema, href)` — What It Does

```javascript
function prototype(addr, schema, href) {
  // 1. Create DynClass extending N3TX
  const DynamicClass = class extends N3TX { ... }

  // 2. Set class name to addr (e.g., "Product")
  // 3. Store static _schema reference
  // 4. Initialize static state (_watchers, _pendingAttaches, __signals, __observers)

  // 5. For each schema property, define getter/setter on prototype:
  //    - getter: returns this.value[field]
  //    - setter: validates type, validates readOnly, updates value, calls notify()
  //    - Stores field labels for UI

  // 6. For each schema method, define prototype method:
  //    - Validates required parameters
  //    - Validates $ref parameter types
  //    - Calls this.call(method, args) for remote invocation

  // 7. Add static type-level methods (call, signal, observe, ATTACH, READ, UPDATE)
  // 8. Apply Actor.subclass(DynamicClass, Observable)

  return DynamicClass;
}
```

### Static Properties

| Property | Type | Description |
|----------|------|-------------|
| `DynClass.instances` | `Map<id, N3TX>` | All entity instances for this model. |
| `DynClass._schema` | `object` | The JSON schema from the backend. |
| `DynClass.schema` | `object` | Getter, returns `_schema`. |
| `DynClass.href` | `string` | CRUD endpoint URL (e.g., `http://.../products`). |
| `DynClass.labels` | `object` | Field name → display label mapping for UI. |
| `DynClass._watchers` | `Set<string>` | Addresses of actors watching this type for instance changes. |
| `DynClass._pendingAttaches` | `Array` | Queued instance-level ATTACHes waiting for READ to complete. |
| `DynClass.__signals` | `Set<Function>` | Static Observable signal callbacks. |
| `DynClass.__observers` | `Map<string, Set>` | Static Observable property observer callbacks. |

### Static Methods

| Method | Description |
|--------|-------------|
| `DynClass.call(method, data?, meta?)` | Sends a TX from the DynClass (type-level). **Omits `source`** so that `Actor._send` assigns it to `className` during Case 3 bubble — this avoids double-prefixing like `"Product/Product"`. |
| `DynClass.signal(callback?, wait?)` | Static Observable. Without args: fires all callbacks. With callback: registers it (fires immediately if `wait=false`). Returns unsubscribe function. |
| `DynClass.observe(property, callback)` | Static Observable. Registers a property observer at the class level. |
| `DynClass.ATTACH(data, tx)` | Handles type-level and instance-level ATTACHes forwarded from `N3TX.ATTACH`. For type-level: adds watcher, sends immediate UPDATE if instances loaded. For instance-level: forwards to instance, or queues in `_pendingAttaches` if instance doesn't exist yet. |
| `DynClass.READ(data)` | Creates/updates N3TX instances from backend records. Replays `_pendingAttaches`, then notifies all watchers with instance addresses. |
| `DynClass.UPDATE(data, tx)` | Delegates to `DynClass.READ()` — handles `meta.inbox='UPDATE'` responses. |

### Two Queues

DynClass uses a second queue (`_pendingAttaches`) that is separate from `N3TX.#waiting`:

| Queue | Location | Purpose |
|-------|----------|---------|
| `N3TX.#waiting` | N3TX static | TXs waiting for DynClass to be **created** (schema not yet received) |
| `DynClass._pendingAttaches` | DynClass static | Instance ATTACHes waiting for **READ to complete** (DynClass exists but instances not yet loaded) |

### Instance (per entity)

```javascript
constructor(data) {
  super(className, data.id);  // → N3TX constructor → TT → Actor
  this.value = data;
  this.href = `${href}/${this.id}`;
}

get value() {
  // Returns this._data with $id (instance URL) and $schema (schema URL) injected
}

set value(val) {
  this._data = val;
  this.signal();  // Fires Observable callbacks
}
```

### Example

After `N3TX.SCHEMA()` processes a schema for "Product" with properties `{id, name, price, description, comments}` and method `{comment}`:

```javascript
// DynClass.name === "Product"
// DynClass.href === "http://localhost:5000/products"
// DynClass.schema === { properties: { ... }, methods: { ... } }

// After READ populates instances:
const product = N3TX.get("Product/1");
product.name              // -> this.value.name (typed getter)
product.price = 29.99     // -> type-checked, calls notify() (Observable)
product.comment({...})    // -> this.call('comment', {...}) -> remote POST

// Relationship hydration: collection fields contain child objects:
product.comments
// -> [{id: 1, $id: "/Comment/1", text: "..."}, ...]
// Each child object is self-describing via $schema/$id.
```

### Mixins Applied

```javascript
Actor.subclass(DynamicClass, Observable)  // Gets full actor wiring + signal/observe/notify
```

Note: Observable is applied at both levels:
- **Instance level** (via `Actor.subclass`): `signal()`, `observe()`, `notify()` on prototype — used for per-entity reactivity
- **Static level** (manually added in `prototype()`): `DynClass.signal()`, `DynClass.observe()` — used for type-level subscriptions (e.g., components subscribing to "when Product class is ready")
