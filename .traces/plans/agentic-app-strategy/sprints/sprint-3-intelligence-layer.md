# Sprint 3: Intelligence Layer Foundation

**Duration:** ~2 weeks (10 working days)
**Wave:** [0.10]
**Branch:** v0.10 (or feature/intelligence-layer off v0.9)
**Predecessor:** Sprint 2 (assumed complete: Grant, Source, AgentActor, WebTools all functional)

---

## 1. Sprint Goal

A user creates a research profile, clicks "Match My Profile," and sees scored grants ranked by relevance -- all with zero frontend code. When an agent creates a new grant, all existing profiles are automatically scored and GrantMatch records are created for high-confidence matches. The matching function is a pure, swappable Python function (keyword-based now, TF-IDF/embeddings later).

**Success Criteria:**
1. `POST /matcher/match_all` with a profile_id returns scored grants in under 3 seconds for 100 grants
2. Creating a Grant via the API triggers lifecycle-driven matching against all profiles
3. All new models (UserProfile, GrantMatch) render correctly in the schema-driven UI with no frontend changes
4. OWNER-scoped access: users see only their own profiles and matches
5. All tests pass: unit tests for `keyword_score()`, integration tests for CRUD + matching + lifecycle

---

## 2. Architecture Decisions

### 2.1 MatcherTools: Non-Storable ActorModel

**Decision:** `MatcherTools` is a non-storable `ActorModel`, identical in pattern to `WebTools`.

**Rationale:** It needs to be routable via Matrix (to receive LIFECYCLE TXs from Grant._subscribers), it needs `@expose_route` methods (for HTTP-accessible `/score` and `/match_all`), and it has no persistent state of its own. A non-storable ActorModel satisfies all three requirements with the least conceptual overhead. It auto-registers with Matrix via ActorMeta, which is exactly what the subscriber wiring needs.

**Alternative rejected:** A plain Actor or ActorProxy. These would work for lifecycle handling but would require manual route registration instead of the automatic `@expose_route` -> `register_routes()` pipeline. Non-storable ActorModel gives us both for free.

### 2.2 Matching Function: Standalone Pure Function

**Decision:** `keyword_score(profile, grant)` is a standalone function in its own module (`example_grants/matching/keyword_score.py`), not a method on any model.

**Rationale:** PyBend's philosophy: "Primitives, not opinions." The scoring function is a composable building block. Keeping it as a pure function with signature `(profile, grant) -> (float, list[str])` means:
- It can be unit-tested without any database or actor infrastructure
- It can be swapped for `tfidf_score()` or `embedding_score()` later by changing one import in `MatcherTools`
- It has zero dependencies on PyBend framework code

### 2.3 Lifecycle Subscriber: Existing Infrastructure

**Decision:** Use the existing `_publish_lifecycle` + `_subscribers` pattern. Wire `Grant._subscribers.append('matcher')` in `main.py` after `create_app()`.

**Rationale:** `ActorModel._publish_lifecycle()` already fires `asyncio.create_task(cls.send(TX(...)))` for each subscriber address. The `MatcherTools` class auto-registers with Matrix under its `__tablename__` address ('matcher'). When Grant publishes a LIFECYCLE TX targeting 'matcher', Matrix routes it to MatcherTools.inbox(), which dispatches to MatcherTools.handler(), which falls through to the generic `LIFECYCLE` method via getattr. Zero new framework mechanisms needed.

### 2.4 JSON Field Serialization

Both `UserProfile` and `GrantMatch` have `list` fields that need JSON TEXT serialization in SQLite. This follows the exact pattern established by `AgentActor.constraints`:

- `_JSON_FIELDS` tuple declaring which fields need serialization
- `_storage_dict()` override: converts Python list/dict to JSON string before storage
- `@model_validator(mode='before')` classmethod: converts JSON string back to Python list/dict when loading from DB
- `update()` classmethod override: serializes JSON fields before delegating to `super().update()`

---

## 3. Task Breakdown

### Task 1: Create the `keyword_score` Module
**File:** `/workspace/example_grants/matching/__init__.py` (empty)
**File:** `/workspace/example_grants/matching/keyword_score.py`
**Dependencies:** None
**Estimate:** 2 hours
**Priority:** P0 (everything else depends on this)

Create a pure Python function with zero framework dependencies:

```python
def keyword_score(profile, grant) -> tuple[float, list[str]]:
```

**Scoring algorithm (4 dimensions, 100 points max):**

| Dimension | Weight | Logic | Max Points |
|-----------|--------|-------|------------|
| Keyword overlap | 50% | `profile.keywords + profile.research_areas` (lowercased set) checked for substring match in `grant.title + " " + grant.description` (lowercased). Score = `matched_count / total_terms * 50`. | 50 |
| Agency match | 20% | If `profile.agencies` is non-empty and `grant.agency` (case-insensitive) is in the list, award 20 points. | 20 |
| Budget range | 15% | If `profile.budget_min` is set and `grant.amount_max` is set and `grant.amount_max >= profile.budget_min`, award 7.5. If `profile.budget_max` is set and `grant.amount_min` is set and `grant.amount_min <= profile.budget_max`, award 7.5. Both conditions met = 15. | 15 |
| Institution type | 15% | Map `profile.institution_type` to a set of keywords (e.g., 'university' -> ['university', 'academic', 'research institution', 'higher education']). If any keyword appears in grant text, award 15 points. | 15 |

**Reasons list:** Each dimension that scores > 0 appends a human-readable reason string. Examples:
- `"Keywords: machine learning, NLP (2/5 matched)"`
- `"Preferred agency: NSF"`
- `"Within budget range"`
- `"Targets university"`

**Score is capped at 100.0.**

**Implementation detail -- profile and grant duck typing:**
The function accesses attributes via dot notation (`profile.keywords`, `grant.title`). It does NOT import UserProfile or Grant. This means it works with any object that has the right attributes, making it trivially testable with plain dataclass/namedtuple stubs.

