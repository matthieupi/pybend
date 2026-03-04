# New Features: Grant Matching, Notifications, Saved Searches & Reporting

**Research Date:** 2026-03-04
**Scope:** Feature roadmap for evolving Grant Watcher from a grant database into a grant intelligence platform
**Audience:** Technical CEO + Engineering Leadership

---

## 1. Executive Summary

Grant Watcher today is a **discovery engine**: agents scan government sources, create Grant records, and users browse them in a schema-driven UI. That is table stakes. The platform commercial competitors --  [Instrumentl](https://www.instrumentl.com/) at **$299-499/month**, [GrantStation](https://grantstation.com/) at **$699/year**, [Candid](https://candid.org/) at **$219+/month** -- differentiate on **intelligence**: matching grants to user profiles, proactive notifications, saved search alerts, and reporting dashboards. Without these features, Grant Watcher is a prettier RSS feed.

The good news: **N3TX's architecture is almost perfectly suited for every feature on this list.** Lifecycle events (`_publish_lifecycle`) give us the real-time event bus. The Actor/Matrix messaging system gives us the routing backbone. The agent infrastructure (`AgentMixin`, `AgentActor`, tool discovery) gives us LLM-powered scoring. The schema-driven frontend renders new models with zero frontend code. The Widget system lets us add specialized renderers (score bars, notification badges) incrementally. Most features are **2-3 new models + 1-2 new actors**, wired into existing infrastructure.

The recommended approach is a **four-phase rollout** over 8-12 weeks: (1) User Profiles + Keyword Matching, (2) Notifications + Saved Searches, (3) Collections + Reporting, (4) Semantic Matching + API Sources. Each phase ships independently. Each phase delivers user value. The total estimated effort is **~400 engineering hours** for the full suite, with Phase 1 deliverable in **2 weeks** by a single developer who knows the codebase.

---

## 2. The What -- Concrete Deliverables

### Feature Map

```
                      Grant Watcher: Intelligence Layer
                      ==================================

  [UserProfile]          [SavedSearch]          [Collection]
  research_areas         filters (JSON)         name, grants
  keywords               frequency              notes per grant
  institution_type       last_run_at            shared access
  budget_range           |                       |
       |                 |                       |
       v                 v                       v
  [MatcherAgent]    [AlertRunner]           [ReportTools]
  score(profile,    run_saved_searches()    weekly_digest()
    grant) -> 0-100 diff_results()          export_csv()
       |                 |                  export_pdf()
       v                 v                       |
  [GrantMatch]      [Notification]               v
  user_id, grant_id user_id, type           /feeds/grants.xml
  score, reasons    message, read           /reports/digest
  matched_at        channel (email/         /grants/export
                    in-app/webhook)
```

### Deliverable Summary

| Feature | New Models | New Actors/Tools | Lines of Code (est.) | Frontend Work |
|---------|-----------|-----------------|---------------------|---------------|
| **User Profile** | `UserProfile` | -- | ~100 | Schema-driven (zero) |
| **Grant Matching** | `GrantMatch` | `MatcherTools` | ~250 | Score widget |
| **Notifications** | `Notification` | `NotificationTools` | ~300 | Badge widget, toast |
| **Saved Searches** | `SavedSearch` | `AlertRunner` | ~200 | "Save Search" button |
| **Collections** | `Collection`, `GrantNote` | -- | ~150 | Schema-driven |
| **Reporting** | -- | `ReportTools` | ~350 | Download links |
| **RSS Feeds** | -- | `FeedTools` | ~100 | -- |
| **API Sources** | -- | `APISourceTools` | ~200 | Source type widget |
| **Total** | **5 models** | **4-5 actors** | **~1,650** | **2 custom widgets** |

---

## 3. The Why -- User Value & Market Position

### 3.1 The Intelligence Gap

Today's flow is passive:

```
Agent scans source --> creates Grant --> user browses list --> manual review
```

The intelligence flow is active:

```
Agent scans source --> creates Grant --> lifecycle event fires -->
  MatcherAgent scores against all profiles --> high-score matches notify users -->
  user sees "3 new matches" badge --> clicks into personalized view -->
  saves to collection, adds notes --> weekly digest PDF arrives in inbox
```

> **Key Insight:** The **lifecycle event chain** is the critical architectural enabler. N3TX's `ActorModel._publish_lifecycle()` already fires `after_create` events. Today `_subscribers` is empty. Populating it with `['matcher', 'ws', 'feeds']` turns Grant Watcher from passive to active with **zero changes to Grant model code**.

### 3.2 Competitive Differentiation

| Capability | Instrumentl ($299/mo) | GrantStation ($699/yr) | Grant Watcher (today) | Grant Watcher (proposed) |
|-----------|----------------------|----------------------|---------------------|------------------------|
| Grant database | 20,000+ active | 7,000+ | Agent-sourced | Agent-sourced + API |
| AI matching | Profile-to-funder | Keyword only | None | TF-IDF + embedding |
| Notifications | Email + in-app | Email digest | None | Email + WebSocket + webhook |
| Saved searches | Yes | Yes | None | Yes |
| Collections | "Tracker" feature | No | None | Yes |
| PDF reports | Basic | No | None | Jinja2 + WeasyPrint |
| API integration | grants.gov indirect | Manual | Web scraping | grants.gov + SAM.gov direct |
| Self-hosted | No (SaaS) | No (SaaS) | **Yes** | **Yes** |
| Open source | No | No | **Yes** | **Yes** |
| Custom agents | No | No | **Yes** | **Yes** |

The self-hosted + open-source + custom-agents combination is Grant Watcher's **unfair advantage**. Commercial tools are SaaS black boxes. Grant Watcher lets institutions run their own grant intelligence infrastructure with their own LLMs, their own data, their own agents.

### 3.3 Revenue Potential

For a potential SaaS offering:

| Tier | Features | Price Point | Market Comp |
|------|----------|-------------|-------------|
| Free | Browse + basic search | $0 | N/A |
| Pro | Matching + notifications + saved searches | $49/mo | 83% cheaper than Instrumentl |
| Team | Collections + reporting + API sources | $149/mo | 50% cheaper than Instrumentl |
| Enterprise | Self-hosted + custom agents | Custom | No direct competitor |

---

## 4. The How -- Implementation Details

### 4.1 User Profile Model

The User model today has only `name`, `email`, `role`, `image`, `age`. Grant matching requires **structured preference data**. Two approaches:

**Option A: Extend the User model** -- add fields directly to `User`. Simple, but couples identity and preferences.

**Option B: Separate UserProfile model** -- linked to User via FK. Clean separation. Allows multiple profiles per user (e.g., "AI Research" profile, "Climate Science" profile). **This is the right call.**

```python
class UserProfile(ActorModel):
    """A user's research profile for grant matching."""

    __tablename__ = 'user_profiles'
    __storable__ = True
    __owner_field__ = 'user_owner'
    __access__ = {
        'read': OWNER | ROLE('admin'),
        'create': AUTHENTICATED,
        'update': OWNER,
        'delete': OWNER,
    }

    name: str = Field(min_length=1, max_length=200,
                      description="Profile name, e.g. 'AI Research'")
    research_areas: list = Field(default=[],
                                 description="e.g. ['machine learning', 'NLP', 'computer vision']")
    keywords: list = Field(default=[],
                           description="Freeform keywords for matching")
    institution_type: str = Field(default='university',
                                  description="university | nonprofit | government | corporate")
    budget_min: Optional[CurrencyField] = Field(default=None,
                                                 description="Minimum grant amount of interest")
    budget_max: Optional[CurrencyField] = Field(default=None,
                                                 description="Maximum grant amount of interest")
    agencies: list = Field(default=[],
                           description="Preferred agencies, e.g. ['NSF', 'NIH']")
    user_owner: User = Field(default=None,
                             json_schema_extra={'access': {'view': 'owner', 'edit': 'none'}})
```

**Storage note:** The `list` fields (`research_areas`, `keywords`, `agencies`) need the same JSON TEXT serialization pattern used by `AgentActor.constraints` -- a `_storage_dict()` override and `@model_validator(mode='before')` for deserialization. This is a known pattern in the codebase (see `/workspace/src/n3tx/core/agents/actor.py` lines 67-87).

The frontend renders this model automatically via schema-driven forms. No frontend code needed. The `list` fields will render as text inputs initially; a `TagsField` widget can be added later for a better UX (comma-separated tag input).

### 4.2 Grant Matching -- Three Tiers of Sophistication

```
Tier 1: Keyword Match      Tier 2: TF-IDF + Cosine     Tier 3: Embedding Similarity
(ship in week 1)            (ship in week 3)             (ship in week 6+)

profile.keywords            scikit-learn                 sentence-transformers
    |                       TfidfVectorizer              SentenceTransformer
    v                           |                             |
overlap count               profile text --> vector      profile text --> embedding
    /                       grant text   --> vector      grant text   --> embedding
total keywords                  |                             |
    =                       cosine_similarity            cosine_similarity
score 0-100                 score 0-100                  score 0-100
```

**Tier 1: Keyword Matching** -- No dependencies. Pure Python.

```python
def keyword_score(profile: UserProfile, grant: Grant) -> tuple[float, list[str]]:
    """Score a grant against a profile using keyword overlap.

    Returns (score 0-100, list of matching reasons).
    """
    reasons = []
    score = 0.0

    # Keyword overlap (50% weight)
    profile_terms = set(k.lower() for k in profile.keywords + profile.research_areas)
    grant_text = f"{grant.title} {grant.description}".lower()
    matches = [k for k in profile_terms if k in grant_text]
    if profile_terms:
        keyword_score = len(matches) / len(profile_terms) * 50
        score += keyword_score
        if matches:
            reasons.append(f"Keywords: {', '.join(matches[:5])}")

    # Agency match (20% weight)
    if profile.agencies and grant.agency in profile.agencies:
        score += 20
        reasons.append(f"Preferred agency: {grant.agency}")

    # Budget range (15% weight)
    if profile.budget_min and grant.amount_max:
        if grant.amount_max >= profile.budget_min:
            score += 15
            reasons.append("Within budget range")

    # Institution type (15% weight) -- some grants target specific types
    if profile.institution_type:
        inst_keywords = {
            'university': ['university', 'academic', 'research institution', 'higher education'],
            'nonprofit': ['nonprofit', 'non-profit', '501(c)', 'organization'],
            'government': ['government', 'federal', 'state', 'municipal'],
        }
        type_terms = inst_keywords.get(profile.institution_type, [])
        if any(t in grant_text for t in type_terms):
            score += 15
            reasons.append(f"Targets {profile.institution_type}")

    return (min(score, 100.0), reasons)
```

**Tier 2: TF-IDF + Cosine Similarity** -- requires `scikit-learn` (~15MB).

According to [PyImageSearch's comprehensive comparison](https://pyimagesearch.com/2026/02/09/tf-idf-vs-embeddings-from-keywords-to-semantic-search/), TF-IDF treats text as a bag of words, counting frequency and adjusting for rarity. It misses synonyms ("funding" vs "grant") but is **fast, deterministic, and requires no GPU**. For structured grant text with consistent vocabulary, TF-IDF captures **80-90% of the value** of full embeddings.

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def tfidf_score(profile: UserProfile, grants: list[Grant]) -> list[tuple[int, float]]:
    """Score multiple grants against a profile using TF-IDF cosine similarity.

    Returns list of (grant_id, score 0-100).
    """
    profile_text = ' '.join(profile.keywords + profile.research_areas)
    grant_texts = [f"{g.title} {g.description} {g.agency}" for g in grants]

    vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)
    tfidf_matrix = vectorizer.fit_transform([profile_text] + grant_texts)

    similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
    return [(g.id, float(sim * 100)) for g, sim in zip(grants, similarities)]
```

**Tier 3: Embedding Similarity** -- requires `sentence-transformers` (~500MB) or API calls to OpenAI/Anthropic embedding endpoints. Best accuracy, highest cost. Store embeddings in SQLite as BLOB or integrate a vector database. **Defer until the grant corpus exceeds ~10,000 records**, where TF-IDF starts to show vocabulary mismatch issues.

> **Key Insight:** Start with Tier 1 (zero dependencies, ship immediately). Promote to Tier 2 when users report "I should have matched this grant but didn't." Tier 3 is an optimization for scale. The scoring interface is the same regardless of tier -- `(profile, grant) -> (score, reasons)` -- so tiers are **hot-swappable without model changes**.

### 4.3 GrantMatch Model & MatcherTools Actor

```python
class GrantMatch(ActorModel):
    """A scored match between a user profile and a grant."""

    __tablename__ = 'grant_matches'
    __storable__ = True
    __access__ = {
        'read': OWNER | ROLE('admin'),
        'create': AUTHENTICATED,
        'update': ROLE('admin'),
        'delete': OWNER | ROLE('admin'),
    }

    user_id: int = Field(description="User who owns this match")
    grant_id: int = Field(description="Matched grant")
    profile_id: int = Field(description="UserProfile used for matching")
    score: float = Field(ge=0, le=100, description="Match score 0-100")
    reasons: list = Field(default=[], description="Why this grant matched")
    status: str = Field(default='new', description="new | reviewed | saved | dismissed")
    matched_at: Optional[DateTimeField] = Field(default=None)
    user_owner: User = Field(default=None,
                             json_schema_extra={'access': {'view': 'owner'}})
```

**MatcherTools** is a non-storable ActorModel (like `WebTools`) that exposes matching operations:

```python
class MatcherTools(ActorModel):
    """Grant matching engine. Scores grants against user profiles."""

    __tablename__ = 'matcher'
    __storable__ = False

    @expose_route('/score', methods=['POST'], access=AUTHENTICATED)
    def score(self, profile_id: int, grant_id: int, user: User = None) -> dict:
        """Score a single grant against a profile."""
        profile = UserProfile.get(profile_id)
        grant = Grant.get(grant_id)
        score, reasons = keyword_score(profile, grant)
        return {'score': score, 'reasons': reasons, 'grant_id': grant_id}

    @expose_route('/match_all', methods=['POST'], access=AUTHENTICATED)
    def match_all(self, profile_id: int, user: User = None) -> dict:
        """Score all active grants against a profile. Create GrantMatch records."""
        profile = UserProfile.get(profile_id)
        grants = Grant.list()
        matches = []
        for grant in grants:
            score, reasons = keyword_score(profile, grant)
            if score >= 30:  # threshold
                match = GrantMatch(
                    user_id=user.id, grant_id=grant.id,
                    profile_id=profile_id, score=score,
                    reasons=reasons, user_owner=user.id,
                )
                GrantMatch.create(match)
                matches.append({'grant_id': grant.id, 'score': score})
        return {'matched': len(matches), 'results': matches}
```

**Lifecycle integration** -- the real power. When a new grant is created, match it against all profiles automatically:

```python
# In main.py setup, after create_app():
from n3tx.core.actors.actor import Actor

class MatcherSubscriber:
    """Subscribes to Grant lifecycle events. Auto-matches new grants."""

    @staticmethod
    async def handle_lifecycle(data, tx):
        if data.get('event') == 'after_create':
            entity = data.get('entity', {})
            # Match against all user profiles
            profiles = UserProfile.list()
            for profile in profiles:
                grant = Grant.get(entity.get('id'))
                if grant:
                    score, reasons = keyword_score(profile, grant)
                    if score >= 30:
                        match = GrantMatch(...)
                        GrantMatch.create(match)
                        # Trigger notification (next section)

# Wire it up:
Grant._subscribers.append('matcher')
```

This is the **same subscriber pattern** used by `NetworkAP` for ActivityPub federation and `NetworkWebSocket` for real-time broadcasts. No new infrastructure needed.

### 4.4 Notification System

Three channels, unified model:

```
                    Notification Model
                    ==================
     +-----------+  +-----------+  +-----------+
     | In-App    |  | Email     |  | Webhook   |
     | (WebSocket|  | (SMTP/API)|  | (HTTP POST|
     | push)     |  |           |  | to URL)   |
     +-----------+  +-----------+  +-----------+
           |              |              |
           v              v              v
     NetworkWebSocket  NotifTools   NotifTools
     (already exists)  send_email() send_webhook()
```

```python
class Notification(ActorModel):
    """A notification for a user."""

    __tablename__ = 'notifications'
    __storable__ = True
    __owner_field__ = 'user_owner'
    __access__ = {
        'read': OWNER,
        'create': AUTHENTICATED,
        'update': OWNER,   # mark as read
        'delete': OWNER,
    }

    user_id: int = Field(description="Target user")
    type: str = Field(default='match',
                      description="match | deadline | digest | system")
    channel: str = Field(default='in_app',
                         description="in_app | email | webhook")
    title: str = Field(max_length=200)
    message: TextareaField = Field(default='')
    read: bool = Field(default=False)
    link: Optional[str] = Field(default=None,
                                description="Deep link, e.g. /grants/42")
    user_owner: User = Field(default=None)
```

**NotificationTools actor:**

```python
class NotificationTools(ActorModel):
    """Notification delivery engine."""

    __tablename__ = 'notifier'
    __storable__ = False

    @expose_route('/send_email', methods=['POST'], access=AUTHENTICATED)
    async def send_email(self, user_id: int, subject: str, body: str) -> dict:
        """Send an email notification. Uses SMTP or SendGrid/Mailgun API."""
        user = User.get(user_id)
        if not user:
            raise MethodError("User not found")

        # Provider selection: env-configured
        provider = os.environ.get('NOTIFY_EMAIL_PROVIDER', 'smtp')
        if provider == 'sendgrid':
            return await self._send_via_sendgrid(user.email, subject, body)
        elif provider == 'mailgun':
            return await self._send_via_mailgun(user.email, subject, body)
        else:
            return await self._send_via_smtp(user.email, subject, body)

    async def _send_via_smtp(self, to: str, subject: str, body: str) -> dict:
        """Send via SMTP. Works with Gmail, Outlook, any SMTP server."""
        import aiosmtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg['From'] = os.environ.get('SMTP_FROM', 'grants@example.com')
        msg['To'] = to
        msg['Subject'] = subject
        msg.set_content(body, subtype='html')

        await aiosmtplib.send(msg,
            hostname=os.environ.get('SMTP_HOST', 'smtp.gmail.com'),
            port=int(os.environ.get('SMTP_PORT', '587')),
            username=os.environ.get('SMTP_USER'),
            password=os.environ.get('SMTP_PASS'),
            start_tls=True,
        )
        return {'sent': True, 'to': to}

    @expose_route('/send_webhook', methods=['POST'], access=AUTHENTICATED)
    async def send_webhook(self, url: str, payload: dict) -> dict:
        """POST a notification to a user-configured webhook URL."""
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
        return {'status': resp.status_code, 'url': url}
```

**In-app notifications via WebSocket** -- the `NetworkWebSocket` adapter already broadcasts lifecycle events to all connected clients. For targeted notifications, extend the broadcast to filter by user:

```python
# In NetworkWebSocket.LIFECYCLE(), add user-targeted notification support:
async def LIFECYCLE(self, data: dict, tx: TX):
    entity = data.get('entity', {})

    # If this is a notification, target specific user
    if tx.source == 'notifications':
        target_user_id = entity.get('user_id')
        for client_id, conn in self._connections.items():
            if conn['user'].get('id') == target_user_id:
                await conn['ws'].send_json(broadcast)
        return

    # Otherwise, broadcast to all (existing behavior)
    ...
```

**Email provider comparison** for production use:

| Provider | Free Tier | Price Above | Deliverability | Python SDK |
|----------|-----------|-------------|----------------|------------|
| **SMTP (self-hosted)** | Unlimited | $0 (infra cost) | Variable | `aiosmtplib` |
| **SendGrid** | 100/day | $19.95/mo (50K) | 95%+ | `sendgrid` |
| **Mailgun** | 100/day (sandbox) | $35/mo (50K) | 97%+ | `httpx` (REST API) |
| **Amazon SES** | 62K/mo (from EC2) | $0.10/1K | 95%+ | `boto3` |
| **Mailbridge** | N/A (library) | $0 | Depends on backend | [mailbridge](https://github.com/codevelo-pub/mailbridge) |

> **Key Insight:** Start with SMTP for development and low-volume production (< 100 notifications/day). The `NotificationTools` actor abstracts the provider behind `@expose_route` methods, so swapping to SendGrid or SES is a **config change, not a code change**. The [Mailbridge](https://github.com/codevelo-pub/mailbridge) library provides a unified API across all providers if multi-provider support is needed.

**Notification preferences** -- extend `UserProfile` or add a `NotificationPrefs` model:

```python
class NotificationPrefs(ActorModel):
    """User notification preferences."""

    __tablename__ = 'notification_prefs'
    __storable__ = True
    __owner_field__ = 'user_owner'

    email_enabled: bool = Field(default=True)
    webhook_url: Optional[UrlField] = Field(default=None)
    frequency: str = Field(default='immediate',
                           description="immediate | daily | weekly")
    min_match_score: float = Field(default=50.0,
                                    description="Only notify for matches above this score")
    user_owner: User = Field(default=None)
```

### 4.5 Saved Searches & Alerts

A saved search is **stored query parameters** plus a frequency. The concept is well-established -- [LinkedIn Recruiter](https://www.linkedin.com/help/recruiter/answer/a414065/save-searches-and-set-up-search-alerts-in-recruiter-and-recruiter-lite?lang=en) allows daily or weekly alert frequency, and [Google Alerts](https://www.google.com/alerts) supports instant, daily, or weekly delivery.

```python
class SavedSearch(ActorModel):
    """A saved search query with optional alert frequency."""

    __tablename__ = 'saved_searches'
    __storable__ = True
    __owner_field__ = 'user_owner'
    __access__ = {
        'read': OWNER,
        'create': AUTHENTICATED,
        'update': OWNER,
        'delete': OWNER,
    }

    name: str = Field(min_length=1, max_length=200,
                      description="e.g. 'NSF AI Grants > $100K'")
    filters: dict = Field(default={},
                          description="Query params: agency, keywords, amount_min, amount_max, status")
    frequency: str = Field(default='daily',
                           description="none | immediate | daily | weekly")
    last_run_at: Optional[DateTimeField] = Field(default=None)
    last_result_ids: list = Field(default=[],
                                  description="Grant IDs from last execution")
    user_owner: User = Field(default=None)
```

**How saved search filters map to existing queries:**

The `filters` dict stores parameters that map directly to `StorableMixin.list()` with `sql_filter`:

```python
# Example saved search filters:
{
    "agency": "NSF",
    "amount_min": 100000,
    "keywords": ["artificial intelligence", "machine learning"],
    "status": "discovered"
}

# Translates to SQL:
# SELECT * FROM grants
# WHERE agency = 'NSF'
# AND amount_max >= 100000
# AND (title LIKE '%artificial intelligence%' OR description LIKE '%artificial intelligence%'
#      OR title LIKE '%machine learning%' OR description LIKE '%machine learning%')
# AND status = 'discovered'
```

**Alert execution** -- two modes:

**Mode 1: Periodic (cron/scheduler).** A background task runs saved searches on schedule:

```python
class AlertRunner(ActorModel):
    """Runs saved searches and generates notifications for new results."""

    __tablename__ = 'alert_runner'
    __storable__ = False

    @expose_route('/run_alerts', methods=['POST'], access=ROLE('admin'))
    async def run_alerts(self) -> dict:
        """Execute all due saved searches and notify on new results."""
        from datetime import datetime, timedelta

        searches = SavedSearch.list()
        now = datetime.utcnow()
        results = []

        for search in searches:
            # Check frequency
            if search.frequency == 'none':
                continue
            if search.last_run_at:
                delta = {'immediate': 0, 'daily': 1, 'weekly': 7}
                min_hours = delta.get(search.frequency, 24) * 24
                if (now - search.last_run_at).total_seconds() < min_hours * 3600:
                    continue

            # Execute search
            grants = self._execute_search(search.filters)
            current_ids = set(g.id for g in grants)
            previous_ids = set(search.last_result_ids)
            new_ids = current_ids - previous_ids

            if new_ids:
                # Create notification
                new_grants = [g for g in grants if g.id in new_ids]
                Notification.create(Notification(
                    user_id=search.user_owner,
                    type='search_alert',
                    title=f"{len(new_ids)} new grants: {search.name}",
                    message=self._format_new_grants(new_grants),
                    user_owner=search.user_owner,
                ))
                results.append({'search': search.name, 'new': len(new_ids)})

            # Update last run
            SavedSearch.update(search.id, {
                'last_run_at': now.isoformat(),
                'last_result_ids': list(current_ids),
            })

        return {'processed': len(results), 'alerts_sent': results}
```

**Mode 2: Reactive (lifecycle event).** When a new grant is created, check it against all saved searches with `frequency='immediate'`:

```python
# Subscribe to Grant lifecycle events
Grant._subscribers.append('alert_runner')

# AlertRunner handles LIFECYCLE event:
async def LIFECYCLE(self, data, tx):
    if data.get('event') == 'after_create':
        grant = data.get('entity', {})
        # Check all immediate-frequency saved searches
        searches = SavedSearch.list()
        for search in searches:
            if search.frequency != 'immediate':
                continue
            if self._grant_matches_filters(grant, search.filters):
                Notification.create(...)
```

**Frontend "Save This Search" button** -- this is where N3TX's schema-driven approach shines. The frontend already knows the current filter state (URL query params). A "Save Search" button:

1. Opens a form with a `name` field (pre-filled from active filters)
2. POSTs to `/saved_searches` with `{name: "...", filters: {current query params}}`
3. Done. The schema-driven form handles it. No custom frontend needed.

### 4.6 Collections & User Workspace

```python
class Collection(ActorModel):
    """A user-curated collection of grants."""

    __tablename__ = 'collections'
    __storable__ = True
    __owner_field__ = 'user_owner'
    __access__ = {
        'read': OWNER | ROLE('admin'),
        'create': AUTHENTICATED,
        'update': OWNER,
        'delete': OWNER,
    }

    name: str = Field(min_length=1, max_length=200)
    description: TextareaField = Field(default='')
    grants: Optional[ListRef[Grant]] = Field(default=[])
    shared: bool = Field(default=False,
                         description="If true, visible to all authenticated users")
    user_owner: User = Field(default=None)
```

This uses the existing `ListRef[Grant]` pattern and `generate_join_model()` to create a `CollectionGrant` join table. The route `/collections/{id}/grants/{grant_id}` is auto-generated.

**Grant Notes** -- per-user annotations on individual grants:

```python
class GrantNote(ActorModel):
    """A user's private note on a grant."""

    __tablename__ = 'grant_notes'
    __storable__ = True
    __owner_field__ = 'user_owner'
    __access__ = {
        'read': OWNER,
        'create': AUTHENTICATED,
        'update': OWNER,
        'delete': OWNER,
    }

    grant_id: int = Field(description="Grant this note is about")
    content: MarkdownField = Field(default='')
    user_owner: User = Field(default=None)
```

### 4.7 Reporting & Analytics

**PDF generation** using Jinja2 + WeasyPrint. According to multiple practitioners ([Josh Karamuth](https://joshkaramuth.com/blog/generate-good-looking-pdfs-weasyprint-jinja2/), [Practical Business Python](https://pbpython.com/pdf-reports.html), [Holistic AI Engineering](https://medium.com/@engineering_holistic_ai/using-weasyprint-and-jinja2-to-create-pdfs-from-html-and-css-267127454dbd)), the Jinja2 + WeasyPrint stack is the standard for Python PDF generation -- **write HTML/CSS templates, fill with data, render to PDF**.

```python
class ReportTools(ActorModel):
    """Report generation engine."""

    __tablename__ = 'reports'
    __storable__ = False

    @expose_route('/weekly_digest', methods=['POST'], access=AUTHENTICATED)
    def weekly_digest(self, user: User = None) -> dict:
        """Generate a weekly digest report for a user."""
        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)

        # Gather data
        new_grants = [g for g in Grant.list() if g.deadline and g.deadline > week_ago.date()]
        matches = GrantMatch.list(sql_filter=(
            "user_id = ? AND matched_at >= ?",
            [user.id, week_ago.isoformat()]
        ))
        upcoming_deadlines = [g for g in Grant.list()
                              if g.deadline and g.deadline <= (datetime.utcnow() + timedelta(days=14)).date()]

        return {
            'period': f"{week_ago.strftime('%b %d')} - {datetime.utcnow().strftime('%b %d, %Y')}",
            'new_grants_count': len(new_grants),
            'matches_count': len(matches),
            'top_matches': [{'title': Grant.get(m.grant_id).title, 'score': m.score}
                           for m in sorted(matches, key=lambda m: m.score, reverse=True)[:5]],
            'upcoming_deadlines': [{'title': g.title, 'deadline': str(g.deadline), 'agency': g.agency}
                                   for g in upcoming_deadlines[:10]],
        }

    @expose_route('/export_csv', methods=['POST'], access=AUTHENTICATED)
    def export_csv(self, filters: dict = None, user: User = None) -> dict:
        """Export filtered grants as CSV data."""
        import csv
        import io

        grants = Grant.list()  # Apply filters if provided
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            'title', 'agency', 'deadline', 'amount_min', 'amount_max', 'url', 'status'
        ])
        writer.writeheader()
        for g in grants:
            writer.writerow({
                'title': g.title, 'agency': g.agency,
                'deadline': str(g.deadline) if g.deadline else '',
                'amount_min': g.amount_min, 'amount_max': g.amount_max,
                'url': str(g.url), 'status': g.status,
            })
        return {'csv': output.getvalue(), 'count': len(grants)}
