# Sprint 2: Frontend Quick Wins + API Integration

**Grant Watcher Application -- N3TX v0.10**
**Sprint Duration: ~6 days**
**Branch: v0.10 (from current v0.9)**

---

## Sprint Overview

Three deliverables, strictly ordered by dependency:

| # | Deliverable | Est. Hours | Days | Dependencies |
|---|------------|-----------|------|-------------|
| 1 | StatusWidget (framework-level widget) | 6h | 1 | None |
| 2 | Grant Detail View (`<grant-detail>`) | 18h | 3 | StatusWidget |
| 3 | GrantsGovAPI Tool Actor | 12h | 2 | None (parallel with #2) |

**Critical path:** Task 1 must complete before Task 2 begins. Task 3 is independent and can run in parallel with Task 2.

---

## Task 1: StatusWidget (Day 1)

### 1.1 Goal

A generic, reusable status widget that renders color-coded chips in display/list mode and a `<select>` dropdown in edit mode. Registered as `'status'` in the widget registry. Not Grant-specific -- any model with a status field and `ui.widget = 'status'` gets colored chips automatically.

### 1.2 Backend: Python `StatusField` Type

**File: `/workspace/src/n3tx/core/widgets/widget.py`** (modify)

Add `StatusField` to the built-in widget field types, after `TextareaField`:

```python
class StatusField(Widget, name='status', base_type=str):
    pass
```

**Why a Widget subclass instead of just `json_schema_extra`:** The `StatusField` Python type gives models a clean annotation (`status: StatusField = Field(...)`) consistent with `CurrencyField`, `DateField`, etc. The `json_schema_extra` approach still works for ad-hoc use, but the Widget subclass is the canonical pattern. Both approaches result in `ui.widget = 'status'` in the JSON Schema -- the Widget subclass just does it via the schema pipeline stage instead of manual `json_schema_extra`.

**Inputs:** Current `widget.py` with 9 built-in types (line 73-108).
**Output:** 10th built-in type `StatusField` added.

**Exact change:**

```python
# After line 108 (TextareaField):
class StatusField(Widget, name='status', base_type=str):
    pass
```

**File: `/workspace/src/n3tx/core/widgets/__init__.py`** (modify)

Add `StatusField` to the public exports. Currently exports:
`UrlField, EmailField, DateField, DateTimeField, MarkdownField, ConsoleField, ReferenceField, CurrencyField, TextareaField`

Add `StatusField` to the import list and `__all__`.

### 1.3 Backend: Annotate Grant.status

**File: `/workspace/example_grants/models/grant.py`** (modify)

Change the `status` field from plain `str` to `StatusField` with `json_schema_extra` providing the color map and allowed values:

```python
from n3tx.core.widgets import UrlField, DateField, CurrencyField, TextareaField, StatusField

# Replace:
#   status: str = Field(default='discovered', description="discovered | reviewed | applied | expired")
# With:
    status: StatusField = Field(
        default='discovered',
        description="Grant lifecycle status",
        json_schema_extra={
            'ui': {
                'config': {
                    'values': ['discovered', 'reviewed', 'applied', 'awarded', 'expired'],
                    'colors': {
                        'discovered': '#6366f1',
                        'reviewed':   '#f59e0b',
                        'applied':    '#22d3c5',
                        'awarded':    '#10b981',
                        'expired':    '#ef4444',
                    }
                }
            }
        }
    )
```

**Why `json_schema_extra` AND `StatusField`:** The `StatusField` annotation causes the widget pipeline stage (`schema_ext.py`) to inject `ui.widget = 'status'`. The `json_schema_extra` adds the `ui.config` block with colors and values. The pipeline stage (`_inject_widgets` at line 163-178 of `schema_ext.py`) skips fields where `ui.widget` is already set, so there is no conflict -- the `json_schema_extra` `ui.config` is merged at schema generation time by Pydantic, and the widget stage adds `ui.widget` if not already present. Since `StatusField` provides the widget name via the pipeline, and `json_schema_extra` provides the config, they complement each other.

**Verification:** After this change, `GET /Grant` should return a schema where `properties.status.ui` contains:
```json
{
    "widget": "status",
    "config": {
        "values": ["discovered", "reviewed", "applied", "awarded", "expired"],
        "colors": {"discovered": "#6366f1", ...}
    }
}
```

### 1.4 Frontend: StatusWidget JS

**File: `/workspace/src/n3tx/static/widgets/StatusWidget.js`** (create)

This is a framework-level widget (lives in `src/n3tx/static/widgets/`, not in `example_grants/`), because status chips are generic and useful for any N3TX application.

```javascript
import { Widget } from './Widget.js';

/**
 * StatusWidget -- Renders status fields as color-coded chips.
 *
 * Config (from schema ui.config):
 *   values: string[]   -- allowed status values (for edit dropdown)
 *   colors: Object     -- { statusValue: '#hexcolor' } mapping
 *
 * Display/list: colored pill chip with uppercase label.
 * Edit: <select> dropdown with all values.
 */
export class StatusWidget extends Widget {

    display(value, config, schema) {
        const color = config?.colors?.[value] || '#555e78';
        return this.el('span', {
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
    }

    edit(value, config, schema, onChange) {
        const values = config?.values || [];
        const select = this.el('select', { class: 'status-select' });
        for (const v of values) {
            const opt = this.el('option', { value: v }, [v]);
            if (v === value) opt.selected = true;
            select.appendChild(opt);
        }
        select.addEventListener('change', () => onChange?.(select.value));
        return select;
    }

    validate(value, config, schema) {
        const values = config?.values;
        if (values && values.length > 0 && value && !values.includes(value)) {
            return `Status must be one of: ${values.join(', ')}`;
        }
        return null;
    }

    list(value, config, schema) {
        const color = config?.colors?.[value] || '#555e78';
        return `<span style="
            display:inline-block; padding:0.15rem 0.5rem; border-radius:100px;
            font-size:0.7rem; font-weight:600; text-transform:uppercase;
            color:white; background:${color};
        ">${this.escape(value || '?')}</span>`;
    }
}
```

**Design decisions:**
- **Inline styles, not CSS classes.** The `list()` method returns an HTML string (not a DOM node), and that string is injected into various shadow roots (`ntx-item`, `ntx-table`, `form.js`). External CSS classes would not penetrate those shadow boundaries. Inline styles are the correct approach, consistent with how `CurrencyWidget.list()` returns formatted strings.
- **`display()` uses `this.el()`.** The `display()` method returns a DOM node (used by `form.js` line 237 which calls `wrapper.appendChild(widgetEl)`). The `el()` helper from the Widget base class creates elements cleanly.
- **`validate()` checks against `config.values`.** This provides client-side enforcement that the status is one of the declared values, consistent with `CurrencyWidget.validate()`.

### 1.5 Frontend: Register StatusWidget

**File: `/workspace/src/n3tx/static/widgets/index.js`** (modify)

Add import and registration:

```javascript
// After line 30 (import TextareaWidget):
import { StatusWidget } from './StatusWidget.js';

