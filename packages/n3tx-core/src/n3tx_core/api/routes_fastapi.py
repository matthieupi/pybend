"""Generate direct FastAPI CRUD and model-action authorization boundaries.

API: register_routes installs model CRUD/schema and exposed-action factories.
Collection handlers decode native where/ordering inside resolver SQL policy.
Model and storage layers validate fields and own selection/counting; action
handlers retain caller injection and the opt-in threaded dispatch bridge."""

import asyncio
import inspect
import json
import logging
from inspect import signature
from typing import Any, Dict, ForwardRef, List, get_args, get_origin
from typing import get_type_hints

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError

from n3tx_core import config
from n3tx_core.models.storable_mixin import StorableMixin
from n3tx_core.utils.erroring import get_traceback_info, MethodError
from n3tx_core.utils.registrar import registered_models
from n3tx_core.utils.typer import flatten_refs
from n3tx_core.utils.populate import parse_populate
from n3tx_core.utils.materialize import materialize_arg
from n3tx_core.utils.decorators import exposed_method_info
from n3tx_core.authorize import AccessContext, DefaultResolver, AccessDenied

logger = logging.getLogger('n3tx.api')

router = APIRouter()
_resolver = DefaultResolver()
_SSE_FLUSH_PADDING = ':' + (' ' * 2048) + '\n'


def _sse_frame(event: str, data: Any) -> str:
    """Serialize an SSE frame with padding to discourage transport buffering."""
    return (
        f"{_SSE_FLUSH_PADDING}"
        f"event: {event}\n"
        f"data: {json.dumps(data, default=str)}\n\n"
    )


def _sse_headers() -> dict:
    """Return headers that discourage SSE caching and proxy buffering."""
    return {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "X-Content-Type-Options": "nosniff",
    }


def _get_user(request: Request) -> dict:
    """Extract user dict from request.state, set by JWTAuthMiddleware."""
    return getattr(request.state, 'user', {}) or {}


def _build_context(request, model_class, action, resource=None, patch=None):
    """Build policy input from trusted identity and optional effective patch."""
    return AccessContext(
        user=_get_user(request),
        action=action,
        model_class=model_class,
        resource=resource,
        patch=patch,
    )


def _serialize(instance):
    """Serialize a model instance for API response.

    model_response() runs the dump pipeline which includes the 'populate'
    stage — any eager-loaded data from _populate_fields() is overlaid
    automatically."""
    return instance.model_response()


def register_route(path, fn, method='GET'):
    """Register a handler for a supported HTTP method, or raise ValueError."""
    # 0. Select the native router decorator for the requested verb.
    if method == 'GET':
        router.get(path)(fn)
    elif method == 'POST':
        router.post(path)(fn)
    elif method == 'PUT':
        router.put(path)(fn)
    elif method == 'DELETE':
        router.delete(path)(fn)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")


# --- Route factories ---

def make_create_instance(model_class):
    """Build a create handler with policy and trusted ownership injection."""

    async def create_instance(
        request: Request, data: model_class,
    ) -> model_class:
        """Authorize validated input, inject ownership, and persist a model."""
        # 0. Authorize creation using middleware identity, not request fields.
        ctx = _build_context(request, model_class, "create")
        try:
            _resolver.authorize(ctx)
        except AccessDenied as e:
            raise HTTPException(status_code=403, detail=str(e))
        # 1. Flatten references and establish protected ownership before create.
        logger.info("Creating %s", model_class.__name__)
        try:
            data_dict = flatten_refs(data)

            # Auto-inject user_owner from JWT on create
            protected = (
                getattr(model_class, '__protected_fields__', None) or set()
            )
            if 'user_owner' in protected:
                user = _get_user(request)
                if user and user.get('user_id'):
                    data_dict['user_owner'] = user['user_id']

            instance = model_class(**data_dict)
            result = model_class.create(instance)
            return result.model_response() if result else result
        except Exception as e:
            logger.error(
                "Failed to create %s: %s", model_class.__name__, e,
                exc_info=True,
            )
            detail = get_traceback_info(e) if config.DEBUG else "Bad request"
            raise HTTPException(status_code=400, detail=detail)

    return create_instance


