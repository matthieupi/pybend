# N3TX Ref System Map and Cleanup Direction

✅ **Recommendation:** treat this as the current-state map for a larger reference-system overhaul. The clearest cleanup path is to make **one canonical identity grammar** authoritative across models, storage, actors, remote transport, methods, and frontend:

```text
Local entity identity:      /ClassName/id             and response $id = {API_URL}/ClassName/id
Distributed entity identity: n3tx://service/ClassName/id
Actor execution address:    tablename[/id]            internal dispatch only
Transport route path:       schema-declared route     from @expose_route metadata
```

The biggest architectural issue is not a missing abstraction; it is that the same concept appears under too many names and paths: `id`, `$id`, href strings, `Ref` objects, local table URLs, class-name URLs, `n3tx://...`, nested remote targets, raw TX targets, and method payload `id` fields.

---

## 📍 Scope

This map covers the current reference/address system across:

- `n3tx-core`: `Ref`, `ListRef`, schema, dump, storage, route generation, materialization
- `n3tx-actors`: `Actor`, `TX`, `Matrix`, `ActorModel`, `NetworkAPI`, `RemoteMatrix`, `RemoteRef`
- `n3tx-ui`: dynamic entity runtime, href/$id consumption, ref/list widgets
- `n3tx-files`: file-specific address parsing and method materialization
- `n3tx-agents`: tool invocation paths where methods and refs are exposed to LLM tools

This is **read-only architecture mapping**. No product code was changed.

---

## 🗺️ Current Mental Model

```text
Python model field
  |  Ref[T] / list[Ref[T]] / ListRef[T]
  v
Pydantic + ProtoModel schema/dump
  |  schema $id, response $id, method schema, $defs
  v
Storage boundary
  |  SQLite canonicalizes Ref writes; hydrates refs/list refs as href strings or populated wrappers
  v
API boundary
  |  Direct routes OR NetworkAPI -> TX -> Matrix -> ActorModel
  v
Distributed boundary
  |  RemoteMatrix maps n3tx://service/Class/id to remote class-name REST
  v
Frontend runtime
  |  NTT uses $schema/$id/href to cache entities, render refs, and invoke methods
```

The architecture is trying to converge on **class-name public identity** (`/Product/1`, `$id`, `n3tx://svc/Product/1`) while keeping **table-name actor/storage compatibility** (`products`, `/products/1`) alive. That migration is incomplete and creates most of the confusion.

---

## 📊 Vocabulary and Current Owners

| Concept | Current shape | Primary owner today | Drift |
|---|---|---|---|
| Local DB id | `id: int` | `ProtoModel`, SQLite | Stable |
| Public entity id | `$id = {API_URL}/ClassName/id` | `proto_dump.instance_url()` | Mostly canonical |
| Local reference input | `int`, numeric string, `/Class/id`, HTTP `$id`, dict with `id`/`$id`, `Ref` | `models/ref.py` + storage | Too permissive but useful |
| Distributed ref | `n3tx://service/Class/id` | `models/ref.py`, `RemoteMatrix` | Identity grammar and transport grammar diverge |
| Actor address | `tablename`, `tablename/id` | `Actor`, `Matrix`, `ActorModel` | Internal but leaks into tools/frontend paths |
| Relationship collection | `ListRef[T]` | storage + routes | Emits href arrays, not canonical `$id` consistently |
| Pointer array | `list[Ref[T]]` | storage JSON field | Distinct from `ListRef`, but easy to confuse |
| Method target id | `data['id']` or URL path `id` | direct routes, NetworkAPI, ActorModel, tools | Multiple invocation paths parse differently |
| File address | `n3tx://files/id`, `/files/id`, `/File/id` | `n3tx-files/address.py` | Parallel parser, narrower than `Ref` |

---

## 🔄 Data Flows

### 1. `Ref[T]` write path

```text
request/model input
  -> StorableMixin.create/update()
  -> SQLiteStorage._normalize_ref_storage_values()
  -> canonicalize_ref()
       local refs -> int
       current-service HTTP refs -> int
       configured remote HTTP refs -> n3tx://service/Class/id
       canonical n3tx:// refs -> preserved
       external HTTP refs -> rejected by storage for Ref fields
  -> SQLite column, usually TEXT for Ref fields
```

Evidence:

- `packages/n3tx-core/src/n3tx_core/models/ref.py`
  - `canonicalize_ref()`
  - `local_ref_id()`
  - `public_ref()`
  - `parse_ref_string()`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
  - `_normalize_ref_storage_values()`
  - `_public_storage_ref()`
  - `_public_ref_list()`

