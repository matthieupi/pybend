# P3–P5 Test Recovery Plan

## ✅ Recommendation

Execute the remaining recovery work in this order:

```text
P3 Formidable + method/UI contracts
        |
        v
P4 Router/topbar/navigation browser contracts
        |
        v
P5 Test-suite hardening and stability gates
```

This plan assumes the existing **P-1 contract triage gate remains mandatory** for every failure cluster. Do not change production code solely to satisfy stale tests.

---

## 1. Current State

The existing test triage artifacts establish:

| Phase | State | Meaning |
|---|---|---|
| `P0` | ✅ resolved | grants users/auth actor-routing storage sync fixed |
| `P1` | ✅ resolved | Socket + NetworkAdapter tests/docs aligned to TX-native transport |
| `P2` | ✅ resolved (tracked scope) | core NTT/DynamicClass runtime/lifecycle boundaries now green |
| `P3` | next | Formidable, methods, item UI, social/comment/favorite behavior |
| `P4` | next after P3 | router/topbar/sidebar/browser-visible navigation drift |
| `P5` | final | fixture isolation, async leak visibility, broad-suite stability |

The remaining work is no longer mainly about transport/runtime substrate correctness. It is now concentrated in:

1. **schema-driven UI contract drift**;
2. **browser-visible navigation/shell contract drift**;
3. **test infrastructure noise and order sensitivity**.

Cross-cutting dependency:

- the method response refresh contract (`_response_()` local update vs `pull()` fallback) still influences P3 method and social UI assertions, so P3 must settle that boundary before broad browser rewrites.

---

## 2. Operating Rules

## 2.1 P-1 gate still applies

Before each P3/P4/P5 slice, write a short contract note:

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

## 2.2 Change hierarchy

Use this precedence:

1. If docs + architecture + integrated runtime clearly define the contract → **fix product code**.
2. If tests assert an old DOM/API contract that the current system intentionally replaced → **update tests and docs**.
3. If failure is from fixtures, shared state, async leaks, mocks, or harness setup → **fix test infrastructure first**.
4. If both current runtime and test expectation are plausible → **stop and record a contract decision**.

## 2.3 Verification discipline

For each slice:

- rerun the narrowest reproducer first;
- fix one cluster at a time;
- rerun the cluster boundary suite;
- only then expand to adjacent suites.

---

## 3. Architecture View

```text
Schema contract
   -> Formidable
   -> ntx-item / ntx-method / ntx-list-field
   -> Router + shell components
   -> stable targeted + broad tests
```

```text
P3 UI surface
  schema.properties / schema.methods / schema.ui
           |
           v
  Formidable normalization + layout
           |
           v
  ntx-item display/edit mode
           |
           +--> attached methods (inline/fieldset)
           +--> button methods (favorite/like)
```

```text
P4 browser shell
  Router (state + hash + stack)
           |
           v
  ntx-router (slot home vs mounted detail)
           |
           +--> ntx-topbar
           +--> ntx-sidebar
           +--> ntx-theme-button
           +--> app-specific shells (Veille)
```

---

## 4. P3 — Formidable + Method/UI Contract Recovery

## 4.1 Goal

Make the UI-layer tests reflect the intended current schema-driven contract for:

- Formidable field rendering and validation;
- method rendering and submission behavior;
- item display/edit flows;
- social/comment/favorite UI contracts.

## 4.2 Main files in scope

