# Backend Core Debug Mode -- Implementation Plan

This plan implements six backend features for N3TX debug mode. Execute each section in order. Every file path is absolute from `/workspace`. Line numbers reference the current state of the codebase at commit `b4b4e82` on branch `v0.9`.

---

## Prerequisites

Before starting, verify you can run the existing tests:

```bash
cd /workspace && python3 -m pytest src/n3tx/core/tests/unit/test_discovery.py src/n3tx/core/tests/unit/test_backend.py src/n3tx/core/tests/unit/test_base_user.py -v --tb=short
```

All tests must pass before any changes.

---

## 1. Auto-Reload in Example `main.py` Files

No abstraction — keep uvicorn as a plain runner. Each example `main.py` uses the import-string form with `reload=True` when `config.DEBUG` is set.

**No changes to `src/n3tx/core/config.py`** for this step.

### File: `/workspace/example_api/main.py`

**Current state** (lines 35-37):
```python
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
```

**Replace with**:
```python
if __name__ == '__main__':
    import uvicorn
    if config.DEBUG:
        uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
    else:
        uvicorn.run(app, host=config.HOST, port=config.PORT)
```

Note: `reload=True` requires an import string (`"main:app"`), not the app object. The non-debug path keeps the object form for faster startup.

### File: `/workspace/example_actor/main.py`

Same pattern — find the `if __name__` block and replace:
```python
if __name__ == '__main__':
    import uvicorn
    if config.DEBUG:
        uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
    else:
        uvicorn.run(app, host=config.HOST, port=config.PORT)
```

### File: `/workspace/example_grants/main.py`

Same pattern:
```python
if __name__ == '__main__':
    import uvicorn
    if config.DEBUG:
        uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
    else:
        uvicorn.run(app, host=config.HOST, port=config.PORT)
```

### File: `/workspace/example_chat/main.py`

Same pattern:
```python
if __name__ == '__main__':
    import uvicorn
    if config.DEBUG:
        uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=True)
    else:
        uvicorn.run(app, host=config.HOST, port=config.PORT)
```

---

## 2. Config -> N3TXApp Flow

### Design Decision

The global `config.DEBUG` is the **single source of truth**. `N3TXApp._debug` should not be an independent flag -- it should propagate to `config.DEBUG` immediately in `__init__`, so that any code running between `N3TXApp()` construction and `build()` already sees the correct debug state.

### File: `/workspace/src/n3tx/core/app.py`

**Current state** (lines 97-137): `N3TXApp.__init__` stores `self._debug = debug` on line 136 but never uses it anywhere.

**Change 1**: In `__init__`, after storing `self._debug`, propagate to global config.

Find this code (lines 129-137):
```python
        self._models: List[Tuple[Type, Optional[AbstractStorage]]] = []
        self._join_pairs: List[Tuple[Type, Type]] = []
        self._static_dirs: List[str] = []
```

Wait -- that's lines 139-141. The `_debug` assignment is at line 136:
```python
        self._debug = debug
```

**Replace line 136** (`self._debug = debug`) with:
```python
        self._debug = debug
        if debug:
            config.configure(debug=True)
```

This ensures that when someone writes `N3TXApp(debug=True)` or `create_app(debug=True)`, the global `config.DEBUG` is set immediately. The `config.configure()` function (line 42-56 of config.py) accepts `debug` as a key (it uppercases it to `DEBUG` and sets `globals()['DEBUG']`).

**Note**: We do NOT set `config.configure(debug=False)` when `debug=False` because we don't want `N3TXApp()` (which defaults `debug=False`) to override an env-var-set `DEBUG=True`. The flow is:
1. Env var `N3TX_DEBUG=true` sets `config.DEBUG = True` at import time
2. `N3TXApp(debug=False)` (default) does NOT override it
3. `N3TXApp(debug=True)` explicitly turns it on

This is the correct semantic: environment is baseline, explicit `debug=True` is additive.

---

## 3. Auto-Admin Registration

### Design Decision

When `config.DEBUG` is `True`, newly registered users via `register_user()` get `role='admin'` instead of `role='user'`. This eliminates permission friction during development. The change is in `BaseUser.register_user()` which is the single codepath for frontend registration (the `/users/register` POST route calls this classmethod via `make_custom_post()` in `routes_fastapi.py`).

