# Relationship Update, Authorization, and Deprecation Contracts

## ✅ Outcome

Complete three backend-facing contracts:

1. Direct and actor updates preserve omitted fields through an `exclude_unset` chain.
2. Parent reads authorize owned `T`/`list[T]` children as part of the parent aggregate; direct child routes continue to enforce child rules.
3. `ManyToMany[T]` is deprecated without expanding or rewriting its behavior.

This plan depends on the owned lifecycle semantics in `ref-owned-relationship-lifecycle.md` but can begin with update and authorization tests in parallel.

## 📍 Authorization decision

```text
GET parent
  -> authorize parent read
  -> hydrate and serialize owned T/list[T]
  -> do not independently evaluate child read ACL

GET child directly
  -> authorize child read
  -> child rules remain authoritative
```

Do not describe this as child tables inheriting parent access rules. It is a request-boundary rule: an owned child embedded in an authorized parent representation is part of that parent aggregate.

No reverse lookup, inherited ACL state, parent context propagation, or nested child route is added.

## 💻 Method Signature Surface

```text
n3tx_core.models.ref
  / def flatten_refs(obj: BaseModel, *, exclude_unset: bool = False) -> dict

n3tx_core.api.routes_fastapi
  + def _make_update_model(model_class: type[BaseModel]) -> type[BaseModel]
  / def make_update_instance(model_class: type) -> Callable

n3tx_actors.api.network_api
  / def _register_crud_routes(router, api_adapter, model_class, endpoint_base, tag) -> None

n3tx_actors.models.actor_model.ActorModel
  / @classmethod
    def handler_crud(cls, tx: TX)

n3tx_core.models.relationships.ManyToMany
  / def __class_getitem__(cls, args)
```

## 🛠️ Implementation steps

### 1. Add update regression tests first

Cover table-name and class-name routes in both direct and actor modes:

- Updating one scalar preserves omitted required/defaulted fields.
- Omitted `T` and `list[T]` fields remain unchanged.
- Explicit `[]` clears a collection and invokes the lifecycle plan's cascade.
- Explicit falsey values (`0`, `False`, `""`) are retained.
- Protected fields remain immutable.
- Missing records return matching 404 responses.
- Invalid supplied values return 422.

Critical tests:

- `packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py`
- `packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py`
- `examples/core/tests/test_products_crud.py`
- `examples/actors/tests/test_products_crud.py`

### 2. Preserve explicit-field information in `flatten_refs`

```diff
-def flatten_refs(obj: BaseModel) -> dict:
-    flat = obj.model_dump()
+def flatten_refs(obj: BaseModel, *, exclude_unset: bool = False) -> dict:
+    flat = obj.model_dump(exclude_unset=exclude_unset)
```

Propagate the option recursively to nested models. Preserve the old default for non-update call sites.

Add focused tests for omitted defaults, explicitly supplied default values, nested models, lists, and `Ref` values.

### 3. Accept partial request bodies

The original model type cannot omit required-at-create fields. Build and cache an update request model with every request field optional while preserving aliases and validation metadata.

```text
Product -> ProductUpdate
required create field -> optional request presence
model_fields_set -> omission versus explicit null/value
```

Both direct and actor HTTP route generation must reuse the same helper rather than defining divergent update schemas.

Recommended empty patch behavior: authorize and return the unchanged full entity with HTTP 200.

### 4. Carry only explicit fields through direct routing

```python
patch = flatten_refs(data, exclude_unset=True)
strip_protected_fields(patch)
result = current if not patch else model_class.update(id, patch)
return result.model_response()
```

Authorization must evaluate the current persisted resource before mutation.

### 5. Carry the same patch through actor routing

The actor HTTP adapter must send exactly:

```python
TX(
    name="update",
    data={"id": id, **explicit_patch},
    meta={"user": user, "model_cls": model_class},
)
```

`ActorModel.handler_crud()` must remove only the route ID and pass the remaining patch unchanged to storage. Do not reconstruct a complete model from the TX patch.

