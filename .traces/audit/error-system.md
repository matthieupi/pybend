# PyBend Error System Audit

**Date:** 2026-03-04
**Branch:** v0.9
**Scope:** Full-stack error handling — backend, frontend, cross-boundary flows

---

## 1. Error Response Format Inconsistencies

### 1.1 The Three Formats

PyBend's HTTP error responses use **three incompatible JSON formats** depending on which backend module generates them:

| Format | Key | Example | Used By |
|--------|-----|---------|---------|
| **FastAPI** | `detail` | `{"detail": "Not found"}` | `routes_fastapi.py`, `network_api.py`, `backend.py` JWT middleware |
| **Flask/legacy** | `error` | `{"error": "Not found"}` | `routes_flask.py` |
| **ActivityPub** | `error` | `{"error": "Activity must have a type"}` | `network_ap.py` |
| **Profiling dashboard** | `error` | `{"error": "No such job"}` | `tests/profiling/dashboard.py` |

Additionally, **Pydantic 422 validation** produces a variant where `detail` is an array:
```json
{"detail": [{"loc": ["body", "name"], "msg": "field required", "type": "missing"}]}
```

And the internal **TX error format** uses `message`/`code`:
```json
{"message": "Access denied", "code": 403}
```

The **WebSocket error wire format** is a TX envelope:
```json
{"name": "ERROR", "source": "ws", "target": "...", "data": {"message": "...", "code": 500}, "meta": {"error": true}}
```

MCP uses JSON-RPC 2.0 error format (intentionally different, protocol-correct).

### 1.2 Complete Inventory of Error Response Sites

#### Sites using `{"detail": "..."}` (FastAPI convention) -- CORRECT

| File | Line(s) | Mechanism | Context |
|------|---------|-----------|---------|
| `routes_fastapi.py` | 65, 87, 105, 153, 177, 194, 199, 209, 214, 231, 239, 244, 298, 307, 317, 324, 334, 349, 356, 369, 379 | `HTTPException(detail=...)` | All CRUD routes, custom methods, auth |
| `network_api.py` | 51, 79, 151, 460 | `HTTPException(detail=...)` | Level 3 TX-to-HTTP conversion, auth, method args |
| `backend.py` | 111 | `JSONResponse(content={"detail": "..."})` | JWT middleware 401 |

#### Sites using `{"error": "..."}` -- INCONSISTENT

| File | Line(s) | Mechanism | Context |
|------|---------|-----------|---------|
| `routes_flask.py` | 60, 127, 173 | `jsonify({"error": ...})` | Flask create (400), get-not-found (404), update (400) |
| `network_ap.py` | 227, 230 | `return {"error": ...}` | AP inbox validation (returned as dict, wrapped by route) |
| `network_ap.py` | 392 | `JSONResponse({"error": ...})` | WebFinger not-found (404) |
| `network_ap.py` | 412 | `JSONResponse({"error": ...})` | AP inbox parse error (400) |
| `dashboard.py` | 77, 84, 88, 96, 107, 109, 125, 168 | `JSONResponse({"error": ...})` | Profiling dashboard (all endpoints) |

#### Internal TX error format (correct for actor system, translated at boundary)

| File | Line(s) | Mechanism | Context |
|------|---------|-----------|---------|
| `tx.py` | 37-45 | `TX.error()` | `data={"message": msg, "code": code}` |
| `actor_model.py` | 34-53 | `_exception_to_tx_error()` | Maps exceptions to TX errors |
| `auth_interceptor.py` | multiple | `tx.error(msg, code=N)` | Tier 1 auth denials |
| `network_ws.py` | 283-289 | Inline dict | WS message handling errors |

#### Protocol-specific formats (intentionally different, correct)

| File | Format | Protocol |
|------|--------|----------|
| `network_mcp.py` | `{"jsonrpc": "2.0", "error": {"code": N, "message": "..."}}` | JSON-RPC 2.0 |
| `network_ws.py` | TX envelope with `data.message`/`data.code` | WebSocket TX wire format |

### 1.3 Frontend Error Extraction

