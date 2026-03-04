# Framework Issues Discovered During Test Suite Build

Discovered by automated test agents while building 1,748 tests across the full stack,
plus in-depth frontend review.

---

# Frontend Issues

## F1. Permissions NOT Rule Always Returns True

**Severity:** High (Security)
**Location:** `src/n3tx/static/utils/Permissions.js:141-164` — `#evaluateCompositeRule()`

The `{ op: 'not', rule: {...} }` composite structure is evaluated incorrectly. The method checks `rule.rule` first (line 145, which is the sub-rule object — always truthy), entering the simple-rule branch and returning `true` without ever reaching the `op === 'not'` branch (line 162).

**Impact:** Any authorization rule using NOT (~) on the frontend is silently bypassed — access is always granted.

**Repro:**
```javascript
permissions.canAction({ delete: { op: 'not', rule: { rule: 'role', roles: ['banned'] } } }, 'delete', {})
// Returns true even for banned users
```

**Fix:** Reorder `#evaluateCompositeRule` to check `rule.op` before `rule.rule`, or restructure the NOT serialization format to use `rules: [...]` instead of `rule: {...}`.

---

## F2. XSS Vulnerability — ntx-profile.js Template Literals

**Severity:** High (Security)
**Location:** `src/n3tx/static/components/ntx-profile.js:34-108`

User data (`user.email`, `user.name`, `user.role`) is interpolated directly into `innerHTML` via template literals with no HTML escaping:

```javascript
this.shadowRoot.innerHTML = `
  <div class="avatar">${initial}</div>
  <h2>${displayName}</h2>
  <div class="email">${user.email}</div>
  ${user.role ? `<span class="role">${user.role}</span>` : ''}
`;
```

If any user field contains HTML (e.g. `<img onerror="...">` in the name or email), it will execute in the shadow DOM context.

**Impact:** Stored XSS if a malicious user sets their name/email to contain HTML. The shadow DOM provides some isolation but `<script>` tags and event handlers still execute.

**Fix:** Escape all user-sourced values before interpolation, or use `textContent` assignment.

---

## F3. XSS Vulnerability — ntx-topbar.js User Pill

**Severity:** High (Security)
**Location:** `src/n3tx/static/components/ntx-topbar.js:88-128` — `#userPillHtml()`

Same pattern as ntx-profile — user data goes directly into `innerHTML`:

```javascript
return `
  <div class="user-avatar">${initial}</div>
  <span class="user-name">${displayName}</span>
  <div class="dropdown-email">${email}</div>
  ${role ? `<div class="dropdown-role">${role}</div>` : ''}
`;
```

**Impact:** Every page load renders the topbar, so this XSS vector fires on every page for every user who views a compromised account's data.

**Fix:** Same as ntx-profile — escape user values.

---

## F4. XSS Vulnerability — ntx-item.js Template Literals

**Severity:** Medium (Security)
**Location:** `src/n3tx/static/components/ntx-item.js` — `xs()`, `sm()`, `md()`

Entity field values are interpolated into `innerHTML` without escaping:

```javascript
// xs() line 142
return `<span class="pill-label" data-value="name">${name}</span>`;

// sm() line 201
nameHtml = `<span class="sm-name" data-value="name">${val || schema.__name__}</span>`;

// sm() line 219-220
smFields.push(`<span class="sm-field" data-value="${key}">${display}</span>`);

// md() line 298
html.push(`<img class="card-image" src="${this.value.image}" alt="${this.value.name || ''}" />`);
```

**Impact:** Any entity with user-controlled fields (name, description, etc.) could inject HTML. The `image` field in `md()` is especially dangerous — a crafted `src` attribute could break out of the `img` tag.

**Fix:** HTML-escape all interpolated entity values, or use DOM APIs (`createElement`/`textContent`).

---

## F5. XSS Vulnerability — form.js Display Values

**Severity:** Medium (Security)
**Location:** `src/n3tx/static/generators/form.js` — `getInput()`, `getHeader()`

Form display mode renders values directly into HTML:

```javascript
// getHeader() line 143
headerHtml.push(`<h2 class="${schema.name}" data-value="name">${name}</h2>`);

// getInput() line 231
html.push(`<div data-value="${key}">${value}</div>`);
```

Edit mode is safer (values go into `value=""` attributes) but display mode has no escaping.

**Impact:** Entity data containing HTML renders as active markup.

---

## F6. NetworkAdapter `emit()` References Undefined `callback`

**Severity:** Medium
**Location:** `src/n3tx/static/core/transport/NetworkAdapter.js` — `emit()`

The `emit()` method references an undefined `callback` variable. The registry lines that would define it are commented out, causing assertion errors on background network error responses.

**Impact:** Network error callbacks silently fail. Error responses from the backend are not properly dispatched back to the originating component. This is the root cause of the 33 unhandled rejection errors in the test suite.

---

## F7. Observable/TT `notify()` Method Conflict

**Severity:** Medium
**Location:** `src/n3tx/static/core/Observable.js` + `src/n3tx/static/core/N3TX.js`

TT's `notify(value)` (sends UPDATE TX to watchers) shadows Observable's `notify(property, newValue, oldValue)` (calls registered observers). Observable.apply's guard (`!("notify" in proto)`) prevents overriding TT's version. This means instance-level property observers registered via `observe()` are never triggered by `notify()`.

**Impact:** Property-level observation on N3TX entities is silently broken. Components using `entity.observe('name', callback)` will never receive notifications.

---

## F8. registrar.js `getRegistrar()` — Inverted Assertion

**Severity:** Medium
**Location:** `src/n3tx/static/utils/registrar.js:41`

```javascript
export function getRegistrar(key) {
    assert(this, key, 'Name must be defined');
    assert(this, !registry.has(key), `No entry found when trying to get registrar for ${key}`);
    return registry.get(key);
}
```

The assertion `!registry.has(key)` throws when the key IS found (the success case) and passes when it's NOT found (the error case). This is backwards — the function returns `undefined` from `registry.get()` on missing keys but throws on valid ones.

**Impact:** Any code calling `getRegistrar()` with a valid key will throw an assertion error. This function may be unused (dead code), but if called it would fail on every valid input.

---

## F9. ntx-user.js — Unvalidated External URL Construction

**Severity:** Low-Medium (Security)
**Location:** `src/n3tx/static/components/ntx-user.js:21-23`

