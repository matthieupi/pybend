# Components

> Part of [n3tx-ui](../README.md)

## What This Covers

The component class hierarchy, message handlers, lifecycle hooks, and extension points. Covers `NTTElement`, `ListElement`, and their concrete subclasses. Does not cover the form generator (see [formidable.md](formidable.md)) or the widget system (see [widgets.md](widgets.md)).

## Architecture

```
Component (n3tx-core: shadow DOM, addr, ref, model, proto, define(), scheduleRender())
  |
  +-- NTTElement (NTTElement.js)          -- Single entity base
  |     Message handlers: UPDATE, DESCRIBE, READ, ERROR
  |     Methods: save(), update(prev, next), onValidationError(errors)
  |     Auto-renders on value change when schema is set
  |     |
  |     +-- NTTItem (ntx-item.js)         -- <ntx-item>
  |     |     Size methods: xs(), sm(), md(), lg(), xl(), row()
  |     |     Modes: display / edit (toggleMode, cancelEdit)
  |     |     Validation: showFieldErrors(), client-side via Formidable
  |     |     Event binding: edit, delete, input change, card click -> SELECT
  |     |     |
  |     |     +-- NTTRow (ntx-row.js)     -- <ntx-row>
  |     |     |     Forces display="row", inline edit with collectInputValues
  |     |     |
  |     |     +-- NTTUser (ntx-user.js)   -- <ntx-user>
  |     |           Overrides xs/sm with avatar rendering
  |     |
  |     +-- (custom subclasses extend NTTElement directly for full control)
  |
  +-- ListElement (ListElement.js)        -- Collection base
  |     Message handlers: UPDATE, SELECT
  |     Methods: loadMore(), createChild(addr)
  |     Selection API: select/deselect/toggle/clearSelection
  |     Pagination: #pageSize=20, #offset tracking
  |     |
  |     +-- NTTList (ntx-list.js)         -- <ntx-list>
  |     |     Default grid renderer, modal create flow, packed card layout
  |     |
  |     +-- NTTTable (ntx-table.js)       -- <ntx-table>
  |           Table with header sort, inline create row, stamps ntx-row
  |
  +-- NTTMethod (ntx-method.js)           -- <ntx-method>
|     Layouts: fieldset (default), inline, button
|     Loads method schema, renders input form, calls entity method
|     Required params render by default; optional/defaulted params hide behind
|     a local disclosure, and zero-visible-param methods collapse to a labeled
|     primary action button with expandable options
|     Retains a small static style contract (`baseStyles`) for source-level overflow assertions
|     Button layout renders `.method-btn`; add `show-label` when a button-layout method should expose visible label text instead of icon-only chrome. Inline layout may render `textarea` when the schema/widget requests it
  |     Icons: shared `ui.icon` tokens rendered through <ntx-icon>
  |     |
  |     +-- NTTStream (ntx-stream.js)     -- <ntx-stream>
  |           Overrides callMethod() for streaming via TX meta.stream
  |           Progressive output rendering with cursor animation
  |
  +-- NTTRouter (ntx-router.js)           -- <ntx-router>
        View container. Slot = home. NAVIGATE pushes views by default, BACK pops,
        and reset navigation clears history so base pages render without router chrome.
        Resolves component tags from schema ui.renderer hints.
```

Standalone (no Component base): `NTTModal`, `NTTRefPicker`, `NTTTopbar`, `NTTSidebar`, `NTTProfile`.
`ntx-favorites` and `ntx-logs` are example-local components under `examples/*/static/components`, not packaged `n3tx-ui` components.

When an app shell uses `ntx-topbar`'s built-in `#@profile` menu entry, the page
must import `./components/ntx-profile.js` during bootstrap so the router can
mount a registered `<ntx-profile>` element instead of an empty unknown tag.

`NTTListField` (`ntx-list-field.js`) is the dedicated array-field surface used by Formidable. It owns scalar-array edit rows, staged `$ref` link add/remove behavior, and `field-change` events back to the parent item.