def make_get_all_instances(model_class):
    """Build a list handler using policy SQL filters and population options."""

    async def list_all_instances(
        request: Request,
        limit: int = Query(default=None, ge=1, le=100),
        offset: int = Query(default=None, ge=0),
        populate: str = Query(default=None),
        depth: int = Query(default=None, ge=0, le=3),
        order_asc: str | None = Query(default=None),
        order_desc: str | None = Query(default=None),
        where: str | None = Query(default=None),
    ):
        """Apply the SQL policy and serialize a collection or paginated page."""
        # 0. Resolve list policy as a SQL filter, not member authorization.
        ctx = _build_context(request, model_class, "list")
        try:
            auth_filter = _resolver.sql_filter_for(ctx)
        except AccessDenied as e:
            raise HTTPException(status_code=403, detail=str(e))
        # 1. Fetch the requested population and page under the SQL restriction.
        pop_spec = parse_populate(populate, depth)
        list_kwargs = {
            'sql_filter': auth_filter, 'limit': limit, 'offset': offset,
            'populate': pop_spec,
        }
        if order_asc is not None:
            list_kwargs['order_asc'] = order_asc
        if order_desc is not None:
            list_kwargs['order_desc'] = order_desc
        try:
            if where is not None:
                list_kwargs['where'] = json.loads(where)
                if not isinstance(list_kwargs['where'], dict):
                    raise ValueError('where must be an object')
            result = model_class.list(**list_kwargs)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        # 2. Preserve paginated and unpaginated response shapes.
        if isinstance(result, dict) and 'data' in result:
            return {
                'data': [_serialize(r) for r in result['data']],
                'meta': result['meta'],
            }

        # Unpaginated response: plain array (backward compatible)
        return [_serialize(r) for r in result]

    return list_all_instances


def make_get_schema(model_class):
    """Build a public schema or optional scaffold-source handler."""

    async def get_model_schema(scaffold: str = None):
        """Return schema metadata, or generate a requested scaffold kind."""
        # 0. Generate optional scaffold source using the authoritative schema.
        if scaffold:
            from fastapi.responses import PlainTextResponse
            from n3tx_core.utils.scaffold import scaffold_single
            try:
                source = scaffold_single(
                    model_class.__name__, kind=scaffold,
                    schema=model_class.schema(),
                )
                return PlainTextResponse(source, media_type='text/plain')
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        # 1. Otherwise expose model metadata without a record-policy check.
        logger.debug("Fetching schema for %s", model_class.__name__)
        return model_class.schema()
    return get_model_schema


def make_get_instance(model_class):
    """Build a populated member read with resource-level authorization."""

    async def read_instance(
        request: Request,
        id: int,
        populate: str = Query(default=None),
        depth: int = Query(default=None, ge=0, le=3),
    ):
        """Load and authorize an existing record before serializing it."""
        # 0. Load the requested record and optional populated relationships.
        logger.debug("Reading %s ID=%s", model_class.__name__, id)
        pop_spec = parse_populate(populate, depth)
        instance = model_class.get(id, populate=pop_spec)
        if not instance:
            raise HTTPException(status_code=404, detail="Not found")
        # 1. Authorize the loaded resource before returning its data.
        ctx = _build_context(request, model_class, "read", resource=instance)
        try:
            _resolver.authorize(ctx)
        except AccessDenied as e:
            raise HTTPException(status_code=403, detail=str(e))
        return _serialize(instance)
    return read_instance


