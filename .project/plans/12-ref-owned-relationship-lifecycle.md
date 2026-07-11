# Owned `T` / `list[T]` Relationship Lifecycle

## ✅ Refined outcome

Make exact scalar `T` and exact `list[T]` one SQLite-backed, owned-local-
relationship primitive. Keep `Ref[T]` and `list[Ref[T]]` non-owning identity
pointers.

| Declaration | SQLite form | Read form | Removal behavior |
|---|---|---|---|
| `child: T` | `<field>_id INTEGER` | hydrated `T` | delete replaced child |
| `children: list[T]` | `<field> TEXT` with ordered JSON IDs | hydrated `list[T]` | delete removed children |
| `Ref[T]` | logical field `TEXT` | pointer/href | never cascade |
| `list[Ref[T]]` | logical field `TEXT` with JSON refs | pointer list | never cascade |
| Parent deletion | — | — | recursively delete exact owned descendants |

The guarantee is **SQLite-specific in this pass**. `JSONStorage` does not have a
cross-file transaction and cannot provide atomic ownership lifecycle semantics.

## 🔎 Current-code findings

The original plan had the right product direction, but implementation must first
resolve these concrete mismatches:

1. `ProtoModel.__init_subclass__()` currently rewrites storable scalar `T` into
   `Ref[T]` before Pydantic creates `model_fields`
   (`models/proto_model.py:93-122`). Scalar ownership is therefore unreachable
   for normal storable models today.
2. Migration already knows the intended scalar physical shape (`child_id
   INTEGER`), but SQLite `create()` and `update()` write logical names. Removing
   the rewrite alone would produce invalid SQL.
3. `list[T]` normalization silently converts malformed non-lists to `[]`, drops
   malformed entries, permits missing positive IDs, and mutates caller data
   (`storage/sqlite_storage.py:149-176`). Existing tests currently encode some
   of that permissiveness.
4. Hydration lives in `ProtoModel.__init__()` and opens child storage reads from
   inside model construction. It catches broad exceptions, lacks parent/field
   diagnostics, and creates an N+1 pattern for parent lists
   (`models/proto_model.py:125-140, 253-377`).
5. `_connection()` returns failed connections to the pool without rollback.
   Public mutations each commit independently. Cascades require a safe outer
   transaction first (`storage/sqlite_storage.py:354-361, 379-414, 696-751`).
6. Existing scalar declarations were physically stored as `field TEXT` because
   of the rewrite. Automatically changing them to `field_id INTEGER` can trigger
   orphan-column deletion and data loss in `SQLiteMigration.migrate_table()`.
7. Core and actor example toggle methods explicitly delete `Like` before
   replacing the parent collection. Those calls would conflict with cascade and
   are currently non-atomic.
8. Exact `T` cannot safely recover a missing child as `None`: Pydantic rejects
   `None` for a required field. The original recommendation to construct an
   exact scalar relationship with `None` is not implementable without weakening
   the public model contract.

## 📍 Refined decisions

- Exact `T` and exact `list[T]` are owned. Optional variants remain unsupported
  in this pass; existing optional-classifier tests must be changed deliberately.
- A missing stored child in `list[T]` is omitted, logged with parent model,
  parent ID, field, and child ID, and never repaired during GET.
- A missing stored child for required scalar `T` raises a dedicated relationship
  integrity error. It is not converted to `None` or silently omitted.
- New writes reject IDs `<= 0`, unsaved models, inline child dictionaries,
  malformed values, remote/external refs, nonexistent rows, non-storable
  targets, and targets outside the owner’s SQLite transaction domain.
- A local integer, persisted target model, or local target path/href is accepted
  only when it resolves to a positive ID and the row exists.
- Duplicate list IDs and list order are preserved. Cascade compares membership:
  `[A, A] -> [A]` does not delete `A`; `[A, A] -> []` deletes it once.
- `populate` remains exclusive to `Ref[T]` and `list[Ref[T]]`.
- Cascaded storage deletion bypasses ActorModel lifecycle events and per-child
  authorization in this pass. Parent authorization is authoritative for owned
  descendants. This must be documented explicitly.