```python
"""Keyword-based grant matching -- Tier 1 scoring.

Pure Python, zero dependencies. Scores a grant against a user profile
using keyword overlap, agency match, budget range, and institution type.

Swap this module for tfidf_score or embedding_score without changing
any model or actor code. The interface is:

    (profile, grant) -> (score: float 0-100, reasons: list[str])
"""

INSTITUTION_KEYWORDS = {
    'university': ['university', 'academic', 'research institution', 'higher education'],
    'nonprofit': ['nonprofit', 'non-profit', '501(c)', 'organization'],
    'government': ['government', 'federal', 'state', 'municipal'],
    'corporate': ['corporate', 'industry', 'company', 'business'],
}

MATCH_THRESHOLD = 30  # Minimum score to create a GrantMatch record


def keyword_score(profile, grant) -> tuple[float, list[str]]:
    """Score a grant against a profile using keyword overlap.

    Args:
        profile: Object with keywords (list), research_areas (list),
                 agencies (list), budget_min (float|None),
                 budget_max (float|None), institution_type (str).
        grant:   Object with title (str), description (str),
                 agency (str), amount_min (float|None),
                 amount_max (float|None).

    Returns:
        (score 0-100, list of human-readable reason strings)
    """
    reasons = []
    score = 0.0

    # --- Keyword overlap (50% weight) ---
    profile_terms = set(
        k.lower().strip()
        for k in (getattr(profile, 'keywords', []) or [])
        + (getattr(profile, 'research_areas', []) or [])
        if k and k.strip()
    )
    grant_text = f"{grant.title} {grant.description}".lower()

    if profile_terms:
        matches = [k for k in profile_terms if k in grant_text]
        keyword_pts = len(matches) / len(profile_terms) * 50
        score += keyword_pts
        if matches:
            display = ', '.join(sorted(matches)[:5])
            reasons.append(f"Keywords: {display} ({len(matches)}/{len(profile_terms)} matched)")

    # --- Agency match (20% weight) ---
    profile_agencies = [a.lower().strip() for a in (getattr(profile, 'agencies', []) or []) if a]
    grant_agency = (getattr(grant, 'agency', '') or '').lower().strip()
    if profile_agencies and grant_agency and grant_agency in profile_agencies:
        score += 20
        reasons.append(f"Preferred agency: {grant.agency}")

    # --- Budget range (15% weight) ---
    budget_pts = 0.0
    profile_budget_min = getattr(profile, 'budget_min', None)
    profile_budget_max = getattr(profile, 'budget_max', None)
    grant_amount_min = getattr(grant, 'amount_min', None)
    grant_amount_max = getattr(grant, 'amount_max', None)

    if profile_budget_min is not None and grant_amount_max is not None:
        if grant_amount_max >= profile_budget_min:
            budget_pts += 7.5
    if profile_budget_max is not None and grant_amount_min is not None:
        if grant_amount_min <= profile_budget_max:
            budget_pts += 7.5

    # If only one side of the range is specified, use the half that matched
    if budget_pts > 0:
        score += budget_pts
        reasons.append("Within budget range")

    # --- Institution type (15% weight) ---
    institution_type = (getattr(profile, 'institution_type', '') or '').lower().strip()
    if institution_type:
        type_terms = INSTITUTION_KEYWORDS.get(institution_type, [])
        if any(t in grant_text for t in type_terms):
            score += 15
            reasons.append(f"Targets {institution_type}")

    return (min(score, 100.0), reasons)
```

### Task 2: Unit Tests for `keyword_score`
**File:** `/workspace/example_grants/tests/test_keyword_score.py`
**Dependencies:** Task 1
**Estimate:** 2 hours
**Priority:** P0

Test cases using plain dataclass stubs (no PyBend imports):

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class FakeProfile:
    keywords: list
    research_areas: list
    agencies: list
    institution_type: str
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None

@dataclass
class FakeGrant:
    title: str
    description: str
    agency: str
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
```

| Test | Input | Expected |
|------|-------|----------|
| `test_perfect_match` | All 4 dimensions match | score ~100, 4 reasons |
| `test_no_match` | No overlap on any dimension | score == 0, no reasons |
| `test_keyword_only` | Keywords match, nothing else | 0 < score <= 50, 1 reason |
| `test_agency_only` | Agency matches, nothing else | score == 20, 1 reason |
| `test_budget_within_range` | Budget matches both sides | budget contributes 15 pts |
| `test_budget_partial_range` | Only one side of budget matches | budget contributes 7.5 pts |
| `test_budget_out_of_range` | Grant too small/large | budget contributes 0 |
| `test_institution_type_match` | 'university' and grant text contains 'academic' | 15 pts |
| `test_institution_type_no_match` | 'university' but no matching terms in grant | 0 from institution |
| `test_empty_profile` | All lists empty | score == 0 |
| `test_none_fields` | Keywords=None, agencies=None | No crash, score == 0 |
| `test_score_capped_at_100` | Pathological case that might exceed 100 | score == 100 |
| `test_case_insensitive` | Keywords/agency differ in case | Still match |
| `test_partial_keyword_overlap` | 3 of 6 keywords match | score = 3/6 * 50 = 25 |
| `test_reasons_content` | Specific matching scenario | Verify reason strings contain expected text |

### Task 3: UserProfile Model
**File:** `/workspace/example_grants/models/user_profile.py`
**Dependencies:** None (parallel with Task 1)
**Estimate:** 2 hours
**Priority:** P0

```python
from __future__ import annotations
import json
from typing import ClassVar, Optional
from pydantic import Field, model_validator

from pybend.core.models.actor_model import ActorModel
from pybend.core.authorize import AUTHENTICATED, OWNER, ROLE
from pybend.core.widgets import CurrencyField
from models.user import User


# Fields stored as JSON TEXT in SQLite
_JSON_FIELDS = ('research_areas', 'keywords', 'agencies')


class UserProfile(ActorModel):
    """A user's research profile for grant matching.

    Users can have multiple profiles (e.g., 'AI Research', 'Climate Science')
    to match against different grant opportunities.
    """

    __tablename__: ClassVar[str] = 'user_profiles'
    __storable__: ClassVar[bool] = True
    __owner_field__: ClassVar[str] = 'user_owner'
    __protected_fields__: ClassVar[set] = {'user_owner'}
    __access__: ClassVar[dict] = {
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
                              description="User who owns this profile",
                              json_schema_extra={'access': {'view': 'owner', 'edit': 'none'}})

    @model_validator(mode='before')
    @classmethod
    def _deserialize_json_fields(cls, data):
        """Deserialize JSON TEXT strings from SQLite back to Python objects."""
        if isinstance(data, dict):
            for field in _JSON_FIELDS:
                val = data.get(field)
                if isinstance(val, str):
                    try:
                        data[field] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
        return data

    def _storage_dict(self, exclude_unset: bool = True) -> dict:
        """Serialize list fields to JSON strings for SQLite storage."""
        d = super()._storage_dict(exclude_unset=exclude_unset)
        for field in _JSON_FIELDS:
            if field in d and not isinstance(d[field], str):
                d[field] = json.dumps(d[field], default=str)
        return d

    @classmethod
    def update(cls, id, data):
        """Serialize JSON fields before storage update."""
        from pydantic import BaseModel
        if isinstance(data, BaseModel):
            data_dict = data.model_dump(exclude_unset=True)
        elif isinstance(data, dict):
            data_dict = dict(data)
        else:
            data_dict = data
        for field in _JSON_FIELDS:
            if field in data_dict and not isinstance(data_dict[field], str):
                data_dict[field] = json.dumps(data_dict[field], default=str)
        return super().update(id, data_dict)
```

**Key implementation notes:**

1. **`_JSON_FIELDS = ('research_areas', 'keywords', 'agencies')`** -- three list fields that need JSON roundtrip. Follows the exact same pattern as `AgentActor._JSON_FIELDS = ('constraints',)`.

2. **`__owner_field__ = 'user_owner'`** -- enables the OWNER access rule. When a user queries `/user_profiles`, the access layer generates a SQL filter `WHERE user_owner = ?` with the authenticated user's ID, so users only see their own profiles.

3. **`__protected_fields__ = {'user_owner'}`** -- the route layer auto-injects `user_owner` from the JWT token on create and strips it from update payloads. Users cannot set or change ownership via the API.

4. **`CurrencyField`** for budget fields -- renders with a currency widget in the frontend automatically.

### Task 4: GrantMatch Model
**File:** `/workspace/example_grants/models/grant_match.py`
**Dependencies:** None (parallel with Task 1, Task 3)
**Estimate:** 2 hours
**Priority:** P0

```python
from __future__ import annotations
import json
from typing import ClassVar, Optional
from pydantic import Field, model_validator

from pybend.core.models.actor_model import ActorModel
from pybend.core.authorize import AUTHENTICATED, OWNER, ROLE
from pybend.core.widgets import DateTimeField
from models.user import User


# Fields stored as JSON TEXT in SQLite
_JSON_FIELDS = ('reasons',)


