# Frontend Test Harness And Contracts — Architecture Audit

## 1. Executive Summary

1. This subsystem is not a single runtime module; it is the boundary between the frontend product contracts and the test harness contracts that verify them.
2. The product contract is explicitly schema-driven: backend schemas carry fields, methods, UI hints, access rules, and `$defs` as the universal frontend contract (`docs/CORE.md:109`, `docs/CORE.md:133`, `FRONTEND.md:218`).
3. The product frontend is split by responsibility: `n3tx-core` owns non-visual runtime, `n3tx-ui` owns visual Web Components, and package static dirs merge at runtime (`FRONTEND.md:20`, `FRONTEND.md:24`, `FRONTEND.md:194`).
4. The test harness has two runner families: Vitest for `tests/**/*.test.js` and Playwright for browser specs under `tests/e2e/*.spec.js` (`scripts/run-frontend-tests.py:4`, `scripts/run-frontend-tests.py:6`, `scripts/run-frontend-tests.py:7`).
5. The failing run shows a systemic problem: several tests assert older or example-local contracts while the product code and docs describe newer package boundaries and DOM/CSS behavior.
6. The highest-risk finding is alias/path drift: Vitest aliases all `../../components/*` imports to `n3tx-ui`, but `ntx-favorites.js` and `ntx-logs.js` exist only under example app static dirs, not under `n3tx-ui`.
7. The second highest-risk finding is Playwright harness drift: core and veille use marker files that their web server commands read with `cat`, so marker creation timing and env propagation are part of the suite startup contract (`tests/frontend/tests/e2e/playwright.config.js:17`, `tests/frontend/tests/e2e/playwright.config.js:51`).
8. The third highest-risk finding is app path drift: grants and perf configs still point at old paths, while current docs say examples live under `examples/` and the frontend harness boots `examples/core` (`FRONTEND.md:182`, `tests/frontend/tests/e2e/playwright.grants.config.js:34`, `tests/frontend/tests/e2e/playwright.perf.config.js:8`).
9. The product runtime itself is not uniformly suspect: `Component.SIZES` including `row`, external component CSS links, and profile `.profile-note` markup are all supported by current code or docs (`Component.js:26`, `ntx-ref-picker.js:86`, `ntx-profile.js:54`).
10. The audit recommendation is to fix the harness contracts before product code: align imports/aliases with component ownership, make Playwright paths/markers consistent, and update stale DOM expectations only after classifying them against current docs.

## 2. Scope And Evidence Base

11. Core runner scope: `scripts/run-frontend-tests.py` defines all frontend suites and is the top-level orchestration entry point (`scripts/run-frontend-tests.py:85`, `scripts/run-frontend-tests.py:151`).
12. Unit harness scope: Vitest uses jsdom, setup file `./tests/setup.js`, and includes all `tests/**/*.test.js` (`tests/frontend/vitest.config.js:8`, `tests/frontend/vitest.config.js:10`, `tests/frontend/vitest.config.js:12`, `tests/frontend/vitest.config.js:13`).
13. Unit alias scope: Vitest rewrites `../../core`, `../../utils`, `../../config.js`, `../../components`, `../../widgets`, `../../generators`, and `../../vendor` to package static dirs (`tests/frontend/vitest.config.js:19`, `tests/frontend/vitest.config.js:31`).
14. Unit environment scope: setup mocks localStorage, fetch, ResizeObserver, WebSocket, and browser globals (`tests/frontend/tests/setup.js:8`, `tests/frontend/tests/setup.js:37`, `tests/frontend/tests/setup.js:47`, `tests/frontend/tests/setup.js:75`, `tests/frontend/tests/setup.js:111`).
15. Core E2E scope: `playwright.config.js` runs against `examples/core`, passes package `PYTHONPATH`, and probes `/Product` (`tests/frontend/tests/e2e/playwright.config.js:7`, `tests/frontend/tests/e2e/playwright.config.js:50`, `tests/frontend/tests/e2e/playwright.config.js:52`, `tests/frontend/tests/e2e/playwright.config.js:58`).
16. Grants E2E scope: `playwright.grants.config.js` matches `grants-*.spec.js` but starts `/workspace/example_grants` (`tests/frontend/tests/e2e/playwright.grants.config.js:11`, `tests/frontend/tests/e2e/playwright.grants.config.js:34`).
17. Veille E2E scope: veille config matches `veille-*.spec.js`, runs `/workspace/apps/veille`, passes `N3TX_PORT=5010`, and probes `/login.html` (`tests/frontend/tests/e2e/veille.playwright.config.js:23`, `tests/frontend/tests/e2e/veille.playwright.config.js:52`, `tests/frontend/tests/e2e/veille.playwright.config.js:56`, `tests/frontend/tests/e2e/veille.playwright.config.js:61`).
18. Perf E2E scope: perf config still resolves `src/n3tx/example` and seed script under `src/n3tx/core/tests/profiling` (`tests/frontend/tests/e2e/playwright.perf.config.js:8`, `tests/frontend/tests/e2e/perf-global-setup.js:14`).
19. Product runtime scope: `Component.js` is the abstract Web Component/Actor bridge (`FRONTEND.md:47`, `docs/frontend/COMPONENTS.md:26`, `Component.js:23`).
20. Product entity scope: `NTT.js` is the schema bootstrap and DynamicClass registry (`FRONTEND.md:43`, `NTT.js:109`, `NTT.js:121`).
21. Product visual scope: `ntx-item`, `ntx-row`, `ntx-ref-picker`, and `ntx-profile` live in `n3tx-ui` and are visual components (`FRONTEND.md:57`, `FRONTEND.md:60`, `FRONTEND.md:63`, `FRONTEND.md:68`, `FRONTEND.md:73`).
22. Example-local scope: `ntx-favorites.js` and `ntx-logs.js` are present under `examples/core/static/components`, not under the package static component dir (`examples/core/static/components/ntx-favorites.js:1`, `examples/core/static/components/ntx-logs.js:1`).

## 3. Product Contract Versus Harness Contract

23. Product code contract: schema drives the runtime, and `NTT.SCHEMA()` creates DynamicClasses from schema data (`FRONTEND.md:279`, `FRONTEND.md:280`, `NTT.js:302`).
24. Product code contract: component rendering uses schema properties, methods, access, `$defs`, and `ui.renderer` rather than hand-coded frontend duplication (`docs/CORE.md:149`, `FRONTEND.md:224`, `docs/frontend/COMPONENTS.md:842`).
25. Product code contract: the package split is runtime-vs-visual, not old monolithic static paths (`FRONTEND.md:20`, `FRONTEND.md:194`).
26. Product code contract: `n3tx-ui` standalone components include `NTTRefPicker` and `NTTProfile`, and docs list standalone components separately from `Component` subclasses (`packages/n3tx-ui/docs/components.md:65`).
27. Product code contract: `NTTItem` supports `row()` as a table row rendering method (`packages/n3tx-ui/docs/components.md:19`, `packages/n3tx-ui/docs/components.md:20`, `ntx-item.js:414`).
28. Harness contract: tests can import package components through relative paths because Vitest aliases `../../components/` to `n3tx-ui/static/components` (`tests/frontend/vitest.config.js:31`).
29. Harness contract: tests can import example-local components only if aliases explicitly point to the app static dir or tests import the app-local path; current aliases do not do that (`tests/frontend/vitest.config.js:31`, `examples/core/static/components/ntx-favorites.js:15`).
30. Harness contract: Playwright configs are responsible for app startup, DB seeding, marker file passing, package `PYTHONPATH`, and cleanup (`tests/frontend/tests/e2e/global-setup.js:23`, `tests/frontend/tests/e2e/playwright.config.js:50`, `tests/frontend/tests/e2e/global-teardown.js:8`).
31. Harness contract: the top-level runner aggregates suites and continues after failures by default (`scripts/run-frontend-tests.py:440`, `scripts/run-frontend-tests.py:498`, `scripts/run-frontend-tests.py:521`).
32. Structural problem: failures mix these contracts without classification, so a stale test can look like a product regression.
33. Existing project planning explicitly requires P-1 contract triage before changing product code (`.project/plans/tests/contract-triage-p-1.md:14`, `.project/plans/tests/contract-triage-p-1.md:16`).
34. Existing project planning classifies many remaining UI failures as schema-driven UI contract drift rather than automatic product bugs (`.project/plans/tests/p3-p5-test-recovery-plan.md:34`, `.project/plans/tests/p3-p5-test-recovery-plan.md:36`).

## 4. Architecture Diagram

