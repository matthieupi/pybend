# Frontend Test Harness and Contracts — Extensibility Audit

## Scope

This audit covers the frontend verification subsystem that connects the Python suite runner, Vitest/jsdom tests, Playwright browser harnesses, app-specific E2E configs, frontend component contracts, schema mocks, and recovery plans. The harness is explicitly split into Vitest for `tests/**/*.test.js` and Playwright for `tests/e2e/*.spec.js`, with specialized Playwright configs for grants, veille, and performance suites. Evidence: `scripts/run-frontend-tests.py:4`, `scripts/run-frontend-tests.py:6`, `scripts/run-frontend-tests.py:7`, `scripts/run-frontend-tests.py:9`.

The product contract being tested is schema-driven frontend rendering: backend JSON Schema is the single frontend/backend contract, carrying properties, UI hints, access rules, methods, nested `$defs`, and identifiers. Evidence: `docs/CORE.md:109`, `docs/CORE.md:111`, `docs/CORE.md:133`, `docs/CORE.md:145`, `FRONTEND.md:218`, `FRONTEND.md:220`.

The key implementation boundary is runtime versus visual UI: `n3tx-core` provides non-visual JS runtime files such as `NTT.js` and `Component.js`, while `n3tx-ui` provides visual components such as `ntx-item`, `ntx-list`, `ntx-row`, `ntx-ref-picker`, and `ntx-profile`. Evidence: `FRONTEND.md:20`, `FRONTEND.md:21`, `FRONTEND.md:22`, `FRONTEND.md:42`, `FRONTEND.md:57`.

The requested files were read for runner/config/setup/harness behavior, component contracts, mocks, and current recovery trajectory. Evidence: `scripts/run-frontend-tests.py:85`, `tests/frontend/vitest.config.js:8`, `tests/frontend/tests/setup.js:1`, `tests/frontend/tests/e2e/playwright.config.js:21`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:23`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:121`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:30`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:21`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:26`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:11`.

## Dependency Graph

```text
                            docs / plans
       FRONTEND.md, docs/CORE.md, components.md, styling.md
                              |
                              v
 scripts/run-frontend-tests.py -------------------------------------+
     | builds Suite list, filters core specs, writes overview        |
     |                                                              |
     +--> Vitest ------------------------------------------------+   |
     |      vitest.config.js aliases package static dirs          |   |
     |      tests/setup.js installs jsdom mocks and cleanup       |   |
     |      *.test.js mock schema/component contracts             |   |
     |                                                           |   |
     +--> Playwright core ---------------------------------------+   |
     |      global-setup seeds examples/core temp DB              |   |
     |      playwright.config boots examples/core webServer       |   |
     |      fixtures/auth.js supplies token helpers               |   |
     |                                                           |   |
     +--> Playwright grants -------------------------------------+   |
     |      grants-global-setup seeds /workspace/example_grants   |   |
     |      playwright.grants.config runs grants-*.spec.js        |   |
     |                                                           |   |
     +--> Playwright veille -------------------------------------+   |
     |      veille.global-setup seeds /workspace/apps/veille      |   |
     |      veille.playwright.config boots port 5010/test LLM     |   |
     |                                                           |   |
     +--> Playwright perf ---------------------------------------+   |
            perf-global-setup seeds profiling DB                  |
            perf-harness.js monkey-patches runtime methods        |

 Runtime contracts under test:
   Component.js -> NTT.js -> NTTElement/ListElement -> ntx-item/ntx-row/ntx-ref-picker/ntx-profile
        ^                ^                         ^
        |                |                         |
   schema mocks      schema bootstrap         browser DOM/assertions
```

The runner owns suite orchestration, not test semantics: `build_suites()` returns one unit suite plus four E2E suites, each represented by a `Suite` dataclass with `name`, `cwd`, `command`, optional appended args, env, and description. Evidence: `scripts/run-frontend-tests.py:44`, `scripts/run-frontend-tests.py:45`, `scripts/run-frontend-tests.py:49`, `scripts/run-frontend-tests.py:85`, `scripts/run-frontend-tests.py:151`.

The default core Playwright suite avoids duplicate execution by excluding `performance.spec.js` and specs prefixed with `grants-` or `veille-`. Evidence: `scripts/run-frontend-tests.py:67`, `scripts/run-frontend-tests.py:68`, `scripts/run-frontend-tests.py:69`, `scripts/run-frontend-tests.py:71`, `scripts/run-frontend-tests.py:75`.

The runner passes additional CLI args to every selected suite when `append_args=True`, which is useful for targeted file filters but also means a broad extra arg can accidentally apply to incompatible runner families. Evidence: `scripts/run-frontend-tests.py:49`, `scripts/run-frontend-tests.py:90`, `scripts/run-frontend-tests.py:105`, `scripts/run-frontend-tests.py:158`, `scripts/run-frontend-tests.py:491`, `scripts/run-frontend-tests.py:492`.

The runner persists longitudinal status in `.project/test-runs/frontend-test-overview.json`, including created time, command, totals, suite statuses, counts, messages, and previous statuses. Evidence: `scripts/run-frontend-tests.py:30`, `scripts/run-frontend-tests.py:392`, `scripts/run-frontend-tests.py:397`, `scripts/run-frontend-tests.py:401`, `scripts/run-frontend-tests.py:402`, `scripts/run-frontend-tests.py:414`, `scripts/run-frontend-tests.py:421`.

## Extension Points

