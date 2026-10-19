# Frontend Test Harness And Contracts — API Contracts Audit

## Scope

This audit is read-only for product and test source. The only written artifact is this report. The audited subsystem is the frontend unit/browser harness and the public contracts asserted by the listed failing frontend tests.

Evidence sources include the frontend runner, Vitest config/setup, Playwright configs/setup/teardown, failing Vitest files, referenced implementation files, frontend docs, and test-triage plans. The reproduced command was `npx vitest run tests/components/ntx-ref-picker.test.js tests/components/ntx-row.test.js tests/components/ntx-profile.test.js tests/components/ntx-favorites.test.js tests/components/ntx-logs.test.js tests/core/Component.test.js tests/integration/display-mode-cascade.test.js tests/integration/schema-bootstrap.test.js --reporter=verbose` from `/workspace/tests/frontend`.

## Classification Rubric

| Classification | Meaning | Evidence Basis |
|---|---|---|
| Current intended contract | The failing assertion matches current docs or implementation intent and should normally remain a product/test contract. | Contract-triage guidance says matching current documentation points toward product regression/current contract preservation. `.project/plans/tests/contract-triage-p-1.md:37-44`, `.project/plans/tests/contract-triage-p-1.md:46-57` |
| Stale contract | The failing assertion targets an older or non-public behavior that contradicts current implementation/docs. | The triage rule says stale tests should be updated and product code should not be regressed to old behavior. `.project/plans/tests/contract-triage-p-1.md:22-35`, `.project/plans/tests/contract-triage-p-1.md:39-44` |
| Infrastructure contract | The failure comes from runner, alias, fixture, marker, environment, mock, cleanup, or suite loading assumptions. | The runner and setup files define isolated jsdom and Playwright harness behavior. `scripts/run-frontend-tests.py:85-148`, `tests/frontend/tests/setup.js:131-199`, `tests/frontend/tests/e2e/playwright.config.js:21-64` |
| Unresolved | Both the test expectation and current implementation are plausible public contracts, or docs disagree. | The triage checklist classifies no authoritative contract as unresolved. `.project/plans/tests/contract-triage-p-1.md:46-57` |

## Public API Inventory

| Surface | Contract | Evidence |
|---|---|---|
| Frontend runtime package boundary | `n3tx-core` owns non-visual JS runtime, including `NTT`, `Component`, actor/matrix/TX, transport, and config. | `FRONTEND.md:20-24`, `FRONTEND.md:40-55` |
| Visual component package boundary | `n3tx-ui` owns registered components, visual bases, widgets, forms, and themes. | `FRONTEND.md:57-89`, `packages/n3tx-ui/docs/components.md:9-18` |
| Component base API | `Component` exposes observed attributes `model`, `addr`, `hash`, `ref`, `display`, schema/proto/value accessors, `attach`, `subscribe`, lifecycle hooks, and `render()` as abstract. | `Component.js:112-145`, `Component.js:167-189`, `Component.js:414-429`, `Component.js:436-465`, `docs/frontend/COMPONENTS.md:67-91` |
| Component display API | `Component.normalizeDisplay()` maps semantic aliases and abstract sizes, while `displayBreakpoints` define `xl/lg/md/sm/xs` thresholds. | `Component.js:25-44`, `Component.js:315-317`, `docs/frontend/COMPONENTS.md:110-150` |
| Row display API | Current implementation and package docs treat `row` as a display mode for table rows. | `Component.js:25-34`, `ntx-row.js:30-42`, `packages/n3tx-ui/docs/components.md:19-27`, `packages/n3tx-ui/docs/components.md:176-184` |
| NTT registry API | `NTT.has`, `NTT.get`, `NTT.attach`, `NTT.ATTACH`, and `NTT.SCHEMA` are the schema/entity bootstrap contract. | `NTT.js:200-254`, `NTT.js:269-342`, `FRONTEND.md:267-295` |
| DynamicClass API | `prototype()` creates a class with `instances`, `_schema`, `href`, `schema`, generated field accessors, generated schema methods, static `READ/CREATE/DELETE/ERROR`, and instance `_response_`. | `NTT.js:619-676`, `NTT.js:686-753`, `NTT.js:870-943`, `NTT.js:950-1079` |
| Schema contract | Backend JSON Schema is the frontend's universal contract for properties, UI hints, access, methods, `$defs`, `$id`, and `$schema`. | `docs/CORE.md:109-168`, `FRONTEND.md:218-247` |
| Ref picker API | `<ntx-ref-picker>` is a standalone custom element with attributes `field`, `model`, `parent-model`, `parent-table`, `parent-id`, `child-table` and events `ref-added` and `ref-created`. | `ntx-ref-picker.js:1-22`, `ntx-ref-picker.js:41-59`, `ntx-ref-picker.js:221-241`, `ntx-ref-picker.js:243-282` |
| Profile API | `<ntx-profile>` displays authenticated user identity and is required to be explicitly imported when app shells expose topbar `#@profile`. | `ntx-profile.js:1-6`, `ntx-profile.js:21-58`, `FRONTEND.md:73-79`, `packages/n3tx-ui/docs/components.md:65-69` |
| NTTRow API | `<ntx-row>` extends `NTTItem`, forces row display, provides inline edit, validation, error banner, action buttons, and row selection. | `ntx-row.js:1-18`, `ntx-row.js:21-42`, `ntx-row.js:129-146`, `ntx-row.js:192-230`, `ntx-row.js:232-285` |

