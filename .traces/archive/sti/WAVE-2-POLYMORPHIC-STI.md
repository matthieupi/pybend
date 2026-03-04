# v0.9 Wave 2: Polymorphic System (STI) — Phases 1 & 2

## Context

PyBend's core principle is "the model is the app." Currently, every model maps to its own table. Wave 2 adds **Single Table Inheritance (STI)**: a developer declares `__discriminator__` on a base class, and the entire stack adapts — storage, schema, routes, and frontend.

This is a competitive differentiator: no other framework generates discriminated union JSON Schema from model definitions. The roadmap estimates 60-70% of the machinery already exists.

**Key design constraint:** `sqlite_storage.py` must NOT be modified. All STI logic lives in `DiscriminatorMixin` (auto-injected like `StorableMixin`) and schema extensions. This ensures any future storage backend gets STI for free.

## What the Developer Writes

```python
class Content(ActorModel):
    __tablename__ = 'content'
    __storable__ = True
    __discriminator__ = 'content_type'   # user-chosen, 'content_type' strongly suggested
    title: str
    author: str

class Article(Content):
    body: str

class Video(Content):
    video_url: str
    duration: int = 0
```

## What They Get

- Single `content` table with `content_type TEXT` column (auto-created from Pydantic field)
- `Article.list()` → only articles (`WHERE content_type = 'Article'`)
- `Content.list()` → all types (polymorphic instantiation)
- `Content.get(id)` → returns correct subtype (Article or Video instance)
- `Article.create(...)` → auto-sets `content_type = 'Article'`
- `GET /Content` → JSON Schema with `oneOf` + `discriminator` mapping
- `GET /Article` → Article-specific schema
- Frontend creates per-subtype DynamicClasses from `$defs`

## How Storage Stays Untouched

The discriminator is a **real Pydantic field** dynamically added by `DiscriminatorMixin.__init_subclass__`. Since it's in `model_fields`, storage handles it naturally through existing code paths:

| Operation | Where STI logic lives | Why storage stays untouched |
|-----------|----------------------|---------------------------|
| **create** | Discriminator is a real field with `default='{ClassName}'` | `storage.create()` iterates `model_fields` — field is just there |
| **list** | `DiscriminatorMixin.list()` merges type filter into `sql_filter` before `super().list()` | Storage already accepts `sql_filter` parameter |
| **get** | `DiscriminatorMixin.get()` calls `super().get(as_dict=True)`, reads discriminator, instantiates correct subtype | Storage already supports `as_dict=True` |
| **update** | `DiscriminatorMixin.update()` strips discriminator from data before `super().update()` | Storage already takes a filtered dict |

**Constraint:** The discriminator field name must NOT start with `_` (Pydantic V2 treats `_`-prefixed names as PrivateAttr, and `create_table()` skips `_`-prefixed fields). Recommended default: `content_type`.

---

## Implementation Plan

### Step 1: DiscriminatorMixin + Auto-Injection
**Files:**
- `src/pybend/core/models/discriminator_mixin.py` (NEW)
- `src/pybend/core/models/proto_model.py` (line 68-89)

**1a. Create `DiscriminatorMixin`** — follows the `StorableMixin` pattern:

```python
class DiscriminatorMixin:
    """Mixin for Single Table Inheritance (STI) support.

    Auto-injected by ProtoModel.__init_subclass__ when __discriminator__ is detected.
    Manages __subtypes__ registry, __sti_root__ tracking, and CRUD overrides.
    """
    __subtypes__: ClassVar[Dict[str, Type]] = {}
    __sti_root__: ClassVar[Optional[Type]] = None
```

The mixin owns ALL STI logic:

**`__init_subclass__`** — Three mutually exclusive branches:
1. **`__discriminator__` in `cls.__dict__`** → this IS the STI root: init `cls.__subtypes__ = {}`, `cls.__sti_root__ = cls`, dynamically add discriminator field: `cls.__annotations__[disc_name] = str` with `Field(default=cls.__name__)`
2. **Walk MRO, find ancestor with `__discriminator__` in its `__dict__`** → STI subtype: set `cls.__sti_root__ = ancestor`, force `cls.__tablename__ = ancestor.__tablename__`, register `ancestor.__subtypes__[cls.__name__] = cls`, dynamically add discriminator field with `Field(default=cls.__name__)`
3. **Neither** → regular inheritance, no STI behavior, nothing happens