- Sharing one owned child between parents remains unsupported. No reverse lookup
  or exclusivity mechanism is added.
- Existing databases do not get an implicit `field TEXT -> field_id INTEGER`
  conversion. Applications with scalar declarations require an explicit/manual
  migration or a separately designed compatibility migration.

## 🗺️ Target flow

```text
Model declaration
  -> exact owned classifier
  -> logical field + physical column metadata

Parent write (one SQLite transaction)
  -> copy caller data
  -> read old raw owned IDs for submitted fields
  -> normalize all submitted owned values
  -> verify target storage domain + row existence with same cursor
  -> mutate parent using logical-to-physical column projection
  -> recursively delete old-membership - new-membership
  -> commit once
  -> on any exception: rollback once

Parent read
  -> read logical scalar from <field>_id and list IDs from JSON
  -> batch load owned targets using the active connection
  -> exact scalar missing: relationship integrity error
  -> list child missing: warning + omit occurrence(s)
  -> construct validated parent
  -> no populate and no read-time repair
```

## 💻 Method signature surface

```text
n3tx_core.utils.introspection
  + @dataclass(frozen=True) class OwnedRelationshipSpec
  + def get_owned_relationship_fields(
        model_class: type,
    ) -> tuple[OwnedRelationshipSpec, ...]
  / def get_fk_fields(model_class: type) -> list[tuple[str, type]]
  / def get_fk_list_fields(model_class: type) -> list[tuple[str, type]]

OwnedRelationshipSpec
  + field_name: str
  + target_cls: type[BaseModel]
  + cardinality: Literal['one', 'many']
  + column_name: str

n3tx_core.storage.sqlite_storage
  + def _transaction(self) -> Iterator[tuple[sqlite3.Connection, sqlite3.Cursor]]
  + def _normalize_owned_id(
        value: object,
        *,
        parent_cls: type,
        spec: OwnedRelationshipSpec,
    ) -> int
  + def _normalize_owned_write_values(
        cursor: sqlite3.Cursor,
        model_class: type,
        data: Mapping[str, object],
    ) -> tuple[dict[str, object], dict[str, tuple[int, ...]]]
  + def _read_owned_ids(
        cursor: sqlite3.Cursor,
        model_class: type,
        id_: int,
        *,
        fields: Iterable[OwnedRelationshipSpec] | None = None,
    ) -> dict[str, tuple[int, ...]]
  + def _delete_owned_entity(
        cursor: sqlite3.Cursor,
        model_class: type,
        id_: int,
        *,
        deleting: set[tuple[type, int]],
    ) -> bool
  / def SQLiteStorage.create(self, model_class: type, data: dict) -> object
  / def SQLiteStorage.update(self, model_class: type, id: int, data: dict) -> None
  / def SQLiteStorage.delete(self, model_class: type, id: int) -> None
  / def SQLiteStorage.get(...)
  / def SQLiteStorage.list(...)

n3tx_core.models.proto_model
  / def ProtoModel.__init_subclass__(cls, **kwargs) -> None
  - def ProtoModel.hydrate_fk(cls, data: object) -> object
  - def _hydrate_fk_value(target_cls: type, value: object) -> object
  - def _hydrate_fk_list(target_cls: type, values: object) -> list

n3tx_core.errors (or local established error module)
  + class RelationshipIntegrityError(ValueError)
```

The preferred refinement is to move persistence hydration into SQLite storage
instead of retaining model-construction-time storage I/O. If deeper inspection
during implementation shows another backend relies on `hydrate_fk()`, retain a
thin compatibility layer but do not let it perform broad-exception storage
queries.

## 🛠️ Implementation plan

### 1. Lock the annotation contract and canonical classifier (red → green)

**Files**

- `packages/n3tx-core/src/n3tx_core/utils/introspection.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_model.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_introspection.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_model.py`

Add failing tests proving exact scalar/list classification, exclusions, optional
non-classification, and immutable physical metadata. Add a separate red test
showing a storable `child: Child` remains `Child`, while explicit `Ref[Child]`
remains a ref. Then remove the legacy direct-model rewrite.

