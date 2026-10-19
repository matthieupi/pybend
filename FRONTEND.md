# Frontend contributor orientation

Read [AGENTS.md](AGENTS.md), then the [frontend guide](docs/frontend/ARCHITECTURE.md).
For a complete application, use [Getting started](docs/GETTING_STARTED.md).
All paths and commands here are relative to the N3TX checkout, not `/workspace`.

## Boundaries

```text
Python models -> runtime schema -> NTT entities -> Web Components
                                      |
                              Matrix / transport -> API
```

| Work | Canonical reference | Source directory |
|---|---|---|
| Bootstrap and schema/data flow | [Architecture](docs/frontend/ARCHITECTURE.md) | `packages/n3tx-core/src/n3tx_core/static/core/` |
| Component usage and routing | [Components](docs/frontend/COMPONENTS.md) | `packages/n3tx-ui/src/n3tx_ui/static/components/` |
| Custom renderers and lifecycle | [Extension guide](packages/n3tx-ui/docs/components.md) | `Component.js`, `NTTElement.js`, `ListElement.js`, `ntx-item.js` |
| Form generation | [Formidable](packages/n3tx-ui/docs/formidable.md) | `packages/n3tx-ui/src/n3tx_ui/static/generators/` |
| Field renderers | [Widgets](packages/n3tx-ui/docs/widgets.md) | `packages/n3tx-ui/src/n3tx_ui/static/widgets/` |
| Theme tokens and shadow styles | [Styling](packages/n3tx-ui/docs/styling.md) | UI `static/*.css`; core `static/utils/theme.js` |
| TX routing and networking | [Actors](docs/frontend/ACTORS.md), [protocol](docs/frontend/MESSAGE_PROTOCOL.md), [transport](docs/frontend/TRANSPORT.md) | Core `static/core/` |
| Python UI capability | [ViewableMixin](packages/n3tx-ui/docs/viewable-mixin.md) | `packages/n3tx-ui/src/n3tx_ui/mixin.py` |
| Verification | [Frontend harness](tests/frontend/README.md) | `tests/frontend/` |

## Invariants

- Import `{ NTT }` from `/core/NTT.js`; `N3TX` is the framework name, not that export.
- Use the native combined static namespace. Do not mount UI separately from its runtime dependencies.
- Import every custom element used by the shell, including custom schema renderers and `ntx-profile` when exposing the profile route.
- Read schemas at runtime. Do not maintain parallel field, method, or permission definitions in JavaScript.
- Extend the narrowest existing visual primitive. Keep native entity subscriptions, forms, and method dispatch rather than rebuilding fetching/state.
- Preserve superclass lifecycle cleanup. `prerender()` creates structure; subsequent rendering must preserve persistent child/stream surfaces where required.
- UI hiding and client validation are usability features, not backend authorization or data validation.
- Use safe DOM text insertion for application data. Formidable is not a general HTML sanitizer.
- Keep app-specific CSS and components in the app static directory. Core runtime must not import visual UI implementations.

## Verification

From `tests/frontend/`, run `npm test` for jsdom unit/integration checks.
Use `npm run test:e2e` for the worker-isolated core browser lane. See the
[harness guide](tests/frontend/README.md) for prerequisites, other lanes, and
artifact paths. Unit tests do not establish browser layout, server authorization,
or real transport parity.
