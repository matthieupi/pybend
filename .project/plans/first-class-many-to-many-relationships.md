# First-Class Many-to-Many Relationships in N3TX

## ✅ Recommendation

Add many-to-many as a **new first-class relationship primitive** instead of stretching the current generated `ListRef` join-subclass model.

Keep today's `ListRef[T]` behavior as the backward-compatible **owned collection** primitive. Introduce a field-aware relationship descriptor, a relationship registry, link-table storage, and explicit schema metadata so backend, routes, actors, and frontend agree on what add/remove/populate mean.

Use `ManyToMany[T]` for the first implementation while adding a deprecation warning for ambiguous plain `List[Model]` fields. The warning should signal the intended N3TX 0.11 behavior change:

```text
List[Model]      -> shared relationship / many-to-many semantics
ListRef[Model]   -> owned parent-scoped collection semantics
List[str|int|...] -> inline JSON field semantics
```

Recommended public model shape:

```python
from n3tx_core.models.relationships import ManyToMany

class Product(ProtoModel):
    __tablename__ = "products"
    __storable__ = True

    tags: ManyToMany[Tag] = Field(default=[])
```

Optional through-model shape for link metadata:

```python
class ProductTag(ProtoModel):
    __tablename__ = "product_tags"
    __storable__ = True

    product_id: Ref[Product]
    tag_id: Ref[Tag]
    relevance: float = 1.0

class Product(ProtoModel):
    tags: ManyToMany[Tag, ProductTag] = Field(default=[])
```

Through-model/link metadata is **not part of the MVP**. It should be designed as the next layer after the base relation primitive, attach/detach routes, schema contract, and frontend picker semantics are stable.

---

## 🧭 Fit With N3TX Philosophy

This direction aligns well with the current N3TX philosophy and architecture.

| N3TX principle | Fit |
|---|---|
| **The model is the app** | The relationship is declared directly in the Python model field: `tags: ManyToMany[Tag]`. |
| **Backend is authoritative** | Backend owns attach/detach/list semantics and emits them into schema. |
| **Schema as universal contract** | The frontend consumes `properties[field].relationship`; it does not infer relationship behavior from URL guesses. |
| **Zero to working, then customize** | `ManyToMany[Tag]` generates a working link table, routes, schema, and UI behavior without boilerplate. |
| **Transparent, not magical** | A `RelationshipSpec` makes generated link tables and routes inspectable. |
| **Primitives, not opinions** | `ManyToMany[T]` is a reusable primitive, while explicit through models can be added later for richer cases. |
| **Single source of truth** | Relationship metadata is derived once from the model field and reused by storage, routes, schema, actors, and UI. |

The strongest architectural correction is that relationship identity becomes **field-aware**:

```text
(owner_class, field_name)
```

instead of the current join-model identity:

```text
(owner_class, child_class)
```

This resolves ambiguous cases such as:

```python
comments: ListRef[Comment]
reviews: ListRef[Comment]
```

and gives N3TX a durable relationship abstraction that is easier to route, hydrate, authorize, and render.

---

## 🪶 Simplest Useful MVP

The first implementation should intentionally avoid link metadata and through-model envelopes.

MVP public model:

```python
class Product(ProtoModel):
    __tablename__ = "products"
    __storable__ = True

    tags: ManyToMany[Tag] = Field(default=[])
```

Generated link table:

```text
products_tags
  id INTEGER PRIMARY KEY
  product_id INTEGER NOT NULL
  tag_id INTEGER NOT NULL
  UNIQUE(product_id, tag_id)
```

Default response values are **target hrefs**, not link hrefs:

```json
{
  "tags": [
    "http://localhost:5000/Tag/3",
    "http://localhost:5000/Tag/7"
  ]
}
```

Populated response values are **target objects**:

```json
{
  "tags": {
    "data": [
      {"$schema": "/Tag", "$id": "/Tag/3", "id": 3, "name": "AI"}
    ],
    "meta": {"total": 1, "limit": 20, "offset": 0, "has_more": false}
  }
}
```

MVP route contract:

```text
GET    /Product/{id}/tags              list related targets
POST   /Product/{id}/tags              attach existing target or create+attach
DELETE /Product/{id}/tags/{target_id}  detach target, do not delete target
```

Attach existing target:

```json
{"id": 3}
```

Create target then attach:

```json
{"create": {"name": "AI"}}
```

MVP identity rule:

```text
Product.tags contains Tags, not ProductTagLinks.
The link row is an internal implementation detail in v1.
Detach addresses the target id, not the link id.
```

Defer to v2:

- `ManyToMany[Tag, ProductTag]`
- link metadata editing
- `$link` serialization
- raw link-row routes
- relation-specific UI for through-model fields

---

## 📍 Current State

N3TX currently has relationship support, but it is optimized for **parent-scoped child collections**.