### 2. `Ref[T]` read path

```text
SQLite row
  -> _deserialize_json_fields()
  -> _public_storage_ref()
       distributed n3tx:// ref -> preserved
       local id -> table-name href: {API_URL}/{target_tablename}/{id}
  -> model instance
  -> model_response()
  -> $schema and $id added by proto_dump
```

⚠️ Drift: `public_ref()` emits class-name URLs (`/File/12`), while SQLite `_local_ref_href()` emits table-name URLs (`/files/12`). This is one of the most important cleanup targets.

### 3. `list[Ref[T]]` pointer-array path

```text
list[Ref[T]] field
  -> detected by get_ref_list_fields()
  -> stored as JSON TEXT
  -> each item canonicalized through canonicalize_ref()
  -> read as local table hrefs or n3tx:// refs
  -> populate optionally resolves local and remote refs into {data, refs, errors}
```

This is the distributed-friendly pointer collection. It is intentionally not the same as `ListRef[T]`.

### 4. `ListRef[T]` relationship path

```text
ListRef[T]
  -> Annotated[List[Union[T, str]], _ListRefMarker(T)]
  -> no parent SQLite column
  -> child or generated join model owns FK
  -> default response emits href array
  -> populate emits {data, meta}
```

This is the local owned relationship primitive. It still depends heavily on href arrays, and those hrefs are usually table-name or relation/tag routes rather than canonical class-name `$id` values.

### 5. Response identity path

```text
model_response()
  -> proto_dump.base()
  -> proto_dump.schema_url(): $schema = {API_URL}/{ClassName}
  -> proto_dump.instance_url():
       normal model -> {API_URL}/{ClassName}/{id}
       join/nested  -> {API_URL}/{OwnerClass}/{parent_id}/{ChildClass}/{id}
  -> proto_dump.populate(): overlays storage-populated fields
```

This is the strongest existing source of truth and should become the public identity authority.

### 6. Level 3 actor route path

```text
HTTP /Product/42
  -> NetworkAPI route handler
  -> TX(name='get', target='products', data={'id': 42}, meta={user, model_cls})
  -> Matrix routes by first target segment
  -> ActorModel.handler_crud()
  -> Product.get(42)
  -> model_response()
  -> TX reply
```

Actor execution is table-name addressed even when HTTP identity is class-name based. That can remain true if it is clearly internal and consistently hidden behind a translation boundary.

### 7. Remote distributed path

```text
n3tx://storage/File/12
  -> RemoteMatrix._parse_target()
  -> GET http://storage/File/12
  -> response $id canonicalized back to n3tx://storage/File/12
```

Remote methods:

```text
TX(name='generate', target='n3tx://compute/Scene/4/Task/9')
  -> RemoteMatrix fetches GET http://compute/Task
  -> reads schema.methods.generate.route
  -> POST http://compute/Scene/4/Task/9/{schema-route}
```

⚠️ Drift: `models/ref.parse_ref_string()` accepts identity refs only (`n3tx://service/Class/id`), while `RemoteMatrix._parse_target()` accepts class-only and nested transport targets (`n3tx://service/Scene/4/Task/9`). That distinction is valid, but the names and boundaries need to be explicit.

### 8. Method invocation path

There are currently several invocation pipelines:

| Path | Input shape | Parser/materializer | Notable drift |
|---|---|---|---|
| Direct FastAPI | URL id + JSON object | `routes_fastapi.make_custom_post()` | Missing optional params are rejected |
| Actor HTTP | URL id + JSON/query object | `NetworkAPI._parse_method_args()` then `ActorModel.handler()` | Defaults can apply; materialization can happen twice |
| Raw TX | `TX.data` dict, instance id in data | `ActorModel.handler()` | BaseModel construction is weaker than HTTP path |
| Agent tool | generated function args | `n3tx_agents.tools` -> TX | `$ref` tool params likely degrade to strings |
| Frontend | Formidable object -> `call()` | JS `NTT.call()`/transport | Method URL/target can be synthesized instead of schema-route driven |

The single best cleanup seam is to make **one method invocation normalizer** the boundary for all of these paths.

### 9. Frontend consumption path

```text
GET /Product schema
  -> NTT.SCHEMA()
  -> prototype() creates DynamicClass
  -> DynamicClass.href = schema model base (/Product)
  -> entity instance href = response $id when present
  -> normalizePopulated() converts populated objects back to href strings and registers instances
```

Frontend currently depends on:

- `$schema` for type/schema matching
- `$id` for instance href and cache identity
- href arrays for `ListRef` rendering
- `$defs`/`$ref` for form rendering and ref-picker model inference

