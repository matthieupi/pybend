# Wave 0b: Frontend vs Backend Actor System Comparison

> **Date**: 2026-02-28
> **Purpose**: Feature-by-feature comparison of the frontend JS Actor/Matrix/TX
> implementation against the backend Python port, to ensure no features were
> forgotten during the 0b implementation.

---

## TX: Frontend (TX.js) vs Backend (tx.py)

| Feature | Frontend (TX.js) | Backend (tx.py) | Status |
|---|---|---|---|
| Core fields: name, source, target, data, meta | `name, source, target, data={}, meta={}` | `name, source, target, data={}, meta={}` | Same |
| Timestamp | `tst` (Date.now()) | `timestamp` (time.time()) | Same (renamed) |
| Identity | `_hash` (lazy content hash via `simpleHash`) | `uuid` (random 12-char hex) | **Different approach** |
| `repr()` -> plain dict | Yes, for wire format | **Missing** | Needed for WebSocket bridge |
| `str()` -> JSON string | Yes (`JSON.stringify(repr())`) | **Missing** | Needed for wire format |
| `fromString()` -> reconstruct from JSON | Yes (static factory) | **Missing** | Needed for wire format |
| `reply()` -> response TX | No | Yes | Backend addition (Result type) |
| `error()` -> error TX | No (handled in NetworkAdapter.onError) | Yes | Backend addition (Result type) |
| `is_error` property | No | Yes | Backend addition |
| Subclasses (ConnectEvent, ReadEvent, etc.) | Yes (convenience constructors) | No | Python uses `TX(name='CONNECT', ...)` directly |

### Key Gaps

1. **No serialization** (`to_dict()` / `from_dict()`) -- needed for WebSocket bridge
   (Wave 3), logging, debugging, and adapter protocol translation.
2. **No content hash** -- frontend uses hash for dedup/comparison. Backend uses uuid
   for correlation instead. Different purpose, but content hash could still be useful
   for idempotency checks.

### Backend Additions (not in frontend)

- `reply(data, name)` -- creates response TX with swapped source/target, new uuid,
  stores original in `meta['in_reply_to']`. This is the Result type pattern.
- `error(message, code)` -- creates ERROR TX. Eliminates the 200-OK anti-pattern.
- `is_error` property -- quick check for error state.

---

## Actor: Frontend (Actor.js) vs Backend (actor.py)

| Feature | Frontend (Actor.js) | Backend (actor.py) | Status |
|---|---|---|---|
| Private addr, children | `#addr`, `#children` (Map) | `_addr`, `_children` (PrivateAttr dict) | Same |
| Parent reference | `#parent` (defaults to constructor) | `_parent` (defaults to None) | **Different** |
| Per-class children (type-level) | `static _children` (Map, via subclass()) | `__children__` (ClassVar dict, via `__init_subclass__`) | Same |
| Root actor reference | `ROOT_ACTOR` module var, `static registerRoot()` | `__root_actor__` ClassVar, `register_root()` classmethod | Same |
| `static get root` | Yes | **Missing** (access `__root_actor__` directly) | Minor |
| Auto-registration in constructor | Yes -- `this.constructor.register(this)` | **No** -- explicit `register()` required | **Different** |
| `inbox()` | Delegates to `_inbox` (dispatch to named method) | Async, calls `handler()` | Same concept |
| `handler()` dispatch | `_inbox`: checks target match, calls `this[tx.name]` | `handler()`: calls `getattr(self, tx.name)` | Same |
| `send()` instance | Throws "must be implemented" | Routes through `_parent` or `__root_actor__` | **Backend more complete** |
| `static _send()` routing | Complex: local -> prefixed -> bubble (with source prefix) | `send_cls()`: class children -> root | **Simpler in backend** |
| Source prefix on bubble | Yes -- `tx.source = typeAddr/tx.source` | **Missing** | Helps with traceability |
| `subclass()` metaclass | Yes (JS workaround for no MI) | `__init_subclass__` (native Python MI) | Equivalent |
| `isActor()` | Yes (static method) | No (use `isinstance()`) | Python built-in |
| `spawn()` | Yes (creates + registers child, asserts no duplicate) | Yes (creates + registers child) | Same |
| `register()` instance | Yes (registers child in parent) | Yes (sets parent + adds to children) | Same |
| `on_start()` / `on_stop()` | No | Yes | Backend addition |

### Key Gaps

1. **No auto-registration** -- Frontend auto-registers every actor instance in its
   type-level children map (`this.constructor.register(this)` in constructor). Backend
   requires explicit `parent.register(child)`. This is a design choice (explicit >
   implicit in Python) but worth noting.

2. **No source prefix on bubble** -- Frontend prefixes source with type address when
   routing up (`tx.source = typeAddr/tx.source`). This creates a traceable path like
   `NTT/Product/42`. Backend doesn't modify source during routing.

3. **Default parent differs** -- Frontend defaults `#parent` to `this.constructor`
   (the class itself), providing type-level routing fallback. Backend defaults to
   `None` and falls back to `__root_actor__` in `send()`. Similar effect, different
   mechanism.

4. **Spawn duplicate guard** -- Frontend asserts no duplicate child address in
   `spawn()`. Backend doesn't check.

### Backend Additions (not in frontend)

- `on_start()` / `on_stop()` lifecycle hooks for actor initialization/teardown.
- `handler()` wraps results in `tx.reply()` and catches exceptions into `tx.error()`.
  Frontend dispatch doesn't have this wrapping layer.