`NTTSidebar` supports `brand`, `subtitle`, and optional `brand-logo` attributes so app shells can place a custom mark in the sidebar brand section without forking the component.
Template children can also declare `sidebar-label="..."` to override the nav
label shown in the sidebar without changing the mounted view or route params.
Plain `<a>` sidebar children can declare `icon="..."` to render a per-link
`<ntx-icon>` token while links without `icon` keep the generic link icon.
Sidebar model navigation emits explicit frontend view routes (`#Model/@` or
`#Model/@table` for table templates), and compact dropdown record links use
member default view routes such as `#Model/5/@`. Legacy `#Model` and
`#Model/5` routes remain selected-state compatible during the migration window.

`NTTIcon` (`ntx-icon.js`) is the shared icon surface used by method buttons,
sidebar avatars, and collection headers. It resolves icon tokens through
`static/utils/icon-resolver.js` and supports inline SVG lookup entries,
emoji, image URLs/paths, and custom lookup keys registered at runtime with
`registerIcons({...})`. Built-in lookup keys include common app navigation
tokens such as `dashboard`, `upload`, and `user`.

**Agent components** (n3tx-agents):

```
NTTList (ntx-list.js)
  |
  +-- NtxAgents (ntx-agents.js)            -- <ntx-agents> hybrid AgentActor list
        Renders stored AgentActor rows plus app-provided built-in workflow
        launchers from window.NTX_AGENT_CATALOGS[catalog].
```

```
NTTItem (ntx-item.js)
  |
  +-- NtxAgent (ntx-agent.js)              -- <ntx-agent> rich AgentActor entity card
        Uses AgentActor schema renderer hints for list/detail routes and embeds
        <ntx-agent-live> for activity in display mode.
```

```
NTTStream (ntx-stream.js)                -- TX-based streaming with cancel()
  |
  +-- NTTStreamAgent (ntx-stream-agent.js)  -- Rich agent output (entries, markdown, tool cards)
  |     Handlers: THINKING, TOOL_CALL, TOOL_RESULT, TEXT, DONE, STREAM_END, STREAM_ERROR
  |
  +-- NTTAgentLive (ntx-agent-live.js)      -- <ntx-agent-live> standalone monitor
  |     prerender(): textarea + log + footer
  |     Handlers: THINKING, TOOL_CALL, TOOL_RESULT, TEXT, DONE, STREAM_END, STREAM_ERROR
  |
  +-- NTTChat (ntx-chat.js)                 -- <ntx-chat> floating chat panel
        prerender(): floating tab + slide-up panel
        Handlers: THINKING, TOOL_CALL, TOOL_RESULT, TEXT, DONE, STREAM_END, STREAM_ERROR
```

**UPPERCASE convention**: All methods that handle TX messages are UPPERCASE — this mirrors the backend actor handler pattern and visually separates inbox handlers from internal component logic (lowercase/camelCase).

## Interface

### NTTElement (single entity base)

```javascript
class NTTElement extends Component {
    // State
    $schema;          // Schema name for CONNECT flow
    error;            // Persistent error message (string|null)

    // Value setter triggers auto-render when schema is available.
    // deepEqual guard prevents infinite loops from signal re-fires.
    set value(data);

    // Message handlers (called by Actor inbox dispatch)
    UPDATE(data);     // Receives entity data push. Requires data.$schema.
    DESCRIBE(data);   // Receives {proto, data}. Subscribes to entity signal.
    READ(data);       // Receives data from URL fetch or hydrated relationship rendering.
    ERROR(event);     // Handles errors. Extracts validation errors from 422.

    // Override points
    update(prev, next);              // Surgical DOM patch. Return false -> full render().
    onValidationError(errors);       // Hook for structured validation errors.
    render();                        // Override for custom rendering.

    // Actions
    save();           // Sends UPDATE TX to entity ref.
}
```

### ListElement (collection base)

```javascript
class ListElement extends Component {
    // Selection
    get selected();               // Set of selected addresses
    select(addr); deselect(addr); toggle(addr); clearSelection();

    // Data
    definedCallback();            // Called when proto arrives. Triggers READ.
    loadMore();                   // Paginated fetch: offset += pageSize.

    // Message handlers
    UPDATE(data);                 // Receives entity address array.
    SELECT(data, tx);             // Toggle selection, forward NAVIGATE to router.

    // Override points
    get childTag();               // Tag for stamped children. Default: 'ntx-item'.
    get childDisplay();           // Display mode for children. Cascades from parent.
    createChild(addr);            // Create child element. Checks <template item-template>.
    update(prev, next);           // Returns false by default → full render fallback.
    render();                     // Override for custom collection rendering.
}
```