**CRUD overrides** (classmethod wrappers that call `super()`):
- **`list(cls, sql_filter=None, ...)`** — If subtype (`cls is not cls.__sti_root__`): merge `WHERE {disc} = ?` with class name into `sql_filter`. If root: no filter. Call `super().list(...)`. Post-process: for root queries, re-instantiate each record as correct subtype using `__subtypes__` lookup on the discriminator value.
- **`get(cls, id, ...)`** — Call `super().get(id, as_dict=True)`. Read discriminator value from dict. Look up correct subtype in `__subtypes__`. Instantiate and return.
- **`update(cls, id, data)`** — Strip discriminator field from data dict. Call `super().update(id, data)`.
- **`create()` needs no override** — the discriminator is a real Pydantic field with a default, so `_storage_dict()` includes it naturally.

**1b. Auto-inject in `ProtoModel.__init_subclass__`** — same pattern as StorableMixin injection at line 73-76:

```python
# After StorableMixin injection, before super().__init_subclass__:
if getattr(cls, '__discriminator__', None):
    if not issubclass(cls, DiscriminatorMixin):
        cls.__bases__ = (DiscriminatorMixin,) + cls.__bases__
```

The `issubclass` guard prevents double injection on subtypes (they already inherit it from root).

### Step 2: Registrar — STI-Aware Registration
**File:** `src/pybend/core/utils/registrar.py`

- Add `sti_models: Dict[str, Type] = {}` dict for STI subtypes (keyed by class name)
- In `register_model()`: detect STI subtypes via `__sti_root__`
  - Root → normal registration in `registered_models[tablename]`, run `create_table()` + `migrate_table()`
  - Subtype → register in `sti_models[class_name]`, run `migrate_table()` only (adds subtype-specific columns), skip `create_table()`

### Step 3: SQLite Migration — Orphan Protection
**File:** `src/pybend/core/storage/sqlite_migration.py`

Since the discriminator is a real Pydantic field, `create_table()` creates the column automatically via existing `model_fields` iteration. No special column injection needed.

**3a. `migrate_table()` orphan protection (line 278-285):** When model participates in STI, collect ALL fields from ALL subtypes (`root.model_fields ∪ subtype1.model_fields ∪ ...`) before deciding what columns are orphaned. Without this, `migrate_table(Video)` would try to drop Article's `body` column.

**3b. Index creation:** After existing index logic, if model has `__discriminator__`, add `CREATE INDEX IF NOT EXISTS idx_{table}_{disc_field}` for efficient type-filtered queries.

### Step 4: Schema Extension — `polymorphic` Stage
**File:** `src/pybend/core/models/proto_schema_sti.py` (NEW)

New `@schema_extension(after='defs')` called `polymorphic`:
- For STI root: generates subtype schemas, builds `oneOf` array + `discriminator.mapping`, puts each subtype in `$defs` with `$id`, `methods`, `access`, `__name__`, `__tablename__`
- For STI subtype: adds discriminator as const property with `ui.display: false`
- Non-abstract base class included in `$defs` alongside subtypes

