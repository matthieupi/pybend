# Plan 3 — Semantic E2E Page Objects, Option B

## Purpose

Implement **Option B: Page objects with semantic component queries** for frontend Playwright tests.

This corresponds to candidate #3 from `.project/plans/frontend-test-architecture-deepening-candidates.md`: **Semantic E2E API/session/page-object layer**.

The goal is to deepen the browser-test boundary so specs express user and framework contracts instead of repeatedly traversing Shadow DOM, hand-editing `localStorage`, and embedding component-specific selectors.

This is a **test architecture refactor**. It should not change production behavior or the intended E2E assertions.

---

## Chosen Design: Option B — Page Objects with Semantic Component Queries

Use small, composable page objects for repeated app surfaces:

```js
const app = createAppPage(page);

await app.gotoHome();
await app.session.loginAs('alice');
await app.topbar.expectAuthenticated();

await app.products.expectReady();
await app.products.openFirst();
await app.router.expectRoute(/^#Product/);
await app.router.back();
await app.router.expectHome();
```

For app-specific surfaces such as Veille:

```js
const veille = createVeillePage(page);

await veille.loginAndOpenAssistant();
const firstTurn = await veille.chat.sendTurn('Hello assistant');

expect(firstTurn.sendEnabled).toBe(true);
expect(firstTurn.messages).toContainText('Hello assistant');
```

Why Option B fits this target:

- The biggest current friction is not raw API setup alone; it is repeated nested Shadow DOM traversal and UI readiness logic.
- Page objects centralize selectors while keeping specs readable.
- The model matches the test domain: topbar, router, product list/detail, and Veille chat are stable semantic surfaces.
- It can be introduced incrementally without rewriting every E2E helper at once.

---

## Problem Statement

Current Playwright specs often encode implementation details directly.

### Auth/topbar example

`authentication.spec.js` manually clears the token, reloads, waits for the topbar, and traverses Shadow DOM:

```js
await gotoApp(page, APP_URL);
await page.evaluate(() => window.localStorage.removeItem('jwtToken'));
await reloadApp(page);
await waitForAnonymousTopbar(page);

const hasSignIn = await page.locator('ntx-topbar').evaluate((el) => {
  return !!el.shadowRoot?.querySelector('.signin-link');
});
expect(hasSignIn).toBe(true);
```

The test intent is simply:

```js
await app.session.logout();
await app.topbar.expectAnonymous();
```

### Product list example

`product-list.spec.js` directly knows the list's Shadow DOM structure:

```js
const names = await page.locator('#product-list').evaluate((list) => {
  const items = list.shadowRoot?.querySelectorAll('ntx-item');
  return Array.from(items).map(item => {
    const nameEl = item.shadowRoot?.querySelector('[data-value="name"], h2, .item-title');
    return nameEl?.textContent || '';
  }).filter(Boolean);
});
```

The intended contract is:

```js
const names = await app.products.names();
expect(names).toHaveLengthGreaterThanOrEqual(3);
```

### Router/detail example

`product-detail.spec.js` manually clicks through nested Shadow DOM and checks hash state:

```js
await page.locator('#product-list').evaluate((list) => {
  const firstItem = list.shadowRoot?.querySelector('ntx-item');
  firstItem?.shadowRoot?.querySelector('.card')?.click();
});

await page.waitForFunction(() => window.location.hash.includes('Product'));
expect(page.url()).toContain('#Product');
```

The intended contract is:

```js
await app.products.openFirst();
await app.router.expectModel('Product');
```

### Veille chat example

`fixtures/ui.js` currently mixes generic UI readiness with app-specific chat interactions:

```js
export async function sendVeilleChatTurn(page, text) {
  const before = await getVeilleChatState(page);

  await page.locator('#agent-detail').evaluate((el, message) => {
    const chat = el.shadowRoot?.querySelector('ntx-chat');
    const textarea = chat?.shadowRoot?.querySelector('textarea');
    const send = chat?.shadowRoot?.querySelector('.send-btn');
    textarea.value = message;
    textarea.dispatchEvent(new Event('input', { bubbles: true, composed: true }));
    send.click();
  }, text);

  await page.waitForFunction(({ messageCount, footerCount }) => {
    const detail = document.querySelector('#agent-detail');
    const chat = detail?.shadowRoot?.querySelector('ntx-chat');
    const root = chat?.shadowRoot;
    return !!root?.querySelector('.send-btn')
      && root.querySelectorAll('.msg').length >= messageCount + 2
      && root.querySelectorAll('.stream-footer').length >= footerCount + 1;
  }, before);
}
```

