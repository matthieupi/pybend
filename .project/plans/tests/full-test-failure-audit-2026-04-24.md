# Full Test Failure Audit — 2026-04-24

## Scope

This report captures the failing and erroring tests from a full cross-stack test run covering:

- backend package unit suites
- backend example application suites
- frontend Vitest runtime/component/integration suites
- frontend Playwright browser suites

The goal is not to propose fixes yet. This document is a failure inventory and diagnosis aid.

## Environment and commands

### Python / backend

- Interpreter used for backend reruns: `/workspace/.venv/bin/python`
- Commands run:
  - `python -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/`
  - `python -m pytest packages/n3tx-actors/src/n3tx_actors/tests/`
  - `python -m pytest packages/n3tx-agents/src/n3tx_agents/tests/`
  - `python -m pytest examples/core/tests/`
  - `python -m pytest examples/actors/tests/`
  - `python -m pytest examples/grants/tests/`

### Frontend

- Vitest command: `cd /workspace/tests/frontend && npx vitest run`
- Playwright command: `cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js`

### Artifact sources

- Vitest saved output: `tool_dbc72ca08001PscWF8HwQ3m6pi`
- Playwright saved output: `tool_dbc91a98f0019ggg3BO60kt82V`
- Grants example saved output: `tool_dbca5a057001W26jnV34mQE68z`

## Executive summary

| Suite | Status |
|---|---|
| `packages/n3tx-core` | ✅ 1074 passed, 5 skipped |
| `packages/n3tx-actors` | ✅ 635 passed |
| `packages/n3tx-agents` | ✅ 138 passed |
| `examples/core` | ❌ 4 failed / 433 passed |
| `examples/actors` | ❌ 3 failed / 443 passed |
| `examples/grants` | ❌ 24 failed, 1 error / 137 passed, 1 skipped |
| `apps/veille` Python | ❌ 7 failed / 14 passed |
| `apps/veille` Node | ❌ 2 failed / 17 passed |
| Frontend Vitest | ❌ 153 failed, 4 errors / 1101 passed, 1 skipped |
| Frontend Playwright | ❌ 135 failed / 405 passed / 24 did not run |

## Cross-cutting failure clusters

### 1. Response contract drift

Several failures indicate APIs now return richer envelopes or richer method payloads than tests expect.

- `examples/core` like/favorite model tests expect `{"action": ...}` only
- grants E2E login helpers expect top-level `token`, but current response shape is `{"data": {"token": ...}}`

### 2. Grants user/auth subsystem is structurally broken

The grants example has a recurring backend error:

`'NoneType' object has no attribute 'list'`

This affects:

- register
- login
- `/users` list route
- any grants E2E that depends on auth bootstrap

### 3. Frontend transport/runtime contract drift

Vitest shows large breakage in the JS runtime layer:

- `Socket` API surface appears missing or renamed
- `NetworkAdapter` expects `socket.connect()` but current object does not satisfy that interface
- `NTT` / `DynamicClass` / schema bootstrap semantics no longer match tests

### 4. UI contract drift in forms, methods, navigation, and topbar

Playwright failures cluster around:

- form rendering structure and field ordering
- method button rendering and counts
- back-button / detail-route behavior
- topbar branding, dropdown, theme control, and sizing

### 5. Streaming/chat rendering mismatches

Streaming appears to partially work in some places, but tests fail because:

- expected text chunks are absent
- expected `.msg-text` content is absent while rich assistant event containers are present
- grants streaming E2E fixture creation gets a 401 before agent creation

### 6. Veille-specific data coercion and shell navigation regressions

The Veille app adds two new failure clusters:

- SQLite bool fields containing `''` / `"''"` are not being coerced to `False` during deserialization
- Veille shell actions that are expected to return to the index/root view now route to concrete list views instead

---

## Backend failures — detailed inventory

## `examples/core` — 4 failures

Shared pattern: the `Comment.like()` and `Product.favorite()` methods appear to return an enriched payload containing join-model metadata (`_field`, `id`, `user`, `created_at`) rather than the smaller action-only payload the tests assert.

| Test | Observed failure | Notes |
|---|---|---|
| `examples/core/tests/test_comment_model.py::TestCommentLike::test_like_creates_new` | Expected `{'action': 'liked'}`; got enriched dict with `_field='likes'`, `id=0`, `user=1`, `created_at=''` | Response payload contract drift |
| `examples/core/tests/test_comment_model.py::TestCommentLike::test_unlike_existing` | Expected `{'action': 'unliked'}`; got enriched dict with `_field='likes'`, `id=5` | Response payload contract drift |
| `examples/core/tests/test_product_model.py::TestProductFavorite::test_favorite_creates_new` | Expected `{'action': 'favorited'}`; got enriched dict with `_field='favorites'`, `id=0`, `user=1`, `created_at=''` | Response payload contract drift |
| `examples/core/tests/test_product_model.py::TestProductFavorite::test_unfavorite_existing` | Expected `{'action': 'unfavorited'}`; got enriched dict with `_field='favorites'`, `id=10` | Response payload contract drift |

## `examples/actors` — 3 failures

| Test | Observed failure | Notes |
|---|---|---|
| `examples/actors/tests/e2e/test_agent_chat.py::TestChatWidgetStreaming::test_send_message_receives_streaming_response` | User and assistant message shells render, but test times out waiting for `.msg-text` content inside the assistant message. Captured HTML shows `.assistant-events` content instead of the simple text node the test expects. | Streaming/chat rendering contract drift |
| `examples/actors/tests/e2e/test_card_overflow.py::test_ntx_item_inputs_have_box_sizing` | Regex could not find a shared `input, textarea { ... }` rule in `ntx-item.css`. | CSS structure/selector contract drift |
| `examples/actors/tests/test_likes_crud.py::TestCommentLikes::test_list_comment_likes_via_populated_comment` | Full suite run observed `likes=[]` where seeded test expected at least 2 likes on populated comment read. | Data hydration/population issue in full run; isolated rerun passed, so this may be flaky or order-sensitive |

