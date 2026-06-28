# N3TX Plan — Minimal Location-Transparent Refs + Remote Materialization

## ✅ Executive Recommendation

Implement the desired distributed-reference behavior by completing N3TX’s existing
address/href/Matrix architecture, not by introducing a new public reference
identity subsystem.

The smallest aligned path is:

```text
Ref value == local id or href
href / $id carries location
Matrix routes addresses
remote adapters handle distant targets
n3tx-files materializes bytes when explicitly requested
```

This preserves the N3TX philosophy:

- **The model/schema remains the contract.**
- **Backend stays authoritative.**
- **Matrix owns routing.**
- **Refs point; they do not transport.**
- **File materialization remains an optional file capability.**

---

## 🎯 Goal

Support model fields such as:

```python
class Media(ActorModel):
    files: list[Ref[File]] = Field(default_factory=list)


class Run(ActorModel):
    artifacts: list[Ref[Artifact]] = Field(default_factory=list)
```

With serialized state like:

```json
{
  "files": ["http://storage:7100/File/12"],
  "artifacts": ["http://storage:7100/Artifact/42"]
}
```

without requiring local mirror rows or domain-code branching between local and
remote resources.

---

## 🧭 Design Principle

Do **not** create a new public `RefIdentity` concept.

Instead:

```text
href is the identity + location + route
Matrix is the resolver/router
Network adapters are the transport boundary
```

This mirrors the frontend runtime, where `NTT` instances keep `href` from `$id`
and call distant methods by sending TXs to that href.

---

## 🧩 Existing Frontend Pattern to Reuse

The frontend already implements the distributed shape we want on the backend:

```text
Actor.send()
  -> local child/type route if known
  -> otherwise bubble to root Matrix
  -> Matrix local child if known
  -> otherwise NetworkAdapter.send(tx)
```

Important frontend files:

| File | Existing pattern |
| --- | --- |
| `packages/n3tx-core/src/n3tx_core/static/core/Matrix.js` | Local-first routing, remote fallback |
| `packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js` | Sends TX target URL through HTTP/WS transport |
| `packages/n3tx-core/src/n3tx_core/static/core/NTT.js` | Entity `$id`/`href` carries canonical location |

Frontend example:

```js
this.href = data.$id || `${href}/${this.id}`;

this.send(new TX({
  name: method,
  source: this.addr,
  target: this.href,
  data,
  meta,
}));
```

Backend should follow the same mental model.

---

## 🗺️ Target Flow

```text
Model field
  files: list[Ref[File]]
        |
        v
SQLite JSON TEXT
  ["http://storage:7100/File/12"]
        |
        v
Read response
  preserve href unchanged
        |
        v
Explicit resolve/materialize
  TX(target="http://storage:7100/File/12")
        |
        v
Matrix
  local child? route locally
  remote href? adapter sends remotely
        |
        v
File response / File.ensure_local()
```

Ordinary reads must remain cheap and robust:

```text
GET /media/1
  -> returns raw href refs
  -> does not require storage node availability
```

Resolution/materialization is explicit.

---

## 📦 Minimal Implementation Slices

### Slice 1 — Preserve Ref hrefs in core storage

**Files**

- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
- tests under `packages/n3tx-core/src/n3tx_core/tests/unit/`

**Current issue**

Storage hydration wraps all `Ref[T]` values into local API hrefs:

```python
record[field_name] = f"{config.API_URL}/{target_table}/{val}"
```

That breaks already-location-carrying values such as:

```text
http://storage:7100/File/12
```

**Change**

Add small private helpers:

```python
def _is_ref_href(value) -> bool:
    return isinstance(value, str) and (
        value.startswith("http://")
        or value.startswith("https://")
        or value.startswith("/")
        or value.startswith("n3tx://")
    )


def _ref_response_value(target_cls, value):
    if value is None:
        return None
    if _is_ref_href(value):
        return value
    target_table = getattr(target_cls, "__tablename__", target_cls.__name__.lower())
    return f"{config.API_URL}/{target_table}/{value}"
```

Use this for `Ref[T]` hydration in `list()` and `get()`.

**Acceptance**

- Local integer `Ref[T]` still reads as local href.
- Remote href `Ref[T]` reads unchanged.
- Relative href `Ref[T]` reads unchanged.
- No remote request happens during normal read.

---

### Slice 2 — Store `list[Ref[T]]` as JSON membership lists

**Files**

- `packages/n3tx-core/src/n3tx_core/utils/introspection.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`

**Intent**

For:

```python
files: list[Ref[File]] = Field(default_factory=list)
```

store:

```json
["http://storage:7100/File/12"]
```

