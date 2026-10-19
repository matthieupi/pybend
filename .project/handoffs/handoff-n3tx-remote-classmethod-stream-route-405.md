# Handoff: RemoteMatrix streams classmethod capability to instance URL and gets 405

Date: 2026-06-17
Repo: Gaussian Splat Capture Portal / N3TX app
Audience: N3TX framework team

## ✅ Summary

The app now correctly uses N3TX `RemoteMatrix.stream()` instead of a raw HTTP/SSE bridge for app → compute streaming. That fixed the previous `IncompleteRead(0 bytes read)` failure.

The next runtime error occurs when the app starts the compute pipeline from the Run page:

```text
Client error '405 Method Not Allowed' for url
'http://compute:7200/ComputePipeline/0/upload_to_splat'
```

The compute capability is already actor-wrapped as `ComputePipeline(ActorModel)`, but the remote stream path resolves to the wrong URL shape.

## 📍 Current application shape

App sends a distributed stream TX:

```python
TX(
    name="upload_to_splat",
    source="app",
    target="n3tx://compute/ComputePipeline/0",
    data={"run_id": ..., "files": ..., "options": ...},
    meta={"stream": True, "user": service_user},
)
```

Compute exposes the capability:

```python
class ComputePipeline(ActorModel):
    __tablename__ = "compute_pipeline"
    __storable__ = False

    @classmethod
    @expose_route("/upload-to-splat", methods=["POST"], stream=True, events={"status": ComputeEvent})
    async def upload_to_splat(cls, run_id: str, files: list = None, options: dict = None):
        ...
```

Relevant files:

| File | Purpose |
| --- | --- |
| `modules/app/services/compute_gateway.py` | Sends the distributed stream TX through Matrix/RemoteMatrix |
| `modules/compute/actors/ComputePipeline.py` | Non-storable actor capability wrapping upload-to-splat pipeline |
| `modules/compute/main.py` | Compute service bootstrap with `routing="actor"` |
| `lib/n3tx/packages/n3tx-actors/src/n3tx_actors/api/remote_matrix.py` | Remote stream URL resolution |

## 🔎 Observed route behavior

Using `TestClient(modules.compute.main.app)` locally:

```text
GET  /ComputePipeline                         -> 200 ✅ schema
POST /ComputePipeline/upload-to-splat          -> 200 ✅ stream route works
POST /compute_pipeline/upload-to-splat         -> 200 ✅ table route works
POST /ComputePipeline/0/upload_to_splat        -> 405 ❌ observed failing URL shape
POST /ComputePipeline/0/upload-to-splat        -> 405 ❌ instance route also not registered
```

So the actor wrapper exists and works at the class/table route level. The failure is route resolution, not missing compute wrapping.

## 🧩 Suspicious schema detail

`GET /ComputePipeline` returns method metadata like:

```json
{
  "methods": {
    "upload_to_splat": {
      "route": "/upload-to-splat",
      "methods": ["POST"],
      "scope": "instancemethod",
      "stream": true
    }
  }
}
```

But the Python method is declared as a `@classmethod`, and the working generated route is class-level:

```text
/ComputePipeline/upload-to-splat
```

This mismatch likely causes `RemoteMatrix._stream_url_for()` to choose an instance URL:

```python
if scope in ('instancemethod', 'instance', 'self'):
    return f'{base}/{class_name}/{ident}{route}'
return f'{base}/{class_name}{route}'
```

Because schema says `scope: instancemethod`, RemoteMatrix uses:

```text
/ComputePipeline/0/upload-to-splat
```

If schema lookup fails, it falls back further to:

```text
/ComputePipeline/0/upload_to_splat
```

which matches the runtime 405 reported by the app.

## 🧪 Existing framework evidence

The framework already has a relevant test:

`lib/n3tx/packages/n3tx-actors/src/n3tx_actors/tests/test_remote_matrix.py`