| Extension point | Mechanism | Difficulty | Recommended pattern | Evidence |
|---|---|---:|---|---|
| Add a Vitest suite | Add `*.test.js` under `tests/frontend/tests/**` | Easy | Import via existing relative aliases and keep schema fixtures close to the component under test | `tests/frontend/vitest.config.js:13`, `tests/frontend/vitest.config.js:17`, `tests/frontend/vitest.config.js:31` |
| Add cross-package static imports | Extend Vitest alias list | Moderate | Add explicit aliases only for real package-static import shapes, not app-specific files | `tests/frontend/vitest.config.js:18`, `tests/frontend/vitest.config.js:20`, `tests/frontend/vitest.config.js:24`, `tests/frontend/vitest.config.js:30` |
| Add global jsdom capability | Extend `tests/setup.js` mocks | Moderate | Mock browser primitives centrally, then reset them in `beforeEach`/`afterEach` | `tests/frontend/tests/setup.js:1`, `tests/frontend/tests/setup.js:37`, `tests/frontend/tests/setup.js:47`, `tests/frontend/tests/setup.js:75`, `tests/frontend/tests/setup.js:131` |
| Add a core E2E spec | Add `*.spec.js` not matching excluded names/prefixes | Easy | Use core Playwright config and seeded `examples/core` app | `scripts/run-frontend-tests.py:67`, `scripts/run-frontend-tests.py:72`, `tests/frontend/tests/e2e/playwright.config.js:22`, `tests/frontend/tests/e2e/playwright.config.js:50` |
| Add an app-specific E2E suite | Add Playwright config + setup/teardown + runner `Suite` | Hard | Copy the run-unique core/veille marker style, not the older fixed-marker grants/perf style | `scripts/run-frontend-tests.py:109`, `scripts/run-frontend-tests.py:122`, `tests/frontend/tests/e2e/playwright.config.js:16`, `tests/frontend/tests/e2e/veille.playwright.config.js:16`, `tests/frontend/tests/e2e/grants-global-setup.js:21` |
| Add performance instrumentation | Inject a module that monkey-patches stable runtime entry points | Moderate | Keep instrumentation in tests and set an explicit sentinel on `window` | `tests/frontend/tests/e2e/perf-harness.js:1`, `tests/frontend/tests/e2e/perf-harness.js:7`, `tests/frontend/tests/e2e/perf-harness.js:17`, `tests/frontend/tests/e2e/perf-harness.js:27`, `tests/frontend/tests/e2e/perf-harness.js:79` |
| Add a visual component | Extend `Component`, `NTTElement`, `NTTItem`, or standalone `HTMLElement` depending on lifecycle needs | Moderate | Use schema-driven renderer hints and docs-backed lifecycle hooks | `packages/n3tx-ui/docs/components.md:11`, `packages/n3tx-ui/docs/components.md:31`, `packages/n3tx-ui/docs/components.md:65`, `docs/frontend/COMPONENTS.md:162` |
| Add component CSS | Return stylesheet URL(s) from `styles` or link CSS manually for standalone components | Easy | Prefer `Component.styles` for Component subclasses; standalone elements can link static CSS in shadow DOM | `docs/frontend/COMPONENTS.md:93`, `docs/frontend/COMPONENTS.md:97`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:258`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:30` |
| Add theme tokens | Add app-level token entrypoint after shared themes | Easy | Use canonical `--ntx-*` tokens only | `packages/n3tx-ui/docs/styling.md:27`, `packages/n3tx-ui/docs/styling.md:35`, `packages/n3tx-ui/docs/styling.md:40`, `packages/n3tx-ui/docs/styling.md:62` |

## Integration Boundaries

### Runner Boundary

The runner boundary is a Python process boundary around `npx vitest` and `npx playwright`. It prints cwd and command before launching each subprocess, streams merged stdout/stderr, parses summary counts from runner output, and converts failures into final process exit behavior. Evidence: `scripts/run-frontend-tests.py:154`, `scripts/run-frontend-tests.py:160`, `scripts/run-frontend-tests.py:164`, `scripts/run-frontend-tests.py:170`, `scripts/run-frontend-tests.py:181`, `scripts/run-frontend-tests.py:226`, `scripts/run-frontend-tests.py:506`, `scripts/run-frontend-tests.py:521`.

The count parser is output-format coupled: Vitest is parsed from the trailing `Tests` summary, while Playwright counts are aggregated from the last 40 lines excluding rows with `[` or `›`. Evidence: `scripts/run-frontend-tests.py:201`, `scripts/run-frontend-tests.py:204`, `scripts/run-frontend-tests.py:208`, `scripts/run-frontend-tests.py:211`, `scripts/run-frontend-tests.py:214`, `scripts/run-frontend-tests.py:216`.

Recommended pattern: when adding runner families, provide a suite-specific parser or a machine-readable reporter instead of extending the current regex heuristics. Evidence for current heuristic coupling: `scripts/run-frontend-tests.py:31`, `scripts/run-frontend-tests.py:181`, `scripts/run-frontend-tests.py:201`, `scripts/run-frontend-tests.py:211`.

### Vitest Boundary

Vitest runs in jsdom with globals, one setup file, `tests/**/*.test.js`, 10s timeout, and restored mocks. Evidence: `tests/frontend/vitest.config.js:8`, `tests/frontend/vitest.config.js:10`, `tests/frontend/vitest.config.js:11`, `tests/frontend/vitest.config.js:12`, `tests/frontend/vitest.config.js:13`, `tests/frontend/vitest.config.js:14`, `tests/frontend/vitest.config.js:15`.

Vitest aliases translate historical relative imports like `../../core/`, `../../components/`, `../../widgets/`, and `../../generators/` into package static directories. Evidence: `tests/frontend/vitest.config.js:4`, `tests/frontend/vitest.config.js:5`, `tests/frontend/vitest.config.js:20`, `tests/frontend/vitest.config.js:31`, `tests/frontend/vitest.config.js:32`, `tests/frontend/vitest.config.js:33`.

Vitest also contains targeted cross-package aliases for agent components importing UI siblings such as `./ntx-item.js`, `./ntx-list.js`, `./ntx-stream.js`, and `./ntx-icon.js`. Evidence: `tests/frontend/vitest.config.js:24`, `tests/frontend/vitest.config.js:25`, `tests/frontend/vitest.config.js:26`, `tests/frontend/vitest.config.js:27`, `tests/frontend/vitest.config.js:29`.

The jsdom setup provides localStorage with both method and bracket access because runtime HTTP uses `window.localStorage['jwtToken']`. Evidence: `tests/frontend/tests/setup.js:8`, `tests/frontend/tests/setup.js:9`, `tests/frontend/tests/setup.js:10`, `tests/frontend/tests/setup.js:20`, `tests/frontend/tests/setup.js:35`.

The jsdom setup mocks `fetch`, `ResizeObserver`, and `WebSocket`, then resets storage, session storage, fetch, timers, WebSockets, DOM, and window notification globals around each test. Evidence: `tests/frontend/tests/setup.js:37`, `tests/frontend/tests/setup.js:47`, `tests/frontend/tests/setup.js:75`, `tests/frontend/tests/setup.js:131`, `tests/frontend/tests/setup.js:143`, `tests/frontend/tests/setup.js:146`, `tests/frontend/tests/setup.js:156`, `tests/frontend/tests/setup.js:165`, `tests/frontend/tests/setup.js:166`, `tests/frontend/tests/setup.js:167`, `tests/frontend/tests/setup.js:170`, `tests/frontend/tests/setup.js:176`, `tests/frontend/tests/setup.js:179`, `tests/frontend/tests/setup.js:189`.

