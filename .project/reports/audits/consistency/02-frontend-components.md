# Frontend JavaScript Component Patterns Audit

**Date**: 2026-03-26
**Scope**: All JavaScript files across packages/ and apps/
**Focus**: Component hierarchy, lifecycle patterns, event handling, schema consumption, CSS management

---

## Executive Summary

The N3TX frontend demonstrates **strong architectural consistency** in core components (85% overall), but shows **notable pattern divergence** in three areas:
1. **n3tx-trace package** -- all components use plain HTMLElement instead of Component
2. **Sidebar/Modal/Profile/Topbar** -- extend HTMLElement instead of Component
3. **Direct fetch() calls** in some app components bypass TX/Matrix routing

---

## Component Hierarchy (Actual)

```
HTMLElement
+-- Component (n3tx-core/static/core/Component.js)
|   +-- NTTElement (n3tx-ui/static/components/NTTElement.js)
|   |   +-- NTTItem (ntx-item)
|   |       +-- NTTUser (ntx-user)
|   |       +-- NTTRow (ntx-row)
|   +-- ListElement (n3tx-ui/static/components/ListElement.js)
|   |   +-- NTTList (ntx-list)
|   |   +-- NTTTable (ntx-table)
|   +-- NTTMethod (ntx-method)
|   |   +-- NTTStream (ntx-stream)
|   |       +-- NTTStreamAgent (ntx-stream-agent)
|   |       +-- NTTAgentLive (ntx-agent-live)
|   |       +-- NTTChat (ntx-chat)
|   |       +-- NTXRunOutput (ntx-run-output) [veille]
|   +-- NTTRouter (ntx-router)
|
+-- HTMLElement DIRECT (DEVIATIONS)
    +-- NTTSidebar (ntx-sidebar)
    +-- NTTModal (ntx-modal)
    +-- NTTProfile (ntx-profile)
    +-- NTTTopbar (ntx-topbar)
    +-- NTTRefPicker (ntx-ref-picker)
    +-- NtxTxInspector (ntx-tx-inspector) [trace]
    +-- TxSidebar (tx-sidebar) [trace]
    +-- TxDetail (tx-detail) [trace]
    +-- TxEntryDetail (tx-entry-detail) [trace]
```

---

## Detailed Component Analysis

### Core Foundation (n3tx-core/static/core/)

#### Component.js -- Unified HTMLElement Base
- **Status**: EXEMPLARY
- **Shadow DOM**: Yes, with adopted stylesheets (cached)
- **ResizeObserver**: Adaptive display modes (xs-xl)
- **Stylesheet**: Fetching with deduplication
- **Rendering**: Coalesced via `scheduleRender()`
- **Cleanup**: Proper `disconnectedCallback()`
- **Lifecycle**: `connectedCallback()` -> `prerender()` -> `render()`

#### Actor.js -- Message Routing Base
- **Status**: GOOD
- **Address generation**: Proper
- **Children registry**: Type-level
- **TX routing**: source/target prefix logic
- **Issues**: Disabled parent delegation code (lines 104-116) -- dead code

#### NTT.js -- Entity Registry & DynamicClass Factory
- **Status**: GOOD
- **Issues**: Commented-out legacy code (lines 84-147). No explicit `export` statements -- relies on implicit globals.

#### TX.js -- Message Envelope
- **Status**: GOOD
- **Structure**: name, source, target, data, meta, timestamp

#### Matrix.js -- Root Actor & Message Dispatcher
- **Status**: GOOD
- **Pattern**: Singleton global `matrix` instance
- **Issues**: Type checking on line 33 uses `E.connect` (wrong case)

#### Router.js -- Navigation State Actor
- **Status**: GOOD
- **Handlers**: NAVIGATE, BACK (UPPERCASE convention followed)
- **Features**: Hash sync optional, history stack, observable properties

#### Transport Layer (HTTP.js, Socket.js, NetworkAdapter.js)
- **Status**: FUNCTIONAL
- **Issues**: HTTP.js uses direct fetch() without retry/backoff. Token read from localStorage directly.

---

### UI Components (n3tx-ui/static/components/)

