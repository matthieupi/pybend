# Component lifecycle and extension

[Frontend entry guide](../../../docs/frontend/ARCHITECTURE.md) ·
[Tag and routing reference](../../../docs/frontend/COMPONENTS.md)

## Choose a base

```text
Component (core: HTMLElement + actor bridge + schema + shadow styles)
  +-- NTTElement (entity data, subscriptions, save)
  |     +-- NTTItem (forms, actions, adaptive display)
  |           +-- NTTRow / NTTUser / app renderers
  +-- ListElement (collection data, pagination, selection)
  |     +-- NTTList / NTTTable / app collections
  +-- NTTMethod (method inputs and invocation)
  |     +-- NTTStream (stream event handling)
  +-- NTTRouter (view mounting)
```

`Component`, `NTTElement`, and `ListElement` are base classes, not registered
tags. Standalone elements such as topbar, sidebar, profile, modal and reference
picker do not all share this lifecycle. Agent-specific components belong to
[n3tx-agents](../../n3tx-agents/README.md).

## Lifecycle

| Hook/state | Actual responsibility |
|---|---|
| Constructor | Shadow root, actor registration, default data and stylesheet adoption |
| `connectedCallback()` | Starts ResizeObserver and calls `prerender()`; can run again on reconnect |
| `prerender()` | Optional structural DOM before schema/data; make it idempotent |
| `define(proto)` / `definedCallback()` | Schema class ready, not necessarily records ready |
| `DESCRIBE({proto,data})` | Entity schema/value delivery and signal subscription |
| `value` setter on NTTElement | Tries `update(prev,next)`; schedules render when it returns false |
| `scheduleRender()` | Coalesces via animation frame and waits for pending stylesheet adoption |
| `render()` | Schema-aware presentation; may run repeatedly |
| `disconnectedCallback()` | Base observer/subscription cleanup; call `super` in overrides |

Preserve structural DOM when it contains live children, stream output, or input
state. This is an implementation responsibility, not a universal automatic
guarantee: `NTTItem.render()` replaces its card markup. Do not use that strategy
for a persistent chat shell. Do not call `Actor.subclass()` again on component
subclasses; the bridge is established by `Component`.

### Full DOM control

Save as application `static/components/issue-summary.js`, import it in the shell,
then use `<issue-summary ref="Issue/1"></issue-summary>` for an existing entity.
This read-only example keeps native fetching/subscriptions and inserts data as text.

```javascript
import { NTTElement } from '/components/NTTElement.js';

class IssueSummary extends NTTElement {
  prerender() {
    if (this.shadowRoot.querySelector('h2')) return;
    const title = document.createElement('h2');
    title.textContent = 'Loading issue...';
    this.shadowRoot.append(title);
  }

  render() {
    this.prerender();
    this.shadowRoot.querySelector('h2').textContent =
      this.error || this.value?.title || 'Untitled issue';
    this._rendered = true;
  }
}
customElements.define('issue-summary', IssueSummary);
```

### Custom item renderer

Prefer extending `NTTItem` when only display changes. This module keeps the native
edit form, validation, save and action wiring. It uses a trusted static template
and fills the application value through `textContent` after mounting.

```javascript
// Application static/components/issue-card.js
import { NTTItem } from '/components/ntx-item.js';

class IssueCard extends NTTItem {
  md() {
    return '<h2 class="issue-title"></h2><button class="edit-btn">Edit</button>';
  }
  md_mounted() {
    const title = this.shadowRoot.querySelector('.issue-title');
    if (title) title.textContent = this.value?.title || 'Untitled issue';
  }
  lg_mounted() { this.md_mounted(); }
  xl_mounted() { this.md_mounted(); }
  update(prev, next) {
    // The inherited patcher assumes the built-in data-value DOM structure.
    return false;
  }
}
customElements.define('issue-card', IssueCard);
```

Import `/components/issue-card.js` in the app shell, then choose it explicitly
with `item-tag="issue-card"` or declare model renderer hints:

```python
# Inside the application's Issue model; import n3tx_ui before defining it.
__ui__ = {'renderer': {'item': 'issue-card', 'detail': 'issue-card'}}
```

The custom display above intentionally shows only a title and edit control, not
all method/delete controls. The click is still permission-checked by the base
edit handler; a production custom surface should also hide unavailable controls.
Use `permissions.canAction(this.schema.access, 'update', this.value)` for that
presentation check. Backend enforcement is still required.

