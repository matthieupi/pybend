import logging
import traceback

from fastapi import APIRouter, Request, HTTPException, status, Body, Path, Query
from typing import Dict, Type, Any, List
from pybend.core import config
from pybend.core.models.storable_mixin import StorableMixin
from pybend.core.utils.erroring import get_traceback_info
from pybend.core.utils.registrar import registered_models, join_models
from pybend.core.utils.typer import flatten_refs
from pybend.core.utils.populate import parse_populate
from pybend.core.authorize import AccessContext, DefaultResolver, AccessDenied

logger = logging.getLogger('pybend.api')

router = APIRouter()
_resolver = DefaultResolver()


def _get_user(request: Request) -> dict:
    """Extract user dict from request.state, set by JWTAuthMiddleware."""
    return getattr(request.state, 'user', {}) or {}


def _build_context(request, model_class, action, resource=None, parent_id=None):
    return AccessContext(
        user=_get_user(request),
        action=action,
        model_class=model_class,
        resource=resource,
        parent_id=parent_id,
    )

def _serialize(instance):
    """Serialize a model instance, overlaying any populated (eager-loaded) data."""
    data = instance.model_dump(response=True)
    populated = instance.__dict__.get('_populated')
    if populated:
        data.update(populated)
    return data


def register_route(path, fn, method='GET'):
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
    param_class = model_class.__parent__ if hasattr(model_class, '__parent__') else model_class

    async def create_instance(request: Request, data: param_class, parent_id: int = None) -> model_class:
        ctx = _build_context(request, model_class, "create", parent_id=parent_id)
        try:
            _resolver.authorize(ctx)
        except AccessDenied as e:
            raise HTTPException(status_code=403, detail=str(e))
        logger.info("Creating %s with parent_id=%s", model_class.__name__, parent_id)
        try:
            data_dict = flatten_refs(data)
            if parent_id:
                fk_field = f"{model_class.__owner__.__name__.lower()}_id"
                data_dict[fk_field] = parent_id

            # Auto-inject user_owner from JWT on create
            protected = getattr(model_class, '__protected_fields__', None) or \
                        getattr(param_class, '__protected_fields__', set())
            if 'user_owner' in protected:
                user = _get_user(request)
                if user and user.get('user_id'):
                    data_dict['user_owner'] = user['user_id']

            instance = model_class(**data_dict)
            result = model_class.create(instance)
            return result.model_dump(response=True) if result else result
        except Exception as e:
            logger.error("Failed to create %s: %s", model_class.__name__, e, exc_info=True)
            detail = get_traceback_info(e) if config.DEBUG else "Bad request"
            raise HTTPException(status_code=400, detail=detail)

    return create_instance


def make_get_all_instances(model_class):
    async def list_all_instances(
        request: Request,
        parent_id: int = None,
        limit: int = Query(default=None, ge=1, le=100),
        offset: int = Query(default=None, ge=0),
        populate: str = Query(default=None),
        depth: int = Query(default=None, ge=0, le=3),
    ):
        ctx = _build_context(request, model_class, "list", parent_id=parent_id)
        try:
            auth_filter = _resolver.sql_filter_for(ctx)
        except AccessDenied as e:
            raise HTTPException(status_code=403, detail=str(e))

        pop_spec = parse_populate(populate, depth)
        target_cls = model_class

        if parent_id:
            # Resolve join model based on registration
            for (parent_name, child_name), join_cls in join_models.items():
                if child_name == model_class.__name__:
                    target_cls = join_cls
                    break

        result = target_cls.list(sql_filter=auth_filter, limit=limit, offset=offset, populate=pop_spec)

        # Paginated response: {data: [...], meta: {...}}
        if isinstance(result, dict) and 'data' in result:
            items = result['data']
            if parent_id:
                fk_field = f"{target_cls.__owner__.__name__.lower()}_id"
                items = [r for r in items if getattr(r, fk_field, None) == parent_id]
            return {
                'data': [_serialize(r) for r in items],
                'meta': result['meta'],
            }

        # Unpaginated response: plain array (backward compatible)
        if parent_id:
            fk_field = f"{target_cls.__owner__.__name__.lower()}_id"
            return [_serialize(r) for r in result if getattr(r, fk_field, None) == parent_id]

        return [_serialize(r) for r in result]

    return list_all_instances


