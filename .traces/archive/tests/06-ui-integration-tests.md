# 06 — UI Integration Tests (Playwright End-to-End User Flows)

> **Scope**: Complete user journeys through the application, testing that components work together correctly, state propagates, and the full data lifecycle works end-to-end.
> **Framework**: Playwright (`tests/e2e/*.spec.js`)
> **Goal**: Verify every user workflow from start to finish. Registration through deletion. Every action must produce the expected result and the UI must reflect changes in real-time.
> **Estimated test cases**: ~250+

---

## EXECUTION INSTRUCTIONS FOR SUBAGENTS

You are writing Playwright E2E integration tests for a schema-driven web application. These tests verify COMPLETE USER FLOWS — not individual components. Each test scenario chains multiple actions and verifies the cumulative result. Think of these as user stories being executed step by step.

### Critical Technical Context

1. **App URL**: `/matrix.html`
2. **Base URL**: `http://localhost:5000` (configured in `playwright.config.js`)
3. **Shadow DOM**: All N3TX components use Shadow DOM. You MUST use `.evaluate()` to access `el.shadowRoot`.
4. **Auth**: Use helpers from `./fixtures/auth.js`:
   ```js
   import { loginAs, logout, getToken, setToken, clearToken, USERS } from './fixtures/auth.js';
   ```
5. **Server fixture** (`./fixtures/server.js`): `seedDatabase()`, `resetDatabase()`, `waitForServer()`
6. **Seed users**: alice/bob/charlie (role: user, passwords: alice123/bob123/charlie123)
7. **Seed data**: 3+ products owned by different users, with comments and likes
8. **Models**: Product (name, price, description, user_owner, comments[], likes[]), Comment (name, description, parent_id, user_owner, likes[]), Like (user_owner), User (name, email, password, role)
9. **API Endpoints**:
   - `POST /users/register` — register new user (body: {name, email, password})
   - `POST /users/login` — login (body: {email, password}) → {token}
   - `GET /auth/me` — current user info (requires auth)
   - `GET /products` — list products (paginated)
   - `GET /products/{id}` — get product (with `?depth=1` for populated children)
   - `POST /products` — create product (requires auth)
   - `PUT /products/{id}` — update product (requires owner/admin)
   - `DELETE /products/{id}` — delete product (requires admin)
   - `POST /products/{id}/comment` — add comment (requires auth)
   - `POST /products/{id}/like` — like product (requires auth)
   - `GET /products/{id}/comments` — list product comments
   - `GET /products/{id}/likes` — list product likes
   - Schema: `GET /Product`, `GET /Comment`, `GET /Like`, `GET /User`

### Important Test Patterns

- **State verification**: After every mutating action, verify both the UI AND the API reflect the change
- **Cross-component verification**: When one component acts, verify other affected components update
- **Isolation**: Each `test.describe` block should be independent. Use `test.beforeEach` to set up clean state
- **Cleanup**: Tests that create data should note it for potential cleanup (or rely on seed reset)
- **Real assertions**: Don't use `expect(typeof x).toBe('boolean')` — assert the actual expected value
- **No conditional tests**: Don't use `if (hasEditBtn)` — set up the test so the condition is guaranteed

---

## AGENT 1: `flow-auth-lifecycle.spec.js` — Authentication Lifecycle

### Complete User Registration → Login → Session → Logout Flow

**Registration Flow**
1. Navigate to app, verify anonymous state (signin link visible)
2. Register new user via API: `POST /users/register` with `{name: 'Test User', email: 'test-flow@example.com', password: 'testpass123'}`
3. Verify registration returns success (201 or 200)
4. Login with newly registered credentials: `POST /users/login`
5. Verify login returns valid JWT token
6. Set token in localStorage and reload
7. Verify topbar shows user pill with "Test User" name
8. Verify `/auth/me` returns correct user data

