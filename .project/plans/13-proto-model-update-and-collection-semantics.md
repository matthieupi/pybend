# ProtoModel Update and Collection Semantics Plan

## ✅ Recommendation

Make **partial update** the single N3TX contract across Python, direct HTTP, actor HTTP/TX, agent tools, OpenAPI, frontend documentation, and tests:

```text
update(id, patch) -> validate patch against current entity -> persist only supplied fields -> return full entity
```

Keep `PUT` as the compatibility verb in this pass rather than introducing a competing `PATCH` route. Full frontend payloads remain valid patches, while omitted fields remain unchanged. Treat `list[T]` as ordered local-owned relationship IDs and `list[Ref[T]]` as ordered local/distributed pointer arrays; both use explicit replacement only when the field is present.

The implementation should centralize request-model creation and patch extraction in `n3tx-core`, then reuse that contract from both direct and actor route generation. Collection normalization should reject malformed members rather than silently dropping them or coercing a malformed collection to `[]`.

## 📍 Current State

| Surface | Current behavior | Problem |
|---|---|---|
| `Model.update(id, patch)` | Partial storage update | Correct baseline contract |
| `instance.update(patch)` | Partial storage update | Correct baseline contract |
| SQLite/JSON storage | Replaces only supplied columns/keys | Correct if field presence survives validation |
| Direct FastAPI `PUT` | Parses full `model_class`, then `model_dump()` | Requires required fields and injects omitted defaults |
| Actor FastAPI `PUT` | Parses full `param_class`, then `model_dump()` | Same expansion before TX dispatch |
| Actor TX update | Partial dictionary excluding `id` | Correct, but HTTP callers reach it through full-model validation |
| Agent update tools | Only `id` is required | Already advertises partial update |
| Frontend save | Sends full current entity | Works, but masks partial-route defects and risks stale full-object writes |
| Docs/tests | Mix partial-update and full-resource semantics | No authoritative public contract |

### Root cause flow

```text
partial JSON body
      |
      v
full ProtoModel validation
      |
      v
flatten_refs(model) -> model_dump() -> omitted defaults materialized
      |
      v
Model.update(id, expanded_dict)
      |
      v
SQLite correctly replaces every supplied field, including accidental [] / {}
```

For relationship collections this means an omitted defaulted field can become an explicit clear:

```text
comments: list[Comment] = []       omitted -> [] -> stored relationship cleared
files: list[Ref[File]] = []        omitted -> [] -> stored pointer array cleared
```

## 🎯 Target State and Invariants

### Universal update invariants

1. Omitted fields remain unchanged.
2. Explicit values replace the field value.
3. Explicit `[]` clears a collection; omission does not.
4. Explicit `None` is accepted only when the original field type is nullable.
5. `id` and `__protected_fields__` are not writable through generated update routes.
6. Unknown fields follow the model's configured Pydantic extra-field policy.
7. The patch is validated in the context of the current complete entity so model-level validators still run.
8. The response is the complete updated entity with `$schema` and `$id`.
9. Direct and actor routes publish the same OpenAPI request contract and produce equivalent status/error behavior.

### Collection invariants

| Field kind | Stored meaning | Accepted update members | Rejected members |
|---|---|---|---|
| `list[T]` | Ordered local child IDs owned/referenced by the parent | Target instances, local IDs, valid local target refs | Remote refs, external links, malformed/unresolvable values |
| `list[Ref[T]]` | Ordered local/distributed pointers | Local IDs/refs and canonicalizable configured N3TX refs | Arbitrary external links and malformed refs |

For both kinds:

- preserve order;
- preserve duplicates in this pass (existing ordered-list behavior; document explicitly);
- reject a malformed collection atomically rather than partially accepting members;
- never coerce a non-list input to an empty list;
- normalize a copy of caller data rather than mutating the caller's patch dictionary.

## 🗺️ Target Architecture

