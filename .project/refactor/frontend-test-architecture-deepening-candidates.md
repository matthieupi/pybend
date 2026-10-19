# Frontend Test Architecture Deepening Candidates

Date: 2026-04-30  
Scope: `tests/frontend`, frontend runtime in `packages/n3tx-core`, visual layer in `packages/n3tx-ui`, agent UI test seams where they touch frontend tests.

## Executive Summary

The frontend test suite has strong coverage, but its architecture currently exposes too much coordination detail to individual tests. Tests often need to know how to:

- build backend-shaped JSON Schemas by hand
- register schemas with `NTT.SCHEMA()`
- seed DynamicClass instances
- mock permissions/config/logging
- mount Web Components in jsdom
- flush render lifecycle timing
- traverse nested Shadow DOM in Playwright
- boot seeded backend apps for browser tests
- manually store JWTs and wait for UI readiness

Those details are not separate product concepts. They are one product concept repeated through many shallow helpers: **"exercise the schema-driven frontend contract."**

The highest-leverage architecture direction is to deepen the test-facing modules so tests can operate at stable boundaries:

```text
Schema + fixture data
        |
        v
Frontend runtime harness
        |
        v
Mounted component / browser page object
        |
        v
Observable user-facing contract
```

This document expands the candidate list from the architecture exploration into detailed RFC-ready opportunities. Each candidate includes current-state snippets, coupling analysis, diagrams, testing impact, and multiple proposed solution shapes.

---

## Dependency Category Reference

| Category | Meaning | Test strategy |
|---|---|---|
| In-process | Pure JS/runtime/component coordination; no real network or process boundary | Deepen directly and test through the new boundary |
| Local-substitutable | Uses local stand-ins such as temp SQLite DBs, spawned local app processes, jsdom, or fake `fetch` | Test with the local substitute running |
| Remote but owned / Ports & Adapters | Crosses the framework's own HTTP/browser/backend boundary | Define a port; use in-memory/test adapter in tests and real adapter in production/E2E |
| True external / Mock | Third-party systems outside N3TX's control | Mock at the boundary |

---

## Candidate Overview

| # | Candidate | Main cluster | Dependency category | Recommended first move |
|---:|---|---|---|---|
| 1 | Frontend test harness for schema → runtime → component setup | Vitest/jsdom helpers, `NTT.js`, component tests | In-process | Add `createFrontendHarness()` and migrate one `ntx-item` vertical slice |
| 2 | Unified E2E app/server lifecycle harness | `start-e2e-app.js`, `fixtures/parallel.js`, Playwright config/teardown | Local-substitutable | Extract one `startSeededApp()` launcher used by serial and parallel modes |
| 3 | Semantic E2E API/session/page-object layer | `auth.js`, `ui.js`, raw `page.request`, Shadow DOM traversal | Remote but owned / Ports & Adapters | Add API client + session object + minimal page objects |
| 4 | Formidable + widgets + permissions boundary | `form.js`, widgets, permissions, `ntx-item` | In-process | Add `renderForm()` contract helper before product refactor |
| 5 | Router/navigation coverage split | `Router.js`, `ntx-router.js`, Vitest + Playwright router specs | Local-substitutable | Define router contract layers and remove duplicated browser cases |
| 6 | Move Playwright "unit" specs down to Vitest | `*-unit.spec.js`, component/form structure tests | In-process | Create migration rule: browser only when browser/backend behavior is required |

---

# 1. Frontend Test Harness: Schema → Runtime → Component

## Problem

Many Vitest tests are not just testing one component. They are manually rebuilding a slice of the N3TX frontend runtime:

```text
test file
  |
  +-- mocks config/logging/permissions
  +-- declares backend-shaped schema object
  +-- calls or bypasses NTT registry behavior
  +-- creates custom element
  +-- mutates schema/value/ref/mode directly
  +-- flushes async lifecycle by hand
  +-- asserts on generated HTML strings or Shadow DOM internals
```

This makes individual tests look like unit tests while actually depending on many cross-cutting contracts. The friction is a signal that the test boundary is too shallow.

## Current Surface Area

### Repeated module mocks in component tests

`tests/frontend/tests/components/ntx-item.test.js` currently owns config, logging, permissions, schema, value setup, and lifecycle bypasses in one file:

```js
vi.mock('../../config.js', () => ({
  config: {
    LOGGING: 3,
    API_URL: 'http://localhost:5000',
    E: { CONNECT: 'CONNECT', UPDATE: 'UPDATE', READ: 'READ', /* ... */ },
  }
}));

vi.mock('../../utils/Permissions.js', () => ({
  permissions: {
    canAction: vi.fn(() => true),
    canView: vi.fn(() => true),
    canEdit: vi.fn(() => true),
    user: null,
    authenticated: false,
    role: 'anonymous',
  }
}));
```

