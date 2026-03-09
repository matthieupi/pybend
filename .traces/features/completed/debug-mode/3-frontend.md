# Frontend Debug Mode — Implementation Plan

## Prerequisites

This plan depends on the backend changes from the parent plan (`debug-mode.md`). Specifically:
- `/_meta` endpoint returns `"debug": true/false` (item 4 in parent plan)
- Custom method responses include `_debug` envelope when `config.DEBUG=True` (item 5 in parent plan)

If those backend changes are not yet implemented, implement them first or stub the `/_meta` response for frontend testing.

---

## 1. Read Debug Flag from `/_meta` and Propagate to Frontend Config

### Context

The frontend config at `/workspace/src/n3tx/static/config.js` has a hardcoded `DEBUG: true` (line 6). The topbar component at `/workspace/src/n3tx/static/components/ntx-topbar.js` already fetches `/_meta` via `fetchMeta()` (lines 44-51) and caches the result in `_metaCache` (line 41). The `/_meta` endpoint is defined in `/workspace/src/n3tx/core/api/discovery.py`.

The goal: the frontend `config.DEBUG` should reflect the backend's debug state, not a hardcoded value.

### Step 1a: Add `applyMeta()` to config.js

**File:** `/workspace/src/n3tx/static/config.js`

**Current code (lines 1-7):**
```javascript

export const config = {
    LOGGING: 3,
    LOGEVENTS: true,
    LOGSPAWN: true,
    DEBUG: true,
    API_URL: (typeof window !== 'undefined' && window.location?.origin) || 'http://localhost:5000',
```

**Change:** Add an `applyMeta` export function at the end of the file, and change `DEBUG` default to `false` (production-safe default — the real value comes from `/_meta`).

**Replace (line 6):**
```javascript
    DEBUG: true,
```

**With:**
```javascript
    DEBUG: false,
```

**Then append after the closing `}` of the config object (after line 69), before the end of file:**
```javascript

/**
 * Apply backend metadata to frontend config.
 * Called by ntx-topbar after fetching /_meta.
 * Sets config.DEBUG from the backend's debug flag so the frontend
 * mirrors the server's debug state.
 *
 * @param {Object} meta - The /_meta response object
 */
export function applyMeta(meta) {
    if (!meta || typeof meta !== 'object') return;
    if (typeof meta.debug === 'boolean') {
        config.DEBUG = meta.debug;
    }
}
```

### Step 1b: Call `applyMeta()` from the topbar's `fetchMeta()` callback

**File:** `/workspace/src/n3tx/static/components/ntx-topbar.js`

**Current import (line 28):**
```javascript
import { config } from '../config.js';
```

**Replace with:**
```javascript
import { config, applyMeta } from '../config.js';
```

**Current `fetchMeta()` function (lines 44-51):**
```javascript
function fetchMeta() {
  if (_metaPromise) return _metaPromise;
  _metaPromise = fetch(`${config.API_URL}/_meta`)
    .then(r => r.ok ? r.json() : null)
    .catch(() => null)
    .then(data => { _metaCache = data; return data; });
  return _metaPromise;
}
```

**Replace the `.then(data => ...)` line (line 49) with:**
```javascript
    .then(data => { _metaCache = data; applyMeta(data); return data; });
```

The full function after the change:
```javascript
function fetchMeta() {
  if (_metaPromise) return _metaPromise;
  _metaPromise = fetch(`${config.API_URL}/_meta`)
    .then(r => r.ok ? r.json() : null)
    .catch(() => null)
    .then(data => { _metaCache = data; applyMeta(data); return data; });
  return _metaPromise;
}
```

### Why this approach

- `fetchMeta()` is module-level and runs once at topbar connect time (before most components render).
- `applyMeta()` is a named export so other code can also call it if needed (e.g., tests).
- The default `DEBUG: false` is production-safe. If `/_meta` fetch fails, debug features stay off.
- The `_metaCache` object is already module-scoped and used by multiple topbar getters; adding `applyMeta()` in the same `.then()` keeps the flow simple.

