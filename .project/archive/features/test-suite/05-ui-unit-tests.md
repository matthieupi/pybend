# 05 — UI Component Unit Tests (Playwright)

> **Scope**: Every visual element, button, input field, and component interaction in the browser — tested in isolation using Playwright against a live server.
> **Framework**: Playwright (`tests/e2e/*.spec.js`)
> **Goal**: Full coverage of every UI element's behavior, appearance, and edge cases. Every button must be clicked. Every input must be typed into. Every visual state must be verified.
> **Estimated test cases**: ~300+

---

## EXECUTION INSTRUCTIONS FOR SUBAGENTS

You are writing Playwright E2E tests for a schema-driven web application. The app uses **Web Components with Shadow DOM** — every component's internals are inside `shadowRoot`. You MUST use `element.evaluate()` or `element.shadowRoot.querySelector()` patterns to access Shadow DOM content.

### Critical Technical Context

1. **App URL**: `/matrix.html`
2. **Base URL**: `http://localhost:5000` (configured in `playwright.config.js`)
3. **Shadow DOM**: All N3TX components (`ntx-list`, `ntx-item`, `ntx-topbar`, `ntx-router`, `ntx-method`, `ntx-logs`, `ntx-favorites`) use Shadow DOM. You CANNOT use normal CSS selectors to reach into them. You MUST use `.evaluate()` to access `el.shadowRoot`.
4. **Auth**: Use the helpers from `./fixtures/auth.js`:
   ```js
   import { loginAs, logout, getToken, USERS } from './fixtures/auth.js';
   ```
   - `loginAs(page, 'alice')` — logs in and reloads
   - `logout(page)` — clears token and reloads
   - `getToken(page.request, email, password)` — gets JWT token for API calls
   - Seed users: `alice`, `bob`, `charlie` (all role `user`, passwords `alice123`, `bob123`, `charlie123`)
5. **Wait pattern**: After page load, use `await page.waitForLoadState('networkidle')` then `await page.waitForTimeout(2000)` for Shadow DOM rendering
6. **Schema endpoints** are public (no auth needed): `GET /Product`, `GET /Comment`, etc.
7. **Data endpoints** require auth: `GET /products`, `POST /products`, etc.
8. **The existing tests are in** `src/n3tx/static/tests/e2e/` — read them first to understand patterns and avoid duplication

### File Organization

Each test file below maps to a single `.spec.js` file. Tests within a file run sequentially (Playwright config: `fullyParallel: false`, `workers: 1`). The server auto-starts via the `webServer` config in `playwright.config.js`.

---

## AGENT 1: `ntx-topbar-unit.spec.js` — Topbar Component

### Component Structure (Shadow DOM)
- `.topbar` container
- `.topbar-title` — app title link
- `.nav-links` — navigation area
- `.signin-link` — shown when anonymous
- `.user-pill` — shown when authenticated (contains `.user-avatar`, `.user-name`)
- `.user-dropdown` — dropdown menu (`.dropdown-email`, `.dropdown-role`, `.theme-toggle`, `.logout-btn`, `a[href="#@profile"]`, `a[href="#@favorites"]`)

### Tests to Write

**Anonymous State (no JWT token)**
1. Topbar renders and is visible
2. `.signin-link` is present and visible
3. `.signin-link` text contains "Sign in"
4. `.user-pill` is NOT present
5. `.user-dropdown` is NOT present or has no authenticated content
6. Favorites link (`a[href="#@favorites"]`) is NOT present
7. Profile link (`a[href="#@profile"]`) is NOT present
8. App title link exists and links to root (hash `""` or `"#"`)
9. Clicking app title navigates to root when on a detail page

**Authenticated State (after loginAs)**
10. `.user-pill` is visible
11. `.user-avatar` shows initial letter of user name (e.g., "A" for Alice)
12. `.user-name` shows the user's display name
13. `.signin-link` is NOT present
14. `.user-dropdown` contains email matching logged-in user
15. `.user-dropdown` contains role badge
16. `.theme-toggle` button exists in dropdown
17. `.logout-btn` exists in dropdown
18. Favorites link exists in dropdown
19. Profile link exists in dropdown

**User Pill Interaction**
20. Clicking user pill opens dropdown (toggles `.open` or visible state)
21. Clicking user pill again closes dropdown
22. Clicking outside dropdown closes it (if applicable)
23. Dropdown shows correct email for alice (`alice@example.com`)
24. Dropdown shows correct email for bob when logged in as bob