| Concern | Files |
|---|---|
| form generation | `packages/n3tx-ui/src/n3tx_ui/static/generators/form.js` |
| method UI | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.js` |
| item rendering/edit mode | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js` |
| array/list field rendering | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list-field.js` |
| method response lifecycle | `packages/n3tx-core/src/n3tx_core/static/core/NTT.js` |
| social example backend contract | `examples/core/models/product.py`, `examples/core/models/comment.py` |
| example-only favorites surface | `examples/core/static/components/ntx-favorites.js` |

## 4.3 Likely boundary tests

| Cluster | Tests |
|---|---|
| Formidable field/layout contracts | `tests/frontend/tests/generators/form.test.js`, `form-array-permissions.test.js`, `form-entity-binding.test.js` |
| Method rendering/optional params | `tests/frontend/tests/components/ntx-method.test.js`, `ntx-method-optional-fields.test.js`, `ntx-method-zero-required.test.js` |
| Item rendering/method placement | `tests/frontend/tests/components/ntx-item.test.js`, `ntx-item-method-attrs.test.js`, `ntx-list-field.test.js` |
| Social/example UI | `tests/frontend/tests/components/ntx-favorites.test.js`, relevant Playwright social specs |

## 4.4 Current contract decisions to preserve by default

| Surface | Intended current contract |
|---|---|
| method schemas | `parameters` normalize to `properties` internally |
| top-level method `$ref` params | expand into dotted keys like `comment.text` |
| attached methods | display mode only; hidden in edit mode |
| optional/defaulted method params | collapsed behind “Show options” |
| zero-visible-param methods | collapse to action button |
| button-layout methods | count driven by `ui.count_field` |
| Product social method | `favorite` / `favorites`, not product `like` / `likes` |
| Comment social method | `like` / `likes` |
| textarea method/widget handling | intentional current contract, not stale bug by default |

## 4.5 P3 execution slices

### Slice P3.0 — Revalidate the narrowest cluster

Run:

```bash
cd /workspace/tests/frontend && npx vitest run \
  tests/generators/form.test.js \
  tests/generators/form-array-permissions.test.js \
  tests/integration/form-entity-binding.test.js \
  tests/components/ntx-method.test.js \
  tests/components/ntx-method-optional-fields.test.js \
  tests/components/ntx-method-zero-required.test.js \
  tests/components/ntx-item.test.js \
  tests/components/ntx-item-method-attrs.test.js \
  tests/components/ntx-list-field.test.js
```

Purpose:

- separate real rendering regressions from stale schema mocks;
- confirm which failures remain after P2 stabilization;
- keep P3 focused before broad Playwright reruns.

### Slice P3.1 — Normalize test schema fixtures to current backend contracts

Likely stale test-contract cleanup:

- Product social mocks using `like` / `likes` should be aligned to `favorite` / `favorites` if current backend/docs remain authoritative.
- Comment social mocks should keep `like` / `likes`.
- Tests expecting a single-line `<input>` for comment/reply methods should be updated if the current widget contract is `textarea`.
- Tests importing `ntx-favorites` through package component aliases should be corrected if `ntx-favorites.js` is example-local rather than a framework component.

Representative target schema shape:

```javascript
// Product
methods: {
  favorite: {
    ui: { layout: 'button', icon: 'star', count_field: 'favorites' }
  },
  comment: {
    ui: { layout: 'inline', attach_to: 'comments', widget: 'textarea' }
  }
}

