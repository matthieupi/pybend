# Issue 017 Plan — Frontend Nested Class Route Support

## ✅ Recommendation

Treat issue `017` as a **frontend completion and hardening slice**. The core parser/resolver already has substantial nested class-name route support in `Router.js`, and route-function tests already cover the main parse/build/resolve paths. The remaining work is to close the acceptance gaps around router state, DOM mounting, ref transport behavior, invalid-route boundaries, and documentation/status alignment.

Target grammar:

```text
#Product/1/Comment/2          -> nested child detail
#Product/1/Comment/2/@item    -> nested child member view
#Product/1/Comment/2/like     -> nested child action/method
#Product/1/Comment/2/@like    -> nested view named like, not method
```

The implementation should remain one-hop and class-name based. Do **not** add arbitrary-depth parsing.

---

## 📍 Current State

| Area | Current status | Remaining gap |
|---|---:|---|
| `Router.parseRoute()` | Already parses `nested-collection`, `nested-detail`, `nested-action` | Add stricter invalid-boundary tests |
| `Router.buildRoute()` | Already round-trips nested shapes | Add missing default nested view/query cases |
| `Router.resolveRoute()` | Already returns canonical nested refs like `Product/1/Comment/2` | Verify child schema lookup and method/view collision in state/DOM tests |
| `Router` actor/hash state | Flat `@` routes covered | Add nested hash sync, initial hash, back/reset tests |
| `<ntx-router>` DOM mount | Flat model/member routes covered | Add nested detail/view/action mount tests |
| `NTT.js`/`Component.js` transport | Supports `$id` hrefs and `meta.href` for URL refs | Add focused tests proving nested refs attach/fetch without table-name ref regressions |
| Existing table-name refs | Still supported | Add regression coverage so `products/1/comments/2` style refs are not broken |

---

## 🧭 Architecture Invariants

1. Nested class-name identity is one-hop only:

   ```text
   /{ParentClass}/{parent_id}/{ChildClass}/{child_id}
   ```

2. The public child model is semantic (`Comment`), not the generated join model (`ProductComment`).
3. Existing flat routes remain unchanged:

   ```text
   Product
   Product/1
   Product/1/run
   Product/@
   Product/1/@item
   ```

4. Existing legacy/table-name refs remain supported in data and components.
5. `@` keeps its boundary inside nested routes:

   ```text
   Product/1/Comment/2/like   -> method/action
   Product/1/Comment/2/@like  -> view, no method attr
   ```

6. Invalid extra segments must resolve to `invalid`/`null`, not silently mount a component.
7. Mounted nested detail components use the canonical transport ref:

   ```html
   <ntx-item ref="Product/1/Comment/2" display="lg"></ntx-item>
   ```

---

## 🗺️ Flow

```text
Browser hash
  #Product/1/Comment/2/@item
        |
        v
Router.parseRoute()
  { type: 'nested-detail', parentModel:'Product', parentId:'1', model:'Comment', id:'2', view:'item', isViewRoute:true }
        |
        v
Router.resolveRoute(parsed, getSchema)
  schema = getSchema('Comment')
  tag = schema.ui.renderer.item || 'ntx-item'
  attrs = { ref:'Product/1/Comment/2', display:'lg' }
        |
        v
<ntx-router>
  document.createElement(tag)
  set attrs
        |
        v
Component.ref = 'Product/1/Comment/2'
        |
        v
NTT.attach('Product/1/Comment/2')
  model key = 'Product'
  fetch target = canonical nested href when needed
```

The final `NTT.attach()` behavior is the subtle part: the current generic attach code derives the schema/model from the first path segment. That is fine for mounted route refs if the mounted component is schema-selected from the child model and only needs `ref` as the transport href, but it can be wrong for cache lookup if the child instance should live under the `Comment` DynamicClass. This slice should explicitly verify the behavior and either preserve a known-good path or add a small normalization helper.

---

## Implementation Plan

### Phase 1 — Lock parser/build invalid boundaries

**Files**