// After line 41 (registerWidget('textarea', ...)):
registerWidget('status', new StatusWidget());
```

### 1.6 Tests

#### 1.6.1 Backend: Schema Pipeline Test

**File: `/workspace/src/n3tx/core/tests/unit/test_widgets.py`** (modify, or create if not exists)

Test that `StatusField` annotation produces the correct schema output:

```python
def test_status_field_schema():
    """StatusField annotation should inject ui.widget='status' into schema."""
    from n3tx.core.widgets import StatusField
    from n3tx.core.models.proto_model import ProtoModel
    from pydantic import Field

    class TestModel(ProtoModel):
        __tablename__ = 'test_status'
        status: StatusField = Field(default='active')

    schema = TestModel.schema()
    status_prop = schema['properties']['status']
    assert status_prop['ui']['widget'] == 'status'
```

#### 1.6.2 Backend: Grant Schema Integration Test

**File: `/workspace/example_grants/tests/test_schema_endpoints.py`** (modify)

Add a test that verifies the Grant schema includes the status widget config:

```python
def test_grant_schema_status_widget(self, client, seed_data):
    """Grant schema should expose status as a widget with colors."""
    resp = client.get("/Grant")
    assert resp.status_code == 200
    schema = resp.json()
    status = schema["properties"]["status"]
    assert status["ui"]["widget"] == "status"
    assert "colors" in status["ui"]["config"]
    assert "values" in status["ui"]["config"]
    assert "discovered" in status["ui"]["config"]["values"]
```

#### 1.6.3 Frontend: Manual Verification

No frontend test framework is currently in place. Verification is manual:

1. Start the server: `cd /workspace/example_grants && python main.py`
2. Open `http://localhost:5000/`
3. Verify: Grant list/table rows show colored status chips instead of plain text
4. Verify: Clicking edit on a grant shows a `<select>` dropdown for status
5. Verify: The schema endpoint (`GET /Grant`) returns the correct `ui.widget` + `ui.config`

### 1.7 Files Summary

| File | Action | Description |
|------|--------|-------------|
| `/workspace/src/n3tx/core/widgets/widget.py` | Modify | Add `StatusField` class (2 lines) |
| `/workspace/src/n3tx/core/widgets/__init__.py` | Modify | Export `StatusField` |
| `/workspace/src/n3tx/static/widgets/StatusWidget.js` | Create | JS widget implementation (~60 lines) |
| `/workspace/src/n3tx/static/widgets/index.js` | Modify | Import + register StatusWidget (2 lines) |
| `/workspace/example_grants/models/grant.py` | Modify | Change `status` field annotation |
| `/workspace/example_grants/tests/test_schema_endpoints.py` | Modify | Add status widget schema test |
| `/workspace/src/n3tx/core/tests/unit/test_widgets.py` | Modify/Create | Add StatusField unit test |

---

## Task 2: Grant Detail View (Days 2-4)

### 2.1 Goal

A custom `<grant-detail>` web component that replaces the generic `ntx-item` when navigating to a single Grant entity. It renders:
- Agency badge with distinct styling
- Status chip via StatusWidget
- Deadline countdown with urgency coloring (expired/urgent/soon/ok)
- Amount range display
- Description block
- "View Grant Listing" action button (external link)

Activated via `ui.renderer.detail = 'grant-detail'` in Grant's `__ui__` dict. The existing `ntx-router.js` `#resolveTag()` (line 137-144) already reads this field and creates the component dynamically.

### 2.2 Backend: Add `__ui__` to Grant Model

**File: `/workspace/example_grants/models/grant.py`** (modify)

Add the `__ui__` ClassVar and the `ClassVar` import:

```python
from typing import ClassVar, Optional

class Grant(ActorModel):
    # ... existing ClassVars ...
    __ui__: ClassVar[dict] = {
        'renderer': {
            'detail': 'grant-detail',
            'item': 'ntx-item',
        },
        'field_order': ['title', 'agency', 'status', 'deadline',
                        'amount_min', 'amount_max', 'url', 'description'],
    }
    # ... existing fields ...
```

**What this does:** When a user clicks a Grant row in the table, `ntx-router.js` receives a NAVIGATE TX with the entity address (e.g., `Grant/5`). `#resolveTag('Grant')` (line 137-144) looks up the DynamicClass, reads `schema.ui.renderer.detail`, and gets `'grant-detail'`. It then creates `<grant-detail ref="http://.../grants/5" display="lg">` and mounts it in the router content area.

**Verification:** After this change, `GET /Grant` should return a schema where `ui.renderer.detail` is `'grant-detail'`.

### 2.3 Frontend: Component File

**File: `/workspace/example_grants/static/components/grant-detail.js`** (create)

This is a Grant-specific component, so it lives in the app's static directory, not in the framework.

