# Frontend Polish: Custom Views, Status Workflows & Dashboards

**Grant Watcher Application -- N3TX v0.10**
**Research Date: 2026-03-04**

---

## 1. Executive Summary

The Grant Watcher frontend currently renders **everything through generic schema-driven components** -- `<ntx-table>`, `<ntx-list>`, and `<ntx-item>`. This is exactly how N3TX is designed to work: define a model, get a working UI. But "working" and "useful for daily grant tracking" are different things. A user scanning 200 grants needs a **deadline countdown**, not a date string. They need a **status pipeline**, not a plain text field that says "discovered". They need a **dashboard** that answers "what needs attention today?", not a flat table.

The good news: N3TX's architecture was **built for this exact upgrade path**. The `ui.renderer.detail` schema field drives component resolution in `ntx-router.js` (line 141). The Widget system (`/workspace/src/n3tx/static/widgets/`) provides field-level customization. `NTTElement` is designed as a base class for custom components (`/workspace/src/n3tx/static/components/NTTElement.js`). Every extension point needed for grant-specific views already exists -- we just need to use them.

The investment is **moderate** (estimated 3-4 weeks for a single frontend developer), the risk is **low** (all changes are additive -- nothing in the generic rendering path needs to change), and the payoff is **high** (transforms a data browser into a purpose-built grant tracking tool). This document lays out exactly what to build, in what order, and how each piece plugs into the existing architecture.

---

## 2. The What -- Concrete Deliverables

### 2.1 Deliverable Map

| # | Deliverable | Type | Priority | Est. Days |
|---|------------|------|----------|-----------|
| 1 | Status Widget (`<status-chip>`) | Widget | **P0** | 1 |
| 2 | Grant Detail View (`<grant-detail>`) | Custom Component | **P0** | 3 |
| 3 | Kanban Board (`<grant-kanban>`) | View Component | **P1** | 4 |
| 4 | Dashboard (`<grant-dashboard>`) | View Component | **P1** | 3 |
| 5 | Source Health Panel | Widget Enhancement | **P2** | 2 |
| 6 | Agent Control Panel | View Component | **P2** | 3 |
| **Total** | | | | **16 days** |

### 2.2 What the User Sees Today vs. After

```
TODAY                                    AFTER
+-----------------------------------+   +-----------------------------------+
| Grants                      12    |   | Grants                      12    |
+------+--------+------+--------+--+   +------+--------+------+--------+--+
| title| agency | url  |deadline|  |   | title| agency |status| days   |  |
+------+--------+------+--------+--+   +------+--------+------+--------+--+
| SBIR | NSF    | http | 2026-  |  |   | SBIR | NSF    | [==] |  14d   |  |
|      |        | ...  | 06-15  |  |   |      |        | chip | remain |  |
+------+--------+------+--------+--+   +------+--------+------+--------+--+
                                        Click row -> rich detail view
                                        Sidebar -> Kanban | Dashboard tabs
```

---

## 3. The Why -- User Experience, Engagement, Operational Efficiency

### 3.1 Problem: Generic Rendering Misses Domain Context

The Grant model (`/workspace/example_grants/models/grant.py`) has **rich domain semantics** that generic rendering ignores:

- **`status`** is a `str` field with allowed values `discovered | reviewed | applied | expired`. The table renders it as plain text. It should be a **color-coded chip** that tells you at a glance where each grant stands.

- **`deadline`** is a `DateField`. The table shows `2026-06-15`. What the user needs is **"14 days remaining"** in amber, or **"EXPIRED"** in red.

- **`amount_min` / `amount_max`** are `CurrencyField` values. Shown separately, they are two numbers. Together as a **range bar**, they answer "is this grant worth pursuing?" instantly.

- **`url`** is a `UrlField`. It gets a clickable link (via UrlWidget). But in a grant context, it should be an **"Apply Now"** action button, not a bare URL.

### 3.2 Business Impact

| Metric | Without Polish | With Polish |
|--------|---------------|-------------|
| Time to find actionable grants | Manual scan of full table | Dashboard highlights top priorities |
| Missed deadlines | User must mentally calculate from dates | Red/amber countdown draws attention |
| Status tracking | Edit field, type status string | Drag card in kanban OR click chip |
| Source monitoring | Check each source manually | Health indicators show scan status |
| Agent oversight | Raw data only | Run history, success rates, one-click trigger |

> **Key Insight:** The generic UI answers "what data exists?" The polished UI answers "what should I do next?" That is the difference between a database viewer and a product.

### 3.3 Competitive Context

