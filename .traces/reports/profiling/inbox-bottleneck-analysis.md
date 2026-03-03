# Actor._inbox() Bottleneck Analysis

**Date**: 2026-03-02
**Observed**: `Actor._inbox()` — 355 calls, Σ1050.9ms (avg 3.0ms/call)
**Scope**: Full message routing chain (send → Matrix.inbox → Actor._inbox → handler)

---

## Message Chain Per TX

A single message (e.g., DESCRIBE to an ntt-item) traverses:

```
component.send(event)
  → Actor._send(event)           new TX(event) + target.split('/') + tx.repr()
    → ROOT_ACTOR.inbox(tx.repr())
      → Matrix.inbox(event)      new TX(event) + target.split('/') + tx.repr()
        → child.inbox(tx.repr())
          → Actor._inbox(event)  new TX(event) + getPrototypeOf + handler()
```

**Per message**: 3× `new TX()`, 3× `tx.repr()` (plain object copy), 2+ `target.split('/')`
**Across 355 messages**: 1065 TX constructions + 1065 object copies — immediately discarded.

---

## Optimizable Changes (Prioritized)

### 1. TX re-creation on every hop — BIGGEST WIN

**Problem**: `tx.repr()` returns a plain `{}` object. The next `inbox` does
`event instanceof TX ? event : new TX(event)` — always fails the check,
always creates a new TX.

```js
// Matrix.js:39 — passes plain object
tx = this.children.get(targetAddr).inbox(tx.repr())

// Actor.js:132 — receives plain object, creates new TX
const tx = event instanceof TX ? event : new TX(event);
```

**Fix**: Pass the TX instance directly. Stop calling `repr()` at routing boundaries.

**Calls saved**: 1065 allocations
**Impact**: HIGH

---

### 2. `target.split('/')` repeated per hop

**Problem**: Every routing function splits the same target string:
- `Matrix.inbox` line 31: `tx.target.split('/')[0]`
- `_send` lines 79-81: `rawTarget.split("/").filter(Boolean)`
- `_inbox` line 136: template literal comparison

**Fix**: Parse once, cache on TX as `tx._segments`.

**Calls saved**: 710 splits
**Impact**: HIGH

---

### 3. Template literal allocations for disabled logging

**Problem** (`_send` line 65):
```js
Logging.dev(`[Actor.${this.addr}_send] Sending '${tx.name}' to ${tx.target}`)
```
JS evaluates the template literal **before** calling `Logging.dev()`, which
returns immediately if `config.LOGGING < 4`. The string is allocated and
thrown away on every `_send`.

**Fix**: Guard with condition before the template, or pass a thunk.

**Calls saved**: 710 string allocs
**Impact**: MEDIUM

---

### 4. `Object.getPrototypeOf(this)` in `_inbox` — per dispatch

**Problem** (line 135): Called on every message dispatch for handler lookup.

**Fix**: Cache the prototype on the class during `subclass()` setup.

**Calls saved**: 355 lookups
**Impact**: LOW

---

### 5. `_inbox` string comparison creates garbage

**Problem** (line 136):
```js
if (tx.target === `/${Type.addr}` || tx.target === Type.addr)
```
Creates a new string `` `/${Type.addr}` `` on every call (355 times).

**Fix**: Pre-compute `/${Type.addr}` as a static property during `subclass()`.

**Calls saved**: 355 string allocs
**Impact**: MEDIUM

---

### 6. `tx.repr()` copies all fields including data

**Problem** (`TX.js:45-55`):
```js
repr() {
    const obj = {}
    obj.name = this.name
    obj.source = this.source
    obj.target = this.target
    obj.data = this.data    // shallow ref to potentially large data
    obj.meta = this.meta
    obj.hash = this._hash
    obj.tst = this.tst
    return obj
}
```
1065 wrapper objects created and immediately discarded.

**Fix**: Eliminated by fix #1 (stop calling repr).

**Impact**: Eliminated by #1

---

### 7. `_send` splits + filters every time

**Problem** (lines 79-81):
```js
let [targetParent, targetChild, childTarget] = rawTarget
    .split("/")
    .filter(Boolean);
```
Allocates an array, filters it, destructures — on every send.

**Fix**: Use `indexOf('/')` for the common case (single-segment target),
only split for multi-segment.

**Calls saved**: 355 split+filter
**Impact**: LOW-MEDIUM

---

### 8. `isUrl()` uses `new URL()` in try/catch

**Problem** (`Utils.js:188-195`): Called from `Component.ref` setter for every item:
```js
function isUrl(str) {
    try { new URL(str); return true; }
    catch (e) { return false; }
}
```
`new URL()` is expensive (full URL parsing). Try/catch with exception
creates a stack trace on failure.

**Fix**: Use `str.startsWith('http')` for the common case.

**Calls saved**: 150+ URL parses
**Impact**: MEDIUM

---

### 9. `Logging.event(tx)` in Matrix.inbox builds string unconditionally

**Problem** (Matrix.js:29):
```js
Logging.event(tx);
// Inside: const msg = tx.name ? `[${tx.name}] ${tx.source} --> ${tx.target}` : String(tx);
```
Function call overhead exists even when `config.LOGEVENTS` is false.

**Fix**: Guard inline: `if (config.LOGEVENTS) Logging.event(tx)`.

**Calls saved**: 355 fn calls
**Impact**: LOW

---

## Summary Table

| # | Change | Calls saved | Impact |
|---|--------|-------------|--------|
| 1 | Pass TX directly, stop `repr()` | 1065 allocations | **HIGH** |
| 2 | Cache `target.split('/')` on TX | 710 splits | **HIGH** |
| 5 | Pre-compute `/${addr}` per class | 355 string allocs | **MEDIUM** |
| 8 | `isUrl()` → `startsWith('http')` | 150+ URL parses | **MEDIUM** |
| 3 | Guard template literals for logging | 710 string allocs | **MEDIUM** |
| 7 | Fast-path `_send` for simple targets | 355 split+filter | **LOW-MED** |
| 4 | Cache `getPrototypeOf` | 355 lookups | **LOW** |
| 6 | Eliminated by #1 | — | — |
| 9 | Inline guard for `Logging.event` | 355 fn calls | **LOW** |

## Estimated Combined Impact

Fixes 1+2+5+8 alone would eliminate ~2300 unnecessary allocations per page load
and cut the per-message overhead from ~0.5ms routing tax to ~0.1ms.
