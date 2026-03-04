# Backend Integration Test Plan — N3TX Framework

> **Scope**: Every API endpoint, cross-module workflow, and authorization scenario.
> **Framework**: pytest + httpx (async) or requests (sync), FastAPI TestClient
> **Estimated test cases**: ~160+

---

## 1. SCHEMA ENDPOINTS

### 1.1 Schema Retrieval (Public)

- **GET /Product** — 200 OK, full JSON Schema with `$schema`, `$id`, `$defs`, `properties`, `methods`, `ui`, `access`, `__tablename__`, `__name__`
  - Verify: `$schema` = `http://localhost:5000/Schema`, `$id` = `http://localhost:5000/Product`
  - Verify: `properties` includes `name`, `price`, `description`, `comments`, `favorites`, `image`, `id`
  - Verify: `comments` and `favorites` fields marked as ListRef
  - Verify: `id`, `image` marked with `ui.display=false`
  - Verify: `access` contains `create`, `read`, `update`, `delete` rules serialized to JSON
  - Verify: `methods` contains `comment`, `favorite` with route, methods, parameters, returns, access
  - Verify: `$defs` contains `Comment`, `Like` schemas with their own `$id`, `methods`, `access`, `ui`
  - Auth: Not required

- **GET /Comment** — 200 OK
  - Verify: `access` rules (read: ANYONE, create: AUTHENTICATED, update: OWNER | ROLE('admin'), delete: OWNER | ROLE('admin'))
  - Verify: `parent_id` field marked as `"type": "selfref"`
  - Verify: `likes` field as ListRef

- **GET /Like** — 200 OK
  - Verify: Protected fields (`user`) marked with `ui.protected=true`

- **GET /User** — 200 OK
  - Verify: `password_hash` field hidden (not in properties)
  - Verify: Methods include `login`, `register` with ANYONE access
  - Verify: `role` field defaults to 'user'

- **GET /{ClassName}?scaffold=component** — 200 OK with text/plain response
  - Invalid scaffold: 400 Bad Request

---

## 2. AUTHENTICATION & LOGIN FLOW

### 2.1 User Registration

- **POST /users/register** — `{"name": "newuser", "email": "newuser@test.com", "password": "testpass123"}`
  - Expected: 201 Created, response has `token` + `user` object
  - Verify: Token is valid JWT with `user_id`, `email`, `role`, `exp`, `iat`
  - Verify: `password_hash` not in response
  - Verify: `role` defaults to `"user"`

- **POST /users/register — duplicate email** — 409 Conflict

- **POST /users/register — invalid email** — 422 Unprocessable Entity

- **POST /users/register — missing fields** — 422 Unprocessable Entity

### 2.2 User Login

- **POST /users/login** — `{"email": "alice@example.com", "password": "alice123"}` — 200 OK with `token`
  - Verify: Token decodes to correct user_id, email, role

- **POST /users/login — invalid password** — 401 Unauthorized

- **POST /users/login — nonexistent email** — 401 Unauthorized

### 2.3 GET /auth/me

- **GET /auth/me (authenticated)** — 200 OK with user identity
- **GET /auth/me (no token)** — 401 Unauthorized
- **GET /auth/me (invalid/expired token)** — 401 Unauthorized

---

## 3. FULL CRUD LIFECYCLE: PRODUCTS

### 3.1 Create Product (POST /products)

- **POST /products — authenticated** — `{"name": "Widget", "price": 99.99, "description": "Great"}` — 201 Created
  - Verify: `$schema`, `$id`, auto-generated `id`, default `image`, `comments=[]`, `favorites=[]`

- **POST /products — unauthenticated** — 403 Forbidden

- **POST /products — missing required field (name)** — 422 Unprocessable Entity

- **POST /products — invalid price (negative)** — 422 (Field constraint `gt=0`)

- **POST /products — name exceeds max_length** — 422

### 3.2 Read Product (GET /products/{id})

- **GET /products/1** — 200 OK
  - Verify: `comments` is array of URLs, `favorites` is array of URLs

- **GET /products/1?populate=comments** — 200 OK with comments as full objects

- **GET /products/1?populate=comments&depth=2** — 200 OK, Comments with Likes populated

- **GET /products/999** — 404 Not Found

### 3.3 List Products (GET /products)