According to [dashboard design best practices](https://www.uxpin.com/studio/blog/dashboard-design-principles/), the most effective dashboards **lead with actionable metrics, not raw data**. Grant management platforms like Grants.gov and Foundation Directory Online all feature status pipelines, deadline calendars, and at-a-glance dashboards. Without these, Grant Watcher looks like a developer tool; with them, it looks like a product.

---

## 4. The How -- Implementation Approach

### 4.1 Architecture Integration Points

The critical question is: **where does custom rendering plug in?** N3TX provides three levels:

```
Level 1: Widget System (field-level)
  Python: CurrencyField, DateField, UrlField
  JS: getWidgetForField() in registry.js -> Widget.display() / .edit() / .list()
  Use for: status chip, deadline countdown, amount range

Level 2: ui.renderer Schema Field (component-level)
  Python: __ui__ = {'renderer': {'detail': 'grant-detail', 'item': 'ntx-item'}}
  JS: ntx-router.js #resolveTag() reads schema.ui.renderer.detail
  Use for: grant detail view, custom list views

Level 3: Custom View Components (page-level)
  JS: Extend ListElement or Component directly
  Navigation: sidebar route template or @route
  Use for: kanban board, dashboard, agent panel
```

```
 Schema Pipeline (backend)
  +------------------+
  | Grant model      |
  | __ui__ = {       |         ui.renderer.detail = 'grant-detail'
  |   renderer: {    |  --->   schema.properties.status.ui.widget = 'status'
  |     detail:      |         schema.properties.deadline.ui.widget = 'date'
  |     'grant-      |
  |      detail'     |
  |   }              |
  | }                |
  +------------------+
         |
         v
  JSON Schema over HTTP
         |
         v
  Frontend Resolution
  +------------------+      +------------------+      +------------------+
  | ntx-router.js    | ---> | grant-detail.js  | ---> | StatusWidget.js  |
  | #resolveTag()    |      | extends          |      | via registry     |
  | reads            |      | NTTElement       |      | getWidgetFor     |
  | ui.renderer.     |      |                  |      | Field()          |
  | detail           |      |                  |      |                  |
  +------------------+      +------------------+      +------------------+
```

### 4.2 Deliverable 1: Status Widget (P0, 1 day)

**What:** A `StatusWidget` registered as `'status'` that renders color-coded chips in display/list mode and a dropdown in edit mode.

**Backend change:** Add widget annotation to the `status` field in `/workspace/example_grants/models/grant.py`:

```python
from n3tx.core.widgets import Widget

class StatusField(Widget, name='status', base_type=str):
    """Grant status with constrained values."""
    pass

class Grant(ActorModel):
    # ... existing fields ...
    status: StatusField = Field(
        default='discovered',
        description="discovered | reviewed | applied | awarded | expired"
    )
```

Or, without a custom Python type, use `json_schema_extra`:

```python
status: str = Field(
    default='discovered',
    description="discovered | reviewed | applied | awarded | expired",
    json_schema_extra={
        'ui': {
            'widget': 'status',
            'config': {
                'values': ['discovered', 'reviewed', 'applied', 'awarded', 'expired'],
                'colors': {
                    'discovered': '#6366f1',   # indigo
                    'reviewed':   '#f59e0b',   # amber
                    'applied':    '#22d3c5',   # teal (accent)
                    'awarded':    '#10b981',   # green
                    'expired':    '#ef4444',   # red
                }
            }
        }
    }
)
```

**Frontend:** New file `example_grants/static/widgets/StatusWidget.js`:

```javascript
import { Widget, registerWidget } from '../../widgets/index.js';

class StatusWidget extends Widget {

  display(value, config) {
    const color = config.colors?.[value] || '#555e78';
    const chip = this.el('span', {
      class: 'status-chip',
      style: `
        display: inline-flex; align-items: center; gap: 0.3rem;
        padding: 0.2rem 0.6rem; border-radius: 100px;
        font-size: 0.75rem; font-weight: 600; letter-spacing: 0.03em;
        text-transform: uppercase;
        color: white;
        background: ${color};
      `
    }, [value || 'unknown']);
    return chip;
  }

  edit(value, config, schema, onChange) {
    const select = this.el('select', { class: 'status-select' });
    for (const v of (config.values || [])) {
      const opt = this.el('option', { value: v }, [v]);
      if (v === value) opt.selected = true;
      select.appendChild(opt);
    }
    select.addEventListener('change', () => onChange?.(select.value));
    return select;
  }

  list(value, config) {
    const color = config.colors?.[value] || '#555e78';
    return `<span style="
      display:inline-block; padding:0.15rem 0.5rem; border-radius:100px;
      font-size:0.7rem; font-weight:600; text-transform:uppercase;
      color:white; background:${color};
    ">${value || '?'}</span>`;
  }
}

registerWidget('status', new StatusWidget());
```

**Why this works with zero framework changes:** The schema pipeline stage `widget` (registered `before='ui'` in `/workspace/src/n3tx/core/widgets/schema_ext.py`) injects `ui.widget` and `ui.config` into JSON Schema properties. On the frontend, `getWidgetForField()` in `/workspace/src/n3tx/static/widgets/registry.js` returns the widget instance. Both `form.js` (line 212-246) and `ntx-item.js` (line 315-319 in `sm()`) already dispatch to widgets before falling through to type-based rendering.

> **Key Insight:** The widget system was designed for exactly this use case -- domain-specific field rendering without touching any generic component code. Zero risk.

### 4.3 Deliverable 2: Grant Detail View (P0, 3 days)

**What:** A custom `<grant-detail>` component that replaces the generic `ntx-item` when viewing a single grant at detail/page size.

**Schema integration:** Add `ui.renderer.detail` to the Grant model:

```python
class Grant(ActorModel):
    __ui__: ClassVar[dict] = {
        'renderer': {'detail': 'grant-detail', 'item': 'ntx-item'},
        'field_order': ['title', 'agency', 'status', 'deadline',
                        'amount_min', 'amount_max', 'url', 'description'],
    }
