# Full Graph Relationship Migration Plan

## ✅ Executive Recommendation

Migrate N3TX relationships to a **first-class graph edge system** centered on a real `Relationship` model:

```python
class Relationship(ProtoModel):
    """Instances are edges; static/class methods are the relationship store API."""
```

The new architecture treats persisted models as **nodes** and persisted `Relationship` rows as **edges**:

```text
Project/1 --tasks-------> Task/7
Project/1 --tasks-------> Task/8
Project/1 --watchers----> User/2
Task/8    --blocked_by--> Task/7
```

This lets N3TX unify the current relationship surface:

```python
task: Task
task: Ref[Task]
tasks: ListRef[Task]
tasks: list[Task]
tasks: list[Ref[Task]]
tasks: ManyToMany[Task]
```

behind a single relationship substrate while preserving schema-driven development, generated APIs, auth, population, nested routes, and frontend href-array contracts.

The migration should be implemented in phases. First introduce the graph edge store and metadata layer while preserving current public behavior. Then move storage, populate, routes, and bootstrap onto graph-backed relationships. Finally deprecate generated join models and `ListRef` as the primary mental model.

---

## 🎯 Goals

### Product / DX goals

1. Make the common case obvious:

   ```python
   class Project(ActorModel):
       tasks: list[Task] = []
   ```

   should mean “Project owns/scopes Task children”.

2. Preserve explicit escape hatches:

   ```python
   assignee: Ref[User] | None = None      # single identity pointer
   blocked_by: list[Ref[Task]] = []       # ordered pointer list
   watchers: ManyToMany[User] = []        # shared membership
   ```

3. Remove the need for most developers to understand join models, FK hydration, generated link tables, `__owner__`, `__parent__`, or `__tagname__`.

4. Preserve existing APIs during migration so examples, tests, and frontend behavior continue to work.

### Architecture goals

1. Make relationships first-class resources.
2. Stop spreading relationship semantics across storage, schema, route generation, app bootstrap, and frontend response assumptions.
3. Use one canonical relationship metadata layer for all relationship fields.
4. Make relationship storage capable of:
   - owned children
   - ordered pointer arrays
   - many-to-many membership
   - per-edge metadata
   - future distributed refs
   - future graph traversal/query APIs
5. Preserve package boundaries:
   - `n3tx-core` owns the graph model, storage, schema, and direct routes.
   - `n3tx-actors` mirrors route behavior through TX/Matrix.
   - `n3tx-ui` remains schema-driven and consumes the same response shapes.

---

## 🚫 Non-Goals

1. Do not rewrite all relationships in one unsafe pass.
2. Do not remove `ListRef`, generated join models, or `join_models` immediately.
3. Do not force app developers to manually create `Relationship` rows for normal model fields.
4. Do not make frontend duplicate relationship semantics already known by backend schema.
5. Do not make `n3tx-core` depend on actors, UI, agents, or files.

---

## 📍 Current State Summary

### Existing primitives

| Declaration | Current meaning | Storage | Public behavior |
|---|---|---|---|
| `task: Task` | nested model / FK-like rewrite in storable paths | scalar FK-ish column | object/ref-like behavior |
| `task: Ref[Task]` | single identity pointer | TEXT/int column | href or distributed ref |
| `tasks: ListRef[Task]` | owned local child relationship | child/join table | href arrays, nested routes, populate |
| `tasks: list[Task]` | relationship-like collection detected by introspection | skipped as parent JSON column | similar to relationship field, less explicit |
| `tasks: list[Ref[Task]]` | pointer array | JSON TEXT | ref array, optional populate |
| `tasks: ManyToMany[Task]` | shared association | generated link model/table | early bootstrap/index support |

### Current key implementation files

| Concern | Current file |
|---|---|
| `Ref`, `ListRef` | `packages/n3tx-core/src/n3tx_core/models/ref.py` |
| `ManyToMany` metadata | `packages/n3tx-core/src/n3tx_core/models/relationships.py` |
| Join model generation | `packages/n3tx-core/src/n3tx_core/models/proto_model.py` |
| Relationship introspection | `packages/n3tx-core/src/n3tx_core/utils/introspection.py` |
| Registration globals | `packages/n3tx-core/src/n3tx_core/utils/registrar.py` |
| App bootstrap | `packages/n3tx-core/src/n3tx_core/app.py` |
| SQLite read/write/populate | `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py` |
| SQLite migrations | `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py` |
| Direct routes | `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py` |
| Actor routes | `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` |
| Response `$id`/populate overlay | `packages/n3tx-core/src/n3tx_core/models/proto_dump.py` |

### Current coupling to remove over time

- `generate_join_model()` creates generated subclasses such as `ProductComment`.
- Generated models carry relationship metadata via `__owner__`, `__parent__`, `__tagname__`.
- `routes_fastapi.py` discovers nested routes by looking for generated models.
- `sqlite_storage.py` discovers effective child table via `owner.__fk_models__`.
- `proto_dump.instance_url()` special-cases join models for parent-scoped `$id`.
- Examples and tests directly read `join_models[(Parent, Child)]` for likes/favorites.

