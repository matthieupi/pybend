---
phase: "04"
plan: "02"
name: "Frontend report view, run history, and hash routing"
subsystem: frontend
tags: [report, history, web-components, hash-routing, shadow-dom, ntx-run-report, ntx-run-panel]

dependency-graph:
  requires:
    - "04-01: Run.report() endpoint and Organization schedule fields"
    - "03-02: ntx-grant-analyze component patterns"
  provides:
    - "ntx-run-report web component displaying grouped grant analysis results"
    - "Run history section in ntx-run-panel with per-run metrics and report links"
    - "Hash route #report/{id} navigates to report panel"
  affects: []

tech-stack:
  added: []
  patterns:
    - "HTMLElement with shadow DOM (no StreamActor mixin) for read-only report view"
    - "observedAttributes + attributeChangedCallback drives data load on attribute change"
    - "Hide-all-then-show pattern extended to fourth panel (report-panel)"
    - "History section with sticky header row and independent scroll (max-height)"

key-files:
  created:
    - apps/veille/static/components/ntx-run-report.js
  modified:
    - apps/veille/static/components/ntx-run-panel.js
    - apps/veille/static/index.html

decisions:
  - "Plain HTMLElement (no StreamActor) for ntx-run-report: read-only fetch, no streaming needed"
  - "History table uses CSS grid with fixed column widths for alignment across rows"
  - "STREAM_END calls #loadHistory() so completed run appears with View Report link immediately"
  - "Grant title in report links to #analyze/{id} for drill-down without leaving the app"

metrics:
  duration: "~3 minutes"
  completed: "2026-03-20"
  tasks-completed: 2
  tasks-total: 2
---

# Phase 4 Plan 02: Frontend Report View, Run History, and Hash Routing Summary

**One-liner:** ntx-run-report renders grouped admissibility buckets from Run.report(); ntx-run-panel gains scrollable history table with View Report links; #report/{id} hash route wires everything together.

## What Was Built

### Task 1: ntx-run-report component and index.html routing

**`apps/veille/static/components/ntx-run-report.js`**

New Web Component extending plain `HTMLElement` (no StreamActor mixin needed -- this is a read-only report view):

- Shadow DOM with embedded styles following the same visual language as ntx-run-panel and ntx-grant-analyze
- Observed attribute: `run-id`; `attributeChangedCallback` triggers `#loadReport()` on change
- `connectedCallback` attaches shadow DOM, renders template, binds "Back to Runs" button
- `#loadReport()` fetches `GET /runs/report?run_id=N` with JWT token; stores result in `#report`
- `#render()` builds full report: run metadata bar, colored summary counts bar, four grouped sections
- Four sections: Admissible (green), Partially Admissible (yellow), Non-Admissible (red), Unanalyzed (gray)
- Each section has a sticky header with colored left border and grant count badge
- Grant cards show: score pill (color-coded), clickable title link to `#analyze/{id}`, funder, deadline, reasoning excerpt (truncated to 200 chars)
- Empty state if no grants in run; error state if fetch fails

**`apps/veille/static/index.html`**

- Added `<link rel="modulepreload" href="./components/ntx-run-report.js">` to head
- Added `import './components/ntx-run-report.js';` in module script
- Added `<ntx-run-report id="report-panel" style="display:none"></ntx-run-report>` inside ntx-router
- Extended `handleRoute()` with `reportPanel` element reference, hide-all block entry, and `report/` hash branch that sets `run-id` attribute and shows the panel

### Task 2: Run history section in ntx-run-panel

**`apps/veille/static/components/ntx-run-panel.js`**

Extended the existing streaming panel with a history section below the footer:

- History section HTML added to template: header row with "Run History" title and Refresh button, scrollable list container
- `historyList` and `refreshHistoryBtn` added to `#els`
- `#loadHistory()` called at end of `connectedCallback()` and inside `STREAM_END()` after run completes
- `#loadHistory()`: fetches `GET /runs?limit=20` with JWT, sorts by `started_at` descending, calls `#renderHistory()`
- `#renderHistory(runs)`: renders a CSS grid table with header row and data rows; columns: Run #, Type, Status, Started, Grants, Sources, Actions
- Completed runs show a "View Report" link navigating to `#report/{id}`; other statuses show "—"
- `#runStatusClass()` maps status strings to color class names
- `#formatDate()` formats ISO timestamps to "Mar 20, 14:35" style
- History list has `max-height: 300px; overflow-y: auto` for independent scroll
- All history styles appended to existing `static styles` block

## Deviations from Plan

None -- plan executed exactly as written.

## Verification Results

All success criteria met:

1. `customElements.define('ntx-run-report', NTXRunReport)` confirmed in component file
2. index.html contains 3 references to `ntx-run-report` (modulepreload, import, element)
3. Hash route `report/` handler confirmed in index.html
4. History section in ntx-run-panel has `#loadHistory()`, `.history-section`, `.history-row` (9 matches)
5. Both JS files pass `node --check` syntax validation

## Next Phase Readiness

Phase 4 is complete. All four plans are done:
- Phase 4 Plan 01: Backend report endpoint, Organization schedule fields, asyncio scheduler
- Phase 4 Plan 02: Frontend report panel, run history, hash routing

The application now provides a full grant monitoring workflow: configure sources, run scraping, analyze grants for admissibility, view structured reports per run, and browse history.
