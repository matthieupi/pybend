# P-1 Contract Triage — Test Failure Audit

## Purpose

This document executes **P-1: Contract Triage Gate** for the current test-failure recovery work.

The goal is to prevent accidental regressions while fixing a stale test suite. A failing test is not automatically proof that production code is wrong. Before a cluster is fixed, we must decide whether it represents:

- a real product regression;
- a stale test contract;
- a test infrastructure issue;
- or an unresolved product/API decision.

## Mandatory Rule

Do **not** change production code simply because a test fails. First verify whether the failing assertion still describes the intended framework contract.

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
        |     -> stale test / contract drift
        |     -> update tests and docs; do not regress code to old behavior
        |
        +-- Unclear
              -> inspect docs, neighboring code, app behavior, and history
              -> record a contract decision before implementation
```

## Classification Rubric

| Classification | Meaning | Required action |
|---|---|---|
| Product regression | Code no longer satisfies the intended current contract | Add/keep failing test, fix production code, update docs only if behavior was undocumented |
| Stale test contract | Test asserts an old behavior that intentionally changed | Update test and docs; do not change production code just to satisfy old behavior |
| Test infrastructure issue | Failure comes from fixtures, mocks, global state, timing, or environment setup | Fix harness/fixtures/mocks before product code |
| Unresolved contract decision | Both current behavior and test expectation are plausible | Stop and decide the intended contract before code/test changes |

## Evidence Checklist

For every cluster, answer these before implementation:

| Question | If yes | Likely classification |
|---|---|---|
| Does current documentation describe the test expectation? | Test matches docs | Product regression more likely |
| Does current documentation describe current implementation instead? | Test contradicts docs | Stale test more likely |
| Does neighboring runtime/app code rely on current behavior? | Current behavior integrated | Avoid reverting code blindly |
| Does isolated rerun change the result? | Suite-order/state dependent | Test infrastructure or global-state issue |
| Would satisfying the test reintroduce older architecture? | High regression risk | Stale test or compatibility decision |
| Is there no authoritative contract? | Ambiguous | Unresolved contract decision |

## Required Contract Note

Each cluster fix must include this note in the implementation summary, PR body, or commit description:

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

---

## Cluster Classifications

### C1 — Grants users/auth `NoneType.storage.list`

**Initial classification:** Likely product regression.

**Observed failure:**

```text
'NoneType' object has no attribute 'list'
```

appears in `/users`, `/users/login`, and `/users/register` paths.

**Why this is likely production-code/bootstrap regression:**

- `BaseUser.login()` and `BaseUser.register_user()` call `cls.list()`.
- `StorableMixin.list()` calls `cls.storage.list(...)`.
- A storable model reached through an application route should not have `storage=None`.
- Grants uses actor routing, so Matrix/model/storage synchronization is part of the runtime contract.

**Do not change code until:**

- a narrow test confirms whether `registered_models['users']` and `matrix.children['users']` are the same class object;
- both have non-`None` storage after test bootstrap;
- isolated grants boot/auth tests reproduce the issue.

**Likely first change:** production code or fixture synchronization, depending on the identity test result.

**Primary files:**

- `examples/grants/main.py`
- `examples/grants/models/user.py`
- `examples/grants/tests/conftest.py`
- `packages/n3tx-core/src/n3tx_core/models/base_user.py`
- `packages/n3tx-core/src/n3tx_core/models/storable_mixin.py`
- `packages/n3tx-actors/src/n3tx_actors/api/network_api.py`
- `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`

---

### C2 — Grants auth token envelope mismatch

**Initial classification:** Stale test contract or test environment drift.

**Observed failure:**

Some helpers expect:

```json
{"token": "..."}
```

but observed responses are shaped like:

```json
{"data": {"token": "..."}, "_debug": {...}}
```

**Why this is not automatically a product-code bug:**

- Debug response envelopes may intentionally wrap custom method results.
- Auth endpoints may have changed from direct return payloads to method-response envelopes.
- Changing production code only to restore a top-level token could bypass a broader response-envelope contract.

**Do not change code until:**

- the intended auth response contract is chosen for debug and non-debug modes;
- tests confirm whether debug should be disabled in grants E2E;
- helpers are reviewed for compatibility with both response shapes.

**Default action:** update test helpers to read `body.token ?? body.data?.token`, unless product explicitly decides auth endpoints must never be debug-wrapped.

**Primary files:**

- `examples/grants/tests/e2e/*`
- `examples/grants/tests/test_auth_flow.py`
- `packages/n3tx-core/src/n3tx_core/models/base_user.py`
- route/method response-envelope code in core/actors route layers

---

### C3 — Frontend Socket legacy API failures

**Initial classification:** Likely stale tests and stale docs, not production-code regression.

**Observed failure:**

`Socket.test.js` expects an older state-machine API including:

- `Socket.resources`
- `Socket.defaultSocket`
- `sendEvent()`
- `sendMessage()`
- `watchdog()`
- `enable()` / `disable()`
- target registration callbacks

Current implementation is a smaller TX-native transport with:

- `constructor(url)`
- `connect(token)`
- `send(tx)`
- `close()`
- `ready`
- `onmessage`
- queue and heartbeat internals

**Why this is likely stale test contract:**

- Current runtime appears intentionally simplified around TX envelopes.
- `NetworkAdapter` calls `socket.send(tx)`, not `sendEvent()`.
- Reintroducing the full legacy API would expand public surface and risk preserving dead architecture.

**Do not change code until:**

- in-repo app/runtime consumers are checked for old Socket methods;
- `docs/frontend/TRANSPORT.md` is reconciled with the intended current transport contract;
- compatibility aliases are justified by real consumers, not only stale tests.

**Default action:** update Socket and NetworkAdapter tests to the TX-native contract, then update docs.

**Primary files:**

- `packages/n3tx-core/src/n3tx_core/static/core/transport/Socket.js`
- `packages/n3tx-core/src/n3tx_core/static/core/transport/NetworkAdapter.js`
- `tests/frontend/tests/transport/Socket.test.js`
- `tests/frontend/tests/transport/NetworkAdapter.test.js`
- `docs/frontend/TRANSPORT.md`

---

### C4 — NTT/DynamicClass instance identity and lifecycle

**Initial classification:** Mixed; unresolved contract decision plus likely localized regressions.

**Observed failure themes:**

- Tests call `DynamicClass.instances.get(1)` / `has(1)`.
- Runtime stores actor addresses as strings, e.g. `'1'` and `'Product/1'`.
- `_response_()` no longer always calls `pull()` for simple method responses.
- Schema/href URLs may derive from `config.API_URL` instead of schema `$id`.

**Why this needs explicit contract decision:**

- String addresses are natural for the actor system.
- Numeric entity IDs are natural for model/database ergonomics and existing tests.
- Both are plausible boundaries; blindly switching one way can break routing or developer expectations.

**Contract decisions required:**

1. Is `DynamicClass.instances` public/developer-observable or internal-only?
2. Should numeric and string IDs be equivalent at the `instances` boundary?
3. Should method responses always pull, update locally when structured, or use hybrid fallback?
4. Should schema `$id` be the source of truth for instance hrefs instead of `config.API_URL`?

**Default action:** keep actor addresses string-based internally, but support numeric key lookup at the `instances` map boundary if that preserves compatibility without complicating routing.

**Primary files:**

- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`
- `packages/n3tx-core/src/n3tx_core/static/core/Actor.js`
- `packages/n3tx-core/src/n3tx_core/static/core/Matrix.js`
- `tests/frontend/tests/core/NTT.test.js`
- `tests/frontend/tests/core/DynamicClassFunctor.test.js`
- `tests/frontend/tests/integration/schema-bootstrap.test.js`
- `tests/frontend/tests/integration/entity-lifecycle.test.js`
- `tests/frontend/tests/integration/nested-entities.test.js`
- `tests/frontend/tests/integration/method-execution.test.js`

---

### C5 — Formidable/form rendering regressions

**Initial classification:** Mixed / unresolved until runtime substrate is stable.

**Observed failure themes:**

- field order;
- protected/hidden fields;
- widgets such as currency, textarea, bool;
- fieldsets/groups;
- list-field structure;
- attached method placement;
- display vs edit mode DOM structure.

**Why this is mixed:**

- Some failures may be real regressions in schema-driven UI rendering.
- Some may reflect intentional design-system or DOM contract changes.
- Many failures depend on NTT/schema/bootstrap behavior, so fixing forms before runtime may create false diagnoses.

**Do not change code until:**

- P1/P2 runtime layers are stable;
- current UI docs and design-system expectations are reviewed;
- each DOM assertion is checked against intended current markup, not old snapshots.

**Default action:** defer until P1/P2 pass; then classify each form subsection separately.

**Primary files:**

- `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js`
- `tests/frontend/tests/generators/form.test.js`
- `tests/frontend/tests/integration/form-entity-binding.test.js`
- browser form rendering specs

---

### C6 — Method/comment/favorite/like UI and API contracts

**Initial classification:** Mixed.

**Observed failure themes:**

- API responses for like/favorite contain richer join-model metadata than tests expect.
- Method buttons and count badges do not match browser DOM expectations.
- Comment/reply flows fail in UI and sometimes API assertions.

**Why this is mixed:**

- Richer join-model responses may be an intentional contract evolution.
- Missing method buttons or broken calls may be real UI/runtime regressions.
- API response shape and UI affordance failures should be separated.

**Do not change code until:**

- response contract is decided: action-only payload vs enriched join entity;
- UI failures are rerun after P1/P2/P3 stability;
- method routing is verified independently of DOM rendering.

**Default action:** preserve richer backend responses if they are now the canonical model-response contract; update stale action-only assertions unless product chooses action-only as the stable custom-method API.

**Primary files:**

- examples product/comment models
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js`
- social/comment/favorite tests in examples and frontend E2E

---

### C7 — Router/topbar/navigation shell drift

**Initial classification:** Mostly unresolved contract decision, with possible UI regressions.

**Observed failure themes:**

- back-button visibility;
- root route vs list route behavior;
- topbar brand text;
- dropdown content;
- theme toggle label/icon;
- topbar height.

**Why this is likely contract drift-heavy:**

- Brand text, dimensions, and dropdown copy are design/product contracts, not framework correctness by themselves.
- Router root behavior can be a real regression if the intended shell model changed accidentally.

**Do not change code until:**

- product/design contract for shell chrome is confirmed;
- router root semantics are separated from visual styling assertions;
- Veille-specific shell expectations are separated from shared framework expectations.

**Default action:** update visual/copy tests if design changed; fix router behavior only where route state violates documented navigation semantics.

**Primary files:**

- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js`
- frontend router/topbar/navigation specs

---

### C8 — Veille bool deserialization

**Initial classification:** Likely product/storage regression.

**Observed failure:**

SQLite bool fields containing `''` or `"''"` are not coerced to `False`, producing Pydantic bool parsing errors and hiding rows downstream.

**Why this is likely product-code bug:**

- Storage deserialization should normalize database legacy/empty values before Pydantic validation.
- The failure cascades into app behavior, not just assertion shape.

**Do not change code until:**

- storage bool coercion rules are checked against core storage docs;
- the behavior is reproduced at the storage layer, not only in Veille flows.

**Default action:** add/keep a storage-level regression test, then fix `_deserialize_json_fields()` / coercion logic if confirmed.

**Primary files:**

- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`
- `apps/veille/tests/test_empty_bool_deserialization.py`
- Veille model definitions containing bool fields

---

### C9 — Backend test isolation and permissive assertions

**Initial classification:** Test infrastructure issue.

**Observed issues:**

- session-scoped mutable fixtures;
- no rollback/reset between tests;
- permissive `status_code in (...)` assertions;
- mega-tests hiding the actual failure step;
- fragile string parsing of href IDs.

**Why this is test infrastructure:**

- These issues can create false positives and false negatives independent of product behavior.
- Fixing product code based on contaminated state risks chasing ghosts.

**Default action:** improve fixtures and assertions as suite-hardening work, not as production-code fixes.

**Primary files:**

- backend/example test `conftest.py` files
- backend integration tests named in `.project/reports/audits/backend-test-issues.md`

---

## Execution Order After P-1

| Next priority | Cluster | P-1 outcome |
|---|---|---|
| P0 | Grants `NoneType.storage.list` | Proceed as likely product/bootstrap regression, but prove with identity test first |
| P0b | Grants token envelope | Treat as contract drift until auth response contract is explicit |
| P1 | Socket/NetworkAdapter | Update stale tests/docs unless real consumers need legacy API |
| P2 | NTT/DynamicClass | Decide ID and response contracts before runtime edits |
| P3 | Form/method UI | Defer until runtime stability; classify per DOM contract |
| P4 | Router/topbar | Separate route semantics from visual/copy contract drift |
| P5 | Suite hardening | Fix infrastructure issues deliberately |

## Immediate Next Step

Begin P0 with a narrow grants actor/storage identity test. Do not change auth response envelope behavior in production during that slice.
