# Test Failure Triage — P0 to P2 Execution Plan

## ✅ Recommendation

Execute recovery in this order:

```text
P-1 Contract triage gate (handled separately)
        |
        v
P0 Grants users/auth actor-routing storage
        |
        v
P1 Frontend transport contract cleanup
        |
        v
P2 NTT/DynamicClass entity lifecycle recovery
```

This plan assumes **P-1 is being handled by another agent** and acts as a mandatory gate before each slice below.

## Current execution status

| Phase | Status | Notes |
|---|---|---|
| `P0` Grants users/auth actor-routing storage | ✅ resolved | actor-routing Matrix/model storage synchronization fixed |
| `P1` Frontend transport contract cleanup | ✅ resolved | transport tests/docs aligned to current Socket contract |
| `P2` NTT/DynamicClass entity lifecycle recovery | ✅ resolved (tracked scope) | core runtime boundary suites now green |

The remaining broad failures now sit outside this document's completed scope and are better treated as follow-on clusters (threads bootstrap, method response contract decisions spilling into UI, Formidable/UI drift, browser-level drift).

The core operating rule for P0–P2 is:

> Do not change product code merely to satisfy an old test. First confirm whether the failing assertion still reflects the intended contract.

---

## 1. Scope and Intent

This plan covers only:

- **P0** — grants users/auth actor-routing storage/bootstrap failures
- **P1** — frontend transport layer failures (`Socket`, `NetworkAdapter`, transport docs/tests)
- **P2** — frontend entity runtime failures (`NTT`, `DynamicClass`, schema bootstrap, instance lifecycle)

This plan intentionally does **not** cover:

- P-1 contract triage workflow itself
- P3+ UI/browser-level contract recovery
- broad test-suite hardening beyond what is necessary to stabilize P0–P2

---

## 2. Operating Model

## 2.1 P-1 Gate Requirement

Before beginning any slice in this document, require a short contract note from the P-1 stream:

```md
Contract decision:
- Intended behavior:
- Evidence:
- Failure type:
  - product regression | stale test | test infrastructure | unresolved
- Change target:
  - product code | tests | docs | fixtures
- Regression risk:
```

If P-1 has **not** classified the slice yet, do not start implementation.

## 2.2 Change Hierarchy

Use this precedence when deciding what to change:

1. **If current architecture/docs/runtime clearly define the intended behavior** → fix product code.
2. **If tests/documentation are stale relative to an intentional implementation** → update tests and docs, avoid product regression.
3. **If the failure comes from fixtures, global state, or mocks** → fix test infrastructure first.
4. **If intent is unclear** → stop and escalate to a contract decision.

## 2.3 Verification Discipline

For each slice:

- run the **narrowest reproducer first**
- fix only one failure cluster at a time
- rerun the **cluster boundary tests**
- only then expand to adjacent suites

---

## 3. Current Diagnosis Summary

| Phase | Problem surface | Likely classification | Why it matters |
|---|---|---|---|
| P0 | grants auth/users actor routing returns 500s | likely product/bootstrap regression | blocks grants auth, CRUD, streaming setup, E2E bootstrap |
| P1 | Socket + NetworkAdapter tests expect old API | likely stale tests/docs | largest single frontend failure cluster |
| P2 | NTT/DynamicClass registry/lifecycle drift | mixed: some regressions, some contract decisions | central entity/runtime layer for most frontend behavior |

Cross-cutting note:

- P0 looks like **real backend/bootstrap breakage**.
- P1 looks like **intentional runtime simplification with stale tests/docs**.
- P2 likely contains **both** real drift and stale assumptions.

---

## 4. Architecture View

```text
Backend grants auth flow

HTTP /users/login
   -> NetworkAPI route
   -> TX(name='login', target='users')
   -> Matrix child lookup
   -> User.login()
   -> BaseUser.login() calls cls.list()
   -> StorableMixin.list()
   -> cls.storage.list(...)

Failure if actor-routed User class is stale or storage=None.
```

```text
Frontend runtime dependency chain

Transport (Socket / NetworkAdapter)
        |
        v
Matrix remote dispatch
        |
        v
NTT schema bootstrap
        |
        v
DynamicClass instance registry
        |
        v
Form/method/router/browser UI
```

This is why P1 must precede P2, and P2 must precede broader UI recovery.

---

## 5. P0 — Grants Users/Auth Actor-Routing Storage Recovery

**Status:** ✅ Resolved

## 5.1 Goal

