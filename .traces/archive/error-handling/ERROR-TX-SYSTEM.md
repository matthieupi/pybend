# PyBend Error System Remediation — ERROR TX All The Way Through

## Context

The error-system audit (`.traces/audit/error-system.md`) identified 6 priority issues across PyBend's full-stack error handling: format inconsistencies, a 200-OK bypass, silent message drops, frontend actor crashes, status code misuse, and a Level 3 auth gap.

Rather than patching each issue individually, this plan establishes **ERROR TX as the canonical error representation throughout the system**. HTTP `{"detail": "..."}` becomes a boundary translation, not the primary representation. This architectural principle naturally resolves all 6 audit issues and unifies the error flow.

### Architectural Principle

```
Error occurs anywhere → ERROR TX → routes through actor system → handler displays
HTTP format {"detail": "..."} exists ONLY at the protocol boundary (translation layer)
```

**Backend flow:**
```
Exception → _exception_to_tx_error() → TX(name='ERROR')
    → Matrix routes to sender → NetworkAPI._response_or_raise() → HTTPException
```

**Frontend flow (UNIFIED — currently split):**
```
HTTP 4xx/5xx → NetworkAdapter.onError() → ERROR TX → Matrix → Component.ERROR()
                                                                    ↓
                                                           toast + banner + field errors
```

**Currently broken:** HTTP.js shows toasts independently, `_checkBodyForError` return ignored, Actor._inbox() crashes on missing handlers, Matrix drops unroutable messages.

---

## Phase 0: Foundation — Shared Error Utilities

### 0a. Extract `_exception_to_tx_error` to shared location
**File:** `src/pybend/core/actors/tx.py` (add method)
**File:** `src/pybend/core/models/actor_model.py` (import from tx.py)

Move `_exception_to_tx_error()` from `actor_model.py` to `tx.py` as a module-level function. This makes it available to Actor base class, ActorModel, and any future code that needs exception→TX translation. Keep the import in `actor_model.py` for backward compat.

```python
# tx.py — add at module level
def exception_to_tx_error(e: Exception, tx: 'TX') -> 'TX':
    """Map exception types to TX error responses with semantic HTTP codes."""
    # Lazy import to avoid circular
    from pybend.core.utils.erroring import MethodError

    if isinstance(e, MethodError):
        return tx.error(e.message, code=e.status_code)
    if hasattr(e, 'status_code') and hasattr(e, 'detail'):
        return tx.error(e.detail, code=e.status_code)

    from pydantic import ValidationError
    if isinstance(e, ValidationError):
        return tx.error(str(e), code=422)
    if isinstance(e, (ValueError, TypeError)):
        return tx.error(str(e), code=400)
    if isinstance(e, PermissionError):
        return tx.error(str(e), code=403)
    if isinstance(e, KeyError):
        return tx.error(f"Missing required field: {e}", code=400)
    return tx.error(str(e), code=500)
```

In `actor_model.py`, replace `_exception_to_tx_error` with:
```python
from pybend.core.actors.tx import exception_to_tx_error as _exception_to_tx_error
```

### 0b. Add Pydantic ValidationError → 422 mapping
Included in the extracted function above. Currently `ValueError`/`TypeError` → 400 catches some Pydantic errors, but `ValidationError` itself should be 422 (matches FastAPI convention).

---

## Phase 1: Backend Error Standardization

### 1a. Standardize error response format → `{"detail": "..."}`
All HTTP error responses use FastAPI's `HTTPException` / `{"detail": "..."}`.

**`src/pybend/core/api/network_ap.py`:**
| Line | Change |
|------|--------|
| 227 | `{'error': ...}` → `{'detail': ...}` |
| 230 | `{'error': ...}` → `{'detail': ...}` |
| 392 | `JSONResponse({'error': ...})` → `raise HTTPException(404, detail=...)` |
| 412 | `JSONResponse({'error': ...})` → `raise HTTPException(400, detail=...)` |
| ~415 | `if 'error' in result:` → `if 'detail' in result:` |

**`src/pybend/core/api/routes_flask.py`:**
| Line | Change |
|------|--------|
| 60 | `jsonify({'error': str(e)})` → `jsonify({'detail': str(e)})` |
| 127 | `jsonify({'error': 'Not found'})` → `jsonify({'detail': 'Not found'})` |
| 173 | `jsonify({'error': str(e)})` → `jsonify({'detail': str(e)})` |

