# P5 Suite Hardening Plan

## ✅ Recommendation

Treat P5 as **test infrastructure stabilization**, not product/UI recovery. While P3/P4 agents settle UI and shell contracts, P5 should make failures more trustworthy by improving isolation, cleanup, and environment determinism without changing application behavior.

Recommended execution order:

```text
P5.1 Frontend Vitest hygiene
        |
        v
P5.2 Playwright DB/server isolation
        |
        v
P5.3 Backend example fixture isolation, grants first
        |
        v
P5.4 Assertion tightening and stability gates
```

Do **not** rewrite broad UI assertions in P5. If a failing assertion depends on form/router/topbar behavior, defer it to P3/P4.

---

## 1. Current State

| Surface | Current behavior | P5 risk |
|---|---|---|
| Vitest setup | `tests/frontend/tests/setup.js` mocks `localStorage`, `fetch`, `ResizeObserver`, `WebSocket`; collects unhandled rejections but does not fail | Hidden async leaks and cross-test state |
| Vitest config | jsdom, globals, single setup file, `restoreMocks: true` | No central DOM/timer/session/WebSocket cleanup |
| Playwright core/Veille | temp DBs seeded in global setup; fixed marker files under `/tmp`; local `reuseExistingServer` | Stale server or marker collision can bypass temp DB |
| Backend examples | session-scoped DB, app client, seed data, tokens, factory fixtures | Mutating tests contaminate later tests |
| Grants backend | same shared DB pattern plus actor routing and agent records | Highest isolation risk |

Key evidence:

- `tests/frontend/tests/setup.js` lines 114-117 collect unhandled rejections but never fail tests.
- `tests/frontend/tests/setup.js` lines 137-155 restore mocks but do not clear DOM, session storage, timers, WebSocket instances, or singleton runtime state.
- `tests/frontend/tests/e2e/global-setup.js` writes fixed marker `/tmp/ntx-e2e-dbpath.txt`; teardown reads the same fixed marker.
- `tests/frontend/tests/e2e/playwright.config.js` and `veille.playwright.config.js` use `reuseExistingServer: !process.env.CI`.
- `examples/core/tests/conftest.py`, `examples/actors/tests/conftest.py`, and `examples/grants/tests/conftest.py` use session-scoped DB/client/seed/token fixtures.

---

## 2. Target State

P5 is complete when:

1. Frontend unit tests fail on hidden unhandled promise rejections after targeted cleanup.
2. DOM, storage, timers, fetch mocks, and WebSocket mocks are consistently reset between Vitest tests.
3. Playwright-launched servers are guaranteed to use the DB seeded for the same run.
4. Marker/temp artifacts are run-unique and safe for concurrent/stale local runs.
5. Backend mutation-heavy tests can opt into fresh DB/client fixtures without rewriting the entire suite at once.
6. Permissive multi-status assertions are tightened only after the intended contract is known.

---

## 3. Architecture View

```text
              P5 hardening boundary

   Vitest setup.js          Playwright setup/config        Pytest conftest.py
        |                           |                           |
        v                           v                           v
 async cleanup + state       run-specific DB/server       fresh fixture option
 visibility                  environment                  for mutating tests
        |                           |                           |
        +------------- trustworthy failure signal ----------+
```

P5 should deepen test infrastructure as a small set of reusable primitives rather than scattering one-off cleanup inside individual tests.

---

## 4. Implementation Slices

### P5.1 — Frontend Vitest hygiene

**Scope**

- `tests/frontend/tests/setup.js`
- `tests/frontend/tests/integration/helpers/test-env.js`
- possibly a new helper under `tests/frontend/tests/helpers/` if existing convention supports it

**Goal**

Centralize neutral cleanup that does not encode P3/P4 UI contracts.

**Planned changes**

1. Clear and assert unhandled rejections around each test.
2. Clear DOM after each test.
3. Clear `sessionStorage` alongside the existing localStorage mock.
4. Clear/restore timers defensively.
5. Track WebSocket mock instances and close them after each test.
6. Clear integration fetch response maps automatically or provide a shared cleanup hook.

**Representative code shape**

```javascript
const _unhandledRejections = [];

beforeEach(() => {
  _unhandledRejections.length = 0;
  window.sessionStorage?.clear?.();
  resetFetchMock();
});

afterEach(async () => {
  await Promise.resolve();

  closeOpenMockSockets();
  document.body.replaceChildren();
  vi.clearAllTimers();
  vi.useRealTimers();

  if (_unhandledRejections.length) {
    const [reason] = _unhandledRejections;
    _unhandledRejections.length = 0;
    throw reason instanceof Error ? reason : new Error(String(reason));
  }

  vi.restoreAllMocks();
  reinstallGlobalMocks();
});
```