This means a ref cleanup must be a migration, not a single backend switch.

### 10. File-specific address path

`n3tx-files` has its own address parser:

```text
parse_file_address()
  accepts n3tx://files/{id}, /files/{id}, /File/{id}
  rejects HTTP URLs
```

File method args use the generic materializer extension seam, but only for `expected_type is File`.

This is a good optional-package pattern, but file addresses should eventually delegate to the canonical reference parser for entity identity instead of maintaining a parallel mini grammar.

---

## ⚠️ Drift Inventory

### A. Ref hydration has no single public protocol

Facts:

- `Ref[T]` fields can surface as `int`, `str`, `Ref`, dict with `$id`, table href, class-name `$id`, `n3tx://...`, or populated object.
- Storage read hydration emits table-name hrefs for local refs.
- `proto_dump` emits class-name `$id` for entity identity.
- Frontend normalizes populated objects back into href strings.

Impact:

- Callers need to defensively handle too many shapes.
- Python methods and JS components cannot rely on one reference protocol.
- Remote/distributed logic is harder to reason about than it should be.

### B. Remote Matrix, URLs, Matrix, WS, `@expose_route`, ActorModel, and storage each parse related address grammar

Facts:

- `ref.py` parses identity refs.
- `RemoteMatrix` parses broader transport targets.
- `NetworkAPI` converts URLs to table-name TX targets.
- `Actor.send()` routes by slash segments.
- Frontend `NTT` stores `href` and sends TX targets to HTTP URLs.
- `n3tx-files` parses file addresses separately.

Impact:

- The same address shape is reinterpreted by multiple modules.
- Public identity and internal dispatch are coupled by convention rather than one clear boundary.
- Tests can pass locally while distributed or frontend paths drift.

### C. Method invocation has parallel argument mental models

Facts:

- Direct routes, actor routes, raw TX, frontend calls, and agent tools each shape method input slightly differently.
- `routes_fastapi.make_custom_post()` rejects missing params even if Python defaults exist.
- `NetworkAPI._parse_method_args()` skips missing params.
- `ActorModel.handler()` relies on `TX.data['id']` for instance methods and does only materializer-based coercion.

Impact:

- The same `@expose_route` method can behave differently depending on invocation path.
- Ref/file/model typed args are not uniformly materialized.
- Tool discovery and remote method invocation have to duplicate route/method knowledge.

---

## 🧭 N3TX Alignment Candidates

### Candidate 1 — Canonical Reference Codec Boundary ✅ Recommended first

**Current shape**
- Identity normalization lives partly in `models/ref.py`, storage helpers, `proto_dump`, `RemoteMatrix`, frontend `NTT`, and file address parsing.

**N3TX misalignment**
- The model/schema should be the source of truth, but reference identity is currently a distributed convention across modules.

**Recommended direction**
- Deepen the existing `models/ref.py` primitive into the single reference codec boundary.
- Keep it simple: no public address object required initially; expose parse/normalize/format functions with explicit domains:
  - entity identity refs
  - actor execution addresses
  - transport route targets
  - public response refs

**Expected outcome**
- Storage, RemoteMatrix, files, and frontend docs stop inventing their own reference grammars.
- Table-name hrefs can be treated as compatibility inputs, not preferred outputs.

### Candidate 2 — Unified Method Invocation Normalizer

**Current shape**
- Direct routes, actor routes, raw TXs, agents, and frontend calls each parse method args.

**N3TX misalignment**
- `@expose_route` schema should define the operation contract once.

**Recommended direction**
- Create one backend method invocation normalizer used by `routes_fastapi`, `NetworkAPI`, and `ActorModel`.
- It should handle defaults, user injection, BaseModel construction, File materialization, future Ref materialization, and instance-id extraction.

**Expected outcome**
- Same method behavior regardless of direct HTTP, actor HTTP, raw TX, remote, frontend, or agent tool path.

### Candidate 3 — Public Identity Migration: `$id` First, href Compatibility

**Current shape**
- `$id` is class-name based, but local refs/ListRefs often emit table-name hrefs.

**N3TX misalignment**
- There should be one public entity identity story.

**Recommended direction**
- Make `$id`/class-name URL the canonical public identity for entity refs.
- Keep table-name routes as transport compatibility, but stop producing table-name hrefs from new response paths.

**Expected outcome**
- Frontend, remote refs, and storage populate converge on the same public entity strings.

### Candidate 4 — Remote Target vs Ref Naming Cleanup

**Current shape**
- `RemoteMatrix` intentionally accepts transport targets broader than identity refs.