Restore grants auth and user routes so that actor-routed `User` methods execute against the correct registered model classes and test storage.

## 5.2 Current Evidence

### Grants app bootstraps actor routing

File: `examples/grants/main.py`

```python
app = create_app(
    models=[User, Grant, Source, WebTools, AgentTool, AgentActor],
    join_models=[(AgentActor, AgentTool)],
    storage=storage,
    routing='actor',
)
```

### Grants tests mutate storage after app import

File: `examples/grants/tests/conftest.py`

```python
for model_cls in registered_models.values():
    if hasattr(model_cls, 'set_storage'):
        model_cls.set_storage(storage)
        model_cls.create_table()
```

### Base auth methods call `cls.list()`

File: `packages/n3tx-core/src/n3tx_core/models/base_user.py`

```python
users = cls.list()
existing = cls.list()
```

### Likely crash site

File: `packages/n3tx-core/src/n3tx_core/models/storable_mixin.py`

```python
cls.storage.list(...)
```

Observed failure:

```text
'NoneType' object has no attribute 'list'
```

## 5.3 Working Hypothesis

The grants test harness updates storage on `registered_models`, but Matrix may still be routing to a stale or differently registered actor class.

The critical invariant that must hold is:

```text
registered_models['users']
    is matrix.children['users']
    and both point at a class with non-null storage
```

## 5.4 Files in Scope

| Concern | Files |
|---|---|
| grants app bootstrap | `examples/grants/main.py` |
| grants user model | `examples/grants/models/user.py` |
| grants test harness | `examples/grants/tests/conftest.py` |
| app registration flow | `packages/n3tx-core/src/n3tx_core/app.py` |
| model registrar | `packages/n3tx-core/src/n3tx_core/utils/registrar.py` |
| matrix registration | `packages/n3tx-actors/src/n3tx_actors/matrix.py` |
| actor child registration | `packages/n3tx-actors/src/n3tx_actors/actor.py` |
| actor CRUD/custom dispatch | `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py` |
| HTTP→TX route bridge | `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` |

## 5.5 P0 Execution Slices

### Slice P0.0 — Revalidate the smallest failing surface

Run:

```bash
python3 -m pytest examples/grants/tests/test_boot.py
python3 -m pytest examples/grants/tests/test_auth_flow.py
```

Purpose:

- confirm current failure mode
- separate 500s from contract-shape mismatches
- avoid conflating auth bootstrap issues with token envelope drift

### Slice P0.1 — Add identity/storage pinning test

Add a new focused regression test in `examples/grants/tests/`:

```python
def test_actor_registered_user_has_test_storage():
    from n3tx_core.utils.registrar import registered_models
    from n3tx_actors.matrix import matrix

    user_cls = registered_models['users']
    routed = matrix.children.get('users')

    assert user_cls.storage is not None
    assert routed is user_cls
    assert routed.storage is not None
```

Interpretation:

| Failure | Meaning | Next move |
|---|---|---|
| `routed is None` | actor model not registered into Matrix | fix actor boot registration |
| `routed is not user_cls` | stale class identity in Matrix | fix app/fixture sync |
| `storage is None` | storage injection missing | fix registration/bootstrap |
| all pass but auth still fails | investigate route/custom dispatch or data shape | continue deeper |

### Slice P0.2 — Make actor registration deterministic in app bootstrap

Preferred fix target: `packages/n3tx-core/src/n3tx_core/app.py`

After `registered_models` are fully applied and before/while actor routes are mounted, explicitly sync actor models into Matrix.

Representative shape:

```python
if self._routing == 'actor':
    from n3tx_actors.actor import Actor
    from n3tx_actors.matrix import matrix

    for model_cls in registered_models.values():
        if isinstance(model_cls, type) and issubclass(model_cls, Actor):
            matrix.register(model_cls)
```

Design goal:

- registration must not depend on import timing or metaclass side effects
- actor-routing should use the same live class objects that the registrar configured

### Slice P0.3 — If fixture rewiring remains necessary, sync Matrix in tests too

If the grants fixture deliberately reassigns storage after app import, then after `_setup_test_db(db_path)` it should also refresh Matrix children for actor models.

Representative helper:

```python
def _sync_actor_models_to_matrix():
    from n3tx_actors.actor import Actor
    from n3tx_actors.matrix import matrix

    for model_cls in registered_models.values():
        if isinstance(model_cls, type) and issubclass(model_cls, Actor):
            matrix.register(model_cls)
```