The setup now fails tests on leaked unhandled rejections after allowing microtasks to flush, which matches the P5 hardening target. Evidence: `tests/frontend/tests/setup.js:122`, `tests/frontend/tests/setup.js:126`, `tests/frontend/tests/setup.js:127`, `tests/frontend/tests/setup.js:156`, `tests/frontend/tests/setup.js:160`, `tests/frontend/tests/setup.js:194`, `.project/plans/tests/p5-suite-hardening-plan.md:93`, `.project/plans/tests/p5-suite-hardening-plan.md:119`.

### Playwright Core Boundary

Core Playwright uses `examples/core`, injects package source directories through `PYTHONPATH`, starts the server on port 5000, and waits for `/Product`. Evidence: `tests/frontend/tests/e2e/playwright.config.js:7`, `tests/frontend/tests/e2e/playwright.config.js:12`, `tests/frontend/tests/e2e/playwright.config.js:50`, `tests/frontend/tests/e2e/playwright.config.js:52`, `tests/frontend/tests/e2e/playwright.config.js:55`, `tests/frontend/tests/e2e/playwright.config.js:58`.

Core setup creates a temp directory and DB, writes the DB path to a run-specific marker, seeds the core app with `seed.py`, and passes `N3TX_SQLITE_DB` into the seed process. Evidence: `tests/frontend/tests/e2e/global-setup.js:23`, `tests/frontend/tests/e2e/global-setup.js:25`, `tests/frontend/tests/e2e/global-setup.js:26`, `tests/frontend/tests/e2e/global-setup.js:35`, `tests/frontend/tests/e2e/global-setup.js:36`, `tests/frontend/tests/e2e/global-setup.js:37`, `tests/frontend/tests/e2e/global-setup.js:42`, `tests/frontend/tests/e2e/global-setup.js:47`.

Core teardown reads the marker, removes the temp directory, and removes the marker file. Evidence: `tests/frontend/tests/e2e/global-teardown.js:8`, `tests/frontend/tests/e2e/global-teardown.js:10`, `tests/frontend/tests/e2e/global-teardown.js:13`, `tests/frontend/tests/e2e/global-teardown.js:17`, `tests/frontend/tests/e2e/global-teardown.js:19`, `tests/frontend/tests/e2e/global-teardown.js:27`, `tests/frontend/tests/e2e/global-teardown.js:28`.

The auth fixture encodes the browser/runtime auth contract: API login returns either top-level `token` or `data.token`, and browser auth is stored in `localStorage.jwtToken` after a page origin exists. Evidence: `tests/frontend/tests/e2e/fixtures/auth.js:23`, `tests/frontend/tests/e2e/fixtures/auth.js:24`, `tests/frontend/tests/e2e/fixtures/auth.js:28`, `tests/frontend/tests/e2e/fixtures/auth.js:36`, `tests/frontend/tests/e2e/fixtures/auth.js:41`, `tests/frontend/tests/e2e/fixtures/auth.js:43`.

### App-Specific Suite Boundaries

Grants uses a separate Playwright config with `testMatch: 'grants-*.spec.js'`, a grants setup/teardown pair, and a webServer command that runs `/workspace/example_grants`. Evidence: `tests/frontend/tests/e2e/playwright.grants.config.js:9`, `tests/frontend/tests/e2e/playwright.grants.config.js:11`, `tests/frontend/tests/e2e/playwright.grants.config.js:12`, `tests/frontend/tests/e2e/playwright.grants.config.js:13`, `tests/frontend/tests/e2e/playwright.grants.config.js:33`, `tests/frontend/tests/e2e/playwright.grants.config.js:34`.

Grants setup writes a fixed marker path under `/tmp`, seeds with `NTT_SQLITE_DB`, and does not inject the package `PYTHONPATH` used by core/veille. Evidence: `tests/frontend/tests/e2e/grants-global-setup.js:12`, `tests/frontend/tests/e2e/grants-global-setup.js:18`, `tests/frontend/tests/e2e/grants-global-setup.js:21`, `tests/frontend/tests/e2e/grants-global-setup.js:26`, `tests/frontend/tests/e2e/grants-global-setup.js:27`.

Veille uses a separate port, app cwd, source-tree `PYTHONPATH`, run-specific marker, and deterministic chat LLM. Evidence: `tests/frontend/tests/e2e/veille.playwright.config.js:7`, `tests/frontend/tests/e2e/veille.playwright.config.js:16`, `tests/frontend/tests/e2e/veille.playwright.config.js:17`, `tests/frontend/tests/e2e/veille.playwright.config.js:36`, `tests/frontend/tests/e2e/veille.playwright.config.js:51`, `tests/frontend/tests/e2e/veille.playwright.config.js:52`, `tests/frontend/tests/e2e/veille.playwright.config.js:56`, `tests/frontend/tests/e2e/veille.playwright.config.js:58`.

Veille setup mirrors the core temp DB pattern and seeds with `N3TX_CHAT_LLM=test`. Evidence: `tests/frontend/tests/e2e/veille.global-setup.js:17`, `tests/frontend/tests/e2e/veille.global-setup.js:18`, `tests/frontend/tests/e2e/veille.global-setup.js:21`, `tests/frontend/tests/e2e/veille.global-setup.js:27`, `tests/frontend/tests/e2e/veille.global-setup.js:30`, `tests/frontend/tests/e2e/veille.global-setup.js:31`, `tests/frontend/tests/e2e/veille.global-setup.js:39`.

Performance uses older paths under `src/n3tx/...` and fixed marker naming via `perf-global-setup.js`, while the main repository docs and current package layout describe `packages/n3tx-core`, `packages/n3tx-ui`, `packages/n3tx-actors`, and `packages/n3tx-agents`. Evidence: `tests/frontend/tests/e2e/playwright.perf.config.js:8`, `tests/frontend/tests/e2e/perf-global-setup.js:14`, `tests/frontend/tests/e2e/perf-global-setup.js:25`, `FRONTEND.md:20`, `FRONTEND.md:21`, `FRONTEND.md:22`.

Recommended pattern: new app-specific suites should follow core/veille run-specific marker and `PYTHONPATH` conventions, not grants/perf fixed-marker or stale-path conventions. Evidence: `tests/frontend/tests/e2e/playwright.config.js:16`, `tests/frontend/tests/e2e/playwright.config.js:17`, `tests/frontend/tests/e2e/veille.playwright.config.js:16`, `tests/frontend/tests/e2e/veille.playwright.config.js:17`, `tests/frontend/tests/e2e/grants-global-setup.js:21`, `tests/frontend/tests/e2e/perf-global-setup.js:25`.