### File: `/workspace/src/n3tx/core/models/base_user.py`

**Current state** (lines 110-148): The `register_user` classmethod creates a user with default `role='user'` (from the field default on line 52). The user instance is created on line 144:
```python
        user = cls(name=name, email=email)
```

The `role` field has `default='user'` (line 52), so this user gets `role='user'`.

**Step 1**: Add module-level import. After line 21 (`from n3tx.core.authorize import ...`), add:
```python
from n3tx.core import config
```
This is safe — `config.py` is a leaf module (only imports `logging` and `os`, zero downstream deps).

**Step 2**: Insert after line 144 (`user = cls(name=name, email=email)`), before line 145 (`user._plain_password = password`):

```python
        if config.DEBUG:
            user.role = 'admin'
```

**After the change, lines 144-148 should read**:
```python
        user = cls(name=name, email=email)
        if config.DEBUG:
            user.role = 'admin'
        user._plain_password = password
        created = cls.create(user)
        token = create_token(created.id, created.email, created.role)
        return {"token": token, "user": created.model_response()}
```

**Why module-level import**: `config.py` is a leaf module with no downstream dependencies (only `logging` and `os`). It's safe to import at the top of `base_user.py`. We read `config.DEBUG` (not a snapshot) so it always reflects the current runtime state.

---

## 4. `/_meta` Debug Flag

### File: `/workspace/src/n3tx/core/api/discovery.py`

**Current state** (lines 27-76): `_build_meta()` returns a dict with keys: `name`, `version`, `base_url`, `models`, `capabilities`.

**Change**: Add `debug` key to the returned dict, reading from `config.DEBUG`.

**Step 1**: Add the import. The file already imports `logging` and `typing.Optional` at the top (lines 1-23). Add the config import after the logger line (line 24):

Find (line 24):
```python
logger = logging.getLogger('n3tx.api.discovery')
```

Replace with:
```python
logger = logging.getLogger('n3tx.api.discovery')

from n3tx.core import config
```

**Step 2**: Add `debug` to the returned dict. Find the return statement (lines 70-76):

```python
    return {
        'name': name,
        'version': version,
        'base_url': base_url,
        'models': models,
        'capabilities': caps,
    }
```

Replace with:
```python
    return {
        'name': name,
        'version': version,
        'base_url': base_url,
        'models': models,
        'capabilities': caps,
        'debug': config.DEBUG,
    }
```

---

## 5. Debug Logging Middleware

### File: `/workspace/src/n3tx/core/api/backend.py`

**Current state** (lines 53-84): `FastAPIBackend.__init__` creates the FastAPI app (line 66), adds CORS middleware (lines 73-79), calls `self._add_auth_middleware()` (line 80), and optionally adds profiling middleware (lines 82-84).

**What to add**: After the profiling middleware block (after line 84), add a debug logging middleware that logs method, path, status code, duration, and user ID for every request.

**Important ordering**: The debug logging middleware MUST be added AFTER the auth middleware because it reads `request.state.user` (set by `JWTAuthMiddleware`). In Starlette/FastAPI, middleware is executed in LIFO order (last added = outermost = runs first for request, last for response). So we actually need the debug middleware to be added BEFORE the auth middleware in code, so it wraps the auth middleware and sees the user after auth has run.

Wait -- let me reconsider. The Starlette middleware stack is LIFO: the LAST middleware added via `add_middleware()` runs FIRST on the request and LAST on the response. So:

1. Auth middleware added at line 80 (`self._add_auth_middleware()`)
2. If we add debug middleware AFTER auth, the debug middleware is outermost -- it runs FIRST on request (before auth sets user), and LAST on response.

That means `request.state.user` won't be available when the debug middleware starts. But it WILL be available after `call_next(request)` returns, because at that point the auth middleware has already run. We can read `request.state.user` AFTER `call_next`.

**Strategy**: Add the debug middleware after the auth middleware. In the dispatch, call `call_next(request)` first, then read `request.state.user` from the request and log.

**Add after line 84** (after the profiling middleware block):