not local join rows.

**Likely current state**

This is already mostly aligned because bare `list[...]` fields are JSON unless
they are `ListRef[T]` or `list[BaseModel]`.

**Change**

Add tests that lock in behavior:

- migration creates `TEXT` column
- create stores JSON list
- read returns same href list
- no local `File` row required
- no join table generated

Only adjust introspection/migration if tests expose a gap.

**Acceptance**

- `list[Ref[T]]` behaves as relationship membership data.
- `ListRef[T]` behavior remains unchanged.

---

### Slice 3 — Make non-self `Ref[T]` TEXT storage explicit

**Files**

- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`

**Why**

Non-self `Ref[T]` currently falls through to `TEXT` in practice. Make this
intentional so href preservation is clearly supported.

**Change**

In create/migrate logic:

```python
if get_origin(field_type) is Ref:
    columns.append(f"{field_name} TEXT")
    continue
```

Self refs remain integer:

```python
parent_id: Ref["self"]
```

**Acceptance**

- `Ref['self']` still stores `INTEGER`.
- `Ref[User]` stores `TEXT`.
- Existing integer-like values still validate and roundtrip.

---

### Slice 4 — Add backend remote adapter mirroring frontend NetworkAdapter

**Files**

- `packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py`
- new optional file, likely `packages/n3tx-actors/src/n3tx_actors/api/remote_http.py`
- tests under `packages/n3tx-actors/src/n3tx_actors/tests/`

**Do not use**

- app-specific `SPLAT_*`
- direct Matrix private child mutation
- remote actor aliases replacing local children as the first design

**Use existing Matrix seam**

Backend Matrix already supports adapter fallback:

```python
elif self._adapters:
    for adapter in self._adapters:
        if adapter.can_handle(tx):
            await adapter.send(tx)
            return
```

**Remote adapter shape**

```python
class RemoteHTTPAdapter:
    def can_handle(self, tx: TX) -> bool:
        return _is_remote_target(tx.target)

    async def send(self, tx: TX) -> None:
        payload = await self._send_http(tx)
        await matrix.inbox(tx.reply(payload))
```

**Target handling**

Support first:

```text
http://host/Model/12
https://host/Model/12
```

Optional later:

```text
n3tx://storage/File/12
```

via a configured node map.

**Acceptance**

- Unknown absolute HTTP target is routed to adapter.
- Adapter maps READ/get-style TXs to HTTP route.
- Response re-enters Matrix as correlated reply.
- Errors become TX errors.
- Local children still win over remote fallback.

---

### Slice 5 — Add minimal ref resolution through Matrix

**Preferred home**

- `n3tx-actors`, because Matrix is actor-layer infrastructure.

Possible file:

```text
packages/n3tx-actors/src/n3tx_actors/ref.py
```

**Shape**

```python
async def resolve_ref(ref, *, user=None, timeout=30):
    target = str(ref)
    tx = TX(
        name="READ",
        source="ref",
        target=target,
        data=None,
        meta={"user": user} if user else {},
    )
    reply = await matrix.request(tx, timeout=timeout)
    if reply.is_error:
        raise RefResolutionError(reply.data)
    return reply.data
```

If backend actor conventions prefer `get` rather than `READ`, keep the resolver
thin and let the adapter translate as needed.

**Important boundary**

`Ref` itself should not contain direct HTTP logic.

```text
Ref points.
Matrix routes.
Adapter transports.
```

**Acceptance**

- Local href resolves locally.
- Remote href resolves via adapter.
- Ref resolution is explicit, not part of ordinary model reads.

---

### Slice 6 — Minimal schema hint for refs

**Files**

- `packages/n3tx-core/src/n3tx_core/models/proto_schema.py`

Current `Ref[T]` schema is `$ref`-oriented. That can remain if changing it would
disturb existing UI behavior.

Minimal additive option:

```json
{
  "$ref": "#/$defs/File",
  "format": "n3tx-ref",
  "x-n3tx-ref": {
    "model": "File",
    "resolve": "matrix"
  }
}
```

For `list[Ref[File]]`, add metadata on `items` if Pydantic does not already
carry enough information.

**Acceptance**

- Existing UI does not regress.
- Agents/tooling can distinguish model refs from arbitrary strings when needed.

---

### Slice 7 — File materialization in `n3tx-files`

**Files**

- `packages/n3tx-files/src/n3tx_files/materialize.py`
- `packages/n3tx-files/src/n3tx_files/file.py`
- possibly `packages/n3tx-files/src/n3tx_files/store.py`

**Keep core file-agnostic**

Core already owns the neutral materializer registry:

```python
n3tx_core.utils.materialize.register_materializer
```

`n3tx-files` already registers file materialization on import.

**Minimal first step**

Teach `n3tx_files.materialize` to recognize `Ref[File]` annotations in addition
to `File` annotations.

```python
if expected_type is File:
    ...

