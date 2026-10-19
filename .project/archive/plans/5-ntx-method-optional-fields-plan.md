# ntx-method optional/default field disclosure plan

## ✅ Recommendation

Implement this as a **frontend-only change in `ntx-method` + Formidable**, with **no backend schema change in phase 1**.

Why:

- The current backend already tells the frontend which method params are `required`.
- In the current Python method signature model, a non-required param is effectively a param with a default.
- The requested UX can be delivered by hiding non-required method params by default, showing an expand control, and treating the zero-visible-fields case as a button-first action.

Keep backend changes out of the first pass. Only add explicit serialized defaults later if we decide expanded forms should be prefilled with exact Python default values rather than omitted from payload.

## 📍 Current state

- `ProtoModel.__n3tx_methods_json_signature__()` emits method schema with `parameters` and `required`, but **not actual default values**.
- `Formidable.normalizeSchema()` already expands top-level `$ref` method params and only renders required nested fields when a referenced schema has a `required` list.
- `Formidable._getLayout()` filters hidden/protected/inaccessible fields, but it does **not** distinguish “primary” vs “optional/defaulted” method fields.
- `ntx-method` chooses one of three layouts: `fieldset`, `inline`, `button`.
- `ntx-method` currently falls back to raw method names for labels.
- `ntx-item` standalone methods do not pass `button-label`, so many method buttons still say `Run` unless the attached-method path provides `ui.button_label`.

## 🎯 Target state

For every non-button `<ntx-method>`:

1. Show only **required** method inputs by default.
2. Hide all **non-required/defaulted** inputs behind a disclosure control.
3. If there are **zero visible inputs by default**, render a **button-first** view with the method name as the label.
4. Use a humanized fallback label when needed: `fetch_source` -> `fetch source`.
5. Let the user expand to reveal optional/defaulted fields, edit them, then submit.

## 🗺️ Intended flow

```text
backend method schema
  -> parameters + required
  -> ntx-method resolves methodSchema
  -> Formidable splits fields into:
       primary = required
       optional = non-required
  -> ntx-method renders:
       primary fields
       optional disclosure button (if any)
       submit button

zero-primary case:
  -> no form shown initially
  -> labeled action button shown
  -> optional disclosure reveals full form
```

## Implementation slices

| Slice | Change | Why |
|---|---|---|
| 1 | Add method-field partitioning helper in Formidable | Keep schema logic centralized |
| 2 | Teach `ntx-method` to render collapsed optional fields | Add the requested UX without changing entity forms |
| 3 | Add humanized label fallback + standalone `button-label` plumbing | Make zero-field methods readable |
| 4 | Add CSS for disclosure/button-first states | Keep behavior visually coherent |
| 5 | Add focused unit tests | Lock behavior before later refinements |

## Detailed plan

### 1) Add a method-only field partition API in Formidable

Add a small helper next to `_getLayout()` that reuses normalized schema and returns two buckets for method forms:

- `primaryFields`: required fields
- `optionalFields`: renderable but non-required fields

Recommended shape:

```js
function getMethodFieldLayout(schema, mode = 'edit') {
  const normalized = normalizeSchema(schema);
  const { renderableFields } = _getLayout(normalized, mode);
  const required = new Set(normalized.required || []);

  return {
    primaryFields: renderableFields.filter((key) => required.has(key)),
    optionalFields: renderableFields.filter((key) => !required.has(key)),
  };
}
```

Notes:

- Gate this to method schemas only; entity forms must stay unchanged.
- Keep `_getLayout()` generic and cacheable.
- Reuse current `$ref` normalization behavior so nested optional fields stay in the optional bucket automatically.

### 2) Make `ntx-method` disclosure-aware

Add component state for optional field expansion:

- `this.optionalExpanded = false`

Reset it conservatively:

- on initial load when method/model/uuid changes
- after successful inline auto-reset

Render rules:

- Compute `primaryFields` + `optionalFields` from Formidable.
- If `primaryFields.length > 0`, render the form as today, but append an optional-fields disclosure if `optionalFields.length > 0`.
- If `primaryFields.length === 0 && optionalFields.length > 0`, render a **button-first** surface:
  - primary action button only
  - secondary “show options” disclosure
  - expanded panel reveals the optional fields + submit button
- If there are no params at all, preserve the simple action button behavior.

Representative shape inside `#renderFormShell()`:

```js
const { primaryFields, optionalFields } = Formidable.getMethodFieldLayout(this.#formLike().schema, 'edit');
const hasPrimary = primaryFields.length > 0;
const hasOptional = optionalFields.length > 0;
const showForm = hasPrimary || this.optionalExpanded;
```

Then render one of two shells:

```js
if (!hasPrimary && hasOptional && !this.optionalExpanded) {
  // button-first collapsed state
}

// normal form state
```

### 3) Separate “method label” from “submit button label”

Today `label` is used for legends/titles, and `buttonLabel` defaults to `Run`.

Adjust the fallback contract:

- `label`: method title or humanized method name
- `buttonLabel`: explicit `button-label` attr or schema UI value or `Run`
- In the **zero-primary button-first case**, the visible button text should default to `label`, not `buttonLabel`

Recommended helper:

```js
function humanizeMethodName(name = '') {
  return String(name).replace(/_/g, ' ');
}
```

Usage:

```js
this.label = this.getAttribute('label') || humanizeMethodName(this.method);
```

This should also be applied in the standalone method stamping path so the attr passed into `<ntx-method>` is already improved.

### 4) Fix standalone method attribute plumbing in `ntx-item`

Update `#standaloneMethodsHtml()` so standalone methods pass the same useful attrs that attached methods already pass:

```html
button-label="${ui.button_label || 'Run'}"
placeholder="${ui.placeholder || ''}"
widget="${ui.widget || ''}"
label="${def.title || humanizedName}"
```

This removes the current attached/standalone inconsistency and lets schema UI drive both paths.

### 5) Add disclosure markup and CSS

Add lightweight markup rather than inventing a new component.

Recommended DOM shape:

```html
<div class="method-optional-toggle-row">
  <button type="button" class="method-optional-toggle">Show options</button>
</div>

<div class="method-optional-panel" hidden>
  ...optional fields...
</div>
```

For the zero-primary collapsed case:

```html
<div class="method-collapsed-actions">
  <button type="button" class="method-btn method-btn--labeled">Fetch</button>
  <button type="button" class="method-optional-toggle">Show options</button>
</div>
```

Important behavior:

- The primary action button should call the method immediately with omitted optional payload.
- Expanding optional fields should not auto-submit.
- Hidden optional fields remain absent from `readFormValue()`, which correctly lets backend defaults apply.

### 6) Keep phase 1 backend contract unchanged

Do **not** change `ProtoModel.__n3tx_methods_json_signature__()` in the first pass.

Current mapping is sufficient for the requested UX:

- `required` => shown by default
- not in `required` => hidden behind disclosure

Only consider a later backend enhancement if you want:

- exact default values serialized into schema
- expanded optional fields prefilled from Python defaults
- param-level UI metadata richer than current type-based emission

## 💻 Code-shape preview

### `form.js`

```diff
+ function getMethodFieldLayout(schema, mode = 'edit') {
+   const normalized = normalizeSchema(schema);
+   if (normalized.__formKind !== 'method') {
+     return { primaryFields: _getLayout(normalized, mode).renderableFields, optionalFields: [] };
+   }
+   const { renderableFields } = _getLayout(normalized, mode);
+   const required = new Set(normalized.required || []);
+   return {
+     primaryFields: renderableFields.filter((key) => required.has(key)),
+     optionalFields: renderableFields.filter((key) => !required.has(key)),
+   };
+ }
```

### `ntx-method.js`

```diff
  constructor() {
    ...
+   this.optionalExpanded = false;
  }

  #readAttrs() {
    ...
-   this.label = this.getAttribute('label') || this.method;
+   this.label = this.getAttribute('label') || humanizeMethodName(this.method);
  }

  #renderFormShell({ inline = false } = {}) {
+   const formLike = this.#formLike();
+   const { primaryFields, optionalFields } = Formidable.getMethodFieldLayout(formLike.schema, 'edit');
+   const hasPrimary = primaryFields.length > 0;
+   const hasOptional = optionalFields.length > 0;
+   const showCollapsedAction = !hasPrimary && hasOptional && !this.optionalExpanded;

+   if (showCollapsedAction) {
+     // render labeled method button + show options disclosure
+   }

    ...
  }
```

### `ntx-item.js`

```diff
  #standaloneMethodsHtml(methods) {
    return Object.entries(methods).map(([name, def]) => {
+     const humanized = name.replace(/_/g, ' ');
      const label = def.title || name;
      const ui = def.ui || {};
      ...
+       placeholder="${ui.placeholder || ''}"
+       button-label="${ui.button_label || 'Run'}"
+       widget="${ui.widget || ''}"
-       label="${label}">
+       label="${def.title || humanized}">
      </${tag}>
    `;
  }
```

## Risks and trade-offs

| Risk | Impact | Mitigation |
|---|---|---|
| Optional/default distinction is inferred from `required`, not actual serialized defaults | Fine for current Python signature model, limited for future richer schemas | Keep backend untouched in phase 1; document this assumption |
| Shared Formidable logic could accidentally affect entity forms | Broader UI regressions | Add a method-only helper instead of changing entity layout behavior |
| Zero-primary methods now become button-first | Minor visual change | Limit that behavior to method schemas with only optional params |
| Label humanization may diverge from title-based schemas | Inconsistent copy | Always prefer schema title/attr label first, humanize only as fallback |

## Verification plan

### Unit tests

Extend `tests/frontend/tests/components/ntx-method.test.js` with cases for:

1. method with one optional boolean only (`use_js: bool = False`) renders button-first by default
2. collapsed state uses humanized method label when no explicit title is present
3. clicking “show options” reveals hidden optional fields
4. clicking primary button in collapsed state submits `{}`
5. after expansion, edited optional fields are included in payload
6. standalone methods receive `button-label` and placeholder plumbing from `ntx-item`

Extend `tests/frontend/tests/generators/form.test.js` with cases for:

1. `getMethodFieldLayout()` splits required vs optional method fields correctly
2. `$ref` method params still put only required nested fields in the primary bucket

### Browser verification

Use the Veille source fetch case as the acceptance scenario:

- open a Source item
- verify `fetch(use_js=False)` shows only a labeled method button initially
- expand options
- verify `use_js` checkbox appears
- submit collapsed and expanded versions

## Acceptance criteria

- A method whose params are all optional/defaulted shows no form by default.
- That method still exposes an explicit affordance to reveal all params.
- Required params remain visible immediately.
- Hidden optional params are omitted from payload unless expanded and edited.
- Button-first methods use the humanized method name when no better label exists.
- Attached and standalone method rendering paths honor the same schema UI knobs.

## Critical Files for Implementation

- packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js
- packages/n3tx-ui/src/n3tx_ui/static/generators/form.js
- packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js
- packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css
- tests/frontend/tests/components/ntx-method.test.js

## Saved Plan

- `.project/plans/ntx-method-optional-fields-plan.md`
