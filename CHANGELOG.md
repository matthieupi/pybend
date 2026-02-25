# Pybend Change Log

# 0.7.0 (2026-02)

## Backend
- [x] **Social features — Like/Favorite toggle** — `Comment.like()` and `Product.favorite()` rewritten as toggle endpoints (create if not liked/favorited, delete if already exists)
  - Uses `join_models` registry to query/delete via join tables (`CommentLike`, `ProductLike`)
  - Empty body allowed (`Body(default={})`) — no payload needed for toggle actions
  - Returns `{"action": "liked"}` / `{"action": "unliked"}` (or `favorited`/`unfavorited`)
- [x] **Comment reply method** — `Comment.reply()` creates a child comment with `parent_id` set to the replied-to comment
  - Resolves product parent for correct join table insertion
  - Access restricted to `AUTHENTICATED` users
- [x] **ProductLike join model** — `generate_join_model(Product, Like)` registered in `main.py` for product favorites
- [x] **Collection routes for join models** — `GET /products/comments`, `GET /products/likes` return all records across parents
  - `make_collection_list()` factory with auth, pagination, and populate support
  - Registered in Pass 1 (before CRUD routes) to avoid `{id:int}` path conflict with static segments
- [x] **Typed path parameters** — all route paths use `{id:int}` and `{parent_id:int}` for proper FastAPI type coercion
- [x] **StorableMixin MRO walk** — `save()` walks `__mro__` to find matching join key, fixing nested saves for join model instances (e.g., ProductComment saving a child Comment)
- [x] **Method UI hints in $defs** — `proto_model.schema()` injects `__ui__.methods` hints into `$defs` method entries for referenced models
- [x] **Like model protected fields** — `user` field marked as `__protected_fields__` (server-injected, not client-editable)
- [x] **Seed data expansion** — added likes on comments (5) and favorites on products (5) to seed script
- [x] **Pagination** — list endpoints accept `?limit=N&offset=M` query params
  - `sqlite_storage.list()` returns `{data: [...], meta: {total, limit, offset, has_more}}` when paginated
  - `storable_mixin.list()` passes `limit`/`offset` through to storage
  - Backward-compatible: unpaginated when no params provided
- [x] **Authenticated user injection** — `@expose_route` methods can declare a `user: User` parameter
  - `_resolve_user()` in `routes_fastapi.py` resolves the JWT user and injects the User instance
  - `Product.comment()` and `Comment.like()` updated to use injected user instead of hardcoded IDs
- [x] **User model UI hints** — added `__ui__` with `renderer` config pointing to `ntt-user` component
- [x] **Protected fields** — `__protected_fields__` class variable prevents API mutation of backend-owned fields
  - `user_owner` auto-injected from JWT on create for models declaring it as protected
  - Protected fields stripped from update payloads in route layer
  - Schema marks protected fields with `ui.protected = true` for frontend consumption
- [x] **OWNER rule FK-hydrated href support** — `_Owner.evaluate()` extracts trailing ID from href strings
  - Handles `user_owner` values like `http://.../users/3` after FK hydration
- [x] **Comment model ABAC** — added `__access__` rules (ANYONE read, AUTHENTICATED create, OWNER|admin update/delete)
- [x] **$defs access rule injection** — `proto_model.schema()` now injects access rules from referenced models into their `$defs` entries
- [x] **[Authorization & Authentication](src/pybend/docs/AUTHORIZATION.md)** — standalone `authorize/` package
  - Added ABAC (Attribute-Based Access Control) with composable rule objects and operator overloading (`|`, `&`, `~`)
  - Built-in rules: `ANYONE`, `AUTHENTICATED`, `OWNER`, `ROLE(*roles)`, `Where(**conditions)` with comparison operators (`__lt`, `__gt`, `__lte`, `__gte`, `__ne`, `__in`)
  - SQL pushdown: rules produce `(WHERE_clause, params)` for efficient list-level filtering
  - `AuthorizationResolver` Protocol for swappable resolution strategies; `DefaultResolver` reads `__access__` from models
  - Schema exposure: access rules serialize to JSON in schema responses for frontend UI adaptation
  - JWT authentication: bcrypt password hashing, token create/decode with `role` in payload
  - `JWTAuthMiddleware` in `FastAPIBackend` — validates tokens, populates `request.state.user`
  - `configure()` function for JWT settings — package has zero PyBend imports, reads env vars by default
  - `access=` parameter on `@expose_route()` for per-method authorization
  - `sql_filter` parameter threaded through `list()` in storage, mixin, and route layers
  - `User.role` field with validator to coerce NULL/empty to `'user'`
  - `Like` model and `CommentLike` join model; `Comment.parent_id` for self-referential nesting via `Ref['self']`
  - Seed data: users, products, comments, nested replies
