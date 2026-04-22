# From Flat to Nested: A Tree Primitive for N3TX

> *How principles from Notion-style recursive block models can reshape our architecture -- and where they cannot.*
> *Companion to the [propositions document](Notion-blocks-propositions.md).*

---

## Abstract

N3TX's schema-driven architecture derives a complete application from a Python model definition -- API, schema, storage, UI. This works for flat entities and one-to-many collections, but **tree-shaped data** (comment threads, wiki hierarchies, nested menus, outline documents) falls through the gaps. The framework detects self-referential models (`Ref['self']`) at every layer but provides no operations, routes, or rendering for the parent-child structure they imply. This paper argues that adding a first-class **tree primitive** -- a `TreeMixin` triggered by `__tree__ = True` -- closes this gap using the same injection machinery as `StorableMixin` and `AgentMixin`, without expanding the framework's conceptual surface area. The adjacency list model N3TX already uses is the right storage strategy; what is missing is the convenience layer that makes tree operations zero-config. We propose a phased approach: tree mixin and schema extension (weeks 1-2), auto-registered API routes (weeks 2-3), and a recursive `<ntx-tree>` Web Component (weeks 3-5).

---

## 1. Introduction: Why This Matters Now

N3TX aspires to handle **any data shape** a developer expresses in a model. Today it handles two shapes well:

1. **Flat entities** -- a `Product` with scalar fields maps to a table, CRUD routes, and a card UI
2. **One-to-many collections** -- `ListRef[Comment]` on `Product` creates a join table, hydrated href arrays, and nested list rendering

But a third shape appears in nearly every real application: **trees**. Comments have replies. Wiki pages have child pages. Task lists have subtasks. Navigation menus have submenus. File browsers have folders within folders. Document outlines have nested headings.

These use cases share a common data model: a self-referential parent pointer (`parent_id`), sibling ordering, and a boolean flag indicating whether a node has children. The Notion API codified this pattern across 200+ billion blocks serving 100+ million users. WordPress Gutenberg applied it to 82 million sites. The pattern is proven, dominant, and conspicuously absent from N3TX.

The timing is right because:

- The **mixin injection system** (`register_mixin()`) was designed for exactly this kind of extension -- `AgentMixin` proved the pattern works
- The **`Ref['self']` infrastructure** already handles self-referential FKs at every layer (type system, schema, migration, frontend) -- the hard plumbing is done
- The **example Comment model** in `examples/core/` already uses `parent_id: Optional[Ref['self']]` with a `reply()` method -- a real tree model that gets no framework help
- Customer applications increasingly require **hierarchical data** that today demands manual SQL, custom routes, and hand-built tree UIs

---

## 2. Principles Worth Importing

The research distills five principles from Notion's block architecture and the broader industry adoption. Three are directly applicable to N3TX.

### Principle 1: The Schema Carries the Tree Contract

In Notion's API, every block response includes `has_children: boolean` and `type: string`. The client never guesses -- it reads the data and adapts. This mirrors N3TX's core philosophy: **the backend is authoritative, the frontend reads schema and adapts.**

N3TX already implements this for flat entities. The JSON Schema returned by `GET /{ClassName}` carries field types, UI hints, access rules, and method signatures. The frontend's `NTT.SCHEMA()` creates `DynamicClass` instances from this schema without any hardcoded knowledge of the model.

For tree models, the schema should carry tree metadata:

```json
{
  "properties": { "parent_id": {"type": "selfref"}, ... },
  "tree": {
    "parent_field": "parent_id",
    "order_field": "order",
    "children_endpoint": "/blocks/{id}/children",
    "roots_endpoint": "/blocks/roots"
  }
}
```

The frontend reads `schema.tree` and knows how to fetch children, when to show expand controls, and which field represents the parent pointer. **Zero hardcoded tree assumptions in the frontend code.**

### Principle 2: Lazy Expansion, Not Eager Trees

Notion's API never returns the full tree in one shot. It returns one level at a time, paginated (max 100 children per page). The client recursively fetches on demand when the user expands a `has_children: true` node.

This maps directly to N3TX's existing pagination pattern. `ListElement.definedCallback()` calls `proto.call('READ', {limit: 20, offset: 0})` and renders a "Load More" button when `has_more: true`. For tree models, the same pattern applies per-level: fetch root nodes first, then fetch children on expand.