- **GET /products (no pagination)** — 200 OK, `{"data": [...], "meta": {"total", "limit", "offset", "has_more"}}`

- **GET /products?limit=2&offset=0** — `has_more=true` when 0+2 < total

- **GET /products?limit=10&offset=0** — `has_more=false` if all fit

- **GET /products?limit=2&offset=4** — last page, `has_more=false`

- **GET /products?offset=10** (beyond total) — `data: []`, `has_more: false`

- **GET /products?limit=0** — 422 (validation: `ge=1`)

- **GET /products?limit=101** — 422 (validation: `le=100`)

- **GET /products?limit=20&offset=-1** — 422 (validation: `ge=0`)

- **GET /products?populate=comments&limit=2** — paginated + eager-loaded

### 3.4 Update Product (PUT /products/{id})

- **PUT /products/1** — `{"name": "Updated Widget"}` — 200 OK

- **PUT /products/1 — unauthenticated** — 403 Forbidden

- **PUT /products/1 — owner vs non-owner** — OWNER check, 403 for non-owner

- **PUT /products/1 — partial update** — only changed fields updated

- **PUT /products/999** — 404 Not Found

- **PUT /products/1 — invalid data** — 422

### 3.5 Delete Product (DELETE /products/{id})

- **DELETE /products/1 (admin)** — 200 OK, subsequent GET → 404

- **DELETE /products/1 (regular user)** — 403 Forbidden

- **DELETE /products/999** — 404 Not Found

---

## 4. FULL CRUD LIFECYCLE: COMMENTS (NESTED UNDER PRODUCTS)

### 4.1 Create Comment

- **POST /products/1/comments (authenticated)** — 201 Created
  - Verify: `user_owner` auto-injected from JWT (not from body)
  - Verify: `product_id` FK set, `parent_id` is null

- **POST /products/1/comments (unauthenticated)** — 403 Forbidden

### 4.2 Read Comment

- **GET /products/1/comments/1 (public)** — 200 OK with `$schema`, `$id`, `user_owner`, `parent_id`, `likes`

- **GET /products/1/comments/1?populate=likes** — 200 OK with likes populated

- **GET /products/1/comments/999** — 404 Not Found

### 4.3 List Comments

- **GET /products/1/comments (public)** — 200 OK, only comments for product_id=1

- **GET /products/1/comments?limit=2** — paginated

- **GET /products/999/comments** — 200 OK, empty data (no comments)

### 4.4 Update Comment

- **PUT /products/1/comments/1 (owner)** — 200 OK, `user_owner` NOT updated (protected field stripped)

- **PUT /products/1/comments/1 (non-owner, non-admin)** — 403 Forbidden

- **PUT /products/1/comments/1 (admin)** — 200 OK

### 4.5 Delete Comment

- **DELETE /products/1/comments/1 (owner)** — 200 OK

- **DELETE /products/1/comments/1 (non-owner, non-admin)** — 403 Forbidden

---

## 5. COLLECTION ROUTES (JOIN MODELS)

- **GET /comments** — all comments across all products, with pagination
- **GET /likes** — all likes across all products
- **GET /commentlikes** — all comment likes (if registered)

---

## 6. CUSTOM METHODS WITH @expose_route

### 6.1 Product.comment()

- **POST /products/{id}/comment** — `{"comment": {"name": "Nice!", "description": "Love this"}}` — 200 OK
  - Verify: `user: User` auto-resolved from JWT
  - Verify: Comment's `user_owner` set to authenticated user's ID

- **POST /products/1/comment (unauthenticated)** — 403 Forbidden

- **POST /products/1/comment — invalid data** — 422

### 6.2 Product.favorite()

- **POST /products/{id}/favorite (first call)** — 200 OK, `{"action": "favorited"}`

- **POST /products/{id}/favorite (second call, same user)** — 200 OK, `{"action": "unfavorited"}`

- **POST /products/1/favorite (unauthenticated)** — 403 Forbidden

### 6.3 Comment.like()

- **POST /products/{pid}/comments/{cid}/like** — 200 OK, `{"action": "liked"}` or `{"action": "unliked"}`

- **POST /products/1/comments/1/like (unauthenticated)** — 403 Forbidden

### 6.4 Comment.reply()

