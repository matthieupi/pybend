# Styling

> Part of [n3tx-ui](../README.md)

## Theme File Split

The shared frontend theme contract now has two layers:

- `packages/n3tx-ui/src/n3tx_ui/static/theme-base.css` owns global selectors and shared structure.
- `packages/n3tx-ui/src/n3tx_ui/static/dark-theme.css` and `packages/n3tx-ui/src/n3tx_ui/static/light-theme.css` own theme-specific token values.

`theme-base.css` is responsible for:

- global element defaults (`html`, `body`, headings, links, form controls)
- page chrome layout (`body > .page`, sidebar offset behavior)
- shared atmosphere selectors (`body::before`, `body::after`, selection, scrollbars)
- consuming the canonical `--ntx-*` token contract

Theme entrypoints are responsible for:

- defining canonical `--ntx-*` tokens for typography, scale, color, motion, shadows, and shared recipes
- setting theme-specific values for page atmosphere, shell surfaces, buttons, and inputs
- exposing the canonical public contract only

## Page Stylesheet Contract

Theme entrypoints are now token-only files. Pages must link `theme-base.css` explicitly alongside the theme files:

```html
<link rel="stylesheet" href="./theme-base.css" />
<link rel="stylesheet" href="./dark-theme.css" />
<link rel="stylesheet" href="./light-theme.css" />
```

Pages may also add app-level token entrypoints after the shared themes. Veille's
`apps/veille/static/industrial-theme.css` is the canonical example: it defines
only `--ntx-*` tokens and participates in runtime cycling by adding
`'industrial'` to `window.NTX_THEME_CONFIG.themes`.

Legacy aliases such as `--surface-*`, `--text-*`, `--accent`, and `--border` are no longer part of the first-party contract.

## Page Theme Contract

Pages provide the available theme order inline and load the runtime helper from `./utils/theme.js`:

```html
<link rel="stylesheet" href="./theme-base.css" />
<link rel="stylesheet" href="./dark-theme.css" />
<link rel="stylesheet" href="./light-theme.css" />
<script>
  window.NTX_THEME_CONFIG = { themes: ['dark', 'light'] };
</script>
<script type="module" src="./utils/theme.js"></script>
```

`toggleTheme()` no longer hardcodes dark/light branching. It cycles through the configured `themes` array in order, while `getTheme()` still resolves the persisted theme or the page's fallback theme.

`setTheme(theme)` updates both `localStorage['ntx-theme']` and `document.documentElement.dataset.theme`, then dispatches `theme-change` so multiple switchers stay synchronized.

## Token Guidance

- Prefer canonical `--ntx-*` tokens in new framework and app CSS.
- Do not reference legacy variable names in first-party CSS or tests.
- Keep theme values in the theme entrypoints; do not add palette literals back into shared structural stylesheets.

## Framework Surface Migration

The primary framework CSS surfaces now consume canonical tokens directly:

- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-table.css`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css`
- `packages/n3tx-ui/src/n3tx_ui/static/auth.css`

These files should reference canonical `--ntx-*` tokens for layout, surfaces, typography, borders, interactions, and status styling. Repeated state treatments such as success, warning, error, and accent badges should prefer the `--ntx-status-*` family.

Current first-party chrome also prefers borderless outer shells for primary surfaces:

- topbar icon controls and the authenticated user menu rely on fill + shadow rather than visible strokes
- table containers keep their internal row/header dividers but drop the outer table border
- `ntx-item` detail shells (`md`/`lg`/`xl`) rely on background, spacing, and shadow instead of card borders

Veille and the shipped example surfaces now follow the same contract as well:

- `apps/veille/static/veille.css`
- `apps/veille/static/components/ntx-run-output.css`
- `apps/veille/static/components/ntx-run-report.css`
- `examples/**/static/*.css`
- `examples/**/static/*.html`
- `packages/n3tx-ui/src/n3tx_ui/static/example.html`
- `packages/n3tx-ui/src/n3tx_ui/static/example.css`

When examples need special semantics, prefer app/example-level composition on top of canonical tokens rather than reintroducing `--surface-*`, `--text-*`, `--accent`, or `--glass-*` dependencies.

## Verification

Recommended verification commands:

```bash
cd /workspace/tests/frontend && npx vitest run
cd /workspace/tests/frontend && npm run test:e2e:fast
cd /workspace/tests/frontend && npm run test:e2e:parallel
cd /workspace && python3 scripts/test-frontend.py
cd /workspace && python3 scripts/test-frontend.py --suite e2e-core
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js tests/e2e/theme-toggle.spec.js
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js tests/e2e/css-and-theming-unit.spec.js tests/e2e/page-load.spec.js
```

### Playwright Environment

- The browser harness runs against `examples/core`.
- `tests/frontend/tests/e2e/start-e2e-app.js` creates and seeds a temp SQLite database inside the Playwright `webServer.command` before the server starts. This avoids relying on `globalSetup` ordering for the DB marker handoff.
- `tests/frontend/tests/e2e/global-teardown.js` removes that temp DB after the run.
- In this workspace, Python web dependencies for the Playwright server are installed in `/workspace/.venv-e2e`; `start-e2e-app.js` auto-detects and uses it.
- Prefer the shared readiness helpers in `tests/frontend/tests/e2e/fixtures/ui.js`
  (`gotoApp`, `waitForTopbar`, `waitForProductList`, etc.) instead of
  `networkidle` plus fixed sleeps. This keeps UI tests tied to actual component
  state and avoids adding seconds of guaranteed delay per assertion.
- Use `tests/e2e/playwright.fast.config.js` / `npm run test:e2e:fast` for the
  parallel read-only smoke lane. The full `playwright.config.js` suite remains
  serial because mutation-heavy specs currently share one backend and database.
- Use `tests/e2e/playwright.parallel.config.js` / `npm run test:e2e:parallel`
  for the fully parallel core lane. Its `fixtures/parallel.js` worker fixture
  starts isolated `examples/core` servers on separate ports with separate temp
  SQLite DBs. App-specific Grants, Veille, and performance specs still use their
  dedicated configs.
- `scripts/test-frontend.py` is the aggregate runner. It executes selected
  suites concurrently with 2 suite workers by default (`--workers N` or
  `N3TX_FRONTEND_SUITE_WORKERS`) while `e2e-core` uses the worker-isolated
  Playwright parallel config internally.
