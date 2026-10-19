# Field widgets

Widgets provide field-specific display, editing and compact rendering. Validation
and field definitions stay in the Python model; the browser registers presentation.

```text
field schema -> registry -> display/edit DOM -> Formidable HTML serialization
                        -> list string -> compact cell rendering
                        -> validate -> client error message
```

## Selection and API

`getWidgetForField(fieldSchema)` resolves:

1. A registered explicit `ui.widget` name, with `ui.config`.
2. Boolean type to `bool`.
3. `x-ref` metadata to `reference`, with its model name.
4. No match: type-based Formidable fallback.

Import from `/widgets/index.js` to load built-ins and access `Widget`,
`registerWidget(name,instance)`, `getWidgetForField(schema)` and `hasWidget(name)`.
Registry-only imports do not load built-ins themselves. A later registration with
the same name replaces the previous instance.

| Widget method | Return | Use |
|---|---|---|
| `display(value,config,schema)` | DOM Node | Detail/display |
| `edit(value,config,schema,onChange)` | Element containing a native input | Editing |
| `list(value,config,schema)` | String, potentially HTML | Compact cells; escape untrusted text |
| `validate(value,config,schema)` | Error string or null | Client validation |
| `escape(text)`, `truncate(text,maxLen=80)`, `el(tag,attrs={},children=[])` | Utilities | Text escaping/DOM assembly |

## A serialization-safe custom widget

Save as application `static/widgets/code-widget.js` and import it in the shell
before rendering the model. This changes presentation only; it adds no duplicate
field rules or domain contract.

```javascript
import { Widget, registerWidget } from '/widgets/index.js';

class CodeWidget extends Widget {
  display(value) {
    const node = document.createElement('code');
    node.textContent = String(value ?? '');
    return node;
  }
  edit(value) {
    const input = document.createElement('input');
    input.type = 'text';
    input.setAttribute('value', String(value ?? ''));
    return input;
  }
  list(value) {
    return this.escape(String(value ?? ''));
  }
}
registerWidget('code', new CodeWidget());
```

In the application model (declaration excerpt):

```python
from pydantic import Field

code: str = Field(default='', json_schema_extra={'ui': {'widget': 'code'}})
```

### Serialization is the important boundary

Formidable wraps widget DOM, then returns `outerHTML`. The final page receives
new nodes, not the objects returned by `edit()`:

- `addEventListener` callbacks on the original widget node **do not survive**.
  Do not rely on `onChange` callbacks for that rendering path.
- Persist initial input state in attributes (`value`, `checked`, `selected`) or
  textarea text content, not only mutable DOM properties.
- Formidable stamps `data-key` and `data-type` on the first input/textarea/select
  (or outer element). Native item/form handlers read those controls after mount.
- Stateful interactive widgets should return a registered custom element whose
  lifecycle binds its own listeners after insertion. Verify its value contract
  with `readFormValue`; arbitrary custom elements are not automatically supported.
- Style widget markup in the consuming shadow root. Page CSS cannot directly
  select elements inside that root; inherited theme tokens still work.

## Built-ins

| Name | Display/edit behavior |
|---|---|
| `url` | Link / URL input |
| `email` | Mail link / email input |
| `date`, `datetime` | Formatted date / date or datetime-local input |
| `markdown` | Markdown HTML / textarea; vendor/runtime behavior requires review for untrusted input |
| `console` | Console text/ANSI rendering / readonly textarea |
| `reference` | Typed URL pointer display / text input |
| `currency` | Formatted amount / number input; `ui.config.symbol` customizes symbol |
| `textarea` | Block text / textarea |
| `bool` | Read-only checkbox presentation / editable checkbox |
| `list` | `ntx-list-field` array component |

Example field configuration:

```python
price: float = Field(
    ge=0,
    json_schema_extra={'ui': {'widget': 'currency', 'config': {'symbol': 'EUR'}}},
)
```

HTML escaping is not URL-policy validation, CSS sanitization, or Markdown
sanitization. Prefer text nodes; validate URL schemes before creating links and
never insert untrusted SVG/HTML into the icon registry. See
[Formidable limitations](formidable.md) and [styling](styling.md).

## Verification

Test display/edit serialization, value reading, empty/invalid inputs, and compact
output, not just direct `widget.edit()` callbacks. The
[BoolWidget tests](../../../tests/frontend/tests/widgets/BoolWidget.test.js)
demonstrate attribute serialization checks; [ReferenceWidget tests](../../../tests/frontend/tests/widgets/ReferenceWidget.test.js)
cover URL-reference selection. Source:
[registry](../src/n3tx_ui/static/widgets/registry.js),
[Widget](../src/n3tx_ui/static/widgets/Widget.js),
[built-in registration](../src/n3tx_ui/static/widgets/index.js).
