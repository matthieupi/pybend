# Notion-Style Blocks & `hasChildren`: Relevance to the N3TX Stack

**Research Focus:** How N3TX's current architecture maps to recursive block concepts, what gaps exist, and where a `hasChildren` property fits within the schema-driven framework.

**Audience:** Engineering leadership + implementation team

---

## 📊 Executive Summary

N3TX already has **more tree infrastructure than you might expect**. The `Ref['self']` type, `parent_id` convention, `selfref` schema type, and `_SelfRefMarker` detection in migrations all prove that self-referential models were anticipated in the original design. What's missing is the **orchestration layer** -- the framework doesn't help you *query* children, *reorder* siblings, *move* subtrees, or *render* trees. Today, those are developer responsibilities.

A `hasChildren` property is the **cheapest possible entry point** into Notion-style block support. It requires zero schema pipeline changes, zero storage changes, and zero migration changes. It can be a computed property on any model with `parent_id`, derived from a COUNT query or cached as a denormalized boolean. The real question is not "can we add `hasChildren`?" -- it's "should we build a `TreeMixin` that makes hierarchical models as effortless as `__storable__ = True` makes CRUD?"

> 💡 **Key Insight:** The N3TX stack already handles the **hard parts** (self-referential FK, schema type detection, SQL column creation, index auto-generation). What's missing is the **convenient parts** (children queries, ordering, tree traversal, recursive rendering). A `TreeMixin` would close this gap using the same injection pattern as `StorableMixin` and `AgentMixin`.

---

## 🔍 Current Architecture: How N3TX Models Hierarchy Today

### The Self-Referential Foundation: `Ref['self']`

N3TX already supports self-referential models through a specific mechanism. Here is how the Comment model in the example app uses it:

```python
# /workspace/examples/core/models/comment.py (line 42)
class Comment(ProtoModel):
    __tablename__: ClassVar[str] = 'comments'
    __storable__: ClassVar[bool] = True

    name: str = Field(min_length=1, max_length=500)
    description: TextareaField = Field(default='')
    parent_id: Optional[Ref['self']] = Field(default=None, description="Parent comment for nesting")
    likes: ListRef[Like] = Field(default=[], description="Likes on this comment")
```

The `Ref['self']` type annotation flows through **four distinct subsystems**:

```
[Model Definition]          [Schema Pipeline]          [Migration]              [Frontend]
parent_id: Ref['self']  --> proto_schema.base()    --> sqlite_migration.py   --> form.js
                            patches to                  creates INTEGER          renders as
                            {"type": "selfref"}         column + INDEX           number input
```

**Step 1 -- Type Resolution** (`/workspace/packages/n3tx-core/src/n3tx_core/utils/typer.py`, line 43):

```python
class Ref(Generic[T]):
    def __class_getitem__(cls, params):
        if params == 'self':
            return Annotated[int, _SelfRefMarker()]
        return super().__class_getitem__(params)
```

When `Ref['self']` is evaluated, it returns `Annotated[int, _SelfRefMarker()]` -- a plain integer with a metadata marker.

**Step 2 -- Schema Generation** (`/workspace/packages/n3tx-core/src/n3tx_core/models/proto_schema.py`, line 189):

```python
def base(cls) -> dict:
    schema = cls.model_json_schema(ref_template="#/$defs/{model}")
    if 'properties' in schema:
        for field_name, field_info in cls.model_fields.items():
            if _is_self_ref(field_info.annotation):
                schema['properties'][field_name] = {"type": "selfref"}
```

The `selfref` type appears in the JSON Schema output, signaling to the frontend that this field is a self-referential parent pointer.

**Step 3 -- Table Creation** (`/workspace/packages/n3tx-core/src/n3tx_core/storage/sqlite_migration.py`, lines 128-130):

```python
if _is_self_ref(field_type):
    columns.append(f"{field_name} INTEGER")
    continue
```

And crucially, an **index is automatically created** on selfref columns (line 196-197):

```python
for field_name, field_info in model_class.model_fields.items():
    if _is_self_ref(field_info.annotation):
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{field_name} ON {table_name} ({field_name})")
```

**Step 4 -- Frontend Rendering** (`/workspace/packages/n3tx-ui/src/n3tx_ui/static/generators/form.js`, lines 275-276 and 314-315):

```javascript
// Edit mode
} else if (type === 'selfref') {
    html.push(`<input type="number" ... placeholder="Parent ID (optional)">`);

// Display mode
} else if (type === 'selfref') {
    html.push(`<div data-value="${key}">${value ? `[Parent: #${value}]` : '(top-level)'}</div>`);
```

And in the item renderer (`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.js`, line 617):

```javascript
const isReply = this.value?.parent_id && this.schema?.properties?.parent_id?.type === 'selfref';
const indentClass = isReply ? ' reply-indent' : '';
```

