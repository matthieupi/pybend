# Fork A: Demo/Investor Path -- Kanban Board + Dashboard

**Scope:** 7 working days
**Prerequisites:** Sprints 1--3 complete (StatusWidget, Grant Detail, GrantsGovAPI, UserProfile, GrantMatch, MatcherTools)
**Goal:** Visual wow factor for demos and investor presentations
**Philosophy:** Application-level components in `example_grants/static/`. Zero backend changes. Zero framework modifications. Uses existing primitives (NTTElement, ListElement, DynamicClass, TX) without modifying them.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Task Breakdown](#2-task-breakdown)
3. [Task 1: Grant Kanban Board](#3-task-1-grant-kanban-board-grant-kanban)
4. [Task 2: Grant Dashboard](#4-task-2-grant-dashboard-grant-dashboard)
5. [Task 3: Sidebar Navigation Integration](#5-task-3-sidebar-navigation-integration)
6. [CSS Strategy](#6-css-strategy)
7. [Test Strategy](#7-test-strategy)
8. [Risk Register](#8-risk-register)

---

## 1. Architecture Overview

### Where These Components Fit

```
example_grants/static/           <-- App-level components (this fork)
  components/
    grant-kanban.js              <-- Kanban board (extends ListElement)
    grant-kanban.css             <-- Kanban styles (Shadow DOM encapsulated)
    grant-dashboard.js           <-- Dashboard (extends Component)
    grant-dashboard.css          <-- Dashboard styles (Shadow DOM encapsulated)
  index.html                     <-- Updated: new imports + sidebar entries

src/pybend/static/               <-- Framework (NOT modified)
  core/NTT.js                    <-- DynamicClass, instances Map, prototype()
  core/Component.js              <-- Base HTMLElement (shadow DOM, stylesheet caching)
  core/Actor.js                  <-- Actor base (addr, send, inbox, register)
  core/TX.js                     <-- TX message envelope
  core/Router.js                 <-- Navigation state actor
  components/ListElement.js      <-- Collection base class
  components/NTTElement.js       <-- Single entity base class
  components/ntt-item.js         <-- Default entity renderer (xs--xl)
  components/ntt-sidebar.js      <-- Sidebar with route templates
  components/ntt-router.js       <-- View container (mounts components)
  widgets/registry.js            <-- getWidgetForField()
```

### Import Resolution

The `create_app()` static file serving mounts app static files (`example_grants/static/`) as explicit routes that take precedence over the framework's catch-all `StaticFiles` mount of `src/pybend/static/`. Both app and framework files are served from the web root `/`. This means:

- `example_grants/static/components/grant-kanban.js` is served at `/components/grant-kanban.js`
- Framework files like `src/pybend/static/core/NTT.js` are served at `/core/NTT.js`
- Imports from app components use the same relative paths as framework components:
  ```javascript
  import { NTT } from '../core/NTT.js';         // resolves to framework NTT
  import { ListElement } from './ListElement.js'; // resolves to framework ListElement
  ```

### Data Flow Summary

Both new components consume data from the same pipeline every other component uses:

```
Grant model (Python)
  |
  v
GET /Grant -> JSON Schema -> NTT.SCHEMA() -> DynamicClass "Grant"
  |
  v
DynamicClass.READ() -> NTT instances in DynamicClass.instances (Map)
  |
  v
grant-kanban: groups instances by status, renders columns
grant-dashboard: aggregates instances into stats, renders cards/charts
```

No new backend endpoints. No new API calls. Client-side grouping and aggregation only.

---

## 2. Task Breakdown

| # | Task | Files Created/Modified | Dependencies | Est. |
|---|------|----------------------|--------------|------|
| 1a | Kanban: component skeleton + column rendering | `components/grant-kanban.js` (new) | None | 0.5d |
| 1b | Kanban: drag-and-drop with Shadow DOM | `components/grant-kanban.js` | 1a | 1.0d |
| 1c | Kanban: status change via TX UPDATE | `components/grant-kanban.js` | 1b | 0.5d |
| 1d | Kanban: CSS styling | `components/grant-kanban.css` (new) | 1a | 0.5d |
| 1e | Kanban: live reactivity (entity signal subscription) | `components/grant-kanban.js` | 1c | 0.5d |
| 1f | Kanban: polish (empty states, column counts, animations) | `components/grant-kanban.js`, `.css` | 1d, 1e | 1.0d |
| 2a | Dashboard: component skeleton + stat cards | `components/grant-dashboard.js` (new) | None | 0.5d |
| 2b | Dashboard: upcoming deadlines list | `components/grant-dashboard.js` | 2a | 0.5d |
| 2c | Dashboard: agency breakdown bars | `components/grant-dashboard.js` | 2a | 0.5d |
| 2d | Dashboard: CSS styling | `components/grant-dashboard.css` (new) | 2a | 0.5d |
| 2e | Dashboard: live reactivity + data bootstrapping | `components/grant-dashboard.js` | 2c | 0.5d |
| 2f | Dashboard: polish (sparklines, status pipeline, empty states) | `components/grant-dashboard.js`, `.css` | 2d, 2e | 0.5d |
| 3 | Sidebar + router integration | `index.html` (modified) | 1a, 2a | 0.5d |
| -- | **Total** | | | **7.0d** |

**Critical path:** Tasks 1a-1f and 2a-2f are independent tracks that can be parallelized. Task 3 depends on both tracks having at least a skeleton.

---

## 3. Task 1: Grant Kanban Board (`<grant-kanban>`)

### 3.1 Base Class Selection

The kanban extends `ListElement` from `/workspace/src/pybend/static/components/ListElement.js`. This is the correct choice because:

1. `ListElement` handles the full data lifecycle: schema resolution via `define()`, DynamicClass subscription via `definedCallback()`, and address array updates via `UPDATE()`.
2. The kanban is a collection view -- it shows many Grant entities grouped by status.
3. `ListElement` provides `proto` (DynamicClass reference), `value` (address array), and `schema` (Grant JSON Schema) automatically.
4. The `SELECT` handler already forwards to the Router for detail navigation.
5. Pattern is identical to `NTTList` and `NTTTable`, both of which extend `ListElement`.

### 3.2 Shadow DOM + Drag-and-Drop Architecture

**The problem:** HTML5 Drag and Drop API events (`dragstart`, `dragover`, `drop`) interact poorly with Shadow DOM boundaries. When dragging across shadow roots, `event.target` returns the shadow host element, not the internal target. Each `<ntt-item>` card lives in its own shadow root, and the kanban column structure lives in the kanban's shadow root.

**The solution: Single shadow root strategy.** The entire kanban board -- all columns and all card wrappers -- lives inside the `<grant-kanban>` element's single shadow root. Drag events never cross a shadow boundary because both the drag source (`.kanban-card` wrapper) and the drop target (`.column-body`) are siblings within the same shadow root.

The `<ntt-item display="sm">` elements nested inside `.kanban-card` wrappers have their own shadow roots, but drag events are bound to the outer `.kanban-card` div, not to the `<ntt-item>` inside it. This means:

- `dragstart` fires on `.kanban-card` (kanban's shadow root) -- works.
- `dragover`/`drop` fire on `.column-body` (kanban's shadow root) -- works.
- No cross-shadow-root drag events occur.

**Why `composedPath()` is not needed (but documented as fallback):** Because both drag source and drop target are in the same shadow root, standard `event.target` works. If a future iteration needs to detect drops on the `<ntt-item>` itself (e.g., for reordering within a column), `event.composedPath()` would be needed to traverse into the `<ntt-item>` shadow root. The code should include a comment documenting this for future reference.

### 3.3 Component Structure

**File:** `/workspace/example_grants/static/components/grant-kanban.js`

```javascript
/**
 * GrantKanban -- Kanban board view for Grant entities.
 *
 * Extends ListElement for data lifecycle (schema, READ, pagination, UPDATE).
 * Groups grants by status into draggable columns. Drag-and-drop changes
 * grant status via TX UPDATE.
 *
 * Usage:
 *   <grant-kanban model="Grant"></grant-kanban>
 */
import { ListElement } from './ListElement.js';
import { NTT } from '../core/NTT.js';
import TX from '../core/TX.js';
import { getWidgetForField } from '../widgets/index.js';

const STATUSES = ['discovered', 'reviewed', 'applied', 'awarded', 'expired'];
const STATUS_COLORS = {
  discovered: '#6366f1',
  reviewed:   '#f59e0b',
  applied:    '#22d3c5',
  awarded:    '#10b981',
  expired:    '#ef4444',
};

export class GrantKanban extends ListElement {

  #eventAC = null;
  #entityUnsubs = [];

  get styles() { return new URL('./grant-kanban.css', import.meta.url).href; }

  // ...
}

customElements.define('grant-kanban', GrantKanban);
```

### 3.4 Data Flow: Kanban Status Change

This is the core interaction. When a user drags a grant card from one column to another:

```
Step 1: User drags .kanban-card[data-addr="Grant/5"] from "discovered" column
  |
  v
Step 2: dragstart handler stores draggedAddr = "Grant/5"
  |
  v
Step 3: User drops on .column-body[data-status="reviewed"]
  |
  v
Step 4: drop handler calls #changeStatus("Grant/5", "reviewed")
  |
  v
Step 5: #changeStatus() resolves the NTT entity instance:
         const entity = NTT.get("Grant/5");     // DynamicClass instance lookup
         entity.value = { ...entity.value, status: "reviewed" };  // optimistic
  |
  v
Step 6: Send TX UPDATE to persist the change:
         entity.send(new TX({
           name: 'UPDATE',
           source: entity.addr,
           target: entity.href,          // "http://.../grants/5"
           data: entity.value            // includes new status
         }));
  |
  v
Step 7: Matrix routes TX to NetworkAdapter
  |
  v
Step 8: NetworkAdapter sends PATCH /grants/5 with { status: "reviewed", ... }
  |
  v
Step 9: Backend validates and updates DB
  |
  v
Step 10: Response flows back:
          NetworkAdapter -> Matrix -> DynamicClass.UPDATE -> entity.update()
  |
  v
Step 11: entity.signal() fires -> subscribed NTTElement/NTTItem re-renders
         + DynamicClass observers fire -> kanban's #onEntityChange() re-renders
```

**Optimistic update detail:** Step 5 updates the entity value immediately so the card moves to the new column before the network round-trip completes. If the PATCH fails, the ERROR handler reverts:

```javascript
#changeStatus(addr, newStatus) {
  const parts = addr.split('/');
  const id = parts[parts.length - 1];
  const entity = NTT.get(`Grant/${id}`);
  if (!entity) return;

  const oldStatus = entity.value?.status;
  if (oldStatus === newStatus) return;

  // Optimistic: update entity, re-render will follow via signal
  const updated = { ...entity.value, status: newStatus };

  // Send UPDATE TX -- entity.UPDATE() handles optimistic + network
  entity.send(new TX({
    name: 'UPDATE',
    source: entity.addr,
    target: entity.href,
    data: updated
  }));
}
```

The `entity.UPDATE()` handler (from NTT.js DynamicClass prototype, line 525-529) calls `entity.update(data)` which sets `entity.value` and fires `entity.signal()`. The kanban subscribes to each visible entity's signal so it re-renders when any entity changes.

### 3.5 Entity Reactivity

The kanban must re-render when:
1. The initial READ populates entities (handled by `ListElement.UPDATE()`)
2. An entity's status changes (drag-drop, or external edit)
3. A new entity is created or deleted

For cases 2 and 3, the kanban subscribes to the DynamicClass-level UPDATE observable (same mechanism `NTTTable` uses in `definedCallback()`). This fires whenever the instance set or any instance value changes.

```javascript
definedCallback() {
  super.definedCallback();
  // Subscribe to class-level UPDATE for create/delete notifications
  this._unsub?.();
  this._unsub = this.proto.observe('UPDATE', () => this.scheduleRender());
}
```

For per-entity status changes from external sources (another user, an agent), the DynamicClass-level observer also fires because `DynamicClass.READ()` and `DynamicClass.UPDATE()` both notify observers.

### 3.6 Render Logic

The render method groups entities by status, then builds a column for each status:

```javascript
render() {
  if (!this.schema || !Array.isArray(this.value)) return;

  // Group grants by status
  const columns = {};
  for (const status of STATUSES) columns[status] = [];

  for (const addr of this.value) {
    const parts = addr.split('/');
    const id = parts[parts.length - 1];
    const entity = NTT.get(`Grant/${id}`);
    const status = entity?.value?.status || 'discovered';
    if (columns[status]) columns[status].push({ addr, entity });
  }

  // Build column HTML
  const columnsHtml = STATUSES.map(status => {
    const items = columns[status];
    const cardsHtml = items.map(({ addr }) => `
      <div class="kanban-card" draggable="true" data-addr="${addr}">
        <ntt-item ref="${addr}" display="sm"
                  data-model="Grant" select-target="${this.addr}"></ntt-item>
      </div>
    `).join('');

    return `
      <div class="kanban-column" data-status="${status}">
        <div class="column-header">
          <span class="column-dot" style="background:${STATUS_COLORS[status]}"></span>
          <span class="column-title">${status}</span>
          <span class="column-count">${items.length}</span>
        </div>
        <div class="column-body" data-status="${status}">
          ${cardsHtml}
          <div class="column-empty ${items.length ? 'hidden' : ''}">
            No grants
          </div>
        </div>
      </div>
    `;
  }).join('');

  this.shadowRoot.innerHTML = `
    <div class="kanban-header">
      <h1>Grant Pipeline</h1>
      <span class="list-count">${this.value.length}</span>
    </div>
    <div class="kanban-board">${columnsHtml}</div>
  `;
  this._rendered = true;
  this.#bindDragDrop();
}
```

### 3.7 Drag-and-Drop Binding

```javascript
#bindDragDrop() {
  this.#eventAC?.abort();
  this.#eventAC = new AbortController();
  const { signal } = this.#eventAC;
  let draggedAddr = null;

  // Drag start on card wrappers
  this.shadowRoot.querySelectorAll('.kanban-card').forEach(card => {
    card.addEventListener('dragstart', (e) => {
      draggedAddr = card.dataset.addr;
      card.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      // Set drag data (required for Firefox)
      e.dataTransfer.setData('text/plain', draggedAddr);
    }, { signal });

    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      draggedAddr = null;
      // Clear all drag-over highlights
      this.shadowRoot.querySelectorAll('.drag-over')
        .forEach(el => el.classList.remove('drag-over'));
    }, { signal });
  });

  // Drop zones (column bodies)
  this.shadowRoot.querySelectorAll('.column-body').forEach(col => {
    col.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      col.classList.add('drag-over');
    }, { signal });

    col.addEventListener('dragleave', (e) => {
      // Only remove highlight if leaving the column entirely
      // (not entering a child element within the column)
      if (!col.contains(e.relatedTarget)) {
        col.classList.remove('drag-over');
      }
    }, { signal });

    col.addEventListener('drop', (e) => {
      e.preventDefault();
      col.classList.remove('drag-over');
      if (!draggedAddr) return;
      const newStatus = col.dataset.status;
      this.#changeStatus(draggedAddr, newStatus);
    }, { signal });
  });
}
```

**Key detail: `dragleave` flicker prevention.** When dragging over child elements inside a column, the browser fires `dragleave` on the column and `dragenter` on the child. Using `col.contains(e.relatedTarget)` prevents the column from losing its drag-over highlight during these internal transitions.

### 3.8 Surgical DOM Update

Override `update(prev, next)` from `ListElement` to avoid full re-renders on every entity change:

```javascript
update(prev, next) {
  // For simple add/remove, re-render is fine (kanban layout changes)
  // For status changes, the full render re-groups correctly
  // Return false to trigger full render -- kanban grouping logic
  // makes surgical updates complex and error-prone
  return false;
}
```

The kanban deliberately does NOT do surgical updates. Full re-renders are acceptable because:
1. The kanban shows at most a few hundred cards
2. `<ntt-item>` children have their own shadow roots and maintain internal state
3. Re-render frequency is low (status changes are infrequent)
4. The `scheduleRender()` coalescing in `Component` prevents multiple renders per frame

### 3.9 Disconnection Cleanup

```javascript
disconnectedCallback() {
  this.#eventAC?.abort();
  this._unsub?.();
  for (const unsub of this.#entityUnsubs) unsub();
  this.#entityUnsubs = [];
  super.disconnectedCallback();
}
```

---

## 4. Task 2: Grant Dashboard (`<grant-dashboard>`)

### 4.1 Base Class Selection

The dashboard extends `Component` from `/workspace/src/pybend/static/core/Component.js` directly, NOT `ListElement`. Rationale:

1. The dashboard is not a collection view -- it does not stamp child elements per entity.
2. It does not need the watcher/UPDATE/value-as-array lifecycle that `ListElement` provides.
3. It needs to aggregate data from the DynamicClass instances Map, which requires direct access to `NTT.get('Grant')`.
4. It bootstraps via `NTT.attach('Grant', callback)`, same as `NTTSidebar`.

### 4.2 Data Strategy: Client-Side Aggregation

The dashboard computes all stats client-side from `DynamicClass.instances`:

```javascript
#computeStats() {
  const DC = NTT.get('Grant');
  if (!DC) return null;

  const grants = [...DC.instances.values()]
    .map(e => e.value)
    .filter(Boolean);

  const now = new Date();
  const total = grants.length;

  // By status
  const byStatus = {};
  for (const g of grants) {
    const s = g.status || 'discovered';
    byStatus[s] = (byStatus[s] || 0) + 1;
  }

  // Upcoming deadlines (next 30 days, sorted)
  const upcoming = grants
    .filter(g => g.deadline && new Date(g.deadline) > now)
    .map(g => ({
      ...g,
      daysLeft: Math.ceil((new Date(g.deadline) - now) / 86400000)
    }))
    .sort((a, b) => a.daysLeft - b.daysLeft)
    .slice(0, 8);

  // By agency (top 6)
  const byAgency = {};
  for (const g of grants) {
    if (g.agency) byAgency[g.agency] = (byAgency[g.agency] || 0) + 1;
  }
  const topAgencies = Object.entries(byAgency)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 6);

  // Total award range
  const amounts = grants
    .filter(g => g.amount_max)
    .map(g => g.amount_max);
  const totalPotential = amounts.reduce((sum, a) => sum + a, 0);

  return { total, byStatus, upcoming, topAgencies, totalPotential };
}
```

**Why this works for Grant Watcher:** The app will have hundreds of grants, not millions. All loaded grants are already in memory (the DynamicClass READ fetches them at page load). Aggregation is O(n) and runs in under 1ms for 1000 grants.

**When to upgrade to server-side aggregation:** If grant count exceeds ~5000, or if the dashboard needs data the frontend doesn't have (e.g., historical trends, cross-user analytics), add a `@expose_route('/stats', methods=['GET'])` method on the Grant model. But for the demo/investor path, client-side is simpler and zero-backend-change.

### 4.3 Reactivity: Live Updates

The dashboard subscribes to the DynamicClass UPDATE observable so it re-renders when grants are created, updated, or deleted:

```javascript
connectedCallback() {
  super.connectedCallback();
  NTT.attach('Grant', (DC) => {
    this._DC = DC;
    this._unsub?.();
    this._unsub = DC.observe('UPDATE', () => this.scheduleRender());
    this.scheduleRender();
  });
}

disconnectedCallback() {
  this._unsub?.();
  super.disconnectedCallback();
}
```

This means: drag a card in the kanban view, switch to the dashboard -- it shows the updated counts. Or: an agent creates a new grant -- the dashboard updates automatically.

### 4.4 Component Structure

**File:** `/workspace/example_grants/static/components/grant-dashboard.js`

```javascript
/**
 * GrantDashboard -- Aggregated stats view for Grant entities.
 *
 * Extends Component directly (not ListElement) because it aggregates
 * data from DynamicClass.instances rather than stamping child elements.
 *
 * Sections:
 *   - Stat cards: total, by status, total potential funding
 *   - Upcoming deadlines: sorted list with countdown badges
 *   - Agency breakdown: horizontal bar chart
 *   - Status pipeline: visual flow showing grant progression
 *
 * Usage:
 *   <grant-dashboard></grant-dashboard>
 */
import { Component } from '../core/Component.js';
import { NTT } from '../core/NTT.js';

const STATUSES = ['discovered', 'reviewed', 'applied', 'awarded', 'expired'];
const STATUS_COLORS = {
  discovered: '#6366f1',
  reviewed:   '#f59e0b',
  applied:    '#22d3c5',
  awarded:    '#10b981',
  expired:    '#ef4444',
};

export class GrantDashboard extends Component {

  _DC = null;
  _unsub = null;

  get styles() { return new URL('./grant-dashboard.css', import.meta.url).href; }

  // ...
}

customElements.define('grant-dashboard', GrantDashboard);
```

### 4.5 Render Sections

#### 4.5.1 Stat Cards Row

```
+----------+----------+----------+----------+----------+
|  Total   | Discover | Reviewed | Applied  | Awarded  |
|    47    |    23    |    12    |     8    |     4    |
+----------+----------+----------+----------+----------+
```

Each card is a `<div class="stat-card">` with a color-coded top border matching `STATUS_COLORS`. The "Total" card uses the accent color (`#22d3c5`). An additional card can show total potential funding (`$2.4M`).

```javascript
#statCard(label, value, color) {
  return `
    <div class="stat-card" style="--stat-accent: ${color}">
      <span class="stat-value">${value}</span>
      <span class="stat-label">${label}</span>
    </div>
  `;
}
```

#### 4.5.2 Upcoming Deadlines

```
+------------------------------------------+
| Upcoming Deadlines                       |
|                                          |
|  SBIR Phase II Research        [  7d  ]  |
|  STTR Industry Partnership     [ 14d  ]  |
|  K-12 STEM Innovation          [ 21d  ]  |
|  Clean Energy Transition       [ 28d  ]  |
+------------------------------------------+
```

Each deadline row shows the grant title and a countdown badge. Badge color:
- Red: <= 7 days
- Amber: <= 30 days
- Default: > 30 days

Clicking a deadline row navigates to the grant detail (sends NAVIGATE TX to the router):

```javascript
#deadlineRow(grant) {
  const urgencyClass = grant.daysLeft <= 7 ? 'urgent'
    : grant.daysLeft <= 30 ? 'soon' : '';
  return `
    <div class="deadline-row" data-ref="Grant/${grant.id}">
      <span class="deadline-title">${grant.title}</span>
      <span class="deadline-badge ${urgencyClass}">${grant.daysLeft}d</span>
    </div>
  `;
}
```

#### 4.5.3 Agency Breakdown

```
+------------------------------------------+
| By Agency                                |
|                                          |
|  NSF      =====================  12      |
|  DOE      =================      10      |
|  NIH      ==============          8      |
|  DARPA    =========               5      |
|  SBA      =====                   3      |
+------------------------------------------+
```

Horizontal bars with width proportional to count. Max bar width = 100% for the largest agency.

```javascript
#agencyBar(agency, count, maxCount) {
  const pct = maxCount > 0 ? (count / maxCount * 100) : 0;
  return `
    <div class="agency-row">
      <span class="agency-name">${agency}</span>
      <span class="agency-bar" style="width: ${pct}%"></span>
      <span class="agency-count">${count}</span>
    </div>
  `;
}
```

#### 4.5.4 Status Pipeline (Optional Enhancement)

A horizontal funnel showing grant flow through statuses:

```
  discovered(23) --> reviewed(12) --> applied(8) --> awarded(4)
                                                      |
                                            expired(0)
```

Implemented as connected circles with labels and counts. This is the "wow" visual for investor demos -- it shows grant lifecycle at a glance.

### 4.6 Dashboard Event Binding

```javascript
#bindEvents() {
  this.#eventAC?.abort();
  this.#eventAC = new AbortController();
  const { signal } = this.#eventAC;

  // Deadline rows -> NAVIGATE to grant detail
  this.shadowRoot.querySelectorAll('.deadline-row[data-ref]').forEach(row => {
    row.addEventListener('click', () => {
      const ref = row.dataset.ref;
      // Find the nearest router and send NAVIGATE
      // Dashboard may not have a router attr, so use matrix dispatch
      import('../core/Matrix.js').then(({ matrix }) => {
        matrix.dispatch({
          name: 'NAVIGATE',
          source: this.addr,
          target: 'main',  // Default router name from index.html
          data: ref,
        });
      });
    }, { signal });
  });
}
```

### 4.7 Chart.js Integration (Optional, Day 7)

For richer visualizations, Chart.js (~11KB gzipped) can be vendored at `/workspace/src/pybend/static/vendor/chart.min.js`. The dashboard would dynamically import it:

```javascript
async #renderChart(container, data) {
  const { Chart } = await import('../vendor/chart.min.js');
  // ... create doughnut chart for status distribution
}
```

This is optional and deferred to the polish phase. The CSS-only bar charts and stat cards provide sufficient visual impact for the initial demo.

---

## 5. Task 3: Sidebar Navigation Integration

### 5.1 How Sidebar Route Templates Work

The `NTTSidebar` component (`/workspace/src/pybend/static/components/ntt-sidebar.js`) scans its Light DOM children for elements with a `model` attribute. Each child becomes a "route template":

```javascript
// ntt-sidebar.js, connectedCallback(), lines 76-87
const children = [...this.querySelectorAll(':scope > [model]')];
for (const child of children) {
  const modelName = child.getAttribute('model');
  const tag = child.tagName.toLowerCase();
  const attrs = {};
  for (const attr of child.attributes) {
    if (!SKIP.has(attr.name)) attrs[attr.name] = attr.value;
  }
  this.#routeTemplates.set(modelName, { tag, attrs });
  child.hidden = true;
}
```

When a user clicks a model name in the sidebar, `#navigateToModel()` dispatches a NAVIGATE TX to the Router with the template's tag and attributes:

```javascript
matrix.dispatch({
  name: 'NAVIGATE',
  source: 'sidebar',
  target: routerAddr,
  data: { tag, attrs, title: modelName },
});
```

The Router's `NTTRouter` component receives this and creates the specified element in its content area.

### 5.2 Current Sidebar Configuration

```html
<!-- Current index.html -->
<ntt-sidebar router="main">
    <ntt-list model="Grant" allow-create></ntt-list>
    <ntt-table model="Source"></ntt-table>
    <ntt-list model="AgentActor"></ntt-list>
</ntt-sidebar>
```

This creates one sidebar entry per model. Clicking "Grant" navigates to `<ntt-list model="Grant" allow-create>`.

### 5.3 Adding Kanban and Dashboard as Additional Views

**Challenge:** The current sidebar maps one model to one route template. We need three views for "Grant": table (existing), kanban, and dashboard.

**Solution: Add kanban and dashboard as separate sidebar entries.** They are not model-specific entries (they don't have a `model` attribute that maps to a DynamicClass). Instead, they are programmatic navigation targets.

**Approach A: Add as named route templates in the sidebar.**

We can add the kanban and dashboard as additional children of `<ntt-sidebar>`. The sidebar derives its model list from children with `model` attribute. But the kanban and dashboard both relate to `model="Grant"`. Adding them with the same model name would overwrite the route template.

**Approach B (Recommended): Use the dashboard and kanban as the default Grant view, with a view switcher.**

Since both kanban and dashboard operate on Grant data, the cleanest approach is:

1. Keep the sidebar with one entry per model (Grant, Source, AgentActor).
2. Add a **view switcher** inside the kanban/dashboard/table that lets users toggle between views.
3. The sidebar's Grant entry navigates to the default view (table).

However, this adds complexity. For the demo/investor path, the simpler approach is:

**Approach C (Simplest for Demo): Add kanban and dashboard as separate entries with distinct labels.**

The sidebar template children do not require unique model names -- they just need to be different elements. We can use a wrapper approach:

```html
<ntt-sidebar router="main">
    <ntt-table model="Grant" allow-create></ntt-table>
    <grant-kanban model="Grant"></grant-kanban>
    <grant-dashboard model="Grant"></grant-dashboard>
    <ntt-table model="Source"></ntt-table>
    <ntt-list model="AgentActor"></ntt-list>
</ntt-sidebar>
```

**Issue:** The sidebar deduplicates by model name. All three Grant entries would collapse to the last one.

**Resolution: The dashboard does not have `model="Grant"` -- it bootstraps via `NTT.attach()` internally.** So we give it a synthetic model name or no model attribute at all.

Actually, re-reading the sidebar code more carefully: when `#routeTemplates` has multiple entries with the same model name, each `.set()` call overwrites the previous. So we need a different approach.

**Final approach: Add view switcher tabs to the main view area.**

Add a lightweight `<grant-views>` wrapper component OR simply add a tab bar directly to `index.html` that dispatches NAVIGATE TXs for each view:

```html
<ntt-sidebar router="main">
    <ntt-table model="Grant" allow-create></ntt-table>
    <ntt-table model="Source"></ntt-table>
    <ntt-list model="AgentActor"></ntt-list>
</ntt-sidebar>

<div class="page">
    <ntt-router name="main" hash>
        <div class="view-tabs">
            <button class="view-tab active" data-view="table">Table</button>
            <button class="view-tab" data-view="kanban">Pipeline</button>
            <button class="view-tab" data-view="dashboard">Dashboard</button>
        </div>
        <ntt-table model="Grant" id="grant-table" allow-create></ntt-table>
    </ntt-router>
</div>
```

The tab buttons dispatch NAVIGATE TXs programmatically:

```javascript
document.querySelectorAll('.view-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const view = tab.dataset.view;
    const views = {
      table:     { tag: 'ntt-table', attrs: { model: 'Grant', 'allow-create': '' } },
      kanban:    { tag: 'grant-kanban', attrs: { model: 'Grant' } },
      dashboard: { tag: 'grant-dashboard', attrs: {} },
    };
    // Route via matrix
    import('./core/Matrix.js').then(({ matrix }) => {
      matrix.dispatch({
        name: 'NAVIGATE',
        source: 'view-tabs',
        target: 'main',
        data: { ...views[view], title: `Grant ${view.charAt(0).toUpperCase() + view.slice(1)}` },
      });
    });
    // Update active tab styling
    document.querySelectorAll('.view-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
  });
});
```

The tabs appear at the top of the main content area, above whichever view is active. They persist across navigations because they are slotted content of the `<ntt-router>` -- but wait, `ntt-router.render()` replaces slot content with the navigated view. So the tabs would disappear on navigation.

**Revised approach: Tabs live outside the router.**

```html
<div class="page">
    <div class="view-tabs" id="grant-views">
        <button class="view-tab active" data-view="table">Table</button>
        <button class="view-tab" data-view="kanban">Pipeline</button>
        <button class="view-tab" data-view="dashboard">Dashboard</button>
    </div>
    <ntt-router name="main" hash>
        <ntt-table model="Grant" id="grant-table" allow-create></ntt-table>
    </ntt-router>
</div>
```

The tabs are siblings of the router, always visible. They dispatch NAVIGATE to the router. When viewing a non-Grant entity (e.g., Source detail), the tabs can be hidden via CSS or JS.

This is the recommended approach. It requires:
1. A small `<div class="view-tabs">` block in `index.html`
2. A few lines of JS in the `<script type="module">` block to bind click handlers
3. CSS for the tabs (inline in `index.html` or in `dark-theme.css`)
4. Logic to show/hide tabs based on current view context

### 5.4 Updated index.html

**File:** `/workspace/example_grants/static/index.html`

Changes needed:

1. **Add CSS preloads** for new component stylesheets:
   ```html
   <link rel="preload" href="./components/grant-kanban.css" as="style">
   <link rel="preload" href="./components/grant-dashboard.css" as="style">
   ```

2. **Add modulepreloads** for new components:
   ```html
   <link rel="modulepreload" href="./components/grant-kanban.js">
   <link rel="modulepreload" href="./components/grant-dashboard.js">
   ```

3. **Add view tabs** above the router:
   ```html
   <div class="view-tabs" id="grant-views">
     <button class="view-tab active" data-view="table">Table</button>
     <button class="view-tab" data-view="kanban">Pipeline</button>
     <button class="view-tab" data-view="dashboard">Dashboard</button>
   </div>
   ```

4. **Add import statements** in the module script:
   ```javascript
   import './components/grant-kanban.js';
   import './components/grant-dashboard.js';
   ```

5. **Add tab switching logic** in the module script.

---

## 6. CSS Strategy

### 6.1 Shadow DOM Encapsulation

Both components use Shadow DOM via the `Component` base class constructor (`this.attachShadow({mode: 'open'})`). All styles are encapsulated -- they cannot leak to or from the rest of the page.

Stylesheets are loaded via the constructable stylesheets API, cached globally by URL in `Component`'s `_sheetCache` Map. This means:
- First instance of `<grant-kanban>` fetches and parses `grant-kanban.css` once.
- Subsequent instances (if any) reuse the cached `CSSStyleSheet` synchronously.
- The `scheduleRender()` method defers rendering until the stylesheet is ready, preventing FOUC.

### 6.2 Color Tokens

Both components use the same color tokens as the existing dark theme. Reference the CSS custom properties defined in `example_grants/static/dark-theme.css` where possible. For status-specific colors, use the `STATUS_COLORS` constant from JavaScript (inline styles on colored elements).

Key tokens to reference (from dark-theme.css):
```css
--bg-primary       /* Page background */
--bg-secondary     /* Card/section background */
--bg-tertiary      /* Nested containers */
--text-primary     /* Main text */
--text-secondary   /* Muted text */
--text-tertiary    /* Very muted */
--accent           /* Brand accent (#22d3c5) */
--accent-hover     /* Accent hover state */
--border           /* Border color */
--border-focus     /* Focus ring */
```

Status colors are NOT CSS custom properties -- they are hardcoded in JavaScript because:
1. They represent domain-specific semantics (grant status), not design tokens.
2. They need to be consistent between JS (StatusWidget) and CSS (kanban columns).
3. They are defined once in the `STATUS_COLORS` constant and applied via inline styles.

### 6.3 Kanban CSS (`grant-kanban.css`)

Key layout rules:

```css
/* Board: horizontal scroll with flexbox columns */
.kanban-board {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  overflow-x: auto;
  min-height: 400px;
}

/* Column: fixed width, vertical scroll for cards */
.kanban-column {
  flex: 0 0 280px;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  border-radius: 0.75rem;
  overflow: hidden;
}

.column-body {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem;
  min-height: 100px;
  transition: background 0.15s ease;
}

/* Drag-over highlight */
.column-body.drag-over {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  outline: 2px dashed var(--accent);
  outline-offset: -2px;
}

/* Dragging card reduced opacity */
.kanban-card.dragging {
  opacity: 0.4;
}

/* Card wrapper */
.kanban-card {
  margin-bottom: 0.5rem;
  border-radius: 0.5rem;
  cursor: grab;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.kanban-card:active {
  cursor: grabbing;
}
.kanban-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
```

### 6.4 Dashboard CSS (`grant-dashboard.css`)

Key layout rules:

```css
.dashboard {
  padding: 1.5rem;
  max-width: 1200px;
}

/* Stat cards: responsive grid */
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.stat-card {
  background: var(--bg-secondary);
  border-radius: 0.75rem;
  padding: 1.25rem;
  border-top: 3px solid var(--stat-accent);
  text-align: center;
}
.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary);
  display: block;
}
.stat-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Two-column grid for deadlines + agency breakdown */
.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}
@media (max-width: 768px) {
  .dashboard-grid { grid-template-columns: 1fr; }
}

/* Deadline row */
.deadline-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.6rem 0;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
}
.deadline-row:hover { background: var(--bg-tertiary); }

.deadline-badge {
  padding: 0.2rem 0.6rem;
  border-radius: 100px;
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}
.deadline-badge.urgent {
  background: #ef4444;
  color: white;
}
.deadline-badge.soon {
  background: #f59e0b;
  color: white;
}

/* Agency bar chart */
.agency-row {
  display: grid;
  grid-template-columns: 120px 1fr 40px;
  gap: 0.5rem;
  align-items: center;
  padding: 0.4rem 0;
}
.agency-bar {
  height: 8px;
  background: var(--accent);
  border-radius: 4px;
  transition: width 0.3s ease;
}
```

### 6.5 View Tabs CSS

Added to `index.html` or `dark-theme.css`:

```css
.view-tabs {
  display: flex;
  gap: 0;
  padding: 0 1rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 0;
}
.view-tab {
  padding: 0.6rem 1.2rem;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-secondary);
  font-size: 0.85rem;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.view-tab:hover { color: var(--text-primary); }
.view-tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}
```

---

## 7. Test Strategy

### 7.1 Testing Approach

Frontend tests use Playwright (e2e) following the existing pattern in `/workspace/example_grants/tests/e2e/`. The tests require a running server (`cd example_grants && python main.py`) and seeded data (`python seed.py`).

Unit-testable logic (stats aggregation) can be extracted into pure functions tested with a lightweight JS test runner, but the existing project does not have one. For the demo timeline, Playwright e2e tests are the pragmatic choice.

### 7.2 Kanban Tests

**File:** `/workspace/example_grants/tests/e2e/test_kanban.py`

**Test 1: Kanban renders with correct column structure**

```python
def test_kanban_renders_columns():
    """Navigate to kanban view and verify all 5 status columns appear."""
    # Navigate to kanban via view tab click
    # Assert 5 .kanban-column elements exist in shadow root
    # Assert column headers match STATUSES
    # Assert column counts are non-negative integers
```

**Test 2: Kanban groups grants by status**

```python
def test_kanban_groups_by_status():
    """Verify grants appear in the correct status column."""
    # Navigate to kanban
    # Count cards in each column
    # Verify total card count matches total grants
```

**Test 3: Drag-and-drop changes status (core interaction)**

```python
def test_drag_drop_changes_status():
    """Drag a card from 'discovered' to 'reviewed' and verify status update."""
    # Navigate to kanban
    # Identify a card in 'discovered' column
    # Perform drag-and-drop using Playwright's drag_to()
    # Wait for network PATCH request
    # Verify card moved to 'reviewed' column
    # Verify entity status in backend (GET /grants/{id})
```

**Playwright drag-and-drop in Shadow DOM:**

Playwright's `locator.drag_to(target)` works with Shadow DOM when using `page.locator()` with `>> shadow` piercing selectors:

```python
# Get drag source (card in discovered column)
source = page.locator(
    'grant-kanban >> .kanban-column[data-status="discovered"] >> .kanban-card >> nth=0'
)
# Get drop target (reviewed column body)
target = page.locator(
    'grant-kanban >> .column-body[data-status="reviewed"]'
)
source.drag_to(target)
```

**Test 4: Card click navigates to detail**

```python
def test_kanban_card_click_navigates():
    """Clicking a kanban card navigates to the grant detail view."""
    # Navigate to kanban
    # Click on a card's ntt-item
    # Verify router shows detail view
    # Verify hash changed
```

### 7.3 Dashboard Tests

**File:** `/workspace/example_grants/tests/e2e/test_dashboard.py`

**Test 1: Dashboard renders stat cards**

```python
def test_dashboard_stat_cards():
    """Navigate to dashboard and verify stat cards show correct totals."""
    # Navigate to dashboard via view tab
    # Assert .stat-card elements exist
    # Assert total count matches known grant count
    # Assert status counts sum to total
```

**Test 2: Dashboard deadline list**

```python
def test_dashboard_deadlines():
    """Verify upcoming deadlines are shown sorted by date."""
    # Navigate to dashboard
    # Assert .deadline-row elements exist
    # Assert first deadline has the soonest date
    # Assert day counts are positive integers
```

**Test 3: Dashboard deadline click navigates**

```python
def test_dashboard_deadline_navigates():
    """Clicking a deadline row navigates to the grant detail view."""
    # Navigate to dashboard
    # Click first deadline row
    # Verify router shows detail view
```

**Test 4: Dashboard live update**

```python
def test_dashboard_updates_on_status_change():
    """Verify dashboard stats update when a grant status changes."""
    # Navigate to dashboard
    # Record current stat counts
    # Change a grant's status via API (PATCH /grants/{id})
    # Wait for dashboard to re-render
    # Verify stat counts changed
```

### 7.4 View Tabs Tests

**Test 1: Tab switching**

```python
def test_view_tab_switching():
    """Verify clicking tabs switches between table, kanban, dashboard."""
    # Click "Pipeline" tab
    # Verify grant-kanban element exists in router content
    # Click "Dashboard" tab
    # Verify grant-dashboard element exists in router content
    # Click "Table" tab
    # Verify ntt-table element exists in router content
```

### 7.5 Testing the Aggregation Logic

If we want to test the dashboard aggregation logic in isolation (without Playwright), we can extract `#computeStats()` as a standalone pure function in a separate module:

```javascript
// example_grants/static/utils/grant-stats.js
export function computeGrantStats(grants) {
  // ... pure function, no DOM, no NTT
}
```

This can be tested with Node.js + a simple test runner. But for the 7-day timeline, this is optional. The Playwright tests cover the integration.

---

## 8. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Drag/drop flicker on dragleave** | High | Low | Use `col.contains(e.relatedTarget)` check in dragleave handler |
| **Firefox drag/drop requires setData** | High | Medium | Always call `e.dataTransfer.setData('text/plain', addr)` in dragstart |
| **Shadow DOM blocks drag events** | Low | High | Mitigated by design: all drag sources and drop targets are in the same shadow root |
| **Performance with 500+ cards in kanban** | Low | Medium | Each card is an `<ntt-item display="sm">` which is lightweight. If needed, virtualize by only rendering visible columns. |
| **Dashboard FOUC on first load** | Low | Low | `Component.scheduleRender()` already defers until stylesheet is adopted |
| **Tab state lost on browser refresh** | Medium | Low | Tabs are not persisted in hash. Default view (table) shows on refresh. Could add `?view=kanban` query param if needed. |
| **DynamicClass not ready when dashboard mounts** | Low | Medium | `NTT.attach()` handles the timing: if DC exists, callback fires immediately; if pending, queued. Dashboard shows "Loading..." until callback fires. |
| **Grant entity lacks status field** | Very Low | High | Sprint 1 already added the status field. If missing, kanban groups all grants into "discovered". |

---

## Appendix A: File Inventory

### New Files

| File | Type | Size Est. | Purpose |
|------|------|-----------|---------|
| `example_grants/static/components/grant-kanban.js` | JS Component | ~200 lines | Kanban board |
| `example_grants/static/components/grant-kanban.css` | CSS | ~150 lines | Kanban styles |
| `example_grants/static/components/grant-dashboard.js` | JS Component | ~180 lines | Dashboard |
| `example_grants/static/components/grant-dashboard.css` | CSS | ~180 lines | Dashboard styles |

### Modified Files

| File | Change | Impact |
|------|--------|--------|
| `example_grants/static/index.html` | Add imports, preloads, view tabs, tab JS | Low risk -- additive only |

### Framework Files Referenced (NOT modified)

| File | What's Used |
|------|-------------|
| `src/pybend/static/components/ListElement.js` | Base class for grant-kanban |
| `src/pybend/static/core/Component.js` | Base class for grant-dashboard |
| `src/pybend/static/core/NTT.js` | `NTT.get()`, `NTT.attach()`, DynamicClass.instances |
| `src/pybend/static/core/TX.js` | TX constructor for UPDATE messages |
| `src/pybend/static/core/Matrix.js` | `matrix.dispatch()` for NAVIGATE |
| `src/pybend/static/components/ntt-item.js` | `<ntt-item display="sm">` inside kanban cards |
| `src/pybend/static/components/ntt-sidebar.js` | Route template mechanism |
| `src/pybend/static/components/ntt-router.js` | View mounting via NAVIGATE |
| `src/pybend/static/widgets/registry.js` | `getWidgetForField()` for status chips in cards |

---

## Appendix B: Day-by-Day Schedule

| Day | Morning | Afternoon |
|-----|---------|-----------|
| **1** | Task 1a: Kanban skeleton + column rendering | Task 1d: Kanban CSS (columns, header, cards) |
| **2** | Task 1b: Drag-and-drop binding + Shadow DOM | Task 1b (cont): Firefox compat, dragleave fix |
| **3** | Task 1c: TX UPDATE on drop + optimistic update | Task 1e: Entity signal subscription, re-render |
| **4** | Task 1f: Polish -- empty states, counts, animations | Task 3: Sidebar/tabs integration, index.html |
| **5** | Task 2a: Dashboard skeleton + stat cards | Task 2d: Dashboard CSS |
| **6** | Task 2b: Upcoming deadlines list | Task 2c: Agency breakdown bars |
| **7** | Task 2e: Live reactivity + NTT.attach bootstrap | Task 2f: Polish -- pipeline visual, empty states |

**Parallelization note:** If two developers are available, kanban (days 1--4) and dashboard (days 5--7) can run in parallel, reducing total calendar time to ~4 days. Task 3 (sidebar integration) takes 0.5 days and depends on both having at least a skeleton.

---

## Appendix C: Grant Model Reference

From `/workspace/example_grants/models/grant.py`:

```python
class Grant(ActorModel):
    __tablename__: ClassVar[str] = 'grants'
    __storable__: ClassVar[bool] = True

    title: str = Field(min_length=1, max_length=500)
    agency: str = Field(min_length=1, max_length=200)
    deadline: Optional[DateField] = Field(default=None)
    amount_min: Optional[CurrencyField] = Field(default=None)
    amount_max: Optional[CurrencyField] = Field(default=None)
    url: UrlField = Field(description="URL to the grant listing")
    description: TextareaField = Field(default='')
    status: str = Field(default='discovered',
                        description="discovered | reviewed | applied | expired")
    user_owner: User = Field(default=None)
```

Status values used by kanban columns: `discovered`, `reviewed`, `applied`, `awarded`, `expired`.

Note: The model description says "discovered | reviewed | applied | expired" (4 values) but the StatusWidget research document includes `awarded` (5 values). The kanban should support all 5, with `awarded` between `applied` and `expired` in the pipeline. If `awarded` is not present in the status field's validation, it should be added to the model description as a pre-task or at the start of this fork.
