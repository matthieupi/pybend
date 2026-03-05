"""NetworkAPI -- HTTP API adapter for Level 3 actor routing.

Bridges FastAPI HTTP routes to the Matrix via TX messaging.
Every request becomes a TX routed through adapter.request(), which
runs interceptors (auth) then sends into the actor system and awaits
the correlated reply.

Level 3 alternative to routes_fastapi.py:
    Level 1/2: ProtoModel/ActorModel + routes_fastapi.py (direct)
    Level 3:   ActorModel + NetworkAPI (full actor routing)

Usage:
    api = NetworkAPI()
    matrix.register(api)
    api.use(auth_interceptor, on='request')
    app.include_router(create_api_routes(api, registered_models))
"""

import json
import logging
from inspect import signature
from typing import Any, Dict, Type

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from n3tx.core.actors.tx import TX
from n3tx.core.api.network_adapter import NetworkAdapter
from n3tx.core.models.storable_mixin import StorableMixin

logger = logging.getLogger('n3tx.network.api')


class NetworkAPI(NetworkAdapter, auto_register=False):
    """HTTP API adapter. Bridges FastAPI routes to Matrix via TX messaging."""

    def __init__(self, **kwargs):
        kwargs.setdefault('addr', 'api')
        super().__init__(**kwargs)


def _get_user(request) -> dict:
    """Extract user dict from request.state, set by JWTAuthMiddleware."""
    return getattr(request.state, 'user', {}) or {}


def _response_or_raise(response: TX):
    """Convert a TX response to HTTP result or raise HTTPException."""
    if response.is_error:
        code = response.data.get('code', 500)
        message = response.data.get('message', 'Internal error')
        raise HTTPException(status_code=code, detail=message)
    return response.data


def create_api_routes(api_adapter: NetworkAPI, models_dict: dict):
    """Create FastAPI routes that bridge HTTP to actor TX messaging.

    Mirrors the route structure of routes_fastapi.py but routes everything
    through the actor system via api_adapter.request().

    Args:
        api_adapter: The NetworkAPI adapter instance (registered with Matrix).
        models_dict: The registered_models dict {tablename: model_class}.

    Returns:
        A FastAPI APIRouter with all CRUD and custom method routes.
    """
    from n3tx.core.utils.registrar import join_models
    from n3tx.core.utils.typer import flatten_refs

    router = APIRouter()

    # Utility routes (not model-specific, no actor routing needed)
    @router.get("/auth/me", tags=["Auth"])
    async def auth_me(request: Request):
        """Return the current user's identity from the JWT token."""
        user = _get_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return {
            "user_id": user.get("user_id"),
            "email": user.get("email"),
            "role": user.get("role", "user"),
        }

    # Pass 1: Static collection routes for join models (must come first)
    for model_name, model_class in models_dict.items():
        parent_class = getattr(model_class, '__owner__', None)
        if parent_class and issubclass(model_class, StorableMixin):
            tag = parent_class.__tablename__.capitalize()
            collection_path = f"/{model_class.__tablename__}"
            _register_collection_route(
                router, api_adapter, model_class, collection_path, tag,
            )

    # Pass 2: All model routes (schema, CRUD, custom methods)
    for model_name, model_class in models_dict.items():
        parent_class = getattr(model_class, '__owner__', None)
        is_storable = issubclass(model_class, StorableMixin)

        if not parent_class:
            tag = model_class.__tablename__.capitalize()
            endpoint_base = f"/{model_name}"
        else:
            tag = parent_class.__tablename__.capitalize()
            endpoint_base = (
                f"/{parent_class.__tablename__}/{{parent_id:int}}"
                f"/{model_class.__tagname__}"
            )

        # Schema route: GET /{ClassName}
        _register_schema_route(router, api_adapter, model_class, tag)

        # CRUD routes
        if is_storable:
            _register_crud_routes(
                router, api_adapter, model_class, endpoint_base, tag,
                has_parent=parent_class is not None,
            )

        # Custom @expose_route methods
        _register_custom_routes(
            router, api_adapter, model_class, endpoint_base, tag,
        )

    return router


# ---- Route registration helpers ----

