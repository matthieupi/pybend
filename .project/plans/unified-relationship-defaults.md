# Unified Relationship Edge Architecture — Full Implementation Plan

## ✅ Executive Summary

N3TX should replace its relationship surface area with a simpler semantic type contract backed by a unified **relationship-edge engine**.

Developer-facing contract:

```python
class Project(ActorModel):
    # Loose/distributed references — explicit pointer semantics.
    owner: Ref[User]
    dependencies: list[Ref[Task]] = Field(default=[])

    # Local bound object graph — same DB, loaded with the parent by default.
    primary_task: Task | None = None
    active: list[Task] = Field(default=[])
    archived: list[Task] = Field(default=[])

    # Shared membership — independent targets, explicit association semantics.
    contributors: ManyToMany[User] = Field(default=[])
```

Internal contract:

| Declaration | Developer meaning | Backend storage | Default read |
|---|---|---|---|
| `Ref[T]` | loose local/distributed pointer | scalar TEXT ref column | public ref string |
| `list[Ref[T]]` | loose pointer list | JSON TEXT ref array | public ref strings |
| `T` / `Optional[T]` | local bound single object | target row + relationship edge | inline object |
| `list[T]` | local bound object collection | target rows + relationship edges | inline capped list |
| `ManyToMany[T]` | shared membership | relationship edges | refs or opt-in load |
| `ListRef[T]` | legacy owned collection | compatibility adapter, then edges | legacy-compatible |

The core implementation shift is from pair-based relationship identity:

```text
(Project, Task)
```

to field-qualified relationship identity:

```text
(owner_type, owner_id, field_name, target_type, target_id)
```

This solves the critical ambiguity:

```python
class Project(ActorModel):
    active: list[Task]
    archived: list[Task]
```

without universal `parent_id`, child schema pollution, or generated subclass explosion.

---

## 🧭 Intent and Non-Negotiable Constraints

### Why this exists

Current relationship DX exposes too many primitives for similar-looking concepts:

- `Task`
- `Ref[Task]`
- `list[Task]`
- `ListRef[Task]`
- `list[Ref[Task]]`
- `ManyToMany[Task]`
- explicit `join_models=[...]`
- generated join tables/classes/routes

The framework can keep optimized internal paths, but developers should choose based on **semantic intent**, not storage mechanics.

### Must preserve

1. **Model-is-the-app:** Python annotations remain the single source of truth.
2. **Backend authoritative schema:** frontend reads relationship behavior from schema, not duplicated JS heuristics.
3. **Distributed refs remain explicit:** only `Ref[T]` and `list[Ref[T]]` support remote/loose references by default.
4. **Local bound models keep identity:** `T` / `list[T]` target rows must be normal N3TX resources with schema, `$id`, routes, auth, and methods.
5. **Compatibility:** existing `ListRef`, generated join models, nested routes, href arrays, and tests must keep working during migration.
6. **No universal `parent_id`:** relationship identity must include field name to support multiple relationships to the same target.

### Deliberate tradeoff

`list[T]` and `ManyToMany[T]` will share edge storage, but not semantics:

- `list[T]`: local bound object graph; create inline allowed; load by default; lifecycle policy may eventually own/delete-orphan.
- `ManyToMany[T]`: shared association; link existing targets by default; do not imply lifecycle ownership; load opt-in by default.

---

## 📍 Current Code Surfaces

These are the exact current modules and functions to change or preserve.

### Relationship primitives

File: `packages/n3tx-core/src/n3tx_core/models/relationships.py`

Current public items:

```python
@dataclass(frozen=True)
class Relationship:
    kind: Literal['many_to_many']
    owner: type
    field_name: str
    target: type
    through: type | None = None
    owner_fk: str | None = None
    target_fk: str | None = None
    table_name: str | None = None

class _ManyToManyMarker: ...
class ManyToMany: ...

def _ensure_owner_relationships(owner_cls: type) -> dict: ...
def generate_relationship_model(owner_cls: type, field_name: str, target_cls: type, through_model: type | None = None): ...
def generate_relationship_models(model_classes: list[type]) -> list[type]: ...
```

### Introspection

File: `packages/n3tx-core/src/n3tx_core/utils/introspection.py`

Current relationship helpers:

```python
def _unwrap_listref(field_type, field_metadata=None): ...
def _unwrap_many_to_many(field_type, field_metadata=None): ...

@functools.lru_cache(maxsize=None)
def get_many_to_many_fields(model_class: Type[Any]) -> List[Tuple[str, Type, Type | None]]: ...

@functools.lru_cache(maxsize=None)
def get_list_fields(model_class: Type[Any]) -> List[Tuple[str, Type]]: ...

@functools.lru_cache(maxsize=None)
def get_ref_fields(model_class: Type[Any]) -> List[Tuple[str, Type]]: ...

@functools.lru_cache(maxsize=None)
def get_ref_list_fields(model_class: Type[Any]) -> List[Tuple[str, Type]]: ...

@functools.lru_cache(maxsize=None)
def get_json_fields(model_class: Type[Any]) -> List[str]: ...
```

### Generated join models

File: `packages/n3tx-core/src/n3tx_core/models/proto_model.py`

Current generator:

```python
def generate_join_model(
    owner_cls: Type[ProtoModel],
    ref_model: Type[ProtoModel],
    field_name: str = None,
): ...
```

Current generated metadata:

```python
__tablename__ = f"{owner_tablename}_{ref_tablename}"
__tagname__ = field_name or ref_model.__tablename__
__storable__ = True
__owner__ = owner_cls
__parent__ = ref_model
{owner_name.lower()}_id: int
```

### Registration

File: `packages/n3tx-core/src/n3tx_core/utils/registrar.py`

Current registry:

```python
registered_models: Dict[str, Type[Any]] = {}
join_models: Dict[tuple[str, str], Type[Any]] = {}

@dataclass
class RegistrationResult:
    model_class: Type[Any]
    tablename: str
    storage: Optional[StorageInterface]
    is_storable: bool
    is_join: bool
    join_key: Optional[Tuple[str, str]]

def prepare_model(model_class: Type[Any], storage: StorageInterface = None) -> RegistrationResult: ...
def apply_registration(result: RegistrationResult) -> None: ...
def register_model(model_class: Type[Any], storage: StorageInterface = None): ...
```

Current issue: `join_models` is keyed by `(ParentName, ChildName)`, which cannot distinguish `active: list[Task]` from `archived: list[Task]`.