- [x] **[ForeignKey Hydration](src/pybend/core/docs/features/01_ForeignKey_Hydration.md)**
  - Added SQLite migration system (`sqlite_migration.py`) with Rails-style run/rollback
  - Added `ListRef[T]` type (`models/ref.py`) for FK hydration — collection fields return href arrays instead of embedded objects
  - Added `__fk_models__` cache on parent models for join model resolution
  - Added `collection_field_names` filter in `update()` to skip List[BaseModel] fields
  - Moved type introspection utilities to `utils/introspection.py` (`get_list_fields`, `_unwrap_listref`)
  - Added nested routes for child entity access (`/tablename/:id/field/:child_id`)

## Frontend
- [x] **`<ntt-method>` button layout** — new compact icon + count pill rendering for social actions (like, favorite)
  - SVG icon library (heart, star, reply, default) with hover/active states
  - `count-field` attribute reads collection length from entity data (supports populated wrappers)
  - `renderButton()` method alongside existing `renderFieldset()` and `renderInline()`
  - Click handler routes through NTT Actor with `_response_` inbox for auto-refresh
- [x] **sm() social method buttons** — like/favorite/reply buttons rendered inline in sm card layout
  - Button-layout methods detected from schema `methods[name].ui.layout === 'button'`
  - Reply button shows inline input box with submit (Enter key or button click)
  - Reply triggers parent entity re-fetch for immediate UI update
- [x] **Reply indent** — comments with `parent_id` (selfref) get `reply-indent` CSS class with left border + margin
- [x] **Populated wrapper normalization** — frontend handles both href strings and populated objects (`{$id, ...}`)
  - `sm()` extracts `$id` from populated `$ref` fields for avatar rendering
  - `form.js` `getListInput()` normalizes `{data: [...], meta: {...}}` wrappers to plain arrays
  - `#patchListField()` extracts `$id` from items for diff comparison
  - Instance `READ` handler runs `normalizePopulated()` on pull responses
- [x] **Instance href from $id** — `DynamicClass` instances use entity `$id` for `href` (correct nested CRUD path like `/products/1/comments/3`)
  - ATTACH handler updates `href` from `meta.href` when a more specific URL is known
- [x] **`<ntt-favorites>` component** — simple page wrapper mounting `<ntt-list model="ProductLike">` at `#@favorites` route
- [x] **Topbar Favorites link** — authenticated users see a "Favorites" nav link in `<ntt-topbar>`
  - `topbar-nav` CSS block with hover transitions
- [x] **JSON render depth guard** — `ntt-logs.js` caps recursion at depth 8 to prevent stack overflow on circular structures
- [x] **Playwright tests** — `test_routing.py` (URL path correctness) and `test_social.py` (API + frontend rendering validation)
- [x] **CLAUDE.md improvements** — reformatted long lines, added Development Workflow section (consistency, bug fix philosophy)
- [x] **Resource-aware OWNER checks** — `Permissions.canAction()` now accepts entity data for real OWNER evaluation
  - `#evaluateOwner()` compares resource's owner field to current user ID
  - Handles FK-hydrated href strings (e.g., `http://.../users/3` → extract trailing ID)
  - All `canAction()` call sites in `ntt-item.js` pass `this.value` for per-entity checks
  - Edit/delete buttons now appear only for actual owners (not just any authenticated user)
- [x] **Entity signal subscriptions** — `NTTElement.DESCRIBE()` subscribes to entity signal for live updates
  - Components auto-update when entity data changes (e.g., after `pull()`)
  - Subscription cleanup in `disconnectedCallback()`
  - Instance `_response_` handler auto-pulls after method calls (replaces manual `setTimeout`)
  - Instance `READ` handler for `pull()` responses