def _register_schema_route(router, api_adapter, model_class, tag):
    """GET /{ClassName} -> schema (no auth, direct)."""
    class_name = model_class.__name__
    addr = model_class.__tablename__

    @router.get(f"/{class_name}", tags=[tag], name=f"schema_{class_name}")
    async def get_schema(
        request: Request,
        scaffold: str = Query(default=None),
        _addr=addr, _cls=model_class,
    ):
        if scaffold:
            from fastapi.responses import PlainTextResponse
            from n3tx.core.utils.scaffold import scaffold_single
            try:
                source = scaffold_single(
                    _cls.__name__, kind=scaffold, schema=_cls.schema(),
                )
                return PlainTextResponse(source, media_type='text/plain')
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        response = await api_adapter.request(
            TX(name='schema', source=api_adapter.addr, target=_addr),
            timeout=10.0,
        )
        return _response_or_raise(response)


def _register_collection_route(router, api_adapter, model_class, path, tag):
    """GET /{join_tablename} -> list all records across parents."""
    addr = model_class.__tablename__

    @router.get(path, tags=[tag], name=f"collection_{addr}")
    async def collection_list(
        request: Request,
        limit: int = Query(default=None, ge=1, le=100),
        offset: int = Query(default=None, ge=0),
        _addr=addr, _cls=model_class,
    ):
        user = _get_user(request)
        data = {}
        if limit is not None:
            data['limit'] = limit
        if offset is not None:
            data['offset'] = offset

        response = await api_adapter.request(
            TX(
                name='list', source=api_adapter.addr, target=_addr,
                data=data,
                meta={'user': user, 'model_cls': _cls},
            ),
            timeout=30.0,
        )
        return _response_or_raise(response)


def _register_crud_routes(
    router, api_adapter, model_class, endpoint_base, tag, has_parent=False,
):
    """Register POST, GET (list), GET (item), PUT, DELETE routes."""
    addr = model_class.__tablename__
    param_class = (
        model_class.__parent__
        if hasattr(model_class, '__parent__')
        else model_class
    )

    # POST - create
    @router.post(endpoint_base, tags=[tag], status_code=201,
                 name=f"create_{addr}")
    async def create_instance(
        request: Request,
        data: param_class,
        parent_id: int = None,
        _addr=addr, _cls=model_class, _param_cls=param_class,
    ):
        from n3tx.core.utils.typer import flatten_refs
        user = _get_user(request)
        data_dict = flatten_refs(data)

        # Inject parent FK
        if parent_id and has_parent:
            fk_field = f"{_cls.__owner__.__name__.lower()}_id"
            data_dict[fk_field] = parent_id

        # Auto-inject user_owner from JWT on create
        protected = (
            getattr(_cls, '__protected_fields__', None)
            or getattr(_param_cls, '__protected_fields__', set())
        )
        if 'user_owner' in protected:
            if user and user.get('user_id'):
                data_dict['user_owner'] = user['user_id']

        response = await api_adapter.request(
            TX(
                name='create', source=api_adapter.addr, target=_addr,
                data=data_dict,
                meta={'user': user, 'model_cls': _cls},
            ),
            timeout=30.0,
        )
        return _response_or_raise(response)

    # GET - list
    @router.get(endpoint_base, tags=[tag], name=f"list_{addr}")
    async def list_instances(
        request: Request,
        parent_id: int = None,
        limit: int = Query(default=None, ge=1, le=100),
        offset: int = Query(default=None, ge=0),
        _addr=addr, _cls=model_class, _has_parent=has_parent,
    ):
        user = _get_user(request)
        data = {}
        if limit is not None:
            data['limit'] = limit
        if offset is not None:
            data['offset'] = offset
        if parent_id and _has_parent:
            data['parent_id'] = parent_id

        response = await api_adapter.request(
            TX(
                name='list', source=api_adapter.addr, target=_addr,
                data=data,
                meta={'user': user, 'model_cls': _cls},
            ),
            timeout=30.0,
        )
        result = _response_or_raise(response)

        # Post-filter by parent FK (mirrors Level 1/2 routes_fastapi.py behavior)
        if parent_id and _has_parent:
            fk_field = f"{_cls.__owner__.__name__.lower()}_id"
            if isinstance(result, list):
                result = [r for r in result if r.get(fk_field) == parent_id]
            elif isinstance(result, dict) and 'data' in result:
                result['data'] = [
                    r for r in result['data'] if r.get(fk_field) == parent_id
                ]
        return result

    # GET - single item
    @router.get(f"{endpoint_base}/{{id:int}}", tags=[tag],
                name=f"get_{addr}")
    async def get_instance(
        request: Request,
        id: int,
        _addr=addr, _cls=model_class,
    ):
        user = _get_user(request)
        response = await api_adapter.request(
            TX(
                name='get', source=api_adapter.addr, target=_addr,
                data={'id': id},
                meta={'user': user, 'model_cls': _cls},
            ),
            timeout=30.0,
        )
        return _response_or_raise(response)

    # PUT - update
    @router.put(f"{endpoint_base}/{{id:int}}", tags=[tag],
                name=f"update_{addr}")
    async def update_instance(
        request: Request,
        id: int,
        data: param_class,
        parent_id: int = None,
        _addr=addr, _cls=model_class, _param_cls=param_class,
    ):
        from n3tx.core.utils.typer import flatten_refs
        user = _get_user(request)
        data_dict = flatten_refs(data)

        # Strip protected fields on update
        protected = (
            getattr(_cls, '__protected_fields__', None)
            or getattr(_param_cls, '__protected_fields__', set())
        )
        for field in protected:
            data_dict.pop(field, None)

        if parent_id and has_parent:
            fk_field = f"{_cls.__owner__.__name__.lower()}_id"
            data_dict[fk_field] = parent_id

        data_dict['id'] = id

        response = await api_adapter.request(
            TX(
                name='update', source=api_adapter.addr, target=_addr,
                data=data_dict,
                meta={'user': user, 'model_cls': _cls},
            ),
            timeout=30.0,
        )
        return _response_or_raise(response)

    # DELETE
    @router.delete(f"{endpoint_base}/{{id:int}}", tags=[tag],
                   name=f"delete_{addr}")
    async def delete_instance(
        request: Request,
        id: int,
        _addr=addr, _cls=model_class,
    ):
        user = _get_user(request)
        response = await api_adapter.request(
            TX(
                name='delete', source=api_adapter.addr, target=_addr,
                data={'id': id},
                meta={'user': user, 'model_cls': _cls},
            ),
            timeout=30.0,
        )
        return _response_or_raise(response)


