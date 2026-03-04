# Polymorphic Systems for N3TX: Executive Summary

> *Standalone summary. Full analysis: [polymorphic-system-analysis.md](../research/polymorphic-system/polymorphic-system-analysis.md)*

---

## The Question

**Should N3TX add first-class support for polymorphic data models -- where multiple specialized types (Article, Video, Podcast) share a common base (Content) with automatic storage discrimination, schema union generation, and type-aware rendering?**

Today, N3TX delivers on its core promise: define a Python model, get a working API, schema, and UI. But this works for flat, independent models. The moment an application needs a unified `Content` type with specialized subtypes queryable from a single endpoint, the developer must work around the framework rather than with it. They define separate models, query separate endpoints, and manually aggregate results.

Polymorphism is the mechanism that would close this gap. One model hierarchy, one table, one endpoint, one schema -- with type-specific fields, access rules, and rendering all derived from the subclass definitions.

**The strategic framing:** This is not a niche database optimization. Polymorphism is the dominant architectural pattern at Stripe (PaymentMethods), WordPress (post types powering 43% of the web), Shopify (product variants), Salesforce (polymorphic relationships), Notion (50+ block types), and GitHub (40+ webhook event types). Every non-trivial application eventually needs it.

> N3TX's unique opportunity: no framework in the market today generates a discriminated union JSON Schema from model definitions and propagates it to automatically adapt frontend rendering. Django, Rails, Strapi, and Prisma all require manual wiring at multiple layers. N3TX can make "define a subclass, get full-stack polymorphism" real.

---

## Key Findings at a Glance

| # | Finding | Evidence |
|---|---------|---------|
| 1 | **N3TX already has 60-70% of the machinery** | `ProtoModel` inheritance, `__init_subclass__()`, `$defs`, DynamicClass system, `__abstract__` flag, per-model access rules |
| 2 | **Remaining work: 13-19 engineering days** across 4 phases | Storage (2-3d) + Schema (3-4d) + Frontend (5-7d) + Routes (3-5d) |
| 3 | **Phases 1-2 alone (5-7 days) deliver the core differentiator** | STI storage + `oneOf` schema output -- the two capabilities with highest value |
| 4 | **No competitor offers schema-propagated polymorphism** | Researched Django, Rails, Strapi, Prisma, Contentful, Sanity -- none auto-generate discriminated union schemas from model hierarchies |
| 5 | **STI is the right default for N3TX** | SQLite-friendly, simplest to implement, aligns with "zero to working" philosophy |
| 6 | **Pydantic v2 natively supports discriminated unions** | `Annotated[Union[Article, Video], Discriminator('type')]` generates the exact JSON Schema format we need |
| 7 | **Adding a new type: 5 minutes vs. 2 hours** | Schema-driven approach requires 1 file change vs. 9-14 files in manual approach |
| 8 | **GitLab banned new STI at their scale** -- but their scale is irrelevant to ours | GitLab serves 30M+ users on PostgreSQL. N3TX targets SQLite apps with sub-100K rows per table. |

---

## What the Industry Tells Us

**The pattern is settled.** Stripe, GitHub, Notion, Figma, CloudEvents, and every major schema registry use an explicit `type` discriminator field with type-specific data. The remaining question is how deeply to integrate it.

| Company | Pattern | Scale |
|---------|---------|-------|
| **Stripe** | `PaymentMethod.type` + type-specific hash | $1T+ processed, 15+ payment types |
| **WordPress** | `wp_posts.post_type` discriminator (STI) | 43% of all websites worldwide |
| **Shopify** | Composition + metafields (not inheritance) | $235.9B GMV, 4.6M+ merchants |
| **Notion** | `block.type` + matching nested object | 50+ block types in a recursive tree |
| **GitHub** | `X-GitHub-Event` header + `action` field | 40+ event types, multiple actions each |
| **Salesforce** | Polymorphic relationships + Record Types | 150,000+ customers |

**Three industry trends converge in N3TX's favor:**

1. **Language-level discriminated unions** -- TypeScript, Python, Kotlin, Rust, Java have all added first-class sum types. The industry is moving type boundaries earlier in the stack -- from runtime database queries to compile-time type checks.

2. **Schema-driven everything** -- The CMS industry (Strapi, Contentful, Sanity) converged on "define types, generate APIs and UIs from schema." N3TX already works this way. Polymorphism is the natural extension.

3. **Composition over deep inheritance** -- Shopify and Stripe favor flat hierarchies with typed metadata, not deep class trees. STI with a discriminator column is the pragmatic middle ground that balances flexibility with simplicity.