```python
        if DEBUG:
            self._add_debug_logging_middleware()
```

Note: `DEBUG` is already imported on line 65: `from n3tx.core.config import DEBUG`. Actually, looking more carefully at line 65:

```python
        from n3tx.core.config import DEBUG
```

This is inside `__init__`, so it captures the value at construction time. That's fine -- `DEBUG` is set before any app is created.

**Add the new method** after `_add_auth_middleware()` (after line 121, before `register_routes`). Insert after the closing of `_add_auth_middleware`:

```python
    def _add_debug_logging_middleware(self):
        import time
        from starlette.middleware.base import BaseHTTPMiddleware

        class DebugLoggingMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                start = time.monotonic()
                response = await call_next(request)
                elapsed = (time.monotonic() - start) * 1000

                user = getattr(getattr(request, 'state', None), 'user', None) or {}
                user_id = user.get('user_id', '-')
                path = request.url.path
                method = request.method

                # Skip static file logging to reduce noise
                if any(path.endswith(ext) for ext in self.app.AUTH_EXEMPT_EXTENSIONS
                       if hasattr(self.app, 'AUTH_EXEMPT_EXTENSIONS')):
                    return response

                logger.info(
                    "[DEBUG] %s %s -> %s (%.1fms) user=%s",
                    method, path, response.status_code, elapsed, user_id,
                )
                return response

        self.app.add_middleware(DebugLoggingMiddleware)
```

Wait, there's a problem: `self.app` inside the middleware class refers to the ASGI app (the next middleware in the chain), not the `FastAPIBackend`. The `AUTH_EXEMPT_EXTENSIONS` reference won't work. Let me fix this by capturing the extensions in the closure:

**Corrected method to add after line 121**:

```python
    def _add_debug_logging_middleware(self):
        import time
        from starlette.middleware.base import BaseHTTPMiddleware

        exempt_extensions = self.AUTH_EXEMPT_EXTENSIONS

        class DebugLoggingMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                start = time.monotonic()
                response = await call_next(request)
                elapsed = (time.monotonic() - start) * 1000

                path = request.url.path

                # Skip static files to reduce noise
                if any(path.endswith(ext) for ext in exempt_extensions):
                    return response

                user = getattr(getattr(request, 'state', None), 'user', None) or {}
                user_id = user.get('user_id', '-')

                logger.info(
                    "[DEBUG] %s %s -> %s (%.1fms) user=%s",
                    request.method, path, response.status_code,
                    elapsed, user_id,
                )
                return response

        self.app.add_middleware(DebugLoggingMiddleware)
```

**And add the call in `__init__`**. Find lines 82-84:

```python
        if os.getenv('N3TX_PROFILING', '').lower() in ('1', 'true'):
            from n3tx.core.tests.profiling.middleware import ProfilingMiddleware
            self.app.add_middleware(ProfilingMiddleware)
```

**Add after line 84** (after the profiling block, before the end of `__init__`):

```python
        if DEBUG:
            self._add_debug_logging_middleware()
```

### Complete `__init__` after changes (lines 53-87):

For reference, here is what `FastAPIBackend.__init__` should look like after the change:

```python
    def __init__(self, cors_origins: list = None, ssr_mode: str = 'off', **data):
        super().__init__(**data)
        self._ssr_mode = ssr_mode
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        if cors_origins is None:
            cors_origins = ["*"]

        if "*" in cors_origins:
            logger.warning("CORS allows all origins ('*'). Set explicit origins for production.")

        from n3tx.core.config import DEBUG
        self.app = FastAPI(
            title=self.name,
            version=self.version,
            description=self.description,
            docs_url="/docs" if DEBUG else None,
            redoc_url="/redoc" if DEBUG else None,
        )
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials="*" not in cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._add_auth_middleware()

        if os.getenv('N3TX_PROFILING', '').lower() in ('1', 'true'):
            from n3tx.core.tests.profiling.middleware import ProfilingMiddleware
            self.app.add_middleware(ProfilingMiddleware)

        if DEBUG:
            self._add_debug_logging_middleware()
```

---

## 6. Unit Tests

### File: `/workspace/src/n3tx/core/tests/unit/test_debug_mode.py` (NEW FILE)