**`src/pybend/core/tests/profiling/dashboard.py`:**
All `JSONResponse({'error': ...})` sites (~8) → `raise HTTPException(status_code=N, detail=...)`.

### 1b. Fix status code semantics

**`src/pybend/core/api/auth_interceptor.py` — 401 vs 403:**
Line 99: unauthenticated → 401 (not 403):
```python
# Before:
return tx.error("Access denied", code=403)
# After:
return tx.error("Authentication required", code=401)
```

**`src/pybend/core/models/actor_model.py` — create/update failure → 409:**
Lines 221, 264: storage returns falsy → constraint violation, not server error:
```python
return tx.error("Create failed", code=409)  # was default 500
return tx.error("Update failed", code=409)  # was default 500
```

### 1c. Fix Level 3 custom method auth gap

**`src/pybend/core/api/auth_interceptor.py` — explicit AUTHENTICATED default:**
Lines 56-64: When no `access=` on `@expose_route`, default to AUTHENTICATED:
```python
if action not in _CRUD_OPS:
    method_access = _get_method_access(model_cls, action)
    if method_access is not None:
        ctx = AccessContext(user=user, action=action, model_class=model_cls)
        if not method_access.evaluate(ctx):
            return tx.error("Access denied", code=403)
        return tx
    # No explicit access= — default to AUTHENTICATED (matches Level 1/2)
    if not user.get('user_id'):
        return tx.error("Authentication required", code=401)
    return tx
```

**`src/pybend/core/models/actor_model.py` — Tier 2 auth for custom methods:**
In `handler()` custom method path (after line 108 `if is_exposed`), add auth check before execution:
```python
if is_exposed:
    endpoint_info = getattr(method, '__endpoint__', {})
    method_access = endpoint_info.get('access')
    if method_access is not None:
        from pybend.core.authorize import AccessContext
        ctx = AccessContext(
            user=tx.meta.get('user', {}),
            action=tx.name, model_class=cls,
        )
        if not method_access.evaluate(ctx):
            await target.send(tx.error("Access denied", code=403))
            return
    # ... existing instance resolution code continues
```

---

## Phase 2: Backend ERROR TX Consistency

### 2a. Fix Matrix message drop → return ERROR TX
**File:** `src/pybend/core/actors/matrix.py`

Replace silent drops (lines 67, 70) with error TX routing back to sender:

```python
async def _route_error(self, tx: TX) -> None:
    """Route error TX back to sender when no route is found."""
    source_root = tx.source.split('/')[0]
    if source_root in self._children:
        await self._children[source_root].inbox(
            tx.error(f"No route to '{tx.target}'", code=404)
        )
    elif self._adapters:
        error_tx = tx.error(f"No route to '{tx.target}'", code=404)
        for adapter in self._adapters:
            if adapter.can_handle(error_tx):
                await adapter.send(error_tx)
                return
```

Update `inbox()` to call `_route_error()` at both warning sites.

### 2b. Actor base class — use semantic error codes
**File:** `src/pybend/core/actors/actor.py`

In `handler()` exception catch (~line 340), use semantic mapping:
```python
except Exception as e:
    logger.error(f"[{target.addr}] Error in {tx.name}: {e}")
    from pybend.core.actors.tx import exception_to_tx_error
    await target.send(exception_to_tx_error(e, tx))
```

This replaces the default 500 with proper semantic codes (ValueError → 400, etc.).

---

## Phase 3: Frontend ERROR TX Unification

**Goal:** Single error path. All errors flow through ERROR TX. Components handle display.

### 3a. HTTP.js — Remove direct toast display
**File:** `src/pybend/static/core/transport/HTTP.js`

**Changes to all verb methods (GET/POST/PUT/DELETE):**

1. **Error path**: Remove `_toastHttpError()` calls. The `onError(json)` callback (→ NetworkAdapter.onError → ERROR TX) handles everything:
```javascript
// Before (lines ~104-108):
errorHandled = true;
return resp.json().then((json) => {
    HTTP._toastHttpError(resp.status, json);  // REMOVE this
    onError(json);
});
```
Also remove the standalone `showToast` for 404 in GET (lines 97-101) — route through `onError` instead.

