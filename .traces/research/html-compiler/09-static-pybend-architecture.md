# Static Site Generation: Mapping to PyBend's Architecture

**Research Document 04** | February 2026
**Audience:** Technical CEO + Engineering Team

---

## Executive Summary

PyBend's rendering pipeline is a four-stage chain: **Model Definition -> JSON Schema -> JavaScript DynamicClass -> Shadow DOM HTML**. A static site exporter (`pybend export --static`) would short-circuit this chain by replacing stages 3-4 with server-side Python templates that consume the same schema and data. This document maps every rendering decision currently made in JavaScript to its Python-side equivalent, identifies the exact boundaries between "purely presentational" and "requires JavaScript," and proposes a concrete architecture.

**Key finding:** Approximately 75% of the frontend rendering logic is presentational HTML generation that can be replicated server-side with Jinja2 templates. The remaining 25% (Actor messaging, live updates, form submission, auth-gated interactions) can be cleanly omitted for a read-only static export.

---

## 1. PyBend's Current Rendering Pipeline

### 1.1 End-to-End Data Flow

```
Python Model (Product)
      |
      v  ProtoModel.schema() --- generates JSON Schema
      |
      v  GET /Product ---------- serves schema over HTTP
      |
      v  NTT.SCHEMA(data) ------ creates DynamicClass via prototype()
      |
      v  DynamicClass.READ() --- fetches /products?limit=20&offset=0
      |
      v  NTTItem.render() ------ dispatches to xs/sm/md/lg/xl size method
      |
      v  Formidable.getForm() -- generates HTML from schema.properties
      |
      v  Shadow DOM ------------ committed to browser
```

**For static export, we replace the bottom four steps:**

```
Python Model (Product)
      |
      v  ProtoModel.schema() --- same schema generation
      |
      v  StorableMixin.list() -- direct DB access (no HTTP)
      |
      v  Jinja2 templates ------ replicate form.js / ntt-item.js logic
      |
      v  HTML files ------------ written to disk
```

### 1.2 Key Source Files in the Pipeline

| Stage | File | Lines | Role |
|-------|------|-------|------|
| Schema gen | `src/pybend/core/models/proto_model.py` | ~430 | `schema()`, `model_dump(response=True)` |
| Data access | `src/pybend/core/storage/sqlite_storage.py` | ~250 | `list()`, `get()` with FK hydration |
| JS bootstrap | `src/pybend/static/core/NTT.js` | ~1083 | `SCHEMA()`, `prototype()`, DynamicClass |
| Form rendering | `src/pybend/static/generators/form.js` | ~368 | `getForm()`, `getInput()`, `getListInput()` |
| Item rendering | `src/pybend/static/components/ntt-item.js` | ~660 | `xs()`, `sm()`, `md()`, `lg()`, `xl()` |
| List rendering | `src/pybend/static/components/ListElement.js` | ~244 | `render()`, `createChild()` |
| Permissions | `src/pybend/static/utils/Permissions.js` | ~191 | `canView()`, `canEdit()`, `canAction()` |

---

## 2. What `form.js` Does -- The Server-Side Replication Target

`form.js` (exported as `Formidable`) is the single most important file to replicate. It reads schema properties and produces HTML strings. The logic is entirely deterministic -- given a schema and a value, the same HTML is always produced.

### 2.1 `getForm()` Logic Map

```
getForm(ntt, mode="display", attachedMethods={})
  |
  |--> Read schema.properties, schema.ui
  |--> Determine fieldOrder:
  |      schema.ui.field_order (filtered to existing fields)
  |      || Object.keys(schema.properties)
  |      + any missing fields appended
  |
  |--> Generate $header via getHeader():
  |      display mode: <h2>name</h2> + <h4>description</h4>
  |      edit mode:    <input> for name + <textarea> for description
  |
  |--> Filter renderableFields:
  |      Exclude: headerFields (name, id, description)
  |      Exclude: ui.display === false
  |      Exclude: ui.protected (in edit mode)
  |      Exclude: !permissions.canView(def)
  |
  |--> If schema.ui.groups defined:
  |      renderGroupedFields() -> <fieldset class="ntt-group">
  |                                 <legend>groupName</legend>
  |                                 ...fields...
  |                               </fieldset>
  |--> Else:
  |      renderableFields.map(key => getInput(ntt, key, mode))
  |
  |--> Return $header.concat($fields).join('')
```

### 2.2 `getInput()` Type Dispatch Table

This is the core field renderer. For static export, we only need the **display** branch:

| Schema Type | Widget Override | Display HTML | Edit HTML |
|-------------|----------------|-------------|-----------|
| `string` | (none) | `<div data-value="key">value</div>` | `<input type="text">` |
| `string` | `textarea` | `<div class="text-block">value</div>` | `<textarea>value</textarea>` |
| `number` | (none) | `<div data-value="key">value</div>` | `<input type="number">` |
| `number` | `currency` | `<div class="currency-display">$X.XX</div>` | `<div class="currency-input"><span>$</span><input type="number">` |
| `boolean` | (none) | `<div>value</div>` | `<input type="checkbox">` |
| `$ref` | (none) | `<div>[Reference: name/id]</div>` | N/A |
| `selfref` | (none) | `<div>(top-level)</div>` or `[Parent: #N]` | `<input type="number">` |
| `array` | (none) | `getListInput()` -> nested `<ntt-item>` tags | Same |

### 2.3 `getListInput()` -- Nested Collection Rendering

```
getListInput(ntt, key, mode):
  VISIBLE_COUNT = 2

  -> Extract modelName from items.$ref
  -> Resolve childTag from $defs[modelName].ui.renderer.item
  -> Count refs in value array

  -> Emit:
     <div class="list-field" data-model="Comment">
       <div class="list-field-header">
         <span class="list-field-label">COMMENT</span>
         <span class="list-field-count">5</span>
       </div>
       <ntt-item ref="http://.../1" display="sm">  // first 2 visible
       <ntt-item ref="http://.../2" display="sm">
       <div class="nested-collapsed">              // rest collapsed
         <ntt-item ref="http://.../3" display="sm">
         ...
       </div>
       <button class="show-more-btn">Show 3 more</button>
     </div>
```

**For static export:** Replace `<ntt-item ref="...">` with pre-rendered HTML for each child entity. The "show more" toggle becomes a `<details>/<summary>` element or is fully expanded.

### 2.4 Python Jinja2 Equivalent

The entire `getInput()` dispatch table translates to a single Jinja2 macro:

```python
# Proposed: src/pybend/core/export/templates/field.html.j2

{% macro render_field(key, field_def, value, mode="display") %}
  {% set widget = field_def.get('ui', {}).get('widget') %}
  {% set type = field_def.get('type', 'string') %}

  {% if key not in ('name', 'id') and type != 'array' %}
    <label class="{{ model_name }} {{ model_name }}-form-item">
      {{ field_def.get('title', key) }}
    </label>
  {% endif %}

  {% if mode == 'display' %}
    {% if widget == 'currency' %}
      <div class="currency-display" data-value="{{ key }}">
        ${{ "%.2f"|format(value) if value is number else value }}
      </div>
    {% elif widget == 'textarea' %}
      <div class="text-block" data-value="{{ key }}">{{ value }}</div>
    {% elif type == 'selfref' %}
      <div data-value="{{ key }}">
        {{ '[Parent: #%s]'|format(value) if value else '(top-level)' }}
      </div>
    {% elif type == 'array' %}
      {{ render_list_field(key, field_def, value, schema) }}
    {% else %}
      <div data-value="{{ key }}">{{ value }}</div>
    {% endif %}
  {% endif %}
{% endmacro %}
```

---

## 3. What `ntt-item.js` Needs Per Size -- Pre-computation Analysis

### 3.1 Size Method Data Requirements

Each size method in `NTTItem` accesses a specific subset of the entity data:

| Size | Data Accessed | Schema Accessed | Can Pre-compute? |
|------|--------------|-----------------|-------------------|
| **xs** | `value.name`, `value.title` | `schema.__name__` | Yes -- trivial |
| **sm** | `value.name`, `value.image`, all `field_order` fields (up to 3), `value.id` | `schema.properties`, `schema.ui.field_order`, `schema.access`, `schema.methods` | Yes -- all static data |
| **md** | All renderable fields, `value.image` | Full schema: properties, ui.groups, access, methods | Yes -- delegates to `Formidable.getForm()` |
| **lg** | Same as md | Same as md | Yes -- currently identical to md |
| **xl** | Same as md | Same as md | Yes -- currently identical to md |

**Conclusion:** All five sizes are fully deterministic given (schema, value) and can be pre-computed server-side.

### 3.2 `sm()` Rendering Logic

The `sm()` method is the most complex adaptive renderer. It has specific logic:

```
sm():
  1. Filter renderable fields via #smFields():
     - Respect ui.field_order
     - Skip: id, ui.display=false, array, selfref, !canView()

  2. Iterate fields:
     - First $ref field -> leadingHtml (avatar/pill)
     - 'name' field -> sm-name identity text
     - Next 3 fields -> sm-field inline values

  3. Build layout:
     If leading $ref:  [avatar] [name + fields vertically] [methods] [actions]
     Otherwise:        [thumb?] [name] [fields inline]     [methods] [actions]

  4. Inject method buttons (layout='button' only): like, favorite icons

  5. Inject action buttons (edit/delete) gated by permissions
```

