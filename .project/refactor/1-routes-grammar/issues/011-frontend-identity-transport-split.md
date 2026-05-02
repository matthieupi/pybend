# 011 — Frontend Class-Name Response Identity Audit

## ✅ Recommendation

Treat issue 011 as a **frontend audit and regression-test slice**, not a new
identity abstraction. After issue 010, backend responses advertise class-name
identity directly through `$id`:

```json
{
  "$schema": "/Product",
  "$id": "/Product/1"
}
```

The frontend should continue using the existing simple invariant:

```text
response.$id -> instance.href -> READ/UPDATE/DELETE/method target
```

Do **not** introduce `$href`, `links`, or `idUrl` in this slice unless tests
surface a concrete need. The goal is to prove the current runtime model works
with class-name `$id` values and to remove stale test assumptions that `$id`
must be table-name based.

---

## 1. Scope

### In scope

- Lock frontend behavior for regular class-name `$id` values such as
  `/Product/1`.
- Lock preservation of class-name nested ref strings such as
  `/Product/1/Comment/2` where current components treat refs opaquely.
- Preserve legacy table-name `$id` compatibility while legacy routes remain
  available.
- Update frontend mocks and expectations from table-name `$id` to class-name
  `$id`.
- Add tests proving the runtime does not require `$href` or `links`.

### Out of scope

- Implementing nested route parsing or nested router mounting. That belongs to
  issue 017.
- Adding backend class-name write/method mirrors. That belongs to issues 012–014.
- Adding `$href`, `links`, `idUrl`, aliases, or frontend-only canonical identity
  registries.
- Removing legacy table-name ref support.

---

## 2. Current Runtime Findings

The core runtime already mostly follows the desired model.

### `NTT.js`

Dynamic instances currently use backend `$id` as the href:

```js
constructor(data) {
  super(className, data.id);
  this.value = data;
  this.href = data.$id || `${href}/${this.id}`;
}
```

The value getter serializes that href back into `$id`:

```js
get value() {
  return {
    ...this._data,
    "$schema": this.constructor._schema?.$id || `${config.API_URL}/${this.constructor.addr}`,
    "$id": this.href,
  };
}
```

That is exactly the right model after issue 010.

### `Component.js`

Flat class-name refs such as `Product/1` continue through normal `ATTACH`
behavior. Absolute URL refs with `data-model` still derive the id from the final
path segment and pass the original href through `meta.href`.

Nested class-name refs such as `Product/1/Comment/2` need issue 017 for full
router/runtime address parsing. In issue 011, only opaque preservation in list
and ref-picker components should be tested.

### `ntx-list-field.js` and `ntx-ref-picker.js`

Both components already treat object refs via `$id` and string refs as opaque ref
strings. The main work is to add class-name `$id` cases and ensure no code
expects table-name paths.

---

## 3. File-by-File Implementation Plan

### 3.1 `tests/frontend/tests/integration/helpers/mock-schemas.js`

Update test helper response identities to match issue 010.

#### Current

```js
export function makeProductData(id = 1) {
  return {
    id,
    $schema: `${API_URL}/Product`,
    $id: `${API_URL}/products/${id}`,
    ...
  };
}
```

#### Target

```js
export function makeProductData(id = 1) {
  return {
    id,
    $schema: `${API_URL}/Product`,
    $id: `${API_URL}/Product/${id}`,
    ...
  };
}
```

For nested comments:

```diff
- $id: `${API_URL}/products/${productId}/comments/${id}`,
+ $id: `${API_URL}/Product/${productId}/Comment/${id}`,
```

For flat likes:

```diff
- $id: `${API_URL}/likes/${id}`,
+ $id: `${API_URL}/Like/${id}`,
```

### 3.2 `tests/frontend/tests/core/NTT.test.js`

Add a focused describe block, e.g.:

```js
describe('class-name response identity', () => { ... })
```

Required tests:

1. **Instance href uses class-name `$id`**

```js
DC.READ([{ id: 501, name: 'Class ID', price: 1, $id: 'http://localhost:5000/DCTest/501' }]);
const inst = DC.instances.get('501');
expect(inst.href).toBe('http://localhost:5000/DCTest/501');
```

2. **Value getter emits class-name `$id`**

```js
expect(inst.value.$id).toBe('http://localhost:5000/DCTest/501');
```

3. **No `$href` or `links` are emitted**

```js
expect(inst.value.$href).toBeUndefined();
expect(inst.value.links).toBeUndefined();
```

4. **Legacy table-name `$id` still works as href**