### Component lifecycle is sometimes bypassed

The same test file documents two different testing modes because private fields and lifecycle side effects are hard to exercise cleanly:

```js
// prototype.call(ctx) is acceptable for pure-function methods that do NOT
// access private fields/methods.
//
// For methods that access private members, use actual element instances.
```

It also installs value storage directly to avoid the real setter:

```js
function createItem(schema, value, opts = {}) {
  const el = document.createElement('ntx-item');
  el.schema = schema;

  Object.defineProperty(el, '_testValue', { value, writable: true });
  Object.defineProperty(el, 'value', {
    get() { return this._testValue; },
    set(v) { this._testValue = v; },
    configurable: true,
  });

  el.mode = opts.mode || 'display';
  el.ref = opts.ref || '';
  return el;
}
```

### Schema fixtures are hand-written and duplicated

`tests/frontend/tests/integration/helpers/mock-schemas.js` is useful, but it encodes backend-shaped schema details directly:

```js
export const ProductSchema = {
  $schema: `${API_URL}/Schema`,
  $id: `${API_URL}/Product`,
  __name__: 'Product',
  __tablename__: 'products',
  required: ['name', 'price'],
  properties: {
    id: { type: 'integer', readOnly: true, ui: { display: false } },
    name: { type: 'string', title: 'Name', minLength: 1, maxLength: 200 },
    price: { type: 'number', title: 'Price', ui: { widget: 'currency' } },
    comments: { type: 'array', items: { anyOf: [{ $ref: '#/$defs/Comment' }] } },
  },
  ui: {
    field_order: ['name', 'price', 'description', 'comments', 'favorites'],
    groups: { main: ['name', 'description', 'price'], Social: ['comments', 'favorites'] },
  },
  methods: { comment: { route: '/comment', methods: ['POST'] } },
  $defs: { Comment: { ...CommentSchema }, Like: { ...LikeSchema } },
};
```

When other tests define local variants, they may accidentally diverge from the canonical backend schema contract.

## Coupling Analysis

| Concern | Current owner | Why tests care today | Why that is friction |
|---|---|---|---|
| Schema identity | Hand-written objects | Tests must set `$id`, `__name__`, `__tablename__` | Noise unrelated to the behavior under test |
| Runtime registration | `NTT.SCHEMA()` / DynamicClass | Component tests need class instances and refs | Tests learn runtime internals |
| Fetch/transport | `global.fetch` mocks and Matrix dispatch | Lists and methods need remote-like responses | Each test invents routing behavior |
| Permissions | `Permissions.js` mock | Forms/actions hide/show fields | Repeated setup; role cache interactions leak |
| Mounting/rendering | `document.createElement()` + manual props | Web Components need schema/value/ref/mode | Tests bypass lifecycle to avoid side effects |
| Queries | HTML strings/class names | Assertions need DOM access | Tests become brittle to structural refactors |

## Desired Deep Module

A single **frontend test harness** should hide schema/runtime/component coordination and expose a small interface.

```text
+---------------------------+
| createFrontendHarness()   |
+-------------+-------------+
              |
              v
+---------------------------+
| schema fixtures/register  |
+-------------+-------------+
              |
              v
+---------------------------+
| DynamicClass + transport  |
+-------------+-------------+
              |
              v
+---------------------------+
| mounted components        |
+-------------+-------------+
              |
              v
+---------------------------+
| semantic queries/asserts  |
+---------------------------+
```

## Proposed Solutions

### Option A: Minimal harness, 1-3 entry points

```js
const h = await createFrontendHarness();

const product = await h.seed('Product', {
  schema: ProductSchema,
  data: makeProductData(1),
});

const item = await h.mountEntity('ntx-item', product, { display: 'md' });

expect(item.field('price').text()).toContain('$29.99');
expect(item.method('favorite')).toBeVisible();
```

Interface sketch:

```ts
type FrontendHarness = {
  seed(model: string, input: { schema: object; data?: object | object[] }): Promise<EntityRef>;
  mountEntity(tag: string, entity: EntityRef, options?: MountOptions): Promise<ComponentHandle>;
  permissions(state: PermissionState): void;
};
```

**Pros**

- Small surface area.
- Forces tests through realistic schema/entity/component flow.
- Easy first migration target.

**Cons**

- Less flexible for tests that need low-level runtime behavior.
- May still need escape hatches for transport/message assertions.

### Option B: Flexible harness with explicit layers

