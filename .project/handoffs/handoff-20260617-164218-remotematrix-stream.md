# Handoff — N3TX `RemoteMatrix.stream()` Backend Primitive

Generated: 2026-06-17 16:42:18 UTC
Session focus: Provide the N3TX backend team with a focused implementation packet for adding distributed streaming support to `RemoteMatrix`.

## ✅ Executive Snapshot

- ✅ N3TX already has a solid local streaming primitive: `NetworkAdapter.stream(tx)` correlates stream chunks by TX uuid and generated `NetworkAPI` routes expose `@expose_route(stream=True)` methods as SSE.
- ❌ `RemoteMatrix` currently supports only request/response REST (`send()` → `_request_remote_rest()`); it does **not** implement `stream()`, so distributed actor streaming falls back to ad hoc HTTP clients in apps.
- 🚨 The Gaussian Splat app hit this limitation: app→compute streaming currently buffers a remote SSE response with `urllib.response.read()`, causing `IncompleteRead(0 bytes read)` during long PyCOLMAP/Nerfstudio jobs.
- 🎯 Required backend feature: `RemoteMatrix.stream(tx)` should call remote generated streaming routes, parse SSE incrementally, and yield TX chunks/errors/end events using the same contract as local `NetworkAdapter.stream()`.
- ⚠️ Key design point: remote method route mapping must handle class/static streaming methods on non-storable actors such as `ComputePipeline.upload_to_splat`, where generated routes are likely `/compute_pipeline/upload-to-splat` and `/ComputePipeline/upload-to-splat`, not `/{Class}/{id}/{method}`.

## 🎯 Current Goal and Next-Session Focus

- User goal: give the N3TX backend development team enough context to implement first-class distributed streaming in the framework.
- Latest request: create a focused handoff only around `RemoteMatrix.stream()`.
- Recommended next focus: add framework-level `RemoteMatrix.stream()` support in `n3tx-actors`, with tests proving remote SSE streaming maps back into TX stream semantics.
- Definition of done:
  - `RemoteMatrix.stream(tx)` exists and can stream from configured remote N3TX services.
  - It preserves TX stream semantics: chunk TXs, error TXs, and stream-end TXs.
  - It sends canonical service-auth headers and optional forwarded user context.
  - It supports remote generated streaming routes for class/static methods and instance methods.
  - Apps no longer need to hand-roll backend-to-backend SSE clients for N3TX actor methods.

## 🧵 Conversation Context

1. The Gaussian Splat Capture Portal uses a three-node N3TX deployment: app, compute, and storage.
2. The compute node exposes a public actor capability:
   ```python
   class ComputePipeline(ActorModel):
       __tablename__ = "compute_pipeline"
       __storable__ = False

       @classmethod
       @expose_route("/upload-to-splat", methods=["POST"], stream=True, events={"status": ComputeEvent})
       async def upload_to_splat(cls, run_id: str, files: list = None, options: dict = None):
           ...
   ```
3. The app initially called compute with a custom `urllib` HTTP/SSE bridge in `modules/app/services/compute_gateway.py`.
4. That bridge buffered the full remote SSE response:
   ```python
   with urlopen(request, timeout=None) as response:
       return response.read().decode("utf-8")
   ```
5. The user ran the real compute backend and got a browser Run activity failure:
   ```text
   Gaussian splat pipeline failed.
   error: IncompleteRead(0 bytes read)
   ```
6. The assistant suggested a short-term incremental SSE parser, but the user asked whether N3TX already has streaming primitives for this exact use case.
7. We confirmed N3TX does have local streaming primitives and generated SSE support, but lacks remote streaming in `RemoteMatrix`.
8. The user explicitly said to “Go straight to #2”, meaning implement the architecture-correct N3TX primitive rather than another app-level workaround.
9. This handoff is intended for the N3TX backend team, not just the app team.

## 📍 Repo / Workspace Context

| Concern | Value |
| --- | --- |
| Framework checkout | `/workspace/lib/n3tx/` |
| Target package | `/workspace/lib/n3tx/packages/n3tx-actors/` |
| Target file | `/workspace/lib/n3tx/packages/n3tx-actors/src/n3tx_actors/api/remote_matrix.py` |
| Local stream primitive | `/workspace/lib/n3tx/packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py` |
| Generated SSE routes | `/workspace/lib/n3tx/packages/n3tx-actors/src/n3tx_actors/api/network_api.py` |
| TX envelope | `/workspace/lib/n3tx/packages/n3tx-actors/src/n3tx_actors/tx.py` |
| Existing stream tests | `/workspace/lib/n3tx/packages/n3tx-actors/src/n3tx_actors/tests/unit/test_streaming.py` |
| App symptom file | `/workspace/modules/app/services/compute_gateway.py` |
| Compute streaming actor | `/workspace/modules/compute/actors/ComputePipeline.py` |