**Login Flow (Existing User)**
9. Login as alice via API, set token, reload
10. Topbar shows alice's name and email in dropdown
11. Verify `localStorage['jwtToken']` contains the token
12. Make authenticated API call — succeeds
13. Make the same call without token — fails with 401

**Session Persistence**
14. Login as alice, reload page multiple times
15. After each reload, verify topbar still shows authenticated state
16. After each reload, verify product list still loads
17. Verify token in localStorage survives page reload

**Logout Flow**
18. Login as alice
19. Click logout button in topbar dropdown (via shadow DOM)
20. Verify token removed from localStorage
21. Verify topbar reverts to signin link
22. Verify authenticated API calls now fail with 401
23. Verify page still functions (product list loads — read is public)

**Multi-User Switching**
24. Login as alice → verify alice's state
25. Logout
26. Login as bob → verify bob's state (different name, email)
27. Verify products visible are filtered by bob's permissions (if applicable)
28. Logout → login as charlie → verify charlie's state

**Token Edge Cases**
29. Set invalid/garbage JWT in localStorage → reload → app handles gracefully (reverts to anonymous)
30. Set expired JWT → reload → app handles gracefully (401 on API calls, UI shows anonymous)
31. Login, then manually delete token from localStorage (without reload) → next API call fails, UI may degrade gracefully
32. Two browser tabs (simulated): login in one affects the other on reload

**Registration Edge Cases**
33. Register with duplicate email → API returns error (if uniqueness enforced) or succeeds (known bug B9)
34. Register with empty name → validation error
35. Register with empty email → validation error
36. Register with empty password → validation error
37. Register with very long name (1000+ chars) → either truncated or error
38. Login with correct email but wrong password → fails
39. Login with non-existent email → fails
40. Login with empty credentials → fails

---

## AGENT 2: `flow-product-crud.spec.js` — Product CRUD Lifecycle

### Complete Create → Read → Update → Delete Flow

**Create Product (Authenticated)**
1. Login as alice
2. Navigate to product list
3. Verify initial product count (store it)
4. Create product via API: `POST /products` with `{name: 'Integration Test Product', price: 42.99, description: 'Created by Playwright'}`
5. Verify API response contains new product with id, $schema, $id
6. Reload page → verify new product appears in list
7. Verify list count incremented by 1
8. Navigate to new product detail → verify all fields correct:
   - name: "Integration Test Product"
   - price: "$42.99"
   - description: "Created by Playwright"
   - user_owner: alice's user_id

**Create Product via UI (if create button exists)**
9. Login as alice, navigate to list
10. Click create button (in list header)
11. Fill in name input: "UI Created Product"
12. Fill in price input: 19.99
13. Fill in description: "Created via UI form"
14. Submit form
15. Verify new product appears in list
16. Navigate to new product detail — all fields match

**Read Product**
17. Anonymous user can view product list (no auth required for read)
18. Anonymous user can view product detail
19. Product detail shows $schema and $id in API response
20. Product detail with `?depth=1` returns populated comments and likes
21. Product schema (`GET /Product`) returns correct structure

**Update Product (Owner)**
22. Login as alice, navigate to alice's product
23. Click edit button → edit mode activates
24. Verify name input has current value
25. Change name to "Updated Product Name"
26. Click save → API PUT sent
27. Verify display mode shows "Updated Product Name"
28. Reload page → name persists as "Updated Product Name"
29. Verify API `GET /products/{id}` returns updated name

**Update Product (Non-Owner Blocked)**
30. Login as bob, navigate to alice's product
31. Verify edit button is NOT visible (bob is not owner and not admin)
32. Attempt API `PUT /products/{alice_product_id}` as bob → 403 Forbidden

**Update Individual Fields**
33. Login as owner, edit price from 42.99 to 99.99 → save → verify "$99.99"
34. Login as owner, edit description to new text → save → verify updated
35. Login as owner, clear description (empty string) → save → verify empty
36. Login as owner, set very long description (500+ chars) → save → verify