35. Primary product flow:

```text
Python model
  -> JSON Schema endpoint
  -> NTT.SCHEMA(data)
  -> DynamicClass registry
  -> Component.define(proto)
  -> n3tx-ui Web Component render
```

36. The model-to-schema contract is documented as model definition generating API, JSON Schema, storage, access, and frontend rendering instructions (`docs/CORE.md:44`, `docs/CORE.md:46`).
37. The schema anatomy includes properties, UI hints, access, methods, and `$defs` (`docs/CORE.md:133`, `docs/CORE.md:141`, `docs/CORE.md:145`).
38. The frontend lifecycle explicitly names `NTT.SCHEMA(data) -> prototype(addr, schema, href) -> DynamicClass` (`FRONTEND.md:279`, `FRONTEND.md:280`).
39. `Component.define()` receives DynamicClass prototypes and calls `definedCallback()` (`Component.js:183`, `Component.js:188`).
40. Components such as `NTTItem` render through schema-driven Formidable and method buttons (`ntx-item.js:398`, `ntx-item.js:407`).

41. Primary test flow:

```text
scripts/run-frontend-tests.py
  +-- unit: npx vitest run --color
  |     -> vitest aliases package static dirs
  |     -> setup.js installs jsdom mocks
  |     -> tests import ../../core, ../../components, ../../utils
  |
  +-- e2e-core: Playwright config + examples/core server
  +-- e2e-grants: grants config + grants app server
  +-- e2e-veille: veille config + apps/veille server
  +-- e2e-perf: perf config + profiling server
```

42. The runner defines unit suite command `npx vitest run --color` (`scripts/run-frontend-tests.py:87`, `scripts/run-frontend-tests.py:90`).
43. The runner defines core Playwright suite with `playwright.config.js` and `core_e2e_specs()` (`scripts/run-frontend-tests.py:95`, `scripts/run-frontend-tests.py:102`, `scripts/run-frontend-tests.py:103`).
44. The runner defines grants, veille, and perf suites with specialized configs (`scripts/run-frontend-tests.py:109`, `scripts/run-frontend-tests.py:123`, `scripts/run-frontend-tests.py:135`).
45. `core_e2e_specs()` excludes performance and prefixes `grants-` and `veille-` from core runs (`scripts/run-frontend-tests.py:67`, `scripts/run-frontend-tests.py:72`).
46. The harness goal is one coverage pass per spec family, not duplicated browser runs (`scripts/run-frontend-tests.py:9`, `scripts/run-frontend-tests.py:10`, `scripts/run-frontend-tests.py:11`).

## 5. Component Inventory

47. `scripts/run-frontend-tests.py`: orchestration runner; owns suite list, command execution, output parsing, overview JSON, and final exit status (`scripts/run-frontend-tests.py:44`, `scripts/run-frontend-tests.py:154`, `scripts/run-frontend-tests.py:201`, `scripts/run-frontend-tests.py:421`, `scripts/run-frontend-tests.py:481`).
48. `Suite`: immutable runner configuration for one suite (`scripts/run-frontend-tests.py:44`).
49. `SuiteResult`: immutable normalized result for one suite (`scripts/run-frontend-tests.py:54`).
50. `core_e2e_specs()`: discovers core browser specs and excludes specialized suites (`scripts/run-frontend-tests.py:67`, `scripts/run-frontend-tests.py:68`, `scripts/run-frontend-tests.py:69`).
51. `build_suites()`: central source of runner suite definitions (`scripts/run-frontend-tests.py:85`).
52. `run_suite()`: subprocess runner that streams output and returns captured text (`scripts/run-frontend-tests.py:154`, `scripts/run-frontend-tests.py:164`, `scripts/run-frontend-tests.py:173`).
53. `parse_frontend_counts()`: output parser that prefers Vitest `Tests` summary and aggregates Playwright summary lines (`scripts/run-frontend-tests.py:201`, `scripts/run-frontend-tests.py:204`, `scripts/run-frontend-tests.py:211`).
54. `save_overview()`: writes suite JSON to `.project/test-runs/frontend-test-overview.json` by default (`scripts/run-frontend-tests.py:30`, `scripts/run-frontend-tests.py:421`).
55. `vitest.config.js`: jsdom + alias contract for unit tests (`tests/frontend/vitest.config.js:8`, `tests/frontend/vitest.config.js:17`).
56. `setup.js`: global jsdom compatibility layer, but also a shared-state cleanup boundary (`tests/frontend/tests/setup.js:131`, `tests/frontend/tests/setup.js:156`).
57. `playwright.config.js`: core browser harness against `examples/core` (`tests/frontend/tests/e2e/playwright.config.js:50`, `tests/frontend/tests/e2e/playwright.config.js:52`).
58. `global-setup.js`: core E2E temp DB creator and seeder (`tests/frontend/tests/e2e/global-setup.js:23`, `tests/frontend/tests/e2e/global-setup.js:42`).
59. `global-teardown.js`: core/perf marker-reader and temp DB remover (`tests/frontend/tests/e2e/global-teardown.js:8`, `tests/frontend/tests/e2e/global-teardown.js:13`, `tests/frontend/tests/e2e/global-teardown.js:18`).
60. `playwright.grants.config.js`: grants browser harness, currently with stale app path (`tests/frontend/tests/e2e/playwright.grants.config.js:9`, `tests/frontend/tests/e2e/playwright.grants.config.js:34`).
61. `grants-global-setup.js`: grants temp DB creator, currently with same stale app path (`tests/frontend/tests/e2e/grants-global-setup.js:12`, `tests/frontend/tests/e2e/grants-global-setup.js:27`).
62. `veille.playwright.config.js`: veille browser harness with separate port and marker namespace (`tests/frontend/tests/e2e/veille.playwright.config.js:17`, `tests/frontend/tests/e2e/veille.playwright.config.js:36`).
63. `veille.global-setup.js`: veille temp DB creator and seed runner (`tests/frontend/tests/e2e/veille.global-setup.js:17`, `tests/frontend/tests/e2e/veille.global-setup.js:30`).
64. `playwright.perf.config.js`: perf browser harness, currently resolving old source-tree paths (`tests/frontend/tests/e2e/playwright.perf.config.js:7`, `tests/frontend/tests/e2e/playwright.perf.config.js:8`).
65. `perf-global-setup.js`: perf temp DB creator, currently resolving old seed script path (`tests/frontend/tests/e2e/perf-global-setup.js:13`, `tests/frontend/tests/e2e/perf-global-setup.js:14`).
66. `Component`: core abstract Web Component base; owns Actor registration, shadow DOM, schema/ref state, stylesheets, display modes, subscriptions, lifecycle hooks (`Component.js:23`, `Component.js:70`, `Component.js:183`, `Component.js:362`, `Component.js:436`).
67. `NTT`: core entity registry; owns schema preloading, DynamicClass creation, waiting queues, instance registry, and method response handling (`NTT.js:121`, `NTT.js:158`, `NTT.js:229`, `NTT.js:302`, `NTT.js:619`, `NTT.js:1034`).
68. `NTTRefPicker`: standalone `HTMLElement` for reference list editing; owns dropdown, search, inline create, optimistic ref events, and parent refresh (`ntx-ref-picker.js:30`, `ntx-ref-picker.js:104`, `ntx-ref-picker.js:175`, `ntx-ref-picker.js:221`, `ntx-ref-picker.js:243`).
69. `ntx-ref-picker.css`: external CSS tokenized through canonical `--ntx-*` variables (`ntx-ref-picker.css:16`, `ntx-ref-picker.css:18`, `ntx-ref-picker.css:37`, `ntx-ref-picker.css:60`).
70. `NTTRow`: `NTTItem` subclass for table rows; owns forced row display, inline edit cells, validation before save, error banner, and SELECT row click (`ntx-row.js:21`, `ntx-row.js:30`, `ntx-row.js:129`, `ntx-row.js:192`, `ntx-row.js:273`).
71. `NTTItem`: default entity component; owns display/edit mode, delete, method rendering, Formidable integration, row rendering, surgical updates, and event binding (`ntx-item.js:26`, `ntx-item.js:132`, `ntx-item.js:375`, `ntx-item.js:419`, `ntx-item.js:592`).
72. `NTTProfile`: standalone profile page component; owns auth init and user identity rendering (`ntx-profile.js:11`, `ntx-profile.js:17`, `ntx-profile.js:21`, `ntx-profile.js:26`).
73. Example `NTTFavorites`: example-local wrapper around `<ntx-list model="ProductLike" display="md">` (`examples/core/static/components/ntx-favorites.js:7`, `examples/core/static/components/ntx-favorites.js:9`, `examples/core/static/components/ntx-favorites.js:10`).
74. Example `NTTLogs`: example-local log viewer backed by `Logging` listener APIs (`examples/core/static/components/ntx-logs.js:1`, `examples/core/static/components/ntx-logs.js:16`, `examples/core/static/components/ntx-logs.js:126`).