**For static export:** The permission checks become a build-time decision (see Section 7). Method buttons (like/favorite) require JS interaction and would be omitted or rendered as static counts.

### 3.3 `md()` Rendering Logic

```
md():
  1. Permission-gated action buttons (edit/delete) -> omit for static
  2. Image banner if value.image exists
  3. Split methods: attached (go into form groups) vs standalone
  4. Formidable.getForm(ntt, mode, attached) -> full field rendering
  5. Standalone method buttons at bottom -> omit for static
```

---

## 4. The CSS Situation

### 4.1 Current CSS File Inventory

| File | Size | Scope | Static-Exportable? |
|------|------|-------|--------------------|
| `dark-theme.css` | ~408 lines | Design tokens (`:root`), page layout, typography, buttons, inputs | Yes -- core design system |
| `light-theme.css` | ~119 lines | Light theme overrides (`[data-theme="light"]`) | Yes -- CSS var overrides |
| `schema.css` | ~442 lines | Kitchen Sink page-specific styles | Partial -- layout classes useful |
| `ntt-item.css` | ~669 lines | All size variants (xs/sm/md/lg/xl), card styles, nested lists | Yes -- **critical** |
| `ntt-list.css` | ~81 lines | List header, grid, load-more button | Yes |
| `ntt-element.css` | ~71 lines | Loading/error/empty states, dirty/committing indicators | Partial -- states are JS |
| `ntt-router.css` | (exists) | Router component styles | No -- navigation is JS |

### 4.2 Shadow DOM vs Static CSS

**Problem:** Today, component CSS lives inside Shadow DOM. Each `<ntt-item>` loads `ntt-item.css` into its shadow root. For static export, Shadow DOM does not exist.

**Solution:** Extract all component CSS into a single flattened stylesheet with scoped selectors:

```css
/* static-export.css — compiled from component CSS */

/* From ntt-item.css — prefix with .ntt-item to replace :host */
.ntt-item {
    display: block;
    animation: staggerIn 0.4s cubic-bezier(0.4, 0, 0.2, 1) both;
}

.ntt-item .card[data-display="xs"] {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
    background: var(--surface-2, rgba(22, 26, 38, 0.7));
    /* ... */
}

/* From ntt-list.css — prefix with .ntt-list */
.ntt-list {
    display: block;
}

.ntt-list .list-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 1.25rem;
}
```

### 4.3 CSS Variable Resolution

All component CSS uses CSS custom properties (`var(--surface-2)`, etc.) defined in `dark-theme.css`. This is already static-friendly -- the variables resolve at render time with no JavaScript.

**What needs to happen:**
1. Concatenate `dark-theme.css` + `light-theme.css` as the base stylesheet
2. Transform component CSS: replace `:host` with class-scoped selectors
3. Strip JS-only CSS (`.ntt-committing`, `.ntt-dirty`, `.loading-spinner`)
4. Output a single `style.css` file

### 4.4 Estimated Static CSS Bundle

```
dark-theme.css        ~408 lines  (include fully)
light-theme.css       ~119 lines  (include fully)
ntt-item.css          ~669 lines  (include, transform :host)
ntt-list.css          ~81 lines   (include, transform :host)
ntt-element.css       ~30 lines   (partial: error/empty states only)
---
Total:                ~1,307 lines -> ~35KB unminified, ~8KB gzipped
```

The Google Fonts import (`Inter`, `JetBrains Mono`) in `dark-theme.css` is the only external dependency. For a fully self-contained export, the fonts could be inlined or downloaded.

---

## 5. JavaScript Dependency Analysis

### 5.1 Features That REQUIRE JavaScript

| Feature | JS Component | Why JS is Needed |
|---------|-------------|------------------|
| Schema bootstrap | `NTT.SCHEMA()`, `prototype()` | Creates runtime classes from JSON -- static export eliminates this |
| Data fetching | `DynamicClass.READ()`, `NetworkAdapter` | HTTP requests -- static export reads DB directly |
| Actor messaging | `Matrix`, `TX`, `Actor` | Inter-component communication -- no components in static |
| Live updates | `Observable`, `signal()`, `notify()` | Reactive UI updates -- static pages don't update |
| Form submission | `NTTItem.save()`, `toggleMode()` | Writes data to backend -- static is read-only |
| Delete | `NTTItem.deleteItem()` | Destructive backend operation |
| Method calls | `<ntt-method>`, `.call()` | Backend RPC (like, comment, favorite) |
| Auth state | `Permissions.init()`, JWT tokens | Reads `/auth/me` -- static export is anonymous or per-role |
| Navigation | `Router`, hash-based routing | SPA navigation -- static uses `<a>` links |
| Pagination | `ListElement.loadMore()` | Incremental fetch -- static pre-renders all pages |
| Show more/less | `.show-more-btn` click handler | Toggle collapsed children |
| Reply inline | `.sm-reply-btn` + inline input | Interactive composition |