// Comment
methods: {
  like: {
    ui: { layout: 'button', icon: 'heart', count_field: 'likes' }
  },
  reply: {
    ui: { layout: 'inline', attach_to: 'replies', widget: 'textarea' }
  }
}
```

### Slice P3.2 — Lock the Formidable contract intentionally

Confirm and preserve:

- entity forms read `schema.properties`;
- method forms read `schema.parameters`, then normalize to `properties`;
- header fields (`name`, `title`, `description`) are rendered by `getHeader()`;
- protected fields downgrade to display-only or disappear according to mode/access;
- arrays route through `<ntx-list-field>`.

Representative invariant:

```javascript
const normalized = Formidable.normalizeSchema(methodSchema);
const fields = normalized.properties;
const required = new Set(normalized.required || []);
```

If tests disagree with this contract but docs and current runtime agree, update tests/docs rather than regressing Formidable.

### Slice P3.3 — Settle the method response refresh contract

Recommended default:

- entity/prototype method calls route replies to `_response_()`;
- structured local updates (`{action, _field}` or entity payloads) update state locally;
- otherwise fallback `pull()`;
- avoid duplicating competing refresh policies in both `NTT.js` and `ntx-method.js`.

Representative shape:

```javascript
_response_(data) {
  if (isStructuredLocalUpdate(data)) {
    this.updateFromMethodResponse(data);
    return;
  }
  return this.pull();
}
```

This slice is the main P3 decision point because it affects social actions, attached methods, and later browser-visible refresh assertions.

### Slice P3.4 — Stabilize `ntx-item` method rendering and edit behavior

Expected behavior:

- `sm()` renders button-layout methods only;
- `md/lg/xl()` render Formidable plus standalone methods in display mode;
- edit mode hides methods;
- permission-denied edit/delete actions stay hidden or abort;
- social counts re-render off `count_field`.

Only change product code here if the current docs + architecture say the runtime behavior is wrong. Otherwise rewrite stale DOM assertions.

## 4.6 P3 verification

Minimum verification:

```bash
cd /workspace/tests/frontend && npx vitest run \
  tests/generators/form.test.js \
  tests/generators/form-array-permissions.test.js \
  tests/integration/form-entity-binding.test.js \
  tests/components/ntx-method.test.js \
  tests/components/ntx-method-optional-fields.test.js \
  tests/components/ntx-method-zero-required.test.js \
  tests/components/ntx-item.test.js \
  tests/components/ntx-item-method-attrs.test.js \
  tests/components/ntx-list-field.test.js
```

Then expand to browser-visible social/form specs only after the Vitest cluster is stable.

---

## 5. P4 — Router/Topbar/Navigation Browser Contract Recovery

## 5.1 Goal

Align router/topbar/sidebar/browser tests to the intended current shell contract and fix genuine navigation regressions without regressing the newer router/theme architecture.

## 5.2 Main files in scope

| Concern | Files |
|---|---|
| pure route parsing/resolution | `packages/n3tx-core/src/n3tx_core/static/core/Router.js` |
| view mounting | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js` |
| topbar shell | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js` |
| sidebar shell | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js` |
| manual theme control | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-theme-button.js` |
| profile route target | `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js` |
| Veille shell | `apps/veille/static/index.html` |

## 5.3 Likely boundary tests

| Cluster | Tests |
|---|---|
| router unit/integration | `tests/frontend/tests/core/Router.test.js`, `components/ntx-router.test.js`, `integration/router-navigation.test.js` |
| shell/browser contracts | `tests/frontend/tests/e2e/ntx-router-unit.spec.js`, `ntx-topbar-unit.spec.js`, `theme-toggle.spec.js`, `product-detail.spec.js`, `flow-navigation-deep.spec.js` |
| Veille browser regressions | `apps/veille/tests/test_frontend_regressions.mjs`, Veille Playwright specs |

## 5.4 Current contract decisions to preserve by default

| Surface | Intended current contract |
|---|---|
| home route | empty route / no hash |
| router home DOM | `.router-content` remains; slot is restored |
| router chrome at home | hidden, not removed |
| back button | shown only when `Router.canGoBack` is true |
| profile route | built-in topbar dropdown link to `#@profile` |
| theme control | explicit `<ntx-theme-button>` slot, not legacy `.theme-toggle` |
| favorites in topbar | not framework-default unless app explicitly slots it |

This means many exact DOM/copy/styling assertions are likely stale tests rather than framework regressions.

## 5.5 P4 execution slices

### Slice P4.0 — Revalidate narrow router/shell boundaries

Run:

```bash
cd /workspace/tests/frontend && npx vitest run \
  tests/core/Router.test.js \
  tests/components/ntx-router.test.js \
  tests/components/ntx-topbar.test.js \
  tests/components/ntx-theme-button.test.js \
  tests/integration/router-navigation.test.js

cd /workspace/tests/frontend && npx playwright test \
  --config=tests/e2e/playwright.config.js \
  tests/e2e/ntx-router-unit.spec.js \
  tests/e2e/ntx-topbar-unit.spec.js \
  tests/e2e/theme-toggle.spec.js \
  tests/e2e/product-detail.spec.js \
  tests/e2e/flow-navigation-deep.spec.js
```

Purpose:

- separate real router/navigation failures from stale DOM assertions;
- keep P4 centered on shell behavior rather than broad app features.

### Slice P4.1 — Rewrite stale router assertions to current router semantics

Prefer assertions like:

```javascript
expect(routerContent).toBeTruthy();
expect(chrome.hidden).toBe(true);
expect(backButton.hidden).toBe(true);
```

Avoid stale expectations like:

```javascript
expect(routerContent).toBeNull();
```

Likely stale categories:

- expecting `.router-content` absence at root;
- expecting `.back-btn` absence rather than hidden state;
- expecting direct deep links to always have back history;
- exact shell-copy/height/version assertions that are not architectural contracts.

### Slice P4.2 — Lock topbar/theme tests to the manual shell contract

Expected behavior:

- profile remains built-in;
- theme is rendered via slotted `<ntx-theme-button>`;
- no built-in framework requirement for topbar favorites;
- logout clears JWT and redirects to `/login.html`;
- multiple theme controls sync through `theme-change`.

If tests still target `.theme-toggle` or built-in favorites chrome, classify them as stale unless a product requirement says otherwise.

### Slice P4.3 — Resolve Veille router ownership

Current risk:

- Veille mounts `<ntx-router name="main">` **and** separately runs app-local `handleRoute()` against `window.location.hash`.

Recommended target:

- make the framework router the canonical navigation source;
- convert Veille dashboard/source/grant/agent/analyze/report surfaces into router-resolved views or controlled app routes;
- remove the long-term double-routing split.

If a full Veille route migration is too large for this phase, add a temporary compatibility adapter, but do not keep two independent routing sources of truth as the end state.

## 5.6 P4 verification

Minimum verification:

```bash
cd /workspace/tests/frontend && npx vitest run \
  tests/core/Router.test.js \
  tests/components/ntx-router.test.js \
  tests/components/ntx-topbar.test.js \
  tests/components/ntx-theme-button.test.js \
  tests/integration/router-navigation.test.js

cd /workspace/tests/frontend && npx playwright test \
  --config=tests/e2e/playwright.config.js \
  tests/e2e/ntx-router-unit.spec.js \
  tests/e2e/ntx-topbar-unit.spec.js \
  tests/e2e/theme-toggle.spec.js \
  tests/e2e/product-detail.spec.js \
  tests/e2e/flow-navigation-deep.spec.js
```

Run Veille-specific browser checks only after the shared shell contract is stable.

---

## 6. P5 — Suite Hardening and Stability Gates

## 6.1 Goal

Remove infrastructure noise, shared-state contamination, and hidden async failures so the remaining suite becomes trustworthy after P3/P4 contracts are settled.

## 6.2 Main files in scope

| Concern | Files |
|---|---|
| frontend global test setup | `tests/frontend/tests/setup.js`, `tests/frontend/vitest.config.js` |
| Playwright temp DB lifecycle | `tests/frontend/tests/e2e/global-setup.js`, `global-teardown.js`, Playwright configs |
| example backend fixture isolation | `examples/core/tests/conftest.py`, `examples/actors/tests/conftest.py`, `examples/grants/tests/conftest.py` |
| Veille harnesses | `apps/veille/tests/*.py`, `apps/veille/tests/*.mjs` |

## 6.3 Current infrastructure risks

| Risk | Evidence |
|---|---|
| unhandled promise rejections are recorded but not failed | `tests/frontend/tests/setup.js` |
| example suites use session-scoped DB/client/token fixtures | `examples/*/tests/conftest.py` |
| Playwright marker file path is fixed | `tests/frontend/tests/e2e/global-setup.js` |
| local reused server can hide env drift | `reuseExistingServer: !process.env.CI` |
| Veille mixes app-local server/browser harnesses with framework suites | Veille tests + app shell |

## 6.4 P5 execution slices

### Slice P5.0 — Sequence P5 after P3/P4 decisions

Do **not** harden by locking in stale P3/P4 assertions. First settle the UI/browser contracts. Then harden the harness around the final intended behavior.

### Slice P5.1 — Make Vitest async leaks visible