class GrantMatch(ActorModel):
    """A scored match between a user profile and a grant.

    Created automatically by MatcherTools when a grant scores above the
    threshold for a user profile, or manually via the /score endpoint.
    """

    __tablename__: ClassVar[str] = 'grant_matches'
    __storable__: ClassVar[bool] = True
    __owner_field__: ClassVar[str] = 'user_owner'
    __protected_fields__: ClassVar[set] = {'user_owner', 'matched_at'}
    __access__: ClassVar[dict] = {
        'read': OWNER | ROLE('admin'),
        'create': AUTHENTICATED,
        'update': OWNER,
        'delete': OWNER | ROLE('admin'),
    }
    __ui__: ClassVar[dict] = {
        'field_order': ['score', 'status', 'reasons', 'grant_id', 'profile_id', 'matched_at'],
    }

    grant_id: int = Field(description="ID of the matched grant")
    profile_id: int = Field(description="ID of the UserProfile used for matching")
    score: float = Field(ge=0, le=100, description="Match score 0-100")
    reasons: list = Field(default=[], description="Why this grant matched")
    status: str = Field(default='new',
                         description="new | reviewed | saved | dismissed")
    matched_at: Optional[DateTimeField] = Field(default=None,
                                                  description="When the match was computed")
    user_owner: User = Field(default=None,
                              description="User who owns this match",
                              json_schema_extra={'access': {'view': 'owner', 'edit': 'none'}})

    @model_validator(mode='before')
    @classmethod
    def _deserialize_json_fields(cls, data):
        """Deserialize JSON TEXT strings from SQLite back to Python objects."""
        if isinstance(data, dict):
            for field in _JSON_FIELDS:
                val = data.get(field)
                if isinstance(val, str):
                    try:
                        data[field] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
        return data

    def _storage_dict(self, exclude_unset: bool = True) -> dict:
        """Serialize list fields to JSON strings for SQLite storage."""
        d = super()._storage_dict(exclude_unset=exclude_unset)
        for field in _JSON_FIELDS:
            if field in d and not isinstance(d[field], str):
                d[field] = json.dumps(d[field], default=str)
        return d

    @classmethod
    def update(cls, id, data):
        """Serialize JSON fields before storage update."""
        from pydantic import BaseModel
        if isinstance(data, BaseModel):
            data_dict = data.model_dump(exclude_unset=True)
        elif isinstance(data, dict):
            data_dict = dict(data)
        else:
            data_dict = data
        for field in _JSON_FIELDS:
            if field in data_dict and not isinstance(data_dict[field], str):
                data_dict[field] = json.dumps(data_dict[field], default=str)
        return super().update(id, data_dict)
```

**Key notes:**

1. **`reasons` is a JSON list** -- stores human-readable strings like `["Keywords: NLP, machine learning", "Preferred agency: NSF"]`. One JSON field, same `_JSON_FIELDS` pattern.

2. **`status` field** -- starts as 'new', transitions to 'reviewed' (user saw it), 'saved' (user bookmarked it), or 'dismissed' (user rejected it). This is a manual state managed by the user via `PUT /grant_matches/{id}`.

3. **`matched_at`** -- set programmatically by MatcherTools when creating the match. Protected field so API consumers can't fake timestamps.

4. **`grant_id` and `profile_id`** -- plain integer FKs, not Ref types. These are cross-references, not ownership relationships. The UI auto-hides `*_id` fields via `_apply_field_exclusion()` in proto_model, but they're visible in the API response for programmatic use.

### Task 5: MatcherTools Actor
**File:** `/workspace/example_grants/models/matcher_tools.py`
**Dependencies:** Task 1, Task 3, Task 4
**Estimate:** 4 hours
**Priority:** P0

```python
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import ClassVar

from pybend.core.models.actor_model import ActorModel
from pybend.core.utils.decorators import expose_route
from pybend.core.authorize import AUTHENTICATED
from pybend.core.utils.erroring import MethodError

logger = logging.getLogger('grants.matcher')


class MatcherTools(ActorModel):
    """Grant matching engine. Scores grants against user profiles.

    Non-storable ActorModel: has HTTP endpoints and receives lifecycle
    events, but stores no data of its own. Match results are stored
    in GrantMatch records.
    """

    __tablename__: ClassVar[str] = 'matcher'
    __storable__: ClassVar[bool] = False

    @expose_route('/score', methods=['POST'], access=AUTHENTICATED)
    def score(self, profile_id: int, grant_id: int, user: 'User' = None) -> dict:
        """Score a single grant against a profile.

        Returns: {score: float, reasons: list, grant_id: int, profile_id: int}
        """
        from models.user_profile import UserProfile
        from models.grant import Grant
        from matching.keyword_score import keyword_score

        profile = UserProfile.get(profile_id)
        if not profile:
            raise MethodError(f"UserProfile {profile_id} not found", status_code=404)

        grant = Grant.get(grant_id)
        if not grant:
            raise MethodError(f"Grant {grant_id} not found", status_code=404)

        # Verify ownership: user can only score against their own profiles
        if user and hasattr(profile, 'user_owner'):
            owner_val = profile.user_owner
            if hasattr(owner_val, 'id'):
                owner_val = owner_val.id
            elif isinstance(owner_val, str) and '/' in owner_val:
                try:
                    owner_val = int(owner_val.rstrip('/').rsplit('/', 1)[-1])
                except (ValueError, IndexError):
                    pass
            if owner_val != user.id:
                raise MethodError("Cannot score against another user's profile", status_code=403)

        score_val, reasons = keyword_score(profile, grant)
        return {
            'score': round(score_val, 2),
            'reasons': reasons,
            'grant_id': grant_id,
            'profile_id': profile_id,
        }

    @expose_route('/match_all', methods=['POST'], access=AUTHENTICATED)
    def match_all(self, profile_id: int, user: 'User' = None) -> dict:
        """Score all active grants against a profile. Create GrantMatch records.

        Only creates matches for scores >= MATCH_THRESHOLD (30).
        Skips grants that already have a GrantMatch for this profile.

        Returns: {matched: int, skipped: int, results: [{grant_id, score}]}
        """
        from models.user_profile import UserProfile
        from models.grant import Grant
        from models.grant_match import GrantMatch
        from matching.keyword_score import keyword_score, MATCH_THRESHOLD

        profile = UserProfile.get(profile_id)
        if not profile:
            raise MethodError(f"UserProfile {profile_id} not found", status_code=404)

        # Verify ownership
        if user:
            owner_val = profile.user_owner
            if hasattr(owner_val, 'id'):
                owner_val = owner_val.id
            elif isinstance(owner_val, str) and '/' in owner_val:
                try:
                    owner_val = int(owner_val.rstrip('/').rsplit('/', 1)[-1])
                except (ValueError, IndexError):
                    pass
            if owner_val != user.id:
                raise MethodError("Cannot match against another user's profile", status_code=403)

        # Get all grants (no pagination -- we need all for scoring)
        grants_result = Grant.list()
        if isinstance(grants_result, dict):
            grants = grants_result.get('data', [])
        else:
            grants = grants_result

        # Check existing matches to avoid duplicates
        existing = GrantMatch.list()
        if isinstance(existing, dict):
            existing = existing.get('data', [])
        existing_pairs = set()
        for m in existing:
            m_profile_id = m.profile_id
            m_grant_id = m.grant_id
            existing_pairs.add((m_profile_id, m_grant_id))

        now = datetime.now(timezone.utc).isoformat()
        matches = []
        skipped = 0

        for grant in grants:
            if (profile_id, grant.id) in existing_pairs:
                skipped += 1
                continue

            score_val, reasons = keyword_score(profile, grant)
            if score_val >= MATCH_THRESHOLD:
                match = GrantMatch(
                    grant_id=grant.id,
                    profile_id=profile_id,
                    score=round(score_val, 2),
                    reasons=reasons,
                    status='new',
                    matched_at=now,
                    user_owner=user.id if user else None,
                )
                GrantMatch.create(match)
                matches.append({
                    'grant_id': grant.id,
                    'score': round(score_val, 2),
                })

        return {
            'matched': len(matches),
            'skipped': skipped,
            'threshold': MATCH_THRESHOLD,
            'results': sorted(matches, key=lambda m: m['score'], reverse=True),
        }

    # ── Lifecycle event handler ──

    async def LIFECYCLE(self, data: dict, tx):
        """Handle lifecycle events from subscribed models (e.g., Grant).

        When a new grant is created, automatically score it against all
        user profiles and create GrantMatch records for high-scoring matches.
        """
        event = data.get('event')
        if event != 'after_create':
            return  # Only match on new grants

        entity = data.get('entity', {})
        grant_id = entity.get('id')
        if not grant_id:
            logger.warning("[MatcherTools] LIFECYCLE after_create with no entity id")
            return

        from models.user_profile import UserProfile
        from models.grant import Grant
        from models.grant_match import GrantMatch
        from matching.keyword_score import keyword_score, MATCH_THRESHOLD

        grant = Grant.get(grant_id)
        if not grant:
            logger.warning("[MatcherTools] Grant %s not found for lifecycle matching", grant_id)
            return

        # Score against ALL profiles (cross-user)
        profiles_result = UserProfile.list()
        if isinstance(profiles_result, dict):
            profiles = profiles_result.get('data', [])
        else:
            profiles = profiles_result

        now = datetime.now(timezone.utc).isoformat()
        match_count = 0

        for profile in profiles:
            score_val, reasons = keyword_score(profile, grant)
            if score_val >= MATCH_THRESHOLD:
                # Resolve user_owner from the profile
                owner_val = profile.user_owner
                if hasattr(owner_val, 'id'):
                    owner_val = owner_val.id
                elif isinstance(owner_val, str) and '/' in owner_val:
                    try:
                        owner_val = int(owner_val.rstrip('/').rsplit('/', 1)[-1])
                    except (ValueError, IndexError):
                        owner_val = None

                match = GrantMatch(
                    grant_id=grant.id,
                    profile_id=profile.id,
                    score=round(score_val, 2),
                    reasons=reasons,
                    status='new',
                    matched_at=now,
                    user_owner=owner_val,
                )
                GrantMatch.create(match)
                match_count += 1

        if match_count:
            logger.info(
                "[MatcherTools] Grant %s matched %d profiles (threshold=%d)",
                grant_id, match_count, MATCH_THRESHOLD,
            )