Framework verification likely needed:

```bash
cd /workspace/lib/n3tx && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/tests/ -q
# or repo runner if preferred/available:
cd /workspace/lib/n3tx && python3 scripts/test-backend.py --suite actors -- -q
```

App-side verification after framework primitive lands:

```bash
cd /workspace && .venv-agent/bin/python -m unittest modules.app.tests.test_compute_gateway modules.app.tests.test_app_run_actor
```

## 🗺️ Current Architecture / Flow

### Existing local streaming flow

```text
HTTP client
  -> NetworkAPI generated streaming route
  -> TX(meta.stream=True)
  -> NetworkAdapter.stream(tx)
  -> Matrix routes to local ActorModel method
  -> async generator yields chunks
  -> TX.chunk(...) / TX.end(...)
  -> NetworkAPI serializes TX envelopes as SSE
```

### Missing distributed streaming flow

```text
App actor/service
  -> TX(name="upload_to_splat", target="n3tx://compute/ComputePipeline/0", meta.stream=True)
  -> Matrix fallback adapter
  -> RemoteMatrix.stream(tx)       # missing today
  -> HTTP SSE to compute generated route
  -> parse remote SSE frames
  -> yield TX chunks/errors/end
  -> caller forwards data progressively
```

### Why this matters

- Long-running actor methods are common for compute, agents, workflows, and external integrations.
- Apps should not need per-service `urllib`/`httpx` SSE clients for N3TX actors.
- Backend-to-backend N3TX communication should stay inside TX/Matrix/NetworkAdapter boundaries.

## ✅ Completed Work Relevant to This Feature

| Slice | Files / Areas | What changed | Status |
| --- | --- | --- | --- |
| Local streaming primitive identified | `network_adapter.py` | `NetworkAdapter.stream(tx)` already yields correlated TX chunks until error or stream_end. | ✅ Existing |
| Generated SSE support identified | `network_api.py` | `_add_streaming_handler()` and `_sse_from_stream()` already expose local streaming methods over SSE. | ✅ Existing |
| Remote gap identified | `remote_matrix.py` | `RemoteMatrix` only implements request/response with `_request_remote_rest()` and `send()`; no `stream()` override. | ✅ Analysis complete |
| App-level failure reproduced by user | `compute_gateway.py` | Current app custom bridge buffers remote SSE response and failed with `IncompleteRead(0 bytes read)`. | ✅ Symptom known |

Relevant existing snippets:

```python
# n3tx_actors/api/network_adapter.py
async def stream(self, tx: TX, timeout: float = 120.0):
    queue = asyncio.Queue()
    self._pending[tx.uuid] = queue
    send_task = asyncio.create_task(self.send(tx))
    ...
    chunk = await asyncio.wait_for(queue.get(), timeout=timeout)
    yield chunk
    if chunk.is_error or chunk.meta.get('stream_end'):
        return
```

```python
# n3tx_actors/api/network_api.py
async def _sse_from_stream(adapter, tx):
    from dataclasses import asdict
    async for chunk in adapter.stream(tx, timeout=120.0):
        tx_dict = asdict(chunk)
        if chunk.is_error:
            yield _sse_frame('error', tx_dict)
            return
        if chunk.meta.get('stream_end'):
            yield _sse_frame('done', tx_dict)
            return
        yield _sse_frame('chunk', tx_dict)
```

```python
# n3tx_actors/api/remote_matrix.py current behavior
async def _request_remote_rest(self, tx: TX) -> dict:
    service, _class_name, _ident = parse_ref_string(tx.target)
    ...
    if tx.name == 'get':
        response = await client.get(url, headers=headers)
    else:
        response = await client.post(url, json=tx.data or {}, headers={...})

async def send(self, tx: TX) -> None:
    data = await self._request_remote_rest(tx)
    response = tx.reply(data=data)
    await parent.inbox(response)
```

## 🔎 Current State

### Known facts

- `RemoteMatrix.can_handle(tx)` recognizes distributed refs via `is_distributed_ref(tx.target)`.
- `RemoteMatrix._headers(tx, remote)` already creates correct service headers:
  - `Accept: application/json`
  - `X-N3TX-Service: <service>`
  - `Authorization: Bearer <token>` when configured
  - `X-N3TX-User: <json>` when `tx.meta.user` exists
- `NetworkAPI` SSE frames contain the full TX envelope serialized via `dataclasses.asdict(chunk)`.
- TX stream chunk/end helpers are on `TX`: `tx.chunk(data, seq)` and `tx.end(data, seq)`.

### Known gap

