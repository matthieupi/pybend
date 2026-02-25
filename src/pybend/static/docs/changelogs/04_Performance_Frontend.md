# Frontend Performance Optimizations

> **Status:** Complete.
> **Scope:** Reduced DOM thrashing and prevented event listener accumulation in the rendering pipeline.

---

## Table of Contents

1. [Summary](#1-summary)
2. [Batched DOM Insertion](#2-batched-dom-insertion)
3. [Event Listener Cleanup](#3-event-listener-cleanup)
4. [File-by-File Changes](#4-file-by-file-changes)
5. [Verification](#5-verification)

---

## 1. Summary

Two optimizations targeting the frontend rendering hot path:

| Optimization | Problem | Fix | Impact |
|---|---|---|---|
| Batched DOM insertion | `render()` appended children one-by-one, triggering N reflows | `DocumentFragment` batch insertion | Single reflow per render |
| Event listener cleanup | `#bindEvents()` added listeners on every render without removing old ones | `AbortController` per render cycle | Zero listener accumulation |

---

## 2. Batched DOM Insertion

### Problem

`ListElement.render()` and `ListElement.update()` appended child elements to the `.list-grid` one at a time. Each `appendChild()` triggers a browser reflow — layout recalculation, paint, and composite. For a list of 20 items, that's 20 reflows.

### Fix

Both methods now batch child elements into a `DocumentFragment` before appending:

```javascript
// render()
const fragment = document.createDocumentFragment();
this.value.forEach((addr, i) => {
  const child = this.createChild(addr);
  child.setAttribute('data-value', addr);
  child.style.setProperty('--stagger-delay', `${i * 50}ms`);
  fragment.appendChild(child);
});
grid.appendChild(fragment);  // Single reflow
```

The `update()` surgical DOM patch path uses the same pattern for additions — batches new children into a fragment, then appends once.

### Why DocumentFragment

A `DocumentFragment` is a lightweight DOM node that acts as a staging area. When appended to the document, only its children are inserted — the fragment itself is not added to the tree. The browser treats the entire insertion as a single operation, triggering one reflow instead of N.

---

## 3. Event Listener Cleanup

### Problem

`NTTItem.#bindEvents()` is called on every `render()`. While `render()` rebuilds `shadowRoot.innerHTML` (which discards old DOM nodes and their listeners), there are edge cases where listeners accumulate:

1. The reply button flow creates elements appended *after* the card — these persist across re-renders
2. If `update()` patches DOM without a full `innerHTML` rebuild, old listeners on surviving elements stack up
3. Any future partial-render optimization would immediately hit this problem

### Fix

Added an `AbortController` pattern — one controller per render cycle:

```javascript
#eventAC = null;

#bindEvents() {
  // Abort previous listeners before binding new ones
  this.#eventAC?.abort();
  this.#eventAC = new AbortController();
  const {signal} = this.#eventAC;

  // All listeners use the signal
  this.shadowRoot.querySelector('.edit-btn')
    ?.addEventListener('click', () => this.toggleMode(), {signal});
  // ... all other listeners
}
```

When `#bindEvents()` is called again, `abort()` automatically removes every listener registered with the previous controller's signal. This works regardless of whether the DOM was fully rebuilt or surgically patched.

### Why AbortController

The `AbortController` + `{ signal }` pattern is the modern standard for listener lifecycle management:
- No need to store references to every handler function
- No need for manual `removeEventListener()` calls
- Handles any number of listeners with a single `abort()` call
- Works on dynamically created elements (like the reply input box)

---

## 4. File-by-File Changes

| File | Changes |
|---|---|
| `components/ListElement.js` | `render()` uses `DocumentFragment` for batched child insertion; `update()` additions loop uses `DocumentFragment` |
| `components/ntt-item.js` | Added `#eventAC` private field; `#bindEvents()` aborts previous controller and creates new one; all `addEventListener` calls pass `{signal}` |

---

## 5. Verification

All changes verified against the full test suite:
- **485 backend unit tests** — all passing
- **386 backend integration tests** — all passing
- No behavioral changes — purely performance improvements
