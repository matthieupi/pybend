"""ActorModel — Models that are actors.

Bridge class: Actor (messaging) + ProtoModel (data/schema/validation).

CRUD operations are routed through handler_crud() which adapts
TX messages to StorableMixin method signatures. Non-CRUD messages
fall through to Actor's generic handler (getattr dispatch).

    class Product(ActorModel):
        __tablename__ = 'products'
        __storable__ = True
        name: str = Field(min_length=1, max_length=200)

    # Product is now an actor:
    # await Product.inbox(TX(name='create', source='api', target='products', data={...}))
"""

import asyncio
import logging
from typing import ClassVar

from pydantic import ConfigDict

from pybend.core.actors.actor import Actor, actormethod, actorproperty
from pybend.core.actors.tx import TX
from pybend.core.models.proto_model import ProtoModel

logger = logging.getLogger('pybend.actors')

# Sentinel — distinguishes "not a CRUD message" from legitimate None returns
_NOT_HANDLED = object()

# CRUD message names handled by handler_crud
_CRUD_OPS = frozenset({'schema', 'create', 'get', 'list', 'update', 'delete'})


class ActorModel(Actor, ProtoModel):
    """A model that IS an actor. The bridge class.

    MRO: Product → ActorModel → Actor → ProtoModel → PydanticBaseModel

    Handles:
    - CRUD messages via handler_crud() adapter (schema, create, get, list, update, delete)
    - Non-CRUD messages via generic Actor handler (getattr dispatch)
    - Lifecycle events published after create/update/delete
    """

    model_config = ConfigDict(
        ignored_types=(actormethod, actorproperty),
        arbitrary_types_allowed=True,
        extra='allow',
    )

    _subscribers: ClassVar[list] = []

    # ── Handler override ──

    @actormethod
    async def handler(target, tx: TX) -> None:
        """Try CRUD adapter first, fall back to generic dispatch."""
        cls = target if isinstance(target, type) else target.__class__
        result = cls.handler_crud(tx)

        if result is not _NOT_HANDLED:
            # Dispatch CRUD result
            try:
                if isinstance(result, TX):
                    await target.send(result)
                elif isinstance(result, (dict, list)):
                    await target.send(tx.reply(data=result))
                elif result is not None:
                    await target.send(tx.reply(data={'result': result}))
                else:
                    await target.send(tx.reply())
            except Exception as e:
                logger.error(f"[{target.addr}] Error dispatching {tx.name}: {e}")
                await target.send(tx.error(str(e)))
        else:
            # Generic fallback for custom @expose_route methods and other messages.
            method = getattr(target, tx.name, None)
            if method and callable(method):
                try:
                    data = tx.data or {}
                    is_exposed = hasattr(method, '__endpoint__')

                    if is_exposed:
                        # @expose_route method: unpack data as kwargs.
                        # Instance methods need 'self' resolved from id in data.
                        from inspect import signature as get_sig
                        sig = get_sig(method)
                        is_instance = 'self' in sig.parameters
                        kwargs = {k: v for k, v in data.items() if k != 'id'}

                        if is_instance:
                            entity_id = data.get('id')
                            if not entity_id:
                                await target.send(tx.error("'id' required for instance method", code=400))
                                return
                            instance = cls.get(entity_id)
                            if not instance:
                                await target.send(tx.error(f"{cls.__name__} {entity_id} not found", code=404))
                                return
                            result = method(instance, **kwargs)
                        else:
                            result = method(**kwargs)
                    else:
                        # Non-exposed method: original (data, tx) signature
                        if asyncio.iscoroutinefunction(method):
                            result = await method(data, tx)
                        else:
                            result = method(data, tx)
                except Exception as e:
                    from pybend.core.utils.erroring import MethodError
                    if isinstance(e, MethodError):
                        code, msg = e.status_code, e.message
                    elif hasattr(e, 'status_code') and hasattr(e, 'detail'):
                        # HTTPException from FastAPI
                        code, msg = e.status_code, e.detail
                    elif isinstance(e, TypeError) and 'required' in str(e):
                        code, msg = 400, str(e)
                    else:
                        code, msg = 500, str(e)
                    logger.error(f"[{target.addr}] Error in {tx.name}: {msg}")
                    await target.send(tx.error(msg, code=code))
                    return

                if isinstance(result, TX):
                    await target.send(result)
                elif isinstance(result, (dict, list)):
                    await target.send(tx.reply(data=result))
                elif isinstance(result, str):
                    # Try to parse JSON strings (custom methods return JSON strings)
                    import json
                    try:
                        parsed = json.loads(result)
                        await target.send(tx.reply(data=parsed))
                    except (json.JSONDecodeError, TypeError):
                        await target.send(tx.reply(data={'result': result}))
                elif result is not None:
                    await target.send(tx.reply(data={'result': result}))
                else:
                    await target.send(tx.reply())
            else:
                await target.send(tx.error(f"Unhandled message: {tx.name}"))

    # ── Tier 2: Handler-level authorization ──

    @classmethod
    def _authorize(cls, action: str, tx: TX, resource=None):
        """Tier 2 auth guard — full ABAC check with resource context.

        Evaluates __access__ rules against tx.meta['user']. Called inside
        handler_crud after the resource instance is fetched, enabling
        resource-dependent rules (OWNER) that Tier 1 interceptors can't check.

        Returns error TX if denied, None if authorized.
        Internal messages (no meta.user) pass through unchecked.
        """
        user = tx.meta.get('user')
        if user is None:
            return None  # Internal message — no auth context

        access = getattr(cls, '__access__', None)
        if not access:
            return None  # No access rules declared

        from pybend.core.authorize import AccessContext, DefaultResolver
        resolver = DefaultResolver()
        rule = resolver.resolve_rule(cls, action)

        ctx = AccessContext(
            user=user, action=action, model_class=cls, resource=resource,
        )
        if not rule.evaluate(ctx):
            return tx.error("Access denied", code=403)
        return None

    # ── CRUD adapter ──

    @classmethod
    def handler_crud(cls, tx: TX):
        """Adapt TX messages to StorableMixin method signatures.

        Returns a result (dict, TX, or value) for CRUD messages,
        or _NOT_HANDLED sentinel for everything else.

        Tier 2 auth: after fetching the resource instance, checks __access__
        rules with resource context (enables OWNER evaluation).
        """
        name = tx.name.lower()
        data = tx.data or {}

        if name not in _CRUD_OPS:
            return _NOT_HANDLED

        try:
            if name == 'schema':
                return cls.schema()

            elif name == 'create':
                denied = cls._authorize('create', tx)
                if denied:
                    return denied
                instance = cls(**data)
                result = cls.create(instance)
                if result:
                    cls._publish_lifecycle('after_create', result.model_response())
                    return result.model_response()
                return tx.error("Create failed")

            elif name == 'get':
                entity_id = data.get('id')
                if not entity_id:
                    return tx.error("'id' required", code=400)
                result = cls.get(entity_id)
                if not result:
                    return tx.error(f"{cls.__name__} {entity_id} not found", code=404)
                denied = cls._authorize('read', tx, resource=result)
                if denied:
                    return denied
                return result.model_response()

            elif name == 'list':
                # sql_filter computed by Tier 1 interceptor, passed via meta
                result = cls.list(
                    sql_filter=tx.meta.get('sql_filter'),
                    limit=data.get('limit'),
                    offset=data.get('offset'),
                )
                # Serialize model instances with $schema/$id (matches Level 1/2)
                _ser = lambda r: r.model_response() if hasattr(r, 'model_response') else r
                if isinstance(result, dict) and 'data' in result:
                    result['data'] = [_ser(r) for r in result['data']]
                    return result
                return [_ser(r) for r in result]

            elif name == 'update':
                entity_id = data.get('id')
                if not entity_id:
                    return tx.error("'id' required", code=400)
                result = cls.get(entity_id)
                if not result:
                    return tx.error(f"{cls.__name__} {entity_id} not found", code=404)
                denied = cls._authorize('update', tx, resource=result)
                if denied:
                    return denied
                update_data = {k: v for k, v in data.items() if k != 'id'}
                result = cls.update(entity_id, update_data)
                if result:
                    cls._publish_lifecycle('after_update', result.model_response())
                    return result.model_response()
                return tx.error("Update failed")

            elif name == 'delete':
                entity_id = data.get('id')
                if not entity_id:
                    return tx.error("'id' required", code=400)
                result = cls.get(entity_id)
                if not result:
                    return tx.error(f"{cls.__name__} {entity_id} not found", code=404)
                denied = cls._authorize('delete', tx, resource=result)
                if denied:
                    return denied
                cls.delete(entity_id)
                cls._publish_lifecycle('after_delete', {'id': entity_id})
                return {'deleted': entity_id}

        except Exception as e:
            logger.error(f"[{cls.__addr__}] CRUD error in {name}: {e}")
            return tx.error(str(e))

        return _NOT_HANDLED

    # ── Lifecycle events ──

    @classmethod
    def _publish_lifecycle(cls, event: str, data: dict):
        """Publish lifecycle event to subscribers. Fire-and-forget.

        Subscribers are future consumers: federation outbox, agent monitor,
        audit logger, websocket bridge. In Wave 0, _subscribers is empty —
        the infrastructure exists but no consumers yet.
        """
        for subscriber_addr in cls._subscribers:
            asyncio.create_task(cls.send(TX(
                name='LIFECYCLE',
                source=cls.__addr__,
                target=subscriber_addr,
                data={'event': event, 'entity': data},
            )))