2. **200-OK error path**: Route to `onError` instead of calling `onSuccess`:
```javascript
// Before (lines ~115-116):
HTTP._checkBodyForError(resp);
onSuccess(resp);

// After:
if (HTTP._checkBodyForError(resp)) {
    onError(resp);
} else {
    onSuccess(resp);
}
```
This is the key change — 200-OK errors now flow through the ERROR TX path.

3. **Reorder `_extractError()`** to check `detail` before `error` (FastAPI format primary):
```javascript
static _extractError(json, status) {
    if (!json || typeof json !== 'object') return null;
    if (Array.isArray(json.detail)) {
        return json.detail.map(e => {
            const field = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : '?';
            return `${field}: ${e.msg}`;
        }).join('; ');
    }
    if (json.detail) return String(json.detail);
    if (json.error) return String(json.error);   // legacy fallback
    if (json.message && status && status >= 400) return String(json.message);
    return null;
}
```

4. **Keep utility methods** (`_extractError`, `_extractValidationErrors`, `_checkBodyForError`, `_toastHttpError`) — they're still useful. Just stop calling `_toastHttpError` from verb methods.

### 3b. NTTElement.ERROR — Add toast display
**File:** `src/pybend/static/components/NTTElement.js`

Add toast to the base ERROR handler so all errors get ephemeral notification:
```javascript
ERROR(event) {
    const response = event?.meta?.response;
    const d = response || event?.data;

    if (d && Array.isArray(d.detail) && d.detail.length > 0) {
        const validationErrors = d.detail.map(e => ({
            field: Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : '?',
            message: e.msg, type: e.type, input: e.input,
        }));
        this.error = validationErrors.map(e => `${e.field}: ${e.message}`).join('; ');
        showToast(this.error, 'error');  // ADD toast
        Logging.error(`[NTTElement] ${this.schema?.__name__ || '?'} — ERROR`, this.error);
        this.onValidationError(validationErrors);
        return;
    }

    const msg = (typeof d === 'string') ? d
      : d?.detail || d?.error || d?.message || 'An error occurred';
    this.error = msg;
    showToast(msg, 'error');  // ADD toast
    Logging.error(`[NTTElement] ${this.schema?.__name__ || '?'} — ERROR`, msg);
    this.scheduleRender();
}
```

Add `showToast` import at top of file.

### 3c. Frontend error boundaries — try/catch in Actor._inbox()
**File:** `src/pybend/static/core/Actor.js`

In `_inbox()` (line 130), fix two issues:

1. **Missing handler**: log warning and return instead of throwing:
```javascript
// Before (lines 141-142):
Logging.warn(`No handler for event ${tx.name}`)
throw new Error(`No handler for event ${tx.name}.`);

// After:
Logging.warn(`[${this.addr || Type.addr}] No handler for '${tx.name}', ignoring`);
return tx;
```

2. **Handler execution**: wrap in try/catch:
```javascript
// Before (lines 136-139):
if (typeof this[tx.name] === "function") {
    return this[tx.name](tx.data, tx);
} else if(tx.name in Prototype){
    return Prototype[tx.name].call(this, tx.data);
}

// After:
try {
    if (typeof this[tx.name] === "function") {
        return this[tx.name](tx.data, tx);
    } else if (tx.name in Prototype) {
        return Prototype[tx.name].call(this, tx.data);
    }
} catch (e) {
    Logging.error(`[${this.addr || Type.addr}] Error in handler '${tx.name}':`, e.message);
    return tx;
}
```

3. **Route error in _send()**: Replace throw at lines 94-97 with log + return:
```javascript
// Before:
Logging.error(`Cannot route to ${targetChild}`)
throw new Error(`Cannot route message to target: ${targetChild}.`);

// After:
Logging.error(`[Actor.${this.addr}] Cannot route to '${targetChild}' — no such child`);
return tx;
```

### 3d. Frontend Matrix error boundary
**File:** `src/pybend/static/core/Matrix.js`

