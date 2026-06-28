# Plan 1 — Frontend Test Harness, Option B

## Purpose

Implement the **Option B flexible frontend test harness** described in `.project/plans/frontend-test-architecture-deepening-candidates.md` candidate #1.

The goal is to deepen the frontend test boundary so Vitest tests can exercise the schema-driven frontend contract without manually wiring every collaborator:

- schema fixture construction
- `NTT.SCHEMA()` / DynamicClass registration
- entity seeding and fetch routes
- permissions/user state
- jsdom Web Component mounting
- render flushing
- semantic DOM queries
- transport/TX assertions where needed

This is a **test architecture refactor**, not a product behavior change. Production runtime code should remain unchanged unless the new boundary tests expose a real product regression.

---

## Problem Statement

Current frontend tests often rebuild the framework by hand. For example, component tests mock config/logging/permissions inline, create schema objects locally, bypass component lifecycle setters, and assert on strings or private markup:

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

The test knows too much about implementation mechanics. The intended contract is simpler:

> Given a backend-shaped schema and entity data, the frontend runtime creates a DynamicClass and mounted component that renders fields, methods, widgets, and actions according to schema and permissions.

This plan introduces a layered harness that owns the setup details and exposes explicit sub-boundaries for tests that need different levels of control.

---

## Target Architecture

Option B uses an explicit layered harness instead of one monolithic helper.

```text
+---------------------------------------------------------------+
| createFrontendHarness()                                       |
+-------------------+-------------------+-----------------------+
                    |                   |
                    v                   v
        +---------------------+  +---------------------+
        | schema fixtures     |  | permissions harness |
        | - canonical schemas |  | - role/user state   |
        | - schema builder    |  | - canView/canEdit   |
        +----------+----------+  +----------+----------+
                   |                        |
                   v                        |
        +---------------------+             |
        | runtime harness     |<------------+
        | - NTT.SCHEMA        |
        | - DynamicClass      |
        | - seeded entities   |
        +----------+----------+
                   |
                   v
        +---------------------+      +---------------------+
        | transport harness   |----->| component harness   |
        | - fetch routes      |      | - mount/unmount     |
        | - TX capture        |      | - flush render      |
        +---------------------+      | - semantic queries  |
                                     +---------------------+
```

### Design Principle

The harness should hide coordination complexity while preserving meaningful test intent:

```js
const h = await createFrontendHarness()
  .withPermissions({ authenticated: true, role: 'admin' })
  .withFetchRoutes({
    'GET http://localhost:5000/Product': ProductSchema,
    'GET http://localhost:5000/products': makeProductListResponse(3),
  });

const Product = await h.runtime.registerSchema(ProductSchema);
const product = h.runtime.seedEntity(Product, makeProductData(1));

const item = await h.components.mount('ntx-item', {
  schema: ProductSchema,
  value: product.value,
  ref: product.href,
  display: 'md',
});

expect(item.field('price').text()).toContain('$29.99');
expect(item.method('favorite')).toBeVisible();
expect(h.transport.sent()).toEqual([]);
```

---

## Scope

### In Scope

- Add reusable Vitest helpers under `tests/frontend/tests/helpers/`.
- Add canonical schema fixture helpers, initially wrapping existing `mock-schemas.js` rather than replacing it wholesale.
- Add a flexible `createFrontendHarness()` with explicit sub-harnesses:
  - `runtime`
  - `transport`
  - `components`
  - `permissions`
  - `schemas`
- Migrate one vertical slice test to prove the interface.
- Keep the first migration small enough to review confidently.
- Add self-tests for the harness where useful.

### Out of Scope

- Product refactors in `NTT.js`, `Component.js`, `ntx-item.js`, or `form.js`.
- Playwright migration work from candidate #6.
- E2E app lifecycle unification from candidate #2.
- Full replacement of every frontend component test.
- GitHub issue creation; this plan is the implementation-grade design artifact.

---

## Current Files and Responsibilities