This belongs in a Veille-specific page object, not the generic UI fixture.

---

## Target Architecture

```text
Playwright spec
      |
      v
+-----------------------+
| createAppPage(page)   |
+-----------+-----------+
            |
            +-- session  -> login/logout/token persistence
            +-- topbar   -> anonymous/authenticated/dropdown contracts
            +-- router   -> route/hash/content/back contracts
            +-- products -> list/card/detail contracts
            +-- page     -> goto/reload/settle convenience

Veille specs
      |
      v
+-------------------------+
| createVeillePage(page)  |
+-------------+-----------+
              |
              +-- dashboard -> featured agent cards
              +-- assistant -> open Assistant detail
              +-- chat      -> send turn/read stream state
```

The page objects should centralize selector knowledge, but they should not become a generic selector framework. Each method should represent a stable user-facing or schema-facing contract.

---

## Proposed File Layout

```text
tests/frontend/tests/e2e/
├── fixtures/
│   ├── auth.js                 # keep seed users + low-level token helper during migration
│   ├── ui.js                   # keep low-level readiness wrappers temporarily
│   └── parallel.js             # unchanged test fixture export
├── pages/
│   ├── app-page.js             # createAppPage(page)
│   ├── session.js              # SessionPage / auth state helper
│   ├── topbar.js               # TopbarPage
│   ├── router.js               # RouterPage
│   ├── product-list.js         # ProductListPage
│   ├── product-detail.js       # ProductDetailPage or product detail methods
│   ├── shadow.js               # small Shadow DOM locator/evaluate helpers
│   └── veille-page.js          # createVeillePage(page), Veille-specific surfaces
└── authentication.spec.js      # first migrated spec target
```

Keep this under `tests/e2e/pages/` rather than `fixtures/` because these objects model app surfaces, not Playwright fixture lifecycle.

---

## Public Interface Sketch

### `createAppPage(page)`

```ts
type AppPage = {
  page: Page;
  session: SessionPage;
  topbar: TopbarPage;
  router: RouterPage;
  products: ProductListPage;

  goto(path?: string): Promise<void>;
  gotoHome(): Promise<void>;
  reload(): Promise<void>;
  waitReady(): Promise<void>;
  settle(): Promise<void>;
};
```

Usage:

```js
const app = createAppPage(page);

await app.gotoHome();
await app.waitReady();
await app.products.expectReady();
```

### `SessionPage`

```ts
type SessionPage = {
  loginAs(userName: 'alice' | 'bob' | 'charlie'): Promise<void>;
  logout(): Promise<void>;
  setToken(token: string): Promise<void>;
  clearToken(): Promise<void>;
  token(): Promise<string | null>;
  expectPersisted(): Promise<void>;
};
```

Implementation should initially delegate to existing `fixtures/auth.js` helpers where possible, then own reload/topbar expectations through `AppPage` composition:

```js
async loginAs(userName) {
  const token = await getToken(this.page.request, USERS[userName].email, USERS[userName].password);
  await this.setToken(token);
  await this.app.reload();
  await this.app.topbar.expectAuthenticated();
}
```

### `TopbarPage`

```ts
type TopbarPage = {
  locator(): Locator;
  waitReady(): Promise<void>;
  state(): Promise<TopbarState>;
  expectAnonymous(): Promise<void>;
  expectAuthenticated(): Promise<void>;
  expectUserNameVisible(): Promise<void>;
  dropdownState(): Promise<TopbarDropdownState>;
  expectNoFavoritesLink(): Promise<void>;
};
```

State shape:

```ts
type TopbarState = {
  hasShell: boolean;
  hasSignIn: boolean;
  hasUserPill: boolean;
  userName: string;
};
```

Implementation can centralize the Shadow DOM selector:

```js
async state() {
  await this.waitReady();
  return this.locator().evaluate((el) => ({
    hasShell: !!el.shadowRoot?.querySelector('.topbar'),
    hasSignIn: !!el.shadowRoot?.querySelector('.signin-link'),
    hasUserPill: !!el.shadowRoot?.querySelector('.user-pill'),
    userName: el.shadowRoot?.querySelector('.user-name')?.textContent || '',
  }));
}
```

### `RouterPage`

