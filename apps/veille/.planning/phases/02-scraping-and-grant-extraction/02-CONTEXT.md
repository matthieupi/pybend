# Phase 2: Scraping and Grant Extraction -- Context

## Agent Scraping Strategy

### Navigation Depth
- **Adaptive exploration**: The LLM agent reads each source page and decides which links are worth following to find grant details
- No fixed hop limit — the agent is prompted to be efficient and stop when it has thoroughly explored the source
- Soft budget: agent is instructed to be efficient, no hard max-pages cap

### Content Fetching
- **HTTP-first with browser fallback**: Try simple HTTP fetch + HTML-to-text. If content appears empty or JS-only, fall back to headless browser (Playwright)
- Most government grant portals use server-side rendering, so HTTP will work for the majority

### Scraping Notes
- **Injected as prompt instructions**: Each source's `scraping_notes` field becomes part of the agent's system prompt when scraping that source
- Example: "This is a listing page — click individual grant links for details" or "French only, look for subventions/programmes"
- This lets humans steer the agent's behavior per-source without code changes

### Source-Type Handling
- Agent adapts its strategy based on what it finds (listing page vs single program page vs org homepage)
- No predefined source types — the agent reasons about page structure

---

## Run Model & Lifecycle

### Run as Persistent Model
- **Run is a stored ActorModel** in the database
- Fields needed: id, status (pending/running/complete/failed), started_at, completed_at, type (full/adhoc), sources covered, grants found count, error info
- Persisted from the start — enables Phase 4 run history without refactoring

### Trigger Mechanism
- **Dedicated run panel** in the sidebar/main area (new sidebar entry: "Runs")
- Panel shows a "Start Run" button for full runs (all active sources)
- Same panel has a URL input field for ad-hoc scans
- Default view: latest run if one exists, or Start button if none

### Streaming Progress
- **Text log + grant cards**: The user sees both:
  - Agent activity as a text stream (thinking, status messages like "Fetching source 2/4...", "Found grant: [title]")
  - Grant cards appearing below the log as they're extracted
- Uses N3TX streaming (`@expose_route(stream=True)` + `ntx-stream` or custom stream component)

### Results Display
- Grants appear both in the run panel (as they stream in) and in the sidebar Grant list (after creation)
- Run panel is the primary view during/after a run

---

## Grant Deduplication

### Detection Method
- **URL match first**: If the grant's own URL (application page) matches an existing grant, it's a duplicate
- **LLM comparison fallback**: If no URL match or URL is ambiguous, the agent compares title + funder + details against existing grants using LLM reasoning
- Two-step: fast check first, expensive check only when needed

### Merge Behavior
- **Enrich existing grant**: When a duplicate is detected, update the existing grant with any new or better information from the second source
- Track all source URLs that contributed to a grant (the `source_url` field may need to become a list, or add a separate tracking mechanism)

### Timing
- **During extraction**: The agent checks for existing matches before creating each new grant
- Prevents duplicates in real time — no temporary duplicate state
- Agent has access to the current grant list (or at least URLs/titles) to perform checks

---

## Ad-hoc URL Scanning

### UI Location
- **In the run panel**: A URL text input next to the Start Run button
- User enters a URL, clicks "Scan" — triggers an ad-hoc run

### Pipeline
- **Same pipeline as full runs**: Creates a Run record with `type='adhoc'`
- Appears in run history alongside full runs
- Same streaming UX — text log + grant cards

### Source Saving
- **Prompt after scan**: After results come back, the UI asks "Save this as a source for future runs?"
- If yes: creates a new Source with `agent_discovered=false` (human-added via ad-hoc scan)
- If no: URL is not saved, grants are still kept

---

## Deferred Ideas

(None raised during discussion)

---
*Created: 2026-03-20 during Phase 2 discussion*
