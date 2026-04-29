# Test Failure Triage Action Plan

## Recommendation

Start with **P-1: contract triage** before touching production code. Many failures come from tests that have not been maintained while framework contracts evolved. Each cluster must first be classified as a **real product regression**, **stale test contract**, **test infrastructure issue**, or **unresolved product decision**.

## Current phase status

| Phase | Status | Notes |
|---|---|---|
| `P-1` Contract triage | active | still the required gate before any code/test contract change |
| `P0` Grants users/auth storage registration | ✅ resolved | grants auth/bootstrap storage regression fixed |
| `P1` Socket + NetworkAdapter contract | ✅ resolved | transport tests/docs aligned to TX-native Socket contract |
| `P2` NTT/DynamicClass lifecycle | ✅ resolved (tracked scope) | runtime boundary suites for schema/bootstrap/lifecycle/entity messaging now green |
| `P3` Formidable + method/comment/favorite UI | next | current highest frontend Vitest cluster |
| `P4` Router/topbar/navigation shell | pending | browser-visible contract drift remains |
| `P5` Suite hardening | pending | worker OOMs / fixture drift still remain |

After that gate, start implementation with **P0: grants users/auth actor-routing storage registration**. It is the highest-leverage likely product-regression cluster because it blocks auth bootstrap, causes many grants failures, and may reveal a framework-level actor-routing invariant: `registered_models`, storage, and `matrix.children` must point at the same live model classes.

Then proceed to frontend runtime in dependency order: **transport contract**, then **NTT/DynamicClass entity lifecycle**, then **forms/methods/navigation**. Do not begin broad UI fixes until the runtime substrate is stable.

```text
P-1 contract triage gate
        |
        v
P0 backend auth/storage
        |
        v
P1 frontend transport contract
        |
        v
P2 NTT/DynamicClass lifecycle
        |
        v
P3 Formidable + method UI contracts
        |
        v
P4 router/topbar/browser polish
        |
        v
P5 suite hardening and coverage gaps
```

## Current State

The 2026-04-24 audit reports:

| Suite area | State | Main issue |
|---|---:|---|
| Framework packages | Green | Core/actors/agents backend packages pass |
| `examples/grants` | Red | users/auth route 500s and token envelope mismatch |
| Frontend Vitest | Red | stale Socket tests, NTT/DynamicClass lifecycle drift, form contract drift |
| Frontend Playwright | Red | browser-visible form/method/navigation/topbar drift |
| Veille | Red | bool deserialization and shell navigation regressions |

Important distinction: not all failures are product bugs. Before fixing a failing test, verify whether the test still describes the intended contract. Several current failures are **contract decisions** that need explicit resolution:

- Old Socket API vs current TX-native Socket.
- Top-level auth token vs debug envelope `{data: {token}}`.
- Always-pull method responses vs local structured updates.
- Numeric instance keys in tests vs string actor addresses in runtime.

## Target State

1. Every failing cluster has an explicit contract classification before any production-code change.
2. Grants auth works through actor routing with test DB storage.
3. Frontend transport tests document the current TX-native Socket contract.
4. NTT/DynamicClass has one explicit instance identity contract that supports actor string addresses and numeric entity IDs safely.
5. UI contract tests run on a stable runtime, so failures reflect real DOM/product decisions rather than substrate breakage.
6. Test infrastructure stops hiding failures through shared state, broad assertions, or stale mocks.

## P-1: Mandatory Contract Triage Gate

### Rule

Do **not** change production code simply because a test fails. First decide whether the test is asserting the current intended contract.

```text
Failing test or cluster
        |
        v
Does the test assert the current intended contract?
        |
        +-- Yes
        |     -> product regression
        |     -> fix code, preserve or strengthen the test
        |
        +-- No
        |     -> contract drift / stale test
        |     -> update test and docs; do not regress code to old behavior
        |
        +-- Unclear
              -> inspect docs, neighboring code, app behavior, and history
              -> write a contract decision note before code changes
```

### Classification categories

| Classification | Meaning | Action |
|---|---|---|
| Product regression | Code no longer satisfies the intended current contract | Fix production code; keep or strengthen the failing test |
| Stale test contract | Test asserts an old API/DOM/runtime behavior that has intentionally changed | Update tests and relevant docs |
| Test infrastructure issue | Failure comes from fixtures, mocks, global state, timing, stale setup, or environment | Fix test harness first |
| Unresolved contract decision | Current behavior and test expectation are both plausible | Stop and record the decision before implementation |

