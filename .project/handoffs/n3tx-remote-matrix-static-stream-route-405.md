# Bug Report: `RemoteMatrix.stream()` uses `/Class/id/method_name` fallback instead of schema route for static/class streaming methods

## ✅ Summary

`RemoteMatrix.stream()` can produce an incorrect remote URL for a schema-declared streaming actor method.

For a static service capability exposed as:

```python
@staticmethod
@expose_route("/upload-to-splat", methods=["POST"], stream=True)
async def upload_to_splat(...):
    ...
```

the expected remote call is:

```text
POST /ComputePipeline/upload-to-splat
```

but the observed remote call is:

```text
POST /ComputePipeline/0/upload_to_splat
```

This returns:

```text
405 Method Not Allowed
```

The bad URL is wrong in two ways:

1. It treats a static service capability as an instance method by inserting `/0`.
2. It uses the Python method name `upload_to_splat` instead of the decorated route `/upload-to-splat`.

---

## 📍 Context

We have a distributed N3TX deployment with three nodes:

```text
app node      -> user-facing N3TX app
compute node  -> actor-backed compute capability
storage node  -> file/artifact service
```

The app calls compute through N3TX actor networking using a streamed TX:

```python
TX(
    name="upload_to_splat",
    source="app",
    target="n3tx://compute/ComputePipeline/0",
    data={
        "run_id": "...",
        "files": [...],
        "options": {...},
    },
    meta={
        "stream": True,
        "user": {...},
    },
)
```

The app then consumes the stream through `RemoteMatrix.stream()` / `matrix.stream(...)`.

---

## ❌ Observed error

The app receives this activity entry after starting the pipeline:

```json
{
  "id": 0,
  "image": "",
  "name": "status",
  "run_id": 3,
  "run_key": "Capture · 28 images",
  "status": "failed",
  "message": "Gaussian splat pipeline failed.",
  "data": {
    "error": "Client error '405 Method Not Allowed' for url 'http://compute:7200/ComputePipeline/0/upload_to_splat'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/405"
  }
}
```

---

## ✅ Expected behavior

Given this actor method:

```python
from typing import ClassVar

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.utils.decorators import expose_route


class ComputePipeline(ActorModel):
    __tablename__: ClassVar[str] = "compute_pipeline"
    __storable__: ClassVar[bool] = False

    @staticmethod
    @expose_route("/upload-to-splat", methods=["POST"], stream=True)
    async def upload_to_splat(
        run_id: str,
        files: list = None,
        options: dict = None,
    ):
        yield {
            "name": "status",
            "status": "complete",
            "message": "done",
            "data": {},
        }
```

`RemoteMatrix.stream()` should resolve the route from schema metadata:

```text
GET  http://compute:7200/ComputePipeline
POST http://compute:7200/ComputePipeline/upload-to-splat
```

It should not synthesize:

```text
POST http://compute:7200/ComputePipeline/0/upload_to_splat
```

---

## 🔎 Why this matters

`upload_to_splat` is a service capability, not an instance operation.

It does not use `self` or `cls`, and it is exposed as a static/class-like actor method. The stable public route is the schema-declared route:

```text
/ComputePipeline/upload-to-splat
```

The fallback route:

```text
/ComputePipeline/0/upload_to_splat
```

breaks generated route semantics and returns `405 Method Not Allowed`.

---

## 🧪 Minimal reproduction

### 1. Define a non-storable actor capability

```python
from typing import ClassVar

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.utils.decorators import expose_route


class ComputePipeline(ActorModel):
    __tablename__: ClassVar[str] = "compute_pipeline"
    __storable__: ClassVar[bool] = False

    @staticmethod
    @expose_route("/upload-to-splat", methods=["POST"], stream=True)
    async def upload_to_splat(
        run_id: str,
        files: list = None,
        options: dict = None,
    ):
        yield {
            "name": "status",
            "status": "complete",
            "message": "done",
            "data": {},
        }
```

### 2. Register it in an actor-routed compute app

```python
from n3tx_core.app import create_app

app = create_app(
    models=[ComputePipeline],
    routing="actor",
    service_name="compute",
)
```

### 3. From another node, call it through `RemoteMatrix`

```python
from n3tx_actors.tx import TX
from n3tx_actors.matrix import matrix

tx = TX(
    name="upload_to_splat",
    source="app",
    target="n3tx://compute/ComputePipeline/0",
    data={
        "run_id": "run-1",
        "files": [],
        "options": {},
    },
    meta={
        "stream": True,
        "user": {
            "user_id": -1,
            "email": "app@service.local",
            "role": "service",
        },
    },
)

async for chunk in matrix.stream(tx, timeout=None):
    print(chunk)
```

### 4. Observed bad request

The remote adapter sends:

```text
POST http://compute:7200/ComputePipeline/0/upload_to_splat
```

which returns:

```text
405 Method Not Allowed
```

---

## 🧭 Schema expectation

The compute schema endpoint should expose:

```json
{
  "methods": {
    "upload_to_splat": {
      "route": "/upload-to-splat",
      "methods": ["POST"],
      "scope": "staticmethod",
      "stream": true
    }
  }
}
```

If schema route lookup succeeds, `RemoteMatrix` has enough information to call:

```text
/ComputePipeline/upload-to-splat
```

---

## ⚠️ Related suspected framework issue: staticmethod scope detection

Static methods may be incorrectly reported as `instancemethod` if the schema extractor does something like:

```python
method = getattr(cls, method_name)

if isinstance(method, staticmethod):
    ...
```

This does not work because `getattr(cls, method_name)` unwraps `staticmethod` and returns the underlying function.

The schema extractor should inspect the raw descriptor:

```python
raw_method = inspect.getattr_static(cls, method_name)

if isinstance(raw_method, staticmethod):
    scope = "staticmethod"
elif isinstance(raw_method, classmethod):
    scope = "classmethod"
else:
    scope = "instancemethod"
```

Then use the descriptor’s underlying function for endpoint metadata and type hints:

```python
descriptor_func = (
    raw_method.__func__
    if isinstance(raw_method, (staticmethod, classmethod))
    else method
)

endpoint_info = descriptor_func.__endpoint__
```

---

## ⚠️ Decorator order detail

This order works with the current `expose_route()` implementation:

```python
@staticmethod
@expose_route("/upload-to-splat", methods=["POST"], stream=True)
async def upload_to_splat(...):
    ...
```

Python applies decorators bottom-up:

```text
1. expose_route(function) -> wrapper with __endpoint__
2. staticmethod(wrapper) -> static descriptor
```

This reverse order may fail:

```python
@expose_route("/upload-to-splat", methods=["POST"], stream=True)
@staticmethod
async def upload_to_splat(...):
    ...
```

because `expose_route()` receives a `staticmethod` object rather than a function. In our local check, this produced:

```text
AttributeError: 'staticmethod' object has no attribute '__globals__'
```

---

## ✅ Suggested fixes

### Fix 1: Correct schema scope detection

In `ProtoModel.__n3tx_methods_json_signature__()` or equivalent schema method extractor:

- use `inspect.getattr_static(cls, method_name)` to detect `staticmethod` / `classmethod`
- use the raw descriptor’s `__func__` to read `__endpoint__`, `__globals__`, and type hints
- emit accurate schema scope:
  - `staticmethod`
  - `classmethod`
  - `instancemethod`

### Fix 2: Make `RemoteMatrix.stream()` fail loudly or log clearly on schema route lookup failure

If `RemoteMatrix.stream()` cannot fetch schema or cannot find method route metadata, it appears to fall back to:

```text
/{ClassName}/{id}/{tx.name}
```

That fallback is dangerous for exposed methods with custom route names.

Recommended behavior:

- log a warning with schema URL and failure reason when schema lookup fails
- include response status/body where possible
- only fall back if explicitly safe
- prefer schema route for all exposed methods

### Fix 3: For non-instance scopes, never include `{id}` in remote method URL

If schema says:

```json
"scope": "staticmethod"
```

or:

```json
"scope": "classmethod"
```

then route should be:

```text
/{ClassName}{route}
```

not:

```text
/{ClassName}/{id}{route}
```

---

## 🧪 Suggested tests

### Static method schema scope

```python
def test_static_exposed_method_schema_reports_static_scope():
    class StaticScopePipeline(ActorModel):
        __tablename__ = "static_scope_pipeline"
        __storable__ = False

        @staticmethod
        @expose_route("/run-task", methods=["POST"], stream=True)
        async def run_task(task_id: str):
            yield {"status": "done"}

    method = StaticScopePipeline.schema()["methods"]["run_task"]

    assert method["route"] == "/run-task"
    assert method["scope"] == "staticmethod"
    assert method["stream"] is True
```

### RemoteMatrix stream uses schema route

```python
async def test_remote_matrix_stream_uses_static_schema_route():
    requests = []

    def handler(request):
        requests.append((request.method, str(request.url)))

        if request.method == "GET":
            return httpx.Response(200, json={
                "methods": {
                    "upload_to_splat": {
                        "route": "/upload-to-splat",
                        "scope": "staticmethod",
                        "stream": True,
                        "methods": ["POST"],
                    }
                }
            })

        return httpx.Response(
            200,
            content='event: done\ndata: {"data": {}, "meta": {"stream_end": true}}\n\n',
            headers={"content-type": "text/event-stream"},
        )

    adapter = RemoteMatrix(
        remotes={"compute": {"url": "http://compute:7200", "token": "token"}},
        service_name="app",
    )
    adapter._transport = httpx.MockTransport(handler)

    tx = TX(
        name="upload_to_splat",
        source="app",
        target="n3tx://compute/ComputePipeline/0",
        data={"run_id": "run-1"},
        meta={"stream": True},
    )

    chunks = [chunk async for chunk in adapter.stream(tx, timeout=1)]

    assert requests[0] == ("GET", "http://compute:7200/ComputePipeline")
    assert requests[1] == ("POST", "http://compute:7200/ComputePipeline/upload-to-splat")
```

### No synthetic fallback when schema route exists

```python
def test_remote_matrix_does_not_use_python_method_name_when_schema_route_exists():
    # Assert this is never called when schema includes route metadata:
    # /ComputePipeline/0/upload_to_splat
    ...
```

---

## 📊 Impact

| Area | Impact |
| --- | --- |
| Distributed actor streaming | Broken for static/class methods if schema lookup/scope fails |
| Non-storable service actors | Especially affected |
| Custom route names | Affected because fallback uses Python method name |
| Runtime symptom | `405 Method Not Allowed` |
| Workaround | Manual raw HTTP or local route special-casing, but that bypasses N3TX design |

---

## ✅ Desired final behavior

For this method:

```python
@staticmethod
@expose_route("/upload-to-splat", methods=["POST"], stream=True)
async def upload_to_splat(...):
    ...
```

and this TX:

```python
TX(
    name="upload_to_splat",
    target="n3tx://compute/ComputePipeline/0",
    meta={"stream": True},
)
```

`RemoteMatrix.stream()` should resolve:

```text
GET  /ComputePipeline
POST /ComputePipeline/upload-to-splat
```

and should not call:

```text
POST /ComputePipeline/0/upload_to_splat
```
