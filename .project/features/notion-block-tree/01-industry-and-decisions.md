# Industry Landscape & Decision Framework: Block-Based Recursive Data Models

> From Notion's 200-billion-block Postgres cluster to WordPress Gutenberg's 82 million installs,
> the "everything is a block" pattern has become the dominant paradigm for content-rich applications.
> This document maps who adopted it, what they gained, what they lost, and when your framework
> should (and should not) provide block primitives natively.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [The Block Model: A Brief History](#-the-block-model-a-brief-history)
3. [Industry Adoption Map](#-industry-adoption-map)
4. [Comparative Architecture Analysis](#-comparative-architecture-analysis)
5. [Business Outcomes & Metrics](#-business-outcomes--metrics)
6. [Developer Ecosystem & API Patterns](#-developer-ecosystem--api-patterns)
7. [Failures, Criticisms & Anti-Patterns](#-failures-criticisms--anti-patterns)
8. [Tree Storage Strategies](#-tree-storage-strategies)
9. [Decision Framework: When to Adopt Block Primitives](#-decision-framework-when-to-adopt-block-primitives)
10. [Build vs. Buy Analysis](#-build-vs-buy-analysis)
11. [Maintenance Economics at Scale](#-maintenance-economics-at-scale)
12. [Recommendations for N3TX](#-recommendations-for-n3tx)
13. [Sources](#-sources)

---

## Executive Summary

The block-based recursive data model -- where **every piece of content is a "block" that can contain child blocks** -- has moved from Notion's novel experiment (2016) to an industry-wide standard in under a decade. The pattern now underpins products serving **over 200 million combined users** across Notion, WordPress Gutenberg, Coda, Craft, Roam Research, Anytype, AppFlowy, AFFiNE, and Outline.

> **Key Insight:** The block model won not because it is the simplest data model, but because it is the **most composable**. It lets a single product serve as notes, wiki, database, project tracker, and CMS -- which is exactly what drove Notion to $500M ARR and a $10B+ valuation. For a schema-driven framework like N3TX, the question is not "should we support blocks?" but "at what layer, and with what constraints?"

**Three things this report will help you decide:**

1. Whether a `hasChildren` recursive nesting primitive belongs in your framework's core
2. What storage strategy to use (adjacency list, closure table, materialized path)
3. Where the block abstraction creates value vs. accidental complexity

---

## :mag: The Block Model: A Brief History

### The Origin Story: Notion (2013-2016)

Ivan Zhao and Simon Last founded Notion in **2013** with a vision to "unlock the full potential of computers" for non-programmers. The first prototype was a **web page builder**, then pivoted to a **web app builder**. Both failed to find market fit.

The critical insight came when Zhao realized that **"most people don't want to build their own apps... they simply want something that solves their problems quickly."** The team hid their composability vision inside productivity software. ([Lenny's Newsletter](https://www.lennysnewsletter.com/p/inside-notion-ivan-zhao))

Technical missteps nearly killed the company. **Betting on Google's early Web Components tech left Notion unstable and unscalable.** Zhao made the painful call to throw away the entire codebase and rebuild from scratch. The team shrank from five to two. They decamped to Kyoto, Japan to cut costs, coding 18-hour days. ([KITRUM](https://kitrum.com/blog/the-phenomenal-journey-of-ivan-zhao-notions-founder/))

**Notion 1.0 launched in March 2016** and became the #1 Product on Product Hunt for the entire month. The key innovation was the **"everything is a block"** philosophy:

> "If everything is a block, and blocks can be any type, and blocks can be nested, then you've built a language. You're not building features, you're building primitives. Features come from combining primitives."
> -- Ivan Zhao ([First Block podcast](https://www.notion.com/blog/first-block-with-ivan-zhao-simon-last))

### The Adoption Curve: From "Weird" to Standard

| Year | Milestone | Signal |
|------|-----------|--------|
| **2016** | Notion 1.0 launches | #1 on Product Hunt; niche productivity tool |
| **2017** | Roam Research founded | Block + bidirectional links for "networked thought" |
| **2018** | WordPress announces Gutenberg | Block editor replaces TinyMCE for 43% of the web |
| **2019** | Notion Series A ($10M, $800M valuation) | Block model validated by VC market |
| **2020** | Notion Series B ($50M, $2B valuation) | COVID drives remote work adoption; Notion usage explodes |
| **2020** | Roam raises $9M seed at $200M valuation | Block + graph model attracts cult following |
| **2021** | Notion Series C ($275M, $10B valuation) | Block model reaches enterprise scale |
| **2021** | Notion API public launch | Developer ecosystem unlocked |
| **2021** | Coda raises $100M Series D ($1.4B val) | "Tables as blocks" variant validated |
| **2022** | AppFlowy, AFFiNE launch as OSS alternatives | Block model commoditized |
| **2024** | Notion reaches 100M users, $400M ARR | Block model = industry standard |
| **2024** | Coda acquired by Grammarly | Consolidation phase begins |
| **2025** | WordPress Gutenberg at 87% adoption | Block model dominates CMS layer too |

> **Key Insight:** The inflection point was **2020-2021**. COVID-driven remote work created explosive demand for flexible workspace tools. Notion's block model was uniquely positioned because it could **replace 5-7 separate tools** (wiki, project tracker, database, notes, docs, CMS). This "Swiss Army knife" quality is the block model's core value proposition -- and its biggest risk (see [Anti-Patterns](#-failures-criticisms--anti-patterns)).

---

## :office: Industry Adoption Map

### Who Uses Blocks (and How)

| Company | Model Variant | Users | Funding | Key Differentiator |
|---------|--------------|-------|---------|-------------------|
| **Notion** | Pure block tree (everything is a block) | 100M+ | $418M raised, $10B+ val | Databases-as-blocks, templates, AI |
| **WordPress/Gutenberg** | Block editor for CMS | 82.7M active installs | Automattic ($900M+ raised) | 43% of all websites; FSE grew 145% in 2025 |
| **Coda** | Tables as first-class blocks | 10K+ paying customers | $240M raised, $1.4B val (acq. by Grammarly) | Formulas, Packs, automation-first |
| **Craft** | Native block editor (Apple-first) | 1M+ installs | $20.2M raised | Native apps, offline-first, Apple Design Award |
| **Roam Research** | Block + bidirectional graph | N/A (subscription only) | $11.4M raised, $200M val | Graph database, networked thought |
| **Anytype** | Block + CRDT + P2P | N/A | N/A (open protocol) | Local-first, E2E encrypted, IPFS |
| **AppFlowy** | Block editor (Rust/Flutter) | 60K+ GitHub stars | OSS (community) | Self-hosted, cross-platform native |
| **AFFiNE** | Block + whiteboard canvas | 45K+ GitHub stars | $18M raised | Doc + whiteboard hybrid, BlockSuite framework |
| **Outline** | Markdown block editor | 30K+ GitHub stars | OSS (hosted SaaS) | Team wiki, real-time collab, fast |
| **Nuclino** | Lightweight block wiki | N/A | N/A | Speed-optimized, graph view, minimal friction |
| **Sanity** | Portable Text (structured blocks) | 300K+ devs | Headless CMS leader | Schema-as-code, GROQ, block = structured data |
| **Contentful** | Structured content types | 300K+ devs | Enterprise CMS | API-first, content governance |

### Categorization by Block Philosophy

```
                    BLOCK MODEL SPECTRUM

    Pure Block Tree          Table-Centric Blocks       Structured Content Blocks
    ================         ====================       ========================
    Everything = block       Tables = foundation        Blocks = typed records
    Pages nest in pages      Docs wrap tables           Schema governs blocks

    Notion                   Coda                       Sanity (Portable Text)
    Roam Research            Airtable                   Contentful
    Craft                                               DatoCMS
    AppFlowy
    AFFiNE
    Outline
    WordPress/Gutenberg
    Nuclino
    Anytype
```

The **pure block tree** (Notion-style) is the most common pattern. The **table-centric** variant (Coda) treats computation and automation as primary. The **structured content** variant (Sanity, Contentful) treats blocks as typed, schema-governed records -- which is closest to what a framework like N3TX would implement.

---

## :bar_chart: Comparative Architecture Analysis

### Notion's Block Data Model (Canonical Reference)

According to [Notion's official engineering blog](https://www.notion.com/blog/data-model-behind-notion), every block has four core attributes:

| Attribute | Type | Purpose |
|-----------|------|---------|
| **id** | UUID v4 | Unique identifier; visible in page URLs |
| **type** | string | Defines rendering + property interpretation (e.g., `"to_do"`, `"heading_1"`, `"database"`) |
| **properties** | object | Type-specific attributes (most common: `"title"` for text content) |
| **content** | ordered array of UUIDs | Child block IDs -- the "downward pointers" forming the render tree |

Additionally, each block has a **parent** pointer (single upward reference) used exclusively for **permission inheritance**, not rendering.

```
                    NOTION RENDER TREE

    [Workspace Block]
         |
    [Page Block: "Q1 Planning"]
         |
         +-- [Heading Block: "Goals"]
         +-- [Paragraph Block: "Ship v2..."]
         +-- [Database Block: "Task Tracker"]
         |        |
         |        +-- [Row Block: "Design review"]
         |        +-- [Row Block: "API migration"]
         |
         +-- [Toggle Block: "Meeting notes"]
                  |
                  +-- [Paragraph Block: "Discussed..."]
                  +-- [To-Do Block: "Follow up with..."]
```

**Critical design choice:** The render tree is **not** the permissions tree. Permissions flow upward through **parent** pointers (which may differ from content relationships), ensuring unambiguous inheritance to the workspace root. This separation is a lesson many block implementations learn the hard way.

### Notion at Scale

The numbers are staggering and worth understanding for any framework architect:

- **200+ billion blocks** stored in Postgres ([ByteByteGo](https://blog.bytebytego.com/p/storing-200-billion-entities-notions))
- **480 logical shards** across **96 physical Postgres instances** (5 shards each) ([Notion Engineering Blog](https://www.notion.com/blog/sharding-postgres-at-notion))
- **Workspace ID** as partition key (all blocks in a workspace live on same shard)
- Data volume: **hundreds of terabytes, compressed**
- Data doubled every **6-12 months** during growth phase
- Migration from 32 to 96 instances in 2023 with **zero downtime** ([Notion: The Great Re-shard](https://www.notion.com/blog/the-great-re-shard))
- Data lake (Postgres -> Debezium -> Kafka -> Hudi -> S3) saved **$1M+/year** ([Notion Data Lake](https://www.notion.com/blog/building-and-scaling-notions-data-lake))

> **Key Insight:** Notion's architecture proves that a block model **can** scale to hundreds of billions of records. But it required **a dedicated infrastructure team**, custom sharding, and years of migration work. The model itself is simple; the operational complexity at scale is enormous.

### Coda: Tables as Blocks

Coda takes a fundamentally different approach. Where Notion's blocks are **content-first** (text, images, embeds that happen to include databases), Coda's blocks are **computation-first** (tables with formulas that happen to have a document wrapper).

| Dimension | Notion | Coda |
|-----------|--------|------|
| **Core primitive** | Block (content unit) | Table (data unit) |
| **Nesting** | Blocks nest arbitrarily | Docs contain tables; tables don't nest |
| **Formulas** | Limited rollups/relations | Full formula language (Turing-complete) |
| **Automation** | Via third-party (Zapier/Make) | Native automations, Packs |
| **UX metaphor** | "Flexible notebook with databases" | "Set of custom tools inside documents" |
| **Revenue** | ~$400M ARR (2024) | ~$41M ARR (2024) |
| **Outcome** | Independent, $10B+ val | Acquired by Grammarly (Dec 2024) |

([Coda vs Notion comparison, multiple sources](https://skywork.ai/blog/ai-agent/coda-vs-notion/))

**The lesson for framework design:** Coda's table-centric model produces more powerful automation but is harder for casual users. Notion's block tree produces more flexible content but weaker computation. **The sweet spot for a framework is probably Sanity's approach: typed, schema-governed blocks** that can be either content or data.

### BlockSuite / AFFiNE: The Framework Approach

[BlockSuite](https://github.com/toeverything/blocksuite) is the most relevant reference for N3TX because it is **an open-source framework for building block editors**, not a product:

- Built natively on **Yjs (CRDT)** for real-time collaboration
- UI components in **Web Components** (framework-agnostic)
- Supports **custom block types** and inline embeds
- **Document-centric CRDT** architecture where the block tree itself is the CRDT document
- Incremental updates and state scheduling across multiple documents

```
    BLOCKSUITE ARCHITECTURE

    [Custom Block Definitions]
           |
    [BlockSuite Framework] --- manages ---> [Yjs CRDT Document]
           |                                       |
    [Block Spec Registry]                    [Collaborative State]
           |                                       |
    [Web Component Renderers]              [Sync Providers]
           |                                (WebSocket, WebRTC)
    [Browser DOM]
```

AFFiNE raised **$18M** across two seed rounds (led by Redpoint Ventures, Sinovation Ventures) to build a product on BlockSuite, validating the "block editor as framework" approach. ([Tracxn](https://tracxn.com/d/companies/affine/__Mo6BFrzUISfgrA8pldUKbTH0mEXrtjxwRlYfPIADZqs))

---

## :bar_chart: Business Outcomes & Metrics

### The Notion Success Story (Headline Numbers)

| Metric | Value | Source |
|--------|-------|--------|
| Total users | **100M+** (Sept 2024) | [Notion announcement](https://taptwicedigital.com/stats/notion) |
| Paying customers | **4M+** | [GetLatka](https://getlatka.com/companies/notion) |
| Annual revenue | **~$400-500M ARR** (2024-2025) | [Sacra](https://sacra.com/c/notion/), [GetLatka](https://getlatka.com/companies/notion) |
| Valuation | **$10-11B** (Dec 2024) | [SaaStr](https://www.saastr.com/notion-and-growing-into-your-10b-valuation-a-masterclass-in-patience/) |
| Total funding | **$418M** across 9 rounds | [Tracxn](https://tracxn.com/d/companies/notion/__LQ8wyN9zLT-OwulhqbMYvw0Ayznneiugbu_OaKuGD4U) |
| Employees | **~600-800** (2024) | Multiple sources |
| Block rows in Postgres | **200B+** | [Notion Engineering](https://www.notion.com/blog/building-and-scaling-notions-data-lake) |
| Postgres cluster | **96 instances, 480 shards** | [Notion Sharding Blog](https://www.notion.com/blog/sharding-postgres-at-notion) |
| Integrations | **250+** third-party | [Notion Integrations](https://www.notion.com/integrations) |

### WordPress Gutenberg: Blocks at Web Scale

WordPress powers **43.4% of the global CMS market** ([AIOSEO](https://aioseo.com/wordpress-statistics/)). The Gutenberg block editor is now used by **87% of all active WordPress installs** -- that is approximately **82.7 million active installations**. In the past 3 years, **264+ million posts** have been written using the block editor. Full Site Editing (FSE) grew **145% in 2025 alone**. ([GutenbergStats](https://gutenstats.blog/))

This is perhaps the strongest signal that block-based editing has moved from "Notion's thing" to an **industry default**.

### Comparative Outcomes

| Company | Revenue/ARR | Valuation | Outcome |
|---------|-------------|-----------|---------|
| Notion | $400-500M | $10-11B | Independent; approaching IPO |
| Coda | $41M | $1.4B | **Acquired by Grammarly (Dec 2024)** |
| Craft | N/A | N/A | Series B, independent, Apple ecosystem focus |
| Roam Research | N/A | $200M (2020) | Profitable from subscriptions; niche |
| Outline | N/A | N/A | OSS + hosted SaaS; team wiki niche |
| AFFiNE | N/A | N/A | $18M seed; pre-revenue; open source |

> **Key Insight:** The block model alone does not guarantee success. Notion succeeded because blocks enabled a **"replace 5 tools with 1"** value proposition at the right market moment (COVID remote work). Coda had arguably superior computation capabilities but a less intuitive UX, leading to acquisition rather than independent scaling. **The execution layer matters more than the data model.**

---

## :zap: Developer Ecosystem & API Patterns

### Notion API: Power and Frustration

Notion launched its public API in **May 2021** after years of requests. The API exposes the block model directly, allowing developers to create, read, update, and delete blocks programmatically.

**Block types supported via API** (as of 2025): paragraph, heading_1/2/3, bulleted_list_item, numbered_list_item, to_do, toggle, child_page, child_database, embed, image, video, file, pdf, bookmark, callout, quote, equation, divider, table_of_contents, column, column_list, link_preview, synced_block, template, link_to_page, audio, code, table, table_row. ([Notion Developers](https://developers.notion.com/reference/block))

**Known limitations:**

- **Unsupported block types** appear as `"type": "unsupported"` with a `block_type` hint (e.g., "form", "button") -- frustrating for integrations that need full fidelity
- **Nesting limit**: Nested blocks can only go **two levels deep** in API create/append operations
- **No reordering**: Blocks can be retrieved, updated, deleted, and appended, but **not reordered** via API
- **Array limit**: Block arrays capped at **100 blocks** per request
- **Rate limits**: Standard Notion API rate limiting applies

([Notion Developers](https://developers.notion.com/docs/working-with-page-content), [Thomas Frank](https://thomasjfrank.com/how-to-handle-notion-api-request-limits/))

### WordPress Gutenberg: Block Registration Pattern

Gutenberg provides a well-documented block registration API that is instructive for framework designers:

```javascript
// WordPress block registration -- a useful pattern reference
registerBlockType('my-plugin/custom-block', {
    title: 'Custom Block',
    icon: 'smiley',
    category: 'layout',
    attributes: {
        content: { type: 'string', source: 'html', selector: 'p' }
    },
    edit: (props) => { /* editor component */ },
    save: (props) => { /* serialized output */ },
});
```

Key architectural lessons from Gutenberg:
- **Block types are registered, not hardcoded** -- extensibility by design
- **Edit and save are separate** -- the editor view can be richer than the stored representation
- **Attributes define the schema** -- typed, sourced from the serialized HTML
- **Performance degrades at 50+ blocks per page** and badly at 3000+ registered block patterns ([WordPress Gutenberg Issue #35719](https://github.com/WordPress/gutenberg/issues/35719), [Issue #64219](https://github.com/WordPress/gutenberg/issues/64219))

### Sanity Portable Text: Schema-Governed Blocks

Sanity's approach is perhaps the most relevant model for a schema-driven framework:

```javascript
// Sanity Portable Text -- blocks as typed, schema-governed records
{
  _type: 'block',
  style: 'h1',
  children: [
    { _type: 'span', text: 'Hello World', marks: ['strong'] }
  ],
  markDefs: []
}
```

Unlike Notion's opaque block model, **Portable Text stores content as structured data**, not HTML or Markdown. This means the same content can be rendered differently across channels without reformatting. Custom block types (callouts, embeds, interactive components) are defined in the schema and validated. ([Sanity.io](https://www.sanity.io/unified-content-operations-system))

---

## :warning: Failures, Criticisms & Anti-Patterns

### The "Everything is a Block" Trap

The most common anti-pattern is **over-applying the block abstraction**. When every entity becomes a block, you lose the semantic meaning that typed models provide.

**Performance complaints** are the #1 criticism of Notion across Hacker News threads:

> "I love Notion but the speed, or rather lack of, is killing me daily." -- [HN user, 2021](https://news.ycombinator.com/item?id=26499810)

> "Is Notion still slow? I really wanted to love Notion but stopped using it due to [performance]." -- [HN user, 2024](https://news.ycombinator.com/item?id=39033834)

Notion's architecture **loads entire pages client-side**, which creates a fundamental bottleneck for large workspaces. This is a direct consequence of the block tree model -- rendering requires traversing the tree and hydrating every block. ([Rosemet](https://www.rosemet.com/pros-and-cons-of-notion/))

### WordPress Gutenberg: Scaling Failures

WordPress Gutenberg provides concrete data on block scaling limits:

| Scenario | Observed Impact |
|----------|-----------------|
| 50+ blocks per post | Editor becomes sluggish |
| 2,500+ reusable blocks | Inserter popup takes several seconds |
| 3,000+ block patterns | ~1 second delay when clicking/focusing on blocks |
| 6,000+ reusable blocks | Editor becomes unusable |
| Tables with many rows | Typing lag |

([WordPress Gutenberg Issues #35719](https://github.com/WordPress/gutenberg/issues/35719), [#64219](https://github.com/WordPress/gutenberg/issues/64219))

The root cause: **the block editor renders/parses all reusable blocks** to identify icons for the inserter. This is a design flaw, not an inherent limitation of the block model -- but it illustrates how easy it is to create O(n) operations on block counts.

### Anti-Pattern Catalog

| Anti-Pattern | Description | Who Hit It | Mitigation |
|-------------|-------------|-----------|------------|
| **Block-type proliferation** | Adding new block types for every content variation | Notion API (many types return "unsupported") | Limit core types; use properties for variation |
| **Infinite nesting** | No depth limit -> pathological tree structures | Any block editor | Cap depth (e.g., 10 levels); warn on deep nesting |
| **Query inefficiency** | "Get all descendants" requires recursive queries | Adjacency list implementations | Closure table or materialized path |
| **Undo/redo explosion** | Each block operation is a separate undo step | Collaborative editors | Group operations; limit undo stack depth |
| **Permission complexity** | Block-level permissions on deeply nested trees | Notion (solved via parent-pointer inheritance) | Inherit from nearest ancestor with explicit permissions |
| **Client-side tree traversal** | Rendering requires loading entire tree | Notion (performance complaints) | Lazy loading, virtual rendering, pagination |
| **"Jack of all trades"** | Block flexibility -> mediocre at each specific function | Notion vs. purpose-built tools | Opinionated defaults; strong typing |

### Undo/Redo: The Hidden Complexity Monster

Collaborative editing with blocks introduces severe undo/redo challenges:

- In non-collaborative systems, undo is a simple stack of operations
- In collaborative systems, **each participant needs their own undo stack**
- Undoing your operation might **invalidate transformations** applied to others' operations
- "Even after over two decades of active research, support of undo for real-time collaborative editing is still very limited" ([Springer](https://link.springer.com/chapter/10.1007/978-3-319-19129-4_16))
- Automerge limits undo history to **100 operations** to prevent unbounded growth

> :warning: **Warning for framework designers:** If you add block nesting, you will eventually be asked "can users undo/redo block moves?" The answer is either "no" (frustrating) or "yes, with CRDT/OT" (6-12 months of engineering). Plan accordingly.

### Coda's Cautionary Tale

Coda raised **$240M** and built arguably the most powerful block-based workspace, with **Turing-complete formulas**, native automations, and "Packs" for third-party integration. Yet:

- Revenue reached only **$41M ARR** by October 2024 (vs. Notion's $400M+)
- **Acquired by Grammarly in December 2024** -- not an independent outcome
- Team of **292 employees** with only **91 engineers**

([GetLatka](https://getlatka.com/companies/coda))

The lesson: **power does not equal adoption**. Coda's table-centric block model was more capable than Notion's, but the learning curve was steeper. Users chose the simpler, more intuitive block tree.

---

## :zap: Tree Storage Strategies

For any framework implementing `hasChildren` / recursive nesting, the storage strategy is a critical architectural decision. Here are the four main approaches, benchmarked:

### Comparison Matrix

| Strategy | Read Children | Read Subtree | Insert | Move Node | Delete Subtree | Space Overhead |
|----------|:------------:|:------------:|:------:|:---------:|:--------------:|:--------------:|
| **Adjacency List** | O(1) | O(depth) recursive | O(1) | O(1) | O(n) recursive | Minimal (1 FK per row) |
| **Closure Table** | O(1) | O(1) flat query | O(depth) | O(n) delete+reinsert | O(n) | High (rows = edges) |
| **Materialized Path** | O(1) | O(1) LIKE query | O(1) | O(n) update paths | O(n) LIKE delete | Moderate (path string) |
| **Nested Set** | O(1) | O(1) range query | O(n) rebalance | O(n) rebalance | O(1) range | Moderate (2 ints per row) |

([Baeldung](https://www.baeldung.com/sql/storing-tree-in-rdb), [MongoDB Docs](https://www.mongodb.com/docs/manual/applications/data-models-tree-structures/), [Ackee Blog](https://www.ackee.agency/blog/hierarchical-models-in-postgresql))

### Recommendation for Framework Use

```
    DECISION TREE: WHICH STORAGE STRATEGY?

    Is the tree read-heavy with rare mutations?
    |
    +-- YES --> Nested Set or Materialized Path
    |           (fast subtree reads, slow writes)
    |
    +-- NO --> How deep is the tree typically?
              |
              +-- Shallow (< 5 levels) --> Adjacency List
              |   (simplest; recursive CTE handles subtree)
              |
              +-- Deep (5+ levels) --> Closure Table
                  (no recursion needed; best general-purpose)
```

**For N3TX specifically:** The **adjacency list** (parent_id FK) is the right default. N3TX already uses SQLite with FK relationships. Adding a `parent_id` self-referential FK is:

- **Zero new infrastructure** -- just another column
- **Compatible with existing CRUD** -- no new query patterns for basic ops
- **Upgradeable** -- a closure table can be added later as a materialized view

The key addition would be a **`children` computed property** (or `ListRef[Self]`) that hydrates child entities. For SQLite's recursive CTE support (available since 3.8.3, 2014):

```sql
-- Get full subtree with adjacency list + recursive CTE
WITH RECURSIVE subtree AS (
    SELECT * FROM blocks WHERE id = :root_id
    UNION ALL
    SELECT b.* FROM blocks b
    JOIN subtree s ON b.parent_id = s.id
)
SELECT * FROM subtree;
```

### Notion's Actual Storage Approach

Notion uses the **adjacency list** pattern at Postgres scale:

- Each block stores `parent_id` and an ordered `content` array of child IDs
- Sharded by **workspace_id** (all blocks in a workspace on the same shard)
- Render tree traversal happens **client-side** after fetching all blocks for a page
- At **200B+ blocks**, they needed 480 shards across 96 Postgres instances

([Notion Sharding Blog](https://www.notion.com/blog/sharding-postgres-at-notion), [Onehouse Analysis](https://www.onehouse.ai/blog/notions-journey-through-different-stages-of-data-scale))

This is strong evidence that the adjacency list pattern works even at extreme scale -- the complexity moves to the sharding layer, not the tree representation.

---

## :bulb: Decision Framework: When to Adopt Block Primitives

### The Application Type Matrix

Not every application benefits from block-based nesting. This matrix maps application types to block model fit:

| Application Type | Block Model Fit | Why | Better Alternative |
|-----------------|:--------------:|-----|-------------------|
| **Knowledge base / Wiki** | :white_check_mark: Strong | Content nests naturally; pages contain pages | -- |
| **CMS / Content editor** | :white_check_mark: Strong | Rich content composition; reusable components | -- |
| **Project management** | :white_check_mark: Moderate | Tasks can have subtasks; descriptions are rich content | Flat tasks + relations may suffice |
| **Note-taking** | :white_check_mark: Strong | Outliner UX; nested thoughts; drag-and-drop reordering | -- |
| **Dashboard / Analytics** | :x: Weak | Widgets are positioned, not nested | Grid layout system |
| **Form builder** | :white_check_mark: Moderate | Form fields as blocks; conditional sections as children | Flat field list + logic rules |
| **Data-grid / Spreadsheet** | :x: Weak | Rows and columns are flat; nesting adds confusion | Typed records + relations |
| **E-commerce catalog** | :x: Weak | Products are flat entities with FK relations | Categories + products (FK tree) |
| **Chat / Messaging** | :x: Weak | Messages are sequential, not hierarchical (except threads) | Flat messages + thread_id FK |
| **Code editor / IDE** | :white_check_mark: Moderate | AST is a tree; block model maps to syntax nodes | Specialized AST storage |

### The Decision Criteria (Measurable)

Use this checklist to determine if your application warrants block primitives:

| Criterion | Threshold | Score |
|-----------|-----------|:-----:|
| Content types mix text, media, and structured data | > 3 content types | +2 |
| Users need to **reorder** content by drag-and-drop | Required feature | +2 |
| Content naturally nests (outlines, sub-items, sections) | > 2 nesting levels typical | +2 |
| Users create **templates** with reusable block patterns | Required feature | +1 |
| Content is **collaborative** (multiple editors) | Required feature | +1 |
| Application needs rich text editing | WYSIWYG required | +1 |
| Data relationships are primarily hierarchical | > 50% of relations are parent-child | +1 |
| Data relationships are primarily tabular/relational | > 50% of relations are FK-based | -2 |
| Application is primarily a CRUD data entry tool | > 70% of interactions are form fills | -2 |
| Real-time collaborative editing is required | With undo/redo across users | -1 (complexity cost) |

**Scoring:**
- **6+ points**: Block primitives are a strong fit. Invest in a `hasChildren` capability.
- **3-5 points**: Block model is useful but not essential. Consider an optional mixin.
- **0-2 points**: Flat entities with FK relations serve you better. Don't add block complexity.
- **Negative**: Block model would be actively harmful. Stick with records + relations.

---

## :office: Build vs. Buy Analysis

### Cost to Hand-Roll Recursive Tree Storage

Based on industry data and framework implementation patterns:

| Component | Estimated Effort | Complexity |
|-----------|:----------------:|:----------:|
| Self-referential FK model + migration | 2-4 hours | Low |
| Recursive CTE queries (get subtree, ancestors) | 4-8 hours | Medium |
| CRUD operations respecting tree structure | 8-16 hours | Medium |
| Drag-and-drop reordering with sibling order | 16-32 hours | High |
| Tree-aware pagination (load children on demand) | 8-16 hours | Medium |
| Permission inheritance through tree | 16-32 hours | High |
| Undo/redo for tree operations | 40-80 hours | Very High |
| Frontend tree rendering (expand/collapse) | 16-32 hours | Medium |
| Real-time collaborative tree editing | 80-160 hours | Extreme |
| **Total (basic, no collaboration)** | **55-110 hours** | -- |
| **Total (full, with collaboration)** | **190-380 hours** | -- |

At **$150/hr** (senior developer loaded cost), that is:
- **Basic tree support**: $8K-$17K per application
- **Full collaborative tree**: $29K-$57K per application

### Framework Primitive Value Proposition

If a framework provides tree primitives, the cost per application drops dramatically:

| Approach | Per-App Cost | Framework Investment | Break-Even |
|----------|:------------:|:--------------------:|:----------:|
| Hand-roll each time | $8K-$17K | $0 | N/A |
| Framework provides basic tree | $1K-$2K (customization) | $15K-$25K | **2-3 apps** |
| Framework provides full tree + UI | $500-$1K | $40K-$60K | **4-6 apps** |

> **Key Insight:** If N3TX expects to power **more than 3 applications** that involve content nesting, parent-child hierarchies, or tree-structured data, a framework-level `hasChildren` primitive pays for itself. The ROI is clear -- but the scope must be carefully bounded to avoid the "everything is a block" trap.

### What the Framework Should Provide vs. Leave to Developers

| Layer | Framework Provides | Developer Provides |
|-------|-------------------|-------------------|
| **Data model** | `parent_id` FK, `children` computed field, `order` field | Custom block types, type-specific properties |
| **Storage** | Recursive CTE queries, tree-aware pagination | Custom indexes for deep trees |
| **API** | `GET /items/:id/children`, tree-aware CRUD | Custom tree endpoints if needed |
| **Schema** | `hasChildren: true` in JSON Schema, `$ref` to self | UI hints for tree rendering |
| **UI** | Tree expand/collapse, indent/outdent, drag-to-reorder | Custom block renderers |
| **Collaboration** | **Nothing** (leave to specialized libs) | CRDT integration if needed |

---

## :bar_chart: Maintenance Economics at Scale

### Schema Migration When Block Types Evolve

One of the hidden costs of the block model is **schema evolution**. When block types change:

| Scenario | Migration Cost | Risk Level |
|----------|:-------------:|:----------:|
| Adding a new block type | Low (new type value; no migration needed) | :white_check_mark: Safe |
| Adding a property to existing type | Medium (backfill existing blocks) | :warning: Moderate |
| Renaming a block type | High (update all type values + client code) | :x: Dangerous |
| Changing property structure | High (data migration on all blocks of type) | :x: Dangerous |
| Removing a block type | Medium (orphaned blocks need handling) | :warning: Moderate |

**Notion's approach:** All blocks share the same schema. Type-specific behavior lives in the `properties` JSON object and client-side rendering logic. This means **adding a new block type requires zero database migration** -- just new client code. This is the strongest argument for storing block properties as a JSON column rather than typed columns.

### Storage Bloat

At scale, block models create significantly more rows than traditional models:

| Content Equivalent | Traditional Model | Block Model | Bloat Factor |
|-------------------|:-----------------:|:-----------:|:------------:|
| A simple web page | 1 page row | 50-200 block rows | 50-200x |
| A product catalog (1K items) | 1K product rows | 1K products + 5K-20K description blocks | 6-21x |
| A wiki (10K articles) | 10K article rows | 10K pages + 500K-2M content blocks | 51-201x |

Notion's experience: **20 billion blocks (2021) -> 200 billion blocks (2024)** for what is essentially a productivity tool. That is **hundreds of terabytes compressed** in Postgres. ([Notion Data Lake](https://www.notion.com/blog/building-and-scaling-notions-data-lake))

For **most N3TX applications**, this bloat factor is irrelevant -- you will never approach Notion's scale. But it is worth understanding that **a 10K-record application becomes a 100K-1M record application** when you block-ify content. Plan your SQLite storage accordingly.

### Backward Compatibility Requirements

The block model creates a **contract between stored data and rendering code**. Every block type that has ever been saved must be renderable forever (or gracefully degraded). This is why:

- Notion's API returns `"unsupported"` for block types the API version does not handle
- WordPress Gutenberg maintains a `deprecated` array on block registrations for old serialization formats
- Sanity Portable Text uses schema validation to reject invalid block structures at write time

**Recommendation for N3TX:** If implementing blocks, require a **block type registry** with versioned schemas. Unknown block types should render as a generic "unsupported block" placeholder, not crash.

---

## :bulb: Recommendations for N3TX

Based on the industry landscape and N3TX's philosophy of "the model is the app," here is the recommended approach:

### 1. Add `hasChildren` as an Optional Model Capability, Not a Core Primitive

```python
# Recommended pattern: opt-in tree nesting via model definition
class WikiPage(ProtoModel):
    __tablename__ = 'wiki_pages'
    __storable__ = True
    __tree__ = True  # Enables parent_id, children, ordering

    title: str = Field(min_length=1)
    content: str = Field(default='')
    # parent_id, children, and order are auto-injected by __tree__ = True
```

This follows N3TX's existing patterns (`__storable__`, `__agent__`, `__access__`) and keeps the block capability **additive, not mandatory**.

### 2. Use Adjacency List Storage (parent_id FK)

```
    N3TX TREE STORAGE (PROPOSED)

    [WikiPage Table]
    +-------+--------+-----------+-------+
    | id    | title  | parent_id | order |
    +-------+--------+-----------+-------+
    | uuid1 | "Home" | NULL      | 0     |
    | uuid2 | "API"  | uuid1     | 0     |
    | uuid3 | "Auth" | uuid1     | 1     |
    | uuid4 | "JWT"  | uuid3     | 0     |
    +-------+--------+-----------+-------+

    Render tree:
    Home
    +-- API Docs
    +-- Auth Guide
        +-- JWT Tokens
```

### 3. Expose Tree Structure in JSON Schema

```json
{
  "$schema": "...",
  "$id": "WikiPage",
  "properties": {
    "title": { "type": "string" },
    "content": { "type": "string" },
    "parent_id": { "type": ["string", "null"], "format": "uuid" },
    "children": {
      "type": "array",
      "items": { "$ref": "#" },
      "readOnly": true
    },
    "order": { "type": "integer" }
  },
  "ui": {
    "tree": true,
    "renderer": { "list": "ntx-tree", "item": "ntx-item" }
  }
}
```

### 4. Do NOT Build Collaborative Editing or CRDT

This is a **framework boundary** decision. The block model adds value as a data structure pattern. Collaborative editing is a different problem entirely, requiring 6-12+ months of CRDT/OT engineering. Leave that to BlockSuite, Yjs, or similar specialized libraries.

### 5. Provide a Clear Upgrade Path

```
    CAPABILITY TIERS

    Tier 1: Flat Entities (current N3TX)
    ========================================
    ProtoModel -> CRUD -> JSON Schema -> UI

    Tier 2: Tree Entities (__tree__ = True)
    ========================================
    ProtoModel + TreeMixin -> Tree CRUD ->
    Enhanced Schema (hasChildren) -> Tree UI

    Tier 3: Block Entities (__blocks__ = True)  [FUTURE]
    ========================================
    ProtoModel + BlockMixin -> Block CRUD ->
    Block Schema (typed children) -> Block Editor UI

    Tier 4: Collaborative Blocks  [OUT OF SCOPE]
    ========================================
    External CRDT library + custom integration
```

---

### Summary Decision Matrix

| Question | Answer | Confidence |
|----------|--------|:----------:|
| Should N3TX support tree nesting? | **Yes, as an optional mixin** | High |
| Should every entity be a block? | **No -- opt-in via `__tree__`** | High |
| Which storage strategy? | **Adjacency list (parent_id FK)** | High |
| Should N3TX build collaborative editing? | **No -- out of scope** | Very High |
| When does the block model pay off? | **3+ apps with hierarchical content** | Medium |
| What is the biggest risk? | **Over-generalization ("everything is a block" trap)** | High |
| What is the biggest opportunity? | **Wiki/CMS/knowledge-base apps get tree nesting for free** | High |

---

## :link: Sources

1. [Notion: The Data Model Behind Notion's Flexibility](https://www.notion.com/blog/data-model-behind-notion) -- Official block architecture explanation
2. [Notion: Herding Elephants -- Sharding Postgres at Notion](https://www.notion.com/blog/sharding-postgres-at-notion) -- Database scaling case study
3. [Notion: Building and Scaling Notion's Data Lake](https://www.notion.com/blog/building-and-scaling-notions-data-lake) -- Data infrastructure evolution
4. [Notion: The Great Re-shard](https://www.notion.com/blog/the-great-re-shard) -- Zero-downtime migration to 96 instances
5. [Notion: Creating the Notion API](https://www.notion.com/blog/creating-the-notion-api) -- API design philosophy
6. [Notion Developers: Block Reference](https://developers.notion.com/reference/block) -- Block type specifications
7. [ByteByteGo: Storing 200 Billion Entities](https://blog.bytebytego.com/p/storing-200-billion-entities-notions) -- Data lake deep dive
8. [Onehouse: Notion's Journey Through Different Stages of Data Scale](https://www.onehouse.ai/blog/notions-journey-through-different-stages-of-data-scale) -- Infrastructure timeline
9. [Lenny's Newsletter: Inside Notion -- Ivan Zhao](https://www.lennysnewsletter.com/p/inside-notion-ivan-zhao) -- Founding story, lost years, near collapse
10. [KITRUM: The Phenomenal Journey of Ivan Zhao](https://kitrum.com/blog/the-phenomenal-journey-of-ivan-zhao-notions-founder/) -- Japan rewrite, Web Components failure
11. [Notion: First Block with Ivan Zhao and Simon Last](https://www.notion.com/blog/first-block-with-ivan-zhao-simon-last) -- "Blocks as primitives" philosophy
12. [SaaStr: Notion at $11 Billion](https://www.saastr.com/notion-and-growing-into-your-10b-valuation-a-masterclass-in-patience/) -- Valuation analysis
13. [GetLatka: Notion Revenue](https://getlatka.com/companies/notion) -- $600M revenue, 4M customers
14. [Sacra: Notion Revenue & Valuation](https://sacra.com/c/notion/) -- $500M ARR estimate
15. [TapTwice Digital: Notion Statistics](https://taptwicedigital.com/stats/notion) -- 100M users, funding rounds
16. [GetLatka: Coda Revenue](https://getlatka.com/companies/coda) -- $41M revenue, team size
17. [Skywork AI: Coda vs Notion](https://skywork.ai/blog/ai-agent/coda-vs-notion/) -- Architecture comparison
18. [Super.so: Notion vs Coda](https://super.so/blog/notion-vs-coda) -- Feature and philosophy comparison
19. [Craft.do: Series B Announcement](https://www.craft.do/blog/craft-raises-12m-series-b-round) -- $12M funding
20. [TechCrunch: Craft Docs $8M](https://techcrunch.com/2021/04/01/collaborative-ios-app-craft-docs-secures-8m-led-by-creandum-and-a-skyscanner-mafia/) -- Initial funding
21. [Crunchbase: Roam Research](https://www.crunchbase.com/organization/roam-research) -- $11.4M funding, $200M valuation
22. [BlockSuite GitHub](https://github.com/toeverything/blocksuite) -- Open-source block editor framework
23. [BlockSuite: Document-Centric CRDT-Native Editors](https://block-suite.com/blog/document-centric.html) -- CRDT architecture
24. [Tracxn: AFFiNE Funding](https://tracxn.com/d/companies/affine/__Mo6BFrzUISfgrA8pldUKbTH0mEXrtjxwRlYfPIADZqs) -- $18M raised
25. [AppFlowy GitHub](https://github.com/AppFlowy-IO/AppFlowy) -- 60K+ stars, Rust/Flutter architecture
26. [Outline GitHub](https://github.com/outline/outline) -- Open-source team wiki
27. [Anytype Docs: Blocks](https://doc.anytype.io/anytype-docs/basics/object-editor/blocks) -- Anytype block model
28. [Anytype Protocol: any-block](https://github.com/anyproto/any-block) -- Protocol Buffer block definitions
29. [WordPress Gutenberg Stats](https://gutenstats.blog/) -- 82.7M installs, 264M posts
30. [AIOSEO: WordPress Statistics](https://aioseo.com/wordpress-statistics/) -- 43.4% CMS market share
31. [WordPress Gutenberg Issue #35719](https://github.com/WordPress/gutenberg/issues/35719) -- Performance with reusable blocks
32. [WordPress Gutenberg Issue #64219](https://github.com/WordPress/gutenberg/issues/64219) -- Performance degradation with 3000+ patterns
33. [Baeldung: Storing a Tree in a Relational Database](https://www.baeldung.com/sql/storing-tree-in-rdb) -- Storage strategy comparison
34. [MongoDB: Model Tree Structures](https://www.mongodb.com/docs/manual/applications/data-models-tree-structures/) -- Tree storage patterns
35. [Ackee Blog: Hierarchical Models in PostgreSQL](https://www.ackee.agency/blog/hierarchical-models-in-postgresql) -- Benchmark comparison
36. [Springer: CRDT Supporting Selective Undo](https://link.springer.com/chapter/10.1007/978-3-319-19129-4_16) -- Undo/redo complexity in collaborative editing
37. [Zed Blog: CRDTs in Zed](https://zed.dev/blog/crdts) -- CRDT implementation lessons
38. [Sanity.io: Headless CMS](https://www.sanity.io/unified-content-operations-system) -- Portable Text, schema-as-code
39. [Educative: Notion System Design](https://www.educative.io/blog/notion-system-design) -- System architecture decomposition
40. [Rosemet: Pros and Cons of Notion](https://www.rosemet.com/pros-and-cons-of-notion/) -- Performance and complexity criticism
41. [HN: Is Notion Still Slow?](https://news.ycombinator.com/item?id=39033834) -- User performance complaints (2024)
42. [HN: The Data Model Behind Notion's Flexibility](https://news.ycombinator.com/item?id=27200177) -- Technical discussion
43. [6sense: Notion Market Share](https://6sense.com/tech/collaborative-workspaces/notion-market-share) -- 34K+ companies using Notion
44. [Nuclino Product](https://www.nuclino.com/product) -- Lightweight block wiki features
45. [DatoCMS: Hierarchical Sorting](https://www.datocms.com/docs/content-modelling/trees) -- CMS tree support
46. [GetDX: Developer Experience Index](https://getdx.com/research/the-one-number-you-need-to-increase-roi-per-engineer/) -- DXI ROI measurement
47. [Notion Developers: Working with Page Content](https://developers.notion.com/docs/working-with-page-content) -- API nesting limits
48. [Thomas Frank: Notion API Rate Limits](https://thomasjfrank.com/how-to-handle-notion-api-request-limits/) -- API limitations