`usesCustomEditLayout` defaults to false: editing falls back to the base
Formidable form even when size methods are overridden. Return true only when
you implement the editor and its input/validation behavior. Post-render hooks
are named for the active size (`md_mounted`, etc.). For custom listeners, clean up
on re-render/disconnect, for example with your own AbortController.

## Collections

`ListElement` provides data lifecycle, not a default grid. `NTTList` owns the
header/count, create modal, load-more control, DOM reconciliation and packed grid.
Extend `NTTList` to retain those features. A direct `ListElement` subclass must
implement rendering and any pagination affordance it wants to expose.

| Surface | Behavior |
|---|---|
| `definedCallback()` | Subscribes to class UPDATE; first READ uses limit 20, offset 0 and UI population depth (default 1) |
| `loadMore()` | Increments offset by 20 and requests another page |
| `proto._paginationMeta` | Last paginated response metadata |
| `value` | Array of cached entity addresses, not raw records |
| `createChild(addr)` | Stamps a template or resolved tag with entity reference and select target |
| `select`, `deselect`, `toggle`, `clearSelection` | Local Set-based selection |
| `SELECT(data,tx)` | Toggles selection, forwards NAVIGATE when `router` is set |

The template path takes precedence and retains the template's own display attrs:

```html
<!-- Import issue-card.js and ntx-list.js first. -->
<ntx-list model="Issue" allow-create>
  <template item-template>
    <issue-card display="md"></issue-card>
  </template>
</ntx-list>
```

Without a template, `createChild()` calls `this.childTag`; the base getter checks
`item-tag`, then `schema.ui.renderer.item`, then `ntx-item`. A subclass overriding
that getter owns its priority policy; preserve `super.childTag` if you want the
attribute/schema behavior. Do not assume an attribute overrides every custom getter.

Default child cascade: `xl -> md`, `lg/md -> sm`, `sm/xs -> xs`, `row -> row`.
`item-display` overrides it. Wide default lists pack `md` cards using measured grid
row spans while preserving DOM order; compact/sidebar lists do not use that layout.

## Adaptive display and styles

| Size | Alias | Minimum width |
|---|---|---:|
| xs | pill | 0 |
| sm | list-item | 200 |
| md | card | 400 |
| lg | detail | 600 |
| xl | page | 800 |
| row | row | Explicit table mode, not auto-selected |

`display="md"` forces a size; `display="auto"` restores width-based selection.
Override `displayBreakpoints` or `displayModeChanged(oldMode,newMode)` only when
needed. Default `lg()`/`xl()` delegate to `md()`; they do not reveal hidden fields.
Use the [styles getter](styling.md#shadow-dom-styles) for component CSS; there is
no `$styles` node to reattach in the constructable-stylesheet path.

## Methods and streams

`NTTMethod` resolves `schema.methods[method]` and generates input fields. Layouts
are `fieldset`, `inline`, and `button`; optional/defaulted fields use a disclosure,
and zero-required-parameter methods can show a primary action without a large form.
`show-label` exposes text for button layout. `ui.attach_to` positions a method
after a field; it does not mutate that field.

```html
<!-- Requires an existing model method marked stream=True and its parameter schema. -->
<ntx-stream model="Issue" uuid="1" method="generate" show-output></ntx-stream>
```

Import `/components/ntx-stream.js`. Plain output is opt-in via `show-output`.
`NTTStream` sends a TX with `meta.stream`, routes replies to `STREAM(data,tx)`,
and dispatches typed payload names to uppercase handlers such as `TEXT(data)`.
Application `DONE` payloads and transport `STREAM_END` are distinct.

`cancel()` suppresses subsequent client chunks and sends `STREAM_CANCEL`;
disconnect calls it. The current adapter does not retain an SSE abort handle for
this path, and the cancel message is not proof that backend work stopped. See
[transport limits](../../../docs/frontend/TRANSPORT.md#streaming).

## Source and tests

[Component](../../n3tx-core/src/n3tx_core/static/core/Component.js),
[NTTElement](../src/n3tx_ui/static/components/NTTElement.js),
[ListElement](../src/n3tx_ui/static/components/ListElement.js),
[NTTItem](../src/n3tx_ui/static/components/ntx-item.js),
[NTTStream](../src/n3tx_ui/static/components/ntx-stream.js).
Tests live in [frontend component tests](../../../tests/frontend/tests/components/)
and [integration tests](../../../tests/frontend/tests/integration/).