## DOM And CSS Contract Inventory

| Surface | Contract | Evidence |
|---|---|---|
| General Component styles | `Component` subclasses expose a `styles` getter returning stylesheet URLs; the base class fetches constructable stylesheets and adopts them into shadow DOM. | `Component.js:91-104`, `Component.js:258-302`, `docs/frontend/COMPONENTS.md:93-108` |
| Standalone ref picker styles | `NTTRefPicker` does not extend `Component`; it links `ntx-ref-picker.css` directly inside shadow DOM. | `ntx-ref-picker.js:28-30`, `ntx-ref-picker.js:85-92`, `ntx-ref-picker.css:1-188` |
| Ref picker classes | Current DOM uses `.add-btn`, `.dropdown-anchor`, `.picker-dropdown`, `.picker-search`, `.picker-option`, `.picker-empty`, `.picker-create-btn`, `.inline-create`, and footer button classes. | `ntx-ref-picker.js:85-92`, `ntx-ref-picker.js:119-126`, `ntx-ref-picker.js:182-194`, `ntx-ref-picker.css:11-188` |
| Profile DOM classes | Current authenticated profile DOM uses `.profile-card`, `.profile-card-shell`, `.avatar`, `.profile-copy`, `.profile-kicker`, `.email`, `.role`, and `.profile-note`. | `ntx-profile.js:43-57` |
| Row DOM classes | Current row DOM uses `.ntx-error`, `.row`, `.cell`, `.edit-cell`, `.row-actions`, `.delete-btn`, `.edit-btn`, `.cancel-btn`, and `.ntx-error-dismiss`. | `ntx-row.js:57-97`, `ntx-row.js:201-226`, `ntx-row.js:238-271` |
| Theme/token CSS contract | First-party CSS should use canonical `--ntx-*` tokens; legacy aliases are not part of the public first-party contract. | `packages/n3tx-ui/docs/styling.md:25-40`, `packages/n3tx-ui/docs/styling.md:60-79` |

## Schema-Method Contract Inventory

| Surface | Contract | Evidence |
|---|---|---|
| Schema method generation | Backend schema includes `methods` generated from exposed routes. | `docs/CORE.md:118-131`, `docs/CORE.md:133-146` |
| Frontend method consumption | `prototype()` reads `Object.keys(schema.methods || {})` and defines one prototype function for each key. | `NTT.js:619-623`, `NTT.js:724-753` |
| Method naming source of truth | The generated function names are exact schema keys, so tests must assert the keys present in the schema fixture. | `NTT.js:724-753`, `tests/frontend/tests/integration/helpers/mock-schemas.js:127-150` |
| Mock schema inconsistency | The helper schema defines Product methods `comment` and `favorite`, while the failing test expects `comment` and `like`. | `tests/frontend/tests/integration/helpers/mock-schemas.js:127-150`, `tests/frontend/tests/integration/schema-bootstrap.test.js:74-80` |

