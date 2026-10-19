# :wrench: Recursive Block Models x N3TX: Technical Propositions

> *How Notion-style tree primitives can extend our schema-driven architecture.*
> *Based on research in `.traces/research/notion-blocks/` and codebase analysis.*

---

## :dart: The Bridge

N3TX's core philosophy -- "the model is the app" -- already implies that any
data shape a developer can express in a Python model should produce a working
full-stack application. Today that works beautifully for **flat entities** and
**one-to-many collections** (via `ListRef[T]`). But a third data shape
dominates modern applications: **trees**. Comment threads, wiki page
hierarchies, nested task lists, navigation menus, outline documents -- all
are self-referential parent-child structures that N3TX can represent in the
model layer (via `Ref['self']`) but cannot **operate on** or **render**
without significant developer effort.

The research reveals that Notion, Directus, Payload CMS, and AppFlowy all
converged on a common pattern: an **adjacency list** with a `parent_id`
column, an `order` field for sibling sequencing, a `has_children` boolean
for lazy UI expansion, and dedicated `/children` API endpoints. N3TX already
has the adjacency list (`Ref['self']` creates an indexed INTEGER column).
It already detects `selfref` at every layer -- type system, schema pipeline,
migration engine, and frontend renderer. What is missing is the
**convenience layer** that turns these raw primitives into a zero-config
tree experience.

The bridge is clean: `__tree__ = True` on a model triggers a `TreeMixin`
injection (same pattern as `StorableMixin`, `AgentMixin`, `ViewableMixin`),
which adds tree query methods, auto-registers tree API routes, emits tree
metadata into the JSON Schema, and tells the frontend to render a
collapsible tree instead of a flat grid.

---

## :bulb: Propositions

### P1: `TreeMixin` via `register_mixin('__tree__', TreeMixin)`

> :wrench: **Proposition:** Add a `TreeMixin` that injects tree operations into any model with `__tree__ = True`, following the exact injection pattern of `StorableMixin` and `AgentMixin`.

**From the research:** Directus and Payload CMS both validate that **mixin-injected tree support is the right abstraction level** for schema-driven frameworks. Notion's API exposes `has_children`, `/children` endpoints, and lazy expansion -- all derivable from model metadata.

**In our system:** The `register_mixin()` infrastructure in `proto_model.py` (lines 25-44) and the `__init_subclass__` loop (lines 112-119) are explicitly designed for this. `AgentMixin` registers via `register_mixin('__agent__', AgentMixin)` in `n3tx_agents/__init__.py`. `ViewableMixin` triggers on `__ui__` via `also_if`. TreeMixin would follow the identical pattern.

**The idea:**

Create `n3tx_core/models/tree_mixin.py` with:

```python
class TreeMixin:
    """Injected when __tree__ = True on a ProtoModel subclass."""

    @classmethod
    def children_of(cls, parent_id, limit=20, offset=0):
        """Direct children of a node, paginated."""
        return cls.list(sql_filter=("parent_id = ?", [parent_id]),
                        limit=limit, offset=offset)

    @classmethod
    def root_nodes(cls, limit=20, offset=0):
        """Top-level nodes (parent_id IS NULL), paginated."""
        return cls.list(sql_filter=("parent_id IS NULL", []),
                        limit=limit, offset=offset)

    @classmethod
    def subtree(cls, root_id, max_depth=3):
        """Recursive descendants via WITH RECURSIVE CTE."""
        # SQLite has supported WITH RECURSIVE since 3.8.3 (2014)
        ...

    def move(self, new_parent_id):
        """Reparent this node. Validates no circular reference."""
        ...

    def reorder(self, position):
        """Set this node's order among siblings."""
        ...
```

Register it at module scope:

```python
from n3tx_core.models.proto_model import register_mixin
register_mixin('__tree__', TreeMixin)
```

Developer usage becomes one line:

```python
class Block(ProtoModel):
    __tablename__ = 'blocks'
    __storable__ = True
    __tree__ = True

    name: str
    content: str = ''
    parent_id: Optional[Ref['self']] = Field(default=None)
    order: int = Field(default=0)
```

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- ~3 days for the mixin class + tests |
| Impact | **High** -- every tree use case gets solved once |
| Risk | **Low** -- pure addition, zero existing code changes |
| Timeline | **1 week** (with tests and docs) |

---

### P2: `@schema_extension(after='ui')` for Tree Metadata

> :wrench: **Proposition:** Add a `tree` schema extension that emits tree configuration into the JSON Schema, telling the frontend how to query and render tree models.