## `examples/grants` — 24 failures + 1 error

### Shared root cause clusters

1. **Auth/user route failure**: repeated backend errors from the users actor/model path:
   - `[users] Error in register_user: 'NoneType' object has no attribute 'list'`
   - `[users] Error in login: 'NoneType' object has no attribute 'list'`
   - `[users] CRUD error in list: 'NoneType' object has no attribute 'list'`
2. **Login envelope mismatch in E2E helpers**:
   - helper expects `resp.json()['token']`
   - actual response shape is `{'data': {'token': ...}, '_debug': ...}`
3. **Streaming endpoint/event issues**:
   - no `text` events observed
   - no `done` events observed
   - E2E setup for streaming agent creation returned `401`
4. **Grant route mismatch**:
   - `GET /grants/{id}` and `PUT /grants/{id}` returned `404`

### Per-test inventory

| Test | Observed failure | Cluster |
|---|---|---|
| `examples/grants/tests/e2e/test_agent_chat.py::TestChatWidgetInteraction::test_send_message_via_widget` | Timed out waiting for any chat messages; result returned `{"error": "timeout", "messageCount": 0}` | E2E chat/rendering |
| `examples/grants/tests/e2e/test_agent_live_first_token.py::TestStreamFirstTokenNotDropped::test_agent_live_renders_complete_streamed_answer` | Fixture setup failed while creating a streaming test agent; agent creation returned `401` after login helper extracted no valid token | E2E auth/bootstrap |
| `examples/grants/tests/e2e/test_create_validation.py::test_create_grant_title_only_client_validation` | `_login()` failed because it looked for top-level `token`; actual login payload nested token under `data.token` | Login envelope mismatch |
| `examples/grants/tests/e2e/test_create_validation.py::test_create_grant_title_only_detailed_feedback_analysis` | Same `_login()` failure as above | Login envelope mismatch |
| `examples/grants/tests/e2e/test_create_validation.py::test_create_grant_title_only_error_visibility` | Same `_login()` failure as above | Login envelope mismatch |
| `examples/grants/tests/e2e/test_navigation.py::test_main_list_click_navigates` | Same `_login()` failure as above | Login envelope mismatch |
| `examples/grants/tests/e2e/test_navigation.py::test_back_button_returns_to_list` | Same `_login()` failure as above | Login envelope mismatch |
| `examples/grants/tests/e2e/test_navigation.py::test_hash_deep_link` | Same `_login()` failure as above | Login envelope mismatch |
| `examples/grants/tests/e2e/test_navigation.py::test_sidebar_item_navigates` | Same `_login()` failure as above | Login envelope mismatch |
| `examples/grants/tests/e2e/test_navigation.py::test_agents_sidebar_route_uses_ntx_agent` | Same `_login()` failure as above | Login envelope mismatch |
| `examples/grants/tests/test_agent_live_first_token.py::TestSSEStreamAllTokensDelivered::test_first_text_chunk_is_not_empty` | `POST /agents/{id}/agentic_stream` returned `200`, but the stream yielded **no `text` events** | Streaming event emission |
| `examples/grants/tests/test_agent_live_first_token.py::TestSSEStreamAllTokensDelivered::test_all_text_chunks_concatenated_match_done_answer` | `POST /agents/{id}/agentic_stream` returned `200`, but the stream yielded **no `done` event** | Streaming event emission |
| `examples/grants/tests/test_auth_flow.py::TestRegistrationFlow::test_register_new_user_returns_token` | `/users/register` returned `500` instead of `200/201` with `register_user: 'NoneType' object has no attribute 'list'` | Users actor/model broken |
| `examples/grants/tests/test_auth_flow.py::TestRegistrationFlow::test_register_with_invalid_email_format_succeeds` | `/users/register` returned `500` instead of `200/201` | Users actor/model broken |
| `examples/grants/tests/test_auth_flow.py::TestRegistrationFlow::test_register_with_duplicate_email_returns_409` | `/users/register` returned `500` instead of expected `409` | Users actor/model broken |
| `examples/grants/tests/test_auth_flow.py::TestLoginFlow::test_login_with_correct_credentials_returns_token` | `/users/login` returned `500` instead of `200` | Users actor/model broken |
| `examples/grants/tests/test_auth_flow.py::TestLoginFlow::test_login_with_wrong_password_returns_401` | `/users/login` returned `500` instead of `401` | Users actor/model broken |
| `examples/grants/tests/test_auth_flow.py::TestLoginFlow::test_login_with_non_existent_user_returns_401` | `/users/login` returned `500` instead of `401` | Users actor/model broken |
| `examples/grants/tests/test_auth_flow.py::TestLoginFlow::test_login_email_case_insensitive` | `/users/login` returned `500` instead of `200` | Users actor/model broken |
| `examples/grants/tests/test_auth_flow.py::TestCompleteFlow::test_register_login_use_token_end_to_end` | Initial register step returned `500`, so end-to-end auth bootstrap failed immediately | Users actor/model broken |
| `examples/grants/tests/test_auth_flow.py::TestCompleteFlow::test_create_grant_with_token_from_registration` | Registration response had no top-level `token`; lookup raised `KeyError: 'token'` on top of the upstream register failure | Users actor/model broken + envelope mismatch |
| `examples/grants/tests/test_auth_flow.py::TestCompleteFlow::test_logout_and_relogin_flow` | Login response had no top-level `token`; lookup raised `KeyError: 'token'` on top of the upstream login failure | Users actor/model broken + envelope mismatch |
| `examples/grants/tests/test_boot.py::TestAppBoot::test_all_routes_accessible` | `GET /users` returned `500`; log shows `[users] CRUD error in list: 'NoneType' object has no attribute 'list'` | Users actor/model broken |
| `examples/grants/tests/test_grants_crud.py::TestGrantGet::test_get_grant_by_id` | `GET /grants/1` returned `404` instead of `200` | Grant route/read mismatch |
| `examples/grants/tests/test_grants_crud.py::TestGrantUpdate::test_update_grant_as_admin` | `PUT /grants/1` returned `404` instead of `200` | Grant route/update mismatch |