```js
DC.READ([{ id: 502, name: 'Legacy ID', price: 1, $id: 'http://localhost:5000/dc_tests/502' }]);
expect(DC.instances.get('502').href).toBe('http://localhost:5000/dc_tests/502');
```

5. **Method calls target class-name href**

Spy on `send` for an instance with `$id=/DCTest/503` and call an exposed method:

```js
const sendSpy = vi.spyOn(inst, 'send');
inst.like();
expect(sendSpy.mock.calls[0][0].target).toBe('http://localhost:5000/DCTest/503');
```

6. **`pull()` targets class-name href**

```js
const sendSpy = vi.spyOn(inst, 'send');
inst.pull();
expect(sendSpy.mock.calls[0][0].target).toBe('http://localhost:5000/DCTest/504');
```

7. **Populated child normalization preserves child class-name `$id`**

Create a parent schema with a ListRef-style field and a child schema already
registered. Feed a populated wrapper:

```js
ProductDC.READ({
  id: 1,
  $id: `${API_URL}/Product/1`,
  comments: {
    data: [{ id: 2, $schema: `${API_URL}/Comment`, $id: `${API_URL}/Product/1/Comment/2`, name: 'Child' }],
    meta: { total: 1, limit: 20, offset: 0, has_more: false },
  },
});
expect(ProductDC.instances.get('1').value.comments).toEqual([`${API_URL}/Product/1/Comment/2`]);
```

Do not require `NTT.get('Product/1/Comment/2')` in this issue; that is issue
017.

### 3.3 `tests/frontend/tests/integration/schema-bootstrap.test.js`

Update existing expectations:

```diff
- expect(val.$id).toContain('/products/1');
+ expect(val.$id).toBe(`${API_URL}/Product/1`);
```

Add a regression asserting the old table-name collection endpoint still remains
the DynamicClass collection href:

```js
expect(DC.href).toBe(`${API_URL}/products`);
```

This keeps an important distinction clear:

```text
schema/table metadata -> collection href remains /products
entity response $id   -> instance href becomes /Product/1
```

### 3.4 `tests/frontend/tests/components/ntx-list-field.test.js`

Add tests for opaque class-name refs:

1. **Renders class-name string refs as-is**

```js
const el = mountListField({
  value: ['http://localhost:5000/Product/1/Comment/2'],
});
const child = el.shadowRoot.querySelector('ntx-item');
expect(child.getAttribute('ref')).toBe('http://localhost:5000/Product/1/Comment/2');
```

2. **Removes class-name refs as-is**

```js
expect(parentSend).toHaveBeenCalledWith(expect.objectContaining({
  target: 'http://localhost:5000/Product/1/Comment/2',
}));
```

3. **Object refs use object `$id`**

```js
value: [{ id: 2, $id: 'http://localhost:5000/Product/1/Comment/2' }]
```

Assert rendered child `ref` and remove button `data-ref` both preserve the exact
class-name URL.

### 3.5 `tests/frontend/tests/components/ntx-ref-picker.test.js`

Add tests for object refs with class-name `$id`:

1. **`currentRefs` extracts class-name `$id` from object arrays**

```js
comments: [
  { $id: 'http://localhost:5000/Product/1/Comment/2', text: 'Comment 2' },
]
```

2. **Picker filters class-name current refs**

Use `DC.instances` entries whose `value.$id` is class-name based and assert the
matching option is filtered out.

3. **`_addRef` dispatches class-name `$id` from entity**

```js
const entity = { id: 5, text: 'Test', $id: 'http://localhost:5000/Product/1/Comment/5' };
picker._addRef(5, entity);
expect(event.detail.ref).toBe('http://localhost:5000/Product/1/Comment/5');
```

Fallback behavior for objects without `$id` should now use the class-name model
base route, not the collection marker route:

```text
entity with no $id -> /{ClassName}/{id}
```

The preferred issue 010 path is still response `$id`; this fallback is only for
incomplete/mock data and must not derive from `/ClassName/_`.

### 3.6 Production code files

Expected production changes: **none or very small**.

Audit these files while writing tests:

```text
packages/n3tx-core/src/n3tx_core/static/core/NTT.js
packages/n3tx-core/src/n3tx_core/static/core/Component.js
packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list-field.js
packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js
```

Only change production code if a test reveals a real table-name assumption.
Accepted production shape after the audit:

- `DynamicClass.href` is the class-name model base URL, e.g. `/Product`.
- Collection transport appends the explicit `_` marker at collection call sites,
  e.g. `/Product/_`.
- `instance.href` should use response `$id`.
- `ntx-ref-picker` nested create targets can remain table-name based until issue
  016/017 fully define nested write mirrors.