## Data Contracts at Boundaries

### Schema Contract

The frontend consumes schema sections as behavior, not just types: `properties` and field UI hints drive DynamicClass and Formidable, `ui.renderer.*` drives router view tags, `access` drives permission visibility, `methods` drive dynamic method buttons, `$defs` register nested DynamicClasses, and `$id`/`$schema` make instances self-describing. Evidence: `docs/CORE.md:149`, `docs/CORE.md:153`, `docs/CORE.md:154`, `docs/CORE.md:162`, `docs/CORE.md:163`, `docs/CORE.md:164`, `docs/CORE.md:167`, `docs/CORE.md:168`.

`NTT.SCHEMA()` materializes that schema into DynamicClasses, processes `$defs` first, creates the main DynamicClass only if missing, replays queued attach messages, and consumes preloaded data. Evidence: `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:302`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:309`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:316`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:325`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:327`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:332`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:338`.

The DynamicClass value getter injects `$schema` from schema `$id` and `$id` from the instance href, which explains why schema mocks must include current `$id` semantics to test runtime behavior accurately. Evidence: `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:651`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:655`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:657`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:658`.

The current recovery plan explicitly treats stale schema mocks as likely P3 work, including Product social mocks using `favorite`/`favorites`, Comment social mocks using `like`/`likes`, and method widget expectations. Evidence: `.project/plans/tests/p3-p5-test-recovery-plan.md:194`, `.project/plans/tests/p3-p5-test-recovery-plan.md:198`, `.project/plans/tests/p3-p5-test-recovery-plan.md:199`, `.project/plans/tests/p3-p5-test-recovery-plan.md:200`, `.project/plans/tests/p3-p5-test-recovery-plan.md:203`.

### Component Contract

`Component` defines the generic component lifecycle: observed attributes are `model`, `addr`, `hash`, `ref`, and `display`; setting `model` attaches to NTT and sends an `ATTACH` TX; `define()` stores the DynamicClass and calls `definedCallback()`; connected components start resize observation and call `prerender()`. Evidence: `packages/n3tx-core/src/n3tx_core/static/core/Component.js:112`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:127`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:130`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:133`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:183`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:188`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:436`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:444`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:445`.

The docs define Component subclass extension via `styles`, `displayBreakpoints`, `displayModeChanged`, `definedCallback`, and `render`, and they explicitly state `render()` is abstract. Evidence: `docs/frontend/COMPONENTS.md:93`, `docs/frontend/COMPONENTS.md:110`, `docs/frontend/COMPONENTS.md:144`, `docs/frontend/COMPONENTS.md:152`, `docs/frontend/COMPONENTS.md:180`, `docs/frontend/COMPONENTS.md:186`, `docs/frontend/COMPONENTS.md:187`.

`NTTItem` is the default single-entity component, with display/edit toggle, Formidable forms, method buttons, adaptive display methods, and a base edit fallback for custom display components. Evidence: `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:1`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:4`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:5`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:7`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:28`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:30`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:443`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:592`.

`NTTRow` is a table-row specialization that extends `NTTItem`, opts into a custom edit layout, forces row display mode, filters protected/ref fields in edit mode, validates before saving, and emits SELECT on row click. Evidence: `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:1`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:21`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:23`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:30`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:33`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:121`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:122`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:130`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:137`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:142`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:273`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:279`.

`NTTRefPicker` is a standalone `HTMLElement`, not a `Component` subclass, so it links CSS manually and reaches back to its host for parent schema/value contracts. Evidence: `packages/n3tx-ui/docs/components.md:65`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:30`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:37`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:61`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:65`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:79`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:86`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:87`.

`NTTProfile` is also standalone and depends directly on the permissions singleton, rendering either an unauthenticated state or profile card after `permissions.init()`. Evidence: `packages/n3tx-ui/docs/components.md:65`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:7`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:11`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:17`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:22`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:29`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:43`.

### Static Serving and Theme Contract

At runtime, static files from core, UI, and agents are merged into one URL namespace, with app-specific static dirs taking precedence over agents, UI, and core. Evidence: `FRONTEND.md:24`, `FRONTEND.md:206`, `FRONTEND.md:208`, `FRONTEND.md:210`, `FRONTEND.md:211`, `FRONTEND.md:212`, `FRONTEND.md:213`, `FRONTEND.md:214`, `FRONTEND.md:216`.

The theme contract requires pages to link `theme-base.css`, `dark-theme.css`, and `light-theme.css`, and new CSS should use canonical `--ntx-*` tokens rather than legacy aliases. Evidence: `packages/n3tx-ui/docs/styling.md:25`, `packages/n3tx-ui/docs/styling.md:27`, `packages/n3tx-ui/docs/styling.md:29`, `packages/n3tx-ui/docs/styling.md:40`, `packages/n3tx-ui/docs/styling.md:60`, `packages/n3tx-ui/docs/styling.md:62`, `packages/n3tx-ui/docs/styling.md:63`.

`ntx-ref-picker.css` follows the canonical token pattern, using `--ntx-*` variables for border, panels, text, focus rings, and buttons. Evidence: `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.css:16`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.css:18`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.css:37`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.css:62`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.css:73`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.css:181`.

## What Is Easy to Change

Adding ordinary unit/component tests is easy because Vitest auto-includes `tests/**/*.test.js`, aliases existing package static roots, and centralizes browser mocks. Evidence: `tests/frontend/vitest.config.js:13`, `tests/frontend/vitest.config.js:18`, `tests/frontend/vitest.config.js:31`, `tests/frontend/tests/setup.js:37`, `tests/frontend/tests/setup.js:47`, `tests/frontend/tests/setup.js:75`.

Adding core E2E specs is easy when the spec can run against `examples/core`, because the runner automatically includes non-grants/non-veille/non-performance specs and the core Playwright config already seeds an isolated DB. Evidence: `scripts/run-frontend-tests.py:67`, `scripts/run-frontend-tests.py:72`, `tests/frontend/tests/e2e/global-setup.js:23`, `tests/frontend/tests/e2e/global-setup.js:42`, `tests/frontend/tests/e2e/playwright.config.js:50`, `tests/frontend/tests/e2e/playwright.config.js:58`.

Adding schema-driven item renderers is reasonably easy because router/rendering can be driven by `schema.ui.renderer`, lists can choose child tags from schema or attrs, and custom display subclasses inherit default Formidable edit behavior unless they opt out. Evidence: `docs/CORE.md:162`, `packages/n3tx-ui/docs/components.md:62`, `packages/n3tx-ui/docs/components.md:164`, `packages/n3tx-ui/docs/components.md:165`, `packages/n3tx-ui/docs/components.md:186`.

Adding tokenized CSS is easy because the docs define a canonical page/theme contract and existing component CSS shows token usage. Evidence: `packages/n3tx-ui/docs/styling.md:27`, `packages/n3tx-ui/docs/styling.md:35`, `packages/n3tx-ui/docs/styling.md:62`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.css:16`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.css:181`.

## What Is Hard to Change

Changing the schema contract is hard because `NTT.SCHEMA()`, `prototype()`, Formidable, router renderer hints, permissions, methods, and `$defs` all consume different schema sections. Evidence: `docs/CORE.md:149`, `docs/CORE.md:153`, `docs/CORE.md:157`, `docs/CORE.md:162`, `docs/CORE.md:163`, `docs/CORE.md:164`, `docs/CORE.md:167`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:309`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:619`.

Changing DynamicClass lifecycle is hard because pending attaches, instance maps, fetch deduplication, populated normalization, watchers, and method response handling are in one generated class closure. Evidence: `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:619`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:628`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:683`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:811`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:831`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:870`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:902`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:1034`.

