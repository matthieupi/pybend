# Fork B: Product/Retention Path -- Notifications + Saved Searches

**Branch:** `v0.9` (continues from Sprints 1-3 completion)
**Duration:** ~3 weeks (15 working days)
**Prerequisites:** Safety, Observability, StatusWidget, Grant Detail, GrantsGovAPI, UserProfile, GrantMatch, MatcherTools with lifecycle subscriber wiring -- all complete.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Sprint 4: Notification Model + In-App Notifications (Days 1-5)](#2-sprint-4-notification-model--in-app-notifications-days-1-5)
3. [Sprint 5: NotificationTools + SavedSearch + AlertRunner (Days 6-10)](#3-sprint-5-notificationtools--savedsearch--alertrunner-days-6-10)
4. [Sprint 6: NotificationPrefs + Integration Wiring + Polish (Days 11-15)](#4-sprint-6-notificationprefs--integration-wiring--polish-days-11-15)
5. [WebSocket Notification Targeting -- Deep Dive](#5-websocket-notification-targeting----deep-dive)
6. [Saved Search Execution -- Deep Dive](#6-saved-search-execution----deep-dive)
7. [Email Delivery -- Deep Dive](#7-email-delivery----deep-dive)
8. [Subscriber Chain Architecture](#8-subscriber-chain-architecture)
9. [Frontend Notification Badge](#9-frontend-notification-badge)
10. [Test Strategy](#10-test-strategy)
11. [New Dependencies](#11-new-dependencies)
12. [Risk Register](#12-risk-register)

---

## 1. Architecture Overview

### Event Flow After Fork B Completion

```
[Grant Scanner Agent]
    |
    | creates Grant via grants_create tool
    v
[Grant ActorModel]
    |
    | _publish_lifecycle('after_create', grant_data)
    |
    +---> [MatcherTools]           (existing subscriber from Sprint 3)
    |         score all UserProfiles
    |         create GrantMatch records
    |         |
    |         | GrantMatch._publish_lifecycle('after_create', match_data)
    |         |
    |         +---> [notification_creator]  (new subscriber)
    |                   check NotificationPrefs for user
    |                   create Notification record
    |                   |
    |                   | Notification._publish_lifecycle('after_create', notif_data)
    |                   |
    |                   +---> [ws] NetworkWebSocket  (user-targeted push)
    |                   +---> [notifier] NotificationTools (email/webhook dispatch)
    |
    +---> [alert_runner] AlertRunner  (new subscriber)
    |         check immediate-frequency SavedSearches
    |         diff results against last_result_ids
    |         create Notifications for new matches
    |
    +---> [ws] NetworkWebSocket    (existing subscriber -- broadcast)
              broadcast CREATE event to all clients
```

### New Models

| Model | Storable | Owner-Scoped | JSON Fields |
|-------|----------|--------------|-------------|
| `Notification` | Yes | Yes (`user_owner`) | -- |
| `SavedSearch` | Yes | Yes (`user_owner`) | `filters`, `last_result_ids` |
| `NotificationPrefs` | Yes | Yes (`user_owner`) | -- |

### New Actors (Non-Storable)

| Actor | `__tablename__` | Purpose |
|-------|-----------------|---------|
| `NotificationTools` | `notifier` | Email/webhook delivery |
| `AlertRunner` | `alert_runner` | Saved search execution + lifecycle reaction |

### Join Models

| Parent | Child | Route Pattern |
|--------|-------|---------------|
| `User` | `Notification` | `/users/{id}/notifications` |

---

## 2. Sprint 4: Notification Model + In-App Notifications (Days 1-5)

### Task 4.1: Notification Model (Day 1)

**File:** `/workspace/example_grants/models/notification.py`

**Dependencies:** None (Sprint 3 complete)

**Time estimate:** 4 hours

**Implementation:**

```python
from __future__ import annotations
from typing import ClassVar, Optional
from pydantic import Field

from pybend.core.models.actor_model import ActorModel
from pybend.core.authorize import OWNER, ROLE, AUTHENTICATED
from pybend.core.widgets import TextareaField
from models.user import User


class Notification(ActorModel):
    """A notification for a user."""

    __tablename__: ClassVar[str] = 'notifications'
    __storable__: ClassVar[bool] = True
    __owner_field__: ClassVar[str] = 'user_owner'
    __protected_fields__: ClassVar[set] = {'user_owner'}
    __access__: ClassVar[dict] = {
        'read': OWNER,
        'create': AUTHENTICATED,
        'update': OWNER,       # mark as read
        'delete': OWNER,
    }
    __ui__: ClassVar[dict] = {
        'field_order': ['title', 'message', 'type', 'read', 'link'],
    }

    user_id: int = Field(description="Target user ID")
    type: str = Field(default='match',
                      description="match | deadline | digest | search_alert | system")
    channel: str = Field(default='in_app',
                         description="in_app | email | webhook",
                         json_schema_extra={'ui': {'display': False}})
    title: str = Field(max_length=200)
    message: TextareaField = Field(default='')
    read: bool = Field(default=False)
    link: Optional[str] = Field(default=None,
                                description="Deep link, e.g. #grants/42")
    user_owner: User = Field(default=None,
                             json_schema_extra={'access': {'view': 'owner', 'edit': 'none'}})
```

**Key decisions:**
- `user_id` is the target user (an integer, used for querying). `user_owner` is the ABAC field (used by OWNER rule). They will hold the same value -- `user_owner` is set as a protected field, auto-injected by the route layer from the JWT.
- `channel` is display-hidden. The delivery channel is determined at creation time; the user sees the notification regardless of how it was delivered.
- `link` uses a hash-fragment format (`#grants/42`) consistent with the frontend's hash-based router.

**Steps:**
1. Create `/workspace/example_grants/models/notification.py` with the model above
2. Add `Notification` to `/workspace/example_grants/models/__init__.py`
3. Register in `main.py`: add `Notification` to the models list, add `(User, Notification)` to `join_models`
4. Write unit test: model instantiation, `_storage_dict()`, `model_response()` includes `$schema`/`$id`
5. Write integration test: CRUD via API (create, list with OWNER filter, mark as read via update)

**Test file:** `/workspace/example_grants/tests/test_notification_model.py`

---

### Task 4.2: User-Notification Join Model (Day 1)

**File:** `/workspace/example_grants/main.py` (modification)

**Dependencies:** Task 4.1

**Time estimate:** 1 hour

**Implementation:**

In `main.py`, update the `create_app` call:

```python
from models import User, Grant, Source, WebTools, Notification

app = create_app(
    models=[User, Grant, Source, WebTools, AgentTool, AgentActor, Notification],
    join_models=[(AgentActor, AgentTool), (User, Notification)],
    ...
)
```

This generates a `UserNotification` join model with auto-generated `user_id` FK column. The route `/users/{user_id}/notifications` is auto-generated. The `user_id` on `Notification` must match the parent user's ID. The `user_owner` field provides ABAC scoping.

**Verification:** After server restart, `GET /Notification` returns a schema with all fields. `POST /notifications` creates a record. `GET /users/1/notifications` returns the user's notifications.

---

### Task 4.3: WebSocket Notification Targeting (Days 2-3)

**File:** `/workspace/src/pybend/core/api/network_ws.py` (modification)

**Dependencies:** Task 4.1

**Time estimate:** 8 hours (this is the trickiest architectural piece)

**Detailed Design:** See [Section 5: WebSocket Notification Targeting -- Deep Dive](#5-websocket-notification-targeting----deep-dive)

**Summary of changes to `NetworkWebSocket.LIFECYCLE()`:**

The current implementation broadcasts every lifecycle event to every connected client. For notifications, we need **user-targeted delivery**: when a Notification entity is created, only the WebSocket connection belonging to that notification's `user_id` should receive it.

The modification is a targeted filter *before* the broadcast loop. The existing broadcast-to-all behavior is preserved for all other models. The change is ~15 lines in the `LIFECYCLE` method.

**Steps:**
1. Modify `LIFECYCLE()` in `network_ws.py` to detect Notification lifecycle events by checking `tx.source == 'notifications'`
2. For notification events, extract `user_id` from entity data and filter `_connections` to only that user's connections
3. For all other events, preserve existing broadcast-to-all behavior
4. Write integration test with mock WebSocket clients: create a notification, verify only the target user's connection receives it

**Test file:** `/workspace/src/pybend/core/tests/unit/test_ws_notification_targeting.py`

---

### Task 4.4: Notification Lifecycle Subscriber Wiring (Day 3)

**File:** `/workspace/example_grants/main.py` (modification)

**Dependencies:** Tasks 4.1, 4.3

**Time estimate:** 2 hours

**Implementation:**

The `Notification` model needs its lifecycle events broadcast via WebSocket. When `create_app` is called with `routing='actor'`, the framework already appends `'ws'` to every model's `_subscribers` list (see `/workspace/src/pybend/core/app.py` lines 245-247). So `Notification._subscribers` will include `'ws'` automatically.

Verification: After creating a notification via API, the WebSocket `LIFECYCLE` handler fires and routes the event only to the target user's connection.

No explicit wiring needed -- the framework handles this. But we need to confirm that `Notification` is in `registered_models` so the `ws` subscriber is attached.

---

### Task 4.5: Frontend Notification Badge Component (Days 4-5)

**Files:**
- `/workspace/example_grants/static/components/notification-badge.js` (new)
- `/workspace/example_grants/static/index.html` (modification -- add badge to nav)

**Dependencies:** Tasks 4.1, 4.3

**Time estimate:** 8 hours

**Detailed Design:** See [Section 9: Frontend Notification Badge](#9-frontend-notification-badge)

**Summary:**

A minimal custom web component `<notification-badge>` that:
1. On connect, fetches unread notification count via `GET /notifications?limit=1&offset=0` with OWNER filter (response `meta.total` gives unread count, or we use a dedicated count approach)
2. Subscribes to WebSocket lifecycle events from `notifications` source
3. On `CREATE` lifecycle event for current user, increments badge count and shows a toast
4. On click, navigates to `#Notification` (the notification list view)
5. Renders as a bell icon with a red count bubble

**Steps:**
1. Create `notification-badge.js` extending `HTMLElement` (not NTTElement -- this is a UI chrome component, not an entity component)
2. On `connectedCallback`, check if user is authenticated (JWT in localStorage)
3. If authenticated, fetch initial unread count
4. Register a WebSocket message listener for `LIFECYCLE` events from `notifications`
5. Add the component tag to the nav area of `index.html`
6. Style with inline CSS (minimal, self-contained)

**Test approach:** Manual verification in browser. The component is thin enough that integration testing at the API level (Task 4.3 tests) covers the data flow.

---

## 3. Sprint 5: NotificationTools + SavedSearch + AlertRunner (Days 6-10)

### Task 5.1: NotificationTools Actor (Days 6-7)

**File:** `/workspace/example_grants/models/notification_tools.py`

**Dependencies:** Task 4.1 (Notification model exists)

**Time estimate:** 8 hours

**Detailed Design:** See [Section 7: Email Delivery -- Deep Dive](#7-email-delivery----deep-dive)

```python
from __future__ import annotations
import logging
import os
from typing import ClassVar

from pybend.core.models.actor_model import ActorModel
from pybend.core.utils.decorators import expose_route
from pybend.core.authorize import AUTHENTICATED, ROLE
from pybend.core.utils.erroring import MethodError

logger = logging.getLogger('grants.notifier')


class NotificationTools(ActorModel):
    """Notification delivery engine. Sends emails and webhooks."""

    __tablename__: ClassVar[str] = 'notifier'
    __storable__: ClassVar[bool] = False

    @expose_route('/send_email', methods=['POST'], access=AUTHENTICATED)
    async def send_email(self, user_id: int, subject: str, body: str) -> dict:
        """Send an email notification to a user.

        Provider is selected from NOTIFY_EMAIL_PROVIDER env var.
        Defaults to SMTP.
        """
        from models.user import User
        user = User.get(user_id)
        if not user:
            raise MethodError("User not found", 404)

        provider = os.environ.get('NOTIFY_EMAIL_PROVIDER', 'smtp')
        try:
            if provider == 'smtp':
                return await self._send_via_smtp(user.email, subject, body)
            else:
                raise MethodError(f"Unknown email provider: {provider}", 400)
        except Exception as e:
            logger.error("Email delivery failed to %s: %s", user.email, e)
            return {'sent': False, 'error': str(e), 'to': user.email}

    async def _send_via_smtp(self, to: str, subject: str, body: str) -> dict:
        """Send via SMTP using aiosmtplib."""
        import aiosmtplib
        from email.message import EmailMessage

        host = os.environ.get('SMTP_HOST', 'localhost')
        port = int(os.environ.get('SMTP_PORT', '587'))
        user = os.environ.get('SMTP_USER', '')
        password = os.environ.get('SMTP_PASS', '')
        from_addr = os.environ.get('SMTP_FROM', 'grants@example.com')
        use_tls = os.environ.get('SMTP_TLS', 'true').lower() == 'true'

        msg = EmailMessage()
        msg['From'] = from_addr
        msg['To'] = to
        msg['Subject'] = subject
        msg.set_content(body, subtype='html')

        await aiosmtplib.send(
            msg,
            hostname=host,
            port=port,
            username=user or None,
            password=password or None,
            start_tls=use_tls,
        )
        return {'sent': True, 'to': to}

    @expose_route('/send_webhook', methods=['POST'], access=AUTHENTICATED)
    async def send_webhook(self, url: str, payload: dict) -> dict:
        """POST a notification payload to a webhook URL.

        SSRF protection: rejects private/loopback IPs.
        """
        import ipaddress
        from urllib.parse import urlparse

        # SSRF validation
        parsed = urlparse(url)
        hostname = parsed.hostname or ''
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_reserved:
                raise MethodError(f"Webhook URL targets a private address: {hostname}", 400)
        except ValueError:
            pass  # hostname is not an IP -- DNS resolution happens at request time

        if not parsed.scheme or parsed.scheme not in ('http', 'https'):
            raise MethodError("Webhook URL must use http or https", 400)

        import httpx
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)
            return {'status': resp.status_code, 'url': url}
        except Exception as e:
            logger.error("Webhook delivery failed to %s: %s", url, e)
            return {'status': 0, 'url': url, 'error': str(e)}
```

**Steps:**
1. Create `/workspace/example_grants/models/notification_tools.py`
2. Add `NotificationTools` to `models/__init__.py`
3. Register in `main.py` models list
4. Write tests with mock SMTP server (see [Section 10: Test Strategy](#10-test-strategy))

**Test file:** `/workspace/example_grants/tests/test_notification_tools.py`

---

### Task 5.2: Notification Lifecycle Handler on NotificationTools (Day 7)

**File:** `/workspace/example_grants/models/notification_tools.py` (add LIFECYCLE handler)

**Dependencies:** Task 5.1

**Time estimate:** 3 hours

**Implementation:**

Add a `LIFECYCLE` handler to `NotificationTools` that dispatches email/webhook delivery when a Notification is created:

```python
    async def LIFECYCLE(self, data: dict, tx):
        """Handle Notification lifecycle events.

        When a Notification is created, check the user's preferences
        and dispatch delivery via the appropriate channel.
        """
        event = data.get('event', '')
        entity = data.get('entity', {})

        if event != 'after_create':
            return

        # Only handle notifications from the notifications model
        if tx.source != 'notifications':
            return

        user_id = entity.get('user_id')
        if not user_id:
            return

        # Check user preferences (Task 6.1)
        from models.notification_prefs import NotificationPrefs
        try:
            prefs_list = NotificationPrefs.list(
                sql_filter=("user_owner = ?", [user_id]),
                limit=1,
            )
            prefs_data = prefs_list.get('data', []) if isinstance(prefs_list, dict) else prefs_list
            prefs = prefs_data[0] if prefs_data else None
        except Exception:
            prefs = None

        # Email delivery
        if prefs and prefs.email_enabled:
            try:
                await self.send_email(
                    user_id=user_id,
                    subject=entity.get('title', 'New Notification'),
                    body=entity.get('message', ''),
                )
            except Exception as e:
                logger.error("Email delivery failed for user %s: %s", user_id, e)

        # Webhook delivery
        if prefs and prefs.webhook_url:
            try:
                await self.send_webhook(
                    url=str(prefs.webhook_url),
                    payload={
                        'type': entity.get('type', 'system'),
                        'title': entity.get('title', ''),
                        'message': entity.get('message', ''),
                        'link': entity.get('link', ''),
                    },
                )
            except Exception as e:
                logger.error("Webhook delivery failed for user %s: %s", user_id, e)
```

**Subscriber wiring (in main.py):**

```python
# After create_app() -- wire Notification lifecycle to NotificationTools
Notification._subscribers.append('notifier')
```

Note: `'ws'` is already attached by `create_app` with `routing='actor'`. Adding `'notifier'` means Notification creation fires two subscribers: `ws` (in-app push) and `notifier` (email/webhook).

---

### Task 5.3: SavedSearch Model (Day 8)

**File:** `/workspace/example_grants/models/saved_search.py`

**Dependencies:** None (independent of Tasks 5.1-5.2)

**Time estimate:** 6 hours

**Implementation:**

```python
from __future__ import annotations
import json
import logging
from typing import ClassVar, Optional
from pydantic import Field, model_validator

from pybend.core.models.actor_model import ActorModel
from pybend.core.authorize import OWNER, AUTHENTICATED
from pybend.core.widgets import DateTimeField
from models.user import User

logger = logging.getLogger('grants.saved_search')

# Fields stored as JSON TEXT in SQLite (same pattern as AgentActor.constraints)
_JSON_FIELDS = ('filters', 'last_result_ids')


class SavedSearch(ActorModel):
    """A saved search query with optional alert frequency."""

    __tablename__: ClassVar[str] = 'saved_searches'
    __storable__: ClassVar[bool] = True
    __owner_field__: ClassVar[str] = 'user_owner'
    __protected_fields__: ClassVar[set] = {'user_owner'}
    __access__: ClassVar[dict] = {
        'read': OWNER,
        'create': AUTHENTICATED,
        'update': OWNER,
        'delete': OWNER,
    }

    name: str = Field(min_length=1, max_length=200,
                      description="e.g. 'NSF AI Grants > $100K'")
    filters: dict = Field(default={},
                          description="Query params: agency, keywords, amount_min, status, etc.")
    frequency: str = Field(default='daily',
                           description="none | immediate | daily | weekly")
    last_run_at: Optional[DateTimeField] = Field(default=None)
    last_result_ids: list = Field(default=[],
                                  description="Grant IDs from last execution")
    user_owner: User = Field(default=None,
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
        """Serialize dict/list fields to JSON strings for SQLite storage."""
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

**Key decisions:**
- `filters` and `last_result_ids` use the identical JSON serialization pattern as `AgentActor.constraints` (see `/workspace/src/pybend/core/agents/actor.py` lines 39-102). This is a proven pattern in the codebase.
- `last_run_at` uses `DateTimeField` (datetime widget) for proper display.
- `frequency` is a plain string enum. We could use a Python `Enum`, but string fields are simpler for SQLite and consistent with `Grant.status`.

**Steps:**
1. Create `/workspace/example_grants/models/saved_search.py`
2. Add `SavedSearch` to `models/__init__.py`
3. Register in `main.py` models list
4. Write unit test: JSON roundtrip (create with dict `filters`, read back, verify deserialized)
5. Write integration test: CRUD via API with OWNER scoping

**Test file:** `/workspace/example_grants/tests/test_saved_search.py`

---

### Task 5.4: AlertRunner Actor (Days 9-10)

**File:** `/workspace/example_grants/models/alert_runner.py`

**Dependencies:** Tasks 4.1 (Notification), 5.3 (SavedSearch)

**Time estimate:** 10 hours

**Detailed Design:** See [Section 6: Saved Search Execution -- Deep Dive](#6-saved-search-execution----deep-dive)

```python
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import ClassVar

from pybend.core.models.actor_model import ActorModel
from pybend.core.utils.decorators import expose_route
from pybend.core.authorize import ROLE, AUTHENTICATED
from pybend.core.actors.tx import TX

logger = logging.getLogger('grants.alert_runner')


class AlertRunner(ActorModel):
    """Executes saved searches and creates notifications for new results.

    Two modes:
    1. Reactive: handles LIFECYCLE events from Grant to check
       immediate-frequency saved searches against new grants.
    2. Periodic: run_alerts() executes all due periodic saved searches,
       diffs results, and creates notifications.
    """

    __tablename__: ClassVar[str] = 'alert_runner'
    __storable__: ClassVar[bool] = False

    # ── Reactive mode: lifecycle event handler ──

    async def LIFECYCLE(self, data: dict, tx: TX):
        """Handle Grant lifecycle events.

        On after_create: check all immediate-frequency saved searches
        against the new grant. If the grant matches, create a notification.
        """
        event = data.get('event', '')
        entity = data.get('entity', {})

        if event != 'after_create':
            return

        # Only react to Grant creation events
        if tx.source != 'grants':
            return

        from models.saved_search import SavedSearch
        from models.notification import Notification

        # Fetch all saved searches with immediate frequency
        all_searches = SavedSearch.list(limit=500)
        searches = all_searches.get('data', []) if isinstance(all_searches, dict) else all_searches

        for search in searches:
            if search.frequency != 'immediate':
                continue
            if self._grant_matches_filters(entity, search.filters):
                # Create notification for the search owner
                try:
                    Notification.create(Notification(
                        user_id=search.user_owner if isinstance(search.user_owner, int) else self._extract_owner_id(search),
                        type='search_alert',
                        title=f"New grant matches: {search.name}",
                        message=f"Grant '{entity.get('title', 'Unknown')}' matches your saved search.",
                        link=f"#grants/{entity.get('id', '')}",
                        user_owner=search.user_owner,
                    ))
                except Exception as e:
                    logger.error("Failed to create notification for search %s: %s", search.name, e)

    # ── Periodic mode: run all due searches ──

    @expose_route('/run_alerts', methods=['POST'], access=ROLE('admin'))
    def run_alerts(self) -> dict:
        """Execute all due saved searches and notify on new results.

        Call this from a cron job or scheduler:
            POST /alert_runner/run_alerts
        """
        from models.saved_search import SavedSearch
        from models.notification import Notification
        from models.grant import Grant

        all_searches = SavedSearch.list(limit=500)
        searches = all_searches.get('data', []) if isinstance(all_searches, dict) else all_searches
        now = datetime.utcnow()
        results = []

        for search in searches:
            if search.frequency == 'none' or search.frequency == 'immediate':
                continue

            # Check if due
            if search.last_run_at:
                last_run = search.last_run_at
                if isinstance(last_run, str):
                    try:
                        last_run = datetime.fromisoformat(last_run)
                    except ValueError:
                        last_run = None

                if last_run:
                    freq_hours = {'daily': 24, 'weekly': 168}.get(search.frequency, 24)
                    if (now - last_run).total_seconds() < freq_hours * 3600:
                        continue

            # Execute search
            grants = self._execute_search(search.filters)
            current_ids = set(g.id for g in grants)
            previous_ids = set(search.last_result_ids or [])
            new_ids = current_ids - previous_ids

            if new_ids:
                new_grants = [g for g in grants if g.id in new_ids]
                owner_id = search.user_owner if isinstance(search.user_owner, int) else self._extract_owner_id(search)

                try:
                    Notification.create(Notification(
                        user_id=owner_id,
                        type='search_alert',
                        title=f"{len(new_ids)} new grant(s): {search.name}",
                        message=self._format_new_grants(new_grants),
                        user_owner=search.user_owner,
                    ))
                    results.append({'search': search.name, 'new_count': len(new_ids)})
                except Exception as e:
                    logger.error("Failed to create notification for search %s: %s", search.name, e)

            # Update last run state
            SavedSearch.update(search.id, {
                'last_run_at': now.isoformat(),
                'last_result_ids': list(current_ids),
            })

        return {'processed': len(searches), 'alerts_sent': results}

    # ── Filter matching and search execution helpers ──

    @staticmethod
    def _grant_matches_filters(grant_data: dict, filters: dict) -> bool:
        """Check if a single grant entity dict matches a SavedSearch filter set.

        This is the reactive-mode filter check (in-memory, no DB query).
        """
        if not filters:
            return True

        # Agency filter
        agency = filters.get('agency')
        if agency and grant_data.get('agency', '').lower() != agency.lower():
            return False

        # Status filter
        status = filters.get('status')
        if status and grant_data.get('status', '') != status:
            return False

        # Amount minimum filter
        amount_min = filters.get('amount_min')
        if amount_min is not None:
            grant_max = grant_data.get('amount_max')
            if grant_max is not None and float(grant_max) < float(amount_min):
                return False

        # Keyword filter (any keyword matches title or description)
        keywords = filters.get('keywords', [])
        if keywords:
            text = f"{grant_data.get('title', '')} {grant_data.get('description', '')}".lower()
            if not any(kw.lower() in text for kw in keywords):
                return False

        return True

    @staticmethod
    def _execute_search(filters: dict) -> list:
        """Execute a SavedSearch's filters against the Grant table.

        Translates the filter dict into sql_filter for StorableMixin.list().
        """
        from models.grant import Grant

        where_parts = []
        params = []

        agency = filters.get('agency')
        if agency:
            where_parts.append("agency = ?")
            params.append(agency)

        status = filters.get('status')
        if status:
            where_parts.append("status = ?")
            params.append(status)

        amount_min = filters.get('amount_min')
        if amount_min is not None:
            where_parts.append("amount_max >= ?")
            params.append(float(amount_min))

        amount_max = filters.get('amount_max')
        if amount_max is not None:
            where_parts.append("amount_min <= ?")
            params.append(float(amount_max))

        # Keyword filter: SQLite LIKE for each keyword, OR'd together
        keywords = filters.get('keywords', [])
        if keywords:
            kw_clauses = []
            for kw in keywords:
                kw_clauses.append("(title LIKE ? OR description LIKE ?)")
                params.extend([f"%{kw}%", f"%{kw}%"])
            where_parts.append(f"({' OR '.join(kw_clauses)})")

        sql_filter = None
        if where_parts:
            sql_filter = (" AND ".join(where_parts), params)

        result = Grant.list(sql_filter=sql_filter, limit=200)
        if isinstance(result, dict):
            return result.get('data', [])
        return result

    @staticmethod
    def _format_new_grants(grants: list) -> str:
        """Format a list of grants into a notification message body."""
        lines = []
        for g in grants[:10]:
            title = getattr(g, 'title', 'Unknown')
            agency = getattr(g, 'agency', 'Unknown')
            lines.append(f"- {title} ({agency})")
        if len(grants) > 10:
            lines.append(f"... and {len(grants) - 10} more")
        return '\n'.join(lines)

    @staticmethod
    def _extract_owner_id(search) -> int:
        """Extract integer user ID from user_owner (which may be an href string)."""
        owner = search.user_owner
        if isinstance(owner, int):
            return owner
        if isinstance(owner, str) and '/' in owner:
            try:
                return int(owner.rstrip('/').rsplit('/', 1)[-1])
            except (ValueError, IndexError):
                pass
        return 0
```

**Steps:**
1. Create `/workspace/example_grants/models/alert_runner.py`
2. Add `AlertRunner` to `models/__init__.py`
3. Register in `main.py` models list
4. Wire subscriber: `Grant._subscribers.append('alert_runner')` in `main.py`
5. Write unit tests: `_grant_matches_filters()` with various filter combinations
6. Write unit tests: `_execute_search()` with mock Grant.list
7. Write integration test: create a saved search, create a grant, verify notification created

**Test file:** `/workspace/example_grants/tests/test_alert_runner.py`

---

## 4. Sprint 6: NotificationPrefs + Integration Wiring + Polish (Days 11-15)

### Task 6.1: NotificationPrefs Model (Day 11)

**File:** `/workspace/example_grants/models/notification_prefs.py`

**Dependencies:** None (independent)

**Time estimate:** 4 hours

```python
from __future__ import annotations
from typing import ClassVar, Optional
from pydantic import Field

from pybend.core.models.actor_model import ActorModel
from pybend.core.authorize import OWNER, AUTHENTICATED
from pybend.core.widgets import UrlField
from models.user import User


class NotificationPrefs(ActorModel):
    """User notification preferences."""

    __tablename__: ClassVar[str] = 'notification_prefs'
    __storable__: ClassVar[bool] = True
    __owner_field__: ClassVar[str] = 'user_owner'
    __protected_fields__: ClassVar[set] = {'user_owner'}
    __access__: ClassVar[dict] = {
        'read': OWNER,
        'create': AUTHENTICATED,
        'update': OWNER,
        'delete': OWNER,
    }
    __ui__: ClassVar[dict] = {
        'field_order': ['email_enabled', 'webhook_url', 'frequency', 'min_match_score'],
    }

    email_enabled: bool = Field(default=True,
                                description="Receive email notifications")
    webhook_url: Optional[UrlField] = Field(default=None,
                                             description="Webhook URL for notification delivery")
    frequency: str = Field(default='immediate',
                           description="immediate | daily | weekly")
    min_match_score: float = Field(default=50.0, ge=0, le=100,
                                    description="Only notify for matches above this score")
    user_owner: User = Field(default=None,
                             json_schema_extra={'access': {'view': 'owner', 'edit': 'none'}})
```

**Steps:**
1. Create `/workspace/example_grants/models/notification_prefs.py`
2. Add `NotificationPrefs` to `models/__init__.py`
3. Register in `main.py` models list
4. Write integration test: create prefs, verify OWNER-scoped read

**Test file:** `/workspace/example_grants/tests/test_notification_prefs.py`

---

### Task 6.2: Full Subscriber Chain Wiring (Day 12)

**File:** `/workspace/example_grants/main.py` (modification)

**Dependencies:** Tasks 4.1, 5.1, 5.4, 6.1

**Time estimate:** 4 hours

**Detailed Design:** See [Section 8: Subscriber Chain Architecture](#8-subscriber-chain-architecture)

**Implementation -- final state of `main.py`:**

```python
from models import (
    User, Grant, Source, WebTools,
    Notification, NotificationTools,
    SavedSearch, AlertRunner,
    NotificationPrefs,
)
from pybend.core.agents.actor import AgentActor
from pybend.core.agents.tool_model import AgentTool

app = create_app(
    models=[
        User, Grant, Source, WebTools,
        AgentTool, AgentActor,
        Notification, NotificationTools,
        SavedSearch, AlertRunner,
        NotificationPrefs,
    ],
    join_models=[
        (AgentActor, AgentTool),
        (User, Notification),
    ],
    storage=storage,
    routing='actor',
    ...
)

# ── Subscriber wiring ──
# Grant lifecycle -> alert_runner (check immediate saved searches)
# Grant lifecycle -> matcher (auto-match profiles) -- already wired from Sprint 3
# Grant lifecycle -> ws (broadcast) -- auto-wired by create_app routing='actor'
Grant._subscribers.append('alert_runner')

# GrantMatch lifecycle -> notification_creator logic
# NOTE: GrantMatch._publish_lifecycle fires after match creation.
# We wire this to notifier so it can create Notification records for high-score matches.
# However, GrantMatch lives in the Sprint 3 scope. If GrantMatch._subscribers
# needs a custom handler, we create a small notification_creator actor.
# For simplicity, we handle match->notification in MatcherTools directly
# (MatcherTools already creates GrantMatch records; it can also create Notifications).

# Notification lifecycle -> ws (auto-wired) + notifier (email/webhook)
Notification._subscribers.append('notifier')
```

**Key decision: Where does match-to-notification happen?**

Two options:
1. **MatcherTools creates Notifications directly** (simpler). When MatcherTools creates a GrantMatch with score above threshold, it also creates a Notification record in the same handler. This is one atomic flow.
2. **GrantMatch lifecycle -> separate subscriber** (more decoupled). GrantMatch fires `after_create`, a subscriber checks the score and creates a Notification.

Option 1 is recommended for this fork. It keeps the subscriber chain shorter and avoids a cascade of lifecycle events that could be hard to debug. MatcherTools already has the user context and score. Creating the notification there is 5 extra lines, not a new actor.

**Modification to MatcherTools (Sprint 3 code):**

Add to the `match_all` method, inside the score-check block:

```python
if score >= 30:
    match = GrantMatch(...)
    GrantMatch.create(match)
    matches.append(...)

    # Create notification for high-score matches
    if score >= prefs_min_score:  # from NotificationPrefs
        Notification.create(Notification(
            user_id=user.id,
            type='match',
            title=f"Grant match: {grant.title} ({int(score)}%)",
            message=f"Score: {int(score)}%. Reasons: {', '.join(reasons[:3])}",
            link=f"#grants/{grant.id}",
            user_owner=user.id,
        ))
```

**Steps:**
1. Update `main.py` with full model registration and subscriber wiring
2. Update `models/__init__.py` with all new model imports
3. Update MatcherTools to create Notifications on high-score matches
4. Write end-to-end integration test: create a grant -> verify MatcherTools fires -> verify GrantMatch created -> verify Notification created -> verify WebSocket receives targeted push -> verify email attempted (mocked)

**Test file:** `/workspace/example_grants/tests/test_e2e_notification_chain.py`

---

### Task 6.3: Seed Data for Notifications (Day 13)

**File:** `/workspace/example_grants/seed.py` (modification)

**Dependencies:** Task 6.2

**Time estimate:** 2 hours

**Implementation:**

Add seed data for NotificationPrefs (one per seeded user) and a sample SavedSearch:

```python
# In seed.py, after user creation:

# Notification preferences
NotificationPrefs.create(NotificationPrefs(
    email_enabled=False,  # Disabled for dev (no SMTP in dev)
    frequency='immediate',
    min_match_score=50.0,
    user_owner=alice.id,
))

# Sample saved search
SavedSearch.create(SavedSearch(
    name='NSF AI Grants',
    filters={'agency': 'NSF', 'keywords': ['artificial intelligence', 'machine learning']},
    frequency='daily',
    user_owner=alice.id,
))
```

---

### Task 6.4: Documentation and Cleanup (Days 14-15)

**Files:**
- `/workspace/CLAUDE.md` (update Key Files, patterns)
- `/workspace/example_grants/models/__init__.py` (final `__all__`)
- Run integration test suite: full pass

**Time estimate:** 8 hours

**Steps:**
1. Update `CLAUDE.md` "Key Files by Area" to include new models
2. Update `CLAUDE.md` "Architecture Overview" subscriber chain example
3. Run all integration test suites: `example_grants/tests/`, `example_actor/tests/`
4. Fix any regressions
5. Manual browser testing: create grant, observe notification badge, click through to notification list
6. Verify WebSocket targeting works (two browser tabs, different users)

---

## 5. WebSocket Notification Targeting -- Deep Dive

### Current State

`NetworkWebSocket.LIFECYCLE()` at `/workspace/src/pybend/core/api/network_ws.py` lines 200-236:

```python
async def LIFECYCLE(self, data: dict, tx: TX):
    # ... builds broadcast dict ...
    # Broadcast to ALL connected clients
    for client_id, conn in self._connections.items():
        try:
            await conn['ws'].send_json(broadcast)
        except Exception:
            dead_clients.append(client_id)
```

Every lifecycle event goes to every client. This is correct for general-purpose events (new Grant created = everyone should know). But Notifications are **user-private** -- user A's notification must not be pushed to user B's WebSocket.

### Proposed Change

The modification adds a **pre-filter step** before the broadcast loop. It checks if the lifecycle event source is `'notifications'` and, if so, extracts the `user_id` from the entity data and filters `_connections` to only the matching user(s).

```python
async def LIFECYCLE(self, data: dict, tx: TX):
    event = data.get('event', '')
    entity = data.get('entity', {})

    event_map = {
        'after_create': 'CREATE',
        'after_update': 'UPDATE',
        'after_delete': 'DELETE',
    }
    frontend_name = event_map.get(event, event.upper())

    broadcast = {
        'name': frontend_name,
        'source': tx.source,
        'target': '*',
        'data': entity,
        'meta': {'push': True, 'lifecycle': True},
        'timestamp': tx.timestamp,
    }

    # ── User-targeted notification delivery ──
    # If the source is 'notifications', only send to the target user's connections.
    # All other sources broadcast to all clients (existing behavior).
    if tx.source == 'notifications':
        target_user_id = entity.get('user_id')
        if target_user_id is not None:
            target_connections = {
                cid: conn for cid, conn in self._connections.items()
                if conn['user'].get('id') == target_user_id
            }
        else:
            target_connections = self._connections
    else:
        target_connections = self._connections

    dead_clients = []
    for client_id, conn in target_connections.items():
        try:
            await conn['ws'].send_json(broadcast)
        except Exception:
            dead_clients.append(client_id)

    for client_id in dead_clients:
        self._connections.pop(client_id, None)
        logger.debug("Removed dead WebSocket connection: %s", client_id)
```

### Why This Design

1. **Minimal change.** The modification is 8 lines of filter logic inserted before the existing broadcast loop. The loop itself is unchanged.

2. **Source-based dispatch.** We use `tx.source == 'notifications'` to identify notification events. This is the `__tablename__` of the Notification model, set as `source` in `_publish_lifecycle()`. No new metadata fields or protocol changes.

3. **User matching.** `conn['user'].get('id')` is the decoded JWT user ID, stored at connection time in `create_ws_routes()`. `entity.get('user_id')` is the Notification's target user. Both are integers from the same auth system.

4. **Fallback to broadcast.** If `user_id` is missing from the entity (shouldn't happen, but defensive), we fall back to broadcasting to all. This preserves safety.

5. **No framework mechanism changes.** We do not add a new "targeted push" concept to the actor system. We simply filter the connection list. If future models need targeted delivery (e.g., DMs), the same `tx.source` check pattern extends naturally.

### Edge Cases

- **User has multiple tabs open.** Same user, multiple WebSocket connections, same `user_id` in JWT. All connections receive the notification. Correct behavior.
- **User is not connected.** The notification is created in the DB. When the user connects and fetches their notification list, they see it. The WebSocket push is best-effort.
- **Anonymous connections.** `conn['user']` is `{}` (no JWT at connect). Anonymous connections have no `id`, so they never match a `target_user_id`. Correct.

---

## 6. Saved Search Execution -- Deep Dive

### Filter Dict Structure

The `filters` dict stored in `SavedSearch.filters` mirrors the Grant model's queryable fields:

```python
{
    "agency": "NSF",                              # exact match
    "status": "discovered",                       # exact match
    "amount_min": 100000,                         # amount_max >= this value
    "amount_max": 500000,                         # amount_min <= this value
    "keywords": ["artificial intelligence", "ML"] # LIKE match on title+description
}
```

### Translation to sql_filter

`AlertRunner._execute_search()` translates each filter key into a SQL WHERE clause fragment:

| Filter Key | SQL Fragment | Parameters |
|-----------|-------------|------------|
| `agency` | `agency = ?` | `['NSF']` |
| `status` | `status = ?` | `['discovered']` |
| `amount_min` | `amount_max >= ?` | `[100000]` |
| `amount_max` | `amount_min <= ?` | `[500000]` |
| `keywords` (list) | `(title LIKE ? OR description LIKE ?) OR ...` | `['%AI%', '%AI%', '%ML%', '%ML%']` |

All fragments are AND-joined. The final `sql_filter` tuple is passed to `Grant.list(sql_filter=(...))`, which delegates to `sqlite_storage.py`'s parameterized query execution.

### Result Diffing

The diff algorithm is simple set subtraction:

```
current_ids  = {g.id for g in _execute_search(filters)}    # today's results
previous_ids = set(search.last_result_ids)                  # last run's results
new_ids      = current_ids - previous_ids                   # grants the user hasn't seen
```

After notification creation, `last_result_ids` is updated to `current_ids`. This means:
- Grants that were in the previous run but not the current run are silently dropped (the grant may have been deleted, expired, or no longer matches).
- Grants that appear in consecutive runs are not re-notified.
- If a grant temporarily disappears and reappears, it IS re-notified. This is acceptable for a grant database where reappearance signals something changed.

### Reactive vs Periodic Mode

**Reactive (immediate frequency):** When a new Grant is created, `AlertRunner.LIFECYCLE()` fires. It loads all saved searches with `frequency='immediate'`, and for each, checks the new grant against the filter dict **in memory** (no DB query). This is `_grant_matches_filters(entity_dict, filters)` -- a pure function that evaluates the filter conditions against the grant's data dict. This avoids N+1 DB queries for N saved searches.

**Periodic (daily/weekly frequency):** `AlertRunner.run_alerts()` is called via an external trigger (cron endpoint, admin API call, or a future scheduler). It loads all non-immediate, non-none saved searches, checks if they're due based on `last_run_at` + frequency interval, executes the full DB search, diffs against `last_result_ids`, and creates notifications for new results.

### Why Not Use StorableMixin.list() for Reactive Mode?

The reactive handler receives a single grant entity dict from the lifecycle event. Running `_execute_search()` (which queries the full Grant table) for each immediate saved search would be O(S * N) where S is the number of immediate searches and N is the grant table size. The in-memory filter check is O(S) -- one pass through the searches, constant-time per check. This is the correct design for a lifecycle event handler that fires on every grant creation.

---

## 7. Email Delivery -- Deep Dive

### aiosmtplib Async Sending

`aiosmtplib` is the standard async SMTP library for Python. It provides `aiosmtplib.send()` as a high-level one-shot function that handles connection, TLS, auth, send, and disconnect in one call.

```python
import aiosmtplib
from email.message import EmailMessage

msg = EmailMessage()
msg['From'] = 'grants@example.com'
msg['To'] = 'alice@example.com'
msg['Subject'] = 'New grant match: NSF-2026-AI'
msg.set_content('<h1>New Match</h1><p>Score: 85%</p>', subtype='html')

await aiosmtplib.send(
    msg,
    hostname='smtp.gmail.com',
    port=587,
    username='user@gmail.com',
    password='app-password',
    start_tls=True,
)
```

### Provider Abstraction

`NotificationTools.send_email()` reads `NOTIFY_EMAIL_PROVIDER` from the environment. Initially, only `smtp` is supported. The method structure supports adding `sendgrid` and `mailgun` branches later -- each would be a new `_send_via_*` method. This is additive, not a framework change.

Environment variables for SMTP:

| Variable | Default | Description |
|----------|---------|-------------|
| `NOTIFY_EMAIL_PROVIDER` | `smtp` | Provider to use |
| `SMTP_HOST` | `localhost` | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP server port |
| `SMTP_USER` | `` | SMTP auth username |
| `SMTP_PASS` | `` | SMTP auth password |
| `SMTP_FROM` | `grants@example.com` | From address |
| `SMTP_TLS` | `true` | Enable STARTTLS |

### Error Handling for Failed Deliveries

Email delivery failures are **logged and returned, not raised**. The `send_email` method catches exceptions from `aiosmtplib.send()` and returns `{'sent': False, 'error': '...'}`. This is deliberate:

1. **The notification was already created in the DB.** The user can see it in-app via the WebSocket push or on their next visit. Email is a best-effort secondary channel.
2. **SMTP failures are transient.** Network issues, server overload, rate limiting. Retrying is a future enhancement (add a `delivery_status` field to Notification, run a retry worker).
3. **We don't want SMTP failures to block the lifecycle event chain.** If email delivery raises, it could prevent the next subscriber from processing.

The `LIFECYCLE` handler in NotificationTools wraps `send_email` in try/except for the same reason:

```python
try:
    await self.send_email(...)
except Exception as e:
    logger.error("Email delivery failed for user %s: %s", user_id, e)
```

### SSRF Protection on Webhooks

`send_webhook` validates the URL before making the HTTP request:
1. Reject URLs targeting private, loopback, or reserved IP addresses (`ipaddress.ip_address` check)
2. Reject non-http/https schemes
3. Use a 10-second timeout to prevent slow-server DoS

This does not cover all SSRF vectors (DNS rebinding, etc.), but it handles the common cases. Full SSRF protection would require DNS resolution validation, which can be added later.

---

## 8. Subscriber Chain Architecture

### The Problem: Multiple Subscribers Must Not Interfere

When a Grant is created, its lifecycle event fires to multiple subscribers. After this fork, `Grant._subscribers` will contain:

```python
['matcher', 'alert_runner', 'ws']  # matcher from Sprint 3, alert_runner from this fork, ws auto-wired
```

Each subscriber receives the same TX via `_publish_lifecycle()`:

```python
@classmethod
def _publish_lifecycle(cls, event: str, data: dict):
    for subscriber_addr in cls._subscribers:
        asyncio.create_task(cls.send(TX(
            name='LIFECYCLE',
            source=cls.__addr__,
            target=subscriber_addr,
            data={'event': event, 'entity': data},
        )))
```

Key properties of this design:

1. **Fire-and-forget.** Each subscriber gets its own `asyncio.create_task()`. They run concurrently. One subscriber's failure does not prevent another from executing.

2. **Independent TX copies.** Each `TX(...)` is a new object with its own `uuid`. Subscribers cannot interfere with each other's TX state.

3. **No ordering guarantee.** The `matcher` and `alert_runner` may execute in any order. This is fine because:
   - `matcher` creates GrantMatch records (a separate model)
   - `alert_runner` checks SavedSearch filters (a separate model)
   - Neither reads or writes data that the other depends on

4. **Error isolation.** If `alert_runner.LIFECYCLE()` raises, it is caught by the Actor's `handler()` error handling and logged. The `matcher` and `ws` subscribers are unaffected.

### Full Subscriber Map (After Fork B)

```
Grant._subscribers = ['matcher', 'alert_runner', 'ws']
    matcher       -> MatcherTools.LIFECYCLE: scores profiles, creates GrantMatch
    alert_runner  -> AlertRunner.LIFECYCLE: checks immediate SavedSearches
    ws            -> NetworkWebSocket.LIFECYCLE: broadcasts to all clients

GrantMatch._subscribers = ['ws']
    ws            -> NetworkWebSocket.LIFECYCLE: broadcasts to all clients
    (MatcherTools creates Notifications directly; no separate subscriber needed)

Notification._subscribers = ['ws', 'notifier']
    ws            -> NetworkWebSocket.LIFECYCLE: targeted push to user's connections
    notifier      -> NotificationTools.LIFECYCLE: email/webhook delivery
```

### Why MatcherTools Creates Notifications Directly

Instead of `GrantMatch._subscribers.append('some_notification_creator')`, MatcherTools creates Notification records directly when it creates high-score GrantMatch records. Reasons:

1. **MatcherTools already has the context.** It knows the user, the score, the reasons, and the grant. Passing this through another lifecycle event loses none of it but adds latency and complexity.
2. **Score threshold filtering.** The decision "should this match generate a notification?" depends on `NotificationPrefs.min_match_score` for the user. MatcherTools can query this directly. A lifecycle subscriber would need to query it separately.
3. **Fewer cascading events.** Grant creation already fires 3 subscribers. Adding a 4th subscriber on GrantMatch that creates Notifications that fire 2 more subscribers is a 5-deep cascade. Keeping it to 3 + direct notification creation is simpler to trace.

---

## 9. Frontend Notification Badge

### Component: `<notification-badge>`

A lightweight custom element, NOT an NTTElement. This is UI chrome (navigation bar decoration), not an entity renderer. It does not need schema resolution, DynamicClass integration, or the full NTTElement lifecycle.

**File:** `/workspace/example_grants/static/components/notification-badge.js`

```javascript
/**
 * <notification-badge> — shows unread notification count in the nav bar.
 *
 * Behavior:
 * 1. On connect: fetch unread count from /notifications?limit=0
 * 2. On WS CREATE event from 'notifications' source: increment count, show toast
 * 3. On click: navigate to #Notification (the notification list view)
 * 4. On UPDATE event (read=true): decrement count
 */
class NotificationBadge extends HTMLElement {
    constructor() {
        super();
        this._count = 0;
        this._shadow = this.attachShadow({ mode: 'open' });
    }

    connectedCallback() {
        this._render();
        this._fetchUnreadCount();
        this._subscribeToWebSocket();
    }

    async _fetchUnreadCount() {
        const token = localStorage.getItem('token');
        if (!token) return;

        try {
            // Fetch notifications with limit=1 to get meta.total for unread
            // We filter read=false via sql_filter (OWNER-scoped already)
            const resp = await fetch('/notifications?limit=1&offset=0', {
                headers: { 'x-access-token': token },
            });
            if (!resp.ok) return;
            const data = await resp.json();
            // Count unread: we need a dedicated endpoint or filter
            // For now, use total count as proxy (all notifications for this user)
            // TODO: Add read=false filter when sql_filter supports it in query params
            this._count = data.meta?.total || 0;
            this._render();
        } catch (e) {
            console.warn('NotificationBadge: fetch failed', e);
        }
    }

    _subscribeToWebSocket() {
        // Listen for WebSocket lifecycle pushes
        // The WS connection is managed by Matrix.js -- listen on window for
        // custom events dispatched by the WS message handler.
        window.addEventListener('ws:lifecycle', (e) => {
            const { name, source, data } = e.detail || {};
            if (source !== 'notifications') return;

            if (name === 'CREATE') {
                this._count++;
                this._render();
                this._showToast(data.title || 'New notification');
            } else if (name === 'UPDATE' && data.read === true) {
                this._count = Math.max(0, this._count - 1);
                this._render();
            }
        });
    }

    _showToast(message) {
        // Minimal toast notification (top-right, auto-dismiss)
        const toast = document.createElement('div');
        toast.className = 'notif-toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('show'));
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    _render() {
        this._shadow.innerHTML = `
            <style>
                :host { position: relative; display: inline-block; cursor: pointer; }
                .bell { font-size: 1.4em; padding: 4px 8px; }
                .badge {
                    position: absolute; top: -4px; right: -4px;
                    background: #ef4444; color: white; font-size: 11px;
                    min-width: 18px; height: 18px; line-height: 18px;
                    border-radius: 9px; text-align: center; padding: 0 4px;
                    display: ${this._count > 0 ? 'block' : 'none'};
                }
                .notif-toast {
                    position: fixed; top: 20px; right: 20px; z-index: 9999;
                    background: #1e293b; color: #f8fafc; padding: 12px 20px;
                    border-radius: 8px; font-size: 14px;
                    opacity: 0; transition: opacity 0.3s;
                }
                .notif-toast.show { opacity: 1; }
            </style>
            <span class="bell" title="Notifications">&#128276;</span>
            <span class="badge">${this._count > 99 ? '99+' : this._count}</span>
        `;
        this._shadow.querySelector('.bell')?.addEventListener('click', () => {
            window.location.hash = '#Notification';
        });
    }
}

customElements.define('notification-badge', NotificationBadge);
```

### WebSocket Event Bridge

The frontend's existing WebSocket handler (in Matrix.js or the WS client code) needs to dispatch a `ws:lifecycle` custom event on `window` for lifecycle pushes. If this event dispatch does not already exist, add it to the WS message handler:

```javascript
// In the WS message handler, when receiving a lifecycle push:
if (msg.meta?.lifecycle) {
    window.dispatchEvent(new CustomEvent('ws:lifecycle', { detail: msg }));
}
```

This is a 3-line addition to the existing WS handler. The `notification-badge` component listens for this event.

### Integration with Nav Bar

In `index.html` (or the app's shell HTML), add the badge component to the navigation area:

```html
<nav>
    <!-- existing nav content -->
    <notification-badge></notification-badge>
</nav>
<script type="module" src="/static/components/notification-badge.js"></script>
```

---

## 10. Test Strategy

### Unit Tests

| Test File | What It Tests | Mock Strategy |
|-----------|--------------|---------------|
| `test_notification_model.py` | Notification CRUD, OWNER scoping, `model_response()` | Fixture-based DB |
| `test_saved_search.py` | SavedSearch CRUD, JSON field roundtrip, OWNER scoping | Fixture-based DB |
| `test_notification_prefs.py` | NotificationPrefs CRUD, OWNER scoping | Fixture-based DB |
| `test_alert_runner.py` | `_grant_matches_filters()`, `_execute_search()`, `run_alerts()`, reactive LIFECYCLE | Mock `Grant.list`, `SavedSearch.list`, `Notification.create` |
| `test_ws_notification_targeting.py` | `NetworkWebSocket.LIFECYCLE()` user filtering | Mock `_connections` dict with mock WebSocket objects |

### Integration Tests

| Test File | What It Tests | Setup |
|-----------|--------------|-------|
| `test_notification_api.py` | Full CRUD via HTTP, OWNER filtering, join model `/users/{id}/notifications` | `example_grants` test client |
| `test_e2e_notification_chain.py` | Grant creation -> MatcherTools -> GrantMatch -> Notification -> WebSocket push -> email dispatch | Full app with mocked SMTP |

### Mock SMTP for Email Tests

```python
import asyncio
from unittest.mock import AsyncMock, patch

async def test_email_delivery():
    """Test that NotificationTools.send_email calls aiosmtplib.send."""
    with patch('aiosmtplib.send', new_callable=AsyncMock) as mock_send:
        tools = NotificationTools()
        result = await tools.send_email(
            user_id=1, subject='Test', body='<p>Hello</p>'
        )
        assert result['sent'] is True
        mock_send.assert_called_once()
        # Verify the EmailMessage structure
        msg = mock_send.call_args[0][0]
        assert msg['To'] == 'alice@example.com'
        assert msg['Subject'] == 'Test'
```

### WebSocket Client Testing

```python
async def test_notification_targets_user():
    """Test that notification lifecycle events only reach the target user."""
    from pybend.core.api.network_ws import NetworkWebSocket
    from pybend.core.actors.tx import TX
    from unittest.mock import AsyncMock

    ws = NetworkWebSocket()

    # Two mock connections: user 1 and user 2
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws._connections = {
        'client_1': {'ws': ws1, 'user': {'id': 1, 'email': 'alice@example.com'}},
        'client_2': {'ws': ws2, 'user': {'id': 2, 'email': 'bob@example.com'}},
    }

    # Lifecycle event for user 1's notification
    tx = TX(
        name='LIFECYCLE', source='notifications', target='ws',
        data={'event': 'after_create', 'entity': {'user_id': 1, 'title': 'New match'}},
    )
    await ws.LIFECYCLE(tx.data, tx)

    # User 1 should receive it
    ws1.send_json.assert_called_once()

    # User 2 should NOT receive it
    ws2.send_json.assert_not_called()
```

### Saved Search Execution Tests

```python
def test_grant_matches_filters_keywords():
    """Test keyword filter matching."""
    entity = {'title': 'NSF AI Research Grant', 'description': 'Machine learning...', 'agency': 'NSF'}
    filters = {'keywords': ['AI', 'quantum']}
    assert AlertRunner._grant_matches_filters(entity, filters) is True

    filters = {'keywords': ['biology']}
    assert AlertRunner._grant_matches_filters(entity, filters) is False

def test_grant_matches_filters_agency():
    entity = {'agency': 'NSF', 'title': 'Test'}
    assert AlertRunner._grant_matches_filters(entity, {'agency': 'NSF'}) is True
    assert AlertRunner._grant_matches_filters(entity, {'agency': 'NIH'}) is False

def test_execute_search_builds_sql_filter(monkeypatch):
    """Test that _execute_search translates filters to correct sql_filter."""
    captured = {}
    def mock_list(sql_filter=None, limit=None):
        captured['sql_filter'] = sql_filter
        captured['limit'] = limit
        return {'data': []}

    monkeypatch.setattr('models.grant.Grant.list', mock_list)
    AlertRunner._execute_search({'agency': 'NSF', 'keywords': ['AI']})

    where, params = captured['sql_filter']
    assert 'agency = ?' in where
    assert 'title LIKE ?' in where
    assert 'NSF' in params
    assert '%AI%' in params
```

---

## 11. New Dependencies

| Dependency | Purpose | Size | Justification |
|-----------|---------|------|---------------|
| `aiosmtplib` | Async SMTP email delivery | ~20KB | The standard async SMTP library for Python. Required for email notifications. No alternative provides async SMTP without this package. `smtplib` from stdlib is synchronous and would block the event loop. |

No other new dependencies are needed:
- `httpx` is already used by `WebTools.scrape()` for HTTP requests (used by webhook delivery)
- `email.message.EmailMessage` is stdlib
- `ipaddress` is stdlib (used for SSRF validation)
- `json` is stdlib (used for JSON field serialization)

### Installation

```
pip install aiosmtplib
```

Or add to `pyproject.toml` / `requirements.txt`:

```
aiosmtplib>=2.0
```

---

## 12. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **WebSocket connection `user` dict missing `id` key** | Medium | High (targeted push fails silently) | Defensive `.get('id')` check with fallback to broadcast. Add assertion in connection setup. |
| **SMTP delivery blocking event loop** | Low | Medium | `aiosmtplib` is fully async. Timeout on send (10s default). Catch-all exception handler. |
| **Saved search `_execute_search` slow for large filter sets** | Low | Medium | SQLite LIKE queries are O(N). For <100K grants, this is <100ms. Index `agency` and `status` columns. |
| **Lifecycle event cascade overload** | Low | High | Each subscriber is fire-and-forget via `create_task`. If 100 saved searches match, 100 Notifications are created. Each fires 2 subscribers (ws + notifier). Bound by adding `limit` to notification creation per alert run. |
| **JSON field deserialization regression** | Low | Medium | Same pattern as `AgentActor.constraints`. Covered by unit tests. |
| **OWNER rule evaluation with href-format user_owner** | Medium | Medium | `_Owner.evaluate()` already handles href extraction (see rules.py lines 186-191). Covered by existing auth tests. |
| **Notification badge count drift** | Medium | Low | Count is a best-effort estimate (increment on CREATE, decrement on UPDATE). Full refresh on page load. Acceptable for v1. |

---

## Appendix: Complete File Manifest

### New Files

| File | Type | Purpose |
|------|------|---------|
| `/workspace/example_grants/models/notification.py` | Model | Notification ActorModel |
| `/workspace/example_grants/models/notification_tools.py` | Actor | Email/webhook delivery engine |
| `/workspace/example_grants/models/saved_search.py` | Model | SavedSearch ActorModel with JSON fields |
| `/workspace/example_grants/models/alert_runner.py` | Actor | Saved search execution + reactive lifecycle |
| `/workspace/example_grants/models/notification_prefs.py` | Model | User notification preferences |
| `/workspace/example_grants/static/components/notification-badge.js` | Frontend | Notification badge web component |
| `/workspace/example_grants/tests/test_notification_model.py` | Test | Notification CRUD tests |
| `/workspace/example_grants/tests/test_notification_tools.py` | Test | Email/webhook delivery tests |
| `/workspace/example_grants/tests/test_saved_search.py` | Test | SavedSearch CRUD + JSON roundtrip tests |
| `/workspace/example_grants/tests/test_alert_runner.py` | Test | Alert execution + filter matching tests |
| `/workspace/example_grants/tests/test_notification_prefs.py` | Test | NotificationPrefs CRUD tests |
| `/workspace/example_grants/tests/test_e2e_notification_chain.py` | Test | End-to-end notification chain test |
| `/workspace/src/pybend/core/tests/unit/test_ws_notification_targeting.py` | Test | WebSocket user targeting tests |

### Modified Files

| File | Change |
|------|--------|
| `/workspace/src/pybend/core/api/network_ws.py` | Add user-targeted delivery in `LIFECYCLE()` |
| `/workspace/example_grants/models/__init__.py` | Add new model imports |
| `/workspace/example_grants/main.py` | Register new models, add subscriber wiring |
| `/workspace/example_grants/seed.py` | Add NotificationPrefs + SavedSearch seed data |
| `/workspace/CLAUDE.md` | Update Key Files, subscriber chain docs |

### Unchanged Framework Files

The following framework files require **zero modifications**:

- `actor_model.py` -- `_publish_lifecycle` and `handler_crud` work as-is
- `actor.py` -- Actor base class, `use()`, `inbox`, `handler`, `send` unchanged
- `matrix.py` -- routing unchanged
- `tx.py` -- TX envelope unchanged
- `storable_mixin.py` -- `list(sql_filter=...)` unchanged
- `rules.py` -- OWNER, AUTHENTICATED, ROLE unchanged
- `decorators.py` -- `@expose_route` unchanged
- `app.py` -- `create_app` and `PyBendApp.build()` unchanged
- `widget.py` -- TextareaField, DateTimeField, UrlField unchanged
