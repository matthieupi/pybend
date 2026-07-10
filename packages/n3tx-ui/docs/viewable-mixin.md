# ViewableMixin

> Part of [n3tx-ui](../README.md)

## What This Covers

`ViewableMixin` and the `viewable` schema pipeline stage. Covers injection via
`__viewable__` / `__ui__`, the schema output format, and the registration
side-effect. Does not cover the components that consume `schema['ui']` (see
[components.md](components.md) and [formidable.md](formidable.md)).

## Architecture

```
n3tx_ui imported
    |
    v
register_mixin('__viewable__', ViewableMixin, also_if=['__ui__'])
+ @schema_extension(after='ui') → viewable stage registered

At model definition time:
    class Product(ProtoModel):
        __viewable__ = True   # or __ui__ = {...} triggers the same
    → ViewableMixin prepended to Product.__bases__

At schema generation time:
    ProtoModel.schema()  →  ... → ui() → viewable() → metadata()
                                                |
                                    emits schema['ui'] from __ui__
```

`ViewableMixin` carries `__ui__: ClassVar[Optional[dict]] = None`, owns the
`viewable` schema extension stage, and registers model view routes for viewable
models. This mirrors the backend capability split: `StorableMixin` makes a
model eligible for CRUD/data routes, while `ViewableMixin` makes a model
eligible for HTML/view routes.

## Injection

### Trigger: `__viewable__ = True`

Explicit opt-in. `ViewableMixin` is injected, but `schema['ui']` is only
emitted if `__ui__` is also set.

```python
import n3tx_ui  # registers ViewableMixin before model definition

class Dashboard(ProtoModel):
    __tablename__ = 'dashboards'
    __viewable__ = True
    # No __ui__ → schema has no 'ui' key, but issubclass(Dashboard, ViewableMixin)
```

### Trigger: `__ui__ = {...}` (guardrail)

Setting `__ui__` automatically sets `__viewable__ = True` and injects the mixin.
This is the common case — you rarely need to set `__viewable__` explicitly.

```python
import n3tx_ui  # must import before model definition

class Product(ProtoModel):
    __tablename__ = 'products'
    __ui__ = {
        'field_order': ['name', 'price'],
        'renderer': {'item': 'ntx-item', 'list': 'ntx-list'},
    }
    # → __viewable__ = True is set automatically
    # → ViewableMixin is injected
```

## Interface

### `__ui__` ClassVar dict

All keys are optional. The entire dict is copied into `schema['ui']`.

| Key | Type | Description |
|-----|------|-------------|
| `field_order` | `list[str]` | Field render order (Formidable) |
| `groups` | `dict[str, list[str]]` | Named fieldset groupings |
| `icon` | `str` | Shared icon token: inline-SVG lookup key, emoji, or URL/path |
| `methods` | `dict[str, dict]` | Per-method UI hints (see below) |
| `renderer` | `dict` | Override component tags: `{'item': 'ntx-item', 'list': 'ntx-list'}` |
| `populate` | `dict` | Schema hydration hints: `{'depth': 2}` |

Any additional keys are passed through unchanged.

### Method UI hints (`__ui__.methods`)

Per-method rendering hints. Each key matches a method name from `@expose_route`.

```python
__ui__ = {
    'methods': {
        'comment': {
            'layout': 'inline',       # 'inline' | 'button' | 'modal'
            'attach_to': 'comments',  # Field to append result to
            'button_label': 'Post',
            'placeholder': 'Add comment...',
            'widget': 'textarea',
        },
        'favorite': {
            'layout': 'button',
            'icon': 'star',
            'count_field': 'favorites',
        },
    }
}
```

These are emitted as `schema['methods'][name]['ui']` for the frontend to read.

### View route registration

`ViewableMixin.register_view_routes(router, tag=...)` registers HTML/view
entrypoints owned by the viewable capability. The collection route grammar
supports both default and named collection views:

```text
GET /{ClassName}/@       # default collection view
GET /{ClassName}/@{view} # named collection view
GET /{ClassName}/{id}/@  # default member view
GET /{ClassName}/{id}/@{view} # named member view
```

The response is an HTML shell that mounts the normal frontend component system;
it is not a separate server-side component renderer. Default collection renderer
resolution matches the frontend router. Default collection views resolve as:

```text
ui.renderer.page → ui.renderer.list → ntx-list
```

Named collection views resolve as:

```text
ui.renderer[view] → known framework fallback → 400 for unknown views
```

Known framework fallbacks currently include:

```text
list  → ntx-list
table → ntx-table
```

Default member views resolve as:

```text
ui.renderer.detail → ui.renderer.item → ntx-item
```

Named member views resolve as:

```text
ui.renderer[view] → known member fallback → 400 for unknown views
```

Known member fallbacks currently include:

```text
item   → ui.renderer.item → ntx-item
detail → ui.renderer.detail → ui.renderer.item → ntx-item
chat   → ntx-chat
```

Custom view names are schema-only: a route such as `/Product/@custom-card` or
`/Product/1/@custom-card` is accepted only when the model declares a matching
`__ui__['renderer']['custom-card']` entry. Unsafe view tokens are rejected before
HTML is generated. Valid view tokens must match:

```text
^[A-Za-z0-9][A-Za-z0-9_-]*$
```

Renderer tags inserted into HTML must be safe custom-element names:

```text
^[a-z][a-z0-9]*(-[a-z0-9]+)+$
```

For example:

```python
class Product(ProtoModel):
    __tablename__ = 'products'
    __ui__ = {'renderer': {'page': 'ntx-products-page', 'list': 'ntx-products'}}
```

registers:

```text
GET /Product/@  -> HTML containing <ntx-products-page model="Product">
GET /Product/@table -> HTML containing <ntx-table model="Product"> unless renderer.table is declared
GET /Product/1/@ -> HTML containing <ntx-item ref="Product/1" display="lg"> unless detail/item is declared
GET /Product/1/@chat -> HTML containing <ntx-chat ref="Product/1" display="lg"> unless renderer.chat is declared
```

`n3tx-core` delegates to this method when present; it does not hard-import
`n3tx_ui`, preserving the package boundary.

Standalone HTML shells import the resolved renderer module using the conventional
static component path `/components/{tag}.js`. For example, if a model declares
`__ui__ = {'renderer': {'item': 'ntx-grant-item'}}`, then
`GET /Grant/1/@` mounts `<ntx-grant-item ref="Grant/1">` and includes:

```html
<script type="module" src="/components/ntx-item.js"></script>
<script type="module" src="/components/ntx-grant-item.js"></script>
```

The base renderer import (`ntx-item` for member routes, `ntx-list` for
collection routes) is kept so custom renderers that extend first-party
components can resolve their dependencies in standalone pages. Duplicate imports
are removed when the resolved tag is the same as the base renderer.

`ui.icon` is a universal contract shared by model shells and method actions.
Accepted values are direct emoji (`'📚'`), direct asset URLs/paths
(`'/static/icons/books.svg'`), or lookup keys (`'books'`). The frontend
resolves lookup keys through a shared registry, typically to inline SVG,
renders URLs as image icons, and otherwise falls back to the raw text token.
Emoji rendering uses a best-effort monochrome filter so icons stay theme-aware
without changing the schema shape.

## Schema Output

```json
{
    "ui": {
        "field_order": ["name", "price"],
        "groups": {"main": ["name", "price"]},
        "renderer": {"item": "ntx-item", "list": "ntx-list"}
    },
    "methods": {
        "comment": {
            "route": "/comment",
            "ui": {"layout": "inline", "attach_to": "comments"}
        }
    }
}
```

For `$defs` models (referenced by relationship fields), `__ui__` is also emitted
into `schema['$defs'][ModelName]['ui']`.

## Usage Patterns

### Standard model with UI config

```python
import n3tx_ui  # in main.py, before model imports

class Product(ProtoModel):
    __tablename__ = 'products'
    __storable__ = True
    __ui__ = {
        'field_order': ['name', 'price', 'description'],
        'groups': {
            'main': ['name', 'price'],
            'details': ['description'],
        },
        'renderer': {'item': 'ntx-item', 'list': 'ntx-list'},
    }
    name: str = Field(...)
    price: float = Field(...)
    description: str = Field(default='')
```

### In an application entry point

```python
# main.py — import n3tx_ui BEFORE model files
import n3tx_ui  # registers ViewableMixin + viewable schema stage
from models import Product, User, Comment  # __ui__ injection fires here
```

## Gotchas

- **Import ordering is mandatory.** `n3tx_ui` must be imported before any
  model with `__ui__` or `__viewable__` is defined. If a model is defined
  first, `register_mixin()` hasn't run yet and the mixin is never injected.
  The model will lack `ViewableMixin` in its MRO and `schema['ui']` will
  be absent. No error is raised — the flag is silently ignored.

- **`__ui__` without `n3tx_ui` import = no schema `ui` key.** If you define
  `__ui__` but forget to import `n3tx_ui`, the class attribute exists but
  ViewableMixin is never injected and the `viewable` stage is never registered.
  `Product.schema()` will not contain a `'ui'` key.

- **Schema cache.** `schema['ui']` is only generated on the first `schema()`
  call. If `n3tx_ui` is imported after the first call, call
  `cls.invalidate_schema_cache()` to regenerate.

- **`__ui__` on a non-model class.** Only `ProtoModel` subclasses go through
  `__init_subclass__`. Plain Python classes with `__ui__` are unaffected.