> 💡 **Key Insight:** The framework already detects `selfref` at every layer -- type system, schema pipeline, migration engine, and frontend renderer. This is a **solid foundation**, but it's scattered across four subsystems with no unifying abstraction.

---

### The Parent-Child Relationship: `ListRef[T]` + `generate_join_model()`

N3TX models **one-to-many relationships** via `ListRef[T]` fields, which create **join tables**:

```python
class Product(ProtoModel):
    comments: ListRef[Comment] = Field(default=[])

# In main.py:
register_model(generate_join_model(Product, Comment), storage=storage_backend)
# Creates: ProductComment table with product_id FK column
```

This produces a **flat collection** -- Products have Comments, but Comments don't know about other Comments' tree structure. The `parent_id` field on Comment is an **unrelated mechanism** layered on top. Here's the data flow:

```
                  ┌─────────────────────┐
                  │    products table    │
                  │  id  │  name  │ ... │
                  └───┬──┘────────┘─────┘
                      │ 1:N via join table
              ┌───────▼──────────┐
              │ products_comments│
              │ id │ comment_id  │
              │    │ product_id  │
              └────┬─────────────┘
                   │
    ┌──────────────▼──────────────────┐
    │        comments table           │
    │ id │ name │ parent_id │ ...    │
    │ 1  │ "Hi" │ NULL      │        │  ← top-level
    │ 2  │ "Re" │ 1         │        │  ← reply to #1
    │ 3  │ "Me" │ 1         │        │  ← reply to #1
    │ 4  │ "OK" │ 2         │        │  ← reply to reply
    └─────────────────────────────────┘
```

The **join table** handles the Product-Comment relationship. The **parent_id** column handles the Comment-Comment nesting. These are **two orthogonal mechanisms** that happen to coexist.

### What Works Today

| Capability | Status | Mechanism |
|-----------|--------|-----------|
| Self-referential FK column | ✅ Works | `Ref['self']` → `_SelfRefMarker` → INTEGER column |
| Auto-index on parent_id | ✅ Works | `sqlite_migration.py` detects `_is_self_ref()` |
| Schema type for selfref | ✅ Works | `proto_schema.base()` emits `{"type": "selfref"}` |
| Frontend display of parent_id | ✅ Works | `form.js` renders `[Parent: #N]` or `(top-level)` |
| Reply indentation in UI | ✅ Works | `ntx-item.js` adds `reply-indent` CSS class |
| Creating a reply | ✅ Works | `Comment.reply()` custom method sets `parent_id` |
| Querying children by parent | ❌ Manual | Developer writes SQL filter: `parent_id = ?` |
| Recursive tree loading | ❌ Missing | No framework support for depth-limited tree queries |
| Ordering siblings | ❌ Missing | No `order` / `position` field convention |
| Moving a node to new parent | ❌ Missing | No `move()` method; manual UPDATE |
| `hasChildren` flag | ❌ Missing | No computed or denormalized boolean |
| Tree rendering in frontend | ❌ Partial | Only one-level indent via CSS; no recursive rendering |

---

## 📊 Gap Analysis: What `hasChildren` Needs from Each Layer

### Gap 1: Schema Pipeline -- Minimal Changes Needed

The schema pipeline (`/workspace/packages/n3tx-core/src/n3tx_core/models/proto_schema.py`) currently has **7 stages** in the default pipeline:

```
base → strip_hidden → methods → defs → access → ui → metadata
```

A `hasChildren` property does **not require a new pipeline stage**. It can surface in three ways:

**Option A: Computed on the model** (zero pipeline change)
```python
class Block(ProtoModel):
    parent_id: Optional[Ref['self']] = Field(default=None)
    has_children: bool = Field(default=False)  # denormalized, updated on child create/delete
```

This is a regular field. The schema pipeline emits it as `{"type": "boolean"}`. No changes needed.

**Option B: Schema extension for tree models** (plugin-style)
```python
@schema_extension(after='ui')
def tree(cls, s: dict) -> dict:
    """Add tree metadata for models with __tree__ = True."""
    if not getattr(cls, '__tree__', False):
        return s
    s['tree'] = {
        'parent_field': 'parent_id',
        'order_field': getattr(cls, '__tree_order__', None),
        'children_endpoint': f"/{cls.__tablename__}/{{id}}/children",
    }
    return s
```

This follows the exact pattern used by `ViewableMixin` (`/workspace/packages/n3tx-ui/src/n3tx_ui/mixin.py`, line 28) and `AgentMixin` schema extension (`schema_ext.py`). The `@schema_extension` decorator inserts relative to named stages -- **zero modification to existing pipeline code**.

**Option C: Implicit detection via `Ref['self']`** (automatic, no flag)

