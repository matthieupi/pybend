# STI (Single Table Inheritance) — Re-Application Guide

**Archived from**: v0.9 branch, Wave 2
**Date archived**: 2026-03-03
**Reason**: No concrete use case on current roadmap justifies the complexity.
**Research**: `.traces/research/polymorphic-system/` (6 documents)
**Plan**: `.traces/plans/v0.9/WAVE-2-POLYMORPHIC-STI.md`

## When To Re-Apply

Only bring this back when you have a **concrete use case** that requires:
1. **Cross-type queries** (e.g., `GET /content` returning mixed Article/Video/Event)
2. **Shared table** (subtypes share one DB table with a discriminator column)
3. **Frontend type dispatch** (oneOf schema with discriminator mapping)

If you only need shared fields/methods across subtypes but separate endpoints,
use Phase 0 (abstract base + separate tables) instead — it already works.

## Files In This Archive

| File | Original Location |
|------|------------------|
| `discriminator_mixin.py` | `src/n3tx/core/models/discriminator_mixin.py` |
| `proto_schema_sti.py` | `src/n3tx/core/models/proto_schema_sti.py` |
| `test_sti.py` | `src/n3tx/core/tests/unit/test_sti.py` |

## Step-By-Step Re-Application

### Step 1: Copy archived files back

```bash
cp .traces/archive/sti/discriminator_mixin.py src/n3tx/core/models/
cp .traces/archive/sti/proto_schema_sti.py src/n3tx/core/models/
cp .traces/archive/sti/test_sti.py src/n3tx/core/tests/unit/
```

### Step 2: Add STI import to `proto_model.py`

In `src/n3tx/core/models/proto_model.py`, add the side-effect import that
registers the `polymorphic` and `sti_type` pipeline stages:

```python
# After the proto_dump import, add:
import n3tx.core.models.proto_schema_sti  # noqa: F401 — registers polymorphic stages
```

### Step 3: Add STI injection block to `proto_model.py`

In `ProtoModel.__init_subclass__()`, add the STI block **after** the
StorableMixin injection and **before** the Agent mixin injection:

```python
        # STI: DiscriminatorMixin injection + discriminator field setup
        # Must happen BEFORE super().__init_subclass__() so Pydantic picks up the field
        if cls.__dict__.get('__discriminator__') or any(
            '__discriminator__' in base.__dict__ for base in cls.__mro__[1:]
        ):
            from .discriminator_mixin import DiscriminatorMixin, setup_sti
            if not issubclass(cls, DiscriminatorMixin):
                cls.__bases__ = (DiscriminatorMixin,) + cls.__bases__
            setup_sti(cls)
```

### Step 4: Add `sti_models` dict to `registrar.py`

In `src/n3tx/core/utils/registrar.py`, add after `join_models`:

```python
sti_models: Dict[str, Type[Any]] = {}
```

And update `apply_registration()` to handle STI subtypes:

```python
def apply_registration(result: RegistrationResult) -> None:
    """Execute the side effects described by a RegistrationResult."""
    model = result.model_class
    logger.info("Registering model: %s", model.__name__)

    if result.is_join and result.join_key:
        join_models[result.join_key] = model

    sti_root = getattr(model, '__sti_root__', None)
    is_sti_subtype = sti_root is not None and model is not sti_root

    if result.is_storable:
        model.set_storage(result.storage)
        if not is_sti_subtype:
            model.create_table()
        if hasattr(result.storage, 'migrate_table'):
            result.storage.migrate_table(model)

    if is_sti_subtype:
        sti_models[model.__name__] = model
    else:
        registered_models[result.tablename] = model
```

