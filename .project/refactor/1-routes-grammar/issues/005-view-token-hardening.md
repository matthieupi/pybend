# Issue 005 Plan: View Token Validation and Unsafe Route Hardening

## Goal

Finalize and implement the safety policy for view route tokens and malformed
route shapes introduced by issues 001–004.

This issue hardens both sides of the hypermedia route grammar:

```text
Frontend hash routes:
  Product/@view
  Product/1/@view

Backend HTML routes:
  GET /Product/@view
  GET /Product/1/@view
```

The outcome should be deterministic, test-covered behavior for:

- safe custom view names
- unknown view names
- numeric view names
- traversal-like view names
- extra path segments
- query conflicts such as `@table?view=list`
- generated HTML escaping

This issue is marked HITL because it locks a product/security policy: how much
ergonomic fallback to allow for unknown view names.

---

## Accepted policy decision

Accepted policy for this refactor:

```text
Require schema-declared renderers for custom/unknown view tokens.
Reject unsafe view tokens.
Reject unsupported extra path segments.
```

In practice:

```text
Product/@custom-card       -> rejected unless schema.ui.renderer['custom-card'] exists
Product/@ntx-custom-card   -> rejected unless schema.ui.renderer['ntx-custom-card'] exists
Product/@0                 -> rejected unless schema.ui.renderer['0'] exists
Product/@../../x           -> rejected / invalid
Product/@<script>          -> rejected / invalid
Product/@table/extra       -> rejected / invalid
Product/1/@item/extra      -> rejected / invalid
```

Why this policy:

- It makes the backend schema authoritative for custom presentation surfaces.
- It avoids arbitrary path traversal or markup injection through route tokens.
- It prevents typos such as `@detial` from silently mounting fallback tags.
- It keeps framework-owned known views (`list`, `table`, `item`, `detail`,
  `chat`) ergonomic while requiring application-specific views to be declared.

The earlier safe custom fallback behavior from issues 002/004 is intentionally
superseded here: custom view names remain valid route tokens, but they only
resolve when declared in `schema.ui.renderer`.

---

## Safe token contract

Use one shared token definition for both frontend and backend behavior:

```text
^[A-Za-z0-9][A-Za-z0-9_-]*$
```

Properties:

- first character must be alphanumeric
- remaining characters may be alphanumeric, underscore, or hyphen
- no slashes
- no dots
- no whitespace
- no percent-decoded path/control characters
- no markup delimiters
- empty token is not a named view; `@` is the default view marker

Examples:

```text
Allowed:
  table
  list
  item
  detail
  chat
  run
  custom-card
  ntx-custom-card
  view_2
  0

Rejected:
  ../../x
  ../x
  x/y
  x.y
  x y
  <script>
  @evil
  %2e%2e
```

Note: a route segment includes the `@` marker externally, but the validated view
token is the part after `@`.

---

## Frontend behavior contract

### Valid view routes

These remain valid:

```text
Product/@
Product/@table
Product/1/@
Product/1/@item
Product/1/@chat
Product/1/@run
```

Custom/unknown tokens such as `custom-card`, `ntx-custom-card`, and `0` are
only valid for resolution when the model schema declares a matching renderer key.

### Invalid route shapes

Malformed route shapes should not silently become another valid route type.

Recommended parse result for invalid route strings:

```javascript
{ type: 'invalid', route, reason: '...' }
```

Then:

```javascript
resolveRoute({ type: 'invalid' }) -> null
buildRoute({ type: 'invalid' }) -> ''
```

This makes invalid routes deterministic without mounting arbitrary components.

Invalid examples:

```text
Product/@/extra
Product/@table/extra
Product/1/@/extra
Product/1/@item/extra
Product/@../../x
Product/1/@../../x
Product/@%2e%2e
Product/@<script>
```

### Query conflict behavior

Path view selection wins over query view selection:

```text
Product/@table?view=list -> view is table
Product/1/@item?view=detail -> view is item
```

