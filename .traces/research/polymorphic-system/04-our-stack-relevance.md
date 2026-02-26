# Polymorphic Data Systems: Relevance to PyBend's Stack

**Analysis Date:** 2026-02-26
**Scope:** How PyBend's current architecture handles (or would handle) polymorphic types -- models that share a base type but have different specializations
**Audience:** Technical CEO + Engineering Leadership

---

## Executive Summary

PyBend's schema-driven architecture already contains **60-70% of the machinery needed for polymorphic data systems**. The `ProtoModel` inheritance chain, `__init_subclass__()` hook, JSON Schema `$defs`, and the frontend's DynamicClass system provide a foundation that most frameworks lack entirely. However, critical gaps exist in **storage discrimination**, **schema union generation**, and **frontend type dispatch** that would need to be addressed before PyBend can offer first-class polymorphism. This document maps every relevant file and function, identifies what works today, what is missing, and provides a phased implementation roadmap.

---

## Table of Contents

1. [What PyBend Already Provides for Polymorphism](#1-what-pybend-already-provides)
2. [What Is Missing for Full Polymorphism](#2-what-is-missing)
3. [Storage Implications](#3-storage-implications)
4. [Schema Generation Implications](#4-schema-generation-implications)
5. [Frontend Implications](#5-frontend-implications)
6. [Authorization Implications](#6-authorization-implications)
7. [Implementation Roadmap](#7-implementation-roadmap)
8. [Competitive Comparison](#8-competitive-comparison)
9. [Sources](#9-sources)

---

## 1. What PyBend Already Provides

### 1.1 ProtoModel as a Polymorphic Base

PyBend already uses inheritance as its primary model definition pattern. Every application model extends `ProtoModel`, which provides schema generation, serialization, and storable injection.

**File:** `/workspace/src/pybend/core/models/proto_model.py`, lines 44-93

```python
class ProtoModel(PydanticBaseModel):
    __fk_models__: ClassVar[Dict[str, Type]] = {}
    _schema_cache: ClassVar[dict] = {}
    _response_meta_cache: ClassVar[dict] = {}

    id: int = Field(default=0)
    image: str = Field(default='')

    def __init_subclass__(cls, **kwargs):
        __storable__ = getattr(cls, '__storable__', False)
        cls._referenced_models = set()
        if __storable__:
            if not issubclass(cls, StorableMixin):
                cls.__bases__ = (StorableMixin,) + cls.__bases__
                # FK Injection: rewrite fields that are Pydantic models into ForeignKey
                ...
        super().__init_subclass__(**kwargs)
```

**What this means for polymorphism:**

| Capability | Status | Evidence |
|-----------|--------|---------|
| Shared base class with common fields (`id`, `image`) | Already works | `ProtoModel` lines 62-63 |
| Automatic StorableMixin injection for subclasses | Already works | `__init_subclass__()` lines 72-93 |
| Per-subclass `__tablename__` | Already works | Each model sets its own `__tablename__` |
| Per-subclass `__access__` rules | Already works | `Comment` has `OWNER \| ROLE('admin')`, `Product` has none |
| Per-subclass `__ui__` configuration | Already works | Each model has independent UI hints |
| Schema generation per subclass | Already works | `ProtoModel.schema()` lines 199-316 |

**The existing inheritance chain is already polymorphic** in the sense that `Product`, `Comment`, `Like`, and `User` all share a base type (`ProtoModel`) but carry completely different fields, access rules, and methods. What is missing is the ability to **treat them as variants of a single parent type** at the storage, route, and schema level.

### 1.2 The BaseUser Pattern -- Polymorphism in Practice

The `BaseUser` class demonstrates the closest thing to polymorphic inheritance PyBend has today.

**File:** `/workspace/src/pybend/core/models/base_user.py`, lines 26-53

```python
class BaseUser(ProtoModel):
    __storable__: ClassVar[bool] = True
    __abstract__: ClassVar[bool] = True   # <-- Abstract flag
    __owner_field__: ClassVar[str] = 'id'
    __hidden_fields__: ClassVar[set] = {'password_hash'}

    name: str
    email: str
    role: str = Field(default='user')
    password_hash: Optional[str] = Field(default=None, exclude=True)
```

The concrete subclass in `User` inherits all fields, login/register endpoints, and password hashing. This is **single-table inheritance (STI) in embryonic form**: the concrete `User` model adds fields to the same table, and the `__abstract__` flag prevents `BaseUser` from being registered directly.

> **Key Insight:** PyBend already supports the `__abstract__` class variable. This is the seed of a discriminator-based polymorphic system -- abstract base types that are never stored directly, with concrete subtypes that share or extend the base schema.

### 1.3 The `__init_subclass__()` Hook

The `__init_subclass__()` hook in `ProtoModel` (lines 72-93) fires every time a new subclass is defined. This is the ideal extension point for polymorphic registration. Currently, it handles:

1. StorableMixin injection
2. FK field rewriting (Pydantic model fields to `Ref` types)
3. `_referenced_models` initialization

**What it does NOT do (but could):**

- Register subtypes in a class-level registry mapping discriminator values to concrete classes
- Propagate a `__discriminator__` column to the table schema
- Accumulate a union schema of all subtypes for `oneOf`/`anyOf` generation

### 1.4 JSON Schema `$defs` for Nested Types

The schema generation system already handles referenced models via `$defs`.

**File:** `/workspace/src/pybend/core/models/proto_model.py`, lines 222-246

```python
if referenced_models:
    if not '$defs' in schema and referenced_models:
        schema['$defs'] = {}
    for model in referenced_models:
        ref_schema = model.referenced_json_schema()
        ref_methods = model.__pybend_methods_json_signature__()
        defs = ref_schema.pop('$defs', {})
        schema['$defs'] = {**defs, **schema['$defs']} if defs else schema['$defs']
        if 'properties' in ref_schema:
            schema['$defs'][model.__name__] = ref_schema
```

This mechanism already supports a critical polymorphism pattern: **a parent model can reference multiple child types via `$defs`**, and the frontend resolves them independently. The gap is that `$defs` entries are currently only created for *referenced* models (via `ListRef[T]` or `Ref[T]`), not for *subtypes*.

### 1.5 DynamicClass Creation and the Frontend Type Registry

The frontend's `prototype()` function creates a DynamicClass for each model schema. The `NTT.SCHEMA()` handler processes `$defs` to register nested types.

**File:** `/workspace/src/pybend/static/core/NTT.js`, lines 390-426

```javascript
static SCHEMA(data, tx) {
    const addr = data.__name__;
    // Handle $defs (nested schemas) first
    if (data.$defs && typeof data.$defs === 'object') {
        for (const [key, value] of Object.entries(data.$defs)) {
            if (key === addr) continue;
            if (value.type === 'object' && value.properties && !NTT.has(key)) {
                const DC = prototype(key, value, defHref);
                NTT.#prototypes.set(key, DC);
                NTT.#replayWaiting(key, DC);
            }
        }
    }
    // Create DynamicClass for the main model
    const DC = prototype(addr, data, href);
    NTT.#prototypes.set(addr, DC);
}
```

**What this means for polymorphism:**

The frontend already creates separate DynamicClasses for each type it encounters. If a polymorphic base type's schema included all subtypes in `$defs`, **the frontend would automatically register DynamicClasses for every subtype**. The gap is on the dispatch side: once you have a mixed-type collection, how does `ntt-list` know which DynamicClass to use for which entity?

### 1.6 How `ntt-item` Renders -- Uniform, Not Type-Dispatched

**File:** `/workspace/src/pybend/static/components/ntt-item.js`, lines 468-486

```javascript
render() {
    if (!this.schema || !this.value) return;
    const size = this.displayMode;
    const html = (this[size] || this.md).call(this);
    // ...
    this.shadowRoot.innerHTML = `<div class="card${indentClass}" ...>${html}</div>`;
}
```

The `render()` method dispatches by **size** (`xs`, `sm`, `md`, `lg`, `xl`) -- NOT by type. Every entity renders through the same schema-driven path regardless of its model class. This is a strength (zero-config rendering for any model) but also a gap: a polymorphic collection would need the ability to render `Article` differently from `Video` even though both are `Content`.

The `#resolveChildTag()` helper (line 632-638) already resolves component tags by model name:

```javascript
#resolveChildTag(refModel) {
    const defs = this.schema?.$defs || {};
    const fromDefs = defs[refModel]?.ui?.renderer?.item;
    if (fromDefs) return fromDefs;
    const DC = NTT.get(refModel);
    return DC?.schema?.ui?.renderer?.item || 'ntt-item';
}
```

This means if each polymorphic subtype declared its own `ui.renderer.item`, the resolution chain would pick it up. The machinery is present; it just is not wired for polymorphic dispatch on the list level.

---

## 2. What Is Missing for Full Polymorphism

### 2.1 Discriminator Column Support in Storage

**Current state:** `sqlite_storage.py` uses one table per `__tablename__`. There is no concept of a discriminator column that marks which subtype a row belongs to.

**File:** `/workspace/src/pybend/core/storage/sqlite_storage.py`, lines 93-118 (create)

```python
def create(self, model_class: Type[Any], data: Dict[str, Any]) -> Any:
    table_name = _validate_identifier(model_class.__tablename__)
    fields = [f for f in model_class.model_fields.keys()
              if f != 'id' and f not in collection_field_names]
    # ... INSERT INTO {table_name} ...
```

No `_type` column is injected. The `model_class` parameter already carries the concrete type, but the storage layer does not persist this information into the row.

### 2.2 Type-Aware Query Filtering

**Current state:** `list()` in `sqlite_storage.py` queries the entire table. There is no built-in filter for "give me only rows of subtype X from a shared table."

```python
def list(self, model_class, sql_filter=None, limit=None, offset=None, populate=None):
    select_sql = f"SELECT * FROM {table_name}"
    # Only applies sql_filter from authorization -- no type discrimination
```

If `Article` and `Video` shared a `content` table, calling `Article.list()` would return ALL rows -- including Video rows -- because the query is purely table-based.

### 2.3 Schema Generation for `oneOf`/`anyOf` with Discriminator

**Current state:** `ProtoModel.schema()` generates a flat schema per model. It does NOT generate JSON Schema union types (`oneOf`, `anyOf`, `discriminator`).

Pydantic natively supports discriminated unions:

```python
# Pydantic supports this natively
from typing import Annotated, Literal, Union
from pydantic import Discriminator, Tag

class Article(Content):
    type: Literal['article'] = 'article'

class Video(Content):
    type: Literal['video'] = 'video'

# Union type with discriminator
ContentUnion = Annotated[Union[Article, Video], Discriminator('type')]
```

But `ProtoModel.schema()` never calls `model_json_schema()` on a union type. The machinery exists in Pydantic; PyBend simply does not invoke it.

### 2.4 Frontend Rendering Dispatch by Subtype

**Current state:** `ntt-list` stamps `ntt-item` for every entity in the collection (via `createChild()` in `ListElement.js`, line 156):

```javascript
const el = document.createElement(this.childTag);
```

`childTag` resolves to a single tag for the entire list. There is no per-item type inspection to stamp `ntt-article` for one entity and `ntt-video` for another.

### 2.5 Form Generation for Type-Specific Fields

**Current state:** `form.js` generates inputs from `schema.properties`. If all subtypes share the same table, the form would show ALL fields (including Video-specific fields when editing an Article).

```javascript
function getForm(ntt, mode="display", attachedMethods = {}) {
    const schema = ntt.schema;
    const fields = schema.properties || {};
    // Renders ALL properties -- no type-aware filtering
}
```

### 2.6 Route Generation for Polymorphic Endpoints

**Current state:** `routes_fastapi.py` registers routes per `registered_models` entry. Each model gets its own endpoint set.

```python
for model_name, model_class in registered_models.items():
    # Schema route
    router.get(f"/{model_class.__name__}", tags=[tag])(make_get_schema(model_class))
    # CRUD routes
    router.post(endpoint_base, tags=[tag], status_code=201)(make_create_instance(model_class))
    # ...
```

There is no mechanism for a single `/content` endpoint that returns both Articles and Videos, or a `POST /content` that inspects a discriminator field to decide which subclass to instantiate.

---

## 3. Storage Implications

### 3.1 Current Architecture: Table-Per-Model

PyBend uses a strict one-table-per-model mapping:

| Model | Table | Created By |
|-------|-------|-----------|
| `Product` | `products` | `register_model()` -> `storage.create_table(Product)` |
| `Comment` | `comments` | `register_model()` -> `storage.create_table(Comment)` |
| `ProductComment` | `products_comments` | `generate_join_model()` |

The migration system in `sqlite_migration.py` (lines 111-187) creates columns by iterating `model_class.model_fields`. No discriminator column is ever generated.

### 3.2 How Single Table Inheritance (STI) Would Work

STI stores all subtypes in one table with a discriminator column and nullable type-specific fields.

```
                     content table (STI)
+----+------+---------+----------+-----------+----------+----------+
| id | type | title   | body     | video_url | duration | author   |
+----+------+---------+----------+-----------+----------+----------+
|  1 | art  | Hello   | World    | NULL      | NULL     | alice    |
|  2 | vid  | Demo    | NULL     | https://  | 120      | bob      |
+----+------+---------+----------+-----------+----------+----------+
```

**Changes needed in `sqlite_storage.py`:**

1. **`create()`** (line 93): Inject the discriminator value before INSERT.
2. **`list()`** (line 124): Add `WHERE _type = ?` when called with a specific subtype.
3. **`create_table()`** in `sqlite_migration.py` (line 111): Add `_type TEXT NOT NULL` column. Collect columns from ALL registered subtypes for a shared `__tablename__`.

**Estimated complexity:** Medium. The storage layer already handles dynamic column generation from model fields. The main challenge is the **column union** -- collecting fields from all subtypes that share a `__tablename__` and creating nullable columns for type-specific fields.

### 3.3 How Class Table Inheritance (CTI) Would Work

CTI uses a base table for shared fields and child tables for type-specific fields, JOINed on read.

```
    content table (base)        article_content table        video_content table
+----+---------+--------+    +----+------+---------+     +----+-----------+----------+
| id | title   | author |    | id | body | summary |     | id | video_url | duration |
+----+---------+--------+    +----+------+---------+     +----+-----------+----------+
|  1 | Hello   | alice  |    |  1 | ...  | ...     |     |  2 | https://  | 120      |
|  2 | Demo    | bob    |    +----+------+---------+     +----+-----------+----------+
```

**Changes needed in `sqlite_storage.py`:**

1. **`get()`** (line 240): JOIN base + child table on read.
2. **`list()`** (line 124): LEFT JOIN all child tables, or query with discriminator to determine which child table to JOIN.
3. **`create()`** (line 93): INSERT into base table, then INSERT type-specific fields into child table.
4. **`create_table()`**: Create both base and child tables.

**Estimated complexity:** High. CTI requires coordinated multi-table operations for every CRUD action. The connection pool context manager (`_connection()`) would need to handle transactions spanning multiple tables.

### 3.4 Recommendation: STI First

STI is simpler, fits SQLite better (no complex JOINs), and aligns with PyBend's "zero to working" philosophy. CTI can be added later for large-scale deployments where NULL column waste becomes a concern.

---

## 4. Schema Generation Implications

### 4.1 Pydantic's Native Discriminated Union Support

Pydantic v2 has first-class support for discriminated unions:

```python
from pydantic import BaseModel, Discriminator
from typing import Annotated, Literal, Union

class Article(BaseModel):
    type: Literal['article'] = 'article'
    body: str

class Video(BaseModel):
    type: Literal['video'] = 'video'
    video_url: str
    duration: int

ContentType = Annotated[Union[Article, Video], Discriminator('type')]

# This generates JSON Schema with oneOf + discriminator:
# {
#   "oneOf": [
#     {"$ref": "#/$defs/Article"},
#     {"$ref": "#/$defs/Video"}
#   ],
#   "discriminator": {
#     "propertyName": "type",
#     "mapping": {"article": "#/$defs/Article", "video": "#/$defs/Video"}
#   }
# }
```

### 4.2 How `ProtoModel.schema()` Would Need to Change

**File:** `/workspace/src/pybend/core/models/proto_model.py`, lines 199-316

Currently, `schema()` generates a flat schema for a single model. For polymorphism, it would need a new path:

```
# Conceptual change (not a code proposal):
if cls has __polymorphic_subtypes__:
    1. Generate individual schemas for each subtype
    2. Combine into a oneOf/anyOf wrapper
    3. Add discriminator mapping
    4. Include all subtype schemas in $defs
    5. Merge methods from all subtypes
```

The `collect_all_referenced_models()` function (used at line 208) would need to be extended to discover subtypes, not just referenced models.

### 4.3 JSON Schema Discriminator Format

The JSON Schema output would need to follow the discriminated union format:

```json
{
  "$schema": "http://localhost:5000/Schema",
  "$id": "http://localhost:5000/Content",
  "__name__": "Content",
  "__tablename__": "content",
  "oneOf": [
    {"$ref": "#/$defs/Article"},
    {"$ref": "#/$defs/Video"}
  ],
  "discriminator": {
    "propertyName": "_type",
    "mapping": {
      "article": "#/$defs/Article",
      "video": "#/$defs/Video"
    }
  },
  "$defs": {
    "Article": {
      "$id": "http://localhost:5000/Article",
      "properties": { "title": {...}, "body": {...}, "_type": {"const": "article"} },
      "methods": { ... },
      "access": { ... },
      "ui": { ... }
    },
    "Video": {
      "$id": "http://localhost:5000/Video",
      "properties": { "title": {...}, "video_url": {...}, "duration": {...}, "_type": {"const": "video"} },
      "methods": { ... },
      "access": { ... },
      "ui": { ... }
    }
  }
}
```

This format is compatible with the existing `$defs` processing in `NTT.SCHEMA()`.

---

## 5. Frontend Implications

### 5.1 How `prototype()` Would Create Type-Aware DynamicClasses

**File:** `/workspace/src/pybend/static/core/NTT.js`, lines 663-1075

The `SCHEMA()` handler already processes `$defs` and creates separate DynamicClasses for each:

```javascript
// Lines 397-407 -- already handles $defs registration
if (data.$defs && typeof data.$defs === 'object') {
    for (const [key, value] of Object.entries(data.$defs)) {
        if (key === addr) continue;
        if (value.type === 'object' && value.properties && !NTT.has(key)) {
            const DC = prototype(key, value, defHref);
            NTT.#prototypes.set(key, DC);
        }
    }
}
```

**What needs to change:** The main DynamicClass for the polymorphic base would need to carry a `discriminator` property so that when instances arrive with different `_type` values, the correct subtype DynamicClass is resolved.

```
// Conceptual frontend flow for polymorphic READ:
DynamicClass.READ = function(data) {
    for (const entity of data) {
        const typeValue = entity[discriminatorField];     // e.g. entity._type = "article"
        const SubDC = NTT.get(discriminatorMapping[typeValue]);  // e.g. NTT.get("Article")
        // Register instance on SubDC, not on the base DynamicClass
        ...
    }
}
```

### 5.2 How `form.js` Would Show/Hide Type-Specific Fields

**File:** `/workspace/src/pybend/static/generators/form.js`, lines 17-65

The form generator already filters fields based on `ui.display`:

```javascript
const renderableFields = fieldOrder.filter(key => {
    if (def?.ui?.display === false) return false;
    if (mode === 'edit' && def?.ui?.protected) return false;
    if (!permissions.canView(def)) return false;
    return true;
});
```

For polymorphism, fields would need to be filtered by **the subtype schema** rather than the base schema. If the discriminator is known, the form should use the subtype's `properties`, not the union's.

Two approaches:

| Approach | Mechanism | Complexity |
|----------|-----------|-----------|
| **Schema swap** | When `_type` is known, replace `ntt.schema` with the subtype's schema from `$defs` | Low |
| **Conditional rendering** | Annotate each property with `"if": {"_type": "article"}` and filter at render time | Medium |

The schema swap approach aligns better with PyBend's "schema is the contract" philosophy.

### 5.3 How `ntt-list` Would Handle Mixed-Type Collections

**File:** `/workspace/src/pybend/static/components/ListElement.js`, lines 146-161

Currently, `createChild()` stamps a single `childTag` for every entity:

```javascript
createChild(addr) {
    const el = document.createElement(this.childTag);  // Same tag for all
    el.ref = addr;
    el.setAttribute('display', this.childDisplay);
    return el;
}
```

For polymorphic collections, `createChild()` would need to resolve the child tag **per entity**, based on the entity's `_type`:

```
// Conceptual change:
createChild(addr) {
    const instance = NTT.get(addr);
    const typeValue = instance?.value?.[discriminatorField];
    const subSchema = this.schema.$defs?.[discriminatorMapping[typeValue]];
    const tag = subSchema?.ui?.renderer?.item || this.childTag;
    const el = document.createElement(tag);
    ...
}
```

The resolution chain via `#resolveChildTag()` in `ntt-item.js` (lines 632-638) already supports per-model tag resolution. The missing piece is the lookup from entity value to model name.

---

## 6. Authorization Implications

### 6.1 Per-Subtype Access Rules

PyBend's ABAC system already supports per-model access rules:

**File:** `/workspace/src/pybend/core/authorize/rules.py`

```python
class Product(ProtoModel):
    __access__ = {'read': ANYONE, 'create': AUTHENTICATED, ...}

class Comment(ProtoModel):
    __access__ = {'read': ANYONE, 'create': AUTHENTICATED, 'update': OWNER | ROLE('admin'), ...}
```

For polymorphic types, each subtype could declare its own `__access__`:

```python
class Article(Content):
    __access__ = {'read': ANYONE, 'create': AUTHENTICATED}

class Draft(Content):
    __access__ = {'read': OWNER, 'create': AUTHENTICATED}
```

### 6.2 How `__access__` Would Compose with Type Discrimination

The `_resolver.sql_filter_for(ctx)` call in `routes_fastapi.py` (line 103) generates SQL WHERE clauses from access rules:

```python
# Current: just authorization filter
auth_filter = _resolver.sql_filter_for(ctx)
result = target_cls.list(sql_filter=auth_filter, ...)
```

For polymorphic queries, two filters would need to be combined:

1. **Type filter:** `WHERE _type = 'article'` (discriminator)
2. **Auth filter:** `WHERE user_owner = ? OR 1=1` (from access rules)

The `Where` rule class (lines 211-278) already supports attribute-based conditions with SQL pushdown:

```python
class Where(AccessRule):
    def sql_filter(self, ctx):
        # e.g. Where(status='published') -> "status = ?", ['published']
        parts, params = [], []
        for field, op, value in self._parse():
            parts.append(f"{field} {op} ?")
            params.append(value)
        return (" AND ".join(parts), params)
```

A `TypeFilter` rule could be composed with existing rules using the `&` operator:

```python
# Conceptual:
effective_access = article_access & Where(_type='article')
```

This would naturally produce the combined SQL clause: `(_type = 'article') AND (user_owner = ? OR 1=1)`.

### 6.3 Schema Serialization for Frontend

Each subtype's access rules are already serialized into JSON Schema via `access_schema()` (line 256 of `proto_model.py`):

```python
schema['access'] = access_schema(cls)
```

And for `$defs` entries (line 307):

```python
schema['$defs'][model.__name__]['access'] = access_schema(model)
```

The frontend `Permissions.js` already reads per-model access rules from schema. If each subtype in `$defs` carries its own `access` block, the frontend can already resolve per-subtype permissions.

---

## 7. Implementation Roadmap

### Phase 0: What Works Today with Zero Framework Changes

Even without any changes, developers can simulate polymorphism using existing patterns:

```python
# Approach: Shared base, separate tables, manual aggregation
class Content(ProtoModel):
    __abstract__ = True
    __storable__ = False   # Not stored directly
    title: str
    author: str

class Article(Content):
    __tablename__ = 'articles'
    __storable__ = True
    body: str

class Video(Content):
    __tablename__ = 'videos'
    __storable__ = True
    video_url: str
    duration: int

# Register both as independent models
app = create_app(models=[Article, Video], ...)
```

**What works:**
- Shared fields inherited from `Content`
- Each subtype gets its own table, routes, schema, DynamicClass
- Per-subtype access rules, UI configuration, methods

**What does NOT work:**
- No unified `/content` endpoint
- No mixed-type collections in the frontend
- No `oneOf`/`anyOf` schema for the union type
- Must query `/articles` and `/videos` separately

**Verdict:** Good enough for many applications. The E-commerce pattern (Product, DigitalProduct, PhysicalProduct) works if each subtype has its own listing page.

### Phase 1: Discriminator Column Support (Small Additions)

**Estimated effort:** 2-3 engineering days

| Change | File | Lines Affected | Description |
|--------|------|---------------|-------------|
| Add `__discriminator__` ClassVar | `proto_model.py` | `__init_subclass__()` | Register subtypes in a class-level `__subtypes__` dict |
| Inject `_type` column | `sqlite_migration.py` | `create_table()` | Add `_type TEXT NOT NULL DEFAULT '{classname}'` |
| Filter by `_type` on read | `sqlite_storage.py` | `list()`, `get()` | Add `WHERE _type = ?` when model has `__discriminator__` |
| Inject `_type` on write | `sqlite_storage.py` | `create()` | Set `_type = model_class.__name__` before INSERT |

**Model definition would look like:**

```python
class Content(ProtoModel):
    __tablename__ = 'content'
    __storable__ = True
    __discriminator__ = '_type'   # NEW: enables STI
    title: str
    author: str

class Article(Content):
    body: str              # Added to 'content' table as nullable column

class Video(Content):
    video_url: str         # Added to 'content' table as nullable column
    duration: int = 0
```

### Phase 2: Schema Union Generation (Medium Additions)

**Estimated effort:** 3-4 engineering days

| Change | File | Description |
|--------|------|-------------|
| Generate `oneOf` + `discriminator` | `proto_model.py` `schema()` | When `__discriminator__` is set, output union schema |
| Include subtype schemas in `$defs` | `proto_model.py` `schema()` | Each subtype gets its own `$defs` entry |
| Register subtype DynamicClasses | `NTT.js` `SCHEMA()` | Process `oneOf` + `discriminator` mapping |
| Per-entity type resolution | `NTT.js` `DynamicClass.READ` | Route entities to correct subtype DynamicClass |

### Phase 3: Frontend Type Dispatch (Architectural Changes)

**Estimated effort:** 5-7 engineering days

| Change | File | Description |
|--------|------|-------------|
| Per-entity `childTag` resolution | `ListElement.js` `createChild()` | Look up entity type, resolve to subtype component |
| Schema swap in forms | `form.js` `getForm()` | Use subtype schema when `_type` is known |
| Type selector in create forms | `form.js` | Dropdown to select subtype before showing fields |
| Mixed-type collection support | `ListElement.js` `render()` | Handle entities with different schemas in one list |

### Phase 4: Polymorphic Query Dispatch (Full Polish)

**Estimated effort:** 3-5 engineering days

| Change | File | Description |
|--------|------|-------------|
| Polymorphic route generation | `routes_fastapi.py` | `/content` returns all subtypes; `/content?_type=article` filters |
| Per-subtype auth composition | `routes_fastapi.py` | Combine type filter with access rules |
| `GET /Content` returns union schema | `routes_fastapi.py` `make_get_schema()` | Schema endpoint returns `oneOf` for polymorphic base |
| `POST /content` dispatches by `_type` | `routes_fastapi.py` `make_create_instance()` | Inspect discriminator in request body |

### Timeline Summary

```
Phase 0:  Today            -- Separate tables, manual aggregation (no changes)
Phase 1:  +2-3 days        -- STI with discriminator column
Phase 2:  +3-4 days        -- JSON Schema union generation
Phase 3:  +5-7 days        -- Frontend polymorphic rendering
Phase 4:  +3-5 days        -- Polymorphic routes and query dispatch
          ────────────
Total:    13-19 eng days    for full polymorphism support
```

---

## 8. Competitive Comparison

### 8.1 Framework Comparison Table

| Feature | Django | Rails | Strapi | Prisma | PyBend (today) | PyBend (Phase 4) |
|---------|--------|-------|--------|--------|---------------|------------------|
| STI (single table inheritance) | Via `django-polymorphic` | Built-in | No | No | No | Yes |
| CTI (class table inheritance) | Via `django-polymorphic` | No | No | No | No | Possible |
| MTI (multi-table inheritance) | Built-in | No | No | No | No | No |
| Discriminator column | Manual | Automatic (`type`) | N/A | Via `@@map` | No | Automatic |
| Polymorphic queries | Via manager | Built-in | N/A | No | No | Yes |
| Schema-driven UI for subtypes | No | No | Partial | No | No | Yes (unique) |
| Access rules per subtype | Manual middleware | Manual | Plugin | Manual | Already works | Already works |
| `oneOf`/`anyOf` schema output | No | No | No | No | No | Yes (unique) |
| Frontend type dispatch | N/A (server-rendered) | N/A | Partial (React) | N/A | No | Yes |

### 8.2 What Django Does

Django's `django-polymorphic` package adds a `polymorphic_ctype` FK column pointing to `ContentType`. Queries on the base manager automatically downcast to the correct subclass:

```python
# Django polymorphic
Content.objects.all()  # Returns [Article, Video, Article, ...]
Article.objects.all()  # Returns only Articles
```

**Advantage:** Mature, battle-tested.
**Disadvantage:** No schema output, no automatic UI adaptation, requires explicit manager usage.

### 8.3 What Rails Does

Rails ActiveRecord has built-in STI with a `type` column:

```ruby
class Content < ApplicationRecord; end
class Article < Content; end
class Video < Content; end
```

The `type` column is automatically set on creation and used for instantiation on read.

**Advantage:** Zero configuration.
**Disadvantage:** STI only -- no CTI. No schema generation. No automatic UI.

### 8.4 What Strapi Does

Strapi v4+ uses "Dynamic Zones" and "Components" for polymorphic-like behavior, but these are content-block aggregation, not true type inheritance. A "Content" type can have a dynamic zone that accepts different component shapes, but there is no shared base type or discriminator-based querying.

**Advantage:** Good UI for content management.
**Disadvantage:** Not true polymorphism. No typed querying. Components are structurally independent.

### 8.5 What PyBend Uniquely Enables

PyBend's schema-driven architecture creates an opportunity that no other framework offers:

> **Schema-Propagated Polymorphism:** Define a polymorphic model in Python, and the discriminator mapping, subtype schemas, per-subtype access rules, and per-subtype UI configuration all propagate to the frontend automatically via JSON Schema. No frontend code changes needed. The frontend reads the `oneOf` + `discriminator` block and adapts its rendering, form generation, and permission checks dynamically.

This is a genuine differentiator. In Django or Rails, adding a new subtype requires: defining the model, creating a migration, updating serializers, updating views/controllers, updating frontend components, updating forms, updating tests. In PyBend (Phase 4), adding a new subtype would require: defining the model class. Everything else propagates through the schema.

---

## 9. Sources

### Codebase Files Analyzed

| File | Key Content |
|------|-------------|
| `/workspace/src/pybend/core/models/proto_model.py` | ProtoModel base class, `__init_subclass__()`, `schema()`, `model_dump()`, `generate_join_model()` |
| `/workspace/src/pybend/core/models/base_user.py` | BaseUser abstract model, `__abstract__` flag, login/register endpoints |
| `/workspace/src/pybend/core/models/storable_mixin.py` | StorableMixin CRUD operations, `set_storage()`, `_storage_dict()` |
| `/workspace/src/pybend/core/storage/sqlite_storage.py` | SQLite backend, `create()`, `list()`, `get()`, FK hydration, populate |
| `/workspace/src/pybend/core/storage/sqlite_migration.py` | Table creation, auto-migration, column management |
| `/workspace/src/pybend/core/api/routes_fastapi.py` | Route generation, CRUD factories, `_resolve_user()`, custom method dispatch |
| `/workspace/src/pybend/core/app.py` | `create_app()`, `PyBendApp` builder, model registration |
| `/workspace/src/pybend/core/authorize/rules.py` | ABAC rules: `ANYONE`, `AUTHENTICATED`, `OWNER`, `ROLE`, `Where`, composable operators |
| `/workspace/src/pybend/core/utils/registrar.py` | `registered_models` dict, `join_models` dict, `register_model()` |
| `/workspace/src/pybend/static/core/NTT.js` | DynamicClass creation, `prototype()`, `SCHEMA()`, type registry, instance management |
| `/workspace/src/pybend/static/components/ntt-item.js` | Entity rendering, size methods, `#resolveChildTag()`, permission-gated buttons |
| `/workspace/src/pybend/static/components/ListElement.js` | Collection base class, `createChild()`, `childTag` resolution, pagination |
| `/workspace/src/pybend/static/generators/form.js` | Schema-driven form generation, field filtering, `resolveAnyOf()` |
| `/workspace/src/pybend/example/models/product.py` | Concrete model example with `ListRef`, methods, UI config |
| `/workspace/src/pybend/example/models/comment.py` | Concrete model with `Ref['self']`, per-field access, `__protected_fields__` |

### External References

- JSON Schema: `oneOf`, `anyOf`, and `discriminator` keywords -- [JSON Schema Specification (2020-12)](https://json-schema.org/specification)
- Pydantic v2 Discriminated Unions -- [Pydantic Documentation](https://docs.pydantic.dev/latest/concepts/unions/)
- Django Polymorphic -- [django-polymorphic on PyPI](https://pypi.org/project/django-polymorphic/)
- Rails Single Table Inheritance -- [Rails Guides: Active Record Inheritance](https://guides.rubyonrails.org/association_basics.html)
- Martin Fowler's Patterns of Enterprise Application Architecture -- STI, CTI, Concrete Table Inheritance patterns