## `apps/veille` — 9 failures

### Suite summary

| Veille suite | Result |
|---|---|
| `apps/veille/tests/*.py` | ❌ 7 failed / 14 passed |
| `apps/veille/tests/*.mjs` | ❌ 2 failed / 17 passed |

### Shared root cause clusters

1. **Empty-string bool deserialization is broken**
   - `_deserialize_json_fields()` leaves `''` and `"''"` intact for bool fields
   - downstream Pydantic model construction fails with `bool_parsing`
   - this cascades into Veille organization lookup/analyze flows
2. **Source fetch path is not honoring the mocked scrape content path in test expectations**
   - persisted content remained the live/default fetched content instead of the monkeypatched content
   - change detection stayed `False` and `last_scrape_error` showed a hostname resolution error
3. **Veille shell return-to-index regression**
   - actions expected to restore the root slot view now leave the router on explicit list routes

### Per-test inventory

| Test | Observed failure | Cluster |
|---|---|---|
| `apps/veille/tests/test_empty_bool_deserialization.py::TestEmptyStringBoolUnit::test_deserialize_coerces_empty_string_bool` | `_deserialize_json_fields()` left `schedule_enabled=''` instead of coercing it to `False` | Bool deserialization |
| `apps/veille/tests/test_empty_bool_deserialization.py::TestEmptyStringBoolUnit::test_deserialize_coerces_literal_quotes_bool` | `_deserialize_json_fields()` left `schedule_enabled="''"` instead of coercing it to `False` | Bool deserialization |
| `apps/veille/tests/test_empty_bool_deserialization.py::TestSQLiteEmptyBoolRoundTrip::test_list_org_with_empty_bool_in_db` | `OrgModel.list(limit=1)` raised Pydantic `bool_parsing` validation error on `schedule_enabled="''"` | Bool deserialization |
| `apps/veille/tests/test_empty_bool_deserialization.py::TestSQLiteEmptyBoolRoundTrip::test_get_org_with_empty_bool_in_db` | `OrgModel.get(1)` raised the same Pydantic `bool_parsing` validation error on `schedule_enabled="''"` | Bool deserialization |
| `apps/veille/tests/test_empty_bool_deserialization.py::TestAnalyzeCascadeFailure::test_analyze_finds_org_when_bool_field_is_empty_string` | org lookup path swallowed the deserialization failure and ended with `data=[]`, so the existing org was effectively invisible | Bool deserialization cascade |
| `apps/veille/tests/test_source_fetch.py::test_source_fetch_persists_scrape_content_and_hash` | persisted `scraped_content` remained `Example Domain ...` instead of the monkeypatched `'Grant funding program now open'` | Source fetch persistence path |
| `apps/veille/tests/test_source_fetch.py::test_source_fetch_marks_change_when_hash_differs` | `scrape_changed` stayed `False`; `last_scrape_error` captured hostname resolution failure instead of using mocked changed content | Source fetch persistence path |
| `apps/veille/tests/test_frontend_regressions.mjs::new pipeline action returns to the index page` | expected router signature `slot::`, got `ntx-list:model=runs::` | Veille shell navigation |
| `apps/veille/tests/test_frontend_regressions.mjs::topbar analytics action returns to the index page` | expected router signature `slot::`, got `ntx-list:model=Grant::` | Veille shell navigation |

---

## Frontend Vitest failures

### Summary

- Runner summary: **153 failed**, **4 errors**, **1101 passed**, **1 skipped**
- Parsed failure headers from saved output: **155** entries
  - The extra discrepancy comes from file-level suite banners and not from additional unique failing assertions.

### Notable runtime errors

1. `TypeError: this.socket.connect is not a function`
   - surfaced in `NetworkAdapter`
   - points to transport interface mismatch between `NetworkAdapter` and the current socket implementation
2. `SyntaxError: Unexpected token ':'`
   - surfaced while jsdom processed a script in `schema-bootstrap.test.js`
   - suggests SSR/schema preload or embedded script payload is not valid executable JS in test context
3. Two `ERR_WORKER_OUT_OF_MEMORY` worker terminations
   - likely secondary fallout from broader runtime issues and/or runaway test state

### Failure inventory by file

#### `tests/components/ntx-favorites.test.js` — 1 failure

Shared observation: file-level failure banner only; the component suite is failing before or during normal per-test reporting.

- `(file-level failure banner)`

#### `tests/components/ntx-logs.test.js` — 1 failure

Shared observation: file-level failure banner only; similar to `ntx-favorites`, this suite appears to crash before detailed case-level output is rendered.

- `(file-level failure banner)`

#### `tests/components/ntx-profile.test.js` — 1 failure

Shared observation: authenticated profile placeholder contract changed.

- `ntx-profile.js (NTTProfile) > connectedCallback (authenticated) > should show placeholder message about settings`

#### `tests/components/ntx-ref-picker.test.js` — 5 failures

Shared observation: ref-picker style contract is missing or no longer exposed in the way tests expect.

- `ntx-ref-picker.js (NTTRefPicker) > _render > should include styles`
- `ntx-ref-picker.js (NTTRefPicker) > static styles > should have styles defined`
- `ntx-ref-picker.js (NTTRefPicker) > static styles > should contain add-btn styles`
- `ntx-ref-picker.js (NTTRefPicker) > static styles > should contain picker-dropdown styles`
- `ntx-ref-picker.js (NTTRefPicker) > static styles > should contain inline-create styles`

#### `tests/components/ntx-row.test.js` — 1 failure

Shared observation: validation/save flow in table rows no longer reaches the `save` call under conditions the test expects.

- `ntx-row.js (NTTRow) > validation before save > should call save when validation passes`

#### `tests/core/Component.test.js` — 1 failure

Shared observation: foundational `SIZES` / alias constants no longer match the component contract.