- **POST /products/{pid}/comments/{cid}/reply** — `{"text": "Great point!"}` — 200 OK
  - Verify: Created comment has `parent_id` = comment_id
  - Verify: `user_owner` auto-injected from JWT

- **POST /products/1/comments/1/reply (unauthenticated)** — 403 Forbidden

---

## 7. AUTHORIZATION & ACCESS CONTROL

### 7.1 ANYONE Rule
- GET /Product (schema) — no token needed, 200 OK
- GET /products/1 (Comment read: ANYONE) — no token, 200 OK

### 7.2 AUTHENTICATED Rule
- POST /products — no token → 403; with token → 201
- POST /products/1/comments — no token → 403; with token → 201

### 7.3 OWNER Rule
- PUT /products/1/comments/1 — owner → 200, non-owner → 403, admin → 200
- Owner field resolution: `__owner_field__ = 'user_owner'`
- FK href as owner: extract trailing ID from `"http://.../users/3"` and compare

### 7.4 ROLE Rule
- DELETE /products/1 — role='user' → 403, role='admin' → 200
- Multiple roles: ROLE('admin', 'moderator')

### 7.5 Composite Rules: OR (|)
- OWNER | ROLE('admin') — owner can update, non-owner admin can update, non-owner non-admin cannot

### 7.6 Composite Rules: AND (&)
- OWNER & Where(status='draft') — only owner of draft can update

### 7.7 Composite Rules: NOT (~)
- ~ROLE('banned') — banned users denied, others allowed

### 7.8 Where Rule
- Where(status='published') — only published resources accessible
- Where(price__lt=100) — price filter

### 7.9 SQL Pushdown Authorization
- GET /products?limit=10 with OWNER rule on list → only current user's products returned
- Composite rule SQL filter: OWNER | ROLE('admin') → combined WHERE

### 7.10 Protected Fields
- Comment.user_owner: backend auto-injects on create (ignores body), strips on update
- Like.user: same behavior
- Schema: marked with `ui.protected=true`

---

## 8. FK HYDRATION & COLLECTION REFERENCES

### 8.1 FK Ref Fields (Single FK)
- Comment.user_owner: stored as integer, API response as href `"http://.../users/1"`

### 8.2 ListRef Fields (Collection References)
- Product.comments: no column on products (join table), API response as href array
- Product.favorites: join table ProductLike, response as href array

### 8.3 Self-Referential FK (Ref['self'])
- Comment.parent_id: nullable integer, schema `"type": "selfref"`

### 8.4 FK Hydration on GET Single
- GET /products/1 — comments/favorites as href arrays with correct API_URL, table names, IDs

### 8.5 FK Hydration on GET List
- GET /products?limit=5 — each product has correctly formatted href arrays

### 8.6 Populate Depth Levels
- `?populate=comments` — 1 level
- `?populate=comments&depth=2` — 2 levels (comments + their likes)
- `?populate=comments.likes&depth=1` — explicit nested field

### 8.7 Populate with Non-existent Field
- `?populate=nonexistent_field` — 200 OK, field ignored

---

## 9. PAGINATION & METADATA

### 9.1 Response Structure
- `{data: [...], meta: {total, limit, offset, has_more}}`

### 9.2 Total Count
- `meta.total` = count of ALL records before LIMIT

### 9.3 has_more Flag
- `has_more = (offset + returned_count) < total`

### 9.4 Pagination with Authorization Filter
- OWNER rule: `meta.total` counts filtered results, `has_more` reflects filtered total

### 9.5 Boundary Conditions
- offset beyond total → `data: []`, `has_more: false`
- limit=0 → 422
- limit=101 → 422
- offset=-1 → 422

---

## 10. ERROR HANDLING & EDGE CASES

### 10.1 404 Not Found
- GET /products/999, GET /products/999/comments/1, PUT /products/999, DELETE /products/999

### 10.2 401 Unauthorized
- Missing token, invalid token, expired token

### 10.3 403 Forbidden
- POST /products without token, PUT as non-owner, DELETE as non-admin

### 10.4 422 Unprocessable Entity
- Missing required field, invalid type, field constraint violation, string length constraints, query param validation

### 10.5 400 Bad Request
- Route parameter type mismatch, invalid scaffold type

### 10.6 409 Conflict
- Duplicate email on registration

### 10.7 Missing/Invalid Fields in Custom Methods
- POST /products/1/comment with missing `comment` field → 400
- POST /products/1/comment with wrong type → 422