Adding app-specific E2E suites is hard because every app needs coordinated seed DB setup, webServer env, port/baseURL, static serving assumptions, auth helpers, teardown, and runner registration. Evidence: `scripts/run-frontend-tests.py:109`, `scripts/run-frontend-tests.py:122`, `tests/frontend/tests/e2e/global-setup.js:42`, `tests/frontend/tests/e2e/playwright.config.js:50`, `tests/frontend/tests/e2e/veille.global-setup.js:30`, `tests/frontend/tests/e2e/veille.playwright.config.js:50`, `tests/frontend/tests/e2e/grants-global-setup.js:26`, `tests/frontend/tests/e2e/playwright.grants.config.js:33`.

Changing component display constants is hard because implementation and tests currently disagree: the implementation includes `row` as a size, one integration test expects that, and another historical unit test expected only five sizes. Evidence: `packages/n3tx-core/src/n3tx_core/static/core/Component.js:26`, `tests/frontend/tests/integration/list-item-interaction.test.js:64`, `tests/frontend/tests/core/Component.test.js:75`, `.project/plans/tests/full-test-failure-audit-2026-04-24.md:270`, `.project/plans/tests/full-test-failure-audit-2026-04-24.md:274`.

## Constraints and Limitations

The runner cannot know whether a failure is product, stale test, infrastructure, or unresolved contract; the recovery plan requires a P-1 contract triage gate before changes. Evidence: `.project/plans/tests/contract-triage-p-1.md:5`, `.project/plans/tests/contract-triage-p-1.md:7`, `.project/plans/tests/contract-triage-p-1.md:14`, `.project/plans/tests/contract-triage-p-1.md:16`, `.project/plans/tests/contract-triage-p-1.md:37`, `.project/plans/tests/contract-triage-p-1.md:43`.

Vitest tests can become stale against implementation because many component tests mock config, Logging, NTT, TX, Permissions, and Formidable rather than booting the full runtime. Evidence: `tests/frontend/tests/components/ntx-ref-picker.test.js:86`, `tests/frontend/tests/components/ntx-ref-picker.test.js:92`, `tests/frontend/tests/components/ntx-ref-picker.test.js:101`, `tests/frontend/tests/components/ntx-ref-picker.test.js:108`, `tests/frontend/tests/components/ntx-ref-picker.test.js:115`, `tests/frontend/tests/components/ntx-ref-picker.test.js:122`, `tests/frontend/tests/components/ntx-row.test.js:3`, `tests/frontend/tests/components/ntx-row.test.js:20`, `tests/frontend/tests/components/ntx-profile.test.js:13`, `tests/frontend/tests/components/ntx-profile.test.js:19`.

Some historical failures are known stale-contract candidates rather than confirmed product defects, including profile placeholder expectations, ref-picker static style exposure, row validation/save behavior, and schema bootstrap expectations. Evidence: `.project/plans/tests/full-test-failure-audit-2026-04-24.md:248`, `.project/plans/tests/full-test-failure-audit-2026-04-24.md:254`, `.project/plans/tests/full-test-failure-audit-2026-04-24.md:264`, `.project/plans/tests/full-test-failure-audit-2026-04-24.md:392`, `.project/plans/tests/README.md:207`, `.project/plans/tests/README.md:212`, `.project/plans/tests/README.md:213`.

Playwright isolation is better in core/veille than in grants/perf because core/veille use run-specific markers, while grants/perf use fixed marker names. Evidence: `tests/frontend/tests/e2e/playwright.config.js:16`, `tests/frontend/tests/e2e/playwright.config.js:17`, `tests/frontend/tests/e2e/veille.playwright.config.js:16`, `tests/frontend/tests/e2e/veille.playwright.config.js:17`, `tests/frontend/tests/e2e/grants-global-setup.js:21`, `tests/frontend/tests/e2e/perf-global-setup.js:25`.

The perf config appears structurally stale relative to the current package split because it points at `src/n3tx/example` and `src/n3tx/core/tests/profiling/seed_perf.py`, while the active frontend docs define the package split under `packages/`. Evidence: `tests/frontend/tests/e2e/playwright.perf.config.js:8`, `tests/frontend/tests/e2e/perf-global-setup.js:14`, `FRONTEND.md:20`, `FRONTEND.md:21`, `FRONTEND.md:22`.

## Current Evolution Trajectory

The recovery trajectory has moved from broad runtime breakage toward UI contract drift and suite hardening: the latest plans mark P0 grants auth, P1 transport, and tracked P2 NTT/DynamicClass as resolved, with P3 Formidable/method/UI, P4 browser navigation, and P5 hardening still pending. Evidence: `.project/plans/tests/p3-p5-test-recovery-plan.md:25`, `.project/plans/tests/p3-p5-test-recovery-plan.md:27`, `.project/plans/tests/p3-p5-test-recovery-plan.md:28`, `.project/plans/tests/p3-p5-test-recovery-plan.md:29`, `.project/plans/tests/p3-p5-test-recovery-plan.md:30`, `.project/plans/tests/p3-p5-test-recovery-plan.md:31`, `.project/plans/tests/p3-p5-test-recovery-plan.md:32`.

The latest README snapshot reports frontend Vitest stable at 11 failures plus 1 error, concentrated in ref-picker, profile, row, schema-bootstrap, display constants, and import-level suites; Playwright regressed sharply in the post P4-P5 rerun. Evidence: `.project/plans/tests/README.md:43`, `.project/plans/tests/README.md:47`, `.project/plans/tests/README.md:61`, `.project/plans/tests/README.md:62`.

