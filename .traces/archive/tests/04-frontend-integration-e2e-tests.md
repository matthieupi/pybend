# Frontend Integration & E2E Test Plan — N3TX N3TX 0.6

> **Scope**: Component interactions, message flows, data binding (integration) + real browser automation (Playwright E2E)
> **Framework**: Integration — Vitest + jsdom; E2E — Playwright
> **Estimated test cases**: ~180+

---

## A. CLASSICAL INTEGRATION TESTS

### 1. Schema Bootstrap Flow

**Test: Schema fetch triggers DynamicClass creation and READ**
- Component sends ATTACH with model name 'Product' to N3TX
- N3TX.SCHEMA handler receives schema from backend
- DynamicClass created, registered in N3TX.#prototypes
- $defs nested schemas (Comment, ProductLike) also registered
- DynamicClass.READ called with initial READ TX
- Product instances created from response, stored in DynamicClass.instances
- Edge: pre-loaded schema via `<script data-ntx-schema>` consumed before network
- Edge: pre-loaded data via `<script data-ntx-data>` skips network fetch
- Edge: multiple simultaneous ATTACH requests queue and replay once schema ready
- Edge: timeout on /Product fetch → error logging

**Test: DynamicClass properties and methods generated from schema**
- product.name getter returns value from instance._data
- Property setter updates value and calls signal()
- Read-only field throws TypeError
- Type mismatch in setter throws TypeError
- product.comment() sends TX with correct target and payload

**Test: $defs registered with own schemas and instances**
- N3TX.get('Comment') returns DynamicClass
- Comment has own .instances map
- Comment properties and methods available independently

---

### 2. Entity Lifecycle (ATTACH → DESCRIBE → UPDATE → Signal → Re-render)

**Test: NTTElement receives entity via DESCRIBE**
- DESCRIBE handler receives {proto: schema, data: values}
- this.schema set to proto, this.value set to data
- value setter triggers render() if both schema and data present
- Entity signal subscription established
- Future value changes from entity.signal() trigger re-render

**Test: NTTElement receives UPDATE notification**
- UPDATE handler receives data with $schema and $id
- this.value updated, render triggered
- If $schema name differs, CONNECT sent to resolve

**Test: Entity value change propagates through Observable**
- instance.signal() → all listeners invoked
- Component listening via _entityUnsub callback receives notification

**Test: Surgical DOM update (incremental patch)**
- update(prev, next) returns true → render() NOT called (partial update)
- Component updates only changed properties in shadow DOM
- update() returns false → full render() called

**Test: Nested entity population and normalization**
- normalizePopulated() converts populated data to href array
- Child instances pre-registered in Comment.instances
- Entity downstream works with normalized hrefs

---

### 3. Actor Messaging (TX Routing Through Matrix)

**Test: TX routed from component to DynamicClass**
- TX(name: 'ATTACH', target: 'N3TX', data: 'Product') → Matrix → N3TX.ATTACH

**Test: TX routed to network (remote)**
- TX(name: 'READ', target: 'http://localhost:5000/products') → Matrix → NetworkAdapter.send
- x-access-token header included if jwtToken in localStorage

**Test: Parent-child message delivery**
- ntx-list registers as watcher on DynamicClass
- DynamicClass.READ sends UPDATE TX to ntx-list with instance addresses

**Test: TX bubble-up through Actor hierarchy**
- ntx-item sends TX to non-existent local actor → bubbles to Matrix

**Test: Message ordering and delivery guarantees**
- 5 sequential ATTACHes before schema ready → all queued
- Schema arrives → all 5 replayed in order
- Edge: duplicate ATTACH for same address

---

### 4. Observable Pattern (Signal/Observe/Notify)

**Test: signal() with callback**
- Callback called immediately (wait=false)
- Callback registered, unsubscribe removes it

**Test: signal() without callback**
- All callbacks in __signals invoked with entity

**Test: observe() property changes**
- Callback not called immediately
- Property change → callback(newVal, oldVal, property, instance)
- Unsubscribe removes callback

**Test: notify() fires observers**
- Only observers for specified property called
- Others not called

**Test: Cross-component reactivity**
- ntx-item and ntx-list both observe same DynamicClass
- Update triggers both independently

---

