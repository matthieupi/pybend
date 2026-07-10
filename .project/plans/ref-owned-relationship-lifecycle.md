# Owned `T` / `list[T]` Relationship Lifecycle

## ✅ Outcome

Make scalar `T` and `list[T]` one coherent owned-local-relationship primitive:

| Declaration | Stored form | Read form | Removal behavior |
|---|---|---|---|
| `child: T` | local child ID | hydrated `T` | delete replaced child |
| `children: list[T]` | ordered JSON child IDs | hydrated `list[T]` | delete removed children |
| Parent deletion | — | — | recursively delete owned children |

`Ref[T]` and `list[Ref[T]]` remain non-owning pointers and are never cascaded.

## 📍 Decisions and non-goals

- Hidden automatic hydration remains intentional.
- `populate` applies only to `Ref[T]` and `list[Ref[T]]`.
- Optional relationship annotations are unsupported in this pass.
- No reverse lookup, exclusive ownership enforcement, or ownership FK is added.
- Sharing one child ID between parents is allowed but unsupported: deletion by one parent may leave a stale ID in another.
- Missing positive child IDs during reads are treated as upstream deletion cleanup: omit them from the hydrated value without writing during GET.
- New writes must reject IDs `<= 0`, unsaved children, malformed values, remote refs, and nonexistent local IDs.

## 🗺️ Target flow

```text
Parent write
  -> classify exact T / list[T]
  -> normalize persisted positive child IDs
  -> verify children exist
  -> mutate parent
  -> old IDs - new IDs
  -> recursively delete removed children
  -> commit once

Parent read
  -> read scalar ID / ordered JSON IDs
  -> batch load children
  -> omit missing positive IDs with diagnostic logging
  -> hydrate T / list[T]
  -> no populate and no read-time repair write
```

## 💻 Method Signature Surface

```text
n3tx_core.utils.introspection
  + def get_owned_relationship_fields(model_class: type) -> list[OwnedRelationshipSpec]

n3tx_core.storage.sqlite_storage
  + def _normalize_owned_id(value: object, *, field_name: str, target_cls: type) -> int
  + def _normalize_owned_values(model_class: type, data: dict) -> dict
  + def _read_owned_ids(cursor, model_class: type, id_: int) -> dict[str, list[int]]
  + def _delete_owned_entity(cursor, model_class: type, id_: int, *, deleting: set[tuple[type, int]]) -> None
  / def SQLiteStorage.create(self, model_class: type, data: dict) -> object
  / def SQLiteStorage.update(self, model_class: type, id_: int, data: dict) -> None
  / def SQLiteStorage.delete(self, model_class: type, id_: int) -> None

n3tx_core.models.proto_model
  / def ProtoModel.hydrate_fk(cls, data: object) -> object
  / def _hydrate_fk_value(target_cls: type, value: object) -> object
  / def _hydrate_fk_list(target_cls: type, values: object) -> list
```

Use an internal immutable descriptor containing `field_name`, `target_cls`, and `cardinality`. Exact naming may follow local conventions.

## 🛠️ Implementation steps

### 1. Add the canonical owned-field classifier

**Files**

- `packages/n3tx-core/src/n3tx_core/utils/introspection.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_introspection.py`

Add red tests proving:

- Exact `T` is scalar-owned.
- Exact `list[T]` is collection-owned.
- `Ref[T]`, `list[Ref[T]]`, primitive lists, dictionaries, and `ManyToMany[T]` are not owned.
- Optional variants are not classified in this pass.

Make migration, storage, hydration, and cascade consume this classifier instead of independently interpreting annotations.

### 2. Stop scalar `T` from diverging from `list[T]`

**Files**

- `packages/n3tx-core/src/n3tx_core/models/proto_model.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`

Remove or narrow the legacy implicit `T -> Ref[T]` rewrite. Preserve scalar `T` as owned relationship metadata.

Keep the existing physical convention if compatible with current databases:

```text
child: T        -> child_id INTEGER
children: list[T] -> children TEXT containing JSON IDs
```

Ensure `create()`, `get()`, `list()`, and `update()` consistently map the logical scalar field to `<field>_id`.

### 3. Reject invalid and unsaved children

Add red tests for scalar and list forms:

- Persisted model with `id > 0` succeeds.
- Positive local integer/path succeeds when the row exists.
- `id=0`, negative ID, unsaved model, inline dictionary without positive ID, remote/external ref, malformed value, and nonexistent child all fail.
- A failed write leaves parent and children unchanged.