Use only if the app-level fix is insufficient.

### Slice P0.4 — Tighten auth behavior regressions

Once storage identity is fixed, add or tighten tests for:

- `/users` list does not 500
- login with correct credentials returns 200
- login with wrong credentials returns 401
- register new user returns 200/201
- duplicate email returns 409

Representative tests:

```python
def test_users_list_does_not_500(client):
    resp = client.get('/users')
    assert resp.status_code != 500

def test_login_with_correct_credentials_returns_token(client):
    resp = client.post('/users/login', json={
        'email': 'alice@example.com',
        'password': 'alice123',
    })
    assert resp.status_code == 200
```

### Slice P0.5 — Resolve token envelope deliberately

Possible responses:

```json
{"token": "...", "user": {...}}
```

or:

```json
{"data": {"token": "...", "user": {...}}, "_debug": {...}}
```

Decision table:

| Option | Meaning | Default |
|---|---|---|
| disable debug in test env | auth always top-level token | acceptable if tests should reflect business contract only |
| accept both in helpers | tolerant helper extraction | best compatibility default |
| rewrite product response | auth endpoints special-case debug wrapping | avoid unless explicitly desired |

Default recommendation:

- keep current product behavior unless P-1 says it is wrong
- make grants test helpers accept both token shapes

## 5.6 P0 Verification

Run in this order:

```bash
python3 -m pytest examples/grants/tests/test_boot.py
python3 -m pytest examples/grants/tests/test_auth_flow.py
python3 -m pytest examples/grants/tests/test_grants_crud.py
python3 -m pytest examples/grants/tests/
```

Success criteria:

- no `NoneType.storage.list` failures
- auth routes no longer 500
- `/users` works in actor-routing mode
- remaining failures, if any, are about contract shape or downstream features, not bootstrap

---

## 6. P1 — Frontend Transport Contract Cleanup

**Status:** ✅ Resolved

## 6.1 Goal

Align transport tests and docs with the **current intended** transport design: a simplified TX-native `Socket` and a `NetworkAdapter` that prefers WebSocket when ready and falls back to HTTP otherwise.

## 6.2 Current Evidence

### Current `Socket.js`

File: `packages/n3tx-core/src/n3tx_core/static/core/transport/Socket.js`

Public shape appears to be:

```javascript
constructor(url)
connect(token)
send(tx)
close()

url
ws
ready
onmessage
```

### Current `NetworkAdapter.js`

File: `packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js`

WS path:

```javascript
if (this.socket && this.socket.ready) {
  const tx = event instanceof TX ? event : new TX(event);
  this.socket.send(tx);
  return;
}
```

### Current tests expect legacy Socket API

File: `tests/frontend/tests/transport/Socket.test.js`

Tests expect:

- `state`
- `ttl`
- `retries`
- `sendEvent()`
- `sendMessage()`
- `disconnect()`
- `watchdog()`
- `Socket.resources`
- `Socket.defaultSocket`

### Current docs are stale

File: `docs/frontend/TRANSPORT.md`

Docs still describe:

```javascript
new Socket(url, targets={}, ttl=1000)
socket.sendEvent(...)
socket.setTarget(...)
socket.watchdog()
```

## 6.3 Working Hypothesis

P1 is primarily a **contract/documentation/test drift** problem, not a product regression.

Default architectural decision:

> Keep the simplified TX-native Socket. Do not restore the legacy state-machine API unless P-1 discovers an active dependency on it.

## 6.4 Files in Scope

| Concern | Files |
|---|---|
| current socket impl | `packages/n3tx-core/src/n3tx_core/static/core/transport/Socket.js` |
| current adapter impl | `packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js` |
| stale transport docs | `docs/frontend/TRANSPORT.md` |
| stale socket tests | `tests/frontend/tests/transport/Socket.test.js` |
| adapter tests | `tests/frontend/tests/transport/NetworkAdapter.test.js` |
| nearby transport integrations | `tests/frontend/tests/integration/network-entity-sync.test.js`, `actor-messaging.test.js`, `method-response-flow.test.js` |

## 6.5 P1 Execution Slices

### Slice P1.0 — Confirm P-1 result for transport cluster

Expected classification:

| Surface | Expected classification |
|---|---|
| `Socket.test.js` state-machine expectations | stale tests |
| `TRANSPORT.md` old Socket docs | stale docs |
| `NetworkAdapter.test.js` expecting `sendEvent()` | stale tests |
| HTTP fallback behavior | still valid contract |