### 5. Router + ntx-router Integration

**Test: Router initialization**
- Router created with name "main", hash sync enabled
- hashchange listener attached

**Test: NAVIGATE changes route and hash**
- Router.current = new data
- Stack updated, hash updated
- ntx-router re-renders with new view

**Test: BACK pops route**
- Returns to previous route, hash updated

**Test: Hash sync on page load**
- /matrix.html#Product/3 → Router reads hash, shows Product/3

**Test: Back unavailable at root**
- canGoBack=false, no back button

**Test: Route types**
- String 'Product/3' → resolves tag from schema
- Object {tag, attrs, title} → creates custom component
- String '@profile' → creates ntx-profile

---

### 6. Form Generation + Entity Binding

**Test: Schema drives form**
- Formidable.getForm() renders header + fields
- Field order from schema.ui.field_order respected
- Fields with ui.display=false hidden
- Protected fields hidden in edit mode

**Test: Inputs bound to entity**
- Input data-key matches entity field
- User change → entity value updated → signal → re-render

**Test: Field grouping**
- schema.ui.groups → <fieldset> elements with legends

**Test: Field widgets**
- widget='currency' → $ prefix + number input
- widget='textarea' → <textarea>
- type='boolean' → checkbox
- type='number' → number input with parseFloat

**Test: Method buttons attached**
- Methods with ui.attach_to render after target field
- In edit mode, method buttons hidden

**Test: Form validation**
- minLength enforced, required field validation

---

### 7. Permission + UI Integration

**Test: canAction() gates edit/delete buttons**
- OWNER: owner sees edit, non-owner doesn't
- ROLE('admin'): admin sees, non-admin doesn't

**Test: canView() hides fields**
- Field access.view='admin': non-admin → hidden

**Test: Protected fields in edit mode**
- ui.protected=true: shown in display, hidden in edit

**Test: OWNER evaluates against entity**
- Extracts id from href "http://.../users/3", compares to user_id

**Test: Composite rules**
- {op: 'or', rules: [owner, admin]} → evaluates correctly
- {op: 'and', rules: [authenticated, admin]} → both must pass

---

### 8. Network Adapter + Entity Sync

**Test: HTTP GET schema** → N3TX.SCHEMA handler invoked
**Test: HTTP POST create** → instance added to DynamicClass
**Test: HTTP PUT update** → entity refreshed
**Test: HTTP DELETE** → instance removed, watchers notified
**Test: 401 → redirect to login**
**Test: Error response → Logging.error**
**Test: Token refresh** → localStorage updated
**Test: Pagination meta** → has_more for Load More button

---

### 9. List + Item Interaction

**Test: ListElement receives address array**
- DynamicClass.READ → watchers → ListElement.UPDATE → render

**Test: Child creation per address**
- createChild() → element with ref, display from SIZE_CASCADE

**Test: Item click → SELECT → NAVIGATE**
- Click → SELECT TX → router NAVIGATE → detail view

**Test: Selection API**
- select/deselect/toggle/clearSelection

**Test: Load More pagination**
- Button visible when has_more=true
- Click → offset incremented → new READ → items appended

**Test: Empty state**
- UPDATE([]) → empty render

---

### 10. Nested Entities

**Test: Product comments ListRef**
- href array rendered as comment list

**Test: Add comment via method**
- ntx-method POST → product._response_ → pull() → comment list updated

**Test: Reply (self-referential)**
- parent_id creates nested comment

**Test: Delete nested entity**
- DELETE with nested URL → instance removed → parent list updated

**Test: Cascade populate**
- depth=2 → comments + their likes loaded

---

### 11. Method Execution

**Test: Instance method** — ntt.call('like') → entity href → _response_ → pull()
**Test: Class method** — Product.call('search') → DynamicClass href
**Test: Method with form** — input captured → payload sent
**Test: Auto-invoke** — mode='auto' → callMethod on input change
**Test: Count badge** — count-field attribute → badge shows likes count
**Test: Response handling** — string response → postCall clears form

---

### 12. Display Mode Cascade

**Test: Resize triggers mode change** — ResizeObserver → displayMode → render()
**Test: Size cascade** — lg parent → sm children
**Test: All size methods** — xs (pill), sm (row), md (card), lg/xl (detail)