Create this file with the following content:

```python
"""
Tests for debug mode features.

Covers:
  - N3TXApp debug -> config.DEBUG propagation
  - BaseUser.register_user() auto-admin in debug mode
  - _build_meta() debug flag exposure
  - DebugLoggingMiddleware in FastAPIBackend
"""

import pytest
from unittest.mock import patch, MagicMock

from n3tx.core import config

pytestmark = pytest.mark.unit


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def restore_debug():
    """Ensure config.DEBUG is restored after each test."""
    original = config.DEBUG
    yield
    config.DEBUG = original


# ===================================================================
# 1. N3TXApp debug -> config.DEBUG propagation
# ===================================================================

class TestN3TXAppDebugPropagation:
    """N3TXApp(debug=True) should set config.DEBUG = True."""

    def test_debug_true_sets_config(self):
        """N3TXApp(debug=True) propagates to config.DEBUG."""
        config.DEBUG = False
        from n3tx.core.app import N3TXApp
        N3TXApp(debug=True)
        assert config.DEBUG is True

    def test_debug_false_does_not_override_env(self):
        """N3TXApp(debug=False) does NOT reset config.DEBUG."""
        config.DEBUG = True  # Simulate env var N3TX_DEBUG=true
        from n3tx.core.app import N3TXApp
        N3TXApp(debug=False)  # Default
        assert config.DEBUG is True  # NOT overridden

    def test_create_app_debug_true_sets_config(self):
        """create_app(debug=True) propagates to config.DEBUG."""
        config.DEBUG = False
        from n3tx.core.app import N3TXApp
        # Just test the constructor, not full build (which needs models)
        N3TXApp(debug=True)
        assert config.DEBUG is True


# ===================================================================
# 3. Auto-Admin Registration
# ===================================================================

class TestAutoAdminRegistration:
    """register_user() assigns role='admin' when config.DEBUG is True."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a temporary SQLite database."""
        from n3tx.core.storage.sqlite_storage import SQLiteStorage
        db_path = tmp_path / "test_debug_admin.db"
        storage = SQLiteStorage(database=str(db_path))
        yield storage

    @pytest.fixture
    def user_model(self, test_db):
        """A concrete User model extending BaseUser."""
        from typing import ClassVar
        from n3tx.core.models.base_user import BaseUser

        class DebugUser(BaseUser):
            __tablename__: ClassVar[str] = 'debug_users'
            __abstract__: ClassVar[bool] = False

        DebugUser.set_storage(test_db)
        DebugUser.create_table()
        yield DebugUser
        DebugUser._storage = None

    @pytest.fixture
    def configure_test_auth(self):
        """Configure auth with test secret."""
        from n3tx.core.authorize import configure
        configure(jwt_secret='test-debug-admin-secret', jwt_expiry_hours=1)
        yield
        configure(jwt_secret=config.JWT_SECRET, jwt_expiry_hours=config.JWT_EXPIRY_HOURS)

    def test_register_user_admin_when_debug_true(self, user_model, configure_test_auth):
        """When DEBUG=True, new registrations get role='admin'."""
        config.DEBUG = True
        result = user_model.register_user(
            name='DebugAlice',
            email='debugalice@example.com',
            password='pass123',
        )
        assert result['user']['role'] == 'admin'

    def test_register_user_normal_when_debug_false(self, user_model, configure_test_auth):
        """When DEBUG=False, new registrations get role='user' (default)."""
        config.DEBUG = False
        result = user_model.register_user(
            name='NormalBob',
            email='normalbob@example.com',
            password='pass123',
        )
        assert result['user']['role'] == 'user'

    def test_register_user_token_has_admin_role_when_debug(self, user_model, configure_test_auth):
        """When DEBUG=True, the JWT token also carries role='admin'."""
        config.DEBUG = True
        from n3tx.core.authorize import decode_token
        result = user_model.register_user(
            name='DebugCharlie',
            email='debugcharlie@example.com',
            password='pass123',
        )
        decoded = decode_token(result['token'])
        assert decoded['role'] == 'admin'

    def test_register_user_stored_role_is_admin_when_debug(self, user_model, configure_test_auth):
        """When DEBUG=True, the stored user record has role='admin'."""
        config.DEBUG = True
        user_model.register_user(
            name='DebugDiana',
            email='debugdiana@example.com',
            password='pass123',
        )
        users = user_model.list()
        diana = next((u for u in users if u.email == 'debugdiana@example.com'), None)
        assert diana is not None
        assert diana.role == 'admin'

    def test_existing_user_role_unaffected_by_debug(self, user_model, configure_test_auth):
        """DEBUG mode only affects new registrations, not existing users."""
        # Register with DEBUG=False
        config.DEBUG = False
        user_model.register_user(
            name='ExistingEve',
            email='existingeve@example.com',
            password='pass123',
        )

        # Turn on DEBUG — existing user should still be 'user'
        config.DEBUG = True
        users = user_model.list()
        eve = next((u for u in users if u.email == 'existingeve@example.com'), None)
        assert eve.role == 'user'


# ===================================================================
# 4. _build_meta() debug flag
# ===================================================================

class TestBuildMetaDebugFlag:
    """_build_meta() should include 'debug' key from config.DEBUG."""

    def test_debug_true_in_meta(self):
        """When DEBUG=True, meta includes debug: True."""
        config.DEBUG = True
        from n3tx.core.api.discovery import _build_meta
        meta = _build_meta({}, 'App', '1.0', 'http://localhost:5000')
        assert meta['debug'] is True

    def test_debug_false_in_meta(self):
        """When DEBUG=False, meta includes debug: False."""
        config.DEBUG = False
        from n3tx.core.api.discovery import _build_meta
        meta = _build_meta({}, 'App', '1.0', 'http://localhost:5000')
        assert meta['debug'] is False

    def test_debug_key_exists(self):
        """The 'debug' key is always present in meta output."""
        from n3tx.core.api.discovery import _build_meta
        meta = _build_meta({}, 'App', '1.0', 'http://localhost:5000')
        assert 'debug' in meta

    def test_debug_is_boolean(self):
        """The 'debug' value is a boolean, not a string."""
        from n3tx.core.api.discovery import _build_meta
        meta = _build_meta({}, 'App', '1.0', 'http://localhost:5000')
        assert isinstance(meta['debug'], bool)


# ===================================================================
# 5. Debug Logging Middleware
# ===================================================================

class TestDebugLoggingMiddleware:
    """FastAPIBackend adds DebugLoggingMiddleware when DEBUG=True."""

    def test_middleware_added_when_debug_true(self):
        """When DEBUG=True, the app has more middleware than DEBUG=False."""
        config.DEBUG = True
        from n3tx.core.api.backend import FastAPIBackend
        backend_debug = FastAPIBackend(
            name="test", description="test", version="1.0.0",
        )
        debug_middleware_count = len(backend_debug.app.user_middleware)

        config.DEBUG = False
        backend_nodebug = FastAPIBackend(
            name="test", description="test", version="1.0.0",
        )
        nodebug_middleware_count = len(backend_nodebug.app.user_middleware)

        assert debug_middleware_count > nodebug_middleware_count

    def test_middleware_not_added_when_debug_false(self):
        """When DEBUG=False, no debug logging middleware is added."""
        config.DEBUG = False
        from n3tx.core.api.backend import FastAPIBackend
        backend = FastAPIBackend(
            name="test", description="test", version="1.0.0",
        )
        # Collect middleware class names
        middleware_names = [m.cls.__name__ for m in backend.app.user_middleware]
        assert 'DebugLoggingMiddleware' not in middleware_names

    def test_middleware_present_when_debug_true(self):
        """When DEBUG=True, DebugLoggingMiddleware is in the stack."""
        config.DEBUG = True
        from n3tx.core.api.backend import FastAPIBackend
        backend = FastAPIBackend(
            name="test", description="test", version="1.0.0",
        )
        middleware_names = [m.cls.__name__ for m in backend.app.user_middleware]
        assert 'DebugLoggingMiddleware' in middleware_names
```