Add exact direct/actor parity assertions for success, 404, 403, and invalid-field behavior.

### 6. Lock the parent-aggregate authorization contract

Add direct and actor integration models where:

- Parent is readable by the caller.
- Owned child direct read is denied.
- Parent embeds scalar and collection children.

Assert:

1. Parent read succeeds and embeds children.
2. Direct child read is denied by child ACL.
3. Adding `populate=owned_field` does not alter behavior.
4. Direct and actor modes agree.

No production authorization chain should be added for this contract. The test formalizes the parent aggregate boundary.

### 7. Prove `populate` remains pointer-only

In storage/dump tests:

- `T` and `list[T]` hydrate normally with or without `populate`.
- Reference resolver is not called for owned fields.
- `Ref[T]` and `list[Ref[T]]` still use existing populate behavior.

### 8. Deprecate `ManyToMany[T]`

Keep the export and current behavior during the compatibility window. In `ManyToMany.__class_getitem__`, emit:

```python
warnings.warn(
    "ManyToMany[T] is deprecated and will be removed in the next "
    "breaking release; define an explicit link model instead.",
    DeprecationWarning,
    stacklevel=2,
)
```

Do not invent a release number unless release policy is confirmed. Do not add new CRUD/populate behavior.

Tests must prove:

- Importing `ManyToMany` does not warn.
- Declaring `ManyToMany[T]` warns at the declaration site.
- Existing discovery/generation remains unchanged during deprecation.
- Documentation recommends explicit link models for new code.

### 9. Update active backend documentation

Update:

- `README.md`
- `AGENTS.md`
- `BACKEND.md`
- `CLAUDE.md`
- `docs/AUTHORIZATION.md`
- `docs/API_REFERENCE.md`
- `docs/MODELS.md`
- `packages/n3tx-core/docs/authorization.md`
- `packages/n3tx-core/docs/storage.md`

Required statements:

- PUT/update is partial: omitted fields are preserved.
- Parent authorization governs embedded owned children.
- Direct child routes apply child access rules.
- This is aggregate authorization, not inherited table ACLs.
- Hidden hydration is intentional.
- `populate` is restricted to pointer forms.
- `ManyToMany` is deprecated; explicit link models replace it.

## ⚠️ Risks

| Risk | Mitigation |
|---|---|
| PUT changes from full replacement to patch semantics | Document and update stale tests |
| Dynamic update model loses field metadata | Test aliases, constraints, OpenAPI names, protected fields |
| Parent exposes stricter child | Explicitly document aggregate disclosure and test both boundaries |
| Warnings break strict suites | Capture declaration warnings locally; no global suppression |
| Actor/direct errors drift | Differential parity assertions on exact status/body |

## 🧪 Verification

```bash
/workspace/.venv-agents/bin/python -m pytest \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_ref.py \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_relationships.py -q

/workspace/.venv-agents/bin/python -m pytest \
  packages/n3tx-actors/src/n3tx_actors/api/tests/test_network_api.py \
  packages/n3tx-actors/src/n3tx_actors/tests/unit/test_actor_model_integration.py -q

/workspace/.venv-agents/bin/python scripts/test-backend.py --suite core -- -q
/workspace/.venv-agents/bin/python scripts/test-backend.py --suite actors -- -q
```

## ✅ Acceptance criteria

- Only explicit update fields reach storage in both routing modes.
- Omitted owned relationships are preserved; explicit values trigger lifecycle behavior.
- Parent reads embed owned children under parent authorization.
- Direct child routes still enforce child rules.
- No reverse ACL lookup or inheritance mechanism is introduced.
- `populate` remains exclusive to pointer relationships.
- `ManyToMany[T]` warns on declaration and remains temporarily compatible.
- Active backend documentation states all contracts consistently.

### Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/models/ref.py`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`
- `packages/n3tx-core/src/n3tx_core/models/relationships.py`