The pipeline already detects `selfref` fields in `base()`. It could automatically add `tree` metadata whenever any property has `type: selfref`:

```python
# Inside existing proto_schema.ui() or a new tree() stage
selfref_fields = [k for k, v in s.get('properties', {}).items() if v.get('type') == 'selfref']
if selfref_fields:
    s.setdefault('tree', {})['parent_field'] = selfref_fields[0]
```

> 💡 **Recommendation:** Option B (explicit `__tree__` flag with `@schema_extension`) is most consistent with N3TX philosophy. It's opt-in, composable, and follows the `StorableMixin` / `AgentMixin` pattern. Option C is clever but violates "transparent, not magical."

### Gap 2: Storage Layer -- `parent_id` Already Works; Children Queries Don't

The SQLite storage layer (`/workspace/packages/n3tx-core/src/n3tx_core/storage/sqlite_storage.py`) supports `parent_id` as a plain INTEGER column. But there is **no API for querying children by parent**. Consider what a developer needs to do today:

```python
# To get children of comment #5, developer must write:
children = Comment.list(sql_filter=("parent_id = ?", [5]))
```

This works, but it's:
- **Not discoverable** -- nothing in the model definition advertises this capability
- **Not recursive** -- no depth-limited tree loading
- **Not ordered** -- no sibling ordering
- **Not cached** -- `hasChildren` must be computed every time

A `TreeMixin` would add these methods:

```python
class TreeMixin:
    @classmethod
    def children_of(cls, parent_id: int, limit=None, offset=None):
        """Get direct children of a node."""
        return cls.list(sql_filter=("parent_id = ?", [parent_id]), limit=limit, offset=offset)

    @classmethod
    def root_nodes(cls, limit=None, offset=None):
        """Get all top-level nodes (parent_id IS NULL)."""
        return cls.list(sql_filter=("parent_id IS NULL", []), limit=limit, offset=offset)

    def descendants(self, max_depth=3):
        """Recursive tree loading with depth limit."""
        # Uses recursive CTE in SQLite (supported since 3.8.3, 2014)
        ...

    def move(self, new_parent_id: int):
        """Reparent this node."""
        self.update(self.id, {'parent_id': new_parent_id})
```

**SQLite recursive CTE support** is the key enabler here. SQLite has supported `WITH RECURSIVE` since version 3.8.3 (2014). A tree query looks like:

```sql
WITH RECURSIVE tree AS (
    SELECT id, parent_id, name, 0 AS depth
    FROM blocks WHERE id = ?
    UNION ALL
    SELECT b.id, b.parent_id, b.name, t.depth + 1
    FROM blocks b JOIN tree t ON b.parent_id = t.id
    WHERE t.depth < ?  -- max_depth limit
)
SELECT * FROM tree ORDER BY depth, id;
```

This is **efficient** for the adjacency list model (which `parent_id` implements) and doesn't require any storage schema changes -- just new query methods on the storage backend.

### Gap 3: Route Layer -- New Endpoints Needed

The route layer (`/workspace/packages/n3tx-core/src/n3tx_core/api/routes_fastapi.py`) currently generates:

```
GET  /{tablename}           → list all
POST /{tablename}           → create
GET  /{tablename}/{id}      → get one
PUT  /{tablename}/{id}      → update
DELETE /{tablename}/{id}    → delete
GET  /{ClassName}            → schema
```

For tree models, we'd need additional routes:

| Route | Method | Purpose |
|-------|--------|---------|
| `/{tablename}/{id}/children` | GET | List direct children (paginated) |
| `/{tablename}/{id}/descendants` | GET | Recursive subtree (depth-limited) |
| `/{tablename}/roots` | GET | Top-level nodes only |
| `/{tablename}/{id}/move` | POST | Reparent a node |
| `/{tablename}/reorder` | POST | Reorder siblings |

These could be registered automatically for any model with `__tree__ = True`, mirroring how `register_routes()` currently auto-generates CRUD routes for any model with `__storable__ = True`.

The `register_routes()` function in `routes_fastapi.py` (line 418) already does **two-pass registration** to avoid path conflicts. Tree routes would go in **Pass 1** (static segments like `/blocks/roots`) alongside collection routes.

### Gap 4: Frontend -- From Flat Lists to Recursive Trees

The frontend currently renders entities in **flat collections**. The key components:

| Component | File | Current behavior | Tree gap |
|-----------|------|-----------------|----------|
| `ntx-list` | `ntx-list.js` | Flat grid of items | No tree view mode |
| `ntx-item` | `ntx-item.js` | Single entity card | Only CSS indent for `reply-indent` |
| `ListElement` | `ListElement.js` | Base collection class | No recursive child loading |
| `form.js` | `form.js` | Schema-driven forms | Shows `parent_id` as number input |
| `NTT.js` | `NTT.js` | Entity registry + CRUD | No `children` query method |