**Guardrails**

- Do not globally call `vi.resetModules()`; many test files intentionally control module reset timing.
- Do not attempt to reset `customElements`; provide a `defineOnce()` helper instead if needed.
- If this exposes many existing leaks, temporarily land cleanup first with logging, then enable failing behavior after the worst known leaks are fixed.

**Verification**

```bash
cd /workspace/tests/frontend && npx vitest run \
  tests/transport/Socket.test.js \
  tests/integration/network-entity-sync.test.js \
  tests/integration/list-item-interaction.test.js
```

Then run full Vitest after P3/P4 are not actively changing shared UI assumptions:

```bash
cd /workspace/tests/frontend && npx vitest run
```

---

### P5.2 — Playwright DB/server isolation

**Scope**

- `tests/frontend/tests/e2e/playwright.config.js`
- `tests/frontend/tests/e2e/global-setup.js`
- `tests/frontend/tests/e2e/global-teardown.js`
- `tests/frontend/tests/e2e/veille.playwright.config.js`
- `tests/frontend/tests/e2e/veille.global-setup.js`
- `tests/frontend/tests/e2e/veille.global-teardown.js`
- grants/perf Playwright configs if still maintained
- `apps/veille/tests/test_frontend_regressions.mjs`

**Goal**

Ensure the server under test uses the same temp DB seeded for that run, and make temp artifacts safe across stale/concurrent runs.

**Planned changes**

1. Make marker paths run-unique.
2. Pass the generated DB path explicitly into webServer commands or a run-env file read by both setup and config.
3. Disable `reuseExistingServer` for isolation-sensitive configs by default; keep an explicit fast-local opt-in if desired.
4. Add a lightweight server DB sanity check after boot where possible.
5. Isolate Veille app-local Node browser tests with their own temp DB and seed/reset.

**Representative marker shape**

```javascript
const runId = process.env.PLAYWRIGHT_RUN_ID || `${process.pid}-${Date.now()}`;
const markerPath = join(tmpdir(), `ntx-e2e-dbpath-${runId}.txt`);
process.env.__NTT_E2E_MARKER = markerPath;
```

**Representative server env shape**

```javascript
webServer: {
  command: `${PYTHON_BIN} main.py`,
  cwd: '/workspace/examples/core',
  env: {
    ...process.env,
    PYTHONPATH,
    N3TX_SQLITE_DB: process.env.N3TX_SQLITE_DB,
  },
  reuseExistingServer: process.env.N3TX_E2E_REUSE_SERVER === '1',
}
```

If Playwright config evaluation makes setup-generated env unavailable to `webServer.env`, prefer a small shared module that creates the run environment before `defineConfig()` and is also used by `global-setup.js`.

**Guardrails**

- Do not depend on fixed `/tmp/ntx-e2e-dbpath.txt` names.
- Do not let local reused servers satisfy isolation-sensitive tests unless explicitly requested.
- Do not change browser assertions here; only harness startup/teardown.

**Verification**

```bash
cd /workspace/tests/frontend && npx playwright test \
  --config=tests/e2e/playwright.config.js \
  tests/e2e/product-detail.spec.js

cd /workspace/tests/frontend && npx playwright test \
  --config=tests/e2e/veille.playwright.config.js \
  tests/e2e/veille-chat.spec.js
```

---

### P5.3 — Backend example fixture isolation, grants first

**Scope**

- `examples/grants/tests/conftest.py`
- then `examples/actors/tests/conftest.py`
- then `examples/core/tests/conftest.py`

**Goal**

Add a fresh fixture path for mutation-heavy tests without forcing the entire suite onto slower function-scoped setup immediately.

**Current risky pattern**

```text
session test_db
  -> session seed_data
  -> session client
  -> session tokens/factories
  -> many tests mutate same DB
```

**Recommended migration path**

| Stage | Action |
|---|---|
| P5.3a | Add a reusable fixture builder that can create DB + seed + client for either session or function scope |
| P5.3b | Introduce `fresh_client` / `fresh_seed_data` / `fresh_tokens` for mutation-heavy files |
| P5.3c | Migrate grants mutation-heavy files first: auth flow, authorization, pagination, CRUD, error handling, agent/chat fixtures |
| P5.3d | Repeat for actors/core only where order sensitivity remains |

**Representative fixture shape**

```python
def build_test_context(tmp_path):
    db_path = tmp_path / 'test.db'
    storage = _setup_test_db(str(db_path))
    seed = _seed_all()

    # actor suites only: re-sync Matrix after storage changes
    sync_actor_models_to_matrix()

    with TestClient(app, raise_server_exceptions=False) as client:
        yield TestContext(client=client, seed=seed, db_path=db_path)
```

