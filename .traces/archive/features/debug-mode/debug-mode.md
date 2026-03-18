# Debug Mode Feature

## Context

N3TX has a basic `DEBUG` flag (`config.py:21`) that controls Swagger docs visibility and error traceback detail. This plan extends it into a full debug mode that accelerates development: auto-reload on code changes, auto-admin for new users (skip permission friction), and rich method call feedback in the frontend.

## Changes

### 1. Auto-Reload Server Startup

**Add `run()` helper** to `src/n3tx/core/config.py`:
- When `DEBUG=True` and app passed as import string: `uvicorn.run(string, reload=True, reload_dirs=[cwd])`
- When `DEBUG=True` and app passed as object: warn, run without reload
- When `DEBUG=False`: standard `uvicorn.run(app)`
- Accept `host`, `port`, `**kwargs` pass-through

**Update all example `main.py` files** (`example_api/`, `example_actor/`, `example_grants/`, `example_chat/`):
- Replace `uvicorn.run(app, ...)` with `from n3tx.core.config import run; run("main:app")`

### 2. Wire `N3TXApp._debug` to `config.DEBUG`

**File: `src/n3tx/core/app.py`** — in `N3TXApp.build()`, add at the top:
```python
if self._debug:
    config.configure(debug=True)
```
Currently `_debug` is stored but never propagated to the global config.

### 3. Auto-Admin Registration

**File: `src/n3tx/core/models/base_user.py`** — in `register_user()`, after creating the user instance (line 144):
```python
from n3tx.core import config as _cfg
if _cfg.DEBUG:
    user.role = 'admin'
```
All new registrations get `role='admin'` in debug mode. Existing users and programmatic creation unaffected.

### 4. Expose Debug Flag via `/_meta`

**File: `src/n3tx/core/api/discovery.py`** — in `_build_meta()`, add to the returned dict:
```python
from n3tx.core import config
...
return {
    ...existing keys...,
    'debug': config.DEBUG,
}
```

### 5. Method Timing Envelope (Backend)

When `config.DEBUG=True`, custom method responses get wrapped in a debug envelope.

**File: `src/n3tx/core/api/routes_fastapi.py`** — in `make_custom_post()`, wrap the `return attr(...)` calls in both `post_with_id` and `post_no_id`:
```python
import time
start = time.monotonic()
result = attr(instance, **parsed_args)
if config.DEBUG:
    elapsed = round((time.monotonic() - start) * 1000, 2)
    return {
        'result': result,
        '_debug': {
            'duration_ms': elapsed,
            'method': attr.__name__,
            'model': model_class.__name__,
        }
    }
return result
```

**File: `src/n3tx/core/api/network_api.py`** — same pattern in `_add_custom_handler()`, wrap the `api_adapter.request()` + `_response_or_raise()` calls in both `custom_with_id` and `custom_no_id`.

### 6. Debug Request Logging Middleware

**File: `src/n3tx/core/api/backend.py`** — add a `DebugLoggingMiddleware` in `FastAPIBackend.__init__()` when `DEBUG=True`:
- Logs: `[DEBUG] POST /products/1/favorite -> 200 (12.3ms) user=5`
- Added after auth middleware so `request.state.user` is available

### 7. Frontend: Read Debug Flag from `/_meta`

**File: `src/n3tx/static/config.js`** — add `applyMeta(meta)` export that sets `config.DEBUG` from `meta.debug`.

**File: `src/n3tx/static/components/ntx-topbar.js`** — in `fetchMeta().then()`, call `applyMeta(data)` to propagate the backend debug flag to the frontend config.

### 8. Frontend: Method Success Toast + Debug Info

**File: `src/n3tx/static/core/NTT.js`** — enhance the `_response_` prototype handler:
```javascript
DynamicClass.prototype._response_ = function(data, tx) {
    // Show success toast with method result
    import('../utils/Toast.js').then(({ showToast }) => {
        let message;
        if (data?._debug) {
            message = `${data._debug.method} (${data._debug.duration_ms}ms)`;
            console.debug('[N3TX Debug]', data._debug.model + '.' + data._debug.method, data);
        } else if (typeof data === 'string') {
            message = data;
        }
        if (message) showToast(message, 'success');
    });
    this.pull();
};
```

This gives users immediate visual feedback on method calls (currently silent), and in debug mode includes timing info.

### 9. Frontend: Debug Badge in Topbar

**File: `src/n3tx/static/components/ntx-topbar.js`** — in `#render()`, after `versionHtml`:
```javascript
const debugBadge = _metaCache?.debug
    ? `<span class="topbar-debug">DEBUG</span>`
    : '';
```
Insert `${debugBadge}` after `${versionHtml}` in the nav template.

**File: `src/n3tx/static/components/ntx-topbar.css`** — add `.topbar-debug` style:
- Small amber badge: `background: var(--warning, #f59e0b); color: #000; font-size: 0.6rem; font-weight: 700; padding: 0.15rem 0.4rem; border-radius: 4px;`

### 10. Tests

- **Unit test** (`src/n3tx/core/tests/unit/test_debug_mode.py`):
  - Test `run()` calls uvicorn with correct args for DEBUG=True/False (mock uvicorn.run)
  - Test `register_user()` assigns `role='admin'` when DEBUG=True
  - Test `_build_meta()` includes `debug` key

- **Integration test** (`example_api/tests/test_debug_mode.py`):
  - Register user via API, verify role is `admin`
  - Call a custom method, verify response contains `_debug` envelope with `duration_ms`
  - GET `/_meta`, verify `debug: true`

## Files Modified

| File | Change |
|------|--------|
| `src/n3tx/core/config.py` | Add `run()` helper |
| `src/n3tx/core/app.py` | Wire `_debug` → `config.DEBUG` in `build()` |
| `src/n3tx/core/models/base_user.py` | Auto-admin in `register_user()` |
| `src/n3tx/core/api/discovery.py` | Add `debug` to `_build_meta()` |
| `src/n3tx/core/api/routes_fastapi.py` | Timing envelope in `make_custom_post()` |
| `src/n3tx/core/api/network_api.py` | Timing envelope in `_add_custom_handler()` |
| `src/n3tx/core/api/backend.py` | Debug logging middleware |
| `src/n3tx/static/config.js` | Add `applyMeta()` export |
| `src/n3tx/static/core/NTT.js` | Success toast + debug info in `_response_` |
| `src/n3tx/static/components/ntx-topbar.js` | Call `applyMeta()`, render debug badge |
| `src/n3tx/static/components/ntx-topbar.css` | `.topbar-debug` style |
| `example_api/main.py` | Use `config.run()` |
| `example_actor/main.py` | Use `config.run()` |
| `example_grants/main.py` | Use `config.run()` |
| `example_chat/main.py` | Use `config.run()` |
| `src/n3tx/core/tests/unit/test_debug_mode.py` | New: unit tests |
| `example_api/tests/test_debug_mode.py` | New: integration tests |

## Verification

1. Set `N3TX_DEBUG=true`, start example_api: `cd example_api && python main.py` — verify auto-reload is on (uvicorn logs show `--reload`)
2. Register a new user via `POST /users/register` — verify the returned user has `role: "admin"`
3. Call a custom method (e.g., `POST /products/1/favorite`) — verify response includes `_debug` with `duration_ms`
4. `GET /_meta` — verify `"debug": true` in response
5. Open frontend — verify DEBUG badge appears in topbar, success toast appears on method calls with timing info
6. Run unit tests: `cd src/n3tx/core && python -m pytest tests/unit/test_debug_mode.py`
7. Run integration tests: `cd /workspace && python -m pytest example_api/tests/test_debug_mode.py`