The query `view` param is internal and must not be passed as a DOM attr.

For member view routes, `method` query params must not become method attrs:

```text
Product/1/@item?method=run -> member view route, no attrs.method
```

Other safe query params continue to pass through:

```text
Product/@table?limit=10 -> attrs.limit = '10'
Product/1/@chat?thread=abc -> attrs.thread = 'abc'
```

### Root app `@`

Preserve existing root app-route behavior for non-model routes. Recommended:

```text
@profile -> app route
@settings?tab=security -> app route
@ -> app route with empty app only if current behavior already does this;
     otherwise treat as invalid/home consistently and test it.
```

Implementation should first check current behavior and preserve it unless it is
clearly unsafe. The important distinction is that root `@profile` is not a model
view route.

---

## Backend behavior contract

### Valid view routes

Backend `ViewableMixin` routes should accept safe tokens:

```text
GET /Product/@table
GET /Product/@custom-card
GET /Product/@0
GET /Product/1/@item
GET /Product/1/@chat
GET /Product/1/@run
GET /Product/1/@0
```

Known framework views remain built in:

```text
collection: list, table
member:     item, detail, chat
```

Safe unknown views require `schema.ui.renderer[view]`; otherwise backend HTML
routes return a deterministic client error.

### Invalid view tokens

Unsafe named views should return a deterministic client error:

```text
HTTP 400 Bad Request
```

with a stable detail message such as:

```json
{"detail": "Invalid view name"}
```

Invalid examples:

```text
GET /Product/@../../x
GET /Product/@%2e%2e
GET /Product/@<script>
GET /Product/1/@../../x
GET /Product/1/@<script>
```

### Extra path segments

Unsupported extra path segments should not match view routes:

```text
GET /Product/@table/extra
GET /Product/1/@item/extra
```

Recommended behavior:

```text
404 Not Found
```

Reason: the route grammar does not define those shapes. They are not invalid
tokens inside a valid route; they are unsupported routes.

### Generated HTML escaping

All generated HTML attrs derived from model/ref/view data must be escaped before
injection.

Escape at least:

```text
tag name validation/fallback result
model attr
ref attr
display attr
any future boot metadata containing view
```

Because tag names cannot be safely HTML-escaped into arbitrary custom element
names, the resolved tag itself must be validated as a safe custom-element tag
before use.

Recommended safe tag pattern:

```text
^[a-z][a-z0-9]*(-[a-z0-9]+)+$
```

This requires a hyphen, matching custom element naming expectations. Built-in
fallbacks like `ntx-list`, `ntx-table`, `ntx-item`, and `ntx-chat` satisfy it.

Schema-declared renderers should also be validated before being inserted as tag
names. If a schema renderer is invalid, return a deterministic error or fall
back only if the fallback is safe and documented. Recommended: deterministic
error in backend HTML generation, because an invalid schema renderer is a
developer/configuration problem.

---

## Module shape

### 1. Shared frontend route helpers

Module:

```text
Router.js route functions
```

Add small internal helpers:

```javascript
const VIEW_TOKEN_RE = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;

function isSafeViewToken(token) { ... }
function invalidRoute(route, reason) { ... }
function stripInternalParams(params) { ... }
```

Parser should reject or invalidate:

```text
too many path segments
unsafe view token
ambiguous malformed @ segment
```

Resolver should return `null` for invalid routes.

### 2. Backend ViewableMixin safety helpers

Module:

```text
n3tx-ui ViewableMixin / adjacent view helper module
```

Add backend helpers near route rendering:

```python
VIEW_TOKEN_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]*$')
TAG_RE = re.compile(r'^[a-z][a-z0-9]*(-[a-z0-9]+)+$')

def validate_view_token(view: str | None) -> str | None: ...
def validate_component_tag(tag: str) -> str: ...
def html_attr(value: object) -> str: ...
```

Use these helpers in:

```text
collection named view rendering
member named view rendering
any future view route rendering
```