---

## 🏗️ Target Architecture

```text
+------------------------+
| Model field annotation |
| tasks: list[Task]      |
+-----------+------------+
            |
            v
+------------------------+
| RelationshipField      |
| owner/field/target     |
+-----------+------------+
            |
            v
+------------------------+
| Relationship edge rows |
| source -> target       |
+-----------+------------+
            |
  +---------+---------+----------------+----------------+
  |                   |                |                |
  v                   v                v                v
schema            storage          routes           frontend
metadata          hydrate/populate  nested CRUD      same href shapes
```

### Conceptual model

```text
ProtoModel instance = node
Relationship instance = edge
RelationshipField = declaration metadata inferred from model fields
```

### Public type semantics

| Type | Meaning | Relationship kind | Stored as |
|---|---|---|---|
| `Ref[T]` | single identity pointer | scalar ref | existing field column |
| `list[T]` | owned child collection | `owned` | graph edges |
| `ListRef[T]` | legacy owned child collection | `owned` | graph edges |
| `list[Ref[T]]` | pointer/reference list | `ref_list` | graph edges, compatibility JSON optional during migration |
| `ManyToMany[T]` | shared membership | `many_to_many` | graph edges |

---

## 🧩 New Core Model: `Relationship`

### File to add

```text
packages/n3tx-core/src/n3tx_core/models/relationship.py
```

### Public exports to update

Update:

```text
packages/n3tx-core/src/n3tx_core/models/__init__.py
packages/n3tx-core/src/n3tx_core/__init__.py
packages/n3tx/src/n3tx/__init__.py  # if meta-package re-exports core symbols
```

Export:

```python
from n3tx_core.models.relationship import Relationship, RelationshipKind
```

### Class contract

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from n3tx_core.models.proto_model import ProtoModel


RelationshipKind = Literal[
    "owned",
    "ref_list",
    "many_to_many",
    "generic",
]


class Relationship(ProtoModel):
    """Graph edge between two N3TX model identities.

    Instances are persisted edges.
    Static methods are the framework's relationship store API.
    """

    __tablename__ = "relationships"
    __storable__ = True
    __abstract__ = False

    source_ref: str = Field(description="Source identity, e.g. /Project/1")
    field_name: str = Field(description="Relationship field on source model")
    target_ref: str = Field(description="Target identity, e.g. /Task/7")
    kind: RelationshipKind = Field(default="generic")

    source_type: str = Field(default="")
    source_id: int | None = Field(default=None)
    target_type: str = Field(default="")
    target_id: int | None = Field(default=None)

    position: int | None = Field(default=None)
    metadata: dict = Field(default={})

    @staticmethod
    def ref_for(model_or_cls: Any, id: int | str | None = None) -> str:
        """Return local class-name identity path for a model instance or class/id."""
        ...

    @staticmethod
    def parse_ref(ref: str) -> tuple[str | None, str, str]:
        """Parse local or distributed ref into (service, class_name, id)."""
        ...

    @staticmethod
    def normalize_ref(value: Any, *, target_cls: type | None = None) -> str:
        """Return canonical edge ref string for local/distributed values."""
        ...

    @staticmethod
    def edge_key(source_ref: str, field_name: str, target_ref: str) -> tuple[str, str, str]:
        """Return unique edge key tuple."""
        ...

    @staticmethod
    def create_edge(
        source: Any,
        field_name: str,
        target: Any,
        *,
        kind: RelationshipKind = "generic",
        position: int | None = None,
        metadata: dict | None = None,
    ) -> "Relationship":
        """Create or return an edge from source.field_name to target."""
        ...

    @staticmethod
    def set_edges(
        source: Any,
        field_name: str,
        targets: list[Any],
        *,
        kind: RelationshipKind = "generic",
        replace: bool = True,
    ) -> list["Relationship"]:
        """Set ordered target edge list for source.field_name."""
        ...

    @staticmethod
    def append_edge(
        source: Any,
        field_name: str,
        target: Any,
        *,
        kind: RelationshipKind = "generic",
        metadata: dict | None = None,
    ) -> "Relationship":
        """Append target edge at the next position."""
        ...

    @staticmethod
    def remove_edge(source: Any, field_name: str, target: Any) -> bool:
        """Delete one edge. Return True if an edge was removed."""
        ...

    @staticmethod
    def clear_edges(source: Any, field_name: str) -> int:
        """Delete all edges for source.field_name. Return deleted count."""
        ...

    @staticmethod
    def list_edges(
        source: Any,
        field_name: str | None = None,
        *,
        kind: RelationshipKind | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list["Relationship"] | dict:
        """List edges for a source, optionally filtered by field/kind."""
        ...

    @staticmethod
    def target_refs(source: Any, field_name: str) -> list[str]:
        """Return ordered target refs for source.field_name."""
        ...

    @staticmethod
    def populate_targets(
        source: Any,
        field_name: str,
        *,
        target_cls: type,
        limit: int | None = None,
        offset: int | None = None,
        populate=None,
    ) -> dict:
        """Resolve target refs into serialized target objects with metadata."""
        ...
```

### Required implementation notes

- `Relationship` must be a normal `ProtoModel` so it receives schema, storage, CRUD, and optional actor behavior later.
- Static methods must use `Relationship.storage` rather than importing SQLite directly.
- Static methods must be safe before app bootstrap only when `Relationship.storage` is configured; otherwise raise a clear `RuntimeError`.
- `normalize_ref()` should reuse `n3tx_core.models.ref` helpers, not duplicate parsing logic.
- Local edge refs should use class-name paths (`/Project/1`), not table-name paths.
- `source_type`, `source_id`, `target_type`, and `target_id` are denormalized index columns for efficient local queries.
- Remote/distributed refs may leave `target_id=None` but still set `target_type` if parseable.

---

## 🗄️ Relationship Table Schema

### SQLite table

```sql
CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_ref TEXT NOT NULL,
    field_name TEXT NOT NULL,
    target_ref TEXT NOT NULL,
    kind TEXT DEFAULT 'generic',
    source_type TEXT DEFAULT '',
    source_id INTEGER DEFAULT NULL,
    target_type TEXT DEFAULT '',
    target_id INTEGER DEFAULT NULL,
    position INTEGER DEFAULT NULL,
    metadata TEXT DEFAULT '{}'
);
```

### Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_relationships_source_field
ON relationships (source_ref, field_name);

CREATE INDEX IF NOT EXISTS idx_relationships_target
ON relationships (target_ref);

CREATE INDEX IF NOT EXISTS idx_relationships_source_type_id_field
ON relationships (source_type, source_id, field_name);

CREATE INDEX IF NOT EXISTS idx_relationships_target_type_id
ON relationships (target_type, target_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_relationships_unique_edge
ON relationships (source_ref, field_name, target_ref);
```