if get_origin(expected_type) is Ref and get_args(expected_type)[0] is File:
    ...
```

**Canonical materialization path**

```python
file = await File.resolve(address, user=user)
local = await file.ensure_local(user=user)
```

**Extend `File.ensure_local()` later**

Current local behavior is already present. Remote projection should be added as
a file capability/provider concern, with:

- streaming download
- temp file + atomic rename
- size verification
- sha256 verification when available
- safe filename/cache policy
- no arbitrary overwrite

**Acceptance**

- `File` annotation still resolves authorized file metadata.
- `Ref[File]` annotation can be accepted by file-aware method materialization.
- Core does not import `n3tx_files`.

---

## 🔐 Compatibility Rules

Must preserve:

- `Ref[T]` with integer IDs.
- Numeric string refs where currently accepted.
- Relative href refs such as `/File/12`.
- Same-origin absolute hrefs as normal local references.
- Existing `ListRef[T]` parent-child behavior.
- Existing generated route and schema-driven UI behavior.

Must avoid:

- public `RefIdentity`
- wholesale `n3tx_ext` adoption
- app-specific `SPLAT_*` config
- direct `matrix._children` mutation
- core dependency on actors/files at import time
- remote availability during basic reads

---

## 🧪 Test Plan

### Core storage tests

Cases:

```python
owner: Ref[User]
files: list[Ref[File]]
```

Assert:

- integer ref hydrates to local href
- remote href remains unchanged
- relative href remains unchanged
- `list[Ref[T]]` JSON roundtrips
- no join table for `list[Ref[T]]`
- `ListRef[T]` tests still pass

### Migration tests

Assert:

- `Ref['self']` creates `INTEGER`
- `Ref[User]` creates `TEXT`
- `list[Ref[File]]` creates `TEXT`

### Matrix/adapter tests

Assert:

- local children are routed before adapter fallback
- absolute remote target is accepted by remote adapter
- remote reply resolves `Matrix.request()` correlation
- remote HTTP error maps to TX error

### File tests

Assert:

- `materialize_arg(value, File)` existing behavior remains
- `materialize_arg(value, Ref[File])` handles file refs through optional package
- `ensure_local()` still works for `LocalFileStore`
- remote projection behavior is tested once implemented

---

## 📊 Risk Table

| Risk | Mitigation |
| --- | --- |
| Remote hrefs accidentally treated as local DB IDs | `_ref_response_value()` and populate helpers skip remote hrefs |
| Existing UI expects `$ref` schema | Add metadata additively; avoid replacing schema shape initially |
| Core/actors/files cyclic dependency | Keep ref storage in core, resolving in actors, materialization in files |
| Remote transport duplicates route grammar | Mirror frontend target-driven adapter; use href target directly where possible |
| Remote unavailable breaks reads | Only resolve/materialize explicitly |
| App-specific concepts leak into framework | Do not adopt `SPLAT_*`; use generic adapter config only |

---

## ✅ Delivery Order

1. Preserve href strings for `Ref[T]` in storage responses.
2. Lock in `list[Ref[T]]` JSON storage with tests.
3. Make non-self `Ref[T]` TEXT migration explicit.
4. Add backend remote HTTP adapter using Matrix adapter fallback.
5. Add `resolve_ref()` helper through Matrix.
6. Extend `n3tx-files` materializer for `Ref[File]`.
7. Add optional schema metadata for `n3tx-ref` if needed by UI/agents.

This order keeps the framework usable after each slice and avoids premature
generalization.

---

## 📍 Critical Files

```text
packages/n3tx-core/src/n3tx_core/utils/typer.py
packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py
packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py
packages/n3tx-core/src/n3tx_core/models/proto_schema.py
packages/n3tx-actors/src/n3tx_actors/matrix.py
packages/n3tx-actors/src/n3tx_actors/api/network_adapter.py
packages/n3tx-files/src/n3tx_files/materialize.py
packages/n3tx-files/src/n3tx_files/file.py
```

---

## ✨ Final Position

The framework does not need a new distributed reference abstraction.

It needs the existing architecture to be made consistent end-to-end:

```text
$id / href is the location-carrying identity
Ref stores/preserves that identity
Matrix routes it
Network adapters cross process boundaries
File capability materializes bytes
```

That is the minimal, N3TX-native path to location-transparent refs and remote
file materialization.
