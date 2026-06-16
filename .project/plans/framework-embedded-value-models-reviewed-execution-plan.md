# ✅ Revised Execution Plan: Explicit Nested Value Models

## ✅ Recommendation

Use an explicit model flag for embedded value models:

```py
class PipelineOptions(ProtoModel):
    __nested__ = True

    training_backend: str | None = None
    nerfstudio_method: str | None = None


class Run(ActorModel):
    __tablename__ = 'runs'
    __storable__ = True

    pipeline_options: PipelineOptions = Field(default_factory=PipelineOptions)
```

This is the lowest-risk contract:

- `Ref[T]` keeps one meaning: **resource/table reference**.
- `__tablename__` keeps one meaning: **resource/table identity**.
- `__nested__ = True` has one meaning: **embedded JSON value model**.
- Existing non-storable, non-nested models remain unaffected.

---

## 🧭 Framework Contract

| Shape | Meaning | Storage | API/schema response |
|---|---|---|---|
| `Ref[T]` | Explicit resource reference | id/FK column | href/id reference |
| `T` where `T.__nested__ = True` | Embedded value object | JSON TEXT | inline object |
| `list[T]` where `T.__nested__ = True` | Embedded value array | JSON TEXT | inline array |
| `T` where `T.__tablename__` exists | Existing resource shorthand | rewritten to `Ref[T]` | href/id reference |
| `ListRef[T]` | Explicit relationship collection | child/join relationship | href array |
| `ManyToMany[T]` | Explicit many-to-many relationship | through table | relationship data |
| `dict` / primitive `list` | Embedded JSON | JSON TEXT | inline JSON |

### Invalid / misconfigured

Reject this combination early:

```py
class Bad(ProtoModel):
    __nested__ = True
    __tablename__ = 'bad'
```

A model should be either a nested value or a table resource, not both.

---

## 🔎 Current Failure

Current `ProtoModel.__init_subclass__()` rewrites every direct Pydantic model field on a storable model into `Ref[T]`:

```py
if isinstance(annotation, type) and issubclass(annotation, BaseModel) and annotation != cls:
    new_annotations[name] = Ref[annotation]
```

That makes a value object behave like a reference:

```py
Run.model_fields['pipeline_options'].annotation
# Ref[PipelineOptions]
```

Then serialization crashes because the `Ref` serializer tries:

```py
int(PipelineOptions(...))
```

The fix is not to change `Ref`. The fix is to **skip Ref rewriting for explicitly nested value models**.

---

## 🗺️ Target Flow

```text
PipelineOptions(__nested__ = True)
  |
  v
Run.pipeline_options: PipelineOptions
  |
  +--> ProtoModel.__init_subclass__ skips Ref rewrite
  +--> schema remains object-shaped / normal JSON Schema $defs
  +--> proto_schema nested stage adds semantic nested metadata
  +--> migration creates pipeline_options TEXT
  +--> create/update JSON-serializes PipelineOptions
  +--> get/list JSON-decodes before Pydantic rebuilds PipelineOptions
```

---

## 💻 Minimal Implementation Shape

### 1. Add the class flag default

File: `packages/n3tx-core/src/n3tx_core/models/proto_model.py`

Add a default class variable near other framework flags:

```py
__nested__: ClassVar[bool] = False
```

Add a simple guard in `__init_subclass__()`:

```py
if getattr(cls, '__nested__', False) and getattr(cls, '__tablename__', None):
    raise ValueError(f'{cls.__name__} cannot declare both __nested__ and __tablename__')
```

### 2. Skip auto-Ref rewrite for nested targets

File: `packages/n3tx-core/src/n3tx_core/models/proto_model.py`

Keep the condition local and readable. No broad helper needed.

```diff
- if isinstance(annotation, type) and issubclass(annotation, BaseModel) and annotation != cls:
+ if (
+     isinstance(annotation, type)
+     and issubclass(annotation, BaseModel)
+     and annotation != cls
+     and not getattr(annotation, '__nested__', False)
+ ):
      new_annotations[name] = Ref[annotation]
```

Optional support can be added later if needed. The reported crash is the direct-field case.

### 3. Detect nested fields as JSON fields

File: `packages/n3tx-core/src/n3tx_core/utils/introspection.py`

Add one tiny predicate if it simplifies repeated checks:

```py
def _is_nested_model_type(t) -> bool:
    return isinstance(t, type) and issubclass(t, BaseModel) and bool(getattr(t, '__nested__', False))
```

Then in `get_json_fields()` include:

```py
if _is_nested_model_type(field_type):
    results.append(field_name)
    continue

if origin is list:
    args = get_args(field_type)
    if args and _is_nested_model_type(args[0]):
        results.append(field_name)
        continue
```

Keep existing exclusions for `ListRef[T]` and `ManyToMany[T]`.

### 4. Keep relationship list detection out of nested lists

File: `packages/n3tx-core/src/n3tx_core/utils/introspection.py`

Current fallback treats all `List[BaseModel]` as relationship collections. Narrow it:

```diff
  if origin is list:
      args = get_args(field_type)
-     if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
+     if args and isinstance(args[0], type) and issubclass(args[0], BaseModel) and not getattr(args[0], '__nested__', False):
          results.append((field_name, args[0]))
```

### 5. Serialize nested values structurally

File: `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`

Current `create()` dereferences any `BaseModel` with `.id`. Avoid doing that for nested values:

```diff
- value.id if isinstance(value, BaseModel) and hasattr(value, 'id') else value
+ value.id if isinstance(value, BaseModel) and hasattr(value, 'id') and not getattr(value.__class__, '__nested__', False) else value
```

Update `_coerce_value()` to handle nested model values and nested model lists before the generic dict/list branch:

```py
if isinstance(v, BaseModel):
    return json.dumps(v.model_dump(mode='json'), default=str)

if isinstance(v, list):
    return json.dumps([
        item.model_dump(mode='json') if isinstance(item, BaseModel) else item
        for item in v
    ], default=str)
```

### 6. Create/migrate nested fields as TEXT

File: `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`

Before generic nested `BaseModel -> INTEGER field_id` handling:

```py
if getattr(field_type, '__nested__', False):
    columns.append(f'{field_name} TEXT')
    continue
```

For list fields:

```py
if origin_type is list:
    args = get_args(field_type)
    if args and getattr(args[0], '__nested__', False):
        columns.append(f'{field_name} TEXT')
        continue
```

Mirror this in `migrate_table()`.

### 7. Add a schema extension for nested processing metadata

File: `packages/n3tx-core/src/n3tx_core/models/proto_schema.py`

Use the schema pipeline for semantic nested metadata instead of hard-coding nested detection in each backend/frontend consumer. Add a small core stage before `ui` so later UI/view stages can still override or enrich presentation hints.

The metadata should describe how to process and validate the nested field. UI widget selection is a consumer of that metadata, not the primary contract.

Example stage shape:

```py
def nested(cls, schema: dict) -> dict:
    properties = schema.get('properties', {})
    for field_name, field_info in cls.model_fields.items():
        field_schema = properties.get(field_name)
        if not field_schema:
            continue

        field_type = field_info.annotation
        origin = get_origin(field_type)
        args = get_args(field_type)

        is_nested_object = getattr(field_type, '__nested__', False)
        is_nested_list = origin is list and args and getattr(args[0], '__nested__', False)

        if not (is_nested_object or is_nested_list):
            continue

        nested_model = field_type if is_nested_object else args[0]
        kind = 'array' if is_nested_list else 'object'

        field_schema['nested'] = {
            'enabled': True,
            'kind': kind,
            'model': nested_model.__name__,
            'schema_ref': f"#/$defs/{nested_model.__name__}",
        }
        field_schema.setdefault('ui', {}).setdefault('widget', 'nested')

    return schema
```

Register it in the default core pipeline before `ui`:

```text
base -> strip_hidden -> methods -> defs -> access -> nested -> ui -> metadata
```

Why this belongs in `proto_schema`:

- The backend schema remains the single processing contract.
- Backend validators, route adapters, frontend forms, and widgets can all detect nested semantics from the same field metadata.
- The frontend can select a nested widget from schema metadata without re-deriving model intent.
- Apps can still override widget choice with explicit field-level `json_schema_extra` if needed.

This stage does **not** fix storage or class rewrite behavior; those still belong in `proto_model.py`, `introspection.py`, `sqlite_storage.py`, and `sqlite_migration.py`.

---

## 🧪 TDD Checklist