def make_collection_list(model_class):
    """GET-only collection route for join models — lists all records across parents."""
    async def collection_list(
        request: Request,
        limit: int = Query(default=None, ge=1, le=100),
        offset: int = Query(default=None, ge=0),
        populate: str = Query(default=None),
        depth: int = Query(default=None, ge=0, le=3),
    ):
        ctx = _build_context(request, model_class, "list")
        try:
            auth_filter = _resolver.sql_filter_for(ctx)
        except AccessDenied as e:
            raise HTTPException(status_code=403, detail=str(e))

        pop_spec = parse_populate(populate, depth)
        result = model_class.list(sql_filter=auth_filter, limit=limit, offset=offset, populate=pop_spec)

        if isinstance(result, dict) and 'data' in result:
            return {
                'data': [_serialize(r) for r in result['data']],
                'meta': result['meta'],
            }
        return [_serialize(r) for r in result]

    return collection_list


def make_get_schema(model_class):
    async def get_model_schema(scaffold: str = None):
        if scaffold:
            from fastapi.responses import PlainTextResponse
            from pybend.core.utils.scaffold import scaffold_single
            try:
                source = scaffold_single(model_class.__name__, kind=scaffold, schema=model_class.schema())
                return PlainTextResponse(source, media_type='text/plain')
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        logger.debug("Fetching schema for %s", model_class.__name__)
        return model_class.schema()
    return get_model_schema


def make_get_instance(model_class):
    async def read_instance(
        request: Request,
        id: int,
        populate: str = Query(default=None),
        depth: int = Query(default=None, ge=0, le=3),
    ):
        logger.debug("Reading %s ID=%s", model_class.__name__, id)
        pop_spec = parse_populate(populate, depth)
        instance = model_class.get(id, populate=pop_spec)
        if not instance:
            raise HTTPException(status_code=404, detail="Not found")
        ctx = _build_context(request, model_class, "read", resource=instance)
        try:
            _resolver.authorize(ctx)
        except AccessDenied as e:
            raise HTTPException(status_code=403, detail=str(e))
        return _serialize(instance)
    return read_instance


def make_update_instance(model_class):
    param_class = model_class.__parent__ if hasattr(model_class, '__parent__') else model_class
    async def update_instance(request: Request, id: int, data: param_class, parent_id: int = None) -> model_class:
        instance = model_class.get(id)
        if not instance:
            raise HTTPException(status_code=404, detail="Not found")
        ctx = _build_context(request, model_class, "update", resource=instance, parent_id=parent_id)
        try:
            _resolver.authorize(ctx)
        except AccessDenied as e:
            raise HTTPException(status_code=403, detail=str(e))
        try:
            data_dict = flatten_refs(data)
            # Strip backend-owned fields that cannot be modified via API
            protected = getattr(model_class, '__protected_fields__', None) or \
                        getattr(param_class, '__protected_fields__', set())
            for field in protected:
                data_dict.pop(field, None)
            if parent_id:
                fk_field = f"{model_class.__owner__.__name__.lower()}_id"
                data_dict[fk_field] = parent_id
            logger.info("Updating %s ID=%s", model_class.__name__, id)
            updated = model_class.update(id, data_dict)
            return updated.model_dump(response=True)
        except Exception as e:
            logger.error("Failed to update %s ID=%s: %s", model_class.__name__, id, e, exc_info=True)
            detail = str(e) if config.DEBUG else "Bad request"
            raise HTTPException(status_code=400, detail=detail)
    return update_instance


def make_delete_instance(model_class):
    async def delete_instance(request: Request, id: int) -> Dict[str, str]:
        instance = model_class.get(id)
        if not instance:
            raise HTTPException(status_code=404, detail="Not found")
        ctx = _build_context(request, model_class, "delete", resource=instance)
        try:
            _resolver.authorize(ctx)
        except AccessDenied as e:
            raise HTTPException(status_code=403, detail=str(e))
        logger.info("Deleting %s ID=%s", model_class.__name__, id)
        model_class.delete(id)
        return {"message": "Deleted successfully"}
    return delete_instance

from fastapi import Body, Path
from inspect import signature
from pydantic import BaseModel
from typing import get_type_hints