## Test Runner Contract

| Surface | Contract | Evidence |
|---|---|---|
| Runner suites | The frontend runner has `unit`, `e2e-core`, `e2e-grants`, `e2e-veille`, and `e2e-perf` suites. | `scripts/run-frontend-tests.py:85-148` |
| Default e2e filtering | Core Playwright excludes `performance.spec.js` and specs prefixed `grants-` or `veille-` so the default core run does not duplicate specialized suites. | `scripts/run-frontend-tests.py:67-75`, `scripts/run-frontend-tests.py:95-107` |
| Runner env | Runner injects color env only; suite-specific app/env setup belongs to Vitest or Playwright configs. | `scripts/run-frontend-tests.py:78-83`, `scripts/run-frontend-tests.py:154-178` |
| Count parsing | Vitest counts prefer the trailing `Tests` summary; Playwright counts aggregate trailing summary lines. | `scripts/run-frontend-tests.py:201-223` |
| Overview persistence | Runner writes JSON overview to `.project/test-runs/frontend-test-overview.json` by default and compares previous suite status if the file exists. | `scripts/run-frontend-tests.py:27-31`, `scripts/run-frontend-tests.py:234-269`, `scripts/run-frontend-tests.py:392-425` |
| Failure continuation | Default is continue-on-failure and return non-zero at end if any suite failed. | `scripts/run-frontend-tests.py:438-451`, `scripts/run-frontend-tests.py:498-521` |
| Vitest scope | Vitest runs jsdom tests matching `tests/**/*.test.js` with globals, setup file, 10s timeout, and `restoreMocks`. | `tests/frontend/vitest.config.js:8-16` |
| Vitest aliases | Vitest rewrites core/static, UI/static, agents/static, and cross-package component imports into package source trees. | `tests/frontend/vitest.config.js:4-7`, `tests/frontend/vitest.config.js:17-35` |
| Vitest cleanup | Setup resets localStorage, sessionStorage, fetch, timers, WebSocket mocks, document body, and window toast globals between tests. | `tests/frontend/tests/setup.js:8-45`, `tests/frontend/tests/setup.js:75-106`, `tests/frontend/tests/setup.js:131-199` |
| Unhandled rejections | Setup captures leaked unhandled rejections and throws one after test cleanup, classifying stale async state as infrastructure-visible failure. | `tests/frontend/tests/setup.js:122-129`, `tests/frontend/tests/setup.js:156-198` |

## Playwright Env, Marker, And DB Contract

| Suite | Contract | Evidence |
|---|---|---|
| Core e2e | Uses package source `PYTHONPATH`, `.venv-e2e` when available, a temp marker file `__NTT_E2E_MARKER`, `examples/core`, `N3TX_SQLITE_DB` and `NTT_SQLITE_DB`, and waits on `/Product`. | `tests/frontend/tests/e2e/playwright.config.js:7-20`, `tests/frontend/tests/e2e/playwright.config.js:50-64`, `tests/frontend/tests/e2e/global-setup.js:12-21`, `tests/frontend/tests/e2e/global-setup.js:23-51`, `tests/frontend/tests/e2e/global-teardown.js:8-32` |
| Grants e2e | Uses `/workspace/example_grants`, `NTT_SQLITE_DB`, a fixed marker path `ntx-grants-e2e-dbpath.txt`, and waits on `/Grant`. | `tests/frontend/tests/e2e/playwright.grants.config.js:9-41`, `tests/frontend/tests/e2e/grants-global-setup.js:12-31`, `tests/frontend/tests/e2e/grants-global-teardown.js:9-30` |
| Veille e2e | Uses package source `PYTHONPATH`, `.venv-e2e` when available, port `5010`, `N3TX_CHAT_LLM=test`, a `__NTX_VEILLE_E2E_MARKER`, and waits on `/login.html`. | `tests/frontend/tests/e2e/veille.playwright.config.js:7-20`, `tests/frontend/tests/e2e/veille.playwright.config.js:50-67`, `tests/frontend/tests/e2e/veille.global-setup.js:6-44`, `tests/frontend/tests/e2e/veille.global-teardown.js:5-26` |
| Perf e2e | Uses legacy-looking workspace paths under `src/n3tx/...`, `NTT_PROFILING`, `NTT_PORT=5099`, `NTT_SQLITE_DB`, and the shared `global-teardown.js` marker contract. | `tests/frontend/tests/e2e/playwright.perf.config.js:6-10`, `tests/frontend/tests/e2e/playwright.perf.config.js:40-48`, `tests/frontend/tests/e2e/perf-global-setup.js:12-35` |
| Docs | Frontend docs describe core Playwright as `examples/core` with isolated SQLite DB, package `PYTHONPATH`, `.venv-e2e` autodetection, and Veille deterministic chat LLM. | `FRONTEND.md:174-184`, `packages/n3tx-ui/docs/styling.md:98-113` |