```text
                          +-----------------------------+
HTTP PUT (direct) ------> | core update contract       |
                          | - generated patch model     |
HTTP PUT (actor) -------> | - supplied-field extraction|
                          | - merge/full validation     |
                          | - protected-field filtering|
                          +--------------+--------------+
                                         |
                    +--------------------+--------------------+
                    |                                         |
                    v                                         v
          Model.update(id, patch)                    TX(name='update', patch)
                    |                                         |
                    +--------------------+--------------------+
                                         v
                            collection normalization
                            - list[T] -> local IDs
                            - list[Ref[T]] -> canonical refs
                                         |
                                         v
                              storage partial update
                                         |
                                         v
                              complete model response
```

The core update helper is the deep module: route layers should not independently decide what “partial,” “writable,” or “provided” means.

## 💻 Method Signature Surface

```text
n3tx_core.api.update_contract
  + def make_update_model(model_class: type[BaseModel]) -> type[BaseModel]
  + def prepare_update_patch(
        model_class: type[BaseModel],
        current: BaseModel,
        payload: BaseModel | Mapping[str, Any],
    ) -> dict[str, Any]
  + def writable_update_fields(model_class: type[BaseModel]) -> set[str]

n3tx_core.models.ref
  / def flatten_refs(obj: BaseModel, *, exclude_unset: bool = False) -> dict[str, Any]

n3tx_core.models.StorableMixin
  / def update(
        target,
        id_or_data: int | BaseModel | dict,
        data: BaseModel | dict | None = None,
    ) -> Any
  / def delete(cls, id: int) -> None

n3tx_core.storage.SQLiteStorage
  / def update(self, model_class: type[Any], id: int, data: dict[str, Any]) -> None

n3tx_core.storage.JSONStorage
  / def update(self, model_class: type[Any], id: int, data: dict[str, Any]) -> None

n3tx_core.api.routes_fastapi
  / def make_update_instance(model_class: type[BaseModel]) -> Callable

n3tx_actors.api.network_api
  / async def update_instance(request: Request, id: int, data: UpdateModel, ...) -> Any

Relationship cleanup helper (module location selected during implementation)
  + def collect_local_relationship_cleanup(
        deleted_model_class: type[BaseModel],
        deleted_id: int,
    ) -> list[tuple[type[BaseModel], int, str, list[int]]]
  + def apply_local_relationship_cleanup(
        patches: Iterable[tuple[type[BaseModel], int, str, list[int]]],
    ) -> None
```

`UpdateModel` above is generated per model by `make_update_model()` and cached; it is not a new handwritten model per resource.

## 📋 Implementation Slices

### Slice 1 — Lock the canonical contract with failing tests

Add regression tests before production changes.

#### Direct route tests

In `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`, define a focused model containing:

```python
name: str
count: int
comments: list[Comment] = Field(default=[])
files: list[Ref[File]] = Field(default=[])
metadata: dict = Field(default={})
optional_note: str | None = None
protected_owner: int | None = None
```

Prove:

- a payload containing only `name` succeeds despite other required fields;
- omitted scalar, dict, `list[T]`, and `list[Ref[T]]` fields remain unchanged;
- explicit `[]` clears each collection;
- explicit `None` works only for nullable fields;
- protected fields are ignored/removed as they are today;
- malformed fields return validation errors without changing storage;
- class-name and table-name route mirrors behave identically;
- generated OpenAPI marks update properties optional rather than requiring create-time fields.

#### Actor route tests

In `packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py`, assert the captured update TX contains only:

```python
{'id': entity_id, **explicitly_supplied_fields}
```

Add parity cases for omitted defaults, explicit clears, protected fields, validation failure, and both route grammars.

#### Existing example contract tests

Change the core and actor product CRUD tests that currently expect `422` for an omitted required field. Their replacement assertion should prove a one-field update succeeds and preserves `price` and relationship collections.

### Slice 2 — Introduce one core update-contract helper

Add `packages/n3tx-core/src/n3tx_core/api/update_contract.py`.

#### Generated request model

`make_update_model(model_class)` should:

- clone each model field's annotation and relevant metadata;
- make every writable field optional-by-presence without making a non-nullable type accept `null`;
- exclude `id` and `__protected_fields__`;
- preserve aliases and the model's extra-field configuration;
- cache generated classes by source model;
- produce a stable name such as `ProductUpdate` for OpenAPI.

Representative shape:

```python
ProductUpdate = create_model(
    'ProductUpdate',
    name=(str, None),
    price=(float, None),
    comments=(list[Comment], None),
    files=(list[Ref[File]], None),
    __config__=patch_config,
)
```

Here a default of `None` means “not required”; the original non-nullable annotation still rejects an explicitly supplied `null`.

#### Patch preparation

`prepare_update_patch()` should:

1. extract only `payload.model_fields_set` / mapping keys;
2. filter to writable fields;
3. merge those fields over `current._storage_dict(exclude_unset=False)`;
4. validate the merged complete object with `model_class.model_validate()` so cross-field validators see complete state;
5. flatten refs from the validated model;
6. return only the top-level fields originally supplied.

Representative control flow:

```python
provided = payload.model_dump(exclude_unset=True)
merged = current._storage_dict(exclude_unset=False) | provided
validated = model_class.model_validate(merged)
flat = flatten_refs(validated)
return {name: flat[name] for name in provided if name in writable}
```

Do not use raw request JSON as the long-term source of truth when Pydantic already tracks supplied fields.

### Slice 3 — Align direct and actor HTTP routes

#### Direct FastAPI

Update `make_update_instance()` to bind its body to the generated update model, load/authorize the current instance, call `prepare_update_patch()`, and pass the resulting patch to `model_class.update()`.

Preserve the existing ordering:

```text
request validation -> existence lookup -> authorization -> patch validation -> update -> response
```

Do not duplicate protected-field stripping in the handler if the core helper owns it.

#### Actor HTTP

Use the same generated update model and helper in `network_api.py`, then add `id` only to the TX envelope:

```python
patch = prepare_update_patch(_cls, current, data)
tx_data = {'id': id, **patch}
```

Because patch validation requires current state, choose one of these implementation shapes:

1. **Recommended:** keep authoritative merge/full validation in `ActorModel.handler_crud()` after it loads the resource; the HTTP route sends the generated patch unchanged. Factor the helper so extraction can happen at HTTP and merge validation at the model boundary.
2. Avoid an extra HTTP-layer `get` TX solely for validation; it adds a race and doubles actor traffic.

The actor handler should therefore validate the patch against the current resource before calling `cls.update()`.

#### Flask compatibility

Update `routes_flask.py` to use the same patch-preparation semantics where practical. If Flask is no longer a supported generated-route backend, explicitly deprecate it rather than leaving a contradictory full-model route.

### Slice 4 — Make ref flattening preserve caller intent

Update `flatten_refs()` to accept `exclude_unset` and pass that behavior through nested model flattening where appropriate. Existing callers retain full-dump behavior by default; update paths can explicitly preserve field presence.

Ensure this helper:

- handles `Ref[T]`, nested models, and lists without changing their established output shape;
- does not mutate the source model or caller dictionary;
- has unit tests for full and exclude-unset modes.

### Slice 5 — Harden collection normalization

In `sqlite_storage.py`, copy incoming dictionaries before normalization and make both normalizers atomic.

#### `list[T]`

Replace destructive coercion/silent omission:

```python
if not isinstance(value, list):
    data[field_name] = []
```

with a validation error. For every member, either produce a valid local target ID or reject the complete field. Reject remote/cross-service and arbitrary external refs. Preserve explicit empty lists.

Add tests for:

- target instances;
- integer IDs;
- local class/table URL forms already accepted by `local_ref_id()`;
- hydrated dictionaries with `id`/`$id`;
- order and duplicates;
- explicit clear;
- invalid scalar collection;
- one invalid member among valid members (no partial write);
- remote/external refs;
- non-mutating input behavior.

Target existence validation should be a **documented follow-up**, not part of this pass: enforcing it storage-wide requires deciding transaction and cross-storage behavior.

#### `list[Ref[T]]`

Add update-specific tests for:

- local integer refs;
- local class-name/table-name URLs;
- canonical remote `n3tx://` refs;
- configured remote HTTP refs canonicalized to N3TX refs;
- mixed local/remote lists;
- explicit clear;
- omission preservation through both HTTP modes;
- external-link rejection;
- malformed member rejection;
- order, duplicates, and non-mutating input.