- `Component.js > SIZES and ALIASES > should define SIZES array`

#### `tests/core/DynamicClassFunctor.test.js` — 8 failures

Shared observation: the DynamicClass functor/prototype builder is not generating the expected property, setter, method, and value getter behavior.

- `DynamicClass Functor Verification > Property Functor > maps readOnly schema fields to throwing setters`
- `DynamicClass Functor Verification > Property Functor > maps writable schema fields to working setters`
- `DynamicClass Functor Verification > Type Validation Functor > accepts correct types`
- `DynamicClass Functor Verification > Method Functor > maps each schema method to a callable function on instances`
- `DynamicClass Functor Verification > Method Functor > preserves method count`
- `DynamicClass Functor Verification > Value Getter Immutability > returns a new object on each access`
- `DynamicClass Functor Verification > Value Getter Immutability > _data does not contain $schema or $id`
- `DynamicClass Functor Verification > Value Getter Immutability > includes $schema and $id in returned value`

#### `tests/core/NTT.test.js` — 19 failures

Shared observation: the entity registry, DynamicClass creation, READ/CREATE/DELETE flows, and value serialization semantics are all drifting from the expected contract.

- `NTT.js > NTT static registry > static get(addr) > should return NTT instance by entity ref`
- `NTT.js > DynamicClass (prototype factory) > should have properties as getters/setters on prototype`
- `NTT.js > DynamicClass (prototype factory) > should throw on read-only property setter`
- `NTT.js > DynamicClass (prototype factory) > DynamicClass.READ (static) > should create instances from array data`
- `NTT.js > DynamicClass (prototype factory) > DynamicClass.READ (static) > should update existing instances`
- `NTT.js > DynamicClass (prototype factory) > DynamicClass.READ (static) > should handle paginated response {data: [...], meta: {...}}`
- `NTT.js > DynamicClass (prototype factory) > DynamicClass.READ (static) > should handle single entity response`
- `NTT.js > DynamicClass (prototype factory) > DynamicClass.CREATE (static) > should add new instance`
- `NTT.js > DynamicClass (prototype factory) > DynamicClass.CREATE (static) > should update existing instance on duplicate`
- `NTT.js > DynamicClass (prototype factory) > DynamicClass.DELETE (static) > should remove instance from registry`
- `NTT.js > DynamicClass (prototype factory) > instance _response_ > should call pull() after method response`
- `NTT.js > NTT instance > value getter/setter > should include $schema and $id in getter`
- `NTT.js > NTT instance > value getter/setter > should return a new object each access (immutability)`
- `NTT.js > NTT instance > value getter/setter > should not pollute _data with $schema/$id`
- `NTT.js > NTT instance > value getter/setter > should persist property setter changes`
- `NTT.js > NTT instance > toJSON() > should return serializable object`
- `NTT.js > NTT instance > update(data) > should set value with provided data`
- `NTT.js > NTT instance > pull() > should return this for chaining`
- `NTT.js > Helper functions > registerInstance > should create new instances and update existing ones`

#### `tests/integration/actor-messaging.test.js` — 5 failures

Shared observation: frontend actor attach/call routing is not delivering the expected TX lifecycle or replay behavior.

- `Actor Messaging > DynamicClass.ATTACH for instance-level creates and delivers`
- `Actor Messaging > pending ATTACHes replayed after READ creates instances`
- `Actor Messaging > NTT instance ATTACH sends DESCRIBE back to source`
- `Actor Messaging > TT.call sends TX with method name and entity href`
- `Actor Messaging > DynamicClass static call sends TX to class href`

#### `tests/integration/display-mode-cascade.test.js` — 2 failures

Shared observation: the size/alias display mode constants are inconsistent with the integration contract.

- `Display Mode Cascade > SIZES and ALIASES constants > SIZES has exactly 5 entries`
- `Display Mode Cascade > SIZES and ALIASES constants > ALIASES maps all semantic names`

#### `tests/integration/entity-lifecycle.test.js` — 4 failures

Shared observation: entity creation, response refresh, and nested normalization no longer produce expected instance state.

- `Entity Lifecycle > DynamicClass.CREATE adds instance and notifies watchers`
- `Entity Lifecycle > instance _response_ handler triggers pull()`
- `Entity Lifecycle > normalizePopulated converts inline objects to href arrays`
- `Entity Lifecycle > DynamicClass.READ with existing instance updates rather than creates new`

#### `tests/integration/form-entity-binding.test.js` — 21 failures

Shared observation: the form generator is not honoring the schema contract across display/edit modes, hidden fields, widgets, field groups, lists, methods, and validation attributes.

- `Form Generation > getForm in edit mode renders input for name`
- `Form Generation > field_order from schema.ui is respected`
- `Form Generation > fields with ui.display=false are hidden`
- `Form Generation > protected fields are hidden in edit mode`
- `Form Generation > currency widget renders $ prefix`
- `Form Generation > currency widget in edit mode renders currency-input with $ symbol`
- `Form Generation > textarea widget renders <textarea> in edit mode`
- `Form Generation > description rendered as header in display mode`
- `Form Generation > boolean field renders checkbox`
- `Form Generation > number field renders number input`
- `Form Generation > field groups render fieldsets with legends`
- `Form Generation > array fields render list-field container`
- `Form Generation > attached methods render ntx-method elements after target field`
- `Form Generation > methods are hidden in edit mode`
- `Form Generation > validationAttrs generates correct HTML5 attributes`
- `Form Generation > validationAttrs with no constraints returns empty string`
- `Form Generation > formatDisplayValue handles currency widget`
- `Form Generation > formatDisplayValue handles selfref type`
- `Form Generation > formatDisplayValue returns plain value for standard fields`
- `Form Generation > getListInput with show-more for arrays > VISIBLE_COUNT`
- `Form Generation > getListInput resolves child tag from $defs renderer hints`

#### `tests/integration/method-execution.test.js` — 9 failures

Shared observation: instance/class method calls, payload routing, pull/refresh behavior, and response inbox routing are all inconsistent.

