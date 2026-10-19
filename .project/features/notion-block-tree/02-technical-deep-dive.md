# Recursive Block Data Models: Technical Deep Dive

**Tree Architectures, Storage Patterns, Schema Design, and Block Type Systems**

*Research prepared for N3TX engineering leadership -- March 2026*

---

## Executive Summary

> **Key Insight:** Notion stores **200+ billion blocks** in sharded PostgreSQL using a simple adjacency-list model with a `content` array for child ordering. The "everything is a block" pattern is deceptively simple in concept but has deep implications for storage, querying, schema design, and collaboration. This document dissects **how** tree-structured block data should be stored, queried, ordered, typed, and evolved -- with concrete SQL, JSON Schema, benchmarks, and architecture trade-offs relevant to N3TX's schema-driven approach.

The core question: **can a `hasChildren` property on entities reproduce Notion's block structure** inside a schema-driven framework? The short answer is yes, but the real engineering is in the five systems that surround it: tree storage, child ordering, polymorphic block types, recursive schema definitions, and collaborative editing. This document covers all five.

---

## Table of Contents

1. [How Notion Actually Stores Blocks](#-how-notion-actually-stores-blocks)
2. [Tree Storage Patterns in SQL](#-tree-storage-patterns-in-sql)
3. [Block Ordering Strategies](#-block-ordering-strategies)
4. [Recursive Schema Design](#-recursive-schema-design-json-schema)
5. [Polymorphic Block Type Systems](#-polymorphic-block-type-systems)
6. [Block Type Registries in Editors](#-block-type-registries-prosemirror-tiptap-blocknote)
7. [Performance and Scale](#-performance-and-scale)
8. [Undo/Redo and Collaboration](#-undoredo-and-collaboration)
9. [Design Recommendations for N3TX](#-design-recommendations-for-n3tx)
10. [Sources](#-sources)

---

## :mag: How Notion Actually Stores Blocks

**The "so what?":** Notion proved that a single data model -- everything is a block -- can scale to 200 billion rows. Their architecture is simpler than you'd expect, and that simplicity is the point.

### The Block Entity

Every piece of content in Notion -- a paragraph, an image, a page, a row in a database -- is a **block**. Each block has [four essential attributes](https://www.notion.com/blog/data-model-behind-notion):

| Attribute | Type | Purpose |
|-----------|------|---------|
| **id** | UUID v4 | Unique identifier (visible in page URLs) |
| **type** | enum | Determines rendering and property interpretation |
| **properties** | JSON | Type-specific data (`title` for text, custom props for DB pages) |
| **content** | ordered array of UUIDs | Child block IDs -- the "downward pointers" |
| **parent** | UUID | Parent block ID -- the "upward pointer" (used for permissions) |

```
                    [Page Block]
                    type: "page"
                    content: [A, B, C]
                        |
            +-----------+-----------+
            |           |           |
        [Block A]   [Block B]   [Block C]
        type: "h1"  type: "p"   type: "toggle"
        content: [] content: [] content: [D, E]
                                    |
                                +---+---+
                                |       |
                            [Block D] [Block E]
                            type: "p" type: "todo"
```

### Storage at Scale

Notion's PostgreSQL infrastructure, as of their [2023 sharding blog post](https://www.notion.com/blog/sharding-postgres-at-notion):

| Metric | Value |
|--------|-------|
| Total blocks | **200+ billion** rows |
| Physical DB servers | **96** |
| Logical shards per server | **5** (PostgreSQL schemas) |
| Total logical shards | **480** |
| Partition key | **Workspace ID** |
| Connection pooling | PgBouncer |
| Data volume | Hundreds of terabytes (compressed) |

The sharding key is **workspace ID**, not block ID. This ensures all blocks within a workspace live on the same shard, preserving transactional consistency. All tables reachable from the block table via foreign keys are co-located on the same shard ([source](https://www.notion.com/blog/sharding-postgres-at-notion)).

> **Key Insight:** Notion uses a simple **adjacency list** pattern -- each block stores its `parent` ID. The `content` array (an ordered list of child IDs) serves double duty as both the tree structure and the ordering mechanism. No nested sets, no closure tables, no materialized paths.

### The Content Array as Ordering

Notion does **not** use fractional indexing or a separate `position` column. The `content` field is an **ordered array of block IDs** stored directly on the parent block. Reordering means mutating this array. This is conceptually the simplest approach and works because:

1. Operations are transaction-scoped per workspace (single shard)
2. The array is small per block (tens to low hundreds of children)
3. Writes are expressed as **operations on records**, batched into transactions

The client sends operations to a `/saveTransactions` endpoint that:
1. Loads affected blocks ("before" state)
2. Applies operations to produce "after" state
3. Validates permissions and data coherency
4. Commits atomically
5. Pushes change notifications via WebSocket ([source](https://www.notion.com/blog/data-model-behind-notion))

---

## :mag: Tree Storage Patterns in SQL

**The "so what?":** Choosing the wrong tree storage pattern can mean the difference between 1ms and 8-second queries. For a block editor, you need fast reads AND frequent writes -- this narrows the field to two realistic options.

### The Four Classic Approaches

```
ADJACENCY LIST          MATERIALIZED PATH       NESTED SETS            CLOSURE TABLE
+----+--------+        +----+----------+        +----+-----+-----+     +----------+----------+-------+
| id | parent |        | id | path     |        | id | lft | rgt |     | ancestor | descendant| depth |
+----+--------+        +----+----------+        +----+-----+-----+     +----------+----------+-------+
| 1  | NULL   |        | 1  | 1.       |        | 1  | 1   | 14  |     | 1        | 1        | 0     |
| 2  | 1      |        | 2  | 1.2.     |        | 2  | 2   | 7   |     | 1        | 2        | 1     |
| 3  | 1      |        | 3  | 1.3.     |        | 3  | 8   | 13  |     | 1        | 3        | 1     |
| 4  | 2      |        | 4  | 1.2.4.   |        | 4  | 3   | 4   |     | 1        | 4        | 2     |
| 5  | 2      |        | 5  | 1.2.5.   |        | 5  | 5   | 6   |     | 2        | 2        | 0     |
+----+--------+        +----+----------+        +----+-----+-----+     | 2        | 4        | 1     |
                                                                        | 2        | 5        | 1     |
                                                                        | ...      | ...      | ...   |
```

### Head-to-Head Comparison

| Operation | Adjacency List | Materialized Path | Nested Sets | Closure Table |
|-----------|:---:|:---:|:---:|:---:|
| **Get immediate children** | **O(1)** single query | O(1) prefix match | O(1) range query | O(1) join, depth=1 |
| **Get all descendants** | O(depth) recursive CTE | **O(1)** LIKE prefix | **O(1)** BETWEEN | **O(1)** single join |
| **Get all ancestors** | O(depth) recursive CTE | O(1) parse path | O(1) range query | **O(1)** single join |
| **Insert leaf node** | **O(1)** single INSERT | O(1) concat path | **O(n)** rebalance lft/rgt | O(depth) insert paths |
| **Move subtree** | **O(1)** update parent_id | **O(subtree)** update paths | **O(n)** rebalance ALL nodes | **O(subtree^2)** delete+reinsert |
| **Delete subtree** | O(subtree) cascade | O(subtree) cascade | **O(n)** rebalance | O(subtree * depth) |
| **Storage overhead** | **Minimal** (1 FK per row) | Moderate (path string) | Minimal (2 ints per row) | **High** (O(n*d) rows) |
| **Best for** | Write-heavy, shallow | Read-heavy, static | Analytics, read-only | Complex queries, moderate writes |

Sources: [Ackee blog](https://www.ackee.agency/blog/hierarchical-models-in-postgresql), [TeddySmith.IO](https://teddysmith.io/sql-trees/), [Baeldung](https://www.baeldung.com/sql/storing-tree-in-rdb), [Hierarchical Data in SQL](https://adamdjellouli.com/articles/databases_notes/03_sql/09_hierarchical_data)

### SQL Examples for Each Pattern

**Adjacency List -- Get subtree with recursive CTE (SQLite compatible):**

```sql
WITH RECURSIVE subtree AS (
    -- Anchor: the target block
    SELECT id, parent_id, type, content, 0 AS depth
    FROM blocks WHERE id = :block_id
    UNION ALL
    -- Recursive step: children
    SELECT b.id, b.parent_id, b.type, b.content, s.depth + 1
    FROM blocks b
    JOIN subtree s ON b.parent_id = s.id
)
SELECT * FROM subtree ORDER BY depth;
```

**Closure Table -- Get descendants in one join:**

```sql
SELECT b.* FROM blocks b
JOIN block_closure bc ON bc.descendant_id = b.id
WHERE bc.ancestor_id = :block_id AND bc.depth > 0
ORDER BY bc.depth;
```

**Materialized Path -- Get subtree with prefix match:**

```sql
SELECT * FROM blocks
WHERE path LIKE (SELECT path FROM blocks WHERE id = :block_id) || '%'
ORDER BY path;
```

**Nested Sets -- Get subtree with range:**

```sql
SELECT child.* FROM blocks child
JOIN blocks parent ON parent.id = :block_id
WHERE child.lft BETWEEN parent.lft AND parent.rgt
ORDER BY child.lft;
```

> **Key Insight:** For a block editor where users constantly insert, move, and delete blocks, **adjacency list + recursive CTE** is the pragmatic choice. It's what Notion uses, it's what SQLite handles well, and the write performance is unbeatable. Closure tables are the runner-up if you need complex ancestor queries (e.g., permission inheritance), but the storage overhead is severe at scale.

### Why Adjacency List Wins for Block Editors

The [Ackee blog](https://www.ackee.agency/blog/hierarchical-models-in-postgresql) recommends: "Always start with the adjacency list solution since it is simple, space-efficient and can be easily combined with any other solution."

For block editors specifically:

- **Writes dominate**: Users add/move/delete blocks constantly. Adjacency list = O(1) insert.
- **Reads are shallow**: A page fetch needs 1-3 levels of children, not the full tree. No need for O(1) deep subtree queries.
- **Move is trivial**: Update one `parent_id` field vs. rebalancing an entire tree (nested sets) or rewriting hundreds of closure rows.
- **SQLite-friendly**: Recursive CTEs work out of the box since SQLite 3.8.3 (2014).

---

## :zap: Block Ordering Strategies

**The "so what?":** How you order blocks within a parent determines whether drag-and-drop is O(1) or O(n). Fractional indexing is the industry standard for collaborative apps -- Figma, Linear, and others use it. But simpler approaches work fine for non-collaborative scenarios.

### Three Approaches Compared

| Approach | Insert Between | Move | Collision Risk | Storage | Concurrent Edits |
|----------|:---:|:---:|:---:|:---:|:---:|
| **Integer array** (Notion) | O(n) rewrite array | O(n) rewrite array | None | Array column | Requires locking |
| **Position float/int column** | O(n) re-index gaps | O(n) shift others | None | 1 column | Poor |
| **Fractional indexing** (Figma) | **O(1)** compute midpoint | **O(1)** compute new index | Theoretical (fixable) | 1 string column | **Excellent** |

### Fractional Indexing Deep Dive

[Figma's engineering blog](https://www.figma.com/blog/realtime-editing-of-ordered-sequences/) pioneered this approach for collaborative editors. [Steve Ruiz's analysis](https://www.steveruiz.me/posts/reordering-fractional-indices) provides the clearest implementation guide.

**Core idea:** Instead of integer positions `[1, 2, 3]`, use sortable strings where you can always generate a value between any two existing values:

```
Before:  [A] order="a1"    [B] order="a2"    [C] order="a3"

Insert D between A and B:
After:   [A] order="a1"    [D] order="a1V"   [B] order="a2"    [C] order="a3"

No other items need updating.
```

**Figma's implementation details:**
- Uses **base-95 encoding** (printable ASCII) for compactness
- Stores indices as strings with **lexicographic sorting**
- Omits the leading "0." -- all values are between 0 and 1 exclusive
- Uses **arbitrary-precision string arithmetic** instead of floating-point
- Avoids the precision ceiling of ~52 halvings with IEEE 754 doubles

[Steve Ruiz notes](https://www.steveruiz.me/posts/reordering-fractional-indices) that after **52 successive insertions** between the same two values using floating-point, precision collapses. String-based fractional indexing has **no such limit**.

**Implementation sketch (Python):**

```python
def midpoint(a: str, b: str | None) -> str:
    """Generate a sort key between a and b (or after a if b is None)."""
    if b is None:
        # Append to end: just increment last char
        return a + "V"  # Middle of alphabet
    # Find first differing position, generate midpoint char
    # Full implementation uses base-95 arithmetic on char codes
    ...
```

> :bulb: **Recommendation:** For N3TX, start with an **integer `order` column** (simple, sufficient for single-user). Design the schema so it can be swapped to **fractional indexing strings** later if collaboration is added. The column type change (int to varchar) is the only migration needed.

---

## :mag: Recursive Schema Design (JSON Schema)

**The "so what?":** JSON Schema natively supports recursive types via `$defs` + `$ref`. This means N3TX can represent block trees in its schema contract without any schema-level hacks -- the standard handles it. But there are UX decisions about how deep to describe the tree in a single schema response.

### Self-Referencing Block Schema

From the [JSON Schema specification](https://tour.json-schema.org/content/06-Combining-Subschemas/07-Recursive-Schemas), recursive schemas use `$ref` pointing back to a `$defs` entry:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://n3tx.example/Block",
  "$defs": {
    "Block": {
      "type": "object",
      "properties": {
        "id": { "type": "string", "format": "uuid" },
        "type": { "type": "string", "enum": ["paragraph", "heading", "image", "toggle", "list_item"] },
        "parent_id": { "type": ["string", "null"], "format": "uuid" },
        "order": { "type": "integer" },
        "has_children": { "type": "boolean", "readOnly": true },
        "content": {
          "type": "object",
          "description": "Type-specific content (text, url, etc.)"
        },
        "children": {
          "type": "array",
          "items": { "$ref": "#/$defs/Block" }
        }
      },
      "required": ["id", "type"]
    }
  },
  "$ref": "#/$defs/Block"
}
```

This schema is **infinitely recursive** -- `children` contains `Block` items, each of which can have their own `children`. Validators handle this correctly; the recursion terminates when `children` is an empty array.

### The `hasChildren` Hint Pattern

Notion's API uses `has_children: boolean` as a **lazy-loading signal**. The response does NOT include the children array inline -- it just tells the frontend "there's more here, fetch it if you need it."

```
Eager loading (inline children):
GET /blocks/:id  -->  { id, type, children: [{ id, type, children: [...] }] }
                       ^--- Full tree in one response. Fast for small pages, dangerous for large ones.

Lazy loading (has_children hint):
GET /blocks/:id  -->  { id, type, has_children: true }
GET /blocks/:id/children  -->  [{ id, type, has_children: false }, ...]
                               ^--- Flat list of immediate children. Client recurses as needed.
```

> :bulb: **Key Insight:** `has_children` is a **computed property**, not stored data. It's derived from whether the block has any children (either from a `content` array being non-empty, or from a `SELECT EXISTS` query). In N3TX terms, this would be a schema hint in `json_schema_extra`, not a model field:
>
> ```python
> has_children: bool = Field(default=False, json_schema_extra={'ui': {'display': 'hidden'}, 'computed': True})
> ```

### Schema Evolution: Adding Block Types Without Breaking Data

The `type` field + `content` JSON blob pattern means new block types don't require schema migrations:

```python
# Adding a new block type = adding a new enum value + content schema variant
# Old blocks are untouched. New blocks use the new type.

# V1: Two block types
class Block(ProtoModel):
    type: Literal["paragraph", "heading"]
    content: dict  # {"text": "..."}

# V2: Added image type -- no migration needed
class Block(ProtoModel):
    type: Literal["paragraph", "heading", "image"]
    content: dict  # {"text": "..."} or {"url": "...", "caption": "..."}
```

This is the **open/closed principle** applied to data: closed for modification (existing blocks unchanged), open for extension (new types added freely).

---

## :mag: Polymorphic Block Type Systems

**The "so what?":** Every block has a `type` and type-specific content. The question is whether to store all types in one table with a JSON `content` column, or split into separate tables per type. For schema-driven frameworks, the single-table approach wins overwhelmingly.

### Single Table (STI) vs. Multi-Table (CTI) for Blocks

| Aspect | Single Table + JSON content | Table-per-type |
|--------|:---:|:---:|
| **Add new block type** | No migration | New table + FK migration |
| **Query all children** | Single query on `blocks` table | JOIN across N tables or UNION ALL |
| **Consistent ordering** | Natural -- one `order` column | Complex -- ordering across tables |
| **Schema simplicity** | One model | N models + base model |
| **Type-specific validation** | At application layer | At database layer |
| **Storage efficiency** | Slightly wasteful (JSON overhead) | Optimal per-type |
| **Index on type-specific fields** | Requires JSON indexing or generated columns | Native column indexes |

**Notion uses single-table.** All blocks -- text, images, databases, pages -- share the same table structure. The `type` field determines how `properties` (their JSON content column) is interpreted.

### Discriminated Unions in Pydantic (Python)

For strong typing at the application layer while keeping a flat storage model, [Pydantic's discriminated unions](https://docs.pydantic.dev/latest/concepts/unions/) are the tool:

```python
from pydantic import BaseModel, Field
from typing import Literal, Union, Annotated

class ParagraphContent(BaseModel):
    type: Literal["paragraph"] = "paragraph"
    text: str
    color: str = "default"

class HeadingContent(BaseModel):
    type: Literal["heading"] = "heading"
    text: str
    level: Literal[1, 2, 3] = 1

class ImageContent(BaseModel):
    type: Literal["image"] = "image"
    url: str
    caption: str = ""
    width: int | None = None

class CodeContent(BaseModel):
    type: Literal["code"] = "code"
    text: str
    language: str = "plain"

# Discriminated union -- Pydantic uses `type` field to pick the right model
BlockContent = Annotated[
    Union[ParagraphContent, HeadingContent, ImageContent, CodeContent],
    Field(discriminator="type")
]
```

This generates a JSON Schema with `oneOf` and a `discriminator` property, which is exactly what the [OpenAPI specification recommends](https://swagger.io/docs/specification/v3_0/data-models/inheritance-and-polymorphism/):

```json
{
  "oneOf": [
    { "$ref": "#/$defs/ParagraphContent" },
    { "$ref": "#/$defs/HeadingContent" },
    { "$ref": "#/$defs/ImageContent" },
    { "$ref": "#/$defs/CodeContent" }
  ],
  "discriminator": {
    "propertyName": "type",
    "mapping": {
      "paragraph": "#/$defs/ParagraphContent",
      "heading": "#/$defs/HeadingContent",
      "image": "#/$defs/ImageContent",
      "code": "#/$defs/CodeContent"
    }
  }
}
```

### Storage: JSON Content Column

In SQLite (N3TX's default), the `content` dict is stored as a JSON TEXT column -- exactly how N3TX already handles `dict` fields via `_coerce_value()` and `_deserialize_json_fields()` in `sqlite_storage.py`:

```sql
CREATE TABLE blocks (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    parent_id TEXT REFERENCES blocks(id),
    "order" INTEGER NOT NULL DEFAULT 0,
    content TEXT NOT NULL DEFAULT '{}',  -- JSON blob
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Query with JSON extraction (SQLite 3.38+)
SELECT id, type, json_extract(content, '$.text') as text
FROM blocks
WHERE type = 'paragraph'
  AND json_extract(content, '$.color') = 'red';
```

---

## :office: Block Type Registries: ProseMirror, Tiptap, BlockNote

**The "so what?":** The editor ecosystem has converged on a **registry pattern** for block types -- define a block spec, register it, and the editor knows how to render and serialize it. This pattern maps directly to N3TX's existing widget system.

### Tiptap/ProseMirror Node Type System

[Tiptap's schema system](https://tiptap.dev/docs/editor/core-concepts/schema) defines block types through extensions with a declarative API:

```javascript
// Defining a custom block type in Tiptap
const Callout = Node.create({
  name: 'callout',
  group: 'block',           // Can appear wherever blocks are allowed
  content: 'block+',        // Must contain one or more child blocks
  defining: true,            // Preserved during paste operations

  addAttributes() {
    return {
      variant: { default: 'info' },  // info, warning, error, success
    }
  },

  parseHTML() {
    return [{ tag: 'div[data-callout]' }]
  },

  renderHTML({ HTMLAttributes }) {
    return ['div', { 'data-callout': '', ...HTMLAttributes }, 0]
  },
})
```

Key concepts in Tiptap's schema:
- **Groups**: Block types belong to groups (`block`, `inline`, `list`) referenced in content rules
- **Content expressions**: `'block+'` (one or more blocks), `'inline*'` (zero or more inline), `'(paragraph|heading)+'`
- **Isolation**: `isolating: true` fences the cursor (useful for table cells)
- **Atoms**: `atom: true` makes a block a single opaque unit (like an image embed)

### BlockNote: Notion-Style on ProseMirror

[BlockNote](https://github.com/TypeCellOS/BlockNote) is an open-source Notion-style editor built on ProseMirror/Tiptap. Its block spec pattern:

```javascript
const Alert = createReactBlockSpec({
  type: "alert",
  propSchema: {
    type: { default: "warning", values: ["warning", "error", "info", "success"] },
  },
  content: "inline",  // What kind of content this block holds

  render: ({ block, editor }) => (
    <div className={`alert alert-${block.props.type}`}>
      <InlineContent />
    </div>
  ),
});
```

### BlockSuite: CRDT-Native Block Registry

[BlockSuite](https://block-suite.com/blog/document-centric.html) (powering AFFiNE, an open-source Notion alternative) takes this further with CRDT-native block definitions backed by Yjs:

```
Document (Y.Doc)
  └── Block Tree (Y.Map)
       ├── Paragraph Block (Y.Map + Y.Text for rich text)
       ├── Image Block (Y.Map with url property)
       └── Database Block (Y.Map + Y.Array for rows)
```

Every block is a `Y.Map` in the Yjs document. Changes to any block property are automatically CRDT-merged, so two users editing different properties of the same block never conflict.

### Mapping to N3TX's Architecture

The editor block registry maps naturally to N3TX's existing patterns:

| Editor Concept | N3TX Equivalent |
|----------------|----------------|
| Block type definition | `type` field on Block model + `json_schema_extra` for content schema |
| Block rendering | `__ui__` → `renderer` mapping → `<ntx-item>` subclass |
| Content expressions | JSON Schema `$ref` + `oneOf` for typed content |
| Extension registry | Widget registry pattern (`packages/n3tx-ui/static/widgets/`) |
| Block group membership | Could use schema `tags` or `ui.group` metadata |

---

## :bar_chart: Performance and Scale

**The "so what?":** Tree queries in SQLite are fast enough for block editors up to ~50K blocks. Beyond that, you need lazy loading. The real bottleneck is not the query engine -- it's loading full trees when you only need the first screen.

### SQLite Recursive CTE Benchmarks

From a [benchmark on the SQLite forum](https://sqlite.org/forum/info/016a25083a9f8eb5c6532ed5a961eb7c2362f667cbca305f65dccb2e82170df7) using a **10-fork tree of height 6** (1,000,001 nodes):

| Method | Time (fast hardware) | Time (slower hardware) |
|--------|:---:|:---:|
| `WITH RECURSIVE` CTE | **0.63s** | 7.7s |
| Manual self-joins | 0.36s | 3.9s |
| `NOT MATERIALIZED` hint | **0.24s** | -- |
| Simple `WHERE id` query | -- | **0.55s** |

Key observations:
- Recursive CTEs are **~2x slower** than manual joins for full-tree traversal
- The `NOT MATERIALIZED` hint improves performance by ~60% on supported SQLite versions
- For **shallow queries** (1-2 levels deep, which is the block editor use case), performance is sub-millisecond even at 100K+ nodes

### Practical Block Editor Performance Profile

For a typical document page:

| Scenario | Blocks | Query Pattern | Expected Latency (SQLite) |
|----------|--------|---------------|:---:|
| Small page | 50 blocks, depth 3 | Eager load full tree | **< 1ms** |
| Medium page | 500 blocks, depth 5 | Lazy load 2 levels | **< 5ms** |
| Large page | 5,000 blocks, depth 8 | Lazy load + pagination | **< 10ms** per level |
| Huge document | 50,000 blocks | Lazy load + virtual scroll | **< 10ms** per batch |
| Notion-scale | 200B+ blocks | Sharded Postgres + caching | Varies |

### The N+1 Problem and Solutions

Fetching a block tree naively creates an N+1 query problem:

```
BAD (N+1 queries):
  GET /blocks/root           -- 1 query for root
  GET /blocks/root/children  -- 1 query for level 1 (returns 10 blocks)
  GET /blocks/A/children     -- 10 queries for level 2
  GET /blocks/B/children     -- ...
  Total: 1 + 10 + 100 + ... queries

GOOD (recursive CTE, 1 query):
  WITH RECURSIVE tree AS (
    SELECT *, 0 as depth FROM blocks WHERE id = :root_id
    UNION ALL
    SELECT b.*, t.depth + 1
    FROM blocks b JOIN tree t ON b.parent_id = t.id
    WHERE t.depth < :max_depth  -- Limit depth!
  )
  SELECT * FROM tree ORDER BY depth, "order";
```

> **Key Insight:** Notion solves the N+1 problem with `loadPageChunk` -- a single API call that descends from a starting block ID down the content tree and returns all blocks needed for rendering, using **multiple caching layers** for efficiency ([source](https://www.notion.com/blog/data-model-behind-notion)). For N3TX, the equivalent would be a `GET /blocks/:id/tree?depth=3` endpoint using a recursive CTE.

### Indexing Strategy for Block Trees

```sql
-- Essential indexes for block tree queries
CREATE INDEX idx_blocks_parent_order ON blocks(parent_id, "order");
-- ^ Covers: get children sorted by order (the most common query)

CREATE INDEX idx_blocks_type ON blocks(type);
-- ^ Covers: find all blocks of a specific type

CREATE INDEX idx_blocks_parent_type ON blocks(parent_id, type);
-- ^ Covers: find children of a specific type (e.g., all heading blocks under a page)
```

The compound index on `(parent_id, order)` is the single most important index. It makes "get children in order" a **single index scan** with no sort step.

### Depth Limits

At what depth does recursion become a problem?

| Depth | Typical Content | UI Feasibility | Query Feasibility |
|-------|----------------|:---:|:---:|
| 1-3 | Normal page content | Excellent | Excellent |
| 4-6 | Deeply nested lists/toggles | Good, needs indentation limits | Good |
| 7-10 | Unusual but possible | Degraded UX (too much nesting) | Fine for SQLite |
| 10-20 | Pathological | Unusable | CTE starts to slow |
| 20+ | Bug or abuse | N/A | Set `SQLITE_MAX_CTE_DEPTH` (default 1000) |

> :warning: **Practical limit:** Cap at **depth 10** in the application layer. Notion doesn't enforce a hard limit but their UI naturally discourages nesting beyond 5-6 levels through indentation. N3TX should emit a schema hint like `"maxDepth": 10` and validate on write.

---

## :mag: Undo/Redo and Collaboration

**The "so what?":** Recursive block trees make undo/redo significantly harder than flat documents. The industry is split between CRDTs (newer, complex, offline-capable) and OT (proven, simpler, requires server). For a framework like N3TX, event sourcing on block operations provides undo without the full complexity of either.

### Why Block Trees Complicate Undo

A flat document has one undo stack. A block tree has **structural operations** (move block, reparent, reorder) that interact with **content operations** (edit text within a block):

```
User action:           "Move block B from under A to under C"
Operations generated:  1. Remove B from A.content array
                       2. Add B to C.content array
                       3. Update B.parent_id from A to C

Undo must reverse:     3 operations atomically. If only #1 is undone,
                       B is orphaned. If only #3, arrays are inconsistent.
```

### Three Approaches to Collaboration on Block Trees

| Approach | Used By | Offline Support | Complexity | Conflict Resolution |
|----------|---------|:---:|:---:|-----|
| **Last-Write-Wins (LWW)** | Notion (for text) | No | Low | Server decides; last edit overwrites |
| **Operational Transform (OT)** | Google Docs | No | Medium | Transform operations against each other |
| **CRDTs** | Figma, BlockSuite/AFFiNE | **Yes** | High | Automatic merge via mathematical properties |

### Notion's Hybrid Approach

Notion uses a [pragmatic hybrid](https://news.ycombinator.com/item?id=38289327):
- **Block structure** (add/move/delete blocks): **intention-preserving** operations validated server-side
- **Text within blocks**: **Last-write-wins** decided by the server -- NOT a CRDT
- Individual blocks are small (paragraph-level), so LWW conflicts are rare and acceptable

This is notably simpler than full CRDTs. The trade-off: two users editing the **same paragraph** simultaneously will see one edit win. In practice, this rarely matters because Notion's block granularity is fine enough that concurrent edits to the same block are uncommon.

### BlockSuite/Yjs: Full CRDT Approach

[BlockSuite](https://block-suite.com/blog/crdt-native-data-flow.html) goes all-in on CRDTs via Yjs:

```
User types "hello" in Block A
  |
  v
Modify Y.Text in underlying Y.Map (the block)
  |
  v
Yjs generates Y.Event (incremental state change)
  |
  v
Block model synced from CRDT state
  |
  v
Slot event triggers UI update
  |
  v
Same Y.Event distributed to other peers
  |
  v
Remote peers apply update -> same pipeline -> UI synced
```

The advantage: **no special code for collaboration**. Local edits and remote edits follow the exact same pipeline. The cost: Yjs adds **~30KB** to the bundle, and CRDT documents can grow large with metadata over time.

### Event Sourcing on Block Operations

For N3TX, the most practical path is **event sourcing** without full CRDTs:

```python
# Each block mutation becomes an immutable event
class BlockEvent:
    event_id: str
    timestamp: datetime
    user_id: str
    block_id: str
    event_type: Literal["create", "update", "move", "delete"]
    payload: dict  # Type-specific data

# Examples:
{"event_type": "create", "block_id": "abc", "payload": {"type": "paragraph", "parent_id": "root", "order": 3}}
{"event_type": "update", "block_id": "abc", "payload": {"content": {"text": "Hello world"}}}
{"event_type": "move",   "block_id": "abc", "payload": {"old_parent": "root", "new_parent": "xyz", "order": 1}}
{"event_type": "delete", "block_id": "abc", "payload": {}}
```

**Undo** = apply inverse events in reverse order. **Redo** = replay forward. This approach is used by many applications and [fits naturally with event sourcing patterns](https://ericjinks.com/blog/2025/event-sourcing/) -- "You can undo or redo by moving backward and forward in the event history. As events are immutable, you can recreate the state of an entity at any version by applying a subset of events."

---

## :bulb: Design Recommendations for N3TX

### Recommended Block Model

```python
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from pydantic import Field
from typing import Optional

class Block(ProtoModel):
    __tablename__ = 'blocks'
    __storable__ = True
    __access__ = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': OWNER | ROLE('admin'),
    }
    __ui__ = {
        'renderer': {'item': 'ntx-block', 'list': 'ntx-block-tree'},
    }

    type: str = Field(
        default="paragraph",
        json_schema_extra={'enum': ['paragraph', 'heading', 'image', 'code',
                                     'toggle', 'list_item', 'callout', 'divider']}
    )
    parent_id: Optional[str] = Field(
        default=None,
        json_schema_extra={'ui': {'display': 'hidden'}}
    )
    order: int = Field(
        default=0,
        json_schema_extra={'ui': {'display': 'hidden'}}
    )
    content: dict = Field(
        default_factory=dict,
        json_schema_extra={'description': 'Type-specific content (text, url, caption, etc.)'}
    )
    has_children: bool = Field(
        default=False,
        json_schema_extra={'ui': {'display': 'hidden'}, 'readOnly': True}
    )
```

### Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        N3TX Block System                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   [Block Model]                                                 │
│   type: str           ──── Discriminator for content schema     │
│   parent_id: str?     ──── Adjacency list FK (tree structure)   │
│   order: int          ──── Position among siblings              │
│   content: dict       ──── Type-specific JSON blob              │
│   has_children: bool  ──── Computed hint for lazy loading       │
│                                                                 │
│   ┌─────────────────┐    ┌──────────────────┐                  │
│   │  Schema Layer    │    │  Storage Layer    │                  │
│   │                  │    │                   │                  │
│   │ $defs/Block with │    │ Single `blocks`   │                  │
│   │ recursive $ref   │    │ table in SQLite   │                  │
│   │ oneOf for typed  │    │ JSON content col  │                  │
│   │ content variants │    │ (parent_id,order) │                  │
│   │ has_children hint│    │ compound index    │                  │
│   └────────┬────────┘    └────────┬──────────┘                  │
│            │                      │                              │
│   ┌────────v────────┐    ┌────────v──────────┐                  │
│   │  API Layer       │    │  Query Layer      │                  │
│   │                  │    │                   │                  │
│   │ GET /blocks/:id  │    │ Recursive CTE for │                  │
│   │ GET /blocks/:id/ │    │ tree fetching     │                  │
│   │   children       │    │ Depth-limited     │                  │
│   │ POST /blocks     │    │ (parent_id,order) │                  │
│   │ PATCH /blocks/:id│    │ index scan        │                  │
│   │ POST /blocks/:id/│    │                   │                  │
│   │   move           │    │                   │                  │
│   └────────┬────────┘    └───────────────────┘                  │
│            │                                                     │
│   ┌────────v────────┐                                           │
│   │  Frontend        │                                          │
│   │                  │                                          │
│   │ <ntx-block>      │ ── Renders single block by type          │
│   │ <ntx-block-tree> │ ── Recursive tree renderer               │
│   │ Block type →     │                                          │
│   │   component map  │ ── Widget registry for block renderers   │
│   └─────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

### Decision Matrix: What to Build When

| Capability | Complexity | When to Build | Depends On |
|------------|:---:|---|---|
| `parent_id` adjacency list | Low | **Phase 1** -- core block model | Nothing |
| `order` integer column | Low | **Phase 1** -- basic ordering | Nothing |
| `has_children` computed field | Low | **Phase 1** -- lazy loading hint | parent_id |
| `content` JSON blob | Low | **Phase 1** -- type-specific data | Existing JSON field support |
| Recursive CTE tree query | Medium | **Phase 1** -- `/blocks/:id/tree` endpoint | parent_id |
| Block type registry (frontend) | Medium | **Phase 2** -- extensible rendering | Widget system |
| Fractional indexing | Medium | **Phase 3** -- collaborative reordering | Collab requirements |
| Event sourcing for undo | High | **Phase 3** -- undo/redo support | Block operations defined |
| CRDT integration (Yjs) | High | **Phase 4** -- real-time collaboration | Fundamental architecture decision |

### SQL Schema for SQLite

```sql
CREATE TABLE blocks (
    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
    type TEXT NOT NULL DEFAULT 'paragraph',
    parent_id TEXT REFERENCES blocks(id) ON DELETE CASCADE,
    "order" INTEGER NOT NULL DEFAULT 0,
    content TEXT NOT NULL DEFAULT '{}',
    has_children INTEGER NOT NULL DEFAULT 0,  -- computed, updated on child insert/delete
    user_owner TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- The critical index: get children in order
CREATE INDEX idx_blocks_parent_order ON blocks(parent_id, "order");

-- Orphan prevention: cascade deletes when parent is deleted
-- Already handled by ON DELETE CASCADE above

-- Useful for type-based queries
CREATE INDEX idx_blocks_type ON blocks(type);
```

### Recursive CTE for Tree Fetch (SQLite)

```sql
-- Fetch a block and all descendants up to depth 3
WITH RECURSIVE block_tree AS (
    SELECT *, 0 AS depth FROM blocks WHERE id = :root_id
    UNION ALL
    SELECT b.*, bt.depth + 1
    FROM blocks b
    JOIN block_tree bt ON b.parent_id = bt.id
    WHERE bt.depth < 3
)
SELECT * FROM block_tree
ORDER BY depth, "order";
```

---

## :chart_with_upward_trend: Comparison: Notion vs. Block Editors vs. N3TX Approach

| Dimension | Notion | BlockNote/Tiptap | Proposed N3TX |
|-----------|--------|------------------|---------------|
| **Storage** | PostgreSQL, sharded by workspace | In-memory ProseMirror doc | SQLite, single `blocks` table |
| **Tree model** | Adjacency list + content array | ProseMirror node tree | Adjacency list + order column |
| **Ordering** | Ordered array of child IDs | ProseMirror position | Integer `order` column |
| **Block types** | ~32 types, properties JSON | Extension-based node specs | `type` enum + `content` dict |
| **Type extensibility** | Internal only | Plugin system | Widget registry + schema hints |
| **Schema format** | Proprietary | ProseMirror schema | JSON Schema with `$defs`/`$ref` |
| **Lazy loading** | `has_children` + `loadPageChunk` | Eager (in-memory) | `has_children` + `/children` endpoint |
| **Collaboration** | Hybrid LWW + intention-preserving | Via Yjs (optional) | Event sourcing (Phase 3) |
| **Scale target** | 200B+ blocks | Client-side only | 10K-1M blocks per instance |

---

## :warning: Risks and Gotchas

1. **Orphaned blocks**: If a parent is deleted without cascading, children become unreachable. Mitigation: `ON DELETE CASCADE` in SQL, plus a periodic cleanup job.

2. **Circular references**: A block could theoretically be its own ancestor. Mitigation: validate on write that `parent_id != id` and run cycle detection for move operations.

3. **Deep recursion DoS**: A malicious user creates blocks nested 1000 levels deep. Mitigation: enforce `maxDepth` at the API layer (recommended: 10).

4. **Order gaps and collisions**: Integer ordering can develop gaps after deletions. Not a problem for correctness, but periodic compaction improves aesthetics. For move operations, use `order = (prev.order + next.order) / 2` with periodic re-indexing.

5. **Large JSON content blobs**: An image block might store base64 data in `content`. Mitigation: store media separately, keep only URLs in content. Enforce a `content` size limit.

6. **Schema recursion in frontend**: JSON Schema validators must handle recursive `$ref` without infinite loops. Most modern validators (Ajv, etc.) handle this correctly, but test thoroughly.

> :warning: **Critical gotcha for N3TX specifically**: The `has_children` field must stay in sync. If it's a stored column, every child insert/delete must update the parent's `has_children`. If it's computed on read, every list query pays the cost of a subquery. **Recommendation**: Store it as a denormalized boolean, update it via triggers or application-layer hooks.

---

## :link: Sources

1. [Exploring Notion's Data Model: A Block-Based Architecture](https://www.notion.com/blog/data-model-behind-notion) -- Notion's official deep dive into block architecture, four block attributes, render tree, transaction model
2. [Herding elephants: lessons learned from sharding Postgres at Notion](https://www.notion.com/blog/sharding-postgres-at-notion) -- Sharding strategy, 480 logical shards, workspace-ID partitioning
3. [The Great Re-shard: adding Postgres capacity with zero downtime](https://www.notion.com/blog/the-great-re-shard) -- Scaling from 32 to 96 physical DB servers
4. [How does Notion handle 200 billion data entities?](https://vutr.substack.com/p/how-does-notion-handle-200-billion) -- Data lake architecture, scale numbers
5. [Examining Notion's Backend Architecture](https://labs.relbis.com/blog/2024-04-18_notion_backend/) -- Node.js web servers, PgBouncer, block data model
6. [Realtime Editing of Ordered Sequences -- Figma Blog](https://www.figma.com/blog/realtime-editing-of-ordered-sequences/) -- Fractional indexing with base-95 string encoding
7. [Reordering Part 2: Tables and Fractional Indexing -- Steve Ruiz](https://www.steveruiz.me/posts/reordering-fractional-indices) -- Practical implementation, precision limits, string-based solution
8. [Hierarchical Models in PostgreSQL -- Ackee Blog](https://www.ackee.agency/blog/hierarchical-models-in-postgresql) -- Comparison of adjacency list, materialized path, nested sets, closure table with PostgreSQL examples
9. [Mastering SQL Trees -- TeddySmith.IO](https://teddysmith.io/sql-trees/) -- SQL examples and comparison table for all four tree storage patterns
10. [Storing Hierarchical Data in Relational Databases](https://adamdjellouli.com/articles/databases_notes/03_sql/09_hierarchical_data) -- Comprehensive comparison with performance profiles and SQL examples
11. [SQLite Recursive CTE Documentation](https://sqlite.org/lang_with.html) -- Official SQLite recursive CTE reference
12. [SQLite Forum: Recursive CTE Performance](https://sqlite.org/forum/info/016a25083a9f8eb5c6532ed5a961eb7c2362f667cbca305f65dccb2e82170df7) -- Benchmark: 1M node tree, CTE vs manual joins
13. [Recursive Schemas -- JSON Schema Tour](https://tour.json-schema.org/content/06-Combining-Subschemas/07-Recursive-Schemas) -- Self-referencing `$defs` + `$ref` pattern
14. [JSON Schema Structuring](https://json-schema.org/understanding-json-schema/structuring) -- `$defs`, `$ref`, and recursive schema patterns
15. [Pydantic Discriminated Unions](https://docs.pydantic.dev/latest/concepts/unions/) -- Tagged unions for polymorphic block content
16. [JSON Schema Patterns: Discriminated Unions -- endjin](https://endjin.com/blog/2024/05/json-schema-patterns-dotnet-pattern-matching-and-discriminated-unions) -- `oneOf` + discriminator property pattern
17. [Tiptap Schema Documentation](https://tiptap.dev/docs/editor/core-concepts/schema) -- Node type definitions, content expressions, group system
18. [BlockNote GitHub Repository](https://github.com/TypeCellOS/BlockNote) -- Notion-style editor on ProseMirror/Tiptap
19. [Building Document-Centric, CRDT-Native Editors -- BlockSuite](https://block-suite.com/blog/document-centric.html) -- CRDT block tree architecture with Yjs
20. [CRDT-Native Data Flow in BlockSuite](https://block-suite.com/blog/crdt-native-data-flow.html) -- Y.Map block representation, event pipeline
21. [Notion API: Block Reference](https://developers.notion.com/reference/block) -- All 32 block types, `has_children`, JSON structure
22. [Working with Page Content -- Notion API](https://developers.notion.com/docs/working-with-page-content) -- Lazy loading pattern, recursive child fetching
23. [Event Sourcing -- Martin Fowler](https://martinfowler.com/eaaDev/EventSourcing.html) -- Foundational pattern for undo/redo via immutable events
24. [Undo/Redo State with Event Sourcing -- Eric Jinks](https://ericjinks.com/blog/2025/event-sourcing/) -- Practical undo/redo implementation with event replay
25. [CRDTs vs. Operational Transformation](https://systemdr.substack.com/p/crdts-vs-operational-transformation) -- Comparison of collaboration approaches
26. [SQL Server Closure Tables -- Red Gate](https://www.red-gate.com/simple-talk/databases/sql-server/t-sql-programming-sql-server/sql-server-closure-tables/) -- Closure table implementation patterns and performance
27. [OpenAPI Discriminator -- Swagger](https://swagger.io/docs/specification/v3_0/data-models/inheritance-and-polymorphism/) -- Polymorphism in API schemas with discriminator
28. [Implementing Fractional Indexing -- David Greenspan](https://observablehq.com/@dgreensp/implementing-fractional-indexing) -- Reference implementation with string arithmetic