**Logout Flow**
25. Clicking logout button removes JWT from localStorage
26. After logout, topbar reverts to anonymous state (signin link appears)
27. After logout, page reloads and product list still loads (read is public)

**Theme Toggle**
28. Clicking theme toggle changes `document.documentElement.dataset.theme`
29. Theme toggle has visual indicator of current theme (icon or text)
30. Theme persists in `localStorage['ntx-theme']` after toggle

**Edge Cases**
31. Topbar renders correctly at 360px mobile viewport
32. Topbar renders correctly at 1920px widescreen viewport
33. Topbar handles corrupted/expired JWT gracefully (no crash, reverts to anonymous)
34. Topbar handles missing user data in JWT payload
35. Multiple rapid login/logout cycles don't crash the topbar
36. Title link works after navigation to detail and back

---

## AGENT 2: `ntx-list-unit.spec.js` — List Component

### Component Structure (Shadow DOM)
- `.list-header` with `h1` (model name) and `.list-count` badge
- `.list-actions` — action buttons area (create button for authenticated users)
- `.list-grid` — container for `ntx-item` elements
- Optional "Load More" button when pagination has more items

### Tests to Write

**Basic Rendering**
1. `ntx-list` element is visible on page load
2. `.list-header h1` contains "Product"
3. `.list-count` shows total product count
4. `.list-grid` contains at least 3 `ntx-item` elements (seed data)
5. Each `ntx-item` in the grid has a `display` attribute set

**Item Display Content**
6. First item shows product name in a visible element
7. First item shows price with `$` prefix (currency widget)
8. Items in list view use compact display mode (xs, sm, or md depending on viewport)
9. Each item has a clickable area (`.card` class in shadow DOM)

**Create Button (Authenticated)**
10. Anonymous user does NOT see create/add button
11. Authenticated user sees create/add button
12. Create button has correct icon or label
13. Clicking create button opens a create form or modal
14. Create form has input fields matching Product schema (name, price, description)
15. Create form name input has `minlength="1"` and `maxlength="200"` attributes
16. Create form price input has `type="number"` and min constraint
17. Submitting create form with valid data creates new product (verify via API)
18. After successful create, new item appears in the list without full page reload
19. Submitting create form with empty name fails validation (required field)
20. Submitting create form with price=0 or negative fails validation

**Pagination**
21. If more than 20 products exist, "Load More" button appears
22. Clicking "Load More" fetches next page and appends items
23. After all items loaded, "Load More" button disappears
24. List count badge updates as more items are loaded

**Click-to-Navigate**
25. Clicking an item navigates to detail view (URL hash changes to `#Product/{id}`)
26. Click triggers hash change without full page reload
27. After click, `ntx-router` shows the detail view

**Empty State**
28. If no products exist, list shows empty state or zero count
29. Empty list still renders the header and create button (if authenticated)

**Edge Cases**
30. List handles server returning empty array gracefully
31. List handles network error on initial fetch (logs error, shows empty)
32. Rapid scroll/pagination doesn't duplicate items
33. List renders at each breakpoint: 360px, 480px, 768px, 1024px, 1200px, 1920px
34. Count badge matches actual number of rendered items
35. Items have consistent display modes within the same list

---

## AGENT 3: `ntx-item-unit.spec.js` — Item Component (All Display Sizes)

### Component Structure (Shadow DOM)
- `.card` wrapper with `data-display` attribute (xs/sm/md/lg/xl)
- Display mode methods: `xs()` pill, `sm()` card, `md()` detail card, `lg()`/`xl()` full detail
- `.edit-btn` and `.delete-btn` (permission-gated)
- `.save-btn` and `.cancel-btn` (in edit mode)
- Form inputs generated by `Formidable` in edit mode

### Tests to Write

**XS (Pill) Display**
1. At xs display, card shows as compact pill
2. Pill contains product name text
3. Pill has small/minimal styling (verify border-radius: 999px in skeleton)

**SM (Small Card) Display**
4. At sm display, card shows avatar area and name
5. SM card contains name in a visible element

**MD (Medium Detail) Display**
6. At md display, card shows name, price, description
7. Price displays with `$` prefix (currency widget)
8. Description shows as text block
9. Field order matches schema `ui.field_order`: name, price, description, comments
10. Groups render as `<fieldset>` with legend labels (e.g., "main", "Social")

