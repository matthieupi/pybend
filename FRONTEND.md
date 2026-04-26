# N3TX Frontend Reference

This document contains frontend-specific key files, schema consumption details, and patterns. It supplements the main `CLAUDE.md` which contains cross-cutting architecture, the multi-package structure, and all directives.

**Before reading this file**, check the documentation first. See `CLAUDE.md` → "Documentation-First Context Loading" for the required order.

Relevant docs:
- `/workspace/docs/frontend/ARCHITECTURE.md` — Frontend architecture overview
- `/workspace/docs/frontend/COMPONENTS.md` — Component layer details
- `/workspace/docs/frontend/TRANSPORT.md` — Transport protocol
- `/workspace/docs/frontend/ACTORS.md` — Frontend actor system
- `/workspace/docs/frontend/MESSAGE_PROTOCOL.md` — Message protocol
- `packages/n3tx-ui/docs/components.md` — Component hierarchy and lifecycle
- `packages/n3tx-ui/docs/formidable.md` — Form generator internals
- `packages/n3tx-ui/docs/styling.md` — Theme architecture, token contract, and frontend theme verification
- `packages/n3tx-ui/docs/widgets.md` — Widget system (JS side)

## Frontend Architecture (Vanilla JS Web Components)

The frontend is split across two packages:
- **n3tx-core** (`packages/n3tx-core/src/n3tx_core/static/`) — Non-visual JS runtime: messaging (Actor/TX/Matrix), entity system (NTT), abstract component bridge (Component), transport, utils
- **n3tx-ui** (`packages/n3tx-ui/src/n3tx_ui/static/`) — Visual layer: registered custom elements, base classes with visual behavior (NTTElement, ListElement), form generator, widgets, themes

At runtime, static files from both packages (plus n3tx-agents if installed) are merged into a single URL namespace by `_discover_static_dirs()` in `backend.py`. The browser doesn't know which package shipped each file.

```
NTT.js (n3tx-core)    Core entity system. Bootstraps by fetching schema from backend.
  |
  +-- SCHEMA()         Receives schema, creates DynamicClass via prototype()
  +-- prototype()      Builds class with typed properties, methods, value getter
  |                    Value getter injects $schema (schema URL) and $id (instance URL)
  |
  v
ntx-list.js (n3tx-ui)   <ntx-list model="Product"> - fetches and renders entity list
ntx-item.js (n3tx-ui)    <ntx-item> - adaptive entity rendering (xs pill → xl page)
ntx-stream.js (n3tx-ui)  Extends ntx-method for streaming methods (SSE + progressive output)
form.js (n3tx-ui)        Formidable generator - builds forms from schema properties
```

## Key Files

### JS Runtime (n3tx-core — non-visual)
- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js` - Core: NTT class, prototype() factory, SCHEMA handler, DynamicClass creation
- `packages/n3tx-core/src/n3tx_core/static/core/Actor.js` - Base actor class (messaging)
- `packages/n3tx-core/src/n3tx_core/static/core/TX.js` - Message envelope
- `packages/n3tx-core/src/n3tx_core/static/core/Matrix.js` - Message bus / root actor
- `packages/n3tx-core/src/n3tx_core/static/core/Component.js` - Abstract HTMLElement + Actor bridge (base for every web component)
- `packages/n3tx-core/src/n3tx_core/static/core/Observable.js` - Observer mixin
- `packages/n3tx-core/src/n3tx_core/static/core/Router.js` - Navigation state Actor (URL sync on by default, history stack, empty-string home route support)
- `packages/n3tx-core/src/n3tx_core/static/core/Utils.js` - Core utilities
- `packages/n3tx-core/src/n3tx_core/static/core/transport/HTTP.js` - HTTP adapter
- `packages/n3tx-core/src/n3tx_core/static/core/transport/Socket.js` - WebSocket transport
- `packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js` - Matrix ↔ network bridge
- `packages/n3tx-core/src/n3tx_core/static/utils/` - Frontend utils (Assert, Logging, Permissions, Toast, DateFormat, Snippets, etc.)
- `packages/n3tx-core/src/n3tx_core/static/config.js` - Frontend config

### Visual Components (n3tx-ui)
- `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js` - Abstract single-entity base (extends Component, adds forms, edit mode, modals)
- `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js` - Abstract collection lifecycle base (selection, pagination, child stamping)
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js` - Item component: size methods (xs-xl), render dispatch, edit toggle
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.js` - Default list renderer (header, grid, modal create, packed cards)
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.js` - Table component
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js` - Table row component
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js` - Method call button
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js` - Streaming method output (extends ntx-method). The fallback plain response box is opt-in via `show-output`; rich consumers like `ntx-chat` and `ntx-agent-live` should leave it off to avoid duplicate reply rendering.
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js` - Generic view container (loads any component via Router)
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js` - Modal overlay
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js` - Reference field picker
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js` - Model navigation sidebar
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar-link-item.js` - Sidebar dropdown record link renderer
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js` - Header/nav bar
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-theme-button.js` - Manual theme-cycle control for shell slots
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js` - User profile page
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-user.js` - User display