---

## 11. CROSS-MODEL WORKFLOWS

### 11.1 Complete Product Lifecycle
1. Create Product → 2. Get Product (empty refs) → 3. Add Comment → 4. Get with populated comments → 5. Like Comment → 6. Get comment with likes → 7. Reply to Comment → 8. Favorite Product → 9. Delete Comment → 10. Delete Product

### 11.2 User-Centric Workflow
1. Register User A → 2. Register User B → 3. A creates product → 4. B adds comment → 5. A replies → 6. B likes reply → 7. A likes B's comment → 8. Get aggregated data with populate&depth=2

### 11.3 Authorization Across Models
1. User A creates comment (auto-owned) → 2. A can update/delete (OWNER) → 3. B cannot update (403) → 4. Admin can update (ROLE) → 5. All can read (ANYONE)

### 11.4 Join Model Behavior
- ProductComment, CommentLike, ProductLike created correctly
- GET /comments returns all across products
- GET /products/1/comments returns filtered by product_id
- Delete cascade behavior

### 11.5 Data Consistency
- FK column values match parent, cascade on delete, no orphans

---

## 12. SCHEMA GENERATION & SERIALIZATION

### 12.1 Model.schema() Output
- All required sections: `$schema`, `$id`, `__name__`, `__tablename__`, `properties`, `required`, `ui`, `access`, `methods`, `$defs`
- ListRef → array of $ref, Ref → integer FK, Ref['self'] → `"selfref"`
- Composite rules serialized: `{op: "or", rules: [...]}`

### 12.2 model_dump(response=True) Output
- `$schema`, `$id` present, FK fields as hrefs, ListRef as href arrays

### 12.3 model_dump(response=False) Output
- No metadata, FK as integers, ListRef empty (stored in join tables)

### 12.4 Field Exclusion & Display Rules
- Auto-hidden: id, image, *_id, created_at, updated_at
- Hidden: password_hash
- Protected: user_owner on Comment, user on Like

---

## 13. TOKEN & JWT HANDLING

- **create_token** — JWT with user_id, email, role, exp, iat, HS256
- **decode_token** — validates signature and expiry
- **Header extraction** — `x-access-token` in middleware
- **User parameter resolution** — StorableMixin subclass → .get(user_id); dict → raw payload
- **Token expiration** — expired token → 401

---

## 14. RESPONSE METADATA & SELF-DESCRIPTION

- Single resources: `$schema` + `$id` on every response
- Paginated lists: `$schema` + `$id` on each item in `data` array
- Navigation: client can GET {$id} to fetch any entity

---

## 15. MIDDLEWARE

### JWT Authentication Middleware
- Exempt paths: /login, /register, /docs, /openapi.json, schema endpoints, static files
- All other routes: valid token required → 401 if invalid

### CORS Middleware
- Allow all origins configured, CORS headers present

---

## 16. EDGE CASES & BOUNDARY CONDITIONS

- Empty collections: `data: []`, `meta.total: 0`
- Single item collections
- Large payloads with deep populate
- Special characters in strings (HTML, SQL injection prevention)
- NULL/empty values: empty description, null optional fields
- Concurrent requests: both succeed, unique IDs
- Deleted parent, orphaned children (cascade behavior)

---

## 17. TEST DATA SETUP

### Seed Users
| Email | Password | Role |
|---|---|---|
| alice@example.com | alice123 | user |
| bob@example.com | bob123 | user |
| charlie@example.com | charlie123 | user |
| (optional admin user) | | admin |

### Seed Data
- 5 Products with varying prices/descriptions
- 8 Comments distributed across products
- 3 Replies (nested comments with parent_id)
- Multiple Likes across products and comments

### Test Isolation
- Each test independent
- Database reset between tests (delete DB file + reseed, or transactional rollback)
- Separate test DB file

---

## 18. EXECUTION NOTES

1. Use `pytest` + `httpx` (async) or FastAPI `TestClient`
2. `pytest` fixtures for: API client, JWT tokens, DB seeding/cleanup, user creation
3. Parametrize similar tests (authorization matrix, status code scenarios)
4. Mock time for token expiration tests
5. Capture and validate error response structure
6. Test names: `test_create_product_as_authenticated_user_succeeds`
7. Group into test classes by feature area