---

## B. PLAYWRIGHT E2E TESTS

### 1. Page Load & Bootstrap

- **matrix.html loads without console errors**
  - No exceptions, shadow DOM exists, stylesheets load (no 404)

- **Product list appears with seeded data**
  - `<ntx-list model="Product">` rendered, items visible (at least 3)
  - Each product shows name field

- **Schema fetch completes**
  - GET /Product → 200, response has $schema, $id, properties, methods

- **Framework components register**
  - `window.N3TX` available, `N3TX.get('Product')` returns DynamicClass

- **Theme CSS loads**
  - CSS variables defined (--surface-0, --text-0, --accent)

- **Topbar renders correctly**
  - Anonymous: "Sign in" link; Authenticated: user pill

---

### 2. Product List Behavior

- **Items display correct fields** — name, price, description per schema.ui.field_order
- **Count badge** — shows correct total
- **Load More button** — appears when has_more=true, click loads more items
- **Empty state** — no products → empty message
- **Responsive** — 480px→sm, 768px→md, 1200px→lg

---

### 3. Product Detail Navigation

- **Click product → detail view** — hash changes to #Product/1, detail form shows
- **Back button** — returns to list, hash clears
- **URL hash sync** — manually change hash → navigates without reload
- **Direct URL** — /matrix.html#Product/3 loads detail directly
- **Detail shows all fields** — header, non-hidden fields, method buttons

---

### 4. CRUD Operations (Requires Auth)

- **Create product** — fill form → POST → new item in list
- **Edit product (owner)** — click Edit → modify → Save → PUT → updated
  - Protected fields NOT editable
- **Edit denied (non-owner)** — Edit button NOT visible
- **Delete product** — click Delete → confirm → DELETE → removed from list
- **Delete denied** — Delete button NOT visible for unauthorized
- **Changes persist** — reload page, values match saved

---

### 5. Form Validation

- **Required field empty** — error shown, form not submitted
- **Min/max length** — strings < min rejected
- **Number validation** — non-numeric rejected, negative rejected (if gt:0)
- **Currency widget** — $ prefix visible, value stored as number
- **Textarea** — multi-line text, line breaks preserved
- **Protected field** — hidden in edit mode

---

### 6. Authentication UI & Flow

- **Anonymous topbar** — "Sign in" link visible
- **Login form** — email + password → POST /users/login → token stored → redirect
- **Login error** — invalid credentials → error message
- **Register form** — name + email + password → POST /users/register → redirect
- **Authenticated topbar** — user pill with initial + name
- **User dropdown** — email, role, theme toggle, profile, logout
- **Logout** — token cleared, redirect to login
- **Token validation** — reload with valid token → still authenticated

---

### 7. Authorization UI

- **Anonymous** — no edit/delete buttons anywhere
- **Non-owner** — no edit/delete on others' items
- **Owner** — edit/delete visible on own items
- **Admin** — edit/delete on all items
- **Field-level access** — field with view='admin' hidden for non-admin
- **Protected fields** — display-only, hidden in edit

---

### 8. Comments (Nested Entity)

- **Comment form on product detail** — `ntx-method[method="comment"]` visible
- **Submit comment** — POST sent, comment appears in list, count updated
- **Comments list** — shows author, text, timestamp
- **Delete own comment** — confirm → removed → count decreases
- **Cannot delete others' comments** — delete button hidden
- **Reply to comment** — parent_id set, nested/indented render

---

### 9. Likes (Method Button)

- **Like button visible** — `ntx-method[method="like"]` with heart icon + count
- **Click like** — POST sent, count increments, visual feedback
- **Unlike (toggle)** — click again, count decrements
- **Count badge** — matches actual likes, persists after reload
- **Permission gate** — anonymous → button hidden/disabled

---

### 10. Theme Toggle

- **Dark mode** — --surface-0 dark, --text-0 light
- **Light mode** — --surface-0 light, --text-0 dark
- **Toggle** — instant switch, no reload
- **Persistence** — theme stored in localStorage, survives reload
- **Accent colors** — visible in both themes
- **Glass morphism** — backdrop blur applied

---

### 11. Responsive/Adaptive Display