### SQLite storage

File: `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`

Current relevant signatures:

```python
def _coerce_value(v): ...
def _deserialize_json_fields(model_class, record): ...
def _normalize_ref_storage_values(model_class, data): ...
def _public_storage_ref(value, target_cls): ...
def _public_ref_list(value, target_cls): ...

class SQLiteStorage(AbstractStorage):
    def __init__(self, database: str = 'database.db', pool_size: int = 4, reference_resolver=None): ...
    def set_reference_resolver(self, reference_resolver): ...
    def _resolve_reference(self, ref, *, target_cls=None, context=None): ...
    def _populate_ref_list_field(self, field_name, target_cls, instances, conn): ...
    def create_table(self, model_class: Type[Any]): ...
    def migrate_table(self, model_class: Type[Any]): ...
    def create(self, model_class: Type[Any], data: Dict[str, Any]) -> Any: ...
    def list(self, model_class: Type[Any], sql_filter: tuple = None,
             limit: int = None, offset: int = None, populate: PopulateSpec = None,
             ids: list = None) -> List[Any]: ...
    def get(self, model_class: Type[Any], id: int, as_dict: bool = False, populate: PopulateSpec = None) -> Any: ...
    def _populate_fields(self, model_class, instances, populate, conn, _visited=None): ...
```

### SQLite migration

File: `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`

Current relevant signatures:

```python
class SQLiteMigration:
    def __init__(self, database: str = 'database.db', migrations_dir: str = 'migrations'): ...
    def _create_relationship_indexes(self, cursor: sqlite3.Cursor, model_class: Type[Any]): ...
    def create_table(self, model_class: Type[Any]): ...
    def migrate_table(self, model_class: Type[Any]): ...
    def run_migrations(self): ...
    def rollback(self, steps: int = 1): ...
    def migration_status(self) -> dict: ...
```

### Direct routes

File: `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`

Current relevant signatures:

```python
def _build_context(request, model_class, action, resource=None, parent_id=None): ...
def _serialize(instance): ...
def make_create_instance(model_class): ...
def make_get_all_instances(model_class): ...
def make_collection_list(model_class): ...
def make_get_schema(model_class): ...
def make_get_instance(model_class): ...
def make_update_instance(model_class): ...
def make_delete_instance(model_class): ...
def register_routes(): ...
```

### Dump pipeline

File: `packages/n3tx-core/src/n3tx_core/models/proto_dump.py`

Current relevant signatures:

```python
def run_pipeline(instance, **kwargs) -> dict: ...
def base(instance, **kwargs) -> dict: ...
def schema_url(instance, d: dict) -> dict: ...
def instance_url(instance, d: dict) -> dict: ...
def populate(instance, d: dict) -> dict: ...
```

---

## 🧱 Full Code Change Surface Matrix

This section is the junior-engineer checklist for where code is added, changed, preserved, or deliberately not removed.

### Add new files

| File | Add | Why |
|---|---|---|
| `packages/n3tx-core/src/n3tx_core/models/relationship_edge.py` | `RelationshipEdge` hidden framework model | Avoid circular imports and keep edge row as a normal storable model |
| `packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_specs.py` | relationship classification tests | Lock semantic type contract |
| `packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_edges.py` | edge table/index bootstrap tests | Verify infrastructure registration |
| `packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_edge_storage.py` | edge CRUD/hydration tests | Verify local bound relationship behavior |
| `packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_schema.py` | schema metadata tests | Verify backend authoritative relationship contract |
| `packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_routes.py` | field route tests | Verify canonical route grammar |
| `examples/core/tests/test_edge_relationships.py` | direct integration tests | Verify app-level DX |
| `examples/actors/tests/test_edge_relationships.py` | actor integration tests | Verify Level 3 parity |

### Change existing files

| File | Change | Why |
|---|---|---|
| `models/relationships.py` | add `RelationshipKind`, `RelationshipStorage`, `RelationshipSpec`, `relationship_schema`; preserve `ManyToMany` | central semantic relationship contract |
| `utils/introspection.py` | add `get_relationship_specs`; keep old helpers compatible | one introspection source of truth |
| `app.py` | auto-register hidden `RelationshipEdge` when edge-backed specs exist | edge table appears without app boilerplate |
| `utils/registrar.py` | add field-qualified relationship registry while preserving `join_models` | distinguish duplicate same-target fields |
| `storage/sqlite_migration.py` | create edge indexes; avoid orphan-column regressions | performance + safe migrations |
| `storage/sqlite_storage.py` | split relationship payloads; create/read/update edges; hydrate defaults | implement edge-backed local relationships |
| `models/proto_schema.py` | emit field-level relationship metadata | schema-driven frontend/tool behavior |
| `api/routes_fastapi.py` | add field-qualified relationship routes | canonical route grammar for edge relations |
| `models/proto_dump.py` | optionally support relation-aware `$id`/metadata overlays | preserve identity during hydration |
| `n3tx_actors/api/network_api.py` | mirror field routes in actor mode | direct/actor parity |
| `static/core/NTT.js` | normalize inline bound objects/lists | frontend accepts new response shapes |
| `n3tx_ui/static/components/ntx-list-field.js` | render inline related objects and legacy href refs | UI compatibility |

### Preserve during implementation

| Surface | Preserve because |
|---|---|
| `Ref[T]` storage and populate | distributed/loose refs already work and are correct |
| `list[Ref[T]]` JSON TEXT behavior | this is the explicit Option-B pointer-list primitive |
| `ListRef[T]` syntax | existing apps and examples use it |
| generated join model routes | compatibility and existing tests rely on them |
| `join_models[(Parent, Child)]` | app methods currently use this lookup |
| href-array ListRef responses | frontend and API tests rely on this shape |

### Do not remove in this project

No production behavior should be removed in the first implementation. These become future deprecations only after edge-backed behavior is stable:

| Future removal/deprecation | Earliest safe point | Replacement |
|---|---|---|
| teaching `ListRef[T]` as default | after examples/docs migrate | `list[T]` |
| explicit `join_models=[...]` for common relationships | after auto edge relationships ship | model field annotations |
| pair-keyed `join_models` as primary registry | after field-keyed registry is adopted | `relationship_models[(owner, field, target)]` |
| generated join model schemas as public primary concept | future major release only | field-qualified relationship routes/schema |

### Functions/classes to delete now

None.