The `ntx-item.js` already has **one level of tree awareness** (lines 617-619):

```javascript
const isReply = this.value?.parent_id && this.schema?.properties?.parent_id?.type === 'selfref';
const indentClass = isReply ? ' reply-indent' : '';
```

But this is **hardcoded to one level** and only applies CSS indentation. A proper tree renderer would need:

1. **`ntx-tree` component** (or tree mode on `ntx-list`) that renders a collapsible tree
2. **Lazy child loading** triggered by expanding a `hasChildren: true` node
3. **Drag-and-drop reordering** for sibling repositioning and reparenting
4. **Depth-aware indentation** beyond one level

The `ListElement` base class (`/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js`) reads `schema.ui.renderer.list` to determine which component tag to use (line 177-181). A tree model could specify:

```python
__ui__ = {
    'renderer': {'item': 'ntx-item', 'list': 'ntx-tree'},
}
```

And the framework would automatically use the tree component for rendering.

### Gap 5: `register_mixin()` -- Ready for `TreeMixin`

The mixin injection system (`/workspace/packages/n3tx-core/src/n3tx_core/models/proto_model.py`, lines 25-44) is **explicitly designed** for this use case:

```python
_mixin_registry: list[tuple] = []  # (flag, mixin_cls, also_if)

def register_mixin(flag: str, mixin_cls: type, *, also_if: list[str] = None) -> None:
    _mixin_registry.append((flag, mixin_cls, also_if or []))
```

A `TreeMixin` would register exactly like `AgentMixin`:

```python
# In n3tx_core/models/tree_mixin.py (or a separate n3tx-tree package)
from n3tx_core.models.proto_model import register_mixin

class TreeMixin:
    """Adds tree operations to any model with parent_id: Ref['self']."""

    @classmethod
    def children_of(cls, parent_id, **kwargs): ...

    @classmethod
    def root_nodes(cls, **kwargs): ...

    def move(self, new_parent_id): ...

    @property
    def has_children(self): ...

register_mixin('__tree__', TreeMixin)
```

The `__init_subclass__` hook in ProtoModel (lines 112-119) would inject it:

```python
# Existing code in proto_model.py (unchanged):
for flag, mixin_cls, also_if in _mixin_registry:
    triggered = getattr(cls, flag, False)
    if not triggered and also_if:
        triggered = any(getattr(cls, alt, None) for alt in also_if)
        if triggered:
            setattr(cls, flag, True)
    if triggered and not issubclass(cls, mixin_cls):
        cls.__bases__ = (mixin_cls,) + cls.__bases__
```

Usage would be:

```python
class Block(ProtoModel):
    __tablename__ = 'blocks'
    __storable__ = True
    __tree__ = True  # ← triggers TreeMixin injection

    name: str
    content: str = ''
    type: str = 'text'
    parent_id: Optional[Ref['self']] = Field(default=None)
    order: int = Field(default=0)
```

---

## ⚡ Three Integration Levels

### Level 1: Minimal -- `hasChildren` as Schema Convention (effort: ~2 days)

**What it provides:** A computed boolean that the frontend can use for lazy loading indicators.

**Changes required:**

| Layer | Change | Effort |
|-------|--------|--------|
| Schema pipeline | None -- `has_children` is a regular `bool` field | 0 |
| Storage | Add `has_children BOOLEAN DEFAULT 0` column | Trivial |
| Routes | None -- standard CRUD covers it | 0 |
| Frontend | Read `has_children` from entity data; show expand icon | Small |
| Models | Developer adds the field + denormalization logic | Manual |

**Example model:**

```python
class Block(ProtoModel):
    __storable__ = True
    __tablename__ = 'blocks'

    content: str = ''
    type: str = 'text'
    parent_id: Optional[Ref['self']] = Field(default=None)
    has_children: bool = Field(default=False)

    @expose_route('/children', methods=['GET'])
    def get_children(self) -> list:
        return Block.list(sql_filter=("parent_id = ?", [self.id]))
```

**Pros / Cons:**

- ✅ Zero framework changes
- ✅ Fully consistent with current architecture
- ✅ Developer retains full control
- ❌ Developer must manually maintain `has_children` (update on create/delete)
- ❌ No ordering, no tree traversal, no move operation
- ❌ Every project reinvents the tree plumbing

### Level 2: Medium -- `TreeMixin` via `register_mixin()` (effort: ~2 weeks)

**What it provides:** Automatic tree operations injected via `__tree__ = True`, following the same pattern as `StorableMixin` and `AgentMixin`.

**Changes required:**