| Existing concept | Current behavior | Why it is not true M:N |
|---|---|---|
| `ListRef[T]` | Marks parent field as a collection of `T` | Marker only; does not create normalized relation metadata |
| `List[T]` where `T` is a `BaseModel` | Also detected as collection relationship by `get_list_fields()` | Looks like embedded data but is excluded from JSON storage and expects relationship storage |
| `generate_join_model(Owner, Child)` | Creates `OwnerChild(Child)` with one owner FK | Duplicates child-shaped rows instead of linking existing child rows |
| `join_models` registry | Keyed by `(OwnerClass, ChildClass)` | Cannot model multiple relation fields to same child cleanly |
| Hydration | Returns nested href arrays like `/products/1/comments/5` | The ID is the generated join row, not necessarily child identity |
| Frontend picker | Constructs nested create URL from table names | Cannot know attach vs create-child vs clone semantics |

Core evidence:

- `packages/n3tx-core/src/n3tx_core/models/ref.py` defines `ListRef[T]`.
- `packages/n3tx-core/src/n3tx_core/utils/introspection.py` treats `ListRef[T]` and plain `List[BaseModel]` as list relationship fields.
- `packages/n3tx-core/src/n3tx_core/models/proto_model.py` has `generate_join_model()`.
- `packages/n3tx-core/src/n3tx_core/utils/registrar.py` stores `join_models[(parent, child)]`.
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py` hydrates list relationship fields by querying an effective child/join table.
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py` generates nested routes from `__owner__`, `__parent__`, and `__tagname__`.
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js` and `ntx-list-field.js` infer relationship behavior from schema refs and URLs.

---

## 🗺️ Target Architecture

```text
Model field
  tags: ManyToMany[Tag]
        |
        v
Relationship descriptor
  owner=Product, field=tags, target=Tag, through=ProductTagLink
        |
        +--> schema.relationships.tags metadata
        +--> SQLite link table product_tags(product_id, tag_id)
        +--> relation routes /Product/{id}/tags attach/detach/list
        +--> actor routing parity for attach/detach/list
        +--> frontend picker uses declared endpoints, not guessed URLs
```

Key design decision: **relationship identity is field-aware**. The canonical key should be `(owner_class, field_name)`, not `(owner_class, target_class)`.

---

## 📊 Options Considered

| Option | Summary | Pros | Cons | Recommendation |
|---|---|---|---|---|
| New `ManyToMany` primitive | Add descriptor + generated link model | Clear semantics, backward compatible, schema-driven | More implementation work | ✅ Default for now |
| Future `List[Model]` semantics | In 0.11, make plain `List[Model]` mean shared relation/M:N | Extremely simple user API | Breaking behavior change; needs warning period | ✅ Long-term direction |
| Explicit through model only | Require developers to define link models manually | Simple internals, transparent, good for metadata | More boilerplate; not “zero to working” | ⚠️ Advanced mode |
| Extend `ListRef` | Make `ListRef[T]` support M:N | Minimal API surface | Breaks owned-child semantics; frontend remains ambiguous | ❌ Avoid |
| `List[Ref[T]]` | Represent many refs as a list of single refs | Reads naturally as references | Harder schema/Pydantic behavior; less expressive | ⚠️ Possible sugar later |
| `__relationships__` config | Put relationship metadata in class config | Explicit and configurable | Splits field from meaning; more boilerplate | ⚠️ Override-only |

### Alternative details

#### A. `ManyToMany[T]` now

```python
tags: ManyToMany[Tag] = Field(default=[])
```

Best non-breaking path. It lets N3TX add real M:N behavior now without changing the current implicit `List[Model]` behavior.

#### B. `List[Model]` in 0.11

```python
tags: List[Tag] = Field(default=[])
```

This is the cleanest long-term API because it reads exactly like the domain model. The tradeoff is migration risk: today plain `List[BaseModel]` is treated similarly to `ListRef[T]` for relationship detection. Add warnings before changing semantics.

#### C. Explicit through model

```python
class ProductTag(ProtoModel):
    product_id: Ref[Product]
    tag_id: Ref[Tag]
    relevance: float = 1.0
```

This is transparent and useful when link metadata matters, but it is too much ceremony for the common case. Keep it as the v2 advanced path.

#### D. Extending `ListRef`

Avoid this. `ListRef[T]` currently means parent-scoped collection. Making it sometimes mean shared target relationship would reduce API count but increase semantic ambiguity.

---

## 💻 Proposed Core Code Shape

### 1. Relationship type marker

Add a new core module, likely:

- `packages/n3tx-core/src/n3tx_core/models/relationships.py`

Representative shape:

```python
class _ManyToManyMarker:
    def __init__(self, target_model, through_model=None, *, inverse=None):
        self.target_model = target_model
        self.through_model = through_model
        self.inverse = inverse