The frontend handles multiple formats via a fallback chain in `HTTP._extractError()` (`HTTP.js:16-30`):

```
json.error          → Flask/AP format
json.detail (array) → Pydantic 422 format
json.detail (string)→ FastAPI format
json.message        → TX format (only for status >= 400)
```

And in `NTTElement.ERROR()` (`NTTElement.js:133-158`):

```
d.detail (array)    → Pydantic 422 validation errors
d.detail (string)   → FastAPI format
d.error             → Flask/AP format
d.message           → TX/WS format
fallback            → "An error occurred"
```

The frontend works because it checks **all** formats. But this is fragile — the extraction chain is order-dependent and undocumented. A new backend module that uses yet another key would silently produce "An error occurred" instead of the real message.

### 1.4 Impact Assessment

**Functional impact:** Low — the frontend fallback chain handles all current formats.

**Maintenance impact:** High — every new backend module must know to use `detail` (not `error`), and the frontend must keep its fallback chain in sync.

**Debugging impact:** Medium — when tracing errors across the stack, developers must remember which format each module uses.

**Contract violation:** The `{"detail": "..."}` format is FastAPI's convention and the one documented in CLAUDE.md. The `{"error": "..."}` format is a deviation that should be standardized.

---

## 2. 200-OK Error Pattern (Partial Fix)

### 2.1 Current State

`HTTP.js` lines 110-116 (GET handler, same pattern in POST/PUT/DELETE):
```javascript
.then((resp) => {
    if (resp === undefined) return;
    if(resp.hasOwnProperty('token')) {
        window.localStorage['jwtToken'] = resp.token;
    }
    HTTP._checkBodyForError(resp);  // shows toast if error detected
    onSuccess(resp);                 // ALWAYS fires regardless
})
```

`_checkBodyForError()` returns `true` when an error is found, but the return value is **never checked**. The success callback fires with error data.

### 2.2 Where It Matters

The `DynamicClass._response_` handler (`NTT.js:1086-1096`) **does** check for embedded errors and short-circuits `pull()`. This covers method call responses.

But for CRUD operations routed through `NetworkAdapter.httpCallback()`, the success path creates a reply TX without checking for embedded errors. The component processes the error data as valid entity data.

### 2.3 Severity

Medium. The MethodError fix eliminated the primary source of 200-OK errors (custom methods now throw proper HTTP errors). The remaining risk is from any future code that returns error dicts from 200 responses.

---

## 3. Silent Error Patterns

### 3.1 Backend Silent Errors

| Location | Pattern | Severity |
|----------|---------|----------|
| `sqlite_storage.py` (6 sites) | `except Exception: pass` / `except OperationalError: pass` in FK hydration and `_populate_fields()` | Medium — hides data integrity issues |
| `sqlite_migration.py` (4 sites) | Column add/remove fails → `logger.warning()` → `continue` | High — schema drift, column never created |
| `matrix.py:67-70` | No route found → `logger.warning()` → message dropped | Critical — sender hangs 30s, gets misleading timeout |
| `backend.py:108` | JWT decode → bare `except Exception` → no logging of actual error | Medium — real decode failures invisible |
| `network_ws.py:257` | JWT decode fails → `logger.warning()` → anonymous connection | Low — intentional for schema requests |

### 3.2 Frontend Silent Errors

| Location | Pattern | Severity |
|----------|---------|----------|
| `Actor.js _inbox()` | No handler for event name → throws (uncaught) | Critical — crashes message pipeline |
| `NTT.js` | Schema fetch failure → ERROR TX → NTT has no ERROR handler → throw | Critical — model stuck forever |
| `HTTP.js:115` | `_checkBodyForError()` return ignored → `onSuccess()` fires with error | Medium — see Section 2 |
| `ListElement.js` | Create modal closes before response → validation errors lost | High — user must start over |
| `ntt-item.js` | Optimistic delete → no rollback on failure | Medium — UI out of sync |
| `ntt-method.js` | Load failures (3 sites) → `Logging.error()` only → empty component | Medium — buttons silently missing |
| `Permissions.js` | `/auth/me` fails → user treated as anonymous, no feedback | Medium |