Pages that expose the topbar's built-in `#@profile` entry must import
`./components/ntx-profile.js` in their shell bootstrap. The router resolves the
route automatically, but custom elements still need explicit registration at app
load time.

### Form Generator (n3tx-ui)
- `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js` - Formidable: schema-driven form generator

### Widgets (n3tx-ui)
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js` - JS base Widget class with display/edit/list methods
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js` - JS registry: `registerWidget()`, `getWidgetForField()`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/index.js` - Loader: imports all built-ins, registers them
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/*.js` - Built-in widgets (Url, Email, Date, Markdown, Console, Reference, Currency, Textarea, Bool)
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css` - Widget-specific styles

Boolean fields now auto-resolve to the built-in `bool` widget even without an
explicit `ui.widget` schema hint, so display and edit modes both render a
checkbox.

### Agent UI (n3tx-agents)
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agents.js` - Hybrid agents list surface. Extends NTTList, combines stored AgentActor rows with app-supplied built-in workflow entries.
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js` - Purpose-built `AgentActor` entity component. Extends NTTItem and embeds `ntx-chat` plus `ntx-agent-live` for rich detail views.
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js` - NTTStreamAgent: rich agent output (entries, markdown, tool cards). Extends NTTStream.
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js` - Real-time agent activity view (extends NTTStream)
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js` - Threaded agent chat shell. Extends `NTTStreamAgent`, uses `create_thread` / `thread_id`, and switches between `xs` launcher mode and `sm+` inline mode from container size.

### Themes & Default HTML (n3tx-ui)
- `packages/n3tx-ui/src/n3tx_ui/static/theme-base.css` - Shared structural theme base (global selectors and layout chrome)
- `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css` - Dark theme
- `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css` - Light theme
- `packages/n3tx-ui/src/n3tx_ui/static/index.html` - Default app entry point (example apps override this)
- `packages/n3tx-ui/src/n3tx_ui/static/login.html` - Default login page
- `packages/n3tx-ui/src/n3tx_ui/static/register.html` - Default register page

For the full theme contract and verification workflow, see `packages/n3tx-ui/docs/styling.md`.

First-party pages now use a static theme contract:

```html
<link rel="stylesheet" href="./theme-base.css" />
<link rel="stylesheet" href="./dark-theme.css" />
<link rel="stylesheet" href="./light-theme.css" />
<script>
  window.NTX_THEME_CONFIG = { themes: ['dark', 'light'] };
</script>
<script type="module" src="./utils/theme.js"></script>
```

`theme.js` reads `window.NTX_THEME_CONFIG.themes` to determine the runtime cycling order and applies the persisted theme through `document.documentElement.dataset.theme` before first paint.

`dark-theme.css` and `light-theme.css` are token-only entrypoints; they no longer import shared structural selectors or expose legacy theme variable aliases.

Canonical theme state now lives in these runtime files:

- `packages/n3tx-core/src/n3tx_core/static/utils/theme.js` - persisted theme selection, configured theme order, `theme-change` dispatch
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-theme-button.js` - reusable manual theme switcher

`ntx-topbar` and `ntx-sidebar` now expose manual shell placement points for theme controls:

- `<ntx-theme-button slot="user-menu"></ntx-theme-button>` renders inside the authenticated topbar dropdown.
- `<ntx-theme-button slot="footer"></ntx-theme-button>` renders at the bottom of the sidebar.

Expanded sidebar model groups now mount the declared route-template tag when a
model section expands, except `ntx-table`, which still falls back to the compact
headless `ntx-list` dropdown shell. Plain dropdown lists still force `item-display="sm"` plus the
dedicated `ntx-sidebar-link-item` child renderer so record entries render as
real internal anchors instead of pill-mode `ntx-item` badges. That renderer
also owns the truncated-label tooltip behavior: it uses a slightly enlarged
hover target and a short custom delay instead of the browser-native `title`
timing, and only shows when the label truly overflows the available row width.
Its sidebar-specific row chrome lives in
`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar-link-item.css` so
`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css` stays generic.
Sidebar route-template children can set `sidebar-label="..."` to override the
displayed nav copy without changing the routed model/view, which is the intended
way to surface human-facing labels like `Agents` for `AgentActor`. Custom list
tags such as `ntx-agents` receive the same `model`, `router`, `headless`, and
`sidebar-dropdown` attrs so app-specific dropdown views can stay compact
without forking the sidebar.
Plain sidebar links follow router semantics too: `href="#"` navigates to the
router home route (empty route, no hash), while `href="#profile"` maps to the
app route `@profile`.

Standard wide `ntx-list` card views now pack uneven card heights more tightly.
`ListElement` keeps CSS grid source ordering, but when children resolve to
`display="md"` it measures each child host with `ResizeObserver` and applies a
small `grid-row-end` span so later cards can rise into gaps left by shorter
neighbors. Sidebar dropdowns and compact lists stay on the existing strict
single-track flow.

The shell components do not auto-render theme controls from config; pages place them explicitly.

Major first-party framework styles now read canonical theme tokens directly in `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.css`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.css`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.css`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.css`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css`, and `packages/n3tx-ui/src/n3tx_ui/static/auth.css`. Status treatments in those surfaces use the canonical `--ntx-status-*` token family.

Veille and the shipped examples now follow the same canonical token contract too, including `apps/veille/static/veille.css`, `apps/veille/static/components/ntx-run-output.css`, `apps/veille/static/components/ntx-run-report.css`, the example login/register pages, and the first-party example shells under `examples/`.

Logged-out pages still honor the persisted theme but do not render `<ntx-theme-button>`.

## Frontend Test Environment

Frontend verification now has two layers:

- `cd /workspace/tests/frontend && npx vitest run` - JS unit tests for runtime, components, and helpers
- `cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js` - browser verification against the seeded `examples/core` app
- `cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/veille.playwright.config.js` - Veille browser verification, including Assistant chat with deterministic `N3TX_CHAT_LLM=test`

The Playwright harness boots `examples/core` as the test app, seeds an isolated SQLite database in `global-setup.js`, and cleans it up in `global-teardown.js`. The harness also passes `PYTHONPATH` so package source trees resolve without installation.

For local execution in this workspace, the Python web dependencies used by the Playwright server live in `/workspace/.venv-e2e`. The harness auto-detects that venv and falls back to `python3` if it is absent.

## Frontend Split Rationale

The backend split axis (core/actors/agents) doesn't map to the frontend. Analysis of the JS import graph:

- **Component.js** imports Actor, Matrix, AND TX — it's the base for every web component
- **NTT.js** extends Actor and uses Matrix — it's the entity registry
- Every `ntx-*` component transitively depends on all three "actor" files

The frontend split axis is **runtime vs. visual**:
- **n3tx-core**: Non-visual runtime — messaging, entity system, abstract component bridge, transport, utils
- **n3tx-ui**: Visual layer — registered custom elements, visual base classes, form generator, widgets, themes
- **n3tx-agents**: Agent-specific UI — `ntx-chat.js` only

No circular dependencies:
```
core ← ui      (ui imports from core, never reverse)
core ← agents  (agents imports from core, never reverse)
ui and agents are independent of each other
```

## Static File Serving (Multi-Package)

Three packages bundle `static/` directories (n3tx-core, n3tx-ui, n3tx-agents). At runtime, `N3TXApp` discovers and merges them into a single URL namespace.

**Mount priority** (highest first):
1. App-specific static dirs (from `create_app(static_dir=...)`)
2. n3tx-agents static (if installed) — `ntx-chat.js`
3. n3tx-ui static (if installed) — all components, widgets, themes, default HTML
4. n3tx-core static (catch-all) — JS runtime, utils, config

`index.html` lives in n3tx-ui and imports from both core and ui directories. Since all static dirs merge into the same URL namespace, relative imports resolve correctly. Example apps override `index.html` with their own versions (existing pattern).

## Schema as Universal Contract

The JSON Schema returned by `GET /{ClassName}` is the **single contract between backend and frontend**. It is not just a type description — it is the complete specification of how an entity behaves, renders, and is controlled.

For full schema anatomy details, see `/workspace/docs/CORE.md`.

### How Each Schema Section Is Consumed

**Frontend reads schema once, adapts everything at runtime:**

| Schema section | Frontend consumer | What it controls |
|---------------|------------------|-----------------|
| `properties` | `prototype()` in NTT.js | Creates typed getters/setters on DynamicClass |
| `properties[field].type` | `form.js` → `getInput()` | Chooses input type (text, number, checkbox, ...) |
| `properties[field].ui.widget` | `form.js` → `getInput()` | Specialized rendering (currency prefix, textarea) |
| `properties[field].ui.display` | `form.js` → field filtering | Hides internal fields |
| `properties[field].ui.protected` | `form.js` → field filtering | Hides backend-owned fields in edit mode |
| `properties[field].ui.placeholder` | `form.js` → input attrs | Sets placeholder text on inputs |
| `properties[field].access` | `Permissions.js` → `canView()` | Field-level visibility per user role |
| `ui.field_order` | `form.js` → `getForm()` | Controls field rendering sequence |
| `ui.groups` | `form.js` → `renderGroupedFields()` | Wraps fields in `<fieldset>` groups |
| `ui.description` | `NTTList.render()` | Optional collection intro text under the header title |
| `ui.create_label` | `NTTList.render()` | Optional labeled collection create button |
| `ui.icon` | `ntx-icon` + icon resolver | Shared icon rendering for model shells and method actions |
| `ui.renderer.*` | `ntx-router.js` → `#resolveTag()` | Chooses component tag for navigation views |
| `access` | `Permissions.js` → `canAction(access, action, resource)` | Shows/hides edit/delete buttons with resource-aware OWNER evaluation |
| `methods` | `prototype()` + `<ntx-method>` / `<ntx-stream>` | Creates callable methods + renders action buttons |
| `$defs` | `NTT.SCHEMA()` | Registers nested DynamicClasses |
| `$id` / `$schema` | DynamicClass value getter | Injected into every entity instance for self-description |

