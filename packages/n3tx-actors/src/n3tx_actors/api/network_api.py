"""Bridge generated FastAPI routes to actors through Matrix and TX.

API: NetworkAPI and create_api_routes provide schema, CRUD and action routes.
Flow: HTTP identity and model metadata accompany adapter requests through the
configured interceptors; list routes decode caller conditions into TX data.
Integration: register the adapter with Matrix, attach the auth interceptor,
and mount create_api_routes(api, registered_models) on the application."""

import json
import logging
from inspect import signature
from typing import Any, Dict, Type

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from n3tx_actors.tx import TX
from n3tx_actors.api.network_adapter import NetworkAdapter
from n3tx_core.models.storable_mixin import StorableMixin

logger = logging.getLogger('n3tx.network.api')

_SSE_FLUSH_PADDING = ':' + (' ' * 2048) + '\n'


def _sse_frame(event: str, data: Any) -> str:
    """Serialize an SSE frame with padding against intermediary buffering."""
    return (
        f"{_SSE_FLUSH_PADDING}"
        f"event: {event}\n"
        f"data: {json.dumps(data, default=str)}\n\n"
    )


class NetworkAPI(NetworkAdapter, auto_register=False):
    """HTTP API adapter. Bridges FastAPI routes to Matrix via TX messaging."""

    def __init__(self, **kwargs):
        """Initialize the adapter with its default API address."""
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


def _read_data(id: int, populate: str | None, depth: int | None) -> dict:
    """Build the common read payload for table and class-name get routes."""
    data = {'id': id}
    if populate is not None:
        data['populate'] = populate
    if depth is not None:
        data['depth'] = depth
    return data