**Grants first files**

- `examples/grants/tests/test_pagination.py`
- `examples/grants/tests/test_authorization.py`
- `examples/grants/tests/test_auth_flow.py`
- `examples/grants/tests/test_error_handling.py`
- agent/chat tests with session/module-scoped created agents

**Guardrails**

- Keep session-scoped fixtures for read-only schema and smoke tests where speed matters.
- Do not silently change seeded IDs unless tests are updated to use seed references instead of hard-coded IDs.
- Actor-routing fixtures must re-sync Matrix/model storage after fresh DB setup.

**Verification**

```bash
python3 -m pytest examples/grants/tests/test_auth_flow.py
python3 -m pytest examples/grants/tests/test_authorization.py
python3 -m pytest examples/grants/tests/test_pagination.py
python3 -m pytest examples/grants/tests/
```

Then apply the same pattern selectively:

```bash
python3 -m pytest examples/actors/tests/
python3 -m pytest examples/core/tests/
```

---

### P5.4 — Assertion tightening and stability gates

**Scope**

- Backend example tests with permissive status assertions.
- P5 CI/local scripts or documentation if present.

**Goal**

Stop hiding real regressions behind broad assertions, but only after P3/P4 and explicit contract decisions settle expected behavior.

**Known candidates**

| Suite | Examples |
|---|---|
| core/actors | `test_likes_crud.py` accepts broad nested route statuses; `test_auth_flow.py` accepts multiple login/password outcomes |
| grants | `test_auth_flow.py`, `test_authorization.py`, `test_error_handling.py`, `test_pagination.py`, `test_boot.py`, `test_grants_crud.py` contain many multi-status assertions |

**Contract note required per cluster**

```md
Contract decision:
- Classification: test infrastructure | stale test | product regression | unresolved decision
- Intended behavior:
- Evidence:
- Changed:
  - production code: no, unless a real regression is proven
  - tests: yes/no
  - docs: yes/no
- Regression risk:
```

**Verification tiers**

| Tier | Scope | When |
|---|---|---|
| narrow | one changed harness/test file | every slice |
| cluster | all tests using the changed fixture/config | phase end |
| broad | full Vitest, examples, Playwright | after P3/P4 settle |
| stability | targeted clusters rerun twice | before declaring P5 done |

---

## 5. Risks and Open Questions

| Risk | Mitigation |
|---|---|
| P5 exposes many hidden Vitest leaks at once | land cleanup in small steps; enable failing unhandled rejection gate after known leaks are triaged |
| Playwright env generated in global setup may not reach `webServer.env` | create run env before config materialization or make command read a run env file |
| Fresh backend fixtures slow suites | use opt-in fresh fixtures first for mutation-heavy tests |
| Hard-coded seeded IDs break under fresh DB contexts | prefer seed references and API-created fixtures |
| P5 accidentally rewrites P3/P4 UI contracts | defer UI DOM assertions to P3/P4 agents |

Open questions to decide before implementation:

1. Should local Playwright default to `reuseExistingServer=false`, or should we require `N3TX_E2E_REUSE_SERVER=1` only for fast local loops?
2. Do we want function-scoped fresh DBs for all grants tests, or an opt-in `fresh_client` migration first?
3. Should unhandled rejections fail immediately, or should P5 first add warning output and then flip to failure after a cleanup pass?

Default recommendations:

- Use explicit opt-in for reused Playwright servers.
- Start backend fixture migration with opt-in fresh fixtures, grants first.
- Enable unhandled rejection failure after a narrow targeted leak cleanup, not across full Vitest on the first commit.

---

## 6. Execution Checklist

```text
1. Add neutral Vitest cleanup helpers.
2. Verify targeted Vitest runtime/harness tests.
3. Make Playwright DB marker/env propagation run-unique and explicit.
4. Verify one core and one Veille Playwright spec uses seeded temp DB.
5. Add grants fresh fixture builder.
6. Migrate grants mutation-heavy tests to fresh fixtures.
7. Tighten permissive assertions only after each contract is explicit.
8. Rerun targeted clusters twice, then broad suites.
```

## Critical Files for Implementation

- `tests/frontend/tests/setup.js`
- `tests/frontend/tests/e2e/playwright.config.js`
- `tests/frontend/tests/e2e/global-setup.js`
- `examples/grants/tests/conftest.py`
- `examples/actors/tests/conftest.py`

## Saved Plan

- `.project/plans/tests/p5-suite-hardening-plan.md`
