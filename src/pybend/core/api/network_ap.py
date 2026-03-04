"""NetworkAP — ActivityPub federation adapter.

Translates between ActivityPub protocol (HTTP + JSON-LD) and TX messages.
Enables PyBend models with __federated__ = True to participate in the Fediverse.

ActivityPub operations:
    GET  /{tablename}/{id}        → AP Actor/Object document
    POST /{tablename}/{id}/inbox  → Receive activity from remote actor → TX
    GET  /{tablename}/{id}/outbox → List published activities
    GET  /.well-known/webfinger   → Actor address resolution

Lifecycle events from ActorModel are received as LIFECYCLE TXs and
converted to AP Activities stored in the outbox.

This adapter is publish-focused (outbox) in Wave 1. Full bidirectional
federation with HTTP Signature validation is deferred to Wave 4+.

Usage:
    ap = NetworkAP(addr='ap', base_url='https://example.com')
    matrix.register(ap)

    # Subscribe federated models to lifecycle events:
    for model in registered_models.values():
        if getattr(model, '__federated__', False):
            model._subscribers.append('ap')

    # In FastAPI:
    app.include_router(create_federation_routes(ap))
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import PrivateAttr

from pybend.core.actors.tx import TX
from pybend.core.api.network_adapter import NetworkAdapter

logger = logging.getLogger('pybend.network.ap')

# ActivityStreams namespace
AS_CONTEXT = 'https://www.w3.org/ns/activitystreams'

# Map lifecycle events to AP activity types
_EVENT_TO_TYPE = {
    'after_create': 'Create',
    'after_update': 'Update',
    'after_delete': 'Delete',
}


class NetworkAP(NetworkAdapter, auto_register=False):
    """ActivityPub federation adapter.

    Registered as a Matrix child at addr='ap'. Receives LIFECYCLE TXs
    from ActorModel subscribers and converts them to AP Activities.
    Handles inbound AP activities by translating to TX and routing
    through the Matrix.
    """

    _base_url: str = PrivateAttr(default='')
    _outbox: dict = PrivateAttr(default_factory=dict)
    _followers: dict = PrivateAttr(default_factory=dict)

    def __init__(self, base_url: str = '', **kwargs):
        kwargs.setdefault('addr', 'ap')
        super().__init__(**kwargs)
        self._base_url = base_url.rstrip('/')

    @property
    def base_url(self) -> str:
        return self._base_url

    # ── Lifecycle event handler (receives TXs from ActorModel._publish_lifecycle) ──

    def LIFECYCLE(self, data: dict, tx: TX):
        """Handle lifecycle events from ActorModel subscribers.

        Called via normal Actor handler dispatch when a LIFECYCLE TX
        arrives with target='ap'. Converts to AP Activity and records
        in the outbox.
        """
        event = data.get('event', '')
        entity = data.get('entity', {})
        source_addr = tx.source

        if event not in _EVENT_TO_TYPE:
            return {'ignored': True, 'reason': f'Unknown event: {event}'}

        # Resolve the model class from Matrix children
        model_cls = self.parent.children.get(source_addr) if self.parent else None

        if model_cls and not getattr(model_cls, '__federated__', False):
            return {'ignored': True, 'reason': 'Model not federated'}

        activity = self.create_activity(event, entity, source_addr)
        tablename = source_addr  # source_addr is the model's __addr__ (typically tablename)
        self.record_activity(activity, tablename)

        logger.info("Recorded %s activity for %s", activity['type'], tablename)
        return {'recorded': True, 'type': activity['type']}

    # ── Actor Document Generation ──

    def generate_actor_document(self, tablename: str, model_name: str,
                                entity_id: int = None) -> dict:
        """Generate an ActivityPub Actor document.

        For a model collection (no entity_id): returns a Service actor.
        For a specific entity (with entity_id): returns a Person actor.
        """
        if entity_id is not None:
            actor_url = f"{self.base_url}/{tablename}/{entity_id}"
            actor_type = 'Person'
            name = f"{model_name} #{entity_id}"
            username = f"{tablename}-{entity_id}"
        else:
            actor_url = f"{self.base_url}/{tablename}"
            actor_type = 'Service'
            name = model_name
            username = tablename

        return {
            '@context': [
                AS_CONTEXT,
                'https://w3id.org/security/v1',
            ],
            'id': actor_url,
            'type': actor_type,
            'name': name,
            'preferredUsername': username,
            'inbox': f"{actor_url}/inbox",
            'outbox': f"{actor_url}/outbox",
            'followers': f"{actor_url}/followers",
            'following': f"{actor_url}/following",
            'url': actor_url,
            'summary': f"PyBend {model_name} actor",
            'endpoints': {
                'sharedInbox': f"{self.base_url}/inbox",
            },
        }

    # ── Activity Creation ──

    def create_activity(self, event: str, entity_data: dict,
                        source_addr: str) -> dict:
        """Convert a lifecycle event to an ActivityPub Activity.

        Maps: after_create → Create, after_update → Update, after_delete → Delete
        """
        activity_type = _EVENT_TO_TYPE.get(event, 'Update')
        entity_id = entity_data.get('id', '')
        actor_url = f"{self.base_url}/{source_addr}"

        activity = {
            '@context': AS_CONTEXT,
            'id': f"{actor_url}/outbox/{activity_type.lower()}-{entity_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            'type': activity_type,
            'actor': actor_url,
            'published': datetime.now(timezone.utc).isoformat(),
        }

        if activity_type == 'Delete':
            activity['object'] = {
                'id': f"{actor_url}/{entity_id}",
                'type': 'Tombstone',
            }
        else:
            # Include entity data as the object
            obj = dict(entity_data)
            obj.setdefault('@context', AS_CONTEXT)
            obj.setdefault('id', f"{actor_url}/{entity_id}")
            obj.setdefault('type', 'Object')
            activity['object'] = obj

        return activity

    # ── Outbox ──

    def record_activity(self, activity: dict, tablename: str):
        """Store an activity in the outbox for a given model."""
        if tablename not in self._outbox:
            self._outbox[tablename] = []
        self._outbox[tablename].insert(0, activity)  # Newest first

    def get_outbox(self, tablename: str, page: int = 1,
                   page_size: int = 20) -> dict:
        """Return paginated outbox as an AP OrderedCollectionPage."""
        activities = self._outbox.get(tablename, [])
        total = len(activities)
        start = (page - 1) * page_size
        end = start + page_size
        items = activities[start:end]

        collection_url = f"{self.base_url}/{tablename}/outbox"

        result = {
            '@context': AS_CONTEXT,
            'id': f"{collection_url}?page={page}",
            'type': 'OrderedCollectionPage',
            'partOf': collection_url,
            'totalItems': total,
            'orderedItems': items,
        }

        if end < total:
            result['next'] = f"{collection_url}?page={page + 1}"
        if page > 1:
            result['prev'] = f"{collection_url}?page={page - 1}"

        return result

    # ── Inbound Inbox ──

    async def handle_inbox(self, activity: dict, tablename: str) -> dict:
        """Receive an ActivityPub activity and route into the Matrix.

        Translates the AP activity to a TX and sends it fire-and-forget.
        Wave 1 handles Follow and basic CRUD activities.
        HTTP Signature validation is deferred to Wave 4+.
        """
        activity_type = activity.get('type', '').lower()
        actor = activity.get('actor', '')

        if not activity_type:
            return {'detail': 'Activity must have a type'}

        if not actor:
            return {'detail': 'Activity must have an actor'}

        # Handle Follow specially
        if activity_type == 'follow':
            return self._handle_follow(actor, tablename)

        # Map AP activity type to TX name
        if activity_type in ('create', 'update', 'delete'):
            obj = activity.get('object', {})
            obj_data = obj if isinstance(obj, dict) else {'id': obj}

            tx = TX(
                name=activity_type,
                source=actor,
                target=tablename,
                data=obj_data,
                meta={'federated': True, 'actor': actor, 'protocol': 'activitypub'},
            )
            await self.send(tx)

            return {
                'accepted': True,
                'type': activity_type,
                'actor': actor,
            }

        # Undo (e.g., Undo Follow)
        if activity_type == 'undo':
            inner = activity.get('object', {})
            inner_type = inner.get('type', '').lower() if isinstance(inner, dict) else ''
            if inner_type == 'follow':
                return self._handle_unfollow(actor, tablename)
            return {'accepted': True, 'type': 'undo'}

        return {'accepted': True, 'type': activity_type}

    def _handle_follow(self, follower_uri: str, tablename: str) -> dict:
        """Handle a Follow activity — add to followers list."""
        if tablename not in self._followers:
            self._followers[tablename] = []
        if follower_uri not in self._followers[tablename]:
            self._followers[tablename].append(follower_uri)
            logger.info("New follower for %s: %s", tablename, follower_uri)
        return {'accepted': True, 'type': 'follow', 'follower': follower_uri}

    def _handle_unfollow(self, follower_uri: str, tablename: str) -> dict:
        """Handle an Undo Follow — remove from followers list."""
        if tablename in self._followers:
            try:
                self._followers[tablename].remove(follower_uri)
                logger.info("Unfollowed %s from %s", follower_uri, tablename)
            except ValueError:
                pass
        return {'accepted': True, 'type': 'undo_follow', 'follower': follower_uri}

    def get_followers(self, tablename: str) -> list[str]:
        """Return list of follower URIs for a model."""
        return self._followers.get(tablename, [])

    # ── WebFinger ──

    def webfinger(self, resource: str) -> Optional[dict]:
        """Resolve a WebFinger resource to AP actor links.

        Supports:
            acct:tablename@domain → collection-level actor
            acct:tablename-id@domain → entity-level actor
            URL → direct match
        """
        if not self.base_url:
            return None

        # Parse domain from base_url
        from urllib.parse import urlparse
        parsed = urlparse(self.base_url)
        domain = parsed.netloc or parsed.path

        # Handle acct: format
        if resource.startswith('acct:'):
            acct = resource[5:]  # strip 'acct:'
            if '@' in acct:
                username, acct_domain = acct.rsplit('@', 1)
                if acct_domain != domain:
                    return None
            else:
                username = acct

            # Check if this matches a registered model
            # username can be tablename or tablename-id
            parts = username.rsplit('-', 1)
            tablename = parts[0]
            entity_id = parts[1] if len(parts) > 1 and parts[1].isdigit() else None

            if self.parent and tablename not in self.parent.children:
                return None

            if entity_id:
                actor_url = f"{self.base_url}/{tablename}/{entity_id}"
            else:
                actor_url = f"{self.base_url}/{tablename}"

            subject = f"acct:{username}@{domain}"

        elif resource.startswith(('http://', 'https://')):
            # Direct URL match
            if not resource.startswith(self.base_url):
                return None
            actor_url = resource
            # Extract tablename from URL for subject
            path = resource[len(self.base_url):].strip('/')
            subject = f"acct:{path.replace('/', '-')}@{domain}"
        else:
            return None

        return {
            'subject': subject,
            'aliases': [actor_url],
            'links': [
                {
                    'rel': 'self',
                    'type': 'application/activity+json',
                    'href': actor_url,
                },
                {
                    'rel': 'http://webfinger.net/rel/profile-page',
                    'type': 'text/html',
                    'href': actor_url,
                },
            ],
        }

    # ── Federated model discovery ──

    def get_federated_models(self) -> list[tuple[str, type]]:
        """Return (addr, cls) for all federated models in the Matrix."""
        if not self.parent:
            return []
        results = []
        for addr, child in self.parent.children.items():
            if isinstance(child, type) and getattr(child, '__federated__', False):
                results.append((addr, child))
        return results


def create_federation_routes(ap_adapter: NetworkAP):
    """Create FastAPI routes for ActivityPub endpoints.

    Returns a FastAPI APIRouter with:
    - GET  /.well-known/webfinger  — WebFinger actor discovery
    - GET  /{tablename}/outbox     — Published activities
    - POST /{tablename}/inbox      — Receive activities (basic, Wave 1)
    """
    from fastapi import APIRouter, HTTPException, Request, Query
    from fastapi.responses import JSONResponse

    router = APIRouter(tags=['Federation'])

    @router.get('/.well-known/webfinger')
    async def webfinger(resource: str = Query(...)):
        """WebFinger endpoint for actor discovery."""
        result = ap_adapter.webfinger(resource)
        if result is None:
            raise HTTPException(status_code=404, detail='Not found')
        return JSONResponse(result, headers={
            'Content-Type': 'application/jrd+json',
            'Access-Control-Allow-Origin': '*',
        })

    @router.get('/{tablename}/outbox')
    async def get_outbox(tablename: str, page: int = Query(default=1)):
        """ActivityPub outbox endpoint."""
        outbox = ap_adapter.get_outbox(tablename, page=page)
        return JSONResponse(outbox, headers={
            'Content-Type': 'application/activity+json',
        })

    @router.post('/{tablename}/inbox')
    async def post_inbox(tablename: str, request: Request):
        """ActivityPub inbox endpoint (basic, Wave 1)."""
        try:
            activity = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail='Invalid JSON')

        result = await ap_adapter.handle_inbox(activity, tablename)
        if 'detail' in result:
            return JSONResponse(result, status_code=422)
        return JSONResponse(result, status_code=202, headers={
            'Content-Type': 'application/activity+json',
        })

    return router
