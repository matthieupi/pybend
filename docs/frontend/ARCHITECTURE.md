# Frontend guide

N3TX renders backend models through runtime schemas and native Web Components.
The application still supplies model registration, storage, access policy, a page
layout, and module imports. Start with the [application tutorial](../GETTING_STARTED.md)
for backend/authentication setup; this guide explains the browser side.

## 1. Bootstrap through the native app

Install `n3tx-ui` alongside `n3tx-core` in the application's Python environment.
Import UI before defining models that request its capability. Continue in the
tutorial's existing `main.py` (there is no separate `models.py`). Keep its imports
and `User`, `Label`, `Issue` declarations; its final bootstrap is:

```python
# In tutorial main.py, after the existing model declarations.
from pathlib import Path

app = create_app(
    models=[User, Label, Issue],
    storage="sqlite:///issues.db",
    static_dir=str(Path(__file__).parent / "static"),
    jwt_secret=config.JWT_SECRET,
    debug=False,
    ssr="off",
    name="Issue tracker",
)
```

Create `static/index.html` in that application. Use this complete shell with a
registered `Issue` model and its read policy configured. An empty collection is
valid; denied reads remain denied even if the page loads.

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Issues</title>
  <link rel="stylesheet" href="/theme-base.css">
  <link rel="stylesheet" href="/dark-theme.css">
  <link rel="stylesheet" href="/light-theme.css">
  <script>window.NTX_THEME_CONFIG = {themes: ['dark', 'light']};</script>
  <script type="module">
    import '/utils/theme.js';
    import { permissions } from '/utils/Permissions.js';
    await permissions.init();
    await import('/core/NTT.js');
    await import('/components/ntx-item.js');
    await import('/components/ntx-list.js');
    await import('/components/ntx-router.js');
    await import('/components/ntx-topbar.js');
    await import('/components/ntx-profile.js');
  </script>
</head>
<body>
  <ntx-topbar brand="Issues"></ntx-topbar>
  <main>
    <ntx-router name="main">
      <ntx-list model="Issue" allow-create></ntx-list>
    </ntx-router>
  </main>
</body>
</html>
```

Module dependencies initialize Matrix and NTT; do not create another Matrix.
Dynamic imports deliberately follow identity initialization: static imports are
evaluated before the `await` and could upgrade protected elements too early.
This retains the tutorial's **trusted-input local demo only** restriction; see
[Formidable HTML safety](../../packages/n3tx-ui/docs/formidable.md#custom-form-path).
The built-in login pages assume a compatible concrete `BaseUser` model and routes;
use the tutorial's authentication setup rather than a hand-written login action.

### One URL namespace, several source packages

```text
Requested /components/ntx-list.js
       |
       +-> app static overrides
       +-> n3tx-agents static (if importable)
       +-> n3tx-ui static
       +-> n3tx-core static
             first matching file wins
```

`/core/NTT.js` comes from core; `/components/ntx-list.js` comes from UI.
Their relative imports resolve in the **same root namespace**. A separate
`/static/ui` mount alone is not a working bootstrap. Keep override names deliberate;
an app `config.js` replaces the framework file rather than merging with it.

Browser `config.API_URL` defaults to `window.location.origin`; `WS_URL` defaults
to empty (HTTP). Backend schema `$id` supplies deployed API identity, so configure
the backend API URL correctly too. For cross-origin or prefixed deployments,
review [transport](TRANSPORT.md) and static URL assumptions rather than replacing
the model contract with client constants.

## 2. Schema and data are separate readiness states

```text
<ntx-list model="Issue">
   | ATTACH
   v
NTT registry -- GET /Issue --> schema + $defs
   | creates DynamicClass; replays waiting attachments
   v
ListElement.definedCallback()
   | READ {limit:20, offset:0, depth:1}
   v
GET /Issue/_ --> {data:[...], meta:{...}}
   | DynamicClass.READ: upsert entity cache, notify address list
   v
<ntx-item ref="Issue/1">
   | ATTACH -> entity -> DESCRIBE {proto, data}
   v