def create_api_routes(api_adapter: NetworkAPI, models_dict: dict):
    """Build generated CRUD and custom-action routes through the TX adapter."""
    from n3tx_core.utils.typer import flatten_refs

    router = APIRouter()
    # 1. Register utility identity independently of model dispatch.

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

    # 2. Register each model's schema, CRUD, and declared action routes.
    for model_name, model_class in models_dict.items():
        is_storable = issubclass(model_class, StorableMixin)
        tag = model_class.__tablename__.capitalize()
        endpoint_base = f"/{model_name}"

        # Schema route: GET /{ClassName}
        _register_schema_route(router, api_adapter, model_class, tag)

        # Optional view/HTML routes owned by model capability mixins.
        # This keeps n3tx-actors package-neutral: ViewableMixin lives in
        # n3tx-ui, but actor routing can delegate to any model capability that
        # exposes this small protocol hook.
        register_view_routes = getattr(
            model_class, 'register_view_routes', None
        )
        if callable(register_view_routes):
            register_view_routes(router, tag=tag)

        # Optional model capabilities can mount package-owned API routes while
        # keeping actor routing free of hard imports. n3tx-files uses this for
        # multipart upload and binary download routes that cannot round-trip as
        # JSON TX payloads.
        register_extra_routes = getattr(
            model_class, 'register_extra_routes', None
        )
        if callable(register_extra_routes):
            register_extra_routes(router, tag=tag)

        # CRUD routes
        if is_storable:
            _register_class_read_mirror(router, api_adapter, model_class, tag)
            _register_crud_routes(
                router, api_adapter, model_class, endpoint_base, tag,
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
        """Return the model schema or requested scaffold source."""
        if scaffold:
            from fastapi.responses import PlainTextResponse
            from n3tx_core.utils.scaffold import scaffold_single
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


def _register_class_read_mirror(router, api_adapter, model_class, tag):
    """GET /{ClassName}/{id:int} -> actor get TX to table-name address."""
    class_name = model_class.__name__
    addr = model_class.__tablename__

    @router.get(
        f"/{class_name}/{{id:int}}", tags=[tag],
        name=f"get_{addr}_class",
    )
    async def get_instance_by_class(
        request: Request,
        id: int,
        populate: str = Query(default=None),
        depth: int = Query(default=None, ge=0, le=3),
        _addr=addr, _cls=model_class,
    ):
        """Fetch one model instance through its class-name route."""
        user = _get_user(request)
        response = await api_adapter.request(
            TX(
                name='get', source=api_adapter.addr, target=_addr,
                data=_read_data(id, populate, depth),
                meta={'user': user, 'model_cls': _cls},
            ),
            timeout=30.0,
        )
        return _response_or_raise(response)


def _register_crud_routes(
    router, api_adapter, model_class, endpoint_base, tag,
):
    """Register POST, GET (list), GET (item), PUT, DELETE routes."""
    addr = model_class.__tablename__
    param_class = model_class
    # 1. Register collection creation and inject protected owner identity.

    @router.post(endpoint_base, tags=[tag], status_code=201,
                 name=f"create_{addr}")
    async def create_instance(
        request: Request,
        data: param_class,
        _addr=addr, _cls=model_class, _param_cls=param_class,
    ):
        """Create an entity through the model actor."""
        from n3tx_core.utils.typer import flatten_refs
        user = _get_user(request)
        data_dict = flatten_refs(data)

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

    # 2. Register collection listing and forward supplied query options.
    @router.get(endpoint_base, tags=[tag], name=f"list_{addr}")
    async def list_instances(
        request: Request,
        limit: int = Query(default=None, ge=1, le=100),
        offset: int = Query(default=None, ge=0),
        populate: str = Query(default=None),
        depth: int = Query(default=None, ge=0, le=3),
        order_asc: str | None = Query(default=None),
        order_desc: str | None = Query(default=None),
        where: str | None = Query(default=None),
        _addr=addr, _cls=model_class,
    ):
        """List entities through the model actor."""
        user = _get_user(request)
        data = {}
        if limit is not None:
            data['limit'] = limit
        if offset is not None:
            data['offset'] = offset
        if populate is not None:
            data['populate'] = populate
        if depth is not None:
            data['depth'] = depth
        if order_asc is not None:
            data['order_asc'] = order_asc
        if order_desc is not None:
            data['order_desc'] = order_desc
        if where is not None:
            try:
                data['where'] = json.loads(where)
                if not isinstance(data['where'], dict):
                    raise ValueError('where must be an object')
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))

        response = await api_adapter.request(
            TX(
                name='list', source=api_adapter.addr, target=_addr,
                data=data,
                meta={'user': user, 'model_cls': _cls},
            ),
            timeout=30.0,
        )
        result = _response_or_raise(response)

        return result

    # 3. Register item reads and share the common populate payload.
    @router.get(f"{endpoint_base}/{{id:int}}", tags=[tag],
                name=f"get_{addr}")
    async def get_instance(
        request: Request,
        id: int,
        populate: str = Query(default=None),
        depth: int = Query(default=None, ge=0, le=3),
        _addr=addr, _cls=model_class,
    ):
        """Fetch one entity through the model actor."""
        user = _get_user(request)
        response = await api_adapter.request(
            TX(
                name='get', source=api_adapter.addr, target=_addr,
                data=_read_data(id, populate, depth),
                meta={'user': user, 'model_cls': _cls},
            ),
            timeout=30.0,
        )
        return _response_or_raise(response)

    # 4. Register updates after canonicalizing and stripping protected fields.
    @router.put(f"{endpoint_base}/{{id:int}}", tags=[tag],
                name=f"update_{addr}")
    async def update_instance(
        request: Request,
        id: int,
        data: Dict[str, Any] = Body(...),
        _addr=addr, _cls=model_class, _param_cls=param_class,
    ):
        """Update an entity through the model actor."""
        user = _get_user(request)
        try:
            data_dict = _cls._canonical_update_patch(dict(data))
        except ValueError as exc:
            logger.warning(
                "Rejected %s update ID=%s fields=%s: %s",
                _cls.__name__, id, sorted(data), exc,
            )
            raise HTTPException(status_code=400, detail=str(exc))
        data_dict.pop('id', None)

        # Strip protected fields on update.
        protected = (
            getattr(_cls, '__protected_fields__', None)
            or getattr(_param_cls, '__protected_fields__', set())
        )
        for field in protected:
            data_dict.pop(field, None)

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

    # 5. Register deletion and preserve the actor authorization boundary.
    @router.delete(f"{endpoint_base}/{{id:int}}", tags=[tag],
                   name=f"delete_{addr}")
    async def delete_instance(
        request: Request,
        id: int,
        _addr=addr, _cls=model_class,
    ):
        """Delete an entity through the model actor."""
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

    class_base = f"/{model_class.__name__}"
    router.post(
        class_base, tags=[tag], status_code=201,
        name=f"create_{addr}_class",
    )(create_instance)
    router.get(
        f"{class_base}/_", tags=[tag],
        name=f"list_{addr}_class",
    )(list_instances)
    router.put(
        f"{class_base}/{{id:int}}", tags=[tag],
        name=f"update_{addr}_class",
    )(update_instance)
    router.delete(
        f"{class_base}/{{id:int}}", tags=[tag],
        name=f"delete_{addr}_class",
    )(delete_instance)