class ManyToMany:
    def __class_getitem__(cls, args):
        target, through = (args if isinstance(args, tuple) else (args, None))
        return Annotated[list[Union[target, str]], _ManyToManyMarker(target, through)]
```

Add introspection helpers in `utils/introspection.py`:

```python
def get_many_to_many_fields(model_class) -> list[tuple[str, type, type | None]]:
    ...

def is_many_to_many(annotation) -> bool:
    ...
```

### 2. Relationship registry

Add a field-aware registry in `utils/registrar.py`:

```python
@dataclass(frozen=True)
class RelationshipSpec:
    kind: Literal["many_to_many"]
    owner: type
    field_name: str
    target: type
    through: type
    owner_fk: str
    target_fk: str
    table_name: str
    tagname: str

relationships: dict[tuple[str, str], RelationshipSpec] = {}
```

This should coexist with existing `join_models` during migration, but implementation should avoid creating a second loosely-owned global if possible. Prefer a deep relationship module that discovers specs once during app build and stores them on the owner class and/or registration metadata for routes, schema, storage, and actors to consume.

### 3. Link model generation

Add `generate_many_to_many_model(owner_cls, field_name, target_cls, through_model=None)` in `proto_model.py` or the new `relationships.py` module.

Default generated link model should **not inherit the target model**:

```python
class ProductTagsLink(ProtoModel):
    __tablename__ = "products_tags"
    __storable__ = True
    __relationship__ = RelationshipSpec(...)
    product_id: int
    tag_id: int
```

Add a uniqueness constraint/index on `(product_id, tag_id)` in SQLite migration, plus indexes on both FK columns.

### 4. Storage behavior

Update SQLite storage to treat M:N differently from `ListRef` / `List[BaseModel]`:

```python
# hydrate Product.tags
SELECT tag_id FROM products_tags WHERE product_id IN (...)

# assign canonical child hrefs by default
record["tags"] = [f"{API_URL}/Tag/{tag_id}" for tag_id in tag_ids]
```

Populate should query links, then batch-fetch target rows:

```python
links = select_links(parent_ids)
targets = Tag.list(ids=unique_tag_ids)
record["tags"] = {
    "data": [target.model_response() for target in targets_for_parent],
    "meta": {...},
}
```

If a through model carries extra fields in v2, expose relation-instance metadata with `$link` in runtime responses:

```json
{
  "tags": {
    "data": [
      {
        "$id": "/Tag/3",
        "name": "AI",
        "$link": {
          "$id": "/Product/1/tags/9",
          "relevance": 0.8
        }
      }
    ]
  }
}
```

### 5. Route contract

Add relation routes that preserve existing route grammar while clarifying semantics:

```text
GET    /Product/{id}/tags              list related targets or link envelopes
POST   /Product/{id}/tags              attach existing target or create+attach
DELETE /Product/{id}/tags/{target_id}  detach target, do not delete target
```

Do **not** use `@links` for JSON relation data. In N3TX route grammar, `@` is reserved for view/html routes. If raw link rows become necessary in v2, prefer one of:

```text
GET /Product/{id}/tags/_links
GET /Product/{id}/tags?include=link
GET /ProductTagsLink/_?product_id=1
```

Default recommendation: no raw link-row route in MVP.

Payloads:

```json
// attach existing
{"id": 3}

// create target then attach
{"create": {"name": "AI"}}

// through metadata
{"id": 3, "link": {"relevance": 0.8}}
```

Existing `ListRef` nested routes keep their current behavior.

### 5a. Authorization semantics

Attach/detach must fit N3TX's backend-authoritative authorization model.

Recommended default mapping:

| Relation action | Required authorization |
|---|---|
| `list` | `read` on owner and `read` on target collection/items |
| `attach` existing target | `update` on owner and `read` on target |
| `create+attach` | `update` on owner and `create` on target |
| `detach` | `update` on owner |
| delete target globally | Not part of relation detach; use target model delete route |

Schema should expose relation action access separately or derive it from these model-level rules so the frontend can hide/show picker controls accurately.

### 6. Schema metadata

Add relationship metadata in the schema pipeline after `defs` and before `ui` / `metadata`.

Use `relationship` in JSON Schema documents. Do **not** use `$link` as the schema descriptor; `$link` is reserved for runtime response metadata when link/through data exists.

```json
{
  "properties": {
    "tags": {
      "type": "array",
      "items": {"$ref": "#/$defs/Tag"},
      "relationship": {
        "kind": "many_to_many",
        "field": "tags",
        "target_model": "Tag",
        "target_table": "tags",
        "through_model": "ProductTagsLink",
        "through_table": "products_tags",
        "endpoints": {
          "list": "/Product/{id}/tags",
          "attach": "/Product/{id}/tags",
          "detach": "/Product/{id}/tags/{target_id}"
        },
        "actions": {
          "select_existing": true,
          "create_target": true,
          "unlink": true,
          "delete_target": false
        }
      }
    }
  }
}
```

### 7. Frontend behavior

Update `ntx-list-field` / `ntx-ref-picker` to prefer `def.relationship` over guessed URLs.

Representative change:

```javascript
const rel = this.schema.relationship;
const attachUrl = rel?.endpoints?.attach
  ?.replace('{id}', this.parentId)
  ?? `${config.API_URL}/${this.parentTable}/${this.parentId}/${this.childTable}`;