**The cautionary tales matter, but not equally:**

- **Stripe's Sources API** (2015-2017): tried to force all payment methods into one polymorphic state machine. Cards finalize immediately; bank transfers take days. Forcing them together created "confusing integration and overloaded abstractions." Deprecated after 2 years. **Lesson:** Do not force fundamentally different lifecycles into a single type hierarchy.

- **GitLab's STI ban:** tables exceeded hundreds of millions of rows, causing lock contention and production incidents. **Lesson:** STI has a ceiling. But GitLab serves 30M+ users on PostgreSQL -- a different universe from N3TX's SQLite target deployments.

- **Magento's EAV:** a product with 50 attributes requires 50+ JOINs. Product pages 3-5x slower than Shopify without aggressive caching and flat table denormalization. **Lesson:** EAV is the anti-pattern N3TX should avoid entirely. JSONB hybrid or STI are the correct approaches for type-specific attributes.

---

## Where We Stand Today

```
WHAT N3TX ALREADY HAS         WHAT IS MISSING
============================     ============================
[x] ProtoModel inheritance       [ ] Discriminator column (_type)
[x] __init_subclass__() hook     [ ] Type-filtered queries
[x] __abstract__ flag            [ ] oneOf/discriminator schema
[x] $defs for nested types       [ ] Frontend type dispatch
[x] DynamicClass per type        [ ] Per-entity component tags
[x] Per-model access rules       [ ] Polymorphic route generation
[x] Per-model UI config          [ ] Type-aware form generation
[x] SQL pushdown (Where rule)    [ ] Type selector in create forms
[x] Component tag resolution     [ ] Mixed-type list rendering
```

**The existing BaseUser pattern is STI in embryonic form.** `BaseUser` declares `__abstract__ = True` and provides shared fields (`name`, `email`, `role`, `password_hash`) plus `login()` and `register()` endpoints. The concrete `User` class inherits everything and adds app-specific fields. This is single-table inheritance without the discriminator column -- the exact seed of the pattern we would formalize.

**The key codebase extension points are already in place:**
- `__init_subclass__()` in `proto_model.py` fires for every new model subclass -- the natural hook for subtype registration
- `$defs` in `ProtoModel.schema()` already creates nested schemas for referenced models -- we would extend this to include subtypes
- `N3TX.SCHEMA()` in `N3TX.js` already iterates `$defs` and creates DynamicClasses for each -- polymorphic subtypes would be processed identically
- `Where.sql_filter()` in `rules.py` already generates parameterized SQL conditions -- composing type filters with access filters is a natural extension

---

## The Numbers

### Implementation Cost

| Phase | What | Effort | Cumulative |
|-------|------|:------:|:----------:|
| **Phase 1** | STI discriminator column, type-filtered queries | 2-3 days | 2-3 days |
| **Phase 2** | `oneOf` + discriminator schema, subtype DynamicClasses | 3-4 days | 5-7 days |
| **Phase 3** | Frontend mixed-type rendering, type-aware forms | 5-7 days | 10-14 days |
| **Phase 4** | Polymorphic routes, per-subtype auth composition | 3-5 days | 13-19 days |

### Developer Productivity (Per New Type)

| Approach | Files Changed | Time | Over 50 Types |
|----------|:------------:|:----:|:-------------:|
| Manual (no polymorphism) | 9-14 | ~2 hours | ~4 weeks |
| N3TX (Phase 2+) | 1 | ~5 minutes | ~4 hours |

### Competitive Position After Phase 2

| Capability | Django | Rails | Strapi | Prisma | **N3TX** |
|-----------|:------:|:-----:|:------:|:------:|:----------:|
| STI support | Plugin | Built-in | No | No | **Yes** |
| Auto discriminator | No | Yes | N/A | No | **Yes** |
| `oneOf` schema output | No | No | No | No | **Yes (unique)** |
| Schema-driven UI per subtype | No | No | Partial | No | **Yes (unique)** |
| Per-subtype access rules | Manual | Manual | Plugin | Manual | **Built-in** |

---

## The Recommendation

**Implement Phases 1-2 now (5-7 engineering days). Defer Phases 3-4.**

Phases 1-2 deliver the **core differentiator** -- discriminator storage and `oneOf` schema generation -- with low risk and no breaking changes. The polymorphism is opt-in via `__discriminator__` ClassVar; existing models are completely unaffected.

**What a developer writes after Phase 2:**