## Reproduced Failure Classification Table

| Failure | Appears To Assert | Classification | Evidence |
|---|---|---|---|
| `ntx-favorites.test.js` file-level import error: missing `../../components/ntx-favorites.js` | Existence of a public `<ntx-favorites>` component that renders an `ntx-list model="ProductLike" display="md"`. | Stale contract | The test imports a component file and asserts registration/list attributes. `tests/frontend/tests/components/ntx-favorites.test.js:27-70`. Current frontend key-file docs list visual components but not `ntx-favorites`. `FRONTEND.md:57-75`. Package component docs list standalone components but not `ntx-favorites`. `packages/n3tx-ui/docs/components.md:65-71`. |
| `ntx-logs.test.js` file-level import error: missing `../../components/ntx-logs.js` | Existence of a public `<ntx-logs>` component with log panel, filters, listener subscription, badge, and clear behavior. | Stale contract | The test imports a component file and asserts DOM/listener API. `tests/frontend/tests/components/ntx-logs.test.js:34-190`. Current frontend key-file docs list visual components but not `ntx-logs`. `FRONTEND.md:57-75`. Package component docs list standalone components but not `ntx-logs`. `packages/n3tx-ui/docs/components.md:65-71`. |
| `ntx-profile.test.js`: expected `.placeholder` settings message | A public `.placeholder` class for the profile settings note. | Stale contract | The test queries `.placeholder`. `tests/frontend/tests/components/ntx-profile.test.js:154-162`. Current implementation renders the same copy as `.profile-note`, not `.placeholder`. `ntx-profile.js:43-57`. Docs only require the profile component be imported/registered and display authenticated user identity, not a `.placeholder` selector. `FRONTEND.md:73-79`, `packages/n3tx-ui/docs/components.md:65-69`. |
| `ntx-ref-picker.test.js`: `_render` should include `<style>` | Inline style tag inside ref picker shadow DOM. | Stale contract | The test asserts `<style>`. `tests/frontend/tests/components/ntx-ref-picker.test.js:382-387`. Current implementation emits a `<link rel="stylesheet" href="...ntx-ref-picker.css">`. `ntx-ref-picker.js:85-92`. The CSS lives in a separate component stylesheet. `ntx-ref-picker.css:1-188`. |
| `ntx-ref-picker.test.js`: `NTTRefPicker.styles` exists and contains CSS selectors | A static source-level CSS string on `NTTRefPicker`. | Stale contract | The test asserts `NTTRefPicker.styles` is a string containing selectors. `tests/frontend/tests/components/ntx-ref-picker.test.js:1155-1171`. Current class has no static `styles`; it uses `STYLES_URL` and linked external CSS. `ntx-ref-picker.js:28-30`, `ntx-ref-picker.js:85-92`. The documented `styles` hook belongs to `Component` subclasses; `NTTRefPicker` is standalone. `docs/frontend/COMPONENTS.md:93-108`, `packages/n3tx-ui/docs/components.md:65-65`. |
| `ntx-row.test.js`: valid inline edit should call `save()` | Row edit validation should permit valid required fields and call save before returning to display. | Current intended contract | The test creates edit mode, valid required values, stubs `save`, and expects save/display. `tests/frontend/tests/components/ntx-row.test.js:125-136`. `NTTRow.toggleMode()` explicitly collects inputs, validates, calls `this.save()` when no errors, then switches mode/render. `ntx-row.js:129-146`. Package docs describe `NTTRow` as forcing row display with inline edit and `collectInputValues`. `packages/n3tx-ui/docs/components.md:19-27`. |
| `Component.test.js`: `Component.SIZES` equals five sizes | Public `Component.SIZES` excludes row. | Unresolved | The test expects exactly `['xs','sm','md','lg','xl']`. `tests/frontend/tests/core/Component.test.js:73-81`. Current implementation includes `row` in both `SIZES` and `ALIASES`. `Component.js:25-34`. Core component docs still list only five static sizes. `docs/frontend/COMPONENTS.md:85-91`. Package docs list `row` as an `NTTItem` display mode. `packages/n3tx-ui/docs/components.md:176-184`. |
| `display-mode-cascade.test.js`: `SIZES` and `ALIASES` have exactly five entries | Display constants exclude row from public semantic/abstract display API. | Unresolved | The test asserts five sizes and five aliases. `tests/frontend/tests/integration/display-mode-cascade.test.js:156-168`. Current implementation includes `row`. `Component.js:25-34`. `ListElement.SIZE_CASCADE` also includes `row`. `ListElement.js:20-28`. Docs disagree because `docs/frontend/COMPONENTS.md` omits row while package docs include it. `docs/frontend/COMPONENTS.md:85-123`, `packages/n3tx-ui/docs/components.md:176-184`. |
| `schema-bootstrap.test.js`: Product instance has `like()` method | Mock schema method names should include `like`. | Stale contract | The test expects `instance.comment` and `instance.like`. `tests/frontend/tests/integration/schema-bootstrap.test.js:74-80`. The helper schema defines `comment` and `favorite`, not `like`. `tests/frontend/tests/integration/helpers/mock-schemas.js:127-150`. `prototype()` generates methods from exact schema keys only. `NTT.js:724-753`. Backend/frontend docs show Product `favorite` as a method in the canonical example and schema method contract. `docs/CORE.md:80-87`, `docs/CORE.md:164-166`. |