- `RemoteMatrix` does not parse remote SSE or expose a stream method.
- `RemoteMatrix._url_for(tx)` currently maps non-`get` calls to:
  ```text
  {base}/{ClassName}/{id}/{tx.name}
  ```
  This may work for instance methods, but not necessarily for class/static methods and not for decorator routes like `/upload-to-splat` where method name `upload_to_splat` differs from route path `upload-to-splat`.

### Unverified

- Exact best route source for remote method paths. Possibilities:
  1. Use target class + method schema from local registered model if available.
  2. Fetch remote schema `GET /ComputePipeline` and read `methods[tx.name].route`.
  3. Extend TX meta to carry method route path when caller knows it.
- Whether current `RemoteMatrix` should stream only distributed refs (`n3tx://service/Class/id`) or also service/class targets for non-storable actors. Existing parser requires an id segment.

## 🧩 Important Decisions and Rationale

| Decision | Rationale | Consequence / Follow-up |
| --- | --- | --- |
| Implement framework primitive, not app workaround | User explicitly requested architectural N3TX solution; internal backend communication should use TX/Matrix. | Add `RemoteMatrix.stream()` and tests before app migration. |
| Preserve TX envelopes, not raw SSE payloads | Local `NetworkAPI` stream serializes full TX objects; `NetworkAdapter.stream()` yields TXs. | Remote parser should reconstruct/normalize TXs from remote SSE frames. |
| Use service auth headers | Existing N3TX remote request path already uses these; storage bugs were caused by token-as-user-JWT misuse. | Streaming must reuse/extend `_headers()` with `Accept: text/event-stream`. |
| Treat route mapping as first-class design issue | Decorator route may not equal method name; classmethod route may not include id. | Tests must include class/static streaming method and instance streaming method cases. |

## 🧪 Verification Evidence

No code for `RemoteMatrix.stream()` was implemented in this session. Verification so far is inspection-based plus app symptom:

| Check | Result | Notes |
| --- | --- | --- |
| Inspected `network_adapter.py` | ✅ Done | Confirmed local `stream()` primitive. |
| Inspected `network_api.py` | ✅ Done | Confirmed generated SSE routes serialize full TX envelopes. |
| Inspected `remote_matrix.py` | ✅ Done | Confirmed request/response only; no stream override. |
| User runtime app→compute real run | ❌ Failed | Browser Run activity showed `IncompleteRead(0 bytes read)` through app custom bridge. |

Recommended tests to add in N3TX framework:

```bash
cd /workspace/lib/n3tx && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/tests/ -q
```

## ⚠️ Risks, Blockers, and Assumptions

| Type | Detail | Mitigation / Next action |
| --- | --- | --- |
| Risk | Method route path may differ from TX method name (`upload_to_splat` vs `/upload-to-splat`). | Resolve route via schema method metadata rather than string munging where possible. |
| Risk | Non-storable class/static actor capabilities have no real id, but distributed refs require id. | Decide and document target shape, e.g. `n3tx://compute/ComputePipeline/0`, or add class-level target support. |
| Risk | Remote stream timeouts for long compute jobs may be too short. | Make per-chunk timeout configurable; app real pipeline likely needs a large timeout or heartbeat events. |
| Risk | Remote SSE parser must handle frame padding/comments (`:` lines) from `_SSE_FLUSH_PADDING`. | Parser should ignore comments and collect only `data:` lines. |
| Risk | HTTP errors before SSE body should become TX error responses. | Mirror current `send()` error behavior: yield `tx.error(..., code=status)` and terminate. |
| Assumption | Remote generated SSE route emits `event: chunk|done|error` with JSON TX envelope in `data:`. | Confirm with `network_api.py`; add integration-style test using `NetworkAPI` if possible. |

## ✨ Recommended Next Steps

1. **Write failing `RemoteMatrix.stream()` tests.**
   - Files: `packages/n3tx-actors/src/n3tx_actors/tests/...` under `/workspace/lib/n3tx`.
   - Cover:
     - parses `event: chunk` TX envelope into yielded TX
     - parses `event: done` with `meta.stream_end`
     - parses `event: error` into error TX
     - ignores SSE comment/padding lines
     - sends service auth and user headers
   - Verify:
     ```bash
     cd /workspace/lib/n3tx && python3 -m pytest packages/n3tx-actors/src/n3tx_actors/tests/ -q
     ```

2. **Design route resolution for remote streaming methods.**
   - File: `packages/n3tx-actors/src/n3tx_actors/api/remote_matrix.py`.
   - Required cases:
     ```text
     instance method: n3tx://svc/Product/12 + tx.name='generate' -> /Product/12/<route>
     class/static method: n3tx://svc/ComputePipeline/0 + tx.name='upload_to_splat' -> /ComputePipeline/<route> or /compute_pipeline/<route>
     get: unchanged -> /Class/id
     ```
   - Prefer schema-driven route lookup if feasible:
     ```text
     GET {base}/{ClassName} -> schema.methods[tx.name].route
     ```
   - Cache schema route lookup per `(service, class_name, method)` to avoid repeated schema fetches.