- `Method Execution > instance method call sends TX to entity href`
- `Method Execution > class-level call sends TX to DynamicClass href`
- `Method Execution > method with payload includes data in TX`
- `Method Execution > _response_ handler triggers pull() on instance`
- `Method Execution > pull() sends READ TX to instance href`
- `Method Execution > pull() with populate depth includes depth parameter`
- `Method Execution > DynamicClass.CREATE adds new instance and notifies watchers`
- `Method Execution > DynamicClass.CREATE with existing id updates instead of creating`
- `Method Execution > call with meta.inbox routes response to correct handler`

#### `tests/integration/nested-entities.test.js` — 8 failures

Shared observation: populated refs and nested collection normalization are not producing the expected href-backed entity graph.

- `Nested Entities > Product comments href array stored after normalization`
- `Nested Entities > populated collection {data, meta} normalized to href array`
- `Nested Entities > populated single Ref normalized to href string`
- `Nested Entities > comment with parent_id (self-referential) is stored correctly`
- `Nested Entities > nested entity DELETE removes from parent collection on pull`
- `Nested Entities > normalizePopulated handles mixed href strings and objects`
- `Nested Entities > deeply nested population (depth=2) normalizes recursively`
- `Nested Entities > instance _response_ triggers pull for method responses`

#### `tests/integration/schema-bootstrap.test.js` — 4 failures

Shared observation: schema bootstrap is producing wrong API base URLs and not reliably registering created instances.

- `Schema Bootstrap Flow > SCHEMA handler creates DynamicClass from schema data`
- `Schema Bootstrap Flow > DynamicClass instances are stored in static instances map`
- `Schema Bootstrap Flow > DynamicClass value getter injects $schema and $id`
- `Schema Bootstrap Flow > single entity READ normalizes to array and creates instance`

#### `tests/transport/NetworkAdapter.test.js` — 1 failure

Shared observation: websocket-mode send path cannot delegate because the socket implementation does not satisfy the expected API.

- `NetworkAdapter.js > send(event) — WS mode > should delegate to socket.sendEvent when in ws mode with socket available`

#### `tests/transport/Socket.test.js` — 64 failures

Shared observation: this is the largest frontend failure cluster. The current `Socket` implementation appears to have lost or renamed most of the public surface the tests rely on: constructor state, `register`, `unregister`, `heartbeat`, `connect`, `reconnect`, `disconnect`, target registration, dispatch, message handling, enable/disable, watchdog, and websocket send helpers.

- `Socket.js > constructor(url, targets, ttl) > should set state to CONNECTING`
- `Socket.js > constructor(url, targets, ttl) > should set default ttl to 1000`
- `Socket.js > constructor(url, targets, ttl) > should accept custom ttl`
- `Socket.js > constructor(url, targets, ttl) > should set retries to 0`
- `Socket.js > constructor(url, targets, ttl) > should set isDisabled to true`
- `Socket.js > constructor(url, targets, ttl) > should initialize empty queue`
- `Socket.js > constructor(url, targets, ttl) > should register in Socket.resources`
- `Socket.js > constructor(url, targets, ttl) > should set itself as defaultSocket`
- `Socket.js > constructor(url, targets, ttl) > should create WebSocket connection`
- `Socket.js > constructor(url, targets, ttl) > should store targets`
- `Socket.js > static register(name, socket) > should add socket to resources`
- `Socket.js > static register(name, socket) > should warn on overwrite`
- `Socket.js > static unregister(name) > should disconnect and remove socket from resources`
- `Socket.js > heartbeat(msg) > should update lrh timestamp`
- `Socket.js > heartbeat(msg) > should call sendMessage with heartbeat key`
- `Socket.js > heartbeat(msg) > should default msg to true`
- `Socket.js > connect(url, callback) > should create new WebSocket`
- `Socket.js > connect(url, callback) > should set state to CONNECTING`
- `Socket.js > connect(url, callback) > should store connect callback`
- `Socket.js > connect(url, callback) > should return this for chaining`
- `Socket.js > connect(url, callback) > should set state to FAILED on WebSocket creation error`
- `Socket.js > reconnect() > should increment retries`
- `Socket.js > reconnect() > should close existing websocket`
- `Socket.js > reconnect() > should set state to RECONNECT`
- `Socket.js > reconnect() > should call disconnect when retries exceed MAX_TRIES`
- `Socket.js > disconnect() > should set state to DISCONNECTED`
- `Socket.js > disconnect() > should reset retries to 0`
- `Socket.js > disconnect() > should clear interval if set`
- `Socket.js > setTarget(target, callback) > should add target callback`
- `Socket.js > setTarget(target, callback) > should return this for chaining`
- `Socket.js > removeTarget(id) > should remove target`
- `Socket.js > removeTarget(id) > should return this for chaining`
- `Socket.js > dispatchEvent(event) > should call target callback with event`
- `Socket.js > dispatchEvent(event) > should log error when target not found`
- `Socket.js > onMessage(msg) > should set state to CONNECTED`
- `Socket.js > onMessage(msg) > should process heartbeat messages by calling heartbeat()`
- `Socket.js > onMessage(msg) > should update lrh timestamp`
- `Socket.js > onMessage(msg) > should log error for invalid JSON`
- `Socket.js > onMessage(msg) > should flush queued messages when connected`
- `Socket.js > sendMessage(key, msg, plain) > should queue message when websocket is not ready`
- `Socket.js > sendMessage(key, msg, plain) > should send JSON.stringify when readyState is 1`
- `Socket.js > sendMessage(key, msg, plain) > should send without key wrapper when key is null/undefined`
- `Socket.js > sendMessage(key, msg, plain) > should send plain message when plain=true`
- `Socket.js > sendMessage(key, msg, plain) > should return this when message is sent`
- `Socket.js > sendMessage(key, msg, plain) > should return undefined when message is queued`
- `Socket.js > sendEvent(event) > should call websocket.send with event.toString()`
- `Socket.js > onOpen(event) > should set state to CONNECTING`
- `Socket.js > onOpen(event) > should call connectCallback`
- `Socket.js > onOpen(event) > should send allStatesRequest`
- `Socket.js > onOpen(event) > should call heartbeat`
- `Socket.js > onClose(event) > should set state to DISCONNECTED`
- `Socket.js > onClose(event) > should call disable()`
- `Socket.js > onClose(event) > should log warning`
- `Socket.js > disable() > should set isDisabled to true`
- `Socket.js > disable() > should call target callbacks when not already disabled`
- `Socket.js > disable() > should not call targets when already disabled`
- `Socket.js > enable() > should set isDisabled to false`
- `Socket.js > enable() > should call target callbacks when was disabled`
- `Socket.js > enable() > should not call targets when already enabled`
- `Socket.js > watchdog() > should transition CONNECTING to WAITING`
- `Socket.js > watchdog() > should transition RECONNECT to WAITING`
- `Socket.js > watchdog() > should call reconnect when FAILED`
- `Socket.js > watchdog() > should enable on CONNECTED state`
- `Socket.js > watchdog() > should transition to WAITING when TTL exceeded`