---

## 4. Architecture Flow

```text
                  +-----------------------------+
                  | Backend entity response     |
                  | $schema=/Product            |
                  | $id=/Product/1              |
                  +--------------+--------------+
                                 |
                                 v
                  +-----------------------------+
                  | DynamicClass.READ()         |
                  | upsertInstance(Product, d)  |
                  +--------------+--------------+
                                 |
                                 v
                  +-----------------------------+
                  | new Product instance        |
                  | addr = "1"                 |
                  | href = data.$id             |
                  +--------------+--------------+
                                 |
       +-------------------------+--------------------------+
       |                                                    |
       v                                                    v
+-------------------+                            +----------------------+
| value getter      |                            | network operations   |
| $id = href        |                            | target = href        |
+-------------------+                            +----------------------+
```

Collection reads remain separate:

```text
Product schema $id=/Product      -> DynamicClass.href=/Product
Collection READ transport        -> /Product/_
Entity response $id=/Product/1   -> instance.href=/Product/1
```

---

## 5. Test Sequence

### Step 1 — Update mocks and add locking tests

1. Update `mock-schemas.js` response `$id` helpers.
2. Add NTT tests for class-name `$id`, no `$href`, method/pull target behavior.
3. Add list-field/ref-picker opaque class-name ref tests.

Run expected-red or expected-green tests:

```bash
cd /workspace/tests/frontend && npx vitest run \
  tests/core/NTT.test.js \
  tests/integration/schema-bootstrap.test.js \
  tests/components/ntx-list-field.test.js \
  tests/components/ntx-ref-picker.test.js
```

### Step 2 — Minimal runtime fixes if needed

If tests expose a table-name assumption, fix only that path.

Likely examples:

- a test expects `/products/1` and should be updated, not production code
- a component reconstructs a table-name ref despite receiving `$id`; change it to
  preserve `$id`

### Step 3 — Focused verification

Run the focused command again:

```bash
cd /workspace/tests/frontend && npx vitest run \
  tests/core/NTT.test.js \
  tests/integration/schema-bootstrap.test.js \
  tests/components/ntx-list-field.test.js \
  tests/components/ntx-ref-picker.test.js
```

### Step 4 — Broader frontend verification

If focused tests pass:

```bash
cd /workspace/tests/frontend && npx vitest run
```

---

## 6. Acceptance Checklist

| Contract | Proof |
|---|---|
| DynamicClass instances use class-name `$id` as `href` | `NTT.test.js` |
| Value serialization emits class-name `$id` | `NTT.test.js`, schema bootstrap test |
| No `$href` or `links` required/emitted | `NTT.test.js` |
| Legacy table-name `$id` still attaches as href | `NTT.test.js` |
| Method calls target class-name instance href | `NTT.test.js` |
| Pull/read targets class-name instance href | `NTT.test.js` |
| Static `DynamicClass.href` remains class-name model base; collection READ appends `_` | schema bootstrap test, `NTT.test.js` |
| Populated child `$id` values are preserved as refs | `NTT.test.js` or integration test |
| List field preserves class-name string/object refs | `ntx-list-field.test.js` |
| Ref picker currentRefs/addRef uses class-name `$id` | `ntx-ref-picker.test.js` |

---

## 7. Risks and Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Frontend mutations hit routes not implemented yet | `$id` becomes `/Product/1`, and methods/writes use href | Land issues 012–014 before relying on mutation E2E flows |
| Nested class-name refs are longer than current flat refs | `NTT.get()` currently understands `Model/id`, not arbitrary nested identity | In issue 011, only preserve nested refs opaquely; full parser/runtime support is issue 017 |
| Collection and entity URLs get conflated | `GET /Product` is schema, not list | Keep `DynamicClass.href` as `/Product`; append `_` only for collection transport |
| Tests hide stale table-name assumptions in helpers | Mocks currently emit `/products/id` | Update helpers first and assert exact class-name `$id` |
| Over-engineering returns through `$href`/links | Adds concepts now intentionally rejected | Add negative assertions that `$href` and `links` are absent |

---

## 8. Suggested Commit

```text
test(frontend): Verify class-name response identity [routes-grammar]
```

Expected files touched:

- `tests/frontend/tests/integration/helpers/mock-schemas.js`
- `tests/frontend/tests/core/NTT.test.js`
- `tests/frontend/tests/integration/schema-bootstrap.test.js`
- `tests/frontend/tests/components/ntx-list-field.test.js`
- `tests/frontend/tests/components/ntx-ref-picker.test.js`
- production runtime files only if tests reveal a real issue
