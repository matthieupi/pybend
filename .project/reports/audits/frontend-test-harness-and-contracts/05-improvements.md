# Frontend Test Harness And Contracts - Strategic Improvements

## Executive Recommendation

The frontend test subsystem is failing for two different reasons that should not be solved with the same motion. First, the Playwright harness still has infrastructure defects: core E2E starts the web server with `cat '${E2E_MARKER}'` before the marker file exists in practice, while grants and perf still point at non-existent pre-split application paths. Second, several Vitest failures are contract-governance problems: tests assert stale DOM details, stale component locations, or stale schema method names even though the current product/docs point elsewhere.

The investment recommendation is to create one small shared harness contract module and one explicit frontend contract fixture layer. The harness module should own run IDs, DB marker paths, app roots, Python env, server command construction, and teardown. The contract fixture layer should own canonical schema mocks and DOM contract helpers so component tests stop re-encoding backend/application facts ad hoc.

The immediate sequence should be:

| Order | Fix cluster | Default classification | Why first |
|---:|---|---|---|
| 1 | E2E marker setup ordering | test infrastructure | Core Playwright cannot start reliably because the webServer command reads a marker before setup writes it. |
| 2 | Wrong app paths | test infrastructure | Grants and perf configs reference paths absent from the current workspace. |
| 3 | Missing component modules | stale test/component ownership | `ntx-favorites` is example-local, but the Vitest alias treats it as a package component. |
| 4 | Schema mock method naming | stale test fixture | Product exposes `favorite`, not `like`; Comment exposes `like`. |
| 5 | Stale component style tests | stale DOM/style contract | Tests assert inline/static CSS while components now use external stylesheet links. |
| 6 | Row display contract | unresolved/test fixture | The test bypasses real element lifecycle and may be asserting validation with incomplete row data. |
| 7 | Profile placeholder contract | stale DOM class contract | Implementation renders `.profile-note`, test expects `.placeholder`. |

## Current-State Evidence

### System Contract

The architecture says the frontend is schema-driven and components communicate through TX messages rather than direct HTTP calls (`docs/frontend/ARCHITECTURE.md:17-22`). The schema is the universal backend/frontend contract and carries UI rendering, access, and method behavior (`docs/CORE.md:109-168`). The frontend docs list Vitest and Playwright as the two verification layers and say Playwright boots `examples/core` with an isolated seeded SQLite database (`FRONTEND.md:174-184`). The styling docs say pages/components now use linked theme/base CSS and canonical token entrypoints, with frontend verification through Vitest and Playwright (`packages/n3tx-ui/docs/styling.md:25-58`, `packages/n3tx-ui/docs/styling.md:98-113`).

### Harness Current State

`scripts/run-frontend-tests.py` defines five frontend suites: Vitest, core Playwright, grants Playwright, Veille Playwright, and perf Playwright (`scripts/run-frontend-tests.py:85-148`). The same runner discovers core E2E specs by excluding grants, veille, and performance files (`scripts/run-frontend-tests.py:67-75`). This is the right mental model, but each Playwright config still owns its own path/env/marker logic instead of sharing a typed run environment.

Core Playwright computes a run-specific marker path during config evaluation and stores it in `process.env.__NTT_E2E_MARKER` (`tests/frontend/tests/e2e/playwright.config.js:16-20`). Its webServer command reads the DB path with `cat '${E2E_MARKER}'` and passes the result into `N3TX_SQLITE_DB`/`NTT_SQLITE_DB` (`tests/frontend/tests/e2e/playwright.config.js:50-57`). The marker is only written by `global-setup.js` later in its setup function (`tests/frontend/tests/e2e/global-setup.js:23-38`). A targeted reproduction of `product-list.spec.js` failed with `cat: /tmp/ntx-e2e-dbpath-...txt: No such file or directory`, followed by SQLite `unable to open database file`, which matches the file-ordering risk in those lines.