### Evidence checklist

For each cluster, collect enough evidence to justify the classification:

| Question | Signal | Likely action |
|---|---|---|
| Does current docs describe the test expectation? | Test matches docs | Production regression is more likely |
| Does current docs describe implementation behavior instead? | Test contradicts docs | Stale test is more likely |
| Does neighboring runtime code rely on current behavior? | Current behavior is integrated | Avoid reverting code blindly |
| Does the failure disappear with isolated state or fresh fixtures? | Shared-state sensitivity | Test infrastructure issue |
| Would satisfying the test reintroduce an older architecture? | Architecture regression risk | Update test or add compatibility intentionally |
| Is there no authoritative contract? | Ambiguous | Write a contract decision note |

### Required contract note

Each cluster fix should include a short note in the implementation summary, PR body, or commit description:

```md
Contract decision:
- Classification: product regression | stale test | test infrastructure | unresolved decision
- Intended behavior:
- Evidence:
- Changed:
  - production code: yes/no
  - tests: yes/no
  - docs: yes/no
- Regression risk:
```

### Examples from this audit

| Cluster | Initial classification | Reason |
|---|---|---|
| Grants `NoneType.storage.list` | Likely product regression | Actor route dispatch should never reach a storable model with `storage=None` |
| Grants top-level `token` vs `data.token` | Likely stale test or environment contract drift | Debug envelopes may intentionally wrap method responses |
| Socket legacy API failures | Likely stale tests/docs | Current implementation appears intentionally TX-native and minimal |
| NTT numeric `instances.get(1)` | Unresolved contract decision | Actor addresses are string-based, tests expect numeric convenience keys |
| Form/method DOM assertions | Mixed/unknown | Some may be real regressions; others may reflect intentional UI changes |

## Prioritized Action Plan

| Priority | Cluster | Why first | Default decision |
|---|---|---|---|
| P-1 | Contract triage gate | Prevents fixing stale tests by regressing product code | Classify before touching production code |
| P0 | Grants users/auth storage registration | ~~Blocks auth, grants CRUD, streaming setup, and many E2E flows~~ | ✅ resolved |
| P1 | Socket + NetworkAdapter tests | ~~Largest single frontend failure cluster; mostly stale tests~~ | ✅ resolved |
| P2 | NTT/DynamicClass lifecycle | ~~Central entity graph; many integrations depend on it~~ | ✅ resolved in tracked scope |
| P3 | Formidable + method/comment/favorite UI | High browser-visible blast radius | Fix only after P1/P2 are green |
| P4 | Router/topbar/navigation shell | Contract drift, less foundational | Decide intended product contract, update tests or UI |
| P5 | Suite hardening | Prevent recurrence | Isolate fixtures, remove permissive assertions, add coverage gaps |

## P0: Highest-Leverage Cluster — Grants Users/Auth

**Status:** ✅ Resolved

### Contract triage

Before implementing P0, split the observed failures:

| Failure | Initial classification | Implementation implication |
|---|---|---|
| `NoneType` storage error in `/users`, `/users/login`, `/users/register` | Likely product regression | Reproduce with a narrow failing test, then fix actor/storage synchronization |
| Login helper expects top-level `token` but receives `{data: {token}}` | Likely stale test or debug-envelope drift | Decide whether tests should disable debug, accept both shapes, or product should special-case auth |
| `/grants/{id}` returns `404` | Unknown until storage/seed state is verified | Do not patch routes until actor storage and seed identity are confirmed |

Only the first item should be treated as production-code work by default. The token-envelope issue should not drive product-code changes until the auth response contract is explicitly decided.

### Working hypothesis

The observed error:

```text
'NoneType' object has no attribute 'list'
```

most likely occurs because `BaseUser.login()` / `BaseUser.register_user()` call `cls.list()`, which resolves to `StorableMixin.list()`, which calls `cls.storage.list(...)`. In the grants actor-routing path, Matrix may be routing `users` to a class whose `storage` is `None` or stale relative to the test DB.

