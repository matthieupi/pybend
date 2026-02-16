# Actor System Reference

Detailed documentation of each class in the Actor/Matrix system.

## Table of Contents

1. [Actor](#actor)
2. [Matrix](#matrix)
3. [TX](#tx)
4. [Observable](#observable)
5. [TT (Transfer Type)](#tt-transfer-type)
6. [PTT (Proto Transfer Type)](#ptt-proto-transfer-type)
7. [NTT (Named Transfer Type)](#ntt-named-transfer-type)
8. [Dynamic Prototype Classes](#dynamic-prototype-classes)

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
- Example: `Actor.subclass(PTT, Observable)` adds signal/observe/notify to PTT

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

The Matrix's children map contains **classes** (not instances):
- `PTT` (registered via `Actor.subclass(PTT)` when Matrix exists)
- `Component` (registered via `Actor.subclass(Component)`)
- `NTT` (registered via `Actor.subclass(NTT)`)
- `TT` (registered via `Actor.subclass(TT)`)
- `List`, `Item` (registered via `Actor.subclass(List)`)

This means a message targeting "PTT" routes to `PTT.inbox()` (the static method), which handles it at the class level.

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
LOAD, ERROR, PING, PONG, HEARTBEAT, LOGIN, LOGOUT, REGISTER, NOTIFY, ALERT
```

---

## Observable

**File:** `core/Observable.js`

A mixin that adds pub/sub reactivity to any Actor subclass. Applied via:

```javascript
Actor.subclass(PTT, Observable)  // PTT instances get signal/observe/notify
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

---

## TT (Transfer Type)

**File:** `core/NTT.js` (within the same module)

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

## PTT (Proto Transfer Type)

**File:** `core/NTT.js`

Schema proxy for a backend model. One PTT per model type (e.g., one for "Product", one for "User"). Pulls the JSON schema from the backend, generates a dynamic NTT subclass, and manages entity instances.

### Static State

| Property | Type | Description |
|----------|------|-------------|
| `PTT.#prototypes` | `Map<string, PTT>` | Registry of all PTT instances by address. |

### Instance State

| Property | Type | Description |
|----------|------|-------------|
| `#instances` | `Map<id, NTT>` | Entity instances created from backend data. |
| `#data` | `object` | The raw JSON schema from the backend. |
| `#cls` | `class` | The dynamically generated NTT subclass. |

### Key Instance Methods

| Method | Description |
|--------|-------------|
| `get schema()` | Returns `#data` (the raw schema). |
| `get value()` | Returns schema with injected `@context` (href) and `@type` (addr). |
| `set value(val)` | Sets schema, runs `prototype(this)` to generate/update the dynamic class, fires `signal()`. |
| `pull()` | Sends `SCHEMA` call to backend via `this.call('SCHEMA')`. |
| `SCHEMA(data)` | Handler for schema response. Sets `this.href` from `__tablename__`, sets `this.value` (triggers class generation). Registers any `$defs` models as new PTTs. |
| `READ(data)` | Handler for list/read response. Creates NTT instances from array data, stores in `#instances`, calls `notify()` with instance addresses. |
| `UPDATE(data)` | Dispatches UPDATE through Matrix. |
| `has(addr)` / `get(addr)` | Instance-level lookup in `#instances`. |

### Static Methods

| Method | Description |
|--------|-------------|
| `PTT.has(addr)` | Checks `#prototypes` registry. |
| `PTT.get(addr)` | Returns existing PTT or creates + pulls a new one. |
| `PTT.factory(addr, href, schema?)` | Creates a PTT. If no schema provided, calls `pull()`. |
| `PTT.attach(addr, callback)` | Attaches a signal callback to a PTT (creates it if needed). Returns unsubscribe function. |
| `PTT.ATTACH(data, tx)` | Static event handler. Looks up or creates the PTT for the given address, registers the sender as a watcher, triggers a READ. |

### Mixins Applied

```javascript
Actor.subclass(PTT, Observable)  // Gets signal(), observe(), notify()
```

Note: PTT.notify (from TT) and Observable.notify coexist. TT's `notify()` sends TX messages to watchers. Observable's `notify()` fires local property observer callbacks. In practice, PTT uses TT's `notify()` for the watcher pattern and Observable's `signal()` for schema-ready callbacks.

---

## NTT (Named Transfer Type)

**File:** `core/NTT.js`

Represents a single entity instance (e.g., Product #1). Linked to a PTT prototype for schema access.

### Instance State

| Property | Type | Description |
|----------|------|-------------|
| `#proto` | `PTT` | Reference to the prototype (schema source). |
| `#data` | `object` | The entity's current data. |
| `#meta` | `object` | Metadata (currently unused, placeholder for future state management). |

### Key Instance Methods

| Method | Description |
|--------|-------------|
| `get value()` | Returns `#data`. |
| `set value(val)` | Sets `#data`. If proto is not set, fires `signal()`. |
| `get proto()` | Returns `#proto`. |
| `get schema()` | Returns `#proto?.schema`. |
| `define(proto)` | Links this NTT to a PTT and sets href. |
| `describe(proto, data)` | Calls `define()` + `update()`. |
| `update(data)` | Merges data into value via spread. |
| `pull()` | Sends READ call to backend for this specific entity. |
| `ATTACH(data, event)` | Registers the sender as a watcher (non-immediate), then sends DESCRIBE back with schema + data. |
| `toJSON()` | Serializes addr, href, data, meta. |

### Static Methods

| Method | Description |
|--------|-------------|
| `NTT.get(addr)` | Looks up instance in `this.children` (class-level). |
| `NTT.READ(data)` | Static handler: updates the NTT instance with received data. |
| `NTT.UPDATE(data)` | Static handler: updates or creates instances from data entries. |
| `NTT.attach(model, hash, callback)` | Creates/gets an NTT and attaches a signal callback. |
| `NTT.create(model, data, callback?)` | Dispatches a CREATE event to the backend. |

### Mixins Applied

```javascript
Actor.subclass(NTT)  // No Observable on base NTT
```

---

## Dynamic Prototype Classes

**File:** `core/NTT.js` (`prototype()` function)

When a PTT receives its schema, it calls `prototype(ptt)` to generate a runtime NTT subclass with schema-aware properties and methods.

### What `prototype(ptt)` does

```javascript
function prototype(ptt) {
  // Reads ptt.schema.properties and ptt.schema.methods

  const DynamicClass = class extends NTT { ... }

  // 1. Sets class name to ptt.addr (e.g., "Product")
  // 2. Stores static _schema reference

  // 3. For each schema property, defines a getter/setter:
  //    - getter: returns this.value[field]
  //    - setter: validates type, validates readOnly, updates value, calls notify()
  //    - Stores field labels for UI

  // 4. For each schema method, defines a prototype method:
  //    - Validates required parameters
  //    - Validates $ref parameter types
  //    - Calls this.call(method, args) for remote invocation

  // 5. Applies Actor.subclass(DynamicClass, Observable)
  //    - Gets full actor wiring + signal/observe/notify

  return DynamicClass;
}
```

### Dynamic Class Instance

```javascript
// constructor(data):
//   - Calls super(DynamicClass.name, data.id) -> NTT constructor
//   - Sets this.value = data
//   - Sets this.href = ptt.href/id

// get value():
//   - Returns this._data with @context and @type injected

// set value(val):
//   - Sets this._data = val
//   - Calls this.signal()
```

### Example

After PTT("Product") pulls its schema with properties `{id, name, price, description, comments}` and method `{comment}`:

```javascript
// DynamicClass.name === "Product"
// instance.name -> this.value.name
// instance.price = 29.99 -> type-checked, calls notify()
// instance.comment({...}) -> this.call('comment', {...}) -> remote POST
```
