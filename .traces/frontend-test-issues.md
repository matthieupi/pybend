# Frontend Test Suite Issues

Discovered during in-depth review of the NTT 0.6 test suite (`src/pybend/static/NTT0.6/tests/`).
703 tests pass across 37 files, but structural problems undermine confidence.

---

## 1. 33 Unhandled Rejection Errors Per Run

**Severity:** High
**Location:** Multiple integration test files, primarily `list-item-interaction.test.js` and `method-execution.test.js`

Every test run produces 33 `AssertionError` unhandled rejections from leaked `fetch()` calls. When tests reset modules via `vi.resetModules()`, the old module's pending promises still resolve and fire callbacks into stale state (`NetworkAdapter.onError → emit()` calls watchers that no longer exist).

**Impact:** Real bugs that manifest as unhandled rejections would be invisible in this noise. The suite reports "37 passed" alongside "33 errors" — a passing run should have zero errors.

**Fix options:**
- Add `unhandledrejection` listener in `setup.js` that fails the test
- Properly `await` all pending promises before module reset
- Add `vi.restoreAllMocks()` in `afterEach` for integration tests
- Set `restoreMocks: true` in `vitest.config.js`

---

## 2. Seven Source Files Have Zero Test Coverage

**Severity:** Medium

| File | LOC | Notes |
|------|-----|-------|
| `components/ntt-favorites.js` | 16 | Simple wrapper, low risk |
| `components/ntt-profile.js` | 113 | Renders user data into innerHTML — XSS risk (see issues.md) |
| `components/ntt-user.js` | 41 | Constructs external avatar URLs with user input |
| `utils/theme.js` | 33 | localStorage persistence + CustomEvent dispatch |
| `utils/registrar.js` | 65 | Used by Actor system, has logic bug (see issues.md) |
| `utils/Snippets.js` | 11 | Dead code — attaches all window events to console.log |
| `utils/str_utils.js` | 3 | Dead code — empty function |

---

## 3. ntt-item.js — Most Complex Component, Shallowest Tests

**Severity:** High
**Location:** `tests/components/ntt-item.test.js` (200 lines) vs source (652 lines)

The test file covers: class registration, `xs()` output, `handleInputChange()`, `update()` bail conditions, `render()` no-op. Everything below is **untested**:

| Method/Feature | Lines | What it does |
|---------------|-------|-------------|
| `sm()` | 153-279 | Most complex size method — $ref resolution, field ordering, method buttons, reply button, action buttons. Zero tests. |
| `md()` | 282-315 | Card rendering with Formidable, attached/standalone method splitting, permission-gated buttons. Zero tests. |
| `deleteItem()` | 62-96 | Permission check, confirm dialog, TX dispatch through DynamicClass, optimistic parent array update. Zero tests. |
| `toggleMode()` | 100-106 | Permission check, save-on-exit, mode toggle. Zero tests. |
| `render()` dispatch | 465-483 | Size method routing, reply indent class, `_rendered` flag, `$styles` append, `#bindEvents` call. Only a no-op guard test. |
| `#bindEvents()` | 491-590 | Edit/delete buttons, input handlers, show-more toggle, reply submission (Enter/Escape keyboard), card click → SELECT. Zero tests. |
| `#updateListField()` | 386-458 | Surgical reconciliation — removals, promotions from collapsed, additions, show-more updates. Zero tests. |
| `#smFields()` | 596-617 | Field filtering (id, hidden, array, selfref, permissions). Zero tests. |
| `#resolveChildTag()` | 623-629 | $defs lookup, NTT registry fallback. Zero tests. |
| `#standaloneMethodsHtml()` | 632-648 | Method button HTML generation. Zero tests. |

---

## 4. ntt-list.test.js — 5 Assertions for Entire Collection System

**Severity:** High
**Location:** `tests/components/ntt-list.test.js` (45 lines)

Only tests: custom element registration, styles getter, method existence. Zero behavioral tests for:

- `loadMore()` pagination (offset increment, READ with limit/offset)
- `createChild()` with `<template item-template>` or childTag resolution
- Display cascade (parent xl→child md, lg→sm, md→sm, sm→xs, xs→xs)
- Surgical DOM reconciliation (removals, additions, count update)
- Selection API (`select`, `deselect`, `toggle`, `clearSelection`)
- Stagger delay rendering (`--stagger-delay = i * 50ms`)
- `definedCallback()` — initial READ trigger with populate depth

---

## 5. Permission-Denied UI Paths Never Tested

**Severity:** High
**Location:** Every component test file

Every component test mocks permissions as:
```js
permissions: { canAction: vi.fn(() => true), canView: vi.fn(() => true), canEdit: vi.fn(() => true) }
```

This means:
- Zero tests verify edit/delete buttons are hidden when `canAction` returns false
- Zero tests verify `toggleMode()` aborts when update is denied
- Zero tests verify `deleteItem()` aborts when delete is denied
- Zero tests verify fields are hidden when `canView` returns false
- Zero tests verify fields are display-only when `canEdit` returns false

The entire permission-gated UI is tested only in the "allowed" state.

---

## 6. No Negative / Error Path Testing

**Severity:** Medium

Almost no tests verify that things don't happen when they shouldn't:

- No test that `deleteItem()` aborts when `confirm()` returns false
- No test that `handleInputChange()` handles missing `dataset.key`
- No test that `NTTMethod.load()` returns early when model not found
- No test that `NTTMethod.load()` returns early when method schema not found
- No test for malformed schema input (missing `properties`, null `$defs`, etc.)
- No test for empty value objects with all field types
- No test that `save()` sends correct payload shape

---

## 7. ntt-logs.test.js — Missing Core Behavior

**Severity:** Medium
**Location:** `tests/components/ntt-logs.test.js` (95 lines)

Tests: registration, DOM structure, listener subscription/unsubscription. Missing:

- Filter toggle (click filter → active, click again → deactivate)
- `#applyFilter()` — hide/show entries by level
- `#appendEntry()` — entry rendering with level colors, timestamps
- `#formatContent()` — JSON tree rendering, long text collapse, XSS escaping via `#esc()`
- `#renderJson()` — depth limit (max 8), type coloring, collapse toggle
- Clear button → `Logging.clear()` → DOM reset
- Panel open/close toggle
- Badge count update on new entry

---

## 8. ntt-topbar.test.js — Missing Authenticated State

**Severity:** Medium
**Location:** `tests/components/ntt-topbar.test.js` (75 lines)

Tests: registration, shadow DOM, sign-in link (unauthenticated). Missing:

- Authenticated rendering (user pill, avatar, dropdown menu)
- Logout handler (localStorage clear + redirect to `/login.html`)
- Theme toggle button click → `toggleTheme()` call
- `theme-change` event listener triggering re-render
- Favorites nav link (shown only when authenticated)
- `#userPillHtml()` with image vs letter initial avatar

---

## 9. Form Generator — Missing Edge Cases

**Severity:** Medium
**Location:** `tests/generators/form.test.js`

Covered: basic types, field_order, groups, protected fields, validation attrs, formatDisplayValue, getListInput. Missing:

- `resolveAnyOf()` — multiple non-null anyOf entries (should throw), single entry resolution
- `refInput()` — NTT.get() fallback when reference not found
- `getInput()` with `effectiveMode` override — when `canEdit()` returns false
- `getInput()` with `selfref` type in both edit and display modes
- `getInput()` with `$ref` type in display mode (`[Reference: ...]` format)
- `getHeader()` with description in edit mode (textarea rendering)
- `getForm()` return type — line 64 calls `.join('')` on `$header.concat($fields)` where `$fields` is sometimes a string, not an array — potential type error
- `getArrayInput()` — legacy function exported but never tested (may be dead code)
- Edge: field in `field_order` but not in `properties`
- Edge: empty value object with all field types

---

## 10. Prototype.call() Anti-Pattern

**Severity:** Medium
**Location:** `ntt-item.test.js`, `ntt-list.test.js`, and others

Many component tests use `NTTItem.prototype.xs.call(ctx)` with a fake context object instead of creating actual custom elements. This:

- Bypasses the shadow DOM entirely
- Skips `connectedCallback` lifecycle
- Doesn't test event binding
- Doesn't test attribute observation
- Doesn't test CSS stylesheet injection (`$styles`)
- Produces false confidence about rendering behavior

The pattern is acceptable for pure-function size methods (`xs`, `sm`, etc.) but not for methods that interact with the DOM (`render`, `#bindEvents`, `update`).

---

## 11. Test Infrastructure Issues

**Severity:** Medium

### setup.js
- **Dead code:** `localStorageMock` is defined then immediately overwritten by `localStorageProxy` on line 37
- **No WebSocket mock reset:** `WebSocketMock` state persists across tests
- **No `customElements` reset:** jsdom persists registrations — once `ntt-item` is defined, it can't be redefined. Forces global state sharing.
- **No `console.error` spy by default:** Unhandled errors in test code pass silently

### vitest.config.js
- **No coverage configuration:** `test:coverage` script runs but no thresholds, reporters, or provider configured
- **No `restoreMocks` setting:** Every test file manually mocks the same 4 modules (Assert, config, Logging, Permissions)

### package.json
- **Missing `@vitest/coverage-v8`:** The `test:coverage` script won't produce output without the coverage provider dependency
- **No coverage thresholds:** No way to enforce minimum coverage as a CI gate

---

## 12. Missing Entire Test Categories

**Severity:** Medium

| Category | Status |
|----------|--------|
| Memory leaks | No tests verify `disconnectedCallback` cleans up all subscriptions, signals, and observers |
| Error boundaries | No tests verify graceful degradation with malformed schemas |
| Concurrent operations | No tests for race conditions (multiple rapid navigations, simultaneous ATTACH for same model) |
| Accessibility | No tests for ARIA attributes, keyboard navigation, focus management |
| Render efficiency | No tests verifying surgical update prevents unnecessary full re-renders |

---

## 13. Integration Test — Missing Scenarios

**Severity:** Low-Medium

The integration tests are the strongest part of the suite but still miss:

- **Pre-loaded schema/data** via `<script data-ntt-schema>` / `<script data-ntt-data>` — NTT.js supports this but it's never integration-tested
- **Race: multiple ATTACH before SCHEMA resolves** — two lists attaching to the same model simultaneously
- **Error propagation** — network request fails mid-lifecycle (only happy paths tested)
- **DELETE lifecycle** — create → delete → verify instance removal and watcher notification
- **Edit/save cycle** — toggle to edit, modify, save, verify UPDATE TX payload
- **Populated data normalization edge cases** — nested objects with missing `$id`, mixed href/object arrays

---

## 14. Permissions.test.js — Documents Bug Instead of Testing Correct Behavior

**Severity:** Low
**Location:** `tests/utils/Permissions.test.js:218-234`

The NOT rule test explicitly documents the bug:
```js
// NOTE: The NOT rule format { op: 'not', rule: {...} } has a conflict
// with the simple rule check (rule.rule is truthy)...
// This is a known limitation of the frontend rule evaluator.
expect(permissions.canAction(access, 'delete')).toBe(true); // wrong behavior
```

This should be a failing test with the expected correct behavior (`false`), not a passing test that validates the wrong behavior. Documenting bugs as passing tests hides them from CI.

---

## 15. ntt-method.test.js — Render Layout Paths Incomplete

**Severity:** Low
**Location:** `tests/components/ntt-method.test.js`

Tests verify render dispatch (inline→renderInline, button→renderButton, fieldset→renderFieldset) and basic button/fieldset output. Missing:

- `renderInline()` with `$ref` parameter resolution (single required field → compact row)
- `renderInline()` with `widget: 'textarea'` override
- `renderFieldset()` with `selfref` type parameter
- `renderFieldset()` with `$ref` and multiple required fields
- `#postCall()` — inline layout clears inputs, fieldset re-renders
- `#bindInputs()` — form submit prevention, input listener attachment
- `load()` error paths — model not found, instance not found, method schema not found
- `attributeChangedCallback` triggering `load()` reload