Also registers `@dump_extension(after='instance_url')` called `sti_type`: ensures discriminator value is present in serialized responses (it should already be there from `model_dump()` since it's a real field, but the extension can set `ui.display: false` on the schema property).

**Activation:** Import from `proto_model.py` to register stages at module load time.

Reuses existing helpers: `referenced_json_schema()` (proto_model.py:204), `_apply_field_exclusion()` (proto_model.py:27), `access_schema()` (authorize/schema.py), `__pybend_methods_json_signature__()`.

### Step 5: App Bootstrap — Registration Order
**File:** `src/pybend/core/app.py`

In `build()`, sort models so STI roots are registered before subtypes (table must exist before subtypes run `migrate_table()`).

### Step 6: Route Registration — Subtype Schema Routes
**File:** `src/pybend/core/api/routes_fastapi.py`

After existing Pass 2 in `register_routes()`, add Pass 3: iterate `sti_models` and register `GET /{SubtypeName}` schema-only routes for each subtype.

### Step 7: Frontend — Polymorphic READ Dispatch
**File:** `src/pybend/static/core/NTT.js`

**7a. `SCHEMA()` handler (line 396-408):** Already works — `$defs` entries with `type: 'object'` and `properties` get DynamicClasses automatically.

**7b. `DynamicClass.READ` handler (line ~922):** When schema has `discriminator`, check each record's discriminator value. Look up subtype DynamicClass via `NTT.get(typeName)`. Instantiate with subtype class. Also store in base class instance map for unified access.

### Step 8: Tests
**File:** `src/pybend/core/tests/unit/test_sti.py` (NEW)

1. `__init_subclass__` — subtypes in `__subtypes__`, shared tablename, `__sti_root__`, discriminator field dynamically added
2. Storage create — discriminator column value matches class name (no storage changes needed)
3. Storage list — subtype filtering via mixin, root returns all, polymorphic instantiation
4. Storage get — returns correct subtype instance via mixin
5. Migration — discriminator column auto-created from model_fields, index exists, subtype columns added, no cross-subtype orphaning
6. Schema — `oneOf` + `discriminator` on root, discriminator const on subtypes, `$defs` per subtype
7. Dump — discriminator in response, correct `$schema` URL per subtype
8. Routes — `GET /Content` polymorphic schema, `GET /Article` subtype schema
9. Edge cases — empty subtypes, base-only queries, `__abstract__` base, non-STI inheritance unaffected

---

## File Summary

| File | Action | Step |
|------|--------|------|
| `src/pybend/core/models/discriminator_mixin.py` | **NEW** — DiscriminatorMixin (STI logic + CRUD overrides) | 1 |
| `src/pybend/core/models/proto_model.py` | Auto-inject DiscriminatorMixin, import STI schema ext | 1, 4 |
| `src/pybend/core/utils/registrar.py` | Add `sti_models` dict, STI-aware registration | 2 |
| `src/pybend/core/storage/sqlite_migration.py` | Orphan protection, discriminator index | 3 |
| `src/pybend/core/models/proto_schema_sti.py` | **NEW** — schema + dump extensions | 4 |
| `src/pybend/core/app.py` | Sort models for registration order | 5 |
| `src/pybend/core/api/routes_fastapi.py` | Subtype schema routes (Pass 3) | 6 |
| `src/pybend/static/core/NTT.js` | Polymorphic READ dispatch | 7 |
| `src/pybend/core/tests/unit/test_sti.py` | **NEW** — comprehensive test suite | 8 |

**NOT modified:** `src/pybend/core/storage/sqlite_storage.py` — all STI CRUD logic lives in DiscriminatorMixin.

## Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Discriminator field | Real Pydantic field, dynamically added | Storage handles it naturally via `model_fields` — zero storage changes |
| Field naming | User-chosen, `content_type` strongly suggested | No `_`-prefix (Pydantic PrivateAttr + migration skip constraint) |
| STI implementation | `DiscriminatorMixin`, auto-injected | Follows `StorableMixin` pattern; storage-agnostic |
| CRUD overrides | Mixin wraps `list()`/`get()`/`update()` via `super()` | Storage layer stays untouched; any future backend gets STI for free |
| Schema impl | `@schema_extension` in new file | Follows extension pattern; zero proto_schema.py core changes |
| Registration | Root in `registered_models`, subtypes in `sti_models` | Prevents tablename key collision |
| CRUD routing | Shared base `/{tablename}` path | Single table = single endpoint |
| Subtype schemas | Each gets `GET /{SubtypeName}` | Frontend needs per-subtype DynamicClass |
| Orphan protection | Union all subtype fields in migration | Prevents cross-subtype column deletion |
| Base class | Instantiable by default | `__abstract__` to exclude from `oneOf` |

## Verification

```bash
# STI-specific tests
cd /workspace/src/pybend/core && pytest tests/unit/test_sti.py -v

# Full regression
cd /workspace/src/pybend/core && pytest tests/unit/ actors/tests/ ../example/tests/
```

## Commit Messages
1. `feat(models): Add DiscriminatorMixin with STI detection and CRUD overrides [0.9.2]`
2. `feat(models): Auto-inject DiscriminatorMixin in ProtoModel.__init_subclass__ [0.9.2]`
3. `feat(storage): Add STI orphan protection and discriminator index in migration [0.9.2]`
4. `feat(models): Add polymorphic schema extension with oneOf + discriminator [0.9.2]`
5. `feat(api): Add schema routes for STI subtypes and registration ordering [0.9.2]`
6. `feat(frontend): Add polymorphic READ dispatch for STI DynamicClasses [0.9.2]`
7. `test(models): Add comprehensive STI test suite [0.9.2]`