```text
POST /users/login
  -> NetworkAPI route
  -> TX(name='login', target='users')
  -> Matrix child 'users'
  -> User.login()
  -> cls.list()
  -> cls.storage.list(...)
        ^ if storage is None, current 500
```

### Key code paths

| Concern | Files |
|---|---|
| Grants app bootstrap | `examples/grants/main.py` |
| Grants user model | `examples/grants/models/user.py` |
| Grants test DB setup | `examples/grants/tests/conftest.py` |
| Base auth methods | `packages/n3tx-core/src/n3tx_core/models/base_user.py` |
| Storage list call | `packages/n3tx-core/src/n3tx_core/models/storable_mixin.py` |
| Actor route bridge | `packages/n3tx-actors/src/n3tx_actors/api/network_api.py` |
| Actor CRUD/custom dispatch | `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py` |
| App actor bootstrap | `packages/n3tx-core/src/n3tx_core/app.py` |

### Implementation slices

#### Slice P0.1 — Reproduce and pin storage identity

Add a narrow regression test in `examples/grants/tests/` that asserts the class identity and storage state after test bootstrap:

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

If `matrix.children['users']` is not the same object, the bug is registration synchronization. If it is the same object but storage is `None`, the bug is storage injection/bootstrap.

#### Slice P0.2 — Fix actor model/storage synchronization

Preferred target: make actor routing enforce the invariant at app build or model registration time:

```python
# Representative shape, not final code
for tablename, model_cls in registered_models.items():
    if issubclass(model_cls, Actor):
        matrix.register(model_cls)
        assert getattr(model_cls, 'storage', None) is not None or not model_cls.__storable__
```

If tests mutate model storage after app import, test fixtures must also re-register/sync Matrix children after `model_cls.set_storage(storage)`.

#### Slice P0.3 — Auth behavior regression tests

Use focused tests before broad grants reruns:

```python
def test_users_list_does_not_500(client):
    resp = client.get('/users')
    assert resp.status_code != 500

def test_register_login_do_not_hit_missing_storage(client):
    reg = client.post('/users/register', json={...})
    assert reg.status_code in (200, 201, 409)
    login = client.post('/users/login', json={...})
    assert login.status_code in (200, 401)
```

Then tighten status expectations once the storage 500 is gone.

#### Slice P0.4 — Resolve token envelope deliberately

After storage is fixed, decide one of:

| Option | Meaning | Recommendation |
|---|---|---|
| Disable debug in tests | Auth returns top-level token consistently | Good if debug wrapper is accidental in tests |
| Accept both helper shapes | Test helpers read `body.token ?? body.data?.token` | Good compatibility patch |
| Change product response | Force auth endpoints to never debug-wrap | Only if auth token is a stable public exception |

Default: update grants E2E helpers to accept both shapes, unless product wants debug envelopes disabled in tests globally.

### Verification for P0

Run in order:

```bash
python3 -m pytest examples/grants/tests/test_boot.py
python3 -m pytest examples/grants/tests/test_auth_flow.py
python3 -m pytest examples/grants/tests/test_grants_crud.py
python3 -m pytest examples/grants/tests/
```

## P1: Frontend Transport Contract

**Status:** ✅ Resolved

### Decision

Keep the current simplified TX-native Socket. Do **not** restore the old state-machine API unless external app code is found to depend on it.

### Contract triage

The Socket failures are the clearest stale-test candidate in the audit. Before changing `Socket.js`, verify:

- current docs and implementation intentionally describe TX-native behavior;
- no in-repo app/runtime code depends on the old `sendEvent`, `sendMessage`, `watchdog`, `resources`, or `defaultSocket` API;
- restoring old methods would not add unused compatibility surface.

Default action: update tests and docs to the current contract. Add compatibility aliases only if a real consumer depends on them.

### Implementation slices

1. Rewrite `tests/frontend/tests/transport/Socket.test.js` around current public API:
   - `constructor(url)`
   - `connect(token)`
   - `send(tx)`
   - `close()`
   - `ready`
   - `onmessage`
   - queue + heartbeat behavior
2. Update `NetworkAdapter.test.js` WS case to expect `socket.send(tx)`, not `socket.sendEvent(event)`.
3. Update stale docs in `docs/frontend/TRANSPORT.md`.