```python
async def test_stream_uses_schema_route_for_class_method(self):
    ...
    assert requests[0][:2] == ('GET', 'http://compute:7200/ComputePipeline')
    assert requests[1][:2] == ('POST', 'http://compute:7200/ComputePipeline/upload-to-splat')
```

That test uses schema metadata with:

```json
"scope": "class"
```

The app’s real compute schema currently reports `scope: instancemethod` for a classmethod.

## 🎯 Requested N3TX fix

Please investigate and fix the framework contract for exposed classmethod routes, especially streaming classmethod routes on non-storable `ActorModel` service capabilities.

Expected contract:

```text
@classmethod + @expose_route(...)
  -> schema.methods[name].scope == "class"
  -> RemoteMatrix.stream(TX target n3tx://compute/ComputePipeline/0)
  -> POST /ComputePipeline/<decorator-route>
```

For this case:

```text
upload_to_splat -> /ComputePipeline/upload-to-splat
```

## 💡 Likely fix areas

Please inspect these framework areas:

| Area | Question |
| --- | --- |
| schema method extraction | Does it preserve/recognize `@classmethod` when combined with `@expose_route`? |
| decorator ordering | Does `@classmethod` outside `@expose_route` hide endpoint metadata or scope detection? |
| actor route generation | Why is class route generated while schema says `instancemethod`? |
| RemoteMatrix fallback | Should stream fallback use schema route when route exists even if scope is wrong/missing? |
| class actor addressing | Is `n3tx://service/Class/0` the right representation for class capabilities, or should a class-ref target be supported? |

## 📊 Candidate fixes

| Option | Change | Pros | Risk |
| --- | --- | --- | --- |
| A | Fix schema scope for `@classmethod @expose_route` to `class` | Aligns schema with generated routes; likely correct root fix | Need ensure no regression for instance methods |
| B | Register instance mirror routes for non-storable classmethod actors | Makes current misclassified scope less fatal | Adds extra URL surface; masks schema bug |
| C | Teach RemoteMatrix to prefer class route for non-storable service actors | Fixes this app path | Requires schema knowledge of storable/service nature; less general |
| D | Support class-only distributed targets (`n3tx://compute/ComputePipeline`) | Cleaner addressing for service actors | Broader parser/addressing change |

Recommended: **Option A first**. The schema is the universal N3TX contract, and right now it disagrees with the generated route table.

## 🧪 Suggested tests to add upstream

Add framework tests that use a real `ActorModel` class instead of mocked schema only:

1. Schema extraction:

```python
class ComputePipeline(ActorModel):
    __tablename__ = "compute_pipeline"
    __storable__ = False

    @classmethod
    @expose_route("/upload-to-splat", methods=["POST"], stream=True)
    async def upload_to_splat(cls, run_id: str):
        yield {"status": "complete"}

assert ComputePipeline.schema()["methods"]["upload_to_splat"]["scope"] == "class"
assert ComputePipeline.schema()["methods"]["upload_to_splat"]["route"] == "/upload-to-splat"
```

2. Generated actor route table:

```python
POST /ComputePipeline/upload-to-splat -> 200
POST /ComputePipeline/0/upload-to-splat -> not the required route
```

3. End-to-end RemoteMatrix stream with a real app schema:

```python
RemoteMatrix.stream(TX(
    name="upload_to_splat",
    target="n3tx://compute/ComputePipeline/0",
    meta={"stream": True},
))

# should GET /ComputePipeline then POST /ComputePipeline/upload-to-splat
```

## ✅ App-side workaround status

No app workaround has been applied for this issue yet.

I initially started adding app tests expecting a route hint in TX metadata, but stopped after confirming that framework `RemoteMatrix` already owns schema route lookup. The right fix should be in the N3TX schema/route contract rather than adding app-specific route metadata.

## ⚠️ Runtime impact

This blocks the production upload-to-splat flow after clicking “Start pipeline” on the Run page. Upload and storage handoff are working; the failure occurs when streaming the compute actor capability remotely.