**Delete Product (Admin Only)**
37. Login as alice (regular user), navigate to alice's product
38. Verify delete button is NOT visible (delete requires admin role)
39. Attempt API `DELETE /products/{id}` as alice → 403 Forbidden
40. (If admin user exists) Login as admin → delete button visible → click → product removed

**Create → Update → Verify Persistence**
41. Create product "Lifecycle Test"
42. Update name to "Lifecycle Updated"
43. Reload page → verify "Lifecycle Updated" shows
44. Navigate away and back → still shows "Lifecycle Updated"
45. Verify via API → returns "Lifecycle Updated"

**Edge Cases**
46. Create product with minimum valid data (only required field: name)
47. Create product with name exactly at maxLength (200 chars)
48. Create product with price at minimum valid value (e.g., 0.01)
49. Create product with unicode characters in name: "Produit Français 日本語"
50. Create product with HTML in name: "<script>alert(1)</script>" — verify no XSS
51. Update product with same values (no actual change) — succeeds gracefully
52. Rapid create → update → update → verify final state correct
53. Create two products simultaneously (parallel API calls) — both succeed with unique IDs

---

## AGENT 3: `flow-comments.spec.js` — Comment Lifecycle

### Complete Add Comment → View → Reply → Delete Flow

**Add Comment to Product**
1. Login as alice
2. Navigate to product 1 detail view
3. Store current comment count
4. Submit comment via API: `POST /products/1/comment` with `{comment: {name: 'Test Comment', description: 'Written by Playwright'}}`
5. Verify API returns success
6. Reload page → navigate to product 1 detail
7. Verify comment count increased by 1
8. Verify new comment visible in comments list
9. Verify comment text matches what was submitted

**Add Comment via UI (Method Button)**
10. Login as alice, navigate to product detail
11. Find `ntx-method[method="comment"]` in item shadow DOM
12. Click the comment method button → form should appear
13. Fill in comment name: "UI Comment"
14. Fill in comment description: "Submitted through the UI"
15. Submit the form
16. Verify comment appears in the product's comment list (without full reload)
17. Verify comment count badge incremented

**Comment Display**
18. Navigate to product with comments
19. Comments list shows as `.list-field[data-value="comments"]`
20. Each comment rendered as `ntx-item` sub-component
21. Comment items show name and description
22. First 2 comments visible, rest collapsed with "Show N more" toggle
23. Clicking "Show N more" reveals all comments
24. Each comment shows the author/user_owner info

**Comment Metadata**
25. Comment has correct `$schema` (pointing to Comment schema)
26. Comment has correct `$id` (URL path: `/products/{pid}/comments/{cid}`)
27. Comment `user_owner` matches the submitting user's ID

**Nested Comments (Replies)**
28. Comment schema has `parent_id` field of type `selfref`
29. Create a reply: comment with `parent_id` pointing to existing comment ID
30. Verify reply appears (may be nested or flat depending on UI rendering)
31. Verify `parent_id` is set correctly in API response

**Multiple Users Commenting**
32. Alice adds comment "Alice's comment" to product 1
33. Bob adds comment "Bob's comment" to product 1
34. Charlie adds comment "Charlie's comment" to product 1
35. Navigate to product 1 → all three comments visible
36. Verify each comment's user_owner is different
37. Comment count shows correct total (previous count + 3)

**Comment on Different Products**
38. Alice comments on product 1
39. Alice comments on product 2
40. Verify product 1 comments don't appear on product 2 and vice versa
41. Each product's comment count is independent

**Anonymous User Cannot Comment**
42. Ensure no JWT token
43. Attempt `POST /products/1/comment` without auth → 401
44. Navigate to product detail as anonymous → comment method button may be hidden or non-functional
45. Verify no comment form appears for anonymous users

