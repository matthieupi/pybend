# New Features: Grant Workflows, Notifications, Search, Tagging, and Beyond

**Research Document -- Grant Watcher Feature Landscape Analysis**
**Date:** 2026-03-04 | **Platform:** N3TX v0.10 | **Audience:** Technical CEO + Engineering Leadership

---

## Executive Summary

Grant Watcher today is a functional demo: it stores grants, scans sources, and renders UI from schema. But a demo is not a product. Commercial grant platforms like [Instrumentl](https://www.instrumentl.com/), [Fluxx](https://www.fluxx.io/), and [Grantx](https://grantx.com/) charge **$15--$40/user/month** and compete on workflow automation, intelligent matching, and collaboration. The gap between Grant Watcher and these platforms is not architecture -- N3TX's schema-driven model already solves the hard parts of data plumbing. The gap is **domain features**.

This document maps 9 feature categories, estimates implementation effort against user value, and recommends a phased rollout. The central finding: **5 of the 9 features are "nearly free" because N3TX's existing patterns already support them** -- they require new models and a few `@expose_route` methods, not framework extensions. The remaining 4 require modest framework enhancements (search indexing, scheduler integration, WebSocket subscriptions, and aggregate endpoints).

> **Key Insight:** The highest-ROI feature is the **grant lifecycle workflow** -- it touches every user interaction, requires zero framework changes, and can ship in under a week. The second is **tagging + search**, which unlocks the matching engine that makes Grant Watcher genuinely useful rather than merely functional.

---

## Table of Contents

1. [Grant Lifecycle Workflow](#1--grant-lifecycle-workflow)
2. [Notifications & Alerts](#2--notifications--alerts)
3. [Search & Advanced Filtering](#3--search--advanced-filtering)
4. [Tagging & Categorization](#4--tagging--categorization)
5. [Collaboration Features](#5--collaboration-features)
6. [Grant Matching & Recommendations](#6--grant-matching--recommendations)
7. [Scheduling & Automation](#7--scheduling--automation)
8. [Reporting & Analytics](#8--reporting--analytics)
9. [Feature Prioritization & Roadmap](#9--feature-prioritization--roadmap)
10. [Feasibility & ROI Analysis](#10--feasibility--roi-analysis)

---

## 1. Grant Lifecycle Workflow

### The Problem

The current `Grant` model has a single `status` field -- a plain string with no enforcement:

```python
# /workspace/example_grants/models/grant.py (line 31)
status: str = Field(default='discovered', description="discovered | reviewed | applied | expired")
```

There is no validation on transitions. Any authenticated user can `PATCH /grants/1 {"status": "awarded"}` even if the grant was never applied to. There is no history of who changed the status, when, or why. This is a status field pretending to be a workflow.

### What Commercial Platforms Do

The [Grants.gov lifecycle](https://www.grants.gov/learn-grants/grants-101/the-grant-lifecycle) defines three canonical phases: **pre-award** (discovery through application), **award** (review, negotiation, notification), and **post-award** (implementation, monitoring, closeout). [NetSuite's grant lifecycle model](https://www.netsuite.com/portal/resource/articles/crm/grant-management-life-cycle.shtml) further breaks this into 8 distinct stages. Instrumentl tracks grants through **Prospecting, Planned, In Progress, Submitted, Awarded, Rejected** with deadline-driven automation ([Instrumentl](https://www.instrumentl.com/blog/fluxx-grantseeker-pricing)).

### Proposed State Machine

```
                         +-----------+
                         | DISCOVERED|  <-- Agent creates
                         +-----+-----+
                               |
                          review()
                               |
                         +-----v-----+
                    +--->| REVIEWED  |
                    |    +-----+-----+
                    |          |
                    |     shortlist() / dismiss()
                    |          |            \
                    |    +-----v-----+  +---v------+
                    |    |SHORTLISTED|  | DISMISSED |
                    |    +-----+-----+  +----------+
                    |          |
                    |      apply()
                    |          |
                    |    +-----v-----+
                    |    |  APPLIED  |
                    |    +-----+-----+
                    |          |
                    |     award() / reject()
                    |          |            \
                    |    +-----v-----+  +---v------+
                    |    |  AWARDED  |  | REJECTED |
                    |    +-----------+  +----------+
                    |
                    |  expire() -- automated, deadline-driven
                    |          |
                    |    +-----v-----+
                    +----| EXPIRED   |
                         +-----------+
```

### Implementation: Zero Framework Changes Needed

Every transition maps naturally to an `@expose_route` method on the `Grant` model. N3TX already handles ABAC on methods, user injection, and schema exposure for frontend rendering. Here is how the model would look:

```python
# Valid states and transitions
GRANT_STATES = {
    'discovered': ['reviewed', 'expired'],
    'reviewed':   ['shortlisted', 'dismissed', 'expired'],
    'shortlisted':['applied', 'dismissed', 'expired'],
    'applied':    ['awarded', 'rejected', 'expired'],
    'awarded':    [],
    'rejected':   [],
    'dismissed':  [],
    'expired':    [],
}

class Grant(ActorModel):
    # ... existing fields ...
    status: str = Field(default='discovered')

    def _transition(self, new_status: str, user: User = None) -> str:
        allowed = GRANT_STATES.get(self.status, [])
        if new_status not in allowed:
            raise MethodError(
                f"Cannot transition from '{self.status}' to '{new_status}'", 400
            )
        old = self.status
        Grant.update(self.id, {'status': new_status})
        # Optionally log to GrantHistory (see below)
        return json.dumps({'action': new_status, 'from': old})

    @expose_route('/review', methods=['POST'], access=AUTHENTICATED)
    def review(self, user: User = None) -> str:
        return self._transition('reviewed', user)

    @expose_route('/shortlist', methods=['POST'], access=AUTHENTICATED)
    def shortlist(self, user: User = None) -> str:
        return self._transition('shortlisted', user)

    @expose_route('/apply', methods=['POST'], access=AUTHENTICATED)
    def apply(self, user: User = None) -> str:
        return self._transition('applied', user)

    @expose_route('/award', methods=['POST'], access=ROLE('admin'))
    def award(self, user: User = None) -> str:
        return self._transition('awarded', user)

    @expose_route('/reject', methods=['POST'], access=ROLE('admin'))
    def reject(self, user: User = None) -> str:
        return self._transition('rejected', user)

    @expose_route('/dismiss', methods=['POST'], access=AUTHENTICATED)
    def dismiss(self, user: User = None) -> str:
        return self._transition('dismissed', user)
```

Each method automatically appears in the JSON Schema under `methods`, and the frontend renders them as action buttons via `<ntx-method>`. ABAC controls who can perform each transition. The `__ui__` config can attach icons and layout hints:

```python
__ui__ = {
    'methods': {
        'review':    {'layout': 'button', 'icon': 'eye'},
        'shortlist': {'layout': 'button', 'icon': 'star'},
        'apply':     {'layout': 'button', 'icon': 'send'},
        'dismiss':   {'layout': 'button', 'icon': 'x-circle'},
    },
}
```

### State History Tracking

A `GrantHistory` model captures every transition:

```python
class GrantHistory(ActorModel):
    __tablename__ = 'grant_history'
    __storable__ = True

    from_status: str = Field(default='')
    to_status: str = Field(min_length=1)
    changed_by: User = Field(default=None)
    changed_at: DateTimeField = Field(default_factory=datetime.now)
    note: str = Field(default='')
```

This uses the existing `generate_join_model(Grant, GrantHistory)` pattern -- history records are children of grants, accessible at `/grants/{id}/history`.

### Automated Expiration

Grants past their deadline can be expired automatically. This ties into the [Scheduling](#7--scheduling--automation) feature, but the transition logic itself is just:

```python
@classmethod
def expire_overdue(cls):
    """Expire all grants past deadline. Called by scheduler."""
    today = date.today().isoformat()
    overdue = cls.list(sql_filter=(
        "deadline < ? AND status NOT IN ('expired','awarded','rejected','dismissed')",
        [today]
    ))
    items = overdue if isinstance(overdue, list) else overdue.get('data', [])
    for grant in items:
        Grant.update(grant.id, {'status': 'expired'})
```

### Why a State Machine Library is Overkill

Libraries like [python-statemachine](https://python-statemachine.readthedocs.io/en/latest/transitions.html) and [pytransitions](https://github.com/pytransitions/transitions) add guard conditions, nested states, and parallel regions. Grant Watcher's workflow is a **flat DAG with 8 states** -- a dictionary of allowed transitions and `@expose_route` methods covers it completely. Adding a state machine dependency would mean integrating its lifecycle hooks with Pydantic validation, ABAC rules, and the schema pipeline -- three integration surfaces for a problem that a 20-line dictionary already solves.

| Approach | Pros | Cons |
|----------|------|------|
| `GRANT_STATES` dict + `@expose_route` | Zero dependencies, integrates naturally with N3TX ABAC and schema | No formal guard conditions or parallel states |
| `python-statemachine` library | Rich DSL, event callbacks, visualization | Adds dependency, requires integration with Pydantic MI + ABAC |
| Schema extension (new pipeline stage) | Reusable across models, declares states in schema | Over-engineering for one model; consider only if 3+ models need workflows |

> **Recommendation:** Start with the dict-based approach. If a second model (e.g., `Application`) needs workflow, refactor into a `@schema_extension` that reads a `__workflow__` ClassVar.

---

## 2. Notifications & Alerts

### The Problem

Grant Watcher creates grants silently. No user is notified when a new grant matches their interests. No one gets a deadline warning. Agent runs complete without any visible feedback to the team. In a team of grant seekers, this means missed deadlines and duplicated effort.

### What Users Need

Based on [Optimy's 2026 grant management guide](https://www.optimy.com/blog-optimy/grant-management-system) and [Funraise's nonprofit guide](https://www.funraise.org/blog/grant-management-software-for-nonprofits), the essential notification categories are:

| Notification Type | Trigger | Priority |
|-------------------|---------|----------|
| Deadline approaching | 7 days, 3 days, 1 day before grant deadline | **Critical** |
| New grant discovered | Agent creates a grant matching user interests | **High** |
| Status change | Grant moves to reviewed/shortlisted/applied | **Medium** |
| Agent run completed | Grant Scanner finishes with results summary | **Medium** |
| Assignment | Grant assigned to team member | **Medium** |
| Comment/note added | Colleague adds a note to a watched grant | **Low** |

### Implementation Architecture

N3TX already has the infrastructure. The `NetworkWebSocket` adapter at `/workspace/src/n3tx/core/api/network_ws.py` (lines 199-236) already handles lifecycle event broadcasts:

```python
# Already exists in network_ws.py
async def LIFECYCLE(self, data: dict, tx: TX):
    """Broadcasts create/update/delete events to all connected clients."""
    broadcast = {
        'name': frontend_name,
        'source': tx.source,
        'target': '*',
        'data': entity,
        'meta': {'push': True, 'lifecycle': True},
    }
    for client_id, conn in self._connections.items():
        await conn['ws'].send_json(broadcast)
```

And `ActorModel._publish_lifecycle()` at `/workspace/src/n3tx/core/models/actor_model.py` (lines 279-293) already fires events after create/update/delete. The pieces exist -- they just need to be connected.

```
┌────────────┐    lifecycle TX    ┌──────────────┐    filter     ┌────────────────┐
│ ActorModel │ ────────────────> │ Notification │ ──────────> │ NetworkWebSocket│
│ (Grant)    │  after_create     │   Actor      │  per-user    │  (broadcast)   │
│            │  after_update     │              │  matching    │                │
└────────────┘                   └──────┬───────┘              └────────────────┘
                                        │
                                        v
                                 ┌──────────────┐
                                 │ Notification │  (persisted)
                                 │   Model      │
                                 │ in DB        │
                                 └──────────────┘
```

### Notification Model

```python
class Notification(ActorModel):
    __tablename__ = 'notifications'
    __storable__ = True
    __access__ = {
        'read': OWNER,
        'create': AUTHENTICATED,
        'update': OWNER,
        'delete': OWNER,
    }

    user_owner: User = Field(description="Recipient")
    type: str = Field(description="deadline | new_grant | status_change | agent_run | assignment")
    title: str = Field(max_length=200)
    message: str = Field(default='')
    grant_id: Optional[int] = Field(default=None, description="Related grant")
    read: bool = Field(default=False)
    created_at: DateTimeField = Field(default_factory=datetime.now)

    @expose_route('/mark_read', methods=['POST'], access=OWNER)
    def mark_read(self, user: User = None) -> str:
        Notification.update(self.id, {'read': True})
        return '{"action": "marked_read"}'

    @expose_route('/mark_all_read', methods=['POST'], access=AUTHENTICATED)
    @classmethod
    def mark_all_read(cls, user: User = None) -> str:
        # Uses sql_filter to update only this user's notifications
        unread = cls.list(sql_filter=("user_owner = ? AND read = 0", [user.id]))
        items = unread if isinstance(unread, list) else unread.get('data', [])
        for n in items:
            cls.update(n.id, {'read': True})
        return json.dumps({'marked': len(items)})
```

### Notification Actor (Event Router)

A non-storable `ActorModel` subscribes to lifecycle events and creates `Notification` records:

```python
class NotificationActor(ActorModel):
    __tablename__ = 'notification_actor'
    __storable__ = False

    async def LIFECYCLE(self, data: dict, tx: TX):
        event = data.get('event', '')
        entity = data.get('entity', {})

        if event == 'after_create' and tx.source == 'grants':
            # New grant discovered -- notify all users (or matched users)
            users = User.list()
            items = users if isinstance(users, list) else users.get('data', [])
            for u in items:
                Notification.create(Notification(
                    user_owner=u.id,
                    type='new_grant',
                    title=f"New grant: {entity.get('title', '')}",
                    message=entity.get('description', '')[:200],
                    grant_id=entity.get('id'),
                ))

        elif event == 'after_update' and tx.source == 'grants':
            # Status change -- notify the grant owner
            owner_id = entity.get('user_owner')
            if owner_id:
                Notification.create(Notification(
                    user_owner=owner_id,
                    type='status_change',
                    title=f"Grant status changed: {entity.get('status', '')}",
                    grant_id=entity.get('id'),
                ))
```

Wiring: `Grant._subscribers.append('notification_actor')` in `main.py`.

### Real-Time Push via WebSocket

The `NetworkWebSocket` already broadcasts lifecycle events. For targeted notifications, extend the LIFECYCLE handler to filter by client user:

```python
# In NotificationActor.LIFECYCLE -- after creating the DB record:
# Also push via WebSocket for immediate display
ws_adapter = Actor.root().children.get('ws')
if ws_adapter:
    for client_id, conn in ws_adapter._connections.items():
        if conn['user'].get('id') == owner_id:
            await conn['ws'].send_json({
                'name': 'NOTIFICATION',
                'data': {'type': 'status_change', 'title': '...', 'grant_id': 1},
                'meta': {'push': True},
            })
```

### Effort Estimate

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| Notification model | 1 day | None |
| NotificationActor event router | 1 day | Notification model |
| Deadline checker (scheduled job) | 0.5 day | Scheduler (see section 7) |
| Frontend notification badge/dropdown | 2 days | WebSocket connection |
| **Total** | **4.5 days** | |

---

## 3. Search & Advanced Filtering

### The Problem

The current `SQLiteStorage.list()` method at `/workspace/src/n3tx/core/storage/sqlite_storage.py` (lines 146-256) supports only `sql_filter` tuples -- raw WHERE clauses passed from the auth interceptor. There is no user-facing search endpoint. Finding a grant means scrolling the list or knowing the exact ID. With 1,000+ grants discovered by agents, this is untenable.

### Option Analysis: Three Search Approaches

| Approach | Setup Cost | Query Speed (1K docs) | Features | Resource Usage |
|----------|-----------|----------------------|----------|----------------|
| **SQLite FTS5** | Low (built-in) | **<5ms** | BM25 ranking, prefix search, phrase, boolean | **<1MB** additional |
| **Meilisearch** | Medium (external service) | **<10ms** | Typo tolerance, facets, highlighting | **~800MB RAM** |
| **Application-level** | Minimal | **50-200ms** | LIKE queries, basic substring | Zero |

According to [benchmarks comparing SQLite FTS5 to Meilisearch](https://github.com/VADOSWARE/fts-benchmark), FTS5 uses **8x less storage** (26MB vs 217MB for the same dataset) and needs no additional process. For Grant Watcher's scale (thousands, not millions of documents), [SQLite FTS5 is the clear winner](https://blog.sqlite.ai/fts5-sqlite-text-search-extension).

> **Key Insight:** SQLite FTS5 is a **zero-dependency** solution. Python's built-in `sqlite3` module includes FTS5 support. No new process, no RAM overhead, no configuration. It runs inside the same database file Grant Watcher already uses.

### FTS5 Implementation

**Step 1: Create FTS virtual table alongside grants**

```python
# In migration or storage setup
def create_fts_index(conn):
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS grants_fts
        USING fts5(
            title,
            agency,
            description,
            content='grants',
            content_rowid='id',
            tokenize='porter unicode61'
        )
    """)
    # Rebuild index from existing data
    conn.execute("""
        INSERT INTO grants_fts(grants_fts) VALUES('rebuild')
    """)
```

The `content='grants'` directive tells FTS5 to use the `grants` table as the content source. The `porter` tokenizer enables stemming ("researching" matches "research"). The [SQLite FTS5 documentation](https://sqlite.org/fts5.html) covers the full syntax.

**Step 2: Keep index in sync via triggers**

```sql
CREATE TRIGGER grants_ai AFTER INSERT ON grants BEGIN
    INSERT INTO grants_fts(rowid, title, agency, description)
    VALUES (new.id, new.title, new.agency, new.description);
END;

CREATE TRIGGER grants_au AFTER UPDATE ON grants BEGIN
    INSERT INTO grants_fts(grants_fts, rowid, title, agency, description)
    VALUES ('delete', old.id, old.title, old.agency, old.description);
    INSERT INTO grants_fts(rowid, title, agency, description)
    VALUES (new.id, new.title, new.agency, new.description);
END;

CREATE TRIGGER grants_ad AFTER DELETE ON grants BEGIN
    INSERT INTO grants_fts(grants_fts, rowid, title, agency, description)
    VALUES ('delete', old.id, old.title, old.agency, old.description);
END;
```

**Step 3: Search endpoint on Grant model**

```python
@expose_route('/search', methods=['GET'], access=ANYONE)
@classmethod
def search(cls, q: str, limit: int = 20) -> str:
    """Full-text search across grants. Returns ranked results."""
    storage = cls.storage
    with storage._connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT g.*, rank
            FROM grants_fts fts
            JOIN grants g ON g.id = fts.rowid
            WHERE grants_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (q, limit))
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        results = []
        for row in rows:
            record = dict(zip(columns, row))
            instance = cls(**record)
            results.append(instance.model_response())
        return json.dumps({'data': results, 'meta': {'query': q, 'count': len(results)}})
```

### Advanced Filtering: Extending the API Pattern

Beyond full-text search, users need structured filters: agency, deadline range, amount range, status, tags. The cleanest approach is a filter endpoint that constructs `sql_filter` tuples:

```python
@expose_route('/filter', methods=['GET'], access=ANYONE)
@classmethod
def filter(cls, agency: str = None, status: str = None,
           deadline_from: str = None, deadline_to: str = None,
           amount_min: float = None, amount_max: float = None,
           tags: str = None, limit: int = 20, offset: int = 0) -> str:
    """Multi-field filter. Builds WHERE clause dynamically."""
    clauses, params = [], []
    if agency:
        clauses.append("agency = ?"); params.append(agency)
    if status:
        clauses.append("status = ?"); params.append(status)
    if deadline_from:
        clauses.append("deadline >= ?"); params.append(deadline_from)
    if deadline_to:
        clauses.append("deadline <= ?"); params.append(deadline_to)
    if amount_min is not None:
        clauses.append("amount_max >= ?"); params.append(amount_min)
    if amount_max is not None:
        clauses.append("amount_min <= ?"); params.append(amount_max)

    sql_filter = (" AND ".join(clauses), params) if clauses else None
    result = cls.list(sql_filter=sql_filter, limit=limit, offset=offset)
    # ... serialize and return
```

### Saved Searches / Watchlists

A `SavedSearch` model stores filter parameters as JSON:

```python
class SavedSearch(ActorModel):
    __tablename__ = 'saved_searches'
    __storable__ = True
    __access__ = {'read': OWNER, 'create': AUTHENTICATED, 'update': OWNER, 'delete': OWNER}

    name: str = Field(min_length=1, max_length=200)
    filters: dict = Field(default={})  # {agency: "NSF", status: "discovered", ...}
    user_owner: User = Field(default=None)
    notify_on_match: bool = Field(default=True)
```

When agents discover new grants, the NotificationActor checks saved searches and creates notifications for matches.

### Effort Estimate

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| FTS5 virtual table + triggers (migration) | 0.5 day | None |
| Search endpoint on Grant | 0.5 day | FTS5 table |
| Advanced filter endpoint | 1 day | None |
| SavedSearch model | 0.5 day | None |
| Frontend search bar + filter panel | 2 days | Search endpoints |
| **Total** | **4.5 days** | |

---

## 4. Tagging & Categorization

### The Problem

Grants currently have two categorical fields: `agency` (a free-text string) and `status`. There is no way to categorize grants by topic ("AI research", "climate", "education"), funding type ("research", "infrastructure", "fellowship"), or any user-defined dimension. Without tags, there is no way to match grants to user interests.

### Industry Standard

[Good Grants](https://goodgrants.com/resources/articles/tagging-the-magic-of-grants-management/) calls tagging "the magic of grants management" -- it enables rapid filtering, workload analysis, and automated routing. Their platform supports both manual and automated tagging, including tags auto-assigned from application form dropdowns.

[Grantx](https://grantx.com/) uses AI-powered classification to automatically categorize grants by topic, eligibility, and funding type. [Instrumentl](https://www.instrumentl.com/) uses keyword matching to filter grants by field of work.

### Implementation: Tag Model + Join Table

N3TX's `ListRef` + `generate_join_model` pattern is tailor-made for this:

```python
class Tag(ActorModel):
    __tablename__ = 'tags'
    __storable__ = True
    __access__ = {'read': ANYONE, 'create': AUTHENTICATED, 'update': ROLE('admin'), 'delete': ROLE('admin')}

    name: str = Field(min_length=1, max_length=100)
    category: str = Field(default='topic', description="topic | funding_type | eligibility | custom")
    color: str = Field(default='#6366f1', description="Hex color for UI display")

class Grant(ActorModel):
    # ... existing fields ...
    tags: ListRef[Tag] = Field(default=[], description="Tags for categorization")

# In main.py
app = create_app(
    models=[User, Grant, Source, Tag, WebTools, AgentTool, AgentActor],
    join_models=[(AgentActor, AgentTool), (Grant, Tag)],  # <-- add join
    ...
)
```

This gives us `GET /grants/{id}/tags`, `POST /grants/{id}/tags`, and tag filtering through the join table -- all auto-generated by `register_routes()`.

### Auto-Tagging via Agent

The Grant Scanner agent can be extended to tag grants after creation. This uses the existing `agent_run()` infrastructure:

```python
# Add a tag_grant method to Grant
@expose_route('/auto_tag', methods=['POST'], access=AUTHENTICATED)
async def auto_tag(self, user: User = None) -> str:
    """Use LLM to suggest tags based on grant description."""
    result = await self.agent_run(
        prompt=(
            "Analyze this grant and suggest 1-5 tags from these categories: "
            "topic (e.g., 'AI', 'climate', 'education', 'health'), "
            "funding_type (e.g., 'research', 'infrastructure', 'fellowship'), "
            "eligibility (e.g., 'nonprofit', 'university', 'small_business'). "
            "Return tag names as a JSON array."
        ),
        tools=['tags', 'grants'],
        task=f"Title: {self.title}\nAgency: {self.agency}\nDescription: {self.description}",
        user={'id': user.id} if user else None,
    )
    return json.dumps(result)
```

Alternatively, a simpler rule-based approach using keyword matching avoids LLM costs:

```python
KEYWORD_TAGS = {
    'AI': ['artificial intelligence', 'machine learning', 'deep learning', 'neural', 'AI'],
    'Climate': ['climate', 'environmental', 'sustainability', 'carbon', 'renewable'],
    'Education': ['education', 'STEM', 'curriculum', 'student', 'teaching'],
    'Health': ['health', 'biomedical', 'clinical', 'disease', 'NIH'],
}

def suggest_tags(title: str, description: str) -> list[str]:
    text = f"{title} {description}".lower()
    return [tag for tag, keywords in KEYWORD_TAGS.items()
            if any(kw.lower() in text for kw in keywords)]
```

### Comparison: Tag Implementation Strategies

| Strategy | Pros | Cons | Best For |
|----------|------|------|----------|
| **ListRef join table** | Standard N3TX pattern, CRUD for free, relational queries | Extra table, join queries | Primary implementation |
| **JSON array field** | Simple, no join table | No relational queries, harder to filter | Ephemeral/suggested tags |
| **Keyword-based auto-tag** | Fast, deterministic, no LLM cost | Rigid, misses context | MVP auto-tagging |
| **LLM-powered auto-tag** | Contextual, handles nuance | Costs ~$0.01/grant, latency | Production auto-tagging |

> **Recommendation:** Use the `ListRef` join table for persistent tags (it is the canonical N3TX pattern). Use keyword matching for MVP auto-tagging, upgrade to LLM-powered tagging when the Grant Scanner agent's prompt is extended.

### Effort Estimate

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| Tag model + join table | 0.5 day | None |
| Keyword-based auto-tagger | 0.5 day | Tag model |
| LLM-powered auto-tagger | 1 day | Agent infrastructure, Tag model |
| Tag filter integration with search | 0.5 day | Search endpoints |
| Frontend tag display + tag filter chips | 1.5 days | Tag model |
| **Total** | **4 days** | |

---

## 5. Collaboration Features

### The Problem

Grant Watcher is a single-player experience. There is no way to share grants with colleagues, add notes, assign grants to team members, or track who is working on what. For teams pursuing multiple grants simultaneously, this creates coordination problems that compound into missed deadlines.

### What Competitors Offer

According to [Neon One's 2025 review](https://neonone.com/resources/blog/grant-management-software/), the essential collaboration features are: document sharing, task assignment, team alerts, and role-based visibility. [Fluxx](https://www.fluxx.io/) differentiates on real-time collaboration for larger teams. [WizeHive](https://www.bonterratech.com/blog/best-grant-management-software) offers shared portals where multiple stakeholders can interact with grant applications.

### Implementation: Reuse the Comment/Like Pattern

The `example_actor` app already has a battle-tested `Comment` model at `/workspace/example_actor/models/comment.py` with nested replies, likes, user attribution, and ABAC rules. Grant Watcher can replicate this pattern directly:

```python
class Note(ActorModel):
    """A note on a grant -- discussions, observations, action items."""
    __tablename__ = 'notes'
    __storable__ = True
    __protected_fields__ = {'user_owner'}
    __access__ = {
        'read': AUTHENTICATED,
        'create': AUTHENTICATED,
        'update': OWNER | ROLE('admin'),
        'delete': OWNER | ROLE('admin'),
    }
    __ui__ = {
        'field_order': ['user_owner', 'text', 'type'],
        'methods': {
            'reply': {'layout': 'inline', 'attach_to': 'text',
                      'button_label': 'Reply', 'placeholder': 'Add a reply...', 'widget': 'textarea'},
        },
    }

    text: TextareaField = Field(min_length=1)
    type: str = Field(default='note', description="note | action_item | question")
    user_owner: User = Field(default=None)
    parent_id: Optional[Ref['self']] = Field(default=None, description="Parent for threading")

# On Grant model:
class Grant(ActorModel):
    # ... existing fields ...
    notes: ListRef[Note] = Field(default=[], description="Team notes and discussions")
```

With `join_models=[(Grant, Note)]` in `create_app()`, this gives threaded discussions on grants for free.

### Grant Assignment

Assignment is a simple field on the Grant model:

```python
class Grant(ActorModel):
    # ... existing fields ...
    assigned_to: Optional[User] = Field(default=None, description="Team member responsible",
                                         json_schema_extra={'access': {'view': 'authenticated', 'edit': 'admin'}})

    @expose_route('/assign', methods=['POST'], access=ROLE('admin'))
    def assign(self, assignee_id: int, user: User = None) -> str:
        Grant.update(self.id, {'assigned_to': assignee_id})
        # Create notification for the assignee
        Notification.create(Notification(
            user_owner=assignee_id,
            type='assignment',
            title=f"You've been assigned: {self.title}",
            grant_id=self.id,
        ))
        return json.dumps({'action': 'assigned', 'to': assignee_id})
```

### Watchlist (Personal Grant Tracking)

```python
class WatchedGrant(ActorModel):
    __tablename__ = 'watched_grants'
    __storable__ = True
    __access__ = {'read': OWNER, 'create': AUTHENTICATED, 'delete': OWNER}

    grant_id: int = Field(description="The grant being watched")
    user_owner: User = Field(default=None)

# On Grant:
@expose_route('/watch', methods=['POST'], access=AUTHENTICATED)
def watch(self, user: User = None) -> str:
    """Toggle watch -- add to or remove from personal watchlist."""
    existing = WatchedGrant.list(
        sql_filter=("grant_id = ? AND user_owner = ?", [self.id, user.id])
    )
    items = existing if isinstance(existing, list) else existing.get('data', [])
    if items:
        WatchedGrant.delete(items[0].id)
        return '{"action": "unwatched"}'
    WatchedGrant.create(WatchedGrant(grant_id=self.id, user_owner=user.id))
    return '{"action": "watched"}'
```

This is exactly the Product `favorite()` toggle pattern from `example_actor`.

### Effort Estimate

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| Note model + join table | 0.5 day | None |
| Grant.assign() + notification | 0.5 day | Notification model |
| WatchedGrant toggle | 0.5 day | None |
| Frontend notes display + inline reply | 1.5 days | Note model |
| Frontend assignment dropdown | 1 day | User list endpoint |
| **Total** | **4 days** | |

---

## 6. Grant Matching & Recommendations

### The Problem

The most valuable feature a grant platform can offer is answering: "Which of the 1,000 newly discovered grants are relevant to me?" Currently, every user sees the same unfiltered list. A researcher in AI should not have to scroll past agricultural grants to find relevant opportunities.

### How Commercial Platforms Do It

[Instrumentl](https://www.instrumentl.com/) uses AI-powered matching where users describe their organization and projects, and the platform returns scored matches. [Grantx](https://grantx.com/) builds an organizational profile and analyzes "hundreds of thousands of funding programs" returning matches with "clear scores and insights." [OpenGrants](https://opengrants.io/) uses an "AI-driven search engine that analyzes factors such as location and organizational objectives."

The common pattern: **user profile + grant features --> similarity score --> ranked feed**.

### Implementation Tiers

**Tier 1: Keyword Matching (MVP -- 2 days)**

```python
class UserProfile(ActorModel):
    __tablename__ = 'user_profiles'
    __storable__ = True
    __access__ = {'read': OWNER, 'create': AUTHENTICATED, 'update': OWNER, 'delete': OWNER}

    user_owner: User = Field(description="The user this profile belongs to")
    interests: str = Field(default='', description="Comma-separated interests: AI, climate, health")
    org_type: str = Field(default='', description="university | nonprofit | small_business | individual")
    min_amount: Optional[CurrencyField] = Field(default=None)
    max_amount: Optional[CurrencyField] = Field(default=None)

def match_score(grant: Grant, profile: UserProfile) -> float:
    """Simple keyword overlap score. Returns 0.0 to 1.0."""
    interests = set(i.strip().lower() for i in profile.interests.split(',') if i.strip())
    grant_text = f"{grant.title} {grant.description} {grant.agency}".lower()
    if not interests:
        return 0.0
    hits = sum(1 for interest in interests if interest in grant_text)
    return hits / len(interests)
```

**Tier 2: Embedding Similarity (1 week)**

Uses sentence embeddings to compute semantic similarity between user profiles and grant descriptions. Requires an embedding model (OpenAI `text-embedding-3-small` at $0.02/1M tokens, or local via `sentence-transformers`).

```
┌────────────┐     embed()      ┌──────────────┐
│ User       │ ──────────────> │ Vector DB    │
│ Profile    │                 │ (SQLite +    │ <── cosine_similarity()
│            │                 │  sqlite-vss) │
└────────────┘                 └──────┬───────┘
                                      │  top-K results
┌────────────┐     embed()      ┌─────v────────┐
│ Grant      │ ──────────────> │ Grant Vectors │
│ Description│                 │ (computed     │
│            │                 │  on ingest)   │
└────────────┘                 └──────────────┘
```

**Tier 3: LLM-Powered Matching Agent (2 weeks)**

A dedicated matching agent that combines keyword matching, semantic similarity, and contextual reasoning:

```python
matcher = AgentActor(
    name="Grant Matcher",
    prompt=(
        "You are a grant matching agent. Given a user profile and a list of grants, "
        "score each grant 0-100 for relevance. Consider: topic alignment, eligibility, "
        "funding range fit, deadline proximity. Return a ranked JSON array."
    ),
    tools=['grants', 'user_profiles', 'tags'],
    llm="anthropic:claude-sonnet-4-5-20250929",
)
```

### Matching Comparison

| Approach | Accuracy | Cost per Match | Latency | Cold Start? |
|----------|----------|---------------|---------|-------------|
| Keyword overlap | Low-Medium | Free | <10ms | Needs explicit interests |
| Embedding similarity | Medium-High | ~$0.001 | <100ms | Needs initial embedding |
| LLM agent | High | ~$0.05-0.10 | 5-30s | Works with any text |

> **Recommendation:** Ship Tier 1 (keyword matching) with the tagging feature. It is free, instant, and solves 80% of the matching problem. Plan Tier 2 for v2 when grant volume exceeds 1,000. Reserve Tier 3 for premium/enterprise tier where per-query cost is acceptable.

### Effort Estimate

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| UserProfile model | 0.5 day | None |
| Keyword matching function | 0.5 day | Tags, UserProfile |
| "Grants for you" endpoint | 1 day | Matching function |
| Frontend recommendation feed | 1.5 days | Matching endpoint |
| Embedding pipeline (Tier 2) | 3-5 days | External embedding API |
| LLM matching agent (Tier 3) | 5-7 days | Agent infrastructure |
| **Total (Tier 1 MVP)** | **3.5 days** | |

---

## 7. Scheduling & Automation

### The Problem

The Grant Scanner agent exists and works -- but it has to be triggered manually via `POST /agents/1/run`. Nobody is going to remember to run it every morning. Deadline monitoring likewise requires manual checks. The platform needs a heartbeat.

### Implementation: APScheduler with FastAPI Lifespan

[APScheduler](https://apscheduler.readthedocs.io/en/3.x/userguide.html) is the standard Python scheduling library. Its `AsyncIOScheduler` runs in the same event loop as FastAPI, requiring no additional processes or infrastructure. The [FastAPI lifespan integration](https://sentry.io/answers/schedule-tasks-with-fastapi/) pattern is well-documented:

```python
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown()

# In create_app():
app = FastAPI(lifespan=lifespan)

# Schedule jobs
@scheduler.scheduled_job('cron', hour=6, minute=0)  # Daily at 6 AM
async def daily_scan():
    """Trigger all active agents to scan their sources."""
    agents = AgentActor.list()
    items = agents if isinstance(agents, list) else agents.get('data', [])
    for agent in items:
        await agent.run(task="Scan all sources for new grants")

@scheduler.scheduled_job('cron', hour=7, minute=0)  # Daily at 7 AM
async def deadline_check():
    """Expire overdue grants and send deadline warnings."""
    Grant.expire_overdue()
    # Send 7/3/1 day warnings
    for days in [7, 3, 1]:
        target_date = (date.today() + timedelta(days=days)).isoformat()
        approaching = Grant.list(sql_filter=(
            "deadline = ? AND status NOT IN ('expired','awarded','rejected','dismissed')",
            [target_date]
        ))
        items = approaching if isinstance(approaching, list) else approaching.get('data', [])
        for grant in items:
            # Create notifications for watchers
            ...
```

### Scheduler as an Actor

For tighter N3TX integration, the scheduler can be wrapped as a non-storable ActorModel with management endpoints:

```python
class Scheduler(ActorModel):
    __tablename__ = 'scheduler'
    __storable__ = False
    __access__ = {'read': ROLE('admin'), 'create': ROLE('admin')}

    @expose_route('/status', methods=['GET'], access=ROLE('admin'))
    @classmethod
    def status(cls) -> str:
        jobs = scheduler.get_jobs()
        return json.dumps([{
            'id': j.id, 'name': j.name,
            'next_run': str(j.next_run_time),
            'trigger': str(j.trigger),
        } for j in jobs])

    @expose_route('/trigger', methods=['POST'], access=ROLE('admin'))
    @classmethod
    async def trigger(cls, job_name: str) -> str:
        """Manually trigger a scheduled job."""
        if job_name == 'daily_scan':
            await daily_scan()
        elif job_name == 'deadline_check':
            await deadline_check()
        return json.dumps({'action': 'triggered', 'job': job_name})
```

### Build vs Buy: Scheduling Options

| Option | Pros | Cons | Best For |
|--------|------|------|----------|
| **APScheduler (in-process)** | Zero infrastructure, same event loop, easy setup | Dies with the process, no distributed execution | Single-instance deployment |
| **System cron + curl** | Battle-tested, OS-level, survives restarts | No visibility, no error handling, Unix only | Production fallback |
| **Celery Beat** | Distributed, persistent, retries | Heavy (Redis/RabbitMQ), complex setup | Multi-worker deployments |
| **External (Temporal, Airflow)** | Workflow orchestration, retry, observability | Massive overkill for periodic scans | Enterprise/complex pipelines |

> **Recommendation:** APScheduler for MVP. It adds a single pip dependency. If Grant Watcher scales to multiple instances, migrate to cron+curl (calling the `/scheduler/trigger` endpoint) -- the scheduler Actor already exposes the HTTP interface for this.

### Effort Estimate

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| APScheduler integration with lifespan | 0.5 day | `pip install apscheduler` |
| Daily scan job | 0.5 day | Agent infrastructure |
| Deadline checker job | 0.5 day | Notification model |
| Scheduler Actor (admin UI) | 1 day | None |
| **Total** | **2.5 days** | |

---

## 8. Reporting & Analytics

### The Problem

After months of operation, the natural questions arise: How many grants are we discovering per week? Which agencies publish the most? What is our application success rate? How is the Grant Scanner agent performing? Currently, answering any of these requires manual SQL queries.

### Implementation: Aggregate Endpoints

Rather than building a separate analytics service, add aggregate endpoints to existing models. This follows the N3TX philosophy of the model being the app:

```python
@expose_route('/stats', methods=['GET'], access=AUTHENTICATED)
@classmethod
def stats(cls) -> str:
    """Aggregate grant statistics."""
    storage = cls.storage
    with storage._connection() as conn:
        cursor = conn.cursor()

        # Total by status
        cursor.execute("SELECT status, COUNT(*) FROM grants GROUP BY status")
        by_status = dict(cursor.fetchall())

        # Total by agency
        cursor.execute("SELECT agency, COUNT(*) FROM grants GROUP BY agency ORDER BY COUNT(*) DESC LIMIT 10")
        by_agency = dict(cursor.fetchall())

        # Discovery rate (last 30 days, grouped by week)
        cursor.execute("""
            SELECT strftime('%Y-W%W', created_at) as week, COUNT(*)
            FROM grants
            WHERE created_at >= date('now', '-30 days')
            GROUP BY week ORDER BY week
        """)
        weekly_rate = dict(cursor.fetchall())

        # Success rate
        total_applied = by_status.get('applied', 0) + by_status.get('awarded', 0) + by_status.get('rejected', 0)
        awarded = by_status.get('awarded', 0)
        success_rate = (awarded / total_applied * 100) if total_applied > 0 else 0

        return json.dumps({
            'by_status': by_status,
            'by_agency': by_agency,
            'weekly_discovery_rate': weekly_rate,
            'success_rate': round(success_rate, 1),
            'total_grants': sum(by_status.values()),
        })
```

### Agent Performance Metrics

Track agent run results in a dedicated model:

```python
class AgentRunLog(ActorModel):
    __tablename__ = 'agent_run_logs'
    __storable__ = True

    agent_id: int = Field(description="The agent that ran")
    task: str = Field(default='')
    grants_found: int = Field(default=0)
    grants_created: int = Field(default=0)
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    duration_seconds: float = Field(default=0)
    status: str = Field(default='success', description="success | error")
    error_message: str = Field(default='')
    created_at: DateTimeField = Field(default_factory=datetime.now)
```

### Export Capabilities

CSV export is a classmethod on any model:

```python
@expose_route('/export', methods=['GET'], access=AUTHENTICATED)
@classmethod
def export(cls, format: str = 'csv') -> str:
    """Export all grants as CSV."""
    import csv, io
    grants = cls.list()
    items = grants if isinstance(grants, list) else grants.get('data', [])
    output = io.StringIO()
    if items:
        writer = csv.DictWriter(output, fieldnames=['title', 'agency', 'deadline', 'amount_min', 'amount_max', 'status', 'url'])
        writer.writeheader()
        for g in items:
            writer.writerow({k: getattr(g, k, '') for k in writer.fieldnames})
    return output.getvalue()
```

### Frontend Dashboard

The frontend can consume the `/grants/stats` endpoint and render charts using lightweight libraries. Since N3TX serves static files, a simple chart library like Chart.js (40KB) can be vendored:

```
┌─────────────────────────────────────────────────────────┐
│  Grant Watcher Dashboard                                │
├────────────────────┬────────────────────────────────────┤
│  Status Pipeline   │  Weekly Discovery Rate             │
│  ┌──────────────┐  │  ┌─────────────────────────────┐  │
│  │ Discovered 47│  │  │  █                           │  │
│  │ Reviewed   23│  │  │  █ █                         │  │
│  │ Shortlisted 8│  │  │  █ █ █                       │  │
│  │ Applied     5│  │  │  █ █ █ █   █                 │  │
│  │ Awarded     2│  │  │──█─█─█─█───█──────────────── │  │
│  └──────────────┘  │  │  W1 W2 W3 W4 W5             │  │
│                    │  └─────────────────────────────┘  │
├────────────────────┴────────────────────────────────────┤
│  Top Agencies: NSF (23) | NIH (18) | DOE (12) | ...    │
│  Success Rate: 28.6% (2 awarded / 7 applied)           │
└─────────────────────────────────────────────────────────┘
```

### Effort Estimate

| Component | Effort | Dependencies |
|-----------|--------|--------------|
| Grant.stats() endpoint | 1 day | None |
| AgentRunLog model | 0.5 day | None |
| CSV export endpoint | 0.5 day | None |
| Frontend dashboard page | 3 days | Chart.js, stats endpoint |
| **Total** | **5 days** | |

---

## 9. Feature Prioritization & Roadmap

### Value vs Effort Matrix

| Feature | User Value | Eng. Effort | Framework Changes? | Dependencies |
|---------|-----------|-------------|-------------------|--------------|
| Grant Lifecycle Workflow | **Critical** | **3 days** | None | -- |
| Tagging & Categorization | **High** | **4 days** | None | -- |
| Search & Filtering | **High** | **4.5 days** | FTS5 migration | -- |
| Collaboration (Notes) | **High** | **4 days** | None | -- |
| Notifications & Alerts | **High** | **4.5 days** | None | WebSocket |
| Scheduling & Automation | **Medium-High** | **2.5 days** | APScheduler dep | Agent infra |
| Grant Matching (Tier 1) | **Medium** | **3.5 days** | None | Tags, UserProfile |
| Reporting & Analytics | **Medium** | **5 days** | None | Lifecycle data |
| Grant Matching (Tier 2+) | **Medium-High** | **5-10 days** | Embedding pipeline | External API |

### Dependency Graph

```
                    ┌──────────────┐
                    │  Lifecycle   │ ◄── Foundation for everything
                    │  Workflow    │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              v            v            v
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  Tags &  │ │  Notes & │ │Scheduling│
        │  Search  │ │  Collab  │ │          │
        └────┬─────┘ └──────────┘ └─────┬────┘
             │                          │
             v                          v
        ┌──────────┐            ┌──────────────┐
        │ Matching │            │ Notifications│
        │ (Tier 1) │            │  & Alerts    │
        └────┬─────┘            └──────────────┘
             │
             v
        ┌──────────┐
        │Reporting │
        │Analytics │
        └──────────┘
```

### Recommended Phased Rollout

#### Phase 1: Foundation (Week 1-2) -- "From Demo to Tool"

| Feature | Days | Why First |
|---------|------|-----------|
| Grant Lifecycle Workflow | 3 | Every other feature depends on structured status |
| Tagging & Categorization | 3 | Enables search, matching, notifications |
| Scheduling (basic) | 2 | Makes the platform self-running |
| **Total** | **8** | |

**Outcome:** Grant Watcher runs autonomously, agents scan sources daily, grants flow through a managed lifecycle with tags. Users can filter by status and category.

#### Phase 2: Discovery (Week 3-4) -- "Find What Matters"

| Feature | Days | Why Now |
|---------|------|---------|
| Search & Advanced Filtering | 4.5 | Users need to find grants in a growing database |
| Grant Matching (Tier 1) | 3.5 | Personalized grant feeds drive engagement |
| Collaboration (Notes + Assignment) | 4 | Teams need to coordinate on grants |
| **Total** | **12** | |

**Outcome:** Users get a personalized "Grants for You" feed, can search the full corpus, filter by any dimension, and collaborate on grants with their team.

#### Phase 3: Intelligence (Week 5-6) -- "Work Smarter"

| Feature | Days | Why Now |
|---------|------|---------|
| Notifications & Alerts | 4.5 | Users need proactive information, not pull |
| Reporting & Analytics | 5 | Leadership needs visibility into the pipeline |
| LLM Auto-tagging | 1 | Leverage existing agent infra for richer tags |
| **Total** | **10.5** | |

**Outcome:** The platform proactively notifies users of relevant grants and approaching deadlines. Leadership can see pipeline metrics and agent performance.

#### Phase 4: Scale (Month 2+) -- "Compete with SaaS"

| Feature | Days | Why Later |
|---------|------|-----------|
| Grant Matching (Tier 2 -- embeddings) | 5-7 | Only needed at 1,000+ grants |
| Application tracking (documents, checklists) | 5-7 | Post-award workflow |
| Multi-tenant / team workspaces | 5-10 | Enterprise feature |
| Email notifications | 3 | WebSocket covers real-time; email is nice-to-have |

---

## 10. Feasibility & ROI Analysis

### Features That Are "Free" (Zero Framework Changes)

These features use existing N3TX patterns -- `@expose_route`, `ListRef`, `generate_join_model`, ABAC rules, schema pipeline, widget types -- and require only new model definitions:

| Feature | Pattern Used | Lines of New Code |
|---------|-------------|-------------------|
| Grant Lifecycle | `@expose_route` + status validation | ~80 lines |
| Tagging | `ListRef[Tag]` + `generate_join_model` | ~30 lines |
| Notes/Comments | `ListRef[Note]` (copied from `example_actor`) | ~40 lines |
| Grant Assignment | `Ref[User]` field + `@expose_route('/assign')` | ~20 lines |
| Watchlist | `WatchedGrant` model + toggle method | ~30 lines |
| UserProfile | New model, basic CRUD | ~25 lines |
| Keyword Matching | Pure Python function | ~30 lines |
| CSV Export | `@expose_route('/export')` | ~20 lines |

**Total: ~275 lines of model code for 8 features.** This is the power of a schema-driven framework -- the infrastructure already exists; features are just models.

### Features Requiring Framework Enhancements

| Feature | Enhancement Needed | Effort | Risk |
|---------|-------------------|--------|------|
| FTS5 Search | Migration to create FTS virtual table + triggers | 0.5 day | Low -- standard SQLite |
| Scheduling | APScheduler integration in `create_app()` lifespan | 0.5 day | Low -- well-documented |
| Aggregate Stats | Direct SQL queries bypassing StorableMixin | 1 day | Low -- read-only |
| Targeted WebSocket Push | Filter broadcast by user in NetworkWebSocket | 0.5 day | Low -- small change |

### Features Requiring External Dependencies

| Feature | Dependency | Cost | Alternative |
|---------|-----------|------|-------------|
| Scheduling | `apscheduler` (pip) | Free/OSS | System cron |
| LLM Auto-tagging | Anthropic/OpenAI API | ~$0.01/grant | Keyword rules (free) |
| Embedding Matching | `sentence-transformers` or OpenAI | ~$0.001/match | Keyword matching |
| Chart Dashboard | Chart.js (vendored JS) | Free/OSS | Plain HTML tables |

### Build vs Buy Summary

| Capability | Build Cost (Grant Watcher) | Buy Cost (SaaS) | Verdict |
|-----------|--------------------------|-----------------|---------|
| Grant Lifecycle | 3 days | Included in $15-40/user/month | **Build** -- trivial with N3TX |
| Search | 4.5 days | Included | **Build** -- FTS5 is free and sufficient |
| Notifications | 4.5 days | Included | **Build** -- WebSocket infra exists |
| Auto-tagging | 1-2 days | $5-15/user/month add-on | **Build** -- leverages existing agent |
| Matching (Tier 1) | 3.5 days | Core feature of Instrumentl ($179/mo) | **Build** -- MVP is keyword matching |
| Scheduling | 2.5 days | N/A (operational) | **Build** -- APScheduler is standard |
| Reporting | 5 days | $10-30/user/month add-on | **Build** -- simple SQL aggregates |
| Application Tracking | 5-7 days | Core feature of Fluxx ($15-40/user/month) | **Defer** -- phase 4 |

> **Key Insight:** A team of 10 users paying $40/user/month for Instrumentl spends **$4,800/year**. The entire Phase 1-3 roadmap (30 engineering days) costs roughly the same as one year of a mid-tier SaaS subscription -- but you own the platform, the data, and the IP. For organizations managing sensitive government grants, self-hosting is often a compliance requirement, not just a preference.

### Competitive Feature Matrix

| Feature | Grant Watcher (Today) | Grant Watcher (Phase 3) | Instrumentl | Fluxx | Grantx |
|---------|----------------------|------------------------|-------------|-------|--------|
| Grant Discovery | Agent-driven | Agent-driven + scheduled | AI-matched database | Manual | AI-matched |
| Lifecycle Workflow | Basic status field | Full state machine | Tracker | Custom workflows | Basic |
| Search | None | FTS5 + filters | AI search | Basic search | AI search |
| Tagging | None | Manual + auto-tag | Keywords | Custom fields | AI categories |
| Notifications | None | WebSocket push | Email + in-app | Email | Email |
| Collaboration | None | Notes + assignment | Team features | Real-time collab | Limited |
| Matching | None | Keyword (Tier 1) | AI matching | None | AI matching |
| Reporting | None | Dashboard + export | Reports | Reports | Basic |
| Self-hosted | **Yes** | **Yes** | No | No | No |
| Open Source | **Yes** | **Yes** | No | No | No |
| Price | Free | Free | $179+/mo | Custom | Custom |

---

## Summary: What to Build First

The entire feature landscape can be distilled to one priority stack:

1. **Lifecycle Workflow** (3 days) -- the skeleton everything hangs on
2. **Tags + Search** (8.5 days) -- the muscles that make it useful
3. **Scheduling** (2.5 days) -- the heartbeat that keeps it alive
4. **Notes + Assignment** (4 days) -- the collaboration that makes it a team tool
5. **Notifications** (4.5 days) -- the nervous system that keeps users informed
6. **Matching** (3.5 days) -- the intelligence that makes it indispensable
7. **Reporting** (5 days) -- the visibility that justifies the investment

**Total: ~31 engineering days from demo to competitive product.**

The good news: N3TX's architecture means most of this is model definitions, not infrastructure work. The schema pipeline, ABAC system, actor messaging, and WebSocket bridge are already built. The features are just data models that take advantage of them.

The even better news: each phase is independently shippable. Phase 1 alone transforms Grant Watcher from "interesting demo" to "daily-use tool."

---

## Sources

- [Grants.gov - The Grant Lifecycle](https://www.grants.gov/learn-grants/grants-101/the-grant-lifecycle)
- [NetSuite - Grant Management Life Cycle](https://www.netsuite.com/portal/resource/articles/crm/grant-management-life-cycle.shtml)
- [Optimy - Grant Management System: The Ultimate 2026 Guide](https://www.optimy.com/blog-optimy/grant-management-system)
- [Optimy - What is Grant Management Software? A 2026 Guide](https://www.optimy.com/blog-optimy/grant-management-software)
- [DevOpsSchool - Top 10 Grant Management Software Tools in 2025](https://www.devopsschool.com/blog/top-10-grant-management-software-tools-in-2025-features-pros-cons-comparison/)
- [Fundsprout - The 12 Best Grant Discovery Platforms to Secure Funding in 2026](https://www.fundsprout.ai/resources/grant-discovery-platforms)
- [Good Grants - Tagging: The Magic of Grants Management](https://goodgrants.com/resources/articles/tagging-the-magic-of-grants-management/)
- [Grantx - AI-Powered Grant Discovery Platform](https://grantx.com/)
- [Instrumentl - Fluxx Grantseeker Pricing](https://www.instrumentl.com/blog/fluxx-grantseeker-pricing)
- [Neon One - 10 Best Grant Management Software Tools for Nonprofits](https://neonone.com/resources/blog/grant-management-software/)
- [Funraise - The Complete Guide to Grant Management Software](https://www.funraise.org/blog/grant-management-software-for-nonprofits)
- [WittOBriens - LLMs' Potential for Grants Management](https://government.wittobriens.com/cge/large-language-models-potential-for-grants-management-opportunities-and-challenges)
- [SQLite FTS5 Documentation](https://sqlite.org/fts5.html)
- [SQLite.ai - FTS5 Full-Text Search Extension](https://blog.sqlite.ai/fts5-sqlite-text-search-extension)
- [VADOSWARE - FTS Benchmark (Postgres, Meilisearch, SQLite)](https://github.com/VADOSWARE/fts-benchmark)
- [pytransitions/transitions - Python State Machine Library](https://github.com/pytransitions/transitions)
- [python-statemachine - Transitions Documentation](https://python-statemachine.readthedocs.io/en/latest/transitions.html)
- [Sentry - Schedule Tasks with FastAPI](https://sentry.io/answers/schedule-tasks-with-fastapi/)
- [APScheduler User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html)
- [MagicBell - Notification System Design: Architecture & Best Practices](https://www.magicbell.com/blog/notification-system-design)
- [OpenGrants - Best Grant Management Software for Nonprofits](https://opengrants.io/best-grant-management-software-for-nonprofits/)
- [Sopact - Grant Management Software](https://www.sopact.com/use-case/grant-management-software)
- [Bonterratech - 13 Best Grant Management Solutions](https://www.bonterratech.com/blog/best-grant-management-software)
- [Fluxx Grantseeker Pricing](https://grantseeker.fluxx.io/pricing)
- [VertesiaHQ - How to Leverage LLMs for Grant Proposal Evaluation](https://vertesiahq.com/blog/llm-powered-grant-review)