### 5.2 Features That Are Purely Presentational

| Feature | Where Rendered | Static Equivalent |
|---------|---------------|-------------------|
| Entity display (all sizes) | `ntt-item.js` xs/sm/md/lg/xl | Jinja2 template with same HTML |
| List grid layout | `ListElement.render()` | Jinja2 loop with CSS grid |
| Field rendering | `Formidable.getForm()` | Jinja2 macro (see Section 2.4) |
| Grouped fields | `renderGroupedFields()` | Jinja2 `{% for group %}` |
| Currency formatting | `$${value.toFixed(2)}` | `"${:.2f}".format(value)` |
| Image display | `<img class="card-image">` | Same HTML |
| Nested entity display | `getListInput()` | Recursive template include |
| Skeleton placeholders | `placeholder()` method | Omitted -- data is pre-rendered |
| Reply indent | `.reply-indent` CSS class | Same CSS class on `parent_id != null` |
| List count badge | `.list-field-count` | Pre-computed count |

### 5.3 Near-Zero JS for Static Export

The only JavaScript worth including in a static export would be for progressive enhancement:

```javascript
// Optional: ~20 lines for show-more/less toggle
document.querySelectorAll('.show-more-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const collapsed = btn.previousElementSibling;
        collapsed.classList.toggle('expanded');
        btn.textContent = collapsed.classList.contains('expanded')
            ? 'Show less'
            : btn.dataset.label;
    });
});
```

This is truly optional -- the alternative is rendering all items expanded, or using `<details>/<summary>`.

---

## 6. How `model_dump(response=True)` Feeds Templates

### 6.1 Current Behavior

```python
# proto_model.py lines 117-137
def model_dump(self, *, response: bool = False, **kwargs) -> Dict[str, Any]:
    data = super().model_dump(**kwargs)
    if response:
        data = {
            '$schema': f"{config.API_URL}/{cls.__name__}",      # Schema URL
            '$id': f"{config.API_URL}/{tablename}/{instance_id}", # Instance URL
            **data
        }
    return data
```

### 6.2 For Static Export

Static export uses `model_dump()` **without** `response=True`. The `$schema` and `$id` URLs reference a live server that won't exist for the static site. Instead:

```python
# Proposed: static export context
def export_entity(instance, schema, base_path=""):
    """Prepare entity data for template rendering."""
    data = instance.model_dump()  # Plain dict, no $schema/$id
    return {
        'value': data,
        'schema': schema,
        'url': f"{base_path}/{schema['__tablename__']}/{data['id']}.html",
        'model_name': schema['__name__'],
    }
```

### 6.3 Template Data Structure

Each Jinja2 template receives:

```python
{
    # Entity data
    'value': {
        'id': 1,
        'name': 'Widget Pro',
        'price': 29.99,
        'description': 'A professional widget',
        'image': 'https://placehold.co/...',
        'comments': [1, 2, 3],  # child IDs (resolved to full objects)
    },
    # Schema (same JSON Schema from ProtoModel.schema())
    'schema': {
        '__name__': 'Product',
        '__tablename__': 'products',
        'properties': {
            'name': {'type': 'string', 'minLength': 1, 'ui': {'placeholder': '...'}},
            'price': {'type': 'number', 'exclusiveMinimum': 0, 'ui': {'widget': 'currency'}},
            # ...
        },
        'ui': {
            'field_order': ['name', 'price', 'description', 'comments', 'favorites'],
            'groups': {'main': ['name', 'description', 'price'], 'Social': ['comments', 'favorites']},
        },
        'access': { ... },
        'methods': { ... },
        '$defs': { ... },
    },
    # Navigation context
    'base_path': '',  # or '../' for nested pages
    'site_title': 'My Store',
    'models': ['Product', 'User', 'Comment'],  # for nav menu
}
```

---

## 7. Authorization and Static Export

### 7.1 The Problem

PyBend's authorization system is deeply integrated:
- **Backend:** `AccessContext` + `DefaultResolver` enforces rules per request
- **Frontend:** `Permissions.canAction()` / `canView()` shows/hides UI elements
- **Schema:** Access rules serialized into JSON Schema for frontend consumption