### Shared Icons

`ui.icon` is resolved by `packages/n3tx-ui/src/n3tx_ui/static/utils/icon-resolver.js`
and rendered by `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-icon.js`.
Resolution order is: empty → nothing, registered lookup key → inline SVG or
other registered token, URL/path-like string → image icon, emoji → emoji icon,
otherwise raw text. Emoji tokens use a best-effort monochrome filter
controlled with CSS variables such as `--icon-filter`, `--icon-opacity`, and
`--icon-size`.

Apps can register their own icon packs at startup with `registerIcons({...})`.
Veille does this in `apps/veille/static/utils/veille-icons.js` before importing
its shell components, so model `__ui__.icon` tokens and app-shell `<ntx-icon>`
usage both resolve through the shared registry.

`ntx-topbar`'s built-in chrome icons are separate from that registry. Profile,
logout, chevron, and hamburger are inline SVG constants defined directly in
`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js`.

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
   NTT.SCHEMA(data) → prototype(addr, schema, href) → DynamicClass
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
   │  Collection fields return href arrays: ["http://.../products/1/comments/1", ...]
```

## Frontend Patterns

### Widget Extension (JS)
On the frontend, `form.js` and `ntx-item.js` dispatch to registered JS Widget instances (`getWidgetForField()`) before falling through to type-based rendering. See `packages/n3tx-ui/docs/widgets.md` for the full widget system.

```javascript
class ColorWidget extends Widget { display(v) { ... } }
registerWidget('color', new ColorWidget());
```

### Streaming Transport

The frontend transport layer supports streaming for long-running operations. See `packages/n3tx-ui/docs/components.md` for the `<ntx-stream>` component.

#### HTTP.stream()

`HTTP.stream(url, data, onChunk, onDone, onError)` — SSE client using Fetch API with `ReadableStream`. Parses `event: chunk|done|error` and `data: {json}` lines. Returns `{ cancel: Function }` for AbortController cancellation.

A `_done` guard prevents double `onDone` callbacks when SSE `event: done` is followed by ReadableStream closure.

```javascript
const handle = HTTP.stream('/products/1/generate', { prompt: 'hello' },
    (chunk) => console.log('Chunk:', chunk),
    (data)  => console.log('Done:', data),
    (err)   => console.error('Error:', err),
);
handle.cancel();  // Cancel mid-stream
```

#### Socket.registerStream()

`socket.registerStream(reqId, onChunk, onDone, onError)` — registers stream handlers for correlated WS messages. Messages with `meta.stream` and matching `meta.req` are dispatched to the registered handler.

#### NetworkAdapter.sendStream()

`adapter.sendStream(event, onChunk, onDone, onError)` — unified streaming API. Uses WebSocket if connected, falls back to HTTP SSE.

#### `<ntx-stream>` Component

Extends `NTTMethod`. For methods with `schema.methods[m].stream === true`. Renders progressive output with blinking cursor, cancels in-flight streams on disconnect.

```html
<ntx-stream model="Product" uuid="1" method="generate" label="Generate"></ntx-stream>
```

### NTTStreamAgent (Agent Streaming)

**File**: `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js`

Extends `NTTStream` with rich agent output rendering — typed entries (thinking, tool calls, text), markdown rendering, and tool result cards. All agent-style streaming components extend `NTTStreamAgent` (or `NTTStream` directly for simpler cases):

```javascript
import { NTTStreamAgent } from './ntx-stream-agent.js';