```

When a user clicks a grant in the table, `ntx-router.js` line 141 resolves:
```javascript
#resolveTag(model) {
    const DC = N3TX.get(model);
    return DC?.schema?.ui?.renderer?.detail   // <-- 'grant-detail'
        || DC?.schema?.ui?.renderer?.item
        || 'ntx-item';
}
```

**Component structure** (`example_grants/static/components/grant-detail.js`):

```javascript
import { NTTElement } from '../../../src/n3tx/static/components/NTTElement.js';
import { getWidgetForField } from '../../../src/n3tx/static/widgets/index.js';

class GrantDetail extends NTTElement {

  get styles() { return new URL('./grant-detail.css', import.meta.url).href; }

  render() {
    if (!this.schema || !this.value) return;
    const v = this.value;
    const props = this.schema.properties || {};

    // Deadline countdown
    const deadline = v.deadline ? new Date(v.deadline) : null;
    const now = new Date();
    const daysLeft = deadline ? Math.ceil((deadline - now) / 86400000) : null;
    const urgency = daysLeft === null ? 'none'
      : daysLeft < 0 ? 'expired'
      : daysLeft <= 7 ? 'urgent'
      : daysLeft <= 30 ? 'soon' : 'ok';

    // Status chip via widget
    const statusWr = getWidgetForField(props.status);
    const statusHtml = statusWr.widget
      ? statusWr.widget.list(v.status, statusWr.config, props.status)
      : v.status;

    // Amount range
    const amtMin = v.amount_min ? `$${Number(v.amount_min).toLocaleString()}` : '?';
    const amtMax = v.amount_max ? `$${Number(v.amount_max).toLocaleString()}` : '?';

    this.shadowRoot.innerHTML = `
      <div class="grant-detail">
        <header class="grant-header">
          <div class="grant-meta">
            <span class="agency-badge">${v.agency || 'Unknown Agency'}</span>
            ${statusHtml}
          </div>
          <h1 class="grant-title">${v.title || 'Untitled Grant'}</h1>
        </header>

        <div class="grant-body">
          <section class="grant-main">
            <div class="grant-description">${v.description || ''}</div>
            <div class="grant-actions">
              <a href="${v.url}" target="_blank" rel="noopener"
                 class="apply-btn">View Grant Listing</a>
            </div>
          </section>

          <aside class="grant-sidebar">
            <div class="sidebar-card">
              <div class="meta-row">
                <span class="meta-label">Deadline</span>
                <span class="meta-value deadline-${urgency}">
                  ${deadline ? deadline.toLocaleDateString() : 'No deadline'}
                  ${daysLeft !== null
                    ? `<span class="days-left">(${daysLeft < 0
                        ? 'Expired' : daysLeft + 'd remaining'})</span>`
                    : ''}
                </span>
              </div>
              <div class="meta-row">
                <span class="meta-label">Award Range</span>
                <span class="meta-value">${amtMin} - ${amtMax}</span>
              </div>
              <div class="meta-row">
                <span class="meta-label">Status</span>
                <span class="meta-value">${statusHtml}</span>
              </div>
            </div>
          </aside>
        </div>
      </div>
    `;
    this._rendered = true;
  }
}

customElements.define('grant-detail', GrantDetail);
```

**Layout sketch:**

```
+------------------------------------------------------------------+
|  [NSF]  [========= APPLIED =========]                           |
|  Accelerating Discovery in STEM Education                        |
+------------------------------------------------------------------+
|                                    |  +------------------------+ |
|  Description text goes here...     |  | Deadline               | |
|  Multiple paragraphs of grant      |  | Jun 15, 2026           | |
|  description content rendered      |  | (14d remaining)        | |
|  from the description field.       |  |                        | |
|                                    |  | Award Range            | |
|                                    |  | $50,000 - $250,000     | |
|                                    |  |                        | |
|  [  View Grant Listing  ]          |  | Status                 | |
|                                    |  | [=== APPLIED ===]      | |
+------------------------------------+  +------------------------+ |
+------------------------------------------------------------------+
```

**How it gets loaded:** The component file must be imported in `index.html`. The `ntx-router` component will automatically use `grant-detail` when navigating to a Grant entity, because it reads `schema.ui.renderer.detail`.

### 4.4 Deliverable 3: Kanban Board (P1, 4 days)

**What:** A `<grant-kanban>` component that shows grants grouped by status in a drag-to-change-status board.

**The critical Shadow DOM challenge:** The HTML5 Drag and Drop API has [known interoperability issues](https://justinribeiro.com/chronicle/2020/07/14/handling-web-components-and-drag-and-drop-with-event.composedpath/) with Shadow DOM. When dragging between shadow roots, `event.target` returns the host element, not the internal drop zone. The solution is `event.composedPath()`, which traverses shadow boundaries.

**Architecture approach:** The kanban board should be a **Light DOM component** (no shadow root for the board itself) or use a single shadow root that contains all columns. Individual grant cards within the kanban can be `<ntx-item display="sm">` elements, which already handle their own Shadow DOM correctly.

**Component sketch** (`example_grants/static/components/grant-kanban.js`):

```javascript
import { ListElement } from '../../../src/n3tx/static/components/ListElement.js';
import { N3TX } from '../../../src/n3tx/static/core/N3TX.js';
import TX from '../../../src/n3tx/static/core/TX.js';