Core teardown still has a fixed fallback marker path even though config/setup now prefer run-specific marker names (`tests/frontend/tests/e2e/global-teardown.js:8-13`). Veille has the same split: config creates a run-specific marker (`tests/frontend/tests/e2e/veille.playwright.config.js:16-20`), setup writes it (`tests/frontend/tests/e2e/veille.global-setup.js:17-28`), and teardown has a fixed fallback (`tests/frontend/tests/e2e/veille.global-teardown.js:5-10`).

Grants Playwright is still anchored to `/workspace/example_grants` in setup and webServer command (`tests/frontend/tests/e2e/grants-global-setup.js:12-28`, `tests/frontend/tests/e2e/playwright.grants.config.js:33-36`). The current workspace contains `examples/grants/main.py` and `examples/grants/seed.py`, not `/workspace/example_grants`, so the config is stale after the package/example split. A targeted reproduction failed with `/bin/sh: 1: cd: can't cd to /workspace/example_grants`, which is the direct consequence of those config lines.

Perf Playwright still computes `EXAMPLE_DIR` as `src/n3tx/example` and the seed script as `src/n3tx/core/tests/profiling/seed_perf.py` (`tests/frontend/tests/e2e/playwright.perf.config.js:6-14`, `tests/frontend/tests/e2e/perf-global-setup.js:12-15`). Those paths do not match the documented current examples layout under `examples/` and packages under `packages/` (`FRONTEND.md:206-216`).

Vitest setup is healthier than the older P5 plan: it now clears local storage and fetch before each test (`tests/frontend/tests/setup.js:131-154`), closes mock WebSockets, clears DOM and session storage, restores timers/mocks, reinstalls fetch/window globals, and fails on leaked unhandled rejections (`tests/frontend/tests/setup.js:156-198`). This means remaining Vitest failures are more likely real contract decisions than hidden async leaks.

### Contract Failure Clusters

`ntx-ref-picker` renders a stylesheet link to `ntx-ref-picker.css` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:28-30`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:85-92`). Its tests still expect inline `<style>` and a static `NTTRefPicker.styles` string containing selectors (`tests/frontend/tests/components/ntx-ref-picker.test.js:382-387`, `tests/frontend/tests/components/ntx-ref-picker.test.js:1155-1171`). This is stale test contract, not a reason to re-inline CSS.

`Component.SIZES` currently includes `row`, and `Component.ALIASES` maps `row` to `row` (`packages/n3tx-core/src/n3tx_core/static/core/Component.js:25-34`). One integration test expects exactly five sizes and aliases (`tests/frontend/tests/integration/display-mode-cascade.test.js:156-168`), while another expects all six including `row` (`tests/frontend/tests/integration/list-item-interaction.test.js:63-65`). This is an internal contract governance gap: two tests assert incompatible definitions of the same public constant.

`ntx-row` forces row display in `connectedCallback()` and deliberately opts into a custom edit layout (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:21-36`). Its save path collects inline inputs, validates through Formidable, saves on zero errors, then returns to display (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:129-146`). The failing test creates a row without appending it to the DOM, overrides `value`, renders manually, and expects `save()` after validation (`tests/frontend/tests/components/ntx-row.test.js:36-48`, `tests/frontend/tests/components/ntx-row.test.js:125-135`). This may expose a genuine row/validation problem, but the test fixture bypasses connected lifecycle and supplies required fields while hidden/filtered fields may be collected differently than runtime.