def _register_custom_routes(
    router, api_adapter, model_class, endpoint_base, tag,
):
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

        if is_instance_method:
            class_route = f"/{model_class.__name__}/{{id:int}}{route}"
        else:
            class_route = f"/{model_class.__name__}{route}"
        if is_stream:
            _add_streaming_handler(
                router, api_adapter, model_class, attr, attr_name,
                class_route, methods, tag, is_instance_method, addr,
            )
        else:
            _add_custom_handler(
                router, api_adapter, model_class, attr, attr_name,
                class_route, methods, tag, is_instance_method, addr,
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
            """Dispatch an instance action using its path ID."""
            user = _get_user(request)
            # Build data payload from body params
            payload = await _parse_method_args(_sig, _type_hints, data, request)
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
            """Dispatch a class action without an instance ID."""
            user = _get_user(request)
            payload = await _parse_method_args(_sig, _type_hints, data, request)

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
    """Convert NetworkAdapter.stream() into SSE text lines.

    Serialize complete TX envelopes with routing, metadata, and chunk data."""
    from dataclasses import asdict

    async for chunk in adapter.stream(tx, timeout=120.0):
        tx_dict = asdict(chunk)
        if chunk.is_error:
            yield _sse_frame('error', tx_dict)
            return
        if chunk.meta.get('stream_end'):
            yield _sse_frame('done', tx_dict)
            return
        yield _sse_frame('chunk', tx_dict)


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
            request: Request,
            id: int = Path(...),
            data: Dict[str, Any] = Body(default={}),
            _attr=attr, _attr_name=attr_name, _sig=sig,
            _type_hints=type_hints, _addr=addr, _cls=model_class,
        ):
            """Dispatch an instance action and return its SSE stream."""
            user = _get_user(request)
            payload = await _parse_method_args(_sig, _type_hints, data, request)
            payload['id'] = id
            tx = TX(
                name=_attr_name, source=api_adapter.addr, target=_addr,
                data=payload,
                meta={'user': user, 'model_cls': _cls, 'stream': True},
            )
            return StreamingResponse(
                _sse_from_stream(api_adapter, tx),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "X-Accel-Buffering": "no",
                    "X-Content-Type-Options": "nosniff",
                },
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
            """Dispatch a class action and return its SSE stream."""
            user = _get_user(request)
            payload = await _parse_method_args(_sig, _type_hints, data, request)
            tx = TX(
                name=_attr_name, source=api_adapter.addr, target=_addr,
                data=payload,
                meta={'user': user, 'model_cls': _cls, 'stream': True},
            )
            return StreamingResponse(
                _sse_from_stream(api_adapter, tx),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "X-Accel-Buffering": "no",
                    "X-Content-Type-Options": "nosniff",
                },
            )


async def _parse_method_args(sig, type_hints, data, request):
    """Parse method arguments from request body or query params.

    For GET, query values are fallbacks and body values take precedence."""
    # Merge query params as fallback (body values override query params)
    query_params = dict(request.query_params) if request.query_params else {}
    merged = {**query_params, **data}

    payload = {}
    for name, param in sig.parameters.items():
        if name in ('self', 'cls', 'user'):
            continue
        param_type = type_hints.get(name, str)
        raw = merged.get(name)
        if raw is None:
            continue
        try:
            from n3tx_core.utils.materialize import materialize_arg
            raw = await materialize_arg(
                raw,
                param_type,
                user=_get_user(request),
                context={'param': name},
            )
            if (isinstance(param_type, type)
                    and issubclass(param_type, BaseModel)):
                payload[name] = (
                    raw if isinstance(raw, param_type)
                    else param_type(**raw) if isinstance(raw, dict)
                    else param_type.model_validate(raw)
                )
            else:
                payload[name] = param_type(raw)
        except Exception as e:
            from n3tx_core.utils.erroring import MethodError
            if isinstance(e, MethodError):
                raise HTTPException(status_code=e.status_code, detail=e.message)
            raise HTTPException(
                status_code=422,
                detail=f"Invalid field '{name}': {e}",
            )

    # Inject user marker — handler_crud and custom handlers resolve this
    if 'user' in sig.parameters:
        user = _get_user(request)
        if user and user.get('user_id'):
            # Resolve full user instance if type hint is StorableMixin subclass
            from n3tx_core.models.storable_mixin import StorableMixin
            user_type = type_hints.get('user')
            if (isinstance(user_type, type)
                    and issubclass(user_type, StorableMixin)
                    and hasattr(user_type, 'get')):
                payload['user'] = user_type.get(user['user_id'])
            else:
                payload['user'] = user

    return payload

# Changelog
# - 2026-11-02: Add optional order_asc/order_desc HTTP query args.
# - 2026-11-02: Forward decoded where objects through native LIST messages.
# - 2026-11-10: Restore native HTTP list query forwarding from 123d825.