```

**Key implementation details:**

1. **`LIFECYCLE` method** -- Named exactly `LIFECYCLE` to match the TX name sent by `_publish_lifecycle()`. The ActorModel handler dispatches to `getattr(target, tx.name)`, and the TX name is `'LIFECYCLE'`. The method signature is `(self, data, tx)` matching Actor's generic handler convention for non-exposed methods.

2. **Imports are local** -- `from models.user_profile import UserProfile` etc. are inside method bodies to avoid circular import issues (MatcherTools is in the same models package).

3. **Duplicate prevention in `match_all`** -- Before scoring, existing `(profile_id, grant_id)` pairs are loaded. This prevents duplicate GrantMatch records on repeated calls.

4. **Owner resolution** -- The `user_owner` field on UserProfile may be hydrated as an href string (e.g., `"http://.../users/3"`) when loaded from DB via FK hydration. The code handles this by extracting the trailing ID, matching the OWNER rule's resolution logic in `authorize/rules.py`.

5. **Cross-user lifecycle matching** -- When a new grant arrives, it must be scored against ALL profiles from ALL users (not just the creating user). This is the reactive intelligence: any user whose profile matches gets a GrantMatch record automatically. The `LIFECYCLE` handler iterates all profiles without auth filtering.

### Task 6: Update Models Package and main.py
**File:** `/workspace/example_grants/models/__init__.py`
**File:** `/workspace/example_grants/main.py`
**Dependencies:** Task 3, Task 4, Task 5
**Estimate:** 1 hour
**Priority:** P0

**6a. Update `models/__init__.py`:**

Add the three new models to the package exports:

```python
from .user import User
from .grant import Grant
from .source import Source
from .web_tools import WebTools
from .user_profile import UserProfile
from .grant_match import GrantMatch
from .matcher_tools import MatcherTools

__all__ = ["User", "Grant", "Source", "WebTools", "UserProfile", "GrantMatch", "MatcherTools"]
```

**6b. Update `main.py`:**

Three changes:

1. Add new models to the `models=` list in `create_app()`
2. Add join models for `(User, UserProfile)` and `(User, GrantMatch)`
3. Wire lifecycle subscriber: `Grant._subscribers.append('matcher')`

```python
# In imports:
from models import User, Grant, Source, WebTools, UserProfile, GrantMatch, MatcherTools

# In create_app():
app = create_app(
    models=[User, Grant, Source, WebTools, AgentTool, AgentActor,
            UserProfile, GrantMatch, MatcherTools],
    join_models=[
        (AgentActor, AgentTool),
        (User, UserProfile),
        (User, GrantMatch),
    ],
    storage=storage,
    routing='actor',
    # ... rest unchanged
)

# After create_app(), before __main__:
Grant._subscribers.append('matcher')
```

**Why join models for `(User, UserProfile)` and `(User, GrantMatch)`:**

These create nested routes:
- `GET /users/{user_id}/user_profiles` -- list profiles for a specific user
- `GET /users/{user_id}/grant_matches` -- list matches for a specific user

This follows the existing pattern of `(AgentActor, AgentTool)` which creates `/agents/{id}/agent_tools`.

**Note:** The `User` model does NOT need a `ListRef[UserProfile]` or `ListRef[GrantMatch]` field for join models to work. The join model is generated from the parent-child pair and creates the FK column (`user_id`) automatically. However, if we want the FK hydration (profile list appearing in User responses), we would need to add these fields. For Sprint 3, we skip this -- profiles and matches are accessed via their own endpoints, not embedded in User responses. This keeps the User model unchanged.

**IMPORTANT: Join model consideration.** Actually, `generate_join_model(User, UserProfile)` requires that User has a `ListRef[UserProfile]` field or at least that we pass the generated model to `register_model`. Looking at the `generate_join_model` function more carefully, it requires `owner_cls` to have storage set (it does) and creates a join table `users_user_profiles`. But the join model approach is specifically for when the parent has a `ListRef` field pointing to the child. Without that field, the join model's nested routes won't have the correct FK wiring.

**Revised approach:** Instead of join models, UserProfile and GrantMatch are **standalone models** with a `user_owner` FK field. Access control via `OWNER` rule ensures users only see their own records. The `/user_profiles` and `/grant_matches` endpoints are top-level, not nested under `/users/{id}/`. This is simpler and consistent with how access control already works -- the OWNER rule generates `WHERE user_owner = ?` SQL filter on list queries.

**Updated main.py** -- remove the join models for User:

```python
app = create_app(
    models=[User, Grant, Source, WebTools, AgentTool, AgentActor,
            UserProfile, GrantMatch, MatcherTools],
    join_models=[
        (AgentActor, AgentTool),
    ],
    storage=storage,
    routing='actor',
    # ... rest unchanged
)