def make_update_instance(model_class):
    """Build a partial-update handler whose policy sees effective input keys."""

    async def update_instance(
        request: Request,
        id: int,
        data: Dict[str, Any] = Body(...),
    ) -> model_class:
        """Authorize a canonical patch, then validate and persist its fields.

        Aliases and metadata are handled before id/protected-field stripping.
        Effective keys must be stable under the model's canonicalizer so its
        second pass cannot redirect an authorized field into another column.
        Unknown keys remain visible to policy. Empty patches are authorized
        normally and remain no-ops when allowed. Values are not yet coerced by
        model validation; the context snapshot cannot mutate the payload."""
        # 0. Load the resource and prepare the effective patch before policy.
        instance = model_class.get(id)
        if not instance:
            raise HTTPException(status_code=404, detail="Not found")
        data_dict = dict(data)
        try:
            data_dict = model_class._canonical_update_patch(data_dict)
            data_dict.pop('id', None)
            # Strip backend-owned fields that cannot be modified via API
            protected = (
                getattr(model_class, '__protected_fields__', None) or set()
            )
            for field in protected:
                data_dict.pop(field, None)
            # The model canonicalizes again; reject aliases that change keys.
            if model_class._canonical_update_patch(data_dict) != data_dict:
                raise ValueError(
                    "Update aliases must resolve to stable canonical fields"
                )
        except ValidationError as e:
            detail = e.errors(include_url=False, include_input=False)
            raise HTTPException(status_code=422, detail=detail)
        except ValueError as e:
            logger.warning(
                "Rejected %s update ID=%s fields=%s: %s",
                model_class.__name__, id, sorted(data_dict), e,
            )
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(
                "Failed to update %s ID=%s: %s", model_class.__name__, id, e,
                exc_info=True,
            )
            detail = str(e) if config.DEBUG else "Bad request"
            raise HTTPException(status_code=400, detail=detail)
        # 1. Authorize the same effective patch passed to the model boundary.
        ctx = _build_context(
            request, model_class, "update", resource=instance, patch=data_dict,
        )
        try:
            _resolver.authorize(ctx)
        except AccessDenied as e:
            raise HTTPException(status_code=403, detail=str(e))
        # 2. Preserve merged-state validation and persistence semantics.
        try:
            logger.info("Updating %s ID=%s", model_class.__name__, id)
            updated = instance.update(data_dict)
            return updated.model_response()
        except ValidationError as e:
            detail = e.errors(include_url=False, include_input=False)
            raise HTTPException(status_code=422, detail=detail)
        except ValueError as e:
            logger.warning(
                "Rejected %s update ID=%s fields=%s: %s",
                model_class.__name__, id, sorted(data_dict), e,
            )
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(
                "Failed to update %s ID=%s: %s", model_class.__name__, id, e,
                exc_info=True,
            )
            detail = str(e) if config.DEBUG else "Bad request"
            raise HTTPException(status_code=400, detail=detail)
    return update_instance


def make_delete_instance(model_class):
    """Build a delete handler with resource-level authorization."""

    async def delete_instance(request: Request, id: int) -> Dict[str, str]:
        """Authorize an existing record and delete it through the model."""
        # 0. Resolve the target before evaluating its delete policy.
        instance = model_class.get(id)
        if not instance:
            raise HTTPException(status_code=404, detail="Not found")
        ctx = _build_context(request, model_class, "delete", resource=instance)
        try:
            _resolver.authorize(ctx)
        except AccessDenied as e:
            raise HTTPException(status_code=403, detail=str(e))
        # 1. Delegate deletion and preserve the acknowledgment contract.
        logger.info("Deleting %s ID=%s", model_class.__name__, id)
        model_class.delete(id)
        return {"message": "Deleted successfully"}
    return delete_instance


def _resolve_custom_return_type(attr, model_class):
    """Resolve a custom route return annotation for FastAPI response_model.

    Model files commonly use ``from __future__ import annotations`` so return
    types such as ``-> Comment`` arrive as strings. FastAPI cannot validate an
    unresolved ForwardRef at request time, so prefer ``get_type_hints()`` which
    resolves importable model annotations in the defining module's namespace."""
    # 0. Resolve annotations without requiring optional forward references.
    annotations = getattr(attr, '__annotations__', {}) or {}
    try:
        type_hints = get_type_hints(attr)
    except (NameError, TypeError):
        type_hints = {}
    return_type = type_hints.get('return', annotations.get('return', None))
    # 1. Preserve fallback handling of unresolved model self-references.
    if isinstance(return_type, (str, ForwardRef)):
        type_str = (
            str(return_type).replace('ForwardRef(', '').replace(')', '')
            .replace("'", "")
        )
        if type_str == model_class.__name__:
            return model_class
        if type_str.startswith(f'List[{model_class.__name__}'):
            return List[model_class]
    elif get_origin(return_type) is list:
        args = get_args(return_type)
        if args and args[0] == model_class.__name__:
            return List[model_class]

    return return_type