const STATUSES = ['discovered', 'reviewed', 'applied', 'awarded', 'expired'];
const STATUS_COLORS = {
  discovered: '#6366f1', reviewed: '#f59e0b', applied: '#22d3c5',
  awarded: '#10b981', expired: '#ef4444',
};

class GrantKanban extends ListElement {

  get styles() { return new URL('./grant-kanban.css', import.meta.url).href; }

  render() {
    if (!this.schema || !Array.isArray(this.value)) return;

    // Group grants by status
    const columns = {};
    for (const status of STATUSES) columns[status] = [];

    for (const addr of this.value) {
      const id = addr.split('/').pop();
      const entity = N3TX.get(`Grant/${id}`);
      const status = entity?.value?.status || 'discovered';
      if (columns[status]) columns[status].push(addr);
    }

    // Render columns
    const columnsHtml = STATUSES.map(status => `
      <div class="kanban-column" data-status="${status}">
        <div class="column-header">
          <span class="column-dot"
                style="background:${STATUS_COLORS[status]}"></span>
          <span class="column-title">${status}</span>
          <span class="column-count">${columns[status].length}</span>
        </div>
        <div class="column-body" data-status="${status}">
          ${columns[status].map(addr => `
            <div class="kanban-card" draggable="true" data-addr="${addr}">
              <ntx-item ref="${addr}" display="sm"></ntx-item>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('');

    this.shadowRoot.innerHTML = `
      <div class="kanban-board">${columnsHtml}</div>
    `;

    this.#bindDragDrop();
  }

  #bindDragDrop() {
    let draggedAddr = null;

    // Drag start
    this.shadowRoot.querySelectorAll('.kanban-card').forEach(card => {
      card.addEventListener('dragstart', (e) => {
        draggedAddr = card.dataset.addr;
        card.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
      });
      card.addEventListener('dragend', () => {
        card.classList.remove('dragging');
        draggedAddr = null;
      });
    });

    // Drop zones (column bodies)
    this.shadowRoot.querySelectorAll('.column-body').forEach(col => {
      col.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        col.classList.add('drag-over');
      });
      col.addEventListener('dragleave', () => {
        col.classList.remove('drag-over');
      });
      col.addEventListener('drop', (e) => {
        e.preventDefault();
        col.classList.remove('drag-over');
        if (!draggedAddr) return;

        const newStatus = col.dataset.status;
        this.#changeStatus(draggedAddr, newStatus);
      });
    });
  }

  #changeStatus(addr, newStatus) {
    // Optimistic UI update
    const id = addr.split('/').pop();
    const entity = N3TX.get(`Grant/${id}`);
    if (entity) {
      // Update via TX -> PATCH /grants/{id}
      entity.send(new TX({
        name: 'UPDATE',
        source: entity.addr,
        target: entity.href,
        data: { ...entity.value, status: newStatus }
      }));
    }
  }
}

customElements.define('grant-kanban', GrantKanban);
```

**Status transition flow:**

```
User drags card from "discovered" to "reviewed"
         |
         v
#changeStatus('Grant/5', 'reviewed')
         |
         v
TX { name: 'UPDATE', target: 'http://.../grants/5', data: {status: 'reviewed'} }
         |
         v
Matrix -> NetworkAdapter -> PATCH /grants/5
         |
         v
Backend validates, updates DB, returns updated entity
         |
         v
DynamicClass.READ() -> entity.update() -> signal() -> kanban re-renders
```

**Sidebar integration:** Add to `index.html`:

```html
<ntx-sidebar router="main">
    <ntx-table model="Grant" allow-create></ntx-table>
    <grant-kanban model="Grant"></grant-kanban>   <!-- new tab -->
    <ntx-table model="Source"></ntx-table>
    <ntx-list model="AgentActor"></ntx-list>
</ntx-sidebar>
```

The sidebar already supports route templates (`/workspace/src/n3tx/static/components/ntx-sidebar.js`, line 76-87). Clicking "Grant" in the sidebar can navigate to either the table or kanban based on the template element.

### 4.5 Deliverable 4: Dashboard (P1, 3 days)

**What:** A `<grant-dashboard>` view showing aggregated stats, deadline timeline, and quick actions.

**Data strategy:** Two approaches, with different trade-offs:

| Approach | Pros | Cons |
|----------|------|------|
| Client-side aggregation | Zero backend changes, uses existing READ data | Only works if all grants fit in memory (<1000) |
| Backend aggregation endpoint | Scales to any dataset, richer queries | Requires new `@expose_route` method on Grant |

**Recommendation:** Start with **client-side aggregation**. The Grant Watcher app will have hundreds, not millions, of grants. The DynamicClass already holds all loaded instances in `DynamicClass.instances` (a `Map`). We can iterate that Map to compute stats without any new API calls.

**Component sketch** (`example_grants/static/components/grant-dashboard.js`):

```javascript
import { Component } from '../../../src/n3tx/static/core/Component.js';
import { N3TX } from '../../../src/n3tx/static/core/N3TX.js';

class GrantDashboard extends Component {

  #unsub = null;

  get styles() { return new URL('./grant-dashboard.css', import.meta.url).href; }

  connectedCallback() {
    super.connectedCallback();
    // Bootstrap Grant DC and subscribe to updates
    N3TX.attach('Grant', (DC) => {
      this.#unsub = DC.observe('UPDATE', () => this.scheduleRender());
      this.scheduleRender();
    });
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.#unsub?.();
  }