## 6. Responsibility Map

75. Product runtime responsibility: resolve schemas, create DynamicClasses, maintain entity instances, and route entity messages (`NTT.js:302`, `NTT.js:619`, `NTT.js:870`).
76. Product visual responsibility: render schema-driven UI without duplicating backend model knowledge (`FRONTEND.md:220`, `docs/CORE.md:149`, `ntx-item.js:407`).
77. Product styling responsibility: use external CSS entrypoints and canonical tokens, not inline style snapshots (`packages/n3tx-ui/docs/styling.md:25`, `packages/n3tx-ui/docs/styling.md:60`, `ntx-ref-picker.js:86`).
78. Product component ownership responsibility: framework components live in package static dirs, while example-only components may live under example static dirs (`FRONTEND.md:57`, `FRONTEND.md:206`, `FRONTEND.md:216`).
79. Unit harness responsibility: provide browser-like APIs and module resolution so package code can run in jsdom (`tests/frontend/tests/setup.js:1`, `tests/frontend/vitest.config.js:17`).
80. Browser harness responsibility: start the right app with the right DB and package sources (`FRONTEND.md:182`, `tests/frontend/tests/e2e/playwright.config.js:50`).
81. Top-level runner responsibility: run all suites, preserve outputs, compare previous status, and return failure if any selected suite failed (`scripts/run-frontend-tests.py:234`, `scripts/run-frontend-tests.py:392`, `scripts/run-frontend-tests.py:517`).
82. What breaks if `scripts/run-frontend-tests.py` is removed: there is no single command that runs unit, core E2E, grants E2E, veille E2E, and perf E2E while writing overview JSON (`scripts/run-frontend-tests.py:85`, `scripts/run-frontend-tests.py:514`).
83. What breaks if Vitest aliases are wrong: tests cannot load package modules through their relative import style (`tests/frontend/vitest.config.js:20`, `tests/frontend/vitest.config.js:31`).
84. What breaks if Playwright markers are wrong: web server commands read empty or missing DB paths via `cat`, causing startup failures before specs execute (`tests/frontend/tests/e2e/playwright.config.js:51`, `tests/frontend/tests/e2e/veille.playwright.config.js:51`).
85. What breaks if component tests assert stale DOM internals: code may be regressed away from documented external stylesheet and component boundary contracts (`ntx-ref-picker.js:86`, `packages/n3tx-ui/docs/styling.md:27`).

## 7. Design Patterns

86. Schema-as-contract pattern: backend schema is not only validation but behavior, permissions, UI instructions, methods, and `$defs` (`docs/CORE.md:111`, `docs/CORE.md:144`, `FRONTEND.md:220`).
87. Dynamic class factory pattern: `prototype(addr, schema, href)` returns a schema-specific subclass with generated properties and methods (`NTT.js:619`, `NTT.js:686`, `NTT.js:724`).
88. Observer pattern: DynamicClass `signal()` and `observe()` support component updates and list subscriptions (`NTT.js:780`, `NTT.js:794`, `packages/n3tx-ui/docs/components.md:128`).
89. Actor bridge pattern: `Component` imports Actor, Matrix, and TX, then `Actor.subclass(Component)` applies actor behavior to all Web Components (`Component.js:13`, `Component.js:14`, `Component.js:15`, `Component.js:468`).
90. Shadow DOM + external stylesheet pattern: `Component` supports stylesheet URLs and constructable stylesheet caching (`Component.js:17`, `Component.js:94`, `Component.js:274`).
91. Standalone Web Component pattern: `NTTRefPicker` and `NTTProfile` extend `HTMLElement` directly rather than `Component`, matching docs that list standalone components separately (`packages/n3tx-ui/docs/components.md:65`, `ntx-ref-picker.js:30`, `ntx-profile.js:11`).
92. Test double pattern: `setup.js` mocks localStorage, fetch, ResizeObserver, and WebSocket to simulate browser capabilities (`tests/frontend/tests/setup.js:8`, `tests/frontend/tests/setup.js:37`, `tests/frontend/tests/setup.js:47`, `tests/frontend/tests/setup.js:75`).
93. Marker-file IPC pattern: Playwright setup writes DB paths to temp files that web server commands read (`tests/frontend/tests/e2e/global-setup.js:35`, `tests/frontend/tests/e2e/global-setup.js:37`, `tests/frontend/tests/e2e/playwright.config.js:51`).
94. Suite registry pattern: `build_suites()` centralizes suite configuration for the Python runner (`scripts/run-frontend-tests.py:85`, `scripts/run-frontend-tests.py:151`).
95. Pattern assessment: product patterns are cohesive and documented; harness patterns are functional but currently inconsistent across app-specific configs.

## 8. Data Flow

96. Unit import flow:

```text
test file import ../../components/ntx-row.js
  -> Vitest alias /^(.\/\.\.\/)+components\//
  -> packages/n3tx-ui/src/n3tx_ui/static/components/ntx-row.js
  -> product component imports ../core, ../generators, ../utils
  -> additional aliases resolve to core/ui package static dirs
```

97. The alias for `../../components/` points to the package UI components dir (`tests/frontend/vitest.config.js:31`).
98. `ntx-row.js` imports `./ntx-item.js`, `../generators/form.js`, `../utils/Permissions.js`, and `../core/TX.js`, relying on package-relative static layout (`ntx-row.js:14`, `ntx-row.js:15`, `ntx-row.js:16`, `ntx-row.js:18`).
99. Tests for `ntx-favorites` import `../../components/ntx-favorites.js`, which will resolve to the package UI dir, but the file exists under example static dirs (`tests/frontend/tests/components/ntx-favorites.test.js:28`, `tests/frontend/vitest.config.js:31`, `examples/core/static/components/ntx-favorites.js:1`).
100. Tests for `ntx-logs` import `../../components/ntx-logs.js`, which will resolve to the package UI dir, but the implementation evidence is example-local (`tests/frontend/tests/components/ntx-logs.test.js:35`, `tests/frontend/vitest.config.js:31`, `examples/core/static/components/ntx-logs.js:1`).
101. Browser startup flow:

```text
globalSetup()
  -> mkdtempSync()
  -> write marker file with DB path
  -> seed.py using temp DB
  -> Playwright webServer.command reads marker with cat
  -> app probes schema URL
  -> tests run
  -> globalTeardown reads marker and removes temp dir
```

102. Core setup creates temp dir and writes marker path (`tests/frontend/tests/e2e/global-setup.js:25`, `tests/frontend/tests/e2e/global-setup.js:37`).
103. Core web server reads the marker inside the shell command (`tests/frontend/tests/e2e/playwright.config.js:51`).
104. Core teardown reads marker and removes the DB directory (`tests/frontend/tests/e2e/global-teardown.js:13`, `tests/frontend/tests/e2e/global-teardown.js:18`).
105. Veille repeats the marker pattern with a separate env key and port (`tests/frontend/tests/e2e/veille.playwright.config.js:17`, `tests/frontend/tests/e2e/veille.global-setup.js:21`).
106. Grants does not pass a marker path into `webServer.env` and starts with a stale cwd, so its DB setup and server startup contracts are split (`tests/frontend/tests/e2e/grants-global-setup.js:21`, `tests/frontend/tests/e2e/playwright.grants.config.js:33`, `tests/frontend/tests/e2e/playwright.grants.config.js:34`).

## 9. State Management