A static site has no "current user." Three strategies:

### 7.2 Strategy A: Public-Only Export (Recommended Default)

Export only what `ANYONE` can see:

```python
def should_export_model(model_class) -> bool:
    access = getattr(model_class, '__access__', {})
    read_rule = access.get('read')
    # ANYONE rule or no access restrictions
    return read_rule is None or hasattr(read_rule, 'rule') and read_rule.rule == 'anyone'

def should_export_field(field_def) -> bool:
    access = field_def.get('access', {})
    view_rule = access.get('view')
    return view_rule is None or view_rule == 'anyone'
```

This mirrors how the frontend `Permissions` class works for anonymous users -- `canView()` returns `True` when no restriction exists or when the rule is `'anyone'`.

### 7.3 Strategy B: Per-Role Export

Generate separate site builds per role:

```bash
pybend export --static --role=anonymous   # -> build/public/
pybend export --static --role=user        # -> build/authenticated/
pybend export --static --role=admin       # -> build/admin/
```

This evaluates `canView()` and `canAction()` at build time with a synthetic user context. More complex but enables password-protected static hosting.

### 7.4 Strategy C: Full Export with Client-Side Gate

Export everything but wrap authenticated content in CSS classes that a thin JS layer can toggle based on a token. Not recommended -- defeats "near-zero JS" goal.

### 7.5 Recommendation

Start with **Strategy A** (public-only). It covers the primary use case (marketing sites, product catalogs, documentation) and requires zero auth complexity. Add Strategy B as an opt-in flag later.

---

## 8. Proposed Architecture

### 8.1 CLI Command

```bash
# Basic usage
pybend export --static --output ./build

# With options
pybend export --static \
    --output ./build \
    --theme dark \
    --models Product,Comment \
    --size md \
    --title "My Store"
```

### 8.2 Module Structure

```
src/pybend/core/export/
    __init__.py              # CLI entry point
    exporter.py              # Main orchestrator
    renderer.py              # Schema-to-HTML rendering (replaces form.js)
    css_compiler.py          # Aggregates + transforms component CSS
    templates/
        base.html.j2         # Page shell: <html>, <head>, CSS links
        index.html.j2        # Site index: list of models
        collection.html.j2   # Model collection page (list view)
        entity.html.j2       # Single entity page (detail view)
        macros/
            field.html.j2    # Field rendering (replaces getInput())
            header.html.j2   # Entity header (replaces getHeader())
            list_field.html.j2  # Nested collection (replaces getListInput())
            card_sm.html.j2  # sm-size card layout
            card_md.html.j2  # md-size card layout
```

### 8.3 Export Pipeline

```python
class StaticExporter:
    """Orchestrates static site generation."""

    def __init__(self, models, storage, output_dir, theme='dark', title='PyBend'):
        self.models = models          # Dict[str, Type[ProtoModel]]
        self.storage = storage        # AbstractStorage instance
        self.output_dir = Path(output_dir)
        self.theme = theme
        self.title = title
        self.env = self._create_jinja_env()

    def export(self):
        """Full export pipeline."""
        # 1. Compile CSS
        css = CSSCompiler(theme=self.theme).compile()
        self._write('static/style.css', css)

        # 2. Generate index page
        self._render_index()

        # 3. For each model:
        for name, model_cls in self.models.items():
            schema = model_cls.schema()
            if not self._should_export(model_cls):
                continue

            # 3a. Fetch all entities
            all_entities = self._fetch_all(model_cls)

            # 3b. Generate collection page
            self._render_collection(model_cls, schema, all_entities)

            # 3c. Generate individual entity pages
            for entity in all_entities:
                self._render_entity(model_cls, schema, entity)

    def _fetch_all(self, model_cls):
        """Fetch all entities without pagination."""
        result = model_cls.list()
        if isinstance(result, dict) and 'data' in result:
            return result['data']
        return result

    def _render_collection(self, model_cls, schema, entities):
        """Render a collection page (list view)."""
        tablename = schema['__tablename__']
        template = self.env.get_template('collection.html.j2')
        html = template.render(
            schema=schema,
            entities=[self._entity_context(e, schema) for e in entities],
            title=self.title,
            model_name=schema['__name__'],
            models=list(self.models.keys()),
            base_path='..',
        )
        self._write(f'{tablename}/index.html', html)

    def _render_entity(self, model_cls, schema, entity):
        """Render a single entity detail page."""
        tablename = schema['__tablename__']
        data = entity.model_dump()
        # Resolve nested entities
        children = self._resolve_children(model_cls, schema, entity)
        template = self.env.get_template('entity.html.j2')
        html = template.render(
            schema=schema,
            value=data,
            children=children,
            title=self.title,
            model_name=schema['__name__'],
            models=list(self.models.keys()),
            base_path='../..',
        )
        self._write(f'{tablename}/{data["id"]}.html', html)
```