### Migration file changes

Modify:

```text
packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py
```

Add methods:

```python
def create_relationship_table(self) -> None:
    ...

def migrate_relationship_table(self) -> None:
    ...

def _create_graph_relationship_indexes(self, cursor: sqlite3.Cursor) -> None:
    ...
```

Call `create_relationship_table()` from `SQLiteStorage.__init__()` or app bootstrap before registering models that may persist edges.

---

## 🧠 Relationship Metadata Layer

The current file `models/relationships.py` already defines a dataclass named `Relationship` for ManyToMany metadata. That name must be freed for the real edge model.

### File to modify

```text
packages/n3tx-core/src/n3tx_core/models/relationships.py
```

### Rename metadata dataclass

Current:

```python
@dataclass(frozen=True)
class Relationship:
    kind: Literal['many_to_many']
    owner: type
    field_name: str
    target: type
    ...
```

Replace with:

```python
from dataclasses import dataclass
from typing import Literal


RelationshipFieldKind = Literal[
    "owned",
    "ref_list",
    "many_to_many",
]


@dataclass(frozen=True)
class RelationshipField:
    """Model-field relationship declaration metadata.

    This is metadata about a model field, not a persisted edge.
    Persisted edges are `n3tx_core.models.relationship.Relationship` instances.
    """

    kind: RelationshipFieldKind
    owner: type
    field_name: str
    target: type
    storage: Literal["graph"] = "graph"
    through: type | None = None
    cascade_delete: bool = False
    ordered: bool = True
    legacy_field_type: str | None = None
```

### Helper functions to add

```python
def ensure_owner_relationship_fields(owner_cls: type) -> dict[str, RelationshipField]:
    ...

def relationship_field_for(
    owner_cls: type,
    field_name: str,
    target_cls: type,
    *,
    kind: RelationshipFieldKind,
    through: type | None = None,
    legacy_field_type: str | None = None,
) -> RelationshipField:
    ...

def get_relationship_fields(owner_cls: type) -> dict[str, RelationshipField]:
    ...

def get_owned_relationship_fields(owner_cls: type) -> list[RelationshipField]:
    ...

def get_ref_list_relationship_fields(owner_cls: type) -> list[RelationshipField]:
    ...

def get_many_to_many_relationship_fields(owner_cls: type) -> list[RelationshipField]:
    ...
```

### ManyToMany generation update

Current `generate_relationship_model()` creates link models. In the graph target state:

- keep it temporarily for compatibility
- update it to attach `RelationshipField` metadata instead of metadata class `Relationship`
- eventually stop generating link models for new `ManyToMany` fields unless compatibility mode is enabled

---

## 🔎 Introspection Changes

### File to modify

```text
packages/n3tx-core/src/n3tx_core/utils/introspection.py
```

### Add helpers

```python
def get_model_list_fields(model_class: Type[Any]) -> list[tuple[str, Type]]:
    """Return plain list[ProtoModel] / list[BaseModel] relationship fields."""
    ...

def get_listref_fields(model_class: Type[Any]) -> list[tuple[str, Type]]:
    """Return ListRef[T] relationship fields."""
    ...

def get_relationship_field_specs(model_class: Type[Any]) -> dict[str, RelationshipField]:
    """Return all graph relationship field metadata for a model class."""
    ...
```

### Preserve compatibility helpers

