# Formidable (Form Generator)

> Part of [n3tx-ui](../README.md)

## What This Covers

The `Formidable` module in `generators/form.js`: schema-driven form generation, field rendering, validation, and layout caching. Covers the full rendering pipeline from schema properties to HTML output.

## Architecture

```
Schema arrives (via DESCRIBE or define())
  |
  v
_getLayout(schema, mode)          -- cached per schema+mode+role
  |  Computes field order (ui.field_order + remaining keys)
  |  Filters by: not header field, ui.display !== false,
  |              not protected (in edit mode), permissions.canView()
  |
  v
getForm(ntt, mode, attachedMethods)
  |
  +-- getHeader(ntt, mode)         -- h2/input for name/title + description
  |
  +-- getFields(ntt, mode, attachedMethods)
  |     Headerless field/body renderer
  |     Accepts both schema.properties and schema.parameters
  |
  +-- renderGroupedFields(...)     -- if schema.ui.groups defined
  |     Wraps fields in <fieldset> with <legend>
  |     Injects attached methods after their target field
  |
  +-- getInput(ntt, key, mode)     -- per-field rendering
        |
        +-- Widget dispatch first: getWidgetForField(def)
        |     If widget found + def.ui.widget set: widget.display/edit
        |     Wraps in .widget-display-wrapper or .widget-edit-wrapper
        |
        +-- Type dispatch fallback:
              string -> input[text] / inline label-value display,
              number/integer -> input[number] / bold single-line inline display,
              boolean -> checkbox, array -> getListInput(),
              $ref -> child component, enum -> select/pill,
              object -> textarea/kv-display, selfref -> parent ID
```

## Interface

```javascript
export const Formidable = {
    // Generate complete form HTML
    getForm(ntt, mode = 'display', attachedMethods = {})
    // ntt: { schema, value, ref?, name? }
    // mode: 'display' | 'edit'
    // Returns: HTML string

    // Generate fields only (no header)
    getFields(ntt, mode = 'display', attachedMethods = {})
    // Accepts both entity schemas (schema.properties)
    // and method schemas (schema.parameters)
    // Returns: HTML string

    // Generate single field
    getInput(ntt, key, mode = 'display')
    // Returns: HTML string

    // Generate list/array field
    getListInput(ntt, key, mode = 'display')
    // Returns: HTML string with nested child components

    // Render grouped fields with fieldsets
    renderGroupedFields(ntt, fields, groups, mode, attachedMethods)
    // Returns: HTML string

    // Format value for surgical update patches
    formatDisplayValue(def, key, value)
    // Returns: string (handles widgets, enums, refs, objects)

    // Client-side validation against schema constraints
    validateForm(ntt)
    // ntt: { schema, value }
    // Returns: [{field, message}] -- empty = valid

    // Build HTML5 validation attribute string
    validationAttrs(def, isRequired = false)
    // Returns: string like ' required minlength="3" max="100"'

    // Clear layout cache (call on login/logout)
    clearCache()
}
```

### validateForm checks

| Check | Applies to | Source |
|-------|-----------|--------|
| Required | all fields in `schema.required` | empty/null/undefined |
| minLength / maxLength | strings | `def.minLength`, `def.maxLength` |
| pattern | strings | `def.pattern` (RegExp) |
| minimum / maximum | numbers | `def.minimum`, `def.maximum` |
| exclusiveMinimum / exclusiveMaximum | numbers | strict bounds |
| Widget validation | fields with `ui.widget` | `widget.validate()` |

Skipped: hidden (`ui.display: false`), protected (`ui.protected`), readOnly, array, object fields.

## Usage Patterns

### Schema-driven form in a custom component

```javascript
import { Formidable } from '../generators/form.js';

class MyComponent extends NTTElement {
    render() {
        const html = Formidable.getForm(
            { schema: this.schema, value: this.value, ref: this.ref },
            this.mode
        );
        this.shadowRoot.innerHTML = `<div class="card">${html}</div>`;
    }
}
```

### Method parameter rendering

`getFields()` is the intended entrypoint for rendering method inputs inside
components like `<ntx-method>`. It accepts method schemas directly:

```javascript
const html = Formidable.getFields({
    schema: {
        __name__: 'Source.fetch',
        parameters: {
            use_js: { type: 'boolean', title: 'Use JS' },
        },
        required: [],
        $defs: {},
    },
    value: { use_js: false },
    name: 'fetch',
}, 'edit');
```

This reuses the same schema-aware rendering path as entity forms, so boolean,
array, enum, and widget-backed method params render consistently.

### Validation before save

```javascript
toggleMode() {
    if (this.mode === 'edit') {
        const errors = Formidable.validateForm(this);
        if (errors.length > 0) {
            this.showFieldErrors(errors);
            return;
        }
        this.save();
    }
    this.mode = this.mode === 'edit' ? 'display' : 'edit';
    this.render();
}
```

### Attached methods

Methods with `ui.attach_to` in their schema render inline after the specified field:

```python
@expose_route('/comment', methods=['POST'], ui={'attach_to': 'comments', 'layout': 'inline'})
def comment(self, comment: Comment) -> str: ...
```

Formidable receives these as `attachedMethods` and injects them after the target field in both grouped and ungrouped layouts.

## Gotchas

- **Layout cache is keyed by `schema.__name__:mode:permissions.role`.** This means the same schema renders differently for different roles (admin sees more fields). Call `Formidable.clearCache()` when the user logs in or out.

- **Header fields (`name`, `title`, `id`, `description`) are filtered from the main field list** by `_getLayout()` and rendered separately by `getHeader()`. If your model has no `name` or `title` field, the header falls back to `schema.name`. The `id` field is always hidden.

- **Method schemas are treated differently from entity schemas for layout.** When a schema uses `parameters` instead of `properties`, `getFields()` renders all method params directly and does not apply the entity header-field filtering for `name`, `title`, `id`, or `description`.

- **Display-mode field rows are split into inline and block layouts.** Plain text, enum, selfref, and numeric values render in a two-column row with a fixed-width label column so values line up across the page. Long labels wrap inside that column. Textarea, object, ref, and array-style content stay block-stacked under their labels.

- **Edit-mode inputs use an underline treatment.** Formidable's default edit controls use a lighter single bottom border instead of a full outlined box, so edit mode reads as active without overpowering the item layout. Array/list fields follow the same treatment through `<ntx-list-field>`.

- **Array fields now route through the dedicated list-field widget.** `Formidable.getListInput()` delegates array rendering to `<ntx-list-field>`, which owns display/edit UI and `$ref` picker integration. Scalar arrays stage edits locally inside the widget. `$ref` arrays persist membership changes immediately through join/unjoin requests, because generic entity `UPDATE` does not store collection fields.

- **Protected fields use effectiveMode.** Even in edit mode, fields with `ui.protected: true` or where `permissions.canEdit()` returns false are rendered as display-only. The mode is downgraded per-field, not globally, including array/list fields.

- **anyOf resolution.** When a field has `anyOf` (Pydantic optional types), `resolveAnyOf()` strips the null type and uses the remaining definition. If multiple non-null types exist, it throws -- this is a schema design issue, not a form bug.

- **getListInput uses a VISIBLE_COUNT of 2.** Arrays show the first 2 items inline, then collapse the rest into a `.nested-collapsed` div with a "Show N more" button. This matches NTTItem's surgical update logic which expects this DOM structure.

- **Widget wrappers stamp `data-key` and `data-type`** on the editable element so that `handleInputChange()` in NTTItem can process widget-produced inputs identically to plain inputs.
