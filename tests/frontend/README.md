# Frontend test harness

This directory owns JavaScript unit/integration tests and Playwright browser
checks. For application development use [Getting started](../../docs/GETTING_STARTED.md)
and the [frontend guide](../../docs/frontend/ARCHITECTURE.md), not test fixtures.

## Prerequisites and commands

Run commands below from `tests/frontend/` in the N3TX checkout. Install the
declared Node dependencies in your development environment before running tests;
the scripts expect local `vitest` and `@playwright/test`. Browser suites also need
Playwright Chromium/system libraries and an environment with the example app's
Python dependencies. Do not install packages into another contributor's shared
Python environment without coordination.

| Command | Scope |
|---|---|
| `npm test` | Vitest unit and mocked integration suites |
| `npm run test:watch` | Vitest watch mode |
| `npm run test:integration` | Mocked integration tests only |
| `npm run test:coverage` | Coverage; may require the matching Vitest coverage provider |
| `npm run test:e2e` | Default: worker-isolated parallel core lane |
| `npm run test:e2e:parallel` | Explicit parallel core lane |
| `npm run test:e2e:serial` | Legacy one-worker shared core server |
| `npm run test:e2e:fast` | Parallel read-only/default UI smoke selection |
| `npm run test:e2e:veille` | Veille app-specific browser lane |
| `npm run test:all` | Unit tests, then parallel core browser suite |

Focused checks:

```bash
npm test -- tests/integration/schema-bootstrap.test.js
npm test -- tests/components/ntx-item.test.js tests/generators/form.test.js
npm test -- tests/utils/theme.test.js tests/components/ntx-theme-button.test.js
npm run test:e2e:serial -- tests/e2e/route-grammar-smoke.spec.js
```

From the **repository root**, `python3 scripts/test-frontend.py --help` describes
the aggregate runner. It can run unit, core, Grants, Veille and performance lanes;
those are distinct environments, not interchangeable coverage.

## Unit/integration architecture

```text
tests/*.test.js -> Vitest aliases -> package static source trees
                         |
                     jsdom + setup mocks
```

[`vitest.config.js`](vitest.config.js) aliases the combined static namespace to
core/UI/agent source trees. Tests import paths like `../../core/NTT.js`; these
are test aliases, not directories to copy into an application.

[`tests/setup.js`](tests/setup.js) supplies mocked fetch, localStorage, WebSocket,
ResizeObserver and cleanup. Integration tests here generally exercise runtime
composition **with mocked networking**, not a running backend. Setup catches
leaked unhandled rejections and raises them after the test; stale comments saying
they are ignored should not be treated as behavior.

| Test area | Best use |
|---|---|
| `tests/core/` | Actor routing, NTT identity, Router grammar, Component primitives |
| `tests/components/` | Registered-element DOM, method input, edit/display behavior |
| `tests/generators/` | Schema normalization, field rendering, form reading/validation |
| `tests/widgets/` | Widget selection and serialized output |
| `tests/transport/` | HTTP/Socket/adapter behavior under mocks |
| `tests/integration/` | Schema/entity/component interactions and message flows |
| `tests/utils/` | Permissions presentation, themes and helpers |

Use actual custom-element instances when methods touch private fields. Flush the
relevant microtasks/animation frames using existing integration helpers. Reset
singleton/module state carefully; also remove DOM nodes and unsubscribe listeners.
Do not convert a backend policy test into a mocked `canAction() => true` assertion.

## Browser isolation

```text
parallel config -> fixture worker 0 -> seeded temp DB + server :5100
                -> fixture worker 1 -> seeded temp DB + server :5101
serial config   -> launcher -> seeded temp DB + server :5000
```

- [`fixtures/parallel.js`](tests/e2e/fixtures/parallel.js) starts one core app per
  worker using `parallelIndex`; each gets its own temp SQLite DB and port.
  It stops the child and removes the temp directory on teardown.
- Specs supporting this lane import `test`/`expect` from that fixture. Importing
  plain Playwright `test` bypasses the worker-server fixture.
- Parallel workers default to 2. Set `N3TX_E2E_PARALLEL_WORKERS` and
  `N3TX_E2E_PARALLEL_BASE_PORT` to tune concurrency/ports.
- Serial and fast lanes use [`start-e2e-app.js`](tests/e2e/start-e2e-app.js).
  Seeding happens in the server command, not globalSetup, because Playwright can
  start its web server first. Marker/PID files support global teardown.
- `N3TX_E2E_REUSE_SERVER=1` permits reuse in the shared lane. Avoid it for mutation
  verification unless you deliberately accept the existing server/data state.
- Grants, Veille and performance use app-specific configs. Veille's launcher
  sets `N3TX_CHAT_LLM=test`; browser tests must not make paid provider calls.

[`paths.js`](tests/e2e/paths.js) derives the repository root from its own location.
Only unusual wrapped/symlinked layouts need `N3TX_REPO_ROOT`. Python selection is:
active `$VIRTUAL_ENV/bin/python`, repo `.venv-e2e/bin/python`, repo `.venv/bin/python`,
then `python3`. Existence is checked, not dependency completeness. The launcher
injects source-tree `PYTHONPATH`; that does not install Python dependencies.

## Readiness, artifacts and limits

Use [`fixtures/ui.js`](tests/e2e/fixtures/ui.js) helpers such as `gotoApp`,
`reloadApp`, `waitForTopbar`, `waitForProductList` and `waitForRouterItem`.
Wait for the specific Shadow DOM/stream state rather than fixed sleeps or generic
`networkidle`. Keep browser coverage for auth/session, history, real networking,
computed CSS, viewport layout and database mutations. Static DOM structure usually
belongs in Vitest.

Playwright retains failure screenshots/video and retry traces according to its
config; default test artifacts may appear under `test-results/`. Vitest may write
cache/coverage files. Aggregate runner reporting and performance traces have
additional output paths—inspect `--help` and configs before a restricted-scope
run. Never point the harness at live application storage.

Report the exact command and result. A dependency error is **not** a failing
application test; a listed test is **not** an executed test. Unit green does not
prove mobile layout, backend enforcement, SSE chunk-boundary correctness, or
HTTP/WebSocket parity.