- [x] **Protected fields** — backend-owned fields excluded from edit forms
  - `__protected_fields__` class variable on models marks fields as server-managed
  - Schema marks protected fields with `ui.protected = true`
  - `form.js` hides protected fields in edit mode
  - Route layer auto-injects `user_owner` from JWT on create, strips protected fields on update
- [x] **CREATE handler** — `DynamicClass.CREATE` registers new instances and notifies list watchers
- [x] **Delete flow improvements** — routes through DynamicClass for proper registry cleanup
  - Uses `ref` (actual API endpoint URL) instead of `$id` for nested entities
  - `NetworkAdapter.js` fixed: DELETE no longer sends request body
- [x] **sm() action buttons** — edit/delete buttons on hover in sm size with CSS transitions
  - sm edit mode delegates to md() for full form experience
  - Layout size adjustment when editing in compact sizes
- [x] **$defs access rules** — referenced model access rules now injected into `$defs` schema entries
- [x] **Pagination UI** — `ListElement` tracks page size/offset, renders "Load More" button when `has_more`
  - Count display shows "current / total" when paginated
  - `NetworkAdapter` encodes `tx.data` objects as URL query params for READ transactions
- [x] **Delete support** — delete button in `ntt-item` `md()` with confirmation dialog and ABAC check
  - `NTT.js` DynamicClass implements DELETE handler: removes instance, notifies watchers
- [x] **`<ntt-user>` component** — custom NTTItem subclass with circular avatar rendering (xs/sm)
  - Fallback to ui-avatars.com when no image is set
  - User model `__ui__.renderer` wires it automatically
- [x] **ATTACH routing improvements** — `NTT.js` fetches individual entities on ATTACH for non-existent instances
  - Pending ATTACH queue replayed after READ completes
  - `Component.ref` setter routes URL refs through ATTACH when `data-model` attribute is present
- [x] **`ntt-item` sm display refinements** — respects `field_order`, renders `$ref` fields as leading avatars
  - Replaced `#topFields()` with `#smFields()` for better field selection
  - `#resolveChildTag()` looks up child component tags from schema
- [x] **Kitchen sink page** — complete rewrite of `schema.html` into a full component showcase
  - Adaptive display demo (xs pill, sm row, md card, lg detail)
  - Live `ntt-list` + `ntt-router` with click-to-navigate
  - User model at xs/sm, collapsible JSON schema inspector, ABAC permission panel
  - Glass morphism sections, `ks-` prefixed CSS, responsive layout
- [x] **[Refactor PTT into NTT](src/pybend/static/docs/PTT_NTT_MERGE.md)**
  - Merged PTT into NTT — NTT is now the universal type registry, schema proxy, and ATTACH router
  - Added null-pointer bootstrap pattern with TX message queueing for async schema loading
  - Added `NTT.SCHEMA` static handler for bootstrap completion and DynamicClass generation
  - Added `NTT.ATTACH` universal router handling both type-level and instance-level ATTACHes
  - Added optimistic update flow: `NTT.UPDATE` updates locally then forwards to backend
- Added `save()` method on `<ntt-item>` with NTT-mediated update path
- Added favicon (SVG)

## Tests
- [x] **test_routing.py** — Playwright test verifying like/reply/favorite POST to correct nested API paths
- [x] **test_social.py** — Playwright test suite (15 checks): schema validation, toggle actions, reply creation, collection routes, frontend rendering (star/heart/reply buttons, reply indent, favorites navigation)