---

## 2. Debug Badge in Topbar

### Context

The topbar renders a version tag badge already (lines 122-124 in `ntx-topbar.js`). We add a similar debug badge next to it.

### Step 2a: Add debug badge to `#render()` method

**File:** `/workspace/src/n3tx/static/components/ntx-topbar.js`

**Current code in `#render()` (lines 122-124):**
```javascript
    const versionHtml = this.#version
      ? `<span class="topbar-tag">v${this.#version.replace(/^v/, '')}</span>`
      : '';
```

**Insert after those lines (after line 124):**
```javascript

    const debugBadge = _metaCache?.debug
      ? `<span class="topbar-debug">DEBUG</span>`
      : '';
```

**Then in the nav template (line 133), insert `${debugBadge}` after `${versionHtml}`:**

**Current (line 133):**
```javascript
        ${versionHtml}
```

**Replace with:**
```javascript
        ${versionHtml}
        ${debugBadge}
```

### Step 2b: Add CSS for the debug badge

**File:** `/workspace/src/n3tx/static/components/ntx-topbar.css`

**Insert after the `.topbar-tag` rule block (after line 99, before the Navigation section comment):**
```css

.topbar-debug {
    font-size: 0.55rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #000;
    background: var(--warning, #f59e0b);
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: 4px;
    padding: 0.12rem 0.4rem;
    animation: debug-pulse 2s ease-in-out infinite;
}

@keyframes debug-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}
```

### Visual result

The topbar brand area will show: `[NX] AppName v1.0 DEBUG` where `DEBUG` is a small amber badge that gently pulses — unmistakable but not distracting.

---

## 3. Debug Side Panel — Move `ntx-logs` from Example App into Framework

### Context

The `<ntx-logs>` component currently exists only in example apps:
- `/workspace/example_api/static/components/ntx-logs.js` (518 lines)
- `/workspace/example_actor/static/components/ntx-logs.js` (identical copy)

Both files are identical. There is NO copy at `/workspace/src/n3tx/static/components/ntx-logs.js` — but the framework's unit test at `/workspace/src/n3tx/static/tests/components/ntx-logs.test.js` (line 35) already imports from `../../components/ntx-logs.js`, expecting it to be in the framework directory.

The component is a floating toggle button (bottom-right) that opens a side panel showing all framework log entries with level filtering, JSON tree rendering, and clear functionality. It subscribes to the `Logging` utility via `Logging.addListener()`.

### Step 3a: Copy the component into the framework

**Action:** Copy `/workspace/example_api/static/components/ntx-logs.js` to `/workspace/src/n3tx/static/components/ntx-logs.js`.

The file should be copied verbatim — it has no example-app-specific dependencies. Its only imports are:
```javascript
import Logging from '../utils/Logging.js';
```
which resolves correctly relative to `src/n3tx/static/components/`.

### Step 3b: Update example apps to import from the framework

After the copy, the example apps should import the framework's copy instead of having their own. However, since the example apps serve their own static dirs which override the framework's, and the file is at the same relative path, both will work. The cleaner approach for later cleanup is to delete the example copies, but that is optional and NOT part of this plan (to avoid breaking existing tests).

**No file changes needed here for functionality.** The example apps' `index.html` files import `./components/ntx-logs.js` which will resolve to the example app's copy first (served via `_mount_static` explicit routes) or fall through to the framework's static mount.

### Step 3c: Conditional loading approach

The `ntx-logs` component is the debug side panel. It should NOT be loaded in production. The approach:

**Option chosen: Dynamic import in the topbar after `/_meta` resolves.**

In the topbar's `connectedCallback()`, after `fetchMeta()` resolves and if `debug` is true, dynamically import the `ntx-logs` component and inject a `<ntx-logs>` element into the document body. This way:
- No debug code is loaded in production (`import()` never called).
- The component auto-registers via `customElements.define('ntx-logs', NTTLogs)` in the imported module.
- The `<ntx-logs>` element in example app HTML files becomes redundant in debug mode (the topbar will create one), and harmless in production (the custom element is never defined, so it's an inert unknown element).

**File:** `/workspace/src/n3tx/static/components/ntx-topbar.js`

**Current `connectedCallback()` (lines 70-77):**
```javascript
  connectedCallback() {
    // Resolve /_meta defaults then re-render
    fetchMeta().then(() => this.#render());
    // Wait for permissions to resolve, then re-render with user data
    permissions.init().then(() => this.#render());
    // Re-render on external theme change
    document.addEventListener('theme-change', () => this.#render());
  }
```

**Replace with:**
```javascript
  connectedCallback() {
    // Resolve /_meta defaults then re-render
    fetchMeta().then(() => {
      this.#render();
      // Conditionally load the debug log panel when backend debug mode is on
      this.#maybeLoadDebugPanel();
    });
    // Wait for permissions to resolve, then re-render with user data
    permissions.init().then(() => this.#render());
    // Re-render on external theme change
    document.addEventListener('theme-change', () => this.#render());
  }
```

**Add a new private method after `#onLogout` (after line 202):**
```javascript
  /**
   * Dynamically load and inject the debug log panel when debug mode is active.
   * Only called once. Errors are silently caught — a missing debug panel
   * should never break the app.
   */
  #maybeLoadDebugPanel() {
    try {
      if (!_metaCache?.debug) return;
      // Don't inject if one already exists (e.g., declared in app HTML)
      if (document.querySelector('ntx-logs')) return;
      import('./ntx-logs.js')
        .then(() => {
          const panel = document.createElement('ntx-logs');
          document.body.appendChild(panel);
        })
        .catch(() => {
          // Debug panel load failure is non-critical — silently ignore
        });
    } catch {
      // Guard against any unexpected error in debug bootstrap
    }
  }
```

### Why this approach

1. **No code shipped in production.** The `import()` call is never executed when `_metaCache.debug` is false. The browser never requests `ntx-logs.js`.
2. **No HTML template changes needed.** The topbar creates the element programmatically.
3. **Idempotent.** Checks `document.querySelector('ntx-logs')` before injecting, so if an example app HTML already has `<ntx-logs>`, no duplicate is created.
4. **Error-resilient.** The entire block is wrapped in try/catch and the import has a `.catch()`. Debug panel failures never break the app.
5. **Works with existing example apps.** Example apps that already have `<ntx-logs>` in their HTML will continue to work — the topbar just skips injection.

### Note on existing example app HTML

The example app `index.html` files (e.g., `/workspace/example_api/static/index.html` line 70) currently have:
```html
<ntx-logs></ntx-logs>
```
and import the component (line 87):
```javascript
import './components/ntx-logs.js';
```

These should eventually be removed (the framework handles it now), but that is a cleanup task, NOT part of this plan. In the interim:
- If the example app sets `debug=True`, the component loads from the example's own static dir (which takes precedence).
- If `debug=False`, the HTML tag stays inert (custom element never defined), which is harmless.

---

## 4. Method Success Toast + Debug Info

### Context

When a custom method (e.g., `like`, `comment`, `favorite`) succeeds, the response flows through:
1. `ntx-method.js` calls `this.ntt.call(method, payload, { inbox: '_response_' })` (line 99)
2. NetworkAdapter sends HTTP POST to `/{tablename}/{id}/{method}` (line 147 in `NetworkAdapter.js`)
3. Response arrives back via `httpCallback()` which dispatches to the entity's `_response_` handler
4. `_response_` on the DynamicClass prototype (line 1097 in `NTT.js`) currently just calls `this.pull()`

Currently there is **no visual feedback** to the user that a method succeeded. The entity just silently refreshes. We want:
- **Always:** Show a success toast with the method result message
- **In debug mode:** Include timing info from the `_debug` envelope
- **In debug mode:** Log to console for developer inspection

### Step 4a: Modify `_response_` handler on DynamicClass prototype

**File:** `/workspace/src/n3tx/static/core/NTT.js`

**Current code (lines 1092-1099):**
```javascript
    /**
     * Instance _response_ — handles method call responses (e.g. comment).
     * After a method executes server-side, re-pull the entity so child
     * lists (comments, etc.) reflect the new state.
     * Errors now flow through ERROR TX → NTTElement.ERROR() → toast.
     */
    DynamicClass.prototype._response_ = function(data, tx) {
        this.pull();
    };
```

**Replace with:**
```javascript
    /**
     * Instance _response_ — handles method call responses (e.g. comment).
     * After a method executes server-side, re-pull the entity so child
     * lists (comments, etc.) reflect the new state.
     * Shows a success toast with the method result; in debug mode,
     * includes timing info from the _debug envelope.
     * Errors flow through ERROR TX -> NTTElement.ERROR() -> toast.
     */
    DynamicClass.prototype._response_ = function(data, tx) {
        // Show success feedback — dynamic import keeps Toast out of the
        // critical path for pages that never trigger methods.
        try {
            import('../utils/Toast.js').then(({ showToast }) => {
                let message;
                if (data && typeof data === 'object' && data._debug) {
                    // Debug envelope: { result: ..., _debug: { duration_ms, method, model } }
                    const d = data._debug;
                    message = `${d.method || 'method'} OK (${d.duration_ms}ms)`;
                    if (config.DEBUG) {
                        Logging.debug(`[N3TX] ${d.model}.${d.method}`, data);
                    }
                } else if (typeof data === 'string' && data.length > 0 && data.length < 200) {
                    // Plain string result from the method
                    message = data;
                } else if (data && typeof data === 'object' && data.result) {
                    // Wrapped result without debug envelope
                    message = typeof data.result === 'string' ? data.result : 'OK';
                }
                if (message) {
                    showToast(message, 'success');
                }
            }).catch(() => {
                // Toast module failed to load — non-critical, skip silently
            });
        } catch {
            // Guard against import() errors in environments without dynamic import
        }
        this.pull();
    };
```

### Important notes on this change

1. **`config` and `Logging` are already imported** at the top of `NTT.js`:
   - `config` is imported on line 2: `import {config} from "../config.js";`
   - `Logging` is imported on line 8: `import Logging from "../utils/Logging.js";`

2. **Dynamic import for Toast.js** is intentional: `Toast.js` is a utility, not a core dependency. Using `import()` keeps it out of the module graph for pages that never trigger method calls. The cost is one extra microtask on the first method response; subsequent calls hit the module cache.

3. **The `pull()` call is NOT inside the `.then()`** — it runs synchronously after scheduling the toast. This preserves the current behavior: the entity refreshes immediately, regardless of whether the toast succeeds.

4. **String length guard** (`data.length < 200`): prevents accidentally toasting a huge JSON blob if the backend returns a large string.

5. **Error resilience**: every path is wrapped in try/catch. A broken toast should never prevent the entity from refreshing.

### What the user sees

- **Production mode (DEBUG=false):** Method calls show a brief green success toast with the method's return string (e.g., "Product liked!"). If the method returns a complex object, no toast is shown (silent success, same as before).
- **Debug mode (DEBUG=true):** Toast shows method name + timing (e.g., "like OK (12.3ms)"). The `_debug` object is logged to the Logging utility at `debug` level, which appears in the `<ntx-logs>` panel.

---

## 5. Conditional Component Loading (ensuring debug code is not sent in production)

This is already handled by the approach in Step 3c. Here is a summary of all the pieces:

### What happens when DEBUG=false (production)

1. `/_meta` returns `{ ..., "debug": false }`
2. `applyMeta()` sets `config.DEBUG = false`
3. `#maybeLoadDebugPanel()` checks `_metaCache?.debug` which is `false` -> returns immediately
4. `import('./ntx-logs.js')` is **never called** -> the browser **never requests** the file
5. The `ntx-logs.js` file is still present on the filesystem (served by StaticFiles), but no client ever fetches it
6. The debug badge is not rendered (the `_metaCache?.debug` check in `#render()` is false)
7. In `_response_`, the `data._debug` branch is never taken (backend doesn't send `_debug` envelope)
8. The `Logging.debug()` call in `_response_` is a no-op when `config.DEBUG` is false (see `Logging.js` line 61)

### What happens when DEBUG=true (development)

1. `/_meta` returns `{ ..., "debug": true }`
2. `applyMeta()` sets `config.DEBUG = true`
3. `#maybeLoadDebugPanel()` checks `_metaCache?.debug` which is `true`
4. Checks if `<ntx-logs>` already exists in DOM (from example app HTML). If yes, skips. If no, dynamically imports and creates one.
5. The debug badge renders in the topbar
6. Method responses include `_debug` envelope, toast shows timing info, Logging.debug() logs to the panel

### Alternative approach considered but rejected: Server-side conditional serving

We considered making the backend NOT serve `ntx-logs.js` at all when DEBUG=false (via a separate StaticFiles mount or a gated route). This was rejected because:
- It adds backend complexity for minimal gain (the file is ~15KB, and no one requests it)
- It breaks the simple `StaticFiles(directory=...)` mount pattern
- It would require changes to `_mount_static()` in `backend.py`
- The dynamic import approach achieves the same goal (no code sent) without any backend changes

### Alternative approach considered but rejected: HTML template injection

We considered having the backend inject `<script type="module" src="./components/ntx-logs.js">` into the HTML template only when DEBUG=true. This was rejected because:
- The framework has no HTML template system (it serves static HTML files)
- SSR mode (`inject_schemas`, `inject_bundle`) modifies HTML at build time, not per-request
- The dynamic import approach is simpler and works with all SSR modes

---

## File Summary

| File | Action | Description |
|------|--------|-------------|
| `/workspace/src/n3tx/static/config.js` | **Modify** | Change `DEBUG: true` -> `DEBUG: false`, add `applyMeta()` export |
| `/workspace/src/n3tx/static/components/ntx-topbar.js` | **Modify** | Import `applyMeta`, call it in `fetchMeta().then()`, add debug badge rendering, add `#maybeLoadDebugPanel()` method |
| `/workspace/src/n3tx/static/components/ntx-topbar.css` | **Modify** | Add `.topbar-debug` badge style + pulse animation |
| `/workspace/src/n3tx/static/core/NTT.js` | **Modify** | Enhance `_response_` handler with success toast + debug info |
| `/workspace/src/n3tx/static/components/ntx-logs.js` | **Create** | Copy from `/workspace/example_api/static/components/ntx-logs.js` (verbatim) |

---

## Complete Code Changes

### Change 1: `/workspace/src/n3tx/static/config.js`

**Line 6 — change default DEBUG to false:**

Find:
```javascript
    DEBUG: true,
```
Replace with:
```javascript
    DEBUG: false,
```

**After line 69 (after the closing `}` of the config object) — add applyMeta:**

Insert:
```javascript

/**
 * Apply backend metadata to frontend config.
 * Called by ntx-topbar after fetching /_meta.
 * Sets config.DEBUG from the backend's debug flag so the frontend
 * mirrors the server's debug state.
 *
 * @param {Object} meta - The /_meta response object
 */
export function applyMeta(meta) {
    if (!meta || typeof meta !== 'object') return;
    if (typeof meta.debug === 'boolean') {
        config.DEBUG = meta.debug;
    }
}
```

### Change 2: `/workspace/src/n3tx/static/components/ntx-topbar.js`

**Line 28 — update import:**

Find:
```javascript
import { config } from '../config.js';
```
Replace with:
```javascript
import { config, applyMeta } from '../config.js';
```

**Line 49 — add applyMeta call in fetchMeta chain:**

Find:
```javascript
    .then(data => { _metaCache = data; return data; });
```
Replace with:
```javascript
    .then(data => { _metaCache = data; applyMeta(data); return data; });
```

**Lines 70-77 — update connectedCallback to load debug panel:**

Find:
```javascript
  connectedCallback() {
    // Resolve /_meta defaults then re-render
    fetchMeta().then(() => this.#render());
    // Wait for permissions to resolve, then re-render with user data
    permissions.init().then(() => this.#render());
    // Re-render on external theme change
    document.addEventListener('theme-change', () => this.#render());
  }
```
Replace with:
```javascript
  connectedCallback() {
    // Resolve /_meta defaults then re-render
    fetchMeta().then(() => {
      this.#render();
      // Conditionally load the debug log panel when backend debug mode is on
      this.#maybeLoadDebugPanel();
    });
    // Wait for permissions to resolve, then re-render with user data
    permissions.init().then(() => this.#render());
    // Re-render on external theme change
    document.addEventListener('theme-change', () => this.#render());
  }
```

**Lines 122-124 — add debug badge variable after versionHtml:**

Find:
```javascript
    const versionHtml = this.#version
      ? `<span class="topbar-tag">v${this.#version.replace(/^v/, '')}</span>`
      : '';
```
Replace with:
```javascript
    const versionHtml = this.#version
      ? `<span class="topbar-tag">v${this.#version.replace(/^v/, '')}</span>`
      : '';

    const debugBadge = _metaCache?.debug
      ? `<span class="topbar-debug">DEBUG</span>`
      : '';
```

**Line 133 — insert debugBadge into the nav template:**

Find:
```javascript
        ${versionHtml}
      </a>
```
Replace with:
```javascript
        ${versionHtml}
        ${debugBadge}
      </a>
```

**After line 202 (the `#onLogout` method), before the closing `}` of the class — add debug panel loader:**

Find:
```javascript
  #onLogout = (e) => {
    e.preventDefault();
    window.localStorage.removeItem('jwtToken');
    window.location.href = '/login.html';
  };
}
```
Replace with:
```javascript
  #onLogout = (e) => {
    e.preventDefault();
    window.localStorage.removeItem('jwtToken');
    window.location.href = '/login.html';
  };

  /**
   * Dynamically load and inject the debug log panel when debug mode is active.
   * Only called once. Errors are silently caught — a missing debug panel
   * should never break the app.
   */
  #maybeLoadDebugPanel() {
    try {
      if (!_metaCache?.debug) return;
      // Don't inject if one already exists (e.g., declared in app HTML)
      if (document.querySelector('ntx-logs')) return;
      import('./ntx-logs.js')
        .then(() => {
          const panel = document.createElement('ntx-logs');
          document.body.appendChild(panel);
        })
        .catch(() => {
          // Debug panel load failure is non-critical — silently ignore
        });
    } catch {
      // Guard against any unexpected error in debug bootstrap
    }
  }
}
```

### Change 3: `/workspace/src/n3tx/static/components/ntx-topbar.css`

**After line 99 (after the `.topbar-tag` rule block, before the Navigation section):**

Find:
```css

/* ═══════════════════════════════════════════════════
   Navigation — center (slot)
   ═══════════════════════════════════════════════════ */
```
Replace with:
```css
.topbar-debug {
    font-size: 0.55rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #000;
    background: var(--warning, #f59e0b);
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: 4px;
    padding: 0.12rem 0.4rem;
    animation: debug-pulse 2s ease-in-out infinite;
}

@keyframes debug-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}


/* ═══════════════════════════════════════════════════
   Navigation — center (slot)
   ═══════════════════════════════════════════════════ */
```

### Change 4: `/workspace/src/n3tx/static/core/NTT.js`

**Lines 1092-1099 — enhance _response_ handler:**

Find:
```javascript
    /**
     * Instance _response_ — handles method call responses (e.g. comment).
     * After a method executes server-side, re-pull the entity so child
     * lists (comments, etc.) reflect the new state.
     * Errors now flow through ERROR TX → NTTElement.ERROR() → toast.
     */
    DynamicClass.prototype._response_ = function(data, tx) {
        this.pull();
    };
```
Replace with:
```javascript
    /**
     * Instance _response_ — handles method call responses (e.g. comment).
     * After a method executes server-side, re-pull the entity so child
     * lists (comments, etc.) reflect the new state.
     * Shows a success toast with the method result; in debug mode,
     * includes timing info from the _debug envelope.
     * Errors flow through ERROR TX -> NTTElement.ERROR() -> toast.
     */
    DynamicClass.prototype._response_ = function(data, tx) {
        // Show success feedback via toast
        try {
            import('../utils/Toast.js').then(({ showToast }) => {
                let message;
                if (data && typeof data === 'object' && data._debug) {
                    // Debug envelope: { result: ..., _debug: { duration_ms, method, model } }
                    const d = data._debug;
                    message = `${d.method || 'method'} OK (${d.duration_ms}ms)`;
                    if (config.DEBUG) {
                        Logging.debug(`[N3TX] ${d.model}.${d.method}`, data);
                    }
                } else if (typeof data === 'string' && data.length > 0 && data.length < 200) {
                    // Plain string result from the method
                    message = data;
                } else if (data && typeof data === 'object' && data.result) {
                    // Wrapped result without debug envelope
                    message = typeof data.result === 'string' ? data.result : 'OK';
                }
                if (message) {
                    showToast(message, 'success');
                }
            }).catch(() => {
                // Toast module failed to load — non-critical
            });
        } catch {
            // Guard against import() errors
        }
        this.pull();
    };
```

### Change 5: Create `/workspace/src/n3tx/static/components/ntx-logs.js`

**Action:** Copy the file verbatim from `/workspace/example_api/static/components/ntx-logs.js`.

The file is 518 lines. It is a self-contained web component with only one import:
```javascript
import Logging from '../utils/Logging.js';
```

It defines the `NTTLogs` class and registers it as `ntx-logs` custom element. Full contents are at `/workspace/example_api/static/components/ntx-logs.js` — copy as-is.

---

## Edge Cases and Error Handling

### 1. `/_meta` fetch fails
- `fetchMeta()` has `.catch(() => null)` — if the backend is unreachable, `_metaCache` is `null`.
- `applyMeta(null)` returns immediately (guard on line 1 of the function).
- `config.DEBUG` stays `false` (safe default).
- Debug badge does not render (`_metaCache?.debug` is `undefined`).
- Debug panel does not load (`_metaCache?.debug` is falsy).

### 2. `ntx-logs.js` fails to load
- The `import('./ntx-logs.js').catch(...)` silently swallows the error.
- No debug panel appears, but the rest of the app works fine.
- The `try/catch` around the entire `#maybeLoadDebugPanel()` body handles synchronous errors too.

### 3. Toast module fails to load
- The `import('../utils/Toast.js').catch(...)` in `_response_` silently swallows the error.
- `this.pull()` still executes (it is outside the Promise chain).
- The entity refreshes normally; the user just doesn't see a toast.

### 4. Backend returns _debug envelope but frontend has DEBUG=false
- This can happen if there's a timing race (config not yet applied) or a mismatch.
- The `data._debug` branch still triggers — the toast shows timing info regardless.
- The `Logging.debug()` call is a no-op when `config.DEBUG` is false (Logging.js line 61 checks `config.DEBUG`).
- This is intentional: if the backend is in debug mode, showing timing info is useful even if the frontend config hasn't caught up yet.

### 5. Multiple topbar instances
- `fetchMeta()` is module-level with a singleton promise (`_metaPromise`). Multiple topbar instances won't cause multiple fetches.
- `#maybeLoadDebugPanel()` checks `document.querySelector('ntx-logs')` before injecting. Only the first topbar instance creates the panel.

### 6. SSR mode
- In SSR modes (`schema`, `bundle`, `full`), the HTML is built at startup.
- The `<ntx-logs>` element is not in the SSR template — it's injected at runtime by the topbar.
- Dynamic `import()` works with all SSR modes because the module is fetched at runtime, not bundled.
- In `full` SSR mode (bundled JS), the topbar's `import('./ntx-logs.js')` will be a separate network request since `ntx-logs.js` is not part of the bundle. This is intentional — debug code should not be in the production bundle.

### 7. Example apps that already have `<ntx-logs>` in HTML
- The `document.querySelector('ntx-logs')` guard in `#maybeLoadDebugPanel()` prevents duplicate injection.
- The example app's static `<script type="module">` import of `ntx-logs.js` will still load and register the component, which is fine.

---

## Verification Steps

### Manual verification

1. **Start the example API app with debug mode:**
   ```bash
   cd /workspace/example_api
   N3TX_DEBUG=true python main.py
   ```

2. **Check `/_meta` response:**
   ```bash
   curl -s http://localhost:5000/_meta | python3 -c "import sys,json; d=json.load(sys.stdin); print('debug:', d.get('debug'))"
   ```
   Expected: `debug: True`

3. **Open the frontend:**
   - Navigate to `http://localhost:5000/`
   - Verify: amber `DEBUG` badge appears in the topbar next to the version tag
   - Verify: the log panel toggle button appears (bottom-right corner)
   - Click the toggle — the log panel should slide in from the right

4. **Test method toast + debug info:**
   - Log in as alice (alice@example.com / alice123)
   - Navigate to a product detail
   - Click the "like" or "favorite" button
   - Verify: a green success toast appears with text like `like OK (5.2ms)`
   - Open the log panel — verify a `debug` level entry shows the `_debug` data

5. **Test production mode:**
   ```bash
   cd /workspace/example_api
   python main.py  # No N3TX_DEBUG set — defaults to false
   ```
   - Open the frontend
   - Verify: NO `DEBUG` badge in topbar
   - Verify: NO log panel toggle button
   - Open browser DevTools Network tab — verify `ntx-logs.js` is NOT requested
   - Call a method — verify a success toast appears with the method's return string (no timing info)

### Automated test verification

1. **Existing tests should still pass:**
   ```bash
   cd /workspace/src/n3tx/static && npx vitest run tests/components/ntx-logs.test.js
   cd /workspace/src/n3tx/static && npx vitest run tests/components/ntx-topbar.test.js
   cd /workspace/src/n3tx/static && npx vitest run tests/core/NTT.test.js
   ```

2. **The `ntx-logs.test.js` test** currently imports from `../../components/ntx-logs.js` which now exists (after the copy). This test should now pass where it may have previously failed.

3. **The `_response_` test** in `/workspace/src/n3tx/static/tests/core/NTT.test.js` (line 374) tests that `_response_` calls `pull()`. Since `pull()` is still called synchronously in our change, this test should still pass. The `import()` call for Toast is asynchronous and doesn't affect the synchronous `pull()` call.

---

## Dependency Diagram

```
/_meta response (backend)
    |
    v
fetchMeta() -> applyMeta() -> config.DEBUG = true/false
    |
    v
ntx-topbar.#render()
    |
    +-- _metaCache.debug? -> render debug badge
    |
    v
ntx-topbar.#maybeLoadDebugPanel()
    |
    +-- _metaCache.debug? -> dynamic import('./ntx-logs.js')
    |                         -> create <ntx-logs> element
    |
    v
NTT.js _response_ handler
    |
    +-- data._debug? -> toast with timing info
    |                   -> Logging.debug() (shown in <ntx-logs> panel)
    |
    +-- else -> toast with method result string
    |
    v
this.pull() (always, regardless of toast)
```
