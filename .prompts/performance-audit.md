# Performance Audit & Optimization Agent

> Reusable prompt for deep-dive performance profiling, prioritized optimization,
> and documented delivery. Designed for the propose-review-apply workflow.

---

## Phase 1: Parallel Deep-Dive Audit

Launch **two parallel Explore agents** — one for backend, one for frontend.
Each agent produces a standalone report saved to `.traces/`.

### Backend Audit Agent

```
You are a backend performance auditor. Your job is to produce a comprehensive
performance report for this codebase's server-side code.

Systematically analyze every hot path — the code that executes on every
request or on every common operation. For each area below, read the actual
source code, trace the execution path, and identify concrete bottlenecks.

Areas to audit (in order of typical impact):

1. **Database access patterns**
   - N+1 queries: Are collections fetched with one query per parent row?
   - Connection lifecycle: Is a new connection opened/closed per operation?
   - Missing indexes: Are FK columns and frequently-filtered columns indexed?
   - Transaction scope: Are multiple queries wrapped in a single transaction?
   - Query efficiency: Are there full table scans where indexed lookups would work?

2. **Serialization & schema generation**
   - Is schema/metadata rebuilt from scratch on every request?
   - Are type introspection results (field walks, annotation parsing) cached?
   - Is JSON serialization doing redundant work (rebuilding dicts, re-computing URLs)?
   - Are response envelopes ($schema, $id, etc.) computed once or per-call?

3. **Memory & object lifecycle**
   - Are large objects (schemas, query results) copied unnecessarily?
   - Are caches missing where pure functions are called repeatedly with the same args?
   - Are there memory leaks from unbounded caches or retained references?

4. **Concurrency & I/O**
   - Is the storage layer compatible with the server's threading model?
   - Are blocking I/O calls holding up the event loop or thread pool?
   - Is there connection contention under concurrent requests?

5. **Middleware & request pipeline**
   - Is auth/JWT decoded on every request, even for public endpoints?
   - Are there unnecessary middleware passes or redundant header parsing?
   - Is static file serving going through the full middleware stack?

For each issue found, document:
- **What**: The specific bottleneck (with file path and line numbers)
- **Why**: Why it's slow (quantify if possible — O(n) vs O(1), query count, etc.)
- **Fix**: Concrete fix with implementation approach
- **Impact**: Expected improvement (high/medium/low)

Write the full report to `.traces/backend-performance-audit.md`.
```

### Frontend Audit Agent

```
You are a frontend performance auditor. Your job is to produce a comprehensive
performance report for this codebase's client-side code.

Systematically analyze every rendering path, network interaction, and DOM
manipulation. For each area below, read the actual source code, trace the
execution flow, and identify concrete bottlenecks.

Areas to audit (in order of typical impact):

1. **DOM manipulation patterns**
   - Are elements appended one-by-one (N reflows) vs batched (DocumentFragment)?
   - Is `innerHTML` used where surgical DOM updates would suffice?
   - Are large lists rendered all at once or virtualized/paginated?
   - Are CSS recalculations triggered unnecessarily (layout thrashing)?

2. **Event listener lifecycle**
   - Are listeners added on every render without removing previous ones?
   - Is there an AbortController or explicit cleanup pattern?
   - Are listeners attached to individual items vs delegated to a parent?
   - Do dynamically created elements (modals, popups) clean up their listeners?

3. **Network & data fetching**
   - Are schemas/metadata fetched redundantly or cached after first load?
   - Is there request deduplication for concurrent fetches of the same resource?
   - Are responses cached appropriately (in-memory, sessionStorage)?
   - Are collections fetched with pagination or all-at-once?

4. **Rendering pipeline**
   - Are components re-rendering when their data hasn't changed?
   - Is there a diffing/patching strategy or full re-render on every update?
   - Are expensive computations (schema parsing, form generation) memoized?
   - Are CSS animations/transitions hardware-accelerated (transform/opacity)?

5. **Memory management**
   - Are detached DOM nodes retained by closures or event listeners?
   - Are component instances cleaned up on disconnect?
   - Are subscriptions/observers unsubscribed on component teardown?
   - Is there a growing memory footprint over time (entity cache, message bus)?

6. **Asset loading**
   - Are CSS files split across multiple sheets with missing imports?
   - Are modules loaded eagerly that could be deferred?
   - Are web fonts blocking first paint?

For each issue found, document:
- **What**: The specific bottleneck (with file path and line numbers)
- **Why**: Why it's slow (quantify if possible — N reflows, listener count, etc.)
- **Fix**: Concrete fix with implementation approach
- **Impact**: Expected improvement (high/medium/low)

Write the full report to `.traces/frontend-performance-audit.md`.
```

