---
name: n3tx-frontend
description: Broad N3TX frontend application development. Use for schema-driven UI, Web Components, routes, forms, widgets, transport, streaming UI, and frontend verification without duplicating backend contracts.
argument-hint: "<frontend feature>"
---

# N3TX Frontend

The N3TX frontend is schema-driven. It should adapt to backend contracts instead of re-declaring them.

## Frontend mental model

```text
GET /{ClassName} schema
   -> NTT.SCHEMA()
   -> DynamicClass via prototype()
   -> components render using schema.properties/ui/access/methods/$defs
```

The browser receives a complete model contract. Use that contract.

## Component layers

| Layer | Purpose |
|---|---|
| `n3tx-core/static/core` | Actor/TX/Matrix, entity registry, transport, abstract component bridge |
| `n3tx-ui/static/components` | Visual Web Components such as `ntx-list`, `ntx-item`, `ntx-method`, `ntx-stream` |
| `n3tx-ui/static/generators/form.js` | Formidable schema-driven forms |
| `n3tx-ui/static/widgets` | Field widgets selected by schema |
| `n3tx-agents/static/components` | Agent UI such as `ntx-chat`, `ntx-agent-live`, `ntx-stream-agent` |

## Frontend route grammar

```text
#Product              legacy/default collection
#Product/@            collection default view
#Product/@table       collection named view
#Product/1            legacy/default detail
#Product/1/@          member default view
#Product/1/@chat      member named view
#Product/1/run        method/action route
#Product/1/@run       view named run, not a method
#@profile             app-level route
```

The `@` segment always means view/presentation, never data or method invocation.

## What schema controls

| Schema section | Frontend use |
|---|---|
| `properties` | fields, validation hints, form inputs |
| `properties[f].ui.widget` | widget selection |
| `properties[f].ui.display` | hide/show fields |
| `properties[f].access` | field-level visibility |
| `ui.field_order` | form order |
| `ui.groups` | fieldsets |
| `ui.renderer` | custom component tags for views |
| `access` | edit/delete/action visibility |
| `methods` | method buttons/streams |
| `methods[m].events` | typed stream event handlers |
| `$defs` | nested DynamicClass registration |

## Frontend boundaries

- Do not hardcode field contracts already present in schema.
- Do not duplicate backend access rules as source of truth.
- Do not use raw `fetch()` for N3TX entity CRUD/method calls when N3TX transport/entity methods apply.
- Do not fork generated UI if `__ui__`, widget registration, renderer hints, or a custom component can solve it.
- Do not make UI call arbitrary internal HTTP routes. Use generated API/entity/action paths and N3TX transport.

## Verification

```bash
cd /workspace/tests/frontend && npx vitest run
cd /workspace/tests/frontend && npm run test:e2e:fast
```

Prefer Vitest for static component/schema behavior and Playwright for browser/auth/routing/layout behavior.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. If source resolves a gap, update or propose docs/skills.
