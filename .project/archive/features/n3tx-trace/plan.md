# TX Inspector — Actor Transaction Visualization Tool

## Context

N3TX's actor system routes all messages through Matrix as TX envelopes. Currently there's no way to visualize the transaction flow between actors at runtime — only scattered `logger.debug` calls and a leftover `print(tx)` in `actor.py:237`. This tool adds a debug-only visual inspector that shows the actor topology as an interactive node graph (LiteGraph.js — ComfyUI-style canvas) with TX messages as color-coded edges, plus a sidebar for browsing request chains.

## Package: n3tx-trace

All code lives in a **new standalone package** `n3tx-trace`. This keeps the core actor system untouched — n3tx-trace monkey-patches Matrix.inbox() at runtime when enabled, requiring zero modifications to n3tx-actors source code.

**Dependency graph** (updated):
```
n3tx-core              ← foundation, no N3TX deps
n3tx-actors            ← depends on n3tx-core
n3tx-ui                ← depends on n3tx-core
n3tx-agents            ← depends on n3tx-core + n3tx-actors
n3tx-trace             ← depends on n3tx-core + n3tx-actors (optional debug tool)
n3tx                   ← meta-package, depends on all five
```

n3tx-trace is an **optional dependency** — if not installed, `debug=True` works as before (FastAPI docs + logging), just without the visual inspector.

## Architecture

Three layers, all gated behind `debug=True` + n3tx-trace being installed:

```
Backend (n3tx-trace)                Frontend (n3tx-trace static/)
┌──────────────────────┐            ┌──────────────────────────────────────┐
│ Matrix.inbox() hook  │──capture──→│  <ntx-tx-inspector>                  │
│ TraceCollector       │            │  ┌────────────────────┬────────────┐ │
│  (ring buffer 2000)  │──SSE────→  │  │  LiteGraph Canvas  │ <tx-sidebar│ │
│ /debug/* routes      │            │  │  Actor nodes       │  TX list   │ │
│ trace_id propagation │            │  │  + TX edges        │  + filter  │ │
└──────────────────────┘            │  └────────────────────┴────────────┘ │
                                    └──────────────────────────────────────┘
```

## File Structure

```
packages/n3tx-trace/
  pyproject.toml             # Package metadata, deps: n3tx-core, n3tx-actors
  src/n3tx_trace/
    __init__.py              # enable_tracing(app, matrix) entry point
    tracer.py                # TraceCollector + TraceEntry
    trace_context.py         # contextvars-based trace_id propagation
    routes.py                # FastAPI debug routes
    static/
      debug.html             # Inspector page shell
      vendor/
        litegraph.js         # LiteGraph.js library (vendored, ~180KB)
        litegraph.css        # LiteGraph default styles
      components/
        ntx-tx-inspector.js  # Main component: layout + SSE + state coordination
        tx-graph.js          # LiteGraph graph setup, custom node types, TX edge rendering
        tx-sidebar.js        # Scrollable TX list with hover/click
        tx-detail.js         # Request chain drill-down panel
      inspector.css          # Dark theme overrides for LiteGraph + sidebar styles
    tests/
      test_tracer.py         # TraceCollector unit tests
      test_trace_context.py  # contextvars propagation tests
      test_routes.py         # Debug endpoint tests
```

---

## Backend

### 1. Trace Hook on Matrix.inbox()

The critical insight: Matrix.inbox() resolves pending futures (correlation) BEFORE interceptors run (matrix.py:56-65). Response TXs are consumed before interceptors see them. So we **cannot use interceptors** for tracing.

Instead, `enable_tracing()` wraps the Matrix instance's `inbox` method to fire trace capture + trace_id propagation BEFORE any routing logic:

```python
async def traced_inbox(tx):
    # ── trace_id propagation ──
    # If TX has no trace_id, inherit from contextvar (set by parent request)
    # or assign tx.uuid as new root trace_id
    trace_id = tx.meta.get('trace_id')
    if not trace_id:
        ctx_trace = get_trace_id()
        trace_id = ctx_trace or tx.uuid
        tx.meta['trace_id'] = trace_id
    token = set_trace_id(trace_id)

    # ── capture ──
    collector.capture(tx)

    try:
        await original_inbox(tx)
    finally:
        if token:
            token.var.reset(token)
```

**Why this works without modifying Actor.send()**: ALL TXs flow through Matrix.inbox() — both incoming requests and outgoing responses. When an actor handler (e.g., agent) creates a new TX and sends it, it bubbles up through Actor.send() → parent.send() → Matrix.inbox(). At that point, the contextvar (set when the original request entered Matrix) is still active in the async context, so the hook reads it and stamps the new TX with the same trace_id. No changes to Actor or any other core code needed.

