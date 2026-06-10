---
name: n3tx-widgets
description: N3TX field widgets, backend Widget types, frontend widget registry, Formidable integration, and schema-driven field rendering. Use when customizing field display or input behavior.
argument-hint: "<widget task>"
---

# N3TX Widgets

Widgets customize field rendering while preserving schema as the contract.

## Backend widget hints

Simple hint:

```python
body: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
price: float = Field(gt=0, json_schema_extra={'ui': {'widget': 'currency'}})
```

Typed widget fields:

```python
from n3tx_core.widgets import MarkdownField, UrlField, CurrencyField

class Post(ActorModel):
    body: MarkdownField(rows=10)
    website: UrlField
    price: CurrencyField
```

## Frontend widget registry

```javascript
import { Widget } from './widgets/Widget.js';
import { registerWidget } from './widgets/registry.js';

class ColorWidget extends Widget {
  display(value, field, schema) { return `<span>${value}</span>`; }
  edit(value, field, schema) { return `<input name="${field}" value="${value ?? ''}">`; }
}

registerWidget('color', new ColorWidget());
```

Use schema `ui.widget = 'color'` to select it.

## When to use widgets vs components

| Need | Use |
|---|---|
| Custom field display/input | Widget |
| Custom whole entity layout | Renderer component |
| Custom collection layout | List/table/custom collection component |
| Custom behavior/action | `@expose_route` + method component |

## Guardrails

- Do not hardcode widgets by model/field name in random components if schema can declare `ui.widget`.
- Do not duplicate validation; backend Pydantic remains authoritative.
- Do not fork Formidable for one field type; register a widget.

## Verification

- Schema includes `ui.widget`.
- Formidable uses the widget in display/edit/list contexts.
- Widget handles empty/null values and safe rendering.
- Vitest covers rendering behavior.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