### 3. View resolver behavior

Existing resolver behavior from issues 001–004 remains for default and known
framework views, but custom fallback is removed unless schema-declared:

```text
schema renderer -> validate component tag
known fallback -> known safe tag
unknown custom token -> invalid/null on frontend, 400 on backend
```

---

## Test-first plan

### Frontend parser negative tests

Update:

```text
tests/frontend/tests/core/route-functions.test.js
```

Add cases:

```javascript
expect(parseRoute('Product/@/extra').type).toBe('invalid');
expect(parseRoute('Product/@table/extra').type).toBe('invalid');
expect(parseRoute('Product/1/@/extra').type).toBe('invalid');
expect(parseRoute('Product/1/@item/extra').type).toBe('invalid');

expect(parseRoute('Product/@../../x').type).toBe('invalid');
expect(parseRoute('Product/1/@../../x').type).toBe('invalid');
expect(parseRoute('Product/@<script>').type).toBe('invalid');
```

Safe token cases:

```javascript
expect(parseRoute('Product/@0')).toMatchObject({ view: '0', isViewRoute: true });
expect(parseRoute('Product/1/@0')).toMatchObject({ view: '0', isViewRoute: true });
expect(parseRoute('Product/@custom-card')).toMatchObject({ view: 'custom-card' });
expect(parseRoute('Product/1/@custom-card')).toMatchObject({ view: 'custom-card' });
```

Query conflict cases:

```javascript
const collection = resolveRoute(parseRoute('Product/@table?view=list&limit=10'), getSchema);
expect(collection.tag).toBe(/* table renderer */);
expect(collection.attrs).toEqual({ model: 'Product', limit: '10' });

const member = resolveRoute(parseRoute('Product/1/@item?method=run&tab=history'), getSchema);
expect(member.attrs.method).toBeUndefined();
expect(member.attrs.tab).toBe('history');
```

Invalid resolve/build cases:

```javascript
expect(resolveRoute(parseRoute('Product/@/extra'))).toBeNull();
expect(buildRoute(parseRoute('Product/@/extra'))).toBe('');
```

### Router state tests

Update:

```text
tests/frontend/tests/core/Router.test.js
tests/frontend/tests/integration/router-navigation.test.js
```

Add tests proving invalid routes do not crash:

```text
NAVIGATE('Product/@/extra') sets current string if router state remains string-based,
but resolved is null and DOM does not mount arbitrary component.
```

Recommended state policy:

- Router may keep the current route string for URL fidelity.
- `resolved` returns null for invalid route shapes.
- `ntx-router` shows the home/empty slot or no mounted view for invalid routes.

If a stronger invalid-route UX is preferred later, add an error route component
in a separate issue.

### Router DOM tests

Update:

```text
tests/frontend/tests/components/ntx-router.test.js
```

Required assertions:

```text
Deep-link #Product/@/extra does not mount <ntx-extra> or any arbitrary component.
Deep-link #Product/1/@item/extra does not mount arbitrary component.
Existing valid custom safe route still mounts expected fallback.
```

### Backend ViewableMixin tests

Update:

```text
packages/n3tx-ui/src/n3tx_ui/tests/test_viewable_mixin.py
```

Required helper tests:

```text
validate_view_token accepts table, custom-card, ntx-custom-card, 0
validate_view_token rejects ../x, ../../x, x/y, x.y, x y, <script>, empty string for named route
validate_component_tag accepts ntx-list and ntx-custom-card
validate_component_tag rejects script, div, ntx, ntx/<bad>, ntx-<script>
html_attr escapes quotes and angle brackets
```

Backend route behavior tests:

```text
GET /Product/@../../x -> 400
GET /Product/1/@../../x -> 400
GET /Product/@<script> -> 400 or 404 depending URL encoding, but never HTML with injected content
GET /Product/@table/extra -> 404
GET /Product/1/@item/extra -> 404
GET /Product/@0 -> 200 text/html with safe fallback tag
GET /Product/1/@0 -> 200 text/html with safe fallback tag
```