**Comment Edge Cases**
46. Comment with empty name → validation error (name required, minLength: 1)
47. Comment with very long description (10000+ chars) → succeeds or truncates
48. Comment with special characters: `<>&"'` → no XSS, renders safely
49. Comment with unicode: emoji, CJK, RTL text → renders correctly
50. Rapidly submit 5 comments → all 5 created with unique IDs
51. Comment on non-existent product → 404 error
52. Comment count shows 0 for product with no comments (verified in UI badge)

---

## AGENT 4: `flow-favorites-and-likes.spec.js` — Favorite & Like Lifecycle

### IMPORTANT: Product has `favorite` method (star icon, toggles). Comment has `like` method (heart icon, toggles).
### Product does NOT have a `like` method. The field is called `favorites` not `likes`.

### Complete Favorite → Verify Count → Unfavorite → Comment Like Flow

**Favorite a Product (Toggle)**
1. Login as alice
2. Get product 1's current favorites count via API: `GET /products/1?depth=1`
3. Favorite product 1: `POST /products/1/favorite`
4. Verify API returns `{"action": "favorited"}`
5. Get product 1 again → favorites count increased
6. Navigate to product 1 detail → favorite button count badge shows updated count

**Unfavorite a Product (Toggle Off)**
7. Favorite product 1 again: `POST /products/1/favorite` (second time)
8. Verify API returns `{"action": "unfavorited"}`
9. Get product 1 → favorites count decreased back
10. Toggle is idempotent: favorite-unfavorite-favorite cycle works correctly

**Favorite via UI Button**
11. Login as alice, navigate to product detail
12. Find favorite button (`ntx-method[method="favorite"]`) in shadow DOM
13. Read current count from `.method-btn-count`
14. Click the favorite button
15. Wait for API response
16. Verify count badge incremented by 1
17. Click again → verify count decremented by 1 (unfavorited)
18. Verify no page reload needed (live update)

**Favorite Without Auth**
19. Ensure anonymous (no token)
20. Attempt `POST /products/1/favorite` without auth → 401
21. Navigate to product detail as anonymous → favorite button may be disabled or hidden
22. Click favorite button as anonymous → no crash, appropriate error handling

**Multiple Users Favoriting**
23. Alice favorites product 1
24. Bob favorites product 1
25. Charlie favorites product 1
26. Get product 1 → favorites array/count should reflect all three
27. Navigate to product 1 detail → favorite count shows total

**Favorite Count Display**
28. Product with 0 favorites → count badge shows "0" or is hidden
29. Product with 1 favorite → count badge shows "1"
30. Favorite count is visible in list view (on each item card) — check `ntx-method` in list items

**Comment Like (Heart Button)**
31. Comment schema has a `like` method with heart icon
32. Like a comment via API `POST /products/{pid}/comments/{cid}/like`
33. Verify API returns `{"action": "liked"}`
34. Like same comment again → API returns `{"action": "unliked"}` (toggle)
35. Navigate to product detail → expand comments → comment's like count visible

**Comment Like via UI**
36. Navigate to product detail with comments
37. Find comment's `ntx-method[method="like"]` in nested shadow DOM
38. Click like button → verify count increments
39. Click again → verify count decrements (unlike toggle)

**Comment Reply**
40. Find comment's `ntx-method[method="reply"]` in nested shadow DOM
41. Enter reply text in the inline textarea
42. Submit reply → API `POST /products/{pid}/comments/{cid}/reply` with `{text: "..."}`
43. Verify new comment created with `parent_id` set to original comment's ID
44. Verify reply appears in comments list

**Cross-Product Favorites**
45. Favorite product 1 and product 2
46. Verify product 1's favorite count is independent from product 2's
47. Favorites on product 1 don't appear on product 2