def _resolve_user(type_hint, request):
    """Bridge auth-layer identity to model-layer entity.

    The auth system (middleware / JWT) speaks plain dicts:
        {"user_id": int, "email": str, "role": str}

    Model methods may need the full User model instance.
    Resolution:
      - storable model type_hint (e.g. User): fetch via .get(user_id)
      - type_hint is dict or unrecognized → return the raw JWT dict as-is
      - no authenticated user: return None"""
    # 0. Resolve only the identity supplied by authentication middleware.
    user_dict = _get_user(request)
    if not user_dict or not user_dict.get('user_id'):
        return None
    # 1. Materialize a model only when the annotation requests a storable type.
    if (isinstance(type_hint, type)
            and issubclass(type_hint, StorableMixin)
            and hasattr(type_hint, 'get')):
        return type_hint.get(user_dict['user_id'])
    return user_dict


def make_custom_post(attr, model_class, route_path):
    """Build an action handler with policy and reserved caller injection."""
    # 0. Inspect the callable and its explicit action-policy declaration.
    sig = signature(attr)
    type_hints = get_type_hints(attr)

    is_instance_method = 'self' in sig.parameters
    is_class_method = 'cls' in sig.parameters
    is_static_method = isinstance(attr, staticmethod)

    endpoint_info = getattr(attr, '__endpoint__', {})
    custom_access = endpoint_info.get('access', None)

    def _check_access(request, model_class, action, resource=None):
        """Authorize the action without treating its body as a CRUD patch."""
        # 0. Prefer explicit method policy over model action fallback.
        ctx = _build_context(request, model_class, action, resource=resource)
        try:
            if custom_access:
                if not custom_access.evaluate(ctx):
                    raise AccessDenied(
                        action=action, model=model_class.__name__,
                        user_id=ctx.user_id,
                    )
            else:
                _resolver.authorize(ctx)
        except AccessDenied as e:
            raise HTTPException(status_code=403, detail=str(e))

    async def post_with_id(
        request: Request,
        id: int = Path(..., description=f"{model_class.__name__} ID"),
        data: Dict[str, Any] = Body(default={}),
    ):
        """Authorize an instance action and adapt its inputs and result."""
        # 0. Load and authorize the action target before materializing inputs.
        instance = model_class.get(id)
        if not instance:
            raise HTTPException(status_code=404, detail="Not found")
        _check_access(request, model_class, attr.__name__, resource=instance)
        # 1. Materialize declared inputs and inject trusted caller identity.
        parsed_args = {}
        for name, param in sig.parameters.items():
            if name in ('self', 'cls', 'user'):
                continue
            param_type = type_hints.get(name, str)
            raw = data.get(name)
            if raw is None:
                raise HTTPException(
                    status_code=400, detail=f"Missing field: {name}",
                )
            try:
                raw = await materialize_arg(
                    raw, param_type, user=_get_user(request),
                    context={'route': route_path, 'param': name},
                )
                if (
                    isinstance(param_type, type)
                    and issubclass(param_type, BaseModel)
                ):
                    parsed_args[name] = (
                        raw if isinstance(raw, param_type)
                        else param_type(**raw) if isinstance(raw, dict)
                        else param_type.parse_obj(raw)
                    )
                else:
                    parsed_args[name] = param_type(raw)
            except Exception as e:
                if isinstance(e, MethodError):
                    raise HTTPException(
                        status_code=e.status_code, detail=e.message,
                    )
                raise HTTPException(
                    status_code=422, detail=f"Invalid field '{name}': {e}",
                )

        if 'user' in sig.parameters:
            user = _resolve_user(type_hints.get('user'), request)
            if user is not None:
                parsed_args['user'] = user
        # 2. Invoke the action and adapt async generators to SSE responses.
        try:
            if attr.__name__ in getattr(model_class, '__thread_roots__', ()):
                from n3tx_agents.threaded_mixin import invoke_threaded
                response = await invoke_threaded(
                    instance, attr.__name__, parsed_args,
                    user=_get_user(request),
                )
                if response.is_error:
                    raise MethodError(
                        response.data.get('message', 'Action failed'),
                        response.data.get('code', 500),
                    )
                return response.data
            result = attr(instance, **parsed_args)
            if asyncio.iscoroutine(result):
                result = await result
            if inspect.isasyncgen(result):

                async def sse(_gen=result):
                    """Stream instance-action chunks and a completion frame."""
                    # 0. Frame each chunk and signal normal completion.
                    async for chunk in _gen:
                        data = (
                            chunk if isinstance(chunk, dict)
                            else {'chunk': chunk}
                        )
                        yield _sse_frame('chunk', data)
                    yield _sse_frame('done', {})
                return StreamingResponse(
                    sse(), media_type="text/event-stream",
                    headers=_sse_headers(),
                )
            return result
        except MethodError as e:
            raise HTTPException(status_code=e.status_code, detail=e.message)

    async def post_no_id(
        request: Request,
        data: Dict[str, Any] = Body(default={}),
    ):
        """Authorize a class/static action and adapt its inputs and result."""
        # 0. Authorize the action without an instance resource.
        _check_access(request, model_class, attr.__name__)
        # 1. Materialize declared inputs and inject trusted caller identity.
        parsed_args = {}
        for name, param in sig.parameters.items():
            if name in ('self', 'cls', 'user'):
                continue
            param_type = type_hints.get(name, str)
            raw = data.get(name)
            if raw is None:
                raise HTTPException(
                    status_code=400, detail=f"Missing field: {name}",
                )
            try:
                raw = await materialize_arg(
                    raw, param_type, user=_get_user(request),
                    context={'route': route_path, 'param': name},
                )
                if (
                    isinstance(param_type, type)
                    and issubclass(param_type, BaseModel)
                ):
                    parsed_args[name] = (
                        raw if isinstance(raw, param_type)
                        else param_type(**raw) if isinstance(raw, dict)
                        else param_type.parse_obj(raw)
                    )
                else:
                    parsed_args[name] = param_type(raw)
            except Exception as e:
                if isinstance(e, MethodError):
                    raise HTTPException(
                        status_code=e.status_code, detail=e.message,
                    )
                raise HTTPException(
                    status_code=422, detail=f"Invalid field '{name}': {e}",
                )

        if 'user' in sig.parameters:
            user = _resolve_user(type_hints.get('user'), request)
            if user is not None:
                parsed_args['user'] = user
        # 2. Invoke the action and adapt async generators to SSE responses.
        try:
            if is_class_method:
                result = attr(model_class, **parsed_args)
            else:
                result = attr(**parsed_args)
            if asyncio.iscoroutine(result):
                result = await result
            if inspect.isasyncgen(result):

                async def sse(_gen=result):
                    """Stream class-action chunks and a completion frame."""
                    # 0. Frame each chunk and signal normal completion.
                    async for chunk in _gen:
                        data = (
                            chunk if isinstance(chunk, dict)
                            else {'chunk': chunk}
                        )
                        yield _sse_frame('chunk', data)
                    yield _sse_frame('done', {})
                return StreamingResponse(
                    sse(), media_type="text/event-stream",
                    headers=_sse_headers(),
                )
            return result
        except MethodError as e:
            raise HTTPException(status_code=e.status_code, detail=e.message)

    return post_with_id if is_instance_method else post_no_id