---

## Execution Checklist

After implementing all changes, run these verification steps:

### Step 1: Run the new unit tests

```bash
cd /workspace && python3 -m pytest src/n3tx/core/tests/unit/test_debug_mode.py -v --tb=short
```

All tests must pass.

### Step 2: Run existing tests to verify no regressions

```bash
cd /workspace && python3 -m pytest src/n3tx/core/tests/unit/test_discovery.py src/n3tx/core/tests/unit/test_backend.py src/n3tx/core/tests/unit/test_base_user.py -v --tb=short
```

All existing tests must still pass.

### Step 3: Run the full unit test suite

```bash
cd /workspace && python3 -m pytest src/n3tx/core/tests/unit/ -v --tb=short
```

### Step 4: Verify manually (optional)

```bash
# Start with DEBUG=True
cd /workspace/example_api && N3TX_DEBUG=true python3 main.py

# In another terminal:
# 1. Check /_meta has debug: true
curl -s http://localhost:5000/_meta | python3 -c "import sys,json; d=json.load(sys.stdin); print('debug:', d.get('debug'))"

# 2. Register a user, check role is admin
curl -s -X POST http://localhost:5000/users/register \
  -H 'Content-Type: application/json' \
  -d '{"name":"TestUser","email":"test@debug.com","password":"test123"}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('role:', d['user']['role'])"

# 3. Check server logs show [DEBUG] request lines
```

