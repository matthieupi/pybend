---
name: n3tx-extension-patterns
description: N3TX extension patterns for schema/dump extensions, mixins, custom storage, widgets, components, network adapters, and auth rules. Use when normal model/UI/actor customization is not enough.
argument-hint: "<extension need>"
---

# N3TX Extension Patterns

Prefer existing app-level customization before extending framework surfaces.

## Extension decision tree

| Need | First choice | Extension if needed |
|---|---|---|
| Field display/input | `ui.widget` | custom frontend widget / backend Widget |
| Entity layout | `__ui__.renderer` | custom Web Component |
| App action | `@expose_route` | actor/tool actor |
| External protocol | tool actor | `NetworkAdapter` |
| Extra schema metadata | `__ui__`/field extras | schema pipeline extension |
| Extra response metadata | model fields | dump pipeline extension |
| New model capability flag | explicit base/mixin | `register_mixin()` |
| Storage engine | SQLite | custom storage backend |
| Access primitive | built-in ABAC rules | custom `AccessRule` |

## Schema extension

```python
from n3tx_core.models.proto_schema import schema_extension

@schema_extension(after='methods')
def federation(cls, schema: dict) -> dict:
    if getattr(cls, '__federated__', False):
        schema['federation'] = {'enabled': True}
    return schema
```

## Dump extension

```python
from n3tx_core.models.proto_dump import dump_extension

@dump_extension(after='response')
def activity(instance, data: dict) -> dict:
    if getattr(instance.__class__, '__federated__', False):
        data['type'] = instance.__class__.__name__
    return data
```

## Mixin registration

```python
from n3tx_core.models.proto_model import register_mixin

register_mixin('__my_capability__', MyMixin)
```

Import the package that registers the mixin before model classes using the flag are defined.

## Network adapter

Use for protocol translation, not ordinary app API calls. Ordinary capabilities should usually be actors with `@expose_route`.

## Guardrails

- Do not create extension machinery for one model if `__ui__`, fields, or methods solve it.
- Do not break package dependency direction.
- Do not make UI extensions authoritative over backend contracts.
- Do not hide external IO outside actor/adapter boundaries.

## Verification

- Extension appears in generated schema/response only when intended.
- Default models remain unchanged.
- Frontend/agents consume the extension through schema, not duplicated code.
- Docs/skills are updated if a new app-facing pattern is introduced.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