**LG/XL (Full Detail) Display**
11. XL display shows all fields including comments list
12. Comments section shows as `.list-field` with count badge
13. Method buttons (comment, like) are visible in detail view
14. `ntx-method` elements present for exposed methods
15. All visible fields are rendered (hidden fields like `id`, `image` are NOT shown)

**Edit Mode (Owner)**
16. Login as alice, navigate to alice's product — edit button visible
17. Click edit button — mode changes, form inputs appear
18. Name input pre-filled with current name value
19. Price input pre-filled with current price value
20. Description textarea pre-filled with current description
21. Protected fields (user_owner) do NOT have edit inputs
22. Save button visible in edit mode
23. Cancel button visible in edit mode
24. Cancel button reverts to display mode without saving
25. Modify name input and click save — API PATCH/PUT sent
26. After save, display mode shows updated name
27. Modify price and save — updated price displays with `$` prefix

**Edit Mode Validation**
28. Clear name field (make empty) — field shows validation error or submit blocked
29. Set price to 0 — validation error (exclusiveMinimum > 0)
30. Set price to negative — validation error
31. Set name to 201+ characters — validation error (maxLength: 200)
32. Save with invalid data — no API call made (client-side validation blocks)

**Delete Flow**
33. Admin user sees delete button (set up admin role or test with correct user)
34. Non-owner non-admin does NOT see delete button
35. Click delete button — confirmation dialog or immediate delete
36. After delete, item removed from list (navigate back, verify item gone)
37. Delete via API returns success status

**Permission-Gated UI**
38. Anonymous user — no edit button, no delete button
39. Non-owner authenticated user — no edit button (unless admin)
40. Owner — edit button visible, delete button may or may not be visible (depends on access rules)
41. Field-level access: price has `access.edit: 'admin'` — non-admin in edit mode sees price as read-only or hidden

**Display/Edit Mode Toggle**
42. Double-click or edit button toggles to edit mode
43. Pressing Escape in edit mode cancels (if implemented)
44. Switching between display and edit preserves data integrity
45. Multiple rapid edit/cancel toggles don't corrupt state

**Edge Cases**
46. Item with empty description renders without error
47. Item with very long name (200 chars) renders without overflow issues
48. Item with price 0.01 displays as `$0.01`
49. Item with price 9999999.99 displays correctly
50. Item with no comments shows comments count as 0
51. Item with null fields renders gracefully
52. Item handles $schema and $id metadata correctly (injected by backend)

---

## AGENT 4: `ntx-method-unit.spec.js` — Method Button Component

### Component Structure (Shadow DOM)
- `.method-btn` — the clickable button
- `.method-btn-icon` — SVG icon (star for favorite, heart for like)
- `.method-btn-label` — text label
- `.method-btn-count` — count badge (for count)
- **Product methods**: `comment` (inline textarea layout), `favorite` (button layout, star icon, count from `favorites` field)
- **Comment methods**: `like` (button layout, heart icon, count from `likes` field), `reply` (inline textarea layout)
- **IMPORTANT**: Product does NOT have a `like` method — it has `favorite`. Comment has `like`.

### Tests to Write

**Product Favorite Button**
1. `ntx-method[method="favorite"]` element exists on product detail
2. Favorite button has star icon (`.method-btn-icon` contains star SVG)
3. Favorite button shows count badge with current favorites count
4. Favorite button is clickable for authenticated users
5. Click favorite button — API call `POST /products/{id}/favorite` sent
6. After clicking favorite, count badge increments by 1 (toggle: "favorited")
7. Click again — count decrements by 1 (toggle: "unfavorited")
8. Favorite button without auth — click should fail gracefully (no crash)
9. Favorite button count shows 0 for product with no favorites
10. Favorite button count shows correct number for product with existing favorites
11. Rapidly clicking favorite multiple times — toggle behavior consistent

**Product Comment Method (Inline Form)**
12. `ntx-method[method="comment"]` element exists on product detail
13. Comment method has inline layout (textarea widget, not just a button)
14. Comment form has textarea placeholder "Add your comment..."
15. Comment form has "Post" button label
16. Submitting comment with valid data — API call `POST /products/{id}/comment` sent
17. After submitting comment, comments list updates with new comment
18. Submitting comment with empty text — validation error or blocked
19. Comment method requires authentication — anonymous user cannot submit