| Layer | Change | Effort |
|-------|--------|--------|
| New: `tree_mixin.py` | `TreeMixin` class with children/roots/move/reorder | Medium |
| Schema pipeline | `@schema_extension` adds `tree` key to schema | Small |
| Storage | New methods: `children_of()`, `root_nodes()`, `descendants()` via recursive CTE | Medium |
| Routes | Auto-register `/children`, `/roots`, `/move`, `/reorder` for tree models | Medium |
| Frontend | New `ntx-tree` component or tree mode on `ntx-list` | Medium |
| Models | Developer adds `__tree__ = True` + `parent_id: Ref['self']` | Trivial |

**`TreeMixin` API surface:**

```python
class TreeMixin:
    """Injected when __tree__ = True on a ProtoModel subclass."""

    # --- Class methods ---
    @classmethod
    def children_of(cls, parent_id: int, limit=20, offset=0) -> dict:
        """Direct children of a node, paginated. Returns {data, meta}."""

    @classmethod
    def root_nodes(cls, limit=20, offset=0) -> dict:
        """Top-level nodes (parent_id IS NULL), paginated."""

    @classmethod
    def subtree(cls, root_id: int, max_depth: int = 3) -> list:
        """Recursive descendants via WITH RECURSIVE CTE."""

    # --- Instance methods ---
    def move(self, new_parent_id: int | None) -> 'Self':
        """Reparent this node. Updates has_children on old/new parents."""

    def reorder(self, position: int) -> None:
        """Set this node's order among siblings."""

    @property
    def has_children(self) -> bool:
        """Computed or denormalized child existence flag."""
```

**Schema output for a tree model:**

```json
{
  "$schema": "http://localhost:5000/Schema",
  "$id": "http://localhost:5000/Block",
  "properties": {
    "parent_id": {"type": "selfref"},
    "order": {"type": "integer"},
    "has_children": {"type": "boolean"}
  },
  "tree": {
    "parent_field": "parent_id",
    "order_field": "order",
    "children_endpoint": "/blocks/{id}/children",
    "roots_endpoint": "/blocks/roots"
  }
}
```

**Auto-generated routes for tree models:**

```
GET  /blocks/roots              → root nodes (paginated)
GET  /blocks/{id}/children      → direct children (paginated)
GET  /blocks/{id}/descendants   → recursive subtree (depth-limited)
POST /blocks/{id}/move          → reparent: {"parent_id": 5}
POST /blocks/{id}/reorder       → reorder: {"position": 2}
```

**Pros / Cons:**

- ✅ "Zero to working" -- `__tree__ = True` gives you everything
- ✅ Consistent with `StorableMixin`, `AgentMixin`, `ViewableMixin` patterns
- ✅ Recursive CTE handles depth-limited queries efficiently
- ✅ Schema carries tree metadata -- frontend adapts automatically
- ✅ `has_children` maintained automatically by mixin's create/delete hooks
- ❌ Adjacency list only -- no closure table or materialized path
- ❌ Deep tree queries (depth > 10) still require multiple queries or CTE limits
- ❌ No cross-type blocks (all children must be same model)

### Level 3: Full -- First-Class `Block` Base Model + Type Registry (effort: ~6-8 weeks)

**What it provides:** A complete Notion-style block system where blocks are the universal content primitive. Every entity IS a block. Blocks can contain blocks of any type.

**Changes required:**

| Layer | Change | Effort |
|-------|--------|--------|
| New: `BlockModel` base class | Extends `ProtoModel` with block semantics | Large |
| Block type registry | Maps block types to renderers (text, heading, list, image, etc.) | Large |
| Schema pipeline | Polymorphic block $defs with discriminator | Large |
| Storage | Closure table or materialized path for efficient tree queries | Large |
| Routes | Full block CRUD + append/move/reorder + transaction-based operations | Large |
| Frontend | Block editor with inline editing, drag-and-drop, slash commands | Very Large |
| Serialization | Block tree → flat list (Notion-style) or nested JSON | Medium |

**This level is significantly more ambitious** and approaches a full block editor implementation. It goes beyond "tree support" into "content editing paradigm."

**Pros / Cons:**

- ✅ Maximum power -- reproduces Notion's content model
- ✅ Polymorphic blocks enable rich content types
- ✅ Could be N3TX's killer feature for content-heavy applications
- ❌ 10-20x the implementation effort of Level 2
- ❌ Risk of over-engineering for most use cases
- ❌ Block editors are notoriously complex (see: ProseMirror, Slate, Editor.js)
- ❌ Diverges from "the model is the app" -- blocks become a meta-layer above models

---

## 🏢 Competitive Landscape: How Other Schema-Driven Frameworks Handle Trees