107. Runner state: previous overview is loaded from JSON if present and attached to each `SuiteResult` (`scripts/run-frontend-tests.py:234`, `scripts/run-frontend-tests.py:258`, `scripts/run-frontend-tests.py:268`).
108. Runner state: output-derived counts drive suite status (`scripts/run-frontend-tests.py:201`, `scripts/run-frontend-tests.py:226`, `scripts/run-frontend-tests.py:258`).
109. Unit global state: setup keeps localStorage data in module-level `store` (`tests/frontend/tests/setup.js:11`).
110. Unit global state: setup tracks `WebSocketMock.instances` statically and clears them after tests (`tests/frontend/tests/setup.js:81`, `tests/frontend/tests/setup.js:99`, `tests/frontend/tests/setup.js:166`).
111. Unit global state: setup records unhandled rejections and throws the first one in `afterEach` (`tests/frontend/tests/setup.js:126`, `tests/frontend/tests/setup.js:194`).
112. Product component state: `Component` stores private actor identity, href/model/proto/data, resize observer, render pending flag, and stylesheet readiness (`Component.js:46`, `Component.js:50`, `Component.js:59`, `Component.js:64`).
113. Product entity state: `NTT` stores prototypes in a private static map and waiting queues in another private static map (`NTT.js:123`, `NTT.js:124`, `NTT.js:125`).
114. Product DynamicClass state: generated classes hold `instances`, `_schema`, watcher sets, observer maps, pending attaches, and read flags (`NTT.js:628`, `NTT.js:629`, `NTT.js:679`, `NTT.js:683`).
115. `NTTRefPicker` state: private `#mode` controls closed, picker, and create modes (`ntx-ref-picker.js:32`, `ntx-ref-picker.js:33`).
116. `NTTRow` state: private AbortController is replaced each render to prevent listener accumulation (`ntx-row.js:25`, `ntx-row.js:233`, `ntx-row.js:234`).
117. `NTTItem` state: edit mode, edit snapshot, and AbortController manage editing and listeners (`ntx-item.js:28`, `ntx-item.js:33`, `ntx-item.js:36`).
118. Example logs state: private fields track open state, filter, panel/badge/list refs, counts, listener, and rendered status (`examples/core/static/components/ntx-logs.js:17`, `examples/core/static/components/ntx-logs.js:23`, `examples/core/static/components/ntx-logs.js:24`).

## 10. Coupling Analysis

119. Unit tests are tightly coupled to import aliases because most imports use `../../components`, `../../core`, or `../../utils` rather than package absolute aliases (`tests/frontend/tests/components/ntx-ref-picker.test.js:132`, `tests/frontend/tests/core/Component.test.js:31`).
120. `ntx-ref-picker.test.js` is tightly coupled to private-ish methods like `_render`, `_showPicker`, `_showInlineCreate`, `_addRef`, `_submitCreate`, and `_close` (`tests/frontend/tests/components/ntx-ref-picker.test.js:365`, `tests/frontend/tests/components/ntx-ref-picker.test.js:426`, `tests/frontend/tests/components/ntx-ref-picker.test.js:628`, `tests/frontend/tests/components/ntx-ref-picker.test.js:807`, `tests/frontend/tests/components/ntx-ref-picker.test.js:865`, `tests/frontend/tests/components/ntx-ref-picker.test.js:1086`).
121. `ntx-ref-picker.test.js` is stale-coupled to inline CSS because it expects `<style>` and static `NTTRefPicker.styles` (`tests/frontend/tests/components/ntx-ref-picker.test.js:382`, `tests/frontend/tests/components/ntx-ref-picker.test.js:1155`).
122. Product `NTTRefPicker` uses external CSS link and has no static `styles` property (`ntx-ref-picker.js:28`, `ntx-ref-picker.js:86`).
123. `Component.test.js` is stale-coupled to five display sizes (`tests/frontend/tests/core/Component.test.js:73`, `tests/frontend/tests/core/Component.test.js:75`).
124. Product `Component.SIZES` includes `row`, and docs for `NTTItem` list `row` in key attributes (`Component.js:26`, `packages/n3tx-ui/docs/components.md:180`).
125. `display-mode-cascade.test.js` repeats the stale five-size assertion (`tests/frontend/tests/integration/display-mode-cascade.test.js:156`, `tests/frontend/tests/integration/display-mode-cascade.test.js:157`).
126. `ntx-profile.test.js` is DOM-class coupled to `.placeholder` (`tests/frontend/tests/components/ntx-profile.test.js:154`, `tests/frontend/tests/components/ntx-profile.test.js:159`).
127. Product `NTTProfile` renders `.profile-note` for the same copy (`ntx-profile.js:54`).
128. `ntx-row.test.js` is coupled to `el.save = vi.fn()` replacing the inherited save boundary (`tests/frontend/tests/components/ntx-row.test.js:125`, `tests/frontend/tests/components/ntx-row.test.js:129`).
129. Product `NTTRow.toggleMode()` calls `this.save()` after collecting input values and validation (`ntx-row.js:130`, `ntx-row.js:142`).
130. If the `ntx-row` save spy is not called, the likely fault domains are validation/mocking (`Formidable.validateForm`) or test setup, not necessarily row save logic (`ntx-row.js:137`, `ntx-row.test.js:132`).
131. `schema-bootstrap.test.js` is coupled to a `like` method on Product instances (`tests/frontend/tests/integration/schema-bootstrap.test.js:74`, `tests/frontend/tests/integration/schema-bootstrap.test.js:79`).
132. The mock Product schema defines `favorite`, not `like` (`tests/frontend/tests/integration/helpers/mock-schemas.js:127`, `tests/frontend/tests/integration/helpers/mock-schemas.js:140`).
133. Current docs use Product `favorite` and `favorites` as the social Product contract (`docs/CORE.md:78`, `docs/CORE.md:83`, `.project/plans/tests/p3-p5-test-recovery-plan.md:165`).
134. Coupling rating: component tests to product internals is high; runner to config files is medium; product code to docs is intentionally high through schema contract.

## 11. Cohesion Assessment

135. `scripts/run-frontend-tests.py` is cohesive as a runner because all functions serve suite execution, parsing, reporting, or CLI behavior (`scripts/run-frontend-tests.py:154`, `scripts/run-frontend-tests.py:201`, `scripts/run-frontend-tests.py:326`, `scripts/run-frontend-tests.py:428`).
136. `vitest.config.js` is cohesive as a resolver/test-environment config, but its alias surface encodes package ownership assumptions (`tests/frontend/vitest.config.js:8`, `tests/frontend/vitest.config.js:17`).
137. `setup.js` is broad but cohesive as a jsdom compatibility harness; its responsibility includes mocks and cleanup (`tests/frontend/tests/setup.js:1`, `tests/frontend/tests/setup.js:131`, `tests/frontend/tests/setup.js:156`).
138. Core Playwright setup/config/teardown are cohesive as a temp DB lifecycle for `examples/core` (`tests/frontend/tests/e2e/global-setup.js:1`, `tests/frontend/tests/e2e/playwright.config.js:50`, `tests/frontend/tests/e2e/global-teardown.js:1`).
139. Grants Playwright files are less cohesive because setup writes a DB marker but config does not use it to start the app and instead starts a stale path (`tests/frontend/tests/e2e/grants-global-setup.js:21`, `tests/frontend/tests/e2e/playwright.grants.config.js:34`).
140. Perf Playwright files are less cohesive because config and seed setup both resolve old `src/n3tx` paths, diverging from the documented multi-package workspace (`tests/frontend/tests/e2e/playwright.perf.config.js:8`, `tests/frontend/tests/e2e/perf-global-setup.js:14`, `AGENTS.md` loaded context lists packages under `/workspace/packages/`).
141. `Component.js` is a large but purposeful base class: actor identity, schema attachment, stylesheet loading, display mode, subscription cleanup, and lifecycle are shared by Web Components (`Component.js:46`, `Component.js:91`, `Component.js:305`, `Component.js:406`, `Component.js:432`).
142. `NTT.js` is a central god-ish runtime module, but its scope matches the core entity registry contract documented in `FRONTEND.md` (`FRONTEND.md:42`, `FRONTEND.md:43`, `NTT.js:109`).
143. `ntx-ref-picker.js` is cohesive around a single form subcomponent: choose existing refs or create a new child entity (`ntx-ref-picker.js:1`, `ntx-ref-picker.js:4`, `ntx-ref-picker.js:19`).
144. `ntx-row.js` is cohesive as a table row specialization of `NTTItem` (`ntx-row.js:1`, `ntx-row.js:4`, `packages/n3tx-ui/docs/components.md:25`).
145. `ntx-profile.js` is cohesive as a profile page component (`ntx-profile.js:1`, `ntx-profile.js:4`).
146. `ntx-ref-picker.test.js` is not cohesive as a unit test file; it contains an 80-line test plan and tests constructor, attributes, rendering, private modes, actions, cleanup, edge cases, and static styles in one file (`tests/frontend/tests/components/ntx-ref-picker.test.js:1`, `tests/frontend/tests/components/ntx-ref-picker.test.js:1155`).

## 12. Boundary Analysis