The performance implication is critical. A tree with 20 nodes per level and 5 levels has 3.2 million total nodes. Lazy expansion collapses this to ~30-50 visible nodes at any time -- the same order of magnitude as a flat paginated list.

### Principle 3: Adjacency List Is Sufficient

The research evaluates four tree storage strategies: adjacency list, closure table, materialized path, and nested sets. For N3TX's use case (interactive editing with SQLite backend), the adjacency list wins:

- **O(1) writes** -- insert and move operations update a single row
- **Recursive CTE** -- `WITH RECURSIVE` in SQLite handles subtree queries efficiently
- **Already exists** -- `Ref['self']` creates exactly this storage model

Closure tables offer O(1) subtree reads but O(depth) writes and O(subtree_size) move operations. For an interactive editor where writes are frequent and reads are lazy (one level at a time), the adjacency list is strictly better.

N3TX does not need to choose a storage strategy -- it already chose the right one by implementing `Ref['self']` as a plain INTEGER column with an auto-generated index.

---

## 3. Our Architecture Through This Lens

Viewing N3TX through the tree-data lens reveals surprising strengths and specific gaps.

### What We Already Have (More Than Expected)

```
                     N3TX Tree Infrastructure Today
+--------------------------------------------------------------------+
|  Layer              | What Exists              | What's Missing     |
|---------------------+--------------------------+--------------------|
|  Type System        | Ref['self'] -> int +     | No tree semantics  |
|                     | _SelfRefMarker           |                    |
|  Schema Pipeline    | base() detects selfref,  | No tree metadata   |
|                     | emits {"type":"selfref"} | key in schema      |
|  Migration Engine   | INTEGER column + auto    | No order column    |
|                     | INDEX on selfref fields  | convention         |
|  Storage            | parent_id as plain int   | No children query  |
|                     | column in SQLite         | No subtree CTE     |
|  Route Layer        | Standard CRUD routes     | No /children route |
|                     |                          | No /roots route    |
|  Frontend Schema    | form.js renders selfref  | No tree-picker     |
|                     | as number input          | widget             |
|  Frontend Render    | ntx-item.js adds         | No recursive       |
|                     | reply-indent CSS class   | rendering          |
|  Mixin Injection    | register_mixin() ready   | No TreeMixin       |
|                     | (proven by AgentMixin)   | registered         |
+--------------------------------------------------------------------+
```

The infrastructure is in place at every layer. The self-referential type (`Ref['self']`) flows through the type system, schema pipeline, migration engine, and frontend renderer. The mixin injection system is designed and proven. What is missing is the **orchestration** -- the code that connects these primitives into a coherent tree experience.

### The Existing Comment Model: A Case Study

The Comment model in `examples/core/models/comment.py` is a real tree model that gets no framework help:

```python
class Comment(ProtoModel):
    __tablename__ = 'comments'
    __storable__ = True

    name: str = Field(min_length=1, max_length=500)
    description: TextareaField = Field(default='')
    parent_id: Optional[Ref['self']] = Field(default=None)

    @expose_route('/reply', methods=['POST'])
    def reply(self, text: str, user: User = None) -> str:
        reply = Comment(name=text, parent_id=self.id, ...)
        Comment.create(reply)
        return "ok"
```

This model defines a tree but gets treated as a flat list. The frontend renders all comments in a grid, with only a CSS indent class distinguishing replies from top-level comments. To display a threaded comment view, the developer would need to:

1. Write a custom endpoint that filters by `parent_id`
2. Write a recursive loading function on the frontend
3. Build a tree renderer from scratch
4. Handle expand/collapse state management

With `__tree__ = True`, all of this comes for free.

### Current vs. Proposed Data Flow

```
TODAY (flat):

  Frontend                    Backend
  ntx-list ----READ---------> GET /comments
            <--[c1,c2,c3]---- All comments, flat
  ntx-item                    No tree awareness

PROPOSED (tree):

  Frontend                    Backend
  ntx-tree ----READ roots---> GET /comments/roots
            <--[c1,c5]------- Top-level only
  [user clicks expand on c1]
  ntx-tree ----READ children-> GET /comments/1/children
            <--[c2,c3]------- Direct children of c1
  [user clicks expand on c3]
  ntx-tree ----READ children-> GET /comments/3/children
            <--[c4]---------- Direct children of c3
```

Each step fetches only what is needed. The total data transferred is O(visible nodes) instead of O(all nodes).

---

## 4. The Synthesis: Where Two Worlds Meet