Representative check:

```python
child_id = local_ref_id(value, target_cls=target_cls)
if child_id is None or child_id <= 0:
    raise ValueError(
        f"Invalid owned relationship {parent_name}.{field_name}: "
        "child must have a persisted positive id"
    )
```

Do not silently filter invalid list entries.

### 4. Make scalar and list hydration symmetrical

Add tests for `get()` and `list()`:

- Scalar IDs hydrate to complete `T` records.
- List IDs hydrate in stored order.
- Duplicate IDs preserve their occurrence and order.
- Missing positive IDs are omitted and logged.
- Reads never repair the parent row.
- `populate` has no effect on owned `T`/`list[T]`.

Keep hidden hydration for now. Avoid broad `except Exception`; only tolerate expected missing-child conditions.

For a missing required scalar child, define one recovery behavior and test it. Recommended: controlled internal construction with `None` plus a warning, while continuing to reject `None` on writes.

### 5. Cascade on field replacement/removal

Within one SQLite transaction:

```text
read old raw owned IDs
normalize and verify submitted IDs
update parent
for each explicitly patched owned field:
    removed = set(old_ids) - set(new_ids)
    recursively delete removed children
commit
```

Required tests:

- Scalar `A -> B` deletes A.
- Scalar `A -> A` deletes nothing.
- List `[A, B] -> [B, C]` deletes A only.
- Reordering deletes nothing.
- Explicit `[]` deletes all former children.
- An omitted relationship field is unchanged.
- Cascades recurse through child-owned relationships.
- Any failure rolls back the parent mutation and every deletion.

### 6. Cascade on parent deletion

Implement an internal recursive helper using the same connection/cursor. Do not call public `storage.delete()` from inside the cascade.

Use a guard:

```python
deleting: set[tuple[type, int]]
```

Tests must prove:

- Parent deletion deletes scalar and list children.
- Descendant ownership cascades recursively.
- Duplicate paths delete once.
- Cycles terminate.
- `Ref` targets are untouched.
- Transaction failure restores parent and children.

### 7. Preserve missing-child cleanup semantics

The current omission of deleted children is acceptable as the system-level projection of upstream removal, with these constraints:

- Only missing positive IDs are omitted.
- Invalid new writes are rejected.
- Surviving list order is preserved.
- A diagnostic identifies parent model, field, and missing ID.
- GET performs no hidden mutation.

Do not auto-repair stored JSON during hydration; repair can occur on the next explicit parent write.

### 8. Update backend documentation

Update:

- `BACKEND.md`
- `docs/MODELS.md`
- `docs/JSON_FIELDS.md`
- `packages/n3tx-core/docs/storage.md`
- `packages/n3tx-core/README.md`

Document ownership, cascade behavior, strict persisted-ID input, unsupported optional variants, missing-child omission, and the absence of exclusivity/reverse lookup.

## ⚠️ Risks

| Risk | Required mitigation |
|---|---|
| Shared child deleted by one parent | Document unsupported sharing; tolerant missing-child hydration |
| Recursive cycles | Transaction-local deletion guard |
| Partial cascade commits | One connection and one outer transaction |
| Existing zero IDs | Reject new writes; decide migration/diagnostic treatment for legacy rows |
| Scalar physical column mismatch | Add create/get/list/update round-trip tests for `<field>_id` |
| Auto-migration field removal | Require explicit migration; do not infer child target after declaration disappears |

## 🧪 Verification

```bash
/workspace/.venv-agents/bin/python -m pytest \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_introspection.py \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_sqlite_storage.py \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_model.py \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_dump_stages.py -q

/workspace/.venv-agents/bin/python scripts/test-backend.py --suite core -- -q
/workspace/.venv-agents/bin/python scripts/test-backend.py --suite actors -- -q
```

## ✅ Acceptance criteria

- Scalar `T` and `list[T]` use one classifier and lifecycle policy.
- Both store only persisted positive local IDs.
- ID `0` and invalid entries fail loudly.
- Both hydrate automatically without `populate`.
- Explicit replacement deletes removed children atomically.
- Parent deletion recursively deletes owned children atomically.
- Omitted fields do not trigger deletion.
- Missing stored children are omitted without read-time writes.
- `Ref` relationships are never cascaded.
- No reverse lookup or exclusivity machinery is added.

### Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/utils/introspection.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_model.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_sqlite_storage.py`