Deleting existing relationship functions during this change would create unnecessary compatibility risk. The implementation should add new canonical APIs, migrate consumers to them, and only then consider deprecation/removal in a later release.

---

## 🧩 New Core Concepts

### RelationshipKind

Add to `packages/n3tx-core/src/n3tx_core/models/relationships.py`.

```python
from enum import Enum


class RelationshipKind(str, Enum):
    """Semantic relationship categories derived from model annotations."""

    REF = "ref"
    REF_LIST = "ref_list"
    BOUND_ONE = "bound_one"
    BOUND_MANY = "bound_many"
    MANY_TO_MANY = "many_to_many"
    LEGACY_LISTREF = "legacy_listref"
```

Why:

- lets storage/routes/schema branch by meaning, not annotation mechanics
- prevents `list[T]`, `list[Ref[T]]`, and `ManyToMany[T]` from being conflated
- gives frontend/tools a stable vocabulary

### RelationshipStorage

Add to `relationships.py`.

```python
class RelationshipStorage(str, Enum):
    REF_COLUMN = "ref_column"
    JSON_REFS = "json_refs"
    RELATIONSHIP_EDGE = "relationship_edge"
    LEGACY_JOIN = "legacy_join"
```

Why:

- separates semantic kind from physical storage
- allows `ListRef[T]` to be semantically `BOUND_MANY` while physically using legacy joins during migration
- allows `ManyToMany[T]` to move from generated link models to relationship edges without changing developer syntax

### RelationshipSpec

Add to `relationships.py`.

```python
@dataclass(frozen=True)
class RelationshipSpec:
    """Canonical relationship descriptor derived from one model field."""

    owner: type
    target: type
    field_name: str
    kind: RelationshipKind
    storage: RelationshipStorage
    cardinality: Literal["one", "many"]
    load_default: bool = False
    owns_lifecycle: bool = False
    ordered: bool = True
    through: type | None = None
    legacy_join_model: type | None = None

    @property
    def owner_type(self) -> str: ...

    @property
    def target_type(self) -> str: ...

    @property
    def route_segment(self) -> str: ...
```

Implementation detail:

```python
@property
def owner_type(self) -> str:
    return self.owner.__name__

@property
def target_type(self) -> str:
    return self.target.__name__

@property
def route_segment(self) -> str:
    return self.field_name
```

Why:

- becomes the single source of truth for routes, schema, storage, and frontend metadata
- field name is first-class, solving same-target ambiguity

### RelationshipEdge

Add hidden infrastructure model to `relationships.py` or a new file `models/relationship_edge.py`. Recommendation: keep in `relationships.py` initially to avoid another module boundary until behavior stabilizes.

```python
class RelationshipEdge(ProtoModel):
    """Hidden framework row connecting one owner field to one target row."""

    __tablename__ = "n3tx_relationship_edges"
    __storable__ = True
    __hidden__ = True

    owner_type: str
    owner_id: int
    field_name: str
    target_type: str
    target_id: int
    relation_kind: str
    position: int | None = None
    metadata: dict = Field(default={})
```

Why:

- one table supports `T`, `list[T]`, `ManyToMany[T]`, and eventually legacy `ListRef[T]`
- avoids child table pollution
- supports multiple parent fields to same target
- supports ordered lists via `position`

### Edge table indexes

Add to `SQLiteMigration._create_relationship_indexes(...)` or a new helper.

```python
def _create_edge_indexes(self, cursor: sqlite3.Cursor, table_name: str = "n3tx_relationship_edges") -> None: ...
```

SQL:

```sql
CREATE INDEX IF NOT EXISTS idx_n3tx_rel_owner_field
ON n3tx_relationship_edges(owner_type, owner_id, field_name);

CREATE INDEX IF NOT EXISTS idx_n3tx_rel_target
ON n3tx_relationship_edges(target_type, target_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_n3tx_rel_unique
ON n3tx_relationship_edges(owner_type, owner_id, field_name, target_type, target_id);
```

Do **not** rely on SQLite partial unique indexes in phase 1. Enforce `BOUND_ONE` cardinality in storage code first for portability.

---

## 🛠️ Implementation Phases

## Phase 0 — Characterize and Protect Current Behavior

### Why

Before refactoring relationship internals, lock down existing behavior so compatibility regressions are visible.

### Code changes

No production code changes except adding tests.

### Tests to add/update

Add `packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_specs.py` later in Phase 1. For Phase 0, add or confirm current tests:

1. Existing `ListRef` href arrays:
   - `examples/core/tests/test_fk_hydration.py`
   - assert `Product.comments` returns href array without populate
2. Existing populated wrapper:
   - assert `GET /Product/{id}?populate=comments` returns `comments.data` and `comments.meta`
3. Existing join schemas/routes:
   - `examples/core/tests/test_schema_endpoints.py`
   - `examples/core/tests/test_comments_crud.py`
4. Existing `list[Ref[T]]` JSON behavior:
   - `packages/n3tx-core/src/n3tx_core/tests/unit/test_sqlite_storage.py`
5. Existing `ManyToMany` generation:
   - `packages/n3tx-core/src/n3tx_core/tests/unit/test_relationships.py`

### Acceptance criteria

```bash
python3 scripts/test-backend.py --suite core -- -q
python3 -m pytest examples/core/tests/test_fk_hydration.py -q
python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_relationships.py -q
```

---

## Phase 1 — Add RelationshipSpec Detection With No Behavior Change

### Why

All layers currently rediscover relationship shape independently. Add a canonical descriptor first, then migrate consumers incrementally.

### Files to change

- `packages/n3tx-core/src/n3tx_core/models/relationships.py`
- `packages/n3tx-core/src/n3tx_core/utils/introspection.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_schema.py` later for schema metadata, but not required for Phase 1

### Additions in `relationships.py`

Add:

```python
class RelationshipKind(str, Enum): ...
class RelationshipStorage(str, Enum): ...

@dataclass(frozen=True)
class RelationshipSpec: ...

def relationship_schema(spec: RelationshipSpec) -> dict:
    """Serialize a RelationshipSpec into schema-safe metadata."""
```

Signature:

```python
def relationship_schema(spec: RelationshipSpec) -> dict:
```

Return shape:

```python
{
    "kind": spec.kind.value,
    "target": spec.target.__name__,
    "field": spec.field_name,
    "storage": spec.storage.value,
    "cardinality": spec.cardinality,
    "load_default": spec.load_default,
    "ordered": spec.ordered,
}
```

### Additions in `introspection.py`