# Wire lifecycle subscriber
Grant._subscribers.append('matcher')
```

### Task 7: Integration Tests -- UserProfile CRUD
**File:** `/workspace/example_grants/tests/test_user_profile_crud.py`
**Dependencies:** Task 3, Task 6
**Estimate:** 2 hours
**Priority:** P0

Update conftest.py seed data (add a `_seed_profiles` function) and write tests:

**7a. Update `conftest.py`:**

Add imports for new models and a profile seeding function:

```python
from models import User, Grant, Source, WebTools, UserProfile, GrantMatch, MatcherTools

def _seed_profiles(users):
    """Create test profiles for Alice and Bob."""
    profiles = {}
    profiles['alice_ai'] = UserProfile.create(UserProfile(
        name="AI Research",
        research_areas=["machine learning", "natural language processing"],
        keywords=["deep learning", "transformer", "NLP"],
        institution_type="university",
        budget_min=50000,
        budget_max=500000,
        agencies=["NSF", "DARPA"],
        user_owner=users["alice"].id,
    ))
    profiles['bob_climate'] = UserProfile.create(UserProfile(
        name="Climate Science",
        research_areas=["climate change", "environmental science"],
        keywords=["carbon capture", "renewable energy", "sustainability"],
        institution_type="nonprofit",
        budget_min=25000,
        budget_max=200000,
        agencies=["EPA", "DOE"],
        user_owner=users["bob"].id,
    ))
    return profiles
```

Update `seed_data` fixture to include profiles.

**7b. Test file:**

| Test Class | Test | Description |
|------------|------|-------------|
| `TestUserProfileCreate` | `test_create_profile_authenticated` | POST `/user_profiles` with valid data, expect 201 |
| | `test_create_profile_unauthenticated` | POST without token, expect 401/403 |
| | `test_create_profile_json_fields_roundtrip` | Create profile with list fields, GET it back, verify lists are deserialized correctly |
| `TestUserProfileList` | `test_list_profiles_owner_only` | Alice sees only her profiles, not Bob's |
| | `test_list_profiles_admin_sees_all` | Admin token sees all profiles |
| `TestUserProfileGet` | `test_get_own_profile` | Alice can GET her own profile |
| | `test_get_other_user_profile_denied` | Alice cannot GET Bob's profile (403) |
| `TestUserProfileUpdate` | `test_update_own_profile` | Alice can PUT her profile |
| | `test_update_other_user_profile_denied` | Alice cannot PUT Bob's profile (403) |
| `TestUserProfileDelete` | `test_delete_own_profile` | Owner can delete |
| | `test_delete_other_user_profile_denied` | Non-owner, non-admin denied |

### Task 8: Integration Tests -- GrantMatch CRUD
**File:** `/workspace/example_grants/tests/test_grant_match_crud.py`
**Dependencies:** Task 4, Task 6
**Estimate:** 1.5 hours
**Priority:** P0

Similar pattern to UserProfile tests but focused on GrantMatch model:

| Test | Description |
|------|-------------|
| `test_list_matches_owner_only` | User sees only their own matches |
| `test_get_own_match` | Owner can read their match |
| `test_update_match_status` | Owner can change status from 'new' to 'reviewed' |
| `test_match_reasons_json_roundtrip` | Create match with reasons list, verify deserialization |

### Task 9: Integration Tests -- MatcherTools Endpoints
**File:** `/workspace/example_grants/tests/test_matcher.py`
**Dependencies:** Task 5, Task 6, Task 7 (needs seed profiles and grants)
**Estimate:** 3 hours
**Priority:** P0

**9a. `/matcher/score` endpoint tests:**

| Test | Description |
|------|-------------|
| `test_score_returns_valid_result` | POST with profile_id + grant_id, verify response has score (float), reasons (list), grant_id, profile_id |
| `test_score_matching_grant` | Seed a grant with keywords matching Alice's AI profile, verify score > 0 |
| `test_score_non_matching_grant` | Seed a grant with no keyword overlap, verify score == 0 or very low |
| `test_score_invalid_profile_id` | Non-existent profile_id, expect 404 |
| `test_score_invalid_grant_id` | Non-existent grant_id, expect 404 |
| `test_score_other_users_profile` | Alice tries to score against Bob's profile, expect 403 |
| `test_score_unauthenticated` | No token, expect 401/403 |

**9b. `/matcher/match_all` endpoint tests:**

| Test | Description |
|------|-------------|
| `test_match_all_creates_records` | POST match_all, verify GrantMatch records are created in DB |
| `test_match_all_response_format` | Verify response has matched (int), skipped (int), threshold (float), results (list) |
| `test_match_all_respects_threshold` | Seed grants that score below threshold, verify they don't create matches |
| `test_match_all_deduplicates` | Run match_all twice, verify no duplicate GrantMatch records |
| `test_match_all_other_users_profile` | Alice tries match_all with Bob's profile_id, expect 403 |

**9c. Seed data for matcher tests:**

Create additional grants that specifically match and don't match the test profiles:

```python
# Matching Alice's AI profile:
Grant(title="NSF AI Research Initiative", agency="NSF",
      description="Deep learning and transformer architectures for NLP",
      amount_min=100000, amount_max=400000, ...)

# Matching Bob's Climate profile:
Grant(title="EPA Climate Adaptation Program", agency="EPA",
      description="Carbon capture and renewable energy solutions",
      amount_min=50000, amount_max=150000, ...)

# Matching nobody:
Grant(title="Maritime Safety Standards Update", agency="USCG",
      description="Coast guard vessel inspection protocols",
      amount_min=10000, amount_max=30000, ...)
```

### Task 10: Integration Tests -- Lifecycle Subscriber (Reactive Matching)
**File:** `/workspace/example_grants/tests/test_lifecycle_matching.py`
**Dependencies:** Task 5, Task 6, Task 7
**Estimate:** 3 hours
**Priority:** P1

This is the most architecturally significant test -- it verifies that creating a Grant via the API triggers automatic matching against all profiles.

**Test approach:** Since `_publish_lifecycle` uses `asyncio.create_task()` (fire-and-forget), the lifecycle handler runs asynchronously after the HTTP response returns. The test needs to account for this timing.

**Strategy:**
1. Create profiles for Alice and Bob via API (or seed data)
2. POST a new grant that should match Alice's profile keywords
3. Wait briefly (or poll) for the GrantMatch records to appear
4. Verify GrantMatch records were created with correct scores

```python
import time