Keep these public/internal helpers working:

```python
get_list_fields(model_class)
get_ref_list_fields(model_class)
get_many_to_many_fields(model_class)
get_json_fields(model_class)
```

But route future storage/schema logic through `get_relationship_field_specs()`.

### Detection rules

```text
list[ProtoModel subclass]       -> RelationshipField(kind="owned")
ListRef[ProtoModel subclass]    -> RelationshipField(kind="owned", legacy_field_type="ListRef")
list[Ref[ProtoModel subclass]]  -> RelationshipField(kind="ref_list")
ManyToMany[ProtoModel subclass] -> RelationshipField(kind="many_to_many")
list[str/int/bool/etc.]         -> JSON field
dict                            -> JSON field
```

---

## 💾 Storage Changes

### File to modify

```text
packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py
```

### New helper signatures

```python
def _extract_relationship_values(model_class: type, data: dict) -> dict[str, list]:
    ...

def _strip_relationship_fields(model_class: type, data: dict) -> dict:
    ...

def _relationship_source_ref(model_class: type, id_: int) -> str:
    ...

def _public_relationship_href(source_cls: type, source_id: int, field_name: str, target_ref: str) -> str:
    ...

def _batch_hydrate_relationship_fields(conn, model_class: type, records: list[dict]) -> None:
    ...

def _persist_relationship_values(model_class: type, instance: Any, values: dict[str, list]) -> None:
    ...
```

### Modify `SQLiteStorage.__init__`

Add relationship table creation:

```python
def __init__(self, database: str = 'database.db', pool_size: int = 4, reference_resolver=None):
    ...
    self._migration = SQLiteMigration(database=database)
    self._migration.create_relationship_table()
```

### Modify `SQLiteStorage.create`

Current behavior:

- strips collection fields
- inserts scalar columns
- returns model instance

Target behavior:

```python
def create(self, model_class: Type[Any], data: Dict[str, Any]) -> Any:
    data_dict = _normalize_input(data)
    relationship_values = _extract_relationship_values(model_class, data_dict)
    _strip_relationship_fields(model_class, data_dict)
    _normalize_ref_storage_values(model_class, data_dict)

    created = _insert_scalar_row(model_class, data_dict)

    _persist_relationship_values(model_class, created, relationship_values)

    return self.get(model_class, created.id)
```

Important semantics:

- Relationship fields supplied on create produce edge rows.
- Relationship fields omitted on create produce no edges.
- Owned child create through nested route still creates child then edge.

### Modify `SQLiteStorage.update`

Target behavior:

```python
def update(self, model_class: Type[Any], id_: int, data: Dict[str, Any]):
    data_dict = _normalize_input(data)
    relationship_values = _extract_relationship_values(model_class, data_dict)
    _strip_relationship_fields(model_class, data_dict)

    _update_scalar_row(model_class, id_, data_dict)

    instance = self.get(model_class, id_)
    for field_name, targets in relationship_values.items():
        Relationship.set_edges(instance, field_name, targets, kind=kind_for(field_name))

    return self.get(model_class, id_)
```

Important semantics:

- Relationship field absent means “leave edges unchanged”.
- Relationship field present as `[]` means “clear all edges for this field”.

### Modify `SQLiteStorage.get`

Replace ListRef FK hydration:

```python
for field_name, child_class in get_list_fields(model_class):
    SELECT id FROM child_table WHERE fk_col = ?
```

with graph hydration:

```python
for field_name, rel in get_relationship_field_specs(model_class).items():
    refs = Relationship.target_refs(source_ref, field_name)
    record[field_name] = [
        _public_relationship_href(model_class, id, field_name, ref)
        for ref in refs
    ]
```

For `ref_list`, public field values can remain target public refs instead of nested parent-scoped hrefs if preserving current `list[Ref[T]]` behavior is required. The plan recommends:

| Relationship kind | Hydrated field response |
|---|---|
| `owned` | parent-scoped hrefs: `/projects/1/tasks/7` |
| `many_to_many` | target hrefs or parent-scoped hrefs; choose parent-scoped for route consistency |
| `ref_list` | target refs: `/Task/7`, `n3tx://remote/Task/9` |

### Modify `SQLiteStorage.list`

Use batched graph hydration:

```sql
SELECT source_id, field_name, target_ref
FROM relationships
WHERE source_type = ?
  AND source_id IN (?, ?, ?)
ORDER BY position ASC, id ASC
```

Populate each record’s relationship fields from grouped results.

### Modify `_populate_fields`

Replace the ListRef-specific block with relationship-field population.

New helper:

```python
def _populate_relationship_field(
    self,
    model_class,
    instances,
    relationship: RelationshipField,
    populate,
    conn,
    _visited=None,
) -> None:
    ...
```

Output shape for `owned` and `many_to_many`:

```json
{
  "data": [{ "$id": "http://localhost:5000/Project/1/Task/7" }],
  "meta": {
    "total": 1,
    "limit": 20,
    "offset": 0,
    "has_more": false
  }
}
```

Output shape for `ref_list`:

```json
{
  "data": [{ "$id": "http://localhost:5000/Task/7" }],
  "refs": ["http://localhost:5000/Task/7"],
  "errors": []
}
```

---

## 🛣️ Direct Route Changes

### File to modify

```text
packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py
```

### Add route factory helpers

```python
def make_create_related_instance(parent_cls: type, relationship: RelationshipField):
    ...

def make_list_related_instances(parent_cls: type, relationship: RelationshipField):
    ...

def make_get_related_instance(parent_cls: type, relationship: RelationshipField):
    ...

def make_update_related_instance(parent_cls: type, relationship: RelationshipField):
    ...

def make_delete_related_instance(parent_cls: type, relationship: RelationshipField):
    ...

def register_relationship_routes(router: APIRouter, parent_cls: type, relationship: RelationshipField, tag: str):
    ...
```

### Register routes

For a parent model:

```python
class Project(ActorModel):
    tasks: list[Task] = []
```

Register:

```text
POST   /projects/{parent_id}/tasks
GET    /projects/{parent_id}/tasks
GET    /projects/{parent_id}/tasks/{id}
PUT    /projects/{parent_id}/tasks/{id}
DELETE /projects/{parent_id}/tasks/{id}

POST   /Project/{parent_id}/Task
GET    /Project/{parent_id}/Task
GET    /Project/{parent_id}/Task/{id}
PUT    /Project/{parent_id}/Task/{id}
DELETE /Project/{parent_id}/Task/{id}
```

### Delete semantics

| Relationship kind | Nested delete behavior |
|---|---|
| `owned` | delete edge and target row by default |
| `many_to_many` | delete edge only |
| `ref_list` | delete edge only |

Expose cascade policy on metadata:

```python
RelationshipField(cascade_delete=True)   # owned default
RelationshipField(cascade_delete=False)  # many_to_many/ref_list default
```

---

## 🎭 Actor Route Changes

### File to modify

```text
packages/n3tx-actors/src/n3tx_actors/api/network_api.py
```

### Add helpers

```python
def _register_relationship_routes(router, api, parent_cls: type, relationship: RelationshipField):
    ...

async def _relationship_create_via_tx(api, parent_cls, relationship, parent_id, data, user):
    ...

async def _relationship_delete_via_tx(api, parent_cls, relationship, parent_id, child_id, user):
    ...
```

### Actor flow

Nested create:

```text
HTTP POST /Project/1/Task
  -> TX create target Task
  -> Relationship.append_edge(Project/1, "tasks", Task/7)
  -> return Task response with parent-scoped $id
```

Nested delete:

```text
HTTP DELETE /Project/1/Task/7
  -> Relationship.remove_edge(Project/1, "tasks", Task/7)
  -> if owned cascade: TX delete target Task/7
```

---

## 📜 Schema Changes

### Files to modify

```text
packages/n3tx-core/src/n3tx_core/models/proto_schema.py
packages/n3tx-core/src/n3tx_core/utils/introspection.py
```

### Add relationship metadata in field schema

For:

```python
class Project(ActorModel):
    tasks: list[Task] = []
```

Schema should include:

```json
{
  "properties": {
    "tasks": {
      "type": "array",
      "items": { "$ref": "#/$defs/Task" },
      "relationship": {
        "kind": "owned",
        "storage": "graph",
        "target": "Task",
        "field": "tasks",
        "ordered": true,
        "cascade_delete": true,
        "routes": {
          "list": "/Project/{id}/Task",
          "create": "/Project/{id}/Task",
          "item": "/Project/{id}/Task/{child_id}"
        }
      }
    }
  }
}
```

Add helper:

```python
def relationship_schema_for_field(owner_cls: type, relationship: RelationshipField) -> dict:
    ...
```

---

## 📦 Dump / Response Changes

### File to modify

```text
packages/n3tx-core/src/n3tx_core/models/proto_dump.py
```

### Add relationship context support

Current join models special-case `$id` via `__owner__`.

Target:

```python
def run_pipeline(instance, **kwargs) -> dict:
    ...

def base(instance, **kwargs) -> dict:
    ...

def instance_url(instance, d: dict, *, relationship_context: dict | None = None) -> dict:
    ...
```

But because current pipeline stage signature is `(instance, d)`, prefer attaching context to the instance before serialization:

```python
instance.__dict__["_relationship_context"] = {
    "source_cls": Project,
    "source_id": 1,
    "field_name": "tasks",
}
```

Then `instance_url()` checks:

```python
ctx = instance.__dict__.get("_relationship_context")
if ctx:
    d["$id"] = f"{config.API_URL}/{ctx['source_cls'].__name__}/{ctx['source_id']}/{cls.__name__}/{instance.id}"
```

Long-term cleaner API:

```python
def model_response(self, *, relationship_context: dict | None = None, **kwargs) -> dict:
    ...
```

---

## 🚀 App Bootstrap Changes

### File to modify

```text
packages/n3tx-core/src/n3tx_core/app.py
```

### Required changes

1. Always register `Relationship` when any registered model declares graph relationship fields.
2. Preserve explicit `join_models=[...]` as compatibility.
3. Stop requiring explicit `.join(parent, child)` for new `list[Child]` relationships.