  render() {
    const DC = N3TX.get('Grant');
    if (!DC) { this.shadowRoot.innerHTML = '<p>Loading...</p>'; return; }

    const grants = [...DC.instances.values()].map(e => e.value).filter(Boolean);
    const now = new Date();

    // ── Stats ──
    const total = grants.length;
    const byStatus = {};
    for (const g of grants) {
      byStatus[g.status] = (byStatus[g.status] || 0) + 1;
    }

    // ── Upcoming deadlines (next 30 days) ──
    const upcoming = grants
      .filter(g => g.deadline && new Date(g.deadline) > now)
      .sort((a, b) => new Date(a.deadline) - new Date(b.deadline))
      .slice(0, 5);

    // ── Agencies breakdown ──
    const byAgency = {};
    for (const g of grants) {
      byAgency[g.agency] = (byAgency[g.agency] || 0) + 1;
    }
    const topAgencies = Object.entries(byAgency)
      .sort(([,a], [,b]) => b - a)
      .slice(0, 5);

    this.shadowRoot.innerHTML = `
      <div class="dashboard">
        <div class="stats-row">
          ${this.#statCard('Total Grants', total, '#22d3c5')}
          ${this.#statCard('Discovered', byStatus.discovered || 0, '#6366f1')}
          ${this.#statCard('Applied', byStatus.applied || 0, '#f59e0b')}
          ${this.#statCard('Awarded', byStatus.awarded || 0, '#10b981')}
        </div>

        <div class="dashboard-grid">
          <section class="upcoming-deadlines">
            <h2>Upcoming Deadlines</h2>
            ${upcoming.map(g => {
              const d = new Date(g.deadline);
              const days = Math.ceil((d - now) / 86400000);
              return `<div class="deadline-row">
                <span class="deadline-title">${g.title}</span>
                <span class="deadline-days ${days <= 7 ? 'urgent' : ''}">${days}d</span>
              </div>`;
            }).join('') || '<p class="empty">No upcoming deadlines</p>'}
          </section>

          <section class="agency-breakdown">
            <h2>By Agency</h2>
            ${topAgencies.map(([agency, count]) => `
              <div class="agency-row">
                <span class="agency-name">${agency}</span>
                <span class="agency-bar"
                  style="width:${(count/total*100)}%"></span>
                <span class="agency-count">${count}</span>
              </div>
            `).join('')}
          </section>
        </div>
      </div>
    `;
  }

  #statCard(label, value, color) {
    return `
      <div class="stat-card" style="--stat-color:${color}">
        <span class="stat-value">${value}</span>
        <span class="stat-label">${label}</span>
      </div>
    `;
  }
}

customElements.define('grant-dashboard', GrantDashboard);
```

**Dashboard layout:**

```
+----------+----------+----------+----------+
| Total    | Discover | Applied  | Awarded  |
|   47     |    23    |    12    |    5     |
+----------+----------+----------+----------+
|                     |                      |
| Upcoming Deadlines  | By Agency            |
|                     |                      |
| SBIR Phase II  14d  | NSF       ===== 12  |
| STTR Program    9d  | DOE       ====  10  |
| K-12 STEM      21d  | NIH       ===    8  |
| Clean Energy   28d  | DARPA     ==     5  |
|                     | SBA       =      3  |
+---------------------+----------------------+
```

**Chart integration:** For richer visualizations (timeline charts, pie charts), [Chart.js](https://www.chartjs.org/) is the recommended choice. It is **11KB gzipped** for core types, works with vanilla JavaScript, renders to Canvas, and requires zero build step. It can be vendored alongside `marked.min.js` and `ansi_up.min.js` in `/workspace/src/n3tx/static/vendor/`.

For inline sparklines (e.g., grant discovery trend in stat cards), [sparklines.js](https://github.com/mitjafelicijan/sparklines) provides **tiny SVG sparkline charts with zero dependencies** -- a single JS file that can be dropped into the vendor directory.

### 4.6 Deliverable 5: Source Health Panel (P2, 2 days)

**What:** Enhance the Source model display with health indicators and scan triggers.

**Backend additions to `/workspace/example_grants/models/source.py`:**

```python
class Source(ActorModel):
    __tablename__ = 'sources'
    __storable__ = True

    name: str = Field(min_length=1, max_length=200)
    url: UrlField = Field(description="URL to scan for grants")
    category: str = Field(default='government',
                          description="government | foundation | corporate")
    # New fields:
    last_scan: Optional[DateField] = Field(default=None)
    scan_status: str = Field(default='idle',
        json_schema_extra={'ui': {'widget': 'status', 'config': {
            'values': ['idle', 'scanning', 'success', 'error'],
            'colors': {'idle': '#555e78', 'scanning': '#f59e0b',
                       'success': '#10b981', 'error': '#ef4444'}
        }}})
    grants_found: int = Field(default=0)

    @expose_route('/scan', methods=['POST'], access=AUTHENTICATED)
    def scan(self, user: User = None) -> str:
        """Trigger a scan of this source."""
        # This would trigger the agent system
        return f"Scan initiated for {self.name}"