```javascript
#avatarUrl() {
    const img = this.value.image;
    if (img) return img;  // User-controlled URL used as img src
    const name = encodeURIComponent(this.value.name || this.value.email || '?');
    return `https://ui-avatars.com/api/?name=${name}&...`;
}
```

The `image` field is used directly as an `<img src>` without URL validation. A crafted value (e.g. `javascript:` URI in older browsers, or a tracking pixel URL) could be used for phishing or data exfiltration.

The `encodeURIComponent` on the fallback path is correct but the primary path (`if (img) return img`) has no validation.

---

## F10. Socket.js `disconnect()` — Reference Error

**Severity:** Medium
**Location:** `src/n3tx/static/core/transport/Socket.js:222-224`

```javascript
disconnect(){
    if (this.websocket.readystate === 1) {  // typo: should be readyState
        websocket.close()  // missing this. prefix
    }
```

Two bugs:
1. `readystate` should be `readyState` (JavaScript is case-sensitive)
2. `websocket.close()` should be `this.websocket.close()` — references undefined global

**Impact:** `disconnect()` never actually closes the WebSocket connection. The `readystate` check always fails (undefined !== 1), so the `close()` call is never reached. Even if it were, it would throw a ReferenceError.

---

## F11. Form `description` Field Bypasses Widget System

**Severity:** Low
**Location:** `src/n3tx/static/generators/form.js` — `getForm()` / `getHeader()`

Fields named `description` are included in `headerFields` and rendered as `<h4>` elements in display mode, bypassing the `getInput()` widget system. If a `description` field has `widget: 'textarea'`, the widget hint is ignored — it always renders as a plain `<h4>` header element.

**Impact:** The `description` field on any model cannot use custom widgets (textarea, rich text, etc.) in display mode. Edit mode is unaffected.

---

## F12. form.js `getForm()` — Array/String Concatenation Bug

**Severity:** Low
**Location:** `src/n3tx/static/generators/form.js:64`

```javascript
return $header.concat($fields).join('');
```

`$header` is always an array (from `getHeader()`). `$fields` is a string when ungrouped (from `.map().join('')`) but a string when grouped (from `renderGroupedFields()`). `Array.concat(string)` wraps the string as a single array element, which works, but this is fragile — if `$fields` were ever `null` or `undefined`, it would produce `"null"` or `"undefined"` in the output.

**Impact:** Works today by accident. A future change to `renderGroupedFields` returning an array instead of string would silently produce nested arrays.

---

## F13. Snippets.js — Debug Code Shipped to Production

**Severity:** Low
**Location:** `src/n3tx/static/utils/Snippets.js`

```javascript
Object.keys(window).forEach(key => {
    if (/^on/.test(key)) {
        window.addEventListener(key.slice(2), event => {
            console.log(event);
        });
    }
});
```

This attaches a `console.log` listener to every single DOM event type on `window`. If imported, it would flood the console and degrade performance.

**Impact:** Performance degradation if imported. Currently appears to be dead code (no imports found), but its presence in the utils directory suggests it could be accidentally imported.

---

# Backend Issues

## B1. `n3tx/__init__.py` Contains Broken Import

**Severity:** Medium
**Location:** `src/n3tx/__init__.py`

Contains `from .api.routes import create_api_blueprint` — the module `api.routes` does not exist (the actual routes are in `api/routes_fastapi.py`). This prevents importing `n3tx` as a package.

**Impact:** Any code that does `import n3tx` or `from n3tx import ...` will fail with ImportError. Does not affect production since `main.py` imports submodules directly, but breaks test environments and package consumers.

**Fix:** Remove or update the stale import in `n3tx/__init__.py`.

---

## B2. PUT Routes Require Full Model Validation (No True Partial Updates)

**Severity:** Medium
**Location:** `src/n3tx/core/api/routes_fastapi.py` — `make_update_instance()`

The `update_instance` handler takes `data: param_class` (the full Pydantic model), so PUT requires all required fields including `price` for Product. Partial updates without required fields return 422 before the route handler even runs.

**Impact:** Clients cannot send partial updates (e.g. only updating `description` without also sending `name` and `price`). This is a significant UX limitation — the frontend must always send the complete entity on save.

**Fix:** Use a separate partial model (with all fields Optional) for updates, or switch to PATCH semantics.

---

## B3. Pre-existing Test Failures (Pydantic V2 Compatibility)

**Severity:** Low
**Location:** `src/n3tx/core/models/product_model.py` — `Product.comment()`

Pydantic V2 rejects instance-level ClassVar assignment (`comment.__owner__ = product`). The production code does this in `Product.comment()` — it works at runtime but fails strict Pydantic validation in isolated unit tests.

**Impact:** Unit test `test_comment_sets_owner` fails. The runtime behavior is correct but the pattern is fragile under Pydantic's validation model.

---

## B4. Auth Module Uses Module-Level Globals (No Isolation)

**Severity:** Low
**Location:** `src/n3tx/core/authorize/auth.py`

The `authorize.auth` module uses module-level globals (`_jwt_secret`, `_jwt_expiry_hours`) set by `configure()`. There is no way to scope configuration to a request, test, or context — it's process-wide mutable state.

**Impact:** Tests that call `configure()` with different secrets can contaminate each other. In production, this is fine (configured once at startup), but it makes the auth module harder to test and impossible to use in multi-tenant scenarios.

---

## B5. Config Test Order Dependency

**Severity:** Low
**Location:** `src/n3tx/core/config.py`

A session-scoped test fixture changes `config.SQLITE_DB_FILE`, and `test_sqlite_db_file`'s expected value depends on execution order. If tests run in a different order, the assertion fails.

**Impact:** Flaky test. The config module's mutable global state makes test isolation difficult.

---

## B6. No Cascade Delete Behavior Defined

**Severity:** Medium
**Location:** `src/n3tx/core/storage/sqlite_storage.py`, `src/n3tx/core/api/routes_fastapi.py`

Deleting a parent entity (Product, Comment) does not cascade to child entities (Comments, Likes). The join table entries (ProductComment, CommentLike) become orphaned — the FK references point to non-existent parent IDs.

**Impact:**
- Deleting a product leaves orphaned comments in the `product_comments` join table
- Deleting a comment leaves orphaned likes in the `comment_likes` join table
- Deleting a comment leaves orphaned replies (comments with `parent_id` pointing to deleted comment)
- Subsequent list/get operations on orphaned entities may return partial data or errors

**Fix:** Add `ON DELETE CASCADE` to FK constraints in `sqlite_storage.py` table creation, or implement soft deletes, or add cascade logic in the route layer before delete.

---

## B7. `CORS allow_origins=["*"]` With `allow_credentials=True`

**Severity:** Medium (Security)
**Location:** `src/n3tx/core/api/backend.py:59-65`

```python
self.app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Per the CORS specification, `allow_origins=["*"]` with `allow_credentials=True` is invalid — browsers will reject the response. FastAPI/Starlette may handle this by reflecting the `Origin` header back, but this effectively allows any origin to make credentialed requests (cookies, JWT tokens).

**Impact:** Any website can make authenticated API calls on behalf of a logged-in user. In production with a real domain, this enables CSRF-like attacks.

**Fix:** Replace `["*"]` with explicit allowed origins, or remove `allow_credentials=True` if credentials aren't sent via cookies.

---

## B8. JWT Secret Hardcoded in Default Config

**Severity:** Medium (Security)
**Location:** `src/n3tx/core/config.py:14`

```python
JWT_SECRET = os.getenv("JWT_SECRET", "ntx-dev-secret-change-in-production")
```

The default fallback secret `"ntx-dev-secret-change-in-production"` is predictable. If `JWT_SECRET` env var is not set in production, tokens can be forged by anyone who reads the source code.

Additionally, `authorize/auth.py` has its own separate default:
```python
_jwt_secret = "authorize-dev-secret-change-in-production"
```

Two different defaults creates confusion about which secret is actually in use.

**Impact:** Token forgery if deployed without setting `JWT_SECRET` env var.

**Fix:** Refuse to start if `JWT_SECRET` is not explicitly set in non-dev environments, or generate a random secret on startup (with a warning).

---

## B9. User Registration Has No Email Uniqueness Enforcement

**Severity:** Medium
**Location:** `src/n3tx/core/api/routes_fastapi.py` — register route, `src/n3tx/core/storage/sqlite_storage.py`

The registration endpoint creates a user without checking if the email is already taken. SQLite has no UNIQUE constraint on the email column. Multiple users can register with the same email, leading to ambiguous login behavior (which user does the password match against?).

**Impact:** Duplicate accounts with same email. Login may authenticate against the wrong user. Data integrity violation.

**Fix:** Add UNIQUE constraint on `users.email` column, and check for existing email in the register route before creating.

---

## B10. Auth Middleware Silently Swallows Token Decode Errors

**Severity:** Low
**Location:** `src/n3tx/core/api/backend.py:90-97`

```python
try:
    payload = decode_token(token)
    request.state.user = payload
except Exception:
    return JSONResponse(
        status_code=401,
        content={"detail": "Invalid or expired token"},
    )
```

The bare `except Exception` catches ALL exceptions — including `ImportError`, `MemoryError`, `KeyboardInterrupt` descendants that inherit from `BaseException` won't be caught, but actual programming errors (e.g., `TypeError` from a misconfigured JWT library) will be silently swallowed as "invalid token".

**Impact:** Debugging difficulty. A broken JWT configuration manifests as "invalid token" for every request, with no stack trace.

**Fix:** Catch only `jwt.ExpiredSignatureError` and `jwt.InvalidTokenError` (or whatever the specific JWT library raises).