Add helper:

```python
def _uses_graph_relationships(model_classes: list[type]) -> bool:
    ...

def _relationship_infrastructure_models(model_classes: list[type]) -> list[type]:
    ...
```

Bootstrap flow update:

```python
explicit_model_classes = [model_class for model_class, _ in self._models]

for model_class in _relationship_infrastructure_models(explicit_model_classes):
    preparations.append(prepare_model(model_class, storage=self._storage))
```

---

## 🧹 Removals and Deprecations

### Keep during compatibility phase

```text
ListRef
generate_join_model()
join_models registry
explicit create_app(join_models=[...])
generated ProductComment schemas/routes
__owner__ / __parent__ / __tagname__
```

### Deprecate in docs once graph routes are stable

```text
ListRef as primary public spelling
manual join_models registration for common parent-child relationships
generated join classes as a public concept
direct app code access to join_models[(Parent, Child)]
```

### Remove only in later major-compatible cleanup

```text
generate_join_model()
join_models global registry
join collection routes such as /products_comments
schema endpoints such as /ProductComment, if compatibility policy allows
```

---

## 🧪 Test Plan

## Unit Test File 1: Relationship Edge Model

Path:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_model.py
```

### Test method signatures

```python
def test_relationship_ref_for_model_instance(tmp_path): ...
def test_relationship_ref_for_model_class_and_id(tmp_path): ...
def test_relationship_normalize_ref_rejects_target_mismatch(tmp_path): ...
def test_relationship_create_edge_persists_canonical_refs(tmp_path): ...
def test_relationship_set_edges_replaces_existing_edges(tmp_path): ...
def test_relationship_set_edges_without_replace_appends_new_edges(tmp_path): ...
def test_relationship_append_edge_preserves_position_order(tmp_path): ...
def test_relationship_remove_edge_deletes_only_matching_edge(tmp_path): ...
def test_relationship_clear_edges_deletes_field_edges_only(tmp_path): ...
def test_relationship_list_edges_filters_by_source_and_field(tmp_path): ...
def test_relationship_list_edges_filters_by_kind(tmp_path): ...
def test_relationship_target_refs_returns_ordered_refs(tmp_path): ...
def test_relationship_unique_edge_prevents_duplicates(tmp_path): ...
def test_relationship_metadata_round_trips_as_json(tmp_path): ...
```

### Full representative test code

```python
from pydantic import Field

from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.relationship import Relationship
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import register_model, registered_models


class Task(ProtoModel):
    __tablename__ = "tasks"
    __storable__ = True
    title: str = ""


class Project(ProtoModel):
    __tablename__ = "projects"
    __storable__ = True
    name: str = ""


def setup_storage(tmp_path):
    registered_models.clear()
    storage = SQLiteStorage(str(tmp_path / "test.db"))
    register_model(Relationship, storage=storage)
    register_model(Project, storage=storage)
    register_model(Task, storage=storage)
    return storage


def test_relationship_ref_for_model_instance(tmp_path):
    setup_storage(tmp_path)
    project = Project.create({"name": "Graph"})
    assert Relationship.ref_for(project) == f"/Project/{project.id}"


def test_relationship_ref_for_model_class_and_id(tmp_path):
    setup_storage(tmp_path)
    assert Relationship.ref_for(Project, 12) == "/Project/12"


def test_relationship_create_edge_persists_canonical_refs(tmp_path):
    setup_storage(tmp_path)
    project = Project.create({"name": "Graph"})
    task = Task.create({"title": "Ship"})

    edge = Relationship.create_edge(project, "tasks", task, kind="owned")

    assert edge.id is not None
    assert edge.source_ref == f"/Project/{project.id}"
    assert edge.field_name == "tasks"
    assert edge.target_ref == f"/Task/{task.id}"
    assert edge.kind == "owned"
    assert edge.source_type == "Project"
    assert edge.source_id == project.id
    assert edge.target_type == "Task"
    assert edge.target_id == task.id


def test_relationship_set_edges_replaces_existing_edges(tmp_path):
    setup_storage(tmp_path)
    project = Project.create({"name": "Graph"})
    first = Task.create({"title": "One"})
    second = Task.create({"title": "Two"})

    Relationship.set_edges(project, "tasks", [first], kind="owned")
    Relationship.set_edges(project, "tasks", [second], kind="owned")

    refs = Relationship.target_refs(project, "tasks")
    assert refs == [f"/Task/{second.id}"]


def test_relationship_append_edge_preserves_position_order(tmp_path):
    setup_storage(tmp_path)
    project = Project.create({"name": "Graph"})
    first = Task.create({"title": "One"})
    second = Task.create({"title": "Two"})

    Relationship.append_edge(project, "tasks", second, kind="owned")
    Relationship.append_edge(project, "tasks", first, kind="owned")

    refs = Relationship.target_refs(project, "tasks")
    assert refs == [f"/Task/{second.id}", f"/Task/{first.id}"]