The plan explicitly says remaining work is concentrated in schema-driven UI contract drift, browser-visible navigation/shell contract drift, and test infrastructure noise/order sensitivity. Evidence: `.project/plans/tests/p3-p5-test-recovery-plan.md:34`, `.project/plans/tests/p3-p5-test-recovery-plan.md:36`, `.project/plans/tests/p3-p5-test-recovery-plan.md:37`, `.project/plans/tests/p3-p5-test-recovery-plan.md:38`.

The correct trajectory is contract-first recovery: P3 settles Formidable/method/item surfaces, P4 settles router/topbar/browser-visible behavior, and P5 makes the harness more deterministic without rewriting broad UI assertions. Evidence: `.project/plans/tests/p3-p5-test-recovery-plan.md:7`, `.project/plans/tests/p3-p5-test-recovery-plan.md:8`, `.project/plans/tests/p3-p5-test-recovery-plan.md:10`, `.project/plans/tests/p3-p5-test-recovery-plan.md:12`, `.project/plans/tests/p5-suite-hardening-plan.md:3`, `.project/plans/tests/p5-suite-hardening-plan.md:5`, `.project/plans/tests/p5-suite-hardening-plan.md:22`.

## Comparison With Alternatives

### Current Hybrid Harness

The current hybrid model gives fast jsdom coverage for runtime/component contracts and browser coverage for seeded app behavior. Evidence: `scripts/run-frontend-tests.py:4`, `scripts/run-frontend-tests.py:6`, `scripts/run-frontend-tests.py:7`, `FRONTEND.md:174`, `FRONTEND.md:176`, `FRONTEND.md:178`, `FRONTEND.md:179`.

The current model also carries duplication risk because Vitest mocks schemas and runtime collaborators while Playwright exercises real backend-generated schema. Evidence: `tests/frontend/tests/components/ntx-ref-picker.test.js:108`, `tests/frontend/tests/components/ntx-ref-picker.test.js:115`, `docs/CORE.md:109`, `docs/CORE.md:111`, `tests/frontend/tests/e2e/global-setup.js:40`, `tests/frontend/tests/e2e/playwright.config.js:50`.

### Alternative: Browser-Only Component Tests

Browser-only component tests would reduce jsdom mock drift but would lose the current fast `tests/**/*.test.js` loop and would require more webServer/static setup for every component test. Evidence for current fast inclusion and centralized mocks: `tests/frontend/vitest.config.js:10`, `tests/frontend/vitest.config.js:13`, `tests/frontend/tests/setup.js:37`, `tests/frontend/tests/setup.js:47`, `tests/frontend/tests/setup.js:75`.

### Alternative: Contract Fixture Generator From Backend Schema

A schema fixture generator would better align Vitest mocks with backend contracts because docs state schema is the universal frontend/backend contract and P3 already identifies stale test schema fixtures as likely cleanup. Evidence: `docs/CORE.md:109`, `docs/CORE.md:111`, `.project/plans/tests/p3-p5-test-recovery-plan.md:190`, `.project/plans/tests/p3-p5-test-recovery-plan.md:194`, `.project/plans/tests/p3-p5-test-recovery-plan.md:198`.

Migration path: add a read-only fixture generation step that captures representative schemas from seeded apps into test fixtures, then update mocks to import those fixtures instead of hand-building divergent shapes. Evidence for seeded apps and schema endpoints: `tests/frontend/tests/e2e/global-setup.js:40`, `tests/frontend/tests/e2e/playwright.config.js:58`, `docs/CORE.md:136`, `docs/CORE.md:145`.

### Alternative: Shared Playwright App Harness Factory

A shared app harness factory would reduce duplication across core, grants, veille, and perf configs because they all define testDir/match/setup/teardown/webServer/baseURL/worker conventions with small app-specific differences. Evidence: `tests/frontend/tests/e2e/playwright.config.js:21`, `tests/frontend/tests/e2e/playwright.grants.config.js:9`, `tests/frontend/tests/e2e/veille.playwright.config.js:21`, `tests/frontend/tests/e2e/playwright.perf.config.js:11`.

Migration path: extract a helper that returns `{PYTHONPATH, PYTHON_BIN, runId, markerPath, tmpDbPath}` and a `defineN3TXE2EConfig()` wrapper, then update app configs incrementally. Evidence for repeated env/marker patterns: `tests/frontend/tests/e2e/playwright.config.js:7`, `tests/frontend/tests/e2e/playwright.config.js:13`, `tests/frontend/tests/e2e/playwright.config.js:16`, `tests/frontend/tests/e2e/veille.playwright.config.js:7`, `tests/frontend/tests/e2e/veille.playwright.config.js:13`, `tests/frontend/tests/e2e/veille.playwright.config.js:16`.

## Feature Integration Guide: New Frontend Component + Tests

1. Decide the component base class from lifecycle needs. Use `NTTElement` or `NTTItem` when the component renders one schema-backed entity, `ListElement`/`NTTList` when it renders collections, `NTTMethod`/`NTTStream` for actions, and standalone `HTMLElement` only when no Actor/NTT lifecycle is needed. Evidence: `packages/n3tx-ui/docs/components.md:11`, `packages/n3tx-ui/docs/components.md:19`, `packages/n3tx-ui/docs/components.md:31`, `packages/n3tx-ui/docs/components.md:33`, `packages/n3tx-ui/docs/components.md:45`, `packages/n3tx-ui/docs/components.md:65`.

2. Preserve the schema contract by deriving fields, methods, child tags, access visibility, and renderer hints from schema rather than duplicating backend knowledge in the component. Evidence: `docs/CORE.md:149`, `docs/CORE.md:153`, `docs/CORE.md:162`, `docs/CORE.md:163`, `docs/CORE.md:164`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:806`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:810`.

