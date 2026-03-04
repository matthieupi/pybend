# N3TX Frontend Reference

This document contains frontend-specific key files, schema consumption details, and patterns. It supplements the main `CLAUDE.md` which contains cross-cutting architecture, the actor system, custom methods, and all directives.

## Frontend Architecture (Vanilla JS Web Components)

```
N3TX.js               Core entity system. Bootstraps by fetching schema from backend.
  |
  +-- SCHEMA()        Receives schema, creates DynamicClass via prototype()
  +-- prototype()     Builds class with typed properties, methods, value getter
  |                   Value getter injects $schema (schema URL) and $id (instance URL)
  |
  v
ntx-list.js          <ntx-list model="Product"> - fetches and renders entity list
ntx-item.js          <ntx-item> - adaptive entity rendering (xs pill → xl page)
ntx-element.js       Base web component class for all N3TX elements
ntx-method.js        Renders callable methods as buttons
form.js              Formidable generator - builds forms from schema properties
```

## Key Files

### Core
- `src/n3tx/static/core/N3TX.js` - Core: N3TX class, prototype() factory, SCHEMA handler, DynamicClass creation
- `src/n3tx/static/core/Matrix.js` - Message bus / actor system
- `src/n3tx/static/core/Actor.js` - Base actor class
- `src/n3tx/static/core/Router.js` - Navigation state Actor (hash sync, history stack, Observable)

### Components
- `src/n3tx/static/components/ntx-item.js` - Item component: size methods (xs-xl), render dispatch, edit toggle, click-to-select
- `src/n3tx/static/components/ntx-list.js` - List component
- `src/n3tx/static/components/ntx-router.js` - Generic view container (loads any component via Router)
- `src/n3tx/static/components/ntx-element.js` - Base component class

### Generators & Utils
- `src/n3tx/static/generators/form.js` - Formidable: schema-driven form generator
- `src/n3tx/static/utils/Permissions.js` - Reads schema access rules for UI permission checks

### Widgets (JS)
- `src/n3tx/static/widgets/Widget.js` - JS base Widget class with display/edit/list methods + shared utilities
- `src/n3tx/static/widgets/registry.js` - JS registry: `registerWidget()`, `getWidgetForField()`
- `src/n3tx/static/widgets/index.js` - Loader: imports all built-ins, registers them, exports public API
- `src/n3tx/static/widgets/*.js` - Built-in widget implementations (UrlWidget, EmailWidget, DateWidget, MarkdownWidget, ConsoleWidget, ReferenceWidget, CurrencyWidget, TextareaWidget)
- `src/n3tx/static/widgets/widgets.css` - Widget-specific styles
- `src/n3tx/static/vendor/marked.min.js` - Vendored markdown parser (~40KB)
- `src/n3tx/static/vendor/ansi_up.min.js` - Vendored ANSI color renderer (~15KB)

## Schema as Universal Contract

The JSON Schema returned by `GET /{ClassName}` is the **single contract between backend and frontend**. It is not just a type description — it is the complete specification of how an entity behaves, renders, and is controlled.

### Schema Anatomy

```
GET /Product → JSON Schema
├── $schema         → "http://localhost:5000/Schema"          (meta-schema URL)
├── $id             → "http://localhost:5000/Product"         (this schema's URL)
├── __name__        → "Product"                               (class name)
├── __tablename__   → "products"                              (API collection path)
├── properties      → { name: {type, minLength, ui, ...}, ...}  (field definitions)
│   └── each field carries:
│       ├── type, format, validation (Pydantic standard)
│       ├── ui.widget       → rendering hint (currency, textarea, ...)
│       ├── ui.placeholder  → input placeholder text
│       ├── ui.display      → false to hide from UI
│       ├── ui.protected    → true for backend-owned fields (hidden in edit forms)
│       └── access          → field-level permission rules
├── ui              → model-level UI configuration
│   ├── field_order → render fields in this sequence
│   ├── groups      → group fields into fieldsets
│   └── renderer    → { item: 'ntx-item', list: 'ntx-list', detail: '...' }
├── access          → model-level ABAC rules (serialized)
│   ├── create      → { rule: "authenticated" }
│   ├── read        → { rule: "anyone" }
│   ├── update      → { op: "or", rules: [{rule: "owner"}, {rule: "role", roles: ["admin"]}] }
│   └── delete      → { rule: "role", roles: ["admin"] }
├── methods         → callable endpoints
│   └── comment     → { route, methods, scope, parameters, returns, access }
├── $defs           → nested/related model schemas
│   └── Comment     → { $id, properties, methods, ui, access, ... }
└── required        → required field names
```