147. Public product boundary: schema sections and Web Component attributes are the durable contract (`FRONTEND.md:224`, `packages/n3tx-ui/docs/components.md:176`, `packages/n3tx-ui/docs/components.md:188`).
148. Internal product boundary: `Component` private fields and `NTT` private maps are intentionally inaccessible (`Component.js:46`, `NTT.js:123`).
149. Leaky test boundary: tests call underscore methods on `NTTRefPicker`, treating them as public despite their internal naming (`tests/frontend/tests/components/ntx-ref-picker.test.js:348`, `tests/frontend/tests/components/ntx-ref-picker.test.js:426`).
150. Stable component ownership boundary: package docs list `NTTProfile` in `n3tx-ui`, but `NTTFavorites` is documented as a page wrapper for favorites route in docs/frontend, not in `n3tx-ui` component docs (`FRONTEND.md:73`, `docs/frontend/COMPONENTS.md:681`).
151. Actual ownership boundary: `ntx-favorites.js` lives in examples, proving the current test import path is a harness mismatch (`examples/core/static/components/ntx-favorites.js:1`).
152. Stable styling boundary: current docs say pages link static CSS files and theme entrypoints, and `Component`/standalone components can link external CSS (`packages/n3tx-ui/docs/styling.md:25`, `docs/frontend/COMPONENTS.md:93`, `ntx-ref-picker.js:86`).
153. Test styling boundary violation: expecting inline `<style>` and static style strings in `NTTRefPicker` reintroduces an older implementation detail (`tests/frontend/tests/components/ntx-ref-picker.test.js:382`, `tests/frontend/tests/components/ntx-ref-picker.test.js:1155`).
154. Browser harness boundary: each Playwright config should be self-contained for one app, but grants/perf configs currently encode old workspace layout (`tests/frontend/tests/e2e/playwright.grants.config.js:34`, `tests/frontend/tests/e2e/playwright.perf.config.js:8`).
155. Runner boundary: `scripts/run-frontend-tests.py` should not know per-app startup internals beyond config file selection, and it mostly preserves that boundary (`scripts/run-frontend-tests.py:112`, `scripts/run-frontend-tests.py:125`, `scripts/run-frontend-tests.py:138`).

## 13. Configuration Surface

156. Top-level runner configuration surface: `--suite`, `--continue-on-failure`, `--fail-fast`, `--list`, `--overview-file`, `--summary-color`, and passthrough `test_args` (`scripts/run-frontend-tests.py:432`, `scripts/run-frontend-tests.py:439`, `scripts/run-frontend-tests.py:447`, `scripts/run-frontend-tests.py:452`, `scripts/run-frontend-tests.py:457`, `scripts/run-frontend-tests.py:467`, `scripts/run-frontend-tests.py:473`).
157. Runner hardcoded surface: suite commands and working dirs are fixed in `build_suites()` (`scripts/run-frontend-tests.py:85`, `scripts/run-frontend-tests.py:87`, `scripts/run-frontend-tests.py:95`).
158. Vitest config surface: aliases are regex-based and global for all unit tests (`tests/frontend/vitest.config.js:18`, `tests/frontend/vitest.config.js:20`, `tests/frontend/vitest.config.js:31`).
159. Unit setup config surface: none; mocks are global and always installed (`tests/frontend/tests/setup.js:35`, `tests/frontend/tests/setup.js:38`, `tests/frontend/tests/setup.js:67`, `tests/frontend/tests/setup.js:106`).
160. Core Playwright config surface: `N3TX_E2E_REUSE_SERVER`, `PLAYWRIGHT_RUN_ID`, `__NTT_E2E_MARKER`, `.venv-e2e`, and package `PYTHONPATH` (`tests/frontend/tests/e2e/playwright.config.js:13`, `tests/frontend/tests/e2e/playwright.config.js:16`, `tests/frontend/tests/e2e/playwright.config.js:17`, `tests/frontend/tests/e2e/playwright.config.js:59`).
161. Veille Playwright config surface: `N3TX_PORT`, `N3TX_API_URL`, `N3TX_CHAT_LLM`, `__NTX_VEILLE_E2E_MARKER` (`tests/frontend/tests/e2e/veille.playwright.config.js:56`, `tests/frontend/tests/e2e/veille.playwright.config.js:57`, `tests/frontend/tests/e2e/veille.playwright.config.js:58`, `tests/frontend/tests/e2e/veille.playwright.config.js:59`).
162. Grants config surface is underdeveloped: it lacks package `PYTHONPATH`, `.venv-e2e` detection, and marker/env handoff used by core and veille (`tests/frontend/tests/e2e/playwright.grants.config.js:33`, `tests/frontend/tests/e2e/playwright.config.js:7`, `tests/frontend/tests/e2e/playwright.config.js:13`).
163. Perf config surface is stale: it uses `NTT_PORT`, `NTT_PROFILING`, and old `src/n3tx/example`, while current config examples and Playwright docs use `N3TX_*` and `examples/core` (`tests/frontend/tests/e2e/playwright.perf.config.js:41`, `FRONTEND.md:182`).
164. Product `Component` config surface: display attribute, semantic aliases, and optional `styles` getter (`Component.js:112`, `Component.js:330`, `Component.js:262`).
165. Product `NTTRefPicker` config surface: field/model/parent/child attributes and `defer-save` (`ntx-ref-picker.js:41`, `ntx-ref-picker.js:53`, `ntx-ref-picker.js:59`).

## 14. Error Propagation

166. Runner subprocess failures become suite status via return code and parsed failed/error counts (`scripts/run-frontend-tests.py:226`, `scripts/run-frontend-tests.py:258`, `scripts/run-frontend-tests.py:506`).
167. Runner continues after failures by default and returns `1` if any selected suite failed (`scripts/run-frontend-tests.py:440`, `scripts/run-frontend-tests.py:517`, `scripts/run-frontend-tests.py:521`).
168. Runner missing cwd becomes a warning result, not a failure (`scripts/run-frontend-tests.py:501`, `scripts/run-frontend-tests.py:504`).
169. Unit setup turns one leaked unhandled rejection into a test failure after cleanup (`tests/frontend/tests/setup.js:126`, `tests/frontend/tests/setup.js:194`).
170. Product stylesheet loading errors are logged as warnings and do not fail component construction (`Component.js:289`, `Component.js:290`, `Component.js:292`).
171. Product `NTT` schema preloaded parse failures are logged and fall back to network (`NTT.js:161`, `NTT.js:167`, `NTT.js:168`).
172. Product `NTT` method response fallback pulls authoritative state when response data is ambiguous or non-object (`NTT.js:1034`, `NTT.js:1036`, `NTT.js:1078`).
173. `NTTRefPicker._showPicker()` silently returns if the child DynamicClass is missing (`ntx-ref-picker.js:108`, `ntx-ref-picker.js:109`).
174. `NTTRefPicker._showInlineCreate()` silently returns if child schema is absent (`ntx-ref-picker.js:179`, `ntx-ref-picker.js:180`).
175. Playwright marker errors are not caught before web server startup; shell `cat` failure occurs inside the command string (`tests/frontend/tests/e2e/playwright.config.js:51`, `tests/frontend/tests/e2e/veille.playwright.config.js:51`).
176. Grants path errors occur before app-level error handling because `cd /workspace/example_grants` is embedded in the command (`tests/frontend/tests/e2e/playwright.grants.config.js:34`).
177. Perf path errors occur before app-level error handling because stale resolved dirs feed both setup and command (`tests/frontend/tests/e2e/playwright.perf.config.js:8`, `tests/frontend/tests/e2e/perf-global-setup.js:14`).

## 15. Failure Cluster Classification