## Documentation
- Updated `CLAUDE.md` — reformatted long lines for readability, added Development Workflow section (consistency principles, bug fix philosophy)
- Updated auto-generated docs: `products.md` (favorites field, favorite method), `products_comments.md` (like toggle, reply method), `products_likes.md` (new)
- Updated `index.md` with `products_likes` entry
- Updated `AUTHORIZATION.md` with protected fields section, OWNER href handling note
- Updated `COMPONENTS.md` with entity signal subscriptions, protected fields, resource-aware OWNER checks, sm action buttons
- Updated `MESSAGE_PROTOCOL.md` with CREATE handler, delete flow through DynClass, `_response_` handler, updated reference table
- Updated `ARCHITECTURE.md` with protected field auto-injection in route factories
- Updated `CLAUDE.md` with pagination lifecycle, user injection, and delete in generated capabilities table
- Updated `API_CRUD_ENDPOINTS.md` with pagination query params, response format, and examples
- Updated `API_CUSTOM_ENDPOINTS.md` with `user` parameter injection pattern
- Updated `ARCHITECTURE.md` data flow to reflect pagination
- Updated `COMPONENTS.md` with ntt-user, delete button, and ListElement pagination docs
- Updated `MESSAGE_PROTOCOL.md` with DELETE handling and paginated READ format
- Updated `TRANSPORT.md` with query parameter encoding for READ
- Added `ROADMAP.md` with v0.8.0 plans
- Added `docs/AUTHORIZATION.md` — full reference for the authorize package (quick start, rules, composition, architecture, extending, reference)
- Created comprehensive README.md for NTT 0.6 (quickstart, architecture, dataflow, CRUD, components)
- Documented FK hydration across README.md, ARCHITECTURE.md, ACTORS.md, COMPONENTS.md, MESSAGE_PROTOCOL.md, TRANSPORT.md
- Added PTT/NTT merge report (`docs/PTT_NTT_MERGE.md`)
- Added FK hydration implementation report (`core/docs/features/FK_HYDRATION.md`)
- Created TODOs.md for project task tracking

# 0.6.0 (2025-12)

## Frontend — Actor Model Architecture (NTTTX v0.6)
- Rewrote entire frontend from event-bus architecture (NTT 0.5) to actor-based model
- Introduced `Actor` base class with hierarchical message routing (`_send` 3-case dispatch, `_inbox` dispatch-or-forward)
- Introduced `Matrix` as root actor and central message router
- Introduced `TX` (Transaction) as the universal message envelope (name, source, target, data, meta)
- Introduced `TT` (Transfer Type) as base entity class with watcher pattern and Observable mixin
- Introduced `PTT` (Proto Transfer Type) as schema proxy and dynamic class factory
- Introduced `NTT` (Named Transfer Type) as per-entity instance base class
- Introduced `DynamicClass` — runtime-generated NTT subclass per backend model with typed getters/setters
- Introduced `Component` base class extending `HTMLElement` with actor registration
- Added `Observable` mixin (`signal`, `observe`, `notify`) applied via `Actor.subclass()`
- Added `NetworkAdapter` for HTTP transport (GET/POST/PUT/DELETE) with TX-based request/response

## Infrastructure
- Added `matrix.html` — main application entry point
- Added `schema.html` — interactive schema explorer page
- Added `config.js` for frontend configuration (API_URL, debug flags)

# 0.5.0 (2025-07)

## Frontend — NTTTX v0.5
- Created NTT 0.5 frontend with event-based architecture (`Event.js`, `Remote.js`, `HTTP.js`)
- Created `<ntt-element>` web component — base component with data binding and render lifecycle
- Created `<ntt-list>` — renders a collection of `<ntt-item>` elements from a model type
- Created `<ntt-item>` — renders a single entity with auto-generated form fields from schema
- Created `<ntt-method>` — invokes backend RPC methods on entities
- Abstracted `<ntt-element>` base class, improved cross-system bindings
- Created `Formidable` form generator — auto-generates input fields from JSON schema (text, number, select, textarea, ref)
- Uncoupled form generation from `<ntt-item>` into standalone generator
- Added `dark-theme.css` with design tokens
- Removed legacy NTT 0.0–0.4 frontend versions (~10,000 lines deleted)

## Backend
- Added methods signature to JSON schema endpoint (`schema.methods`)
- Fixed routes registration closure bug — models were all binding to last registered model
- Added `ProtoModel.__init__` by id for direct entity lookup
- Added `List[RefProtoModel]` backend logic for one-to-many references
- Added nested routes for references (`POST /products/:id/comments`)
- Added join model architecture for managing entity relationships
- Started foreign key implementation with schema view support
- Added SQLite database file support

# 0.2.0 (2025-04)
- Added interface for multiple backend (added FastAPI)
- Updated README to reflect new features
- Created Universal Context Protocol (UCP) specification document for
  compute over meta models (COMM) first draft (very rough, WIP)

# 0.1.0 (2024-12)

## Initial release
- Created pybend module with flask and swagger support
- Support for multiple backend storages