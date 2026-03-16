# Widget System

> Part of [n3tx-ui](../README.md)

## What This Covers

The widget base class, registry, built-in widgets, and extension API. Covers how `ui.widget` schema hints flow from Python model definitions to specialized frontend renderers.

## Architecture

```
Python model field
  Field(json_schema_extra={'ui': {'widget': 'currency', 'config': {'symbol': '$'}}})
      |
      v
Backend schema pipeline (widget stage)
  Injects ui.widget + ui.config into JSON Schema properties
      |
      v
Frontend: form.js getInput() / ntx-item.js sm()
  Calls getWidgetForField(fieldSchema)
      |
      v
registry.js: _widgets[name] lookup
  Returns { widget: WidgetInstance, config: ui.config }
      |
      v
Widget method call (context-dependent):
  display(value, config, schema) -> DOM Node     (detail views)
  edit(value, config, schema, onChange) -> DOM Node (form inputs)
  list(value, config, schema) -> string           (table cells, sm fields)
  validate(value, config, schema) -> string|null  (form validation)
```

If no widget is registered for the field's `ui.widget` name, `getWidgetForField()` returns `{widget: null, config: {}}` and Formidable falls through to type-based rendering.

## Interface

### Widget base class

```javascript
class Widget {
    // Render for detail/display context. Returns DOM Node.
    display(value, config, schema) { return document.createTextNode(value ?? ''); }

    // Render for edit context. Returns DOM Node (input element).
    edit(value, config, schema, onChange) { /* returns <input> */ }

    // Render for list/table cell. Returns plain text or HTML string.
    list(value, config, schema) { return String(value ?? ''); }

    // Validate value. Returns error message string or null.
    validate(value, config, schema) { return null; }

    // Utilities (inherited by all widgets)
    truncate(str, maxLen = 80)           // Ellipsis truncation
    escape(html)                         // HTML entity escaping
    el(tag, attrs = {}, children = [])   // DOM element builder
}
```

### Registry API

```javascript
registerWidget(name, widgetInstance)    // Register by name (matches ui.widget)
getWidgetForField(fieldSchema)         // Returns { widget: Widget|null, config: Object }
hasWidget(name)                        // Check if registered
```

### Built-in widgets

| Name | Class | Display | Edit | Validates |
|------|-------|---------|------|-----------|
| `url` | UrlWidget | Clickable `<a>` link | `input[url]` | URL parse check |
| `email` | EmailWidget | `mailto:` link | `input[email]` | Email regex |
| `date` | DateWidget | Localized date string | `input[date]` | Date parse check |
| `datetime` | DateWidget | Localized date string | `input[datetime-local]` | Date parse check |
| `markdown` | MarkdownWidget | Parsed HTML (marked.js) | `<textarea>` + live preview | No |
| `console` | ConsoleWidget | `<pre>` with ANSI colors (ansi_up.js) | Readonly `<textarea>` | No |
| `reference` | ReferenceWidget | Clickable entity link | `input[text]` | No |
| `currency` | CurrencyWidget | `$X,XXX.XX` formatted | `input[number]` with symbol prefix | Number + bounds |
| `textarea` | TextareaWidget | Block text `<div>` | `<textarea>` | No |

## Usage Patterns

### Creating a custom widget

```javascript
import { Widget, registerWidget } from '../widgets/index.js';

class ColorWidget extends Widget {
    display(value, config, schema) {
        if (!value) return document.createTextNode('');
        const swatch = this.el('span', {
            class: 'color-swatch',
            style: `background: ${this.escape(value)}; width: 20px; height: 20px; display: inline-block; border-radius: 4px;`
        });
        return this.el('span', {}, [swatch, ` ${value}`]);
    }

    edit(value, config, schema, onChange) {
        const input = document.createElement('input');
        input.type = 'color';
        input.setAttribute('value', value ?? '#000000');
        if (onChange) input.addEventListener('input', () => onChange(input.value));
        return input;
    }

    list(value) {
        return value ?? '';
    }
}

registerWidget('color', new ColorWidget());
```

Then on the backend:

```python
color: str = Field(default='#000000', json_schema_extra={'ui': {'widget': 'color'}})
```

### Widget with config

Config is passed from `schema.ui.config`:

```python
price: float = Field(json_schema_extra={'ui': {'widget': 'currency', 'config': {'symbol': 'EUR'}}})
```

```javascript
// In CurrencyWidget.display():
display(value, config, schema) {
    const symbol = config?.symbol || '$';  // 'EUR' from schema
    // ...
}
```

### Widget with validation

```javascript
class PercentWidget extends Widget {
    validate(value, config, schema) {
        if (value == null) return null;
        const num = parseFloat(value);
        if (isNaN(num)) return 'Must be a number';
        if (num < 0 || num > 100) return 'Must be between 0 and 100';
        return null;
    }
}
```

Formidable calls `widget.validate()` during `validateForm()` after standard schema constraint checks.

## Gotchas

- **display() and edit() return DOM Nodes, list() returns a string.** This asymmetry exists because display/edit results are wrapped in container divs by Formidable (via `.outerHTML`), while list() output is inserted directly into HTML template strings by NTTItem's sm() method.

- **Widget dispatch requires both conditions.** `getWidgetForField()` returns a widget only if the name exists in the registry. But the callers in form.js and ntx-item.js additionally check `def.ui?.widget` before using the widget. This means registering a widget alone does not activate it -- the schema must also carry the `ui.widget` hint.

- **edit() must produce an element with data-key.** Formidable stamps `data-key` and `data-type` on the editable element (or the first input/textarea/select inside the returned node). This is required for `handleInputChange()` in NTTItem to process the value correctly. If your widget returns a complex DOM tree, ensure the primary input has these attributes or Formidable will stamp them on the outermost element.

- **Vendor libraries are optional.** MarkdownWidget checks `typeof marked !== 'undefined'` and falls back to `<pre>`. ConsoleWidget checks `typeof AnsiUp !== 'undefined'` and falls back to plain text. Include `vendor/marked.min.js` and `vendor/ansi_up.min.js` via script tags if you need these features.

- **The `el()` helper handles `on*` attributes as event listeners.** `this.el('button', {onclick: handler})` calls `addEventListener('click', handler)`, not `setAttribute('onclick', ...)`. Use this for interactive widget elements.