Keep `get_fk_fields()` and `get_fk_list_fields()` as compatibility projections
from the canonical descriptor initially. Update `collect_all_referenced_models`,
schema/dump relationship discovery, migration, and storage to consume the
canonical result rather than reinterpreting annotations.

### 2. Make migration consume physical relationship metadata

**Files**

- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`
- the existing migration unit test module, or a new focused
  `test_sqlite_migration_relationships.py`

Generate exact scalar `<field>_id INTEGER` and list `<field> TEXT` from
`OwnedRelationshipSpec.column_name`. Ensure orphan detection compares physical
column names. Add fresh-schema tests.

Do **not** silently convert legacy `field TEXT` columns. Add a guard that detects
the ambiguous legacy shape and raises/warns with explicit migration guidance
before orphan deletion can remove data. Decide the exact guard based on existing
manual migration conventions; do not infer ownership after a declaration has
already disappeared.

### 3. Establish rollback-safe SQLite transaction ownership

**Files**

- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_sqlite_storage.py`

Add `_transaction()` around pooled connections: commit only after the complete
operation, rollback on every exception, and return a clean connection to the
pool. Refactor `create()`, `update()`, and `delete()` to use it before adding
cascade behavior. Internal helpers receive a cursor and never commit.

Add tests that inject failures, assert no parent/child mutation, and then reuse
the same pool successfully. Preserve public exception types unless a dedicated
relationship error is raised.

### 4. Add strict owned write normalization and column projection

**Files**

- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_sqlite_storage.py`

Normalize into a copy; never mutate caller dictionaries. Validate every owned
field before parent mutation. Use the same cursor to check target existence and
same-database storage compatibility.

Project logical input to physical columns:

```text
{'child': Child(id=3), 'children': [Child(id=4), '/Child/5']}
  -> SQL {'child_id': 3, 'children': '[4, 5]'}
  -> normalized logical {'child': 3, 'children': [4, 5]}
```

Red tests cover valid persisted models/IDs/local paths and every invalid form
listed in the decisions. Replace existing permissive tests that expect a
nonexistent child ID to be accepted.

### 5. Move owned hydration to the storage read boundary

**Files**

- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_model.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_dump.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_sqlite_storage.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_dump_stages.py`

For each `get()`/`list()` result set, gather target IDs by relationship field,
query each target table once on the active connection, and restore scalar/list
values before parent construction. Preserve list order and duplicates.

Raise `RelationshipIntegrityError` for missing required scalar targets. For
lists, log and omit missing positive IDs without writing. Remove broad exception
suppression. Ensure child construction uses already-loaded rows rather than
calling `target_cls(id=...)` and reopening storage reads.

Prove `populate` is ignored for owned fields while explicit refs still populate.
Retain dump-pipeline enrichment so hydrated children receive `$schema`, `$id`,
and registered dump extensions.

### 6. Cascade replaced/removed children atomically

Within `update()`:

```text
read old raw IDs only for explicitly submitted owned fields
normalize and verify all new IDs
update parent
for each submitted field:
  removed = set(old_ids) - set(new_ids)
  recursively delete each removed child
commit once
```

Tests:

- scalar `A -> B`, `A -> A`;
- list `[A, B] -> [B, C]`, reorder-only, explicit `[]`, omitted field;
- duplicate transitions `[A, A] -> [A]` and `[A, A] -> []`;
- recursive descendants and `Ref` targets untouched;
- failure after parent update rolls back every mutation.

### 7. Cascade parent deletion recursively

Use `_delete_owned_entity()` with the same cursor and a transaction-local
`deleting: set[tuple[type, int]]`. Mark a node before descending so cycles
terminate. Read raw child IDs before deleting the row. Duplicate paths delete at
most once. Do not call public `storage.delete()` recursively.

Tests cover scalar/list children, descendants, duplicate paths, cycles, missing
rows, refs untouched, and rollback during a descendant deletion.

### 8. Remove conflicting manual deletes and verify domain declarations

**Files**

- `examples/core/models/product.py`
- `examples/core/models/comment.py`
- `examples/actors/models/product.py`
- `examples/actors/models/comment.py`
- corresponding core/actor social tests