class MyComponent extends NTTStreamAgent {
    // UPPERCASE = TX inbox handlers (actor convention)
    TEXT(data, meta)       { /* data.text */ }
    TOOL_CALL(data, meta)  { /* data.tool, data.args, data.call_id */ }
    DONE(data, meta)       { /* data.answer, data.usage */ }

    // Lifecycle hooks
    STREAM_END(data)       { /* stream completed */ }
    STREAM_ERROR(err)      { /* error */ }
}
```

**Component hierarchy:**

```
Component → NTTMethod → NTTStream → NTTStreamAgent → (app subclasses)
```

**Lifecycle hooks:**

| Method | When | Purpose |
|--------|------|---------|
| `prerender()` | `connectedCallback()`, before schema | Structural DOM (shell, layout). Never wiped by render(). |
| `render()` | After schema arrives | Additive updates (title, etc.). Must not wipe prerender() output. |
| `callMethod()` | User triggers execution | Starts stream. Generates `#streamReqId` correlation ID. |
| `cancel()` | Cleanup / user action | Sets `#cancelled` flag, sends `STREAM_CANCEL` TX, calls `STREAM_END`. |
| `disconnectedCallback()` | Element removed | Auto-calls `cancel()` for cleanup. |

**Dispatch flow:**

1. `callMethod()` sends TX with `meta: {stream: true, req: reqId}` via Actor system
2. Backend sends stream chunks as TX messages
3. `NTTStream.STREAM()` handler receives chunks, skips if `#cancelled`
4. Dispatches to UPPERCASE handlers: `THINKING()`, `TOOL_CALL()`, `TEXT()`, `DONE()`, `STREAM_END()`, `STREAM_ERROR()`

**UPPERCASE convention**: All methods that handle TX messages are UPPERCASE. lowercase/camelCase = internal component logic. This mirrors the backend actor handler pattern.

**Concrete components extending NTTStream:**
- `<ntx-agent-live>` — Real-time agent activity log with structured event rendering
- `<ntx-chat>` — Floating chat panel for conversational agent interaction

Both extend `NTTStream` directly, use `prerender()` for structural UI, and auto-cancel streams in `disconnectedCallback()`.

### Schema-Declared Stream Events

Streaming methods can declare their event vocabulary via `events=` on `@expose_route` (backend). The schema pipeline serializes these into `schema.methods[m].events`:

```json
{
  "methods": {
    "agentic_stream": {
      "stream": true,
      "events": {
        "text": {"type": "object", "properties": {"text": {"type": "string"}}},
        "tool_call": {"type": "object", "properties": {"tool": {...}, "args": {...}}},
        "done": {"type": "object", "properties": {"answer": {...}, "usage": {...}}}
      }
    }
  }
}
```

Frontend components can read `events` to discover available chunk types and validate their handler coverage.