- `tests/frontend/tests/core/route-functions.test.js`
- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`

**Add/verify tests**

Current tests already cover:

```text
Product/1/Comment
Product/1/Comment/@table
Product/1/Comment/2
Product/1/Comment/2/@item
Product/1/Comment/2/like
Product/1/Comment/2/@like
```

Add missing edge coverage:

```text
Product/1/Comment/2/@              -> nested-detail default view
Product/1/Comment/2/@item?tab=x    -> params preserved
Product/1/Comment/@                -> nested-collection default view if retained
Product/1/Comment/2/@/extra        -> invalid
Product/1/Comment/2/@item/extra    -> invalid
Product/1/Comment/2/like/extra     -> invalid
Product/1/comment/2                -> invalid or legacy flat parse, choose and lock
Product/1/Comment                  -> keep only if nested collection support is intentional
```

**Recommended decision**

Keep the already-implemented `nested-collection` and `nested-action` support because `FRONTEND.md` documents them as planned routes and existing tests already cover them. Lock them down rather than removing them.

**Likely code change**

Small parser guard if `Product/1/Comment/2/like/extra` or `@.../extra` currently slips through. The current `parts.length > 5` guard should catch six-segment routes; tests should prove it.

---

### Phase 2 — Harden `resolveRoute()` contract

**Files**

- `tests/frontend/tests/core/route-functions.test.js`
- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`

**Add/verify tests**

1. Nested detail uses **child** schema renderer:

```js
resolveRoute(parseRoute('Product/1/Comment/2'), getSchema)
// getSchema called/effective for 'Comment'
// -> { tag:'ntx-comment-card', attrs:{ ref:'Product/1/Comment/2', display:'lg' } }
```

2. Nested default member view:

```text
Product/1/Comment/2/@ -> renderer.detail -> renderer.item -> ntx-item
```

3. Nested named member view:

```text
Product/1/Comment/2/@item -> renderer.item
```

4. Nested action route:

```text
Product/1/Comment/2/like -> attrs.method='like'
```

5. Nested same-name view route:

```text
Product/1/Comment/2/@like -> no attrs.method
```

6. Internal `view` query param is filtered:

```text
Product/1/Comment/2/@item?view=detail&tab=x
-> attrs.tab='x', attrs.view undefined
```

**Likely code change**

None expected for the happy path. If schema lookup ambiguity appears, make the child model lookup explicit and obvious:

```js
const schema = getSchema(parsed.model); // parsed.model === child model for nested routes
```

---

### Phase 3 — Router actor/hash sync coverage

**Files**

- `tests/frontend/tests/core/Router.test.js`
- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`

**Add tests**

1. `NAVIGATE('Product/1/Comment/2')` sets `current` and `#Product/1/Comment/2`.
2. `NAVIGATE('Product/1/Comment/2/@item')` sets `current` and hash exactly.
3. Initial hash load from `#Product/1/Comment/2/@item` sets current without fake back history.
4. Duplicate nested navigation is a no-op.
5. `BACK()` works from nested detail/action to previous route.
6. Reset to home from nested route clears hash and stack.
7. `router.resolved` returns child renderer and canonical nested ref.

**Likely code change**

None expected; Router state treats routes as opaque strings. These tests prove nested routes remain first-class navigation routes.

---

### Phase 4 — `<ntx-router>` DOM mounting coverage

**Files**

- `tests/frontend/tests/components/ntx-router.test.js`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-router.js`

**Add tests**

1. Deep-link nested detail mounts child renderer:

```text
#Product/1/Comment/2
-> <ntx-comment-card ref="Product/1/Comment/2" display="lg">
```

2. Deep-link nested named view mounts schema renderer and no method attr:

```text
#Product/1/Comment/2/@item
-> <ntx-comment-card ref="Product/1/Comment/2" display="lg">
```

3. Deep-link nested action mounts method renderer:

```text
#Product/1/Comment/2/like
-> <ntx-like-method ref="Product/1/Comment/2" method="like" display="lg">
```

4. Invalid nested routes restore/show slot instead of mounting arbitrary tags.
5. Collection nested route, if retained:

```text
#Product/1/Comment/@table
-> <ntx-comment-table model="Comment" parent="Product/1">
```

**Likely code change**

No DOM code change expected. `<ntx-router>` already mounts arbitrary `{ tag, attrs }` returned by `Router.resolved`.

---

### Phase 5 — NTT/Component nested ref transport audit

**Files**

- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`
- `packages/n3tx-core/src/n3tx_core/static/core/Component.js`
- `tests/frontend/tests/core/NTT.test.js`
- `tests/frontend/tests/integration/nested-entities.test.js`

**Questions to answer with tests**

1. When a component receives `ref="Product/1/Comment/2"`, does it fetch the correct backend URL?
2. Does the resulting child entity register under the `Comment` DynamicClass or accidentally under `Product`?
3. Do populated nested objects with `$id = http://.../Product/1/Comment/2` still normalize to href arrays?
4. Do legacy parent-scoped table-name hrefs still work?

**Recommended implementation if a gap appears**

