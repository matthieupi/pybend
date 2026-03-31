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
- `packages/n3tx-core/src/n3tx_core/static/core/Router.js` - Navigation state Actor (URL sync on by default, history stack)
- `packages/n3tx-core/src/n3tx_core/static/core/Utils.js` - Core utilities
- `packages/n3tx-core/src/n3tx_core/static/core/transport/HTTP.js` - HTTP adapter
- `packages/n3tx-core/src/n3tx_core/static/core/transport/Socket.js` - WebSocket transport
- `packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js` - Matrix ↔ network bridge
- `packages/n3tx-core/src/n3tx_core/static/utils/` - Frontend utils (Assert, Logging, Permissions, Toast, DateFormat, Snippets, etc.)
- `packages/n3tx-core/src/n3tx_core/static/config.js` - Frontend config

### Visual Components (n3tx-ui)
- `packages/n3tx-ui/src/n3tx_ui/static/components/NTTElement.js` - Abstract single-entity base (extends Component, adds forms, edit mode, modals)
- `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js` - Abstract collection base (extends Component, adds pagination, filtering)
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js` - Item component: size methods (xs-xl), render dispatch, edit toggle
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.js` - List component
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.js` - Table component
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js` - Table row component
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js` - Method call button
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-stream.js` - Streaming method output (extends ntx-method)
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js` - Generic view container (loads any component via Router)
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js` - Modal overlay
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js` - Reference field picker
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js` - Model navigation sidebar
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js` - Header/nav bar
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js` - User profile page
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-user.js` - User display

### Form Generator (n3tx-ui)
- `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js` - Formidable: schema-driven form generator

### Widgets (n3tx-ui)
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/Widget.js` - JS base Widget class with display/edit/list methods
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/registry.js` - JS registry: `registerWidget()`, `getWidgetForField()`
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/index.js` - Loader: imports all built-ins, registers them
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/*.js` - Built-in widgets (Url, Email, Date, Markdown, Console, Reference, Currency, Textarea)
- `packages/n3tx-ui/src/n3tx_ui/static/widgets/widgets.css` - Widget-specific styles

### Agent UI (n3tx-agents)
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.js` - NTTStreamAgent: rich agent output (entries, markdown, tool cards). Extends NTTStream.
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent-live.js` - Real-time agent activity view (extends NTTStream)
- `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-chat.js` - Agent chat panel (extends NTTStream)

### Themes & Default HTML (n3tx-ui)
- `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css` - Dark theme
- `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css` - Light theme
- `packages/n3tx-ui/src/n3tx_ui/static/index.html` - Default app entry point (example apps override this)
- `packages/n3tx-ui/src/n3tx_ui/static/login.html` - Default login page
- `packages/n3tx-ui/src/n3tx_ui/static/register.html` - Default register page

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
| `ui.renderer.*` | `ntx-router.js` → `#resolveTag()` | Chooses component tag for navigation views |
| `access` | `Permissions.js` → `canAction(access, action, resource)` | Shows/hides edit/delete buttons with resource-aware OWNER evaluation |
| `methods` | `prototype()` + `<ntx-method>` / `<ntx-stream>` | Creates callable methods + renders action buttons |
| `$defs` | `NTT.SCHEMA()` | Registers nested DynamicClasses |
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
