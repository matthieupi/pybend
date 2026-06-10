---
name: n3tx-ui-schema
description: N3TX schema-driven UI contracts, __ui__, field metadata, renderer hints, access adaptation, route grammar, and frontend schema consumption. Use when shaping UI from backend models.
argument-hint: "<schema UI task>"
---

# N3TX UI Schema

The backend schema is the frontend contract.

## `__ui__` pattern

```python
class Product(ActorModel):
    __ui__ = {
        'icon': 'box',
        'description': 'Products available in the catalog.',
        'create_label': 'Add product',
        'field_order': ['name', 'price', 'description'],
        'groups': {'main': ['name', 'price'], 'Details': ['description']},
        'renderer': {'list': 'ntx-list', 'item': 'ntx-item', 'detail': 'ntx-item'},
        'methods': {'favorite': {'layout': 'button', 'icon': 'star', 'count_field': 'favorites'}},
    }
```

Field-level UI hints:

```python
name: str = Field(json_schema_extra={'ui': {'placeholder': 'Product name'}})
body: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
```

## Schema sections consumed by UI

- `properties` -> fields/forms
- `properties[f].ui.widget` -> widget registry
- `properties[f].ui.display` -> hide/show
- `properties[f].ui.protected` -> hidden in edit mode
- `ui.field_order` -> form order
- `ui.groups` -> fieldsets
- `ui.renderer` -> route/view component tag
- `access` -> action visibility
- `methods` -> method buttons/streams
- `$defs` -> nested entity classes

## Route/view semantics

```text
#Product/@table      collection table view
#Product/1/@chat     detail chat view
#Product/1/run       method route
#Product/1/@run      view route, not method
```

## Guardrails

- Do not hardcode frontend field order or labels if schema can carry them.
- Do not duplicate access rules in JS.
- Do not infer method/view meaning without respecting `@` boundary.
- Do not fork UI when renderer hints or widgets can express the customization.

## Verification

- `GET /{ClassName}` includes expected `ui` and field hints.
- Formidable renders fields in order/groups.
- Router resolves renderer tags.
- Access-aware controls match schema rules.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