### 8.4 File Structure Output

```
build/
  index.html                     # Site index with links to all collections
  static/
    style.css                    # Compiled CSS (dark-theme + components)
    fonts/                       # Optional: self-hosted Inter + JetBrains Mono
  products/
    index.html                   # Product list (grid of md cards)
    1.html                       # Product detail page (lg/xl view)
    2.html
    3.html
  users/
    index.html                   # User list (public profiles)
    1.html
  comments/                      # Only if Comment has read=ANYONE
    index.html
    1.html
```

---

## 9. Jinja2 Template Examples from Actual Codebase

### 9.1 Collection Page (mirrors `ListElement.render()`)

```html
{# collection.html.j2 -- mirrors ListElement.render() from ListElement.js:212-243 #}
{% extends "base.html.j2" %}
{% block content %}
<div class="ntt-list">
  <div class="list-header">
    <h1>{{ model_name }}s</h1>
    <span class="list-count">{{ entities|length }}</span>
  </div>
  <div class="list-grid">
    {% for entity in entities %}
    <a href="{{ entity.value.id }}.html" class="ntt-item"
       style="--stagger-delay: {{ loop.index0 * 50 }}ms">
      {# sm-size card for list view #}
      {% include "macros/card_sm.html.j2" %}
    </a>
    {% endfor %}
  </div>
</div>
{% endblock %}
```

### 9.2 sm Card (mirrors `NTTItem.sm()` from ntt-item.js:156-282)

```html
{# macros/card_sm.html.j2 #}
{% set props = schema.properties %}
{% set ui = schema.get('ui', {}) %}
{% set field_order = ui.get('field_order', props.keys()|list) %}

{# Filter renderable sm fields: skip id, hidden, array, selfref #}
{% set sm_fields = [] %}
{% for key in field_order %}
  {% if key in props %}
    {% set def = props[key] %}
    {% if key != 'id'
       and def.get('ui', {}).get('display') != false
       and def.get('type') != 'array'
       and def.get('type') != 'selfref' %}
      {% do sm_fields.append(key) %}
    {% endif %}
  {% endif %}
{% endfor %}

<div class="card" data-display="sm">
  {# Image thumbnail #}
  {% if entity.value.image %}
    <img class="sm-thumb" src="{{ entity.value.image }}" alt="" />
  {% endif %}

  {# Name #}
  <span class="sm-name" data-value="name">
    {{ entity.value.name or entity.value.title or model_name }}
  </span>

  {# Inline fields (up to 3) #}
  <span class="sm-fields">
    {% for key in sm_fields[:4] %}
      {% if key != 'name' %}
        {% set def = props[key] %}
        {% set val = entity.value.get(key, '') %}
        <span class="sm-field" data-value="{{ key }}">
          {% if def.get('ui', {}).get('widget') == 'currency' and val is number %}
            ${{ "%.2f"|format(val) }}
          {% else %}
            {{ val }}
          {% endif %}
        </span>
      {% endif %}
    {% endfor %}
  </span>
</div>
```

### 9.3 md Card (mirrors `NTTItem.md()` from ntt-item.js:284-318)

```html
{# macros/card_md.html.j2 -- mirrors NTTItem.md() #}
{% set props = schema.properties %}
{% set ui = schema.get('ui', {}) %}

<div class="card" data-display="md">
  {# Image banner #}
  {% if value.image %}
    <img class="card-image" src="{{ value.image }}" alt="{{ value.name or '' }}" />
  {% endif %}

  {# Header: name + description #}
  {% include "macros/header.html.j2" %}

  {# Fields -- grouped or ungrouped #}
  {% if ui.groups %}
    {% for group_name, group_fields in ui.groups.items() %}
      {% set renderable = group_fields|select_renderable(props, 'display') %}
      {% if renderable %}
        <fieldset class="ntt-group ntt-group-{{ group_name }}">
          <legend>{{ group_name }}</legend>
          {% for key in renderable %}
            {{ render_field(key, props[key], value.get(key, ''), 'display') }}
          {% endfor %}
        </fieldset>
      {% endif %}
    {% endfor %}
  {% else %}
    {% for key in field_order %}
      {% if key not in ('name', 'id', 'description') %}
        {{ render_field(key, props[key], value.get(key, ''), 'display') }}
      {% endif %}
    {% endfor %}
  {% endif %}
</div>
```