3. Add CSS through `get styles()` for `Component` subclasses, returning one URL or an array of URLs; for standalone components, link the CSS in shadow DOM and keep token usage canonical. Evidence: `docs/frontend/COMPONENTS.md:95`, `docs/frontend/COMPONENTS.md:97`, `docs/frontend/COMPONENTS.md:99`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:94`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:299`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:30`, `packages/n3tx-ui/docs/styling.md:62`.

4. Register the custom element once at module load and export the class for Vitest imports. Existing components register `ntx-ref-picker`, `ntx-row`, `ntx-item`, and `ntx-profile` at module tail, while `ntx-profile` also exports the class. Evidence: `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:300`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js:288`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js:839`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:61`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:63`.

5. Add focused Vitest tests under `tests/frontend/tests/components/<component>.test.js`; use current schema fixtures, mock only the narrow collaborators needed, and avoid assertions that freeze private implementation details unless the docs declare them as contract. Evidence: `tests/frontend/vitest.config.js:13`, `tests/frontend/tests/components/ntx-row.test.js:37`, `tests/frontend/tests/components/ntx-row.test.js:52`, `tests/frontend/tests/components/ntx-ref-picker.test.js:108`, `tests/frontend/tests/components/ntx-ref-picker.test.js:115`, `.project/plans/tests/contract-triage-p-1.md:50`, `.project/plans/tests/contract-triage-p-1.md:56`.

6. If the component is browser-visible in the default app, add a Playwright spec to the core suite unless it belongs to grants, veille, or perf naming/config boundaries. Evidence: `scripts/run-frontend-tests.py:67`, `scripts/run-frontend-tests.py:68`, `scripts/run-frontend-tests.py:69`, `scripts/run-frontend-tests.py:72`, `tests/frontend/tests/e2e/playwright.grants.config.js:11`, `tests/frontend/tests/e2e/veille.playwright.config.js:23`, `tests/frontend/tests/e2e/playwright.perf.config.js:13`.

7. Verify narrowly first with Vitest component tests, then with relevant Playwright spec/config, then with `scripts/run-frontend-tests.py --suite ...` if the change touches multiple harness boundaries. Evidence: `scripts/run-frontend-tests.py:432`, `scripts/run-frontend-tests.py:435`, `scripts/run-frontend-tests.py:453`, `scripts/run-frontend-tests.py:481`, `scripts/run-frontend-tests.py:506`, `packages/n3tx-ui/docs/styling.md:98`, `packages/n3tx-ui/docs/styling.md:103`, `packages/n3tx-ui/docs/styling.md:104`.

8. Update package or cross-cutting docs when behavior changes, especially component lifecycle docs, schema contract docs, and styling docs. Evidence: `packages/n3tx-ui/docs/components.md:5`, `packages/n3tx-ui/docs/components.md:118`, `docs/CORE.md:109`, `packages/n3tx-ui/docs/styling.md:98`, `FRONTEND.md:174`.

## Cross-Cutting Concerns

### Logging and Error Visibility

Runtime components use `Logging` for dev/error/warn paths, while tests generally mock Logging in unit suites. Evidence: `packages/n3tx-core/src/n3tx_core/static/core/Component.js:12`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:244`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:290`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:8`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:446`, `tests/frontend/tests/components/ntx-ref-picker.test.js:101`, `tests/frontend/tests/components/ntx-row.test.js:17`, `tests/frontend/tests/components/ntx-profile.test.js:9`.

The runner surfaces suite-level failures and previous status, but it does not classify root cause; classification lives in `.project/plans/tests/contract-triage-p-1.md`. Evidence: `scripts/run-frontend-tests.py:326`, `scripts/run-frontend-tests.py:357`, `scripts/run-frontend-tests.py:358`, `scripts/run-frontend-tests.py:517`, `scripts/run-frontend-tests.py:519`, `.project/plans/tests/contract-triage-p-1.md:37`, `.project/plans/tests/contract-triage-p-1.md:43`.

### Configuration

Vitest config hardcodes source aliases from `/workspace/tests/frontend` to package static roots, while Playwright configs hardcode app dirs, ports, `PYTHONPATH`, and Python binary selection. Evidence: `tests/frontend/vitest.config.js:4`, `tests/frontend/vitest.config.js:5`, `tests/frontend/vitest.config.js:6`, `tests/frontend/tests/e2e/playwright.config.js:7`, `tests/frontend/tests/e2e/playwright.config.js:13`, `tests/frontend/tests/e2e/playwright.config.js:52`, `tests/frontend/tests/e2e/veille.playwright.config.js:52`, `tests/frontend/tests/e2e/veille.playwright.config.js:56`.

Recommended pattern: introduce shared test config helpers only after P3/P4 behavior contracts settle, because P5 is scoped to hardening and explicitly should not rewrite broad UI assertions. Evidence: `.project/plans/tests/p5-suite-hardening-plan.md:5`, `.project/plans/tests/p5-suite-hardening-plan.md:22`, `.project/plans/tests/p5-suite-hardening-plan.md:153`, `.project/plans/tests/p5-suite-hardening-plan.md:168`.

### Authentication

The frontend/browser auth contract centers on JWT storage in localStorage, with E2E helpers calling `/users/login` and accepting both top-level and enveloped token shapes. Evidence: `tests/frontend/tests/e2e/fixtures/auth.js:23`, `tests/frontend/tests/e2e/fixtures/auth.js:28`, `tests/frontend/tests/e2e/fixtures/auth.js:41`, `tests/frontend/tests/e2e/fixtures/auth.js:43`.

The historical grants token mismatch was already classified as likely stale test or environment drift unless product explicitly decides auth endpoints must never be debug-wrapped. Evidence: `.project/plans/tests/contract-triage-p-1.md:118`, `.project/plans/tests/contract-triage-p-1.md:120`, `.project/plans/tests/contract-triage-p-1.md:130`, `.project/plans/tests/contract-triage-p-1.md:144`, `.project/plans/tests/contract-triage-p-1.md:148`.

### Static Serving

Tests must respect the merged static namespace because app pages can import package components by relative paths even though files live in separate packages. Evidence: `FRONTEND.md:24`, `FRONTEND.md:206`, `FRONTEND.md:208`, `FRONTEND.md:216`, `tests/frontend/vitest.config.js:20`, `tests/frontend/vitest.config.js:31`.

### Method Response Contract

The runtime currently handles method responses locally when action metadata or same-entity data is present, and falls back to `pull()` for ambiguous or different-entity responses. Evidence: `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:1034`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:1040`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:1058`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:1062`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:1070`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:1071`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:1078`.

The recovery notes still call out disagreement between `_response_()` pull and no-pull tests, so new method/component tests should state whether they expect local update, authoritative pull, or both. Evidence: `.project/plans/tests/README.md:196`, `.project/plans/tests/README.md:198`, `.project/plans/tests/README.md:202`, `.project/plans/tests/README.md:203`, `.project/plans/tests/README.md:205`.

## Concrete Recommended Patterns

1. Treat backend-generated schema as the source for reusable test fixtures, and use hand-written schema mocks only for intentionally minimal unit tests. Evidence: `docs/CORE.md:109`, `docs/CORE.md:111`, `.project/plans/tests/p3-p5-test-recovery-plan.md:190`, `.project/plans/tests/p3-p5-test-recovery-plan.md:198`.

2. Keep core/veille run-specific marker behavior as the template for new Playwright suites. Evidence: `tests/frontend/tests/e2e/playwright.config.js:16`, `tests/frontend/tests/e2e/playwright.config.js:17`, `tests/frontend/tests/e2e/global-setup.js:35`, `tests/frontend/tests/e2e/global-setup.js:36`, `tests/frontend/tests/e2e/veille.playwright.config.js:16`, `tests/frontend/tests/e2e/veille.playwright.config.js:17`.

3. Avoid adding new fixed `/tmp` marker names or `reuseExistingServer: !process.env.CI` defaults for isolation-sensitive app suites. Evidence: `tests/frontend/tests/e2e/grants-global-setup.js:21`, `tests/frontend/tests/e2e/perf-global-setup.js:25`, `tests/frontend/tests/e2e/playwright.grants.config.js:36`, `.project/plans/tests/p5-suite-hardening-plan.md:205`, `.project/plans/tests/p5-suite-hardening-plan.md:206`.

4. Test component public behavior through DOM, events, schema contracts, and TX boundaries; avoid requiring static style strings unless the docs designate a static source contract. Evidence: `packages/n3tx-ui/docs/components.md:51`, `.project/plans/tests/full-test-failure-audit-2026-04-24.md:256`, `.project/plans/tests/full-test-failure-audit-2026-04-24.md:258`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:86`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.css:11`.

5. For new `Component` subclasses, prefer `get styles()` and `scheduleRender()` lifecycle instead of manually linking styles, unless the component is intentionally standalone like `ntx-profile` or `ntx-ref-picker`. Evidence: `packages/n3tx-core/src/n3tx_core/static/core/Component.js:94`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:262`, `packages/n3tx-core/src/n3tx_core/static/core/Component.js:362`, `packages/n3tx-ui/docs/components.md:65`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js:30`, `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js:86`.

6. When adding app-specific suite support to `run-frontend-tests.py`, register it as a named `Suite`, document its exclusion from core if needed, and ensure `core_e2e_specs()` cannot double-run its specs. Evidence: `scripts/run-frontend-tests.py:67`, `scripts/run-frontend-tests.py:69`, `scripts/run-frontend-tests.py:72`, `scripts/run-frontend-tests.py:85`, `scripts/run-frontend-tests.py:109`, `scripts/run-frontend-tests.py:122`, `scripts/run-frontend-tests.py:135`.

7. Use the P-1 contract note for every red cluster before editing product code or tests. Evidence: `.project/plans/tests/contract-triage-p-1.md:59`, `.project/plans/tests/contract-triage-p-1.md:61`, `.project/plans/tests/contract-triage-p-1.md:64`, `.project/plans/tests/contract-triage-p-1.md:65`, `.project/plans/tests/contract-triage-p-1.md:68`, `.project/plans/tests/contract-triage-p-1.md:72`.

8. For method response tests, explicitly choose one of the current runtime cases: action response with `_field`, same-entity data response, different-entity response requiring `pull()`, or ambiguous primitive response requiring `pull()`. Evidence: `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:1027`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:1028`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:1030`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:1032`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:1035`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:1067`, `packages/n3tx-core/src/n3tx_core/static/core/NTT.js:1078`.