// Many-to-many attach existing target
data = rel?.kind === 'many_to_many'
  ? { id: entity.id }
  : entity;
```

Removal should call `detach` for M:N and retain existing nested delete for `ListRef` / owned collections.

### 8. Runtime `$link` serialization

`$link` is the preferred runtime response key for relation-instance metadata because N3TX already uses `$schema` and `$id` for transport metadata.

Do not emit `$link` in the MVP. Add it only when through models/link metadata are supported.

Runtime v2 example:

```json
{
  "$schema": "/Tag",
  "$id": "/Tag/3",
  "name": "AI",
  "$link": {
    "$schema": "/ProductTag",
    "$id": "/Product/1/tags/9",
    "relevance": 0.8
  }
}
```

This does not conflict with JSON Schema as long as it is used in runtime entity responses rather than as the relationship schema descriptor. Unknown `$...` keys are also extension keywords in JSON Schema, but `relationship` is clearer for schema documents.

---

## 🧩 Implementation Slices

| Slice | Goal | Area | Verification |
|---|---|---|---|
| 1 | Add marker + introspection only | Backend | Unit tests for `ManyToMany[T]` detection and JSON-field exclusion |
| 2 | Add relationship registry + generated link model | Backend | Registration tests for field-aware keys and duplicate target fields |
| 3 | SQLite link table migration | Backend | Table shape, indexes, no parent-table array column |
| 4 | Hydration + populate | Backend | `Product.tags` hrefs and `populate=tags` target objects |
| 5 | Direct route attach/detach/list | Backend | API tests for attach existing, create+attach, detach-not-delete |
| 6 | Schema relationship metadata | Backend | Schema tests for `properties[field].relationship` and `$defs` |
| 7 | Frontend picker consumes relationship metadata | UI | Vitest for attach/detach URLs and payload semantics |
| 8 | Actor routing parity | Backend/Actors | Level 3 tests mirroring direct API behavior |
| 9 | `List[Model]` warning | Backend | Warning tests for ambiguous plain `List[ProtoModel]` fields |
| 10 | Example app + docs | Full-stack | Core example tags/favorites smoke + docs updates |

---

## 🧪 Verification Plan

Backend:

```bash
python3 scripts/test-backend.py --suite core -- -q
python3 scripts/test-backend.py --suite actors -- -q
python3 scripts/test-backend.py --short
```

Frontend:

```bash
cd tests/frontend && npx vitest run
cd tests/frontend && npm run test:e2e:fast
```

Specific new tests:

- `packages/n3tx-core/src/n3tx_core/tests/unit/test_relationships.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_many_to_many_storage.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_many_to_many_routes.py`
- `tests/frontend/tests/components/ntx-ref-picker.test.js`
- `tests/frontend/tests/components/ntx-list-field.test.js`

---

## ⚠️ Risks and Guardrails

| Risk | Mitigation |
|---|---|
| `ListRef` behavior accidentally changes | Keep `ListRef` and `ManyToMany` separate; add regression tests |
| `List[BaseModel]` ambiguity persists | Add deprecation warning now; signal 0.11 behavior change toward shared relationship semantics |
| Ambiguous identity: link row vs target row | Default field values are target hrefs; expose link metadata only as `$link` in v2 runtime responses |
| Duplicate relation fields to same target | Registry key is `(owner, field_name)` |
| Frontend URL guessing persists | Schema declares attach/detach endpoints; UI falls back only for old schemas |
| SQLite migration lacks constraints | Add unique index `(owner_fk, target_fk)` and FK indexes |
| Actor/direct routing drift | Add direct and actor parity tests |
| Route grammar drift | Do not use `@` for relation JSON routes; reserve `@` for views |

---

## ✨ Next Steps

1. Decide the public API name. `ManyToMany[T]` is the clean default.
2. Implement slices 1-3 as a backend-only tracer bullet.
3. Add route + schema metadata before frontend changes.
4. Update frontend picker only after backend schema contract is stable.
5. Decide whether plain `List[ProtoModel]` should remain an implicit relationship or become an explicit warning path.

## Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/models/ref.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_model.py`
- `packages/n3tx-core/src/n3tx_core/utils/introspection.py`
- `packages/n3tx-core/src/n3tx_core/utils/registrar.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list-field.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js`