Create:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_nested_value_models.py
```

### Red tests

1. `test_nested_model_field_is_not_rewritten_to_ref`
2. `test_non_nested_model_field_still_rewrites_to_ref`
3. `test_nested_model_cannot_declare_tablename`
4. `test_nested_model_response_serializes_inline`
5. `test_nested_model_is_json_field`
6. `test_list_of_nested_models_is_json_field`
7. `test_list_of_nested_models_is_not_relationship_field`
8. `test_nested_model_round_trips_through_sqlite`
9. `test_list_of_nested_models_round_trips_through_sqlite`
10. `test_nested_model_update_round_trips_through_sqlite`
11. `test_nested_model_creates_text_column`
12. `test_list_of_nested_models_creates_text_column`
13. `test_ref_annotation_behavior_is_unchanged`
14. `test_listref_behavior_is_unchanged`
15. `test_nested_schema_stage_marks_nested_object_metadata`
16. `test_nested_schema_stage_marks_nested_array_metadata`
17. `test_nested_schema_stage_sets_default_nested_widget`
18. `test_explicit_field_ui_widget_override_wins_for_nested_field`

### Narrow loop

```bash
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_nested_value_models.py -q
```

### Regression checks

```bash
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_json_fields.py -q
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_introspection.py -q
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_sqlite_migration.py -q
cd /workspace && python3 scripts/test-backend.py --suite core -- -q
```

---

## 📚 Docs to Update

- `packages/n3tx-core/docs/storage.md`
  - Document `__nested__ = True` value models as JSON TEXT fields.
  - Clarify `Ref[T]` remains resource-reference-only.
- `packages/n3tx-core/docs/schema-pipeline.md`
  - Document nested value object schema behavior.
- `docs/MODELS.md`
  - Add `__nested__` to model flags.
  - Replace blanket “BaseModel annotations -> Ref[T]” wording.
- `docs/CORE.md`
  - Add embedded nested value models to generated behavior table.

---

## 🎛️ UI Widget / Form Follow-up

Nested value models are a backend storage/schema feature, but they also create a new frontend rendering requirement: object-shaped fields must be displayable and editable without hand-written forms.

### Required UI review

| Area | Check / change |
|---|---|
| `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js` | Verify Formidable can render object fields and `$defs`-backed nested schemas. |
| widget registry | Decide whether `__nested__` fields should auto-map to a dedicated `nested` widget. |
| schema metadata | Use the core `proto_schema` nested stage to expose semantic `nested` metadata and default `ui.widget = nested`. |
| submit serialization | Ensure nested object form controls serialize to `{ field: { ...nestedValues } }`, not flat string values. |
| list serialization | For `list[NestedModel]`, decide first UI behavior: read-only JSON display, editable repeated fieldset, or dedicated array widget. |

### Recommended minimal first UI scope

Keep backend implementation independent and add a targeted UI follow-up after backend tests pass:

1. Confirm nested object schemas render at least as readable JSON/object blocks.
2. Add a `nested` field widget only if Formidable does not already handle object fields cleanly.
3. Defer full editable `list[__nested__]` UX if it requires a larger array-editor component.

### UI tests to add if widget behavior changes

```bash
cd /workspace/tests/frontend && npx vitest run
```

Suggested coverage:

- nested object field renders from schema
- nested object/array detection reads `field_schema.nested`, not duplicated frontend type inference
- nested object field submits structured object payload
- nested list field does not degrade into `[object Object]`
- explicit `ui.widget` override still wins over auto-detected nested widget

---

## ✅ Acceptance Criteria

- `Run(..., pipeline_options=PipelineOptions(...)).model_response()` returns inline JSON and does not crash when `PipelineOptions.__nested__ = True`.
- Nested model fields are not rewritten to `Ref[T]`.
- Non-nested Pydantic/N3TX model fields retain existing auto-Ref behavior.
- `Ref[T]`, `ListRef[T]`, and `ManyToMany[T]` behavior is unchanged.
- Nested object/list fields create and migrate as same-name `TEXT` columns.
- Nested object/list fields round-trip through SQLite create, get, list, and update.
- Nested fields are marked in schema with backend-owned semantic metadata for processing, validation, and UI/widget selection.
- A model declaring both `__nested__ = True` and `__tablename__` fails fast.
- Nested fields have an explicit UI follow-up path: either verified existing Formidable support or a dedicated nested widget plan.
- Docs explain `__nested__` and the reference-vs-value distinction.

---

## 📍 Critical Files

- `packages/n3tx-core/src/n3tx_core/models/proto_model.py`
- `packages/n3tx-core/src/n3tx_core/models/proto_schema.py`
- `packages/n3tx-core/src/n3tx_core/utils/introspection.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`
- `packages/n3tx-core/src/n3tx_core/tests/unit/test_nested_value_models.py`
- `packages/n3tx-core/docs/storage.md`
- `packages/n3tx-core/docs/schema-pipeline.md`
- `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js` *(review/follow-up if UI behavior is not already sufficient)*
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/` *(possible nested widget follow-up)*
- `docs/MODELS.md`
- `docs/CORE.md`

## 📝 Saved Plan

- `.project/plans/framework-embedded-value-models-reviewed-execution-plan.md`