**From the research:** Notion's API never returns the full tree. It returns one level at a time, with `has_children: boolean` as the cue for lazy expansion. The schema must carry enough metadata for the frontend to self-configure.

**In our system:** The `@schema_extension` decorator in `proto_schema.py` (lines 98-119) is the exact mechanism. `ViewableMixin` uses `@schema_extension(after='ui')` in `n3tx_ui/mixin.py` (line 28). The tree extension follows the same pattern.

**The idea:**

```python
@schema_extension(after='ui')
def tree(cls, s: dict) -> dict:
    if not getattr(cls, '__tree__', False):
        return s
    s['tree'] = {
        'parent_field': 'parent_id',
        'order_field': 'order' if 'order' in s.get('properties', {}) else None,
        'children_endpoint': f"/{cls.__tablename__}/{{id}}/children",
        'roots_endpoint': f"/{cls.__tablename__}/roots",
        'has_children_field': 'has_children',
    }
    return s
```

The frontend reads `schema.tree` and knows: which field is the parent pointer, where to fetch children, and whether to show expand/collapse controls. No hardcoded conventions.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- ~0.5 day, single function |
| Impact | **High** -- bridges backend tree config to frontend |
| Risk | **Low** -- no-op for non-tree models |
| Timeline | **1 day** |

---

### P3: Auto-registered Tree Routes in `register_routes()`

> :wrench: **Proposition:** Extend `register_routes()` in `routes_fastapi.py` to auto-generate `/roots`, `/children`, `/descendants`, and `/move` endpoints for models with `__tree__ = True`.

**From the research:** Notion exposes `GET /blocks/{id}/children` (paginated, max 100). Directus auto-generates tree view endpoints when it detects self-referential O2M relations.

**In our system:** `register_routes()` in `routes_fastapi.py` (line 418) already does two-pass registration. Pass 1 handles static collection routes (e.g., `/products/comments`). Tree routes like `/blocks/roots` must also go in Pass 1 to avoid being shadowed by `/{table}/{id:int}`.

**The idea:**

Add a Pass 1.5 for tree models:

```
GET  /blocks/roots              -> root nodes (paginated)
GET  /blocks/{id}/children      -> direct children (paginated)
GET  /blocks/{id}/descendants   -> recursive subtree (depth-limited)
POST /blocks/{id}/move          -> reparent: {"parent_id": 5}
POST /blocks/{id}/reorder       -> reorder: {"position": 2}
```

The `/children` endpoint calls `TreeMixin.children_of()`. The `/descendants` endpoint uses the recursive CTE in `TreeMixin.subtree()`. The `/move` endpoint validates circular references before updating `parent_id`.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- ~2 days, route factories + auth integration |
| Impact | **High** -- complete REST API for tree operations |
| Risk | **Low** -- follows existing route registration patterns |
| Timeline | **3 days** (with auth, validation, tests) |

---

### P4: SQLite Recursive CTE for `subtree()` Queries

> :wrench: **Proposition:** Add a `subtree()` method to the storage layer that uses `WITH RECURSIVE` CTEs for depth-limited tree loading in a single query.

**From the research:** SQLite has supported `WITH RECURSIVE` since version 3.8.3 (2014). Adjacency list + recursive CTE handles subtree queries efficiently up to reasonable depths (~50 levels). Closure tables are overkill for typical document trees.

**In our system:** `sqlite_storage.py` uses parameterized queries throughout. The `list()` method (line 161) already supports `sql_filter` tuples. A CTE query fits naturally as a new method on the storage backend or as a classmethod on `TreeMixin` that calls into the storage layer.

**The idea:**

```sql
WITH RECURSIVE tree AS (
    SELECT id, parent_id, name, 0 AS depth
    FROM blocks WHERE id = ?
    UNION ALL
    SELECT b.id, b.parent_id, b.name, t.depth + 1
    FROM blocks b JOIN tree t ON b.parent_id = t.id
    WHERE t.depth < ?
)
SELECT * FROM tree ORDER BY depth, id;
```

This executes as a single query and returns all descendants up to `max_depth` levels deep. Combined with the existing `_connection()` pool context manager in `sqlite_storage.py`, it reuses pooled connections efficiently.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- ~2 days, CTE query + result hydration |
| Impact | **High** -- eliminates N+1 query problem for tree loading |
| Risk | **Low** -- SQLite CTE is well-tested, standard SQL |
| Timeline | **2 days** |

---

### P5: `has_children` as Denormalized Boolean with Auto-Maintenance