Remove explicit `Like.delete()` calls before parent relationship replacement.
The parent update must be the atomic lifecycle operation.

Audit active exact `list[T]` declarations before release:

| Declaration | Consequence to validate |
|---|---|
| `Product.comments`, `Product.favorites`, `Comment.likes` | parent owns rows; deletion cascades |
| `Conversation.messages` | conversation deletion owns messages |
| `AgentActor.tools` | agent deletion/replacement owns `AgentTool` rows |

If any target is conceptually shared, change that model declaration to
`list[Ref[T]]` as part of this implementation and add compatibility tests. Do
not weaken the ownership primitive to accommodate an incorrectly declared
shared pointer.

### 9. Document the actual contract

Update:

- `AGENTS.md` and `BACKEND.md`
- `docs/ARCHITECTURE.md`
- `docs/CORE.md`
- `docs/MODELS.md`
- `docs/JSON_FIELDS.md`
- `docs/API_CRUD_ENDPOINTS.md`
- `packages/n3tx-core/README.md`
- `packages/n3tx-core/docs/storage.md`
- affected example comments/readmes

Document SQLite scope, exact-only annotation support, strict persisted-ID input,
physical columns, cascade and rollback semantics, required-scalar integrity
failure, list missing-child omission, no read repair, no exclusivity/reverse
lookup, no ref cascade, no child lifecycle events, and explicit legacy migration
requirements.

## 📊 Risk and mitigation

| Risk | Mitigation |
|---|---|
| Legacy scalar `field TEXT` is dropped | detect ambiguous shape; require explicit migration |
| Failed transaction poisons pooled connection | rollback in one outer transaction helper; reuse test |
| Required scalar child disappears | typed integrity error; never construct `None` for exact `T` |
| Owned target uses another backend/database | reject registration/write; require one SQLite transaction domain |
| Shared child is deleted | audit declarations; shared relationships use `Ref` primitives |
| Recursive cycle | mark-before-descend deletion guard |
| Duplicate list IDs | preserve sequence; cascade by membership set |
| Actor lifecycle expectations | document cascade as storage lifecycle; add events later only with an outbox design |
| Hydration query explosion | batch per target/field on the active connection |
| HTTP full-model PUT clears omitted defaults | retain existing compatibility warning and test explicit replacement behavior |

## 🧪 Verification

Run narrow red/green groups first, then package and integration suites:

```bash
/workspace/.venv-agents/bin/python -m pytest \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_introspection.py \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_model.py \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_sqlite_storage.py \
  packages/n3tx-core/src/n3tx_core/tests/unit/test_proto_dump_stages.py -q

/workspace/.venv-agents/bin/python scripts/test-backend.py --suite core -- -q
/workspace/.venv-agents/bin/python scripts/test-backend.py --suite actors -- -q
/workspace/.venv-agents/bin/python scripts/test-backend.py --suite agents -- -q
/workspace/.venv-agents/bin/python -m pytest examples/chat/tests/ -q
```

Add the focused migration test module to the first command once its final name is
chosen. If declaration audits change schemas used by the frontend, also run:

```bash
cd /workspace/tests/frontend && npx vitest run
```

## ✅ Acceptance criteria

- One immutable classifier drives schema relationship discovery, migration,
  write projection, hydration, dump enrichment, and cascade.
- Storable scalar `T` is no longer rewritten into `Ref[T]`.
- Both owned forms accept only existing persisted positive local IDs.
- Scalar uses `<field>_id`; list uses ordered JSON IDs.
- Reads batch hydrate without `populate` or hidden writes.
- Missing list children are logged and omitted; missing exact scalar children
  raise a relationship integrity error.
- Explicit replacement and parent deletion recursively cascade in one atomic
  SQLite transaction.
- Omitted update fields do not cascade.
- `Ref[T]` and `list[Ref[T]]` never cascade.
- Failed writes/cascades roll back and leave pooled connections reusable.
- Legacy scalar columns are not silently dropped or converted.
- Active model declarations have been audited for true ownership.

### Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/utils/introspection.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_model.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_sqlite_storage.py`