3. **Implement incremental SSE parser.**
   - File: `remote_matrix.py`.
   - Sketch:
     ```python
     async def _iter_sse_json(response):
         buffer = ''
         async for text in response.aiter_text():
             buffer += text
             frames = buffer.replace('\r\n', '\n').split('\n\n')
             buffer = frames.pop()
             for frame in frames:
                 data = '\n'.join(line[5:].strip() for line in frame.split('\n') if line.startswith('data:'))
                 if data:
                     yield json.loads(data)
     ```
   - Must tolerate `_SSE_FLUSH_PADDING` comment lines beginning with `:`.

4. **Implement `RemoteMatrix.stream()`.**
   - File: `remote_matrix.py`.
   - Sketch:
     ```python
     async def stream(self, tx: TX, timeout: float = 120.0):
         service, class_name, ident = parse_ref_string(tx.target)
         remote = self._remotes[service]
         url = await self._stream_url_for(tx, service, class_name, ident)
         headers = {**self._headers(tx, remote), 'Accept': 'text/event-stream', 'Content-Type': 'application/json'}
         try:
             async with httpx.AsyncClient(timeout=None) as client:
                 async with client.stream('POST', url, json=tx.data or {}, headers=headers) as response:
                     response.raise_for_status()
                     async for payload in _iter_sse_json(response):
                         chunk = _tx_from_payload(payload, fallback=tx)
                         yield chunk
                         if chunk.is_error or chunk.meta.get('stream_end'):
                             return
         except httpx.HTTPStatusError as exc:
             yield tx.error(str(exc), code=exc.response.status_code)
         except Exception as exc:
             yield tx.error(str(exc), code=502)
     ```

5. **Update docs.**
   - Files likely:
     - `/workspace/lib/n3tx/docs/ACTORS.md`
     - `/workspace/lib/n3tx/docs/ARCHITECTURE.md`
     - package docs under `packages/n3tx-actors/docs/` if present.
   - Add remote streaming contract and route/target shape.

6. **Then app team can migrate `compute_gateway.py`.**
   - App file: `/workspace/modules/app/services/compute_gateway.py`.
   - Replace `_post_sse_request()` path with TX/Matrix stream to compute remote.
   - Verify:
     ```bash
     cd /workspace && .venv-agent/bin/python -m unittest modules.app.tests.test_compute_gateway modules.app.tests.test_app_run_actor
     ```

## 🧠 Suggested Skills / Context to Load

1. `n3tx-skill-routing` — mandatory first skill in this repo.
2. `n3tx-framework-maintenance` — this is framework internals work.
3. `n3tx-streaming` — TX stream protocol and SSE behavior.
4. `n3tx-networking` — `RemoteMatrix`, service auth, distributed refs.
5. `n3tx-actors` — ActorModel/TX/Matrix mechanics.
6. `n3tx-testing` — package and app verification strategy.
7. Canonical docs:
   - `/workspace/lib/n3tx/docs/ARCHITECTURE.md`
   - `/workspace/lib/n3tx/docs/ACTORS.md`
   - `/workspace/lib/n3tx/docs/API_REFERENCE.md`
   - `/workspace/lib/n3tx/BACKEND.md`

## 📚 Artifact References

- `/workspace/.project/handoffs/handoff-20260617-161005.md` — broader session handoff including app/compute/storage state and why remote streaming is needed.
- `/workspace/.project/plans/e2e-upload-to-splat.md` — original product plan; useful for app context but not required for framework implementation.
- `/workspace/lib/n3tx/packages/n3tx-actors/src/n3tx_actors/api/remote_matrix.py` — target implementation file.
- `/workspace/lib/n3tx/packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py` — local streaming reference implementation.
- `/workspace/lib/n3tx/packages/n3tx-actors/src/n3tx_actors/api/network_api.py` — SSE serialization route reference.
- `/workspace/lib/n3tx/packages/n3tx-actors/src/n3tx_actors/tx.py` — TX envelope and stream chunk/end helpers.
- `/workspace/modules/app/services/compute_gateway.py` — current app workaround to replace after framework primitive lands.
- `/workspace/modules/compute/actors/ComputePipeline.py` — concrete class/static streaming method that motivated this feature.

## 🔐 Sensitive Content Handling

No real secrets are included in this handoff. Runtime concepts that involve credentials are described generically:

- service token: `[REDACTED]`, represented operationally by `N3TX_SERVICE_TOKEN` / `SPLAT_INTERNAL_TOKEN`.
- user JWT/session context: `[REDACTED]`, forwarded via `X-N3TX-User` only when present.

Do not log, commit, or paste real service tokens, JWTs, cookies, passwords, private keys, uploaded user captures, or production credentials.