## Priority Recommendations

| Priority | Recommendation | Impact | Effort | Evidence |
|---:|---|---|---|---|
| 1 | Create a shared Playwright app harness helper for run IDs, marker paths, Python binary, `PYTHONPATH`, temp DB, setup, and teardown | Reduces app-specific drift and stale fixed-marker failures | Medium | `tests/frontend/tests/e2e/playwright.config.js:16`, `tests/frontend/tests/e2e/veille.playwright.config.js:17`, `tests/frontend/tests/e2e/grants-global-setup.js:21`, `.project/plans/tests/p5-suite-hardening-plan.md:170` |
| 2 | Generate or snapshot representative backend schemas for Vitest fixtures | Reduces stale schema mocks in P3 component/form tests | Medium | `docs/CORE.md:109`, `docs/CORE.md:145`, `.project/plans/tests/p3-p5-test-recovery-plan.md:190`, `.project/plans/tests/p3-p5-test-recovery-plan.md:198` |
| 3 | Add suite-specific machine-readable reporters or parsers to the Python runner | Makes overview counts less brittle than regex over terminal output | Small/Medium | `scripts/run-frontend-tests.py:31`, `scripts/run-frontend-tests.py:201`, `scripts/run-frontend-tests.py:211`, `scripts/run-frontend-tests.py:214` |
| 4 | Normalize app-specific configs to core/veille isolation defaults | Prevents stale local servers and marker collisions | Small | `tests/frontend/tests/e2e/playwright.config.js:59`, `tests/frontend/tests/e2e/veille.playwright.config.js:62`, `tests/frontend/tests/e2e/playwright.grants.config.js:36`, `.project/plans/tests/p5-suite-hardening-plan.md:173` |
| 5 | Make component tests assert documented public contracts rather than private implementation shape | Reduces churn when standalone components change internals | Small | `packages/n3tx-ui/docs/components.md:118`, `.project/plans/tests/full-test-failure-audit-2026-04-24.md:256`, `.project/plans/tests/contract-triage-p-1.md:42` |

## Bottom Line

The frontend test subsystem is extensible, but the safe extension path is narrow: preserve schema as the source of truth, keep jsdom mocks synchronized with backend-generated contracts, use core/veille E2E isolation patterns for new apps, and classify red tests before changing product behavior. Evidence: `docs/CORE.md:109`, `docs/CORE.md:111`, `tests/frontend/tests/setup.js:131`, `tests/frontend/tests/e2e/playwright.config.js:16`, `tests/frontend/tests/e2e/veille.playwright.config.js:17`, `.project/plans/tests/contract-triage-p-1.md:14`, `.project/plans/tests/contract-triage-p-1.md:16`.

The highest-leverage evolution is not more component-specific assertions; it is shared harness primitives plus schema-derived fixtures, so test failures point to real contract drift instead of stale mocks, marker collisions, or local server reuse. Evidence: `.project/plans/tests/p5-suite-hardening-plan.md:153`, `.project/plans/tests/p5-suite-hardening-plan.md:168`, `.project/plans/tests/p3-p5-test-recovery-plan.md:190`, `.project/plans/tests/README.md:207`, `.project/plans/tests/README.md:226`.