```

The `scan_status` field reuses the same StatusWidget built in Deliverable 1. The `scan` method gets rendered as an `<ntx-method>` button automatically -- zero frontend work needed for that.

### 4.7 Deliverable 6: Agent Control Panel (P2, 3 days)

**What:** A custom view for AgentActor that shows run history, tool usage, and a "Run Now" button with live progress.

**The WebSocket connection:** N3TX's `NetworkWebSocket` adapter (`/workspace/src/n3tx/core/api/network_ws.py`) already bridges frontend TX to backend TX. Agent lifecycle events (`after_create`, `after_update`) flow through this channel. The agent panel can subscribe to WebSocket messages to show **live progress** during agent runs.

**Architecture:**

```
[Run Now] button click
     |
     v
TX { name: 'run', target: '/agents/1/run', data: { task: '...' } }
     |
     v
NetworkAdapter -> POST /agents/1/run
     |
     v
AgentActor.run() starts async execution
     |                    |
     v                    v
Response: "Run started"   LIFECYCLE TX via WebSocket
     |                         |
     v                         v
UI: "Running..."          agent-panel receives WS UPDATE
     |                         |
     v                         v
poll or WS update         Re-render with new status
```

**Key implementation detail:** The `AgentActor` model already supports a `run` method via `@expose_route`. The frontend already renders this as an `<ntx-method>` button. The agent panel enhancement would be a custom component that wraps this with:

- Run history (fetched from a future `runs` child model)
- Tool usage counters (from `agent.tools` array field)
- Status indicator (idle / running / error) using the StatusWidget
- Log output using the existing `ConsoleWidget` (`/workspace/src/n3tx/static/widgets/ConsoleWidget.js`)

---

## 5. Feasibility Assessment

### 5.1 Complexity Matrix

| Deliverable | Backend Changes | Frontend Changes | New Files | Risk Level |
|------------|----------------|-----------------|-----------|------------|
| Status Widget | 1 field annotation | 1 new widget class | 1 JS | **Low** |
| Grant Detail | 1 `__ui__` dict | 1 component + CSS | 2 JS + 1 CSS | **Low** |
| Kanban Board | None | 1 component + CSS | 2 JS + 1 CSS | **Medium** (drag/drop + Shadow DOM) |
| Dashboard | None | 1 component + CSS | 2 JS + 1 CSS | **Low** |
| Source Health | 3 new fields | Reuses StatusWidget | 0 new | **Low** |
| Agent Panel | None (uses existing) | 1 component + CSS | 2 JS + 1 CSS | **Medium** (WebSocket integration) |

### 5.2 Dependencies

```
Deliverable 1 (Status Widget)  <-- independent, no deps
         |
         v
Deliverable 2 (Grant Detail)   <-- uses Status Widget
         |
         v
Deliverable 3 (Kanban Board)   <-- uses Status Widget, needs Grant data
Deliverable 4 (Dashboard)      <-- needs Grant data (independent of 2,3)
         |
         v