- **Pill (xs)** — 360px viewport → compact pill with name only
- **Row (sm)** — 600px → avatar + name + inline fields
- **Card (md)** — 800px → full form, all fields
- **Detail (lg/xl)** — 1200px+ → full page layout
- **Orientation change** — adapts smoothly
- **Font scaling** — sizes appropriate per breakpoint

---

### 12. Logs Panel

- **Open/close** — toggle button, slides in/out
- **Entries displayed** — level, timestamp, message, color-coded
- **Filter by level** — error/warn/info only
- **Clear logs** — all removed, badge resets
- **Expand/collapse** — JSON detail shown on expand
- **Badge count** — updates as logs added

---

### 13. Error Scenarios

- **Server down** — error message, graceful, can retry
- **401 → redirect to login**
- **403 → action denied feedback**, list unchanged
- **404 → item not found**, can navigate back
- **Network timeout** — error shown, form data preserved
- **Malformed response** — parse error caught, no white screen
- **Missing schema field** — field skipped, form still renders

---

### 14. Favorites

- **Navigate** — click Favorites link → #@favorites
- **Shows liked products** — only liked items
- **Empty state** — no likes → empty message
- **Unlike from favorites** — product removed from list

---

### 15. Visual Regression

- **Screenshot all display modes** — xs, sm, md, lg (compare baselines)
- **Dark/light screenshots** — both themes match baselines
- **Interaction states** — hover, focus, error states
- **CSS vars resolve** — no "var(...)" in computed styles
- **Typography** — Inter font family, correct weights

---

## KEY PLAYWRIGHT SELECTORS

```
// Components
'ntx-list'                                    // List container
'ntx-item[ref="Product/1"]'                   // Specific item
'ntx-router[name="main"]'                     // Router
'ntx-topbar'                                  // Top navigation
'ntx-logs'                                    // Logs panel
'ntx-method[method="like"]'                   // Method button

// Shadow DOM piercing (Playwright)
'ntx-item[ref="Product/1"] >>> span'

// Form elements
'input[data-key="name"]'
'input[data-key="price"]'
'textarea[data-key="description"]'
'button[class*="edit-btn"]'
'button[class*="delete-btn"]'

// Navigation
'a[href="/login.html"]'
'button[title="Back"]'
'a[href="#@favorites"]'

// Auth
'#email', '#password'
'.user-pill', '.user-dropdown', '.logout-btn'

// Logs
'button[class*="toggle"]'
'button[data-level="error"]'
'.log-list'
```

### Network Requests to Monitor

```
GET  /Product                           — Schema fetch
GET  /products?limit=20&offset=0        — List fetch
GET  /products/1                        — Single entity
POST /products                          — Create
PUT  /products/1                        — Update
DELETE /products/1                      — Delete
POST /products/1/comment               — Custom method
POST /users/login                      — Login
POST /users/register                   — Register
GET  /auth/me                          — User info
```

### Browser Evaluation Commands

```javascript
window.N3TX.get('Product')                     // DynamicClass
window.N3TX.get('Product').instances.size       // Instance count
document.documentElement.getAttribute('data-theme')  // Theme
window.localStorage.getItem('jwtToken')        // Auth token
```

---

## EDGE CASES & CORNER CASES

### Data
- Empty/null values in lists, very long strings, special characters (emoji, HTML)
- Decimal precision in currency, negative numbers, large collections (1000+)
- Concurrent updates, stale data after deletion

### Timing & Race Conditions
- ATTACH before SCHEMA, multiple DESCRIBE on same entity
- NAVIGATE while previous route loading, rapid save clicks
- Page reload during in-flight request

### Browser
- Very small viewport (<320px), very large (4K+)
- Touch-only devices, keyboard navigation (Tab, Enter, Escape)
- Copy/paste, browser back/forward buttons
- Private/incognito mode, third-party cookie restrictions

### Auth
- Token expired mid-session, rapid login/logout
- Multiple tabs (one logs out), CORS preflight

### Component Lifecycle
- disconnectedCallback during render, rapid attribute changes
- Component removal while async in flight, memory leaks
- Shadow DOM styling conflicts, nested components of same type

### Form & Validation
- Submit with required field empty, paste large text
- Browser autofill interference, hidden required fields
- Array fields with complex objects