Keep `list[Ref[T]]` non-owning: deleting the target must not mutate these pointer arrays automatically.

Mirror equivalent JSON-storage tests or explicitly close any capability gap. The two advertised storage backends must not expose different update semantics.

### Slice 6 — Clean stale local `list[T]` IDs on child deletion

Add model-layer cleanup for registered local-owned relationships only.

Recommended sequence:

```text
1. Discover registered parent models with list[DeletedType] fields.
2. Snapshot affected parent IDs and filtered ordered child-ID arrays while the child is readable.
3. Delete the child.
4. Apply parent patches through the normal update path.
5. Report cleanup failures rather than hiding them.
```

Important constraints:

- operate only on `list[T]`, never `list[Ref[T]]`;
- retain parent ordering and duplicate behavior for remaining IDs;
- support parents with multiple relationship fields targeting the same child type;
- avoid recursive delete semantics—this is reference cleanup, not cascading deletion;
- account for paginated `list()` return shapes;
- document the initial O(parent rows) scan cost;
- leave room for storage-native indexed cleanup later.

Tests should cover one parent, multiple parents, multiple relationship fields, unrelated types, already-stale IDs, and deletion of a missing child. Verify direct and actor delete routes observe the same persisted result.

Because model-level cleanup cannot be transactionally atomic across arbitrary storage backends, preserve stale-ID tolerance during hydration. A failed cleanup must not make unrelated reads fail.

### Slice 7 — Align downstream callers and documentation

#### Frontend

Keep `NTTElement.save()` compatible, but change optimistic forwarding in `NTT.UPDATE()` to send the incoming patch rather than the merged `this.value` where the call path represents a local edit patch:

```diff
 UPDATE(data, event) {
   this.update(data);
   if (!event.source?.startsWith('http')) {
-    this.call('UPDATE', this.value);
+    this.call('UPDATE', data);
   }
 }
```

Evaluate `NTTElement.save()` separately: Formidable currently commits a complete form value, which remains valid. Do not manufacture a frontend dirty-field tracker in this pass unless tests show full-form saves cause real regressions. Document that custom components can send narrow patches.

Add frontend transport/entity tests proving a narrow update remains narrow over HTTP while the local instance merges the server's complete response.

#### Agent tools

Retain `required: ['id']` for update tools. Reuse `writable_update_fields()` when generating CRUD tool schemas so protected-field knowledge has one source of truth. Ensure at least one writable field is supplied at runtime.

#### Documentation

Update:

- `docs/API_CRUD_ENDPOINTS.md`
- `docs/API_OVERVIEW.md`
- `docs/API_DATA_MODELS.md`
- `docs/JSON_FIELDS.md`
- `docs/ARCHITECTURE.md`
- `packages/n3tx-core/docs/storage.md`
- `BACKEND.md`
- `FRONTEND.md`
- `AGENTS.md` only if the architectural/key-file map changes

Document:

- `PUT` is N3TX's compatibility partial-update operation;
- omission versus explicit `null`/`[]`;
- collection replacement semantics;
- ownership distinction between `list[T]` and `list[Ref[T]]`;
- local child deletion cleanup;
- concurrency warning for read-modify-write array replacement;
- recommendation to use domain-specific `@expose_route` methods for append/remove/toggle behavior.

## 💻 Representative Code Shape

### Route integration

```python
def make_update_instance(model_class):
    UpdateModel = make_update_model(model_class)

    async def update_instance(request: Request, id: int, data: UpdateModel):
        current = model_class.get(id)
        if not current:
            raise HTTPException(status_code=404, detail='Not found')
        authorize_update(request, model_class, current)
        patch = prepare_update_patch(model_class, current, data)
        updated = model_class.update(id, patch)
        return updated.model_response()

    return update_instance
```

### Strict local collection normalization

```python
normalized = []
for item in value:
    local_id = local_ref_id(item, target_cls=target_cls)
    if local_id is None:
        raise ValueError(
            f'Invalid local {target_cls.__name__} relationship value '
            f'for {field_name}: {item!r}'
        )
    normalized.append(local_id)
data[field_name] = normalized
```

