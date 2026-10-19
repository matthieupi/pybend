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
  display(value, config, schema) {
    const span = document.createElement('span');
    span.textContent = String(value ?? '');
    return span;
  }
  edit(value, config, schema, onChange) {
    const input = document.createElement('input');
    input.type = 'text';
    input.setAttribute('value', String(value ?? ''));
    return input;
  }
  list(value, config, schema) {
    return this.escape(String(value ?? ''));
  }
}

registerWidget('color', new ColorWidget());
```

Use schema `ui.widget = 'color'` to select it. `display` and `edit` return
DOM nodes; `list` returns escaped HTML text. Formidable stamps the input's field
metadata; the second argument is widget config, not a field name.

This is a plain-text example, not CSS color interpolation. Formidable serializes
widget markup; listeners attached before serialization do not survive. Follow
the [widget guide](../../../packages/n3tx-ui/docs/widgets.md) for round trips and
automatic bool/x-ref selection. Backend validation remains authoritative.

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

Read relevant docs/skills first, then current implementation/tests before meaningful
changes. Also inspect source when docs are incomplete or contradicted. Docs first
is not docs only; update or propose documentation corrections when gaps are found.