```ts
type RouterPage = {
  locator(): Locator;
  waitContent(): Promise<void>;
  waitItem(): Promise<void>;
  hash(): Promise<string>;
  expectRoute(expected: string | RegExp): Promise<void>;
  expectModel(model: string): Promise<void>;
  expectHome(): Promise<void>;
  title(): Promise<string>;
  back(): Promise<void>;
  expectBackHiddenAtRoot(): Promise<void>;
};
```

### `ProductListPage`

```ts
type ProductListPage = {
  locator(): Locator;
  waitReady(): Promise<void>;
  itemCount(): Promise<number>;
  names(): Promise<string[]>;
  firstText(): Promise<string>;
  expectReady(): Promise<void>;
  expectNamesVisible(min?: number): Promise<void>;
  openFirst(): Promise<void>;
};
```

### `VeillePage`

```ts
type VeillePage = {
  page: Page;
  dashboard: VeilleDashboardPage;
  assistant: VeilleAssistantPage;
  chat: VeilleChatPage;

  login(): Promise<void>;
  loginAndOpenAssistant(): Promise<void>;
  waitReady(): Promise<void>;
};
```

Chat surface:

```ts
type VeilleChatPage = {
  state(): Promise<VeilleChatState>;
  type(text: string): Promise<VeilleChatState>;
  sendTurn(text: string): Promise<VeilleChatState>;
  expectUsable(): Promise<void>;
};
```

---

## Shadow DOM Helper Boundary

Add a small helper for repeated shadow traversal, but keep it intentionally small.

```js
export async function shadowState(locator, fn) {
  return locator.evaluate((el, source) => {
    const root = el.shadowRoot;
    const helper = {
      text: (selector) => root?.querySelector(selector)?.textContent || '',
      has: (selector) => !!root?.querySelector(selector),
      count: (selector) => root?.querySelectorAll(selector).length || 0,
    };
    return Function('root', 'h', `return (${source})(root, h);`)(root, helper);
  }, String(fn));
}
```

However, prefer direct `locator.evaluate()` inside page objects if the helper becomes too clever. The important boundary is the page object method, not a generalized Shadow DOM DSL.

---

## Implementation Steps

### Step 1 — Add page-object skeleton

Create:

- `tests/frontend/tests/e2e/pages/app-page.js`
- `tests/frontend/tests/e2e/pages/session.js`
- `tests/frontend/tests/e2e/pages/topbar.js`
- `tests/frontend/tests/e2e/pages/router.js`
- `tests/frontend/tests/e2e/pages/product-list.js`
- `tests/frontend/tests/e2e/pages/veille-page.js`

Initial `app-page.js`:

```js
import { gotoApp, reloadApp, waitForAppReady, waitForUiSettled } from '../fixtures/ui.js';
import { createSessionPage } from './session.js';
import { createTopbarPage } from './topbar.js';
import { createRouterPage } from './router.js';
import { createProductListPage } from './product-list.js';

export function createAppPage(page) {
  const app = {
    page,
    async goto(path = '/') { await gotoApp(page, path); },
    async gotoHome() { await gotoApp(page, '/'); },
    async reload() { await reloadApp(page); },
    async waitReady() { await waitForAppReady(page); },
    async settle() { await waitForUiSettled(page); },
  };

  app.topbar = createTopbarPage(page, app);
  app.router = createRouterPage(page, app);
  app.products = createProductListPage(page, app);
  app.session = createSessionPage(page, app);
  return app;
}
```

This deliberately wraps existing helpers first to avoid big-bang behavior changes.

### Step 2 — Implement `TopbarPage`

Move topbar-specific Shadow DOM knowledge out of specs:

```js
export function createTopbarPage(page) {
  return {
    locator: () => page.locator('ntx-topbar'),

    async waitReady() {
      await expect(page.locator('ntx-topbar')).toBeVisible();
      await page.waitForFunction(() => {
        const topbar = document.querySelector('ntx-topbar');
        return !!topbar?.shadowRoot?.querySelector('.topbar');
      });
    },

    async state() {
      await this.waitReady();
      return this.locator().evaluate((el) => ({
        hasSignIn: !!el.shadowRoot?.querySelector('.signin-link'),
        hasUserPill: !!el.shadowRoot?.querySelector('.user-pill'),
        userName: el.shadowRoot?.querySelector('.user-name')?.textContent || '',
      }));
    },

    async expectAuthenticated() {
      await expect.poll(async () => (await this.state()).hasUserPill).toBe(true);
    },
  };
}
```