```js
const h = await createFrontendHarness()
  .withPermissions({ role: 'admin', authenticated: true })
  .withFetchRoutes({
    'GET /Product': ProductSchema,
    'GET /products': makeProductListResponse(3),
  });

const Product = await h.runtime.registerSchema(ProductSchema);
const product = h.runtime.seedEntity(Product, makeProductData(1));
const item = await h.components.mount('ntx-item', { ref: product.addr, display: 'md' });
```

Interface sketch:

```ts
type FrontendHarness = {
  runtime: RuntimeHarness;
  components: ComponentHarness;
  transport: TransportHarness;
  permissions: PermissionHarness;
  cleanup(): Promise<void>;
};
```

**Pros**

- Supports broad suite migration.
- Makes lower-level contracts testable without copy/paste setup.
- Easier to extend to generated method wrappers and list refresh flows.

**Cons**

- Larger API can become another shallow abstraction if not curated.
- Requires stronger conventions around semantic query handles.

### Option C: Contract-first helpers only

Do not build a full harness. Add focused helpers:

```js
const schema = productSchema().withCurrencyField('price').build();
const el = await mountComponent('ntx-item', { schema, value });
const view = queryEntityComponent(el);
```

**Pros**

- Lowest risk.
- Easy to introduce incrementally.

**Cons**

- Does not fully hide `NTT.SCHEMA()`, transport, or permission setup.
- Can proliferate helper fragments rather than deepen one module.

## Recommendation

Start with **Option A**, but design its internals so it can grow toward Option B. The first migrated vertical slice should be:

```text
ProductSchema
  -> NTT.SCHEMA(ProductSchema)
  -> seed Product instance
  -> mount <ntx-item display="md">
  -> assert visible fields, methods, widgets, edit affordances
```

## Test Replacement Plan

| Existing test style | Replacement boundary test |
|---|---|
| `NTTItem.prototype.xs.call(ctx)` pure HTML assertions | Mounted component renders identity in xs/sm/md modes |
| Manual `createItem()` with fake value setter | Harness-managed component with schema/value/ref lifecycle |
| Inline schema variants in many files | Schema fixture builder or canonical product fixture overrides |
| Repeated permission mocks | `h.permissions({ role: 'admin' })` |
| HTML string assertions | Semantic component handles: `field()`, `method()`, `action()` |

---

# 2. Unified E2E App/Server Lifecycle Harness

## Problem

The Playwright server lifecycle has two main paths:

1. serial/config-driven `webServer.command` via `start-e2e-app.js`
2. parallel worker fixture via `fixtures/parallel.js`

They solve the same problem but duplicate lifecycle ownership:

- choose app directory
- create temp directory and SQLite DB path
- construct Python environment
- run `seed.py --reset`
- spawn `main.py`
- wait for readiness
- stop process
- clean temp files

## Current Surface Area

### Serial launcher

`tests/frontend/tests/e2e/start-e2e-app.js` defines app profiles and starts one detached process:

```js
const APPS = {
  core: {
    dir: repoPath('examples/core'),
    dbName: 'test.db',
    tmpPrefix: 'ntx-e2e-',
    port: '5000',
    resetArg: '--reset',
  },
  veille: {
    dir: repoPath('apps/veille'),
    dbName: 'veille-test.db',
    port: '5010',
    extraEnv: { N3TX_CHAT_LLM: 'test' },
  },
};

const tmpDir = mkdtempSync(join(tmpdir(), app.tmpPrefix));
const dbPath = join(tmpDir, app.dbName);

const env = {
  ...process.env,
  PYTHONPATH,
  N3TX_SQLITE_DB: dbPath,
  NTT_SQLITE_DB: dbPath,
  N3TX_PORT: app.port,
  N3TX_API_URL: `http://localhost:${app.port}`,
  ...(app.extraEnv || {}),
};

execFileSync(PYTHON_BIN, ['seed.py', app.resetArg].filter(Boolean), { cwd: app.dir, env });
child = spawn(PYTHON_BIN, ['main.py'], { cwd: app.dir, env, detached: true });
```

### Parallel worker fixture

`tests/frontend/tests/e2e/fixtures/parallel.js` performs a similar setup per worker:

```js
const port = BASE_PORT + workerInfo.parallelIndex;
const baseURL = `http://localhost:${port}`;
const appDir = repoPath('examples/core');
const tmpDir = mkdtempSync(join(tmpdir(), `ntx-e2e-parallel-${workerInfo.parallelIndex}-`));
const dbPath = join(tmpDir, 'test.db');