```python
class Content(ProtoModel):
    __tablename__ = 'content'
    __storable__ = True
    __discriminator__ = '_type'    # <- this is new

    title: str
    author: str

class Article(Content):
    body: str

class Video(Content):
    video_url: str
    duration: int = 0
```

**What they get:** A `content` table with a `_type` discriminator column. `Article.list()` returns only articles. `Content.list()` returns everything. `GET /Content` returns a JSON Schema with `oneOf` + `discriminator` mapping. The frontend creates separate DynamicClasses for each subtype from `$defs`. Access rules compose with type filtering via SQL pushdown.

**Why STI first:** SQLite-friendly. Simplest to implement. Aligns with "zero to working." Migrating to CTI later is a documented, incremental process if needed.

**Why defer Phases 3-4:** Mixed-type frontend rendering and polymorphic routes are valuable but complex. They matter only when a specific use case demands a unified mixed-type list in the UI. Build it then, not speculatively.

---

## Top 3 Risks

| # | Risk | Probability | Mitigation |
|---|------|:-----------:|-----------|
| 1 | **STI table bloat at scale** -- nullable columns accumulate, queries slow down | Low (N3TX targets sub-100K row tables, not GitLab-scale) | Document max 5-8 subtypes. Provide CTI migration path. |
| 2 | **Authorization gap with shared tables** -- stricter subtype rules bypassed by base-type queries | Low (but high impact) | Compose type filter with access filter: `WHERE (_type = 'article' AND 1=1) OR (_type = 'draft' AND user_owner = ?)`. The `Where` rule class already supports this. |
| 3 | **Developer misuse ("Polymorphism Envy")** -- creating hierarchies for types that should be separate | High probability, low impact | Include decision framework in docs. Detection rule: if the base type name sounds artificial (`BaseEntity`, `GenericItem`), you are forcing inheritance. |

---

## Next Steps

### Week 1 (Days 1-3): Phase 1 -- Storage Layer

| Task | File | Description |
|------|------|-------------|
| Detect `__discriminator__` | `proto_model.py` | In `__init_subclass__()`, register subtypes in `__subtypes__` dict on the base class |
| Inject `_type` column | `sqlite_migration.py` | When model has `__discriminator__`, add `_type TEXT NOT NULL DEFAULT '{classname}'` |
| Filter by `_type` on read | `sqlite_storage.py` | `list()` and `get()` add `WHERE _type = ?` for subtype queries |
| Inject `_type` on write | `sqlite_storage.py` | `create()` sets `_type = model_class.__name__` before INSERT |
| Test STI CRUD | New test file | Create, read, list (all types), list (single type), update, delete |

### Week 2 (Days 4-7): Phase 2 -- Schema Layer

| Task | File | Description |
|------|------|-------------|
| Generate `oneOf` + `discriminator` | `proto_model.py` | When `__discriminator__` is set, wrap subtype schemas in `oneOf` with mapping |
| Include subtypes in `$defs` | `proto_model.py` | Each subtype gets its own `$defs` entry with `access`, `ui`, `methods` |
| Detect polymorphic schema | `N3TX.js` | `SCHEMA()` recognizes `oneOf` + `discriminator`, creates per-subtype DynamicClasses |
| Route entities by type | `N3TX.js` | `DynamicClass.READ` dispatches entities to correct subtype class via discriminator |
| Integration tests | New test file | Validate schema output format, frontend DynamicClass creation, type resolution |

### After Phase 2: Decision Point

- **Do we have a concrete use case requiring mixed-type frontend lists?**
  - If yes: proceed to Phase 3 (5-7 days for mixed-type rendering, type-aware forms)
  - If no: ship Phases 1-2 as a release, gather community and developer feedback

- **Is there demand for unified polymorphic API endpoints?**
  - If yes: proceed to Phase 4 (3-5 days for `GET /content` returning all types, `POST /content` dispatching by `_type`)
  - If no: developers can use per-subtype endpoints (which already work in Phase 1)

### Documentation Deliverables

- Update `CLAUDE.md` with polymorphic model patterns and `__discriminator__` usage
- Add decision framework to developer docs: when to use polymorphism, when not to, quantitative thresholds
- Add migration guide for converting separate models to a polymorphic hierarchy
- Include anti-pattern warnings: >8 subtypes, <30% shared fields, artificial base names

---

*Summary based on analysis of 5 research documents, 25+ primary sources, and direct codebase audit of 8 key framework files. Full analysis: [polymorphic-system-analysis.md](../research/polymorphic-system/polymorphic-system-analysis.md)*