> :wrench: **Proposition:** When `__tree__ = True`, the `TreeMixin` auto-maintains a `has_children` boolean column by hooking into create/delete operations.

**From the research:** Notion's API always returns `has_children: boolean` on every block. This is the signal the UI uses to show expand arrows and trigger lazy loading. Computing it per-request adds a COUNT subquery; denormalizing it to a column makes reads instant.

**In our system:** `StorableMixin.create()` in `storable_mixin.py` (line 64) and `StorableMixin.delete()` (line 129) are the two operations that change a node's child count. `TreeMixin` can override (or wrap) these to update the parent's `has_children` flag.

**The idea:**

On create: if the new record has `parent_id`, execute `UPDATE blocks SET has_children = 1 WHERE id = ?` on the parent.

On delete: count remaining children of the orphaned parent, set `has_children = (count > 0)`.

Both updates happen inside the existing transaction context from `_connection()`, ensuring atomicity.

The `has_children` field is **not developer-declared** -- it is auto-injected by `TreeMixin.__init_subclass__` into the model's annotations, similar to how `StorableMixin` injects storage capabilities. The developer writes `__tree__ = True` and gets `has_children` for free.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- ~1.5 days, create/delete hooks + field injection |
| Impact | **Medium** -- instant `has_children` reads; enables lazy UI |
| Risk | **Medium** -- must handle edge cases (bulk delete, direct SQL) |
| Timeline | **2 days** |

---

### P6: `<ntx-tree>` Web Component for Recursive Rendering

> :wrench: **Proposition:** Create an `<ntx-tree>` component (or tree mode on `ntx-list`) that renders collapsible, lazy-loading tree views driven by the `schema.tree` metadata.

**From the research:** Web Components handle recursion natively -- a custom element can create instances of itself inside its own shadow DOM. The critical UX patterns are: lazy expansion on click, `grid-template-rows: 0fr -> 1fr` CSS animation for expand/collapse, and indent guides for depth visualization.

**In our system:** `ListElement` in `ListElement.js` already handles paginated child loading with a "Load More" button. `NTTItem.render()` already checks for `selfref` to apply `reply-indent` (line 617 of `ntx-item.js`). The widget registry pattern maps `ui.widget` names to renderers. A tree model specifies `__ui__ = {'renderer': {'list': 'ntx-tree'}}` and the framework uses the tree component automatically.

**The idea:**

`<ntx-tree>` extends `ListElement` but changes the rendering strategy:

1. `definedCallback()` calls `proto.call('READ', {roots: true, limit: 50})` instead of the flat paginated READ
2. `createChild()` stamps `<ntx-tree-item>` elements instead of `<ntx-item>`
3. `<ntx-tree-item>` extends `NTTElement` with expand/collapse, lazy child loading via the `/children` endpoint, and CSS indent at `calc(depth * 24px)`
4. Expand/collapse uses the `grid-template-rows` CSS technique (3 lines of CSS, works in all modern browsers)

```
Component
  +-- ListElement
  |     +-- NTTList (ntx-list)
  |     +-- NtxTree (ntx-tree)        <-- NEW
  +-- NTTElement
        +-- NTTItem (ntx-item)
        +-- NtxTreeItem (ntx-tree-item)  <-- NEW
```

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **High** -- ~5 days, two new components + CSS + lazy loading |
| Impact | **High** -- visual tree rendering from schema alone |
| Risk | **Medium** -- shadow DOM depth performance, drag-drop complexity |
| Timeline | **1-2 weeks** |

---

### P7: Tree-Picker Widget for `parent_id` Selection

> :wrench: **Proposition:** Add a `tree-picker` widget that renders a searchable tree dropdown for selecting parent nodes, replacing the raw number input for `selfref` fields.

**From the research:** Every tree-capable CMS (Directus, Payload) provides a parent-picker UI. A raw ID input is hostile UX.

**In our system:** The widget registry (`widgets/index.js`) maps `ui.widget` names to Widget instances. `form.js` (lines 275-276) currently renders `selfref` as `<input type="number">`. The tree-picker follows the established `UrlWidget` / `MarkdownWidget` pattern, lazy-loading the tree from `/roots` and `/children`. When `__tree__ = True`, the schema extension auto-sets this widget on `parent_id`.

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- ~3 days | Impact | **Medium** | Risk | **Low** | Timeline | **3-4 days** |

---

### P8: Drag-and-Drop Reordering via SortableJS

> :wrench: **Proposition:** Integrate SortableJS (7KB, framework-agnostic) for cross-level drag-and-drop in `<ntx-tree>`.