`ListElement` is the collection lifecycle base. The default list UI now lives in
`NTTList`, mirroring the `NTTElement` → `NTTItem` split on the single-entity side.

### NTTItem key attributes

| Attribute | Effect |
|-----------|--------|
| `display` | Size mode: xs, sm, md, lg, xl, row |
| `ref` | Entity address (href URL) |
| `model` | Model class name |
| `select-target` | Actor address to send SELECT TX to |
| `create-mode` | Present = create mode (no existing data) |

`NTTItem` subclasses now inherit the default Formidable edit form automatically. If a custom component overrides `md()`/`lg()`/`xl()` only for display, edit mode still falls back to the base `NTTItem` form. Components that own a true custom editor must opt out with `get usesCustomEditLayout() { return true; }` and render their own edit UI.

### ListElement/NTTList key attributes

| Attribute | Effect |
|-----------|--------|
| `model` | Model class name to list |
| `display` | List display size (cascades to children) |
| `router` | Router actor address for SELECT navigation |
| `item-tag` | Override child tag (default from schema) |
| `item-display` | Override child display mode |
| `headless` | Hide the `ntx-list` header (title + count) |
| `allow-create` | Show the `ntx-list` create button (permission-gated) |

List and table headers render `schema.ui.icon` beside the collection title when
present. `schema.ui.description` adds intro copy under that title, and
`schema.ui.create_label` switches the default `+` create affordance to a labeled
header button. Sidebar model avatars do the same and fall back to initials when
no icon is declared.

Wide `ntx-list` instances whose children resolve to `display="md"` now use a
packed grid: the DOM order stays unchanged, but card hosts get measured and
assigned `grid-row-end` spans so shorter cards no longer reserve the tallest
row height. Compact/sidebar lists (`sm`/`xs` children or `sidebar-dropdown`)
stay on the old single-row flow.

## Usage Patterns

### Custom entity component

Extend NTTElement for full control over rendering:

```javascript
import { NTTElement } from '../components/NTTElement.js';

class ProductCard extends NTTElement {
    get styles() { return new URL('./product-card.css', import.meta.url).href; }

    render() {
        if (!this.schema || !this.value) return;
        this.shadowRoot.innerHTML = `
            <h2>${this.value.name}</h2>
            <p>$${this.value.price}</p>
        `;
        this._rendered = true;
    }
}
customElements.define('product-card', ProductCard);
```

### Templated list children

Use a `<template>` to customize what ListElement stamps per item:

```html
<ntx-list model="Product">
    <template item-template>
        <product-card></product-card>
    </template>
</ntx-list>
```

### Sidebar with route templates

Declarative route templates control what the sidebar navigates to:

```html
<ntx-sidebar router="main">
    <ntx-table model="Grant" allow-create></ntx-table>
    <ntx-agents model="AgentActor" sidebar-label="Agents" catalog="veille"></ntx-agents>
    <ntx-list model="Source"></ntx-list>
    <ntx-theme-button slot="footer"></ntx-theme-button>
</ntx-sidebar>
```

When a sidebar has both `brand` and `router`, clicking the rendered brand copy
returns the bound router to its home slot by dispatching a reset navigation with
the empty home route (`buildRoute({ type: 'home' })`).

Expanded model groups now mount the declared route-template tag for that model
when it is a list-style custom surface. `ntx-table` route templates still fall
back to a headless `ntx-list` for the compact dropdown shell. Plain dropdown
lists still force `item-display="sm"` and use the
sidebar-only `ntx-sidebar-link-item` renderer. That renderer outputs a real
internal `<a href="#Model/id/@">...</a>` for each record so dropdown entries
target member default view routes instead of compact pills. Legacy `#Model/id`
routes remain supported by the router. The full label is also
exposed through a lightweight delayed hover/focus tooltip when the row text is
actually truncated. The trigger hitbox extends slightly beyond the label
itself, the delay is tuned to about `220ms`, dropdown record labels
intentionally render a step smaller than top-level model rows, the rows sit
flush with no inter-item gap, use slightly roomier vertical padding, align to
the model-name text column, and use the full remaining row width before
ellipsis appears, and model counts now read as plain inline metadata rather
than badge chrome. The renderer carries its own stylesheet so sidebar-only row
chrome stays out of the shared `ntx-item.css` shell.