Replace repeated spec snippets with this page object in one file first.

### Step 3 — Implement `SessionPage`

Initial version delegates to existing `fixtures/auth.js` token helpers:

```js
import { USERS, getToken } from '../fixtures/auth.js';

export function createSessionPage(page, app) {
  return {
    async setToken(token) {
      await page.evaluate((t) => window.localStorage.setItem('jwtToken', t), token);
    },

    async clearToken() {
      await page.evaluate(() => window.localStorage.removeItem('jwtToken'));
    },

    async loginAs(name) {
      const user = USERS[name];
      const token = await getToken(page.request, user.email, user.password);
      await this.setToken(token);
      await app.reload();
      await app.topbar.expectAuthenticated();
    },

    async logout() {
      await this.clearToken();
      await app.reload();
      await app.topbar.expectAnonymous();
    },
  };
}
```

This prevents direct `localStorage` manipulation from continuing to spread.

### Step 4 — Migrate `authentication.spec.js`

Use this as the first migration target because it exercises session + topbar but has limited product-list/router coupling.

Before:

```js
await gotoApp(page, APP_URL);
await loginAs(page, 'alice');

const hasPill = await page.locator('ntx-topbar').evaluate((el) => {
  return !!el.shadowRoot?.querySelector('.user-pill');
});
expect(hasPill).toBe(true);
```

After:

```js
const app = createAppPage(page);

await app.gotoHome();
await app.session.loginAs('alice');
await app.topbar.expectAuthenticated();
```

Keep the raw API token tests in `authentication.spec.js` for now, or move them later to an API client plan if candidate #3 evolves toward Option A/Hybrid.

### Step 5 — Implement `ProductListPage`

Centralize product-list Shadow DOM traversal:

```js
export function createProductListPage(page) {
  return {
    locator: () => page.locator('#product-list'),

    async waitReady() {
      await expect(this.locator()).toBeVisible();
      await page.waitForFunction(() => {
        const list = document.querySelector('#product-list');
        return !!list?.shadowRoot?.querySelector('.list-grid ntx-item');
      });
    },

    async names() {
      await this.waitReady();
      return this.locator().evaluate((list) => {
        const items = list.shadowRoot?.querySelectorAll('ntx-item') || [];
        return Array.from(items)
          .map((item) => item.shadowRoot?.querySelector('[data-value="name"], h2, .item-title')?.textContent || '')
          .filter(Boolean);
      });
    },

    async openFirst() {
      await this.waitReady();
      await this.locator().evaluate((list) => {
        list.shadowRoot?.querySelector('ntx-item')
          ?.shadowRoot?.querySelector('.card')
          ?.click();
      });
    },
  };
}
```

Then migrate one or two `product-list.spec.js` and `product-detail.spec.js` assertions.

### Step 6 — Implement `RouterPage`

Centralize router content/hash/back-button contracts:

```js
export function createRouterPage(page) {
  return {
    locator: () => page.locator('ntx-router'),

    async waitContent() { /* existing waitForRouterContent semantics */ },
    async hash() { return page.evaluate(() => window.location.hash || ''); },

    async expectModel(model) {
      await expect.poll(async () => this.hash()).toContain(model);
    },

    async back() {
      await this.locator().evaluate((r) => r.shadowRoot?.querySelector('.back-btn')?.click());
    },
  };
}
```

Migrate product detail navigation after product-list object exists.

### Step 7 — Move Veille-specific helpers into `VeillePage`

Create `tests/frontend/tests/e2e/pages/veille-page.js`.

Move app-specific logic from `fixtures/ui.js` conceptually, but do not delete the old exported functions immediately. Re-export wrappers for compatibility if needed:

```js
export function createVeillePage(page) {
  return {
    async login() { /* login page form */ },
    async waitReady() { /* dashboard or AgentActor detail readiness */ },
    async loginAndOpenAssistant() { ... },
    chat: createVeilleChatPage(page),
  };
}
```

Migrate `veille-chat.spec.js` first, leaving thread-id/no-recreate/stability specs for a later pass.

### Step 8 — Add usage documentation

Update frontend test documentation after implementation:

- `FRONTEND.md` E2E section, or
- `tests/frontend/README.md` if introduced/available.

Document:

- use page objects for repeated Shadow DOM/component interactions
- specs should express user-visible behavior
- raw selectors are allowed for one-off assertions but should not duplicate shared readiness or navigation logic
- app-specific helpers belong in app-specific page objects, not generic `fixtures/ui.js`

---

## Migration Strategy

### Phase 1 — Add page objects without deleting helpers

- Add `pages/` modules.
- Keep `fixtures/auth.js` and `fixtures/ui.js` stable.
- Use existing helpers internally to preserve behavior.

### Phase 2 — Migrate authentication spec

- Replace topbar Shadow DOM assertions with `TopbarPage`.
- Replace localStorage manipulation with `SessionPage`.
- Keep API token assertions as-is initially.

### Phase 3 — Migrate product list/detail specs

- Move list readiness and item traversal to `ProductListPage`.
- Move router hash/content/back checks to `RouterPage`.

### Phase 4 — Migrate Veille chat spec

- Move `loginAndOpenVeilleAssistant`, `waitForVeilleUi`, `sendVeilleChatTurn`, and `getVeilleChatState` behavior into `VeillePage`/`VeilleChatPage`.
- Keep wrapper functions temporarily for remaining specs.

### Phase 5 — Prune old helpers

- After migrated specs cover all usages, reduce `fixtures/ui.js` to generic app readiness helpers or mark it internal.
- Move seed-user and token helpers toward an API/session module if Option A/Hybrid is later adopted.

---

## Verification Commands

Run the first migrated spec:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js tests/e2e/authentication.spec.js
```

Run product specs after product/router page objects:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js tests/e2e/product-list.spec.js tests/e2e/product-detail.spec.js
```

Run Veille spec after Veille page object migration:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/veille.playwright.config.js tests/e2e/veille-chat.spec.js
```

Run parallel smoke if migrated specs use `fixtures/parallel.js`:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.parallel.config.js tests/e2e/authentication.spec.js
```

---

## Acceptance Criteria

- `tests/frontend/tests/e2e/pages/` contains page objects for `AppPage`, `SessionPage`, `TopbarPage`, `RouterPage`, and `ProductListPage`.
- `authentication.spec.js` uses `createAppPage(page)` for topbar/session assertions.
- At least one product list/detail spec uses `ProductListPage` and/or `RouterPage`.
- `VeillePage` exists before migrating Veille chat helpers, or the plan explicitly defers app-specific migration.
- No migrated spec directly traverses topbar/product-list/router Shadow DOM for behavior covered by a page object.
- Existing helper functions remain compatible until all specs are migrated.
- Targeted Playwright specs pass.
- Documentation explains the page-object boundary and when to use raw selectors.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Page objects become broad selector dumps | Tests become abstract but not clearer | Only expose semantic user/framework actions and state |
| Selectors still brittle, just moved | Component refactors still break many page object methods | Prefer stable schema attributes (`data-value`, route hashes, host tags) and keep selectors centralized |
| App-specific logic leaks into generic page object | Generic helpers become hard to reason about | Put Veille-only behavior in `veille-page.js` |
| Migration changes wait semantics | Flaky or slower tests | Wrap existing `fixtures/ui.js` waits first; refactor waits later |
| Specs lose direct visibility into important DOM details | Regressions may hide behind helper | Page object methods should return state objects when tests need detailed assertions |

---

## Non-Goals / Guardrails

- Do not convert Playwright specs to Vitest in this plan.
- Do not introduce a full generic page-object framework.
- Do not remove existing `fixtures/ui.js` functions in the first pass.
- Do not hide one-off browser/layout assertions behind page objects unless they repeat.
- Do not change production component DOM solely to fit page objects.

---

## Follow-Up Plans

1. Add an E2E API client/session boundary if raw `page.request` calls remain noisy.
2. Move unit-like Playwright specs to Vitest once the frontend harness from Plan 1 is available.
3. Replace remaining Veille helper wrappers after all Veille chat specs use `VeillePage`.
4. Add page-object lint/review guidance: repeated Shadow DOM traversal in specs should move into a semantic page object.

---

## Critical Files for Implementation

- `tests/frontend/tests/e2e/pages/app-page.js`
- `tests/frontend/tests/e2e/pages/topbar.js`
- `tests/frontend/tests/e2e/pages/session.js`
- `tests/frontend/tests/e2e/pages/product-list.js`
- `tests/frontend/tests/e2e/authentication.spec.js`