| Framework | Tree Support | Mechanism | Self-Referential | `hasChildren` Equivalent |
|-----------|-------------|-----------|-----------------|-------------------------|
| **[Directus](https://www.restack.io/docs/directus-knowledge-directus-tree-structure)** | Built-in Tree View | O2M self-relation + tree view interface | ✅ Native | ✅ Implicit via children count |
| **[Strapi](https://github.com/strapi/strapi/issues/6329)** | Plugin only | Self-relation + [strapi-plugin-tree](https://github.com/4levels/strapi-plugin-tree) (nested sets) | ✅ Via relation | ❌ Plugin-dependent |
| **[Payload CMS](https://payloadcms.com/docs/plugins/nested-docs)** | Official plugin | `nested-docs` plugin: auto parent field + breadcrumbs | ✅ Plugin-managed | ✅ Via breadcrumbs array |
| **[KeystoneJS](https://keystonejs.com/docs/fields/relationship)** | Manual | Standard relationship field pointing to same list | ✅ Via relationship | ❌ Manual |
| **[Notion API](https://developers.notion.com/reference/get-block-children)** | Core concept | Block model with `has_children` + `/children` endpoint | ✅ Everything is a block | ✅ `has_children: boolean` |
| **N3TX (today)** | Partial | `Ref['self']` + manual queries | ✅ Native type | ❌ Not present |

> 💡 **Key Insight:** Directus and Payload CMS are the closest competitors in approach. Directus detects self-referential O2M and auto-offers a tree view interface. Payload's `nested-docs` plugin auto-adds `parent` and `breadcrumbs` fields. Both validate that **mixin-injected tree support is the right abstraction level** for schema-driven frameworks.

### Notion's Block Model as Reference

The [Notion API](https://developers.notion.com/reference/get-block-children) uses a specific pattern worth studying:

1. **Every block has `has_children: boolean`** -- set by the server, not the client
2. **Children are fetched lazily** via `GET /blocks/{id}/children` (paginated, max 100)
3. **Recursive fetching is client-side** -- the API returns one level; the client recurses on `has_children: true`
4. **Block types are discriminated** via a `type` field (paragraph, heading_1, bulleted_list_item, etc.)
5. **Ordering is implicit** in the array order returned by the children endpoint

This maps cleanly to N3TX's architecture:

```
Notion Concept          N3TX Equivalent
─────────────          ────────────────
Block                  ProtoModel with __tree__ = True
has_children           TreeMixin.has_children (computed/denormalized)
/blocks/{id}/children  Auto-route from tree model registration
block.type             Model class name or __discriminator__ field
parent_id              Ref['self'] (already exists)
```

---

## 🔍 Self-Referential Models: Technical Deep Dive

### Pydantic V2 and Recursive Schemas

Pydantic V2 [supports self-referential models](https://docs.pydantic.dev/latest/concepts/forward_annotations/) natively via forward annotations. The pattern:

```python
from __future__ import annotations
from pydantic import BaseModel

class TreeNode(BaseModel):
    name: str
    children: list[TreeNode] = []

TreeNode.model_rebuild()  # Resolves forward references
```

This generates a valid JSON Schema with recursive `$ref`:

```json
{
  "$defs": {
    "TreeNode": {
      "properties": {
        "name": {"type": "string"},
        "children": {
          "items": {"$ref": "#/$defs/TreeNode"},
          "type": "array"
        }
      }
    }
  }
}
```

**N3TX's approach is different** -- it uses `Ref['self']` as a plain integer FK rather than embedding full child objects. This is the right choice for a database-backed system (avoids infinite recursion in serialization), but it means the JSON Schema doesn't carry the recursive structure. The `selfref` type is a **custom extension** that signals "this is a same-table FK" without trying to embed child schemas.

### JSON Schema Recursive $ref Support

JSON Schema has evolved its recursive support across drafts:

| Draft | Mechanism | Complexity |
|-------|-----------|-----------|
| Draft-07 | `$ref` pointing to `#` or `#/definitions/X` | Basic; no extension support |
| [2019-09](https://www.learnjsonschema.com/2019-09/core/recursiveref/) | `$recursiveRef` + `$recursiveAnchor` | Enables extensible recursive schemas |
| 2020-12 | `$dynamicRef` + `$dynamicAnchor` | Replaces $recursiveRef; more flexible |

N3TX currently uses draft-style `$ref` within `$defs`. For tree models, the schema could use [recursive schemas](https://tour.json-schema.org/content/06-Combining-Subschemas/07-Recursive-Schemas) to express the tree structure:

```json
{
  "type": "object",
  "properties": {
    "parent_id": {"type": "selfref"},
    "children": {
      "type": "array",
      "items": {"$ref": "#"}
    }
  }
}
```

However, this is **informational only** in N3TX's case -- the actual children are lazy-loaded via API calls, not embedded in the schema. The `tree` metadata object (from the schema extension) is more useful than recursive `$ref` for N3TX's frontend.

### SQLite Tree Storage: Adjacency List vs. Alternatives

N3TX uses SQLite as its primary storage backend. Here's how tree storage strategies compare:

| Strategy | Read (children) | Read (subtree) | Write (insert) | Write (move) | Storage overhead | SQLite support |
|----------|----------------|----------------|----------------|-------------|-----------------|---------------|
| **Adjacency List** (`parent_id`) | O(1) query | Recursive CTE | O(1) | O(1) | 1 column | ✅ Native |
| **[Closure Table](https://charlesleifer.com/blog/querying-tree-structures-in-sqlite-using-python-and-the-transitive-closure-extension/)** | O(1) query | O(1) query | O(depth) inserts | O(subtree) deletes + inserts | O(n*depth) rows | ✅ Via extension or manual |
| **[Materialized Path](https://bojanz.wordpress.com/2014/04/25/storing-hierarchical-data-materialized-path/)** | LIKE query | LIKE prefix | O(1) | O(subtree) updates | 1 TEXT column | ✅ Native |
| **Nested Sets** (lft/rgt) | Range query | Range query | O(n) renumber | O(n) renumber | 2 columns | ✅ Native |

**Recommendation: Adjacency List** (what N3TX already has via `parent_id`).

Rationale:
- **Simplest** -- zero additional tables or columns (already exists)
- **Write-friendly** -- O(1) inserts and moves (important for interactive editing)
- **SQLite recursive CTE** handles subtree queries efficiently up to reasonable depths
- **Closure tables** are overkill for typical document trees (10-50 levels of nesting)
- **Materialized paths** are fragile under concurrent writes

The only addition needed is an `order` column for sibling ordering. This is a standard INTEGER column that the `TreeMixin` would manage.

---

## ⚠️ Risks and Gotchas

### 1. N+1 Query Problem for Tree Rendering

Loading a tree one level at a time creates N+1 queries (one for each expanded node). Solutions:

- **Batch children loading**: `GET /blocks/{id}/descendants?depth=3` uses a single recursive CTE
- **`populate` parameter**: N3TX already supports `?populate=children&depth=2` on list endpoints
- **Frontend caching**: DynamicClass instances persist in the NTT registry -- repeated expands hit cache

### 2. Circular Parent References

A node can't be its own ancestor. The `move()` method must validate:

```python
def move(self, new_parent_id):
    if new_parent_id == self.id:
        raise ValueError("Cannot be own parent")
    # Check ancestors to prevent cycles
    ancestors = self.ancestors()
    if new_parent_id in [a.id for a in ancestors]:
        raise ValueError("Circular reference detected")
```

### 3. `has_children` Consistency

If `has_children` is denormalized (stored as a column), it must be updated atomically with child create/delete operations. Options:

- **On create**: `UPDATE blocks SET has_children = 1 WHERE id = ?` (parent)
- **On delete**: `UPDATE blocks SET has_children = (SELECT COUNT(*) > 0 FROM blocks WHERE parent_id = ?) WHERE id = ?`
- **Alternative**: Compute `has_children` at query time via subquery or JOIN -- avoids consistency issues at the cost of slightly slower reads

### 4. Schema Ownership and `ListRef['self']`

Today, `ListRef[T]` requires `T` to be a **different model class**. Self-referential collections (`ListRef['self']` or `ListRef[Block]`) would need the `generate_join_model()` function to handle same-table references. This is currently untested and likely requires:

```python
# In proto_model.py, generate_join_model()
# Today: asserts owner_cls != ref_model
# Would need: handle case where owner_cls IS ref_model
```

However, for tree models, `ListRef['self']` is **not the right abstraction**. Children are queried via `parent_id`, not via a join table. The `TreeMixin` would add a `children_of()` classmethod instead.

### 5. Frontend `selfref` vs. Tree-Aware Rendering

The frontend currently treats `selfref` fields as **simple number inputs** in edit mode. For tree models, the parent selector should be a **tree picker** (searchable dropdown showing the tree structure), not a raw number. This requires a new widget:

```python
parent_id: Optional[Ref['self']] = Field(
    default=None,
    json_schema_extra={'ui': {'widget': 'tree-picker'}}
)
```

---

## 💡 Consistency with N3TX Design Principles

| Principle | Assessment | Notes |
|-----------|-----------|-------|
| **"The model is the app"** | ✅ Fits perfectly | `__tree__ = True` on the model drives everything |
| **"Zero to working, then customize"** | ✅ Level 2 achieves this | One flag → tree routes + schema + rendering |
| **"Primitives, not opinions"** | ✅ TreeMixin is a primitive | It provides operations; developers own presentation |
| **"Backend is authoritative"** | ✅ Schema carries tree config | Frontend reads `tree` from schema, adapts rendering |
| **"Transparent, not magical"** | ⚠️ Needs care | `has_children` auto-update must be traceable |
| **"Modular where it simplifies"** | ✅ TreeMixin is opt-in | No impact on models without `__tree__` |

The `TreeMixin` approach is **architecturally identical** to how N3TX already handles:

```
StorableMixin:  __storable__ = True  → CRUD operations + DB table
AgentMixin:     __agent__ = True     → LLM reasoning + tool discovery
ViewableMixin:  __ui__ = {...}       → Frontend rendering config
TreeMixin:      __tree__ = True      → Tree operations + children routes  ← NEW
```

The pattern is proven. The machinery exists. The only question is priority.

---

## 📊 Implementation Roadmap

### Phase 1: Minimal Foundation (Level 1) -- Sprint 1

| Task | Files Affected | Effort |
|------|---------------|--------|
| Document `Ref['self']` + `parent_id` convention | `docs/CORE.md`, `CLAUDE.md` | 1 day |
| Add `has_children` example to Comment model | `examples/core/models/comment.py` | 0.5 day |
| Frontend: expand/collapse icon when `has_children` is true | `ntx-item.js`, `ntx-item.css` | 1 day |

### Phase 2: TreeMixin (Level 2) -- Sprints 2-3

| Task | New/Changed Files | Effort |
|------|------------------|--------|
| `TreeMixin` class + `register_mixin('__tree__')` | `n3tx_core/models/tree_mixin.py` | 3 days |
| `@schema_extension(after='ui')` for tree metadata | `n3tx_core/models/tree_schema.py` | 1 day |
| SQLite recursive CTE for `descendants()` | `n3tx_core/storage/sqlite_storage.py` | 2 days |
| Auto-route registration for tree endpoints | `n3tx_core/api/routes_fastapi.py` | 2 days |
| `ntx-tree` Web Component | `n3tx_ui/static/components/ntx-tree.js` | 3 days |
| Tree picker widget for `parent_id` | `n3tx_ui/static/widgets/tree-picker.js` | 2 days |
| Tests: tree CRUD, CTE queries, route generation | `tests/unit/test_tree_*.py` | 2 days |

### Phase 3: Polish & Block Foundation (Level 2.5) -- Sprint 4

| Task | Files | Effort |
|------|-------|--------|
| Drag-and-drop reordering in `ntx-tree` | `ntx-tree.js` | 3 days |
| `BlockModel` example (text, heading, list block types) | `examples/blocks/` | 2 days |
| Polymorphic block rendering via `__discriminator__` | Schema pipeline | 3 days |

---

## 🔗 Sources

- [Notion API: Retrieve Block Children](https://developers.notion.com/reference/get-block-children)
- [Notion API: Working with Page Content](https://developers.notion.com/docs/working-with-page-content)
- [Pydantic: Managing Recursive Models](https://www.kevsrobots.com/learn/pydantic/06_recursive_models.html)
- [Pydantic: Forward Annotations](https://docs.pydantic.dev/latest/concepts/forward_annotations/)
- [Pydantic Recursive Models in FastAPI](https://www.getorchestra.io/guides/pydantic-recursive-models-in-fastapi-a-detailed-tutorial)
- [JSON Schema: Recursive Schemas](https://tour.json-schema.org/content/06-Combining-Subschemas/07-Recursive-Schemas)
- [JSON Schema: $recursiveRef (2019-09)](https://www.learnjsonschema.com/2019-09/core/recursiveref/)
- [Directus Tree Structure Overview](https://www.restack.io/docs/directus-knowledge-directus-tree-structure)
- [Directus Tree View Discussion #3054](https://github.com/directus/directus/discussions/3054)
- [Strapi: Hierarchical Collection Issue #6329](https://github.com/strapi/strapi/issues/6329)
- [strapi-plugin-tree: Draggable Nested Sets](https://github.com/4levels/strapi-plugin-tree)
- [Payload CMS: Nested Docs Plugin](https://payloadcms.com/docs/plugins/nested-docs)
- [Payload CMS: Tree View RFC #13982](https://github.com/payloadcms/payload/discussions/13982)
- [KeystoneJS: Relationship Fields](https://keystonejs.com/docs/fields/relationship)
- [SQLite: Querying Tree Structures with Transitive Closure Extension](https://charlesleifer.com/blog/querying-tree-structures-in-sqlite-using-python-and-the-transitive-closure-extension/)
- [Materialized Path for Hierarchical Data](https://bojanz.wordpress.com/2014/04/25/storing-hierarchical-data-materialized-path/)
- [Hierarchical Models in PostgreSQL (Adjacency vs Closure vs Path)](https://www.ackee.agency/blog/hierarchical-models-in-postgresql)
- [Percona: Moving Subtrees in Closure Table Hierarchies](https://www.percona.com/blog/moving-subtrees-in-closure-table/)