---

## Summary of All File Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `/workspace/src/n3tx/core/config.py` | NO CHANGE | (no `run()` helper — uvicorn stays plain) |
| `/workspace/src/n3tx/core/app.py` | EDIT line 136 | Add `config.configure(debug=True)` after `self._debug = debug` |
| `/workspace/src/n3tx/core/models/base_user.py` | INSERT after line 144 | Auto-admin: set `user.role = 'admin'` when `config.DEBUG` |
| `/workspace/src/n3tx/core/api/discovery.py` | EDIT line 24, lines 70-76 | Import config; add `'debug': config.DEBUG` to return dict |
| `/workspace/src/n3tx/core/api/backend.py` | ADD method + call | `_add_debug_logging_middleware()` method; call in `__init__` after profiling block |
| `/workspace/example_api/main.py` | EDIT lines 35-37 | Inline auto-reload: `uvicorn.run("main:app", reload=True)` when DEBUG |
| `/workspace/example_actor/main.py` | EDIT lines 36-38 | Inline auto-reload: `uvicorn.run("main:app", reload=True)` when DEBUG |
| `/workspace/example_grants/main.py` | EDIT lines 51-53 | Inline auto-reload: `uvicorn.run("main:app", reload=True)` when DEBUG |
| `/workspace/example_chat/main.py` | EDIT lines 67-69 | Inline auto-reload: `uvicorn.run("main:app", reload=True)` when DEBUG |
| `/workspace/src/n3tx/core/tests/unit/test_debug_mode.py` | NEW file | All unit tests for debug mode features |

---

## Edge Cases and Design Notes

1. **`N3TXApp(debug=False)` does not reset `config.DEBUG`**: Only `debug=True` propagates. This prevents `create_app()` (which defaults `debug=False`) from overriding `N3TX_DEBUG=true` environment variable.

2. **Auto-admin only affects `register_user()`**: The `BaseUser.create()` classmethod (used for programmatic/seed creation) is NOT modified. Only frontend registration via the `/register` endpoint gets auto-admin. This is intentional -- seed scripts should control roles explicitly.

3. **`_build_meta()` reads `config.DEBUG` at call time, not import time**: Since `config.DEBUG` can be changed by `configure()` at runtime, the meta endpoint correctly reflects the current state on each request.

4. **Debug middleware skips static files**: The middleware checks `path.endswith(ext)` against `AUTH_EXEMPT_EXTENSIONS` to avoid logging noise from `.js`, `.css`, `.html` requests.

5. **Middleware ordering**: `DebugLoggingMiddleware` is added AFTER `JWTAuthMiddleware` in code, making it the outermost middleware. It reads `request.state.user` AFTER `call_next()` returns (post-response), which is after the auth middleware has set it.

6. **Auto-reload in examples**: Each example `main.py` handles it inline — no shared helper. `reload=True` requires the import-string form (`"main:app"`), non-debug keeps the object form for faster startup.