Custom list tags such as `<ntx-agents>` receive the model name, sidebar router,
`headless`, and `sidebar-dropdown` attrs so they can implement compact hybrid
dropdown views without rewriting the sidebar.

### Manual shell theme controls

Shell pages place the reusable theme control explicitly:

```html
<ntx-topbar>
    <ntx-theme-button slot="user-menu"></ntx-theme-button>
</ntx-topbar>

<ntx-sidebar router="main">
    <ntx-list model="Product"></ntx-list>
    <ntx-theme-button slot="footer"></ntx-theme-button>
</ntx-sidebar>
```

`ntx-topbar` exposes `slot="user-menu"` inside the authenticated dropdown, and `ntx-sidebar` exposes `slot="footer"` at the bottom of the shell. Neither component auto-renders theme UI. Sidebar labels now render in uppercase, footer actions stretch to the full available width by default, and route-matched entries receive a persistent selected state separate from hover and accordion expansion. The selected accent now reads as a full-height left rail, while expanded/selected rows no longer rely on an accent border around the rest of the card.

Additional theme-control rules:

- multiple `<ntx-theme-button>` instances stay synchronized through the global `theme-change` event
- logged-out pages should not render the button; they only honor the persisted theme
- the button cycles through `window.NTX_THEME_CONFIG.themes` order rather than hardcoded dark/light branching

## Gotchas

- **NTTElement value setter has a deepEqual guard** that skips re-render if the new value is semantically identical to the previous one. This prevents infinite loops from signal subscriptions but means the initial set (from constructor default `{}`) must bypass the guard. The guard only activates after `_rendered` is true.

- **Custom `NTTItem` subclasses get edit fallback by default.** In edit mode, `NTTItem.render()` uses the base Formidable form unless the subclass opts into custom edit layout with `usesCustomEditLayout`. This prevents display-only custom cards from swallowing edit mode.
- **Custom item visuals belong with the subclass, not the framework shell.** If an app defines `ntx-grant-item` or similar, add any model-specific CSS through the subclass `styles` getter so `ntx-item.css` stays generic.
- **Detail title uppercasing is display-only.** Shared item and grant titles only uppercase in `lg`/`xl` detail views via CSS; `xs`/`sm`/`md` preserve the underlying `name` and `title` casing.
- **Default detail cards are borderless and shadow-only on hover.** The shared `ntx-item.css` `md`/`lg`/`xl` shells use no visible outer border and do not translate upward on hover; visual emphasis comes from the shadow ramp.
- **NTTItem.sm() delegates to md() in edit mode.** If you override sm() but not md(), editing in sm context will use the default md() form. Override md() only when you also intend to own edit rendering.

- **ListElement.definedCallback() deduplicates READ calls.** If another list instance for the same model already triggered a READ, `proto._listReadPending` is true and the second list skips the request. Both lists get notified when the READ completes via the UPDATE observable.

- **AbortController for event listeners.** NTTItem and NTTRow create a new AbortController per render and abort the previous one. This prevents listener accumulation. If you extend these classes and add custom listeners, use the same pattern with `{signal}`.

- **NTTStream binds a dynamic handler** named after the method (e.g., `this.GENERATE = (data, tx) => ...`). If the method name changes, the old handler is unbound. The handler dispatches based on `tx.meta`: stream_end -> onDone, error -> onError, else -> onChunk. For agent-style streaming with typed events (text, tool_call, done, etc.), extend `NTTStreamAgent` instead — it unwraps STREAM envelopes and dispatches to UPPERCASE handler methods (THINKING, TOOL_CALL, TEXT, DONE, etc.).

- **Router URL sync is opt-out, not opt-in.** `Router()` and `<ntx-router>` synchronize with `window.location.hash` by default so navigation updates the browser URL without extra configuration. Initial deep links do not create fake back history, returning to root through browser history clears the in-app back state, and `<ntx-router>` hides its chrome when there is no back history. Sidebar-driven base-page navigation now sends reset navigation so the target route becomes the new root instead of stacking on the prior page.

- **NTTModal locks body scroll** (`document.body.style.overflow = 'hidden'`) while open and restores on close via the `modal-close` event listener.
