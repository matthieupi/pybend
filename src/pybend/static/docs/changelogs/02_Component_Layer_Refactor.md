# Component Layer Refactor & Enhancement Primitives

> **Status:** Complete (P0 through P3).
> **Scope:** Rebuilt the entire component hierarchy and added schema-driven UI primitives.

---

## Table of Contents

1. [Summary](#1-summary)
2. [P0: Component Layer Refactor](#2-p0-component-layer-refactor)
3. [P1: Schema Extensions & Field Exclusion](#3-p1-schema-extensions--field-exclusion)
4. [P2: Formidable Enhancements & SSR](#4-p2-formidable-enhancements--ssr)
5. [P3: Scaffolding, Renderer Hints, Relationship Defaults](#5-p3-scaffolding-renderer-hints-relationship-defaults)
6. [File-by-File Changes](#6-file-by-file-changes)
7. [Remaining Work](#7-remaining-work)

---

## 1. Summary

The NTT frontend component layer was rebuilt from a 4-class hierarchy with multiple issues (circular imports, dual lifecycle paths, broken super chains, hardcoded child components) into a clean 5-class hierarchy with schema-driven primitives.

### Before

```
HTMLElement
  └── Component              (core/Component.js, ~70 lines — Actor bridge only)
        └── NTTElement       (components/ntt-element.js, ~155 lines — did everything)
              ├── Item       (components/ntt-item.js)   → <ntt-item>
              └── List       (components/ntt-list.js)   → <ntt-list>
```

### After

```
HTMLElement
  └── Component              (core/Component.js, ~317 lines — merged base)
        ├── NTTElement       (components/NTTElement.js, ~107 lines — entity lifecycle)
        │     └── NTTItem    (components/ntt-item.js, ~129 lines — built-in default)
        └── ListElement      (components/ListElement.js, ~133 lines — collection lifecycle)
              └── NTTList    (components/ntt-list.js, ~19 lines — built-in default)
```

### Impact

| Metric | Before | After |
|--------|--------|-------|
| Lifecycle paths | 2 (define + describe) | 1 (define → definedCallback) |
| Actor.subclass calls | 3 (Component, NTTElement, List) | 1 (Component only) |
| Circular imports | 1 (Component → ntt-item) | 0 |
| Schema-driven rendering | manual | field_order, groups, widgets, validation, renderer hints |
| Adaptive display | none | ResizeObserver with displayMode in every component |
| SSR support | none | Pre-loaded schema + data via inline `<script>` tags |
| Scaffolding | none | CLI + API endpoint generates starter components |

---

## 2. P0: Component Layer Refactor

### Merged Component + NTTElement → Component

The old `Component` (Actor bridge only, ~70 lines) and `NTTElement` (schema/value/ref binding, ~155 lines) were merged into a single `Component` base class. This eliminated:

- Circular import (Component.js → ntt-item.js)
- Duplicate abstract `render()` declarations
- Broken `disconnectedCallback` super chain
- `observedAttributes` override without merge
- Zero-consumer intermediate class

### Split Entity vs Collection Lifecycle

**NTTElement** (single entity):
- Default value `{}`
- Message handlers: `UPDATE`, `DESCRIBE`, `READ`
- `save()` for pushing edits back
- `set value()` auto-renders when schema available

**ListElement** (collection):
- Default value `[]`
- `definedCallback()` subscribes to proto + triggers READ
- `UPDATE(data)` receives address array
- `createChild(addr)` with template/childTag/schema hint resolution chain
- Default `render()` stamps children

### Removed

- `describe()` — dead dual-init path
- `update()` — trivial wrapper that children override with message handlers
- Auto-render in `Component.set value()` — subclasses decide

---

## 3. P1: Schema Extensions & Field Exclusion

### `__ui__` ClassVar (Backend)

New `__ui__` ClassVar on ProtoModel subclasses, injected into schema output as-is:

```python
class Product(ProtoModel):
    __ui__: ClassVar[dict] = {
        'field_order': ['name', 'price', 'description', 'comments'],
        'groups': {'main': ['name', 'description'], 'pricing': ['price']},
        'renderer': {'item': 'ntt-item', 'list': 'ntt-list'},
    }
```

### Field Exclusion Conventions (Backend)

`_apply_field_exclusion()` in `proto_model.py` auto-hides:
- Fields ending in `_id` (except `id` itself) → `ui.display: false`
- `id`, `created_at`, `updated_at` → `ui.display: false`
- Explicit `json_schema_extra={'ui': {'display': True}}` overrides

### Per-Field UI Hints

```python
price: float = Field(gt=0, json_schema_extra={'ui': {'widget': 'currency'}})
description: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
name: str = Field(json_schema_extra={'ui': {'placeholder': 'Product name...'}})
```

### Slot-Based Child Templates

ListElement resolves child components via priority chain:
1. `<template item-template>` in light DOM
2. `item-tag="..."` HTML attribute
3. `get childTag()` JS property override
4. `schema.ui.renderer.item` schema hint
5. `'ntt-item'` framework default

---

## 4. P2: Formidable Enhancements & SSR

### Formidable (form.js) — Enhanced

- **Field ordering**: `getForm()` reads `schema.ui.field_order`, renders in that order
- **Field groups**: `renderGroupedFields()` wraps fields in `<fieldset class="ntt-group">` with `<legend>`
- **Widget hints**: `ui.widget` takes priority over `type`:
  - `textarea` → `<textarea>` / `<div class="text-block">`
  - `currency` → `<input type="number" step="0.01">` with `$` prefix / `$X.XX` display
- **Validation attrs**: `validationAttrs()` maps JSON Schema constraints → HTML5 attributes:
  - `minLength` → `minlength`, `maxLength` → `maxlength`
  - `minimum`/`exclusiveMinimum` → `min`, `maximum`/`exclusiveMaximum` → `max`
  - `pattern` → `pattern`, `required` from `schema.required`, `placeholder` from `ui.placeholder`

### SSR Pre-Loading (NTT.js)

Two private static helpers on `NTT`:
- `#consumePreloadedSchema(model)` — checks for `<script data-ntt-schema="Model">`, parses JSON, feeds to `NTT.SCHEMA()`, removes tag
- `#consumePreloadedData(tablename)` — checks for `<script data-ntt-data="tablename">`, parses JSON, removes tag

Wired into: `NTT.attach()`, `NTT.ATTACH()`, `NTT.SCHEMA()`. Eliminates both network round-trips for server-rendered pages.

### Adaptive Display Modes (Component.js)

ResizeObserver on every component:
- `displayBreakpoints` → `{page: 800, card: 400, 'list-item': 200, chip: 0}`
- `displayMode` → current mode string
- `displayModeChanged(old, new)` → hook, default re-renders

---

## 5. P3: Scaffolding, Renderer Hints, Relationship Defaults

### Schema Renderer Hints (§6)

Backend `__ui__.renderer` keys flow through to frontend:
- `ListElement.childTag` checks `schema.ui.renderer.item`
- `getListInput()` in Formidable checks `$defs[model].ui.renderer.item`
- Product model includes `renderer: {item: 'ntt-item', list: 'ntt-list'}` as example

### Relationship-Aware Smart Defaults (§13)

`getListInput()` enhanced in `form.js`:
- Resolves child tag from referenced model's `$defs` entry renderer hints
- Renders `.list-field-header` with model name label + count badge
- Collapse/expand for items beyond VISIBLE_COUNT

New CSS in `ntt-item.css`:
- `.list-field-header` — flex row
- `.list-field-label` — uppercase accent label
- `.list-field-count` — pill badge

### Scaffolding CLI & API (§10)

**New file**: `src/pybend/core/utils/scaffold.py`

Functions:
- `scaffold_item(schema)` → JS component extending NTTElement with explicit render()
- `scaffold_list(schema)` → JS component extending ListElement with custom childTag
- `scaffold_css(schema)` → Starter CSS with glass morphism, field-specific selectors
- `scaffold_list_css(schema)` → List component CSS
- `scaffold_model(name)` → Writes all 4 files (skips existing)
- `scaffold_single(name, kind)` → Returns source string (for API)

CLI: `cd src/pybend/core && python -m utils.scaffold Product`

API: `GET /Product?scaffold=item` → PlainTextResponse. Integrated into `make_get_schema()` in `routes_fastapi.py`.

---

## 6. File-by-File Changes

### New Files

| File | Purpose | Lines |
|------|---------|-------|
| `core/Component.js` | Merged base class | ~317 |
| `components/NTTElement.js` | Entity base | ~107 |
| `components/ListElement.js` | Collection base | ~133 |
| `core/utils/scaffold.py` | Component scaffolding | ~310 |

### Modified Files

| File | Changes |
|------|---------|
| `components/ntt-item.js` | Slimmed: extends NTTElement, Formidable rendering, show-more toggle |
| `components/ntt-list.js` | Slimmed: extends ListElement, styles only |
| `components/ntt-item.css` | Added: `.list-field-header`, `.list-field-label`, `.list-field-count`, fieldset glass styles |
| `components/ntt-element.css` | Added: `.loading-spinner`, `.error-state`, `.empty-state` |
| `generators/form.js` | Enhanced: field_order, groups, widget hints, validation, renderer-aware list fields |
| `core/NTT.js` | SSR: `#consumePreloadedSchema()`, `#consumePreloadedData()`, guards in ATTACH/SCHEMA |
| `models/proto_model.py` | `__ui__` injection, `_apply_field_exclusion()`, `$defs` UI propagation |
| `models/product_model.py` | Added `__ui__` with field_order, groups, renderer |
| `models/comment_model.py` | Added `__ui__` with field_order |
| `api/routes_fastapi.py` | `?scaffold=` query parameter on schema endpoint |

### Deleted Files

| File | Reason |
|------|--------|
| `components/ntt-element.js` | Absorbed into `core/Component.js` |

---

## 7. Remaining Work

| Priority | Enhancement | Status |
|----------|-------------|--------|
| **P4** | Schema-driven permissions (§12) | Pending — needs auth system maturity |
| — | Adaptive display schema integration | Future — `display_modes` in `__ui__` to auto-select fields per mode |
| — | Typed `__ui__` config | Future — replace plain dict with Pydantic model for validation |