def test_relationship_remove_edge_deletes_only_matching_edge(tmp_path):
    setup_storage(tmp_path)
    project = Project.create({"name": "Graph"})
    first = Task.create({"title": "One"})
    second = Task.create({"title": "Two"})

    Relationship.set_edges(project, "tasks", [first, second], kind="owned")
    removed = Relationship.remove_edge(project, "tasks", first)

    assert removed is True
    assert Relationship.target_refs(project, "tasks") == [f"/Task/{second.id}"]


def test_relationship_list_edges_filters_by_source_and_field(tmp_path):
    setup_storage(tmp_path)
    project = Project.create({"name": "Graph"})
    first = Task.create({"title": "One"})
    second = Task.create({"title": "Two"})

    Relationship.append_edge(project, "tasks", first, kind="owned")
    Relationship.append_edge(project, "blocked_by", second, kind="ref_list")

    edges = Relationship.list_edges(project, "tasks")

    assert len(edges) == 1
    assert edges[0].field_name == "tasks"
    assert edges[0].target_ref == f"/Task/{first.id}"


def test_relationship_target_refs_returns_ordered_refs(tmp_path):
    setup_storage(tmp_path)
    project = Project.create({"name": "Graph"})
    first = Task.create({"title": "One"})
    second = Task.create({"title": "Two"})

    Relationship.set_edges(project, "tasks", [first, second], kind="owned")

    assert Relationship.target_refs(project, "tasks") == [
        f"/Task/{first.id}",
        f"/Task/{second.id}",
    ]


def test_relationship_unique_edge_prevents_duplicates(tmp_path):
    setup_storage(tmp_path)
    project = Project.create({"name": "Graph"})
    task = Task.create({"title": "Ship"})

    Relationship.append_edge(project, "tasks", task, kind="owned")
    Relationship.append_edge(project, "tasks", task, kind="owned")

    refs = Relationship.target_refs(project, "tasks")
    assert refs == [f"/Task/{task.id}"]
```

## Unit Test File 2: Relationship Introspection

Path:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_introspection.py
```

### Test method signatures

```python
def test_list_model_detected_as_owned_relationship(): ...
def test_listref_detected_as_owned_relationship(): ...
def test_list_ref_detected_as_ref_list_relationship(): ...
def test_many_to_many_detected_as_many_to_many_relationship(): ...
def test_primitive_list_remains_json_field(): ...
def test_relationship_fields_exclude_json_fields(): ...
def test_optional_list_model_detected_as_owned_relationship(): ...
def test_forward_ref_listref_resolves_to_model_class(): ...
def test_two_fields_to_same_target_keep_distinct_field_names(): ...
```

## Unit Test File 3: SQLite Graph Hydration