Current setup collects unhandled rejections but does not fail runs.

Recommended direction:

```javascript
const unhandled = [];

process.on('unhandledRejection', (reason) => {
  unhandled.push(reason);
});

afterEach(() => {
  if (unhandled.length) {
    const reason = unhandled.shift();
    unhandled.length = 0;
    throw reason;
  }
});
```

Apply only after reducing known P3/P4 async noise, or this will flood the suite with non-actionable failures.

### Slice P5.2 — Improve backend example fixture isolation

Current issue:

- core/actors/grants example suites share session-scoped DB, client, and seeded data.

Recommended migration path:

| Stage | Action |
|---|---|
| `P5.2a` | identify mutation-heavy test files |
| `P5.2b` | move those files to function-scoped or class-scoped fresh DB fixtures |
| `P5.2c` | keep read-only schema tests session-scoped if needed for speed |
| `P5.2d` | replace permissive `>=` / multi-status assertions with exact expectations |

### Slice P5.3 — Make Playwright temp artifacts run-unique

Current marker path:

```text
/tmp/ntx-e2e-dbpath.txt
```

Recommended shape:

```javascript
const runId = process.env.PLAYWRIGHT_RUN_ID || `${process.pid}-${Date.now()}`;
const markerPath = join(tmpdir(), `ntx-e2e-dbpath-${runId}.txt`);
process.env.__NTT_E2E_MARKER = markerPath;
```

Then teardown should read the run-specific marker rather than a fixed filename.

### Slice P5.4 — Define verification tiers

| Tier | When | Scope |
|---|---|---|
| narrow | every slice | only directly affected files/tests |
| cluster | phase end | all P3-related or P4-related boundary tests |
| broad | pre-merge/nightly | backend packages + examples + full Vitest + Playwright |
| stability | before declaring P5 done | rerun targeted clusters twice, fail unhandled rejections |

### Slice P5.5 — CI behavior defaults

Recommended CI defaults:

- keep Playwright serialized until server/DB isolation is proven parallel-safe;
- set `reuseExistingServer=false` in CI;
- require zero unhandled frontend test errors before accepting a green cluster;
- reserve full broad-suite runs for nightly/pre-merge if per-PR cost is too high.

## 6.5 P5 verification

Minimum P5 proof should include:

```bash
# rerun targeted P3/P4 clusters twice

cd /workspace/tests/frontend && npx vitest run

python3 -m pytest examples/core/tests/
python3 -m pytest examples/actors/tests/
python3 -m pytest examples/grants/tests/

cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js
```

Then expand to Veille and any app-specific suites.

---

## 7. Recommended Execution Order

```text
1. P3 targeted rerun + classifications
2. Align schema mocks and stale DOM assertions
3. Fix only real Formidable/method/item regressions
4. Verify P3 Vitest cluster
5. P4 targeted rerun + classifications
6. Align router/topbar/theme tests to current contract
7. Resolve Veille routing ownership or add explicit compatibility bridge
8. Verify P4 browser cluster
9. Apply P5 infrastructure hardening
10. Rerun broad suites and stability checks
```

---

## 8. Risks and Open Questions

| Risk | Decision needed |
|---|---|
| method response refresh semantics | finalize hybrid local-update + pull fallback |
| `ntx-favorites` ownership | example-only component or promote to framework package |
| Veille routing ownership | framework router canonical vs retained app-local hash router |
| shell copy/style assertions | which are product contracts vs stale snapshots |
| fixture isolation cost | full function-scope DB reset vs selective isolation |

---

## 9. Success Criteria

P3–P5 are complete when:

1. P3 UI boundary suites are green against the intended current schema-driven contract.
2. P4 shell/navigation suites are green without restoring legacy router/theme behavior.
3. Veille routing expectations are explicit and stable.
4. Frontend test runs surface zero hidden unhandled rejection noise.
5. Shared-state/order-sensitive failures are materially reduced in backend example suites.
6. Broad reruns fail only on real remaining product issues, not stale contracts or harness contamination.