**From the research:** Every serious tree DnD uses a **flattened list with depth metadata** -- nested sortable contexts cannot support cross-level dragging.

**In our system:** SortableJS initializes on `.block-children` containers with a shared group. On drag end, the handler calls `/move` and `/reorder` endpoints with optimistic UI updates. This is a **Phase 2 enhancement** after `ntx-tree` exists.

| Dimension | Assessment |
|-----------|-----------|
| Effort | **High** -- ~4 days | Impact | **Medium** | Risk | **Medium** | Timeline | **1 week** |

---

### P9: Breadcrumb Navigation for Deep Trees

> :wrench: **Proposition:** Add `<ntx-breadcrumb>` for ancestor path display and `TreeMixin.ancestors()` for upward traversal.

**From the research:** Notion, file managers, and CMS tree views all provide breadcrumb navigation for wayfinding in deep structures.

**In our system:** Backend adds `TreeMixin.ancestors(max_depth=10)` that walks `parent_id` upward. Frontend `<ntx-breadcrumb node-id="5" model="Block">` renders clickable `Root / Section A / Current` path segments.

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- ~1.5 days | Impact | **Medium** | Risk | **Low** | Timeline | **2 days** |

---

## :building_construction: Proposition Map

```
                        HIGH IMPACT
                            |
         P1 TreeMixin  *---+---*  P3 Auto Routes
         P2 Schema Ext *   |   *  P4 Recursive CTE
                        |   |   |
    LOW EFFORT ---------+---+---+--------- HIGH EFFORT
                        |   |   |
         P5 has_children*   |   *  P6 ntx-tree
         P9 Breadcrumbs *   |   *  P8 Drag-Drop
                        |   |   |
         P7 Tree-Picker *---+---*
                            |
                        LOW IMPACT
```

| Category | Propositions | Total Effort |
|----------|-------------|--------------|
| **Quick Wins** | P1, P2, P5 | ~5 days |
| **Strategic Investments** | P3, P4, P6, P7 | ~12 days |
| **Moonshots** | P8, P9 | ~6 days |

---

## :warning: What NOT to Do

**1. Do not implement a closure table or materialized path storage model.**
The adjacency list (which `Ref['self']` already provides) combined with SQLite recursive CTEs handles all practical tree depths. Closure tables add O(depth) writes on every insert and O(subtree_size) deletes on every move. For an interactive editing framework where writes are frequent and trees are shallow (< 50 levels), this is pure overhead. The research confirms: Notion stores 200+ billion blocks with a simple adjacency list.

**2. Do not build a full block editor (Level 3).**
A Notion-style rich text block editor with inline editing, slash commands, and polymorphic block types is a 6-8 week project that would exceed the scope of a framework primitive. N3TX should provide the **tree data layer** and the **tree rendering component**, then let developers build block editors on top. The framework provides primitives, not opinions.

**3. Do not auto-detect tree models from `Ref['self']` without an explicit flag.**
The research (stack-relevance doc) correctly identifies this: implicit detection violates "transparent, not magical." A `Comment` model with `parent_id: Ref['self']` might be a flat threaded view, not a tree. The developer should explicitly opt in with `__tree__ = True`. Auto-detection looks clever but creates confusion when a selfref field is used for a non-tree purpose (e.g., "original_id" for versioning, "merged_into" for deduplication).

---

## :dart: Recommended Starting Point

**Start with P1 + P2 together** (TreeMixin + schema extension). These two form the backend foundation: the mixin adds tree query methods, the schema extension tells the frontend about the tree structure. Both follow existing patterns perfectly (AgentMixin, ViewableMixin) and require **zero changes to existing code** -- they are purely additive.

**Validation approach:**

1. Create a `Block` model in `examples/` with `__tree__ = True`
2. Verify that `TreeMixin` is injected via `__init_subclass__`
3. Verify that `Block.schema()` includes the `tree` key
4. Write a test that creates a 3-level tree, calls `root_nodes()`, `children_of()`, and `subtree()`
5. Verify the recursive CTE returns correct depth-limited results

If validation succeeds, proceed to P3 (auto routes) and P6 (ntx-tree component) in parallel -- one engineer on backend, one on frontend.

**Decision gate:** After P1-P3 are complete, the team should evaluate whether P6 (ntx-tree) is worth building in-house or whether exposing the tree API is sufficient for developers to build their own tree UIs. The answer depends on how many of our target use cases actually need a tree UI vs. just tree data operations.
