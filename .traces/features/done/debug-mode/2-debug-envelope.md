# Plan 2: Transport-Agnostic Debug Envelope

## Context

When `config.DEBUG=True`, custom method responses (`@expose_route`) should be wrapped with timing and debug metadata. The original plan proposed adding wrapping code in both `routes_fastapi.py` (Level 1/2) and `network_api.py` (Level 3) — two separate integration points with duplicated logic.

After exploration, we found a **more seamless approach**: the `@expose_route` decorator in `decorators.py` is annotation-only today (stores `__endpoint__` metadata, returns the function unwrapped). Both Level 1/2 and Level 3 call the decorated function directly. By enhancing the decorator to wrap with timing, we get **one file change, zero dispatch changes, all transports covered automatically.**

## Why the Decorator Approach Works

The original plan (Option 1) rejected this approach, but the cons were overstated:

| Concern | Reality |
|---------|---------|
| "Breaks return type" | Only in DEBUG mode. Frontend `_response_` handler calls `this.pull()` regardless — it ignores the response body for data. Tests run with DEBUG=False. |
| "Contaminates method signature" | `functools.wraps` preserves signature, name, doc, `__endpoint__` (via `__dict__` update). `inspect.signature()` follows `__wrapped__`. |
| "Affects model-to-model calls" | Extremely rare in practice. Only in DEBUG mode. Easily caught during dev. |
| "No transport-level context" | Instance ID available from `self.id`. User ID omitted from decorator (transport-specific). |

## Envelope Format

```python
{
    "result": <original_return_value>,  # str, dict, list, whatever
    "_debug": {
        "method": "favorite",
        "model": "Product",
        "instance_id": 42,       # from self.id, or None for classmethod
        "duration_ms": 3.14,
    }
}
```

When `config.DEBUG=False`: returns the original result unchanged (single boolean check, zero overhead).

## Implementation

### File: `src/n3tx/core/utils/decorators.py`

This is the **only file that changes**. Current state (19 lines):

```python
def expose_route(route, methods=["POST"], access=None):
    def decorator(func):
        func.__endpoint__ = {
            'route': route,
            'methods': methods,
            'access': access,
        }
        return func
    return decorator
```

Replace with:

```python
import time
import json
import logging
from functools import wraps

from n3tx.core import config

logger = logging.getLogger('n3tx.debug')


def expose_route(route, methods=["POST"], access=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not config.DEBUG:
                return func(*args, **kwargs)

            start = time.monotonic()
            result = func(*args, **kwargs)
            elapsed = round((time.monotonic() - start) * 1000, 2)

            # Extract instance_id from self (first arg for instance methods)
            instance_id = None
            if args and hasattr(args[0], 'id'):
                instance_id = getattr(args[0], 'id', None)

            # Extract model name from self.__class__ or cls
            model_name = None
            if args:
                obj = args[0]
                model_name = obj.__name__ if isinstance(obj, type) else type(obj).__name__

            # Parse JSON string results so envelope is uniform
            parsed_result = result
            if isinstance(result, str):
                try:
                    parsed_result = json.loads(result)
                except (json.JSONDecodeError, TypeError):
                    pass

            return {
                'result': parsed_result,
                '_debug': {
                    'method': func.__name__,
                    'model': model_name,
                    'instance_id': instance_id,
                    'duration_ms': elapsed,
                }
            }

        wrapper.__endpoint__ = {
            'route': route,
            'methods': methods,
            'access': access,
        }
        return wrapper
    return decorator
```

**Key design decisions:**
- `functools.wraps` preserves `__name__`, `__doc__`, `__module__`, `__qualname__`, `__annotations__`, and updates `__dict__` (which copies `__endpoint__` from the inner func). We also set `__endpoint__` explicitly on the wrapper for clarity.
- `inspect.signature()` (used in `routes_fastapi.py:279` and `actor_model.py:103`) follows `__wrapped__` automatically, so parameter introspection still works.
- JSON string results are pre-parsed in the envelope so the frontend always gets structured data.
- `config.DEBUG` is read at call time (not import time), so toggling debug works.

### Edge Cases

1. **`MethodError` exceptions** — raised inside `func()`, propagate through the wrapper unchanged. The `try/except MethodError` in `routes_fastapi.py:333` and the `except Exception` in `actor_model.py:125` catch them as before.

2. **Level 3 result handling** — `actor_model.py:130-145` checks `isinstance(result, ...)`. The envelope is a `dict`, so it takes the `dict` branch (line 132) and replies with `tx.reply(data=result)`. Works correctly.

3. **Level 1/2 result handling** — `routes_fastapi.py:332` returns the result directly. FastAPI serializes the dict to JSON. Works correctly.

4. **Non-DEBUG mode** — single `if not config.DEBUG: return func(*args, **kwargs)` early return. Zero overhead.

5. **Classmethods** — `@classmethod` wraps the `expose_route` wrapper. The descriptor handles binding. `args[0]` is the class, so `isinstance(args[0], type)` is True and `model_name = args[0].__name__`.

6. **Static methods** — `args` may be empty. `model_name` and `instance_id` will be `None`. The envelope still works.