**Favorites Page Integration**
48. Login as alice, favorite product 1
49. Navigate to `#@favorites`
50. Verify favorites page shows favorited products (ProductLike entries)
51. Verify `ntx-favorites` component renders with `ntx-list[model="ProductLike"]`
52. Unfavorite product 1 → refresh favorites page → product no longer listed

**Edge Cases**
53. Favorite non-existent product (ID 99999) → 404 or error
54. Favorite with expired token → 401
55. Favorite with empty request body → still succeeds (favorite takes no body params)
56. Favorite count survives page reload
57. Favorite count visible at all viewport sizes
58. Rapid toggle (5 quick clicks) → final state is deterministic (favorited or not)

---

## AGENT 5: `flow-social-chain.spec.js` — Full Social Interaction Chain

### Complete: Register → Create Product → Comment → Like → Verify All → Delete

This is the master integration test. It chains EVERYTHING together.

**Phase 1: Setup**
1. Register a fresh user: `POST /users/register` with unique email
2. Login as the new user
3. Verify authenticated state in topbar

**Phase 2: Create**
4. Create a new product: `{name: 'Social Chain Product', price: 55.00, description: 'Full flow test'}`
5. Verify product appears in list
6. Navigate to product detail → verify all fields

**Phase 3: Social Actions**
7. Add comment via `POST /products/{id}/comment`: `{comment: {name: 'First Comment', description: 'Testing the chain'}}`
8. Verify comment appears on the product
9. Add a second comment: `{comment: {name: 'Second Comment', description: 'Another test'}}`
10. Verify comment count is now 2
11. Favorite the product via `POST /products/{id}/favorite` (NOT "like" — Product has `favorite` method with star icon)
12. Verify favorites count is now 1
13. Navigate to `#@favorites` → product should appear (ProductLike entry)

**Phase 4: Cross-User Interaction**
14. Login as bob
15. Navigate to the social chain product
16. Bob adds a comment: `{comment: {name: 'Bobs Comment', description: 'Cross-user test'}}`
17. Verify comment count is now 3
18. Bob favorites the product via `POST /products/{id}/favorite`
19. Verify favorites count is now 2
20. Bob tries to edit the product → blocked (not owner)

**Phase 5: Verify Aggregate State**
21. Navigate to product detail
22. Verify total comments: 3 (2 from creator, 1 from bob)
23. Verify total favorites: 2 (1 from creator, 1 from bob)
24. Verify product name unchanged: "Social Chain Product"
25. Verify product owner is the original creator

**Phase 6: Update**
26. Login as original creator
27. Edit product name to "Updated Social Chain"
28. Save → verify name changed in display
29. Verify comments and likes still intact after update
30. Verify comment count and like count unchanged

**Phase 7: Cleanup & Final State**
31. Verify via API that all data is consistent:
    - `GET /products/{id}?depth=1` returns full product with comments and likes
    - Comment objects have correct user_owner values
    - Like objects have correct user_owner values
32. Verify via UI that everything renders correctly
33. Navigate to list → product shows in list with correct name

---

## AGENT 6: `flow-navigation-deep.spec.js` — Navigation & Routing Integration

### Complex Navigation Patterns

**List → Detail → Back → Detail Flow**
1. Load app → product list visible
2. Click first product → detail view, hash = `#Product/{id}`
3. Click back → list view, hash = `""` or `"#"`
4. Click second product → different detail, hash = `#Product/{id2}`
5. Verify different product data shown
6. Click back → list again

**Deep Link Navigation**
7. Navigate directly to `matrix.html#Product/1` → detail loads
8. Navigate directly to `matrix.html#Product/2` → different detail loads
9. Navigate directly to `matrix.html#@favorites` → favorites view
10. Navigate directly to invalid hash `matrix.html#Product/99999` → graceful handling

**Browser History Integration**
11. Navigate: list → product 1 → product 2
12. Press browser back → product 1 detail shown
13. Press browser back → list shown
14. Press browser forward → product 1 again
15. Press browser forward → product 2 again