### Integration Point 1: TreeMixin + StorableMixin Composition

**Current state:** `StorableMixin` provides CRUD (`create`, `list`, `get`, `update`, `delete`). Self-referential models use these operations on flat collections with no tree awareness.

**Proposed state:** `TreeMixin` extends `StorableMixin` operations with tree-specific behavior. It hooks into `create()` to update the parent's `has_children` flag, into `delete()` to recompute it, and adds new class methods (`root_nodes`, `children_of`, `subtree`) that call `list()` with appropriate filters.

```
Before:                          After:

ProtoModel                       ProtoModel
    |                                |
StorableMixin                    StorableMixin
  create()                         create() -----> TreeMixin._after_create()
  list()                           list()            -> update parent has_children
  get()                            get()
  update()                         update()
  delete()                       delete() -----> TreeMixin._after_delete()
                                                   -> recompute parent has_children
                                 TreeMixin
                                   root_nodes()    -> list(parent_id IS NULL)
                                   children_of()   -> list(parent_id = ?)
                                   subtree()       -> WITH RECURSIVE CTE
                                   move()          -> validate + update parent_id
                                   reorder()       -> update order column
                                   ancestors()     -> walk parent_id upward
```

**Migration path:** TreeMixin is injected via `register_mixin('__tree__', TreeMixin)`. Models that already have `parent_id: Ref['self']` add `__tree__ = True` and gain all tree operations. Existing data is unchanged -- the adjacency list storage model is already in place.

**Expected outcomes:**
- Tree operations available on any model with one flag
- `has_children` maintained automatically
- Consistent with StorableMixin and AgentMixin patterns
- Zero impact on non-tree models

### Integration Point 2: Schema Pipeline Extension

**Current state:** The schema pipeline runs 7 stages: `base -> strip_hidden -> methods -> defs -> access -> ui -> metadata`. External packages add stages via `@schema_extension`. The `viewable` stage (from `n3tx-ui`) adds UI config after `ui`. The `agent` stage (from `n3tx-agents`) adds agent config after `methods`.

**Proposed state:** A `tree` stage, registered after `ui` via `@schema_extension(after='ui')`, adds tree metadata to the schema for any model with `__tree__ = True`.

```
Pipeline stages (with tree extension):

base -> strip_hidden -> methods -> defs -> access -> ui -> viewable -> tree -> metadata
                                                                       ^^^^
                                                              New stage: emits tree config
```

The `tree` stage reads the model's `__tree__` flag and field definitions, then emits a `tree` key in the schema with endpoint URLs, field names, and rendering hints. The frontend reads this key in `NTT.SCHEMA()` and configures the tree component accordingly.

**Migration path:** The `@schema_extension` decorator handles registration. No existing pipeline code changes. The tree schema extension is a single function in a single file.

**Expected outcomes:**
- Frontend self-configures from schema (no hardcoded conventions)
- Tree metadata visible in `GET /{ClassName}` response for inspection
- Other consumers (CLI tools, test harnesses) can read tree config from schema

### Integration Point 3: Frontend Tree Rendering

**Current state:** `ListElement` renders flat grids. `NTTItem` renders single-entity cards. `NTTItem.render()` applies a one-level `reply-indent` CSS class for `selfref` fields but has no recursive rendering.

**Proposed state:** `<ntx-tree>` extends `ListElement` with a tree rendering strategy. Instead of fetching all entities and rendering a grid, it fetches root nodes and renders `<ntx-tree-item>` elements. Each tree item can expand to lazy-load children via the `/children` endpoint.

```
Before:                          After:

ntx-list                         ntx-list (flat models, unchanged)
  +-- ntx-item                     +-- ntx-item
  +-- ntx-item
  +-- ntx-item                   ntx-tree (tree models)
                                   +-- ntx-tree-item (root 1, expanded)
                                   |     +-- ntx-tree-item (child 1.1)
                                   |     +-- ntx-tree-item (child 1.2, collapsed)
                                   |           [expand arrow: has_children=true]
                                   +-- ntx-tree-item (root 2)
```

The developer switches from flat to tree rendering by setting:

```python
__ui__ = {
    'renderer': {'item': 'ntx-tree-item', 'list': 'ntx-tree'},
}
```

Or, when `__tree__ = True`, the framework could default the renderer to `ntx-tree` unless explicitly overridden.