const env = {
  ...process.env,
  PYTHONPATH,
  N3TX_SQLITE_DB: dbPath,
  NTT_SQLITE_DB: dbPath,
  N3TX_PORT: String(port),
  N3TX_API_URL: baseURL,
};

execFileSync(PYTHON_BIN, ['seed.py', '--reset'], { cwd: appDir, env });
const child = spawn(PYTHON_BIN, ['main.py'], { cwd: appDir, env });
await waitForServer(baseURL);
```

## Current Flow Diagram

```text
Serial Playwright config
        |
        v
start-e2e-app.js
        |
        +-- app profile
        +-- temp DB
        +-- seed.py
        +-- spawn main.py detached
        +-- marker file
        |
        v
global-teardown.js cleanup

Parallel Playwright config
        |
        v
fixtures/parallel.js worker fixture
        |
        +-- hardcoded core app
        +-- temp DB
        +-- seed.py
        +-- spawn main.py attached
        +-- waitForServer()
        |
        v
fixture finally cleanup
```

## Coupling Analysis

| Concern | Serial path | Parallel path | Risk |
|---|---|---|---|
| App profile | `APPS` object | hardcoded core app | New app config may only update one path |
| DB/env setup | inline | inline | Divergent env variables |
| Seeding | `timeout: 60000` | `timeout: 30000` | Different failure behavior |
| Process mode | detached + marker | attached child | Cleanup semantics differ |
| Readiness | Playwright webServer URL | local `waitForServer()` | Different readiness contract |
| Cleanup | global teardown reads marker | fixture finally block | Stale marker/setup files confuse future changes |

## Proposed Solutions

### Option A: Extract shared `startSeededApp()` module

Create a reusable local-substitutable harness:

```js
// tests/e2e/harness/app-server.js
export async function startSeededApp(options) {
  const profile = resolveAppProfile(options.app);
  const runtime = prepareRuntime({ profile, port: options.port });

  seedDatabase(runtime);
  const child = spawnApp(runtime);
  await waitForApp(runtime.baseURL, options.readinessPath || profile.readinessPath);

  return {
    app: profile.name,
    baseURL: runtime.baseURL,
    dbPath: runtime.dbPath,
    env: runtime.env,
    stop: () => stopAndCleanup(child, runtime),
  };
}
```

Serial launcher becomes a thin CLI wrapper:

```js
const server = await startSeededApp({ app: process.argv[2], detached: true, marker: true });
keepProcessAlive(server);
```

Parallel fixture becomes:

```js
const server = await startSeededApp({ app: 'core', port });
await use(server);
await server.stop();
```

**Pros**

- Removes duplicate lifecycle code.
- Keeps Playwright config changes small.
- Gives one module to test with local process/DB stand-ins.

**Cons**

- Needs careful handling of detached vs attached process cleanup.

### Option B: Class-based app server harness

```js
const server = await E2EAppServer.for('core')
  .withPort(port)
  .withTempDatabase()
  .withSeedReset()
  .start();

await server.ready();
await server.stop();
```

**Pros**

- Clear lifecycle object.
- Good place for debug logging and tracing.

**Cons**

- More abstraction than needed unless many profiles grow.

### Option C: Keep launchers separate but share profile/env builders

```js
const profile = appProfile('core');
const runtime = createAppRuntime(profile, { port });
```

**Pros**

- Lowest risk.
- Reduces drift in env/profile setup.

**Cons**

- Still duplicates process and cleanup behavior.

## Recommendation

Choose **Option A**. It is deep enough to own the lifecycle while keeping the interface small.

## Boundary Tests to Add

| Behavior | Test |
|---|---|
| Core app starts with isolated DB | `startSeededApp({ app: 'core' })` returns healthy `/Product` |
| Per-worker isolation | two servers on different ports use different DB paths |
| Cleanup | `stop()` terminates child and removes temp dir |
| App profile env | Veille profile includes `N3TX_CHAT_LLM=test` |
| Failure reporting | seed failure includes app name, cwd, db path |

---

# 3. Semantic E2E API, Session, and Page Objects

## Problem

Many Playwright specs directly know too much about backend API paths, JWT storage, seed users, app readiness, and Shadow DOM internals.

This makes test intent harder to read:

```text
Spec intent: "Alice can see authenticated topbar"

Actual required knowledge:
  - login endpoint is /users/login
  - token may be body.token or body.data.token
  - localStorage key is jwtToken
  - app must reload after token write
  - topbar readiness means .user-pill exists inside shadowRoot
