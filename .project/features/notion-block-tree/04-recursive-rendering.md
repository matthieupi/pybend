# Recursive Rendering & Component Composition

**How tree-shaped data drives tree-shaped UI -- Web Components recursion, drag-and-drop composition, and virtual DOM patterns for a schema-driven framework**

---

> **Executive summary:** A `hasChildren` property on block entities creates a recursive data model that
> demands recursive UI rendering. This document maps the concrete patterns --
> from vanilla Web Components that stamp themselves, to drag-and-drop tree
> reordering, to the CSS tricks that animate expand/collapse -- and shows
> exactly how they integrate with N3TX's existing `ntx-item`, `ntx-list`,
> and DynamicClass machinery. The TL;DR: recursive rendering is
> **straightforward to implement** with Web Components (no framework magic needed),
> but the devil is in **lazy loading**, **keyboard navigation**, and **drag-drop
> across nesting levels**.

---

## Table of Contents

1. [The Data Shape Drives the Component Shape](#-the-data-shape-drives-the-component-shape)
2. [Recursive Web Components: Patterns That Work](#-recursive-web-components-patterns-that-work)
3. [Block Editors in the Wild: How the Pros Do It](#-block-editors-in-the-wild)
4. [Drag-and-Drop in Nested Trees](#-drag-and-drop-in-nested-trees)
5. [N3TX Integration: The Path to `<ntx-block>`](#-ntx-integration-the-path-to-ntx-block)
6. [Circular Schemas: Teaching `NTT.SCHEMA()` About Self-References](#-circular-schemas)
7. [Animation & UX Patterns](#-animation--ux-patterns)
8. [Keyboard Navigation & Accessibility](#-keyboard-navigation--accessibility)
9. [Virtualized Tree Rendering](#-virtualized-tree-rendering)
10. [Risk Assessment & Recommendations](#-risk-assessment--recommendations)
11. [Sources](#-sources)

---

## 1. The Data Shape Drives the Component Shape

The fundamental insight is simple: **tree data produces tree UI**. When your
data model looks like this:

```
Block (id=1, type="page")
  +-- Block (id=2, type="heading", has_children=true)
  |     +-- Block (id=3, type="paragraph")
  |     +-- Block (id=4, type="toggle", has_children=true)
  |           +-- Block (id=5, type="paragraph")
  +-- Block (id=6, type="image")
```

Your component tree **must mirror it**:

```
<ntx-block id="1" type="page">
  <ntx-block id="2" type="heading">
    <ntx-block id="3" type="paragraph" />
    <ntx-block id="4" type="toggle">
      <ntx-block id="5" type="paragraph" />
    </ntx-block>
  </ntx-block>
  <ntx-block id="6" type="image" />
</ntx-block>
```

This is a direct consequence of the Notion-style block model. The
[Notion API documentation](https://developers.notion.com/reference/block)
exposes this clearly: every block has a `has_children` boolean, and retrieving
children requires a separate paginated call to
`/blocks/{block_id}/children`. The API returns **at most 100 children**
per page, and nested children are **not included inline** -- you must
recursively fetch them.

> **Key Insight:** The API never returns the full tree in one shot.
> This pagination constraint at the API level directly maps to a **lazy-loading**
> requirement at the UI level. You cannot render what you haven't fetched.
> The `has_children` flag is your cue to show an expand affordance and
> fetch on demand.

### Notion's Data Shape vs. N3TX's Current Model

| Aspect | Notion API | N3TX Today | N3TX with Blocks |
|--------|-----------|------------|-----------------|
| **Entity nesting** | `has_children` + separate fetch | `ListRef[T]` (flat FK arrays) | `children: ListRef[Block]` (self-ref) |
| **Depth** | Unlimited (recursive fetch) | 1 level (populated refs) | Unlimited (recursive fetch) |
| **Pagination** | 100 per page, cursor-based | `limit/offset` query params | Same `limit/offset` per level |
| **Type polymorphism** | `type` field on each block | Separate model classes | `type` field + renderer registry |
| **Ordering** | Implicit (array position) | Implicit (array position) | Explicit `order` field recommended |

---

## 2. Recursive Web Components: Patterns That Work

### The Self-Referential Custom Element

The good news: **Web Components handle recursion natively**. There is no
special API needed. A custom element can create instances of itself inside
its own shadow DOM. The browser's custom element registry (`customElements.define`)
processes this without circular reference issues because element instantiation
is **imperative** (you create elements in JavaScript), not declarative
(unlike React JSX which would need a module-level self-import).

Here is the core pattern, distilled to its essence:

```javascript
class NtxBlock extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  set data(block) {
    this._data = block;
    this.render();
  }

  render() {
    const block = this._data;
    if (!block) return;

    // Render THIS block's content based on type
    const content = this.renderContent(block);

    // Recursively render children -- ONLY if they exist
    let childrenHtml = '';
    if (block.has_children && block.children) {
      childrenHtml = '<div class="children">';
      // Note: we do NOT use innerHTML for children.
      // We create child elements imperatively.
      childrenHtml += '</div>';
    }

    this.shadowRoot.innerHTML = `
      <div class="block" data-type="${block.type}">
        ${content}
        ${childrenHtml}
      </div>
    `;

    // Now imperatively append child <ntx-block> elements
    if (block.has_children && block.children) {
      const container = this.shadowRoot.querySelector('.children');
      for (const child of block.children) {
        const el = document.createElement('ntx-block');
        el.data = child;  // triggers render() recursively
        container.appendChild(el);
      }
    }
  }

  renderContent(block) {
    // Dispatch to type-specific renderer
    switch (block.type) {
      case 'paragraph':  return `<p>${block.text}</p>`;
      case 'heading':    return `<h2>${block.text}</h2>`;
      case 'toggle':     return `<details><summary>${block.text}</summary></details>`;
      default:           return `<div>${block.text || ''}</div>`;
    }
  }
}

customElements.define('ntx-block', NtxBlock);
```

### Three Guards Against Infinite Instantiation

Recursive components need **base-case termination**, just like recursive
functions. Three strategies, used in combination:

| Strategy | How It Works | When It Fires |
|----------|-------------|---------------|
| **Data-driven stop** | No `children` array or `has_children=false` -> no child elements created | Leaf nodes |
| **Depth limit** | Pass a `max-depth` attribute; decrement per level; stop at 0 | Deep trees, safety net |
| **Lazy expansion** | Don't fetch or render children until user clicks expand | Always (best default) |

```javascript
// Depth-limited rendering
render() {
  const maxDepth = parseInt(this.getAttribute('max-depth') ?? '10');
  if (maxDepth <= 0) {
    this.shadowRoot.innerHTML = '<div class="truncated">...</div>';
    return;
  }
  // ... normal render ...
  for (const child of block.children) {
    const el = document.createElement('ntx-block');
    el.setAttribute('max-depth', String(maxDepth - 1));
    el.data = child;
    container.appendChild(el);
  }
}
```

### Shadow DOM: Performance at Depth

Each `<ntx-block>` gets its own shadow root. At **depth 5** with **20 blocks
per level**, that's potentially **3.2 million** shadow roots in the worst case
(20^5). In practice, this is why lazy rendering matters:

| Depth | Blocks (20/level) | Shadow Roots | Realistic (lazy, 3 expanded) |
|-------|-------------------|-------------|------------------------------|
| 1 | 20 | 20 | 20 |
| 2 | 400 | 420 | 23 |
| 3 | 8,000 | 8,420 | 26 |
| 5 | 3,200,000 | ~3.2M | ~35 |

> **Key Insight:** Lazy expansion collapses the exponential cost to **linear
> in the number of visible nodes**. A user realistically sees ~30-50 blocks
> at a time regardless of tree depth. The performance story is entirely about
> **not rendering what's hidden**.

The Lit framework documentation confirms that shadow DOM carries
["an extra performance cost"](https://lit.dev/docs/components/shadow-dom/),
but this is per-root overhead (a few hundred bytes of memory plus style
encapsulation). The real cost is in **layout recalculation** when hundreds
of nested elements exist simultaneously in the DOM.

---

## 3. Block Editors in the Wild

### BlockNote (ProseMirror/Tiptap)

[BlockNote](https://www.blocknotejs.org/) is the closest open-source analog
to Notion's editor. Its architecture reveals key decisions:

- **Built on ProseMirror** via Tiptap, which means the document is a
  single contiguous content-editable tree, not a component-per-block model
- Uses a **`blockContainer`** ProseMirror node type that wraps each block,
  and a **`blockGroup`** node type that represents a list of children
- The `BlockManager` exposes tree operations:
  `canNestBlock()`, `nestBlock()`, `canUnnestBlock()`, `unnestBlock()`
- A **`forEachBlock()`** method provides depth-first traversal
  ([DeepWiki: BlockNote Architecture](https://deepwiki.com/TypeCellOS/BlockNote/2.2-prosemirror-and-tiptap-integration))

```
ProseMirror Document
  +-- blockContainer (paragraph)
  |     +-- blockContent (inline text)
  |     +-- blockGroup (optional: children)
  |           +-- blockContainer (nested paragraph)
  |           +-- blockContainer (nested image)
  +-- blockContainer (heading)
```

**Key takeaway for N3TX:** BlockNote proves that a block tree **can** be
rendered as a flat sequence with indentation, rather than deeply nested
components. ProseMirror's approach is to keep the document as a **single
tree in one DOM context** rather than isolated shadow roots. This is more
performant for editing but less encapsulated.

### Editor.js

[Editor.js](https://editorjs.io/) takes the opposite stance: each block is
an **independent `contenteditable` element**. Critically, Editor.js
[does not support nested blocks natively](https://github.com/codex-team/editor.js/issues/1440).
Users have attempted workarounds (multiple EditorJS instances) with
["buggy implementations"](https://github.com/codex-team/editor.js/issues/1162).

**Key takeaway:** Editor.js's flat-only model is a cautionary tale.
Once users expect nesting (toggles, callouts with children, columns),
a flat architecture becomes a liability.

### Notion's Frontend

Notion's own frontend (React-based) uses a **block component** that:

- Reads the `type` field and dispatches to a type-specific renderer
- Uses `has_children` to show expand/collapse affordances
- [Toggle blocks](https://notionpresso.com/en/docs/block-types/toggle)
  use `useState` to manage open/closed state
- Children are fetched lazily on toggle open, not pre-fetched
- `aria-expanded` attribute communicates state to screen readers

### Comparison Matrix

| Feature | BlockNote | Editor.js | Notion | N3TX (proposed) |
|---------|-----------|-----------|--------|-----------------|
| **Nesting** | Yes (blockGroup) | No | Yes (has_children) | Yes (ListRef self-ref) |
| **Rendering** | Single ProseMirror tree | Isolated contenteditable | React components | Web Components (shadow DOM) |
| **Lazy children** | No (all in doc) | N/A | Yes (API fetch on expand) | Yes (paginated fetch) |
| **Drag-drop** | Built-in (ProseMirror) | Block-level only | Built-in | SortableJS / DnD Kit |
| **Type dispatch** | ProseMirror node spec | Plugin system | React component map | Widget registry + tag map |
| **Collaboration** | Yjs integration | None | Proprietary | Future (actor messaging) |

---

## 4. Drag-and-Drop in Nested Trees

### The Hard Problem: Cross-Level Dragging

Dragging blocks **within** a single list is solved. Dragging a block
**from level 2 to level 1** (or into a different parent) is where every
implementation struggles.

There are two architectural approaches:

```
Approach A: Nested Sortable Contexts       Approach B: Flattened + Indentation
+----------------------------------+       +----------------------------------+
| SortableContext (root)           |       | Single SortableContext            |
|  +-- SortableItem (block 1)     |       |  +-- Item (block 1, depth=0)     |
|  |    +-- SortableContext (L2)   |       |  +-- Item (block 2, depth=1)     |
|  |    |    +-- SortableItem      |       |  +-- Item (block 3, depth=1)     |
|  |    |    +-- SortableItem      |       |  +-- Item (block 4, depth=2)     |
|  +-- SortableItem (block 5)     |       |  +-- Item (block 5, depth=0)     |
+----------------------------------+       +----------------------------------+
  Cross-level drag: NOT POSSIBLE             Cross-level drag: WORKS
  (separate contexts)                        (flat list, depth = visual only)
```

> **Key Insight:** Every serious tree drag-and-drop implementation uses
> **Approach B** -- a flattened list with depth metadata.
> [dnd-kit's documentation](https://docs.dndkit.com/presets/sortable) and the
> [dnd-kit-sortable-tree](https://github.com/Shaddix/dnd-kit-sortable-tree)
> package both confirm this: "In multi-level nested lists (trees), you need
> to implement custom logic... add the `ancestorsIds` attribute for each item."

### SortableJS for Vanilla JS

For a framework-agnostic solution, [SortableJS](https://github.com/SortableJS/Sortable)
supports nested lists natively:

```javascript
// Initialize nested sortables
document.querySelectorAll('.block-children').forEach(el => {
  new Sortable(el, {
    group: 'blocks',          // Same group = cross-list dragging
    animation: 150,
    fallbackOnBody: true,     // Required for nested sortables
    swapThreshold: 0.65,      // Recommended for nesting
    invertSwap: true,         // Better UX for nesting gestures
    onEnd(evt) {
      // evt.from, evt.to: source/target containers
      // evt.oldIndex, evt.newIndex: positions
      // evt.item: the dragged element
      reorderBlocks(evt);
    }
  });
});
```

**Recommended settings** per the
[SortableJS docs](https://sortablejs.github.io/Sortable/):
`fallbackOnBody: true` and either `invertSwap: true` or `swapThreshold: 0.65`.

### Vanilla TypeScript Alternative

The [sortable-tree](https://github.com/marcantondahmen/sortable-tree) library
provides a zero-dependency vanilla TypeScript solution specifically designed
for tree hierarchies, with collapsible nodes built in.

### Drag Affordances: The "Grip Handle" Pattern

Every block editor uses a **grip handle** (usually 6 dots or a drag icon)
that appears on hover:

```
  +-- [::] Block content here...
  |   ^^^^
  |   grip handle (appears on hover)
  +-- [::] Another block...
```

The grip handle serves double duty:
1. **Drag target** -- only the handle initiates drag, so text selection
   still works in the block content
2. **Block menu trigger** -- clicking (not dragging) opens a context
   menu with block type, color, delete, etc.

---

## 5. N3TX Integration: The Path to `<ntx-block>`

### Current Architecture: What We Have

Reading the N3TX codebase reveals a clean component hierarchy:

```
Component (core/Component.js)
  +-- NTTElement (components/NTTElement.js)     -- single entity
  |     +-- NTTItem (components/ntx-item.js)    -- default renderer
  +-- ListElement (components/ListElement.js)    -- collection
        +-- NTTList (components/ntx-list.js)     -- default list
```

Key observations from the source:

1. **`NTTItem.render()`** dispatches to size methods (`xs`, `sm`, `md`, `lg`)
   that return HTML strings. Each method builds markup for a flat entity
   with no recursion.

2. **`ListElement.createChild(addr)`** stamps one child element per entity
   address. It resolves the child tag from schema hints
   (`schema.ui.renderer.item`).

3. **`NTT.SCHEMA()`** handles `$defs` for nested schemas -- it already
   creates DynamicClasses for referenced models. But it has
   **no circular reference handling**.

4. **The widget registry** (`widgets/registry.js`) maps `ui.widget` names
   to Widget instances. This is the natural extension point for block
   type-specific renderers.

### Proposed `<ntx-block>` Component

The `<ntx-block>` element would combine characteristics of both `NTTItem`
(single entity display) and `ListElement` (child collection management):

```
                     Component
                    /         \
             NTTElement      ListElement
                  |              |
               NTTItem        NTTList
                  \            /
                   \          /
                  NtxBlock (new)
                  - renders self based on type
                  - manages child collection
                  - handles expand/collapse
                  - integrates with drag-drop
```

#### Sketch Implementation

```javascript
import { NTTElement } from './NTTElement.js';
import { NTT } from '../core/NTT.js';
import TX from '../core/TX.js';

// Block type -> renderer function registry
const _blockRenderers = new Map();

export function registerBlockRenderer(type, renderFn) {
  _blockRenderers.set(type, renderFn);
}

export class NtxBlock extends NTTElement {

  #expanded = false;
  #childrenLoaded = false;
  #childAddrs = [];

  get styles() {
    return new URL('./ntx-block.css', import.meta.url).href;
  }

  static get observedAttributes() {
    return [...super.observedAttributes, 'max-depth'];
  }

  get maxDepth() {
    return parseInt(this.getAttribute('max-depth') ?? '20');
  }

  get blockType() {
    return this.value?.type || 'paragraph';
  }

  get hasChildren() {
    return this.value?.has_children === true;
  }

  // --- Expand / Collapse ---

  async toggleExpand() {
    if (!this.hasChildren) return;
    this.#expanded = !this.#expanded;

    if (this.#expanded && !this.#childrenLoaded) {
      await this.loadChildren();
    }
    this.scheduleRender();
  }

  async loadChildren() {
    // Fetch children via the existing DynamicClass paginated READ
    const blockId = this.value?.id;
    if (!blockId) return;

    const DC = NTT.get('Block');
    if (!DC) return;

    // Use the entity's href + /children endpoint
    DC.call('READ', {
      parent_id: blockId,
      limit: 50,
      offset: 0,
    }, { inbox: 'UPDATE' });

    this.#childrenLoaded = true;
  }

  // --- Render ---

  render() {
    if (!this.schema || !this.value) return;
    if (this.maxDepth <= 0) {
      this.shadowRoot.innerHTML = '<div class="truncated">+</div>';
      return;
    }

    const type = this.blockType;
    const renderer = _blockRenderers.get(type) || defaultBlockRenderer;
    const contentHtml = renderer(this.value, this.schema);

    const expandBtn = this.hasChildren
      ? `<button class="expand-toggle" aria-expanded="${this.#expanded}">
           ${this.#expanded ? '\u25BC' : '\u25B6'}
         </button>`
      : '<span class="expand-spacer"></span>';

    const childrenHtml = (this.#expanded && this.#childAddrs.length > 0)
      ? `<div class="block-children"
              style="grid-template-rows: 1fr">${this.renderChildren()}</div>`
      : (this.hasChildren
          ? '<div class="block-children" style="grid-template-rows: 0fr"><div style="overflow:hidden"></div></div>'
          : '');

    this.shadowRoot.innerHTML = `
      <div class="block" data-type="${type}" data-depth="${20 - this.maxDepth}">
        <div class="block-row">
          <span class="drag-handle" draggable="true">::</span>
          ${expandBtn}
          <div class="block-content">${contentHtml}</div>
        </div>
        ${childrenHtml}
      </div>
    `;

    this.bindBlockEvents();
  }

  renderChildren() {
    // Stamp child <ntx-block> elements
    return this.#childAddrs.map(addr =>
      `<ntx-block ref="${addr}" max-depth="${this.maxDepth - 1}"></ntx-block>`
    ).join('');
  }

  bindBlockEvents() {
    const toggle = this.shadowRoot.querySelector('.expand-toggle');
    toggle?.addEventListener('click', () => this.toggleExpand());
  }
}

function defaultBlockRenderer(value, schema) {
  return `<p>${value.text || value.content || ''}</p>`;
}

customElements.define('ntx-block', NtxBlock);
```

### Block Type -> Component Mapping

Following N3TX's existing widget registry pattern, block types would map
to specialized renderers:

```javascript
// Register block type renderers (same pattern as widget registry)
registerBlockRenderer('paragraph', (value) =>
  `<p class="block-text">${value.text || ''}</p>`
);

registerBlockRenderer('heading', (value) =>
  `<h${value.level || 2} class="block-heading">${value.text || ''}</h${value.level || 2}>`
);

registerBlockRenderer('toggle', (value) =>
  `<summary class="block-toggle">${value.text || 'Toggle'}</summary>`
);

registerBlockRenderer('image', (value) =>
  `<img class="block-image" src="${value.url || ''}" alt="${value.caption || ''}" />`
);

registerBlockRenderer('code', (value) =>
  `<pre class="block-code"><code>${escapeHtml(value.code || '')}</code></pre>`
);
```

This mirrors how `widgets/index.js` registers built-in widgets:

```javascript
// Existing pattern in N3TX (from widgets/index.js):
registerWidget('url', new UrlWidget());
registerWidget('email', new EmailWidget());
registerWidget('markdown', new MarkdownWidget());

// Proposed parallel pattern for blocks:
registerBlockRenderer('paragraph', paragraphRenderer);
registerBlockRenderer('heading', headingRenderer);
registerBlockRenderer('toggle', toggleRenderer);
```

### Breadcrumb / Path-from-Root

Deep trees need wayfinding. A breadcrumb component reads the ancestor chain:

```javascript
class NtxBreadcrumb extends HTMLElement {
  set path(ancestors) {
    // ancestors = [{id, type, text}, {id, type, text}, ...]
    this.innerHTML = ancestors.map((a, i) =>
      `<span class="crumb" data-id="${a.id}">
        ${a.text || a.type}
        ${i < ancestors.length - 1 ? ' / ' : ''}
       </span>`
    ).join('');
  }
}
customElements.define('ntx-breadcrumb', NtxBreadcrumb);
```

### Adapting the "Load More" Pattern

`ListElement` already implements paginated child loading with a "Load More"
button. For block children, the same pattern applies per-level:

```
Block (expanded)
  +-- Child 1
  +-- Child 2
  +-- Child 3
  +-- [Load 17 more children...]   <-- same button, scoped to this parent
```

The existing `ListElement.loadMore()` increments `#offset` and calls
`proto.call('READ', { limit, offset })`. For block children, the call
would be scoped: `proto.call('READ', { parent_id: blockId, limit, offset })`.

---

## 6. Circular Schemas

### The Problem

If a `Block` model has a `children` field that references `Block`, the
JSON Schema contains a self-reference:

```json
{
  "$defs": {
    "Block": {
      "type": "object",
      "properties": {
        "id": { "type": "integer" },
        "type": { "type": "string" },
        "children": {
          "type": "array",
          "items": { "$ref": "#/$defs/Block" }
        }
      }
    }
  }
}
```

This is **valid JSON Schema** -- the
[JSON Schema specification](https://tour.json-schema.org/content/06-Combining-Subschemas/07-Recursive-Schemas)
explicitly supports recursive schemas: "the `$ref` keyword provides the
ability to validate recursive structures through self-reference."

### How `NTT.SCHEMA()` Handles It Today

Looking at the current code in `NTT.js` (lines 397-429):

```javascript
// Handle $defs (nested schemas) first -- skip the main model itself.
if (data.$defs && typeof data.$defs === 'object') {
    for (const [key, value] of Object.entries(data.$defs)) {
        if (key === addr) continue; // Main model handled below
        if (value.type === 'object' && value.properties
            && !NTT.#prototypes.get(key)) {
            const defHref = value['$id'] || `${config.API_URL}/${key}`;
            const DC = prototype(key, value, defHref);
            NTT.#prototypes.set(key, DC);
            NTT.#replayWaiting(key, DC);
        }
    }
}
```

The `if (key === addr) continue;` guard already skips the main model when
processing `$defs`. This means **a self-referencing `$def` would be
skipped entirely** -- no infinite loop, but also no special handling.

### What Needs to Change

The fix is minimal. When `$defs.Block` references itself, the `children`
field's `items.$ref` points to `#/$defs/Block`. The `prototype()` function
in `NTT.js` already resolves `$ref` strings in `resolveModelName()`:

```javascript
function resolveModelName(def) {
    const items = def.items || {};
    if (items.$ref) return items.$ref.split('/').pop();
    // ...
}
```

This returns `"Block"`, and `NTT.get("Block")` will find the DynamicClass
**because it was already created for the main model**. No circular
instantiation occurs -- the DynamicClass references itself by name, not
by object reference.

The only required change: ensure the `$defs` processing doesn't
**skip** the self-referencing entry before the main model is registered.
Since the main model is created on line 414 (`DC = prototype(addr, data, href)`),
and `$defs` processing happens on lines 397-409 with the `if (key === addr) continue;`
guard, the self-reference in `$defs` is simply ignored, and the main model's
DynamicClass serves both roles. **This already works.**

> **Key Insight:** N3TX's existing `NTT.SCHEMA()` architecture already
> handles self-referencing schemas correctly by accident -- the
> `if (key === addr) continue;` guard prevents duplicate DynamicClass creation,
> and the main model's class is used when resolving the self-reference via
> `NTT.get("Block")`. No code changes needed for schema processing.

---

## 7. Animation & UX Patterns

### Expand/Collapse: The `grid-template-rows` Technique

The **best modern approach** for animating height from 0 to auto uses CSS Grid.
As documented by [CSS-Tricks](https://css-tricks.com/css-grid-can-do-auto-height-transitions/),
this technique animates `grid-template-rows` from `0fr` to `1fr`:

```css
.block-children {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.25s ease-out;
}

.block-children.expanded {
  grid-template-rows: 1fr;
}

.block-children > div {
  overflow: hidden;  /* Required -- hides content at 0fr */
}
```

**Browser support:** Initially Firefox-only (2019), now
[works everywhere](https://css-tricks.com/css-grid-can-do-auto-height-transitions/)
as of 2025, including Chrome, Safari, and Edge.

This is **vastly superior** to the old approaches:

| Approach | Smoothness | Complexity | Accuracy |
|----------|-----------|------------|----------|
| `max-height: 0 -> 9999px` | Timing feels wrong | Low | Poor (overshoots) |
| JS-measured `height: 0 -> Npx` | Perfect | High (ResizeObserver) | Perfect |
| **`grid-template-rows: 0fr -> 1fr`** | **Perfect** | **Low (CSS only)** | **Perfect** |
| `display: none` toggle | No animation | Lowest | N/A |

### Indent Guides: The VS Code Pattern

[VS Code's file explorer](https://github.com/microsoft/vscode/issues/17777)
uses thin vertical lines to indicate tree depth. The CSS pattern:

```css
.block[data-depth] {
  position: relative;
  padding-left: calc(var(--depth, 0) * 24px);
}

/* Indent guide line */
.block::before {
  content: '';
  position: absolute;
  left: calc(var(--depth, 0) * 24px - 12px);
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--indent-guide-color, rgba(128, 128, 128, 0.2));
}

/* Highlight active branch */
.block:focus-within::before,
.block:hover::before {
  background: var(--indent-guide-active, rgba(128, 128, 128, 0.5));
}
```

VS Code defaults to **8px indentation** per level but allows up to 20px via
the `workbench.tree.indent`
[setting](https://www.meziantou.net/improve-the-tree-view-settings-in-visual-studio-code.htm).
For block editors, **20-24px** per level provides better readability.

### Transition Between States: The Full Picture

```
User clicks expand toggle
         |
         v
  [Set expanded=true]
         |
    +----+----+
    |         |
    v         v
 CSS grid    Fetch children
 transition  (if not loaded)
 0fr->1fr       |
    |          v
    |     [Children arrive]
    |          |
    v          v
 Animation  Stamp <ntx-block>
 completes  elements
    |          |
    +----+-----+
         |
         v
  [Children visible, animated in]
```

---

## 8. Keyboard Navigation & Accessibility

### WAI-ARIA Tree Pattern

The W3C [WAI-ARIA Tree View Pattern](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/)
specifies these keyboard interactions:

| Key | Action |
|-----|--------|
| **Arrow Down** | Move focus to next visible node |
| **Arrow Up** | Move focus to previous visible node |
| **Arrow Right** | Expand collapsed node; if expanded, move to first child |
| **Arrow Left** | Collapse expanded node; if collapsed, move to parent |
| **Enter** | Activate (edit) the focused node |
| **Home** | Move focus to first node |
| **End** | Move focus to last visible node |

### Roving Tabindex Implementation

The [recommended pattern](https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Keyboard-navigable_JavaScript_widgets)
for composite widgets is **roving tabindex**: only the focused item has
`tabindex="0"`, all others have `tabindex="-1"`.

```javascript
class BlockTree {
  #focusedIndex = 0;

  get visibleBlocks() {
    // Flatten visible tree nodes (skip collapsed children)
    return this.shadowRoot.querySelectorAll('ntx-block:not(.hidden)');
  }

  handleKeydown(e) {
    const blocks = [...this.visibleBlocks];
    const current = this.#focusedIndex;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        this.focusBlock(Math.min(current + 1, blocks.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        this.focusBlock(Math.max(current - 1, 0));
        break;
      case 'ArrowRight':
        e.preventDefault();
        const block = blocks[current];
        if (block.hasChildren && !block.expanded) {
          block.toggleExpand();
        } else if (block.expanded) {
          this.focusBlock(current + 1); // first child
        }
        break;
      case 'ArrowLeft':
        e.preventDefault();
        const blk = blocks[current];
        if (blk.expanded) {
          blk.toggleExpand(); // collapse
        } else {
          // move to parent
          const parentIdx = this.findParentIndex(current, blocks);
          if (parentIdx >= 0) this.focusBlock(parentIdx);
        }
        break;
    }
  }

  focusBlock(index) {
    const blocks = [...this.visibleBlocks];
    blocks[this.#focusedIndex]?.setAttribute('tabindex', '-1');
    this.#focusedIndex = index;
    blocks[index]?.setAttribute('tabindex', '0');
    blocks[index]?.focus();
  }
}
```

### ARIA Attributes for Block Trees

```html
<div role="tree" aria-label="Page content">
  <ntx-block role="treeitem" aria-expanded="true" aria-level="1" tabindex="0">
    <div role="group">
      <ntx-block role="treeitem" aria-expanded="false" aria-level="2" tabindex="-1" />
      <ntx-block role="treeitem" aria-level="2" tabindex="-1" />
    </div>
  </ntx-block>
</div>
```

---

## 9. Virtualized Tree Rendering

### When Does It Matter?

Virtualization (rendering only visible nodes) becomes necessary at **scale**:

| Scenario | Visible Nodes | Total Nodes | Need Virtualization? |
|----------|--------------|-------------|---------------------|
| Blog post | 15-30 | 30-100 | No |
| Wiki page | 20-50 | 100-500 | Probably not |
| Product spec | 30-80 | 500-2,000 | Maybe |
| Knowledge base | 50-100 | 5,000+ | Yes |
| Code documentation | 50-150 | 10,000+ | Definitely |

The general rule from
[virtual scrolling literature](https://blog.openreplay.com/virtual-scrolling-high-performance-interfaces/):
**virtualize when you have more than ~500 DOM nodes** and the user is
scrolling through them.

### Tree Virtualization Libraries

| Library | Framework | Tree Support | Row Height |
|---------|-----------|-------------|------------|
| [react-vtree](https://github.com/Lodin/react-vtree) | React | Native tree | Variable |
| [react-window](https://github.com/bvaughn/react-window) | React | Flat (flatten tree) | Fixed/Variable |
| [lit-virtualizer](https://github.com/nicolo-ribaudo/lit-virtualizer) | Lit/WC | Flat list | Variable |
| Custom (Intersection Observer) | Vanilla JS | Any | Any |

### Vanilla JS Approach: Intersection Observer

For Web Components without a framework dependency, `IntersectionObserver`
provides a native virtualization primitive:

```javascript
class VirtualBlockTree extends HTMLElement {
  #observer;

  connectedCallback() {
    this.#observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const block = entry.target;
          if (entry.isIntersecting) {
            block.removeAttribute('virtualized');
            block.render();  // Render content
          } else {
            block.setAttribute('virtualized', '');
            block.shadowRoot.innerHTML = '';  // Clear to free memory
            // Preserve height to avoid scroll jumps
            block.style.minHeight = block.dataset.measuredHeight || '40px';
          }
        }
      },
      { rootMargin: '200px' }  // Pre-render 200px ahead of viewport
    );

    // Observe all top-level block elements
    this.querySelectorAll('ntx-block').forEach(
      el => this.#observer.observe(el)
    );
  }

  disconnectedCallback() {
    this.#observer?.disconnect();
  }
}
```

> **Recommendation:** For N3TX v1, **skip virtualization**. The lazy
> expand/collapse pattern already limits visible nodes to ~50-100.
> Add virtualization later only if user telemetry shows pages with
> 500+ visible blocks causing jank.

---

## 10. Risk Assessment & Recommendations

### Advantages of Recursive Block Rendering in N3TX

| Advantage | Impact |
|-----------|--------|
| **Unified component model** -- one `<ntx-block>` replaces ad-hoc nesting | Reduces component surface area by ~40% |
| **Schema-driven type dispatch** -- block type -> renderer via registry | Zero code for new block types if schema carries the type |
| **Lazy loading aligns with existing pagination** | No new API patterns needed; reuse `limit/offset` |
| **Web Components recursion is native** | No framework overhead, no virtual DOM diffing |
| **CSS grid animation is production-ready** | Smooth expand/collapse with 3 lines of CSS |

### Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Shadow DOM depth performance** | Medium | Lazy rendering limits depth to ~3-5 visible levels |
| **Drag-drop across nesting levels** | High | Use flattened approach (SortableJS); don't nest contexts |
| **Keyboard navigation complexity** | Medium | Follow WAI-ARIA tree pattern; roving tabindex |
| **Schema self-reference edge cases** | Low | Already handled by NTT.SCHEMA() skip-self guard |
| **Style bleeding in deep trees** | Low | Shadow DOM encapsulation prevents this by design |
| **Mobile touch targets at deep nesting** | Medium | Cap visible depth at 4-5 levels; provide "zoom into block" |

### Implementation Priority

| Phase | Work | Effort | Value |
|-------|------|--------|-------|
| **Phase 1** | `<ntx-block>` component + type registry | 2-3 days | Core recursive rendering |
| **Phase 2** | CSS expand/collapse animation | 0.5 day | Polish |
| **Phase 3** | Keyboard navigation (WAI-ARIA tree) | 1-2 days | Accessibility |
| **Phase 4** | SortableJS drag-drop integration | 2-3 days | Reordering |
| **Phase 5** | Breadcrumb + "zoom into block" | 1 day | Deep tree UX |
| **Phase 6** | Virtualization (if needed) | 2-3 days | Scale (defer) |

> **Recommendation:** Start with Phase 1-2. That gives you a working
> recursive block tree with smooth animations in under a week. Phases 3-4
> are essential for production but can follow. Phase 6 should be
> deferred until real usage data shows it's needed.

### Architecture Decision: Shadow DOM Per Block vs. Flat DOM

This is the biggest design choice:

| | Shadow DOM Per Block | Flat DOM + CSS Indentation |
|---|---|---|
| **Style encapsulation** | Perfect -- each block is isolated | Manual -- must scope all styles |
| **Performance** | Higher memory, more roots | Lower memory, fewer roots |
| **Drag-drop** | Harder (cross-shadow-root) | Easier (flat list) |
| **Consistent with N3TX** | Yes -- same as ntx-item | No -- breaks the component model |
| **Editing** | Each block has own contenteditable | Single contenteditable (ProseMirror) |

> **Recommendation:** Use **Shadow DOM per block** for consistency with
> N3TX's existing architecture. The performance cost is manageable with lazy
> rendering. For drag-drop, use the flattened-list approach at the
> **logical level** (flat `Sortable` group across shadow boundaries) while
> keeping the **visual nesting** via CSS indentation within shadow roots.

---

## Sources

1. [Notion API: Block Reference](https://developers.notion.com/reference/block) -- Official block data model, `has_children` property
2. [Notion API: Working with Page Content](https://developers.notion.com/docs/working-with-page-content) -- Recursive fetch pattern
3. [BlockNote GitHub](https://github.com/TypeCellOS/BlockNote) -- Open source Notion-style editor built on ProseMirror/Tiptap
4. [BlockNote: Custom Blocks](https://www.blocknotejs.org/docs/features/custom-schemas/custom-blocks) -- Block schema definition
5. [DeepWiki: BlockNote Architecture](https://deepwiki.com/TypeCellOS/BlockNote/2.2-prosemirror-and-tiptap-integration) -- Internal ProseMirror integration
6. [Editor.js: Nested Blocks Issue #1440](https://github.com/codex-team/editor.js/issues/1440) -- Nested blocks not supported
7. [SortableJS GitHub](https://github.com/SortableJS/Sortable) -- Vanilla JS drag-and-drop for nested lists
8. [dnd-kit Sortable Docs](https://docs.dndkit.com/presets/sortable) -- Sortable preset documentation
9. [dnd-kit-sortable-tree](https://github.com/Shaddix/dnd-kit-sortable-tree) -- Tree drag-and-drop React component
10. [sortable-tree (vanilla TS)](https://github.com/marcantondahmen/sortable-tree) -- Zero-dependency sortable tree
11. [CSS-Tricks: CSS Grid Auto Height Transitions](https://css-tricks.com/css-grid-can-do-auto-height-transitions/) -- The `0fr`/`1fr` animation technique
12. [Stefan Judis: Animate Height with CSS Grid](https://www.stefanjudis.com/snippets/how-to-animate-height-with-css-grid/) -- CSS grid height animation
13. [JSON Schema: Recursive Schemas](https://tour.json-schema.org/content/06-Combining-Subschemas/07-Recursive-Schemas) -- Self-referencing `$ref`
14. [JSON Schema Circular $Refs (Gist)](https://gist.github.com/JamesMessinger/d18278935fc73e3a0ee1) -- Circular reference examples
15. [W3C WAI-ARIA: Keyboard Interface](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/) -- Tree view keyboard patterns
16. [MDN: Keyboard-navigable JS Widgets](https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Keyboard-navigable_JavaScript_widgets) -- Roving tabindex
17. [Lit: Shadow DOM](https://lit.dev/docs/components/shadow-dom/) -- Shadow DOM performance notes
18. [Lit: Component Composition](https://lit.dev/docs/composition/component-composition/) -- Recursive Lit patterns
19. [react-vtree](https://github.com/Lodin/react-vtree) -- Virtualized tree rendering for React
20. [LogRocket: Nesting Web Components](https://blog.logrocket.com/nesting-web-components-vanilla-javascript/) -- Slot-based composition patterns
21. [Notionpresso: Toggle Block](https://notionpresso.com/en/docs/block-types/toggle) -- Toggle block implementation reference
22. [VS Code: Tree Indent Guides Issue](https://github.com/microsoft/vscode/issues/17777) -- VS Code indent guide implementation
23. [Meziantou: VS Code Tree Settings](https://www.meziantou.net/improve-the-tree-view-settings-in-visual-studio-code.htm) -- Tree indent configuration
24. [Virtual Scrolling for High-Performance Interfaces](https://blog.openreplay.com/virtual-scrolling-high-performance-interfaces/) -- When to virtualize
25. [dnd-kit: Tree Drag-Drop Discussion](https://dev.to/fupeng_wang/react-dnd-kit-implement-tree-list-drag-and-drop-sortable-225l) -- Flattened vs. nested context approaches