Uses `object.__setattr__` for Pydantic PrivateAttr compatibility (same pattern as our test mocks — see MEMORY.md).

### 2. Trace Context Propagation (trace_context.py)

Links nested TXs into request chains using `contextvars`:

```python
import contextvars

_current_trace: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    'n3tx_trace_id', default=None
)

def get_trace_id() -> str | None:
    return _current_trace.get()

def set_trace_id(trace_id: str) -> contextvars.Token:
    return _current_trace.set(trace_id)
```

- When a TX enters Matrix without a `trace_id`, it gets `trace_id = tx.uuid` (root)
- The contextvar persists through `await` chains — when Matrix routes TX to an actor handler and that handler sends sub-requests, those sub-requests arrive at Matrix.inbox() where the hook reads the contextvar and stamps them
- `asyncio.create_task()` automatically copies context, so fire-and-forget lifecycle events also inherit the trace_id

This means: HTTP request → agent → products → comments all share one `trace_id`, enabling the full request chain view.

### 3. TraceCollector (tracer.py)

```python
class TraceEntry:
    tx_uuid, name, source, target, timestamp,
    trace_id, req, is_error, is_stream, seq, data_summary

class TraceCollector:
    _buffer: deque(maxlen=2000)       # Ring buffer
    _clients: dict[id, asyncio.Queue] # SSE fan-out

    capture(tx)      # Sync — called from inbox hook
    snapshot()       # Current buffer as list[dict]
    subscribe(id)    # Returns Queue for SSE client
    unsubscribe(id)  # Cleanup
```

Fan-out uses `put_nowait` — zero cost when no clients connected. Full queue → drop client (acceptable for debug tool).

### 4. Debug Routes (routes.py)

| Endpoint | Purpose |
|----------|---------|
| `GET /debug/` | Inspector HTML page |
| `GET /debug/topology` | Actor tree as JSON `{nodes, edges}` |
| `GET /debug/snapshot` | Current trace buffer |
| `GET /debug/stream` | SSE live TX events |
| `GET /debug/static/{path}` | Debug UI static files |

Topology endpoint walks `matrix._children` and `matrix._adapters` recursively to build the graph.

### 5. N3TXApp Integration

In `app.py` build(), after actor routing setup (line ~250), add:

```python
if self._debug and self._routing == 'actor':
    try:
        from n3tx_trace import enable_tracing
        enable_tracing(backend.app, matrix)
    except ImportError:
        pass  # n3tx-trace not installed — skip
```

Optional dependency — `try/except ImportError` means debug mode still works without n3tx-trace installed.

### 6. Cleanup

Remove the `print(tx)` debug leftover on line 237 of `actor.py`. This is unrelated housekeeping but should be done while we're in this area.

---

## Frontend (LiteGraph.js)

### Why LiteGraph.js

- Canvas2D rendering with built-in zoom/pan (ComfyUI/Blender-style)
- Custom node types with full control over appearance (`onDrawForeground`)
- Programmatic node creation and connection API
- Mouse events on nodes (click, hover, double-click)
- `allow_interaction = false` for read-only mode
- No framework dependency — vanilla JS, includable via `<script>` tag

### Layout

```
┌────────────────────────────────────────────┬────────────────────┐
│         LITEGRAPH CANVAS                   │     SIDEBAR        │
│                                            │                    │
│  ┌──────────┐         ┌────────────┐      │  [filter input]    │
│  │ NetworkAPI│────────→│  Product   │      │                    │
│  │  (api)   │    ┌───→│ (products) │      │  ● create products │
│  └──────────┘    │    └────────────┘      │  ● list products   │
│                  │                         │  ● get users/3     │
│  ┌──────────┐   │    ┌────────────┐       │  ● update prod/1   │
│  │NetworkWS │   │    │  Comment   │       │                    │
│  │  (ws)    │   │    │ (comments) │       ├────────────────────┤
│  └──────────┘   │    └────────────┘       │  CHAIN DETAIL      │
│                  │                         │  (shown on click)  │
│  Zoom/pan via LiteGraph built-in          │                    │
│  Edges colored red→blue by time           │                    │
│  Hover sidebar → highlight edge           │                    │
└────────────────────────────────────────────┴────────────────────┘
```

### Custom LiteGraph Node Types (tx-graph.js)

Register one node type per actor category:

```javascript
// Actor node base — inputs (receives TX) and outputs (sends TX)
function ActorNode() {
    this.addInput("in", "tx");
    this.addOutput("out", "tx");
    this.size = [180, 50];
    this.properties = { addr: '', actorType: 'model', txCount: 0 };
    this.color = "#2a4858";
    this.bgcolor = "#1a2a38";
}

ActorNode.title = "Actor";
ActorNode.prototype.onDrawForeground = function(ctx) {
    // Custom rendering: activity pulse, TX count badge
    if (this.properties.txCount > 0) {
        ctx.fillStyle = "#58a6ff";
        ctx.beginPath();
        ctx.arc(this.size[0] - 15, 10, 5, 0, Math.PI * 2);
        ctx.fill();
    }
};

// Register variants with different colors
LiteGraph.registerNodeType("actor/adapter", AdapterNode);  // blue
LiteGraph.registerNodeType("actor/model", ModelNode);       // green
LiteGraph.registerNodeType("actor/agent", AgentNode);       // purple
```

### Dynamic Edge Management

LiteGraph connections are persistent graph edges. We use them as **channels** that "light up" when TX flows through:

1. **Topology load**: Create nodes for each actor. No connections yet.
2. **First TX between A→B**: Create connection `nodeA.connect(0, nodeB, 0)`. Store link_id.
3. **Subsequent TX on same path**: Update the link's color to show activity.
4. **Request chain view**: Set link colors based on chain position (red→blue gradient). Dim non-chain links.
5. **Link color API**: `graph.links[link_id].color = "#ff4444"` per-link coloring.

### Color Coding

- **Live mode**: Active edges pulse with accent color (`#58a6ff`), fade to dim (`#333`) after 2s
- **Chain view**: Edges colored by position in chain: first = `hsl(0,80%,60%)` (red), last = `hsl(240,80%,60%)` (blue), interpolated linearly by timestamp
- **Error edges**: Red dashed (`#f85149`)
- **Stream edges**: Teal (`#3fb950`), thickness increases with chunk count

### Node Positioning

LiteGraph has no auto-layout, so we position programmatically on topology load:

```javascript
// 3-column layout
const COLS = { adapter: 100, matrix: 400, model: 700 };
const ROW_GAP = 100;
const ROW_START = 100;

topology.nodes.forEach((n, i) => {
    const node = LiteGraph.createNode(`actor/${n.type}`);
    node.title = n.label;
    node.properties.addr = n.id;
    node.pos = [COLS[n.type] || COLS.model, ROW_START + i * ROW_GAP];
    graph.add(node);
});
```

Users can drag nodes to rearrange (LiteGraph built-in). Position persists for the session.

### Component Architecture

**`<ntx-tx-inspector>`** — Main layout + state manager (Web Component, Shadow DOM)
- Creates split layout: canvas area (75%) + sidebar (25%)
- Fetches `/debug/topology` + `/debug/snapshot` on connect
- Opens `EventSource` to `/debug/stream` for live updates
- Maintains: entries array (capped at 2000), selected trace_id, node map, link map
- Coordinates graph and sidebar via method calls + DOM events

**`tx-graph.js`** — LiteGraph wrapper (module, not Web Component)
- Initializes `LGraph` + `LGraphCanvas` on the inspector's canvas element
- Registers custom node types (adapter, model, agent)
- Exposes: `addActorNode()`, `addTxEdge()`, `highlightEdge()`, `highlightChain()`, `clearHighlights()`
- Manages link-to-TX mapping for hover/click resolution
- Custom dark theme via LiteGraph CSS override + `graphCanvas.default_link_color`

**`<tx-sidebar>`** — Transaction list (Web Component, Shadow DOM)
- Scrollable list, newest first
- Each entry: `[timestamp] source → target name`
- Color by type: CRUD=default, ERROR=red, STREAM=teal, LIFECYCLE=amber
- Hover → emits `tx-hover` → inspector calls `graph.highlightEdge(tx_uuid)`
- Click → emits `tx-select` → inspector calls `graph.highlightChain(trace_id)`
- Text filter + trace_id dropdown for filtering
- Auto-scroll unless user scrolled up

**`<tx-detail>`** — Request chain drill-down (Web Component, Shadow DOM)
- Shows all TXs with same `trace_id`, ordered by timestamp
- Time offset from root TX, source→target, name, badges (root/response/error/stream)
- Total chain duration
- Selecting highlights ALL chain edges in graph simultaneously

### Interaction Flow

1. Page loads → LiteGraph canvas renders actor nodes from topology
2. SSE stream starts → new TXs create/animate edges + appear in sidebar
3. Hover sidebar entry → corresponding edge highlighted (bright color, thicker)
4. Click sidebar entry → all edges for that `trace_id` shown with red→blue gradient, non-chain edges dim
5. Click "clear" or Escape → return to live mode
6. LiteGraph zoom/pan works natively (scroll wheel, drag background)

### Dark Theme

Override LiteGraph defaults in `inspector.css`:

```css
.litegraph .lgraphcanvas {
    background-color: #0d1117;
}
/* Override node colors, link colors, selection colors, etc. */
```

