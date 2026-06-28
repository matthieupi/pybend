# ✅ Plan: Support Embedded Value Models in N3TX Storable Models

📍 **Goal**: Fix the framework-level mismatch where every Pydantic model field on a storable `ProtoModel` is auto-rewritten into `Ref[T]`, even when the nested model is a non-storable value object meant to serialize inline as JSON.

This directly addresses the `Run.pipeline_options: PipelineOptions` crash:

```text
Error calling function `<lambda>`: TypeError: int() argument must be a string,
a bytes-like object or a real number, not 'PipelineOptions'
```

---

## 1. 🔎 Current Failure

### Concrete app shape

```py
class PipelineOptions(ProtoModel):
    training_backend: str | None = None
    nerfstudio_method: str | None = None

class Run(ActorModel):
    __tablename__ = "runs"
    __storable__ = True

    pipeline_options: PipelineOptions = Field(default_factory=PipelineOptions)
```

### Current framework behavior

`ProtoModel.__init_subclass__()` rewrites any Pydantic model field on a storable model into a `Ref[T]`:

```py
# lib/n3tx/packages/n3tx-core/src/n3tx_core/models/proto_model.py
if isinstance(annotation, type) and issubclass(annotation, BaseModel) and annotation != cls:
    new_annotations[name] = Ref[annotation]
```

That makes this true at runtime:

```py
Run.model_fields["pipeline_options"].annotation
# n3tx_core.utils.typer.Ref[modules.app.actors.Run.PipelineOptions]
```

But the value is still a `PipelineOptions(...)` object. Serialization uses the `Ref` serializer:

```py
lambda v: v if isinstance(v, str) else (int(v) if v is not None else None)
```

So `model_dump()` / `model_response()` crashes with `int(PipelineOptions(...))`.

---

## 2. 🧭 Intended Framework Contract

N3TX should distinguish between:

| Field shape | Meaning | Storage | API/schema response |
|---|---|---|---|
| `Ref[T]` explicitly | Foreign-key reference | integer FK | href/id reference |
| `SomeStorableModel` | Legacy shorthand for FK | integer FK | href/id reference |
| `SomeNonStorableModel` | Embedded value object | JSON TEXT | inline object |
| `dict` / `list` | Embedded JSON | JSON TEXT | inline JSON |
| `ListRef[T]` / `ManyToMany[T]` | Relationship collection | join table | href array / relationship data |

✅ **Rule to implement**: only rewrite nested Pydantic model fields to `Ref[T]` when the target type is explicitly storable.

```py
should_auto_ref = (
    isinstance(annotation, type)
    and issubclass(annotation, BaseModel)
    and annotation is not cls
    and getattr(annotation, "__storable__", False)
)
```

Non-storable `ProtoModel` subclasses become first-class embedded schema/value models.

---

## 3. 🗺️ Affected Flow

```text
Model class definition
  |
  v
ProtoModel.__init_subclass__
  | currently rewrites every nested BaseModel -> Ref[T]
  | planned: rewrite only storable nested models -> Ref[T]
  v
Pydantic model_fields
  |
  +--> schema pipeline
  |      embedded non-storable model remains object/$defs
  |
  +--> storage migration
  |      embedded non-storable model gets TEXT column
  |
  +--> storage create/update
  |      embedded model serialized to JSON TEXT
  |
  +--> storage get/list
         JSON TEXT deserialized before model instantiation
```

---

## 4. 📍 Files to Change