---

## 10. Gap Analysis

### 10.1 What Exists Today vs. What Static Export Needs

| Capability | Exists in Codebase | Needs for Static Export | Gap |
|-----------|-------------------|----------------------|-----|
| Schema generation | `ProtoModel.schema()` | Same | None |
| Data access | `StorableMixin.list()`, `.get()` | Same | None |
| FK hydration | `sqlite_storage.py` batch hydration | Need full-object hydration, not hrefs | Small -- add `as_objects=True` mode |
| Field rendering | `form.js` `getInput()` | Jinja2 macros | Medium -- 1:1 translation |
| Size-based layout | `ntt-item.js` xs/sm/md/lg/xl | Jinja2 templates | Medium -- 1:1 translation |
| Grouped fields | `form.js` `renderGroupedFields()` | Jinja2 group loop | Small |
| CSS design system | `dark-theme.css`, `light-theme.css` | Same files concatenated | Small -- strip `:host` |
| Component CSS | Shadow DOM CSS files | Scoped class selectors | Medium -- automated transform |
| Access filtering | `Permissions.canView()` | Python equivalent | Small -- mirror logic |
| CLI command | None | `pybend export` | New -- Click/Typer CLI |
| Jinja2 templates | None | Full template set | New -- ~200 lines |
| CSS compiler | None | Concatenate + transform | New -- ~80 lines |
| Child entity resolution | `getListInput()` + `<ntt-item ref>` | Pre-fetch children, inline HTML | Medium |

### 10.2 Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| FK hydration returns hrefs, not objects | Medium | Add `populate` mode to fetch call, or iterate children in exporter |
| CSS `backdrop-filter: blur()` requires modern browser | Low | Graceful degradation already in place via fallback values |
| Google Fonts dependency | Low | Optional self-hosting or system font fallback |
| Large datasets (10K+ entities) | Medium | Configurable pagination: generate paginated collection pages |
| Circular references (Comment -> Comment via parent_id) | Medium | Depth limit on recursive child rendering |
| Custom components (apps that extend NTTElement) | Low | Document: static export only covers built-in components |

### 10.3 Implementation Effort Estimate

| Component | Lines of Code | Effort |
|-----------|--------------|--------|
| `exporter.py` -- main orchestrator | ~150 | 1 day |
| `renderer.py` -- schema-to-HTML (replaces form.js) | ~200 | 1-2 days |
| `css_compiler.py` -- CSS aggregation | ~80 | 0.5 day |
| Jinja2 templates (all macros + pages) | ~300 | 1-2 days |
| CLI command (`__init__.py` / Click) | ~50 | 0.5 day |
| Tests | ~200 | 1 day |
| **Total** | **~980** | **5-7 days** |

---

## 11. Integration Points with Existing Architecture

### 11.1 Where Static Export Plugs In

```
PyBendApp / create_app()
    |
    +-- .build() -> FastAPI app (existing)
    |
    +-- .export() -> Static HTML (new)
         |
         +-- Uses same registered_models dict
         +-- Uses same storage backend
         +-- Calls same ProtoModel.schema()
         +-- Calls same StorableMixin.list() / .get()
         |
         +-- Does NOT start FastAPI server
         +-- Does NOT register routes
         +-- Does NOT need JWT/auth middleware
```

### 11.2 Proposed API

```python
# Level 1: One-liner
from pybend import create_app, export_static

app = create_app(models=[Product, User], storage="sqlite:///app.db")
export_static(app, output="./build")  # New function

# Level 2: Builder
pb = PyBendApp(storage="sqlite:///app.db")
pb.model(Product).model(User).join(Product, Comment)
pb.export(output="./build", theme="dark")  # New method

# Level 3: CLI
# $ pybend export --static --db sqlite:///app.db --output ./build
```

### 11.3 Reuse of `NTT.js` Pre-loading (Already Exists!)

A remarkable discovery: `NTT.js` already contains SSR pre-loading infrastructure (lines 237-277):

```javascript
// NTT.js line 243-257
static #consumePreloadedSchema(model) {
    const el = document.querySelector(`script[data-ntt-schema="${model}"]`);
    if (!el) return false;
    try {
        const data = JSON.parse(el.textContent);
        el.remove();
        NTT.SCHEMA(data);
        return true;
    } catch (e) {
        return false;
    }
}

static #consumePreloadedData(tablename) {
    const el = document.querySelector(`script[data-ntt-data="${tablename}"]`);
    if (!el) return null;
    try {
        const data = JSON.parse(el.textContent);
        el.remove();
        return data;
    } catch (e) {
        return null;
    }
}
```

