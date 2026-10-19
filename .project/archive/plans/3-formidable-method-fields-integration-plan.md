# Formidable Method Fields Integration Plan

## Goal

Fix the frontend method-form rendering gap by routing method parameters through `Formidable` instead of `ntx-method`'s manual input renderer.

This should make method params such as `boolean`, `array`, `enum`, `object`, and widget-backed fields render correctly and consistently with entity forms.

## Problem Statement

Today there are two separate rendering paths:

```text
Entity forms   -> Formidable.getForm()
Method forms   -> ntx-method manual rendering
```

This duplication causes schema drift.

Current bug example:

- `Source.fetch(use_js: bool = False)` emits a method parameter schema with `type: "boolean"`
- `ntx-method` renders primitive params with `type="${def.type}"`
- the browser receives `<input type="boolean">`
- invalid HTML input type falls back to a text input

The same structural problem likely affects array params and may affect enum / object / typed coercion paths.

## Architectural Direction

Introduce a new headerless Formidable entrypoint:

```js
Formidable.getFields(nttLike, mode = 'display', attachedMethods = {})
```

This should render field bodies without entity headers and should accept either:

1. entity-style schemas via `schema.properties`
2. method-style schemas via `schema.parameters`

After this, `ntx-method` should delegate field rendering to `Formidable.getFields(...)` and retain responsibility only for:

- method layout shell (`fieldset`, `inline`, `button`)
- request submission
- response handling
- form reset behavior

## Target End State

After implementation:

- `Formidable.getForm()` remains backward-compatible for entity forms
- `Formidable.getFields()` renders both entity and method fields
- `ntx-method` no longer manually renders primitive method params
- boolean params render as checkboxes
- array params render through the list/widget path
- method submission collects typed values from Formidable-rendered fields
- method form validation reuses `Formidable.validateForm()`

## Files in Scope

### Primary implementation files

- `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js`

### Secondary verification / follow-up files

- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js`
- `packages/n3tx-ui/docs/formidable.md`
- `FRONTEND.md` (only if the documented frontend architecture needs updating)

### Test files

- `tests/frontend/tests/generators/form.test.js`
- `tests/frontend/tests/components/ntx-method.test.js`

Optional browser-level follow-up:

- `tests/frontend/tests/e2e/ntx-method-unit.spec.js`

## Constraints and Invariants

The implementation must preserve:

- existing entity form behavior through `Formidable.getForm()`
- current method shell behaviors (button, fieldset, inline)
- backend method schema contract (`parameters`, `required`, `$defs`)
- attached methods rendering in normal entity forms

The implementation must not introduce a second new rendering system. `getFields()` should be extracted from the current Formidable path, not invented separately.

## Known Gaps to Address

### Gap 1 — Formidable assumes `schema.properties`

Many internal helpers read `schema.properties` directly. These need to be normalized so both `properties` and `parameters` are supported.

### Gap 2 — `ntx-method` assumes `name`-based inputs

`ntx-method` currently reads values from `name` attributes and plain `input` events. Formidable emits fields using `data-key`, `data-type`, and widgets/list-field behavior that do not match this assumption.

### Gap 3 — top-level `$ref` method params

`ntx-method` currently has bespoke support for method parameters whose schema is a top-level `$ref`. Formidable edit-mode rendering does not currently provide an equivalent path.

### Gap 4 — reset and validation behavior

Current `ntx-method` reset logic only clears basic input values. That is insufficient for checkboxes, selects, and widgets. Validation should be upgraded to use `Formidable.validateForm()` once rendering is unified.

## Implementation Plan

---

## Phase 1 — RED: reproduce the bug in method rendering

### Objective

Add failing tests that prove `ntx-method` renders method parameters incorrectly today.

### File

- `tests/frontend/tests/components/ntx-method.test.js`

### Tests to add

#### 1. Boolean parameter renders as checkbox in fieldset mode

Create a method schema like:

```js
methods: {
  fetch: {
    parameters: {
      use_js: { type: 'boolean', title: 'Use JS' }
    },
    required: []
  }
}
```

Assert:

- rendered shadow DOM contains `input[type="checkbox"]`
- rendered shadow DOM does **not** contain `input[type="boolean"]`

#### 2. Array parameter does not fall back to raw primitive input

Method schema like:

```js
parameters: {
  tags: {
    type: 'array',
    items: { type: 'string' }
  }
}
```

Assert:

- no `input[type="array"]`
- rendered output uses the list/widget path or another explicit supported structure

#### Optional 3. Top-level `$ref` method parameter remains supported

If current test coverage or real usage indicates this matters now, add a regression test before migration.

---

## Phase 2 — RED: define the new Formidable contract

### Objective

Write tests for the new `Formidable.getFields(...)` API before implementing it.

### File

- `tests/frontend/tests/generators/form.test.js`

### Tests to add

#### 1. `Formidable.getFields()` renders a method-style boolean param correctly

Pass:

```js
{
  schema: {
    parameters: {
      use_js: { type: 'boolean', title: 'Use JS' }
    }
  },
  value: { use_js: true }
}
```

Assert:

- checkbox is rendered
- checked state is reflected

#### 2. `Formidable.getFields()` also supports normal entity-style schemas

Pass a standard `properties` schema and verify the output remains correct.

#### 3. `Formidable.getFields()` respects required / ordering for method params

Method schema example:

```js
{
  parameters: {
    q: { type: 'string' },
    use_js: { type: 'boolean' }
  },
  required: ['q']
}
```

Assert:

- both fields render
- required field markup is preserved where applicable

#### Optional 4. `$ref` method param rendering

Add if top-level `$ref` support is part of this same implementation wave.

---

## Phase 3 — GREEN: extract `getFields(...)` from Formidable

### Objective

Refactor `form.js` so field rendering is reusable without headers.

### File

- `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js`

### Concrete changes

#### 3.1 Add normalized field definition helper

Add:

```js
function getFieldDefs(schema) {
  return schema?.properties || schema?.parameters || {};
}
```

Then replace hardcoded `schema.properties` lookups where field rendering depends on top-level definitions.

Expected touch points:

- `_getLayout(schema, mode)`
- `getInput(ntt, key, mode)`
- `getListInput(ntt, key, mode)`
- `validateForm(ntt)`

#### 3.2 Introduce `getFields(ntt, mode = 'display', attachedMethods = {})`

Extract the field-body rendering portion of `getForm()` into a new public helper.

Behavior:

- no header rendering
- render fields using the same current body-generation logic
- preserve grouped rendering support when available
- support `schema.parameters` as well as `schema.properties`

#### 3.3 Refactor `getForm()` to delegate to `getFields()`

Current `getForm()` should become:

```js
function getForm(ntt, mode = 'display', attachedMethods = {}) {
  const header = getHeader(ntt, mode);
  const fields = getFields(ntt, mode, attachedMethods);
  return header.concat(fields).join('');
}
```

This preserves entity behavior and ensures there is only one field-rendering path.

#### 3.4 Export `getFields`

Add it to the public `Formidable` export object.

---

## Phase 4 — GREEN: ensure Formidable supports method schemas directly

### Objective

Allow `Formidable.getFields(...)` to work with real method schemas without synthesizing a fake entity schema.

### Supported schema shapes

#### Entity-style

```js
{
  schema: {
    properties: {...},
    required: [...],
    ui: {...}
  },
  value: {...}
}
```

#### Method-style

```js
{
  schema: {
    parameters: {...},
    required: [...],
    ui: {...},
    $defs: {...}
  },
  value: {...}
}
```

### Expected behavior

- field order uses `schema.ui.field_order` if present
- otherwise defaults to the definition key order
- hidden/protected rules still apply consistently
- validation reads from normalized field defs

---

## Phase 5 — GREEN: close Formidable gaps for method params

### Objective

Ensure all important method param types are supported through the shared path.

### Types to verify

- boolean
- array
- enum
- object
- number / integer
- selfref

### Special case: top-level `$ref` params

If a method param is declared as:

```js
{ type: '$ref', $ref: '#/$defs/Foo' }
```

then edit-mode Formidable rendering should preserve current behavior by:

1. resolving the referenced schema from `$defs`
2. identifying required fields on the referenced schema
3. rendering those required fields as dotted keys, e.g.:
   - `input.title`
   - `input.deadline`

This keeps method inputs compatible with the current backend payload shape and avoids a breaking regression.

The implementation should remain intentionally scoped: preserve current method `$ref` behavior without attempting to build a full arbitrary nested object editor.

---

## Phase 6 — GREEN: migrate `ntx-method` fieldset rendering to Formidable

### Objective

Replace manual field rendering in `ntx-method` with `Formidable.getFields(...)`.

### File

- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js`

### Concrete changes

#### 6.1 Import Formidable

Add:

```js
import { Formidable } from '../generators/form.js';
```

#### 6.2 Build a method-form adapter object

Use:

```js
const formLike = {
  schema: this.methodSchema,
  value: this.value,
  name: this.method,
};
```

Because `getFields()` will accept `parameters`, no fake entity schema should be required.

#### 6.3 Replace manual field generation in `renderFieldset()`

Keep the existing fieldset shell, legend, button, and output rendering.

Replace only the field body with:

```js
Formidable.getFields(formLike, 'edit')
```

This should eliminate duplicated primitive field rendering logic from `ntx-method`.

---

## Phase 7 — GREEN: replace `ntx-method` value extraction with typed collection

### Objective

Align `ntx-method` submission with Formidable-rendered DOM.

### Problem

Current `ntx-method` logic assumes:

- `name` attributes
- primitive `input`/`textarea` fields only
- raw string values
- one-level dotted parsing

This does not match Formidable's output contract, which uses:

- `data-key`
- `data-type`
- `checkbox`, `select`, widgets, list-field components

### Recommendation