| File | Change |
|---|---|
| `lib/n3tx/packages/n3tx-core/src/n3tx_core/models/proto_model.py` | Narrow auto-FK rewrite to storable target models only. Add small helper for clarity. |
| `lib/n3tx/packages/n3tx-core/src/n3tx_core/utils/introspection.py` | Teach `get_json_fields()` to include non-storable `BaseModel` fields and optional non-storable model fields. Ensure `get_ref_fields()` remains only `Ref[T]`. |
| `lib/n3tx/packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py` | Create `TEXT` columns for embedded non-storable model fields instead of `INTEGER`/`*_id`. Preserve `INTEGER`/`*_id` for storable model shorthand. |
| `lib/n3tx/packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py` | JSON-serialize embedded model values on write/update and deserialize them on read/list through existing JSON field path. |
| `lib/n3tx/packages/n3tx-core/src/n3tx_core/tests/unit/...` | Add regression tests for embedded value model serialization, storage round-trip, and storable model FK shorthand preservation. |
| `lib/n3tx/packages/n3tx-core/docs/storage.md` | Document embedded value object storage. |
| `lib/n3tx/packages/n3tx-core/docs/schema-pipeline.md` | Document storable-FK vs embedded-value model distinction. |
| `lib/n3tx/docs/MODELS.md` and/or `lib/n3tx/docs/CORE.md` | Add cross-cutting contract note if docs are intended to mirror package behavior. |

---

## 5. 💻 Core Implementation Shape

### 5.1 Add classification helpers

Use a tiny helper near the current rewrite logic so the rule is readable and reused by storage/migration where useful.

Candidate location: `n3tx_core.utils.introspection`.

```py
def is_pydantic_model_type(annotation) -> bool:
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def is_storable_model_type(annotation) -> bool:
    return is_pydantic_model_type(annotation) and bool(getattr(annotation, "__storable__", False))


def is_embedded_model_type(annotation) -> bool:
    return is_pydantic_model_type(annotation) and not is_storable_model_type(annotation)


def unwrap_optional(annotation):
    origin = get_origin(annotation)
    if origin in (Union, UnionType) and type(None) in get_args(annotation):
        return next(arg for arg in get_args(annotation) if arg is not type(None))
    return annotation
```

Keep this helper local and conservative: it should not try to classify `ListRef`, `ManyToMany`, or arbitrary containers.

### 5.2 Narrow FK injection

```diff
# proto_model.py
- if isinstance(annotation, type) and issubclass(annotation, BaseModel) and annotation != cls:
+ if (
+     isinstance(annotation, type)
+     and issubclass(annotation, BaseModel)
+     and annotation != cls
+     and getattr(annotation, "__storable__", False)
+ ):
      new_annotations[name] = Ref[annotation]
```

This preserves existing shorthand FK behavior for fields like:

```py
class Product(ProtoModel):
    __storable__ = True

class Order(ProtoModel):
    __storable__ = True
    product: Product  # still rewritten to Ref[Product]
```

But leaves this embedded:

```py
class Money(ProtoModel):
    amount: float
    currency: str

class Product(ProtoModel):
    __storable__ = True
    price: Money  # remains inline object
```

### 5.3 Treat embedded models as JSON fields

Update `get_json_fields(model_class)` to include:

- `field_type` is non-storable `BaseModel`
- `Optional[field_type]` where inner is non-storable `BaseModel`

Pseudo-diff:

```diff
 def get_json_fields(model_class):
     ...
     field_type = unwrap_optional(field_info.annotation)
+    if is_embedded_model_type(field_type):
+        results.append(field_name)
+        continue
```

This lets existing storage read/write JSON field infrastructure handle embedded models.

### 5.4 Store embedded models as JSON TEXT

`SQLiteStorage._coerce_value()` currently only JSON-serializes `dict` and `list`; arbitrary `BaseModel` falls to `str(v)`. Change it to serialize Pydantic model values via `model_dump(mode="json")` first.

```diff
 def _coerce_value(v):
     if isinstance(v, _SQLITE_NATIVE):
         return v
     ...
+    if isinstance(v, BaseModel):
+        return json.dumps(v.model_dump(mode="json"), default=str)
     if isinstance(v, (dict, list)):
         return json.dumps(v, default=str)
```

This improves SQLite bind behavior for embedded values without changing storage of explicit `Ref[T]` fields, because `Ref` values are flattened before storage or are already primitive/href-normalized.