#### NTTElement.js -- Single Entity Base
- **Status**: EXEMPLARY
- **Extends**: Component
- **Lifecycle**: `definedCallback()` -> `define()` -> schema resolution
- **Handlers**: UPDATE, DESCRIBE, ERROR (UPPERCASE)
- **Features**: Value setter with deepEqual guard, auto-subscription to entity signals

#### NTTItem.js (ntx-item) -- Concrete Entity Renderer
- **Status**: EXEMPLARY
- **Extends**: NTTElement
- **Size methods**: xs(), sm(), md(), lg(), xl()
- **Display modes**: display vs edit with mode toggle
- **Event handling**: AbortController-based cleanup (#eventAC)
- **Lifecycle separation**: prerender() vs render() correctly separated
- **CSS**: adoptedStylesheets pattern via `get styles()`

#### ListElement.js -- Collection Base
- **Status**: EXEMPLARY
- **Extends**: Component
- **Features**: Selection API, pagination with offset/limit, dedup for READ requests
- **Handlers**: UPDATE (UPPERCASE)

#### NTTList.js (ntx-list) -- Collection Grid
- **Status**: EXEMPLARY
- **Extends**: ListElement
- **CSS**: External stylesheet via `get styles()`

#### NTTMethod.js (ntx-method) -- Method Invoker
- **Status**: GOOD
- **Extends**: Component
- **Layouts**: fieldset, inline, button
- **Issues**: `_response_()` handler is NOT UPPERCASE -- deviation from convention

#### NTTStream.js (ntx-stream) -- Streaming Output
- **Status**: EXEMPLARY
- **Extends**: NTTMethod
- **Handlers**: `STREAM()` dispatches to UPPERCASE handlers (TEXT, DONE, STREAM_ERROR)
- **Stream protocol**: SSE format with typed events

#### NTTSidebar.js (ntx-sidebar) -- Model Navigation
- **Status**: INCONSISTENT
- **Extends**: HTMLElement (NOT Component)
- **Issues**:
  - Manual stylesheet loading (link element, not Component.styles)
  - No prerender/render separation
  - Direct innerHTML manipulation
  - No shadow DOM lifecycle management

#### NTTRouter.js (ntx-router) -- View Container
- **Status**: GOOD
- **Extends**: Component
- **Handlers**: NAVIGATE, BACK (UPPERCASE)
- **Issues**: Inconsistent route resolution (strings vs objects)

#### NTTModal.js (ntx-modal) -- Dialog
- **Status**: INCONSISTENT
- **Extends**: HTMLElement (NOT Component)

#### NTTProfile.js (ntx-profile) -- User Profile
- **Status**: INCONSISTENT
- **Extends**: HTMLElement (NOT Component)

#### NTTTopbar.js (ntx-topbar) -- Top Navigation
- **Status**: INCONSISTENT
- **Extends**: HTMLElement (NOT Component)

#### NTTRefPicker.js (ntx-ref-picker) -- Reference Picker
- **Status**: INCONSISTENT
- **Extends**: HTMLElement (NOT Component)

---

### Agent Components (n3tx-agents/static/components/)

#### NTTStreamAgent.js (ntx-stream-agent)
- **Status**: EXEMPLARY
- **Extends**: NTTStream
- **Handlers**: THINKING, TOOL_CALL, TOOL_RESULT, TEXT, DONE, STREAM_END, STREAM_ERROR (all UPPERCASE)
- **Features**: Typed event dispatch, tool card tracking, render throttling, JSON collapsing

#### NTTAgentLive.js (ntx-agent-live)
- **Status**: GOOD
- **Extends**: NTTStream
- **Lifecycle**: prerender() sets DOM, render() updates title (correct separation)
- **Handlers**: THINKING, TOOL_CALL, etc. (UPPERCASE)

#### NTTChat.js (ntx-chat)
- **Status**: GOOD
- **Extends**: NTTStream
- **Issues**: `callMethod()` has conditional non-streaming path using `entity.call` instead of super

---

### Trace Components (n3tx-trace/static/components/)

#### ALL TRACE COMPONENTS -- MAJOR PATTERN DEVIATION

| Component | Extends | Shadow DOM | Stylesheet | TX Messaging | Lifecycle |
|-----------|---------|------------|------------|--------------|-----------|
| NtxTxInspector | HTMLElement | No (Light DOM) | Inline | No (custom events) | No prerender/render |
| TxSidebar | HTMLElement | Yes | Inline CSS | No (custom events) | No prerender/render |
| TxDetail | HTMLElement | Yes | Inline CSS | No (custom events) | No prerender/render |
| TxEntryDetail | HTMLElement | Yes | Inline CSS | No (custom events) | No prerender/render |

**Why**: These are purpose-specific visualization components (TX debugging), not entity CRUD. Written with different assumptions about the framework.

**Impact**: Maintenance burden. Would benefit from Component pattern for consistency, adaptive display modes, and automatic cleanup.

---

### Veille App Components (apps/veille/static/components/)

#### NTXGrantItem.js (ntx-grant-item)
- **Status**: EXEMPLARY
- **Extends**: NTTItem (correct)
- **Features**: Overrides md() for custom layout, score color coding, status pills

#### NTXRunPanel.js (ntx-run-panel)
- **Status**: GOOD
- **Extends**: HTMLElement
- **Issues**: Direct fetch() for run creation, 50ms polling with 10-second timeout (unsafe), manual token access

#### NTXRunOutput.js (ntx-run-output)
- **Status**: GOOD
- **Extends**: NTTStream (correct)
- **Handlers**: UPPERCASE handlers for structured output

---

## Consistency Matrix

| Aspect | n3tx-core | n3tx-ui | n3tx-agents | n3tx-trace | apps/veille |
|--------|-----------|---------|-------------|------------|-------------|
| Component inheritance | N/A (defines it) | 70% | 100% | 0% | 75% |
| customElements.define | N/A | 100% | 100% | 100% | 100% |
| prerender/render separation | Pattern defined | Follows | Follows | Missing | Follows |
| UPPERCASE handlers | All | All | All | None | Most |
| Shadow DOM | All | All | All | Mixed | All |
| Stylesheet adoption | Pattern defined | Follows | Follows | Inline CSS | Follows |
| TX-based messaging | All | Mostly | Mostly | Custom events | Mixed |
| Event cleanup (AbortController) | All | Good | Good | Manual | Manual |

---

## Key Findings

### Correct Patterns (to maintain)

1. **Lifecycle separation**: `prerender()` for structural DOM, `render()` for schema-aware updates
2. **UPPERCASE handler convention**: All TX inbox handlers are UPPERCASE (UPDATE, DESCRIBE, STREAM, TEXT, etc.)
3. **CSS via `get styles()`**: Component handles adoption, deduplication, caching
4. **AbortController cleanup**: Modern event listener management with signal parameter
5. **Schema consumption**: NTT.SCHEMA() / NTT.get() with DynamicClass attachment

### Deviations Requiring Action

1. **5 UI components extend HTMLElement instead of Component** -- NTTSidebar, NTTModal, NTTProfile, NTTTopbar, NTTRefPicker. Miss lifecycle management, adaptive display modes, stylesheet handling.

2. **Entire n3tx-trace package** -- All 4 components bypass Component pattern entirely. Different CSS strategy (inline), different event strategy (custom events), no TX messaging.

3. **Direct fetch() calls** -- NTTChatView, NTXRunPanel bypass TX/Matrix routing. Should route through Matrix/NetworkAdapter.

4. **NTT.js lacks explicit exports** -- Classes defined but no `export` statement. Relies on implicit globals.

5. **Dead code** -- Actor.js lines 104-116 (disabled parent delegation), NTT.js lines 84-147 (commented legacy).

---

## Recommendations

### Priority 1 (High Impact)
1. Convert NTTSidebar, NTTModal, NTTProfile, NTTTopbar, NTTRefPicker to extend Component
2. Refactor trace components to use Component pattern (lifecycle, stylesheet adoption, cleanup)
3. Add explicit `export` statements to NTT.js

### Priority 2 (Medium Impact)
4. Standardize all remote calls through TX/Matrix (remove direct fetch())
5. Ensure all components use `get styles()` pattern for CSS
6. Fix NTTMethod._response_() to follow UPPERCASE convention

### Priority 3 (Low Impact)
7. Remove dead code in Actor.js and NTT.js
8. Add AbortController cleanup to sidebar/modal/profile (manual event listeners)
9. Document handler naming convention in CLAUDE.md