```

## Current Surface Area

### Auth helper mixes API login, storage, reload, and UI readiness

```js
export async function loginAs(page, userName) {
  const user = USERS[userName];
  const token = await getToken(page.request, user.email, user.password);
  await setToken(page, token);
  await reloadApp(page);
  await waitForAuthenticatedTopbar(page);
}
```

### UI helper exposes Shadow DOM selectors as readiness contract

```js
export async function waitForAuthenticatedTopbar(page) {
  await waitForTopbar(page);
  await page.waitForFunction(() => {
    const topbar = document.querySelector('ntx-topbar');
    return !!topbar?.shadowRoot?.querySelector('.user-pill');
  });
}
```

### Generic UI helpers contain app-specific Veille chat behavior

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
    return root?.querySelectorAll('.msg').length >= messageCount + 2
      && root?.querySelectorAll('.stream-footer').length >= footerCount + 1;
  }, before);
}
```

## Proposed Module Boundary

```text
Playwright spec
   |
   +-- api.products.create(...)
   +-- session.loginAs('alice')
   +-- app.topbar.expectAuthenticated()
   +-- app.products.open(1).expectField('name', '...')
   +-- veille.chat.send('...').expectAssistantTurn()
```

## Proposed Solutions

### Option A: API client + session object only

```js
const api = createApiClient(page.request);
const session = createSession(page, api.auth);

await session.loginAs('alice');
const product = await api.products.create({ name: 'Notebook', price: 12 });
```

Interface sketch:

```ts
type ApiClient = {
  auth: { login(user: SeedUser): Promise<AuthSession> };
  products: ResourceClient<Product>;
  comments: ResourceClient<Comment>;
};

type Session = {
  loginAs(name: 'alice' | 'bob' | 'charlie'): Promise<void>;
  logout(): Promise<void>;
  withToken(token: string): Promise<void>;
};
```

**Pros**

- Reduces raw API calls and localStorage coupling.
- Lowers setup complexity in specs.

**Cons**

- Does not solve Shadow DOM traversal.

### Option B: Page objects with semantic component queries

```js
const app = createAppPage(page);

await app.gotoHome();
await app.session.loginAs('alice');
await app.products.expectListReady();
await app.products.open('Test Product 1');
await app.productDetail.expectActionVisible('favorite');
```

Interface sketch:

```ts
type AppPage = {
  session: Session;
  topbar: TopbarPage;
  router: RouterPage;
  products: ProductListPage;
};
```

**Pros**

- Tests read like user flows.
- Shadow DOM selectors are centralized.
- Component DOM refactors only update page objects.

**Cons**

- Page objects can become too broad if they expose every selector.

### Option C: Ports & adapters split for browser/backend API

Define an owned port for test app interactions:

```ts
interface TestAppPort {
  login(user: SeedUser): Promise<void>;
  createProduct(data: ProductInput): Promise<Product>;
  openProduct(id: number): Promise<void>;
  assertAuthenticated(): Promise<void>;
}
```

Adapters:

- `PlaywrightTestAppPort`: real browser + backend
- `VitestTestAppPort`: jsdom + fake transport for lower-level tests

**Pros**

- Best long-term alignment for moving Playwright unit specs down to Vitest.
- Strong contract across test layers.

**Cons**

- Larger design investment.
- Needs discipline to avoid hiding too much browser behavior.

## Recommendation

Use a hybrid of **Option A + Option B**:

- add an API client and session object first
- add small page objects only for repeated semantic surfaces: topbar, router, product list/detail, Veille chat
- do not create a universal page-object framework

## Test Replacement Plan

| Current pattern | Replacement |
|---|---|
| `page.request.post('/users/login')` | `api.auth.login('alice')` |
| `localStorage.setItem('jwtToken', token)` | `session.withToken(token)` |
| `shadowRoot.querySelector('.user-pill')` | `topbar.expectAuthenticated()` |
| `#agent-detail` nested `ntx-chat` evaluation | `veille.chat.sendTurn(text)` |
| Raw product route calls in specs | `api.products.create/get/list` |

---

# 4. Formidable + Widgets + Permissions Boundary

## Problem

`Formidable` is already a deep product module in some ways: it hides a lot of schema-to-form rendering behavior behind `getForm()`, `getFields()`, and `getInput()`. The test boundary around it, however, is shallow and string-heavy.

`form.js` owns:

- entity vs method schema normalization
- `$ref` parameter expansion
- required field calculation
- field ordering
- layout cache by schema/mode/role
- permission filtering
- protected/hidden field filtering
- grouped fields
- attached methods
- widget dispatch
- display/edit rendering
- value reading and validation

## Current Surface Area

### Formidable imports multiple collaborators directly