Add helpers:

```python
def _unwrap_optional(field_type):
    """Return (inner_type, is_optional) for Optional[T] / T | None."""

def _resolve_forward_model(owner_cls: Type[Any], maybe_model):
    """Resolve string forward refs against owner_cls.__module__."""

def _is_model_type(type_: Any) -> bool:
    """Return True for concrete Pydantic/N3TX model classes."""

def _unwrap_bound_model_field(model_class: Type[Any], field_type, field_metadata=None):
    """Return target model for T / Optional[T] bound-one fields, excluding Ref/ListRef/ManyToMany."""

@functools.lru_cache(maxsize=None)
def get_relationship_specs(model_class: Type[Any]) -> dict[str, RelationshipSpec]:
    """Return canonical relationship specs keyed by field name."""
```

Required exact signature:

```python
@functools.lru_cache(maxsize=None)
def get_relationship_specs(model_class: Type[Any]) -> dict[str, RelationshipSpec]:
```

Detection rules, in order:

1. `ManyToMany[T]` → `MANY_TO_MANY`, `RELATIONSHIP_EDGE`, many, `load_default=False`
2. `ListRef[T]` → `LEGACY_LISTREF`, `LEGACY_JOIN`, many, `load_default=False` during compatibility phase
3. `list[Ref[T]]` → `REF_LIST`, `JSON_REFS`, many, `load_default=False`
4. `Ref[T]` → `REF`, `REF_COLUMN`, one, `load_default=False`
5. `list[T]` where `T` is model → `BOUND_MANY`, `RELATIONSHIP_EDGE`, many, `load_default=True`
6. `T` / `Optional[T]` where `T` is model → `BOUND_ONE`, `RELATIONSHIP_EDGE`, one, `load_default=True`

Important guardrail:

- `list[str]`, `list[int]`, `dict`, `list[dict]` remain JSON fields.
- `list[Ref[T]]` must not be classified as `BOUND_MANY`.
- `ListRef[T]` must keep legacy behavior until explicit migration.

### Changed functions

Do not remove current functions yet. Update their implementation to use shared lower-level helpers only where safe:

```python
def get_list_fields(model_class: Type[Any]) -> List[Tuple[str, Type]]:
```

Keep return behavior unchanged for compatibility.

```python
def get_json_fields(model_class: Type[Any]) -> List[str]:
```

Ensure it continues to exclude `list[T]`, `ListRef[T]`, and `ManyToMany[T]`, and continues to include `list[Ref[T]]`.

### Tests

Create `packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_specs.py`.

Test cases:

```python
def test_relationship_specs_classify_ref_scalar(): ...
def test_relationship_specs_classify_ref_list_as_json_refs(): ...
def test_relationship_specs_classify_bound_one_plain_model(): ...
def test_relationship_specs_classify_optional_bound_one_plain_model(): ...
def test_relationship_specs_classify_bound_many_plain_model_list(): ...
def test_relationship_specs_classify_many_to_many(): ...
def test_relationship_specs_classify_legacy_listref(): ...
def test_relationship_specs_do_not_treat_primitive_lists_as_relationships(): ...
def test_relationship_specs_support_two_fields_to_same_target(): ...
```

Key assertion for duplicate fields:

```python
specs["active"].field_name == "active"
specs["archived"].field_name == "archived"
specs["active"].target is Task
specs["archived"].target is Task
```

### Acceptance criteria

```bash
python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_specs.py -q
python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_json_fields.py -q
```

---

## Phase 2 — Add RelationshipEdge Infrastructure

### Why

Before changing `T` / `list[T]` behavior, create the table/model and low-level storage helpers.

### Files to change

- `packages/n3tx-core/src/n3tx_core/models/relationships.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`
- `packages/n3tx-core/src/n3tx_core/app.py`
- `packages/n3tx-core/src/n3tx_core/utils/registrar.py` only if hidden framework registration needs metadata

### Add `RelationshipEdge`

Signature/class shape:

```python
class RelationshipEdge(ProtoModel):
    __tablename__ = "n3tx_relationship_edges"
    __storable__ = True
    __hidden__ = True

    owner_type: str
    owner_id: int
    field_name: str
    target_type: str
    target_id: int
    relation_kind: str
    position: int | None = None
    metadata: dict = Field(default={})
```

Implementation note:

- `ProtoModel` is defined in `proto_model.py`, which imports relationship helpers in places. Avoid circular import by importing `ProtoModel` lazily at bottom or putting `RelationshipEdge` in a separate `relationship_edge.py`.
- Recommended to avoid circularity:

```text
packages/n3tx-core/src/n3tx_core/models/relationship_edge.py
```

with:

```python
from pydantic import Field
from n3tx_core.models.proto_model import ProtoModel

class RelationshipEdge(ProtoModel): ...
```

Then re-export from `relationships.py` if needed.

### Add edge table registration during app bootstrap

File: `packages/n3tx-core/src/n3tx_core/app.py`

Add helper:

```python
def _has_edge_relationships(model_classes: list[type]) -> bool:
    """Return True when any model declares relationship_edge-backed specs."""
```

Signature:

```python
def _has_edge_relationships(model_classes: list[type]) -> bool:
```

Logic:

```python
for cls in model_classes:
    for spec in get_relationship_specs(cls).values():
        if spec.storage is RelationshipStorage.RELATIONSHIP_EDGE:
            return True
return False
```

In `N3TXApp.build()` / `create_app()` registration preparation:

- if any edge-backed relationship exists, include `RelationshipEdge` in framework registrations
- mark hidden so schema/nav/UI do not expose it as an app model unless explicitly requested

### Migration changes

File: `sqlite_migration.py`

Add:

```python
def _is_relationship_edge_model(model_class: Type[Any]) -> bool:
    """Return True for the framework RelationshipEdge model."""

def _create_edge_indexes(self, cursor: sqlite3.Cursor, table_name: str) -> None:
    """Create indexes for n3tx_relationship_edges."""
```

Change:

```python
def _create_relationship_indexes(self, cursor: sqlite3.Cursor, model_class: Type[Any]):
```

to call `_create_edge_indexes(...)` when `model_class.__tablename__ == "n3tx_relationship_edges"`.

### Tests

Add to `test_relationship_specs.py` or new `test_relationship_edges.py`:

```python
def test_relationship_edge_table_created_when_bound_relationship_exists(tmp_path): ...
def test_relationship_edge_table_not_created_when_only_ref_relationships_exist(tmp_path): ...
def test_relationship_edge_indexes_created(tmp_path): ...
```