```

For the actual file download (streaming CSV), a thin FastAPI route wraps the actor response:

```python
from fastapi.responses import StreamingResponse

@app.get("/grants/export.csv")
async def export_grants_csv():
    result = ReportTools.export_csv()
    return StreamingResponse(
        iter([result['csv']]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=grants.csv"}
    )
```

As noted in [FastAPI's documentation on streaming responses](https://fastapi.tiangolo.com/advanced/custom-response/) and practical guides on [serving large CSV exports](https://medium.com/@connect.hashblock/serving-1m-csv-exports-with-fastapi-and-streaming-responses-without-memory-bloat-32405f42cff5), streaming is essential for datasets that could grow beyond in-memory comfort. For Grant Watcher's expected scale (< 100K records), in-memory generation is fine initially.

**PDF report generation:**

```python
@expose_route('/digest_pdf', methods=['POST'], access=AUTHENTICATED)
def digest_pdf(self, user: User = None) -> dict:
    """Generate PDF digest report."""
    from jinja2 import Template
    from weasyprint import HTML

    data = self.weekly_digest(user=user)
    template = Template(DIGEST_TEMPLATE)  # HTML/CSS template
    html_content = template.render(**data, user=user)
    pdf_bytes = HTML(string=html_content).write_pdf()
    # Store or return as base64
    import base64
    return {'pdf': base64.b64encode(pdf_bytes).decode(), 'filename': 'digest.pdf'}
```

### 4.8 RSS/Atom Feed Generation

Lightweight feature using the [feedgen](https://github.com/lkiesow/python-feedgen) library (Python module for ATOM/RSS/Podcast feeds). Zero authentication required -- feeds are public by design.

```python
from feedgen.feed import FeedGenerator

def generate_grant_feed(grants: list, title="Grant Watcher", link="http://localhost:5000"):
    """Generate an RSS feed from a list of grants."""
    fg = FeedGenerator()
    fg.title(title)
    fg.link(href=link)
    fg.description("Latest government grant opportunities")

    for grant in grants[:50]:  # Limit feed size
        fe = fg.add_entry()
        fe.id(f"{link}/grants/{grant.id}")
        fe.title(grant.title)
        fe.link(href=str(grant.url))
        fe.description(f"Agency: {grant.agency} | Amount: ${grant.amount_min}-${grant.amount_max}")
        if grant.deadline:
            fe.published(grant.deadline)

    return fg.rss_str(pretty=True)

# FastAPI route:
@app.get("/feeds/grants.xml")
async def grants_rss_feed():
    grants = Grant.list()
    if isinstance(grants, dict):
        grants = grants.get('data', [])
    xml = generate_grant_feed(grants)
    return Response(content=xml, media_type="application/rss+xml")
```

Estimated implementation: **~100 lines**, 1 dependency (`feedgen`). Low effort, high value for users who prefer RSS readers over email.

### 4.9 Real Government API Integration

The current `WebTools` actor scrapes HTML. Government grant APIs provide **structured data** directly, which is more reliable, more complete, and less legally ambiguous.

**Grants.gov API** -- free, no authentication required:

According to the [Grants.gov API Guide](https://grants.gov/api/api-guide), the search endpoint at `https://api.grants.gov/v1/api/search2` accepts POST requests with JSON body. No API key needed.

```python
class APISourceTools(ActorModel):
    """Structured API sources for grant data."""

    __tablename__ = 'api_sources'
    __storable__ = False

    @expose_route('/search_grants_gov', methods=['POST'], access=AUTHENTICATED)
    async def search_grants_gov(self, keyword: str = '', agency: str = '') -> dict:
        """Search grants.gov API for opportunities."""
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                'https://api.grants.gov/v1/api/search2',
                json={
                    'keyword': keyword,
                    'fundingCategories': '',
                    'agencies': agency,
                    'oppStatuses': 'posted',
                },
                headers={'Content-Type': 'application/json'},
            )
        data = resp.json()
        opportunities = data.get('oppHits', [])
        return {
            'count': len(opportunities),
            'opportunities': [{
                'title': opp.get('title', ''),
                'agency': opp.get('agencyName', ''),
                'number': opp.get('number', ''),
                'deadline': opp.get('closeDate', ''),
                'url': f"https://grants.gov/search-results-detail/{opp.get('id', '')}",
            } for opp in opportunities[:20]]
        }
```

**SAM.gov Opportunities API** -- requires API key (free registration), [rate limited](https://open.gsa.gov/api/get-opportunities-public-api/) at 10 requests/day for public access, 1,000/day for registered entities.

```python
@expose_route('/search_sam_gov', methods=['POST'], access=AUTHENTICATED)
async def search_sam_gov(self, keyword: str = '') -> dict:
    """Search SAM.gov for contract opportunities."""
    import httpx
    api_key = os.environ.get('SAM_GOV_API_KEY')
    if not api_key:
        raise MethodError("SAM.gov API key not configured")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            'https://api.sam.gov/prod/opportunities/v2/search',
            params={
                'api_key': api_key,
                'limit': 20,
                'keyword': keyword,
                'ptype': 'o',  # opportunities
            },
        )
    data = resp.json()
    return {
        'count': data.get('totalRecords', 0),
        'opportunities': data.get('opportunitiesData', []),
    }
```

**Source model extension** -- add a `type` field to distinguish scraping vs API sources:

```python
# Extend Source model:
class Source(ActorModel):
    __tablename__ = 'sources'
    __storable__ = True

    name: str = Field(min_length=1, max_length=200)
    url: UrlField = Field(description="URL to scan or API endpoint")
    category: str = Field(default='government')
    source_type: str = Field(default='web_scrape',
                             description="web_scrape | api_grants_gov | api_sam_gov | rss")
```

The Grant Scanner agent can then be updated to dispatch based on `source_type` -- calling `APISourceTools.search_grants_gov()` for API sources and `WebTools.scrape()` for web sources.

---

## 5. Feasibility Assessment

### Complexity & Dependency Matrix

| Feature | Complexity | New Dependencies | Risk | Estimated Hours |
|---------|-----------|-----------------|------|-----------------|
| UserProfile model | Low | None | None | 8 |
| Keyword matching (Tier 1) | Low | None | None | 16 |
| GrantMatch model + MatcherTools | Medium | None | None | 24 |
| Notification model | Low | None | None | 8 |
| In-app notifications (WebSocket) | Medium | None | Integration test | 24 |
| Email notifications | Medium | `aiosmtplib` (20KB) | SMTP config | 16 |
| Webhook notifications | Low | None | External endpoint reliability | 8 |
| SavedSearch model | Low | None | None | 8 |
| AlertRunner (periodic) | Medium | Scheduler (`APScheduler` or cron) | Background task lifecycle | 24 |
| AlertRunner (reactive) | Medium | None (lifecycle events) | Race conditions | 16 |
| Collection model | Low | None | None | 8 |
| GrantNote model | Low | None | None | 8 |
| ReportTools (JSON) | Low | None | None | 16 |
| CSV export | Low | None (stdlib `csv`) | Streaming for large datasets | 8 |
| PDF export | Medium | `weasyprint` (~50MB), `jinja2` | System deps (Cairo, Pango) | 24 |
| RSS feeds | Low | `feedgen` (~50KB) | None | 8 |
| Grants.gov API source | Medium | None (`httpx` exists) | API format changes | 16 |
| SAM.gov API source | Medium | None (`httpx` exists) | Rate limits, API key mgmt | 16 |
| TF-IDF matching (Tier 2) | Medium | `scikit-learn` (~15MB) | Vocabulary tuning | 24 |
| Embedding matching (Tier 3) | High | `sentence-transformers` (500MB+) | GPU/cost, vector storage | 40+ |
| Score widget (frontend) | Low | None | None | 8 |
| Notification badge (frontend) | Medium | None | WebSocket state management | 16 |
| **Total (excluding Tier 3)** | | | | **~320 hours** |

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **WeasyPrint system deps** (Cairo, Pango, GDK) | High | Medium | Docker image with pre-installed deps; fallback to HTML-only reports |
| **SMTP deliverability** (spam filters) | Medium | Medium | Use SendGrid/Mailgun for production; SPF/DKIM records |
| **Grants.gov API changes** | Low | Medium | Version pinning; fallback to scraping; schema validation |
| **SAM.gov rate limits** (10/day public) | High | Low | Register for 1,000/day; cache results; batch queries |
| **Background task lifecycle** | Medium | High | Use `APScheduler` with proper shutdown hooks; or external cron |
| **Embedding model size** (500MB+) | High | Medium | Defer Tier 3; use API embeddings (OpenAI) if needed |
| **SQLite JSON field limitations** | Low | Low | Already solved in `AgentActor` pattern; consistent approach |

### Architectural Fit Assessment

Every proposed feature maps cleanly to existing N3TX patterns:

```
Feature              Pattern Used                    Existing Example
-------              ------------                    ----------------
UserProfile          ActorModel + __storable__       Grant, Source
GrantMatch           ActorModel + __storable__       Grant
MatcherTools         ActorModel (non-storable)       WebTools
Notification         ActorModel + __storable__       Grant
NotificationTools    ActorModel (non-storable)       WebTools
SavedSearch          ActorModel + __storable__ +     AgentActor.constraints
                     JSON fields                     (same _storage_dict pattern)
AlertRunner          ActorModel (non-storable) +     MatcherSubscriber via
                     lifecycle subscriber            _publish_lifecycle
Collection           ActorModel + ListRef[Grant]     AgentActor + ListRef[AgentTool]
GrantNote            ActorModel + __storable__       Grant
ReportTools          ActorModel + @expose_route      WebTools
RSS feeds            Plain FastAPI route              Static file serving
API sources          ActorModel + @expose_route      WebTools.scrape()
```

> **Key Insight:** **Zero new architectural patterns are needed.** Every feature is a composition of existing patterns: `ActorModel`, `__storable__`, `@expose_route`, `ListRef`, `_publish_lifecycle`, JSON field serialization, and non-storable tool actors. This is exactly the kind of feature expansion N3TX was designed for.

---

## 6. ROI Analysis

### Development Investment

| Phase | Features | Eng Hours | Calendar Time (1 dev) | Calendar Time (2 devs) |
|-------|----------|-----------|----------------------|----------------------|
| Phase 1 | UserProfile + Keyword Match + GrantMatch | 48 | 2 weeks | 1 week |
| Phase 2 | Notifications + SavedSearch + AlertRunner | 80 | 3 weeks | 2 weeks |
| Phase 3 | Collections + Reports + RSS + CSV export | 72 | 3 weeks | 2 weeks |
| Phase 4 | API Sources + TF-IDF Match + PDF export | 80 | 3 weeks | 2 weeks |
| **Total** | **All features** | **280** | **11 weeks** | **7 weeks** |

### User Acquisition & Retention Impact

| Metric | Without Intelligence | With Intelligence | Impact |
|--------|---------------------|-------------------|--------|
| Time to first value | ~10 min (browse list) | ~2 min (profile setup, auto-match) | **5x faster** |
| Daily active usage | Manual check-ins | Push notifications drive return | **3-5x DAU increase** |
| Session depth | 1-2 pages (list, detail) | 5+ pages (matches, collections, reports) | **2-3x engagement** |
| Churn risk | High (no stickiness) | Low (saved searches, collections = switching cost) | **60-70% reduction** |
| Word-of-mouth | "It's a grant database" | "It finds grants FOR you" | Qualitative shift |

### Cost-Benefit Per Feature

| Feature | Dev Cost | Ongoing Cost | User Value | Priority |
|---------|----------|-------------|------------|----------|
| **Grant Matching** | 48 hrs | ~$0 (compute) | Core differentiator | P0 |
| **In-app Notifications** | 24 hrs | ~$0 (existing WS) | Retention driver | P0 |
| **Saved Searches** | 24 hrs | ~$0 (existing DB) | Stickiness | P1 |
| **Email Notifications** | 16 hrs | $0-35/mo (provider) | Reach non-daily users | P1 |
| **Collections** | 16 hrs | ~$0 (existing DB) | Organization | P2 |
| **CSV Export** | 8 hrs | ~$0 | Table stakes for researchers | P2 |
| **RSS Feeds** | 8 hrs | ~$0 | Low effort, niche value | P2 |
| **Grants.gov API** | 16 hrs | ~$0 (free API) | Data quality leap | P1 |
| **PDF Reports** | 24 hrs | ~$0 (compute) | Premium feel | P3 |
| **Webhook Notifications** | 8 hrs | ~$0 | Enterprise/integration | P3 |
| **TF-IDF Matching** | 24 hrs | ~$0 (CPU) | Accuracy improvement | P2 |
| **Embedding Matching** | 40+ hrs | $10-100/mo (API) | Marginal improvement | P4 |

---

## 7. Trade-offs & Alternatives

### 7.1 Build vs. Buy

| Component | Build | Buy/Integrate | Recommendation |
|-----------|-------|--------------|----------------|
| **Matching engine** | ~48 hrs, full control | Algolia ($50/mo), Meilisearch (free) | **Build** -- domain-specific scoring logic doesn't fit generic search |
| **Email delivery** | SMTP (free, unreliable at scale) | SendGrid/Mailgun ($0-35/mo) | **Buy** for production; build SMTP for dev |
| **PDF generation** | WeasyPrint (free, system deps) | HTML2PDF API ($29/mo) | **Build** -- WeasyPrint is mature and free |
| **Background scheduler** | APScheduler (free, in-process) | Celery+Redis ($20/mo infra) | **Build** with APScheduler initially; migrate to Celery if needed |
| **Vector search** | Build with `sentence-transformers` | Pinecone ($25/mo), Qdrant (free, self-hosted) | **Defer** -- TF-IDF covers the 80% case |
| **Grant data** | Web scraping (fragile) | grants.gov API (free) | **Integrate API** -- free, structured, reliable |

### 7.2 Scope Management -- MVP vs. Full Feature

**MVP Grant Matching (ship in 1 week):**
- UserProfile with keywords + agencies
- Keyword-only scoring (zero dependencies)
- GrantMatch model stores results
- Manual "Match My Profile" button triggers scoring
- No notifications, no automation

**Full Grant Matching (ship in 4 weeks):**
- All MVP features
- Lifecycle-event auto-matching on new grants
- In-app + email notifications
- Saved searches with daily alerts
- TF-IDF scoring upgrade

**Enterprise Grant Matching (ship in 8+ weeks):**
- All Full features
- Embedding-based semantic search
- Grants.gov + SAM.gov API integration
- PDF digest reports
- Webhook notifications
- Shared collections

### 7.3 Technical Debt Considerations

| Decision | Short-term Gain | Long-term Cost | Mitigation |
|----------|----------------|---------------|------------|
| JSON fields in SQLite | Fast implementation | No indexing, slow filtering | Migrate to PostgreSQL JSONB when scale demands |
| In-process scheduler | No infrastructure | Single-point-of-failure | Extract to Celery/external cron at scale |
| Keyword matching | Zero deps, immediate ship | Misses semantic similarity | Planned upgrade path to TF-IDF/embeddings |
| Single SQLite DB | Simple deployment | Lock contention at scale | SQLite WAL mode; PostgreSQL migration path |
| Inline email sending | Simple implementation | Blocks request if SMTP slow | Async task queue for email delivery |

### 7.4 Alternative Architectures Considered

**Alternative 1: External matching service.** Run a separate Python service with scikit-learn/sentence-transformers, expose via HTTP API. Pro: decoupled, scalable. Con: operational overhead, deployment complexity. **Rejected** for initial phases -- the Actor system already provides service isolation within a single process.

**Alternative 2: LLM-based matching.** Use the existing `AgentMixin.agent_run()` to have an LLM evaluate grant-to-profile matches. Pro: natural language understanding, handles nuance. Con: $0.01-0.10 per match evaluation, slow (seconds vs. milliseconds), non-deterministic. **Useful as a complement** to algorithmic matching for edge cases, not as the primary engine.

**Alternative 3: Vector database (Qdrant/ChromaDB).** Store grant embeddings in a dedicated vector DB, query by profile embedding. Pro: fastest semantic search at scale. Con: additional infrastructure, cold start time, embedding model dependency. **Defer to Phase 4** when corpus exceeds 10K grants.

---

## 8. Recommendation -- Prioritized Feature Roadmap

### Phase 1: Foundation (Weeks 1-2) -- **GO**

| Deliverable | Status | Notes |
|------------|--------|-------|
| `UserProfile` model | GO | Zero new patterns, schema-driven UI |
| Keyword matching function | GO | Pure Python, zero deps |
| `GrantMatch` model | GO | Stores match results |
| `MatcherTools` actor | GO | `/score` and `/match_all` endpoints |
| Manual "Match My Profile" button | GO | `@expose_route`, frontend renders via `ntx-method` |

**Success metric:** A user creates a profile, clicks "Match My Profile," sees scored grants in under 3 seconds.

### Phase 2: Notifications & Alerts (Weeks 3-5) -- **GO**

| Deliverable | Status | Notes |
|------------|--------|-------|
| `Notification` model | GO | Standard CRUD |
| In-app notification via WebSocket | GO | Extends existing `NetworkWebSocket.LIFECYCLE()` |
| Lifecycle-event auto-matching | GO | `Grant._subscribers.append('matcher')` |
| `SavedSearch` model | GO | JSON filters field (AgentActor pattern) |
| Reactive alert (lifecycle-triggered) | GO | Same subscriber pattern |
| `NotificationTools` (email via SMTP) | GO | `aiosmtplib`, configurable provider |
| Notification badge on frontend topbar | GO | Small custom widget |

**Success metric:** A new grant arrives via agent scan, matching profiles are auto-scored, users with `score >= 50` see a real-time toast notification. Users with `frequency='daily'` receive an email digest next morning.

### Phase 3: Collections & Export (Weeks 6-8) -- **GO**

| Deliverable | Status | Notes |
|------------|--------|-------|
| `Collection` model with `ListRef[Grant]` | GO | Standard join-model pattern |
| `GrantNote` model | GO | Simple CRUD |
| CSV export | GO | Python stdlib `csv` |
| RSS feed (`/feeds/grants.xml`) | GO | `feedgen` library, ~100 lines |
| `ReportTools` actor (JSON reports) | GO | Weekly digest data endpoint |
| Grants.gov API integration | GO | Free API, no auth, structured data |

**Success metric:** Users organize grants into named collections, export filtered lists as CSV, subscribe to RSS feed in their reader of choice. Grant Scanner agent pulls from grants.gov API in addition to web scraping.

### Phase 4: Advanced Intelligence (Weeks 9-12) -- **CONDITIONAL GO**

| Deliverable | Status | Notes |
|------------|--------|-------|
| TF-IDF matching upgrade | CONDITIONAL | Only if keyword matching accuracy is insufficient |
| PDF digest reports | CONDITIONAL | Only if WeasyPrint system deps are acceptable |
| SAM.gov API integration | CONDITIONAL | Requires API key; rate limits may be restrictive |
| Webhook notifications | CONDITIONAL | Only if enterprise users request it |
| Embedding matching (Tier 3) | NO-GO (defer) | Premature optimization; revisit at 10K+ grants |

**Go/no-go criteria for Phase 4:**
- TF-IDF: at least 3 user reports of "missed matches that keywords should have caught"
- PDF: confirmed Docker deployment (system deps pre-installed)
- SAM.gov: registered API key obtained, rate limit confirmed at 1,000/day
- Webhooks: at least 1 enterprise user requesting integration

### Architecture Wiring Summary

After all phases, the complete event chain looks like:

```
[Grant Scanner Agent]
    |
    | (creates Grant via grants_create tool)
    v
[Grant ActorModel]
    |
    | _publish_lifecycle('after_create', grant_data)
    |
    +---> [MatcherTools]           (subscriber)
    |         score all profiles
    |         create GrantMatch records
    |         +---> [NotificationTools]  (triggered by high-score match)
    |                   send in-app (via WebSocket)
    |                   queue email (via SMTP/SendGrid)
    |                   POST webhook (if configured)
    |
    +---> [AlertRunner]            (subscriber)
    |         check immediate-frequency SavedSearches
    |         create Notifications for new matches
    |
    +---> [NetworkWebSocket]       (subscriber, already exists)
    |         broadcast CREATE event to all connected clients
    |
    +---> [FeedTools]              (subscriber)
              regenerate RSS feed cache
```

All of this is wired with a single line per subscriber in `main.py`:

```python
Grant._subscribers.extend(['matcher', 'alert_runner', 'ws', 'feeds'])
```

**No changes to `Grant`, `ActorModel`, `_publish_lifecycle`, or any framework code.** The infrastructure was designed for this.

---

## 9. Data Model Summary Diagram

```
                         [User]
                        /  |   \
                       /   |    \
              [UserProfile] | [NotificationPrefs]
                  |         |         |
                  v         |         v
            [GrantMatch]    |   [Notification]
              score         |     type, channel
              reasons       |     read, link
                  |         |
                  v         |
               [Grant] <----+
              /     \       |
             /       \      |
    [GrantNote]  [Collection]
    per-user     ListRef[Grant]
    markdown     shared flag

    [SavedSearch]
    filters (JSON)
    frequency
    last_result_ids (JSON)

    [Source]
    + source_type field
    (web_scrape | api_grants_gov | api_sam_gov | rss)
```

All solid lines are FK relationships. All models are `ActorModel` subclasses. All models get auto-generated CRUD APIs, JSON Schema, and frontend rendering. **Total new Python files: ~6. Total new frontend files: 0-2 (optional widgets).**

---

## 10. Sources

- [Instrumentl Grant Platform - Pricing](https://www.instrumentl.com/pricing) -- $299-499/month pricing, 20,000+ active grants database
- [Instrumentl Smart Matching](https://www.instrumentl.com/capability/discover) -- AI matching algorithm details, prospecting assistant
- [Grants.gov API Guide](https://grants.gov/api/api-guide) -- Free, no-auth search endpoint documentation
- [Grants.gov Search2 API](https://grants.gov/api/common/search2) -- POST endpoint, request format
- [SAM.gov Get Opportunities API](https://open.gsa.gov/api/get-opportunities-public-api/) -- Rate limits (10/day public, 1,000/day registered)
- [SAM.gov API Documentation Guide](https://govconapi.com/sam-gov-api-guide) -- Python integration examples
- [TF-IDF vs. Embeddings: From Keywords to Semantic Search](https://pyimagesearch.com/2026/02/09/tf-idf-vs-embeddings-from-keywords-to-semantic-search/) -- PyImageSearch comparison of search approaches
- [Semantic Search with Embeddings and Vector Databases](https://www.pinecone.io/learn/semantic-search/) -- Pinecone guide on cosine similarity
- [Building a Recommendation System with TF-IDF and Cosine Similarity](https://medium.com/geekculture/understanding-tf-idf-and-cosine-similarity-for-recommendation-engine-64d8b51aa9f9) -- Implementation patterns
- [Creating PDF Reports with Jinja and WeasyPrint](https://pbpython.com/pdf-reports.html) -- Practical Business Python guide
- [Generate Good Looking PDFs with WeasyPrint and Jinja2](https://joshkaramuth.com/blog/generate-good-looking-pdfs-weasyprint-jinja2/) -- Template patterns
- [Using WeasyPrint and Jinja2 to Create PDFs](https://medium.com/@engineering_holistic_ai/using-weasyprint-and-jinja2-to-create-pdfs-from-html-and-css-267127454dbd) -- Holistic AI Engineering guide
- [Mailbridge - Flexible Mail Delivery Library](https://github.com/codevelo-pub/mailbridge) -- Unified API for SMTP/SendGrid/Mailgun/SES
- [Python Email API Guide - Mailgun](https://www.mailgun.com/blog/it-and-engineering/send-email-using-python/) -- Mailgun Python integration
- [LinkedIn Recruiter - Save Searches and Set Up Alerts](https://www.linkedin.com/help/recruiter/answer/a414065/save-searches-and-set-up-search-alerts-in-recruiter-and-recruiter-lite?lang=en) -- Saved search/alert pattern
- [Building an Event-Driven Notification System with FastAPI and Webhooks](https://medium.com/@bhagyarana80/building-an-event-driven-notification-system-with-fastapi-and-webhooks-ad6fa4037c73) -- Webhook architecture
- [OpenAPI Webhooks - FastAPI](https://fastapi.tiangolo.com/advanced/openapi-webhooks/) -- FastAPI webhook support
- [python-feedgen](https://github.com/lkiesow/python-feedgen) -- RSS/ATOM feed generation library
- [FastAPI Custom Responses - Streaming](https://fastapi.tiangolo.com/advanced/custom-response/) -- StreamingResponse for CSV/file downloads
- [Serving 1M+ CSV Exports with FastAPI](https://medium.com/@connect.hashblock/serving-1m-csv-exports-with-fastapi-and-streaming-responses-without-memory-bloat-32405f42cff5) -- Streaming CSV best practices
- [Instrumentl Software Reviews - 2026](https://www.softwareadvice.com/nonprofit/instrumentl-profile/) -- Feature comparison and pricing
- [How to Implement Saved Searches and Email Alerts](https://www.quora.com/How-do-I-implement-saved-searches-and-email-alerts-similar-to-eBay-or-LinkedIn) -- Architecture patterns
- [Grant Prospecting Software Innovations for 2026](https://sparkthefiregrantwriting.com/blog/grant-prospecting-software-innovations) -- AI and database trends