Schema renderer safety tests:

```text
invalid schema renderer tag is rejected by backend HTML generation
valid schema renderer tag is used
```

### Backend direct route tests

Update focused direct route tests, if separate from `n3tx-ui` helper tests:

```text
packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py
```

Required assertions:

```text
invalid backend view tokens produce deterministic client errors
extra segments are not routed as valid view routes
schema endpoint and class-name read mirror still work
legacy table-name routes still work
```

---

## Implementation steps

### Step 1 — HITL policy confirmation

Confirmed and documented policy in this file before code changes:

```text
Schema-only custom views, reject unsafe tokens, reject extra path segments.
```

### Step 2 — Red: frontend negative tests

Add failing tests for unsafe tokens, extra segments, numeric safe tokens, query
conflicts, and invalid resolve/build behavior.

Expected failures before implementation:

```text
malformed routes may parse as valid detail/action routes
unsafe view tokens may produce arbitrary fallback tags
```

### Step 3 — Green: frontend parser/resolver hardening

Update `Router.js` helpers:

1. Add safe view token validation.
2. Add invalid route shape return value.
3. Reject extra path segments beyond supported grammar.
4. Ensure `resolveRoute(invalid)` returns null.
5. Ensure `buildRoute(invalid)` returns empty string.
6. Preserve valid safe custom view fallback behavior.
7. Preserve root app route behavior.

### Step 4 — Red: backend safety tests

Add failing ViewableMixin/backend tests for unsafe tokens, extra segments,
component tag validation, and HTML escaping.

Expected failures before implementation:

```text
unsafe tokens may be accepted
generated HTML may not escape attrs
schema renderer tags may be inserted without validation
```

### Step 5 — Green: backend validation and escaping

Implement backend helpers near `ViewableMixin`:

```text
validate_view_token
validate_component_tag
html_attr
```

Use them in collection and member HTML rendering.

Return `HTTPException(status_code=400, detail='Invalid view name')` for unsafe
tokens in otherwise valid view routes.

Let unsupported extra segments remain 404 by route shape.

### Step 6 — Verify focused suites

Run:

```bash
cd /workspace/tests/frontend && npx vitest run tests/core/route-functions.test.js tests/core/Router.test.js tests/integration/router-navigation.test.js tests/components/ntx-router.test.js
cd /workspace && python3 -m pytest packages/n3tx-ui/src/n3tx_ui/tests/test_viewable_mixin.py -q
cd /workspace && python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/test_routes.py -q
```

If a new backend route-view test file exists, run it explicitly too.

---

## Non-goals for this issue

- Replacing safe custom fallback with schema-only renderer policy.
- Adding production/dev configuration for fallback strictness.
- Adding a user-visible frontend invalid-route component.
- Actor route parity hardening; actor parity comes later.
- Sidebar migration.
- Browser E2E smoke.
- Class-name CRUD/method mirrors.
- `$id` migration.

---

## Acceptance checklist

- [ ] The accepted view-token policy is documented in this file.
- [ ] Frontend accepts safe custom view tokens consistently.
- [ ] Frontend marks unsafe view tokens/routes as invalid.
- [ ] Frontend invalid routes resolve to null and do not mount arbitrary components.
- [ ] Frontend path view wins over query `view`.
- [ ] Frontend filters internal `view` and member-view `method` query attrs.
- [ ] Backend validates named collection view tokens.
- [ ] Backend validates named member view tokens.
- [ ] Backend returns deterministic 400 for unsafe view tokens in valid route shapes.
- [ ] Backend leaves unsupported extra segments as 404.
- [ ] Backend validates schema-declared renderer tags before HTML insertion.
- [ ] Backend escapes generated HTML attrs.
- [ ] Safe unknown views still use deterministic fallback.
- [ ] Existing schema, data, class-read, and table-name method routes still work.