### How Each Schema Section Is Consumed

**Frontend reads schema once, adapts everything at runtime:**

| Schema section | Frontend consumer | What it controls |
|---------------|------------------|-----------------|
| `properties` | `prototype()` in N3TX.js | Creates typed getters/setters on DynamicClass |
| `properties[field].type` | `form.js` → `getInput()` | Chooses input type (text, number, checkbox, ...) |
| `properties[field].ui.widget` | `form.js` → `getInput()` | Specialized rendering (currency prefix, textarea) |
| `properties[field].ui.display` | `form.js` → field filtering | Hides internal fields (IDs, timestamps, FKs) |
| `properties[field].ui.protected` | `form.js` → field filtering | Hides backend-owned fields in edit mode (display-only) |
| `properties[field].ui.placeholder` | `form.js` → input attrs | Sets placeholder text on inputs |
| `properties[field].access` | `Permissions.js` → `canView()` | Field-level visibility per user role |
| `ui.field_order` | `form.js` → `getForm()` | Controls field rendering sequence |
| `ui.groups` | `form.js` → `renderGroupedFields()` | Wraps fields in `<fieldset>` groups |
| `ui.renderer.*` | `ntx-router.js` → `#resolveTag()` | Chooses component tag for navigation views |
| `access` | `Permissions.js` → `canAction(access, action, resource)` | Shows/hides edit/delete buttons with resource-aware OWNER evaluation |
| `methods` | `prototype()` + `<ntx-method>` | Creates callable methods + renders action buttons |
| `$defs` | `N3TX.SCHEMA()` | Registers nested DynamicClasses (Comment, etc.) |
| `$id` / `$schema` | DynamicClass value getter | Injected into every entity instance for self-description |

### Schema Propagation Lifecycle

```
1. Model Definition (Python)
   Product(ProtoModel) with fields, __ui__, __access__, @expose_route
                    │
2. Schema Generation (Backend, on GET /Product)
   ProtoModel.schema() → proto_schema pipeline (base → strip_hidden → methods → defs → access → widget → ui → metadata)
                    │
3. Network Transport
   HTTP GET /Product → JSON response
                    │
4. Schema Bootstrap (Frontend)
   N3TX.SCHEMA(data) → prototype(addr, schema, href) → DynamicClass
   │  Creates typed class with getters, setters, methods from schema
   │  Registers nested $defs as additional DynamicClasses
                    │
5. Component Rendering (Frontend)
   NTTItem.DESCRIBE() receives { proto: schema, data: values }
   │  form.js reads schema.properties → builds form HTML
   │  Permissions.js reads schema.access → shows/hides controls
   │  ntx-method reads schema.methods → renders action buttons
   │  ntx-router reads schema.ui.renderer → resolves navigation targets
                    │
6. Entity Responses (Backend, on GET /products)
   model_response() runs dump pipeline → injects $schema + $id into each record
   │  Frontend DynamicClass value getter preserves these for self-description
   │  Any entity can be independently resolved: GET $id → full entity
   │  Collection fields return href arrays: ["http://.../products/1/comments/1", ...]
```

## Frontend Patterns

### Widget Extension (JS)
On the frontend, `form.js` and `ntx-item.js` dispatch to registered JS Widget instances (`getWidgetForField()`) before falling through to type-based rendering. Fields without `ui.widget` render identically to before (zero-risk).

App developers extend with a single class:
```javascript
class ColorWidget extends Widget { display(v) { ... } }
registerWidget('color', new ColorWidget());
```