178. C1 missing `../../components/ntx-favorites.js`: harness contract drift, because alias points to `n3tx-ui` but implementation is example-local (`tests/frontend/vitest.config.js:31`, `tests/frontend/tests/components/ntx-favorites.test.js:28`, `examples/core/static/components/ntx-favorites.js:1`).
179. C2 missing `../../components/ntx-logs.js`: harness contract drift for same reason (`tests/frontend/vitest.config.js:31`, `tests/frontend/tests/components/ntx-logs.test.js:35`, `examples/core/static/components/ntx-logs.js:1`).
180. C3 `ntx-ref-picker` inline `<style>` expectation: stale test contract, because implementation links `ntx-ref-picker.css` and styling docs prefer external/tokenized CSS (`ntx-ref-picker.js:86`, `ntx-ref-picker.css:1`, `packages/n3tx-ui/docs/styling.md:25`).
181. C4 `NTTRefPicker.styles` static expectation: stale test contract, because class has no static styles and uses `STYLES_URL` constant (`ntx-ref-picker.js:28`, `ntx-ref-picker.js:30`, `tests/frontend/tests/components/ntx-ref-picker.test.js:1155`).
182. C5 `Component.SIZES` five sizes expectation: stale test contract, because current implementation and component docs include `row` (`Component.js:26`, `packages/n3tx-ui/docs/components.md:180`, `tests/frontend/tests/core/Component.test.js:75`).
183. C6 `ntx-profile` `.placeholder` expectation: stale DOM class assertion or unresolved naming contract, because product renders `.profile-note` (`ntx-profile.js:54`, `tests/frontend/tests/components/ntx-profile.test.js:159`).
184. C7 `ntx-row` save spy not called: unresolved until validation mock behavior is inspected, because product code calls `this.save()` after `Formidable.validateForm(this)` returns no errors (`ntx-row.js:137`, `ntx-row.js:142`, `tests/frontend/tests/components/ntx-row.test.js:132`).
185. C8 schema bootstrap expects `instance.like`: stale test assertion, because mock schema defines `favorite` and docs mark Product social method as `favorite` (`tests/frontend/tests/integration/schema-bootstrap.test.js:79`, `tests/frontend/tests/integration/helpers/mock-schemas.js:140`, `docs/CORE.md:83`).
186. C9 core Playwright marker startup failure: harness infrastructure issue, because web server command assumes marker file exists and is readable before startup (`tests/frontend/tests/e2e/playwright.config.js:17`, `tests/frontend/tests/e2e/playwright.config.js:51`, `tests/frontend/tests/e2e/global-setup.js:37`).
187. C10 veille marker startup failure: harness infrastructure issue, same marker-file pattern with separate env variable (`tests/frontend/tests/e2e/veille.playwright.config.js:17`, `tests/frontend/tests/e2e/veille.playwright.config.js:51`, `tests/frontend/tests/e2e/veille.global-setup.js:27`).
188. C11 grants wrong path: harness path drift, because config and setup use `/workspace/example_grants` while current project examples are under `examples/` (`tests/frontend/tests/e2e/playwright.grants.config.js:34`, `tests/frontend/tests/e2e/grants-global-setup.js:12`, `AGENTS.md` loaded context lists `/workspace/examples/grants`).
189. C12 perf wrong path: harness path drift, because config uses `src/n3tx/example` and setup uses `src/n3tx/core/tests/profiling`, which do not match current package/example layout (`tests/frontend/tests/e2e/playwright.perf.config.js:8`, `tests/frontend/tests/e2e/perf-global-setup.js:14`).

## 16. Contract Tables

190. Product contract table:

| Contract | Evidence | Current Direction |
|---|---|---|
| Runtime and visual packages are split | `FRONTEND.md:20`, `FRONTEND.md:194` | Keep package ownership explicit |
| Schema is universal frontend contract | `docs/CORE.md:109`, `FRONTEND.md:218` | Update mocks to schema reality |
| Product social action is favorite/favorites | `docs/CORE.md:83`, `tests/frontend/tests/integration/helpers/mock-schemas.js:140` | Do not restore Product `like` only for stale test |
| `row` is a valid display mode | `Component.js:26`, `packages/n3tx-ui/docs/components.md:180` | Update tests that expect five sizes |
| Component CSS can be external | `Component.js:262`, `ntx-ref-picker.js:86` | Do not require inline style strings |
| Profile note class is current DOM | `ntx-profile.js:54` | Decide whether class is public before changing |

191. Harness contract table:

| Contract | Evidence | Risk |
|---|---|---|
| `../../components` resolves to `n3tx-ui` | `tests/frontend/vitest.config.js:31` | Example-only component imports fail |
| setup mocks browser APIs globally | `tests/frontend/tests/setup.js:35`, `tests/frontend/tests/setup.js:67` | Shared state can hide leaks |
| core E2E starts examples/core | `tests/frontend/tests/e2e/playwright.config.js:52` | Marker must exist before shell command |
| grants E2E starts example_grants | `tests/frontend/tests/e2e/playwright.grants.config.js:34` | Path drift breaks startup |
| perf E2E starts old src tree | `tests/frontend/tests/e2e/playwright.perf.config.js:8` | Path drift breaks startup |
| runner excludes grants/veille/perf from core | `scripts/run-frontend-tests.py:68`, `scripts/run-frontend-tests.py:69` | Good dedupe contract |

## 17. Strategic Improvement Propositions

192. P1 — Make component ownership explicit in Vitest imports.
193. Current state: all `../../components/*` imports route to `n3tx-ui` (`tests/frontend/vitest.config.js:31`).
194. Problem: example-local components fail module resolution when tests pretend they are package components (`tests/frontend/tests/components/ntx-favorites.test.js:28`, `tests/frontend/tests/components/ntx-logs.test.js:35`).
195. Proposed contract sketch:

```js
// Framework component tests
import '../../components/ntx-profile.js';

// Example component tests
import '../../../../examples/core/static/components/ntx-favorites.js';
```

196. Migration path: classify each test file as `framework`, `example-core`, `example-actors`, or `app-veille`, then make imports reflect ownership.
197. Risk: if product wants `ntx-favorites` or `ntx-logs` promoted to `n3tx-ui`, promotion should include docs and package static files, not only an alias workaround.

198. P2 — Add app-specific aliases only when intentionally testing app-local components.
199. Current state: no alias maps `../../components/ntx-favorites.js` to examples (`tests/frontend/vitest.config.js:31`).
200. Proposed contract sketch:

```js
{ find: /^@example-core\//, replacement: path.resolve(__dirname, '../../examples/core/static/') + '/' }
```

201. What gets simpler: tests visually distinguish framework imports from app imports.
202. Migration path: introduce aliases like `@example-core/components/ntx-favorites.js`, then move app-local component tests out of `tests/components` if needed.
203. Risk: more aliases can hide ownership if names are too generic.

204. P3 — Normalize display-mode tests to current `row` contract.
205. Current state: product defines `SIZES = ['xs','sm','md','lg','xl','row']` (`Component.js:26`).
206. Current stale assertions expect exactly five sizes (`tests/frontend/tests/core/Component.test.js:75`, `tests/frontend/tests/integration/display-mode-cascade.test.js:157`).
207. Proposed contract sketch:

```js
expect(Component.SIZES).toEqual(['xs', 'sm', 'md', 'lg', 'xl', 'row']);
expect(Component.normalizeDisplay('row')).toBe('row');
```

208. Migration path: update tests and docs/frontend/COMPONENTS if it still lists only five sizes (`docs/frontend/COMPONENTS.md:89`).
209. Risk: some adaptive breakpoint tests should still exclude `row` because `row` is forced display, not a width breakpoint (`Component.js:315`).

210. P4 — Treat CSS presence as behavior, not inline implementation.
211. Current state: `NTTRefPicker` renders `<link rel="stylesheet" href="...ntx-ref-picker.css">` (`ntx-ref-picker.js:86`, `ntx-ref-picker.js:87`).
212. Stale tests assert `<style>` and static CSS strings (`tests/frontend/tests/components/ntx-ref-picker.test.js:382`, `tests/frontend/tests/components/ntx-ref-picker.test.js:1155`).
213. Proposed contract sketch:

```js
const link = picker.shadowRoot.querySelector('link[rel="stylesheet"]');
expect(link.href).toContain('ntx-ref-picker.css');
```

214. Migration path: update tests to assert external stylesheet link and move CSS selector assertions to CSS file text checks if source-level CSS assertions are still valuable.
215. Risk: jsdom does not load CSS visually, so behavior tests should not depend on computed styles.

216. P5 — Unify Playwright app path and env conventions.
217. Current state: core uses `examples/core` with `N3TX_SQLITE_DB`; veille uses `apps/veille`; grants/perf use old paths (`tests/frontend/tests/e2e/playwright.config.js:52`, `tests/frontend/tests/e2e/veille.playwright.config.js:52`, `tests/frontend/tests/e2e/playwright.grants.config.js:34`, `tests/frontend/tests/e2e/playwright.perf.config.js:8`).
218. Proposed contract sketch:

```js
const APPS = {
  core: { cwd: '/workspace/examples/core', schemaUrl: '/Product', port: 5000 },
  grants: { cwd: '/workspace/examples/grants', schemaUrl: '/Grant', port: 5000 },
  veille: { cwd: '/workspace/apps/veille', schemaUrl: '/login.html', port: 5010 },
};
```