```javascript
import { NTTElement } from '/components/NTTElement.js';
import { getWidgetForField } from '/widgets/index.js';
import { permissions } from '/utils/Permissions.js';
import TX from '/core/TX.js';

class GrantDetail extends NTTElement {

    get styles() { return '/components/grant-detail.css'; }

    render() {
        if (!this.schema || !this.value) return;
        const v = this.value;
        const props = this.schema.properties || {};

        // ── Deadline computation ──
        const deadline = v.deadline ? new Date(v.deadline) : null;
        const now = new Date();
        const daysLeft = deadline ? Math.ceil((deadline - now) / 86400000) : null;
        const urgency = daysLeft === null ? 'none'
            : daysLeft < 0 ? 'expired'
            : daysLeft <= 7 ? 'urgent'
            : daysLeft <= 30 ? 'soon' : 'ok';

        const deadlineDisplay = deadline
            ? deadline.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
            : 'No deadline';
        const daysDisplay = daysLeft !== null
            ? (daysLeft < 0 ? 'Expired' : `${daysLeft}d remaining`)
            : '';

        // ── Status chip via widget ──
        const statusWr = getWidgetForField(props.status || {});
        const statusHtml = (statusWr.widget && props.status?.ui?.widget)
            ? statusWr.widget.list(v.status, statusWr.config, props.status)
            : `<span>${v.status || 'unknown'}</span>`;

        // ── Amount range ──
        const fmt = (n) => n != null ? `$${Number(n).toLocaleString()}` : '?';
        const amountRange = `${fmt(v.amount_min)} - ${fmt(v.amount_max)}`;

        // ── Actions ──
        const canUpdate = permissions.canAction(this.schema?.access, 'update', v);
        const canDelete = permissions.canAction(this.schema?.access, 'delete', v);

        this.shadowRoot.innerHTML = `
            <div class="grant-detail">
                <header class="grant-header">
                    <div class="grant-meta">
                        <span class="agency-badge">${v.agency || 'Unknown Agency'}</span>
                        ${statusHtml}
                    </div>
                    <h1 class="grant-title">${v.title || 'Untitled Grant'}</h1>
                    ${canUpdate || canDelete ? `
                    <div class="header-actions">
                        ${canUpdate ? '<button class="edit-btn" title="Edit">Edit</button>' : ''}
                        ${canDelete ? '<button class="delete-btn" title="Delete">Delete</button>' : ''}
                    </div>` : ''}
                </header>

                <div class="grant-body">
                    <section class="grant-main">
                        <div class="grant-description">${v.description || '<em>No description available.</em>'}</div>
                        ${v.url ? `<div class="grant-actions">
                            <a href="${v.url}" target="_blank" rel="noopener" class="apply-btn">View Grant Listing</a>
                        </div>` : ''}
                    </section>

                    <aside class="grant-sidebar">
                        <div class="sidebar-card">
                            <div class="meta-row">
                                <span class="meta-label">Deadline</span>
                                <span class="meta-value deadline-${urgency}">
                                    ${deadlineDisplay}
                                    ${daysDisplay ? `<span class="days-left">${daysDisplay}</span>` : ''}
                                </span>
                            </div>
                            <div class="meta-row">
                                <span class="meta-label">Award Range</span>
                                <span class="meta-value">${amountRange}</span>
                            </div>
                            <div class="meta-row">
                                <span class="meta-label">Status</span>
                                <span class="meta-value">${statusHtml}</span>
                            </div>
                            <div class="meta-row">
                                <span class="meta-label">Agency</span>
                                <span class="meta-value">${v.agency || '?'}</span>
                            </div>
                        </div>
                    </aside>
                </div>
            </div>
        `;
        this._rendered = true;
        this.#bindEvents();
    }

    #bindEvents() {
        this.shadowRoot.querySelector('.edit-btn')?.addEventListener('click', () => {
            // Navigate to edit -- for now, open the generic ntx-item in edit mode
            // Future: inline edit form within grant-detail
        });
        this.shadowRoot.querySelector('.delete-btn')?.addEventListener('click', () => {
            this.deleteItem?.();
        });
    }
}

customElements.define('grant-detail', GrantDetail);
```

**Import path strategy:** The `example_grants/static/` directory is served as explicit routes by the backend (`backend.py` line 139-156). Files in `example_grants/static/components/` are served at `/components/grant-detail.js`. Meanwhile, the framework's static directory (`src/n3tx/static/`) is mounted at `/` as a catch-all. So:
- `/components/NTTElement.js` resolves to `src/n3tx/static/components/NTTElement.js` (framework catch-all)
- `/components/grant-detail.js` resolves to `example_grants/static/components/grant-detail.js` (explicit route, higher priority)
- `/components/grant-detail.css` resolves to `example_grants/static/components/grant-detail.css` (explicit route)

This means imports using absolute paths from root (`/components/NTTElement.js`) will work correctly for both framework and app files. The app's explicit routes take precedence for app files; everything else falls through to the framework catch-all.

### 2.4 Frontend: Component Stylesheet

**File: `/workspace/example_grants/static/components/grant-detail.css`** (create)

The CSS is loaded via the `Component` base class's constructable stylesheet mechanism (`#adoptStylesheet()` in `Component.js` line 266-287). The `get styles()` getter returns a URL; the Component fetches it, creates a `CSSStyleSheet`, and adopts it into the shadow root. Cached globally across instances.