`ntx-profile` renders a `.profile-note` paragraph with "Profile settings coming soon." (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:43-57`). The test expects `.placeholder` (`tests/frontend/tests/components/ntx-profile.test.js:154-162`). The product-visible text matches the expected semantics, but the CSS class contract is stale or undocumented.

The canonical Product model exposes `comment`, `countdown`, and `favorite` methods, and its favorite UI is attached to `favorites` (`examples/core/models/product.py:34-48`, `examples/core/models/product.py:63-82`). The canonical Comment model exposes `like` and `reply` (`examples/core/models/comment.py:30-36`, `examples/core/models/comment.py:45-69`). The shared mock schema already defines Product `favorite` (`tests/frontend/tests/integration/helpers/mock-schemas.js:127-150`), but `schema-bootstrap.test.js` still expects `instance.like` on Product (`tests/frontend/tests/integration/schema-bootstrap.test.js:74-80`). This is stale assertion drift inside the same fixture cluster.

`ntx-favorites.test.js` imports `../../components/ntx-favorites.js` as if it were a package component (`tests/frontend/tests/components/ntx-favorites.test.js:27-29`). The actual `ntx-favorites.js` files are example-local under `examples/core/static/components/` and `examples/actors/static/components/`, and the core example component simply wraps `<ntx-list model="ProductLike" display="md">` (`examples/core/static/components/ntx-favorites.js:1-15`). This should be governed as an example component test, not a framework component test.

## Before And After Mental Model

### Before

```text
scripts/run-frontend-tests.py
  |-- Vitest config/setup
  |-- Playwright core config ----> own marker/env/path/server command
  |-- Playwright grants config --> own marker/env/path/server command (stale path)
  |-- Playwright veille config --> own marker/env/path/server command
  `-- Playwright perf config ---> own marker/env/path/server command (stale path)

tests/**/*.test.js
  |-- local schema facts duplicated in mock-schemas.js
  |-- component tests assert private DOM/CSS details
  |-- app-local components imported through package aliases
  `-- incompatible constants asserted by separate suites
```

### After

```text
frontend-harness/run-env.js
  |-- app registry: core | grants | veille | perf
  |-- run id + temp DB + marker path
  |-- PYTHONPATH + Python binary
  |-- seed command + server command
  `-- teardown target

Playwright configs
  |-- import createPlaywrightAppConfig('core')
  |-- import createPlaywrightAppConfig('grants')
  `-- override only testMatch/baseURL/port when needed

frontend-contracts/
  |-- canonical mock schemas generated/validated from backend schemas
  |-- DOM contract helpers: assertStylesheetLink, assertDisplayModes, assertProfileNote
  |-- component ownership map: framework | agent | example | app
  `-- contract decision notes per failure cluster
```

## Proposition 1 - Build A Shared Playwright Run Environment

### Current State

Core and Veille configs each compute marker paths and shell out to `cat` inside `webServer.command` (`tests/frontend/tests/e2e/playwright.config.js:16-20`, `tests/frontend/tests/e2e/playwright.config.js:50-57`, `tests/frontend/tests/e2e/veille.playwright.config.js:16-20`, `tests/frontend/tests/e2e/veille.playwright.config.js:50-60`). Core setup writes the marker inside `globalSetup()` (`tests/frontend/tests/e2e/global-setup.js:23-38`). Grants and perf use their own stale path logic (`tests/frontend/tests/e2e/grants-global-setup.js:12-28`, `tests/frontend/tests/e2e/playwright.grants.config.js:33-36`, `tests/frontend/tests/e2e/playwright.perf.config.js:6-14`).

### Problem

The harness has two hidden contracts: Playwright server startup order and current app paths. Those contracts are duplicated in several files, so a fix to core does not fix grants/perf. The result is infrastructure noise that masks browser contract failures.

### Proposed Change

Create `tests/frontend/tests/e2e/harness/run-env.js` and make each Playwright config call it during config evaluation, before `defineConfig()` returns. Do not rely on `globalSetup()` to create data consumed by `webServer.command`.

```javascript
// tests/frontend/tests/e2e/harness/run-env.js
import { existsSync, mkdtempSync, writeFileSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';

const APPS = {
  core:   { cwd: '/workspace/examples/core',   port: 5000, marker: 'ntx-core-e2e', seed: 'seed.py', health: '/Product' },
  grants: { cwd: '/workspace/examples/grants', port: 5000, marker: 'ntx-grants-e2e', seed: 'seed.py', health: '/Grant' },
  veille: { cwd: '/workspace/apps/veille',     port: 5010, marker: 'ntx-veille-e2e', seed: 'seed.py --reset', health: '/login.html' },
};

export function createRunEnv(appName) {
  const app = APPS[appName];
  if (!app) throw new Error(`Unknown E2E app: ${appName}`);
  if (!existsSync(app.cwd)) throw new Error(`Missing E2E app cwd: ${app.cwd}`);

  const runId = process.env.PLAYWRIGHT_RUN_ID || `${process.pid}-${Date.now()}`;
  const tmp = mkdtempSync(join(tmpdir(), `${app.marker}-`));
  const dbPath = join(tmp, `${appName}.db`);
  const markerPath = join(tmpdir(), `${app.marker}-dbpath-${runId}.txt`);
  writeFileSync(markerPath, dbPath);

  return { app, runId, tmp, dbPath, markerPath, python: pythonBin(), pythonPath: PYTHONPATH };
}
```

```diff
// tests/frontend/tests/e2e/playwright.config.js
- const RUN_ID = process.env.PLAYWRIGHT_RUN_ID || `${process.pid}-${Date.now()}`;
- const E2E_MARKER = process.env.__NTT_E2E_MARKER || join(tmpdir(), `ntx-e2e-dbpath-${RUN_ID}.txt`);
- process.env.__NTT_E2E_MARKER = E2E_MARKER;
+ import { createRunEnv, serverCommand, seedSetup, cleanupTeardown } from './harness/run-env.js';
+ const run = createRunEnv('core');

  webServer: {
-   command: `N3TX_SQLITE_DB="$(cat '${E2E_MARKER}')" NTT_SQLITE_DB="$(cat '${E2E_MARKER}')" ${PYTHON_BIN} main.py`,
-   cwd: '/workspace/examples/core',
+   command: serverCommand(run),
+   cwd: run.app.cwd,
    env: {
      ...process.env,
-     PYTHONPATH,
-     __NTT_E2E_MARKER: E2E_MARKER,
+     PYTHONPATH: run.pythonPath,
+     N3TX_SQLITE_DB: run.dbPath,
+     NTT_SQLITE_DB: run.dbPath,
    },
  }
```

### Target Files

`tests/frontend/tests/e2e/harness/run-env.js`, `tests/frontend/tests/e2e/playwright.config.js`, `tests/frontend/tests/e2e/veille.playwright.config.js`, `tests/frontend/tests/e2e/playwright.grants.config.js`, `tests/frontend/tests/e2e/playwright.perf.config.js`, global setup/teardown files.

### Trade-Offs

This adds one harness module, but removes repeated path/marker/env logic from every config. It also makes config evaluation do a small amount of filesystem work; that is acceptable because the alternative is nondeterministic server startup.

### Migration Path

Start with core, because it currently reproduces marker-order failure. Then migrate grants to fix the stale path. Then migrate Veille and perf. Keep old setup files as thin wrappers during migration, then delete duplicated marker logic.

### Verification

Run `npx playwright test --config=tests/e2e/playwright.config.js tests/e2e/product-list.spec.js --project=chromium`, `npx playwright test --config=tests/e2e/playwright.grants.config.js --list`, and one grants spec. The server log must not contain `cat: ... No such file or directory`, and grants must not attempt to cd into `/workspace/example_grants`.

## Proposition 2 - Introduce An App Registry Instead Of Hardcoded Paths

### Current State

The runner knows suite names but not application roots or maintained app ownership (`scripts/run-frontend-tests.py:85-148`). Playwright configs hardcode app paths independently (`tests/frontend/tests/e2e/playwright.config.js:50-58`, `tests/frontend/tests/e2e/playwright.grants.config.js:33-36`, `tests/frontend/tests/e2e/veille.playwright.config.js:50-61`, `tests/frontend/tests/e2e/playwright.perf.config.js:6-14`).

### Problem

Path drift becomes a runtime failure instead of a compile-time/config-time failure. The grants path is stale, and perf appears to reference the pre-split `src/n3tx` tree. This breaks convention over configuration: the repo already has a current `examples/` convention, but configs do not consume it centrally.

### Proposed Change

Add `tests/frontend/tests/e2e/harness/apps.js` with an explicit registry.

```javascript
export const E2E_APPS = {
  core: {
    root: '/workspace/examples/core',
    seed: ['seed.py'],
    main: ['main.py'],
    port: 5000,
    healthPath: '/Product',
    env: {},
  },
  grants: {
    root: '/workspace/examples/grants',
    seed: ['seed.py'],
    main: ['main.py'],
    port: 5000,
    healthPath: '/Grant',
    env: {},
  },
  veille: {
    root: '/workspace/apps/veille',
    seed: ['seed.py', '--reset'],
    main: ['main.py'],
    port: 5010,
    healthPath: '/login.html',
    env: { N3TX_CHAT_LLM: 'test' },
  },
};
```

### Target Files

Same as Proposition 1, plus `scripts/run-frontend-tests.py` can optionally read/validate the registry before executing suites.

### Trade-Offs

Central registry must be kept current, but that is easier than tracking path literals in five configs and multiple setup files.

### Migration Path

Add registry first with `validateApp(appName)`. Make grants config use it immediately. Update runner `--list` output to show app root and health URL from the registry.

### Verification

Add a tiny config validation test or script that asserts every registered `root` exists and has `main.py`; grants and perf stale paths should fail before this migration and pass after.

## Proposition 3 - Govern Canonical Schema Fixtures

### Current State

`mock-schemas.js` says it mirrors real Product/Comment/Like backend schemas (`tests/frontend/tests/integration/helpers/mock-schemas.js:1-4`). It correctly exposes Product `favorite` (`tests/frontend/tests/integration/helpers/mock-schemas.js:127-150`), matching the backend Product model (`examples/core/models/product.py:34-48`, `examples/core/models/product.py:81-102`). A schema bootstrap test still expects `instance.like` on Product (`tests/frontend/tests/integration/schema-bootstrap.test.js:74-80`).

### Problem

The suite has no governance mechanism for whether mock schema facts are current. A single stale assertion can make engineers suspect `prototype()` method generation even though `NTT.js` generates methods from `schema.methods` exactly as designed (`packages/n3tx-core/src/n3tx_core/static/core/NTT.js:619-621`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:724-752`).

### Proposed Change

Create a schema contract generator or snapshot validator that compares `mock-schemas.js` against live schemas from `examples/core`. Until generation is automated, add named helpers that encode intent.

```javascript
export const ProductMethodNames = Object.freeze(['comment', 'favorite', 'countdown']);
export const CommentMethodNames = Object.freeze(['like', 'reply']);

export function expectMethods(instance, names) {
  for (const name of names) expect(typeof instance[name]).toBe('function');
}
```

```diff
- expect(typeof instance.comment).toBe('function');
- expect(typeof instance.like).toBe('function');
+ expectMethods(instance, ['comment', 'favorite']);
```

### Target Files

`tests/frontend/tests/integration/helpers/mock-schemas.js`, `tests/frontend/tests/integration/schema-bootstrap.test.js`, eventually a new `tests/frontend/tests/integration/helpers/schema-contract.test.js`.

### Trade-Offs

Generated schemas add a backend dependency to fixture updates. The low-cost first step is static fixture governance with explicit method-name constants.

### Migration Path

Fix Product `like` expectation to `favorite`. Add a contract test that checks Product method names in the fixture equal the intended list. Later, add a `scripts/export-example-schemas.py` command if mock drift continues.

### Verification

Run `npx vitest run tests/integration/schema-bootstrap.test.js`. It should prove dynamic method generation from current schema methods, not old social naming.

## Proposition 4 - Make Component Ownership Explicit

### Current State

Framework component docs list `ntx-profile`, `ntx-user`, `ntx-topbar`, `ntx-sidebar`, and other package components (`FRONTEND.md:57-80`). `ntx-favorites.js` is not listed as a framework component and lives under example static dirs (`examples/core/static/components/ntx-favorites.js:1-15`). The test imports it through the package component alias (`tests/frontend/tests/components/ntx-favorites.test.js:27-29`).

### Problem

The test directory layout implies everything under `tests/components` is a reusable package component. App/example-local components need a different test import root and lifecycle assumptions. Without ownership metadata, missing modules show up as Vite import failures instead of intentional "this component is example-local" decisions.

### Proposed Change

Add a component ownership map used by Vitest aliases and tests.

```javascript
export const COMPONENT_OWNERS = {
  'ntx-item': 'ui',
  'ntx-profile': 'ui',
  'ntx-agent': 'agents',
  'ntx-favorites': 'examples/core',
};

export function componentPath(tag) {
  const owner = COMPONENT_OWNERS[tag];
  if (owner === 'ui') return `${uiStatic}/components/${tag}.js`;
  if (owner === 'agents') return `${agentsStatic}/components/${tag}.js`;
  if (owner?.startsWith('examples/')) return `/workspace/${owner}/static/components/${tag}.js`;
  throw new Error(`Unknown component owner: ${tag}`);
}
```

### Target Files

`tests/frontend/vitest.config.js`, `tests/frontend/tests/components/ntx-favorites.test.js`, possibly a new `tests/frontend/tests/helpers/component-owner.js`.

### Trade-Offs

This slightly expands test infrastructure, but it prevents accidental promotion of example-only components into package public API.

### Migration Path

Move or rename `ntx-favorites.test.js` into an example-specific test group, or configure an explicit alias for example components. Do not add `ntx-favorites` to `n3tx-ui` unless product decides favorites is a framework primitive.

### Verification

Run `npx vitest run tests/components/ntx-favorites.test.js` after moving/fixing import. The test should either pass as an example component test or be deleted if covered by Playwright example flows.

## Proposition 5 - Define DOM Contract Levels For Component Tests

### Current State

The component docs describe styles as a URL getter on `Component` subclasses (`docs/frontend/COMPONENTS.md:93-109`). `ntx-ref-picker` is standalone and injects a stylesheet link directly (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:28-30`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:85-92`). Tests assert private CSS storage details: inline `<style>` and `NTTRefPicker.styles` selector strings (`tests/frontend/tests/components/ntx-ref-picker.test.js:382-387`, `tests/frontend/tests/components/ntx-ref-picker.test.js:1155-1171`).

`ntx-profile` renders the user-facing note with `.profile-note` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:43-57`), while the test expects `.placeholder` (`tests/frontend/tests/components/ntx-profile.test.js:154-162`).

### Problem

Tests mix public DOM contracts with implementation details. This makes harmless style implementation changes look like product regressions and encourages production code to preserve dead CSS APIs.

### Proposed Change

Adopt three DOM assertion levels:

| Level | Allowed assertions | Example |
|---|---|---|
| Public semantic | visible text, ARIA role, custom element tag, emitted event | profile note contains "coming soon" |
| Structural public | documented class/data attribute | `.profile-note` only if documented |
| Private implementation | stylesheet selectors, exact internal wrappers | only in explicitly named source-contract tests |

Add helpers:

```javascript
export function expectStylesheetLink(root, filename) {
  const link = root.querySelector('link[rel="stylesheet"]');
  expect(link).toBeTruthy();
  expect(link.getAttribute('href')).toContain(filename);
}

export function expectSemanticText(root, text) {
  expect(root.textContent).toContain(text);
}
```

### Target Files

`tests/frontend/tests/components/ntx-ref-picker.test.js`, `tests/frontend/tests/components/ntx-profile.test.js`, `packages/n3tx-ui/docs/components.md` if `.profile-note` is declared public.

### Trade-Offs

Less exact DOM testing can miss accidental class changes. That is acceptable for private CSS; class-level contracts should be declared before being enforced.

### Migration Path

Rewrite stale style assertions to assert a stylesheet link and visible affordances. Rewrite profile test to assert text or declare `.profile-note` as public. Keep only one source-level style contract where docs require static strings, as `ntx-method` does (`packages/n3tx-ui/docs/components.md:45-53`).

### Verification

Run `npx vitest run tests/components/ntx-ref-picker.test.js tests/components/ntx-profile.test.js`.

## Proposition 6 - Settle The Row Display Contract

### Current State

`Component.SIZES` includes `row` (`packages/n3tx-core/src/n3tx_core/static/core/Component.js:25-34`). `ntx-row` forces row display during connected lifecycle (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:30-36`). One test expects six sizes including row (`tests/frontend/tests/integration/list-item-interaction.test.js:63-65`), while another expects exactly five (`tests/frontend/tests/integration/display-mode-cascade.test.js:156-168`).

### Problem

The test suite has no explicit distinction between adaptive viewport sizes and semantic/non-adaptive display modes. `row` is currently encoded as both a size and a special table-row mode. That complicates mental model and creates incompatible tests.

### Proposed Change

Separate adaptive sizes from display modes while preserving `normalizeDisplay('row')`.

```javascript
static ADAPTIVE_SIZES = ['xs', 'sm', 'md', 'lg', 'xl'];
static DISPLAY_MODES = [...Component.ADAPTIVE_SIZES, 'row'];
static SIZES = Component.DISPLAY_MODES; // temporary compatibility alias
static ALIASES = { pill: 'xs', 'list-item': 'sm', card: 'md', detail: 'lg', page: 'xl', row: 'row' };
```

```diff
- expect(Component.SIZES).toHaveLength(5);
+ expect(Component.ADAPTIVE_SIZES).toHaveLength(5);
+ expect(Component.DISPLAY_MODES).toContain('row');
```

### Target Files

`packages/n3tx-core/src/n3tx_core/static/core/Component.js`, `docs/frontend/COMPONENTS.md`, `packages/n3tx-ui/docs/components.md`, `tests/frontend/tests/integration/display-mode-cascade.test.js`, `tests/frontend/tests/integration/list-item-interaction.test.js`.

### Trade-Offs

Adds two names, but removes the ambiguity around whether `row` is a responsive size. Keep `SIZES` as a compatibility alias until tests/docs migrate.

### Migration Path

Add new constants, migrate tests to assert the right level, then decide whether `SIZES` remains public or becomes deprecated.

### Verification

Run both display tests and `ntx-row.test.js`.

## Proposition 7 - Require Contract Decision Notes For Red Clusters

### Current State

The P-1 plan already requires classifying failures before source changes (`.project/plans/tests/contract-triage-p-1.md:37-45`, `.project/plans/tests/contract-triage-p-1.md:59-73`). The P3-P5 recovery plan repeats that the remaining work is schema-driven UI drift, browser shell drift, and test infrastructure noise (`.project/plans/tests/p3-p5-test-recovery-plan.md:21-43`).

### Problem

The rule exists as a plan, not an enforceable workflow artifact. The same categories are being rediscovered across tests: stale schema mocks, stale DOM styles, app/package ownership drift, and infrastructure path/marker drift.

### Proposed Change

Add `.project/contracts/frontend-tests/` notes for each fixed cluster and require PR summaries to link one note when changing a failing test.

```md
# C-frontend-schema-product-social

- Classification: stale test contract
- Intended behavior: Product exposes favorite/favorites; Comment exposes like/likes.
- Evidence: examples/core/models/product.py:34-48, examples/core/models/comment.py:30-36
- Changed: tests only
- Regression risk: accidentally removing Comment.like coverage
```

### Target Files

`.project/contracts/frontend-tests/*.md`, PR template or contributor docs if desired.

### Trade-Offs

More process. But it is lightweight and prevents a high-risk anti-pattern: changing product code to satisfy stale tests.

### Migration Path

Start with the seven immediate fix clusters listed in this report. Do not require retroactive notes for already-green work.

### Verification

Every PR that touches red tests includes a classification. Engineering leads can review whether product/test/docs changes match the classification.

## Priority Matrix

| # | Proposition | Simplifies | Impact | Effort | Risk | Dependencies |
|---:|---|---|---|---|---|---|
| P1 | Shared Playwright run environment | marker/env/server startup | Very high | Medium | Medium | none |
| P2 | App registry for E2E configs | app path ownership | High | Low | Low | P1 benefits but can start first |
| P3 | Canonical schema fixtures | backend/frontend method contract | High | Low | Low | none |
| P4 | Component ownership map | package vs example component boundary | High | Low | Low | none |
| P5 | DOM contract levels/helpers | stale style/profile assertions | Medium | Low | Low | P7 improves governance |
| P6 | Row/adaptive display constants split | display mental model | Medium | Medium | Medium | docs update |
| P7 | Contract decision notes | test contract governance | Medium | Low | Low | none |

Quick wins: P2, P3, P4, P5, P7. Strategic investment: P1. Design cleanup: P6.

## Immediate Fix Cluster Separation

### E2E Marker Setup Ordering

Current state: config reads marker via shell `cat` in the webServer command (`tests/frontend/tests/e2e/playwright.config.js:50-57`), setup writes marker inside `globalSetup()` (`tests/frontend/tests/e2e/global-setup.js:23-38`).

Fix direction: create DB path and marker before `defineConfig()` returns, or stop using marker files for webServer and pass `N3TX_SQLITE_DB` directly through `webServer.env`.

Verification: targeted core Playwright spec starts without `cat: ... No such file or directory`.

### Wrong App Paths

Current state: grants points to `/workspace/example_grants` (`tests/frontend/tests/e2e/grants-global-setup.js:12-28`, `tests/frontend/tests/e2e/playwright.grants.config.js:33-36`), while the repo uses `examples/grants`. Perf points to `src/n3tx/example` and `src/n3tx/core/tests/profiling/seed_perf.py` (`tests/frontend/tests/e2e/playwright.perf.config.js:6-14`, `tests/frontend/tests/e2e/perf-global-setup.js:12-15`).

Fix direction: app registry with `examples/grants` and a deliberate decision on whether perf is still maintained.

Verification: `npx playwright test --config=tests/e2e/playwright.grants.config.js --list` plus one grants spec.

### Stale Component Style Tests

Current state: `ntx-ref-picker` uses `<link rel="stylesheet">` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:85-92`), tests assert inline/static styles (`tests/frontend/tests/components/ntx-ref-picker.test.js:382-387`, `tests/frontend/tests/components/ntx-ref-picker.test.js:1155-1171`).

Fix direction: test stylesheet link and semantic behavior, not private selector strings.

Verification: targeted `ntx-ref-picker.test.js`.

### Row Display Contract

Current state: `row` is in `Component.SIZES` (`packages/n3tx-core/src/n3tx_core/static/core/Component.js:25-34`), and tests disagree on whether `SIZES` has five or six entries (`tests/frontend/tests/integration/display-mode-cascade.test.js:156-168`, `tests/frontend/tests/integration/list-item-interaction.test.js:63-65`).

Fix direction: introduce `ADAPTIVE_SIZES` vs `DISPLAY_MODES`; migrate assertions to the correct concept.

Verification: both display-mode suites and `ntx-row.test.js`.

### Profile Placeholder Contract

Current state: implementation renders `.profile-note` (`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:43-57`), test expects `.placeholder` (`tests/frontend/tests/components/ntx-profile.test.js:154-162`).

Fix direction: either document `.profile-note` as public and test it, or assert visible text only.

Verification: `ntx-profile.test.js`.

### Schema Mock Method Naming

Current state: Product exposes `favorite` (`examples/core/models/product.py:34-48`, `examples/core/models/product.py:81-102`), mock schema exposes `favorite` (`tests/frontend/tests/integration/helpers/mock-schemas.js:127-150`), test expects Product `like` (`tests/frontend/tests/integration/schema-bootstrap.test.js:74-80`).

Fix direction: replace Product `like` assertion with `favorite`; keep Comment `like` coverage.

Verification: `schema-bootstrap.test.js`.

### Missing Component Modules

Current state: test imports `../../components/ntx-favorites.js` (`tests/frontend/tests/components/ntx-favorites.test.js:27-29`), but `ntx-favorites.js` is example-local (`examples/core/static/components/ntx-favorites.js:1-15`).

Fix direction: move test to an example component context or add explicit example alias; do not silently promote component to framework package.

Verification: targeted `ntx-favorites.test.js` after ownership decision.

## Governance Rule

No product code should be changed for any of the above clusters until the classification is written. The current evidence strongly suggests infrastructure changes for Playwright marker/path issues and test contract changes for schema/style/profile/favorites ownership. Row validation remains the main cluster that should be treated as unresolved until a lifecycle-faithful test confirms whether production code is wrong.