219. Migration path: share a small E2E helper module for package `PYTHONPATH`, Python binary detection, marker path generation, and app cwd.
220. Risk: shared helpers must not hide app-specific setup, especially veille `N3TX_CHAT_LLM=test` (`tests/frontend/tests/e2e/veille.playwright.config.js:58`).

221. P6 — Replace shell `cat marker` with explicit env handoff or guarded command.
222. Current state: server commands read marker files inline with `cat` (`tests/frontend/tests/e2e/playwright.config.js:51`, `tests/frontend/tests/e2e/veille.playwright.config.js:51`).
223. Proposed contract sketch:

```js
command: `${PYTHON_BIN} main.py`,
env: { ...process.env, N3TX_SQLITE_DB: process.env.__NTX_E2E_DB_PATH, PYTHONPATH }
```

224. Alternative guarded sketch:

```sh
test -f "$MARKER" && N3TX_SQLITE_DB="$(cat "$MARKER")" python main.py
```

225. Migration path: setup writes both marker and process env; config uses env when available and marker only as fallback.
226. Risk: Playwright global setup and config run in different phases; confirm env mutation visibility before relying on it.

227. P7 — Make mock schemas first-class contract fixtures.
228. Current state: `schema-bootstrap.test.js` expects `like`, but `mock-schemas.js` defines `favorite` (`tests/frontend/tests/integration/schema-bootstrap.test.js:79`, `tests/frontend/tests/integration/helpers/mock-schemas.js:140`).
229. Proposed contract sketch:

```js
expect(typeof instance.favorite).toBe('function');
expect(instance.like).toBeUndefined();
```

230. Migration path: annotate mock schema fixture with source contract links and keep Product `favorite`, Comment `like` split explicit.
231. Risk: if backend Product schema changes, fixture must be regenerated or validated against live schema.

232. P8 — Split high-coupling component tests by public boundary.
233. Current state: `ntx-ref-picker.test.js` tests private methods and static styles in one file (`tests/frontend/tests/components/ntx-ref-picker.test.js:348`, `tests/frontend/tests/components/ntx-ref-picker.test.js:1155`).
234. Proposed contract sketch:

```text
ntx-ref-picker.render.test.js     -> public DOM/events
ntx-ref-picker.actions.test.js    -> emitted events/TX sends
ntx-ref-picker.contract.test.js   -> attributes/currentRefs/childSchema
```

235. Migration path: preserve behavior assertions but reduce direct calls to `_showPicker()` unless explicitly marked as white-box tests.
236. Risk: fewer private-method assertions may reduce immediate coverage, but public behavior coverage better matches Web Component contracts.

## 18. Risk Register

237. Risk R1: Fixing product code to satisfy stale imports would blur package boundaries and hide example-local ownership (`tests/frontend/vitest.config.js:31`, `examples/core/static/components/ntx-favorites.js:1`).
238. Risk R2: Reintroducing inline styles into `NTTRefPicker` would conflict with external CSS/token guidance (`ntx-ref-picker.js:86`, `packages/n3tx-ui/docs/styling.md:60`).
239. Risk R3: Removing `row` from `Component.SIZES` would break `NTTRow`, table row docs, and `NTTItem.row()` (`Component.js:26`, `ntx-row.js:34`, `ntx-item.js:419`).
240. Risk R4: Changing Product method names from `favorite` back to `like` would contradict current core docs and fixture schema (`docs/CORE.md:83`, `tests/frontend/tests/integration/helpers/mock-schemas.js:140`).
241. Risk R5: Hardcoding old app paths in more places will make runner failures look like app regressions (`tests/frontend/tests/e2e/playwright.grants.config.js:34`, `tests/frontend/tests/e2e/playwright.perf.config.js:8`).
242. Risk R6: Relying on marker files without guardrails creates opaque startup failures before specs can report useful context (`tests/frontend/tests/e2e/playwright.config.js:51`).
243. Risk R7: Shared jsdom mocks can hide or create suite-order failures if global state is not reset (`tests/frontend/tests/setup.js:131`, `tests/frontend/tests/setup.js:156`).
244. Risk R8: Tests that assert private methods make legitimate refactors expensive (`tests/frontend/tests/components/ntx-ref-picker.test.js:426`, `tests/frontend/tests/components/ntx-ref-picker.test.js:865`).
245. Risk R9: `ntx-row` failure classification is ambiguous without inspecting actual `Formidable.validateForm` behavior under test mocks (`ntx-row.js:137`, `tests/frontend/tests/components/ntx-row.test.js:132`).

## 19. Verification Strategy For Future Fixes

246. First verify runner listing with `python3 scripts/run-frontend-tests.py --list`; this reads suite definitions without starting apps (`scripts/run-frontend-tests.py:481`, `scripts/run-frontend-tests.py:483`).
247. For import fixes, run only the affected Vitest files before full suite because Vitest includes all test files by default (`tests/frontend/vitest.config.js:13`).
248. For component ownership fixes, assert that framework component tests import `n3tx-ui` components and example component tests import example static files (`tests/frontend/vitest.config.js:31`, `examples/core/static/components/ntx-favorites.js:1`).
249. For marker fixes, run one Playwright config at a time because each config starts a server and uses temp DB state (`tests/frontend/tests/e2e/playwright.config.js:50`, `tests/frontend/tests/e2e/veille.playwright.config.js:50`).
250. For grants path fixes, verify setup and config both use the same app cwd and DB env variable (`tests/frontend/tests/e2e/grants-global-setup.js:12`, `tests/frontend/tests/e2e/playwright.grants.config.js:34`).
251. For perf path fixes, verify config server cwd and seed script path are both in current workspace layout (`tests/frontend/tests/e2e/playwright.perf.config.js:8`, `tests/frontend/tests/e2e/perf-global-setup.js:14`).
252. For Product method fixture fixes, verify generated methods on DynamicClass match `Object.keys(ProductSchema.methods)` (`NTT.js:620`, `NTT.js:725`, `tests/frontend/tests/integration/helpers/mock-schemas.js:127`).
253. For display mode fixes, test `normalizeDisplay('row')` separately from breakpoint resolution because breakpoints remain `xs` through `xl` (`Component.js:41`, `Component.js:315`).
254. For CSS contract fixes, test link presence and CSS file contents rather than inline `<style>` (`ntx-ref-picker.js:86`, `ntx-ref-picker.css:11`).
255. For profile DOM fixes, decide whether `.profile-note` is public; if yes, update test selectors, if no, assert text content only (`ntx-profile.js:54`, `tests/frontend/tests/components/ntx-profile.test.js:161`).

## 20. Downstream Use Guide

256. For bug fixing: start with C1/C2 import failures because they block Vitest collection before behavior assertions matter (`tests/frontend/tests/components/ntx-favorites.test.js:28`, `tests/frontend/tests/components/ntx-logs.test.js:35`).
257. For bug fixing: handle Playwright path/marker failures before app behavior failures because startup failures prevent meaningful browser assertions (`tests/frontend/tests/e2e/playwright.config.js:51`, `tests/frontend/tests/e2e/playwright.grants.config.js:34`).
258. For test repair: apply P-1 classification note before editing product code (`.project/plans/tests/contract-triage-p-1.md:59`, `.project/plans/tests/contract-triage-p-1.md:64`).
259. For feature development: preserve schema as the universal contract and avoid adding test-only frontend duplication of backend model knowledge (`docs/CORE.md:111`, `FRONTEND.md:220`).
260. For integration planning: document whether a component is framework-level, example-local, or app-local before adding a test import (`FRONTEND.md:57`, `FRONTEND.md:206`).
261. For refactoring: do not split `Component` responsibilities unless an alternative still supports actor bridge, schema attach, stylesheet loading, display mode, and cleanup (`Component.js:76`, `Component.js:183`, `Component.js:274`, `Component.js:380`, `Component.js:448`).
262. For suite hardening: keep runner suite definitions centralized but share E2E helper code for repeated Python path, venv detection, marker path, and temp DB setup (`scripts/run-frontend-tests.py:85`, `tests/frontend/tests/e2e/playwright.config.js:7`, `tests/frontend/tests/e2e/global-setup.js:12`).
263. For docs updates after fixes: update `FRONTEND.md` test environment section if runner behavior changes (`FRONTEND.md:174`, `FRONTEND.md:176`).
264. For docs updates after component contract fixes: update `docs/frontend/COMPONENTS.md` if `Component.SIZES` remains documented as five sizes (`docs/frontend/COMPONENTS.md:89`, `Component.js:26`).

## 21. Finding Index