## Tests

### File: `src/n3tx/core/tests/unit/test_debug_envelope.py` (new)

```python
"""Tests for @expose_route debug envelope wrapping."""
import pytest
from unittest.mock import patch
from n3tx.core import config
from n3tx.core.utils.decorators import expose_route

pytestmark = pytest.mark.unit

@pytest.fixture(autouse=True)
def restore_debug():
    original = config.DEBUG
    yield
    config.DEBUG = original


class FakeModel:
    __name__ = 'FakeModel'
    id = 42

    @expose_route('/action', methods=['POST'])
    def action(self):
        return '{"action": "done"}'

    @classmethod
    @expose_route('/class_action', methods=['POST'])
    def class_action(cls):
        return '{"action": "class_done"}'

    @expose_route('/dict_return', methods=['POST'])
    def dict_return(self):
        return {"key": "value"}

    @expose_route('/none_return', methods=['POST'])
    def none_return(self):
        return None

    @expose_route('/raises', methods=['POST'])
    def raises(self):
        raise ValueError("boom")


class TestDebugEnvelopeOff:
    def test_returns_raw_when_debug_false(self):
        config.DEBUG = False
        result = FakeModel.action(FakeModel())
        assert result == '{"action": "done"}'

    def test_classmethod_returns_raw_when_debug_false(self):
        config.DEBUG = False
        result = FakeModel.class_action()
        assert result == '{"action": "class_done"}'


class TestDebugEnvelopeOn:
    def test_wraps_with_envelope(self):
        config.DEBUG = True
        result = FakeModel.action(FakeModel())
        assert '_debug' in result
        assert 'result' in result
        assert result['_debug']['method'] == 'action'
        assert result['_debug']['model'] == 'FakeModel'
        assert result['_debug']['instance_id'] == 42
        assert isinstance(result['_debug']['duration_ms'], float)

    def test_json_string_parsed_in_envelope(self):
        config.DEBUG = True
        result = FakeModel.action(FakeModel())
        assert result['result'] == {"action": "done"}  # parsed, not string

    def test_dict_return_preserved(self):
        config.DEBUG = True
        result = FakeModel.dict_return(FakeModel())
        assert result['result'] == {"key": "value"}

    def test_none_return_wrapped(self):
        config.DEBUG = True
        result = FakeModel.none_return(FakeModel())
        assert result['result'] is None
        assert '_debug' in result

    def test_classmethod_envelope(self):
        config.DEBUG = True
        result = FakeModel.class_action()
        assert result['_debug']['model'] == 'FakeModel'
        assert result['_debug']['instance_id'] is None

    def test_exception_propagates(self):
        config.DEBUG = True
        with pytest.raises(ValueError, match="boom"):
            FakeModel.raises(FakeModel())

    def test_endpoint_metadata_preserved(self):
        assert hasattr(FakeModel.action, '__endpoint__')
        assert FakeModel.action.__endpoint__['route'] == '/action'

    def test_signature_preserved(self):
        from inspect import signature
        sig = signature(FakeModel.action)
        assert 'self' in sig.parameters
```

### File: `example_api/tests/test_debug_envelope.py` (new)

Integration test that starts the app with DEBUG=True and verifies the envelope comes through HTTP.

```python
"""Integration tests for debug envelope on custom methods."""
import pytest
from n3tx.core import config


@pytest.fixture(autouse=True)
def enable_debug():
    original = config.DEBUG
    config.DEBUG = True
    yield
    config.DEBUG = original


def test_custom_method_returns_debug_envelope(client, seed):
    """POST to a custom method returns _debug envelope when DEBUG=True."""
    token = seed['tokens']['alice']
    resp = client.post(
        f"/products/{seed['product_id']}/like",
        headers={"x-access-token": token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert '_debug' in data
    assert 'result' in data
    assert data['_debug']['method'] == 'like'
    assert data['_debug']['model'] == 'Product'
    assert isinstance(data['_debug']['duration_ms'], (int, float))

def test_custom_method_no_envelope_when_debug_off(client, seed):
    """POST to a custom method returns raw result when DEBUG=False."""
    config.DEBUG = False
    token = seed['tokens']['alice']
    resp = client.post(
        f"/products/{seed['product_id']}/like",
        headers={"x-access-token": token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert '_debug' not in data
```

## Verification

1. Run unit tests: `cd /workspace && python3 -m pytest src/n3tx/core/tests/unit/test_debug_envelope.py -v`
2. Run integration tests: `cd /workspace && python3 -m pytest example_api/tests/test_debug_envelope.py -v`
3. Run existing tests to verify no regressions: `cd /workspace && python3 -m pytest src/n3tx/core/tests/unit/ -v --tb=short`
4. Run example_api integration tests: `cd /workspace && python3 -m pytest example_api/tests/ -v --tb=short`

## Files Modified

| File | Change |
|------|--------|
| `src/n3tx/core/utils/decorators.py` | Enhance `@expose_route` with DEBUG timing wrapper |
| `src/n3tx/core/tests/unit/test_debug_envelope.py` | New: unit tests |
| `example_api/tests/test_debug_envelope.py` | New: integration tests |