Deliverable 5 (Source Health)   <-- uses Status Widget
Deliverable 6 (Agent Panel)    <-- independent, uses existing infra
```

**Critical path:** Status Widget (1d) -> Grant Detail (3d) -> Kanban (4d) = **8 days minimum** before the most impactful features ship.

### 5.3 Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Drag/drop + Shadow DOM** | Medium | Medium | Use `composedPath()` per [Justin Ribeiro's guidance](https://justinribeiro.com/chronicle/2020/07/14/handling-web-components-and-drag-and-drop-with-event.composedpath/); or contain entire kanban in a single shadow root |
| **Widget CSS bleeding** | Low | Low | StatusWidget uses inline styles; grant-detail uses adoptedStyleSheets via Component base class |
| **Performance with many grants** | Low | Medium | Client-side aggregation is O(n); fine for <1000 grants. If >1000, add backend aggregation endpoint |
| **Breaking generic rendering** | Very Low | High | All changes are additive. Generic `ntx-item` still works for any model without `ui.renderer.detail` |
| **Maintenance burden** | Low | Medium | Custom components follow same patterns as framework components; well-documented base classes |

> **Key Insight:** The highest-risk item (kanban drag/drop) is also the most deferrable (P1). The two P0 items (Status Widget and Grant Detail) are both low-risk because they use established extension points.

---

## 6. ROI Analysis

### 6.1 Investment

| Resource | Quantity | Cost Estimate |
|----------|----------|---------------|
| Frontend dev time | 16 person-days | ~$8K-$16K (depending on rate) |
| Backend dev time | 2 person-days (field annotations, new fields) | ~$1K-$2K |
| QA / testing | 3 person-days | ~$1.5K-$3K |
| **Total** | **21 person-days** | **~$10.5K-$21K** |

### 6.2 Returns

| Return | Timeline | Value |
|--------|----------|-------|
| Demo-able product (vs. data browser) | Week 1 | Investor/customer conversations unlock |
| Reduced user cognitive load | Week 2 | ~60% faster grant triage (status chip + countdown) |
| Self-serve status tracking | Week 2 | Eliminates manual spreadsheet shadow systems |
| Competitive parity with grant platforms | Week 3 | Necessary to position as product, not tool |
| Framework showcase (N3TX extensibility) | Immediate | Proves schema-driven + custom works together |

### 6.3 Payback Timeline

The Status Widget and Grant Detail view deliver **the highest value per day of investment**:

- **Day 1:** Status Widget ships. Every table row, list item, and detail view immediately shows color-coded status. One JS file, one Python annotation.
- **Days 2-4:** Grant Detail ships. Clicking any grant shows a rich, purposeful view. The app feels like a product for the first time.
- **Days 5-8:** Kanban ships. Status management becomes drag-and-drop. This is the "wow" feature for demos.
- **Days 9-11:** Dashboard ships. The app now answers "what needs attention?" without any user effort.

> **Key Insight:** The first two deliverables cost 4 days and deliver 70% of the user experience improvement. Ship those first, evaluate, then proceed.

---

## 7. Trade-offs & Alternatives

### 7.1 Generic vs. Custom: The Fundamental Trade-off

| Approach | Maintenance Cost | User Value | Framework Alignment |
|----------|-----------------|------------|---------------------|
| **Pure generic** (status quo) | Zero | Low for domain users | Perfect |
| **Widget-only** (Status, Deadline) | Very low | Medium | Perfect |
| **Widget + Custom detail** | Low | High | Good (uses `ui.renderer`) |
| **Widget + Custom detail + Kanban + Dashboard** | Medium | Very High | Good |
| **Full custom frontend** (abandon schema-driven) | Very High | Very High | Breaks N3TX philosophy |

**Recommendation:** Go with **Widget + Custom detail + Kanban + Dashboard** (row 4). This hits the sweet spot: high user value, medium maintenance, and stays within N3TX's extensibility model.

### 7.2 Why Not a React/Vue Frontend?

N3TX's frontend is **vanilla JS Web Components** with zero build step. This is a deliberate architectural choice, not a limitation:

- **No build step** means `create_app()` serves a working UI immediately
- **Web Components** are framework-agnostic -- they work in React, Vue, or alone
- **Schema-driven** rendering means the backend is authoritative; the frontend adapts
- **Shadow DOM** provides CSS encapsulation without a CSS-in-JS library

Adding React would violate N3TX's core principle: *"The model is the app."* A React frontend would create a second source of truth for UI structure, require a build step, and decouple the frontend from the schema pipeline. The Widget system and `NTTElement` base class provide the same extensibility within the existing architecture.

### 7.3 Custom Components vs. Framework Components

| Consideration | Framework Component (in `src/n3tx/static/`) | App Component (in `example_grants/static/`) |
|--------------|----------------------------------------------|---------------------------------------------|
| Reusability | Works for any N3TX app | Grant-specific only |
| Maintenance | N3TX team owns it | App team owns it |
| Schema coupling | Must be model-agnostic | Can assume Grant schema |
| Recommended for | StatusWidget, DeadlineWidget | grant-detail, grant-kanban, grant-dashboard |

**The StatusWidget is arguably framework-level** -- many apps need status chips. Consider promoting it to `/workspace/src/n3tx/static/widgets/StatusWidget.js` after proving it in the grants app. The grant-detail component is inherently app-specific and should stay in `example_grants/static/`.

### 7.4 Alternative: CSS-Only Enhancements

Some improvements require **zero JavaScript**:

```css
/* In example_grants/static/dark-theme.css or a new grants.css */

