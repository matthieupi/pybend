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
import inspect
import logging
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from n3tx_actors.actor import Actor
from n3tx_core.utils.descriptors import fullmethod, fullproperty
from n3tx_core.utils.decorators import exposed_method_info
from n3tx_actors.tx import TX
from n3tx_core.models.proto_model import ProtoModel

logger = logging.getLogger('n3tx.actors')

# Sentinel — distinguishes "not a CRUD message" from legitimate None returns
_NOT_HANDLED = object()

# CRUD message names handled by handler_crud
_CRUD_OPS = frozenset({'schema', 'create', 'get', 'list', 'update', 'delete'})


def _parse_populate_from_data(data: dict):
    """Parse populate/depth from TX.data into a PopulateSpec (or None)."""
    populate_str = data.get('populate')
    depth_int = data.get('depth')
    if populate_str is None and depth_int is None:
        return None
    from n3tx_core.utils.populate import parse_populate
    return parse_populate(populate_str, depth_int)


class ActorModel(Actor, ProtoModel):
    """A model that IS an actor. The bridge class.

    MRO: Product → ActorModel → Actor → ProtoModel → PydanticBaseModel

    Handles:
    - CRUD messages via handler_crud() adapter (schema, create, get, list, update, delete)
    - Non-CRUD messages via generic Actor handler (getattr dispatch)
    - Lifecycle events published after create/update/delete
    """

    model_config = ConfigDict(
        ignored_types=(fullmethod, fullproperty),
        arbitrary_types_allowed=True,
        extra='allow',
    )

    _subscribers: ClassVar[list] = []

    @classmethod
    def ref(cls, address, *, matrix=None, user=None):
        """Return an explicit handle for calling this model at a ref address.

        This keeps model construction (`Artifact(...)`) distinct from remote or
        distributed identity handles (`Artifact.ref('n3tx://...')`).
        """
        from n3tx_actors.remote_proxy import RemoteRef
        return RemoteRef(address, model_cls=cls, matrix=matrix, user=user)

    # ── Handler override ──

    @fullmethod
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
                elif isinstance(result, BaseModel):
                    await target.send(tx.reply(data=result.model_dump()))
                elif result is not None:
                    await target.send(tx.reply(data=result))
                else:
                    await target.send(tx.reply())
            except Exception as e:
                logger.error(f"[{target.addr}] Error dispatching {tx.name}: {e}")
                await target.send(tx.error(str(e)))
        else:
            # Generic fallback for custom @expose_route methods and other messages.
            method = getattr(target, tx.name, None)
            exposed = exposed_method_info(cls, tx.name)
            if exposed is not None:
                method = exposed.bound
            if method and callable(method):
                try:
                    data = tx.data or {}
                    is_exposed = exposed is not None or hasattr(method, '__endpoint__')

                    if is_exposed:
                        # @expose_route method: unpack data as kwargs.
                        # Instance methods need 'self' resolved from id in data.
                        from inspect import signature as get_sig
                        from typing import get_type_hints
                        from n3tx_core.utils.materialize import materialize_arg
                        signature_target = exposed.func if exposed is not None else method
                        sig = get_sig(signature_target)
                        type_hints = get_type_hints(signature_target)
                        is_instance = exposed.requires_instance if exposed is not None else 'self' in sig.parameters

                        instance = None
                        if is_instance:
                            entity_id = data.get('id')
                            if not entity_id:
                                await target.send(tx.error("'id' required for instance method", code=400))
                                return
                            instance = cls.get(entity_id)
                            if not instance:
                                await target.send(tx.error(f"{cls.__name__} {entity_id} not found", code=404))
                                return

                        # Tier 2 auth: final method access check happens after
                        # instance resolution so resource-dependent rules such
                        # as OWNER and Where evaluate against the target row.
                        endpoint_info = getattr(method, '__endpoint__', {})
                        method_access = endpoint_info.get('access')
                        if method_access is not None:
                            user = tx.meta.get('user')
                            if user is not None:
                                # External or agent-proxied request — evaluate access
                                from n3tx_core.authorize import AccessContext
                                ctx = AccessContext(
                                    user=user,
                                    action=tx.name, model_class=cls,
                                    resource=instance,
                                )
                                if not method_access.evaluate(ctx):
                                    await target.send(tx.error("Access denied", code=403))
                                    return
                            # user is None → internal message, no auth context (matches _authorize())

                        kwargs = {k: v for k, v in data.items() if k != 'id'}
                        user = tx.meta.get('user')
                        for arg_name, arg_value in list(kwargs.items()):
                            expected_type = type_hints.get(arg_name)
                            if expected_type is None:
                                continue
                            kwargs[arg_name] = await materialize_arg(
                                arg_value,
                                expected_type,
                                user=user,
                                context={'tx': tx, 'param': arg_name},
                            )

                        if is_instance:
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
                    logger.error(f"[{target.addr}] Error in {tx.name}: {e}")
                    await target.send(tx.exception(e))
                    return

                # If result is a coroutine, await it first
                if asyncio.iscoroutine(result):
                    result = await result

                # Streaming: handler returned an async generator
                if inspect.isasyncgen(result):
                    seq = 0
                    try:
                        async for chunk in result:
                            chunk_data = chunk if isinstance(chunk, dict) else {'chunk': chunk}
                            await target.send(tx.chunk(chunk_data, seq))
                            seq += 1
                        await target.send(tx.end(seq=seq))
                    except Exception as e:
                        logger.error(f"[{target.addr}] Stream error in {tx.name}: {e}")
                        await target.send(tx.exception(e))
                    return

                if isinstance(result, TX):
                    await target.send(result)
                elif isinstance(result, (dict, list)):
                    await target.send(tx.reply(data=result))
                elif isinstance(result, BaseModel):
                    await target.send(tx.reply(data=result.model_dump()))
                elif isinstance(result, str):
                    import json
                    try:
                        parsed = json.loads(result)
                        await target.send(tx.reply(data=parsed))
                    except (json.JSONDecodeError, TypeError):
                        await target.send(tx.reply(data=result))
                elif result is not None:
                    await target.send(tx.reply(data=result))
                elif tx.name == 'LIFECYCLE':
                    return
                else:
                    await target.send(tx.reply())
            else:
                # Drop errors and responses — sending an error in response
                # to an error creates infinite bounce loops between actors.
                if tx.is_error or tx.name.endswith('_RESPONSE'):
                    addr = target.addr if not isinstance(target, type) else target.__addr__
                    logger.debug("[%s] Dropped unhandled %s from %s", addr, tx.name, tx.source)
                    return
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

        from n3tx_core.authorize import AccessContext, DefaultResolver
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
                return tx.error("Create failed", code=409)

            elif name == 'get':
                entity_id = data.get('id')
                if not entity_id:
                    return tx.error("'id' required", code=400)
                populate = _parse_populate_from_data(data)
                result = cls.get(entity_id, populate=populate)
                if not result:
                    return tx.error(f"{cls.__name__} {entity_id} not found", code=404)
                denied = cls._authorize('read', tx, resource=result)
                if denied:
                    return denied
                return result.model_response()

            elif name == 'list':
                # sql_filter computed by Tier 1 interceptor, passed via meta
                populate = _parse_populate_from_data(data)
                result = cls.list(
                    sql_filter=tx.meta.get('sql_filter'),
                    limit=data.get('limit'),
                    offset=data.get('offset'),
                    populate=populate,
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
                return tx.error("Update failed", code=409)

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
            return tx.exception(e)

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