Key changes from default:
- Skip `create_table()` for STI subtypes (they share the root's table)
- Register subtypes in `sti_models` instead of `registered_models`

### Step 5: Add discriminator index to `sqlite_migration.py`

In `create_table()`, after the self-ref index block, add:

```python
        # STI discriminator index for efficient type-filtered queries
        disc = getattr(model_class, '__discriminator__', None)
        if disc:
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{disc} "
                f"ON {table_name} ({disc})"
            )
```

In `migrate_table()`, replace the orphan column check with STI-aware version:

```python
        # STI orphan protection: collect all fields from all subtypes
        # so we don't drop columns belonging to sibling subtypes
        valid_columns = set(model_columns.keys())
        sti_root = getattr(model_class, '__sti_root__', None)
        if sti_root:
            valid_columns.update(sti_root.model_fields.keys())
            for subtype in getattr(sti_root, '__subtypes__', {}).values():
                valid_columns.update(subtype.model_fields.keys())

        # Remove orphaned columns
        for col in existing_columns:
            if col not in valid_columns or col.startswith('_') or col.startswith('__'):
```

And add the discriminator index at the end of `migrate_table()`:

```python
        # STI discriminator index for efficient type-filtered queries
        disc = getattr(model_class, '__discriminator__', None)
        if disc:
            try:
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{disc} "
                    f"ON {table_name} ({disc})"
                )
            except sqlite3.OperationalError:
                pass
```

### Step 6: Add STI sort key to `app.py`

In `N3TXApp.build()`, before the `for result in preparations:` loop, add:

```python
        # Sort so STI roots are registered before subtypes (table must exist first)
        def _sti_sort_key(result):
            root = getattr(result.model_class, '__sti_root__', None)
            if root is None:
                return 0  # non-STI: register first
            if result.model_class is root:
                return 1  # STI root: register second
            return 2  # STI subtype: register last

        preparations.sort(key=_sti_sort_key)
```

### Step 7: Add STI subtype schema routes to `routes_fastapi.py`

Import `sti_models` in the imports:

```python
from n3tx.core.utils.registrar import registered_models, join_models, sti_models
```

Add Pass 3 at the end of `register_routes()`:

```python
    # Pass 3: Register schema-only routes for STI subtypes
    # Each subtype gets GET /{SubtypeName} for its schema (frontend needs
    # per-subtype DynamicClass). CRUD goes through the shared base table.
    for subtype_name, subtype_class in sti_models.items():
        root = getattr(subtype_class, '__sti_root__', None)
        if root:
            tag = root.__tablename__.capitalize()
        else:
            tag = subtype_name
        router.get(f"/{subtype_name}", tags=[tag])(make_get_schema(subtype_class))
        logger.info("STI subtype schema route: GET /%s", subtype_name)
```

### Step 8: Update test DEFAULT_STAGES

In `test_schema_ext.py`:
```python
DEFAULT_STAGES = ['base', 'strip_hidden', 'methods', 'agent', 'defs', 'polymorphic', 'access', 'ui', 'metadata']
# Count: 9
```

In `test_proto_dump.py`:
```python
DEFAULT_STAGES = ['base', 'schema_url', 'instance_url', 'sti_type']
```

### Step 9: Run tests

```bash
cd /workspace/src/n3tx/core && pytest tests/unit/test_sti.py -v
cd /workspace/src/n3tx/core && pytest tests/unit/test_schema_ext.py -v
cd /workspace/src/n3tx/core && pytest tests/unit/test_proto_dump.py -v
cd /workspace/src/n3tx/core && pytest tests/unit/ -v
```

## Design Decisions (for context)

1. **DiscriminatorMixin is auto-injected** via `__init_subclass__` (same pattern as StorableMixin)
2. **Discriminator is a REAL Pydantic field** — dynamically added to annotations so storage handles it naturally. `sqlite_storage.py` is NOT modified.
3. **STI subtypes skip `create_table()`** — they share the root's table. Migration adds their columns.
4. **Orphan protection** — `migrate_table()` collects ALL subtype fields before deciding what to drop, preventing sibling column deletion.
5. **Schema pipeline** — `polymorphic` stage generates `oneOf` + `discriminator` mapping for root, `const` discriminator for subtypes.
6. **Dump pipeline** — `sti_type` stage is a no-op hook for future dump logic.