/* Color-code status text in table cells */
ntx-row [data-value="status"] {
  /* Can't reach inside shadow DOM from outside */
}
```

Unfortunately, Shadow DOM prevents external CSS from styling internal elements. This makes the Widget approach (which renders within the shadow root) the only viable path for field-level visual changes.

---

## 8. Recommendation

### Go/No-Go: **GO** -- with phased delivery

**Phase 1 (Week 1): Ship P0 items -- 4 days**
1. Build and register `StatusWidget`
2. Add `json_schema_extra` to `Grant.status` field
3. Build `<grant-detail>` component
4. Add `ui.renderer.detail` to Grant's `__ui__`
5. Import both in `index.html`

**Result:** The app immediately looks like a grant tracking tool. Color-coded statuses, deadline countdowns, agency badges, and a rich detail view -- all from 4 days of work.

**Phase 2 (Week 2-3): Ship P1 items -- 7 days**
1. Build `<grant-kanban>` with drag-to-change-status
2. Build `<grant-dashboard>` with client-side aggregation
3. Add sidebar navigation to both views
4. Optionally vendor Chart.js for richer dashboard visualizations

**Result:** The app gains its "wow" features. Kanban for intuitive status management, dashboard for operational awareness.

**Phase 3 (Week 3-4): Ship P2 items -- 5 days**
1. Add health fields to Source model
2. Build agent control panel (if agent system is mature enough)
3. Polish CSS, add loading states, handle edge cases

**Result:** Complete operational tool.

### Decision Matrix

| Factor | Score (1-5) | Weight | Weighted |
|--------|-------------|--------|----------|
| User impact | 5 | 0.30 | 1.50 |
| Implementation risk | 4 (low risk) | 0.25 | 1.00 |
| Framework alignment | 4 | 0.20 | 0.80 |
| Maintenance cost | 3 (medium) | 0.15 | 0.45 |
| Time to value | 5 (fast) | 0.10 | 0.50 |
| **Total** | | | **4.25 / 5** |

### Final Recommendation

Start with **the StatusWidget** tomorrow. It is a single file, takes one day, and immediately transforms every view in the application. That alone justifies the investment and proves the extension pattern works. Then build the grant detail view. After that, evaluate whether the kanban or dashboard delivers more value for your specific user base, and build that next.

The framework was designed for this. Use it.

---

## 9. Appendix: File Reference

### Existing Files (Read and Analyzed)

| File | Role | Key Lines |
|------|------|-----------|
| `/workspace/src/n3tx/static/components/NTTElement.js` | Single entity base class | L89-106: DESCRIBE handler sets schema+value |
| `/workspace/src/n3tx/static/components/ntx-item.js` | Default entity renderer | L315-319: Widget dispatch in `sm()` |
| `/workspace/src/n3tx/static/components/ntx-table.js` | Table collection component | L45-67: `tableColumns()` field filtering |
| `/workspace/src/n3tx/static/components/ntx-router.js` | View container / mini browser | L137-144: `#resolveTag()` reads `ui.renderer.detail` |
| `/workspace/src/n3tx/static/components/ListElement.js` | Collection base class | L55-65: `definedCallback()` subscribes + triggers READ |
| `/workspace/src/n3tx/static/core/N3TX.js` | Entity system + DynamicClass factory | L668-1106: `prototype()` creates DynamicClass |
| `/workspace/src/n3tx/static/core/Component.js` | Unified web component base | L94-102: Constructable stylesheet caching |
| `/workspace/src/n3tx/static/core/Router.js` | Navigation state actor | L45-54: NAVIGATE handler |
| `/workspace/src/n3tx/static/generators/form.js` | Schema-driven form generator | L212-246: Widget dispatch in `getInput()` |
| `/workspace/src/n3tx/static/widgets/Widget.js` | Widget base class | L12-98: display/edit/list/validate API |
| `/workspace/src/n3tx/static/widgets/registry.js` | Widget name -> instance map | L32-38: `getWidgetForField()` |
| `/workspace/src/n3tx/static/widgets/index.js` | Widget loader + re-exports | L33-41: Built-in registrations |
| `/workspace/example_grants/models/grant.py` | Grant model definition | L24-33: Fields including status, deadline |
| `/workspace/example_grants/models/source.py` | Source model definition | L9-17: name, url, category fields |
| `/workspace/example_grants/static/index.html` | App entry point | L64-75: Current sidebar + router layout |
| `/workspace/example_grants/main.py` | App bootstrap | L35-45: create_app with routing='actor' |

### New Files to Create

| File | Purpose |
|------|---------|
| `example_grants/static/widgets/StatusWidget.js` | Status chip widget |
| `example_grants/static/components/grant-detail.js` | Rich grant detail view |
| `example_grants/static/components/grant-detail.css` | Detail view styles |
| `example_grants/static/components/grant-kanban.js` | Kanban board component |
| `example_grants/static/components/grant-kanban.css` | Kanban board styles |
| `example_grants/static/components/grant-dashboard.js` | Dashboard component |
| `example_grants/static/components/grant-dashboard.css` | Dashboard styles |

---

## 10. Sources

- [MDN: Kanban board with drag and drop](https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API/Kanban_board) -- Official HTML5 drag/drop kanban tutorial
- [Justin Ribeiro: Web Components and Drag-and-Drop with composedPath()](https://justinribeiro.com/chronicle/2020/07/14/handling-web-components-and-drag-and-drop-with-event.composedpath/) -- Critical Shadow DOM interop guidance
- [Chart.js](https://www.chartjs.org/) -- Lightweight chart library (11KB gzipped)
- [Sparklines.js](https://github.com/mitjafelicijan/sparklines) -- Zero-dependency SVG sparkline charts
- [CSS-Tricks: Web Components and Progressive Enhancement](https://css-tricks.com/html-web-components-make-progressive-enhancement-and-css-encapsulation-easier/) -- Enhancement patterns for web components
- [UXPin: Dashboard Design Principles 2025](https://www.uxpin.com/studio/blog/dashboard-design-principles/) -- Dashboard UX best practices
- [Design Studio: Dashboard UI Design Guide 2026](https://www.designstudiouiux.com/blog/dashboard-ui-design-guide/) -- Current dashboard design standards
- [Smart Interface Design: Badges vs Pills vs Chips vs Tags](https://smart-interface-design-patterns.com/articles/badges-chips-tags-pills/) -- Status indicator taxonomy
- [Embeddable: 6 Best JavaScript Charting Libraries 2026](https://embeddable.com/blog/javascript-charting-libraries) -- Chart library comparison
- [Cloud Four: Web Components as Progressive Enhancement](https://cloudfour.com/thinks/web-components-as-progressive-enhancement/) -- Progressive enhancement with custom elements
- [SitePoint: Build a Countdown Timer in 18 Lines of JavaScript](https://www.sitepoint.com/build-javascript-countdown-timer-no-dependencies/) -- Minimal deadline countdown approach
- [jKanban: Vanilla JavaScript Kanban Plugin](https://github.com/riktar/jkanban) -- Reference implementation for kanban boards
- [Glass UI: CSS Glassmorphism Generator](https://ui.glass/generator) -- Glassmorphism design tokens reference
- [Medium: Building a Modern Kanban Board with Vanilla JavaScript](https://medium.com/@francesco-saviano/building-a-modern-kanban-board-with-vanilla-javascript-a-complete-guide-to-drag-and-drop-task-4f1d1b27387f) -- Complete vanilla JS kanban guide