**Migration path:**
1. Create `ntx-tree.js` extending `ListElement` with root-node fetching
2. Create `ntx-tree-item.js` extending `NTTElement` with expand/collapse
3. Register `customElements.define('ntx-tree', NtxTree)` and `customElements.define('ntx-tree-item', NtxTreeItem)`
4. Existing `ntx-list` and `ntx-item` are unchanged

**Expected outcomes:**
- Collapsible tree rendering from schema alone
- Lazy loading keeps DOM size proportional to visible nodes
- CSS grid animation for smooth expand/collapse transitions
- Consistent with existing component hierarchy

---

## 5. Boundaries: Where This Does Not Apply

### Not a Block Editor

This proposal adds **tree data operations and tree rendering** to N3TX. It does not build a rich text block editor with inline editing, slash commands, contenteditable, or collaborative editing. Those are application-layer concerns built on top of tree primitives, not framework concerns.

ProseMirror, Tiptap, and BlockNote are 50,000+ line projects dedicated to inline editing. N3TX should not attempt to replicate them. Instead, a developer building a Notion-like editor would use `__tree__ = True` for the data layer and bring their own editor UI.

### Not a CRDT Engine

Real-time collaborative tree editing (multiple users rearranging blocks simultaneously) requires conflict resolution that goes far beyond what a REST API with SQLite can provide. This is firmly in the territory of CRDTs (Yjs, Automerge) or operational transform systems. N3TX's actor messaging system could eventually bridge to these, but that is a separate initiative.

### Not Polymorphic Block Types

The Notion model assigns a `type` field to each block (paragraph, heading, image, toggle) and dispatches rendering accordingly. This proposal does not add a block type registry or polymorphic dispatch to N3TX. A developer can implement this with a `type: str` field and a custom frontend renderer. If demand warrants it, a `BlockModel` base class with a type registry could be a future extension.

### Models That Should Stay Flat

Not every self-referential model is a tree. A `User` with a `referred_by: Ref['self']` field represents a referral chain, not a tree. A `Document` with `previous_version: Ref['self']` represents a linked list. These use cases should not be forced into tree semantics. The explicit `__tree__ = True` flag ensures opt-in, not auto-detection.

---

## 6. A Path Forward

### Phase 1: Backend Tree Foundation (Weeks 1-2)

**Deliverables:**
- `n3tx_core/models/tree_mixin.py` with `TreeMixin` class
- `register_mixin('__tree__', TreeMixin)` registration
- `@schema_extension(after='ui')` for tree metadata
- `children_of()`, `root_nodes()`, `subtree()` query methods
- `has_children` auto-maintenance on create/delete
- Unit tests for all tree operations

**Success criteria:**
- A `Block` model with `__tree__ = True` passes all CRUD + tree operation tests
- `Block.schema()` includes `tree` key with correct endpoint URLs
- `Block.subtree(root_id, max_depth=3)` returns correct results via recursive CTE
- `has_children` is correctly maintained across create, delete, and move operations

**Decision gate:** Do the tree operations feel right? Do they compose well with existing `StorableMixin` methods? If yes, proceed to Phase 2. If the API feels awkward, iterate before building routes.

### Phase 2: API Routes + Frontend Foundation (Weeks 2-4)

**Deliverables:**
- Auto-registered tree routes in `register_routes()`: `/roots`, `/children`, `/descendants`, `/move`, `/reorder`
- `<ntx-tree>` component with root-node rendering
- `<ntx-tree-item>` component with expand/collapse and lazy child loading
- CSS expand/collapse animation via `grid-template-rows`
- Example app in `examples/tree/` demonstrating a multi-level tree

**Success criteria:**
- `GET /blocks/roots` returns paginated root nodes
- `GET /blocks/{id}/children` returns paginated children
- `<ntx-tree model="Block">` renders a working collapsible tree from schema alone
- Expanding a node triggers a `/children` fetch and renders children with indent
- The example app loads, renders, and navigates a 3-level tree

**Decision gate:** Is the tree rendering component useful enough to ship? Does the developer experience match the "zero to working" promise? If yes, proceed to Phase 3.

### Phase 3: Polish and Advanced Features (Weeks 4-6)

**Deliverables:**
- Tree-picker widget for `parent_id` selection
- Breadcrumb navigation component
- Drag-and-drop reordering (SortableJS integration)
- Keyboard navigation (WAI-ARIA tree pattern)
- Performance profiling with 500+ node trees