Plus set JS properties:
```javascript
LiteGraph.NODE_DEFAULT_COLOR = "#2a4858";
LiteGraph.NODE_DEFAULT_BGCOLOR = "#1a2a38";
LiteGraph.DEFAULT_LINK_COLOR = "#444";
```

---

## Implementation Phases

### Phase 0: Package Scaffolding
1. Create `packages/n3tx-trace/` directory structure
2. Create `pyproject.toml` (hatchling build, deps: n3tx-core, n3tx-actors)
3. Create `src/n3tx_trace/__init__.py` with `enable_tracing()` stub
4. `pip install -e packages/n3tx-trace`
5. Remove `print(tx)` from actor.py:237

### Phase 1: Backend Trace Infrastructure
1. Implement `tracer.py` (TraceCollector + TraceEntry)
2. Implement `trace_context.py` (contextvars)
3. Complete `__init__.py` (enable_tracing: Matrix.inbox() wrapping)
4. Implement `routes.py` (debug endpoints)
5. Wire `enable_tracing()` in `N3TXApp.build()` (app.py — `try/except ImportError`)
6. Write tests in `tests/`

### Phase 2: Static Graph (LiteGraph)
1. Vendor `litegraph.js` + `litegraph.css` into `static/vendor/`
2. Create `debug.html` shell page
3. Create `ntx-tx-inspector.js` — layout, topology fetch, canvas setup
4. Create `tx-graph.js` — LiteGraph init, custom node types, dark theme
5. Create `inspector.css` — dark theme overrides
6. Verify: start `examples/actors` with `debug=True`, navigate to `/debug/`, see actor graph

### Phase 3: Live Streaming + Sidebar
1. Create `tx-sidebar.js` — scrollable TX list
2. Add EventSource in inspector for `/debug/stream`
3. Wire live entries → dynamic edge creation/animation in graph + sidebar append
4. Add hover highlighting (sidebar ↔ graph edge)
5. Verify: make API requests via curl, watch TXs flow in real-time

### Phase 4: Request Chain + Detail
1. Create `tx-detail.js` — chain view panel
2. Click sidebar entry → show chain, highlight all chain edges with red→blue gradient
3. Dim non-chain edges
4. Sidebar filtering (text + trace_id dropdown)
5. Polish: edge fade timing, node activity pulse, auto-scroll, error edge styling

---

## Key Files Modified

| File | Change |
|------|--------|
| `packages/n3tx-actors/src/n3tx_actors/actor.py` | Remove `print(tx)` line 237 (cleanup only) |
| `packages/n3tx-core/src/n3tx_core/app.py` | Add `try: from n3tx_trace import enable_tracing` in `build()` |

## Key Files Created (all in `packages/n3tx-trace/`)

| File | Purpose |
|------|---------|
| `pyproject.toml` | Package config (hatchling, deps) |
| `src/n3tx_trace/__init__.py` | `enable_tracing()` entry point |
| `src/n3tx_trace/tracer.py` | TraceCollector + TraceEntry |
| `src/n3tx_trace/trace_context.py` | contextvars trace_id propagation |
| `src/n3tx_trace/routes.py` | FastAPI debug endpoints |
| `src/n3tx_trace/static/vendor/litegraph.js` | LiteGraph.js library (vendored) |
| `src/n3tx_trace/static/vendor/litegraph.css` | LiteGraph.js styles |
| `src/n3tx_trace/static/debug.html` | Inspector page shell |
| `src/n3tx_trace/static/components/ntx-tx-inspector.js` | Main inspector component |
| `src/n3tx_trace/static/components/tx-graph.js` | LiteGraph wrapper + custom nodes |
| `src/n3tx_trace/static/components/tx-sidebar.js` | TX list sidebar |
| `src/n3tx_trace/static/components/tx-detail.js` | Request chain detail |
| `src/n3tx_trace/static/inspector.css` | Dark theme + layout styles |
| `src/n3tx_trace/tests/test_tracer.py` | TraceCollector unit tests |
| `src/n3tx_trace/tests/test_trace_context.py` | contextvars propagation tests |
| `src/n3tx_trace/tests/test_routes.py` | Debug endpoint tests |

## Verification

1. Start actors example: `cd examples/actors && python3 main.py` (with `debug=True`)
2. Open `/debug/` in browser → LiteGraph canvas shows actor nodes (api, ws, products, users, etc.)
3. Make API requests (`curl` CRUD operations) → TXs appear as animated edges + sidebar entries
4. Hover sidebar entry → corresponding edge highlights in canvas
5. Click a request → full chain displayed with red→blue gradient, detail panel opens
6. Zoom/pan with scroll wheel and drag — LiteGraph built-in
7. Run tests: `python3 -m pytest packages/n3tx-trace/src/n3tx_trace/tests/`