---

## Frontend Playwright failures

### Summary

- **135 failed**
- **405 passed**
- **24 did not run**

The browser suite failures are less about infrastructure crashing and more about browser-visible contract drift: permissions, form structure, method rendering, topbar/sidebar layout, router/back-button behavior, and comments/favorites/likes UI semantics.

### Failure inventory by spec file

#### `tests/e2e/accessibility-unit.spec.js` — 1 failure

Shared observation: focus-visible styling or selector coverage is no longer satisfying the accessibility expectation.

- `accessibility — Color & Contrast › interactive elements have visible focus indicators via :focus-visible`

#### `tests/e2e/authentication.spec.js` — 2 failures

Shared observation: authenticated topbar/dropdown content no longer matches the expected auth UI contract.

- `Authentication › user dropdown contains email, role, theme toggle, logout`
- `Authentication › favorites link visible when authenticated`

#### `tests/e2e/authorization.spec.js` — 6 failures

Shared observation: schema-declared access rules and the browser-observed authorization behavior are out of sync.

- `Authorization UI › schema access rules are present in schema response`
- `Authorization UI › product read access allows anonymous`
- `Authorization UI › product create requires authentication`
- `Authorization UI › product delete requires admin role`
- `Authorization UI › product update is owner OR admin`
- `Authorization UI › protected fields marked in schema`

#### `tests/e2e/comments.spec.js` — 3 failures

Shared observation: comment affordances or comment result wiring is broken on product detail pages.

- `Comments › comment method visible on product detail`
- `Comments › comments list visible on product detail`
- `Comments › submit comment via API adds comment`

#### `tests/e2e/error-scenarios.spec.js` — 3 failures

Shared observation: HTTP auth/error status codes or error envelope structure differ from test expectations.

- `Error Scenarios › 401 response when accessing protected endpoint without token`
- `Error Scenarios › 403 on unauthorized delete`
- `Error Scenarios › API returns proper error structure`

#### `tests/e2e/favorites.spec.js` — 2 failures

Shared observation: authenticated favorites navigation affordance is missing or not routing as expected.

- `Favorites › favorites link visible for authenticated user`
- `Favorites › clicking favorites navigates to #@favorites`

#### `tests/e2e/flow-auth-lifecycle.spec.js` — 2 failures

Shared observation: registration flow behavior differs from the test contract.

- `Auth Lifecycle — Registration Flow › register a new user via API and login with those credentials`
- `Auth Lifecycle — Registration Flow › register with empty name — backend accepts it (no server-side validation)`

#### `tests/e2e/flow-comments.spec.js` — 10 failures

Shared observation: comment API payloads, ownership fields, visibility, count badges, nested reply handling, anonymous rejection, and persistence/escaping behavior are all drifting.

- `Comment Lifecycle — Add Comment via API › comment API response contains expected fields`
- `Comment Lifecycle — Add Comment via API › comment user_owner is set to the authenticated user`
- `Comment Lifecycle — UI Display › comments list visible on product detail`
- `Comment Lifecycle — UI Display › comment count badge shows correct number`
- `Comment Lifecycle — UI Display › comment method button visible on product detail`
- `Comment Lifecycle — UI Display › comment items rendered as ntx-item sub-components`
- `Comment Lifecycle — Nested Replies › reply to a comment sets parent_id correctly`
- `Comment Lifecycle — Anonymous User › anonymous user cannot comment (403)`
- `Comment Lifecycle — Edge Cases › comment with special characters is stored correctly`
- `Comment Lifecycle — Edge Cases › comment with unicode and emoji is stored correctly`

#### `tests/e2e/flow-data-integrity.spec.js` — 4 failures

Shared observation: updates are not consistently reflected across UI/API, and schema/entity shape metadata is drifting.

- `Data Integrity — Update and Verify Everywhere › update reflected in list view`
- `Data Integrity — Comment FK Relationship › comment $schema and $id URLs are correct`
- `Data Integrity — Schema Consistency › schema properties match entity data structure`
- `Data Integrity — Schema Consistency › required fields in schema are always present in entity data`

#### `tests/e2e/flow-error-resilience.spec.js` — 2 failures

Shared observation: auth error code expectations and comment XSS handling differ from test expectations.

- `Error Resilience — API Error Responses › DELETE /products/{id} without auth returns 403`
- `Error Resilience — XSS Prevention › comment with script tag in description does not execute`

#### `tests/e2e/flow-favorites-and-likes.spec.js` — 6 failures

Shared observation: favorite/comment-like API responses and UI affordances are not matching the browser contract.

- `Favorite — Toggle via API › favorite a product and verify action response`
- `Favorite — Without Auth › favorite without auth returns 403`
- `Favorite — UI Button › favorite button visible on product detail`
- `Favorite — UI Button › favorite button shows count badge`
- `Comment Like — Toggle via API › like a comment and verify toggle behavior`
- `Comment Like — UI Button › like button visible on comment items in product detail`