| File | Current role | Harness impact |
|---|---|---|
| `tests/frontend/tests/setup.js` | Global jsdom mocks, cleanup, `fetch`, `localStorage`, `WebSocket`, `ResizeObserver` | Harness should build on this, not duplicate global setup |
| `tests/frontend/tests/integration/helpers/test-env.js` | Simple fetch route helpers and promise flushing | Likely superseded or wrapped by `transport` and `flush` helpers |
| `tests/frontend/tests/integration/helpers/mock-schemas.js` | Canonical Product/Comment/Like schemas and sample data | Move behind `schemas` harness; keep as source during first phase |
| `tests/frontend/tests/components/ntx-item.test.js` | Large component test with local mocks, schemas, lifecycle bypasses | First migration target for one contract slice |
| `tests/frontend/tests/generators/form.test.js` | String-heavy Formidable tests | Future consumer of harness/component query helpers, not first target |
| `packages/n3tx-core/src/n3tx_core/static/core/NTT.js` | DynamicClass registry and schema runtime | Runtime harness should use public static APIs where possible |
| `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js` | Entity renderer | Mounted via component harness; no product edits planned |

---

## Proposed File Layout

```text
tests/frontend/tests/helpers/
├── frontend-harness.js          # createFrontendHarness(), top-level composition
├── harness/
│   ├── runtime.js               # NTT schema/entity helpers
│   ├── transport.js             # fetch route mock + TX capture helpers
│   ├── components.js            # mount/flush/query handles
│   ├── permissions.js           # permissions state control
│   ├── schemas.js               # canonical schema builders/wrappers
│   └── flush.js                 # render/microtask flushing helpers
└── queries/
    ├── component-handle.js      # generic shadow/DOM wrapper
    └── entity-component.js      # field/method/action semantic queries

tests/frontend/tests/components/
└── ntx-item.contract.test.js    # first migrated vertical slice
```

This layout keeps the public entry point small while allowing internals to stay cohesive.

---

## Public Interface Sketch

### `createFrontendHarness()`

```ts
type FrontendHarness = {
  runtime: RuntimeHarness;
  transport: TransportHarness;
  components: ComponentHarness;
  permissions: PermissionHarness;
  schemas: SchemaHarness;

  withPermissions(state: PermissionState): FrontendHarness;
  withFetchRoutes(routes: RouteMap): FrontendHarness;
  cleanup(): Promise<void>;
};

async function createFrontendHarness(options?: HarnessOptions): Promise<FrontendHarness>;
```

Usage:

```js
const h = await createFrontendHarness()
  .withPermissions({ authenticated: true, role: 'admin' })
  .withFetchRoutes({
    '/Product': ProductSchema,
    '/products': makeProductListResponse(3),
  });
```

### `RuntimeHarness`

```ts
type RuntimeHarness = {
  registerSchema(schema: object): Promise<DynamicClass>;
  registerSchemas(schemas: object[]): Promise<Record<string, DynamicClass>>;
  getClass(model: string): DynamicClass | undefined;
  seedEntity(modelOrClass: string | DynamicClass, data: object): EntityHandle;
  seedList(modelOrClass: string | DynamicClass, data: object[]): EntityHandle[];
};
```

Expected implementation shape:

```js
async function registerSchema(schema) {
  NTT.SCHEMA(schema);
  await flushMicrotasks();
  return NTT.get(schema.__name__);
}

function seedEntity(modelOrClass, data) {
  const DC = typeof modelOrClass === 'string' ? NTT.get(modelOrClass) : modelOrClass;
  const entity = new DC(data.id, data);
  return createEntityHandle(entity, data);
}
```

Note: exact DynamicClass constructor behavior must be verified during implementation. If direct construction is not stable, seed through the same public `READ`/`UPDATE` path tests currently use.

### `TransportHarness`

```ts
type TransportHarness = {
  route(methodAndUrl: string | RegExp, response: unknown, options?: ResponseOptions): void;
  routes(routeMap: RouteMap): void;
  clearRoutes(): void;
  fetchCalls(): FetchCall[];
  sent(): TX[];
  captureTX(tx: TX): void;
};
```

Fetch route behavior should supersede `integration/helpers/test-env.js` without forcing a big-bang migration.

```js
h.transport.route('GET /Product', ProductSchema);
h.transport.route(/\/products(\?.*)?$/, makeProductListResponse(3));
```

### `ComponentHarness`

```ts
type ComponentHarness = {
  mount(tag: string, state?: ComponentMountState): Promise<ComponentHandle>;
  mountEntity(tag: string, entity: EntityHandle, options?: EntityMountOptions): Promise<EntityComponentHandle>;
  flush(): Promise<void>;
  unmountAll(): void;
};
```