| ID | Type | Severity | Finding | Primary Evidence | Classification |
|---|---|---:|---|---|---|
| F1 | Import | High | `ntx-favorites` tests import package component that is example-local | `tests/frontend/vitest.config.js:31`, `examples/core/static/components/ntx-favorites.js:1` | Harness drift |
| F2 | Import | High | `ntx-logs` tests import package component that is example-local | `tests/frontend/vitest.config.js:31`, `examples/core/static/components/ntx-logs.js:1` | Harness drift |
| F3 | CSS | Medium | `ntx-ref-picker` tests assert inline style but product links external CSS | `ntx-ref-picker.js:86`, `tests/frontend/tests/components/ntx-ref-picker.test.js:386` | Stale test |
| F4 | CSS | Medium | `NTTRefPicker.styles` expected but not part of implementation | `ntx-ref-picker.js:28`, `tests/frontend/tests/components/ntx-ref-picker.test.js:1157` | Stale test |
| F5 | Display | Medium | Tests expect five sizes but product supports `row` | `Component.js:26`, `packages/n3tx-ui/docs/components.md:180` | Stale test/docs drift |
| F6 | Profile | Low | Profile test expects `.placeholder`, implementation renders `.profile-note` | `ntx-profile.js:54`, `tests/frontend/tests/components/ntx-profile.test.js:159` | Stale DOM assertion |
| F7 | Row | Medium | Save spy failure requires validation/mock triage before product change | `ntx-row.js:137`, `ntx-row.js:142` | Unresolved |
| F8 | Schema | Medium | Test expects Product `like`, mock/product docs define `favorite` | `tests/frontend/tests/integration/schema-bootstrap.test.js:79`, `tests/frontend/tests/integration/helpers/mock-schemas.js:140` | Stale test |
| F9 | E2E | High | Core web server command reads marker file via shell `cat` | `tests/frontend/tests/e2e/playwright.config.js:51` | Harness fragility |
| F10 | E2E | High | Veille web server command repeats marker `cat` fragility | `tests/frontend/tests/e2e/veille.playwright.config.js:51` | Harness fragility |
| F11 | E2E | Critical | Grants config/setup use stale `/workspace/example_grants` path | `tests/frontend/tests/e2e/playwright.grants.config.js:34`, `tests/frontend/tests/e2e/grants-global-setup.js:12` | Harness path drift |
| F12 | E2E | Critical | Perf config/setup use stale `src/n3tx` paths | `tests/frontend/tests/e2e/playwright.perf.config.js:8`, `tests/frontend/tests/e2e/perf-global-setup.js:14` | Harness path drift |
| F13 | Runner | Strength | Top-level runner correctly separates unit/core/grants/veille/perf suites | `scripts/run-frontend-tests.py:85`, `scripts/run-frontend-tests.py:148` | Design strength |
| F14 | Runner | Strength | Core E2E discovery excludes specialized specs | `scripts/run-frontend-tests.py:68`, `scripts/run-frontend-tests.py:72` | Design strength |
| F15 | Runtime | Strength | Schema bootstrap and DynamicClass factory align with docs | `FRONTEND.md:279`, `NTT.js:302`, `NTT.js:619` | Design strength |

## 22. Final Assessment

265. The subsystem’s product architecture is sounder than the current failure list suggests: schema-driven runtime and Web Component composition are documented and visible in code (`docs/CORE.md:109`, `FRONTEND.md:267`, `NTT.js:302`).
266. The failures cluster around stale or under-specified test harness contracts: imports, app paths, marker files, DOM class names, CSS loading style, and schema fixture expectations.
267. The most important guardrail is to classify each failure before product edits, because several straightforward “fixes” would regress product architecture to older behavior.
268. Immediate repair work should start with harness path/import correctness, then schema fixture alignment, then ambiguous behavior-level tests such as `ntx-row` validation.
269. Product code should only change where a test still matches current docs and runtime contracts after this classification.

## 23. Suggested Triage Order

270. Step 1: repair or reclassify missing module imports, because Vitest cannot evaluate behavior tests if module collection fails (`tests/frontend/tests/components/ntx-favorites.test.js:28`, `tests/frontend/tests/components/ntx-logs.test.js:35`).
271. Step 2: decide whether `ntx-favorites` and `ntx-logs` remain example-local or become package components; current code says example-local (`examples/core/static/components/ntx-favorites.js:1`, `examples/core/static/components/ntx-logs.js:1`).
272. Step 3: update CSS assertions around `NTTRefPicker` to external stylesheet behavior, because the product code already points at `ntx-ref-picker.css` (`ntx-ref-picker.js:28`, `ntx-ref-picker.js:86`).
273. Step 4: align display mode tests and docs around `row`, but keep breakpoint assertions focused on `xs` through `xl` (`Component.js:26`, `Component.js:315`).
274. Step 5: update Product schema bootstrap assertions to `favorite` while leaving Comment social behavior free to use `like` (`tests/frontend/tests/integration/helpers/mock-schemas.js:140`, `docs/CORE.md:83`).
275. Step 6: isolate `ntx-row` save behavior with explicit `Formidable.validateForm` expectations before modifying `NTTRow.toggleMode()` (`ntx-row.js:137`, `ntx-row.js:142`).
276. Step 7: normalize Playwright app paths before browser behavior triage, because startup path failures are infrastructure, not app behavior (`tests/frontend/tests/e2e/playwright.grants.config.js:34`, `tests/frontend/tests/e2e/playwright.perf.config.js:8`).
277. Step 8: centralize marker-file handling after paths are fixed, because marker fragility appears in both core and veille configs (`tests/frontend/tests/e2e/playwright.config.js:51`, `tests/frontend/tests/e2e/veille.playwright.config.js:51`).
278. Step 9: rerun `scripts/run-frontend-tests.py --suite unit` before browser suites, because unit import failures are independent from web server startup (`scripts/run-frontend-tests.py:87`, `scripts/run-frontend-tests.py:95`).
279. Step 10: only after unit contract drift is settled, run app-specific Playwright configs one at a time (`scripts/run-frontend-tests.py:109`, `scripts/run-frontend-tests.py:123`, `scripts/run-frontend-tests.py:135`).

## 24. Open Questions

280. OQ1: Should `ntx-favorites` be promoted from example-local page wrapper to `n3tx-ui` framework component, given docs/frontend describes it as a component but package docs do not list it under `n3tx-ui` (`docs/frontend/COMPONENTS.md:681`, `packages/n3tx-ui/docs/components.md:65`)?
281. OQ2: Should `ntx-logs` be framework-level developer tooling or remain example-local debugging UI, given it imports shared `Logging` but lives in examples (`examples/core/static/components/ntx-logs.js:1`, `examples/core/static/components/ntx-logs.js:16`)?
282. OQ3: Is `.profile-note` a stable selector contract or an implementation detail; current docs mention profile route registration but not this DOM class (`FRONTEND.md:76`, `ntx-profile.js:54`)?
283. OQ4: Should Playwright marker files remain the app startup IPC primitive, or should configs move toward direct env injection where Playwright phase semantics permit it (`tests/frontend/tests/e2e/global-setup.js:37`, `tests/frontend/tests/e2e/playwright.config.js:51`)?
284. OQ5: Should perf tests still belong to the frontend harness if their seed script and app path point at removed source-tree locations (`tests/frontend/tests/e2e/playwright.perf.config.js:8`, `tests/frontend/tests/e2e/perf-global-setup.js:14`)?
285. OQ6: Should `docs/frontend/COMPONENTS.md` be treated as stale where it lists `Component.SIZES` as five values, or should `row` be documented as a non-breakpoint mode in the same table (`docs/frontend/COMPONENTS.md:89`, `Component.js:26`)?
286. OQ7: Should component unit tests prefer public Web Component events and DOM behavior over direct calls to underscore methods (`tests/frontend/tests/components/ntx-ref-picker.test.js:400`, `tests/frontend/tests/components/ntx-ref-picker.test.js:818`)?
287. OQ8: Should mock schemas be generated from live backend schema snapshots to prevent mismatches like `like` versus `favorite` (`tests/frontend/tests/integration/schema-bootstrap.test.js:79`, `tests/frontend/tests/integration/helpers/mock-schemas.js:140`)?

## 25. Audit Constraints Honored

288. The audit did not modify product source files.
289. The audit did not modify test source files.
290. The only written artifact is this report at `.project/audits/frontend-test-harness-and-contracts/01-architecture.md`.
291. Product contracts and test harness contracts are explicitly separated throughout the report.
292. Claims are tied to file:line citations from docs, runner files, tests, and product runtime/component code.
293. Recommendations are framed as audit findings and propositions, not applied fixes.