def _resolve_user(type_hint, request):
    """Bridge auth-layer identity to model-layer entity.

    The auth system (middleware / JWT) speaks plain dicts:
        {"user_id": int, "email": str, "role": str}

    Model methods may need the full User model instance.
    Resolution:
      - type_hint is a storable model class (e.g. User) → fetch via .get(user_id)
      - type_hint is dict or unrecognized → return the raw JWT dict as-is
      - no authenticated user → return None
    """
    user_dict = _get_user(request)
    if not user_dict or not user_dict.get('user_id'):
        return None
    if (isinstance(type_hint, type)
            and issubclass(type_hint, StorableMixin)
            and hasattr(type_hint, 'get')):
        return type_hint.get(user_dict['user_id'])
    return user_dict


def make_custom_post(attr, model_class, route_path):
    sig = signature(attr)
    type_hints = get_type_hints(attr)

    is_instance_method = 'self' in sig.parameters
    is_class_method = 'cls' in sig.parameters
    is_static_method = isinstance(attr, staticmethod)

    endpoint_info = getattr(attr, '__endpoint__', {})
    custom_access = endpoint_info.get('access', None)

    def _check_access(request, model_class, action, resource=None):
        ctx = _build_context(request, model_class, action, resource=resource)
        try:
            if custom_access:
                if not custom_access.evaluate(ctx):
                    raise AccessDenied(action=action, model=model_class.__name__, user_id=ctx.user_id)
            else:
                _resolver.authorize(ctx)
        except AccessDenied as e:
            raise HTTPException(status_code=403, detail=str(e))

    async def post_with_id(
        request: Request,
        id: int = Path(..., description=f"{model_class.__name__} ID"),
        data: Dict[str, Any] = Body(default={}),
    ):
        instance = model_class.get(id)
        if not instance:
            raise HTTPException(status_code=404, detail="Not found")
        _check_access(request, model_class, attr.__name__, resource=instance)

        parsed_args = {}
        for name, param in sig.parameters.items():
            if name in ('self', 'cls', 'user'):
                continue
            param_type = type_hints.get(name, str)
            raw = data.get(name)
            if raw is None:
                raise HTTPException(status_code=400, detail=f"Missing field: {name}")
            try:
                if isinstance(param_type, type) and issubclass(param_type, BaseModel):
                    parsed_args[name] = param_type(**raw) if isinstance(raw, dict) else param_type.parse_obj(raw)
                else:
                    parsed_args[name] = param_type(raw)
            except Exception as e:
                raise HTTPException(status_code=422, detail=f"Invalid field '{name}': {e}")

        if 'user' in sig.parameters:
            user = _resolve_user(type_hints.get('user'), request)
            if user is not None:
                parsed_args['user'] = user

        return attr(instance, **parsed_args)

    async def post_no_id(
        request: Request,
        data: Dict[str, Any] = Body(default={}),
    ):
        _check_access(request, model_class, attr.__name__)

        parsed_args = {}
        for name, param in sig.parameters.items():
            if name in ('self', 'cls', 'user'):
                continue
            param_type = type_hints.get(name, str)
            raw = data.get(name)
            if raw is None:
                raise HTTPException(status_code=400, detail=f"Missing field: {name}")
            try:
                if isinstance(param_type, type) and issubclass(param_type, BaseModel):
                    parsed_args[name] = param_type(**raw) if isinstance(raw, dict) else param_type.parse_obj(raw)
                else:
                    parsed_args[name] = param_type(raw)
            except Exception as e:
                raise HTTPException(status_code=422, detail=f"Invalid field '{name}': {e}")

        if 'user' in sig.parameters:
            user = _resolve_user(type_hints.get('user'), request)
            if user is not None:
                parsed_args['user'] = user

        if is_class_method:
            return attr(model_class, **parsed_args)
        else:
            return attr(**parsed_args)

    return post_with_id if is_instance_method else post_no_id


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