Usage:

```js
const item = await h.components.mountEntity('ntx-item', product, {
  display: 'md',
  mode: 'display',
});

expect(item.field('name').text()).toContain('Test Product 1');
```

### `PermissionHarness`

```ts
type PermissionHarness = {
  set(state: PermissionState): void;
  anonymous(): void;
  authenticated(role?: string, user?: object): void;
  allowAll(): void;
  deny(action: 'view' | 'edit' | 'action', predicate?: Function): void;
};
```

This should centralize the repeated mock behavior currently spread across test files:

```js
permissions.canAction.mockImplementation(() => true);
permissions.canView.mockImplementation(() => true);
permissions.canEdit.mockImplementation(() => true);
```

### `SchemaHarness`

Initial version should wrap existing fixtures:

```ts
type SchemaHarness = {
  product(overrides?: SchemaOverrides): object;
  comment(overrides?: SchemaOverrides): object;
  like(overrides?: SchemaOverrides): object;
  productData(id?: number, overrides?: object): object;
  productList(count?: number, overrides?: object): object;
};
```

Later it can grow into a builder:

```js
const schema = h.schemas.model('Product')
  .field('name', { type: 'string', required: true })
  .field('price', { type: 'number', widget: 'currency' })
  .method('favorite', { layout: 'button', count_field: 'favorites' })
  .build();
```

Do not introduce this builder in the first implementation unless the wrapper API proves insufficient.

---

## Implementation Steps

### Step 1 — Add harness skeleton and cleanup ownership

Create:

- `tests/frontend/tests/helpers/frontend-harness.js`
- `tests/frontend/tests/helpers/harness/flush.js`
- `tests/frontend/tests/helpers/harness/permissions.js`

Initial pseudo-diff:

```diff
+ export async function createFrontendHarness(options = {}) {
+   const permissions = createPermissionHarness();
+   const transport = createTransportHarness();
+   const runtime = createRuntimeHarness({ transport });
+   const components = createComponentHarness({ runtime });
+   const schemas = createSchemaHarness();
+
+   return {
+     permissions,
+     transport,
+     runtime,
+     components,
+     schemas,
+     withPermissions(state) { permissions.set(state); return this; },
+     withFetchRoutes(routes) { transport.routes(routes); return this; },
+     async cleanup() { components.unmountAll(); transport.clearRoutes(); },
+   };
+ }
```

Keep cleanup local to harness-created state. Do not alter `tests/setup.js` yet.

### Step 2 — Implement transport route mocking

Create `tests/frontend/tests/helpers/harness/transport.js`.

Requirements:

- support exact strings and regex routes
- normalize method + URL enough for readable tests
- record fetch calls
- return Response-like objects compatible with current tests
- allow per-route status/text/json
- avoid global leakage by restoring/clearing in `cleanup()`

Pseudo-code:

```js
export function createTransportHarness() {
  const routes = [];
  const calls = [];

  global.fetch = vi.fn(async (url, options = {}) => {
    const method = options.method || 'GET';
    const urlString = String(url);
    calls.push({ method, url: urlString, options });

    const match = findRoute(routes, method, urlString);
    if (!match) return response({ error: 'Not found' }, { status: 404 });
    return response(match.data, match.options);
  });

  return { route, routes, clearRoutes, fetchCalls: () => calls.slice(), sent: () => sent.slice() };
}
```

### Step 3 — Implement schema fixture wrappers

Create `tests/frontend/tests/helpers/harness/schemas.js`.

First version should reuse existing fixtures:

```js
import {
  ProductSchema,
  CommentSchema,
  LikeSchema,
  makeProductData,
  makeProductListResponse,
} from '../../integration/helpers/mock-schemas.js';

export function createSchemaHarness() {
  return {
    product: (overrides = {}) => mergeSchema(ProductSchema, overrides),
    comment: (overrides = {}) => mergeSchema(CommentSchema, overrides),
    like: (overrides = {}) => mergeSchema(LikeSchema, overrides),
    productData: (id = 1, overrides = {}) => ({ ...makeProductData(id), ...overrides }),
    productList: makeProductListResponse,
  };
}
```

Use a small deep merge for `properties`, `ui`, `methods`, and `$defs`. Avoid a generalized schema DSL until at least two migrated tests need it.