```css
/* grant-detail.css -- Shadow DOM styles for <grant-detail> */

:host {
    display: block;
    max-width: 900px;
    margin: 0 auto;
}

.grant-detail {
    background: var(--card-bg, #1a1a2e);
    border-radius: 12px;
    overflow: hidden;
}

/* ── Header ── */
.grant-header {
    padding: 1.5rem 2rem 1rem;
    border-bottom: 1px solid var(--border, rgba(255,255,255,0.06));
}

.grant-meta {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
}

.agency-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.75rem;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    background: var(--accent, #22d3c5);
    color: var(--bg, #0f0f23);
}

.grant-title {
    margin: 0;
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--fg, #e8e8f0);
    line-height: 1.3;
}

.header-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.75rem;
}

.header-actions button {
    padding: 0.4rem 1rem;
    border-radius: 6px;
    border: 1px solid var(--border, rgba(255,255,255,0.1));
    background: transparent;
    color: var(--fg-muted, #a0a0b8);
    font-size: 0.8rem;
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
}
.header-actions button:hover {
    background: var(--hover-bg, rgba(255,255,255,0.05));
    color: var(--fg, #e8e8f0);
}
.header-actions .delete-btn:hover {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
}

/* ── Body layout ── */
.grant-body {
    display: grid;
    grid-template-columns: 1fr 280px;
    gap: 2rem;
    padding: 1.5rem 2rem 2rem;
}

@media (max-width: 700px) {
    .grant-body {
        grid-template-columns: 1fr;
    }
}

/* ── Main content ── */
.grant-main {
    min-width: 0;
}

.grant-description {
    color: var(--fg-muted, #a0a0b8);
    font-size: 0.95rem;
    line-height: 1.7;
    white-space: pre-wrap;
}

.grant-actions {
    margin-top: 1.5rem;
}

.apply-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.6rem 1.2rem;
    border-radius: 8px;
    background: var(--accent, #22d3c5);
    color: var(--bg, #0f0f23);
    font-weight: 600;
    font-size: 0.9rem;
    text-decoration: none;
    transition: opacity 0.15s;
}
.apply-btn:hover {
    opacity: 0.85;
}

/* ── Sidebar ── */
.sidebar-card {
    background: var(--card-bg-alt, rgba(255,255,255,0.02));
    border: 1px solid var(--border, rgba(255,255,255,0.06));
    border-radius: 10px;
    padding: 1.25rem;
}

.meta-row {
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--border, rgba(255,255,255,0.04));
}
.meta-row:last-child {
    border-bottom: none;
}

.meta-label {
    display: block;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--fg-dim, #6a6a80);
    margin-bottom: 0.3rem;
}

.meta-value {
    display: block;
    font-size: 0.95rem;
    color: var(--fg, #e8e8f0);
}

.days-left {
    display: block;
    font-size: 0.8rem;
    margin-top: 0.15rem;
}

/* ── Deadline urgency colors ── */
.deadline-expired { color: #ef4444; }
.deadline-expired .days-left { color: #ef4444; font-weight: 600; }

.deadline-urgent { color: #f59e0b; }
.deadline-urgent .days-left { color: #f59e0b; font-weight: 600; }

.deadline-soon { color: #22d3c5; }
.deadline-soon .days-left { color: #22d3c5; }

.deadline-ok { color: var(--fg, #e8e8f0); }
.deadline-ok .days-left { color: var(--fg-muted, #a0a0b8); }

.deadline-none { color: var(--fg-dim, #6a6a80); }
```

### 2.5 Frontend: Load Component in index.html

**File: `/workspace/example_grants/static/index.html`** (modify)

Add two things:

1. **Modulepreload hint** in `<head>` (after the existing widget modulepreloads, around line 59):

```html
<!-- App-specific components -->
<link rel="modulepreload" href="./components/grant-detail.js">
```

2. **Import in the module script** (after the existing component imports, around line 94):

```javascript
// App-specific components
import './components/grant-detail.js';
```

**Why both modulepreload AND import:** The `modulepreload` eliminates the network waterfall (the browser starts fetching the JS before it is needed). The `import` actually executes the module (which calls `customElements.define('grant-detail', GrantDetail)`), registering the element so it is available when `ntx-router` creates it.

### 2.6 Frontend: CSS Preload

**File: `/workspace/example_grants/static/index.html`** (modify)

Add a CSS preload hint in the `<head>` section (after the existing preloads, around line 19):

```html
<link rel="preload" href="./components/grant-detail.css" as="style">
```

### 2.7 Tests

#### 2.7.1 Backend: Schema Test

**File: `/workspace/example_grants/tests/test_schema_endpoints.py`** (modify)

Add a test verifying the `ui.renderer.detail` field:

```python
def test_grant_schema_detail_renderer(self, client, seed_data):
    """Grant schema should specify grant-detail as the detail renderer."""
    resp = client.get("/Grant")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["ui"]["renderer"]["detail"] == "grant-detail"
    assert schema["ui"]["renderer"]["item"] == "ntx-item"
```

#### 2.7.2 Backend: Field Order Test

```python
def test_grant_schema_field_order(self, client, seed_data):
    """Grant schema should include field_order in ui config."""
    resp = client.get("/Grant")
    schema = resp.json()
    assert "field_order" in schema["ui"]
    assert schema["ui"]["field_order"][0] == "title"
```

#### 2.7.3 Frontend: Manual Verification Checklist

1. Navigate to `http://localhost:5000/`
2. The grant table loads normally (StatusWidget shows colored chips in table cells)
3. Click a grant row -- `ntx-router` creates `<grant-detail>` (not `<ntx-item>`)
4. Verify the detail view shows:
   - Agency badge (teal pill with agency name)
   - Status chip (colored, from StatusWidget)
   - Title (large heading)
   - Description text
   - Sidebar with: deadline + countdown, award range, status, agency
   - "View Grant Listing" button linking to the grant URL
5. Verify deadline urgency colors:
   - Expired grants: red text
   - Grants with deadline < 7 days: amber text
   - Grants with deadline < 30 days: teal text
   - Other grants: default text color
6. Click "Back" button in router chrome -- returns to table
7. Verify responsive layout: narrow the browser window below 700px -- sidebar stacks below main content

### 2.8 Files Summary

