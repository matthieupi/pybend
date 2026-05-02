# Issue 020 Plan — Frontend Route Alias Resolution

## ✅ Recommendation

Implement frontend aliases as a **canonicalization layer inside `NTT`**, with the
router remaining a pure route-string parser/resolver.

Backend issue 019 owns alias truth:

```json
{
  "__name__": "AgentActor",
  "canonical_name": "AgentActor",
  "__aliases__": ["Agent"],
  "__tablename__": "agents"
}
```

Frontend issue 020 should consume that metadata so this works:

```text
#Agent/1/@
  -> NTT.attach('Agent') fetches /Agent if needed
  -> backend returns canonical AgentActor schema
  -> NTT registers only one DynamicClass: AgentActor
  -> NTT maps Agent -> AgentActor
  -> alias waiters replay against AgentActor
  -> router mounts canonical attrs/ref:
       <ntx-agent ref="AgentActor/1" display="lg">
```

Do **not** create an `Agent` DynamicClass. Aliases are lookup keys only.

---

## 📍 Current State

| Area | Current behavior | Needed for issue 020 |
|---|---|---|
| `NTT.#prototypes` | `model -> DynamicClass | null` | Keep canonical-only DynamicClasses |
| `NTT.#waiting` | queues callbacks/TXs by requested model key | Replay alias queues when canonical schema arrives |
| `NTT.get(addr)` | direct map lookup by model segment | Resolve alias model segment to canonical before lookup |
| `NTT.attach(addr)` | fetches `/addr` when unknown | Fetch `/Alias`, then attach callback to canonical DC |
| `NTT.ATTACH()` | queues/fetches schema by route model | Queue alias requests and replay as canonical refs |
| `NTT.SCHEMA()` | uses `data.__name__` as canonical addr | Register `__aliases__`/`canonical_name` mapping |
| `Router.resolveRoute()` | uses parsed model verbatim in attrs/ref | Use canonical schema metadata for mount attrs/ref |
| `ntx-router` | schema accessor is `window.NTT.get(model)?.schema` | Works if `NTT.get(alias)` resolves to canonical DC |

---

## Architecture Invariants

1. **Backend remains authoritative.** The frontend only trusts aliases declared in
   schema metadata from issue 019.
2. **One DynamicClass per canonical model.** `Agent` must not create a separate
   class or cache from `AgentActor`.
3. **Alias waiters must replay.** If callers wait on `Agent`, they must be
   notified when `AgentActor` schema arrives.
4. **Router URLs may remain friendly.** The current hash may stay `#Agent/1/@`,
   but mounted component attrs should be canonical to avoid cache splits.
5. **Canonical routes remain unchanged.** `#AgentActor/1/@` and existing
   `#Product/...` routes continue to work.
6. **No frontend-only alias declaration.** No hardcoded alias map outside schema
   responses and preloaded schema tags.

---

## Target Contract

### `NTT` alias behavior

```js
NTT.attach('Agent', cb)
// if unknown: dispatch SCHEMA to http://localhost:5000/Agent
// when schema returns __name__='AgentActor', __aliases__=['Agent']:
//   cb receives DynamicClass AgentActor

NTT.get('Agent') === NTT.get('AgentActor')
NTT.get('Agent/1') === NTT.get('AgentActor/1')
NTT.has('Agent') === true
```

### Router/mount behavior

```js
parseRoute('Agent/1/@')
// remains route-preserving:
// { type: 'detail', model: 'Agent', id: '1', isViewRoute: true, view: null }

resolveRoute(parseRoute('Agent/1/@'), getSchema)
// with schema.__name__ = 'AgentActor'
// returns attrs.ref = 'AgentActor/1'
```

Collection routes canonicalize the mounted model attr:

```text
#Agent/@table -> <ntx-table model="AgentActor">
```

Member and action routes canonicalize refs:

```text
#Agent/1/@      -> ref="AgentActor/1"
#Agent/1/run    -> ref="AgentActor/1" method="run"
```

The hash stays user-facing/friendly unless the user navigates elsewhere.

---

## Implementation Plan

## Phase 1 — Add alias registry to `NTT`

Primary file:

- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`

Add a private alias map:

```js
static #aliases = new Map(); // alias -> canonical model name
```

Add helpers:

```js
static #canonicalModel(model) {
  return NTT.#aliases.get(model) || model;
}

static #canonicalAddr(addr) {
  if (!addr) return addr;
  const [model, ...rest] = String(addr).split('/');
  const canonical = NTT.#canonicalModel(model);
  return [canonical, ...rest].join('/');
}

static #schemaCanonicalName(schema) {
  return schema?.canonical_name || schema?.__name__;
}