**Success criteria:**
- Reparenting via tree-picker works end-to-end
- Drag-and-drop correctly updates `parent_id` and `order`
- Keyboard navigation follows WAI-ARIA tree pattern
- No visible jank with 500 nodes (200ms budget for full render)

**Decision gate:** Should the tree components ship as part of `n3tx-ui` or as a separate `n3tx-tree` package? The answer depends on how many core use cases require trees vs. how much it increases the `n3tx-ui` bundle size.

---

## 7. Conclusion

The question is not whether N3TX needs tree support -- the Comment model with `Ref['self']` already proves developers reach for hierarchical structures. The question is whether the framework should **own** the tree experience or leave it as an exercise for each project.

The answer is clear: **the framework should own it.**

N3TX's value proposition is "define a model, get an API, a schema, a working UI." Today that promise breaks for tree-shaped data. Adding `__tree__ = True` restores it. The implementation is not speculative -- every piece uses proven infrastructure: `register_mixin()` for injection, `@schema_extension` for schema, `register_routes()` for API, `ListElement` for rendering. The adjacency list storage model is already in place.

The risk profile is unusually favorable. The tree mixin is a pure addition with zero changes to existing code paths. Non-tree models are completely unaffected. The worst case is that tree operations exist but are unused; the best case is that N3TX gains a capability that puts it on par with Directus and Payload CMS for hierarchical data while maintaining its "model is the app" identity.

The bet: adding a tree primitive is a modest investment (3-5 weeks) that unlocks a disproportionately large set of use cases -- comment threads, wiki pages, nested menus, outline notes, file browsers, org charts, recursive task lists. Every one of these is currently buildable in N3TX, but only with significant manual plumbing. With `__tree__ = True`, they become zero-config.

That is the N3TX promise. Trees should be part of it.

---

## References

### Research Documents
- `.traces/research/notion-blocks/01-industry-and-decisions.md` -- Industry landscape and decision framework
- `.traces/research/notion-blocks/02-technical-deep-dive.md` -- Recursive block data models technical deep dive
- `.traces/research/notion-blocks/03-stack-relevance.md` -- N3TX stack relevance analysis
- `.traces/research/notion-blocks/04-recursive-rendering.md` -- Recursive rendering and component composition

### Codebase Files Referenced
- `packages/n3tx-core/src/n3tx_core/models/proto_model.py` -- ProtoModel base class, `register_mixin()`, `__init_subclass__`
- `packages/n3tx-core/src/n3tx_core/models/proto_schema.py` -- Schema pipeline, `@schema_extension`, `register_stage()`
- `packages/n3tx-core/src/n3tx_core/models/storable_mixin.py` -- StorableMixin CRUD operations
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py` -- SQLite backend, `list()` with `sql_filter`
- `packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py` -- Auto-migration, `_is_self_ref()` detection, INDEX creation
- `packages/n3tx-core/src/n3tx_core/models/ref.py` -- `ListRef[T]` type alias
- `packages/n3tx-core/src/n3tx_core/utils/typer.py` -- `Ref['self']` -> `_SelfRefMarker`, `Ref[T]` generic
- `packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py` -- Route registration, two-pass pattern
- `packages/n3tx-ui/src/n3tx_ui/mixin.py` -- `ViewableMixin`, `@schema_extension(after='ui')`
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js` -- NTTItem, `reply-indent` CSS class
- `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.js` -- NTTList (thin wrapper on ListElement)
- `packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js` -- Collection base, pagination, `createChild()`
- `packages/n3tx-core/src/n3tx_core/static/core/NTT.js` -- DynamicClass creation, `NTT.SCHEMA()`, `$defs` handling

### External Sources
- [Notion API: Block Reference](https://developers.notion.com/reference/block)
- [Notion API: Working with Page Content](https://developers.notion.com/docs/working-with-page-content)
- [SQLite WITH RECURSIVE documentation](https://www.sqlite.org/lang_with.html)
- [Directus Tree Structure](https://www.restack.io/docs/directus-knowledge-directus-tree-structure)
- [Payload CMS Nested Docs Plugin](https://payloadcms.com/docs/plugins/nested-docs)
- [CSS Grid Auto Height Transitions](https://css-tricks.com/css-grid-can-do-auto-height-transitions/)
- [WAI-ARIA Tree View Pattern](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/)
- [SortableJS](https://github.com/SortableJS/Sortable)

### Companion Document
- [Technical Propositions](Notion-blocks-propositions.md) -- Numbered implementation proposals with effort/impact ratings