```js
import { permissions } from '../utils/Permissions.js';
import { NTT } from '../core/NTT.js';
import Logging from '../utils/Logging.js';
import { getWidgetForField } from '../widgets/index.js';
import '../components/ntx-ref-picker.js';
```

### Layout and permission decisions are cached internally

```js
const _layoutCache = new Map();

function _getLayout(schema, mode) {
  const normalized = normalizeSchema(schema);
  const cacheKey = `${normalized.__name__}:${normalized.__formKind}:${mode}:${permissions.role}`;
  const cached = _layoutCache.get(cacheKey);
  if (cached) return cached;

  const renderableFields = fieldOrder.filter(key => {
    if (!isMethodSchema && _headerFieldSet.has(key)) return false;
    if (def?.ui?.display === false) return false;
    if (mode === 'edit' && def?.ui?.protected) return false;
    if (!permissions.canView(def)) return false;
    return true;
  });

  const layout = { renderableFields, groups: ui.groups };
  _layoutCache.set(cacheKey, layout);
  return layout;
}
```

### Tests assert generated HTML strings

```js
const html = Formidable.getForm(ntt, 'display');

expect(html).toContain('<fieldset class="ntx-group ntx-group-main">');
expect(html).toContain('<legend>main</legend>');
expect(html.indexOf('data-value="price"')).toBeGreaterThan(html.indexOf('ntx-group-main'));
```

String tests are useful for exact rendering regressions, but they make larger refactors hard because they freeze internal markup instead of the form contract.

## Flow Diagram

```text
schema + value + mode
        |
        v
normalizeSchema()
        |
        v
_getLayout(schema, mode, permissions.role)
        |
        +-- field_order
        +-- groups
        +-- hidden/protected fields
        +-- permissions.canView()
        |
        v
getInput() per field
        |
        +-- widget registry
        +-- ref picker
        +-- scalar input fallback
        |
        v
HTML string
        |
        v
component shadow DOM / form readback
```

## Proposed Solutions

### Option A: Test-only `renderForm()` boundary helper

Keep product code unchanged initially. Add a DOM contract wrapper in tests:

```js
const form = renderForm({ schema, value, mode: 'edit', role: 'admin' });

expect(form.field('price')).toUseWidget('currency');
expect(form.field('secret')).not.toExist();
expect(form.group('Social')).toContainField('comments');
expect(form.read()).toEqual({ name: 'Test Product', price: 29.99 });
```

**Pros**

- Immediate test clarity.
- Allows markup changes while preserving semantic contract tests.

**Cons**

- Product implementation remains string-based internally.

### Option B: Product refactor into FormPlan + renderer

Split current behavior into an explicit intermediate plan:

```ts
type FormPlan = {
  header: HeaderPlan;
  fields: FieldPlan[];
  groups: GroupPlan[];
  attachedMethods: MethodPlan[];
};

class Formidable {
  static plan(ntt, mode, attachedMethods): FormPlan;
  static render(plan): string;
  static read(root): object;
  static validate(root, plan): ValidationResult;
}
```

Callers can still use:

```js
Formidable.getForm(ntt, mode, methods); // plan + render compatibility wrapper
```

**Pros**

- Makes schema/layout behavior testable without string assertions.
- Clarifies ownership: planning vs rendering vs readback.
- Potentially improves product architecture, not just tests.

**Cons**

- Larger production refactor.
- Needs careful compatibility with existing components.

### Option C: Deepen around widget registry instead

Define a field rendering service:

```ts
type FieldRenderer = {
  renderDisplay(field: FieldDef, value: unknown, context: FieldContext): string;
  renderEdit(field: FieldDef, value: unknown, context: FieldContext): string;
  read(root: Element, field: FieldDef): unknown;
};
```

`Formidable` remains layout owner; field rendering and readback move behind a deeper widget boundary.

**Pros**

- Targets the most volatile area: scalar/list/ref/widget field rendering.
- Can improve widgets and forms together.

**Cons**

- Does not solve schema normalization and grouping complexity.

## Recommendation

Use **Option A first** to stabilize tests, then consider **Option B** as a product refactor once contract tests exist. Contract tests should precede production refactoring.

## Boundary Tests to Add

| Contract | Example assertion |
|---|---|
| Hidden fields stay hidden | `form.field('id').not.toExist()` |
| Protected fields are not editable | `form.field('user_owner').not.toHaveInput()` |
| Method parameter refs expand | `form.field('comment.name').toHaveInput()` |
| Boolean fields use checkbox | `form.field('active').input.type === 'checkbox'` |
| Widgets round-trip values | currency/bool/textarea display + edit + readback |
| Role changes invalidate layout | admin-visible field appears after `role='admin'` |