class TestLifecycleMatching:

    def test_new_grant_triggers_matching(self, client, alice_token, seed_data):
        """Creating a grant should auto-create GrantMatch records for matching profiles."""
        # 1. Verify Alice has a profile (from seed data)
        profiles = seed_data.get("profiles", {})
        assert "alice_ai" in profiles

        # 2. Create a grant that matches Alice's AI profile
        resp = client.post("/grants", json={
            "title": "NSF Deep Learning Initiative",
            "agency": "NSF",
            "url": "https://nsf.gov/deep-learning",
            "description": "Research in deep learning, transformer models, and NLP applications",
            "amount_min": 100000,
            "amount_max": 300000,
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201
        grant_id = resp.json()["id"]

        # 3. Wait for async lifecycle handler to complete
        # In test environment, asyncio tasks run on the event loop.
        # The TestClient handles this, but we may need a brief delay.
        time.sleep(0.5)

        # 4. Check that GrantMatch records were created
        matches_resp = client.get("/grant_matches", headers=auth_header(alice_token))
        assert matches_resp.status_code == 200
        matches = matches_resp.json()
        if isinstance(matches, dict):
            matches = matches.get("data", [])

        # Find matches for our new grant
        new_matches = [m for m in matches if m["grant_id"] == grant_id]
        assert len(new_matches) >= 1, "Lifecycle matching should have created at least one GrantMatch"
        assert new_matches[0]["score"] > 0
        assert len(new_matches[0]["reasons"]) > 0

    def test_non_matching_grant_no_matches(self, client, alice_token, seed_data):
        """A grant with no keyword overlap should not create GrantMatch records."""
        resp = client.post("/grants", json={
            "title": "Maritime Vessel Inspection Program",
            "agency": "USCG",
            "url": "https://uscg.gov/vessel-inspection",
            "description": "Coast guard protocols for vessel safety inspection and certification.",
        }, headers=auth_header(alice_token))
        assert resp.status_code == 201
        grant_id = resp.json()["id"]

        time.sleep(0.5)

        matches_resp = client.get("/grant_matches", headers=auth_header(alice_token))
        matches = matches_resp.json()
        if isinstance(matches, dict):
            matches = matches.get("data", [])
        new_matches = [m for m in matches if m["grant_id"] == grant_id]
        assert len(new_matches) == 0, "Non-matching grant should not create GrantMatch records"
```

**Note on async testing:** The `TestClient` from FastAPI/Starlette runs async code synchronously. However, `asyncio.create_task()` in `_publish_lifecycle` schedules the task on the event loop. In the test environment with `TestClient`, these tasks may or may not execute before the next HTTP call. If `time.sleep(0.5)` is insufficient, we have two alternatives:

- **Alternative A:** Use `httpx.AsyncClient` with `ASGITransport` and explicitly `await asyncio.sleep(0.1)` to let the event loop process pending tasks.
- **Alternative B:** Add a test-only flush mechanism that awaits all pending tasks.

Start with `time.sleep(0.5)` and adjust if flaky. Document the timing sensitivity.

### Task 11: Schema Endpoint Tests
**File:** `/workspace/example_grants/tests/test_schema_endpoints.py` (update existing)
**Dependencies:** Task 6
**Estimate:** 1 hour
**Priority:** P1

Add tests verifying the new models appear in schema endpoints:

| Test | Description |
|------|-------------|
| `test_user_profile_schema` | GET `/UserProfile`, verify properties include research_areas, keywords, agencies, budget_min, budget_max, institution_type |
| `test_grant_match_schema` | GET `/GrantMatch`, verify properties include score, reasons, status, matched_at |
| `test_matcher_tools_schema` | GET `/MatcherTools`, verify methods include score and match_all with correct parameters |
| `test_user_profile_access_in_schema` | Verify schema.access has OWNER rules |

### Task 12: Update conftest.py Seed Data
**File:** `/workspace/example_grants/tests/conftest.py`
**Dependencies:** Task 3, Task 4, Task 5
**Estimate:** 1 hour
**Priority:** P0

Update the conftest to:

1. Import new models: `UserProfile, GrantMatch, MatcherTools`
2. Add `_seed_profiles(users)` function (as described in Task 7a)
3. Add additional test grants that exercise matching (as described in Task 9c)
4. Update `seed_data` fixture to include `profiles` key
5. Ensure new models are registered in `_setup_test_db` (they should be, since `registered_models` is populated by `main.py` import)

### Task 13: Create `matching/` Package Directory
**File:** `/workspace/example_grants/matching/__init__.py`
**Dependencies:** None
**Estimate:** 5 minutes
**Priority:** P0 (required by Task 1)

Create the matching package directory and empty `__init__.py`. This is a clean separation: matching logic lives in its own package, not in the models package.

```
example_grants/
  matching/
    __init__.py
    keyword_score.py     # Task 1
  models/
    user_profile.py      # Task 3
    grant_match.py       # Task 4
    matcher_tools.py     # Task 5
    ...
```

---

## 4. Task Dependency Graph

```
Task 13 (create matching/ dir) ─────┐
                                     v
Task 1 (keyword_score function) ────────┬──> Task 2 (unit tests)
                                        │
Task 3 (UserProfile model)  ────────────┤
                                        │
Task 4 (GrantMatch model)  ─────────────┤
                                        │
                                        v
Task 5 (MatcherTools actor) ────────────┤
                                        │
                                        v
Task 6 (main.py + __init__.py) ─────────┤
                                        │
Task 12 (conftest.py seeds) ────────────┤
                                        │
                  ┌─────────────────────┼─────────────────────┐
                  v                     v                     v
Task 7            Task 8              Task 9                Task 10
(UserProfile      (GrantMatch         (Matcher              (Lifecycle
 CRUD tests)       CRUD tests)         endpoint tests)       matching tests)
                                        │
                                        v
                                   Task 11
                                   (Schema tests)
```

**Parallelism opportunities:**
- Tasks 1, 3, 4, 13 can all run in parallel (day 1-2)
- Task 2 can start as soon as Task 1 is done
- Task 5 starts after 1, 3, 4 are done
- Tasks 7, 8, 9, 10, 11 can all run in parallel once Task 6 and 12 are done

---

## 5. Detailed JSON Field Serialization Pattern

This is the most critical implementation detail to get right. Three models use JSON fields; all follow the identical pattern established by `AgentActor`.

### The Problem

SQLite has no native list/array type. Python `list` objects cannot be bound to SQLite parameters directly. Pydantic's `list` type annotation creates a `TEXT` column in SQLite, but `sqlite3.InterfaceError: Error binding parameter` occurs when trying to INSERT/UPDATE a Python list into a TEXT column.

### The Solution (3-part pattern)

**Part 1: `_JSON_FIELDS` tuple** -- declares which fields need serialization

```python
_JSON_FIELDS = ('research_areas', 'keywords', 'agencies')  # UserProfile
_JSON_FIELDS = ('reasons',)                                  # GrantMatch
```

**Part 2: `_storage_dict()` override** -- serializes on write

```python
def _storage_dict(self, exclude_unset: bool = True) -> dict:
    d = super()._storage_dict(exclude_unset=exclude_unset)
    for field in _JSON_FIELDS:
        if field in d and not isinstance(d[field], str):
            d[field] = json.dumps(d[field], default=str)
    return d
```

This intercepts the dict before it reaches `sqlite_storage.py`. The `isinstance(d[field], str)` guard prevents double-serialization.

**Part 3: `@model_validator(mode='before')` classmethod** -- deserializes on read

```python
@model_validator(mode='before')
@classmethod
def _deserialize_json_fields(cls, data):
    if isinstance(data, dict):
        for field in _JSON_FIELDS:
            val = data.get(field)
            if isinstance(val, str):
                try:
                    data[field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
    return data
```

This intercepts the dict from SQLite before Pydantic validation. The `isinstance(val, str)` guard ensures it only deserializes when the value is a JSON string (from DB), not when it's already a Python list (from API input).

**Part 4 (bonus): `update()` classmethod override** -- serializes on partial update

```python
@classmethod
def update(cls, id, data):
    from pydantic import BaseModel
    if isinstance(data, BaseModel):
        data_dict = data.model_dump(exclude_unset=True)
    elif isinstance(data, dict):
        data_dict = dict(data)
    else:
        data_dict = data
    for field in _JSON_FIELDS:
        if field in data_dict and not isinstance(data_dict[field], str):
            data_dict[field] = json.dumps(data_dict[field], default=str)
    return super().update(id, data_dict)
```

This handles `PUT /user_profiles/{id}` which calls `cls.update(id, data_dict)` directly with a dict (not going through `_storage_dict()`).

### Data Flow

```
API Input (JSON)          DB Row (SQLite TEXT)        Python Object (Pydantic)
───────────────           ──────────────────          ─────────────────────────
{"keywords": ["AI"]}  →  keywords='["AI"]'  →       keywords=["AI"]
                          (via _storage_dict)          (via @model_validator)

PUT {"keywords": ["ML"]} → keywords='["ML"]'  →     keywords=["ML"]
                            (via update())             (via @model_validator)
```

---

## 6. Lifecycle Subscriber Wiring -- Deep Dive

### How It Works End-to-End

```
1. Grant.create(grant)
   └─ handler_crud() in ActorModel
       └─ cls._publish_lifecycle('after_create', result.model_response())

2. _publish_lifecycle('after_create', {...})
   └─ for subscriber_addr in cls._subscribers:  # ['matcher']
       └─ asyncio.create_task(cls.send(TX(
              name='LIFECYCLE',
              source='grants',        # Grant.__addr__ = Grant.__tablename__
              target='matcher',        # subscriber_addr
              data={'event': 'after_create', 'entity': {...}},
          )))

3. Actor.send(tx) on Grant class
   └─ children check: 'matcher' not in Grant.__children__
   └─ bubble to parent (Matrix)
       └─ tx.source = 'grants/grants'  # prefixed
       └─ matrix.inbox(tx)

4. Matrix.inbox(tx)
   └─ target_root = 'matcher'
   └─ 'matcher' in matrix._children  ✓  (auto-registered by ActorMeta)
   └─ await MatcherTools.inbox(tx)

5. MatcherTools.inbox(tx)
   └─ interceptors: none
   └─ await MatcherTools.handler(tx)

6. MatcherTools.handler(tx)  [ActorModel.handler]
   └─ handler_crud: 'LIFECYCLE' not in _CRUD_OPS → _NOT_HANDLED
   └─ generic fallback: getattr(MatcherTools, 'LIFECYCLE', None) → bound method
   └─ not is_exposed (no __endpoint__) → call as (data, tx) signature
   └─ MatcherTools.LIFECYCLE(data={'event': 'after_create', 'entity': {...}}, tx=tx)

7. MatcherTools.LIFECYCLE(data, tx)
   └─ event == 'after_create' → proceed
   └─ grant_id from data['entity']['id']
   └─ Grant.get(grant_id) → grant instance
   └─ UserProfile.list() → all profiles
   └─ for each profile: keyword_score(profile, grant)
   └─ if score >= 30: GrantMatch.create(...)
```

### Key Observations

1. **Source address prefixing:** When `Grant.send()` bubbles to Matrix, it prefixes `tx.source` with `'grants/'`. The MatcherTools LIFECYCLE handler does NOT use `tx.source` for anything, so this is harmless. But be aware of it when debugging TX routing.

2. **LIFECYCLE is not an `@expose_route` method.** It has no `__endpoint__` attribute. This means:
   - It does NOT appear in the schema's `methods` section (no button in the UI)
   - It is NOT accessible via HTTP (no route is generated)
   - It follows the non-exposed `(data, tx)` signature convention
   - It gets dispatched via the `else` branch in `ActorModel.handler()`

3. **Fire-and-forget semantics.** `asyncio.create_task()` means the HTTP response for the Grant creation returns before the lifecycle handler finishes (or even starts). This is correct for the reactive matching use case -- the user doesn't need to wait for all profiles to be scored before getting a 201 response.

4. **Error isolation.** If the LIFECYCLE handler raises an exception, it's caught by the generic handler's try/except, which sends an error TX. Since the lifecycle TX was fire-and-forget, this error TX has nowhere meaningful to go (source is `'grants/grants'`). The error is logged but does not affect the original Grant creation.

### Wiring in main.py

```python
# After create_app() returns:
Grant._subscribers.append('matcher')
```

This is a ClassVar mutation on the Grant class. It must happen AFTER `create_app()` because:
- `create_app()` imports and registers all models
- ActorMeta auto-registers MatcherTools with Matrix under addr 'matcher'
- Only then is 'matcher' a valid routing target

It must happen BEFORE any grants are created, which is always true since the server hasn't started yet.

**Note:** If using WebSocket bridge (`ws=True`), `create_app()` already appends `'ws'` to all ActorModel `_subscribers` lists. Our `'matcher'` append happens after, so the list will be `['ws', 'matcher']` -- both subscribers receive the same LIFECYCLE TX.

---

## 7. Matching Algorithm Specification

### Input

```
profile: {
    keywords: ["deep learning", "transformer"],
    research_areas: ["machine learning", "NLP"],
    agencies: ["NSF", "DARPA"],
    institution_type: "university",
    budget_min: 50000,
    budget_max: 500000,
}

grant: {
    title: "NSF AI Research Initiative",
    description: "Deep learning and transformer architectures for NLP",
    agency: "NSF",
    amount_min: 100000,
    amount_max: 400000,
}
```

### Scoring Calculation

```
Step 1: Keyword overlap (max 50 pts)
  profile_terms = {"deep learning", "transformer", "machine learning", "nlp"}  (4 terms)
  grant_text = "nsf ai research initiative deep learning and transformer architectures for nlp"
  matches = {"deep learning", "transformer", "nlp"}  (3 of 4)
  keyword_pts = 3/4 * 50 = 37.5

Step 2: Agency match (max 20 pts)
  profile_agencies = ["nsf", "darpa"]
  grant_agency = "nsf"
  "nsf" in ["nsf", "darpa"] → True
  agency_pts = 20

Step 3: Budget range (max 15 pts)
  profile_budget_min=50000, grant_amount_max=400000: 400000 >= 50000 → +7.5
  profile_budget_max=500000, grant_amount_min=100000: 100000 <= 500000 → +7.5
  budget_pts = 15

Step 4: Institution type (max 15 pts)
  institution_type = "university"
  type_terms = ["university", "academic", "research institution", "higher education"]
  grant_text contains "research" but not "research institution" specifically
  (substring match: "research institution" is NOT in the grant text as a substring)
  institution_pts = 0
  (Note: this is conservative. "university" itself is not in the grant text either.)

Total: 37.5 + 20 + 15 + 0 = 72.5
Reasons: ["Keywords: deep learning, nlp, transformer (3/4 matched)",
          "Preferred agency: NSF", "Within budget range"]
```

### Threshold

`MATCH_THRESHOLD = 30` -- only matches with score >= 30 create GrantMatch records.

**Rationale:** A score of 30 means at least one strong dimension matched (e.g., keyword overlap > 60% alone, or moderate keyword overlap + agency match). Below 30, the match is noise.

**Configurability:** The threshold is a module-level constant in `keyword_score.py`, exported and used by MatcherTools. In a future sprint, this could become a per-profile field on UserProfile.

---

## 8. File Manifest

### New Files

| File | Type | Description |
|------|------|-------------|
| `example_grants/matching/__init__.py` | Package init | Empty |
| `example_grants/matching/keyword_score.py` | Pure function | Scoring algorithm |
| `example_grants/models/user_profile.py` | Model | UserProfile ActorModel |
| `example_grants/models/grant_match.py` | Model | GrantMatch ActorModel |
| `example_grants/models/matcher_tools.py` | Actor | MatcherTools (non-storable) |
| `example_grants/tests/test_keyword_score.py` | Unit tests | keyword_score() tests |
| `example_grants/tests/test_user_profile_crud.py` | Integration tests | UserProfile CRUD |
| `example_grants/tests/test_grant_match_crud.py` | Integration tests | GrantMatch CRUD |
| `example_grants/tests/test_matcher.py` | Integration tests | MatcherTools endpoints |
| `example_grants/tests/test_lifecycle_matching.py` | Integration tests | Reactive matching via lifecycle |

### Modified Files

| File | Changes |
|------|---------|
| `example_grants/models/__init__.py` | Add UserProfile, GrantMatch, MatcherTools imports/exports |
| `example_grants/main.py` | Add new models to create_app(), wire Grant._subscribers |
| `example_grants/tests/conftest.py` | Add new model imports, _seed_profiles(), additional test grants |
| `example_grants/tests/test_schema_endpoints.py` | Add tests for new model schemas |

### Unchanged Files

| File | Why unchanged |
|------|---------------|
| `src/pybend/core/models/actor_model.py` | Existing _publish_lifecycle + _subscribers works as-is |
| `src/pybend/core/actors/actor.py` | No framework changes needed |
| `src/pybend/core/actors/matrix.py` | Routing works as-is |
| `src/pybend/core/models/proto_model.py` | No changes needed |
| `src/pybend/core/authorize/rules.py` | OWNER, AUTHENTICATED, ROLE all work as-is |
| `example_grants/models/grant.py` | Grant model unchanged -- subscriber wiring is external |
| `example_grants/models/user.py` | User model unchanged -- no ListRef fields added |
| All frontend files | Schema-driven rendering handles new models automatically |

---

## 9. Time Estimates and Schedule

### Week 1 (Days 1-5)

| Day | Tasks | Hours | Focus |
|-----|-------|-------|-------|
| Day 1 | Task 13, Task 1, Task 3, Task 4 | 6 | Create matching package, keyword_score function, UserProfile model, GrantMatch model |
| Day 2 | Task 2, Task 5 | 6 | Unit tests for keyword_score, MatcherTools actor |
| Day 3 | Task 6, Task 12 | 2 | Wire main.py, update conftest.py seeds |
| Day 3 | Task 7 | 2 | UserProfile CRUD integration tests |
| Day 4 | Task 8, Task 9 | 4.5 | GrantMatch CRUD tests, Matcher endpoint tests |
| Day 5 | Task 10, Task 11 | 4 | Lifecycle matching tests, Schema endpoint tests |

**Week 1 total: ~24.5 hours**
**Week 1 deliverable:** All models, matching function, MatcherTools actor, and subscriber wiring are complete and tested.

### Week 2 (Days 6-10)

| Day | Focus | Hours |
|-----|-------|-------|
| Day 6-7 | Fix test failures, edge cases, async timing issues | 8 |
| Day 8 | Manual testing: start server, create profiles via UI, test matching flow end-to-end | 4 |
| Day 9 | Polish: error messages, logging, edge case handling (empty lists, null fields, deleted grants) | 4 |
| Day 10 | Documentation updates: CLAUDE.md architecture section, test run verification | 4 |

**Week 2 total: ~20 hours**
**Week 2 deliverable:** Sprint complete. All tests green. Manual verification done. Documentation updated.

**Total estimated hours: ~44.5 hours**

---

## 10. Risk Mitigation

### Risk 1: Async Lifecycle Timing in Tests
**Risk:** `asyncio.create_task()` in `_publish_lifecycle` may not complete before the next HTTP call in tests.
**Mitigation:** Start with `time.sleep(0.5)`. If flaky, switch to `httpx.AsyncClient` with `ASGITransport` and explicit `await asyncio.sleep(0.1)`. Document timing sensitivity in test comments.

### Risk 2: ClassVar _subscribers Shared Across Tests
**Risk:** `ActorModel._subscribers` is a ClassVar. Appending 'matcher' in main.py affects all test sessions.
**Mitigation:** The conftest already imports `from main import app`, which triggers the main.py execution including the subscriber wiring. This is actually correct -- the tests should exercise the full wiring. If isolation is needed for specific tests, save/restore `Grant._subscribers` in a fixture.

### Risk 3: SQLite JSON Field Double-Serialization
**Risk:** If `_storage_dict()` is called when the field is already a JSON string (e.g., on update after a read), it would double-serialize: `'"[1,2,3]"'`.
**Mitigation:** The `isinstance(d[field], str)` guard in `_storage_dict()` prevents this. Same pattern proven in AgentActor since Sprint 1.

### Risk 4: Owner Resolution with FK Hydration
**Risk:** `profile.user_owner` might be an href string (`"http://localhost:5000/users/3"`) instead of an integer, depending on whether FK hydration has run.
**Mitigation:** MatcherTools explicitly handles both cases: `hasattr(owner_val, 'id')`, string with `/`, or plain int. Same resolution logic used by `_Owner.evaluate()` in authorize/rules.py.

### Risk 5: Large Grant Lists in match_all
**Risk:** `Grant.list()` without pagination returns all grants. For 10K+ grants, this is slow.
**Mitigation:** For Sprint 3 scope (< 1000 grants), this is fine. Note in code comments that pagination/batching should be added when the grant corpus exceeds 5000. The matching function itself is O(n*m) where n=grants, m=profile_terms -- fast for keyword matching, needs optimization for TF-IDF/embeddings.

---

## 11. Definition of Done

- [ ] `keyword_score()` function passes all 15+ unit tests
- [ ] UserProfile model: create, list (OWNER-filtered), get, update, delete all work via API
- [ ] GrantMatch model: same CRUD operations via API
- [ ] `POST /matcher/score` returns correct scores for matching and non-matching grants
- [ ] `POST /matcher/match_all` creates GrantMatch records for scores >= threshold
- [ ] `POST /grants` (creating a grant) triggers lifecycle-driven matching against all profiles
- [ ] JSON list fields round-trip correctly through SQLite (create, read, update)
- [ ] Schema endpoints return correct properties, methods, and access rules for all new models
- [ ] All integration tests pass: `python3 -m pytest example_grants/tests/ -v`
- [ ] Manual verification: UI renders UserProfile and GrantMatch with zero frontend code
- [ ] CLAUDE.md updated with new model paths and matching module documentation
- [ ] No framework files (`src/pybend/core/`) were modified

---

## 12. Post-Sprint Notes

### What This Sprint Enables (Sprint 4+)

1. **Notification model** (Sprint 4) -- GrantMatch creation is the trigger event. When MatcherTools.LIFECYCLE creates a high-score match, it can also create a Notification record and/or push via WebSocket.

2. **TF-IDF upgrade** (Sprint 5+) -- Replace `from matching.keyword_score import keyword_score` with `from matching.tfidf_score import tfidf_score` in MatcherTools. One import change, zero model changes. The scoring interface is identical.

3. **Score widget** (Sprint 4) -- A frontend widget that renders `score` fields as colored progress bars (red < 30, yellow 30-60, green > 60). Register via `registerWidget('score', new ScoreWidget())` in JS.

4. **Saved searches** (Sprint 4) -- SavedSearch model with JSON filters field (same `_JSON_FIELDS` pattern) and an AlertRunner actor that subscribes to Grant.LIFECYCLE events to check immediate-frequency searches.

### Architectural Invariants Preserved

- **The model is the app.** Three new Python models + one scoring function = working full-stack feature.
- **Zero frontend code.** Schema-driven rendering handles everything.
- **Backend is authoritative.** Access rules, field definitions, and UI hints all live in model definitions.
- **Transparent, not magical.** Every step from Grant creation to GrantMatch record is traceable through `_publish_lifecycle` -> `TX` -> `Matrix.inbox` -> `MatcherTools.LIFECYCLE`.
- **No framework modifications.** All new code lives in `example_grants/`. The framework's existing lifecycle/subscriber/actor infrastructure works as designed.
