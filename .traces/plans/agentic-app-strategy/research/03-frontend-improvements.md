# Option 3: Frontend Improvements -- Custom Grant Components, Dashboard Views, and Rich Interactions

**Research Date:** March 4, 2026
**Audience:** Technical CEO + Engineering Leadership
**Application:** Grant Watcher (N3TX v0.10 agentic application)

---

## Executive Summary

Grant Watcher today is a **schema-driven zero-code frontend**. The entire UI renders from JSON Schema at runtime -- no custom JavaScript, no component overrides, zero frontend build step. This is both its greatest strength and its most visible limitation.

The current frontend delivers a generic CRUD experience: table of grants, list of agents, sidebar navigation. It works. But a grant management tool demands **domain-specific affordances**: deadline countdowns, pipeline visualization, funding range displays, agent activity monitoring, and search/filter capabilities that go beyond "click a column header to sort."

This document analyzes exactly what the current frontend stack can and cannot do, maps the gap to concrete component designs, and provides a **prioritized roadmap** that balances domain richness against the maintenance cost of custom code. The central question: **where does schema-driven rendering stop being enough, and where does hand-crafted UI become worth the investment?**

> **Key Insight:** The highest-ROI improvements are not new components -- they are **new widgets and schema annotations** that work within the existing system. A `StatusWidget` with colored badges, a `DeadlineWidget` with countdown logic, and a `CurrencyRangeWidget` would transform the Grant table appearance with **zero new components** and **zero divergence** from the schema-driven philosophy.

---

## Table of Contents