Switch to submit-time typed collection.

#### Add a helper in `ntx-method`

Example shape:

```js
collectFormValue() {
  const form = this.shadowRoot.querySelector('form');
  const result = {};
  // walk editable controls, read data-key/data-type, coerce, assign nested
  return result;
}
```

#### It must support

- booleans via checkbox state
- number / integer coercion
- selects
- textareas
- dotted paths into nested objects
- object parsing where necessary
- list/widget-backed fields to the extent required by existing Formidable output

#### Update `callMethod()`

Before submission:

```js
this.value = this.collectFormValue();
caller.call(this.method, { ...this.value }, { inbox: '_response_' });
```

This makes the submitted payload the source of truth, rather than relying on incremental `name`-based state mutation.

---

## Phase 8 — GREEN: update event binding and auto mode

### Objective

Ensure method forms respond correctly to checkbox/select/widget changes.

### Current limitation

`#bindInputs()` only listens to `input, textarea` and only on the `input` event.

### Required update

Bind:

- `input`
- `textarea`
- `select`

Listen to:

- `input`
- `change`

### Auto mode behavior

If `mode === 'auto'`, re-collect the current form state and call the method.

This is safer than preserving the existing `name`-based incremental update approach.

---

## Phase 9 — GREEN: validate method forms through Formidable

### Objective

Reuse `Formidable.validateForm()` before method submission.

### Implementation

Before submit:

1. build `formLike`
2. set `formLike.value = collectFormValue()`
3. run `Formidable.validateForm(formLike)`
4. abort submit if errors are present

This brings method forms onto the same schema-validation path as entity forms.

---

## Phase 10 — GREEN: handle inline layout intentionally

### Objective

Preserve compact inline UX where it makes sense without forcing all complex widgets into one-line layouts.

### Recommendation

For `renderInline()`:

- if the method is a simple single scalar param, keep a compact inline layout
- if fields are non-trivial (boolean, array, `$ref`, object, or multi-field), use a stacked inline body rendered by `Formidable.getFields(...)` plus an actions block

This keeps the UX intentional while prioritizing correctness.

---

## Phase 11 — REFACTOR: simplify and remove duplicate logic

Once tests are green and fieldset rendering is stable:

- remove obsolete primitive rendering branches from `ntx-method`
- keep only layout-specific shells and collection/submit logic
- ensure `getForm()` and `getFields()` share the same internal rendering primitives

---

## Verification Plan

### Focused frontend unit verification

Run:

```bash
cd /workspace/tests/frontend && npx vitest run tests/generators/form.test.js tests/components/ntx-method.test.js
```

### Expected passing scope

- new `Formidable.getFields()` tests
- existing `Formidable` tests
- existing `ntx-method` tests
- new boolean / array method param tests

### Optional broader frontend verification

Run:

```bash
cd /workspace/tests/frontend && npx vitest run
```

### Optional browser-level smoke check

If unit tests pass and we want extra confidence:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js tests/e2e/ntx-method-unit.spec.js
```

## Risks and Mitigations

| Risk | Area | Mitigation |
|---|---|---|
| Entity form regressions | `form.js` | Keep `getForm()` contract stable and verify entity-style tests still pass |
| Top-level `$ref` method params regress | `getFields()` / `getInput()` | Add explicit regression test before removing manual method rendering |
| Arrays still break under method schemas | `getListInput()` | Normalize field lookup away from hardcoded `schema.properties` |
| Auto mode breaks for checkboxes/selects | `ntx-method` | Bind `change` and use typed form collection |
| Reset logic fails for widgets | `ntx-method` | Reset by clearing state + re-render rather than mutating DOM controls manually |

## Recommended Execution Order

### Wave 1 — define the failing behavior

1. Add failing `ntx-method` boolean render test
2. Add failing `Formidable.getFields()` boolean render test
3. Add failing array render test if the current bug reproduces there

### Wave 2 — build the shared primitive

4. Add normalized field-def helper in `form.js`
5. Refactor internal field lookup paths
6. Add `getFields(...)`
7. Refactor `getForm()` to call `getFields(...)`
8. Export `getFields`

### Wave 3 — migrate method fieldset rendering

9. Switch `renderFieldset()` in `ntx-method` to `Formidable.getFields(...)`
10. Add typed collection helper
11. Validate before submit
12. Re-run focused unit tests

### Wave 4 — migrate inline rendering safely

13. Implement simple-vs-complex inline branching
14. Migrate inline mode to use shared field rendering
15. Re-run focused unit tests

### Wave 5 — tighten regressions and docs

16. Add `$ref` regression coverage if needed
17. Run broader frontend verification
18. Update `packages/n3tx-ui/docs/formidable.md`

## Deliverable Summary

The implementation is complete when:

- method parameter rendering is routed through `Formidable`
- `getFields(...)` exists and is tested
- boolean method params render as checkboxes
- array method params no longer degrade to primitive text fallback
- method submission uses typed collection
- focused frontend tests pass