### Verification

```bash
cd tests/frontend && npx vitest run \
  tests/transport/Socket.test.js \
  tests/transport/NetworkAdapter.test.js \
  tests/integration/network-entity-sync.test.js \
  tests/integration/actor-messaging.test.js
```

## P2: NTT/DynamicClass Entity Lifecycle

**Status:** ✅ Resolved (tracked scope)

### Decision

Preserve actor string addresses internally, but make `DynamicClass.instances` compatible with numeric entity IDs.

### Contract triage

This cluster mixes likely regressions with unresolved contract decisions. Before editing `NTT.js`, decide and document:

- whether `DynamicClass.instances` is a public-ish test/developer API or purely internal;
- whether numeric entity IDs should be accepted for developer ergonomics even though actor addresses are strings;
- whether method responses should always pull, update locally, or use a hybrid fallback.

Default action: keep string actor addresses as the internal source of truth, but support numeric lookup at the `instances` boundary if that preserves compatibility without complicating routing.

### Implementation slices

1. Add a tiny key-normalizing map wrapper or helper so these are equivalent:

```javascript
DC.instances.get(1) === DC.instances.get('1')
DC.instances.has(1) === DC.instances.has('1')
DC.instances.delete(1) === DC.instances.delete('1')
```

2. Restore `_response_()` fallback semantics:

```javascript
_response_(tx) {
  if (tx?.data && typeof tx.data === 'object' && tx.data.id) {
    this.update(tx.data);
    return;
  }
  return this.pull();
}
```

3. Prefer schema-provided `$id` over `config.API_URL` for href/schema URL construction where possible.
4. Fix generated method payload mapping if tests expose positional-array payloads instead of named parameter objects.

### Verification

```bash
cd tests/frontend && npx vitest run \
  tests/core/NTT.test.js \
  tests/core/DynamicClassFunctor.test.js \
  tests/integration/schema-bootstrap.test.js \
  tests/integration/entity-lifecycle.test.js \
  tests/integration/nested-entities.test.js \
  tests/integration/method-execution.test.js
```

## P3-P5 Follow-Up

### P3 — Formidable and methods

Only start once P1/P2 pass. Focus files:

- `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js`

Use the existing form/method Vitest failures as contract tests; decide intentionally where the old DOM contract is stale.

### P4 — Router/topbar/navigation shell

Focus files:

- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js`

Separate actual routing bugs from visual-copy changes like brand text and topbar height.

### P5 — Test suite hardening

Backend:

- Replace session-scoped mutable DB fixtures with function/class scoped isolation.
- Remove permissive `status_code in (...)` assertions.
- Split mega workflow tests.
- Add unit coverage for `generate_join_model()`, route factories, and FK hydration.

Frontend:

- Fail tests on unhandled promise rejections.
- Reset WebSocket/mocks/custom element state where possible.
- Add denied-permission and negative-path component tests.
- Remove tests that document known-wrong behavior as passing behavior.

## Risks and Open Questions

| Risk/question | Default answer |
|---|---|
| Are stale tests or product code wrong? | Decide per cluster; P1 appears stale tests, P0 appears product/bootstrap bug |
| Should debug envelopes wrap auth responses? | Accept both in helpers until product contract is explicit |
| Numeric vs string entity IDs? | Support both at `instances` boundary; keep actor addresses string-based |
| Could P0 reveal global Matrix contamination? | Yes; inspect/reset Matrix state in grants fixtures if identity test fails |
| Should UI tests be updated before runtime? | No; runtime instability will create false UI diagnoses |

## Concrete Next Steps

1. Apply the P-1 contract triage note to the first cluster being fixed.
2. Implement P0.1 identity regression test for grants actor/storage registration.
3. Fix actor-routing model/storage synchronization only if the test proves a product/bootstrap regression.
4. Re-run grants boot/auth tests.
5. Resolve token envelope helpers as a contract drift decision, not as an accidental production-code change.
6. Move to P1 transport contract cleanup.

## Critical Files for Implementation

- `examples/grants/tests/conftest.py`
- `packages/n3tx-core/src/n3tx_core/app.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-core/src/n3tx_core/static/core/transport/Socket.js`
- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`

## Saved Plan

- `.project/plans/test-failure-triage-action-plan.md`