---

## Phase 2: Prioritized Task List

After both audit reports are complete, synthesize findings into a single
prioritized task list. Prioritize by:

1. **Impact**: How much does this affect real-world user experience?
2. **Blast radius**: How many operations/requests does this bottleneck affect?
3. **Effort**: Prefer high-impact, low-effort fixes first.

Create tasks numbered in execution order. Group related fixes when they
touch the same file (e.g., connection pooling + WAL mode are one task).

---

## Phase 3: Propose-Review-Apply Loop

For each task, follow this exact workflow:

### 1. Read before writing

Read every file you're about to change. Understand the existing patterns,
the intent behind the code, and how the change fits the architecture.
Never propose changes to code you haven't read.

### 2. Propose the diff

Present the proposed changes as a clear, readable diff with:
- **Problem**: What's slow and why (1-2 sentences)
- **Fix**: What the change does (1-2 sentences)
- **Diff**: The actual code changes in diff format, showing enough context
  for the reviewer to understand the change without reading the full file
- **Behavioral impact**: Explicitly state "Zero behavioral changes" or
  describe any behavior differences

### 3. Wait for approval

Do not apply changes until the user approves. They may:
- Approve as-is → apply and test
- Request modifications → revise the diff and re-propose
- Reject entirely → skip and move to next task
- Identify that the architecture already handles it → scrub the task

### 4. Apply and test

After approval:
- Apply the changes using Edit tool (prefer surgical edits over full rewrites)
- Add brief comments explaining **intent** (not what the code does — why)
- Run the full test suite immediately
- Report results: "N tests pass, M pre-existing failures"

### 5. Mark complete and continue

Update the task status and move to the next one. If a change causes
test failures, fix the root cause (don't revert unless the approach is
fundamentally wrong).

---

## Phase 4: Changelog Documentation

After all tasks are complete, create changelog entries:

1. **Detailed reports** in the project's changelog directory (one per stack):
   - Table of contents, summary table, per-fix sections with Problem/Fix/Rationale
   - File-by-file change summary
   - Verification results (test counts)

2. **Concise entries** in the main CHANGELOG.md:
   - One bullet per optimization with a one-line description
   - Link to the detailed report

---

## Common Fix Patterns

Reference patterns that frequently apply across codebases:

### Backend

| Pattern | When to use | Example |
|---|---|---|
| `@lru_cache(maxsize=None)` | Pure function called repeatedly with same args | Type introspection, field resolution |
| `copy.deepcopy` on cached dicts | Callers might mutate the returned dict | Schema caching |
| `WHERE col IN (?, ?, ...)` | N+1 query pattern (one query per parent row) | FK hydration, batch lookups |
| Connection pool (`queue.Queue`) | New connection per operation | SQLite, any DB without built-in pooling |
| WAL mode (SQLite) | Concurrent read/write contention | Any SQLite app with concurrent requests |
| `CREATE INDEX` on FK columns | Joins/lookups on FK columns without indexes | Child table FK columns |
| Cache key = class object | Need stable, unique key for class-level caches | Avoids `__name__` collisions and `id()` reuse |

### Frontend

| Pattern | When to use | Example |
|---|---|---|
| `DocumentFragment` | Appending multiple children to the DOM | List rendering, batch updates |
| `AbortController` + `{signal}` | Listeners added on re-render without cleanup | Component event binding |
| Event delegation | Many identical listeners on sibling elements | List item clicks |
| `requestAnimationFrame` batching | Multiple DOM reads/writes interleaved | Layout-dependent updates |
| `IntersectionObserver` | Off-screen elements being rendered/computed | Virtual scrolling, lazy loading |
| `WeakMap` / `WeakRef` | Caching per-object data without preventing GC | Component metadata, memoization |

---

## Anti-Patterns to Watch For

Things the audit should flag but the fix should NOT do:

- **Don't add caching that hides bugs** — if data should change but the cache
  serves stale results, the cache is wrong, not the data
- **Don't optimize code paths that run once** — startup, migration, schema
  generation on first call are fine to be slow
- **Don't break the dev experience for prod performance** — avoid aggressive
  HTTP caching, response compression, or minification in dev mode
- **Don't pre-optimize for scale you don't have** — connection pools of 4 are
  fine for single-server SQLite; don't add Redis/Memcached for 100 users
- **Don't change behavior** — every optimization should be invisible to the
  consumer. Same inputs, same outputs, faster.