Add a small route/ref parser in `NTT.js` rather than spreading string-splitting across components:

```js
function parseEntityRef(ref) {
  const parts = String(ref || '').replace(/^https?:\/\/[^/]+\//, '').split('/').filter(Boolean);
  if (parts.length === 2) return { model: parts[0], id: parts[1], hrefPath: parts.join('/') };
  if (parts.length === 4 && isClassName(parts[0]) && isClassName(parts[2])) {
    return { parentModel: parts[0], parentId: parts[1], model: parts[2], id: parts[3], hrefPath: parts.join('/') };
  }
  return null;
}
```

Use it in the attach/fetch path so schema lookup can use the child model while transport href remains canonical nested class path.

**Keep the interface simple**

Mounted components should continue to receive one public attr:

```html
ref="Product/1/Comment/2"
```

Do not add `parent-model`, `parent-id`, `child-model`, or transport-specific attrs unless tests prove they are necessary.

---

### Phase 6 — Documentation/status cleanup

**Files**

- `FRONTEND.md`
- `.project/refactor/1-routes-grammar/issues/017-frontend-nested-class-route-support-plan.md`

`FRONTEND.md` already documents nested routes as planned. After implementation, update wording from “planned” to “supported” and note the exact one-hop grammar and invalid-route behavior.

---

## Main Code Shape

The desired router shape is already close to this:

```js
if (parts.length >= 3 && isClassNameToken(parts[2])) {
  const [parentModel, parentId, childModel, childId, nestedAction] = parts;

  if (parts.length === 4) {
    return { type:'nested-detail', parentModel, parentId, model: childModel, id: childId, action:null, params };
  }

  if (nestedAction === '@' || nestedAction?.startsWith('@')) {
    return { type:'nested-detail', parentModel, parentId, model: childModel, id: childId, view, isViewRoute:true, params };
  }

  return { type:'nested-action', parentModel, parentId, model: childModel, id: childId, action:nestedAction, params };
}
```

Resolution should continue to produce a component instruction, not perform network work:

```js
{
  tag: resolveViewTag(commentSchema, parsed.view, 'member'),
  attrs: { ref: 'Product/1/Comment/2', display: 'lg', ...passthrough },
}
```

---

## Risks and Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Child schema lookup uses parent model | Nested detail could mount the wrong renderer | Explicit tests: `getSchema('Comment')` renderer wins |
| `NTT.attach()` caches nested child under parent model | Updates/method calls may target wrong DynamicClass | Add `parseEntityRef()` if current behavior fails tests |
| Invalid extra segments mount arbitrary tags | Security and route correctness risk | Preserve `invalid` route behavior and DOM slot fallback |
| Nested action/view collision | `@like` must never become method `like` | Tests for both nested action and same-named nested view |
| Over-general arbitrary-depth parser | Adds ambiguity before backend supports it | Keep only one-hop grammar |
| Legacy table-name refs regress | Existing populated refs and stored data still use old forms | Add regression tests for table-name hrefs |

---

## Verification Plan

Focused unit/component checks:

```bash
cd /workspace/tests/frontend && npx vitest run \
  tests/core/route-functions.test.js \
  tests/core/Router.test.js \
  tests/components/ntx-router.test.js \
  tests/core/NTT.test.js \
  tests/integration/nested-entities.test.js
```

Broader frontend check after any NTT/Component changes:

```bash
cd /workspace/tests/frontend && npx vitest run
```

Optional browser smoke after backend issue `016` is green:

```bash
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js tests/e2e/route-grammar-smoke.spec.js
```

---

## Acceptance Checklist

```text
[ ] parseRoute recognizes Product/1/Comment/2 as nested-detail
[ ] parseRoute recognizes nested @ views and nested actions distinctly
[ ] buildRoute round-trips nested detail/view/action routes
[ ] resolveRoute returns child renderer and ref=Product/1/Comment/2
[ ] Router state/hash/back/reset cover nested routes
[ ] ntx-router mounts nested detail/view/action DOM correctly
[ ] Invalid nested extra segments resolve to null/no mounted arbitrary component
[ ] Component/NTT fetch/attach nested class refs without breaking legacy table-name refs
[ ] Documentation says nested routes are supported, not merely planned
```

### Critical Files for Implementation

- `packages/n3tx-core/src/n3tx_core/static/core/Router.js`
- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js`
- `packages/n3tx-core/src/n3tx_core/static/core/Component.js`
- `tests/frontend/tests/core/route-functions.test.js`
- `tests/frontend/tests/components/ntx-router.test.js`