### Domain methods for concurrency-sensitive mutations

Do not add a generic `append_to_relationship()` framework API in this pass. Keep business intent explicit:

```python
@expose_route('/comment', methods=['POST'])
def comment(self, comment: Comment) -> Comment:
    created = Comment.create(comment)
    type(self).update(self.id, {'comments': [*self.comments, created]})
    return created
```

This remains last-write-wins today. If concurrent relationship mutation is a demonstrated requirement, follow with storage-level atomic collection operations or normalized link rows; a generic model helper without transactional storage support would only hide the race.

## 🧪 Verification Matrix

| Area | Verification |
|---|---|
| Core model/storage | `test_storable_mixin.py`, `test_sqlite_storage.py`, `test_json_storage.py`, relationship/ref tests |
| Direct routes | focused `test_routes.py` partial/collection/OpenAPI cases |
| Actor routes | `test_network_api.py`, `test_actor_model_integration.py`, lifecycle tests |
| Examples | core and actor CRUD/comment/like tests |
| Agents | tool schema and tool-call CRUD tests |
| Frontend | Vitest NTT/transport/component update tests |
| Full regression | backend short runner, then frontend unit suite |

Suggested implementation-time commands:

```bash
.venv-agents/bin/python -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_storable_mixin.py packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py packages/n3tx-core/src/n3tx_core/tests/unit/test_sqlite_storage.py packages/n3tx-core/src/n3tx_core/tests/unit/test_json_storage.py -q
.venv-agents/bin/python -m pytest packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py packages/n3tx-actors/src/n3tx_actors/tests/unit/test_actor_model_integration.py -q
.venv-agents/bin/python -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_tools.py -q
.venv-agents/bin/python scripts/test-backend.py --short -- -q
cd tests/frontend && npx vitest run
```

Also inspect generated OpenAPI for one representative model and manually verify:

```text
PUT /products/{id}
PUT /Product/{id}
```

show the same optional-field update schema in direct and actor modes.

## 📊 Risks and Decisions

| Risk/decision | Chosen handling |
|---|---|
| `PUT` vs `PATCH` | Keep `PUT` for compatibility; document N3TX partial semantics. Do not add two mutation contracts. |
| Model-level validators | Validate merged current+patch state, not an isolated synthetic patch alone. |
| OpenAPI request schema | Generate cached per-model update models with optional-by-presence fields. |
| Empty patch | Reject before storage with a clear client error. |
| Collection duplicates | Preserve existing order and duplicates; document. |
| Target existence | Defer strict existence checks until transaction/storage policy is designed. |
| Child deletion cleanup | Apply only to owned local `list[T]`; tolerate stale IDs if cleanup fails. |
| Cleanup performance | Accept initial O(parent rows) scan; instrument/document for later storage-native optimization. |
| Concurrent append/remove | Document last-write-wins and use domain methods; do not add a falsely atomic generic API. |
| Flask support | Align if supported; otherwise explicitly deprecate rather than silently diverge. |

## ✨ Execution Order

1. Add failing direct/actor route tests for omission preservation and explicit clears.
2. Add the shared update-contract helper and generated update request models.
3. Align direct routes, then actor handler/routes, then Flask compatibility.
4. Harden `flatten_refs()` and collection normalization with focused unit tests.
5. Add stale local `list[T]` cleanup on child deletion.
6. Narrow frontend optimistic update forwarding and verify transport behavior.
7. Reuse writable-field metadata in agent tools.
8. Update docs and example tests to one partial-update contract.
9. Run focused suites, backend short regression, frontend unit tests, and OpenAPI inspection.

## 🚫 Non-Goals

- Adding parallel `PATCH` and `PUT` semantics.
- Introducing normalized join tables or replacing JSON-backed relationships.
- Automatically deleting `list[Ref[T]]` pointers when targets disappear.
- Cross-service existence validation for distributed refs.
- Building a generic atomic relationship mutation API without transactional storage support.
- Changing the frontend to maintain a comprehensive dirty-field tracking system.

## Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-core/src/n3tx_core/models/storable_mixin.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`

## Saved Plan

- `.project/plans/proto-model-update-and-collection-semantics.md`
