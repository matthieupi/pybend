# Frontend Test Harness and Contracts — Deep Audit Report

## Executive Summary

The frontend test harness and contracts subsystem is the verification boundary for N3TX's schema-driven frontend. The product side is intentionally split between `n3tx-core` non-visual runtime (`NTT`, `Component`, Actor/TX/Matrix, transport) and `n3tx-ui` visual Web Components (`ntx-item`, `ntx-list`, `ntx-row`, `ntx-ref-picker`, `ntx-profile`, widgets, themes). The backend JSON Schema remains the universal backend/frontend contract: it carries properties, UI hints, access rules, methods, nested `$defs`, `$id`, and `$schema`, and the frontend adapts at runtime from that schema rather than duplicating model facts (`docs/CORE.md:109-168`, `FRONTEND.md:20-24`, `FRONTEND.md:218-247`).

The harness side is a hybrid verification system. `python3 scripts/run-frontend-tests.py` orchestrates Vitest/jsdom unit and integration tests plus Playwright browser suites for core, grants, veille, and perf (`scripts/run-frontend-tests.py:85-148`). Vitest provides fast runtime/component coverage through aliases into package static dirs and a shared jsdom setup (`tests/frontend/vitest.config.js:8-35`, `tests/frontend/tests/setup.js:8-199`). Playwright boots seeded apps with temp SQLite DBs and package `PYTHONPATH`, but the app-specific configs have drifted: core and veille rely on marker-file shell substitution, grants points to `/workspace/example_grants`, and perf points to pre-split `src/n3tx/...` paths (`tests/frontend/tests/e2e/playwright.config.js:50-64`, `tests/frontend/tests/e2e/playwright.grants.config.js:33-41`, `tests/frontend/tests/e2e/playwright.perf.config.js:6-14`).

The reproduced command, `python3 scripts/run-frontend-tests.py`, should not currently be interpreted as a pure product-correctness signal. The red clusters mix stale tests, infrastructure drift, unresolved contract governance, and a few real runtime coverage risks. The clearest infrastructure problems are Playwright marker/path drift and example-local component imports routed through package aliases. The clearest stale contracts are inline/static CSS expectations for `ntx-ref-picker`, Product `like()` instead of `favorite()`, `.placeholder` instead of `.profile-note`, and tests expecting only five display sizes. The highest product-risk gap is not one of those stale assertions; it is DynamicClass generated method argument mapping in `NTT.js`, which is likely under-tested because current tests often bypass generated wrappers and call lower-level methods directly (`03-quality-risks.md:39`, `03-quality-risks.md:96`).

The top recommendation is contract-first recovery. Repair the Playwright harness before reading browser failures. Then update stale Vitest assertions to current documented behavior. Then add narrow product tests for actual runtime hotspots, especially generated schema methods and structured method response handling, before editing `NTT.js` or component internals. This prevents the high-risk anti-pattern of changing product code to satisfy stale tests.

Strategically, N3TX should add two small coordination layers: a shared Playwright run-environment/app registry and a canonical frontend contract fixture layer. The first makes DB paths, app roots, Python env, server commands, ports, health checks, and cleanup explicit. The second makes schema fixtures, component ownership, display-mode semantics, and DOM assertion levels explicit. Together they reduce harness noise while strengthening the schema-as-contract model.

## Component Overview

```text
                         Backend model definitions
                                  |
                                  v
                    JSON Schema endpoint: GET /{ClassName}
                                  |
                                  v
        +------------------- n3tx-core frontend runtime -------------------+
        | NTT.SCHEMA() -> prototype() -> DynamicClass registry             |
        | Component base -> Actor/TX/Matrix bridge -> transport/utils      |
        +----------------------------+-------------------------------------+
                                     |
                                     v
        +--------------------- n3tx-ui visual layer -----------------------+
        | NTTElement/ListElement/Formidable/widgets/themes                 |
        | ntx-item / ntx-list / ntx-row / ntx-ref-picker / ntx-profile      |
        +----------------------------+-------------------------------------+
                                     |
                                     v
                         Browser-visible application UI

        +---------------- frontend verification harness -------------------+
        | scripts/run-frontend-tests.py                                    |
        |   |-- unit: Vitest + jsdom + tests/setup.js                      |
        |   |       aliases ../../core, ../../utils, ../../components       |
        |   |       package static dirs: n3tx-core, n3tx-ui, n3tx-agents    |
        |   |                                                             |
        |   |-- e2e-core: Playwright + examples/core + temp SQLite DB       |
        |   |-- e2e-grants: Playwright grants specs + grants app           |
        |   |-- e2e-veille: Playwright veille specs + deterministic LLM     |
        |   `-- e2e-perf: Playwright performance instrumentation            |
        +-----------------------------------------------------------------+