| File | Action | Description |
|------|--------|-------------|
| `/workspace/example_grants/models/grant.py` | Modify | Add `__ui__` dict with `renderer.detail` and `field_order` |
| `/workspace/example_grants/static/components/grant-detail.js` | Create | Custom detail component (~120 lines) |
| `/workspace/example_grants/static/components/grant-detail.css` | Create | Shadow DOM styles (~180 lines) |
| `/workspace/example_grants/static/index.html` | Modify | Add modulepreload + import + CSS preload (3 lines) |
| `/workspace/example_grants/tests/test_schema_endpoints.py` | Modify | Add renderer + field_order tests |

---

## Task 3: GrantsGovAPI Tool Actor (Days 2-3, parallel with Task 2)

### 3.1 Goal

A non-storable `ActorModel` that wraps the grants.gov REST API (no authentication required). Two `@expose_route` methods: `search()` and `fetch()`. Auto-discovered as agent tools via `discover_tools()` when an agent lists `"grants_gov_api"` in its tool addresses.

### 3.2 Backend: Model Definition

**File: `/workspace/example_grants/models/grants_gov_api.py`** (create)

Follows the exact `WebTools` pattern from `/workspace/example_grants/models/web_tools.py`:

```python
from __future__ import annotations
from typing import ClassVar

from n3tx.core.models.actor_model import ActorModel
from n3tx.core.utils.decorators import expose_route
from n3tx.core.utils.erroring import MethodError
from n3tx.core.authorize import AUTHENTICATED


class GrantsGovAPI(ActorModel):
    """Tool actor wrapping the grants.gov REST API.

    Provides structured grant search and detail retrieval. No authentication
    required for grants.gov. Registered as a non-storable actor so
    discover_tools() can find its @expose_route methods.

    API docs: https://grants.gov/api/api-guide
    """

    __tablename__: ClassVar[str] = 'grants_gov_api'
    __storable__: ClassVar[bool] = False

    BASE_URL: ClassVar[str] = 'https://api.grants.gov/v1/api'

    @expose_route('/search', methods=['POST'], access=AUTHENTICATED)
    async def search(
        self,
        keyword: str = '',
        agency: str = '',
        status: str = 'posted',
        rows: int = 25,
        start_record: int = 1,
    ) -> dict:
        """Search grants.gov for funding opportunities.

        Args:
            keyword: Search term (title, description, etc.)
            agency: Filter by agency code (e.g. 'NSF', 'DOE', 'NIH')
            status: Opportunity status filter: posted|forecasted|closed|archived
            rows: Number of results to return (max 500, default 25)
            start_record: Pagination offset (1-indexed)

        Returns:
            dict with 'total' count and 'opportunities' list.
        """
        import httpx

        rows = min(max(1, rows), 500)

        payload = {
            'keyword': keyword,
            'rows': rows,
            'startRecordNum': start_record,
            'oppStatuses': status,
        }
        if agency:
            payload['agencies'] = agency

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f'{self.BASE_URL}/search2',
                    json=payload,
                )
                resp.raise_for_status()
        except httpx.TimeoutException:
            raise MethodError("grants.gov API timeout", 504)
        except httpx.HTTPStatusError as e:
            raise MethodError(f"grants.gov API error: {e.response.status_code}", 502)
        except httpx.RequestError as e:
            raise MethodError(f"grants.gov connection error: {e}", 502)

        data = resp.json()
        hits = data.get('data', {}).get('oppHits', [])
        total = data.get('data', {}).get('hitCount', 0)

        return {
            'total': total,
            'opportunities': [
                {
                    'id': h.get('id'),
                    'number': h.get('number', ''),
                    'title': h.get('title', ''),
                    'agency': h.get('agencyCode', ''),
                    'status': h.get('oppStatus', ''),
                    'open_date': h.get('openDate'),
                    'close_date': h.get('closeDate'),
                    'description': h.get('description', '')[:500],
                }
                for h in hits
            ],
        }

    @expose_route('/fetch', methods=['POST'], access=AUTHENTICATED)
    async def fetch(self, opportunity_id: str) -> dict:
        """Fetch full details for a specific grants.gov opportunity.

        Args:
            opportunity_id: The grants.gov opportunity ID.

        Returns:
            dict with full opportunity details.
        """
        import httpx

        if not opportunity_id:
            raise MethodError("opportunity_id is required", 400)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f'{self.BASE_URL}/fetchOpportunity/{opportunity_id}',
                )
                resp.raise_for_status()
        except httpx.TimeoutException:
            raise MethodError("grants.gov API timeout", 504)
        except httpx.HTTPStatusError as e:
            raise MethodError(f"grants.gov API error: {e.response.status_code}", 502)
        except httpx.RequestError as e:
            raise MethodError(f"grants.gov connection error: {e}", 502)

        return resp.json()
```