Inspect SQLite with:

```sql
SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='n3tx_relationship_edges'
```

### Acceptance criteria

```bash
python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_edges.py -q
```

---

## Phase 3 — Add Edge Storage Helper Methods

### Why

Keep relationship-edge operations encapsulated in `SQLiteStorage`; do not scatter raw SQL through routes or models.

### Files to change

- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`

### Add methods to `SQLiteStorage`

Required signatures:

```python
def _edge_table_exists(self, conn) -> bool:
    """Return True if n3tx_relationship_edges exists."""

def _split_relationship_data(
    self,
    model_class: Type[Any],
    data: dict,
) -> tuple[dict, dict[str, Any]]:
    """Split scalar DB columns from relationship field payloads."""

def _create_edge(
    self,
    conn,
    *,
    owner_type: str,
    owner_id: int,
    field_name: str,
    target_type: str,
    target_id: int,
    relation_kind: str,
    position: int | None = None,
    metadata: dict | None = None,
) -> None:
    """Insert one relationship edge."""

def _delete_edges(
    self,
    conn,
    *,
    owner_type: str,
    owner_id: int,
    field_name: str | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
) -> None:
    """Delete edges matching supplied filters."""

def _replace_edges_for_field(
    self,
    conn,
    *,
    owner_type: str,
    owner_id: int,
    spec: RelationshipSpec,
    targets: list[tuple[int, int | None]],
) -> None:
    """Replace all edges for one owner field with ordered target ids."""

def _load_edges_for_owners(
    self,
    conn,
    *,
    owner_type: str,
    owner_ids: list[int],
    field_names: list[str] | None = None,
) -> dict[tuple[int, str], list[dict]]:
    """Batch-load edges grouped by (owner_id, field_name)."""

def _resolve_or_create_edge_target(
    self,
    conn,
    *,
    spec: RelationshipSpec,
    value: Any,
) -> int:
    """Return target id, creating a target row for inline dict/model values."""

def _hydrate_edge_relationships(
    self,
    model_class: Type[Any],
    records: list[dict],
    conn,
    *,
    load_default_only: bool = True,
    limit_per_field: int | None = None,
    _visited: set[tuple[str, int]] | None = None,
) -> None:
    """Attach edge-backed relationship values to parent record dicts."""
```

### How `_split_relationship_data` works

Input:

```python
data = {
    "name": "Demo",
    "primary_task": {"title": "Plan"},
    "active": [{"title": "Build"}],
    "owner": "/User/1",
}
```

Output:

```python
scalar_data = {"name": "Demo", "owner": "/User/1"}
relationship_data = {
    "primary_task": {"title": "Plan"},
    "active": [{"title": "Build"}],
}
```

Rules:

- split only `BOUND_ONE`, `BOUND_MANY`, `MANY_TO_MANY` when storage is `RELATIONSHIP_EDGE`
- leave `REF` and `REF_LIST` in scalar data because existing `_normalize_ref_storage_values` handles them
- leave `LEGACY_LISTREF` out of scalar data as current `get_list_fields` already does

### How `_resolve_or_create_edge_target` works

Supported values:

| Input shape | Behavior |
|---|---|
| `{"id": 3}` | link existing target id 3 after verifying exists |
| `{"$id": "http://.../Task/3"}` | parse local id and link existing |
| `"/Task/3"` | parse local id and link existing |
| `Task(id=3, ...)` | link existing id 3 |
| `Task(title="New")` | create target row, return new id |
| `{"title": "New"}` | create target row, return new id for bound relationships |

Do not allow remote refs for edge-backed relationships. If value canonicalizes to distributed ref, raise `ValueError` instructing user to use `Ref[T]` / `list[Ref[T]]`.

### Changed `create(...)`

Current:

```python
def create(self, model_class: Type[Any], data: Dict[str, Any]) -> Any:
```

Keep signature unchanged.

New control flow:

```text
1. Convert Pydantic model to dict if needed.
2. Split edge-backed relationship data from scalar data.
3. Normalize Ref/list[Ref] values in scalar data.
4. Insert parent row using scalar fields only.
5. For each edge-backed relationship payload:
   - bound_one: resolve/create one target, replace owner-field edge
   - bound_many: resolve/create each target, replace owner-field edges with positions
   - many_to_many: link existing targets by default; reject inline create initially unless explicitly allowed
6. Commit once.
7. Re-read created parent via get(...), or instantiate with hydrated values.
```

Important: use one connection and one transaction for parent + targets + edges. If any target create fails, rollback everything.

### Changed `update(...)`

`SQLiteStorage.update` exists below the read window and should keep its public signature. Update it similarly:

```python
def update(self, model_class: Type[Any], id_: int, data: Dict[str, Any]) -> Any:
```

New behavior:

- scalar fields update current table
- omitted relationship fields are unchanged
- relationship fields supplied as `None` clear `BOUND_ONE`
- relationship fields supplied as list replace `BOUND_MANY` / `MANY_TO_MANY` edges for that field
- empty list clears edges

### Changed `get(...)` and `list(...)`

Keep signatures:

```python
def get(self, model_class: Type[Any], id: int, as_dict: bool = False, populate: PopulateSpec = None) -> Any:

def list(self, model_class: Type[Any], sql_filter: tuple = None,
         limit: int = None, offset: int = None, populate: PopulateSpec = None,
         ids: list = None) -> List[Any]:
```

New behavior:

- existing Ref and list[Ref] hydration remains unchanged
- legacy ListRef behavior remains unchanged until compatibility migration
- edge-backed `BOUND_ONE` and `BOUND_MANY` with `load_default=True` hydrate inline by default
- `ManyToMany` does not hydrate inline by default unless explicitly populated or configured later

Default cap:

```python
DEFAULT_EDGE_RELATION_LIMIT = 20
```

Add module constant near top of `sqlite_storage.py`.

For lists over cap:

```json
"active": [ ... first 20 items ... ],
"active_meta": {"total": 42, "limit": 20, "has_more": true}
```

Alternative wrapper may be chosen later. For implementation consistency and frontend ease, use explicit sibling metadata initially to keep `active` a list.

### Tests

Add `packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_edge_storage.py`.

Test cases:

```python
def test_create_parent_with_bound_one_creates_target_and_edge(tmp_path): ...
def test_create_parent_with_bound_many_creates_targets_and_ordered_edges(tmp_path): ...
def test_bound_many_two_fields_same_target_stay_distinct(tmp_path): ...
def test_bound_one_replaces_existing_edge_on_update(tmp_path): ...
def test_bound_many_update_replaces_edges_without_deleting_targets(tmp_path): ...
def test_ref_fields_remain_scalar_refs_not_edges(tmp_path): ...
def test_ref_list_fields_remain_json_refs_not_edges(tmp_path): ...
def test_many_to_many_links_existing_targets_without_inline_create(tmp_path): ...
def test_edge_create_rolls_back_parent_when_target_create_fails(tmp_path): ...
def test_edge_backed_relationship_rejects_distributed_ref(tmp_path): ...
```

### Acceptance criteria

```bash
python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_edge_storage.py -q
python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_sqlite_storage.py -q
```

---

## Phase 4 — Schema Relationship Metadata

### Why

The frontend must not infer relationship behavior from raw JSON Schema alone. The backend should publish relationship semantics explicitly.

### Files to change

- `packages/n3tx-core/src/n3tx_core/models/proto_schema.py`
- `packages/n3tx-core/src/n3tx_core/models/relationships.py`
- tests for schema output

### Add schema stage

In `proto_schema.py`, add a stage before metadata, after `ui`:

```python
def relationships(cls, schema: dict) -> dict:
    """Inject N3TX relationship metadata into field schemas."""
```

Register order:

```python
register_stage('relationships', relationships, after='ui')
```

If modifying stage order is risky, use decorator style if available in the module.

### Schema shape

For `list[T]`:

```json
{
  "properties": {
    "active": {
      "type": "array",
      "items": {"$ref": "#/$defs/Task"},
      "relationship": {
        "kind": "bound_many",
        "target": "Task",
        "field": "active",
        "storage": "relationship_edge",
        "cardinality": "many",
        "load_default": true,
        "ordered": true,
        "routes": {
          "collection": "/Project/{id}/active",
          "item": "/Project/{id}/active/{target_id}"
        }
      }
    }
  }
}
```

For `Ref[T]`:

```json
{
  "relationship": {
    "kind": "ref",
    "target": "User",
    "storage": "ref_column",
    "cardinality": "one",
    "load_default": false
  }
}
```

### Tests

Add schema tests:

```python
def test_schema_marks_bound_one_relationship(): ...
def test_schema_marks_bound_many_relationship_routes(): ...
def test_schema_marks_ref_and_ref_list_relationships(): ...
def test_schema_marks_many_to_many_without_load_default(): ...
def test_schema_preserves_defs_for_bound_models(): ...
```

### Acceptance criteria

```bash
python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_schema.py -q
```

---

## Phase 5 — Field-Qualified Direct Routes

### Why

Class-only nested routes cannot represent two fields to the same target. Field-qualified routes are canonical.

### Files to change

- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`

### Add route factories

Required signatures:

```python
def make_relation_list(owner_class, spec: RelationshipSpec):
    """Return FastAPI handler for GET /Owner/{id}/{field}."""

def make_relation_create(owner_class, spec: RelationshipSpec):
    """Return FastAPI handler for POST /Owner/{id}/{field}."""

def make_relation_get(owner_class, spec: RelationshipSpec):
    """Return FastAPI handler for GET /Owner/{id}/{field}/{target_id}."""

def make_relation_update(owner_class, spec: RelationshipSpec):
    """Return FastAPI handler for PUT /Owner/{id}/{field}/{target_id}."""

def make_relation_delete(owner_class, spec: RelationshipSpec):
    """Return FastAPI handler for DELETE /Owner/{id}/{field}/{target_id}."""
```

Handler shapes:

```python
async def relation_list(
    request: Request,
    owner_id: int,
    limit: int = Query(default=None, ge=1, le=100),
    offset: int = Query(default=None, ge=0),
    populate: str = Query(default=None),
    depth: int = Query(default=None, ge=0, le=3),
): ...
```

```python
async def relation_create(
    request: Request,
    owner_id: int,
    data: dict = Body(default={}),
): ...
```

```python
async def relation_get(request: Request, owner_id: int, target_id: int): ...
async def relation_update(request: Request, owner_id: int, target_id: int, data: dict = Body(default={})): ...
async def relation_delete(request: Request, owner_id: int, target_id: int): ...
```

Route paths:

```python
base = f"/{owner_class.__name__}/{{owner_id:int}}/{spec.field_name}"
router.get(base, tags=[tag])(make_relation_list(owner_class, spec))
router.post(base, tags=[tag], status_code=201)(make_relation_create(owner_class, spec))
router.get(f"{base}/{{target_id:int}}", tags=[tag])(make_relation_get(owner_class, spec))
router.put(f"{base}/{{target_id:int}}", tags=[tag])(make_relation_update(owner_class, spec))
router.delete(f"{base}/{{target_id:int}}", tags=[tag])(make_relation_delete(owner_class, spec))
```

### Authorization behavior

For relation list:

1. authorize parent read
2. authorize target read for each returned target, or use target SQL filter if available

For relation create/link:

1. authorize parent update for field modification
2. if creating target, authorize target create
3. if linking existing target, authorize target read/link policy; for now target read + parent update is sufficient

For relation delete/unlink:

1. authorize parent update
2. delete edge only by default; do not delete target unless future ownership policy says so

### Storage helper needed

Add to `SQLiteStorage`:

```python
def list_relation(
    self,
    owner_class: Type[Any],
    owner_id: int,
    spec: RelationshipSpec,
    *,
    limit: int | None = None,
    offset: int | None = None,
    populate: PopulateSpec | None = None,
) -> dict:
    """Return related targets for one owner field with pagination metadata."""

def link_relation_target(
    self,
    owner_class: Type[Any],
    owner_id: int,
    spec: RelationshipSpec,
    value: Any,
    *,
    position: int | None = None,
) -> Any:
    """Create/link one target and return the target instance."""

def unlink_relation_target(
    self,
    owner_class: Type[Any],
    owner_id: int,
    spec: RelationshipSpec,
    target_id: int,
) -> None:
    """Remove one relationship edge without deleting target."""
```

### Compatibility routes

Keep existing generated join routes as-is:

- `/products/{parent_id}/comments`
- `/Product/{parent_id}/Comment`
- `/ProductComment`

Add field routes in addition. Do not remove current routes in this phase.

### Tests

Add direct route tests:

```python
def test_field_route_lists_bound_many_targets(): ...
def test_field_route_creates_inline_target_and_edge(): ...
def test_field_route_links_existing_target_by_ref(): ...
def test_field_route_unlinks_without_deleting_target(): ...
def test_two_same_target_field_routes_are_distinct(): ...
def test_class_only_route_skipped_or_not_registered_when_ambiguous(): ...
def test_many_to_many_field_route_links_existing_target(): ...
```

### Acceptance criteria

```bash
python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_routes.py -q
python3 -m pytest examples/core/tests/test_comments_crud.py -q
```

---

## Phase 6 — Actor Route Parity

### Why

Level 1/2 direct routes and Level 3 actor routes must remain behaviorally aligned.

### Files to change

- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- possibly `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`

### Required changes

Mirror direct field-qualified routes in actor routing:

```python
def _register_relationship_routes(router, adapter, model_class, tag): ...
```

or integrate into existing `_register_crud_routes()` / `create_api_routes()`.

Handler behavior:

- route HTTP to TX for owner/target operations where possible
- use storage relation helpers for edge operations if actor CRUD does not expose them yet
- preserve two-tier auth: boundary auth interceptor + model/resource auth

### Tests

Add actor example tests mirroring direct:

```python
def test_actor_field_route_lists_bound_many_targets(): ...
def test_actor_field_route_creates_inline_target_and_edge(): ...
def test_actor_two_same_target_field_routes_are_distinct(): ...
```

### Acceptance criteria

```bash
python3 scripts/test-backend.py --suite actors -- -q
```

---

## Phase 7 — Frontend Runtime and Components

### Why

The frontend currently handles href arrays and populated wrappers. It must understand inline bound objects and relationship schema metadata.

### Files to change

- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list-field.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js`
- frontend tests under `tests/frontend/tests/`

### Required frontend behavior

1. `Ref[T]` fields remain href/ref strings.
2. `list[Ref[T]]` fields remain arrays of href/ref strings.
3. `T` fields may arrive as inline object; register DynamicClass instance and render nested item/summary.
4. `list[T]` fields may arrive as inline object array; register each instance and render list field.
5. Existing ListRef href arrays still work.
6. Existing populated wrappers still normalize.

### Tests

Add/update Vitest tests:

```javascript
it('registers inline bound object fields as instances', async () => {})
it('registers inline bound list objects as instances', async () => {})
it('keeps ref list arrays as refs', async () => {})
it('renders relationship schema field routes', async () => {})
it('keeps legacy ListRef href arrays working', async () => {})
```

### Acceptance criteria

```bash
cd tests/frontend && npx vitest run
```

---

## Phase 8 — Legacy ListRef and Join Model Migration

### Why

Existing apps use `ListRef[T]`, generated join models, and `join_models[(Parent, Child)]`. We must preserve them while moving new defaults to edges.

### Files to change

- `packages/n3tx-core/src/n3tx_core/models/proto_model.py`
- `packages/n3tx-core/src/n3tx_core/utils/registrar.py`
- `packages/n3tx-core/src/n3tx_core/app.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`

### Registry changes

Keep current:

```python
join_models: Dict[tuple[str, str], Type[Any]] = {}
```

Add field-qualified registry:

```python
relationship_models: Dict[tuple[str, str, str], Type[Any]] = {}
```

Key:

```text
(owner_name, field_name, target_name)
```

Change `RegistrationResult`:

```python
@dataclass
class RegistrationResult:
    model_class: Type[Any]
    tablename: str
    storage: Optional[StorageInterface]
    is_storable: bool
    is_join: bool
    join_key: Optional[Tuple[str, str]]
    relationship_key: Optional[Tuple[str, str, str]] = None
```

Change `prepare_model(...)` to set relationship key when join metadata includes `__tagname__`:

```python
if is_join:
    parent = model_class.__owner__
    base = model_class.__bases__[-1]
    field_name = getattr(model_class, '__tagname__', base.__tablename__)
    join_key = (parent.__name__, base.__name__)
    relationship_key = (parent.__name__, field_name, base.__name__)
```

Change `apply_registration(...)`:

```python
if result.relationship_key:
    relationship_models[result.relationship_key] = model
if result.is_join and result.join_key:
    join_models[result.join_key] = model  # legacy last-one-wins behavior retained
```

### `generate_join_model(...)` change

Keep signature but make field name deterministic and required internally:

```python
def generate_join_model(owner_cls: Type[ProtoModel], ref_model: Type[ProtoModel], field_name: str = None): ...
```

Change class name to include field when necessary:

```python
class_name = f"{owner_name}{field_name[:1].upper()}{field_name[1:]}{ref_model.__name__}"
```

Backcompat concern: existing tests may expect `ProductComment`. Keep legacy class name when there is only one field to that target; use field-qualified name only when duplicate same-target fields exist.

### Tests

```python
def test_relationship_models_registry_uses_field_name(): ...
def test_legacy_join_models_registry_still_populated(): ...
def test_duplicate_listref_same_target_generates_distinct_relationship_models(): ...
def test_existing_product_comment_schema_still_exists_for_legacy_example(): ...
```

---

## Phase 9 — Documentation and Examples

### Files to update

- `docs/CORE.md`
- `docs/MODELS.md`
- `docs/JSON_FIELDS.md`
- `packages/n3tx-core/docs/storage.md`
- `packages/n3tx-core/docs/schema-pipeline.md`
- `BACKEND.md`
- examples under `examples/core` and `examples/actors`

### New docs wording

Teach this table prominently:

| Use this | When |
|---|---|
| `Ref[T]` | loose/distributed single pointer |
| `list[Ref[T]]` | loose/distributed pointer list, ordered refs |
| `T` | local bound single object, loaded by default |
| `list[T]` | local bound collection, loaded by default |
| `ManyToMany[T]` | shared membership between independent resources |
| `ListRef[T]` | legacy compatibility for older owned collections |

### Example migration

Old:

```python
class Product(ActorModel):
    comments: ListRef[Comment] = Field(default=[])

app = create_app(models=[Product, Comment], join_models=[(Product, Comment)])
```

New:

```python
class Product(ActorModel):
    comments: list[Comment] = Field(default=[])