static #schemaAliases(schema) {
  return Array.isArray(schema?.__aliases__) ? schema.__aliases__ : [];
}
```

Register schema aliases:

```js
static #registerSchemaAliases(schema) {
  const canonical = NTT.#schemaCanonicalName(schema);
  if (!canonical) return [];
  const aliases = NTT.#schemaAliases(schema).filter(a => a && a !== canonical);
  for (const alias of aliases) {
    NTT.#aliases.set(alias, canonical);
    if (NTT.#prototypes.get(alias) === null) {
      NTT.#prototypes.delete(alias); // alias is not a real DynamicClass key
    }
  }
  return aliases;
}
```

Important: keep `#prototypes` canonical-only after schema load.

### Update `has()`

```js
static has(addr) {
  const model = NTT.#canonicalModel(addr);
  return NTT.#prototypes.has(model);
}
```

### Update `get()`

```js
static get(addr) {
  if (!addr) return undefined;
  addr = String(addr);
  if (addr.includes('/')) {
    const [model, id] = addr.split('/');
    const DC = NTT.#prototypes.get(NTT.#canonicalModel(model));
    return DC ? DC.children.get(id) : undefined;
  }
  return NTT.#prototypes.get(NTT.#canonicalModel(addr)) || undefined;
}
```

### Update `attach()`

`attach('Agent')` should:

1. resolve alias if known,
2. signal canonical DC if already available,
3. otherwise queue under requested key (`Agent`) and fetch `/Agent`,
4. replay that queue when canonical `AgentActor` schema arrives.

Pseudo-diff:

```diff
- const DC = NTT.#prototypes.get(addr);
+ const requested = addr;
+ const canonical = NTT.#canonicalModel(requested);
+ const DC = NTT.#prototypes.get(canonical);

  if (DC) return DC.signal(callback);

- NTT.#prototypes.set(addr, null);
- NTT.#waiting.set(addr, [{_attachCallback: callback}]);
- if (!NTT.#consumePreloadedSchema(addr)) fetch /addr
+ NTT.#prototypes.set(requested, null);
+ NTT.#waiting.set(requested, [{_attachCallback: callback}]);
+ if (!NTT.#consumePreloadedSchema(requested)) fetch /requested
```

Do not set `#prototypes.set('AgentActor', null)` when fetching alias unless the
canonical name is already known. The canonical name is learned from the schema.

### Update `ATTACH()`

`ATTACH('Agent/1')` should queue by requested model if alias is unknown, but once
the alias is known it should dispatch through canonical `AgentActor`.

Pseudo-diff:

```diff
  const addr = typeof data === 'string' ? data : tx.data;
  const model = addr.split('/')[0];
- const DC = NTT.#prototypes.get(model);
+ const canonicalModel = NTT.#canonicalModel(model);
+ const DC = NTT.#prototypes.get(canonicalModel);

  if (DC) {
-   DC.ATTACH(addr, tx);
+   DC.ATTACH(NTT.#canonicalAddr(addr), tx);
  } else if (DC === null) {
-   NTT.#waiting.get(model).push(tx);
+   NTT.#waiting.get(canonicalModel).push(tx);
  } else {
    // unknown alias/canonical: queue by requested model and fetch requested schema
  }
```

For unknown aliases, queue under `model` and fetch `/model`. For known aliases,
queue under canonical if canonical schema is in flight.

---

## Phase 2 — Register aliases during `SCHEMA()` and replay all waiters

Primary file:

- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`

Update main schema handling:

```diff
- const addr = data.__name__;
+ const addr = data.canonical_name || data.__name__;
  const href = collectionHref(data, addr);
+ const aliases = NTT.#registerSchemaAliases(data);
```

After creating or retrieving the canonical DC:

```diff
  NTT.#replayWaiting(addr, DC);
+ for (const alias of aliases) {
+   NTT.#replayWaiting(alias, DC);
+ }
```

Update `$defs` registration to consume aliases too:

```js
const defName = value.canonical_name || value.__name__ || key;
const defAliases = NTT.#registerSchemaAliases(value);
const DC = prototype(defName, value, defHref);
NTT.#prototypes.set(defName, DC);
NTT.#replayWaiting(defName, DC);
for (const alias of defAliases) NTT.#replayWaiting(alias, DC);
```

### Replay canonicalization

Modify `#replayWaiting(addr, DC)` so queued TX data/targets that referenced the
alias become canonical before reaching `DynamicClass.ATTACH()`.

```diff
- repr.target = typeof repr.data === 'string' ? repr.data : addr;
+ if (typeof repr.data === 'string') repr.data = NTT.#canonicalAddr(repr.data);
+ repr.target = typeof repr.data === 'string' ? repr.data : DC.addr || DC.name;
```

For attach callbacks:

```js
DC.signal(entry._attachCallback);
```

The callback receives canonical `AgentActor` DynamicClass.

### Add `DynamicClass.addr`

Today some code uses `DynamicClass.addr`, but `prototype()` does not explicitly
define it. Add it while touching identity:

```js
Object.defineProperty(DynamicClass, 'addr', { value: className });
```

This improves traceability and avoids relying on function `name` for actor-like
class identity.

---

## Phase 3 — Canonicalize router mount attrs from schema metadata

Primary file:

- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`

The parser and builder should stay route-preserving. Do not rewrite
`parseRoute('Agent/1/@')` to `AgentActor/1/@`; it cannot know schema.

Add small pure helpers:

```js
function canonicalModel(schema, fallback) {
  return schema?.canonical_name || schema?.__name__ || fallback;
}

function modelRef(schema, model, id) {
  return `${canonicalModel(schema, model)}/${id}`;
}
```

Use them in `resolveRoute()`:

```diff
  const schema = getSchema(parsed.model);
+ const resolvedModel = canonicalModel(schema, parsed.model);

  // model route
- attrs: { model: parsed.model, ...passthrough }
+ attrs: { model: resolvedModel, ...passthrough }

  // detail/action route
- ref: parsed.model + '/' + parsed.id
+ ref: modelRef(schema, parsed.model, parsed.id)
```

Nested behavior recommendation for issue 020:

- canonicalize the **rendered child model** when its schema is resolved by alias,
- keep nested parent alias combinations deferred unless issue 019 implements
  nested alias routes.

So for root alias scope:

```text
#Agent/1/@         -> ref="AgentActor/1"
#Agent/@table      -> model="AgentActor"
```

For nested paths, do not add combinatorial alias expansion in this issue unless
backend issue 019 explicitly shipped those routes:

```text
#Product/1/Feedback/2  # only if Feedback alias route exists backend-side
```

---

## Phase 4 — `ntx-router` works via existing schema accessor

Primary file:

- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js`

The current accessor is already the right boundary:

```js
const getSchema = (model) => window.NTT?.get(model)?.schema || null;
```

If `NTT.get('Agent')` resolves to `AgentActor`, `ntx-router` does not need new
alias-specific behavior.

Only change this file if tests reveal one of these gaps:

1. the router renders before alias schema arrives and never re-renders, or
2. mounted component attrs need an async schema attach trigger.

Current likely behavior:

- Direct deep link `#Agent/1/@` may initially mount fallback `ntx-item` if schema
  is not loaded.
- The mounted component `ref="AgentActor/1"` can then drive `NTT.attach()` once
  schema access is resolved.

If tests show no re-render after schema arrival, add a small alias/schema attach
bridge in `ntx-router`:

```js
const parsed = parseRoute(this.#router.current);
if (parsed?.model && !window.NTT?.get(parsed.model)) {
  window.NTT?.attach(parsed.model, () => this.render());
}
```

Prefer avoiding this unless necessary; `NTT` should remain the primary alias
resolution owner.

---

## Test Plan

## Phase 1 Tests — `NTT` alias registry and lookup

Primary file:

- `tests/frontend/tests/core/NTT.test.js`

Add a focused describe block:

```js
describe('backend route aliases', () => { ... })
```

Tests:

1. `SCHEMA()` registers only canonical DynamicClass and maps aliases:

```js
const schema = {
  __name__: 'AgentActor',
  canonical_name: 'AgentActor',
  __aliases__: ['Agent'],
  __tablename__: 'agents',
  properties: { id: { type: 'integer' }, name: { type: 'string' } },
  methods: {},
};
NTT.SCHEMA(schema);

expect(NTT.get('Agent')).toBe(NTT.get('AgentActor'));
expect(NTT.has('Agent')).toBe(true);
```

2. Alias instance lookup resolves to canonical cache:

```js
const DC = NTT.get('AgentActor');
DC.READ([{ id: 1, name: 'A', $id: 'http://localhost:5000/AgentActor/1' }]);
expect(NTT.get('Agent/1')).toBe(NTT.get('AgentActor/1'));
```

3. `attach('Agent')` dispatches schema fetch to `/Agent` when alias is unknown.

Use a spy on `matrix.dispatch` or existing test helper pattern:

```js
NTT.attach('FreshAlias', cb);
expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({
  name: 'SCHEMA',
  target: 'http://localhost:5000/FreshAlias',
}));
```

4. Alias attach callback replays when canonical schema arrives:

```js
const cb = vi.fn();
NTT.attach('QueuedAgent', cb);
NTT.SCHEMA({ __name__: 'QueuedAgentActor', canonical_name: 'QueuedAgentActor', __aliases__: ['QueuedAgent'], ... });
expect(cb).toHaveBeenCalledWith(NTT.get('QueuedAgentActor'));
```

5. Alias `ATTACH('Agent/1')` replays as canonical instance attach:

```js
NTT.ATTACH('QueuedAgent/1', tx);
NTT.SCHEMA(agentActorSchema);
// assert the canonical DC has pending/fetch behavior for id 1, not a separate Agent prototype
```