1. [Current Frontend Capabilities Assessment](#-1-current-frontend-capabilities-assessment)
2. [Gap Analysis: What Grant Watcher Needs](#-2-gap-analysis-what-grant-watcher-needs)
3. [The Schema-Driven vs Custom Code Spectrum](#-3-the-schema-driven-vs-custom-code-spectrum)
4. [Dashboard and Analytics Views](#-4-dashboard-and-analytics-views)
5. [Custom Grant Components](#-5-custom-grant-components)
6. [Search, Filter, and Sort](#-6-search-filter-and-sort)
7. [Real-Time and Interactive Features](#-7-real-time-and-interactive-features)
8. [Implementation Roadmap and ROI](#-8-implementation-roadmap-and-roi)
9. [Sources](#-sources)

---

## 1. Current Frontend Capabilities Assessment

### 1.1 What the Stack Already Provides

The N3TX frontend is surprisingly capable for a system with zero application-specific JavaScript. Here is a concrete inventory of what each layer delivers.

| Layer | Component | What It Does | Grant Watcher Usage |
|-------|-----------|-------------|-------------------|
| **Entity System** | `N3TX.js` | Creates DynamicClass from JSON Schema, manages instance registry, handles ATTACH/READ/DESCRIBE lifecycle | Bootstraps `Grant`, `Source`, `AgentActor` types at page load |
| **Base Component** | `Component.js` | Shadow DOM, ResizeObserver, stylesheet adoption, adaptive display (xs-xl), ref resolution | Every `ntx-*` component inherits this |
| **Entity Component** | `NTTElement.js` | Single-entity data lifecycle (UPDATE, DESCRIBE, READ handlers), save(), error handling, validation | Base for `ntx-item`, extensible for custom components |
| **Collection Component** | `ListElement.js` | Collection lifecycle, pagination (loadMore), child stamping, surgical DOM updates | Base for `ntx-list`, `ntx-table` |
| **Item Renderer** | `ntx-item.js` | Adaptive sizes (xs pill -> xl detail), edit/delete, form rendering, method buttons, reply inline | Renders individual Grant/Source/Agent cards |
| **Table Renderer** | `ntx-table.js` | Column-aligned grid, sort by column, inline create row, field-level validation | Main Grant listing view |
| **List Renderer** | `ntx-list.js` | Card grid layout, modal create | Sidebar Agent/Source lists |
| **Form Generator** | `form.js` (Formidable) | Builds forms from schema properties: input types, groups, field order, validation, widget dispatch | Auto-generates edit forms for all models |
| **Widget System** | `Widget.js` + registry | `display()`, `edit()`, `list()` methods per widget type; registered by name, dispatched from schema `ui.widget` | DateWidget, CurrencyWidget, UrlWidget, TextareaWidget active |
| **Router** | `Router.js` + `ntx-router.js` | Hash-based navigation, history stack, back button, dynamic component mounting | Hash navigation between Grant list and detail views |
| **Sidebar** | `ntx-sidebar.js` | Model navigation, accordion expand, lazy-loaded record lists, schema-driven labels, route templates | Left sidebar with Grant/Source/AgentActor sections |
| **Permissions** | `Permissions.js` | Reads schema `access` rules, `canAction()` / `canView()` / `canEdit()` for UI gating | Shows/hides edit/delete buttons based on ABAC rules |

### 1.2 The Grant Model Schema Surface

The Grant model (`example_grants/models/grant.py`) exposes these fields with widget annotations:

```python
class Grant(ActorModel):
    title: str                          # plain text
    agency: str                         # plain text
    deadline: Optional[DateField]       # DateWidget -> calendar picker, "Mar 15, '26" display
    amount_min: Optional[CurrencyField] # CurrencyWidget -> "$10,000.00" display
    amount_max: Optional[CurrencyField] # CurrencyWidget -> "$50,000.00" display
    url: UrlField                       # UrlWidget -> clickable link icon
    description: TextareaField          # TextareaWidget -> expandable text block
    status: str                         # PLAIN STRING -- no widget, no enum, no color
    user_owner: User                    # Ref -> user pill/avatar
```

The schema pipeline converts these into JSON Schema properties with `ui.widget` annotations, which the frontend widget registry dispatches to the correct `Widget` subclass.

### 1.3 Current Layout (index.html)

```
+------------------------------------------------------+
| ntx-topbar  [Grant Watcher v0.10]            [user]  |
+------+-----------------------------------------------+
| ntx- |                                                |
| side |   ntx-router (name="main", hash)               |
| bar  |   +------------------------------------------+ |
|      |   | ntx-table model="Grant" allow-create      | |
| Grant|   |   [title] [agency] [deadline] [status]    | |
| Source   |   row 1...                                | |
| Agent|   |   row 2...                                | |
|      |   |   + Add Grant                             | |
|      |   +------------------------------------------+ |
+------+-----------------------------------------------+
```

The sidebar uses **route templates** -- clicking "Grant" navigates the router to mount `<ntx-table model="Grant" allow-create>`, clicking "Source" mounts `<ntx-table model="Source">`, etc.

### 1.4 What Works Well Today

- **Zero-code CRUD**: Adding a field to the Python model auto-generates the column, input, and validation. Zero frontend changes.
- **Inline create**: The table's bottom row expands into an input form with Enter-to-submit and Escape-to-cancel.
- **Client-side sort**: Click column headers to sort ascending/descending by any field.
- **Widget rendering**: Dates show "Mar 15, '26", amounts show "$10,000.00", URLs show as clickable links.
- **ABAC integration**: Edit/delete buttons appear based on the user's role and ownership.
- **Surgical DOM updates**: Adding/removing entities patches the DOM without full re-render.
- **Pagination**: "Load More" button with server-side `limit`/`offset`.

---

## 2. Gap Analysis: What Grant Watcher Needs

### 2.1 The Gap Table

| Need | Current State | Gap Severity | Fix Category |
|------|--------------|--------------|-------------|
| Status badges (colored) | Plain text "discovered" | **High** | Widget |
| Deadline countdown ("3 days left") | Static date "Mar 15, '26" | **High** | Widget |
| Amount range display ("$10K - $50K") | Two separate columns | **Medium** | Widget or schema |
| Filter by agency/status/date | No filtering at all | **High** | Component + Backend |
| Full-text search | None | **High** | Backend + Component |
| Dashboard summary cards | None | **Medium** | Custom component |
| Grant pipeline / Kanban | None | **Medium** | Custom component |
| Agent run console | None | **Low** | Custom component |
| WebSocket live updates | Backend adapter exists, not wired | **Medium** | Integration |
| Deadline alerts / notifications | None | **Low** | WebSocket + Widget |
| Sort by multiple columns | Single-column sort only | **Low** | Component enhancement |
| Keyboard navigation | Partial (Enter/Escape in create row) | **Low** | Component enhancement |

### 2.2 Severity Assessment

The gaps fall into three tiers:

```
TIER 1: "This looks like a generic database browser"     <- WIDGETS
  - Status badges, deadline countdowns, amount ranges
  - Fix: new Widget subclasses, zero new components
  - Effort: 2-3 days
  - Impact: transforms visual impression immediately

TIER 2: "I can't find what I'm looking for"              <- SEARCH/FILTER
  - Filter bar, full-text search, status quick-filters
  - Fix: ntx-table enhancement + backend query params
  - Effort: 3-5 days
  - Impact: makes the app usable for real workflows

TIER 3: "I want workflow visualization"                   <- CUSTOM COMPONENTS
  - Dashboard, pipeline board, agent console
  - Fix: new custom elements extending NTTElement
  - Effort: 5-15 days
  - Impact: differentiates from generic tools
```

> **Key Insight:** Tier 1 and Tier 2 together take **5-8 days** and deliver **80% of the perceived improvement**. Tier 3 is visually impressive but is only worth building after the foundation is solid.

---

## 3. The Schema-Driven vs Custom Code Spectrum

This is the most important architectural decision in the document. N3TX's philosophy is "the model is the app" -- the backend schema drives everything. Custom frontend code is a departure from that contract. When is it worth it?

### 3.1 The Spectrum

```
SCHEMA-DRIVEN (zero code)          PROGRESSIVE ENHANCEMENT           CUSTOM COMPONENTS
|                                  |                                  |
|  [Widget System]                 |  [ntx-table filter bar]          |  [grant-dashboard]
|  - StatusWidget                  |  - Schema annotation hints       |  [grant-pipeline]
|  - DeadlineWidget                |  - Component reads schema        |  [agent-console]
|  - CurrencyRangeWidget           |  - Falls back gracefully         |
|                                  |                                  |
|  model change -> auto-update     |  model change -> mostly works    |  model change -> may break
|  maintenance: zero               |  maintenance: low                |  maintenance: medium
|  differentiation: low            |  differentiation: medium         |  differentiation: high
```

### 3.2 Decision Framework

| Question | If YES -> | If NO -> |
|----------|----------|---------|
| Can a Widget subclass handle this? | Widget (schema-driven) | Continue |
| Does it apply to all models, not just Grant? | Enhance generic component | Continue |
| Does it need data from multiple models? | Custom component | Continue |
| Is it a single-model view with custom layout? | `ui.renderer` override + custom element | N/A |

### 3.3 The Widget Extension Point (Recommended for Tier 1)

The widget system is the **ideal extension point** for domain-specific rendering without leaving the schema-driven world. Here is why:

```
Backend model         Schema pipeline           Frontend registry        Render

class Grant:          proto_schema.widget()     getWidgetForField()     DateWidget.display()
  deadline: DateField  -> ui.widget: "date"      -> DateWidget           -> <time>Mar 15, '26</time>
  status: str          -> (nothing)              -> (plain text)         -> "discovered"
```

The `status` field renders as plain text because it has no widget annotation. **Adding a `StatusWidget` is a 30-line change** -- one Python class, one JavaScript class, one registry call. The schema pipeline auto-injects `ui.widget: "status"`, the frontend dispatches to `StatusWidget.display()`, and the table cell gets a colored badge. No new components. No divergence from the architecture.

### 3.4 The `ui.renderer` Override Point (Recommended for Tier 3)

For truly custom views, N3TX already supports renderer overrides in the schema:

```python
class Grant(ActorModel):
    __ui__ = {
        'renderer': {
            'item': 'ntx-item',           # default card component
            'detail': 'grant-detail',      # custom detail component
            'list': 'ntx-table',           # default list component
        },
    }
```

The router (`ntx-router.js` line 141) resolves the component tag from `schema.ui.renderer.detail`, so navigating to a Grant would mount `<grant-detail>` instead of `<ntx-item>`. The custom component extends `NTTElement`, gets schema and data via the standard `DESCRIBE` handler, and renders whatever it wants. This is **the intended escape hatch** -- it preserves the data lifecycle while allowing custom rendering.

### 3.5 Comparison: Approaches Used at Other Companies

| Company | Pattern | Outcome |
|---------|---------|---------|
| **Expedia** | [Schema-driven UI](https://medium.com/expedia-group-tech/schema-driven-uis-dd8fdb516120) for configuration tools. Server sends schema, frontend renders. Custom overrides for complex views. | "Incredibly easy to maintain. Testing simplified by altering the schema." |
| **Airbnb** | Server-driven UI for listing pages. Backend controls layout, frontend renders components from a catalog. | Enables A/B testing and iteration without app releases. |
| **Apollo GraphQL** | [SDUI schema design](https://www.apollographql.com/docs/graphos/schema-design/guides/sdui/schema-design) patterns. Backend sends view models, not raw data. | Centralizes business logic, reduces cross-platform duplication. |

N3TX's approach maps closest to Expedia's pattern: the schema carries rendering intent (`ui.widget`, `ui.renderer`, `ui.groups`), and the frontend interprets it. The lesson from all three: **keep generic rendering as the default, layer custom views on top, never replace the schema contract**.

---

## 4. Dashboard and Analytics Views

### 4.1 What a Grant Dashboard Should Show

Based on research from [Good Grants](https://goodgrants.com/resources/articles/5-must-have-metrics-on-your-grant-management-dashboard/), [Foundant](https://www.foundant.com/blog/grants-management-dashboard/), and [iNetSoft](https://www.inetsoft.com/business/bi/kpis-in-grant-management-dashboards/), the essential metrics for a grant management dashboard are:

```
+------------------------------------------------------------------+
|                     GRANT WATCHER DASHBOARD                       |
+------------------------------------------------------------------+
|                                                                   |
|  [  42  ]    [  $1.2M  ]    [  7  ]    [  3 days  ]              |
|  Active       Total          Expiring    Next                     |
|  Grants       Available      Soon        Deadline                 |
|                                                                   |
+------------------------------------------------------------------+
|                          |                                        |
|  PIPELINE                |  GRANTS BY AGENCY                      |
|  +---------+---------+   |  +-------------------------------+     |
|  |Discovered| 28     |   |  | NSF          |||||||||| 12    |     |
|  |Reviewed  | 8      |   |  | NIH          ||||||     8     |     |
|  |Applied   | 4      |   |  | DOE          ||||       6     |     |
|  |Expired   | 2      |   |  | USDA         |||        4     |     |
|  +---------+---------+   |  +-------------------------------+     |
|                          |                                        |
+------------------------------------------------------------------+
|                                                                   |
|  UPCOMING DEADLINES                                               |
|  +-----+------------------------------------------+---------+    |
|  | Mar 7| NSF CAREER Award                        | $500K   |    |
|  | Mar 12| NIH R01 Renewal                        | $250K   |    |
|  | Mar 20| DOE Early Career                       | $150K   |    |
|  +-----+------------------------------------------+---------+    |
|                                                                   |
+------------------------------------------------------------------+
```

### 4.2 Implementation: `<grant-dashboard>` Component

The dashboard needs data from the Grant model -- specifically, **aggregated data**. There are two paths:

**Path A: Client-side aggregation** (recommended for v1)
- Fetch all grants via the existing `READ` endpoint (already paginated)
- Aggregate in JavaScript: count by status, sum amounts, sort by deadline
- Pro: zero backend changes. Con: requires loading all grants into memory.

**Path B: Backend aggregate endpoint** (recommended for scale)
- Add a `/grants/stats` endpoint returning pre-computed aggregates
- Pro: efficient for 1000+ grants. Con: requires new backend endpoint outside the CRUD pattern.

For a grant database under **500 records** (typical for a single organization), Path A is the right choice. Client-side aggregation of 500 flat objects takes <5ms on modern hardware.

### 4.3 Component Architecture

```
<grant-dashboard>   (extends NTTElement)
  |
  +-- DESCRIBE()     receives Grant schema + data
  |
  +-- render()       builds dashboard layout
  |     |
  |     +-- #summaryCards()    -> stat cards (count, total $, deadlines)
  |     +-- #pipelineChart()   -> status distribution bar
  |     +-- #agencyChart()     -> horizontal bar chart
  |     +-- #deadlineList()    -> upcoming deadlines sorted
  |
  +-- update()       surgical DOM patch for stat values
```

**Code example: registering the dashboard as a route template**

```html
<!-- In index.html sidebar -->
<ntx-sidebar router="main">
    <grant-dashboard model="Grant"></grant-dashboard>  <!-- NEW -->
    <ntx-table model="Grant" allow-create></ntx-table>
    <ntx-table model="Source"></ntx-table>
    <ntx-list model="AgentActor"></ntx-list>
</ntx-sidebar>
```

The sidebar's route template system already handles this -- clicking "Dashboard" in the sidebar navigates the router to mount `<grant-dashboard>`.

**Code example: the component skeleton**

```javascript
import { NTTElement } from '../components/NTTElement.js';
import { N3TX } from '../core/N3TX.js';

export class GrantDashboard extends NTTElement {

  get styles() { return new URL('./grant-dashboard.css', import.meta.url).href; }

  definedCallback() {
    // Subscribe to Grant DynamicClass updates
    this.subscribe(this.proto, 'UPDATE', (addrs) => this.#aggregate(addrs));
  }

  #aggregate(addrs) {
    const stats = { total: 0, discovered: 0, reviewed: 0, applied: 0, expired: 0,
                    totalMin: 0, totalMax: 0, deadlines: [] };

    for (const addr of addrs) {
      const entity = N3TX.get(addr);
      if (!entity?.value) continue;
      const g = entity.value;
      stats.total++;
      stats[g.status] = (stats[g.status] || 0) + 1;
      if (g.amount_min) stats.totalMin += g.amount_min;
      if (g.amount_max) stats.totalMax += g.amount_max;
      if (g.deadline) stats.deadlines.push({ title: g.title, deadline: g.deadline,
                                              amount: g.amount_max, agency: g.agency });
    }

    stats.deadlines.sort((a, b) => new Date(a.deadline) - new Date(b.deadline));
    this._stats = stats;
    this.scheduleRender();
  }

  render() {
    if (!this._stats) return;
    const s = this._stats;
    // ... render summary cards, pipeline, deadline list
  }
}

customElements.define('grant-dashboard', GrantDashboard);
```

### 4.4 Data Aggregation: Client vs Server

| Factor | Client-Side | Server-Side |
|--------|------------|-------------|
| **Dataset < 500 rows** | 2-5ms compute, immediate | Unnecessary overhead |
| **Dataset > 5000 rows** | 50ms+, memory pressure | Recommended |
| **Real-time updates** | Recalculates on entity change | Requires cache invalidation |
| **Backend effort** | Zero | New endpoint + aggregation query |
| **Schema-driven** | Yes (reads from N3TX registry) | No (custom endpoint) |

> **Recommendation:** Start with client-side aggregation. Monitor performance. Add a backend `/grants/stats` endpoint only if the grant count exceeds 1000 or aggregation latency exceeds 50ms.

---

## 5. Custom Grant Components

### 5.1 Priority-Ordered Component List

| Component | Purpose | Effort | Depends On |
|-----------|---------|--------|-----------|
| `StatusWidget` | Colored status badges in table/list | **0.5 days** | Nothing |
| `DeadlineWidget` | Countdown display ("3 days left", color-coded) | **0.5 days** | Nothing |
| `CurrencyRangeWidget` | Merged "min-max" display | **0.5 days** | Nothing |
| `<ntx-filter-bar>` | Filter controls for ntx-table | **2-3 days** | Backend query params |
| `<grant-dashboard>` | Summary stats + charts | **3-4 days** | Widget changes |
| `<grant-pipeline>` | Kanban board for status workflow | **3-5 days** | StatusWidget |
| `<grant-detail>` | Enhanced detail view | **1-2 days** | Dashboard |
| `<agent-console>` | Agent run output viewer | **2-3 days** | WebSocket |
| `<source-health>` | Source status indicators | **1 day** | Nothing |

### 5.2 Tier 1: New Widgets (Highest ROI)

#### StatusWidget

A new widget that renders the `status` field as a colored badge instead of plain text.

**Backend (Python) -- 12 lines:**

```python
# src/n3tx/core/widgets/widget.py (or app-level widgets.py)
class StatusField(Widget, name='status', base_type=str):
    """Status enum rendered as colored badge."""
    pass
```

Then in the Grant model:
```python
from n3tx.core.widgets import StatusField

class Grant(ActorModel):
    status: StatusField = Field(default='discovered',
        json_schema_extra={'ui': {
            'config': {
                'options': {
                    'discovered': {'color': '#3b82f6', 'label': 'Discovered'},
                    'reviewed':   {'color': '#f59e0b', 'label': 'Reviewed'},
                    'applied':    {'color': '#10b981', 'label': 'Applied'},
                    'expired':    {'color': '#ef4444', 'label': 'Expired'},
                }
            }
        }})
```

**Frontend (JavaScript) -- 35 lines:**

```javascript
import { Widget } from './Widget.js';

export class StatusWidget extends Widget {

    display(value, config, schema) {
        const options = config?.options || {};
        const opt = options[value] || { color: '#94a3b8', label: value };
        return this.el('span', {
            class: 'widget-status-badge',
            style: `background: ${opt.color}20; color: ${opt.color}; border: 1px solid ${opt.color}40`,
        }, [opt.label || value]);
    }

    edit(value, config, schema, onChange) {
        const select = document.createElement('select');
        const options = config?.options || {};
        for (const [key, opt] of Object.entries(options)) {
            const option = document.createElement('option');
            option.value = key;
            option.textContent = opt.label || key;
            if (key === value) option.selected = true;
            select.appendChild(option);
        }
        if (onChange) select.addEventListener('change', () => onChange(select.value));
        return select;
    }

    list(value, config, schema) {
        const options = config?.options || {};
        const opt = options[value] || {};
        const color = opt.color || '#94a3b8';
        const label = opt.label || value || '';
        return `<span style="background:${color}20;color:${color};border:1px solid ${color}40;
                padding:2px 8px;border-radius:12px;font-size:0.8em">${label}</span>`;
    }
}
```

**Before/After in the Grant table:**

```
BEFORE:                              AFTER:
+--------+--------+---------+       +--------+--------+------------------+
| Title  | Agency | Status  |       | Title  | Agency | Status           |
+--------+--------+---------+       +--------+--------+------------------+
| NSF... | NSF    | discovered      | NSF... | NSF    | [o Discovered]   |  <- blue badge
| NIH... | NIH    | reviewed |      | NIH... | NIH    | [o Reviewed]     |  <- amber badge
| DOE... | DOE    | expired  |      | DOE... | DOE    | [o Expired]      |  <- red badge
+--------+--------+---------+       +--------+--------+------------------+
```

#### DeadlineWidget (Enhanced DateWidget)

Extends the existing DateWidget to show relative time and urgency color.

```javascript
import { DateWidget } from './DateWidget.js';

export class DeadlineWidget extends DateWidget {

    display(value, config, schema) {
        if (!value) return document.createTextNode('No deadline');
        const d = new Date(value);
        if (isNaN(d.getTime())) return document.createTextNode(String(value));

        const now = new Date();
        const diffMs = d - now;
        const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

        let urgency = 'normal';
        if (diffDays < 0) urgency = 'expired';
        else if (diffDays <= 7) urgency = 'urgent';
        else if (diffDays <= 30) urgency = 'soon';

        const relative = diffDays < 0 ? `${Math.abs(diffDays)}d ago`
                       : diffDays === 0 ? 'Today'
                       : diffDays === 1 ? 'Tomorrow'
                       : `${diffDays}d left`;

        const formatted = d.toLocaleDateString(undefined, {
            month: 'short', day: 'numeric', year: '2-digit'
        });

        return this.el('span', { class: `widget-deadline widget-deadline-${urgency}` }, [
            this.el('span', { class: 'deadline-date' }, [formatted]),
            this.el('span', { class: 'deadline-relative' }, [relative]),
        ]);
    }

    list(value, config, schema) {
        if (!value) return '';
        const d = new Date(value);
        if (isNaN(d.getTime())) return String(value);
        const now = new Date();
        const diffDays = Math.ceil((d - now) / (1000 * 60 * 60 * 24));
        const dateStr = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
        if (diffDays < 0) return `<span style="color:#ef4444">${dateStr} (expired)</span>`;
        if (diffDays <= 7) return `<span style="color:#f59e0b">${dateStr} (${diffDays}d)</span>`;
        return `${dateStr} (${diffDays}d)`;
    }
}
```

#### CurrencyRangeWidget

A composite approach for the `amount_min`/`amount_max` pair. Since widgets operate on individual fields, the cleanest solution is a display-only enhancement that abbreviates large numbers:

```javascript
export class CompactCurrencyWidget extends CurrencyWidget {

    list(value, config, schema) {
        if (value == null || value === '') return '';
        const symbol = config?.symbol || '$';
        if (value >= 1_000_000) return `${symbol}${(value / 1_000_000).toFixed(1)}M`;
        if (value >= 1_000) return `${symbol}${(value / 1_000).toFixed(0)}K`;
        return `${symbol}${value.toFixed(0)}`;
    }
}
```

This renders "$50K" instead of "$50,000.00" in table cells -- far more scannable.

### 5.3 Tier 2: Enhanced ntx-table (Filter Bar)

See [Section 6](#-6-search-filter-and-sort) for full details. The filter bar is the single most impactful Tier 2 feature.

### 5.4 Tier 3: Custom Components

#### `<grant-pipeline>` -- Kanban Board

A Kanban board for visualizing grant status workflow. Grants move between columns via drag-and-drop, which triggers a backend UPDATE.

```
+------------------------------------------------------------------+
|  GRANT PIPELINE                                                   |
+------------------------------------------------------------------+
|  Discovered (28)  |  Reviewed (8)   |  Applied (4)  |  Expired   |
|  +-------------+  |  +-----------+  |  +---------+  |  +-------+ |
|  | NSF CAREER  |  |  | NIH R01   |  |  | DOE EC  |  |  | USDA  | |
|  | $500K       |  |  | $250K     |  |  | $150K   |  |  | $50K  | |
|  | Mar 7       |  |  | Mar 12    |  |  | Mar 20  |  |  | Feb 1 | |
|  +-------------+  |  +-----------+  |  +---------+  |  +-------+ |
|  | Another...  |  |               |  |             |  |           |
|  +-------------+  |               |  |             |  |           |
+------------------------------------------------------------------+
```

**Implementation approach:**

The HTML5 Drag and Drop API provides native support for this pattern without any library dependency. According to [MDN's Kanban board tutorial](https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API/Kanban_board), a vanilla JS Kanban board needs only `dragstart`, `dragover`, and `drop` event handlers.

```javascript
import { ListElement } from '../components/ListElement.js';
import { N3TX } from '../core/N3TX.js';
import TX from '../core/TX.js';

export class GrantPipeline extends ListElement {

    static COLUMNS = ['discovered', 'reviewed', 'applied', 'expired'];

    get childTag() { return 'ntx-item'; }
    get childDisplay() { return 'sm'; }

    render() {
        if (!this.schema || !Array.isArray(this.value)) return;

        // Group entities by status
        const groups = {};
        for (const col of GrantPipeline.COLUMNS) groups[col] = [];

        for (const addr of this.value) {
            const entity = N3TX.get(addr);
            if (!entity?.value) continue;
            const status = entity.value.status || 'discovered';
            if (groups[status]) groups[status].push(addr);
        }

        // Render columns
        this.shadowRoot.innerHTML = `
          <div class="pipeline-header"><h1>Grant Pipeline</h1></div>
          <div class="pipeline-board">
            ${GrantPipeline.COLUMNS.map(col => `
              <div class="pipeline-column" data-status="${col}">
                <div class="column-header">
                  <span class="column-title">${col}</span>
                  <span class="column-count">${groups[col].length}</span>
                </div>
                <div class="column-body" data-status="${col}">
                  ${groups[col].map(addr => {
                    const child = this.createChild(addr);
                    child.setAttribute('draggable', 'true');
                    return child.outerHTML;
                  }).join('')}
                </div>
              </div>
            `).join('')}
          </div>
        `;

        this.#bindDragDrop();
    }

    #bindDragDrop() {
        // ... dragstart/dragover/drop handlers that call
        // entity.call('UPDATE', { status: newColumn })
    }
}

customElements.define('grant-pipeline', GrantPipeline);
```

#### `<agent-console>` -- Agent Run Output

The AgentActor model has a `run()` method (`POST /agents/{id}/run`). An agent console component would:

1. Provide a text input for the task prompt
2. Send the `run` method call via `ntx-method`
3. Display streaming output (if WebSocket is wired) or poll for results
4. Show tool call visualization (which tools were invoked, what they returned)

The existing `ConsoleWidget` (renders ANSI terminal output) could be composed into this view.

```
+------------------------------------------+
|  AGENT CONSOLE: Grant Scanner            |
+------------------------------------------+
|  Task: [Scan all sources for new grants] |
|  [Run]                                   |
+------------------------------------------+
|  > Checking source: grants.gov           |
|  > Found 3 new grants                    |
|  > Tool call: grants_create({...})       |
|  > Tool call: grants_create({...})       |
|  > Done. 3 grants added.                 |
+------------------------------------------+
|  Usage: 1,234 tokens | Duration: 4.2s   |
+------------------------------------------+
```

**Effort estimate:** 2-3 days, primarily because the `run()` endpoint currently returns a single JSON blob rather than streaming. WebSocket integration would enable streaming but adds complexity.

#### `<grant-detail>` -- Enhanced Detail View

The default `ntx-item` in `md`/`lg`/`xl` mode already renders a full form with all fields. A custom `<grant-detail>` would add:

- Deadline countdown prominently at top
- Amount range visualization
- Related sources (if a source-grant relationship exists)
- Quick status change buttons
- Agent discovery history ("Found by Grant Scanner on Feb 28")

This component would be registered via `ui.renderer.detail`:

```python
class Grant(ActorModel):
    __ui__ = {
        'renderer': {'detail': 'grant-detail'},
        'field_order': ['title', 'agency', 'deadline', 'amount_min', 'amount_max', 'status', 'url'],
    }
```

The router would automatically mount `<grant-detail>` when navigating to a specific grant.

---

## 6. Search, Filter, and Sort

### 6.1 Current State

**Sorting:** `ntx-table` supports single-column sort (click header to toggle asc/desc). Client-side only, operates on the loaded dataset. Works well for small collections.

**Filtering:** None. Zero filter capability exists today.

**Search:** None.

### 6.2 Architecture Decision: Client-Side vs Server-Side

Per research from [DEV Community](https://dev.to/marmariadev/deciding-between-client-side-and-server-side-filtering-22l9) and [Moesif](https://www.moesif.com/blog/technical/api-design/REST-API-Design-Filtering-Sorting-and-Pagination/), the decision depends on dataset size:

| Dataset Size | Recommendation | Rationale |
|-------------|---------------|-----------|
| < 200 rows | Client-side only | Instant feedback, zero backend changes |
| 200-2000 rows | Hybrid (client filter on loaded data, server for search) | Balance UX speed with memory |
| > 2000 rows | Server-side only | Client memory pressure, stale data risk |

For Grant Watcher, a typical organization tracks **50-500 grants**. **Client-side filtering is the right default**, with server-side search as an upgrade path.

### 6.3 Filter Bar Design

```
+----------------------------------------------------------------------+
|  [Search grants...        ]  Agency: [All v]  Status: [All v]  [x]   |
+----------------------------------------------------------------------+
|  Title           | Agency | Deadline       | Amount    | Status       |
+----------------------------------------------------------------------+
|  NSF CAREER      | NSF    | Mar 7 (3d)     | $500K     | [Discovered] |
|  NIH R01         | NIH    | Mar 12 (8d)    | $250K     | [Reviewed]   |
+----------------------------------------------------------------------+
```

### 6.4 Implementation: `<ntx-filter-bar>` Component

The filter bar should be a **generic component** that reads schema properties to auto-generate filter controls. This keeps it schema-driven while adding filtering capability.

```javascript
/**
 * N3TXFilterBar -- Schema-driven filter controls for collections.
 *
 * Reads schema.properties to generate:
 *   - Text search input (searches all string fields)
 *   - Dropdown filters for fields with ui.widget="status" or enum values
 *   - Date range for date/deadline fields
 *
 * Emits 'filter-change' custom event with filter criteria.
 * Parent component (ntx-table) applies filters to its value array.
 */
export class N3TXFilterBar extends HTMLElement {

    #schema = null;
    #filters = {};

    set schema(s) {
        this.#schema = s;
        this.#render();
    }

    #render() {
        if (!this.#schema?.properties) return;
        const props = this.#schema.properties;
        const filterableFields = [];

        // Auto-detect filterable fields from schema
        for (const [key, def] of Object.entries(props)) {
            if (def.ui?.widget === 'status' && def.ui?.config?.options) {
                filterableFields.push({ key, type: 'select', options: def.ui.config.options });
            } else if (def.ui?.widget === 'date' || def.ui?.widget === 'deadline') {
                filterableFields.push({ key, type: 'daterange' });
            } else if (def.type === 'string' && key !== 'description' && key !== 'id') {
                // Collect unique values for auto-complete (from loaded data)
                filterableFields.push({ key, type: 'text-select' });
            }
        }

        // Build filter controls HTML
        // ... (search input + dropdowns for each filterable field)
    }

    #emitChange() {
        this.dispatchEvent(new CustomEvent('filter-change', {
            detail: { ...this.#filters },
            bubbles: true, composed: true,
        }));
    }
}
```

### 6.5 Integration with ntx-table

The ntx-table component would listen for `filter-change` events and apply client-side filtering:

```javascript
// In NTTTable, after render:
this.shadowRoot.querySelector('ntx-filter-bar')
    ?.addEventListener('filter-change', (e) => {
        this.#applyFilters(e.detail);
    });

#applyFilters(criteria) {
    const filtered = this.value.filter(addr => {
        const entity = N3TX.get(addr);
        if (!entity?.value) return true;
        const v = entity.value;

        // Text search: match against all string fields
        if (criteria.search) {
            const term = criteria.search.toLowerCase();
            const match = Object.values(v).some(val =>
                typeof val === 'string' && val.toLowerCase().includes(term));
            if (!match) return false;
        }

        // Status filter
        if (criteria.status && v.status !== criteria.status) return false;

        // Agency filter
        if (criteria.agency && v.agency !== criteria.agency) return false;

        return true;
    });

    // Re-render with filtered list (keep original for reset)
    this.#filteredValue = filtered;
    this.scheduleRender();
}
```

### 6.6 Server-Side Query Parameters (Backend Enhancement)

For full-text search and large datasets, the backend `list()` endpoint should support query parameters. N3TX's `StorableMixin.list()` already accepts `limit`/`offset`. Adding filter parameters is straightforward:

```
GET /grants?status=discovered&agency=NSF&deadline_before=2026-04-01&search=climate
```

The SQLite storage backend would translate these to SQL WHERE clauses, similar to how the ABAC `sql_filter` already works. The authorization system's `Where` rule provides a pattern for this.

**Effort:** 1-2 days for the backend, primarily in `sqlite_storage.py` and `routes_fastapi.py`.

### 6.7 Sort Enhancement

Current sort is single-column only. Multi-column sort is a nice-to-have but low priority. The bigger improvement is **default sort order** -- grants should sort by deadline (ascending) by default, not by insertion order.

This can be achieved via a schema annotation:

```python
class Grant(ActorModel):
    __ui__ = {
        'default_sort': {'field': 'deadline', 'direction': 'asc'},
    }
```

The ntx-table would read `schema.ui.default_sort` on initial render and apply the sort before displaying rows. **Effort: 2 hours.**

---

## 7. Real-Time and Interactive Features

### 7.1 WebSocket Integration (NetworkWebSocket Already Exists)

The backend already has a fully functional `NetworkWebSocket` adapter (`network_ws.py`). It:
- Accepts WebSocket connections at `/ws` with JWT authentication
- Translates frontend TX messages to backend TX format
- Broadcasts lifecycle events (create/update/delete) to all connected clients
- Handles heartbeat pings

**What is missing:** The frontend does not connect to it. The `HTTP.js` transport layer uses traditional fetch(). Wiring the WebSocket requires:

1. A frontend `NetworkWebSocket` adapter (or extension of `NetworkAdapter.js`)
2. Connecting at page load with the JWT token
3. Routing incoming push events to the correct DynamicClass

```
Current flow (polling):
  [ntx-table] --ATTACH--> [DynamicClass] --READ--> [HTTP GET /grants] --> response --> render

With WebSocket:
  [ntx-table] --ATTACH--> [DynamicClass] --READ--> [WS: {name:READ, target:grants}] --> response --> render
                                          <--PUSH-- [WS: {name:CREATE, data:{...}}]  --> #auto-update
```

### 7.2 What Real-Time Enables

| Feature | Mechanism | User Impact |
|---------|-----------|-------------|
| **New grant notification** | Agent creates grant -> LIFECYCLE broadcast -> WS push -> DynamicClass.CREATE -> table auto-updates | User sees new grants appear without refreshing |
| **Agent status updates** | Agent run progress -> WS push events | Console shows live progress |
| **Collaborative editing** | User A edits grant -> LIFECYCLE broadcast -> User B sees update | Multi-user awareness |
| **Deadline alerts** | Scheduled backend task sends TX when deadline < 24h | Toast notification |

### 7.3 Implementation Effort

| Task | Effort | Dependency |
|------|--------|-----------|
| Frontend WS adapter class | 1 day | None |
| Connect at page load, route events | 0.5 days | WS adapter |
| Backend: wire WS adapter in `create_app()` | 0.5 days | None |
| Toast notifications for push events | 0.5 days | WS adapter |
| Agent console streaming | 1-2 days | WS adapter + agent-console component |

**Total: 3-5 days** to go from "no real-time" to "grants appear instantly when agents create them."

### 7.4 Notification Toast System

The frontend already has a `showToast()` utility (imported from `Toast.js`). Push notifications would reuse this:

```javascript
// On incoming WS LIFECYCLE push:
if (msg.meta?.lifecycle && msg.name === 'CREATE') {
    showToast(`New grant: ${msg.data.title}`, 'info');
}
```

### 7.5 Drag-and-Drop Status Changes

For the Kanban pipeline board, status changes via drag-and-drop would:

1. User drags a grant card from "Discovered" to "Reviewed"
2. `drop` handler reads `data-status` from the target column
3. Component sends UPDATE TX: `{ status: 'reviewed' }`
4. Backend validates and persists
5. If WebSocket is active, other clients see the move instantly

The HTML5 Drag and Drop API is [well-supported](https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API/Kanban_board) and requires no libraries. Total drag-and-drop code is approximately 40 lines.

---

## 8. Implementation Roadmap and ROI

### 8.1 Phase 1: Widget Upgrades (2-3 days, highest ROI)

**Goal:** Transform the visual experience without any new components.

| Task | Effort | Impact |
|------|--------|--------|
| `StatusWidget` (colored badges) | 4 hours | High -- instant visual improvement |
| `DeadlineWidget` (countdown + urgency colors) | 4 hours | High -- makes deadlines scannable |
| `CompactCurrencyWidget` (abbreviations) | 2 hours | Medium -- better table readability |
| `StatusField` Python type + schema annotation | 2 hours | Required for StatusWidget |
| CSS for new widgets | 2 hours | Required for visual polish |
| Default sort by deadline (`ui.default_sort`) | 2 hours | Medium -- most relevant grants first |

**Total: ~2.5 days**

**Deliverable:** The exact same `<ntx-table model="Grant">` now renders colored status badges, deadline countdowns with urgency colors, and compact dollar amounts. Zero new HTML. Zero new components. The model annotation change propagates through the schema pipeline automatically.

### 8.2 Phase 2: Search and Filter (3-5 days, high ROI)

**Goal:** Users can find specific grants without scrolling.

| Task | Effort | Impact |
|------|--------|--------|
| `<ntx-filter-bar>` component | 1.5 days | High -- enables all filtering |
| Integration with `ntx-table` (client-side filter) | 1 day | High -- instant filter feedback |
| Backend query param support (`?status=`, `?agency=`, `?search=`) | 1.5 days | Medium -- scales to large datasets |
| Quick-filter status chips (click to filter) | 0.5 days | Medium -- one-click filtering |

**Total: ~4 days**

**Deliverable:** A filter bar above the grant table with text search, status dropdown, and agency dropdown. Filters apply instantly on the client side. Backend query params available for future scaling.

### 8.3 Phase 3: Dashboard and Real-Time (5-8 days, medium ROI)

**Goal:** Overview analytics and live updates.

| Task | Effort | Impact |
|------|--------|--------|
| `<grant-dashboard>` component | 3 days | Medium -- executive overview |
| Frontend WebSocket adapter | 1.5 days | Medium -- enables real-time |
| Backend WS wiring in `create_app()` | 0.5 days | Required for WS |
| Push notification toasts | 0.5 days | Medium -- awareness of new grants |
| Sidebar integration (dashboard as route template) | 0.5 days | Required for navigation |

**Total: ~6 days**

**Deliverable:** A dashboard view with summary cards (total grants, total funding, upcoming deadlines), pipeline visualization, and agency distribution. New grants from agent scans appear in real-time with toast notifications.

### 8.4 Phase 4: Advanced Components (5-10 days, lower ROI)

**Goal:** Domain-specific workflow tools.

| Task | Effort | Impact |
|------|--------|--------|
| `<grant-pipeline>` Kanban board | 3-5 days | Medium -- visual workflow |
| Drag-and-drop status changes | 1 day | Medium -- satisfying UX |
| `<agent-console>` with streaming | 2-3 days | Low -- developer/admin tool |
| `<source-health>` status panel | 1 day | Low -- monitoring |

**Total: ~7 days**

### 8.5 Cumulative ROI Curve

```
Impact
  ^
  |                                                    /----  Phase 4
  |                                              /----/       (advanced components)
  |                                     /-------/
  |                             /------/                      Phase 3
  |                     /------/                              (dashboard + real-time)
  |              /-----/
  |        /----/                                             Phase 2
  |   /---/                                                   (search + filter)
  |--/                                                        Phase 1
  |                                                           (widgets)
  +---+----------+----------+----------+----------+-----> Days
      3          8          14         20         25
```

**Phase 1 + Phase 2** together take **~7 days** and deliver the majority of visible improvement. This is the recommended stopping point for an MVP. Phases 3 and 4 can be delivered incrementally based on user feedback.

### 8.6 Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Custom components diverge from schema contract | **Medium** | Use `ui.renderer` overrides, extend NTTElement, never bypass schema data flow |
| Widget maintenance when model changes | **Low** | Widgets read schema config at runtime; model field changes auto-propagate |
| Client-side filter performance at scale | **Low** | Hybrid approach: client filter < 500 rows, server filter > 500 |
| WebSocket connection management (reconnect, auth) | **Medium** | Implement exponential backoff reconnect; refresh JWT on reconnect |
| Dashboard data freshness | **Low** | Client-side aggregation recalculates on every UPDATE notification |

### 8.7 What NOT to Build

Things that look tempting but have poor ROI for this application:

- **Custom CSS framework** -- The existing dark/light theme is fine. Polish the widgets instead.
- **Virtual scrolling** -- Grants are paginated at 20/page. Not needed until 1000+ visible rows.
- **Full charting library** (Chart.js, D3) -- CSS-only bars and counters are sufficient for dashboard v1. Add a library only if users demand interactive charts.
- **Offline support / service workers** -- Grant management is an online workflow. Offline adds significant complexity for minimal value.
- **Mobile-first redesign** -- The ResizeObserver adaptive sizing already handles smaller viewports. Dedicated mobile components are premature.

---

## 9. Sources

1. [Good Grants - 5 Must-have metrics on your grant management dashboard](https://goodgrants.com/resources/articles/5-must-have-metrics-on-your-grant-management-dashboard/)
2. [Foundant - Grants Management Dashboard for Strategic Alignment](https://www.foundant.com/blog/grants-management-dashboard/)
3. [iNetSoft - What KPIs Are Used in Grant Management Dashboards?](https://www.inetsoft.com/business/bi/kpis-in-grant-management-dashboards/)
4. [Expedia Group - Schema Driven UIs](https://medium.com/expedia-group-tech/schema-driven-uis-dd8fdb516120)
5. [Apollo GraphQL - Server-Driven UI Schema Design](https://www.apollographql.com/docs/graphos/schema-design/guides/sdui/schema-design)
6. [MDN - Kanban board with drag and drop](https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API/Kanban_board)
7. [Moesif - REST API Design: Filtering, Sorting, and Pagination](https://www.moesif.com/blog/technical/api-design/REST-API-Design-Filtering-Sorting-and-Pagination/)
8. [DEV Community - Deciding Between Client-Side and Server-Side Filtering](https://dev.to/marmariadev/deciding-between-client-side-and-server-side-filtering-22l9)
9. [Lit - Component Composition](https://lit.dev/docs/composition/component-composition/)
10. [DesignRush - 9 Dashboard Design Principles (2026)](https://www.designrush.com/agency/ui-ux-design/dashboard/trends/dashboard-design-principles)
11. [Cloudvara - 10 Essential Grant Management Best Practices for 2025](https://cloudvara.com/grant-management-best-practices/)
12. [Grant Frog - 5 Best Grants Management Software for Nonprofits](https://grantfrog.com/5-best-grants-management-software/)
13. [Good Grants - 6 Grantmaking trends for 2026](https://goodgrants.com/resources/articles/6-grantmaking-trends-for-2026-how-to-maximise-impact-and-efficiency/)
14. [State of HTML 2025 - Web Components](https://2025.stateofhtml.com/en-US/features/web_components/)
15. [Kinsta - A Complete Introduction to Web Components in 2026](https://kinsta.com/blog/web-components/)
16. [Codefinity - Real-Time Notification System with Node.js and WebSockets](https://codefinity.com/blog/Real-Time-Notification-System-with-Node.js-and-WebSockets)
17. [Blackbaud - 10 Tips for Mastering Your Grantmaking Dashboards](https://blog.blackbaud.com/10-tips-for-mastering-your-grantmaking-dashboards/)
18. [Instrumentl - Best Grant Management Software for Nonprofits](https://www.instrumentl.com/blog/best-grant-management-software)
19. [Optimy - Grant Management System: The Ultimate 2026 Guide](https://www.optimy.com/blog-optimy/grant-management-system)

---

*Document generated for the N3TX Grant Watcher project. All code examples reference the existing codebase at `/workspace/src/n3tx/static/` and `/workspace/example_grants/`.*