**N3TX misalignment**
- “Ref” and “remote target” are related but not the same; current naming blurs them.

**Recommended direction**
- Keep core `Ref` strict.
- Rename/document `RemoteTarget` as transport-only and ensure it never leaks into model fields.

**Expected outcome**
- Distributed actor calls can support nested/class targets without weakening the model identity primitive.

### Candidate 5 — File Address Delegation

**Current shape**
- `n3tx-files` has a separate parser for file identity.

**N3TX misalignment**
- File is an `ActorModel`, so its identity should be a normal entity ref where possible.

**Recommended direction**
- Make `File.resolve()` accept canonical entity refs via core ref parsing, while keeping current `/files/{id}` and `n3tx://files/{id}` compatibility forms.

**Expected outcome**
- File method args behave like normal model refs, reducing special cases.

---

## 💻 Method Signature Surface

No callable/interface signatures changed in this mapping pass.

Likely future refactor surfaces to design in the next step:

```text
n3tx_core.models.ref
  / def parse_ref_string(value: str) -> tuple[str | None, str | None, str | None]
  / def canonicalize_ref(value, *, target_cls=None, api_url=None, remotes=None) -> str | int | None
  / def public_ref(value, *, target_cls=None, api_url=None, remotes=None) -> str | None
  + def parse_entity_ref(value: object, *, target_cls=None, api_url=None, remotes=None) -> ...
  + def public_entity_ref(value: object, *, target_cls=None, api_url=None, remotes=None) -> str | None

n3tx_core.utils.materialize or new method invocation module
  + async def normalize_method_args(...)
  + async def materialize_ref(...)

n3tx_actors.api.remote_matrix
  / def _parse_target(self, target: str) -> RemoteTarget
```

These future signatures are illustrative only; they should be finalized after the next design pass.

---

## 🧪 Verification Map for the Future Refactor

| Area | Existing tests to extend | Behavior to lock |
|---|---|---|
| Ref parser/codec | `packages/n3tx-core/src/n3tx_core/tests/unit/test_ref.py` | accepted inputs, rejected external links, canonical public format |
| Storage refs | `test_sqlite_storage.py` | write canonicalization, read public refs, populate remote/local refs |
| Route identity | `test_routes.py` | `$id` class-name identity, nested identity, no `$href` regression |
| Remote matrix | `packages/n3tx-actors/src/n3tx_actors/tests/test_remote_matrix.py` | remote `$id` canonicalization, schema route method lookup, nested transport targets |
| Method invocation | core/actor route tests + agent tool tests | same args/defaults/user/materialization across paths |
| Frontend refs | `tests/frontend` Vitest + E2E | `$id`/href compatibility, ref-picker/list-field rendering |
| Files | `packages/n3tx-files/src/n3tx_files/tests/test_address.py`, `test_resolve.py` | canonical entity refs resolve to File |

---

## ⚠️ Risks and Open Questions

1. **Public ref output choice:** should local `Ref[T]` response fields immediately switch from table-name hrefs to class-name `$id` URLs, or should this be staged behind compatibility tests?
2. **ListRef relation identity:** if multiple relationships point to the same child class, class-name nested identity is ambiguous today. Docs already acknowledge this; cleanup should avoid pretending relation aliases are solved.
3. **Frontend migration:** components expect href arrays. Switching outputs requires either compatibility in `NTT`/widgets or a staged backend output mode.
4. **Remote target grammar:** nested remote targets should stay transport-level, not become valid model `Ref[T]` values.
5. **Missing/stale adapter:** tests/docs reference `n3tx_actors.api.adapter_n3tx.NetworkN3TX`, but no implementation file exists. That may be stale feature drift and should be explicitly triaged.

---

## ✨ Suggested Next Step

Proceed with a focused design pass for **Candidate 1: Canonical Reference Codec Boundary**, then use it to drive Candidates 2 and 3.

Thin-slice order:

1. Add characterization tests for current accepted ref inputs and current public outputs.
2. Design the canonical reference vocabulary and compatibility matrix.
3. Introduce the codec boundary in `models/ref.py` without changing outputs.
4. Move storage public ref formatting to the codec.
5. Move file address parsing and remote response canonicalization onto the codec where safe.
6. Switch local public ref outputs to class-name identity behind tests.
7. Unify method argument normalization and generic `Ref[T]` materialization.
8. Update frontend compatibility once backend response shapes are stable.

---

## Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/models/ref.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`
- `packages/n3tx-actors/src/n3tx_actors/api/remote_matrix.py`

## Saved Plan

- `.project/reports/research/n3tx-ref-system-map.md`