def _register_custom_routes(router, api_adapter, model_class, endpoint_base, tag):
    """Register @expose_route custom method routes."""
    from inspect import signature as get_sig
    from typing import get_type_hints

    addr = model_class.__tablename__

    for attr_name in dir(model_class):
        attr = getattr(model_class, attr_name, None)
        if not callable(attr) or not hasattr(attr, '__endpoint__'):
            continue

        route_info = attr.__endpoint__
        route = route_info['route']
        methods = route_info['methods']

        sig = get_sig(attr)
        is_instance_method = 'self' in sig.parameters

        if is_instance_method:
            full_route = f"{endpoint_base}/{{id:int}}{route}"
        else:
            full_route = f"{endpoint_base}{route}"

        is_stream = route_info.get('stream', False)
        if is_stream:
            _add_streaming_handler(
                router, api_adapter, model_class, attr, attr_name,
                full_route, methods, tag, is_instance_method, addr,
            )
        else:
            _add_custom_handler(
                router, api_adapter, model_class, attr, attr_name,
                full_route, methods, tag, is_instance_method, addr,
            )


def _add_custom_handler(
    router, api_adapter, model_class, attr, attr_name,
    full_route, methods, tag, is_instance_method, addr,
):
    """Create and register a single custom method handler."""
    from inspect import signature as get_sig
    from typing import get_type_hints

    sig = get_sig(attr)
    type_hints = get_type_hints(attr)

    if is_instance_method:
        @router.api_route(full_route, methods=methods, tags=[tag],
                          name=f"custom_{addr}_{attr_name}")
        async def custom_with_id(
            request: Request,
            id: int = Path(...),
            data: Dict[str, Any] = Body(default={}),
            _attr=attr, _attr_name=attr_name, _sig=sig,
            _type_hints=type_hints, _addr=addr, _cls=model_class,
        ):
            user = _get_user(request)
            # Build data payload from body params
            payload = _parse_method_args(_sig, _type_hints, data, request)
            payload['id'] = id

            response = await api_adapter.request(
                TX(
                    name=_attr_name, source=api_adapter.addr, target=_addr,
                    data=payload,
                    meta={'user': user, 'model_cls': _cls},
                ),
                timeout=30.0,
            )
            return _response_or_raise(response)
    else:
        @router.api_route(full_route, methods=methods, tags=[tag],
                          name=f"custom_{addr}_{attr_name}")
        async def custom_no_id(
            request: Request,
            data: Dict[str, Any] = Body(default={}),
            _attr=attr, _attr_name=attr_name, _sig=sig,
            _type_hints=type_hints, _addr=addr, _cls=model_class,
        ):
            user = _get_user(request)
            payload = _parse_method_args(_sig, _type_hints, data, request)

            response = await api_adapter.request(
                TX(
                    name=_attr_name, source=api_adapter.addr, target=_addr,
                    data=payload,
                    meta={'user': user, 'model_cls': _cls},
                ),
                timeout=30.0,
            )
            return _response_or_raise(response)