---

## 4. Status Code Semantics

### 4.1 401 vs 403 Conflation

Both `auth_interceptor.py` and `routes_fastapi.py` return **403** for unauthenticated users. Per HTTP semantics:
- **401 Unauthorized** = "you need to authenticate" (include `WWW-Authenticate` header)
- **403 Forbidden** = "you're authenticated but not allowed"

Current behavior: all ABAC denials return 403, whether the user is anonymous or authenticated-but-denied.

The only place 401 is used correctly is the JWT middleware (`backend.py:110`) for invalid/expired tokens and `/auth/me` for missing auth.

### 4.2 Default 500 for Create/Update Failures

`actor_model.py` handler_crud returns `tx.error("Create failed")` and `tx.error("Update failed")` when the storage operation returns falsy. `TX.error()` defaults to code **500**. These are almost never server errors — they're constraint violations (409) or validation errors (400).

### 4.3 ValueError/TypeError Mapped to 400 (Not 422)

`_exception_to_tx_error()` maps `ValueError` and `TypeError` to 400. When these come from Pydantic validation (`cls(**data)`), 422 would be more semantically correct and consistent with FastAPI's own Pydantic handling.

---

## 5. Level 1/2 vs Level 3 Behavioral Inconsistencies

| Behavior | Level 1/2 (Direct Routes) | Level 3 (Actor Routing) |
|----------|--------------------------|------------------------|
| Missing custom method args | 400 `"Missing field: {name}"` | Silently skipped → TypeError (500) |
| Validation errors in CRUD | 400 (broad `except Exception`) | 500 (ValidationError not specifically caught) |
| Custom methods without `access=` | Falls back to `_resolver.authorize()` → AUTHENTICATED | **No auth check at all** |
| Error detail in create (DEBUG) | Traceback list or "Bad request" | `str(e)` via TX error |

The auth gap for custom methods without explicit `access=` in Level 3 is the most concerning — they are effectively public.

---

## 6. Error Flow Diagrams

### 6.1 Canonical HTTP Error Flow (Working)
```
Request → FastAPI Route → try/except → HTTPException(status_code, detail="...")
                                                    ↓
Client ← HTTP 4xx/5xx ← {"detail": "..."} ←────────┘
  ↓
HTTP._extractError() → json.detail → showToast()
NetworkAdapter.onError() → ERROR TX → Component.ERROR() → error banner
```

### 6.2 Actor System Error Flow (Working)
```
Request → NetworkAPI → TX → auth_interceptor
                               ↓ (denied)
                         tx.error("Access denied", 403)
                               ↓
                 NetworkAdapter.request() resolves Future
                               ↓
                 _response_or_raise() → HTTPException(403, detail="Access denied")
                               ↓
                 Client ← HTTP 403 ← {"detail": "Access denied"}
```

### 6.3 Matrix Message Drop (BROKEN)
```
Component → TX(target: "produccts") → Matrix.inbox()
                                          ↓
                              logger.warning("No route")
                              MESSAGE DROPPED SILENTLY
                                          ↓
                              ... 30 seconds ...
                                          ↓
                    NetworkAdapter.request() → TimeoutError → tx.error("timed out", 504)
                                          ↓
                    Client ← HTTP 504 ← "timed out" (MISLEADING)
```

### 6.4 Frontend Actor Crash (BROKEN)
```
WebSocket message → Socket.onmessage → JSON.parse
                                          ↓
                    matrix.dispatch(data) → Actor._inbox()
                                               ↓
                                   No handler for event name
                                               ↓
                                   throw Error("No handler...")
                                               ↓
                               UNCAUGHT — message pipeline crashes
```

---

## 7. TX Error Format (Internal Standard)

The actor system has a clean, consistent internal error format:

```python
# TX.error() always produces:
TX(
    name='ERROR',
    source=self.target,        # swapped
    target=self.source,        # swapped
    data={'message': str, 'code': int},
    meta={..., 'in_reply_to': uuid, 'error': True},
)
```