---

# 5. Router / Navigation Coverage Split

## Problem

Router behavior appears in several layers:

- pure route parsing/history behavior in `Router.js`
- component rendering in `ntx-router.js`
- jsdom integration navigation tests
- Playwright browser tests

The same concepts — hash routes, empty home route, `NAVIGATE`, `BACK`, rendered route content — can be tested repeatedly across layers. The issue is not that these tests are wrong; it is that ownership is unclear.

## Desired Layering

```text
Router unit tests
  - parse route
  - update history stack
  - emit navigation messages
  - map empty route / hash route

ntx-router component tests
  - receives route state
  - chooses renderer tag
  - mounts configured model/view component

Browser E2E smoke
  - browser hash changes route the visible app
  - back/forward works through real browser history
```

## Proposed Solutions

### Option A: Explicit router test matrix

Create a small document or test helper table defining ownership:

| Behavior | Unit | Component | E2E |
|---|---:|---:|---:|
| hash parsing | yes | no | smoke only |
| history stack | yes | no | browser back smoke |
| renderer selection | no | yes | one smoke |
| route to entity detail | no | yes with fake schema | yes with backend |
| invalid route fallback | yes | yes | optional |

**Pros**

- Lowest implementation cost.
- Helps delete duplication safely.

**Cons**

- Does not by itself deepen APIs.

### Option B: Router harness with fake browser location

```js
const router = createRouterHarness({ initialHash: '#Product/1' });

router.navigate('Product/2');
expect(router.current()).toEqual({ model: 'Product', id: '2' });
expect(router.history()).toEqual(['Product/1', 'Product/2']);
```

**Pros**

- Makes jsdom route tests clear and local-substitutable.

**Cons**

- Still needs separate component/browser coverage.

### Option C: Route contract shared by `Router` and `ntx-router`

Extract a route state object:

```ts
type RouteState = {
  raw: string;
  model?: string;
  id?: string;
  view?: string;
  isHome: boolean;
};

parseRoute(hashOrPath): RouteState;
resolveRouteView(route, schemaRegistry): ViewPlan;
```

**Pros**

- Deepens product interface and reduces repeated parsing/render logic.

**Cons**

- More production impact; should be justified by observed duplication in source, not just tests.

## Recommendation

Start with **Option A**. If duplication persists after pruning tests, consider Option B for tests. Reserve Option C for a product refactor only if source-level route parsing/rendering is also duplicated.

---

# 6. Move Playwright "Unit" Specs Down to Vitest

## Problem

Several browser specs are named or shaped like unit/component tests but run through a full app server and browser. This expands cost and conceptual scope:

```text
Component assertion
  requires:
    Playwright browser
    seeded backend app
    temp SQLite DB
    auth/session setup
    shell bootstrap
    Shadow DOM traversal
```

This is useful for compatibility smoke tests, but it should not be the primary way to verify static component DOM contracts.

## Proposed Test Placement Rule

| Test needs... | Put it in... |
|---|---|
| schema-to-DOM mapping | Vitest/jsdom |
| generated DynamicClass behavior | Vitest/jsdom with frontend harness |
| widget/form rendering and readback | Vitest/jsdom |
| browser layout, viewport, CSS computation | Playwright |
| real backend schema compatibility | Playwright smoke or API-backed integration |
| auth/session behavior in browser | Playwright |
| CRUD flows through backend + UI | Playwright |
| streaming/SSE/browser event behavior | Playwright unless fake transport is sufficient |

## Proposed Solutions

### Option A: One-for-one migration with thin Playwright smoke

For each `*-unit.spec.js`:

1. Move static assertions into Vitest using the frontend harness.
2. Keep one Playwright smoke asserting the component loads in the real app.

```text
Before:
  e2e/ntx-item-unit.spec.js  -> many DOM assertions via browser/backend

After:
  components/ntx-item.contract.test.js -> detailed DOM contract in jsdom
  e2e/component-smoke.spec.js          -> one real app smoke
```

### Option B: Batch by surface

Move all item/list/method/form unit-ish specs together after the frontend harness exists.

**Pros**

- Lets the harness design settle across multiple components.
- Bigger immediate E2E speedup.

**Cons**

- Larger PR / more review risk.

### Option C: Keep E2E files but tag/lane them differently

Retain browser tests but split fast smoke and full flow lanes.

**Pros**

- No migration risk.

**Cons**

- Does not address architecture friction.
- Keeps backend/browser cost for unit-like coverage.

## Recommendation

Choose **Option A** after Candidate 1 introduces the frontend harness. Migrate one file first, likely the smallest `ntx-method` or `form-rendering` unit-like browser spec, then proceed surface by surface.