- `register_cls()` classmethod for class-level child registration (equivalent to
  frontend's static `_register` but as a separate explicit call).

---

## Matrix: Frontend (Matrix.js) vs Backend (matrix.py)

| Feature | Frontend (Matrix.js) | Backend (matrix.py) | Status |
|---|---|---|---|
| Extends Actor | Yes | Yes | Same |
| Auto-registers as root | `if (!Actor.root) Actor.registerRoot(this)` | **No** -- must call `register_root()` separately | **Missing** |
| `has(addr)` | Yes -- checks child by first segment | **Missing** | Useful utility |
| CONNECT event routing | Yes -- special `connect()` handler | **Missing** | Significant feature |
| Self-send prevention | Yes -- `if (tx.target === this.addr) throw Error` | **Missing** | Safety check |
| Local child routing | `this.children.get(targetAddr).inbox(tx.repr())` | `self._children[target_root].inbox(tx)` | Same |
| Remote fallback | `this.remote.send(tx)` (single NetworkAdapter) | `for adapter in self._adapters` (multiple adapters) | **Backend more flexible** |
| `dispatch()` alias | Yes (alias for inbox) | No | Trivial, not needed |
| `connect()` method | Yes -- routes CONNECT to child actor | **Missing** | Frontend wiring pattern |
| NetworkAdapter in constructor | Yes (always created) | No -- `register_adapter()` (explicit, multiple) | Backend more flexible |

### Key Gaps

1. **No `connect()` / CONNECT event** -- The frontend has a distinct actor-to-actor
   connection protocol. Used for component wiring (e.g., `<ntt-item>` connecting to
   its NTT entity actor). Question: is this needed backend-side, or is it purely a
   frontend component wiring concern?

2. **No `has(addr)`** -- Quick child existence check by first address segment. Trivial
   to add.

3. **No auto-register as root** -- Frontend Matrix auto-registers as root if no root
   exists. Backend requires explicit `register_root()` call.

4. **No self-send prevention** -- Frontend throws if Matrix tries to send to itself.
   Backend silently allows it (would hit "no route" warning).

### Backend Additions (not in frontend)

- Multiple adapter support (`register_adapter()` + loop) vs frontend's single
  NetworkAdapter. More flexible for backend's multi-protocol needs (HTTP, WS, MCP, AP).
- `send()` override routes internally via `inbox()` instead of requiring parent routing.

---

## Event Types (Frontend config.E)

The frontend defines these event types in `config.js`:

| Event | Used In | Backend Equivalent | Notes |
|---|---|---|---|
| CONNECT | Matrix.connect(), ConnectEvent | **Not implemented** | Actor wiring |
| CONNECTED | Connection confirmation | **Not implemented** | Response to CONNECT |
| DISCONNECTED | Connection teardown | **Not implemented** | Cleanup |
| ENABLE | EnableEvent | **Not implemented** | Actor lifecycle |
| DISABLE | DisableEvent | **Not implemented** | Actor lifecycle |
| SCHEMA | NTT.SCHEMA() | Will be in ActorModel (Wave 0d) | Schema request |
| READ | NetworkAdapter, ReadEvent | Will be in ActorModel (Wave 0d) | CRUD |
| CREATE | NetworkAdapter | Will be in ActorModel (Wave 0d) | CRUD |
| UPDATE | NetworkAdapter, UpdateEvent | Will be in ActorModel (Wave 0d) | CRUD |
| DELETE | NetworkAdapter | Will be in ActorModel (Wave 0d) | CRUD |
| DESCRIBE | DescribeEvent | **Not implemented** | Entity detail view |
| NAVIGATE | Router | N/A (frontend-only) | Navigation |
| ERROR | NetworkAdapter.onError | `tx.error()` | Error responses |

### Events to consider for backend:

- **DESCRIBE** -- Frontend uses this for entity detail view requests. Backend equivalent
  would be a READ with specific ID. May not need a separate event type.
- **CONNECT/CONNECTED/DISCONNECTED** -- Actor connection lifecycle. Relevant if backend
  actors need dynamic wiring (e.g., WebSocket clients subscribing to entity updates).
- **ENABLE/DISABLE** -- Actor lifecycle control. Could map to `on_start()`/`on_stop()`
  but with message-based triggering rather than direct calls.

---

## Recommendations

### Should Add (functional gaps)

1. **TX serialization**: `to_dict()` / `from_dict()` -- needed for WebSocket bridge,
   logging, adapter protocol translation.
2. **Matrix `has(addr)`** -- utility method, trivial to add.
3. **Matrix self-send guard** -- safety check to prevent infinite loops.

### Design Decisions to Discuss

4. **Source prefix on routing** -- Frontend adds traceability path during bubble-up.
   Useful for debugging and logging. Worth adding to backend `send()`?
5. **CONNECT event protocol** -- Is this needed backend-side for dynamic actor wiring
   (e.g., WebSocket client subscribing to entity updates), or is it purely a frontend
   component concern?
6. **Auto-registration** -- Frontend auto-registers instances in type-level children.
   Backend is explicit. Recommendation: keep explicit (Pythonic, avoids surprises).
7. **Matrix auto-register as root** -- Should the first Matrix auto-register?
   Recommendation: keep explicit (supports multiple Matrix instances cleanly).
8. **Spawn duplicate guard** -- Frontend asserts no duplicate child addr. Should
   backend do the same?

### Intentionally Different (no action needed)

- `subclass()` -> `__init_subclass__` (Python MI is cleaner)
- `isActor()` -> `isinstance()` (Python built-in)
- `inbox`/`send` binding -> Python bound methods work differently
- Single NetworkAdapter -> Multiple adapters (backend more flexible)
- TX subclasses (ConnectEvent, etc.) -> Direct `TX(name=...)` construction
- `dispatch()` alias -> Not needed