6. `$defs` aliases resolve:

```js
$defs: {
  AgentActor: { __name__: 'AgentActor', __aliases__: ['Agent'], ... }
}
```

Expected:

```js
NTT.get('Agent') === NTT.get('AgentActor')
```

## Phase 2 Tests — Router pure resolution with aliases

Primary file:

- `tests/frontend/tests/core/route-functions.test.js`

Add tests without changing parser semantics:

```js
it('alias collection routes resolve to canonical model attrs', () => {
  const schema = { __name__: 'AgentActor', canonical_name: 'AgentActor', __aliases__: ['Agent'], ui: { renderer: { table: 'ntx-agent-table' } } };
  const r = resolveRoute(parseRoute('Agent/@table'), () => schema);
  expect(r.attrs.model).toBe('AgentActor');
});

it('alias member view routes resolve to canonical refs', () => {
  const schema = { __name__: 'AgentActor', canonical_name: 'AgentActor', __aliases__: ['Agent'], ui: { renderer: { item: 'ntx-agent' } } };
  const r = resolveRoute(parseRoute('Agent/1/@item'), () => schema);
  expect(r.attrs.ref).toBe('AgentActor/1');
});

it('alias action routes resolve to canonical refs without changing route parse', () => {
  const schema = { __name__: 'AgentActor', methods: { run: {} } };
  const parsed = parseRoute('Agent/1/run');
  expect(parsed.model).toBe('Agent');
  expect(resolveRoute(parsed, () => schema).attrs.ref).toBe('AgentActor/1');
});
```

Also test canonical routes unchanged:

```js
resolveRoute(parseRoute('AgentActor/1/@'), () => schema).attrs.ref === 'AgentActor/1'
```

## Phase 3 Tests — `ntx-router` DOM mounting aliases

Primary file:

- `tests/frontend/tests/components/ntx-router.test.js`

Tests:

1. Alias collection deep link mounts canonical model attr:

```text
window.location.hash = '#Agent/@table'
window.NTT.get('Agent') -> { schema: canonical AgentActor schema }
mounted <ntx-agent-table model="AgentActor">
```

2. Alias member deep link mounts canonical ref:

```text
window.location.hash = '#Agent/1/@item'
mounted <ntx-agent ref="AgentActor/1" display="lg">
```

3. Alias method route mounts canonical ref and method attr:

```text
#Agent/1/run -> ref="AgentActor/1" method="run"
```

4. Canonical route still mounts unchanged:

```text
#AgentActor/1/@item -> ref="AgentActor/1"
```

If async schema loading is added to `ntx-router`, add a test proving an alias
deep link re-renders after `NTT.attach(alias)` callback fires.

---

## Edge Cases and Decisions

| Case | Decision |
|---|---|
| `NTT.get('Agent')` before schema fetched | `undefined` |
| `NTT.attach('Agent')` before schema fetched | queue under `Agent`, fetch `/Agent` |
| schema arrives as `AgentActor` with `__aliases__=['Agent']` | create only `AgentActor`, map `Agent -> AgentActor`, replay `Agent` waiters |
| schema arrives without declaring requested alias | do not invent alias; canonical schema registers normally |
| `NTT.get('Agent/1')` after alias known | same instance as `AgentActor/1` |
| router `parseRoute('Agent/1/@')` | preserves `model:'Agent'` |
| router `resolveRoute(...)` with schema | emits canonical `model`/`ref` attrs |
| nested alias routes | defer unless backend 019 implements nested alias combinations |

---

## Risks and Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Duplicate DynamicClasses | Splits caches and watchers | Keep `#prototypes` canonical-only; aliases live in `#aliases` |
| Lost alias waiters | Components waiting on `Agent` never define | Replay `#waiting.get(alias)` after schema alias registration |
| Friendly hash causes alias refs | `ref="Agent/1"` can fetch alias paths and split identity | Router emits canonical attrs once schema is known |
| Premature frontend aliases | Diverges from backend source of truth | Only register aliases from `schema.__aliases__` |
| Async router first render fallback | Deep link may mount fallback before schema arrives | Add router attach/re-render bridge only if tests prove needed |
| Nested alias ambiguity | Parent/child aliases multiply route forms | Defer nested alias frontend support until backend routes are explicit |

---

## Verification Commands

```bash
cd /workspace/tests/frontend && npx vitest run \
  tests/core/NTT.test.js \
  tests/core/route-functions.test.js \
  tests/components/ntx-router.test.js
```

Optional broader frontend check:

```bash
cd /workspace/tests/frontend && npx vitest run
```

---

## Critical Files

- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`
- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js`
- `tests/frontend/tests/core/NTT.test.js`
- `tests/frontend/tests/core/route-functions.test.js`
- `tests/frontend/tests/components/ntx-router.test.js`