This means PyBend already supports a **hybrid** mode: inject schema + data as inline `<script>` tags, and the frontend skips network fetches. The static exporter could generate pages that include both:
1. Pre-rendered HTML for immediate display (zero JS)
2. Inline `<script data-ntt-schema>` + `<script data-ntt-data>` tags for progressive enhancement

This enables a graceful upgrade path: pages load instantly with static HTML, then the full NTT system hydrates on top if the JS bundle is included.

---

## 12. Rendering Fidelity Comparison

### 12.1 Visual Parity Matrix

To validate that static export matches the dynamic rendering, compare output HTML:

| Element | Dynamic (JS) | Static (Jinja2) | Parity |
|---------|-------------|-----------------|--------|
| `<div class="card" data-display="sm">` | `NTTItem.render()` sets `data-display` | Template sets same attribute | Exact |
| `<span class="sm-name">Widget Pro</span>` | `sm()` builds from `this.value.name` | Template reads `value.name` | Exact |
| `<span class="sm-field">$29.99</span>` | `sm()` formats currency | Jinja2 `"%.2f"\|format()` | Exact |
| `<div class="currency-display">$29.99</div>` | `getInput()` currency branch | Jinja2 macro currency branch | Exact |
| `<fieldset class="ntt-group ntt-group-main">` | `renderGroupedFields()` | Jinja2 group loop | Exact |
| `<div class="list-field"><span class="list-field-count">5</span>` | `getListInput()` | Jinja2 child count | Exact |
| Edit/delete buttons | `permissions.canAction()` | Omitted (read-only) | By design |
| `<ntt-method model="Product">` | Custom element | Omitted (requires JS) | By design |
| Skeleton placeholder | `placeholder()` | Omitted (data pre-rendered) | By design |

### 12.2 What Won't Match

1. **Stagger animation**: CSS `animation-delay: var(--stagger-delay)` relies on inline style set by JS. Static export can set the same inline style via Jinja2's `loop.index0 * 50`.

2. **Show more/less**: Currently JS-driven. Static options: (a) fully expand, (b) `<details>/<summary>`, (c) include the 20-line JS snippet.

3. **Interactive methods**: Like/favorite/comment buttons are omitted. Static pages show counts but not interactive buttons.

4. **Hover actions**: Edit/delete buttons that appear on hover are omitted since the actions require a backend.

---

## 13. Proposed Implementation Order

### Phase 1: Core Export (MVP)

1. **CSS Compiler** -- Concatenate theme + component CSS, transform `:host` selectors
2. **Field Renderer** -- Jinja2 macros mirroring `getInput()` for display mode
3. **Entity Template** -- md-size detail page with grouped fields
4. **Collection Template** -- sm-size list page with CSS grid
5. **Exporter** -- Orchestrator: iterate models, fetch data, render templates, write files
6. **CLI** -- `pybend export --static --output ./build`

### Phase 2: Polish

7. **Index page** -- Landing page with links to all collections
8. **Navigation** -- Breadcrumbs, model-to-model links
9. **Image handling** -- Download remote images, rewrite URLs to local paths
10. **Pagination** -- Split large collections into paginated HTML pages

### Phase 3: Advanced

11. **Per-role export** -- Strategy B from Section 7
12. **Hybrid mode** -- Inject inline `<script data-ntt-schema>` for progressive enhancement
13. **Custom templates** -- Allow apps to provide their own Jinja2 overrides
14. **Nested entity pages** -- `/products/1/comments/2.html` routes

---

## 14. Conclusion

PyBend's architecture is remarkably well-suited for static export because the rendering pipeline is already split into clean, deterministic stages:

1. **Schema generation** (`ProtoModel.schema()`) is already server-side Python
2. **Data access** (`StorableMixin.list()`) is already server-side Python
3. **Field rendering** (`form.js`) is a pure function of (schema, value) with no side effects
4. **Size layouts** (`ntt-item.js` xs/sm/md/lg/xl) are pure functions of (schema, value)
5. **CSS** uses custom properties that resolve without JavaScript

The JS-dependent parts (Actor messaging, live updates, form submission, auth) are cleanly separated from the presentational parts. No rendering logic requires access to browser APIs -- it all operates on schema and data.

The existing `consumePreloadedSchema()` / `consumePreloadedData()` infrastructure in `NTT.js` shows the architecture was already moving toward pre-rendering. Static export is the natural next step: skip the client entirely and generate the HTML that the DynamicClass system would have produced.

**Estimated effort:** 5-7 engineering days for the MVP, producing a fully functional `pybend export --static` command that generates a complete, styled, responsive static website from any PyBend application's models and data.
