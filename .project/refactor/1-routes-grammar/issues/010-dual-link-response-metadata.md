# 010 — Flip response `$id` to class-name identity

## ✅ Recommendation

Use the route grammar migration to make `$id` the class-name identity directly.
Do **not** add `$href`, `links.canonical`, or `links.legacy` as intermediate
response complexity.

```json
{
  "$schema": "/Product",
  "$id": "/Product/1"
}
```

Nested/join responses should mirror the current parent-scoped shape while
replacing table/tag segments with class-name segments:

```json
{
  "$schema": "/Comment",
  "$id": "/Product/1/Comment/2"
}
```

Legacy table-name routes remain available for compatibility, but response
identity becomes model-centric now.

```text
model_response()
  -> base
  -> schema_url     ($schema = /ClassName)
  -> instance_url   ($id = /ClassName/id or /Parent/id/Child/id)
  -> populate       (overlays populated relation payloads)
```

---

## 📍 Current State

| Area | Current behavior | Required change |
|---|---|---|
| Regular response | `$schema=/Product`, `$id=/products/1` | `$id=/Product/1` |
| Class-name read mirror | Reuses table read serializer; `$id=/products/1` | Same payload as table route, but `$id=/Product/1` |
| Join model response | `instance_url()` can emit `$id=/products/1/comments/2` | `$id=/Product/1/Comment/2` |
| Populated `ListRef` children | Storage manually rewrites child `$id` to parent-scoped table route | Rewrite to parent-scoped class-name route |
| Existing clients | May store table-name `$id` values | Legacy table-name routes remain supported; tests/docs must call out public identity change |

---

## 🧭 Design Constraints

1. **No `$href` field.** `$id` is the only response identity URL.
2. **No `links` object.** Avoid parallel identity concepts unless a future need
   proves they are necessary.
3. **Class-name routes must be operational before frontend writes rely on `$id`.**
   This issue changes response identity; issues 012–014 ensure writes/methods
   exist everywhere the frontend may target them.
4. **Nested `$id` is parent-scoped and class-name based.** Use
   `/{ParentClass}/{parent_id}/{ChildClass}/{child_id}`.
5. **Keep table-name API compatibility.** Existing `/products/...` routes remain
   available even though responses now advertise `/Product/...` identities.

---

## 🔧 Implementation Plan

### Step 1 — Change regular `instance_url()` output

Primary file:

```text
packages/n3tx-core/src/n3tx_core/models/proto_dump.py
```

Update the regular model branch from table-name base URLs to class-name base
URLs:

```python
_instance_url_cache[cls] = {
    'base_url': f"{config.API_URL}/{cls.__name__}",
}
```

Expected regular output:

```text
$schema -> {API_URL}/Product
$id     -> {API_URL}/Product/1
```

### Step 2 — Change join/nested `instance_url()` output

For generated join models, use existing metadata:

- `__owner__` for the parent class, e.g. `Product`
- `__parent__` for the child/reference class, e.g. `Comment`
- generated parent FK field, e.g. `product_id`
- instance `id` for child id

Code shape:

```python
owner_cls = getattr(cls, '__owner__', None)
child_cls = getattr(cls, '__parent__', None) or cls

_instance_url_cache[cls] = {
    'owner_base': f"{config.API_URL}/{owner_cls.__name__}",
    'child_name': child_cls.__name__,
    'fk_field': f"{owner_cls.__name__.lower()}_id",
}

url = f"{owner_base}/{parent_id}/{child_name}/{instance_id}"
```

Expected nested output:

```text
$schema -> {API_URL}/ProductComment or {API_URL}/Comment, depending on effective serialized class
$id     -> {API_URL}/Product/1/Comment/2
```

Do not use `__tagname__` for the class-name `$id` in this plan. The chosen
grammar intentionally drops the relation segment for now.

### Step 3 — Update populated child overrides in SQLite storage

Primary file:

```text
packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py
```

Current populated `ListRef` children are serialized and then patched:

```python
dumped = child_inst.model_response()
dumped['$id'] = f"{config.API_URL}/{model_class.__tablename__}/{pid}/{field_name}/{rec.get('id')}"
```

Change that manual override to the class-name nested shape:

```python
child_cls = getattr(effective_cls, '__parent__', effective_cls)
dumped['$id'] = f"{config.API_URL}/{model_class.__name__}/{pid}/{child_cls.__name__}/{rec.get('id')}"
```

This preserves the parent-scoped relationship shape while making it class-name
based.

### Step 4 — Update dump-pipeline tests

Primary file:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_dump_stages.py
```

Update expectations:

1. Regular model response:
   - `$schema == {API_URL}/_DumpSimple`
   - `$id == {API_URL}/_DumpSimple/10`
   - no `$href`
   - no `links`
2. Join model response:
   - `$id == {API_URL}/DumpOwner/2/DumpChild/3`
   - no table-name `/pd_owners/2/children/3` identity remains in response
3. Pipeline order remains simple:
   - `base -> schema_url -> instance_url -> populate`

### Step 5 — Update route mirror identity tests

Primary file:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
```

Extend class-name read mirror tests so table-name and class-name routes return
the same response body and both advertise class-name `$id`:

```python
table_payload = table_response.json()
class_payload = class_response.json()

assert class_payload == table_payload
assert class_payload['$schema'].endswith('/MirrorProduct')
assert class_payload['$id'].endswith(f'/MirrorProduct/{created.id}')
assert '$href' not in class_payload
assert 'links' not in class_payload
```

### Step 6 — Add populated nested response regression coverage

Use a small parent/child relationship and fetch with `populate=children`. Assert
the populated child response advertises:

```text
$id -> /LinkParent/{parent_id}/LinkChild/{child_id}
```

If the runtime serializes the generated join class rather than the base child
class, assert the class-name segment that the implementation deliberately emits.
The important contract is: class-name parent, class-name child, no table names,
and no `$href`/`links`.

---

## 🧪 Verification

Run narrow backend checks first:

```bash
cd /workspace && python3 -m pytest \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_dump_stages.py \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
```

Then run the short backend suite:

```bash
cd /workspace && python3 scripts/test-backend.py --short
```

Frontend follow-up verification belongs with issue 011 and the write/method
mirror issues, because changing `$id` affects client transport behavior.

---

## 📊 Acceptance Checklist

| Contract | Proof |
|---|---|
| Regular responses use `$id=/{ClassName}/{id}` | dump-stage unit test |
| Table-name and class-name reads return identical class-name `$id` payloads | route mirror test |
| Join responses use `$id=/{ParentClass}/{parent_id}/{ChildClass}/{child_id}` | join dump test |
| Populated children use class-name nested `$id` | populated relation regression test |
| No `$href` is emitted | unit/route assertions |
| No `links` object is emitted | unit/route assertions |
| Legacy table-name routes still work | existing route/example tests |

---

## ⚠️ Risks and Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Frontend writes target missing class-name routes | Frontend uses `$id` as `href` today | Land direct/actor write and method mirrors immediately after this slice |
| External clients store old table-name `$id` | Public identity semantics change | Keep table-name routes working and document the migration clearly |
| Nested grammar loses relation segment | Multiple relations to same child class become ambiguous | Accept simpler grammar now; revisit aliases/relation-aware grammar if needed |
| Storage override drifts from dump stage | Populated children manually patch `$id` | Update storage override and cover it with tests |

---

## 🚫 Out of Scope

- Adding `$href`.
- Adding `links` metadata.
- Removing legacy table-name routes.
- Adding friendly route aliases.
- Supporting duplicate same-child relationships in nested class-name identity.

---

## Suggested Commit

```text
feat(core): Flip responses to class-name identity [routes-grammar]
```

Expected files touched:

- `packages/n3tx-core/src/n3tx_core/models/proto_dump.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_dump_stages.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`