app = create_app(models=[Product, Comment])
```

---

## 🧪 Full Test Matrix

### Unit tests — introspection

File: `packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_specs.py`

- classify `Ref[T]`
- classify `list[Ref[T]]`
- classify `T`
- classify `Optional[T]`
- classify `list[T]`
- classify `ManyToMany[T]`
- classify `ListRef[T]`
- distinguish primitive JSON lists
- support duplicate same-target fields
- forward refs for relationship targets

### Unit tests — migration

File: `packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_edge_migration.py`

- edge table created when needed
- edge table hidden but storable
- indexes created
- no edge table for refs-only models
- migration does not drop existing legacy join FK columns
- migration preserves JSON list columns for `list[Ref[T]]`

### Unit tests — storage

File: `packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_edge_storage.py`

- create parent + bound one
- create parent + bound many
- create two fields to same target
- update bound one replacement
- update bound many replacement
- unlink target without delete
- link existing local target
- reject remote ref for bound relationship
- preserve `Ref[T]` scalar behavior
- preserve `list[Ref[T]]` JSON behavior
- many-to-many link existing target
- transaction rollback on failure
- default load cap
- cycle prevention

### Unit tests — schema

File: `packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_schema.py`

- relationship metadata emitted per kind
- field-qualified routes emitted
- `$defs` includes bound targets
- legacy `ListRef` metadata remains compatible
- schema cache invalidation works in tests

### Unit tests — direct routes

File: `packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_routes.py`

- `GET /Project/{id}/active`
- `POST /Project/{id}/active` inline create
- `POST /Project/{id}/active` link existing
- `GET /Project/{id}/active/{target_id}`
- `PUT /Project/{id}/active/{target_id}`
- `DELETE /Project/{id}/active/{target_id}` unlink
- ambiguous class-only route skipped
- legacy nested route still works

### Integration tests — examples/core

Add or update:

- `examples/core/tests/test_edge_relationships.py`
- `examples/core/tests/test_edge_relationship_routes.py`

Coverage:

- app with `active: list[Task]`, `archived: list[Task]`
- parent create with inline children
- parent fetch loads children inline
- field routes distinct
- existing comments/likes ListRef flows still pass

### Integration tests — examples/actors

Add actor parity tests:

- same field route behavior in `routing='actor'`
- same default read shape
- same auth behavior

### Frontend tests

Under `tests/frontend/tests/`:

- dynamic class handles inline object relation
- dynamic class handles inline object list relation
- list-field renders inline objects and legacy refs
- method/count UI supports list and wrapper shapes
- E2E creates parent with local bound children and renders them

### Full commands

```bash
python3 scripts/test-backend.py --suite core -- -q
python3 scripts/test-backend.py --suite actors -- -q
python3 scripts/test-backend.py --short
cd tests/frontend && npx vitest run
```

---

## 🚦 Rollout Strategy

### Release 1 — Internal foundation

- Add `RelationshipSpec`
- Add `RelationshipEdge`
- Add schema metadata
- No behavior change for existing apps

### Release 2 — New syntax enabled

- `T` and `list[T]` become edge-backed local bound relationships
- field-qualified routes available
- examples add new relationship style
- `ListRef` remains supported

### Release 3 — ManyToMany edge backend

- move `ManyToMany[T]` onto edge engine
- preserve generated link table compatibility where existing apps use it

### Release 4 — Deprecation notice

- docs stop teaching explicit `join_models`
- `ListRef[T]` documented as legacy compatibility
- generated join model public schemas/routes retained until a future major version

---

## ⚠️ Risks and Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Inline default loading becomes expensive | `list[T]` may be large | default cap, field routes for pagination, `relations=none` later |
| Breaking existing ListRef apps | production data/routes may depend on joins | compatibility adapter, no silent migration initially |
| Ambiguous auth semantics | edge mutation touches parent and target | require parent update + target read/create checks |
| Circular graphs recurse forever | bound objects may reference parents | visited set keyed by `(type, id)`, depth cap |
| Frontend shape mismatch | existing UI expects href arrays | schema metadata + maintain legacy href support |
| ManyToMany ownership confusion | shared targets should not be deleted | distinct `RelationshipKind` lifecycle policy |
| Transaction partial writes | nested create can fail mid-way | one transaction for parent + targets + edges |

---

## 🔎 Key Open Decisions

1. **Default `list[T]` JSON shape**
   - Recommendation: inline capped plain list plus sibling metadata when capped.
2. **Delete-orphan lifecycle**
   - Recommendation: not by default; add explicit policy later.
3. **RelationshipEdge public visibility**
   - Recommendation: hidden framework model.
4. **Class-only nested routes**
   - Recommendation: keep only when unambiguous; field-qualified routes are canonical.
5. **ManyToMany inline create**
   - Recommendation: reject initially; link existing only unless later configured.

---

## 📌 Critical Implementation Checklist

### Add

- `RelationshipKind`
- `RelationshipStorage`
- `RelationshipSpec`
- `RelationshipEdge`
- `get_relationship_specs(...)`
- edge storage helpers on `SQLiteStorage`
- field-qualified route factories
- relationship schema metadata stage
- field-qualified registry `relationship_models`

### Change

- `get_json_fields(...)` guardrails, if needed
- `SQLiteStorage.create/update/get/list` to handle edge-backed relationships
- `SQLiteMigration._create_relationship_indexes(...)` to index edge table
- `N3TXApp.build()` to register hidden edge table when needed
- `register_routes()` to add field relationship routes
- frontend `NTT.js` to normalize inline objects/lists

### Preserve

- `Ref[T]` scalar behavior
- `list[Ref[T]]` JSON behavior
- `ListRef[T]` legacy behavior
- generated join routes and schemas
- existing example apps/tests until explicitly migrated

### Avoid

- universal `parent_id`
- direct SQLite relationship SQL in routes
- frontend-only inference of relationship semantics
- silent migration of existing join rows into edge table in early phases

---

## ✨ Final Architecture Flow

```text
Python annotation
   |
   v
get_relationship_specs(Model)
   |
   +--> Ref[T] / list[Ref[T]] -------> existing ref/json-ref storage
   |
   +--> T / list[T] -----------------> RelationshipEdge + target rows
   |
   +--> ManyToMany[T] ---------------> RelationshipEdge membership
   |
   +--> ListRef[T] ------------------> legacy join adapter, future edge migration
   |
   v
Schema relationship metadata
   |
   v
Routes + Storage + Frontend all consume same semantics
```

This aligns with N3TX’s philosophy: developers express app structure with natural model annotations; N3TX owns storage, routing, hydration, authorization, and UI propagation.

## Saved Plan

- `.project/plans/unified-relationship-defaults.md`