### 5.5 Create TEXT columns for embedded models

`SQLiteMigration.create_table()` currently maps nested `BaseModel` fields to `INTEGER` with `field_name_id`. Split behavior:

```diff
- if isinstance(field_type, type) and issubclass(field_type, BaseModel):
+ if is_storable_model_type(field_type):
      sql_type = 'INTEGER'
      field_name = f"{field_name}_id"
+ elif is_embedded_model_type(field_type):
+     sql_type = 'TEXT'
```

Do the same in `migrate_table()` if it has parallel column-type logic.

### 5.6 Read/list deserialization

Once `get_json_fields()` includes embedded model fields, this existing path should work:

```py
_deserialize_json_fields(model_class, record)
```

Pydantic should then instantiate the nested model from the decoded dict.

Potential detail to verify: `SQLiteStorage.get()` builds `data` from `record` by model field name. For old DBs with prior `pipeline_options_id` columns, this change will not read that column. That is acceptable for the new embedded contract, but app migrations may need follow-up if any production DB already has wrong columns.

---

## 6. 🧪 Test Plan

### 6.1 Unit: class rewrite behavior

File: `lib/n3tx/packages/n3tx-core/src/n3tx_core/tests/unit/test_embedded_models.py`

```py
def test_non_storable_model_field_is_not_rewritten_to_ref():
    class Options(ProtoModel):
        backend: str | None = None

    class Job(ProtoModel):
        __tablename__ = "embedded_jobs"
        __storable__ = True
        options: Options = Field(default_factory=Options)

    assert Job.model_fields["options"].annotation is Options
```

### 6.2 Unit: storable shorthand FK still works

```py
def test_storable_model_field_still_rewrites_to_ref():
    class Account(ProtoModel):
        __tablename__ = "embedded_accounts"
        __storable__ = True
        name: str

    class Invoice(ProtoModel):
        __tablename__ = "embedded_invoices"
        __storable__ = True
        account: Account

    assert "Ref" in str(Invoice.model_fields["account"].annotation)
```

### 6.3 Unit: model response serializes inline value

```py
def test_embedded_model_serializes_inline_in_model_response():
    class Options(ProtoModel):
        backend: str | None = None

    class Job(ProtoModel):
        __tablename__ = "embedded_jobs_response"
        __storable__ = True
        options: Options = Field(default_factory=Options)

    payload = Job(id=1, options=Options(backend="nerfstudio")).model_response()

    assert payload["options"]["backend"] == "nerfstudio"
```

### 6.4 Integration: SQLite round-trip

Use file-based SQLite, not `:memory:`.

```py
def test_embedded_model_round_trips_through_sqlite(tmp_path):
    storage = SQLiteStorage(str(tmp_path / "test.db"))

    class Options(ProtoModel):
        backend: str | None = None
        iterations: int | None = None

    class Job(ProtoModel):
        __tablename__ = "embedded_jobs_storage"
        __storable__ = True
        options: Options = Field(default_factory=Options)

    register_model(Job, storage=storage)
    created = Job.create(Job(options=Options(backend="nerfstudio", iterations=30_000)))
    loaded = Job.get(created.id)

    assert isinstance(loaded.options, Options)
    assert loaded.options.backend == "nerfstudio"
    assert loaded.model_response()["options"]["iterations"] == 30_000
```

### 6.5 App regression: Run no longer crashes

Add or update app-side test after framework test passes:

```py
def test_run_model_response_serializes_pipeline_options_value_object(self):
    from modules.app.actors.Run import PipelineOptions, Run

    payload = Run(
        id=1,
        name="run-1",
        pipeline_options=PipelineOptions(training_backend="nerfstudio"),
    ).model_response()

    self.assertEqual(payload["pipeline_options"]["training_backend"], "nerfstudio")
```

---

## 7. 📊 Compatibility and Risk