**Design decisions:**
- **`MethodError` for all error cases.** Per CLAUDE.md's "200-OK error" case study, errors must be returned as proper HTTP errors, not success responses with error strings. `MethodError` is caught by the route layer and converted to an `HTTPException` with the correct status code.
- **`httpx` imported inside methods.** Follows the `WebTools` pattern (line 18 of `web_tools.py`). Lazy import keeps the module lightweight and avoids import errors if `httpx` is not installed.
- **`rows` capped at 500.** The grants.gov API has limits; this provides a safe ceiling.
- **Description truncated to 500 chars.** The search endpoint returns summaries, not full descriptions. Prevents bloated responses that waste agent tokens.
- **No authentication required for grants.gov.** Per the [grants.gov API guide](https://grants.gov/api/api-guide), the `search2` and `fetchOpportunity` endpoints are public.

### 3.3 Backend: Register Model

**File: `/workspace/example_grants/models/__init__.py`** (modify)

Add the import and export:

```python
from .user import User
from .grant import Grant
from .source import Source
from .web_tools import WebTools
from .grants_gov_api import GrantsGovAPI

__all__ = ["User", "Grant", "Source", "WebTools", "GrantsGovAPI"]
```

**File: `/workspace/example_grants/main.py`** (modify)

Add `GrantsGovAPI` to the models list:

```python
from models import User, Grant, Source, WebTools, GrantsGovAPI

# ... in create_app call:
app = create_app(
    models=[User, Grant, Source, WebTools, GrantsGovAPI, AgentTool, AgentActor],
    # ... rest unchanged
)
```

### 3.4 Agent Integration: Adding tools to the Scanner Agent

The Grant Scanner agent already has tools pointing to `grants`, `sources`, and `web_tools`. To make `GrantsGovAPI` available, a new `AgentTool` record needs to be created linking the scanner agent to the `grants_gov_api` actor address.

**File: `/workspace/example_grants/seed.py`** (modify, if it exists) or via manual API call:

```bash
# After the server starts with the new model registered:
TOKEN=$(curl -s -X POST http://localhost:5000/users/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"alice123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Add grants_gov_api tool to the scanner agent (agent ID 1)
curl -X POST http://localhost:5000/agents/1/agent_tools \
  -H 'Content-Type: application/json' \
  -H "x-access-token: $TOKEN" \
  -d '{"target": "grants_gov_api", "description": "Search grants.gov API"}'
```

**Alternatively**, add to `conftest.py`'s `_seed_agent()` function for test seeding:

```python
# In _seed_agent(), after existing tool_data:
tool_data = [
    {"target": "grants", "description": "Grant CRUD"},
    {"target": "sources", "description": "Source listing"},
    {"target": "web_tools", "description": "Web scraping"},
    {"target": "grants_gov_api", "description": "Search grants.gov API"},  # NEW
]
```

### 3.5 How discover_tools() Finds the Methods

The tool discovery flow (no code changes needed):

1. Agent's `tools` field contains `AgentTool` records with `target = "grants_gov_api"`
2. `discover_tools(["grants_gov_api"], matrix)` in `/workspace/src/n3tx/core/agents/tools.py`:
   - Finds `GrantsGovAPI` as a child of Matrix (registered via `ActorMeta.__new__`)
   - Reads `GrantsGovAPI.schema()` which includes `methods.search` and `methods.fetch`
   - Generates `ToolSpec` objects: `grants_gov_api_search` and `grants_gov_api_fetch`
3. `create_tool_function(spec)` generates Python callables that route through the actor system
4. The LLM agent can now call `grants_gov_api_search(keyword="stem education", agency="NSF")`

### 3.6 Tests

#### 3.6.1 Unit: Model Schema Test

**File: `/workspace/example_grants/tests/test_schema_endpoints.py`** (modify)

```python
def test_grants_gov_api_schema(self, client, seed_data):
    """GrantsGovAPI should expose search and fetch methods in schema."""
    resp = client.get("/GrantsGovAPI")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["__name__"] == "GrantsGovAPI"
    assert schema["__tablename__"] == "grants_gov_api"
    methods = schema.get("methods", {})
    assert "search" in methods
    assert "fetch" in methods
    # search should have keyword, agency, status, rows params
    search_params = methods["search"].get("parameters", {})
    assert "keyword" in search_params
    assert "agency" in search_params
```

#### 3.6.2 Integration: API Endpoint Test (Mocked)

**File: `/workspace/example_grants/tests/test_grants_gov_api.py`** (create)

```python
"""Tests for the GrantsGovAPI tool actor."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from helpers import auth_header


class TestGrantsGovAPISearch:
    """Test the /grants_gov_api/search endpoint."""

    def test_search_requires_auth(self, client):
        """Search endpoint should require authentication."""
        resp = client.post("/grants_gov_api/search", json={"keyword": "stem"})
        assert resp.status_code in (401, 403)

    @patch('httpx.AsyncClient')
    def test_search_returns_opportunities(self, mock_client_cls, client, alice_token):
        """Search should return parsed opportunity data from grants.gov."""
        # Mock the httpx response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'data': {
                'hitCount': 1,
                'oppHits': [{
                    'id': '350211',
                    'number': 'PD-24-7980',
                    'title': 'CISE Research Initiation',
                    'agencyCode': 'NSF',
                    'oppStatus': 'posted',
                    'openDate': '2025-01-01',
                    'closeDate': '2026-06-15',
                    'description': 'Computer science research.',
                }]
            }
        }
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client_instance

        resp = client.post(
            "/grants_gov_api/search",
            json={"keyword": "CISE", "agency": "NSF"},
            headers=auth_header(alice_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["opportunities"]) == 1
        assert data["opportunities"][0]["agency"] == "NSF"

    @patch('httpx.AsyncClient')
    def test_search_handles_timeout(self, mock_client_cls, client, alice_token):
        """Search should return 504 on timeout."""
        import httpx

        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client_instance

        resp = client.post(
            "/grants_gov_api/search",
            json={"keyword": "test"},
            headers=auth_header(alice_token),
        )
        assert resp.status_code in (504, 400, 500)  # MethodError translated


class TestGrantsGovAPIFetch:
    """Test the /grants_gov_api/fetch endpoint."""

    def test_fetch_requires_auth(self, client):
        """Fetch endpoint should require authentication."""
        resp = client.post("/grants_gov_api/fetch",
                          json={"opportunity_id": "350211"})
        assert resp.status_code in (401, 403)

    def test_fetch_requires_opportunity_id(self, client, alice_token):
        """Fetch should error without an opportunity_id."""
        resp = client.post(
            "/grants_gov_api/fetch",
            json={"opportunity_id": ""},
            headers=auth_header(alice_token),
        )
        assert resp.status_code in (400, 422, 500)
```

**Mocking strategy:** The tests mock `httpx.AsyncClient` to avoid making real network calls to grants.gov. This keeps tests fast, deterministic, and CI-friendly. The mock returns realistic response structures matching the grants.gov API format.

**Note on actor routing:** Since `routing='actor'`, the route goes through `NetworkAPI -> Matrix -> GrantsGovAPI.handler()`. The handler dispatches to the `@expose_route` method. The mock must intercept at the `httpx` level (inside the method), not at the route level.

#### 3.6.3 Test: Tool Discovery Integration

**File: `/workspace/example_grants/tests/test_grants_gov_api.py`** (same file, additional class)

```python
class TestGrantsGovAPIToolDiscovery:
    """Verify GrantsGovAPI is discoverable as agent tools."""

    def test_model_registered(self, client, seed_data):
        """GrantsGovAPI should be in registered_models."""
        from n3tx.core.utils.registrar import registered_models
        assert 'grants_gov_api' in registered_models

    def test_schema_has_methods(self, client, seed_data):
        """GrantsGovAPI schema methods should be discoverable."""
        from models import GrantsGovAPI
        schema = GrantsGovAPI.schema()
        assert 'methods' in schema
        assert 'search' in schema['methods']
        assert 'fetch' in schema['methods']
```

### 3.7 Update conftest.py

**File: `/workspace/example_grants/tests/conftest.py`** (modify)

Update imports to include `GrantsGovAPI`:

```python
from models import User, Grant, Source, WebTools, GrantsGovAPI
```

And add the `grants_gov_api` tool to the scanner agent seed:

```python
# In _seed_agent(), update tool_data:
tool_data = [
    {"target": "grants", "description": "Grant CRUD"},
    {"target": "sources", "description": "Source listing"},
    {"target": "web_tools", "description": "Web scraping"},
    {"target": "grants_gov_api", "description": "Search grants.gov API"},
]
```

### 3.8 Files Summary

| File | Action | Description |
|------|--------|-------------|
| `/workspace/example_grants/models/grants_gov_api.py` | Create | GrantsGovAPI ActorModel (~110 lines) |
| `/workspace/example_grants/models/__init__.py` | Modify | Add GrantsGovAPI import + export |
| `/workspace/example_grants/main.py` | Modify | Add GrantsGovAPI to models list |
| `/workspace/example_grants/tests/test_grants_gov_api.py` | Create | Mocked API + schema tests (~100 lines) |
| `/workspace/example_grants/tests/test_schema_endpoints.py` | Modify | Add GrantsGovAPI schema test |
| `/workspace/example_grants/tests/conftest.py` | Modify | Import GrantsGovAPI + add to seed tools |

---

## Execution Schedule

```
Day 1 (Task 1: StatusWidget)
├── 1.2  Backend: StatusField Python type                    (30 min)
├── 1.3  Backend: Grant.status annotation                    (30 min)
├── 1.4  Frontend: StatusWidget.js                           (2 hours)
├── 1.5  Frontend: Register in index.js                      (15 min)
├── 1.6  Tests: schema pipeline + integration                (1.5 hours)
└── 1.7  Manual verification                                 (1 hour)
         ✓ StatusWidget complete — all views show colored status chips

Day 2 (Task 2: Grant Detail — start; Task 3: GrantsGovAPI — start)
├── 2.2  Backend: Add __ui__ to Grant model                  (30 min)
├── 2.3  Frontend: grant-detail.js (first pass)              (3 hours)
├── 3.2  Backend: GrantsGovAPI model (parallel)              (3 hours)
└── 3.3  Backend: Register in __init__.py + main.py          (30 min)

Day 3 (Task 2: Grant Detail — CSS + polish; Task 3: GrantsGovAPI — tests)
├── 2.4  Frontend: grant-detail.css                          (2 hours)
├── 2.5  Frontend: index.html imports                        (15 min)
├── 3.6  Tests: GrantsGovAPI schema + mocked API             (3 hours)
└── 3.7  Update conftest.py                                  (30 min)
         ✓ GrantsGovAPI complete

Day 4 (Task 2: Grant Detail — integration + test + polish)
├── 2.7  Tests: schema + manual verification                 (2 hours)
├── 2.x  Polish: responsive layout, edge cases               (2 hours)
├── 2.x  Fix any issues from manual testing                  (2 hours)
└── Sprint wrap-up: verify all tests pass                    (1 hour)
         ✓ Grant Detail complete
         ✓ Sprint 2 complete
```

---

## Dependency Graph

```
StatusField (widget.py)
    │
    ├──> StatusWidget.js (framework widget)
    │       │
    │       ├──> register in index.js
    │       │
    │       └──> Grant.status annotation (grant.py)
    │               │
    │               └──> grant-detail.js (uses StatusWidget via getWidgetForField)
    │                       │
    │                       ├──> grant-detail.css
    │                       │
    │                       └──> index.html (import + preload)
    │
    └──> Grant.__ui__ (grant.py)
            │
            └──> ntx-router.js #resolveTag() reads ui.renderer.detail
                    (no changes needed -- already works)

GrantsGovAPI (independent)
    │
    ├──> grants_gov_api.py (model)
    ├──> __init__.py (export)
    ├──> main.py (register)
    ├──> conftest.py (seed tool)
    └──> test_grants_gov_api.py (tests)
```

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **StatusWidget inline styles look different across browsers** | Low | Low | Inline styles are standardized; test Chrome + Firefox |
| **grant-detail.css vars not defined** | Medium | Low | CSS custom properties fall back to hardcoded values (every `var()` has a fallback) |
| **ntx-router does not find grant-detail element** | Low | High | Element must be defined BEFORE router navigates; the `import` in index.html ensures this. Verify with `customElements.get('grant-detail')` in console |
| **grants.gov API response format changes** | Low | Medium | Response parsing is defensive (`.get()` with defaults throughout). Add schema test against live API as a smoke test (run manually, not in CI) |
| **httpx not installed** | Low | High | `httpx` is already a dependency (used by `WebTools.scrape()`). Verify in `requirements.txt` or `pyproject.toml` |
| **Widget edit mode select not triggering handleInputChange** | Medium | Medium | The `edit()` method returns a `<select>` element. `form.js` (line 224-228) stamps `data-key` and `data-type` on the editable element. The `NTTItem.handleInputChange` listens for `change` events on `select` elements (line 657-660 binds to `input, textarea` but not `select`). **Action required:** Verify that `ntx-item.js` line 657 also binds `select` elements. If not, add `select` to the querySelectorAll. |

### Known Issue: Select Element Event Binding

Looking at `ntx-item.js` line 657:
```javascript
this.shadowRoot.querySelectorAll('input, textarea').forEach(el => {
```

This does NOT include `select` elements. The StatusWidget's edit mode renders a `<select>`, so change events will not be captured by `handleInputChange`.

**Fix required in `/workspace/src/n3tx/static/components/ntx-item.js`** (line 657):
```javascript
// Before:
this.shadowRoot.querySelectorAll('input, textarea').forEach(el => {

// After:
this.shadowRoot.querySelectorAll('input, textarea, select').forEach(el => {
```

And update the event type detection (same line area):
```javascript
const event = (el.type === 'checkbox') ? 'change'
    : (el.tagName === 'SELECT') ? 'change'
    : 'input';
```

This is a framework-level fix that benefits any widget using `<select>` in edit mode. Add it to Task 1 as a sub-task.

---

## Complete File Manifest

### New Files (4)

| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `/workspace/src/n3tx/static/widgets/StatusWidget.js` | ~65 | Framework widget: status chip rendering |
| `/workspace/example_grants/static/components/grant-detail.js` | ~120 | App component: rich grant detail view |
| `/workspace/example_grants/static/components/grant-detail.css` | ~180 | Shadow DOM styles for grant-detail |
| `/workspace/example_grants/models/grants_gov_api.py` | ~110 | GrantsGovAPI tool actor model |
| `/workspace/example_grants/tests/test_grants_gov_api.py` | ~100 | Mocked API + schema tests |

### Modified Files (9)

| File | Change Size | Description |
|------|------------|-------------|
| `/workspace/src/n3tx/core/widgets/widget.py` | +2 lines | Add `StatusField` class |
| `/workspace/src/n3tx/core/widgets/__init__.py` | +1 line | Export `StatusField` |
| `/workspace/src/n3tx/static/widgets/index.js` | +2 lines | Import + register StatusWidget |
| `/workspace/src/n3tx/static/components/ntx-item.js` | +2 lines | Add `select` to event binding |
| `/workspace/example_grants/models/grant.py` | +15 lines | StatusField annotation + `__ui__` dict |
| `/workspace/example_grants/models/__init__.py` | +2 lines | Export GrantsGovAPI |
| `/workspace/example_grants/main.py` | +2 lines | Register GrantsGovAPI |
| `/workspace/example_grants/static/index.html` | +3 lines | Modulepreload + import + CSS preload |
| `/workspace/example_grants/tests/conftest.py` | +2 lines | Import GrantsGovAPI + seed tool |
| `/workspace/example_grants/tests/test_schema_endpoints.py` | +20 lines | Schema tests for status widget, renderer, field_order |

---

## Verification Checklist (Sprint Complete)

### Automated Tests
- [ ] `python3 -m pytest example_grants/tests/` -- all pass
- [ ] `python3 -m pytest src/n3tx/core/tests/unit/` -- all pass (no regressions)

### Manual Frontend Tests
- [ ] Table view: Grant rows show colored status chips (not plain text)
- [ ] Table view: Status chips use correct colors (indigo=discovered, amber=reviewed, etc.)
- [ ] Edit mode: Status field shows `<select>` dropdown with 5 options
- [ ] Edit mode: Changing status via dropdown and saving persists the change
- [ ] Detail view: Clicking a grant row opens `<grant-detail>` (not `<ntx-item>`)
- [ ] Detail view: Agency badge, status chip, title, description all render
- [ ] Detail view: Deadline shows countdown with urgency colors
- [ ] Detail view: Amount range shows formatted currency
- [ ] Detail view: "View Grant Listing" button opens URL in new tab
- [ ] Detail view: Back button returns to table
- [ ] Responsive: Detail view stacks sidebar below main content on narrow screens

### API Tests
- [ ] `GET /Grant` schema includes `ui.widget: "status"` with config
- [ ] `GET /Grant` schema includes `ui.renderer.detail: "grant-detail"`
- [ ] `GET /GrantsGovAPI` schema includes `search` and `fetch` methods
- [ ] `POST /grants_gov_api/search` returns 401 without token
- [ ] `POST /grants_gov_api/search` with mock returns structured results

---

## Post-Sprint Notes

### What This Unlocks (Sprint 3 Candidates)

1. **Kanban Board** (`<grant-kanban>`) -- can now use StatusWidget for column headers and drag-to-change-status. Depends on StatusWidget (done) and Grant data (done).

2. **Dashboard** (`<grant-dashboard>`) -- client-side aggregation of grant data. Independent of this sprint but benefits from the StatusWidget color mapping.

3. **Multi-Agent Pipeline** -- GrantsGovAPI is now available as a tool. Adding it to the Scanner agent's tool list means it can search grants.gov programmatically instead of scraping HTML. Next step: wire lifecycle events so new grants trigger analysis.

4. **Source Health Panel** -- Source model can reuse StatusWidget for `scan_status` field (idle/scanning/success/error) with different colors.

### Architecture Validation

This sprint validates three key N3TX extension patterns:

- **Widget system works end-to-end:** Python annotation -> schema pipeline -> JSON Schema -> frontend registry -> rendering. Zero framework changes needed (except the `select` event binding fix).

- **`ui.renderer.detail` works:** Backend declares the component tag, `ntx-router.js` reads it, creates the element. Custom components plug in without modifying any routing code.

- **Non-storable ActorModel works as tool actor:** `GrantsGovAPI` follows the exact `WebTools` pattern. `discover_tools()` finds it automatically. Zero agent framework changes needed.