#### `tests/e2e/flow-navigation-deep.spec.js` — 4 failures

Shared observation: back-button visibility/state and auth-driven detail-view affordances no longer align with router expectations.

- `Navigation — List to Detail to Back › back button returns to list view`
- `Navigation — Auth State Changes › edit button appears after login on product detail`
- `Navigation — Auth State Changes › edit button disappears after logout`
- `Navigation — State Consistency › router shows back button on detail view, hidden at root`

#### `tests/e2e/flow-permissions-matrix.spec.js` — 9 failures

Shared observation: API permissions and UI permission affordances are not aligned with the declared matrix.

- `Permissions — Anonymous User (API) › cannot view product detail (403)`
- `Permissions — Anonymous User (API) › cannot delete product (403)`
- `Permissions — Anonymous User (API) › cannot add comment (403)`
- `Permissions — Anonymous User (API) › cannot favorite product (403)`
- `Permissions — Authenticated User (API) › can view product detail (200 OK)`
- `Permissions — Authenticated User (API) › can update any product (Product has no owner check)`
- `Permissions — Authenticated User (API) › can add comment to any product (200 OK)`
- `Permissions — Authenticated User (UI) › edit button visible for authenticated user on product detail`
- `Permissions — Role Escalation Prevention › registration with role=admin is ignored (user gets regular role)`

#### `tests/e2e/flow-product-crud.spec.js` — 9 failures

Shared observation: product detail authorization, populated detail reads, edit affordances, and UI persistence after create/update are broken.

- `Product CRUD — Create via API › created product appears in UI after reload`
- `Product CRUD — Read › anonymous user cannot view product detail (403 — read on detail requires auth)`
- `Product CRUD — Read › authenticated user can view product detail`
- `Product CRUD — Read › product detail with depth=1 returns populated children`
- `Product CRUD — Update Flow › updated product visible in UI after reload`
- `Product CRUD — Update without Auth › anonymous user cannot update product (403)`
- `Product CRUD — UI Edit Flow › edit button visible for authenticated user on product detail`
- `Product CRUD — UI Edit Flow › edit mode shows form inputs`
- `Product CRUD — Create Update Verify Persistence › verify updated name persists in UI after reload`

#### `tests/e2e/flow-responsive-breakpoints.spec.js` — 2 failures

Shared observation: back-button and social affordances are not surviving responsive layouts consistently.

- `Responsive — Mobile (360x640) › back button returns to list`
- `Responsive — Desktop (1280x720) › comments and favorites visible and functional on desktop`

#### `tests/e2e/flow-social-chain.spec.js` — 1 failure

Shared observation: the long-form social chain scenario fails at the first registration step, blocking the remaining chained phases.

- `Social Chain — Complete User Journey › Phase 1: Register a fresh user`

#### `tests/e2e/form-rendering-unit.spec.js` — 15 failures

Shared observation: display-mode rendering, field order, group fieldsets, list-field structure, favorites/comments sections, and labeling all diverge from the expected DOM contract.

- `form-rendering — Field Type Rendering (Display Mode) › currency widget renders with $ prefix in display mode`
- `form-rendering — Field Type Rendering (Display Mode) › currency display shows formatted number (e.g. $29.99)`
- `form-rendering — Field Type Rendering (Display Mode) › header renders name as h2; description as h4 only when non-empty`
- `form-rendering — Field Type Rendering (Display Mode) › name renders as h2 with data-value="name" and non-empty text`
- `form-rendering — Field Type Rendering (Display Mode) › detail header uses uppercase text-transform in large detail view only`
- `form-rendering — Field Type Rendering (Display Mode) › display mode shows values as divs (not inputs)`
- `form-rendering — Field Order › fields render in ui.field_order sequence`
- `form-rendering — Groups/Fieldsets › grouped fields render inside fieldset elements`
- `form-rendering — Groups/Fieldsets › each fieldset has a legend with the group name`
- `form-rendering — Groups/Fieldsets › group "main" contains price field (name/description are header fields)`
- `form-rendering — Groups/Fieldsets › group "Social" contains comments list field`
- `form-rendering — List Fields (Array/Ref) › comments array renders as .list-field with data-model="Comment"`
- `form-rendering — List Fields (Array/Ref) › list-field has header with label and count badge`
- `form-rendering — List Fields (Array/Ref) › favorites array renders as .list-field with data-model="Like"`
- `form-rendering — Labels › non-header fields have label elements with field title`

#### `tests/e2e/form-validation.spec.js` — 3 failures

Shared observation: schema-driven rendering for currency, textarea, and groups does not match the browser form contract.

- `Form Validation › currency widget shows $ prefix in display mode`
- `Form Validation › textarea widget renders for description field`
- `Form Validation › field groups render as fieldsets`

#### `tests/e2e/grants-create-validation.spec.js` — 4 failures

Shared observation: grants inline create validation flow appears to be making unintended requests and/or entering error loops.

- `Grant Create — Number Field Validation › inline create with valid text fields and empty optional numbers submits without error loop`
- `Grant Create — Number Field Validation › submitting empty inline create form sends no POST request`
- `Grant Create — Number Field Validation › ERROR events never reach the backend as HTTP requests`
- `Grant Create — Number Field Validation › backend validation error returns proper HTTP status, no error loop`

#### `tests/e2e/likes.spec.js` — 4 failures

Shared observation: like method presence, API behavior, and auth failure shape are all inconsistent with the test contract.

- `Likes › like method exists in schema`
- `Likes › like via API succeeds with auth`
- `Likes › like count accessible via API`
- `Likes › like without auth fails`

#### `tests/e2e/logs-panel.spec.js` — 1 failure

Shared observation: logs panel entry styling/level coloration does not satisfy the expected presentation contract.

- `Logs Panel › entries are color-coded by level`

#### `tests/e2e/ntx-item-unit.spec.js` — 5 failures

