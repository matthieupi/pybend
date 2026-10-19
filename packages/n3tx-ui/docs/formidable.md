# Formidable

Formidable converts a **runtime schema plus values** into HTML strings. It does
not fetch entities or persist changes. `NTTItem` and `NTTMethod` supply lifecycle,
event binding and submission. Prefer those components before building an editor.

```text
entity properties / method parameters
  -> normalizeSchema -> ordered/filtered/grouped layout
  -> field widget or type fallback -> HTML string
  -> mounted inputs -> readFormValue -> validateForm -> native save/call
```

## API

Import `{ Formidable }` from `/generators/form.js` in a native app.
An `ntt` input is `{schema, value, ref?, name?}`; obtain schema from NTT or an
entity component, not a duplicated client model declaration.

| Function | Result/purpose |
|---|---|
| `normalizeSchema(schema)` | Common properties shape for entity/method schemas |
| `getForm(ntt, mode='display', attachedMethods={})` | Header plus fields, HTML string |
| `getFields(ntt, mode='display', attachedMethods={})` | Fields only; preferred for method forms |
| `getInput(ntt, key, mode='display')` | One field |
| `getListInput(ntt, key, mode='display')` | Array through list widget / `ntx-list-field` |
| `renderGroupedFields(ntt, fields, groups, mode, attachedMethods={})` | Fieldsets and attached actions |
| `formatDisplayValue(def,key,value)` | Compact display representation; may contain markup |
| `readFormValue(root,ntt)` | Current rendered values, including dotted paths and list fields |
| `validateForm(ntt)` | Array of `{field,message}` errors |
| `validationAttrs(def,isRequired=false)` | HTML validation attribute string |
| `clearFieldErrors(root)` / `showFieldErrors(root,errors)` | Shared inline feedback |
| `clearCache()` | Invalidate role-dependent layout cache |

## Custom form path

The following module creates a standalone editor using an existing NTT entity.
It reuses the backend schema, native reading/validation, and entity update transport.
The host is supplied by the app; call only after the entity is loaded.

```javascript
import { Formidable } from '/generators/form.js';
import { permissions } from '/utils/Permissions.js';

export function mountEditor(host, entity) {
  const context = {schema: entity.schema, value: entity.value, ref: entity.href};
  if (!permissions.canAction(context.schema.access, 'update', context.value)) {
    host.textContent = 'Editing is unavailable.';
    return;
  }
  const form = document.createElement('form');
  form.innerHTML = Formidable.getForm(context, 'edit');
  const save = document.createElement('button');
  save.type = 'submit';
  save.textContent = 'Save';
  form.append(save);
  form.addEventListener('submit', event => {
    event.preventDefault();
    const patch = Formidable.readFormValue(form, context);
    const errors = Formidable.validateForm({
      schema: context.schema, value: {...context.value, ...patch},
    });
    Formidable.showFieldErrors(form, errors);
    if (!errors.length) entity.call('UPDATE', patch);
  });
  host.replaceChildren(form);
}
```

This demonstrates form assembly, not a complete async save-status UI. `call()`
dispatches a TX, not a promise of persistence. Use `NTTItem` for its native edit/error
workflow, or separately subscribe to responses in a full custom editor. Before
mounting, initialize permissions as in the [frontend shell](../../../docs/frontend/ARCHITECTURE.md).

**HTML safety:** current Formidable branches interpolate header/field/schema text
into HTML. It is **not a general sanitizer**. Do not render untrusted HTML-bearing
content through this snippet without an application-reviewed sanitization policy.
Use text-only DOM rendering for untrusted display content; the custom renderer
example in [components](components.md) demonstrates that boundary. This is an
existing implementation limitation, not a claim that schema validation prevents XSS.

## Layout and method parameters

- `ui.field_order` orders known fields; remaining fields append.
- Entity header fields (`name`, `title`, `id`, `description`) are excluded from
  the body layout. Header rendering follows a separate path; do not assume body
  filtering protects header values.
- `ui.groups` creates fieldsets; ungrouped fields follow them.
- Body fields are filtered by `ui.display`, view permissions and, in edit mode,
  `ui.protected`. Direct field rendering downgrades non-editable fields to display.
- Method `parameters` normalize to `properties` without entity header filtering.
  Top-level `$ref` parameters expand to dotted keys such as `comment.text`, using
  referenced required fields (or all fields if no required list exists).
- Nullable `anyOf` resolves only when exactly one non-null alternative remains;
  multi-type unions throw rather than guessing a renderer.
- Layout cache keys include schema name/title, form kind, mode and role—not the
  full schema contents. Clear it when replacing schema or changing auth state.

For method input HTML, obtain the existing method definition and include model
`$defs` when needed:

```javascript
// modelClass is an already-loaded NTT DynamicClass.
const method = modelClass.schema.methods.comment;
const html = Formidable.getFields({
  schema: {...method, __name__: `${modelClass.name}.comment`, $defs: modelClass.schema.$defs},
  value: {},
}, 'edit');
```

## Validation boundaries

| Checked client-side | Limit |
|---|---|
| Required, string length/pattern | Not all JSON Schema/Pydantic validators are implemented |
| Numeric inclusive/exclusive bounds | HTML `min`/`max` alone cannot encode strict inequality |
| Required arrays | Empty-array check, not full item/collection validation |
| Registered widget validation | Widget-specific; not backend enforcement |

Hidden/protected/readOnly fields and object validation are skipped. Server
validation is authoritative; a successful client check does not guarantee a write.

## Arrays and references

`getListInput()` delegates to `ntx-list-field`. The default visible count is 8;
`visible-count`, `ui.visible_count` or `ui.visibleCount` can override it. `all`/`none`
disable collapsing. Scalar edits emit composed, bubbling `field-change` events.

**Destructive edge:** for model-reference rows, the current Remove handler both
updates local membership and sends **DELETE to the referenced entity URL** when
the parent entity is cached. It is not a safe unlink-only operation. Reference
picker creation can also perform requests before the parent save. Do not promise
that Cancel reverses these effects; use an explicit domain action for unlinking
shared records until the application has verified the intended path.

Backend updates do store supplied collection fields as replacements. The old
claim that arrays require immediate join/unjoin requests is not the current
storage contract. See [CRUD updates](../../../docs/API_CRUD_ENDPOINTS.md#update-resource).

## Sources and verification

[Formidable source](../src/n3tx_ui/static/generators/form.js),
[list-field source](../src/n3tx_ui/static/components/ntx-list-field.js),
[generator tests](../../../tests/frontend/tests/generators/),
[form/entity integration](../../../tests/frontend/tests/integration/form-entity-binding.test.js).
See [widgets](widgets.md) for HTML serialization constraints.