### Step 4 — Implement runtime harness around `NTT`

Create `tests/frontend/tests/helpers/harness/runtime.js`.

Requirements:

- import `NTT` from aliased static runtime
- register schema through public `NTT.SCHEMA(schema)`
- return DynamicClass from `NTT.get(schema.__name__)`
- seed entities in the way closest to real runtime behavior
- expose stable `EntityHandle`

Entity handle shape:

```ts
type EntityHandle = {
  model: string;
  id: string | number;
  href: string;
  addr: string;
  value: object;
  instance: object;
};
```

Implementation note:

`NTT.js` stores DynamicClasses and instances behind static/private state. If there is no public reset API, the harness must avoid assuming a clean registry beyond the global Vitest setup. Prefer unique model names in harness self-tests if needed, or add a test-only reset helper only after confirming no public cleanup path exists.

Do **not** modify `NTT.js` for reset in the first pass unless failing isolation proves it necessary.

### Step 5 — Implement component mounting and semantic handles

Create:

- `tests/frontend/tests/helpers/harness/components.js`
- `tests/frontend/tests/helpers/queries/component-handle.js`
- `tests/frontend/tests/helpers/queries/entity-component.js`

Mounting requirements:

- create custom element by tag
- apply attributes and/or direct properties
- append to `document.body`
- wait for render lifecycle with `flushRender()`
- return handle object rather than raw element only

Generic handle:

```ts
type ComponentHandle = {
  el: HTMLElement;
  root(): ShadowRoot | HTMLElement;
  query(selector: string): Element | null;
  queryAll(selector: string): Element[];
  text(): string;
  remove(): void;
};
```

Entity component handle:

```ts
type EntityComponentHandle = ComponentHandle & {
  field(name: string): FieldHandle;
  method(name: string): MethodHandle;
  action(name: 'edit' | 'delete' | 'save' | string): ActionHandle;
};
```

Initial semantic query mapping can be pragmatic:

```js
field(name) {
  return wrap(
    root.querySelector(`[data-value="${name}"]`) ||
    root.querySelector(`[data-key="${name}"]`) ||
    root.querySelector(`[name="${name}"]`)
  );
}
```

Do not overfit to every component in phase 1. Start with enough for `ntx-item` contract coverage.

### Step 6 — Add harness self-tests

Create `tests/frontend/tests/helpers/frontend-harness.test.js`.

Cover the harness behavior itself:

| Harness area | Test |
|---|---|
| permissions | `withPermissions({ role: 'admin' })` updates mocked permission state |
| transport | route matching returns JSON and records calls |
| schemas | `schemas.product()` returns backend-shaped Product schema with overrides |
| runtime | `registerSchema(ProductSchema)` makes `NTT.get('Product')` available |
| components | `mount('ntx-item', ...)` appends and cleans up an element |

These tests should not assert product rendering details deeply; that belongs in migrated component contract tests.

### Step 7 — Migrate one vertical `ntx-item` contract slice

Create `tests/frontend/tests/components/ntx-item.contract.test.js`.

First contract:

```js
describe('ntx-item schema runtime contract', () => {
  it('renders Product fields and schema-declared methods from a registered schema', async () => {
    const h = await createFrontendHarness()
      .withPermissions({ authenticated: true, role: 'admin' });

    const schema = h.schemas.product();
    const Product = await h.runtime.registerSchema(schema);
    const product = h.runtime.seedEntity(Product, h.schemas.productData(1));

    const item = await h.components.mountEntity('ntx-item', product, {
      display: 'md',
      mode: 'display',
    });

    expect(item.field('name').text()).toContain('Test Product 1');
    expect(item.field('price').text()).toContain('$29.99');
    expect(item.method('favorite')).toBeVisible();

    await h.cleanup();
  });
});
```

Then remove or mark redundant only the directly equivalent shallow assertions from `ntx-item.test.js` if the replacement is clearly stronger. If not confident, keep both temporarily and note redundancy.

### Step 8 — Document harness usage in frontend test docs

Update documentation after implementation:

- `FRONTEND.md` frontend test section, or
- a new `tests/frontend/README.md` if one exists or is preferred during implementation.

Document:

- when to use the harness
- when not to use it
- how to add schema fixtures
- test placement guidance for component vs integration vs Playwright

---

## Migration Strategy