## Error Handling Contracts

| Surface | Contract | Evidence |
|---|---|---|
| Component value type mismatch | Base `Component.value` silently logs a dev message and does not update if assigned a type different from default value. | `Component.js:239-251` |
| Abstract render | `Component.render()` throws if not implemented. | `Component.js:460-465`, `tests/frontend/tests/core/Component.test.js:107-112` |
| Stylesheet load failure | Stylesheet fetch failures are logged as warnings and do not throw. | `Component.js:274-302` |
| Dynamic field setters | Read-only field setters throw `Error`; incompatible typed setters throw `TypeError`. | `NTT.js:686-716`, `tests/frontend/tests/integration/schema-bootstrap.test.js:127-139` |
| Dynamic method validation | Generated methods throw `TypeError` for missing/invalid parameters according to method parameter schema. | `NTT.js:724-753` |
| Row validation | `NTTRow.toggleMode()` blocks save and keeps edit mode when `Formidable.validateForm()` returns errors. | `ntx-row.js:129-146`, `tests/frontend/tests/components/ntx-row.test.js:105-123` |
| Ref picker missing DynamicClass/schema | `_showPicker()` returns early when `NTT.get(modelName)` is absent; `_showInlineCreate()` returns early when child schema is absent. | `ntx-ref-picker.js:104-110`, `ntx-ref-picker.js:175-181`, `tests/frontend/tests/components/ntx-ref-picker.test.js:602-611`, `tests/frontend/tests/components/ntx-ref-picker.test.js:796-804` |
| Vitest leaked async errors | Setup captures unhandled promise rejections and throws them after cleanup, making leaked async state a test failure. | `tests/frontend/tests/setup.js:122-129`, `tests/frontend/tests/setup.js:156-198` |

## Type Safety Assumptions