### Slice P1.1 — Rewrite `Socket.test.js` around current contract

Replace the old API expectations with tests for:

- constructor initializes `url`, `ws=null`, `ready=false`, `onmessage=null`
- `connect(token)` creates a WebSocket, appending `?token=...` when present
- `onopen` sets `ready=true`, flushes queue, resets reconnect delay, starts heartbeat
- `send(tx)` serializes `tx.repr()` when connected
- `send(tx)` queues payload when disconnected
- `onmessage` parses JSON and forwards non-heartbeat messages to `onmessage`
- invalid JSON logs error
- `close()` disables reconnect and clears timers
- reconnect scheduling grows backoff correctly

Representative test shape:

```javascript
it('send(tx) queues while disconnected', () => {
  const socket = new Socket('ws://localhost:5000/ws');
  socket.send({ name: 'READ' });
  expect(socket._queue).toHaveLength(1);
});
```

### Slice P1.2 — Update `NetworkAdapter.test.js` WS expectations

Current stale expectation:

```javascript
expect(socket.sendEvent).toHaveBeenCalled()
```

Target expectation:

```javascript
expect(socket.send).toHaveBeenCalled()
```

Update fake socket to current shape:

```javascript
class FakeSocket {
  constructor(url) {
    this.url = url;
    this.ready = true;
    this.onmessage = null;
    this.send = vi.fn();
    this.connect = vi.fn();
  }
}
```

Also add verification for:

- `_initWebSocket()` calls `connect(token)`
- `socket.onmessage(data)` forwards to `matrix.dispatch(data)`
- when `socket.ready` is false, adapter still uses HTTP fallback

### Slice P1.3 — Update transport docs to current runtime

Revise `docs/frontend/TRANSPORT.md` to describe:

```javascript
const socket = new Socket(wsUrl);
socket.onmessage = (data) => matrix.dispatch(data);
socket.connect(token);
socket.send(tx);
socket.close();
```

Explicitly remove or mark obsolete:

- `Socket.resources`
- `Socket.defaultSocket`
- `sendEvent`
- `sendMessage`
- `disconnect`
- `watchdog`
- target registration API

Also document:

- `sendStream()` is deprecated
- streaming primarily flows via `HTTP.stream()` and TX envelopes
- WebSocket is optional, not the default runtime dependency

## 6.6 P1 Verification

Run:

```bash
cd tests/frontend && npx vitest run \
  tests/transport/Socket.test.js \
  tests/transport/NetworkAdapter.test.js \
  tests/integration/network-entity-sync.test.js \
  tests/integration/actor-messaging.test.js \
  tests/integration/method-response-flow.test.js
```

Success criteria:

- transport tests describe the current product contract
- no `this.socket.connect is not a function`
- no stale `sendEvent()` assumptions remain
- HTTP fallback remains green

---

## 7. P2 — NTT / DynamicClass Entity Lifecycle Recovery

**Status:** ✅ Resolved (tracked scope)

## 7.1 Goal

Stabilize the frontend entity runtime so that schema bootstrap, instance registration, populated normalization, CRUD lifecycle, and method response behavior all operate consistently.

## 7.2 Current Evidence

### DynamicClass stores instances in a Map

File: `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`

```javascript
static instances = new Map();
```

### Current code normalizes IDs to strings

```javascript
const id = String(value.id);
DynamicClass.instances.has(id)
```

### Tests expect numeric compatibility

Examples in:

- `tests/frontend/tests/core/NTT.test.js`
- `tests/frontend/tests/core/DynamicClassFunctor.test.js`
- `tests/frontend/tests/integration/schema-bootstrap.test.js`
- `tests/frontend/tests/integration/entity-lifecycle.test.js`
- `tests/frontend/tests/integration/method-execution.test.js`

They expect:

```javascript
DC.instances.has(1)
DC.instances.get(1)
NTT.get('Product/1')
```

### `_response_()` currently no-ops on simple method responses

```javascript
if (!data || typeof data !== 'object') return;
```

Tests expect simple success responses to trigger `pull()`.

### Schema bootstrap currently derives URLs from `config.API_URL`

This can drift from authoritative mock schema URLs or nested `$id` values.

## 7.3 Working Hypothesis

P2 is a mixed cluster:

- real runtime drift in instance lookup/response semantics
- stale assumptions in some tests around identity/API base behavior

Default decisions:

| Question | Default answer |
|---|---|
| numeric vs string instance keys | support both at the `instances` boundary |
| internal actor address format | keep string-based |
| method response fallback | preserve local updates when possible, otherwise pull |
| URL authority | prefer schema-provided identifiers where available |

## 7.4 Files in Scope

| Concern | Files |
|---|---|
| entity runtime | `packages/n3tx-core/src/n3tx_core/static/core/NTT.js` |
| transport dependency | `packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js` |
| core tests | `tests/frontend/tests/core/NTT.test.js`, `DynamicClassFunctor.test.js` |
| integration tests | `tests/frontend/tests/integration/schema-bootstrap.test.js`, `entity-lifecycle.test.js`, `method-execution.test.js`, `nested-entities.test.js` |

## 7.5 P2 Execution Slices

### Slice P2.0 — Confirm P-1 contract decisions

Required before implementation:

- whether `instances.get(1)` is intended public/test-facing behavior
- whether `_response_()` should still pull on simple success responses
- whether schema `$id` should win over `config.API_URL`
- whether generated instance methods should default to `_response_` inbox routing

### Slice P2.1 — Introduce key-normalized instance access

Goal:

```javascript
DC.instances.get(1) === DC.instances.get('1')
DC.instances.has(1) === DC.instances.has('1')
DC.instances.delete(1) === DC.instances.delete('1')
```

Preferred shape:

```javascript
class InstanceMap extends Map {
  _key(key) { return key == null ? key : String(key); }
  get(key) { return super.get(this._key(key)); }
  has(key) { return super.has(this._key(key)); }
  set(key, value) { return super.set(this._key(key), value); }
  delete(key) { return super.delete(this._key(key)); }
}
```

Then:

```javascript
static instances = new InstanceMap();
```

Why this is preferable:

- preserves internal actor-string addressing
- avoids global ID-type rewrites
- gives tests and surrounding code numeric compatibility

### Slice P2.2 — Collapse instance upsert logic into one helper

Current instance registration behavior is duplicated across:

- `registerInstance()`
- `DynamicClass.READ`
- `DynamicClass.CREATE`
- populated normalization flows

Refactor to one helper:

```javascript
function upsertInstance(DC, data) {
  if (!data || data.id === undefined) return undefined;
  normalizePopulated(data, DC._schema);
  const existing = DC.instances.get(data.id);
  if (existing) {
    existing.update(data);
    return existing;
  }
  return new DC(data);
}
```

Benefits:

- one canonical ID normalization path
- one canonical normalization path
- lower entropy for subsequent runtime fixes

### Slice P2.3 — Restore `_response_()` fallback semantics

Target behavior:

1. **Action response with `_field`** → update local array field in place.
2. **Entity response with `id`** → update local instance directly.
3. **Simple success response / string / empty payload** → call `pull()`.

Representative target shape:

```javascript
DynamicClass.prototype._response_ = function(data, tx) {
  if (data && typeof data === 'object' && data.action && data._field && data.id !== undefined) {
    updateLocalActionField(...);
    return;
  }

  if (data && typeof data === 'object' && data.id !== undefined) {
    normalizePopulated(data, DynamicClass._schema);
    this.update(data);
    return;
  }

  return this.pull();
};
```

This preserves newer efficient behavior while recovering the authoritative refresh fallback older tests rely on.

### Slice P2.4 — Prefer schema-provided identifiers where possible

Current bootstrap builds URLs from `config.API_URL`:

```javascript
const href = data.__tablename__
  ? `${config.API_URL}/${data.__tablename__}`
  : `${config.API_URL}/${addr}`;
```

Plan:

- use schema `$id` as the authoritative schema URL when present
- use nested entity `$id` for instance hrefs (already partially done)
- derive collection href from declared table/schema only when necessary

This should reduce base-URL drift between jsdom defaults and schema fixtures.

### Slice P2.5 — Fix generated schema method payload mapping

Current generated method logic is suspicious because it indexes positional args by parameter name.

Target behavior:

- if called with a single object → use it as named payload
- otherwise map positional args to parameter order
- validate the resulting payload against schema definitions
- optionally default instance-method responses to `_response_`

Representative shape:

```javascript
DynamicClass.prototype[method] = function(...args) {
  const params = Object.keys(definition.parameters || {});
  const payload =
    args.length === 1 && typeof args[0] === 'object' && !Array.isArray(args[0])
      ? args[0]
      : Object.fromEntries(params.map((name, i) => [name, args[i]]));

  validatePayload(payload, definition.parameters);
  this.call(method, payload, { inbox: '_response_' });
};
```