**Hash Change Without Reload**
16. Set `window.location.hash = '#Product/1'` → router updates without page reload
17. Set `window.location.hash = ''` → returns to list
18. Rapid hash changes (1 → 2 → 3 → 1) → final state correct
19. Hash change during data loading → no race condition crash

**Navigation with Auth State Changes**
20. Browse as anonymous → list and details work (read is public)
21. Login → navigate to detail → edit button appears
22. Navigate to list and back to detail → edit button still visible
23. Logout → navigate to detail → edit button gone
24. Login as different user → edit button appears/disappears based on ownership

**Favorites Navigation**
25. Login, navigate to `#@favorites`
26. `ntx-favorites` component renders inside `ntx-router`
27. Favorites shows `ntx-list[model="ProductLike"]`
28. Click back from favorites → returns to list
29. Navigate favorites → product detail → back → favorites → back → list

**Profile Navigation**
30. Login, navigate to `#@profile`
31. Profile view renders (or graceful handling if not implemented)
32. Back button returns to previous view

**Concurrent Navigation Stress Test**
33. Navigate to detail, immediately navigate to another detail (don't wait for load)
34. Navigate to detail, immediately go back (before data loads)
35. 10 rapid hash changes → no crash, final state correct
36. Navigate during network slow-down (simulate with page.route throttle)

**Navigation State Consistency**
37. After navigation, the correct `ntx-item` is rendered inside `ntx-router`
38. After back, the `ntx-list` shows all items (not stale data)
39. URL hash always matches displayed content
40. Router title updates to match current view

---

## AGENT 7: `flow-permissions-matrix.spec.js` — Authorization Matrix

### Verify Every Permission Combination

**Anonymous User Permissions**
1. Can view product list (200 OK)
2. Can view product detail (200 OK)
3. Can view product schema (200 OK)
4. Cannot create product (401)
5. Cannot update product (401)
6. Cannot delete product (401)
7. Cannot add comment (401)
8. Cannot favorite product (401) — Product uses `favorite` method, not `like`
9. Cannot access `/auth/me` (401)
10. UI: no edit button on any product detail
11. UI: no delete button on any product detail
12. UI: no create button on product list
13. UI: signin link visible, user pill hidden

**Authenticated Non-Owner (bob viewing alice's product)**
14. Can view product list (200 OK)
15. Can view alice's product detail (200 OK)
16. Can create own product (200 OK)
17. Cannot update alice's product (403)
18. Cannot delete alice's product (403) — delete requires admin
19. Can add comment to alice's product (200 OK)
20. Can favorite alice's product (200 OK) — `POST /products/{id}/favorite`
21. UI: no edit button on alice's product
22. UI: no delete button on alice's product

**Authenticated Owner (alice viewing own product)**
23. Can update own product (200 OK)
24. Cannot delete own product (403) — delete requires admin role, not owner
25. Can add comment to own product (200 OK)
26. Can favorite own product (200 OK)
27. UI: edit button visible on own product
28. UI: no delete button (unless alice is admin)
29. UI: edit mode works — can modify and save

**Field-Level Access**
30. Price field has `access.edit: 'admin'` — non-admin in edit mode:
    - price may show as read-only or hidden in edit form
    - Attempting to update price via API as non-admin → behavior depends on backend enforcement
31. Protected fields (user_owner) not editable in UI edit mode
32. Protected fields automatically injected by backend on create (user_owner = JWT user)

**Method-Level Access**
33. Favorite method requires `authenticated` → anonymous gets 401
34. Comment method works for anyone (but user injection from JWT)
35. Comment like method requires `authenticated` → anonymous gets 401
35. Methods visible in UI only when user can invoke them

**Schema Access Rules Verification**
36. `GET /Product` schema.access.read.rule === "anyone"
37. `GET /Product` schema.access.create.rule === "authenticated"
38. `GET /Product` schema.access.update is OR(owner, role:admin)
39. `GET /Product` schema.access.delete.rule === "role" with roles: ["admin"]
40. Comment `$defs` has its own access rules
41. Frontend `Permissions.js` correctly interprets these rules

**Role Escalation Prevention**
42. Regular user cannot forge admin role via API (JWT is server-signed)
43. Modifying JWT payload client-side → 401 (signature mismatch)
44. Setting `role: 'admin'` in registration body → ignored (role assigned by backend)

---

## AGENT 8: `flow-error-resilience.spec.js` — Error Handling & Edge Cases

### Network Errors & Error Recovery

**API Error Responses**
1. `POST /products` without auth → 401, JSON body with error detail
2. `PUT /products/{id}` as non-owner → 403, JSON body with error detail
3. `DELETE /products/{id}` as non-admin → 403, JSON body with error detail
4. `POST /products` with empty body → 422 or 400 validation error
5. `POST /products` with invalid JSON → 400 or 422
6. `GET /products/99999` → 404 or null response
7. `POST /products` with missing required field (no name) → 422

**UI Error Handling**
8. Navigate to non-existent product (`#Product/99999`) → no crash, graceful state
9. Navigate to malformed hash (`#???`) → no crash
10. Navigate to empty model hash (`#Unknown/1`) → no crash
11. Page load with corrupted localStorage → no crash
12. Page load with network timeout on schema fetch → no crash (error logged)

**Validation Error Display**
13. Create product with empty name → error message visible (either inline or alert)
14. Edit product, clear name, save → validation prevents save or shows error
15. Create product with price=0 → validation error
16. Create product with negative price → validation error

**Concurrent/Race Condition Tests**
17. Start creating product, navigate away before response → no crash
18. Start editing, submit, navigate away before response → no crash or data corruption
19. Two rapid submissions of the same form → one succeeds, duplicate handled
20. Navigate to detail, schema not yet loaded → component waits or shows loading state

**Server Down Recovery**
21. Load app normally
22. (Simulate) Make API call that fails → error logged, UI shows error state
23. Retry or reload → app recovers when server is available

**XSS Prevention**
24. Create product with name `<img src=x onerror=alert(1)>` → rendered as text, not HTML
25. Create comment with description `<script>alert('xss')</script>` → rendered safely
26. Product name with `javascript:alert(1)` in any href → not clickable as JS

**Large Data Handling**
27. Product with 100+ comments → list renders with pagination/collapse
28. Product with 1000+ likes → count shows correct number
29. Product list with 50+ products → pagination works ("Load More")
30. Very long product name (200 chars) → doesn't break layout
31. Very long comment description → doesn't break layout

**Edge Data Types**
32. Product price with many decimal places (42.999999) → displays as reasonable format
33. Product price exactly 0.01 → displays as "$0.01"
34. Product price very large (999999.99) → displays correctly
35. Product with all optional fields empty → renders without error
36. Product with unicode name → renders correctly
37. Product with emoji in description → renders correctly

---

## AGENT 9: `flow-responsive-breakpoints.spec.js` — Cross-Viewport Integration

### Verify Full Flows Work at Every Viewport Size

**Mobile (360x640)**
1. Page loads, list visible
2. Click product → detail visible
3. Back button returns to list
4. Login → topbar shows user pill (may be compact)
5. Edit flow works on mobile
6. Comment flow works on mobile
7. All text readable (no overflow/truncation)
8. Logs panel opens and closes

**Tablet (768x1024)**
9. Page loads, list in appropriate grid
10. Click product → detail with medium display
11. Navigation works correctly
12. Login/logout flow works
13. Edit form usable (inputs not too small)

**Desktop (1280x720)**
14. Page loads, list in multi-column grid
15. Click product → detail with xl display
16. Full CRUD flow works
17. Comments and likes visible and functional
18. Logs panel doesn't overlap content

**Widescreen (1920x1080)**
19. Content has max-width (doesn't stretch to 1920px)
20. All features work as desktop
21. No horizontal scrollbar

**Viewport Resize During Use**
22. Start at desktop → navigate to detail → resize to mobile → still functional
23. Start at mobile → resize to desktop → layout adjusts
24. Edit mode at desktop → resize to mobile → form still usable
25. Logs panel open → resize → panel adjusts

**Display Mode Transitions**
26. At 360px: list items use xs or sm display
27. At 768px: list items use sm or md display
28. At 1200px: list items use md or lg display
29. Detail view always uses lg or xl display
30. Display modes match item's `data-display` attribute

---

## AGENT 10: `flow-data-integrity.spec.js` — Data Integrity & Consistency

### Verify Data Consistency Across UI and API

**Create and Verify Everywhere**
1. Create product via API → verify in list UI → verify in detail UI → verify via API GET
2. Product has consistent ID across all views
3. Product `$schema` URL is correct: `{API_URL}/Product`
4. Product `$id` URL is correct: `{API_URL}/products/{id}`
5. Product `user_owner` set to creator's user_id

**Update and Verify Everywhere**
6. Update product name → list shows new name → detail shows new name → API returns new name
7. Update product price → verify `$X.XX` format consistent in list and detail
8. Update doesn't change ID, user_owner, or creation metadata

**Comment and Verify Everywhere**
9. Add comment → product detail shows comment → API `?depth=1` includes comment
10. Comment has correct `$schema` and `$id` URLs
11. Comment belongs to correct product (FK relationship intact)
12. Comment user_owner matches the commenter's user_id

**Like and Verify Everywhere**
13. Like product → count in UI matches count from API
14. Like has correct `$schema` and `$id`
15. Like belongs to correct product

**Pagination Consistency**
16. List page 1 returns `{data: [...], meta: {total, limit, offset, has_more}}`
17. `meta.total` matches actual total count
18. `meta.has_more` is true when more pages exist, false otherwise
19. `meta.limit` matches requested limit
20. `meta.offset` increases correctly per page
21. All items across all pages have unique IDs
22. Loading all pages via "Load More" shows total count matching `meta.total`

**Schema Consistency**
23. `GET /Product` schema matches the actual data structure returned by `GET /products`
24. Every field in schema.properties has a corresponding field in entity data
25. Required fields in schema are always present in entity data
26. $defs schemas match their respective entity data structures
27. Schema methods match available API endpoints

**Orphan/Cascade Behavior (known bug B6)**
28. Delete a product → check if its comments become orphaned
29. Delete a comment → check if its likes become orphaned
30. Note: this documents the B6 bug behavior — tests should verify CURRENT behavior, flagging as known issue

**Concurrent Modifications**
31. Two users edit same product simultaneously (via API) → last write wins, no data corruption
32. User edits product while another user comments on it → both changes persist
33. Rapid create-update-delete cycle → final state consistent

---

## EXECUTION NOTES

- Each agent works on ONE spec file independently and in parallel
- All tests run against the LIVE server (Playwright auto-starts it)
- Tests use seed data (3+ products, 3 users)
- Tests that create data should use unique identifiers (timestamps, random strings) to avoid conflicts
- After writing tests, run: `cd /workspace/src/n3tx/static && npx playwright test --config=tests/e2e/playwright.config.js tests/e2e/{filename}.spec.js`
- Fix any failing tests before declaring done — a failing test means either the test is wrong or there's a real bug. Investigate which.
- If you discover a real bug, still write the test but document the expected behavior vs actual behavior in a comment
- Use `test.describe.serial()` for tests that depend on each other within a group (e.g., create then verify)
- DO NOT skip tests with `test.skip()` — either fix them or document the bug
- Think about EVERY edge case: empty strings, null values, very long strings, special characters, unicode, rapid clicks, concurrent actions, network errors, auth state changes