### Phase 1 — Introduce without disruption

- Add harness files and self-tests.
- Add one new contract test.
- Do not delete old tests unless exact redundancy is obvious.

### Phase 2 — Replace repeated setup in nearby tests

Target `ntx-item.test.js` first:

| Current cluster | Replacement |
|---|---|
| local Product schema | `h.schemas.product()` |
| local `createItem()` helper | `h.components.mountEntity()` |
| permission mocks in file | `h.withPermissions()` |
| field HTML string assertions | `item.field(name)` semantic assertions |
| method button string assertions | `item.method(name)` semantic assertions |

### Phase 3 — Expand to list/method/form integration

After `ntx-item` proves stable:

- `ntx-method.test.js`: generated method TX/call assertions through `transport.sent()` or captured `call()` behavior
- `ntx-list.test.js`: schema + list response + mounted list children
- `form.test.js`: use component/form query handles for DOM semantics
- `schema-bootstrap.test.js`: use runtime harness for schema registration assertions

---

## Test Commands

Run narrow checks first:

```bash
cd /workspace/tests/frontend && npx vitest run tests/helpers/frontend-harness.test.js
cd /workspace/tests/frontend && npx vitest run tests/components/ntx-item.contract.test.js
```

Then relevant component/generator checks:

```bash
cd /workspace/tests/frontend && npx vitest run tests/components/ntx-item.test.js tests/components/ntx-method.test.js tests/generators/form.test.js
```

Then full frontend unit suite:

```bash
cd /workspace/tests/frontend && npx vitest run
```

If harness changes touch test placement or docs only, Playwright is not required for phase 1. Run Playwright only after migrating browser unit-like coverage.

---

## Risks and Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Harness becomes a second frontend framework | Too much abstraction can hide behavior under test | Keep the public API explicit and grounded in repeated current needs |
| DynamicClass global state leaks between tests | `NTT` registry uses static/private state | Prefer unique schemas in harness self-tests; avoid broad reset hacks initially |
| Semantic queries overfit current markup | Query helper becomes brittle | Query by schema contract attributes first: `data-value`, `data-key`, method attrs |
| Transport harness conflicts with `tests/setup.js` fetch reset | Global fetch is already mocked per test | Install routes per harness and clear them in `cleanup()`; rely on global setup after each test |
| Permissions cache interacts with Formidable layout cache | `Formidable` caches by role | Migrated form tests must call `Formidable.clearCache()` or harness should expose optional cache clearing later |
| First contract test duplicates existing coverage | Temporary duplication increases suite size | Accept in phase 1; delete only direct redundant shallow assertions after confidence |

---

## Acceptance Criteria

- A new `createFrontendHarness()` exists under `tests/frontend/tests/helpers/`.
- Harness exposes `runtime`, `transport`, `components`, `permissions`, and `schemas` sub-harnesses.
- Harness self-tests pass.
- At least one new `ntx-item` contract test uses the harness end-to-end.
- The new contract test does not manually mock config/logging/permissions inside the file.
- The new contract test does not bypass component lifecycle with custom `value` property descriptors.
- Existing frontend unit tests still pass.
- Documentation explains when and how to use the harness.

---

## Non-Goals / Guardrails

- Do not add production-only test hooks to `NTT.js` unless isolation cannot be achieved otherwise.
- Do not rewrite all frontend tests in the first PR.
- Do not hide all selectors behind page-object-like abstractions in Vitest; semantic handles should map to schema/component contracts.
- Do not convert Playwright specs in this step.
- Do not change product behavior to satisfy the new harness unless a real regression is proven.

---

## Follow-Up Plans

This plan intentionally creates the foundation for later plans:

1. **Plan 2:** Formidable contract helper and string-test reduction.
2. **Plan 3:** Generated method wrapper and TX contract tests.
3. **Plan 4:** Migrate unit-like Playwright specs into Vitest contracts.
4. **Plan 5:** E2E semantic API/session/page-object layer.

---

## Critical Files for Implementation

- `tests/frontend/tests/helpers/frontend-harness.js`
- `tests/frontend/tests/helpers/harness/runtime.js`
- `tests/frontend/tests/helpers/harness/transport.js`
- `tests/frontend/tests/helpers/harness/components.js`
- `tests/frontend/tests/components/ntx-item.contract.test.js`