Wrap child inbox dispatch in try/catch (line 39):
```javascript
// Before:
tx = this.children.get(targetAddr).inbox(tx)

// After:
try {
    tx = this.children.get(targetAddr).inbox(tx);
} catch (e) {
    Logging.error(`[Matrix] Error dispatching '${tx.name}' to ${targetAddr}:`, e.message);
}
```

### 3e. Simplify NTT._response_ handler
**File:** `src/pybend/static/core/NTT.js`

With errors now routing through ERROR TX (Priority 2 fix ensures 200-OK errors → onError), the defensive check in `_response_` is no longer needed:

```javascript
// Before (lines 1086-1096):
DynamicClass.prototype._response_ = function(data, tx) {
    if (data && typeof data === 'object') {
        const errorMsg = data.error || data.detail;
        if (errorMsg) {
            showToast(String(errorMsg), 'error');
            Logging.warn(`[${className}._response_] Error from method call`, errorMsg);
            return;
        }
    }
    this.pull();
};

// After:
DynamicClass.prototype._response_ = function(data, tx) {
    this.pull();
};
```

The `showToast` import for `_response_` can also be removed if no other code in that scope uses it.

---

## Phase 4: Tests

### 4a. Backend unit tests

**`src/pybend/core/tests/unit/test_actor_system.py`** — add:
- Test `exception_to_tx_error` with Pydantic ValidationError → 422
- Test `exception_to_tx_error` with MethodError → uses its status_code
- Test Matrix sends ERROR TX (404) when no route found (not silent drop)

**`src/pybend/core/tests/unit/test_schema_ext.py`** — update DEFAULT_STAGES if needed.

### 4b. Integration tests

**`example_actor/tests/test_error_handling.py`** — update:
- Test 401 (not 403) for unauthenticated access
- Test 409 for create/update constraint violations
- Test Level 3 custom method without `access=` requires auth

### 4c. Frontend tests

**`src/pybend/static/tests/transport/HTTP.test.js`** — add:
- Test `_extractError` priority order: `detail` before `error`
- Test `onSuccess` NOT called when response has embedded error
- Test `onError` IS called when response has embedded error

**`src/pybend/static/tests/transport/NetworkAdapter.test.js`** — update if needed for ERROR TX flow.

---

## File Change Summary

| File | Phase | Changes |
|------|-------|---------|
| `src/pybend/core/actors/tx.py` | 0 | Add `exception_to_tx_error()` function |
| `src/pybend/core/models/actor_model.py` | 0,1 | Import from tx.py, fix 409 codes, add Tier 2 custom method auth |
| `src/pybend/core/api/network_ap.py` | 1 | `error` → `detail`, use HTTPException |
| `src/pybend/core/api/routes_flask.py` | 1 | `error` → `detail` |
| `src/pybend/core/tests/profiling/dashboard.py` | 1 | `error` → HTTPException |
| `src/pybend/core/api/auth_interceptor.py` | 1 | 401 for unauth, explicit AUTHENTICATED default |
| `src/pybend/core/actors/matrix.py` | 2 | Add `_route_error()`, stop silent drops |
| `src/pybend/core/actors/actor.py` | 2 | Use `exception_to_tx_error` in handler |
| `src/pybend/static/core/transport/HTTP.js` | 3 | Remove toasts, route 200-OK errors to onError, reorder extraction |
| `src/pybend/static/components/NTTElement.js` | 3 | Add toast to ERROR handler |
| `src/pybend/static/core/Actor.js` | 3 | Error boundaries, no-throw on missing handler |
| `src/pybend/static/core/Matrix.js` | 3 | Try/catch around child dispatch |
| `src/pybend/static/core/NTT.js` | 3 | Simplify _response_ (remove defensive check) |
| Test files (4 files) | 4 | New + updated tests |

---

## Verification

```bash
# Unit tests
cd /workspace/src/pybend/core && pytest tests/unit/ -v

# Integration tests (example_actor uses Level 3 routing)
cd /workspace && pytest example_actor/tests/ -v

# Frontend tests
cd /workspace/src/pybend/static && npx vitest run

# Manual verification
cd /workspace/example_actor && python3 main.py
# 1. curl without token → expect 401 (not 403)
# 2. curl with wrong user → expect 403
# 3. All error responses → {"detail": "..."}
# 4. Frontend: trigger error → single toast from component ERROR handler
```

Wave tag: `[0.9]`
