# Phase 3 Plan 02: Admissibility Analysis Frontend Summary

## Status: COMPLETE

**One-liner:** StreamActor-based ntx-grant-analyze component for per-grant admissibility re-analysis with real-time streaming progress, grant info card with score/status display, and hash routing (#analyze/{id}) wired into index.html.

## What was built

- `apps/veille/static/components/ntx-grant-analyze.js` -- New web component `<ntx-grant-analyze>`. Extends `StreamActor(HTMLElement)`. Observed attribute `grant-id` triggers grant load via `GET /grants/{id}`. Renders a grant info card (title, funder, status pill, admissibility score with colour coding, URL, deadline, justification preview). "Re-run Analysis" button triggers `POST /grants/{id}/analyze` via `this.stream(url, {})`. "Back to Grants" sets `window.location.hash = ''`. All 7 UPPERCASE TX handlers implemented: THINKING (with animated placeholder), TOOL_CALL (with friendly descriptions for organizations_list, grants_update, scrape variants), TOOL_RESULT (spinner removal + score confirmation for grant updates), TEXT (debounced marked.js rendering), DONE (token usage footer), STREAM_END (reloads grant info to show updated score/status), STREAM_ERROR (error entry + re-enable button). ~430 lines.

- `apps/veille/static/index.html` -- Added `<link rel="modulepreload">` for the new component, `<ntx-grant-analyze id="analyze-panel">` element inside ntx-router, `import './components/ntx-grant-analyze.js'` in the module script, and extended `handleRoute()` to support `#analyze/{id}` routes with a cleaner hide-all-then-show pattern. Existing `#runs` and default (source-list/upload) routes preserved.

## Verification Results

- `ntx-grant-analyze.js` exists at expected path -- PASS
- StreamActor import present -- PASS
- All 7 UPPERCASE handlers present: THINKING, TOOL_CALL, TOOL_RESULT, TEXT, DONE, STREAM_END, STREAM_ERROR -- PASS
- `customElements.define('ntx-grant-analyze', ...)` present -- PASS
- `index.html` has 4 references to `ntx-grant-analyze` (modulepreload, element, import, route handler) -- PASS
- `hash.startsWith('analyze/')` route handler present -- PASS
- Existing `#runs` route preserved -- PASS
- Default (source-list) route preserved -- PASS

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| attributeChangedCallback drives grant reload | Attribute change is the natural signal; guards against double-load when `connectedCallback` fires after attribute is set |
| `#reset()` called on each attributeChangedCallback | Prevents stale log from previous grant when navigating between analyze views |
| STREAM_END reloads grant via `#loadGrant()` | Shows updated score/status/justification immediately after analysis without requiring a page refresh |
| Friendly tool descriptions for analysis-specific tools | organizations_list -> "Reading organisation profile", grants_update -> "Saving analysis results" gives meaningful UX during analysis |
| Hide-all-then-show pattern in handleRoute() | Cleaner than per-branch show/hide; new panels don't require changes to every existing branch |
| Grant info card shows justification preview (3-line clamp) | Most useful quick context without dominating the panel |

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| Hash | Description |
|------|-------------|
| 813c0fa | feat(03-02): Create ntx-grant-analyze StreamActor component |
| 83b0f38 | feat(03-02): Wire ntx-grant-analyze into index.html |

## Duration

Start: 2026-03-20T18:06:55Z
End: 2026-03-20T18:09:00Z
Duration: ~2 minutes