@router.get("/auth/me", tags=["Auth"])
async def auth_me(request: Request):
    """Return the current user's identity from the JWT token."""
    # 0. Require authenticated middleware identity before returning claims.
    user = _get_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "role": user.get("role", "user"),
    }


def register_routes():
    """Register schema, capability, CRUD and action routes for known models."""
    # 0. Register each model's public schema and optional capability routes.
    for model_name, model_class in registered_models.items():
        # Extract model metadata
        logger.info(
            "Registering routes for model: %s (%s)",
            model_name, model_class.__name__,
        )
        model_title = model_name.capitalize()
        is_storable = issubclass(model_class, StorableMixin)
        tag = model_class.__tablename__.capitalize()
        endpoint_base = f"/{model_name}"

        # Register basic GET route for schema
        router.get(f"/{model_class.__name__}", tags=[tag])(
            make_get_schema(model_class)
        )

        # Register view/HTML routes owned by optional view-capability mixins.
        # This keeps n3tx-core package-neutral: ViewableMixin lives in n3tx-ui,
        # but any model capability can expose this small registration hook.
        register_view_routes = getattr(
            model_class, 'register_view_routes', None,
        )
        if callable(register_view_routes):
            register_view_routes(router, tag=tag)

        # Register package-owned API routes for optional capabilities.
        # This mirrors the view-route hook while staying package-neutral:
        # n3tx-core does not import optional packages such as n3tx-files.
        register_extra_routes = getattr(
            model_class, 'register_extra_routes', None,
        )
        if callable(register_extra_routes):
            register_extra_routes(router, tag=tag)
        # 1. Share CRUD handlers between table-name and class-name routes.
        if is_storable:
            create_instance = make_create_instance(model_class)
            list_instances = make_get_all_instances(model_class)
            read_instance = make_get_instance(model_class)
            update_instance = make_update_instance(model_class)
            delete_instance = make_delete_instance(model_class)

            router.post(endpoint_base, tags=[tag], status_code=201)(
                create_instance
            )
            router.get(endpoint_base, tags=[tag])(list_instances)
            router.get(f"{endpoint_base}/{{id:int}}", tags=[tag])(read_instance)
            # Storable class-name read mirror reuses the table-name read
            # handler so auth, populate, 404, and serialization behavior stay
            # identical.
            router.get(f"/{model_class.__name__}/{{id:int}}", tags=[tag])(
                read_instance
            )
            router.put(f"{endpoint_base}/{{id:int}}", tags=[tag])(
                update_instance
            )
            router.delete(f"{endpoint_base}/{{id:int}}", tags=[tag])(
                delete_instance
            )

            class_base = f"/{model_class.__name__}"
            router.post(class_base, tags=[tag], status_code=201)(
                create_instance
            )
            router.get(f"{class_base}/_", tags=[tag])(list_instances)
            router.put(f"{class_base}/{{id:int}}", tags=[tag])(update_instance)
            router.delete(f"{class_base}/{{id:int}}", tags=[tag])(
                delete_instance
            )
        # 2. Register declared actions with mirrored paths and return contracts.
        for attr_name in dir(model_class):
            exposed = exposed_method_info(model_class, attr_name)
            if exposed is not None:
                attr = exposed.bound
                # Instance methods need a resource ID in their route.
                route_info = exposed.endpoint
                route = route_info['route']
                methods = route_info['methods']
                is_instance_method = exposed.requires_instance
                if is_instance_method:
                    full_route = f"{endpoint_base}/{{id:int}}{route}"
                else:
                    full_route = f"{endpoint_base}{route}"

                return_type = _resolve_custom_return_type(attr, model_class)

                handler = make_custom_post(attr, model_class, full_route)
                # DEBUG wraps results in a dict, not the declared return type.
                resp_model = (
                    None if config.DEBUG
                    else (return_type if return_type else None)
                )
                router.add_api_route(
                    full_route, handler,
                    methods=methods, tags=[model_title], name=attr.__name__,
                    response_model=resp_model,
                )
                if is_instance_method:
                    class_route = f"/{model_class.__name__}/{{id:int}}{route}"
                else:
                    class_route = f"/{model_class.__name__}{route}"
                router.add_api_route(
                    class_route, handler,
                    methods=methods, tags=[model_title],
                    name=f"{attr.__name__}_class",
                    response_model=resp_model,
                )
# Expose router to be used in FastAPI app
__all__ = ["router", "register_routes", "register_route"]


# Changelog
# - 2026-11-10: Import native collection where/ordering and HTTP 422 mapping;
#   retain current custom-action caller injection and threaded dispatch.
# - 2026-10-31: Bridge opt-in instance actions after native HTTP authorization.
# - 2026-10-26: Authorize canonical effective PUT patches before model updates;
#   reject unstable alias mappings, document operations and standardize layout.
# - 2026-10-31: Map initial CRUD get/list PermissionError to a constant 403.
# - 2026-10-31: Remove task-added initial-read exception mapping; retain native
#   CRUD policy evaluation and pre-existing effective-patch authorization.