### Slice P2.6 — Stabilize preloaded schema script contract

Current runtime consumes:

```javascript
<script data-ntx-schema="Model">{json}</script>
```

Tests currently create executable scripts with JSON text, which jsdom may parse as JS.

Preferred path:

- update tests to use `type="application/json"`
- optionally make runtime tolerant of both plain and JSON-typed script tags

Recommended test shape:

```javascript
const script = document.createElement('script');
script.type = 'application/json';
script.setAttribute('data-ntx-schema', 'TestModel');
script.textContent = JSON.stringify(schema);
```

## 7.6 P2 Verification

Run in layers.

### Core runtime first

```bash
cd tests/frontend && npx vitest run \
  tests/core/NTT.test.js \
  tests/core/DynamicClassFunctor.test.js
```

### Then lifecycle integrations

```bash
cd tests/frontend && npx vitest run \
  tests/integration/schema-bootstrap.test.js \
  tests/integration/entity-lifecycle.test.js \
  tests/integration/method-execution.test.js \
  tests/integration/nested-entities.test.js
```

### Then nearby runtime integrations

```bash
cd tests/frontend && npx vitest run \
  tests/integration/actor-messaging.test.js \
  tests/integration/network-entity-sync.test.js \
  tests/integration/list-item-interaction.test.js \
  tests/integration/method-response-flow.test.js
```

Success criteria:

- `instances.get(1)` and `instances.get('1')` both work
- `NTT.get('Product/1')` works reliably
- `READ`, `CREATE`, `DELETE` have stable registry semantics
- method responses update locally or pull correctly
- populated children normalize into href arrays and register child instances

---

## 8. Risks and Guardrails

| Risk | Mitigation |
|---|---|
| accidentally reintroducing obsolete product behavior to satisfy stale tests | require P-1 classification before each slice |
| mixing P0 bootstrap bugs with auth envelope drift | verify 500s separately before response-shape changes |
| overcorrecting Socket into legacy API | keep transport cleanup centered on current runtime |
| breaking actor routing by changing ID semantics globally | keep internal actor addresses string-based; normalize only `instances` boundary |
| starting UI repair too early | do not begin P3+ until P1 and P2 verification sets are green |

### Do not do these

- Do not restore the full legacy Socket state machine just because old tests reference it.
- Do not rewrite auth product responses before deciding whether the envelope is intentional.
- Do not globally convert actor identifiers from string to numeric.
- Do not weaken failing tests with broad permissive assertions.
- Do not jump to forms/router/topbar/browser UI before runtime substrate is stable.

---

## 9. Execution Checklist

## P0

- [ ] Re-run grants boot/auth failures
- [ ] Add actor/storage identity regression test
- [ ] Fix app-level actor registration determinism
- [ ] Sync fixture if app-level fix is insufficient
- [ ] Tighten auth behavior tests
- [ ] Resolve token extraction shape deliberately
- [ ] Re-run grants suite

## P1

- [ ] Confirm transport contract classification from P-1
- [ ] Rewrite `Socket.test.js` around current API
- [ ] Update `NetworkAdapter.test.js` WS expectations
- [ ] Update `docs/frontend/TRANSPORT.md`
- [ ] Re-run transport/integration boundary tests

## P2

- [ ] Confirm identity/response/url decisions from P-1
- [ ] Introduce normalized `instances` map behavior
- [ ] Collapse instance upsert logic
- [ ] Restore `_response_()` fallback behavior
- [ ] Prefer schema-provided identifiers where possible
- [ ] Fix generated method payload mapping
- [ ] Stabilize preloaded schema script contract
- [ ] Re-run core and integration runtime suites

---

## 10. Critical Files for Implementation

- `examples/grants/tests/conftest.py`
- `packages/n3tx-core/src/n3tx_core/app.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-core/src/n3tx_core/static/core/transport/Socket.js`
- `packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js`
- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`
- `tests/frontend/tests/transport/Socket.test.js`
- `tests/frontend/tests/transport/NetworkAdapter.test.js`
- `docs/frontend/TRANSPORT.md`

---

## 11. Expected Outcome

At the end of P0–P2:

- grants auth/bootstrap failures should no longer block backend and E2E work
- transport tests should describe the actual runtime contract
- NTT/DynamicClass should have a stable, explicit instance lifecycle contract
- subsequent UI/browser failures should be far easier to classify as real regressions vs stale contract tests