```

Consolidated component map:

| Component | Responsibility | Evidence |
|---|---|---|
| `scripts/run-frontend-tests.py` | Top-level suite registry, subprocess execution, count parsing, overview JSON, final exit code. | `01-architecture.md:87-95`, `02-api-contracts.md:58-63` |
| `tests/frontend/vitest.config.js` | jsdom unit harness, global aliases into package static trees, all `tests/**/*.test.js`. | `01-architecture.md:18-21`, `02-api-contracts.md:64-66` |
| `tests/frontend/tests/setup.js` | Browser primitive mocks, cleanup, unhandled rejection surfacing. | `01-architecture.md:21`, `02-api-contracts.md:66-67`, `04-extensibility.md:92-97` |
| Core Playwright config/setup/teardown | Runs `examples/core`, seeds isolated DB, probes `/Product`. | `01-architecture.md:22`, `02-api-contracts.md:73` |
| Grants Playwright config/setup | Intended grants browser suite; currently stale path and DB env drift. | `01-architecture.md:23`, `03-quality-risks.md:28` |
| Veille Playwright config/setup | Runs `apps/veille` on port 5010 with deterministic chat LLM. | `01-architecture.md:24`, `02-api-contracts.md:75` |
| Perf Playwright config/setup | Performance browser suite; currently references legacy `src/n3tx` paths. | `01-architecture.md:25`, `03-quality-risks.md:29` |
| `NTT.js` | Schema bootstrap, DynamicClass factory, instance registry, method response handling. | `01-architecture.md:107-108`, `04-extensibility.md:124-132` |
| `Component.js` | Abstract Web Component/Actor bridge, display modes, stylesheet handling, lifecycle hooks. | `01-architecture.md:106`, `02-api-contracts.md:24-26` |
| `ntx-ref-picker.js` | Standalone reference picker and inline create flow, linked stylesheet. | `01-architecture.md:108-110`, `02-api-contracts.md:30`, `02-api-contracts.md:39-40` |
| `ntx-row.js` | `NTTItem` table-row specialization with forced row display and inline edit/save. | `01-architecture.md:110`, `02-api-contracts.md:32`, `04-extensibility.md:142` |
| `ntx-profile.js` | Standalone authenticated profile page component. | `01-architecture.md:112`, `02-api-contracts.md:31` |
| Example `ntx-favorites.js` / `ntx-logs.js` | Example-local components, not package `n3tx-ui` components. | `01-architecture.md:29`, `05-improvements.md:53` |

## Key Findings

### Critical Issues

#### C1 — Playwright app startup contracts are duplicated and drifting

Finding: Core and veille use marker-file shell substitution, grants uses a stale app path, and perf uses legacy pre-split paths. This makes `python3 scripts/run-frontend-tests.py` fail before product behavior is exercised.

Evidence: `tests/frontend/tests/e2e/playwright.config.js:50-57` reads DB paths with `cat`; `tests/frontend/tests/e2e/global-setup.js:23-38` writes the marker later; grants starts `cd /workspace/example_grants` (`tests/frontend/tests/e2e/playwright.grants.config.js:34`); perf resolves `src/n3tx/example` and `src/n3tx/core/tests/profiling/seed_perf.py` (`tests/frontend/tests/e2e/playwright.perf.config.js:8`, `tests/frontend/tests/e2e/perf-global-setup.js:14`). The docs say core Playwright boots `examples/core` with an isolated SQLite DB and package `PYTHONPATH` (`FRONTEND.md:174-184`).

Severity: Critical.

Recommendation: Add a shared E2E run environment/app registry and migrate core first, grants second, veille third, perf only after deciding whether it is maintained.

#### C2 — Example-local components are imported as package components

Finding: `ntx-favorites` and `ntx-logs` tests import through `../../components/*`, but Vitest aliases that prefix to `n3tx-ui/static/components`; the implementations are example-local.

Evidence: Vitest aliases `../../components/` to the package UI component dir (`tests/frontend/vitest.config.js:31`). The tests import `../../components/ntx-favorites.js` and `../../components/ntx-logs.js` (`tests/frontend/tests/components/ntx-favorites.test.js:28`, `tests/frontend/tests/components/ntx-logs.test.js:35`). The files exist under `examples/core/static/components`, not package UI (`01-architecture.md:29`, `05-improvements.md:53`).

Severity: Critical for harness trust, not product runtime.

Recommendation: Make component ownership explicit. Either move these tests into an example-specific harness/import root or intentionally promote the components into `n3tx-ui` with docs and package files. Do not add silent package shims.

#### C3 — Product/runtime method wrapper coverage is insufficient

Finding: DynamicClass generated methods may mishandle named arguments, but current tests can miss this by calling lower-level `instance.call(...)` directly.

Evidence: The quality report identifies generated method code indexing `args[param]` where `args` is an array and `param` is a string (`03-quality-risks.md:39`, citing `NTT.js:728`, `NTT.js:731`, `NTT.js:745`, `NTT.js:751`). Method execution tests currently bypass generated methods (`03-quality-risks.md:39`, `03-quality-risks.md:96`). The schema contract says `prototype()` defines one method per `schema.methods` key (`02-api-contracts.md:49-52`).

Severity: Critical product-risk coverage gap.

Recommendation: Add a narrow failing test for calling a generated method with real parameters from schema, then fix product code only if the test reproduces the bug.

#### C4 — Stale DOM/CSS assertions encourage product regressions

Finding: Tests assert inline `<style>` and `NTTRefPicker.styles`, but the current component links `ntx-ref-picker.css`; reintroducing static CSS strings would conflict with current style/token contracts.

Evidence: `ntx-ref-picker` emits `<link rel="stylesheet" href="...ntx-ref-picker.css">` (`ntx-ref-picker.js:85-92`), while tests expect `<style>` and `NTTRefPicker.styles` (`tests/frontend/tests/components/ntx-ref-picker.test.js:382-387`, `tests/frontend/tests/components/ntx-ref-picker.test.js:1155-1171`). Styling docs prefer linked/theme CSS and canonical tokens (`packages/n3tx-ui/docs/styling.md:25-40`, `packages/n3tx-ui/docs/styling.md:60-79`).

Severity: High.

Recommendation: Update tests to assert stylesheet link presence and public behavior, not private CSS storage.

#### C5 — Display-mode contract is inconsistently governed

Finding: `row` is a current product display mode, but some tests and cross-cutting docs assert only five adaptive sizes.

Evidence: `Component.SIZES` includes `row` and aliases `row` to `row` (`Component.js:25-34`); `ntx-row` forces row display (`ntx-row.js:30-42`); package docs list `row` as an `NTTItem` display mode (`packages/n3tx-ui/docs/components.md:176-184`). Some tests expect exactly five sizes (`tests/frontend/tests/core/Component.test.js:73-81`, `tests/frontend/tests/integration/display-mode-cascade.test.js:156-168`). `02-api-contracts.md` classified this as unresolved because cross-cutting docs omit `row`; `01-architecture.md` and `03-quality-risks.md` classify it as stale test. This synthesis resolves it as current intended product contract with stale/incomplete docs/tests.

Severity: High.

Recommendation: Introduce `ADAPTIVE_SIZES` versus `DISPLAY_MODES`, keep `SIZES` as compatibility alias during migration, and update docs/tests to assert the right concept.

### Design Strengths

| Strength | Evidence |
|---|---|
| Schema as universal contract keeps product architecture coherent. | `docs/CORE.md:109-168`, `FRONTEND.md:218-247`, `01-architecture.md:31-44` |
| Runtime/visual package split is clear and acyclic. | `FRONTEND.md:20-24`, `FRONTEND.md:186-204` |
| Hybrid Vitest + Playwright harness gives fast unit feedback plus browser validation. | `FRONTEND.md:174-184`, `04-extensibility.md:198-204` |
| Runner continues after failures and writes longitudinal overview JSON. | `scripts/run-frontend-tests.py:392-425`, `scripts/run-frontend-tests.py:438-521`, `02-api-contracts.md:61-63` |
| jsdom setup now fails leaked unhandled rejections instead of hiding async noise. | `tests/frontend/tests/setup.js:122-129`, `tests/frontend/tests/setup.js:156-198`, `04-extensibility.md:96` |
| Core/veille Playwright suites use package `PYTHONPATH` and isolated DB concepts. | `02-api-contracts.md:73`, `02-api-contracts.md:75` |
| `Component` stylesheet loading and standalone linked CSS support current tokenized style direction. | `Component.js:258-302`, `ntx-ref-picker.js:85-92`, `packages/n3tx-ui/docs/styling.md:25-79` |

### Design Trade-offs

| Trade-off | Benefit | Cost | Evidence |
|---|---|---|---|
| Vitest aliases historical relative imports into package static dirs. | Tests can import browser modules without package installation. | Alias hides ownership; example components fail as package imports. | `tests/frontend/vitest.config.js:17-35`, `01-architecture.md:96-100` |
| jsdom unit tests mock many collaborators. | Fast and focused component tests. | Mocks can diverge from real schema/runtime behavior. | `04-extensibility.md:180` |
| Playwright configs are app-specific. | App-specific env and health checks are explicit. | Duplicated path/marker/env logic drifts. | `04-extensibility.md:108-120` |
| `Component.SIZES` includes semantic `row`. | Table row rendering is first-class in component display flow. | Blurs responsive sizes versus non-adaptive display modes. | `Component.js:25-34`, `05-improvements.md:380-399` |
| DynamicClass centralizes schema runtime behavior. | Strong single place for schema bootstrap and methods. | Changes have high blast radius; targeted tests are mandatory. | `04-extensibility.md:168-170` |

### Improvement Opportunities

| Rank | Opportunity | Classification | Impact | Effort | Source |
|---:|---|---|---|---|---|
| 1 | Shared Playwright run environment and app registry. | Infrastructure | Very high | Medium | `05-improvements.md:96-177` |
| 2 | Fix grants/perf path drift or remove from default until maintained. | Infrastructure | High | Low-Medium | `03-quality-risks.md:28-30` |
| 3 | Component ownership map for package/example/app components. | Harness contract | High | Low | `05-improvements.md:281-327` |
| 4 | Canonical schema fixture governance. | Contract fixture | High | Low | `05-improvements.md:236-280` |
| 5 | DOM contract levels and helpers. | Test quality | Medium | Low | `05-improvements.md:328-379` |
| 6 | `ADAPTIVE_SIZES` / `DISPLAY_MODES` split. | Contract clarity | Medium | Medium | `05-improvements.md:380-421` |
| 7 | Generated method wrapper tests. | Product-risk coverage | Very high | Low | `03-quality-risks.md:39`, `03-quality-risks.md:96` |
| 8 | Method response contract tests for local update versus pull. | Product-risk coverage | High | Medium | `03-quality-risks.md:41`, `04-extensibility.md:264-268` |
| 9 | Vitest worker/memory hardening. | Infrastructure | Medium | Medium | `03-quality-risks.md:33`, `03-quality-risks.md:88-92` |
| 10 | Contract decision notes for red clusters. | Governance | Medium | Low | `05-improvements.md:423-461` |

## Strategic Propositions

### Simplification Propositions

#### S1 — Shared Playwright Run Environment

Current state: Each Playwright config duplicates app root, marker, DB env, Python env, and server command logic. Core/veille rely on marker files read with shell `cat`; grants/perf are stale (`05-improvements.md:96-104`).

Proposed change:

```javascript
// tests/frontend/tests/e2e/harness/run-env.js
export const E2E_APPS = {
  core: { root: '/workspace/examples/core', port: 5000, health: '/Product', seed: ['seed.py'] },
  grants: { root: '/workspace/examples/grants', port: 5000, health: '/Grant', seed: ['seed.py'] },
  veille: { root: '/workspace/apps/veille', port: 5010, health: '/login.html', seed: ['seed.py', '--reset'], env: { N3TX_CHAT_LLM: 'test' } },
};

export function createRunEnv(appName) {
  const app = E2E_APPS[appName];
  if (!app) throw new Error(`Unknown E2E app: ${appName}`);
  const runId = process.env.PLAYWRIGHT_RUN_ID || `${process.pid}-${Date.now()}`;
  const tmpDir = mkdtempSync(join(tmpdir(), `ntx-${appName}-e2e-`));
  const dbPath = join(tmpDir, `${appName}.db`);
  return { app, runId, tmpDir, dbPath, python: pythonBin(), pythonPath: packagePythonPath() };
}

export function webServer(run) {
  return {
    cwd: run.app.root,
    command: `${run.python} main.py`,
    env: { ...process.env, PYTHONPATH: run.pythonPath, N3TX_SQLITE_DB: run.dbPath, NTT_SQLITE_DB: run.dbPath, ...run.app.env },
    url: `http://localhost:${run.app.port}${run.app.health}`,
    reuseExistingServer: false,
  };
}
```

What gets simpler: one place owns path/env/DB semantics; config-time validation catches missing apps before browser startup; shell `cat` disappears.

Migration path: Migrate core first and verify no marker `cat` failures. Migrate grants to `/workspace/examples/grants`. Migrate veille preserving `N3TX_CHAT_LLM=test`. Decide whether perf has a current app before re-adding.

Risk: Config evaluation now creates temp paths. Keep cleanup explicit and avoid hiding app-specific seeding behavior.

#### S2 — Separate Adaptive Sizes From Display Modes

Current state: `row` is encoded in `Component.SIZES`, which mixes responsive sizes with a semantic table-row mode (`Component.js:25-34`, `05-improvements.md:380-389`).

Proposed change:

```javascript
class Component extends HTMLElement {
  static ADAPTIVE_SIZES = ['xs', 'sm', 'md', 'lg', 'xl'];
  static DISPLAY_MODES = [...Component.ADAPTIVE_SIZES, 'row'];
  static SIZES = Component.DISPLAY_MODES; // compatibility during migration
  static ALIASES = {
    pill: 'xs', 'list-item': 'sm', card: 'md', detail: 'lg', page: 'xl', row: 'row',
  };
}
```

What gets simpler: tests can assert five adaptive breakpoints while table tests assert `row` display support.

Migration path: Add constants, update docs, migrate display tests, keep `SIZES` for compatibility.

Risk: Adds names to a small API; mitigate by documenting `SIZES` as legacy aggregate.

#### S3 — Canonical Schema Fixture Governance

Current state: `mock-schemas.js` says it mirrors real backend schemas, but tests still assert stale method names such as Product `like()` (`05-improvements.md:236-245`).

Proposed change:

```javascript
// tests/frontend/tests/integration/helpers/schema-contracts.js
export const ProductMethodNames = Object.freeze(['comment', 'favorite', 'countdown']);
export const CommentMethodNames = Object.freeze(['like', 'reply']);

export function expectSchemaMethods(schema, expected) {
  expect(Object.keys(schema.methods || {}).sort()).toEqual([...expected].sort());
}

export function expectInstanceMethods(instance, expected) {
  for (const method of expected) expect(typeof instance[method]).toBe('function');
}
```

What gets simpler: schema facts are named once; stale social-method drift is obvious.

Migration path: Replace Product `like` expectations with `favorite`; add a fixture contract test. Later generate snapshots from seeded `examples/core` if drift recurs.

Risk: Static constants still require maintenance; generation adds backend dependency.

### Composability & Extensibility Propositions

#### E1 — Component Ownership Map

Current friction: Tests cannot tell whether `../../components/foo.js` is a framework package component or an app/example component. Missing example files look like product package regressions.

Proposed design:

```javascript
// tests/frontend/tests/helpers/component-owner.js
export const COMPONENT_OWNERS = Object.freeze({
  'ntx-item': 'ui',
  'ntx-list': 'ui',
  'ntx-row': 'ui',
  'ntx-profile': 'ui',
  'ntx-agent': 'agents',
  'ntx-favorites': 'examples/core',
  'ntx-logs': 'examples/core',
});

export function componentImport(owner, tag) {
  if (owner === 'ui') return `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/${tag}.js`;
  if (owner === 'agents') return `/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/${tag}.js`;
  if (owner.startsWith('examples/')) return `/workspace/${owner}/static/components/${tag}.js`;
  throw new Error(`Unknown component owner: ${owner}`);
}
```

What it enables: App-local tests, framework tests, and agent tests can share conventions without alias ambiguity.

Effort estimate: Low.

#### E2 — DOM Contract Levels

Current friction: Tests freeze private DOM/CSS implementation details and create false regressions.

Proposed design:

```javascript
export function expectStylesheetLink(root, filename) {
  const link = root.querySelector('link[rel="stylesheet"]');
  expect(link).toBeTruthy();
  expect(link.getAttribute('href')).toContain(filename);
}

export function expectVisibleText(root, text) {
  expect(root.textContent).toContain(text);
}

export function expectPublicClass(root, selector) {
  expect(root.querySelector(selector)).toBeTruthy();
}
```

What it enables: Test authors choose semantic, structural-public, or private-source assertions explicitly.

Effort estimate: Low.

#### E3 — Generated Method Contract Tests

Current friction: Method tests can bypass generated schema wrappers and miss actual frontend method-call behavior.

Proposed design:

```javascript
it('generated schema method maps positional args to named parameters', async () => {
  const Product = await registerMockProductSchema();
  const product = new Product({ id: 1, name: 'Camera' });
  const call = vi.spyOn(product, 'call').mockResolvedValue({ ok: true });

  await product.comment({ text: 'hello' });

  expect(call).toHaveBeenCalledWith('comment', { comment: { text: 'hello' } });
});
```

What it enables: Product fixes for `NTT.js` can be made test-first and narrow.

Effort estimate: Low.

### Resilience Propositions

#### R1 — Config-Time App Validation

Current failure mode: Stale paths fail inside shell commands or setup scripts.

Proposed improvement: `validateE2EApp(app)` checks `root`, `main.py`, seed script, port, and health path before `defineConfig()` returns.

Blast radius reduction: Path errors become single clear config failures instead of cascading Playwright startup logs.

#### R2 — Seeded DB Sanity Probe

Current failure mode: A reused server or wrong DB can make browser tests pass/fail against stale data.

Proposed improvement: After server boot, query a known seeded endpoint or marker record and assert run-specific DB path was used.

Blast radius reduction: Prevents false browser failures caused by stale servers or wrong databases (`03-quality-risks.md:31`, `03-quality-risks.md:98`).

#### R3 — Suite Tiering / Maintained Defaults

Current failure mode: The aggregate command runs maintained and stale suites together, hiding root causes (`03-quality-risks.md:27`).

Proposed improvement:

```python
Suite(name='e2e-perf', tier='optional', maintained=False, ...)
Suite(name='e2e-grants', tier='default', maintained=True, ...)
```

Blast radius reduction: Default red output reflects maintained contracts; optional suites remain runnable.

#### R4 — Vitest Isolation Controls

Current failure mode: Import-heavy suites repeatedly reset modules and can trigger worker OOM or singleton leakage (`03-quality-risks.md:33`, `03-quality-risks.md:88-92`).

Proposed improvement: Constrain workers for integration suites or add runtime singleton reset helpers.

Blast radius reduction: Memory failures stop obscuring contract failures.

### Proposition Priority Matrix

| # | Proposition | Simplifies | Impact | Effort | Risk | Enables |
|---:|---|---|---|---|---|---|
| S1 | Shared Playwright run environment | Marker/env/path/server duplication | Very high | Medium | Medium | Trustworthy browser runs |
| S2 | Adaptive sizes vs display modes | `row` contract ambiguity | Medium | Medium | Medium | Clear display tests/docs |
| S3 | Canonical schema fixtures | Schema method drift | High | Low | Low | Reliable schema bootstrap tests |
| E1 | Component ownership map | Package/example import ambiguity | High | Low | Low | App-local component testing |
| E2 | DOM contract levels | Stale private DOM/CSS assertions | Medium | Low | Low | Safer component refactors |
| E3 | Generated method contract tests | Under-tested DynamicClass methods | Very high | Low | Low | Test-first product bug fixes |
| R1 | Config-time app validation | Stale path crashes | High | Low | Low | Early harness failure clarity |
| R2 | Seeded DB sanity probe | Wrong DB/server reuse | High | Medium | Low | Reliable E2E data isolation |
| R3 | Suite tiering | Broad red output | Medium | Low | Low | Maintained default command |
| R4 | Vitest isolation controls | OOM/singleton noise | Medium | Medium | Medium | Stable full Vitest runs |

## Contract Triage for Reproduced Failure Clusters

| Failure cluster | Reproduced symptom | Classification | Intended behavior | Evidence | Proposed target |
|---|---|---|---|---|---|
| `ntx-favorites` import | Missing `../../components/ntx-favorites.js` through Vitest alias. | Infrastructure/stale ownership. | `ntx-favorites` is currently example-local unless intentionally promoted. | Alias to package UI (`tests/frontend/vitest.config.js:31`); example file (`examples/core/static/components/ntx-favorites.js:1-15`); `01-architecture.md:178`. | Move/re-alias as example component test or promote with docs. |
| `ntx-logs` import | Missing `../../components/ntx-logs.js`. | Infrastructure/stale ownership. | `ntx-logs` is example-local log viewer, not `n3tx-ui` public component. | `tests/frontend/tests/components/ntx-logs.test.js:35`; `examples/core/static/components/ntx-logs.js:1`; `01-architecture.md:179`. | Same as above. |
| `ntx-ref-picker` inline style | Test expects `<style>`. | Stale test. | Standalone ref picker links external CSS. | `ntx-ref-picker.js:85-92`; `ntx-ref-picker.css:1-188`; `02-api-contracts.md:86`. | Assert stylesheet link and public behavior. |
| `NTTRefPicker.styles` | Test expects static CSS string. | Stale test. | `styles` is `Component` subclass hook; ref picker is standalone. | `ntx-ref-picker.js:28-30`; `packages/n3tx-ui/docs/components.md:65`; `02-api-contracts.md:87`. | Remove static style assertion. |
| `Component.SIZES` five modes | Tests expect `xs-sm-md-lg-xl` only. | Stale test/docs gap; current intended product contract includes `row`. | `row` is valid display mode; adaptive sizes remain five. | `Component.js:25-34`; `ntx-row.js:30-42`; `packages/n3tx-ui/docs/components.md:176-184`; contradiction noted in `02-api-contracts.md:89-90`. | Add `ADAPTIVE_SIZES`/`DISPLAY_MODES`; update tests/docs. |
| `display-mode-cascade` five aliases | Integration test expects no `row`. | Stale test/docs gap. | `normalizeDisplay('row')` remains valid for table rows. | `Component.js:25-34`; `ListElement.js:20-28`; `05-improvements.md:45`. | Same display split target. |
| `ntx-profile` `.placeholder` | Test queries `.placeholder`. | Stale DOM selector or undocumented selector. | User-facing note exists as `.profile-note`; stable semantic contract is text unless class documented. | `ntx-profile.js:43-57`; `tests/frontend/tests/components/ntx-profile.test.js:154-162`; `02-api-contracts.md:85`. | Assert visible text or document/test `.profile-note`. |
| `ntx-row` save spy | Valid inline edit does not call `save()` in test. | Current intended behavior; reproduced failure likely brittle test/setup until proven otherwise. | Row should validate, call `this.save()`, then return to display when no errors. | `ntx-row.js:129-146`; package docs describe inline edit (`packages/n3tx-ui/docs/components.md:19-27`); API report classifies current contract (`02-api-contracts.md:88`); architecture notes likely validation/mocking fault domain (`01-architecture.md:184`). | Write lifecycle-faithful narrow reproduction around `Formidable.validateForm`; fix test or product based on result. |
| Product `like()` in schema bootstrap | Product instance expected to have `like`. | Stale test. | Product exposes `favorite`; Comment exposes `like`. | `docs/CORE.md:78-83`; `mock-schemas.js` Product `favorite` (`tests/frontend/tests/integration/helpers/mock-schemas.js:127-150`); `02-api-contracts.md:91`. | Replace Product expectation with `favorite`; preserve Comment `like` coverage. |
| Core Playwright marker | Server command fails with missing marker or wrong DB. | Infrastructure. | DB path must be available to web server before startup. | `playwright.config.js:16-20`, `playwright.config.js:50-57`, `global-setup.js:23-38`, `05-improvements.md:31`. | Shared run-env; pass DB path through `webServer.env`. |
| Veille marker | Same marker-file pattern. | Infrastructure. | Same as core, preserving port 5010 and `N3TX_CHAT_LLM=test`. | `veille.playwright.config.js:16-20`, `veille.playwright.config.js:50-60`, `veille.global-setup.js:17-28`. | Migrate after core. |
| Grants path | `cd /workspace/example_grants` fails. | Infrastructure path drift. | Grants app root should be `/workspace/examples/grants` if suite is maintained. | `playwright.grants.config.js:34`; `grants-global-setup.js:12`; `FRONTEND.md:182`; `05-improvements.md:35`. | App registry; update root/env or remove from default. |
| Perf path | Legacy `src/n3tx/...` paths. | Infrastructure/unresolved maintenance. | Either define current perf app or mark suite optional/unmaintained. | `playwright.perf.config.js:8`; `perf-global-setup.js:14`; `03-quality-risks.md:29`. | Decide ownership, then update or exclude. |
| Vitest OOM | Historical worker OOM. | Infrastructure. | Full unit run should not fail from worker memory churn. | `.project/plans/tests/full-test-failure-audit-2026-04-24.md:231`; `03-quality-risks.md:33`. | Worker limits or singleton reset helpers. |
| Generated methods | Not necessarily reproduced by current red cluster; risk found in audit. | Product regression / coverage gap. | Schema-generated method wrappers must map parameters correctly. | `03-quality-risks.md:39`, `03-quality-risks.md:96`; schema method contract `02-api-contracts.md:49-52`. | Add failing generated-method tests before product edit. |

## Downstream Use Guide

### For Bug Hunting

Known risk areas:

| Area | Edge cases | Suggested tests |
|---|---|---|
| DynamicClass generated methods | Named parameters, missing params, multiple params, object params, instance method IDs. | Call generated wrapper directly and assert `call(method, payload)` shape. |
| Method response handling | Structured social updates, duplicate add/remove, ambiguous response fallback pull. | Separate tests for local update, same-entity update, different-entity pull, empty response pull. |
| Ref picker fallback | Missing `modelName` currently can yield `undefineds`. | Treat as bug-like edge; assert safe empty/failure behavior rather than canonizing bad fallback. |
| Row save path | Required fields, hidden/protected fields, checkbox/number coercion, lifecycle connection. | Append element to DOM, enter edit mode via public UI, mock `Formidable.validateForm` narrowly. |
| Playwright DB isolation | Reused server, wrong DB path, stale marker. | Add post-start seed sanity check and disable reuse for default isolation-sensitive suites. |
| Vitest singleton state | NTT registry, Matrix root, customElements registration, WebSocket instances. | Prefer reset helpers over repeated `vi.resetModules()` where possible. |

### For Feature Development

Use schema-first patterns. If a feature changes fields, methods, access, renderer hints, `$defs`, or response shape, update backend schema/docs and then frontend fixtures/tests. Do not duplicate model facts in component code when the schema already carries them (`docs/CORE.md:149-168`, `FRONTEND.md:224-247`).

Choose component base class deliberately: `NTTElement`/`NTTItem` for one entity, `ListElement`/`NTTList` for collections, `NTTMethod`/`NTTStream` for actions/streams, standalone `HTMLElement` only when no Actor/NTT lifecycle is needed (`04-extensibility.md:222-238`).

For CSS, use `get styles()` on `Component` subclasses and linked CSS for standalone components; use canonical `--ntx-*` tokens (`04-extensibility.md:228`, `packages/n3tx-ui/docs/styling.md:60-79`).

Test new framework components under package component tests. Test example/app components through explicit example/app import roots or browser flows. Do not rely on `../../components` unless the component belongs to `n3tx-ui`.

### For Integration Planning

Boundaries:

| Boundary | Checklist |
|---|---|
| Backend schema to frontend runtime | Schema includes `$id`, `$schema`, `properties`, `methods`, `$defs`, `ui`, `access`; fixtures reflect live schema. |
| Runtime to visual components | Component reads schema/proto/value; display mode semantics are documented; methods use generated wrappers. |
| Package static dirs to app shell | App-specific static overrides are intentional; package components are imported from package dirs; agents UI imports are explicit. |
| Vitest to product code | Aliases match ownership; setup mocks browser APIs; tests avoid private implementation details unless marked source-contract. |
| Playwright to app | App root exists; seed runs; DB path is passed directly; health endpoint matches app; teardown removes temp data. |

### For Refactoring

Technical debt sequence:

1. Stabilize harness infrastructure: shared run-env, app registry, direct DB env, path validation.
2. Classify and update stale tests: component ownership, ref-picker CSS, profile note, Product `favorite`, display modes.
3. Add narrow product-risk tests: generated methods and method response handling.
4. Only then edit product runtime code if tests prove regressions.
5. Harden full-suite execution: worker controls, suite tiering, overview/report parser improvements.

Risks:

| Risk | Mitigation |
|---|---|
| Changing product to satisfy stale test | Require contract decision note before product edit. |
| Shared harness hides app-specific behavior | Registry supports per-app env/seed overrides; keep setup explicit. |
| Display constants break consumers | Keep `SIZES` compatibility alias while adding clearer constants. |
| Schema fixture generation becomes slow | Start with static constants; automate only if drift recurs. |

## Appendix: Complete Finding Index

| ID | Dimension | Type | Severity | Finding/Proposition | File(s) | Status |
|---|---|---|---|---|---|---|
| A1 | Architecture | Finding | Critical | Harness mixes product and test contracts; failures need classification. | `01-architecture.md` | Consolidated |
| A2 | Architecture | Finding | Critical | Vitest alias maps example component imports to package UI. | `tests/frontend/vitest.config.js`, `examples/core/static/components/*` | Action needed |
| A3 | Architecture | Finding | Critical | Playwright grants/perf path drift. | `playwright.grants.config.js`, `playwright.perf.config.js` | Action needed |
| A4 | Architecture | Finding | High | Marker-file IPC is fragile. | `playwright.config.js`, `global-setup.js` | Action needed |
| A5 | Architecture | Strength | Medium | Runner centralizes suite execution and overview JSON. | `scripts/run-frontend-tests.py` | Keep |
| API1 | API Contracts | Finding | High | `ntx-row` save is current intended contract. | `ntx-row.js`, `ntx-row.test.js` | Needs lifecycle-faithful reproduction |
| API2 | API Contracts | Finding | High | Row display was classified unresolved due docs disagreement. | `Component.js`, docs | Resolved here as current product contract plus doc/test drift |
| API3 | API Contracts | Finding | Medium | Profile DOM selector undocumented. | `ntx-profile.js`, `ntx-profile.test.js` | Action needed |
| API4 | API Contracts | Finding | High | Ref-picker static/inline style assertions stale. | `ntx-ref-picker.js`, `ntx-ref-picker.test.js` | Action needed |
| API5 | API Contracts | Finding | High | Product `like` expectation stale. | `mock-schemas.js`, `schema-bootstrap.test.js` | Action needed |
| QR1 | Quality | Risk | High | Aggregate runner hides root causes. | `scripts/run-frontend-tests.py` | Mitigate with tiering/classification |
| QR2 | Quality | Risk | High | Grants stale path and DB env drift. | `playwright.grants.config.js`, `grants-global-setup.js` | Action needed |
| QR3 | Quality | Risk | High | Perf stale paths and env names. | `playwright.perf.config.js`, `perf-global-setup.js` | Decide maintenance |
| QR4 | Quality | Risk | High | Server reuse can target wrong DB/code. | Playwright configs | Add DB sanity probe |
| QR5 | Quality | Risk | High | Vitest OOM from singleton churn. | `vitest.config.js`, integration tests | Harden later |
| QR6 | Quality | Risk | Critical | Generated DynamicClass method mapping likely under-tested product bug. | `NTT.js` | Add test-first reproducer |
| QR7 | Quality | Risk | High | Method response handling contract hotspot. | `NTT.js`, method tests | Add coverage |
| QR8 | Quality | Risk | Medium | Ref picker `undefineds` fallback canonized by test. | `ntx-ref-picker.js`, test | Fix after classification |
| EX1 | Extensibility | Strength | Medium | Adding ordinary Vitest tests is easy. | `vitest.config.js`, `setup.js` | Keep |
| EX2 | Extensibility | Constraint | High | App-specific E2E suite addition is hard and duplicated. | Playwright configs | Shared harness |
| EX3 | Extensibility | Proposition | High | Use backend-generated schemas or governed fixtures. | `mock-schemas.js` | Proposed |
| EX4 | Extensibility | Proposition | Medium | Test public behavior through DOM/events/TX, not private internals. | Component tests | Proposed |
| IM1 | Improvements | Proposition | Very high | Shared Playwright run environment. | E2E harness/configs | Priority 1 |
| IM2 | Improvements | Proposition | High | App registry instead of hardcoded paths. | E2E harness/configs | Priority 2 |
| IM3 | Improvements | Proposition | High | Canonical schema fixtures. | `mock-schemas.js`, schema tests | Priority 3 |
| IM4 | Improvements | Proposition | High | Component ownership map. | Vitest config/tests | Priority 4 |
| IM5 | Improvements | Proposition | Medium | DOM contract levels/helpers. | Component tests/docs | Priority 5 |
| IM6 | Improvements | Proposition | Medium | Row/adaptive display constants split. | `Component.js`, docs/tests | Priority 6 |
| IM7 | Improvements | Proposition | Medium | Contract decision notes for red clusters. | `.project/contracts/frontend-tests` | Priority 7 |
| SYN1 | Synthesis | Decision | High | Treat `row` as current intended contract, not product regression. | `Component.js`, `ntx-row.js`, package docs | Resolved contradiction |
| SYN2 | Synthesis | Decision | High | Treat `ntx-row` failure as current intended behavior with likely brittle test/setup until reproduced. | `ntx-row.js`, reports | Resolved contradiction |
| SYN3 | Synthesis | Decision | Critical | Do not change product code for stale import/style/profile/schema assertions. | Reports 01-05 | Governance rule |