---

## Recommended Execution Sequence

```text
Phase 1: Test boundary kit
  |
  +-- createFrontendHarness()
  +-- schema fixture builder / canonical fixtures
  +-- semantic component query handles
  +-- migrate one ntx-item or ntx-method slice
  |
  v
Phase 2: Form contract tests
  |
  +-- renderForm() helper
  +-- convert HTML string-heavy tests to DOM/semantic contracts
  +-- optionally refactor Formidable into plan/render/read later
  |
  v
Phase 3: E2E lifecycle deepening
  |
  +-- startSeededApp()
  +-- serial launcher wrapper
  +-- parallel fixture wrapper
  +-- stale setup/teardown cleanup
  |
  v
Phase 4: E2E semantic layer
  |
  +-- API client
  +-- session helper
  +-- topbar/router/product/veille page objects
  |
  v
Phase 5: Move browser unit specs down
  |
  +-- Vitest contract coverage
  +-- thin Playwright smoke coverage
```

## Risk Table

| Risk | Impact | Mitigation |
|---|---|---|
| Harness becomes too broad | Tests depend on harness implementation instead of product behavior | Keep initial interface small and add only repeated needs |
| Semantic page objects hide important browser behavior | E2E tests become too abstract | Expose user-visible actions/assertions, not generic selector wrappers |
| Moving Playwright coverage loses real-browser signal | Regressions in browser-only behavior may slip | Keep smoke tests for browser/layout/auth/backend compatibility |
| Formidable refactor changes markup | UI regressions | Add DOM contract tests before production changes |
| App launcher cleanup breaks CI | Hanging processes or stale DB files | Add lifecycle tests and preserve old launcher as wrapper during migration |

## RFC Candidates to File as GitHub Issues

### RFC 1: Introduce frontend test harness for schema-runtime-component contracts

**Problem:** Vitest component/integration tests duplicate schema setup, `NTT.SCHEMA()` registration, permissions, component mounting, and DOM querying.  
**Interface:** `createFrontendHarness()` with `seed()`, `mountEntity()`, and `permissions()`.  
**Testing:** migrate one `ntx-item` vertical slice and delete equivalent shallow setup.

### RFC 2: Unify Playwright app server lifecycle

**Problem:** serial and parallel E2E launchers duplicate temp DB, env, seed, process, readiness, and cleanup behavior.  
**Interface:** `startSeededApp({ app, port, mode })`.  
**Testing:** lifecycle tests for start, readiness, per-worker isolation, cleanup.

### RFC 3: Add semantic E2E API/session/page objects

**Problem:** specs directly know backend route paths, JWT storage, seed users, and nested Shadow DOM selectors.  
**Interface:** `createApiClient()`, `createSession()`, `createAppPage()`.  
**Testing:** convert auth/topbar/product/veille flows to semantic helpers.

### RFC 4: Stabilize Formidable tests with form contract boundary

**Problem:** form tests assert HTML strings across schema normalization, layout, permissions, widgets, and methods.  
**Interface:** `renderForm()` semantic test helper, later `FormPlan` product API if warranted.  
**Testing:** hidden/protected fields, grouping, widgets, method refs, role-specific layout.

### RFC 5: Define frontend test placement policy and migrate browser unit specs

**Problem:** Playwright unit-like specs boot backend/browser for assertions that jsdom can own.  
**Interface:** documented test placement matrix plus harness-backed Vitest contracts.  
**Testing:** one-for-one migration with thin Playwright smoke retained.

---

## Recommended First RFC

File **RFC 1: Introduce frontend test harness for schema-runtime-component contracts** first.

Why:

1. It unlocks migration of browser unit specs.
2. It gives Formidable and widget refactors safer contract coverage.
3. It reduces the largest day-to-day AI navigation friction in Vitest tests.
4. It is fully in-process, so the blast radius is lower than E2E process lifecycle changes.

Suggested first implementation target:

```text
tests/frontend/tests/helpers/frontend-harness.js
tests/frontend/tests/components/ntx-item.contract.test.js
```

Minimal initial API:

```js
const h = await createFrontendHarness();

const product = await h.seed('Product', {
  schema: ProductSchema,
  data: makeProductData(1),
});

const item = await h.mountEntity('ntx-item', product, { display: 'md' });

expect(item.field('name').text()).toContain('Test Product 1');
expect(item.field('price').text()).toContain('$29.99');
expect(item.method('favorite')).toBeVisible();
```

The goal is not to add helpers for their own sake. The goal is to move tests from "assembling the framework by hand" to "exercising the framework contract at the boundary."
