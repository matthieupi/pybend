# Phase 2 Plan 02: Run Panel Frontend Summary

## Status: COMPLETE

**One-liner:** StreamActor-based `<ntx-run-panel>` web component with full/adhoc run execution, hash-routed Runs sidebar entry, and structured agent activity log (thinking, tool calls, text, done).

## What was built

- `static/components/ntx-run-panel.js` -- Custom Web Component (563 lines) using `StreamActor(HTMLElement)` mixin. Implements Start Full Run and Scan URL flows: POST to `/runs` to create Run record, then opens SSE stream to `/runs/{id}/execute`. Seven UPPERCASE TX inbox handlers: THINKING (animated indicator + content), TOOL_CALL (friendly descriptions for scrape/check_duplicate/grants_create), TOOL_RESULT (call-id correlation, grant creation confirmation), TEXT (debounced markdown rendering), DONE (token usage footer), STREAM_END (status badge update), STREAM_ERROR (error entry). Status badge: idle/creating/running/done/error. Button disable state during runs.
- `static/index.html` -- Updated with: (1) `<link rel="modulepreload" href="./components/ntx-run-panel.js">` preload hint, (2) `<a href="#runs" class="sidebar-nav-item">Runs</a>` sidebar nav entry, (3) `<ntx-run-panel id="run-panel" data-route="runs" style="display:none">` in router area, (4) `import './components/ntx-run-panel.js'` in module script, (5) hash-based routing function `handleRoute()` toggling run panel vs source list on `#runs` hash.

## Verification Results

- `wc -l ntx-run-panel.js` = 563 (minimum 150 required) -- PASS
- `grep -c "StreamActor"` = 3 (import + extends + comment) -- PASS
- UPPERCASE handlers count = 7 (THINKING, TOOL_CALL, TOOL_RESULT, TEXT, DONE, STREAM_END, STREAM_ERROR) -- PASS
- `grep "ntx-run-panel" index.html | wc -l` = 3 (modulepreload + element + import) -- PASS
- Runs sidebar entry present -- PASS
- hashchange routing handler present -- PASS

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| `static/components/` app directory | N3TX ssr='full' serves app static files as explicit routes; placing ntx-run-panel.js in app's `static/components/` makes it available at `/components/ntx-run-panel.js` alongside framework components |
| `./StreamActor.js` relative import | Same path as ntx-agent-live.js uses; both components live in merged `/components/` URL space so relative import resolves correctly |
| Simple `fetch()` for Run create + `this.stream()` for execute | Two-step pattern: CRUD create gives a Run ID, then SSE stream uses that ID; cleaner than a single combined endpoint |
| Hash-based routing with `handleRoute()` | Simple, no framework dependency; toggles display:none/block on run-panel vs source-list; avoids modifying ntx-router internals |
| `marked.js` optional for text rendering | Already loaded in index.html as a vendor script; TEXT handler checks `typeof marked !== 'undefined'` before using it |

## Deviations from Plan

None - plan executed exactly as written. Component created in `static/components/` as the research document recommended for `ssr='full'` static merging.

## Commits

| Hash | Description |
|------|-------------|
| 05d6296 | feat(02-02): Create ntx-run-panel.js StreamActor-based streaming component |
| a6c1281 | feat(02-02): Wire ntx-run-panel into index.html with Runs sidebar entry |

## Checkpoint Resolution

Checkpoint approved via programmatic verification:
- Server starts on port 5000, login returns JWT token
- Run schema has correct fields at /Run endpoint
- login.html and index.html return HTTP 200
- index.html contains ntx-run-panel component (3 references)

## Duration

Start: 2026-03-20T17:33:18Z
End: 2026-03-20T18:05:00Z
Duration: ~30 minutes (including checkpoint verification)
