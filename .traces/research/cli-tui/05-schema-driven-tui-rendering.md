# Schema-Driven TUI Rendering: Can JSON Schema Drive Terminal UIs the Same Way It Drives Web UIs?

```
/.traces/research/cli-tui/05-schema-driven-tui-rendering.md
```

---

## Executive Summary

**The one-sentence pitch:** N3TX already generates complete web UIs from JSON Schema -- extending this to generate terminal UIs with Textual/Rich would create a genuinely novel "write a model, get a web app AND a terminal admin" capability that no other framework offers today.

**The state of the art:** In the web world, schema-driven form generation is mature and battle-tested. Libraries like [react-jsonschema-form](https://github.com/rjsf-team/react-jsonschema-form) (14k+ GitHub stars, ~36k weekly npm downloads) have proven the pattern. In the terminal world, only one project -- [SchemaUI](https://github.com/YuniqueUnic/schemaui) (37 stars, Rust) -- has attempted JSON Schema to TUI form mapping. **Nobody has done this in Python. Nobody has done it with Textual. The field is wide open.**

**The technical feasibility:** High. Textual's widget set maps cleanly to JSON Schema types: `Input(type="integer")` for numbers, `Checkbox` for booleans, `Select` for enums, `TextArea` for long text, `DataTable` for arrays. Textual's CSS-like styling, reactive data binding, and `data_bind()` mechanism are architecturally similar to web component patterns. N3TX's `form.js` logic -- ~370 lines that turn schema properties into HTML inputs -- could be ported to a Python `FormWidget` of comparable size.

**The risk:** Terminal constraints are real -- no images, no rich media, no drag-and-drop, no color pickers. But for CRUD administration, data browsing, and entity management, the TUI medium is not just adequate -- it is faster and more accessible than a browser for many workflows.

> **Key Insight:** N3TX's architecture already separates schema generation (backend) from schema consumption (frontend). Adding a TUI renderer is a matter of building a second consumer -- the schema contract stays unchanged. This is the architectural payoff of schema-driven design.

---

## Table of Contents

1. [The Web Precedent: Schema-to-Form Is a Solved Problem](#the-web-precedent)
2. [The Terminal Frontier: Who Has Tried This?](#the-terminal-frontier)
3. [Textual's Widget System: The Building Blocks](#textuals-widget-system)
4. [Schema-to-Widget Mapping: The Concrete Translation Table](#schema-to-widget-mapping)
5. [N3TX's form.js vs. Theoretical TUI Formidable](#ntx-formjs-vs-tui)
6. [Reactive Data Binding: Web Components vs. Textual](#reactive-data-binding)
7. [Read-Only Rendering: Lists and Detail Views](#read-only-rendering)
8. [The Isomorphic Form Architecture](#isomorphic-form-architecture)
9. [Textual CSS: Shared Design Tokens](#textual-css-shared-design-tokens)
10. [Interactive CRUD in TUI](#interactive-crud-in-tui)
11. [Limitations and Graceful Degradation](#limitations-and-graceful-degradation)
12. [Implementation Roadmap](#implementation-roadmap)
13. [Sources](#sources)

---

## 1. The Web Precedent: Schema-to-Form Is a Solved Problem {#the-web-precedent}

The pattern of generating forms from JSON Schema is **mature, proven, and widely adopted** in the web ecosystem. Understanding how these libraries work is essential because the TUI renderer will follow the same architectural patterns.

### Major Web Libraries

| Library | Framework | GitHub Stars | Weekly Downloads | Key Innovation |
|---------|-----------|-------------|-----------------|----------------|
| [react-jsonschema-form](https://github.com/rjsf-team/react-jsonschema-form) | React | 14k+ | ~36k npm | Introduced `uiSchema` separation |
| [FormKit](https://formkit.com/essentials/schema) | Vue | 4k+ | ~50k npm | Schema-first, deeply integrated validation |
| [Form.io](https://form.io/json-forms/) | Multi-framework | 2k+ | Enterprise | JSON defines form + API in one spec |
| [ngx-formly](https://github.com/ngx-formly/ngx-formly) | Angular | 2.7k+ | ~30k npm | Dynamic forms from JSON config |
| **N3TX form.js** | Vanilla JS | -- | -- | Schema carries UI hints inline (`json_schema_extra`) |

### The RJSF Default Widget Mapping (Web Standard)

[react-jsonschema-form](https://rjsf-team.github.io/react-jsonschema-form/docs/usage/widgets/) established the canonical mapping from JSON Schema types to HTML widgets that most libraries now follow:

| JSON Schema Type | Format | Default HTML Widget |
|-----------------|--------|-------------------|
| `string` | -- | `<input type="text">` |
| `string` | `email` | `<input type="email">` |
| `string` | `uri` | `<input type="url">` |
| `string` | `date` | `<input type="date">` |
| `string` | `date-time` | `<input type="datetime-local">` |
| `string` | `time` | `<input type="time">` |
| `string` | `data-url` | `<input type="file">` |
| `number` | -- | `<input type="number">` |
| `integer` | -- | `<input type="number">` |
| `boolean` | -- | `<input type="checkbox">` |
| `string` + `enum` | -- | `<select>` |
| `array` | -- | Repeated fields |
| `object` | -- | Nested fieldset |

The critical insight from RJSF: **JSON Schema alone is insufficient for full UI control**. RJSF solved this with a separate `uiSchema` object. N3TX solved it differently -- and better -- by embedding UI hints directly in the schema via `json_schema_extra`. This means N3TX's schema already carries everything a TUI renderer would need.

> **Key Insight:** N3TX's approach of inlining UI metadata (`ui.widget`, `ui.placeholder`, `ui.groups`, `ui.field_order`) into the JSON Schema itself is architecturally superior for multi-renderer scenarios. A TUI renderer reads the same schema, no separate `uiSchema` needed.

---

## 2. The Terminal Frontier: Who Has Tried This? {#the-terminal-frontier}

The honest answer: **almost nobody**. Schema-driven TUI form generation is a near-greenfield area.

### SchemaUI (Rust) -- The Closest Prior Art

[SchemaUI](https://github.com/YuniqueUnic/schemaui) is a Rust library (37 GitHub stars, 246 commits, version 0.4.3) that turns JSON Schema documents into interactive terminal UIs using [ratatui](https://ratatui.rs/) and crossterm. It is the **only production-grade attempt** at schema-driven TUI rendering.

**SchemaUI's Schema-to-Widget Mapping:**

| Schema Feature | TUI Control |
|---------------|------------|
| `type: string/integer/number` | Inline text editors with numeric guards |
| `type: boolean` | Toggle/checkbox |
| `enum` | Popup selector |
| Arrays | Inline list summary + overlay editor |
| `patternProperties` | Key/value editor with validation |
| `$ref` / `definitions` | Resolved before layout; inlined |
| `oneOf` / `anyOf` | Variant chooser + overlay |

**Architecture:** Root objects become **tabs**, nested objects flatten into **sections**, complex nodes open **dedicated overlays**. Every keystroke triggers `jsonschema::Validator` for immediate feedback.

**Limitations:** SchemaUI is written in Rust (not Python), targets configuration editing (not CRUD), and has no concept of entity lists, pagination, or backend API integration. It proves the concept is viable but solves a different problem.

### django-admin-tui -- Model-Driven TUI Admin

[django-admin-tui](https://github.com/valberg/django-admin-tui) (55 stars, v0.0.1, September 2024) renders Django's admin interface in the terminal using Textual. It proves that **model-driven TUI admin is a compelling idea** -- but it derives its UI from Django's `ModelAdmin` configuration, not from JSON Schema. It is early-stage (7 commits) but validates market demand.

### textual-forms -- Manual Form Builder

[textual-forms](https://github.com/rhymiz/textual-forms) (6 stars, v0.3.0) provides `StringField`, `NumberField`, and `IntegerField` for building Textual forms. **It does not support JSON Schema** -- forms are defined manually in Python code. It demonstrates the widget-level building blocks exist but has no schema-driven generation.

### Database CLI Tools (pgcli, litecli)

[pgcli](https://github.com/dbcli/pgcli) and [litecli](https://www.pgcli.com/launching-litecli.html) render tabular query results beautifully in the terminal using prompt_toolkit. They prove that **tabular data rendering in terminals is a solved problem** -- but they are SQL-centric, not schema-driven.

### The Gap

```
  Web Ecosystem                     Terminal Ecosystem
  ============                      ==================
  JSON Schema --> RJSF/FormKit      JSON Schema --> SchemaUI (Rust only)
  --> Rich forms, validation         --> Config editing only
  --> Multiple themes/renderers      --> Single renderer
  --> Production-ready (14k stars)   --> Early stage (37 stars)

  Django Models --> Django Admin     Django Models --> django-admin-tui
  --> Full CRUD web UI               --> Early prototype (55 stars)
  --> Battle-tested since 2005       --> v0.0.1, 7 commits

  N3TX Schema --> form.js          N3TX Schema --> ???
  --> Full CRUD web UI               --> NOTHING EXISTS YET
  --> Schema carries UI hints        --> Opportunity is wide open
```

**Nobody has built a Python library that takes JSON Schema and generates Textual TUI forms.** This is the opportunity.

---

## 3. Textual's Widget System: The Building Blocks {#textuals-widget-system}

[Textual](https://textual.textualize.io/) (33.8k GitHub stars, [2.5M+ PyPI downloads in 2024](https://johal.in/textual-tui-widgets-python-rich-terminal-user-interfaces-apps-2025/)) is the dominant Python TUI framework. Its widget set is comprehensive enough to map every JSON Schema type that matters for CRUD forms.

### Complete Widget Inventory (Form-Relevant)

| Widget | Purpose | JSON Schema Relevance |
|--------|---------|----------------------|
| **[Input](https://textual.textualize.io/widgets/input/)** | Text entry with types: `"text"`, `"integer"`, `"number"` | Primary widget for `string`, `number`, `integer` |
| **[TextArea](https://textual.textualize.io/widgets/data_table/)** | Multi-line text with syntax highlighting | Maps to `ui.widget: "textarea"` |
| **[Checkbox](https://textual.textualize.io/widgets/checkbox/)** | Boolean toggle | Maps to `type: "boolean"` |
| **[Switch](https://textual.textualize.io/widgets/select/)** | Alternative boolean toggle | Alternative for `type: "boolean"` |
| **[Select](https://textual.textualize.io/widgets/select/)** | Dropdown from options | Maps to `enum` values |
| **[RadioSet](https://textual.textualize.io/widgets/radioset/)** | Mutually exclusive options | Alternative for small `enum` sets |
| **[SelectionList](https://deepwiki.com/Textualize/textual/6.3-list-and-selection-widgets)** | Multi-select checkboxes | Maps to `type: "array"` + `enum` items |
| **[DataTable](https://textual.textualize.io/widgets/data_table/)** | Full data grid with cursors | Entity lists, array field display |
| **[MaskedInput](https://textual.textualize.io/widgets/masked_input/)** | Template-masked input | Maps to `format: "date"`, phone numbers |
| **[OptionList](https://deepwiki.com/Textualize/textual/6.3-list-and-selection-widgets)** | Vertical option list | References, `$ref` field selection |
| **[ListView](https://textual.textualize.io/widget_gallery/)** | Scrollable item list | Entity collection rendering |
| **[TabbedContent](https://textual.textualize.io/widget_gallery/)** | Tabbed panels | Maps to `ui.groups` |
| **[Collapsible](https://textual.textualize.io/widget_gallery/)** | Expandable sections | Alternative for `ui.groups` |
| **[Tree](https://textual.textualize.io/widget_gallery/)** | Hierarchical tree | Self-referential models (`Ref['self']`) |
| **[Label](https://textual.textualize.io/widget_gallery/)** | Static text | Field labels, display mode |
| **[Button](https://textual.textualize.io/widget_gallery/)** | Action trigger | Method buttons (`schema.methods`) |
| **[ProgressBar](https://textual.textualize.io/widget_gallery/)** | Progress display | Long-running method feedback |

### Input Widget Deep Dive

The [Input widget](https://textual.textualize.io/widgets/input/) is the workhorse for schema-driven forms. Its configuration maps directly to JSON Schema constraints:

| Input Feature | JSON Schema Source | Example |
|--------------|-------------------|---------|
| `type="text"` | `type: "string"` | Default string input |
| `type="integer"` | `type: "integer"` | Auto-restricts to integers |
| `type="number"` | `type: "number"` | Auto-restricts to floats |
| `placeholder` | `ui.placeholder` | `Input(placeholder="Product name...")` |
| `max_length` | `maxLength` | `Input(max_length=200)` |
| `restrict` (regex) | `pattern` | `Input(restrict=r"[a-zA-Z0-9]*")` |
| `password=True` | `format: "password"` | Masked input |
| `validators` | `minimum`, `maximum`, `minLength` | `Number(minimum=0, maximum=100)` |
| `suggester` | `enum` (as suggestions) | Autocomplete from enum values |

### Built-in Validators

Textual ships with [validators](https://textual.textualize.io/api/validation/) that map to JSON Schema constraints:

- **`Number(minimum, maximum)`** -- maps to `minimum`/`maximum`
- **`Integer(minimum, maximum)`** -- maps to integer `minimum`/`maximum`
- **`Length(min, max)`** -- maps to `minLength`/`maxLength`
- **Custom validators** via subclassing -- maps to `pattern` or complex constraints

---

## 4. Schema-to-Widget Mapping: The Concrete Translation Table {#schema-to-widget-mapping}

This is the core mapping that would drive a TUI form generator. Each row shows how a JSON Schema property definition translates to a specific Textual widget.

### Primary Mapping (Edit Mode)

| JSON Schema Type | Format/Widget Hint | Textual Widget | Configuration |
|-----------------|-------------------|----------------|---------------|
| `string` | -- | `Input(type="text")` | `max_length`, `restrict` |
| `string` | `ui.widget: "textarea"` | `TextArea()` | Multi-line editing |
| `string` | `ui.widget: "currency"` | `Input(type="number")` + prefix label | `$` prefix via `Horizontal(Label("$"), Input())` |
| `string` | `format: "email"` | `Input()` + email validator | Custom regex validator |
| `string` | `format: "password"` | `Input(password=True)` | Masked display |
| `string` | `format: "date"` | `MaskedInput(template="9999-99-99")` | Date mask |
| `string` | `format: "uri"` | `Input()` + URL validator | Custom validator |
| `string` + `enum` | -- | `Select(options)` | Options from `enum` array |
| `string` + `enum` (<=5 items) | -- | `RadioSet(options)` | Small enum as radio buttons |
| `number` | -- | `Input(type="number")` | `Number(minimum, maximum)` validator |
| `integer` | -- | `Input(type="integer")` | `Integer(minimum, maximum)` validator |
| `boolean` | -- | `Checkbox(label)` or `Switch()` | Direct mapping |
| `array` (of `$ref`) | -- | `DataTable()` or `ListView()` | Nested entity list |
| `array` (of primitives) | -- | `SelectionList()` | Multi-select |
| `object` | -- | `Collapsible()` with nested form | Recursive form generation |
| `$ref` | -- | `Select()` with entity options | Loaded from referenced model |
| `selfref` | -- | `Input(type="integer")` | Parent ID (nullable) |

### Display Mode Mapping

| JSON Schema Type | Widget Hint | Textual Widget | Notes |
|-----------------|------------|----------------|-------|
| `string` | -- | `Label(value)` or `Static(value)` | Plain text display |
| `string` | `ui.widget: "currency"` | `Label(f"${value:.2f}")` | Formatted currency |
| `string` | `ui.widget: "textarea"` | `Static(value)` | Block text |
| `number` / `integer` | -- | `Label(str(value))` | Number as text |
| `boolean` | -- | `Label("Yes" / "No")` or `Checkbox(disabled=True)` | Read-only toggle |
| `array` | -- | `DataTable()` | Read-only table |
| `$ref` | -- | `Label(f"[{ref_name}]")` | Clickable reference |

### Validation Constraint Mapping

| JSON Schema Constraint | Textual Validator | Applied To |
|-----------------------|-------------------|-----------|
| `required` | Widget-level `valid_empty=False` | Any Input |
| `minLength` / `maxLength` | `Length(min, max)` | Input, TextArea |
| `minimum` / `maximum` | `Number(minimum, maximum)` | Input(type="number") |
| `exclusiveMinimum` / `exclusiveMaximum` | Custom validator | Input(type="number") |
| `pattern` | `Input(restrict=pattern)` | Input |
| `enum` | Enforced by Select/RadioSet widget | Select |

---

## 5. N3TX's form.js vs. Theoretical TUI Formidable {#ntx-formjs-vs-tui}

N3TX's [`form.js`](/workspace/src/n3tx/static/generators/form.js) is a ~370-line module that reads JSON Schema properties and generates HTML form elements. The TUI equivalent would follow the **exact same logic flow** but output Textual widgets instead of HTML strings.

### Side-by-Side: form.js Logic vs. TUI Equivalent

**Step 1: Field ordering and filtering**

```javascript
// form.js (web) - lines 24-42
const fieldOrder = ui.field_order
    ? ui.field_order.filter(k => k in fields)
    : Object.keys(fields);

const renderableFields = fieldOrder.filter(key => {
    if (headerFields.includes(key)) return false;
    if (def?.ui?.display === false) return false;
    if (mode === 'edit' && def?.ui?.protected) return false;
    if (!permissions.canView(def)) return false;
    return true;
});
```

```python
# tui_form.py (theoretical TUI equivalent)
def get_renderable_fields(schema: dict, mode: str = "display") -> list[str]:
    fields = schema.get("properties", {})
    ui = schema.get("ui", {})
    field_order = ui.get("field_order", list(fields.keys()))
    field_order = [k for k in field_order if k in fields]
    # Safety: add unlisted fields
    for k in fields:
        if k not in field_order:
            field_order.append(k)

    HEADER_FIELDS = {"name", "id", "description"}
    return [
        key for key in field_order
        if key not in HEADER_FIELDS
        and fields[key].get("ui", {}).get("display") is not False
        and not (mode == "edit" and fields[key].get("ui", {}).get("protected"))
        and can_view(fields[key])
    ]
```

**Step 2: Widget selection (the core mapping)**

```javascript
// form.js - getInput() lines 173-236
if (widget === 'textarea' || type === 'text') {
    html.push(`<textarea ...>${value}</textarea>`);
} else if (widget === 'currency') {
    html.push(`<div class="currency-input">
        <span class="currency-symbol">$</span>
        <input type="number" step="0.01" ...>
    </div>`);
} else if (type === 'boolean') {
    html.push(`<input type="checkbox" ...>`);
} else if (type === 'string') {
    html.push(`<input type="text" ...>`);
} else if (type === 'number') {
    html.push(`<input type="number" ...>`);
} else if (type === 'array') {
    html.push(getListInput(ntt, key, mode));
}
```

```python
# tui_form.py (theoretical TUI equivalent)
from textual.widgets import Input, TextArea, Checkbox, Select, Label, Static
from textual.containers import Horizontal
from textual.validation import Number, Integer, Length

def get_widget(key: str, definition: dict, value=None, mode="edit"):
    """Map a JSON Schema property to a Textual widget."""
    widget_hint = definition.get("ui", {}).get("widget")
    schema_type = definition.get("type", "string")
    validators = build_validators(definition)

    if mode == "display":
        return get_display_widget(key, definition, value)

    if widget_hint == "textarea" or schema_type == "text":
        return TextArea(str(value or ""), id=key)

    elif widget_hint == "currency":
        return Horizontal(
            Label("$"),
            Input(value=str(value or ""), type="number",
                  id=key, validators=validators),
        )

    elif schema_type == "boolean":
        return Checkbox(
            definition.get("title", key),
            value=bool(value), id=key
        )

    elif schema_type == "string":
        enum_values = definition.get("enum")
        if enum_values:
            options = [(v, v) for v in enum_values]
            return Select(options, value=value, id=key)
        return Input(
            value=str(value or ""), type="text",
            placeholder=definition.get("ui", {}).get("placeholder", ""),
            max_length=definition.get("maxLength", 0),
            restrict=definition.get("pattern"),
            id=key, validators=validators,
        )

    elif schema_type in ("number", "integer"):
        input_type = "integer" if schema_type == "integer" else "number"
        return Input(
            value=str(value or ""), type=input_type,
            id=key, validators=validators,
        )

    elif schema_type == "array":
        return build_list_widget(key, definition, value)

    elif schema_type == "selfref":
        return Input(
            value=str(value or ""), type="integer",
            placeholder="Parent ID (optional)", id=key,
        )

    else:
        return Input(value=str(value or ""), id=key)
```

**Step 3: Validation attribute mapping**

```javascript
// form.js - validationAttrs() lines 159-171
function validationAttrs(def, isRequired = false) {
    const attrs = [];
    if (isRequired) attrs.push('required');
    if (def.minLength != null) attrs.push(`minlength="${def.minLength}"`);
    if (def.minimum != null) attrs.push(`min="${def.minimum}"`);
    if (def.pattern) attrs.push(`pattern="${def.pattern}"`);
    if (def.ui?.placeholder) attrs.push(`placeholder="${def.ui.placeholder}"`);
    return attrs.length ? ' ' + attrs.join(' ') : '';
}
```

```python
# tui_form.py - TUI equivalent
def build_validators(definition: dict) -> list:
    """Build Textual validators from JSON Schema constraints."""
    validators = []
    schema_type = definition.get("type", "string")

    if schema_type in ("number", "integer"):
        minimum = definition.get("minimum", definition.get("exclusiveMinimum"))
        maximum = definition.get("maximum", definition.get("exclusiveMaximum"))
        ValidatorClass = Integer if schema_type == "integer" else Number
        if minimum is not None or maximum is not None:
            validators.append(ValidatorClass(minimum=minimum, maximum=maximum))

    if schema_type == "string":
        min_len = definition.get("minLength")
        max_len = definition.get("maxLength")
        if min_len is not None or max_len is not None:
            validators.append(Length(minimum=min_len, maximum=max_len))

    return validators
```

**Step 4: Grouped fields**

```javascript
// form.js - renderGroupedFields() lines 87-126
for (const [groupName, groupFields] of Object.entries(groups)) {
    html.push(`<fieldset class="ntx-group">`);
    html.push(`<legend>${groupName}</legend>`);
    html.push(fieldsInGroup.map(key => getInput(ntt, key, mode)).join(''));
    html.push(`</fieldset>`);
}
```

```python
# tui_form.py - TUI equivalent using TabbedContent
from textual.widgets import TabbedContent, TabPane

def build_grouped_form(schema, values, mode="edit"):
    """Render fields in tabbed groups from schema.ui.groups."""
    groups = schema.get("ui", {}).get("groups", {})
    renderable = get_renderable_fields(schema, mode)

    if not groups:
        # Flat form -- all fields in a single container
        return [get_widget(k, schema["properties"][k], values.get(k), mode)
                for k in renderable]

    grouped = set()
    tabs = []
    for group_name, group_fields in groups.items():
        fields_in_group = [k for k in group_fields if k in renderable]
        if not fields_in_group:
            continue
        grouped.update(fields_in_group)
        widgets = [get_widget(k, schema["properties"][k], values.get(k), mode)
                   for k in fields_in_group]
        tabs.append(TabPane(group_name, *widgets))

    # Ungrouped fields go at the end
    ungrouped = [k for k in renderable if k not in grouped]
    if ungrouped:
        widgets = [get_widget(k, schema["properties"][k], values.get(k), mode)
                   for k in ungrouped]
        tabs.append(TabPane("Other", *widgets))

    return [TabbedContent(*tabs)]
```

### Structural Comparison

| Concern | form.js (Web) | TUI Formidable (Textual) |
|---------|---------------|--------------------------|
| Field ordering | `ui.field_order` array | Same -- identical logic |
| Field filtering | `ui.display`, `ui.protected`, permissions | Same -- identical logic |
| Widget selection | `type` + `ui.widget` hint | Same -- mapped to Textual widgets |
| Validation | HTML5 attributes (`min`, `max`, `pattern`) | Textual validators (`Number`, `Length`) |
| Groups | `<fieldset>` + `<legend>` | `TabbedContent` + `TabPane` |
| Display mode | `<div data-value>` static text | `Label()` / `Static()` widgets |
| Edit mode | `<input>`, `<textarea>`, `<select>` | `Input()`, `TextArea()`, `Select()` |
| Array fields | Nested `<ntx-item>` components | `DataTable()` or `ListView()` |
| Method buttons | `<ntx-method>` component | `Button()` with action handlers |
| Code size | ~370 lines JavaScript | Estimated ~400 lines Python |

---

## 6. Reactive Data Binding: Web Components vs. Textual {#reactive-data-binding}

One of N3TX's most powerful patterns is the DynamicClass system ([`N3TX.js`](/workspace/src/n3tx/static/core/N3TX.js)) where schema properties become reactive getters/setters on entity instances. Textual has a **remarkably similar** reactivity system.

### Comparison Table

| Feature | N3TX Web (N3TX.js) | Textual (Python) |
|---------|--------------------|--------------------|
| Reactive declarations | `Object.defineProperty(proto, field, {get, set})` | `attribute = reactive("default")` |
| Change detection | Setter fires `this.signal()` | Setter auto-triggers `render()` |
| Watch/observe | `entity.signal(callback)` | `watch_attribute(old, new)` method |
| Computed values | Not built-in (manual in getter) | `compute_attribute()` auto-cached |
| Validation on set | `isTypeCompatible(value, type)` check | `validate_attribute(value)` method |
| Data binding | `entity.watch(component_addr)` | `widget.data_bind(Parent.attr)` |
| Batch updates | Single-tick signal coalescing | Textual batches into single refresh |

### DynamicClass in Textual

N3TX's `prototype()` function creates DynamicClasses at runtime from schema. A Textual equivalent could use Python's `type()` or class decoration:

```python
def create_entity_widget(schema: dict):
    """Create a Textual Widget subclass from a JSON Schema -- analogous to
    N3TX.js prototype() creating DynamicClasses."""
    class_name = schema["__name__"]
    fields = schema.get("properties", {})

    # Build reactive attributes for each schema field
    attrs = {}
    for field_name, definition in fields.items():
        attrs[field_name] = reactive(definition.get("default"))

    # Create the class dynamically
    EntityWidget = type(
        f"{class_name}Form",
        (Widget,),
        {
            "_schema": schema,
            **attrs,
            "compose": lambda self: self._build_form(),
            "_build_form": lambda self: build_grouped_form(
                schema, {k: getattr(self, k) for k in fields}, "edit"
            ),
        }
    )
    return EntityWidget
```

> **Key Insight:** Textual's `reactive()` + `watch_*()` + `data_bind()` is structurally equivalent to N3TX's `Object.defineProperty()` + `signal()` + `watch()`. The DynamicClass pattern ports almost 1:1.

---

## 7. Read-Only Rendering: Lists and Detail Views {#read-only-rendering}

N3TX's [`ntx-list.js`](/workspace/src/n3tx/static/components/ntx-list.js) and [`ntx-item.js`](/workspace/src/n3tx/static/components/ntx-item.js) handle entity collection and detail rendering. Terminal equivalents using Rich tables and Textual DataTable are straightforward.

### Entity List View: ntx-list -> DataTable

N3TX's `ListElement` ([source](/workspace/src/n3tx/static/components/ListElement.js)) manages pagination, stamping child elements, and surgical DOM updates. The Textual equivalent uses `DataTable`:

```python
from textual.widgets import DataTable, Footer, Header, Button
from textual.app import ComposeResult

class EntityList(Widget):
    """TUI equivalent of <ntx-list>. Renders entity collection as a DataTable."""

    def __init__(self, schema: dict, entities: list[dict]):
        super().__init__()
        self._schema = schema
        self._entities = entities

    def compose(self) -> ComposeResult:
        # Determine visible columns from schema field_order
        props = self._schema.get("properties", {})
        ui = self._schema.get("ui", {})
        columns = ui.get("field_order", list(props.keys()))
        columns = [c for c in columns if props.get(c, {}).get("ui", {}).get("display") is not False]

        table = DataTable(id="entity-table")
        yield table
        yield Button("Load More", id="load-more")

    def on_mount(self):
        table = self.query_one("#entity-table", DataTable)
        props = self._schema["properties"]
        for col in self._visible_columns():
            label = props[col].get("title", col)
            table.add_column(label, key=col)
        for entity in self._entities:
            row = [self._format_cell(col, entity.get(col)) for col in self._visible_columns()]
            table.add_row(*row, key=str(entity.get("id")))
```

### Entity Detail View: ntx-item sizes -> Textual layouts

N3TX's `NTTItem` renders at 5 sizes (xs/sm/md/lg/xl). The TUI equivalent:

| Web Size | Web Layout | TUI Equivalent |
|----------|-----------|----------------|
| `xs` | Pill badge (name only) | `Label(entity.name)` inline |
| `sm` | Compact row: thumb + name + 3 fields | `Horizontal(Label, Label, Label)` |
| `md` | Card: image + full form + methods | `Vertical(form_widgets + Button(methods))` |
| `lg` | Detail: expanded card | Full-screen form with all fields |
| `xl` | Page: full metadata | Tabbed detail with metadata panes |

### Rich Tables for Static Output

For CLI (non-interactive) output, [Rich tables](https://rich.readthedocs.io/en/stable/tables.html) map directly:

```python
from rich.table import Table
from rich.console import Console

def render_entity_table(schema: dict, entities: list[dict]):
    """Render entities as a Rich table -- CLI equivalent of ntx-list."""
    table = Table(title=f"{schema['__name__']}s")
    props = schema.get("properties", {})
    columns = schema.get("ui", {}).get("field_order", list(props.keys()))

    for col in columns:
        if props.get(col, {}).get("ui", {}).get("display") is False:
            continue
        table.add_column(props[col].get("title", col))

    for entity in entities:
        row = [format_value(props[col], entity.get(col)) for col in columns
               if props.get(col, {}).get("ui", {}).get("display") is not False]
        table.add_row(*row)

    Console().print(table)
```

### DataTable Performance

For large entity lists, Textual's built-in `DataTable` handles **thousands of rows** with virtual scrolling. For extreme cases (100k+ rows), [textual-fastdatatable](https://github.com/tconbeer/textual-fastdatatable) provides a performance-focused reimplementation backed by Apache Arrow.

---

## 8. The Isomorphic Form Architecture {#isomorphic-form-architecture}

The ultimate goal: **one schema, two renderers**. N3TX's backend generates JSON Schema once; `form.js` renders it in browsers; a new `tui_form.py` renders it in terminals. The schema contract is the abstraction layer.

### Architecture Diagram

```
                    N3TX Backend
                    ==============
  Model Definition (Python)
         |
         v
  ProtoModel.schema()  -----> JSON Schema
         |                     (single source of truth)
         |                          |
         v                          v
  register_routes()           Schema served at
  (CRUD API)                  GET /{ClassName}
                                    |
                    +---------------+---------------+
                    |                               |
              Web Frontend                    TUI Frontend
              ============                    ============
         N3TX.SCHEMA(data)               schema_to_form(data)
              |                               |
              v                               v
         prototype()                   create_entity_widget()
         DynamicClass                  ReactiveWidgetClass
              |                               |
              v                               v
         form.js                         tui_form.py
         getInput()                      get_widget()
              |                               |
              v                               v
    HTML: <input>, <select>,          Textual: Input(), Select(),
    <textarea>, <checkbox>            TextArea(), Checkbox()
              |                               |
              v                               v
        Browser DOM                    Terminal Screen
```

### What Is Shared vs. Renderer-Specific

| Layer | Shared (Backend) | Web-Specific (form.js) | TUI-Specific (tui_form.py) |
|-------|-----------------|----------------------|---------------------------|
| Schema generation | ProtoModel.schema() | -- | -- |
| API transport | GET /{ClassName}, CRUD routes | fetch() / NetworkAdapter | httpx / aiohttp |
| Field ordering | `ui.field_order` in schema | Iterated in getForm() | Iterated in build_form() |
| Field filtering | `ui.display`, `ui.protected` | Filtered in renderableFields | Filtered in get_renderable_fields() |
| Validation rules | `minLength`, `minimum`, `pattern` | HTML5 attributes | Textual validators |
| Widget hints | `ui.widget` in schema | getInput() switch | get_widget() switch |
| Groups | `ui.groups` in schema | `<fieldset>` | TabbedContent/Collapsible |
| Access control | `access` in schema | Permissions.js | Python permission checker |
| Methods | `methods` in schema | `<ntx-method>` component | `Button()` + API call |

### The Abstraction Layer

The key insight is that **no new abstraction layer is needed**. The JSON Schema already IS the abstraction. Both renderers consume the same schema and independently decide how to visualize each property. This is fundamentally different from approaches like RJSF's `uiSchema` which requires a separate rendering description.

```
                  N3TX's Advantage
                  ==================

  RJSF:        JSON Schema  +  uiSchema  +  Theme  =  Form
                (structure)    (rendering)   (style)

  N3TX Web:   JSON Schema (with ui hints baked in)  =  Form
                (structure + rendering in one)

  N3TX TUI:   Same JSON Schema                      =  TUI Form
                (same hints, different consumer)
```

---

## 9. Textual CSS: Shared Design Tokens {#textual-css-shared-design-tokens}

[Textual CSS](https://textual.textualize.io/guide/CSS/) (TCSS) uses a subset of web CSS syntax, making it possible to share design intent -- if not exact tokens -- between web and terminal renderers.

### Web CSS vs. Textual CSS Comparison

| Feature | Web CSS | Textual CSS |
|---------|---------|-------------|
| Selectors | Type, class, ID, attribute | Type, class, ID (no attribute) |
| Variables | `--var-name: value` | `$var-name: value` |
| Layouts | Flexbox, Grid, Block | Horizontal, Vertical, Grid |
| Colors | Full RGB/HSL/hex | 16M colors (terminal-dependent) |
| Fonts | Any web font | Terminal monospace only |
| Units | px, em, rem, %, vw, vh | cells, %, vw, vh, fr |
| Pseudo-classes | `:hover`, `:focus`, `:nth-child` | `:hover`, `:focus`, `:dark`, `:light` |
| Nesting | Native (modern CSS) | Supported with `&` |
| Media queries | `@media (min-width)` | Not supported (terminal is terminal) |
| Specificity | Standard cascade | Same rules |

### Shared Token Strategy

While exact CSS cannot be shared, **design intent** can be expressed in a shared token file:

```yaml
# design-tokens.yml (shared between web and TUI)
colors:
  primary: "#3b82f6"
  danger: "#ef4444"
  success: "#22c55e"
  muted: "#6b7280"

spacing:
  field-gap: 1       # web: 1rem, tui: 1 cell
  group-gap: 2       # web: 2rem, tui: 2 cells
  form-padding: 2    # web: 2rem, tui: 2 cells

borders:
  field: "round"     # web: border-radius, tui: round box style
```

This generates both:

```css
/* web/tokens.css */
:root {
  --color-primary: #3b82f6;
  --spacing-field-gap: 1rem;
}
```

```tcss
/* tui/tokens.tcss */
$primary: #3b82f6;
$field-gap: 1;
```

### Textual-Web: The Bridge

A remarkable capability: [Textual apps can run in web browsers](https://textual.textualize.io/blog/2024/09/08/towards-textual-web-applications/) via `textual serve`. This means a TUI admin could be served to a browser with **zero frontend code changes** -- the terminal rendering is streamed via WebSocket and displayed using xterm.js. This gives you three deployment modes from one codebase:

1. **Browser (native web)** -- N3TX's form.js web frontend
2. **Terminal (native TUI)** -- Textual TUI frontend
3. **Browser (served TUI)** -- `textual serve` streams TUI to browser

---

## 10. Interactive CRUD in TUI {#interactive-crud-in-tui}

A full schema-driven TUI admin requires entity listing, detail viewing, form editing, and entity creation -- all from schema, all in the terminal.

### CRUD Flow Architecture

```
TUI App (Textual)
====================
+-------------------------------------------+
|  Header: "N3TX Admin - Products"        |
+-------------------------------------------+
|                                           |
|  [DataTable: Entity List]                 |
|  +-------+----------+--------+---------+  |
|  | ID    | Name     | Price  | Status  |  |
|  +-------+----------+--------+---------+  |
|  | 1     | Widget A | $29.99 | Active  |  |
|  | 2     | Widget B | $49.99 | Draft   |  |
|  | 3     | Gadget C | $19.99 | Active  |  |
|  +-------+----------+--------+---------+  |
|                                           |
|  [n] New  [e] Edit  [d] Delete  [q] Quit |
+-------------------------------------------+
|  Footer: Key bindings                     |
+-------------------------------------------+

      |                   |
      | [Enter] or [e]    | [n]
      v                   v

+------------------+  +------------------+
| Detail/Edit View |  | Create Form      |
| (schema-driven)  |  | (schema-driven)  |
|                  |  |                  |
| Name: [Widget A] |  | Name: [________] |
| Price: [$29.99 ] |  | Price: [$______] |
| Desc: [________] |  | Desc: [________] |
| [Save] [Cancel]  |  | [Create][Cancel] |
+------------------+  +------------------+
```

### Keyboard Navigation Model

| Key | Action | Equivalent Web Action |
|-----|--------|----------------------|
| `j` / Down | Move cursor down in list | Scroll list |
| `k` / Up | Move cursor up in list | Scroll list |
| `Enter` | View entity detail | Click entity card |
| `e` | Edit current entity | Click edit button |
| `n` | Create new entity | Click create button |
| `d` | Delete (with confirm) | Click delete button |
| `Tab` | Next field (in form) | Tab between inputs |
| `Escape` | Back to list | Navigate back |
| `/` | Filter/search | Search box |
| `q` | Quit | Close browser tab |

### Screen Architecture

```python
from textual.app import App, ComposeResult
from textual.screen import Screen

class EntityListScreen(Screen):
    """Schema-driven entity list -- TUI equivalent of <ntx-list>."""

    BINDINGS = [
        ("n", "new_entity", "New"),
        ("e", "edit_entity", "Edit"),
        ("d", "delete_entity", "Delete"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, schema: dict, api_url: str):
        super().__init__()
        self.schema = schema
        self.api_url = api_url

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="entities")
        yield Footer()

    async def on_mount(self):
        # Fetch entities from N3TX API
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.api_url}/{self.schema['__tablename__']}")
            data = resp.json()
        self._populate_table(data["data"] if "data" in data else data)

    def action_edit_entity(self):
        table = self.query_one("#entities", DataTable)
        row_key = table.cursor_row
        entity_id = table.get_row_at(row_key)[0]  # ID column
        self.app.push_screen(EntityFormScreen(self.schema, entity_id, mode="edit"))


class EntityFormScreen(Screen):
    """Schema-driven form -- TUI equivalent of <ntx-item> in edit mode."""

    def __init__(self, schema: dict, entity_id=None, mode="create"):
        super().__init__()
        self.schema = schema
        self.entity_id = entity_id
        self.mode = mode

    def compose(self) -> ComposeResult:
        yield Header()
        # Generates all form widgets from schema
        yield from build_grouped_form(self.schema, self._values, self.mode)
        yield Horizontal(
            Button("Save" if self.mode == "edit" else "Create", variant="primary"),
            Button("Cancel", variant="default"),
        )
        yield Footer()
```

### Method Buttons

N3TX's `@expose_route` methods appear as buttons in the web UI via `<ntx-method>`. The TUI equivalent:

```python
def build_method_buttons(schema: dict, entity_id: str) -> list[Button]:
    """Generate action buttons from schema.methods -- TUI ntx-method."""
    buttons = []
    for method_name, method_def in schema.get("methods", {}).items():
        label = method_def.get("title", method_name)
        icon = method_def.get("ui", {}).get("icon", "")
        btn = Button(f"{icon} {label}", id=f"method-{method_name}")
        buttons.append(btn)
    return buttons
```

---

## 11. Limitations and Graceful Degradation {#limitations-and-graceful-degradation}

Not everything from the web UI translates to terminal. Being honest about boundaries prevents over-promising.

### What Translates Well

| Web Feature | TUI Mapping | Fidelity |
|------------|------------|----------|
| Text inputs | Input widget | 100% -- identical semantics |
| Number inputs | Input(type="number") | 100% -- with validators |
| Checkboxes | Checkbox / Switch | 100% |
| Dropdowns | Select widget | 100% |
| Text areas | TextArea widget | 95% -- no rich text, but syntax highlighting |
| Data tables | DataTable | 95% -- virtual scrolling, sorting |
| Field groups | TabbedContent | 90% -- tabs instead of fieldsets |
| Validation feedback | Validation events | 90% -- inline errors |
| Pagination | Button + API calls | 100% |
| Method buttons | Button widget | 100% |
| Keyboard navigation | Textual key bindings | Better than web (keyboard-first) |
| Permissions (show/hide) | Conditional compose | 100% -- same schema access rules |

### What Does NOT Translate

| Web Feature | TUI Limitation | Graceful Degradation |
|------------|---------------|---------------------|
| Image display | Terminal cannot render images* | Show URL or `[Image: filename]` placeholder |
| Color pickers | No color widget | Hex input with preview using background color |
| File uploads | No drag-and-drop | File path input with DirectoryTree browser |
| Maps / geo | No map rendering | Lat/lng number inputs |
| Rich text (WYSIWYG) | No bold/italic/link editing | Markdown TextArea with preview |
| Video / audio | Impossible | Show URL link |
| Drag-and-drop reorder | No pointer support** | Arrow keys + Ctrl+Up/Down |
| Inline images in lists | No image rendering | Text-only list rows |
| Custom CSS animations | No animation support | Static layout |

*Some terminals (iTerm2, Kitty) support inline images via protocols, but this is not portable.
**Textual does support mouse events, so basic click-to-select works.

### The 80/20 Rule

For **CRUD administration** -- the primary use case -- approximately **85-90% of web form functionality** maps directly to TUI widgets. The remaining 10-15% is media-specific (images, video, rich text) and can be gracefully degraded to text representations.

> **Key Insight:** The features that don't translate (images, rich media, color pickers) are rarely critical for admin workflows. A developer managing products, users, or comments cares about **reading and editing text and numbers** -- exactly what terminals excel at. The TUI admin is not a replacement for the web UI; it is a power-user complement.

---

## 12. Implementation Roadmap {#implementation-roadmap}

### Phase 1: Schema-to-Form Engine (2-3 weeks)

**Deliverable:** `tui_form.py` -- the Textual equivalent of `form.js`

| Task | Effort | Dependencies |
|------|--------|-------------|
| Schema fetching (HTTP client for `GET /{ClassName}`) | 2 days | httpx |
| `get_widget()` -- type-to-widget mapping function | 3 days | Textual widgets |
| `build_validators()` -- schema constraints to validators | 1 day | Textual validation |
| `build_grouped_form()` -- field ordering + groups | 2 days | TabbedContent |
| Display mode (read-only rendering) | 1 day | Label/Static |
| Edit mode (interactive inputs) | 2 days | Input/Select/etc |
| Unit tests | 2 days | pytest |

### Phase 2: Entity CRUD Screens (2-3 weeks)

**Deliverable:** `EntityListScreen`, `EntityFormScreen`, `EntityDetailScreen`

| Task | Effort | Dependencies |
|------|--------|-------------|
| List screen with DataTable | 3 days | DataTable, API client |
| Detail screen (read-only) | 2 days | tui_form.py display mode |
| Create screen (form + POST) | 2 days | tui_form.py edit mode |
| Edit screen (form + PUT) | 1 day | Builds on Create |
| Delete confirmation | 1 day | Textual Screen |
| Pagination (Load More) | 1 day | API pagination params |
| Method buttons | 2 days | Button + API calls |
| Keyboard bindings | 1 day | Textual Bindings |

### Phase 3: CLI Integration (1 week)

**Deliverable:** `n3tx admin` CLI command

```bash
# Start the TUI admin
n3tx admin --url http://localhost:5000

# Quick entity listing (non-interactive, Rich tables)
n3tx list products --limit 20
n3tx show Product/1

# Quick entity CRUD
n3tx create Product --name "Widget" --price 29.99
n3tx update Product/1 --price 39.99
n3tx delete Product/1
```

### Phase 4: Polish and Advanced Features (2+ weeks)

- Search/filter in entity lists
- Schema caching (avoid re-fetch)
- Authentication flow (login screen)
- Textual CSS theming
- Shared design tokens (web + TUI)
- `textual serve` deployment option

### Total Estimated Effort: 7-10 weeks

For a single developer. The core value (Phase 1 + 2) is deliverable in **4-6 weeks**.

---

## 13. Sources {#sources}

### Web Schema-to-Form Libraries
- [react-jsonschema-form (RJSF)](https://github.com/rjsf-team/react-jsonschema-form) -- React form generation from JSON Schema, 14k+ stars
- [RJSF Widget Documentation](https://rjsf-team.github.io/react-jsonschema-form/docs/usage/widgets/) -- Default widget mapping reference
- [RJSF uiSchema Reference](https://rjsf-team.github.io/react-jsonschema-form/docs/api-reference/uiSchema/) -- UI customization specification
- [FormKit Schema](https://formkit.com/essentials/schema) -- Vue schema-first form builder
- [Form.io JSON Forms](https://form.io/json-forms/) -- Multi-framework JSON form builder
- [Form.io Schema Architecture](https://form.io/features/form-from-json-schema/) -- Schema-driven dynamic forms

### Textual Framework
- [Textual Documentation](https://textual.textualize.io/) -- Official framework docs
- [Textual Widget Gallery](https://textual.textualize.io/widget_gallery/) -- Complete widget inventory
- [Textual Input Widget](https://textual.textualize.io/widgets/input/) -- Input configuration, types, validators
- [Textual CSS Guide](https://textual.textualize.io/guide/CSS/) -- CSS-like styling for TUI
- [Textual Reactivity](https://textual.textualize.io/guide/reactivity/) -- Reactive attributes, watchers, data binding
- [Textual DataTable](https://textual.textualize.io/widgets/data_table/) -- Data grid widget
- [Textual Select Widget](https://textual.textualize.io/widgets/select/) -- Dropdown selection
- [Textual Validation API](https://textual.textualize.io/api/validation/) -- Built-in validators
- [Textual GitHub Repository](https://github.com/Textualize/textual) -- 33.8k stars, source code
- [Textual Web: Browser-Based TUIs](https://textual.textualize.io/blog/2024/09/08/towards-textual-web-applications/) -- Serving TUI apps in browsers
- [Textual-Web GitHub](https://github.com/Textualize/textual-web) -- Run TUIs in browser
- [Textual TUI Widgets 2025](https://johal.in/textual-tui-widgets-python-rich-terminal-user-interfaces-apps-2025/) -- 250k+ PyPI downloads Q1 2025

### Terminal Schema Tools
- [SchemaUI (Rust)](https://github.com/YuniqueUnic/schemaui) -- JSON Schema to TUI forms, 37 stars
- [SchemaUI Crate](https://crates.io/crates/schemaui) -- Rust package registry
- [SchemaUI Documentation](https://docs.rs/schemaui) -- API docs
- [django-admin-tui](https://github.com/valberg/django-admin-tui) -- Django admin in terminal, 55 stars
- [textual-forms](https://github.com/rhymiz/textual-forms) -- Manual form builder for Textual, 6 stars
- [textual-fastdatatable](https://github.com/tconbeer/textual-fastdatatable) -- Performance-focused DataTable

### Database CLI Tools
- [pgcli](https://github.com/dbcli/pgcli) -- PostgreSQL CLI with autocompletion
- [litecli](https://www.pgcli.com/launching-litecli.html) -- SQLite CLI client

### Rich Library
- [Rich Tables Documentation](https://rich.readthedocs.io/en/stable/tables.html) -- Terminal table rendering
- [Rich GitHub](https://github.com/Textualize/rich) -- Rich text formatting library

### Python / Pydantic
- [Pydantic JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/) -- Schema generation from models
- [Real Python: Textual Tutorial](https://realpython.com/python-textual/) -- Comprehensive Textual guide
- [Contact Book CRUD with Textual](https://realpython.com/contact-book-python-textual/) -- Full CRUD TUI tutorial
- [Building Terminal and Web UIs with Textual](https://www.blog.brightcoding.dev/2025/08/29/building-terminal-and-web-uis-in-python-with-textual/) -- Dual deployment guide

### General Architecture
- [Isomorphic Rendering (Airbnb)](https://medium.com/airbnb-engineering/isomorphic-javascript-the-future-of-web-apps-10882b7a2ebc) -- Multi-environment rendering patterns
- [Isomorphic Web Components](https://jakelazaroff.com/words/isomorphic-web-components/) -- Universal component patterns

---

*Research conducted February 2026. All statistics and version numbers reflect the latest available data.*