NTTElement.value -> update(prev,next) or scheduleRender() -> UI
```

- `NTT.attach('Issue', callback)` means **schema/class ready**, not records loaded.
- `NTT.SCHEMA()` registers classes; it does not automatically request every record.
  Lists initiate paginated reads; missing member attachments initiate individual reads.
- `NTT.get('Issue/1')` reads the current cache synchronously; it is not a fetch.
- Entity `$schema` identifies its model; `$id` identifies the entity. Local
  relationships retain flat child identities, not invented parent-scoped URLs.
- Browser notifications synchronize local consumers. They do not by themselves
  prove cross-client live updates or conflict resolution.

The backend model owns the contract. Components consume `properties`, `methods`,
`$defs`, `ui`, and `access`; do not hand-copy those sections into app JavaScript.
See [models](../MODELS.md) and [schema pipeline](../../packages/n3tx-core/docs/schema-pipeline.md).

## 3. Choose an extension point

| Need | Use | Reference |
|---|---|---|
| Change field order, groups, renderer hints | Model `__ui__` / field `json_schema_extra` | [ViewableMixin](../../packages/n3tx-ui/docs/viewable-mixin.md) |
| Change one item's appearance, retain editing | Extend `NTTItem` | [Custom renderer](../../packages/n3tx-ui/docs/components.md#custom-item-renderer) |
| Own an entity's full DOM | Extend `NTTElement` | [Lifecycle](../../packages/n3tx-ui/docs/components.md#lifecycle) |
| Change collection presentation | Extend `NTTList`, or implement `ListElement.render()` | [Collections](../../packages/n3tx-ui/docs/components.md#collections) |
| Assemble an editor from the runtime schema | `Formidable` | [Forms](../../packages/n3tx-ui/docs/formidable.md) |
| Change one field type's presentation | Register a widget | [Widgets](../../packages/n3tx-ui/docs/widgets.md) |
| Change palette, layout, shadow CSS | Theme tokens / `styles` getter | [Styling](../../packages/n3tx-ui/docs/styling.md) |
| Navigate between views | `ntx-router` and schema renderer hints | [Routes](COMPONENTS.md#routing) |

## 4. Security and lifecycle limits

Backend authorization and validation remain authoritative. `ui.display=false`
does not make a field secret; hiding a button does not deny its API action.
Permissions metadata is a browser rendering aid, not an access grant. See
[authorization](../AUTHORIZATION.md).

Entity saves may send the complete current value. HTTP partial updates preserve
omitted fields, but supplied collections replace the field and writes are
last-write-wins. A domain method can express append/remove intent; its name does
not make the implementation atomic. See [update semantics](../API_CRUD_ENDPOINTS.md#update-resource).

### Preloading is not prerendering

`prerender()` is a component lifecycle hook for structural DOM. NTT also supports
one-shot JSON tags named `data-ntx-schema="Issue"` and
`data-ntx-data="issues"` (the latter uses `__tablename__`). Those tags seed runtime
state; they are not server-rendered components. Native app SSR modes inject schemas
and/or bundles, not an automatic authorization-safe dump of all records. Queue
replay can trigger a consumer READ before preloaded data is consumed, so do not
promise zero network requests. Never inline private data into a shared cached page.

## Troubleshooting

| Symptom | Inspect first |
|---|---|
| Unknown/empty element | Module import, HTTP status and `customElements.get(tag)` |
| Schema succeeds, list empty | `/Issue/_` response, auth state, registration/storage, pagination |
| Wrong origin in requests | Backend schema `$id`, browser `config.API_URL` |
| Custom view fails after direct navigation | `/components/{tag}.js` exists and dependencies are imported |
| Custom renderer stops updating | Inherited `update()` patch policy versus new DOM structure |
| Widget loses its handler | Formidable HTML serialization; use native inputs or custom elements |

## Further reference

[Components and routing](COMPONENTS.md) · [Runtime actors](ACTORS.md) ·
[Message protocol](MESSAGE_PROTOCOL.md) · [Transport](TRANSPORT.md) ·
[Test harness](../../tests/frontend/README.md).

The numbered enhancement/refactor documents and [package proposal](PACKAGE_ARCHITECTURE.md)
are historical design records, not current instructions.