This is correctly translated at boundaries:
- **NetworkAPI** → `_response_or_raise()` → `HTTPException(status_code=code, detail=message)`
- **NetworkWebSocket** → `_translate_outgoing()` → TX wire format with `name='ERROR'`
- **NetworkMCP** → JSON-RPC error response with `isError: True`

The internal TX format is sound. The problem is only at **non-TX HTTP boundaries** (Flask, AP, profiling dashboard) where developers bypassed FastAPI's `HTTPException` and used raw `JSONResponse` with `{"error": "..."}` instead.

---

## 8. Remediation Plan

### Priority 1: Standardize Error Response Format

**Goal:** All HTTP error responses use `{"detail": "..."}` format via FastAPI's `HTTPException`.

**Files to change:**

| File | Current | Target | Change |
|------|---------|--------|--------|
| `network_ap.py:227` | `return {'error': 'Activity must have a type'}` | `return {'detail': 'Activity must have a type'}` | Key rename |
| `network_ap.py:230` | `return {'error': 'Activity must have an actor'}` | `return {'detail': 'Activity must have an actor'}` | Key rename |
| `network_ap.py:392` | `JSONResponse({'error': 'Not found'}, ...)` | `raise HTTPException(status_code=404, detail='Not found')` | Use HTTPException |
| `network_ap.py:412` | `JSONResponse({'error': 'Invalid JSON'}, ...)` | `raise HTTPException(status_code=400, detail='Invalid JSON')` | Use HTTPException |
| `network_ap.py:415` | `if 'error' in result:` | `if 'detail' in result:` | Match new key |
| `routes_flask.py:60` | `jsonify({'error': str(e)})` | `jsonify({'detail': str(e)})` | Key rename |
| `routes_flask.py:127` | `jsonify({'error': 'Not found'})` | `jsonify({'detail': 'Not found'})` | Key rename |
| `routes_flask.py:173` | `jsonify({'error': str(e)})` | `jsonify({'detail': str(e)})` | Key rename |
| `dashboard.py:77,84,88,96,107,109,125,168` | `JSONResponse({'error': ...})` | `raise HTTPException(status_code=N, detail=...)` | Use HTTPException |

**Frontend impact:** `HTTP._extractError()` already checks `json.detail` before `json.error`. After standardization, the `json.error` check becomes a defensive fallback rather than a primary path. No frontend changes needed — the extraction order still works, just hits `json.detail` first now.

### Priority 2: Fix 200-OK Bypass

**File:** `HTTP.js` lines 115, 168, 220, 258

**Change:** Guard `onSuccess()` behind `_checkBodyForError()` result:
```javascript
if (!HTTP._checkBodyForError(resp)) {
    onSuccess(resp);
}
```

### Priority 3: Fix Matrix Message Drop

**File:** `matrix.py` lines 67-70

**Change:** Return error TX to sender instead of silently dropping:
```python
# Instead of: logger.warning(f"[Matrix] No route to {tx.target}")
await self.send(tx.error(f"No route to {tx.target}", code=404))
```

### Priority 4: Add Frontend Error Boundaries

**File:** `Matrix.js` `inbox()` and `Actor.js` `_inbox()`

**Change:** Wrap handler dispatch in try/catch, convert throws to ERROR TXs.

### Priority 5: Fix Status Code Semantics

- Distinguish 401 (unauthenticated) from 403 (unauthorized) in `auth_interceptor.py` and `routes_fastapi.py`
- Change create/update failure codes from default 500 to 409 in `actor_model.py`
- Map `ValueError`/`TypeError` from Pydantic validation to 422 instead of 400

### Priority 6: Fix Level 3 Auth Gap

- Custom methods without `access=` in Level 3 should default to `AUTHENTICATED` (matching Level 1/2 behavior)

---

## 9. Error Format Contract (Post-Remediation)

After fixing, the error format contract should be:

### HTTP Responses (All Endpoints)
```
Success: 2xx with entity/collection data
Client Error: 4xx with {"detail": "human-readable message"}
Validation Error: 422 with {"detail": [{"loc": [...], "msg": "...", "type": "..."}]}
Server Error: 5xx with {"detail": "human-readable message"}
```

### TX Messages (Internal Actor System)
```
Error TX: name='ERROR', data={'message': str, 'code': int}, meta={error: true}
```

### WebSocket Wire Format
```
Error: {name: 'ERROR', data: {message, code}, meta: {error: true}}
```

### MCP (JSON-RPC 2.0)
```
Protocol Error: {"jsonrpc": "2.0", "error": {"code": N, "message": "..."}}
Tool Error: {"jsonrpc": "2.0", "result": {"content": [...], "isError": true}}
```

### Frontend Extraction Contract
```
HTTP errors:  HTTP._extractError(json, status) → string
Validation:   HTTP._extractValidationErrors(json) → [{field, message, type, input}]
200-OK check: HTTP._checkBodyForError(json) → boolean (gates onSuccess)
WS errors:    NTTElement.ERROR() reads data.message
```

---

## Appendix A: Files Audited

### Backend
- `src/pybend/core/api/routes_fastapi.py` — Level 1/2 CRUD routes
- `src/pybend/core/api/network_api.py` — Level 3 actor routing
- `src/pybend/core/api/network_ap.py` — ActivityPub federation
- `src/pybend/core/api/network_mcp.py` — MCP JSON-RPC
- `src/pybend/core/api/network_ws.py` — WebSocket bridge
- `src/pybend/core/api/auth_interceptor.py` — Tier 1 ABAC gate
- `src/pybend/core/api/backend.py` — JWT middleware
- `src/pybend/core/api/routes_flask.py` — Flask routes (legacy)
- `src/pybend/core/models/actor_model.py` — ActorModel CRUD + dispatch
- `src/pybend/core/models/proto_model.py` — ProtoModel base
- `src/pybend/core/actors/tx.py` — TX message envelope
- `src/pybend/core/actors/actor.py` — Actor base class
- `src/pybend/core/actors/matrix.py` — Matrix message router
- `src/pybend/core/storage/sqlite_storage.py` — SQLite backend
- `src/pybend/core/storage/sqlite_migration.py` — Auto-migration
- `src/pybend/core/authorize/errors.py` — AccessDenied exception
- `src/pybend/core/authorize/resolver.py` — DefaultResolver
- `src/pybend/core/utils/erroring.py` — MethodError
- `src/pybend/core/tests/profiling/dashboard.py` — Profiling dashboard

### Frontend
- `src/pybend/static/core/transport/HTTP.js` — HTTP transport
- `src/pybend/static/core/transport/NetworkAdapter.js` — TX/HTTP bridge
- `src/pybend/static/core/transport/Socket.js` — WebSocket client
- `src/pybend/static/core/NTT.js` — Entity system
- `src/pybend/static/core/Matrix.js` — Frontend message router
- `src/pybend/static/core/Actor.js` — Frontend actor base
- `src/pybend/static/core/Router.js` — Navigation state
- `src/pybend/static/components/NTTElement.js` — Base component
- `src/pybend/static/components/ntt-item.js` — Item component
- `src/pybend/static/components/ntt-list.js` — List component
- `src/pybend/static/components/ntt-table.js` — Table component
- `src/pybend/static/components/ntt-row.js` — Row component
- `src/pybend/static/components/ntt-router.js` — View container
- `src/pybend/static/components/ntt-modal.js` — Modal dialog
- `src/pybend/static/components/ntt-method.js` — Method buttons
- `src/pybend/static/generators/form.js` — Form generator
- `src/pybend/static/utils/Permissions.js` — Frontend ABAC
- `src/pybend/static/utils/Toast.js` — Toast notifications
- `src/pybend/static/widgets/*.js` — Widget implementations

### Example Apps
- `example_actor/models/product.py`, `comment.py` — MethodError usage
- `example_api/models/product.py`, `comment.py` — Same models, direct routing
- `example_grants/` — Agent system models
