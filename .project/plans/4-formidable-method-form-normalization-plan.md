# Formidable Method Form Normalization Plan

## Recommendation

Adopt a **contract-first simplification** for method forms:

1. Normalize method schemas once in `Formidable` into a canonical form spec.
2. Use that same spec for **rendering**, **value reading**, **validation**, and **field error display**.
3. Reduce `ntx-method` to a thin shell that chooses layout and invokes the method.

This is the highest-value entropy reduction because it removes the remaining split between:

- schema normalization in `ntx-method`
- rendering in `Formidable`
- submit-time DOM parsing in `ntx-method`
- incomplete validation parity for expanded `$ref` method params

## Current State

Today the method-form flow is:

```text
raw method schema
  -> ntx-method.#formLike()
     -> Formidable.getFields()
     -> ntx-method.collectFormValue()
     -> Formidable.validateForm()
```

### Main problems

1. `form.js` still branches on `schema.properties || schema.parameters` in multiple places.
2. `ntx-method.collectFormValue()` is DOM-shape-driven and weak for:
   - `ntx-list-field`
   - custom widgets
   - any non-native control
3. Top-level `$ref` method params are rendered as expanded nested fields, but validation still reasons about flatter/raw definitions.
4. `ntx-method` silently returns on validation failure instead of showing field errors.
5. `#formLike()` is overloaded with schema adaptation, inline placeholder policy, compact label suppression, and textarea override behavior.

## Target State

Move to this architecture:

```text
raw entity/method schema
  -> Formidable.normalizeSpec(...)
     -> Formidable.getFields(...)
     -> Formidable.readFormValue(...)
     -> Formidable.validateValue(...)
     -> Formidable.showFieldErrors(...)
```

Then `ntx-method` becomes responsible only for:

- resolving the method
- choosing layout (`button`, `fieldset`, `inline`)
- invoking `caller.call(...)`
- resetting local state after submit
- rendering method responses

## Design Principles

### 1. One internal schema shape

Externally, `Formidable` should still accept both:

- entity schemas via `schema.properties`
- method schemas via `schema.parameters`

Internally, everything should operate on a canonical normalized shape with:

- `schema.properties`
- `required`
- `$defs`
- `ui`
- `kind: 'entity' | 'method'`

### 2. Expand top-level `$ref` during normalization

Do not keep `$ref` expansion as a rendering-only special case.

The same expanded field entries must be used for:

- render
- read
- validate
- error reporting
- payload reconstruction

### 3. Read values by normalized field spec, not raw DOM heuristics

The collector should operate on canonical field entries and support:

- native inputs
- widget wrappers
- `ntx-list-field`
- dotted nested keys for expanded `$ref`

### 4. Reuse field error UI

`ntx-item` already has good field error highlighting behavior. That should move into `Formidable` and be reused by `ntx-method`.

## Proposed Canonical Form Spec

Minimal recommended shape:

```js
{
  kind: 'entity' | 'method',
  schema: {
    ...schema,
    properties: { ...normalizedFields },
    required: [...normalizedRequired],
    $defs: { ...defs },
    ui: { ...ui },
  },
  entries: [
    {
      path: 'comment.text',
      key: 'comment.text',
      sourceKey: 'comment',
      def: { type: 'string', title: 'Text', ui: {...} },
      required: true,
      expandedFromRef: true,
    },
    {
      path: 'use_js',
      key: 'use_js',
      sourceKey: 'use_js',
      def: { type: 'boolean', title: 'Use JS' },
      required: false,
      expandedFromRef: false,
    }
  ],
  defs: { ...schema.$defs },
  ui: { ...schema.ui },
  omitHeaderFields: kind === 'entity',
}
```

This spec is intentionally plain data, not a class hierarchy.

## File Scope

### Primary implementation files

- `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js`

### Tests

- `tests/frontend/tests/generators/form.test.js`
- `tests/frontend/tests/components/ntx-method.test.js`
- `tests/frontend/tests/components/ntx-list-field.test.js`

### Docs

- `packages/n3tx-ui/docs/formidable.md`

## Implementation Plan

---

## Phase 1 — RED: lock the missing behavior with tests

### Objective

Add failing tests for the current weak spots before changing internals.

### 1.1 `Formidable` normalized method behavior

File:

- `tests/frontend/tests/generators/form.test.js`

Add tests for:

1. method schema via `parameters` and entity schema via `properties` render the same field types for:
   - boolean
   - array
   - top-level `$ref`
2. expanded `$ref` required subfields are validated the same way they are rendered
3. `validateValue()` / normalized validation catches missing nested required fields like:
   - `comment.text`

### 1.2 `ntx-method` submission parity

File:

- `tests/frontend/tests/components/ntx-method.test.js`

Add tests for:

1. expanded `$ref` missing required nested field blocks submit
2. validation errors are shown in the method form DOM
3. method array param submission includes updated `ntx-list-field` values
4. compact inline still works for single simple field methods after normalization

### 1.3 `ntx-list-field` typing parity

File:

- `tests/frontend/tests/components/ntx-list-field.test.js`

Add tests for:

1. scalar number arrays emit numbers/null
2. integer arrays emit integers/null
3. boolean arrays emit booleans
4. `field-change.detail.value` reflects current edited array value

---

## Phase 2 — GREEN: add canonical normalization in `Formidable`

### Objective

Introduce one normalization entrypoint and make internal helpers consume the normalized spec.

### File

- `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js`

### Add

```js
function normalizeSpec(schema, opts = {}) {
  const kind = schema?.parameters && !schema?.properties ? 'method' : 'entity';
  const rawFields = schema?.properties || schema?.parameters || {};
  const defs = opts.defs || schema?.$defs || {};
  const ui = schema?.ui || {};
  const normalized = expandTopLevelRefs(rawFields, defs, opts);

  return {
    kind,
    schema: {
      ...schema,
      properties: normalized.properties,
      required: normalized.required,
      $defs: defs,
      ui,
    },
    entries: normalized.entries,
    defs,
    ui,
    omitHeaderFields: kind === 'entity',
  };
}
```

### Notes

- Do **not** mutate the incoming schema.
- Preserve public compatibility: callers may still pass `schema.parameters`.
- Centralize the method/entity distinction into `kind` / `omitHeaderFields`, not scattered shape checks.

---

## Phase 3 — GREEN: move top-level `$ref` expansion into normalization

### Objective

Make expanded `$ref` behavior a schema contract, not a rendering special case.

### Current rule to preserve

For a top-level method param like:

```js
comment: { type: '$ref', $ref: '#/$defs/Comment' }
```

if `Comment.required` exists, render/validate only those required subfields.

If `required` is empty, fall back to all subfields.

### Add helper

```js
function expandTopLevelRefs(fields, defs, opts = {}) {
  // returns { properties, required, entries }
}
```

Representative output:

```js
{
  properties: {
    'comment.text': { type: 'string', title: 'Text', ui: {...} },
  },
  required: ['comment.text'],
  entries: [
    { path: 'comment.text', sourceKey: 'comment', expandedFromRef: true, ... }
  ]
}
```

### Why

This aligns:

- render
- read
- validate
- error field mapping

on the same expanded field set.

---

## Phase 4 — GREEN: refactor Formidable helpers to consume normalized spec

### Objective

Collapse most `properties || parameters` branching.

### Update `_getLayout()`

Current:

```js
function _getLayout(schema, mode) { ... }
```

Target:

```js
function _getLayout(spec, mode) {
  const schema = spec.schema;
  const fields = schema.properties || {};
  ...
  if (spec.omitHeaderFields && _headerFieldSet.has(key)) return false;
}
```

### Update `getFields()`

Normalize first:

```js
const spec = ntt.spec || normalizeSpec(ntt.schema, ntt.normalizeOpts || {});
```

Then render from `spec`.

### Update `getInput()`

- operate on `spec.schema.properties`
- remove method/entity shape detection
- keep only the presentation distinction that depends on `spec.kind`

### Update `getListInput()`

- read `spec.schema.properties[key]`

### Update validation entrypoint

Either:

```js
function validateValue(spec, value)
```

or preserve:

```js
function validateForm(ntt)
```

but internally normalize first and validate against canonical properties.

### Recommendation

Keep `validateForm(ntt)` for backwards compatibility, but add and prefer:

```js
function validateValue(spec, value)
```

---

## Phase 5 — GREEN: add canonical form reading in `Formidable`

### Objective

Remove bespoke DOM parsing from `ntx-method`.

### Add helpers

```js
function readFieldValue(el, entry) {
  // checkbox, number/integer, object, select, textarea, widget, list-field
}

function assignPath(target, path, value) {
  ...
}

function collapseExpandedRefs(value, spec) {
  // e.g. { 'comment.text': 'hi' } -> { comment: { text: 'hi' } }
}

function readFormValue(root, spec) {
  const result = {};
  for (const entry of spec.entries) {
    const el = root.querySelector(`[data-key="${entry.path}"]`);
    if (!el) continue;
    assignPath(result, entry.path, readFieldValue(el, entry));
  }
  return collapseExpandedRefs(result, spec);
}
```

### Required support

- `input`, `textarea`, `select`
- checkbox booleans
- number/integer coercion
- object JSON parsing
- `widget-edit-wrapper`
- `ntx-list-field`

### `ntx-list-field` support recommendation

Support both:

1. reading current encoded `value` attribute
2. honoring `field-change`-driven current state if present

The field reader should not assume all values live in native child inputs.

---

## Phase 6 — GREEN: move field error rendering into `Formidable`

### Objective

Unify error display for item edit forms and method forms.

### Add

```js
function clearFieldErrors(root) { ... }
function showFieldErrors(root, errors) { ... }
```

### Reuse existing behavior from `ntx-item`

Preserve current logic:

- clear `.field-error`
- remove `.error-message`
- locate target by `[data-key="field"]`
- highlight `.widget-edit-wrapper` when applicable
- insert error message after highlighted node

### Then update

- `ntx-item.showFieldErrors()` to delegate to `Formidable`
- `ntx-method` to show validation errors before returning from submit

---