Path:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_sqlite_graph_relationships.py
```

### Test method signatures

```python
def test_create_with_list_model_field_creates_edges(tmp_path): ...
def test_update_with_relationship_field_replaces_edges(tmp_path): ...
def test_update_without_relationship_field_preserves_edges(tmp_path): ...
def test_get_hydrates_owned_relationship_as_parent_scoped_hrefs(tmp_path): ...
def test_list_batch_hydrates_relationship_fields(tmp_path): ...
def test_populate_owned_relationship_returns_data_meta(tmp_path): ...
def test_populate_ref_list_relationship_returns_data_refs_errors(tmp_path): ...
def test_relationship_order_preserved_in_get_and_populate(tmp_path): ...
def test_many_to_many_edges_hydrate_membership_field(tmp_path): ...
```

## Integration Test File: Direct Routes

Path:

```text
examples/core/tests/test_graph_relationships.py
```

### Test method signatures

```python
def test_parent_get_returns_relationship_href_array(client, auth_headers): ...
def test_nested_create_creates_child_and_edge(client, auth_headers): ...
def test_nested_list_reads_edges_not_fk_columns(client, auth_headers): ...
def test_nested_read_returns_parent_scoped_id(client, auth_headers): ...
def test_nested_update_updates_child_not_edge(client, auth_headers): ...
def test_populate_owned_relationship_returns_data_meta_wrapper(client, auth_headers): ...
def test_many_to_many_membership_uses_edges(client, auth_headers): ...
def test_ref_list_relationship_preserves_order(client, auth_headers): ...
def test_nested_delete_owned_child_deletes_child_and_edge(client, auth_headers): ...
def test_nested_delete_many_to_many_deletes_edge_only(client, auth_headers): ...
```

## Integration Test File: Actor Routes

Path:

```text
examples/actors/tests/test_graph_relationships.py
```

### Test method signatures

```python
def test_actor_nested_create_creates_child_and_edge(client, auth_headers): ...
def test_actor_nested_list_reads_relationship_edges(client, auth_headers): ...
def test_actor_populate_owned_relationship_returns_data_meta(client, auth_headers): ...
def test_actor_nested_delete_owned_child_cascades(client, auth_headers): ...
def test_actor_many_to_many_delete_removes_edge_only(client, auth_headers): ...
```

## Frontend Tests

Path:

```text
tests/frontend/tests/integration/graph-relationships.test.js
```

### Test method names

```javascript
test('normalizes graph populated relationship wrappers to href arrays', async () => {})
test('renders graph-backed owned relationship list fields', async () => {})
test('updates local href arrays after nested create response', async () => {})
test('keeps ref_list target refs stable after populate', async () => {})
```

---

## 🧭 Implementation Phases

### Phase 1 — Add `Relationship` edge model

Files:

```text
packages/n3tx-core/src/n3tx_core/models/relationship.py
packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py
packages/n3tx-core/src/n3tx_core/__init__.py
```

Deliverables:

- relationship table creation
- indexes
- static edge store methods
- unit tests for edge CRUD/order/uniqueness

### Phase 2 — Add relationship field metadata

Files:

```text
packages/n3tx-core/src/n3tx_core/models/relationships.py
packages/n3tx-core/src/n3tx_core/utils/introspection.py
```

Deliverables:

- `RelationshipField` metadata
- detection for `list[T]`, `ListRef[T]`, `list[Ref[T]]`, `ManyToMany[T]`
- compatibility helpers remain intact

### Phase 3 — Graph-backed storage hydration/populate

Files:

```text
packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py
packages/n3tx-core/src/n3tx_core/models/proto_dump.py
```

Deliverables:

- relationship fields persist edges on create/update
- get/list hydrate from edges
- populate resolves edges into target data
- response shapes remain compatible

### Phase 4 — Graph-backed direct routes

Files:

```text
packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py
```

Deliverables:

- nested routes from `RelationshipField`
- field-name and class-name route compatibility
- cascade semantics by relationship kind

### Phase 5 — Graph-backed actor routes

Files:

```text
packages/n3tx-actors/src/n3tx_actors/api/network_api.py
```

Deliverables:

- actor route parity with direct routes
- TX create/update/delete still authoritative for target resources
- relationship edge methods called from route layer or via actorized `Relationship` later

### Phase 6 — Bootstrap integration

Files:

```text
packages/n3tx-core/src/n3tx_core/app.py
packages/n3tx-core/src/n3tx_core/utils/registrar.py
```

Deliverables:

- auto-register `Relationship` for graph apps
- remove need for explicit `join_models` for `list[Child]`
- preserve compatibility with existing explicit join pairs

### Phase 7 — Docs, examples, deprecations

Files:

```text
docs/CORE.md
docs/MODELS.md
docs/JSON_FIELDS.md
packages/n3tx-core/docs/storage.md
packages/n3tx-core/docs/app-bootstrap.md
BACKEND.md
examples/core/models/*
examples/actors/models/*
```

Deliverables:

- teach `list[Child]` as default owned relationship
- teach `list[Ref[Child]]` as pointer list
- teach `ManyToMany[Child]` as shared membership
- mark `ListRef` and join models as legacy compatibility

---

## ⚠️ Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Breaks existing nested routes | high | keep old generated join routes until graph routes pass parity tests |
| Frontend href shape changes | high | preserve href arrays and `{data, meta}` wrappers |
| Relationship table becomes hot | medium | add source/target indexes; batch hydration queries |
| Edge uniqueness blocks legitimate duplicates | medium | uniqueness is correct for relationship membership; use metadata/position for ordering, not duplicate edges |
| Cascade delete surprises users | high | cascade only for `owned`; edge-only delete for `ref_list` and `many_to_many` |
| Remote refs unresolved | medium | keep target refs canonical; populate returns per-ref errors when resolver missing |
| Existing FK columns linger | low/medium | do not auto-drop; ignore after graph migration |

---

## 🧪 Verification Commands

```bash
python3 scripts/test-backend.py --suite core -- -q
python3 scripts/test-backend.py --suite actors -- -q
python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_model.py -q
python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_relationship_introspection.py -q
python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_sqlite_graph_relationships.py -q
python3 -m pytest examples/core/tests/test_graph_relationships.py -q
python3 -m pytest examples/actors/tests/test_graph_relationships.py -q
cd tests/frontend && npx vitest run
```

---

## ✅ Definition of Done

The migration is complete when:

1. `Relationship` exists as a real storable model and edge store.
2. `list[Child]` relationships work without explicit `join_models` registration.
3. `ListRef[Child]` remains compatible and graph-backed.
4. `list[Ref[Child]]` and `ManyToMany[Child]` are graph-backed.
5. Direct and actor nested routes work from relationship metadata.
6. Populate works from graph edges with current response shapes.
7. Frontend tests pass without duplicating relationship rules client-side.
8. Docs teach the new relationship model and mark join models as legacy.

---

## 📌 Critical Implementation Files

```text
packages/n3tx-core/src/n3tx_core/models/relationship.py
packages/n3tx-core/src/n3tx_core/models/relationships.py
packages/n3tx-core/src/n3tx_core/utils/introspection.py
packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py
packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py
packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py
packages/n3tx-core/src/n3tx_core/models/proto_dump.py
packages/n3tx-core/src/n3tx_core/app.py
packages/n3tx-actors/src/n3tx_actors/api/network_api.py
docs/CORE.md
docs/MODELS.md
packages/n3tx-core/docs/storage.md
BACKEND.md
```
