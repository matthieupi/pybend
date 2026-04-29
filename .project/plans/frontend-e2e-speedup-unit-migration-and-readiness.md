# Frontend E2E Speedup Plan: Unit Migration + Readiness Helpers

## Recommendation

Implement only speedup items **2** and **3**:

- **2 — Move unit-ish Playwright specs into Vitest/jsdom** where browser/backend fidelity is not required.
- **3 — Replace fixed sleeps and weak waits with deterministic readiness helpers**.

Do not change worker tuning or broad batching in this pass.

## Current State

The frontend has two test layers:

```text
Vitest/jsdom
  tests/frontend/tests/**/*.test.js
  Fast component/runtime tests

Playwright/E2E
  tests/frontend/tests/e2e/*.spec.js
  Real browser + backend + seeded SQLite
```

Several files named `*-unit.spec.js` still run through full Playwright:

```text
ntx-logs-unit.spec.js
ntx-topbar-unit.spec.js
ntx-method-unit.spec.js
ntx-list-unit.spec.js
ntx-item-unit.spec.js
form-rendering-unit.spec.js
ntx-router-unit.spec.js
```

These are the best migration candidates.

## Target State

```text
Unit-ish DOM/component contracts
  -> Vitest/jsdom

Browser fidelity contracts
  -> Playwright

Slow fixed sleeps/networkidle
  -> Specific readiness helpers
```

This preserves integrity by keeping real-browser coverage for layout, focus, auth, routing, screenshots, and backend mutation flows.

## Implementation Slices

### Slice 1 — Classify Playwright unit-ish specs

For each `*-unit.spec.js`, split tests into Vitest-safe checks and browser-required checks.

| Spec | Move to Vitest | Keep in Playwright |
|---|---|---|
| `ntx-logs-unit.spec.js` | rendering/filter state with mocked log data | browser integration with real app logs |
| `ntx-topbar-unit.spec.js` | anonymous/auth DOM structure, dropdown rendering | login/logout flows, corrupted JWT |
| `ntx-method-unit.spec.js` | method button rendering/schema params | real POST/mutation method calls |
| `ntx-list-unit.spec.js` | list DOM structure, empty/loading states | responsive grid layout |
| `ntx-item-unit.spec.js` | field/method rendering, hidden fields | edit mode with real browser focus |
| `form-rendering-unit.spec.js` | field order/groups/widgets | real validation/browser form behavior |
| `ntx-router-unit.spec.js` | route resolution/component selection | browser history/hash navigation |

### Slice 2 — Add Vitest equivalents for low-risk tests

Use existing Vitest setup:

```js
// tests/frontend/tests/components/ntx-topbar.test.js
import { describe, it, expect } from 'vitest';
import '../../src-path-or-alias/components/ntx-topbar.js';

describe('ntx-topbar', () => {
  it('renders anonymous signin link', async () => {
    const el = document.createElement('ntx-topbar');
    document.body.appendChild(el);

    await Promise.resolve();

    const signin = el.shadowRoot.querySelector('.signin-link');
    expect(signin).toBeTruthy();
  });
});
```

Recommended migration order:

1. `ntx-logs-unit.spec.js`
2. `ntx-topbar-unit.spec.js`
3. Non-network portions of `ntx-method-unit.spec.js`
4. Schema/form static rendering portions of `form-rendering-unit.spec.js`

### Slice 3 — Remove migrated checks from E2E

After Vitest coverage exists, either delete migrated Playwright tests or leave only thin browser smoke tests.

Example Playwright smoke shape:

```js
test('topbar renders in real app shell', async ({ page }) => {
  await gotoApp(page, '/');
  await waitForTopbar(page);
});
```

Do not remove browser coverage for:

- real auth
- router history/back behavior
- viewport/responsive behavior
- CSS computed styles
- screenshots
- DB/API mutation flows

### Slice 4 — Replace fixed sleeps with readiness helpers

Add targeted helpers in:

```text
tests/frontend/tests/e2e/fixtures/ui.js
```

Recommended helper shapes:

```js
export async function waitForChatTurnComplete(page) {
  await page.waitForFunction(() => {
    const detail = document.querySelector('#agent-detail');
    const chat = detail?.shadowRoot?.querySelector('ntx-chat');
    const root = chat?.shadowRoot;
    return !!root?.querySelector('.stream-footer, .assistant-message')
      && !root?.querySelector('button[disabled]');
  });
}
```

```js
export async function waitForRequestQuiet(page, matcher, quietMs = 300) {
  let lastSeen = Date.now();

  page.on('request', (request) => {
    if (matcher(request)) lastSeen = Date.now();
  });

  await page.waitForFunction(
    ({ lastSeen, quietMs }) => Date.now() - lastSeen >= quietMs,
    { lastSeen, quietMs }
  );
}
```

Primary replacements:

| File | Replace |
|---|---|
| `veille-chat*.spec.js` | `setTimeout(..., 2500)` with chat completion helper |
| `grants-create-validation.spec.js` | long “no request” waits with shorter request-quiet helper |
| `flow-navigation-deep.spec.js` | `waitForTimeout(50)` with `waitForUiSettled()` or route-specific wait |
| `performance.spec.js` | keep `networkidle` only if metric intentionally measures it |

## Verification

Run in this order:

```bash
cd /workspace/tests/frontend
npx vitest run
npm run test:e2e:parallel
```

Then targeted checks:

```bash
npx playwright test --config=tests/e2e/playwright.parallel.config.js tests/e2e/ntx-topbar-unit.spec.js
npx playwright test --config=tests/e2e/playwright.parallel.config.js tests/e2e/veille-chat.spec.js
```

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| jsdom misses browser layout/focus bugs | keep browser smoke tests |
| migrated tests lose backend confidence | only migrate mocked/static DOM assertions |
| readiness helper races | wait on observable DOM/network completion, not arbitrary time |
| negative assertions still need time window | use short quiet-window helper, not zero wait |

## Critical Files for Implementation

- `tests/frontend/tests/e2e/fixtures/ui.js`
- `tests/frontend/tests/e2e/veille-chat.spec.js`
- `tests/frontend/tests/e2e/grants-create-validation.spec.js`
- `tests/frontend/tests/e2e/ntx-topbar-unit.spec.js`
- `tests/frontend/tests/components/ntx-topbar.test.js`