Shared observation: detail-mode item rendering is not producing the expected price display, list-field blocks, method renderers, and fieldset grouping.

- `ntx-item — MD/LG/XL Detail Display › detail view (xl) shows name and price with $`
- `ntx-item — MD/LG/XL Detail Display › detail view shows comments section as .list-field`
- `ntx-item — MD/LG/XL Detail Display › comments section has list-field-count badge`
- `ntx-item — MD/LG/XL Detail Display › detail view shows ntx-method elements for exposed methods`
- `ntx-item — MD/LG/XL Detail Display › groups render as fieldset elements`

#### `tests/e2e/ntx-logs-unit.spec.js` — 8 failures

Shared observation: log entries are missing expected structure, filtering behavior, badge counts, and clear/repopulate interactions.

- `ntx-logs — Log Entries › entries exist after page load`
- `ntx-logs — Log Entries › each entry has level-dot, level, time elements`
- `ntx-logs — Log Entries › entries have data-level attribute for filtering`
- `ntx-logs — Log Entries › entry time shows valid HH:MM:SS format`
- `ntx-logs — Filtering › clicking filter activates it and hides non-matching entries`
- `ntx-logs — Clear › clear button removes all entries and resets badge`
- `ntx-logs — Clear › new logs still appear after clear`
- `ntx-logs — Badge Counter › badge count reflects Logging.size (capped at buffer max)`

#### `tests/e2e/ntx-method-unit.spec.js` — 13 failures

Shared observation: both favorite and comment method renderers are missing expected DOM structure, icons, counts, placeholder copy, and/or API behavior.

- `ntx-method — Product Favorite Button › favorite method element exists on product detail`
- `ntx-method — Product Favorite Button › favorite button has star icon SVG`
- `ntx-method — Product Favorite Button › favorite button shows count badge`
- `ntx-method — Product Favorite Button › favorite button is clickable (has .method-btn)`
- `ntx-method — Product Favorite Button › favorite button uses button layout (pill-shaped)`
- `ntx-method — Product Comment Method (Inline) › comment method element exists on product detail`
- `ntx-method — Product Comment Method (Inline) › comment method has inline layout with textarea`
- `ntx-method — Product Comment Method (Inline) › comment textarea has placeholder "Add your comment..."`
- `ntx-method — Product Comment Method (Inline) › comment form has "Post" submit button`
- `ntx-method — Edge Cases › method button renders with correct structure`
- `ntx-method — Edge Cases › method component has correct attributes from schema`
- `ntx-method — Edge Cases › favorite API call works with auth`
- `ntx-method — Edge Cases › favorite API call fails without auth (401)`

#### `tests/e2e/ntx-router-unit.spec.js` — 2 failures

Shared observation: router root rendering and chrome structure differ from the expected shell contract.

- `ntx-router — Root State (No Hash) › at root, router shows slot content (ntx-list)`
- `ntx-router — Edge Cases › router chrome has correct CSS structure`

#### `tests/e2e/ntx-topbar-unit.spec.js` — 5 failures

Shared observation: topbar branding, dropdown content, theme toggle labeling/icon, and height all differ from the old UI contract. Saved output explicitly showed examples like expected title containing `NTT` but received `N3TX Example`, expected theme toggle label text but received empty string, and expected `56px` height but received `72px`.

- `ntx-topbar — Anonymous State › topbar renders with .topbar nav and brand`
- `ntx-topbar — Authenticated State › dropdown contains email, role, theme, profile, logout`
- `ntx-topbar — Theme Toggle › clicking theme toggle changes theme and shows correct label`
- `ntx-topbar — Theme Toggle › theme toggle has SVG icon`
- `ntx-topbar — Edge Cases › topbar height is 56px`

#### `tests/e2e/performance.spec.js` — 1 failure

Shared observation: the test timed out waiting for bootstrap/item visibility and then failed writing profiling output because the target directory did not exist.

- `Performance Profiling › 2. Page load + bootstrap timing`

#### `tests/e2e/product-detail.spec.js` — 1 failure

Shared observation: the router/back-button contract at root no longer matches expectations.

- `Product Detail Navigation › back button not visible at root`

#### `tests/e2e/veille-chat.spec.js` — 6 failures

Shared observation: Veille chat tests are failing very early in auth/navigation. Saved output showed repeated `page.waitForURL('/')` timeouts after login button submission.

- `Veille Assistant chat › second reply keeps the chat textarea visible inside the panel viewport`
- `Veille Assistant chat › second reply keeps the send button visible inside the panel viewport`
- `Veille Assistant chat › first reply keeps the chat shell mounted and usable`
- `Veille Assistant chat › second reply does not unmount the chat component`
- `Veille Assistant chat › second reply preserves route and agent detail visibility`
- `Veille Assistant chat › dashboard opens Assistant and completes a deterministic threaded chat flow`

#### `tests/e2e/visual-regression.spec.js` — 1 failure

Shared observation: the test hit a `localStorage` access security error while checking immediate theme application.

- `Visual Regression › no unstyled flash — theme applied immediately`

---

## Priority triage order for later fixing

This section is intentionally brief; it exists only to help sequence future work.

1. **Grants users/auth route breakage** — largest backend blocker; breaks many grants suites
2. **Frontend transport contract (`Socket` + `NetworkAdapter`)** — largest single frontend runtime cluster
3. **`NTT` / `DynamicClass` / schema bootstrap regressions** — central entity/runtime failure surface
4. **Formidable/form rendering regressions** — high blast radius across Vitest + Playwright
5. **Method/comment/favorite/like UI contract drift** — high-visible product behavior failures
6. **Navigation/topbar/router contract drift** — browser-shell consistency failures

## Notes

- This report intentionally records the failures as observed from the test outputs and targeted reruns.
- It does **not** assume the tests are always correct; some failures may reflect intended product or contract changes.
- The actors comment-like population failure was seen in the full-suite run but did not reproduce on isolated rerun, so it should be treated as potentially flaky or order-dependent until revalidated.