**Comment Like Button (Nested in Product Detail)**
20. On product detail, expand comments, find a comment's `ntx-method[method="like"]`
21. Comment like button has heart icon
22. Comment like button shows count badge
23. Click like — API call `POST /products/{pid}/comments/{cid}/like` sent
24. Toggle behavior: first click "liked", second click "unliked"

**Comment Reply Method (Nested)**
25. On product detail, expand comments, find `ntx-method[method="reply"]`
26. Reply method has inline layout with textarea
27. Reply placeholder says "Write a reply..."
28. Reply button label says "Reply"
29. Submitting reply creates new comment with `parent_id` set to parent comment's ID

**Method Schema Verification**
30. Schema `methods.favorite` has `scope: 'instancemethod'`, `ui.layout: 'button'`, `ui.icon: 'star'`, `ui.count_field: 'favorites'`
31. Schema `methods.comment` has parameters including `comment` object with its own schema
32. Schema `methods.favorite` has `access.rule: 'authenticated'`
33. Comment $defs schema has `methods.like` with `ui.icon: 'heart'`, `ui.count_field: 'likes'`
34. Comment $defs schema has `methods.reply` with `ui.layout: 'inline'`

**Edge Cases**
35. Method button renders at all display sizes (xs, sm, md, lg, xl)
36. Method button disabled state when not authenticated
37. Method handles API error response gracefully (show error, don't crash)
38. Method handles network timeout gracefully
39. Method button works after page navigation (detail → list → detail)
40. Favorite toggle is idempotent (n rapid clicks → final state is either favorited or not)

---

## AGENT 5: `ntx-router-unit.spec.js` — Router/Navigation Component

### Component Structure (Shadow DOM)
- `.router-content` — main content area (renders selected view)
- `.router-title` — title showing current model/view name
- `.back-btn` — back navigation button (only in detail/sub views)
- Slot fallback — shows `ntx-list` when no hash route active

### Tests to Write

**Root State (No Hash)**
1. At root (`matrix.html` or `matrix.html#`), router shows slot content (ntx-list)
2. Back button is NOT visible at root
3. Router title is empty or shows default at root
4. `ntx-list` is rendered inside router's slot

**Detail Navigation**
5. Navigate to `#Product/1` — router shows ntx-item with product detail
6. Router title shows "Product" for product detail
7. Back button IS visible in detail view
8. Detail item uses xl display mode
9. Detail item shows all fields (name, price, description, comments)

**Back Navigation**
10. Click back button — returns to previous view (list)
11. After back, URL hash is empty
12. After back, ntx-list is visible again with all items
13. Multiple forward/back navigations maintain correct state

**Hash-Based Routing**
14. Direct URL `matrix.html#Product/1` loads detail view directly
15. Direct URL `matrix.html#Product/999` (non-existent) handles gracefully
16. Hash change via `window.location.hash = '#Product/2'` triggers navigation
17. Programmatic hash change to `''` returns to root/list view

**Special Routes**
18. `#@favorites` navigates to favorites view (ntx-favorites component)
19. `#@profile` navigates to profile view
20. Unknown hash routes (e.g., `#@unknown`) don't crash the router

**Navigation History**
21. Browser back button works after hash navigation
22. Browser forward button works after going back
23. History stack maintains correct order after multiple navigations

**Edge Cases**
24. Rapid sequential hash changes (Product/1 → Product/2 → Product/3) don't crash
25. Navigate to detail while data is still loading — no race condition
26. Router handles missing schema for unknown model name
27. Router renders correctly at mobile viewport (360px)
28. Router renders correctly at desktop viewport (1280px)
29. Navigating away and back to same item preserves its state

---

## AGENT 6: `ntx-logs-unit.spec.js` — Logs Panel Component

### Component Structure (Shadow DOM)
- `.toggle` button with `.badge` count
- `.panel` (opens/closes with `.open` class)
- `.panel-header` with `.panel-title` and `.close-btn`
- `.toolbar` with `.filters` (filter buttons by level) and `.clear-btn`
- `.log-list` with `.entry` elements
- Each entry: `.level-dot`, `.level`, `.time`, `.message`, optional `.json-node`

### Tests to Write

**Toggle Behavior**
1. Toggle button visible on page load
2. Panel starts closed (no `.open` class)
3. Click toggle — panel opens (`.open` class added)
4. Click toggle again — panel closes
5. Click close button — panel closes
6. Badge shows log count number

**Log Entries**
7. After page load, log entries exist (schema fetch, component init logged)
8. Each entry has `.level-dot`, `.level`, `.time` elements
9. Entry level classes are valid: `level-error`, `level-warn`, `level-info`, `level-event`, `level-debug`, `level-dev`
10. Entries are added in chronological order (newest at bottom or top)
11. Entry message text is non-empty

**Filtering**
12. Filter buttons exist for all 6 levels: error, warn, info, event, debug, dev
13. Clicking a filter button activates it (`.active` class)
14. Active filter hides non-matching entries (`display: none`)
15. Clicking active filter again deactivates it (shows all entries)
16. Only one filter active at a time (clicking different filter switches)
17. Filter maintains state when panel is closed and reopened

**Clear**
18. Clear button removes all entries from log list
19. After clear, badge count resets to 0
20. New logs still appear after clear
21. Clear button works when filter is active

**JSON Expansion**
22. Entries with JSON data have `.json-node` elements
23. JSON nodes start collapsed (`.collapsed` class)
24. Clicking JSON toggle expands the node (removes `.collapsed`)
25. Clicking again collapses it
26. Expanded JSON shows formatted key-value content

**Badge Counter**
27. Badge shows 0 when no logs
28. Badge increments as new logs arrive
29. Badge resets to 0 after clear
30. Badge count matches total entries (not filtered count)

**Edge Cases**
31. Panel renders correctly at mobile viewport
32. Panel with 1000+ entries doesn't freeze the page
33. Entries with very long messages don't break layout
34. Entries with special characters in messages render safely (no XSS)
35. Opening panel during active network requests shows real-time logs

---

## AGENT 7: `form-rendering-unit.spec.js` — Form Generator Visual Tests

### Tests to Write (in-browser via Playwright, verify rendered HTML)

**Field Type Rendering**
1. String field renders as `<input type="text">` in edit mode
2. Number field renders as `<input type="number">` in edit mode
3. Boolean field renders as `<input type="checkbox">` in edit mode
4. Textarea widget renders as `<textarea>` in edit mode
5. Currency widget renders with `$` prefix in display mode
6. Currency widget renders as number input in edit mode

**Field Order**
7. Fields render in `ui.field_order` sequence: name → price → description → comments
8. Fields not in `field_order` are appended at end
9. Hidden fields (id, image, FK fields ending in `_id`) are NOT rendered

**Groups/Fieldsets**
10. Fields with `ui.groups` render inside `<fieldset>` elements
11. Each fieldset has a `<legend>` with the group name
12. Ungrouped fields appear after grouped fields
13. Group "main" contains name, description, price
14. Group "Social" contains comments

**Validation Attributes**
15. Required fields have `required` attribute on input
16. Name input has `minlength="1"` and `maxlength="200"`
17. Price input has `min` attribute reflecting `exclusiveMinimum`
18. Placeholder text from `ui.placeholder` appears on input

**Display Mode Rendering**
19. In display mode, string values show as plain text (not inputs)
20. In display mode, currency shows as `$29.99` format
21. In display mode, textarea shows as `.text-block` div
22. In display mode, boolean shows as visual indicator (checkbox or badge)
23. In display mode, null/undefined values show as empty string

**Protected Fields**
24. Protected fields (ui.protected=true) are hidden in edit mode
25. Protected fields may still show in display mode (read-only display)
26. `user_owner` field is protected and not editable

**List Fields (Array/Ref)**
27. Comments array renders as `.list-field` with count badge
28. Count badge shows correct number of items
29. First 2 items are visible, rest collapsed with "Show N more" toggle
30. Clicking "Show N more" expands all items
31. Each list item rendered as `ntx-item` sub-component with xs display

**Edge Cases**
32. Form handles schema with no `ui` key (uses defaults)
33. Form handles schema with no `field_order` (renders all fields in schema order)
34. Form handles empty `properties` object
35. Form handles field with `type: 'selfref'` (shows parent reference)
36. Form handles field with `type: '$ref'` (shows reference display)
37. Very long field labels don't break layout
38. Input with extremely long value doesn't overflow container
39. Number input rejects non-numeric text entry
40. Checkbox toggles correctly on click in edit mode

---

## AGENT 8: `css-and-theming-unit.spec.js` — Visual/CSS/Theme Tests

### Tests to Write

**CSS Variable Resolution**
1. `--surface-0` through `--surface-2` all resolve to non-empty values
2. `--text-0` through `--text-2` all resolve to non-empty values
3. `--accent` resolves to a color value
4. `--border` resolves to a color value
5. No CSS variable contains `var(` in its computed value (broken reference)
6. `--radius` variables resolve (for border-radius)
7. `--spacing-*` variables resolve (if defined)

**Dark Theme**
8. With `ntx-theme=dark`, `--surface-0` is a dark color (not white)
9. With `ntx-theme=dark`, `--text-0` is a light color (for contrast)
10. Dark theme `--surface-0` differs from light theme `--surface-0`

**Light Theme**
11. With `ntx-theme=light`, `--surface-0` is a light color (not black)
12. With `ntx-theme=light`, `--text-0` is a dark color (for contrast)
13. Light theme screenshot differs from dark theme screenshot

**Font & Typography**
14. Body font-family includes sans-serif (Inter, system-ui, or fallback)
15. Headings (h1, h2) use expected sizing
16. Text is readable (sufficient contrast between text and background)

**Component-Level Styles**
17. `ntx-topbar` has fixed/sticky positioning at top
18. `ntx-item .card` has border-radius and border styling
19. `ntx-item .card` has hover state (cursor pointer in list view)
20. `ntx-method .method-btn` has button styling (background, padding, border-radius)
21. `ntx-logs .panel` has slide-in animation or transition

**Responsive Breakpoints**
22. At 360px: items render in single column
23. At 480px: items render in appropriate grid
24. At 768px: items render in 2-3 column grid
25. At 1024px: items render in multi-column grid
26. At 1200px: items render in wider grid
27. At 1920px: items render with max-width constraint

**No Visual Regressions**
28. Screenshot at 1280x720 dark theme (list view) — non-trivial image
29. Screenshot at 1280x720 light theme (list view) — non-trivial image
30. Screenshot at 1280x720 detail view — non-trivial image
31. Screenshot at 360x640 mobile list view — non-trivial image
32. Dark and light screenshots are NOT byte-identical

**Edge Cases**
33. Theme change doesn't flash unstyled content (FOUC)
34. Theme applied immediately from localStorage on page load (before DOMContentLoaded)
35. CSS loads without 404 errors
36. No unstyled elements visible during initial render
37. Viewport resize doesn't cause layout shift or overflow

---

## AGENT 9: `accessibility-unit.spec.js` — Accessibility & Keyboard Tests

### Tests to Write

**Keyboard Navigation**
1. Tab key moves focus through interactive elements (buttons, inputs, links)
2. Enter key activates focused button
3. Escape key closes open dropdown (topbar user dropdown)
4. Escape key cancels edit mode (if implemented)
5. Tab order follows logical reading order (topbar → list → items)

**ARIA & Semantics**
6. Buttons have accessible labels (text content or aria-label)
7. Form inputs have associated labels or aria-label
8. Required fields have `aria-required="true"` or `required` attribute
9. List items have role or semantic markup for screen readers
10. Navigation links have descriptive text

**Focus Management**
11. After opening edit mode, first input receives focus
12. After closing edit mode, focus returns to edit button
13. After navigation, focus moves to the new view content
14. Modal/panel trap focus when open (if applicable)

**Color & Contrast**
15. Text color has sufficient contrast ratio against background (both themes)
16. Interactive elements have visible focus indicators
17. Error states use more than just color (icon or text)

**Screen Reader**
18. Page has a main landmark
19. Navigation is identifiable
20. Dynamic content changes are announced (aria-live if applicable)

**Edge Cases**
21. Keyboard-only navigation can complete full create flow
22. Keyboard-only navigation can complete full edit flow
23. All buttons reachable via keyboard (no focus trap in shadow DOM)
24. No elements with tabindex > 0 (anti-pattern)

---

## EXECUTION NOTES

- Each agent works on ONE spec file independently and in parallel
- Tests MUST pass against the live server (Playwright starts it automatically)
- Tests use seed data (3+ products, users alice/bob/charlie)
- After writing tests, run them with: `cd /workspace/src/n3tx/static && npx playwright test --config=tests/e2e/playwright.config.js tests/e2e/{filename}.spec.js`
- Fix any failing tests before declaring done
- Each test should be self-contained and not depend on other test files' side effects
- Use `test.describe()` blocks to group related tests
- Use `test.beforeEach()` for common setup (page navigation, login)
- Avoid hardcoded IDs where possible — query for first available item instead