def register_routes():
    # Pass 1: Register static collection routes for join models FIRST.
    # These must come before parent model's /{table}/{id:int} routes because
    # FastAPI matches routes by registration order, and {id:int} would match
    # "comments" before the static /products/comments route gets a chance.
    # Route path uses __tablename__ to match the DynamicClass href the frontend
    # constructs from the schema's __tablename__ field.
    for model_name, model_class in registered_models.items():
        parent_class = getattr(model_class, '__owner__', None)
        if parent_class and issubclass(model_class, StorableMixin):
            tag = parent_class.__tablename__.capitalize()
            collection_path = f"/{model_class.__tablename__}"
            router.get(collection_path, tags=[tag])(make_collection_list(model_class))
            logger.info("Collection route: GET %s", collection_path)

    # Pass 2: Register all model routes (schema, CRUD, custom methods)
    for model_name, model_class in registered_models.items():
        # Extract model metadata
        logger.info("Registering routes for model: %s (%s)", model_name, model_class.__name__)
        model_title = model_name.capitalize()
        is_storable = issubclass(model_class, StorableMixin)
        parent_class = getattr(model_class, '__owner__', None)
        # Check if has parent
        if not parent_class:
            tag = model_class.__tablename__.capitalize()
            endpoint_base = f"/{model_name}"
        else:
            tag = model_class.__owner__.__tablename__.capitalize()
            parent_name = parent_class.__name__.lower()
            endpoint_base = f"/{parent_class.__tablename__}/{{parent_id:int}}/{model_class.__tagname__}"

        # Register basic GET route for schema
        router.get(f"/{model_class.__name__}", tags=[tag])(make_get_schema(model_class))
        # Register basic CRUD routes
        if is_storable:
            router.post(endpoint_base, tags=[tag], status_code=201)(make_create_instance(model_class))
            router.get(endpoint_base, tags=[tag])(make_get_all_instances(model_class))
            router.get(f"{endpoint_base}/{{id:int}}", tags=[tag])(make_get_instance(model_class))
            router.put(f"{endpoint_base}/{{id:int}}", tags=[tag])(make_update_instance(model_class))
            router.delete(f"{endpoint_base}/{{id:int}}", tags=[tag])(make_delete_instance(model_class))

        # Custom @expose_route handlers
        for attr_name in dir(model_class):
            attr = getattr(model_class, attr_name)
            if callable(attr) and hasattr(attr, '__endpoint__'):
                # Check if method needs an instance (has 'self' param) → needs {id}
                route_info = attr.__endpoint__
                route = route_info['route']
                methods = route_info['methods']
                sig = signature(attr)
                is_instance_method = 'self' in sig.parameters
                if is_instance_method:
                    full_route = f"{endpoint_base}/{{id:int}}{route}"
                else:
                    full_route = f"{endpoint_base}{route}"

                from typing import get_origin, get_args, ForwardRef
                return_type = attr.__annotations__.get('return', None)

                if isinstance(return_type, (str, ForwardRef)):
                    type_str = str(return_type).replace('ForwardRef(', '').replace(')', '').replace("'", "")
                    if type_str == model_class.__name__:
                        return_type = model_class
                    elif type_str.startswith(f'List[{model_class.__name__}'):
                        return_type = List[model_class]
                elif get_origin(return_type) is list:
                    args = get_args(return_type)
                    if args and args[0] == model_class.__name__:
                        return_type = List[model_class]

                custom_method = None
                if isinstance(attr, (classmethod, staticmethod)):
                    if 'GET' in methods:
                        async def custom_get(attr=attr) -> return_type:
                            logger.debug("Custom GET handler for %s", attr.__name__)
                            return attr()
                        router.add_api_route(full_route, custom_get, methods=['GET'], tags=[model_title], name=attr.__name__)
                        custom_method = custom_get
                    elif 'POST' in methods:
                        async def custom_post(data: Dict[str, Any] = Body(default={}), attr=attr) -> return_type:
                            logger.debug("Custom POST handler for %s", attr.__name__)
                            return attr(**data)
                        custom_method = custom_post
                else:
                    if 'GET' in methods:
                        async def custom_get(id: int = Path(..., description=f"{model_name.capitalize()} primary key"), attr=attr) -> return_type:
                            logger.debug("Custom GET handler for %s ID=%s", attr.__name__, id)
                            instance = parent_class.get(id)
                            return attr(instance)
                        custom_method = custom_get

                    elif 'POST' in methods:
                        async def custom_post(
                                id: int = Path(..., description=f"{model_name.capitalize()} primary key"),
                                data: Dict[str, Any] = Body(default={}),
                                attr=attr
                        ) -> return_type:
                            logger.debug("Custom POST handler for %s ID=%s", attr.__name__, id)
                            instance = parent_class.get(id)
                            return attr(instance, **data)
                        custom_method = custom_post

                handler = make_custom_post(attr, model_class, full_route)
                router.add_api_route(full_route, handler,
                                     methods=methods, tags=[model_title], name=attr.__name__,
                                     response_model=return_type if return_type else None,
                                     )


# Expose router to be used in FastAPI app
__all__ = ["router", "register_routes", "register_route"]