| Assumption | Status | Evidence |
|---|---|---|
| DynamicClass instance data must be an object. | Current intended contract. | `NTT.js:661-667` |
| Schema field setters enforce `readOnly` and `definition.type`. | Current intended contract. | `NTT.js:686-716`, `tests/frontend/tests/integration/schema-bootstrap.test.js:127-139` |
| Form/ref picker collection values are serialized from `data-key` controls with checkbox/number/object coercions. | Current intended contract. | `ntx-ref-picker.js:243-257`, `tests/frontend/tests/components/ntx-ref-picker.test.js:865-984` |
| Row inline edit coerces booleans and numbers before validation. | Current intended contract. | `ntx-row.js:148-169` |
| Mock schemas are expected to mirror real backend schemas. | Test fixture contract, currently violated for `like` vs `favorite`. | `tests/frontend/tests/integration/helpers/mock-schemas.js:1-4`, `tests/frontend/tests/integration/helpers/mock-schemas.js:127-150`, `tests/frontend/tests/integration/schema-bootstrap.test.js:74-80` |

## Naming Analysis

| Name | Finding | Evidence |
|---|---|---|
| `favorite` vs `like` | Product schema fixture and docs use `favorite`; the failing schema-bootstrap test expects `like`, so the test name is stale relative to its own fixture. | `tests/frontend/tests/integration/helpers/mock-schemas.js:140-149`, `tests/frontend/tests/integration/schema-bootstrap.test.js:74-80`, `docs/CORE.md:80-87` |
| `row` display mode | Implementation uses `row` as a first-class `Component.SIZES`/alias member, but cross-cutting docs still define only `xs` through `xl`. | `Component.js:25-34`, `ListElement.js:20-28`, `docs/frontend/COMPONENTS.md:85-123`, `packages/n3tx-ui/docs/components.md:176-184` |
| `profile-note` vs `placeholder` | Current profile DOM uses semantic component-specific copy class `.profile-note`; the test expects generic `.placeholder`. | `ntx-profile.js:43-57`, `tests/frontend/tests/components/ntx-profile.test.js:154-162` |
| `NTTRefPicker.styles` | `styles` is a `Component` getter contract, while `NTTRefPicker` is standalone and uses `STYLES_URL`; tests conflate the two style-loading patterns. | `Component.js:258-302`, `ntx-ref-picker.js:28-30`, `ntx-ref-picker.js:85-92`, `packages/n3tx-ui/docs/components.md:65-65` |
| `__NTT_E2E_MARKER` vs `__NTX_VEILLE_E2E_MARKER` | Core/grants/perf use `NTT` marker naming while Veille uses `NTX`, creating parallel marker conventions that are public to the harness. | `tests/frontend/tests/e2e/playwright.config.js:16-20`, `tests/frontend/tests/e2e/grants-global-setup.js:21-23`, `tests/frontend/tests/e2e/veille.playwright.config.js:16-20`, `tests/frontend/tests/e2e/perf-global-setup.js:25-28` |

## Lifecycle And Ordering

| Surface | Contract | Evidence |
|---|---|---|
| Component connect order | `connectedCallback()` applies forced display, starts ResizeObserver, then calls `prerender()`. | `Component.js:436-446`, `docs/frontend/COMPONENTS.md:180-188` |
| Component schema order | `model` attribute change calls `attach()`, sends `ATTACH` to `NTT`, and `define()` later calls `definedCallback()`. | `Component.js:127-139`, `Component.js:183-189`, `docs/frontend/COMPONENTS.md:162-171` |
| NTT schema order | `NTT.SCHEMA()` registers `$defs` first, creates/reuses the main DynamicClass, replays waiting messages, and consumes preloaded data without firing a network read. | `NTT.js:302-342` |
| List read order | `ListElement.definedCallback()` subscribes to class-level `UPDATE`, skips duplicate reads, and triggers paginated `READ` with populate depth. | `ListElement.js:49-67` |
| Ref picker order | `_showPicker()` closes current state, sets picker mode, reads existing DC instances, optionally triggers `READ`, renders dropdown, then registers outside click listener after a timeout. | `ntx-ref-picker.js:104-173` |
| Inline create order | `_showInlineCreate()` closes current state, sets create mode, gets child schema, renders Formidable edit form, binds cancel/submit/keyboard handlers. | `ntx-ref-picker.js:175-217` |
| Row save order | In edit mode, `NTTRow.toggleMode()` collects inputs, validates, shows row errors and returns on failure, otherwise calls `save()`, toggles mode, and renders. | `ntx-row.js:129-146` |
| Profile order | `connectedCallback()` awaits `permissions.init()` before rendering user or not-authenticated state. | `ntx-profile.js:17-24` |

