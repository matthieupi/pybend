# P2: Widget Upgrades — StatusWidget, DeadlineWidget, CompactCurrency

## Summary

Three widget upgrades for the Grant Watcher app, all operating within the existing widget pipeline:

1. **StatusField/StatusWidget** — Colored badge display + dropdown edit
2. **DeadlineField/DeadlineWidget** — Countdown display with urgency colors
3. **CurrencyWidget compact mode** — Abbreviates large values in list view ($50K, $1.2M)

## Architecture

The existing widget pipeline requires NO changes:
1. Python Widget type annotation → `schema_ext.py` injects `ui.widget` + `ui.config`
2. Frontend `getWidgetForField()` dispatches to registered JS widget
3. Widget's `display()`, `edit()`, `list()` methods handle rendering

**Critical gap identified**: `ntx-row.js` `#editCells()` and `ntx-table.js` create row do NOT dispatch through the widget system for edit rendering. They manually map widget names to input types. Fix: make both widget-aware.

**Another gap**: `ntx-item.js` `#bindEvents()` only queries `input, textarea` — not `select`. StatusWidget produces a `<select>`. Both `ntx-item.js` and `ntx-row.js` need to include `select`.

## Backend Changes

### `src/n3tx/core/widgets/widget.py` — Add 2 new Widget types

```python
class StatusField(Widget, name='status', base_type=str):
    """Status enum rendered as colored badge. Config carries options mapping."""
    pass

class DeadlineField(Widget, name='deadline', base_type=date):
    """Date rendered with countdown and urgency colors."""
    pass
```

### `src/n3tx/core/widgets/__init__.py` — Export new types

Add `StatusField` and `DeadlineField` to imports and `__all__`.

### `example_grants/models/grant.py` — Apply widgets

```python
deadline: Optional[DeadlineField] = Field(default=None)
status: StatusField(options={
    'discovered': {'color': '#3b82f6', 'label': 'Discovered'},
    'reviewed':   {'color': '#f59e0b', 'label': 'Reviewed'},
    'applied':    {'color': '#10b981', 'label': 'Applied'},
    'expired':    {'color': '#ef4444', 'label': 'Expired'},
}) = Field(default='discovered')
```

Schema output for `status` field:
```json
{
  "type": "string",
  "ui": {
    "widget": "status",
    "config": {
      "options": {
        "discovered": {"color": "#3b82f6", "label": "Discovered"},
        ...
      }
    }
  }
}
```

## Frontend Changes

### New: `src/n3tx/static/widgets/StatusWidget.js`
- `display()`: Colored pill badge using CSS custom property `--status-color`
- `edit()`: `<select>` dropdown built from config.options; fallback to text input if no options
- `list()`: HTML string badge for table cells

### New: `src/n3tx/static/widgets/DeadlineWidget.js`
- Extends `DateWidget` (inherits `edit()` calendar picker)
- `display()`: Date + relative countdown ("3d left") with urgency class
- `list()`: Compact format "Mar 15 (3d)" with urgency coloring
- 5 urgency levels: normal (>14d), soon (7-14d), urgent (3-7d), critical (<3d), expired (<0d)

### Modified: `src/n3tx/static/widgets/CurrencyWidget.js`
- `list()` now abbreviates: `$1.2M`, `$50K`, `$500`
- `display()` unchanged (full format `$10,000.00`)

### Modified: `src/n3tx/static/widgets/index.js`
- Import and register `StatusWidget` and `DeadlineWidget`

### New: `src/n3tx/static/widgets/widgets.css` (append)
- `.widget-status-badge` with `color-mix()` for background tinting
- `.widget-deadline` with urgency color classes
- `.widget-deadline-compact` for list mode
- `.widget-status-select` for edit dropdown

### Modified: `src/n3tx/static/components/ntx-row.js`
- `#editCells()`: Check for registered widget, use `widget.edit()` when available
- `#bindRowEvents()`: Add `select` to querySelector

### Modified: `src/n3tx/static/components/ntx-table.js`
- Create row: Widget-aware select rendering for status fields

### Modified: `src/n3tx/static/components/ntx-item.js`
- `#bindEvents()`: Add `select` to querySelector
- Use `change` event for `select` elements (like checkboxes)

## Tests

### Backend: `src/n3tx/core/tests/unit/test_widgets.py`
- `StatusField` bare and with config
- `DeadlineField` bare
- Schema pipeline injects correct `ui.widget` and `ui.config`

### Frontend: `src/n3tx/static/tests/widgets/StatusWidget.test.js`
- display() badge with color, fallback for unknown values
- edit() select with options, fallback to text input
- list() HTML string output

### Frontend: `src/n3tx/static/tests/widgets/DeadlineWidget.test.js`
- display() countdown for future/past dates, null handling
- list() compact format with urgency class
- edit() inherits DateWidget

### Frontend: `src/n3tx/static/tests/widgets/CurrencyWidget.test.js`
- list() abbreviation: millions, thousands, small values
- display() still full format

### Integration: `example_grants/tests/test_grant_widget_schema.py`
- Grant schema has status widget with options
- Grant schema has deadline widget
- Grant schema has currency widgets on amount fields

## Execution Order

```
Phase 1: Backend types (widget.py, __init__.py, grant.py)
Phase 2: Frontend widgets (StatusWidget.js, DeadlineWidget.js, CurrencyWidget.js) — parallel
Phase 3: CSS styles (widgets.css)
Phase 4: Table edit integration (ntx-row.js, ntx-table.js, ntx-item.js)
Phase 5: Tests
```

## Files Summary

**New files (4):**
- `src/n3tx/static/widgets/StatusWidget.js`
- `src/n3tx/static/widgets/DeadlineWidget.js`
- `src/n3tx/static/tests/widgets/StatusWidget.test.js`
- `src/n3tx/static/tests/widgets/DeadlineWidget.test.js`

**Modified files (10):**
- `src/n3tx/core/widgets/widget.py`
- `src/n3tx/core/widgets/__init__.py`
- `example_grants/models/grant.py`
- `src/n3tx/static/widgets/index.js`
- `src/n3tx/static/widgets/CurrencyWidget.js`
- `src/n3tx/static/widgets/widgets.css`
- `src/n3tx/static/components/ntx-item.js`
- `src/n3tx/static/components/ntx-row.js`
- `src/n3tx/static/components/ntx-table.js`
- `example_grants/static/index.html`