| Risk | Impact | Mitigation |
|---|---|---|
| Existing apps depend on non-storable nested models becoming FK refs | Low/medium; non-storable models cannot be safely referenced via storage anyway | Preserve FK shorthand only for `__storable__ = True`; document behavior clearly. |
| Existing SQLite DB has `field_id` column from previous auto-migration | Medium for already-created local DBs | Auto-migration likely adds new `field` TEXT column but does not migrate `field_id`; app-specific migration/data cleanup may be required. Call out in release notes/docs. |
| JSONStorage has separate behavior | Unknown until inspected | Add JSONStorage round-trip test if JSONStorage is used in core tests; apply same embedded model serialization rule if needed. |
| Schema shape changes for embedded fields | Desired behavior | Tests should assert embedded fields remain `$ref` to `$defs` object schema, not integer refs. |
| Forward references / optional embedded models | Medium | Include `Optional[Options]` test if helper supports `UnionType` and `typing.Union`. |

---

## 8. 🚦 Implementation Sequence

### Phase 1 — Red tests

1. Add `test_embedded_models.py` in core tests.
2. Include at minimum:
   - non-storable model is not rewritten to `Ref`
   - storable model shorthand still rewrites to `Ref`
   - embedded model `model_response()` does not crash
   - SQLite round-trip stores and reloads embedded value object
3. Run:

```bash
cd /workspace/lib/n3tx && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_embedded_models.py -q
```

Expected: at least the embedded tests fail on current behavior.

### Phase 2 — Green framework change

1. Add/refine classification helpers in `introspection.py`.
2. Narrow `ProtoModel.__init_subclass__()` FK rewrite.
3. Update `get_json_fields()` for embedded model fields.
4. Update SQLite migration column typing.
5. Update `_coerce_value()` for `BaseModel` JSON serialization.
6. Run the narrow core test until green.

### Phase 3 — App regression

1. Add `Run.pipeline_options` serialization regression test.
2. Run:

```bash
cd /workspace && .venv-agent/bin/python -m unittest modules.app.tests.test_app_run_actor.RunActorTests.test_run_model_response_serializes_pipeline_options_value_object
```

### Phase 4 — Broader verification

Run core and app checks:

```bash
cd /workspace/lib/n3tx && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/ -q
cd /workspace && .venv-agent/bin/python -m unittest discover -s modules/app/tests
cd /workspace && .venv-agent/bin/python -m compileall modules tests
```

If the local framework package test runner is configured differently, use the repo runner documented by N3TX:

```bash
cd /workspace/lib/n3tx && python3 scripts/test-backend.py --suite core -- -q
```

### Phase 5 — Docs

Update:

- `packages/n3tx-core/docs/storage.md`
- `packages/n3tx-core/docs/schema-pipeline.md`
- cross-cutting `docs/MODELS.md` / `docs/CORE.md` if those docs are shipped as the high-level contract

---

## 9. ✅ Acceptance Criteria

- `Run(id=1, pipeline_options=PipelineOptions(...)).model_response()` returns inline `pipeline_options` JSON and does not crash.
- Non-storable nested `ProtoModel` fields are stored as JSON TEXT and round-trip as nested model instances.
- Storable nested model shorthand still becomes `Ref[T]` and preserves existing FK behavior.
- Explicit `Ref[T]`, `ListRef[T]`, and `ManyToMany[T]` behavior is unchanged.
- Schema for embedded value objects remains object-shaped with `$defs`, not integer-reference-shaped.
- Core tests and app regression tests pass.
- Docs explain the distinction between embedded value models and storable references.

---

## 10. ✨ Follow-up Considerations

- Consider adding an explicit marker later, e.g. `Embedded[T]`, if the implicit rule ever becomes ambiguous.
- Consider a migration note for apps that already created incorrect `*_id` columns for embedded models.
- Consider making `get_json_fields()` support nested `BaseModel` lists separately if the framework wants `list[NonStorableModel]` as embedded JSON arrays. This plan keeps scope to single embedded model fields first.