## Phase 7 — GREEN: simplify `ntx-method` around the normalized spec

### Objective

Make `ntx-method` a thin orchestration shell.

### File

- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js`

### Replace `#formLike()` with `#getFormSpec()`

Current problem:

- `#formLike()` builds a schema-like object and mixes rendering policy into it.

Target:

```js
#getFormSpec({ inline = false, compact = false } = {}) {
  return Formidable.normalizeSpec(this.methodSchema || this.schema || {}, {
    defs: this.proto?.schema?.$defs || {},
    placeholder: inline ? this.placeholderText : '',
    compact,
    widgetOverride: this.widgetOverride,
    name: this.method || this.label || 'method',
  });
}
```

### Replace `collectFormValue()` path

Current:

```js
const nextValue = this.collectFormValue();
const formLike = this.#formLike(nextValue);
const errors = Formidable.validateForm(formLike);
```

Target:

```js
const spec = this.#getFormSpec();
const nextValue = Formidable.readFormValue(this.shadowRoot, spec);
const errors = Formidable.validateValue(spec, nextValue);
if (errors.length > 0) {
  Formidable.showFieldErrors(this.shadowRoot, errors);
  return;
}
```

### Remove bespoke helpers

Delete from `ntx-method`:

- `collectFormValue()`
- `#assignPath()`

### Keep in `ntx-method`

- method resolution
- layout selection
- compact inline policy
- response handling
- reset behavior

---

## Phase 8 — GREEN: keep inline compact behavior, but make it spec-driven

### Objective

Preserve the current compact UX without reintroducing custom field rendering.

### Recommended rule

Compact inline applies only when:

- exactly one param
- not `$ref`
- not `array`
- not `object`
- no textarea override

That policy can stay in `ntx-method`, but rendering should still use the normalized spec through `Formidable.getInput(...)` or `Formidable.getFields(...)`.

### Important

Do not let compact inline create a second schema contract.

It is a presentation mode only.

---

## Phase 9 — REFACTOR: docs and cleanup

### Update docs

File:

- `packages/n3tx-ui/docs/formidable.md`

Document:

- normalized internal contract
- public support for both `properties` and `parameters`
- `readFormValue()`
- `validateValue()`
- `showFieldErrors()`
- top-level `$ref` expansion rule for method forms

### Remove outdated language

The docs should stop implying that method forms are special-cased throughout the renderer. After this refactor they should be treated as a normalized variant at the boundary.

## Test Plan

### `tests/frontend/tests/generators/form.test.js`

Add:

1. method schema and entity schema render equivalent boolean fields
2. method schema and entity schema render equivalent array fields
3. top-level `$ref` expands into normalized nested required fields
4. `validateValue()` catches missing `comment.text`
5. `readFormValue()` reads checkbox/number/object correctly
6. `readFormValue()` reads current `ntx-list-field` value

### `tests/frontend/tests/components/ntx-method.test.js`

Add:

1. invalid expanded `$ref` blocks submit
2. method form shows validation errors in DOM
3. array/list-field method param submits updated array payload
4. compact inline still submits correctly
5. inline reset still clears state after successful call

### `tests/frontend/tests/components/ntx-list-field.test.js`

Add:

1. scalar number array emits typed values
2. scalar integer array emits typed values
3. scalar boolean array emits typed values
4. current emitted value matches encoded `value` attribute after edits

## Verification Commands

Focused:

```bash
cd /workspace/tests/frontend && npx vitest run tests/generators/form.test.js tests/components/ntx-method.test.js tests/components/ntx-list-field.test.js
```

Broader:

```bash
cd /workspace/tests/frontend && npx vitest run
```

## Risks and Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Cache drift | `_getLayout()` currently caches raw schema assumptions | Cache on normalized spec identity/name + mode + role |
| `$ref` behavior changes | expansion rule is currently implicit | codify required-only-else-all behavior in tests |
| Widget/list-field reading regressions | non-native fields do not expose simple `.value` | explicitly support widget wrappers and `ntx-list-field` in `readFieldValue()` |
| Over-abstraction | too many adapters can increase complexity | keep one plain normalized spec, not classes or layered adapters |
| Error UI divergence | `ntx-item` and `ntx-method` can drift | centralize `showFieldErrors()` in `Formidable` |

## Recommended Execution Order

1. Add failing tests for list-field submission and expanded `$ref` validation parity
2. Introduce `normalizeSpec()`
3. Move `$ref` expansion into normalization
4. Refactor render helpers to consume normalized spec
5. Add `readFormValue()` and `validateValue()`
6. Switch `ntx-method` to normalized spec
7. Move field error rendering into `Formidable`
8. Run focused tests, then broader frontend verification
9. Update `formidable.md`

## Deliverable Summary

This simplification wave is complete when:

- `Formidable` internally operates on one canonical normalized form spec
- method schema `parameters` are normalized once at the boundary
- top-level `$ref` expansion is shared across render/read/validate/error mapping
- `ntx-method` no longer owns bespoke DOM collection logic
- method forms can submit `ntx-list-field` values correctly
- method validation errors are visible in the UI
- focused frontend tests pass