## Documentation Gaps

| Gap | Impact | Evidence |
|---|---|---|
| `row` display mode is inconsistently documented. | Tests and implementation disagree over whether `row` is public `Component.SIZES` or a table-only extension. | `Component.js:25-34`, `ListElement.js:20-28`, `docs/frontend/COMPONENTS.md:85-123`, `packages/n3tx-ui/docs/components.md:176-184` |
| Standalone component style contract is not separated from `Component.styles`. | Tests assert `NTTRefPicker.styles` even though the component is standalone and links CSS directly. | `Component.js:258-302`, `ntx-ref-picker.js:28-30`, `ntx-ref-picker.js:85-92`, `packages/n3tx-ui/docs/components.md:65-65` |
| Profile DOM selector contract is undocumented. | Tests target `.placeholder`, while implementation uses `.profile-note`; docs only describe registration/import and identity display. | `ntx-profile.js:43-57`, `tests/frontend/tests/components/ntx-profile.test.js:154-162`, `FRONTEND.md:73-79` |
| Component catalog does not explicitly deprecate or exclude `ntx-favorites` and `ntx-logs`. | Missing-file test failures are hard to classify without a documented removed/deprecated component list. | `tests/frontend/tests/components/ntx-favorites.test.js:27-70`, `tests/frontend/tests/components/ntx-logs.test.js:34-190`, `FRONTEND.md:57-75`, `packages/n3tx-ui/docs/components.md:65-71` |
| Mock schema fixture drift is not documented as a contract hazard. | `schema-bootstrap` fails because the test expects a method not present in its own fixture. | `tests/frontend/tests/integration/helpers/mock-schemas.js:1-4`, `tests/frontend/tests/integration/helpers/mock-schemas.js:127-150`, `tests/frontend/tests/integration/schema-bootstrap.test.js:74-80` |
| Playwright marker/env naming differs by suite. | Core and Veille marker env names are not uniform, and perf uses legacy-looking paths; the runner treats them as separate public harness contracts. | `tests/frontend/tests/e2e/playwright.config.js:16-20`, `tests/frontend/tests/e2e/veille.playwright.config.js:16-20`, `tests/frontend/tests/e2e/playwright.perf.config.js:6-10`, `tests/frontend/tests/e2e/perf-global-setup.js:12-35` |

## Top Classifications

| Classification | Failures |
|---|---|
| Stale contract | `ntx-favorites`, `ntx-logs`, `ntx-profile .placeholder`, `ntx-ref-picker` inline/static styles, `schema-bootstrap` `like()` expectation. |
| Current intended contract | `ntx-row` valid inline edit should call `save()`. |
| Unresolved | `Component.SIZES` and `display-mode-cascade` row-size inclusion because implementation/package docs and cross-cutting docs disagree. |
| Infrastructure contract | No listed reproduced failure was purely runner/setup-caused, but the harness exposes important infrastructure contracts around Vitest aliases/cleanup and Playwright DB markers/env. |

## Recommended Contract Decisions Before Fixes

1. Decide whether `row` is part of public `Component.SIZES`/`ALIASES` or an internal/table-only mode; then align `docs/frontend/COMPONENTS.md`, `packages/n3tx-ui/docs/components.md`, and tests.
2. Treat standalone component CSS as linked external CSS unless a static source-level CSS string is explicitly documented as public.
3. Update schema-bootstrap fixtures/tests so method assertions come from the fixture schema keys, not legacy Product method names.
4. Keep the row validation/save test as a live contract unless deeper inspection proves the failure is test setup or mock leakage.
5. Either remove/deprecate stale component tests for missing `ntx-favorites` and `ntx-logs`, or document and implement those components as intentional public surfaces.