async def _sse_from_stream(adapter, tx):
    """Convert NetworkAdapter.stream() into SSE text lines."""
    async for chunk in adapter.stream(tx, timeout=120.0):
        if chunk.is_error:
            yield f"event: error\ndata: {json.dumps(chunk.data)}\n\n"
            return
        if chunk.meta.get('stream_end'):
            yield f"event: done\ndata: {json.dumps(chunk.data)}\n\n"
            return
        yield f"event: chunk\ndata: {json.dumps(chunk.data, default=str)}\n\n"


def _add_streaming_handler(
    router, api_adapter, model_class, attr, attr_name,
    full_route, methods, tag, is_instance_method, addr,
):
    """SSE route for streaming @expose_route methods (Level 3)."""
    from inspect import signature as get_sig
    from typing import get_type_hints
    sig = get_sig(attr)
    type_hints = get_type_hints(attr)

    if is_instance_method:
        @router.api_route(full_route, methods=methods, tags=[tag],
                          name=f"stream_{addr}_{attr_name}")
        async def stream_with_id(
            request: Request, id: int = Path(...),
            data: Dict[str, Any] = Body(default={}),
            _attr=attr, _attr_name=attr_name, _sig=sig,
            _type_hints=type_hints, _addr=addr, _cls=model_class,
        ):
            user = _get_user(request)
            payload = _parse_method_args(_sig, _type_hints, data, request)
            payload['id'] = id
            tx = TX(
                name=_attr_name, source=api_adapter.addr, target=_addr,
                data=payload,
                meta={'user': user, 'model_cls': _cls, 'stream': True},
            )
            return StreamingResponse(
                _sse_from_stream(api_adapter, tx),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
    else:
        @router.api_route(full_route, methods=methods, tags=[tag],
                          name=f"stream_{addr}_{attr_name}")
        async def stream_no_id(
            request: Request,
            data: Dict[str, Any] = Body(default={}),
            _attr=attr, _attr_name=attr_name, _sig=sig,
            _type_hints=type_hints, _addr=addr, _cls=model_class,
        ):
            user = _get_user(request)
            payload = _parse_method_args(_sig, _type_hints, data, request)
            tx = TX(
                name=_attr_name, source=api_adapter.addr, target=_addr,
                data=payload,
                meta={'user': user, 'model_cls': _cls, 'stream': True},
            )
            return StreamingResponse(
                _sse_from_stream(api_adapter, tx),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )


def _parse_method_args(sig, type_hints, data, request):
    """Parse method arguments from request body, matching routes_fastapi.py behavior."""
    payload = {}
    for name, param in sig.parameters.items():
        if name in ('self', 'cls', 'user'):
            continue
        param_type = type_hints.get(name, str)
        raw = data.get(name)
        if raw is None:
            continue
        try:
            if isinstance(param_type, type) and issubclass(param_type, BaseModel):
                payload[name] = (
                    param_type(**raw) if isinstance(raw, dict)
                    else param_type.model_validate(raw)
                )
            else:
                payload[name] = param_type(raw)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid field '{name}': {e}")

    # Inject user marker — handler_crud and custom handlers resolve this
    if 'user' in sig.parameters:
        user = _get_user(request)
        if user and user.get('user_id'):
            # Resolve full user instance if type hint is StorableMixin subclass
            from n3tx.core.models.storable_mixin import StorableMixin
            user_type = type_hints.get('user')
            if (isinstance(user_type, type)
                    and issubclass(user_type, StorableMixin)
                    and hasattr(user_type, 'get')):
                payload['user'] = user_type.get(user['user_id'])
            else:
                payload['user'] = user

    return payload
