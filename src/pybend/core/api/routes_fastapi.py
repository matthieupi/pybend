import traceback

from fastapi import APIRouter, Request, HTTPException, status, Body, Path
from typing import Dict, Type, Any, List
from models.storable_mixin import StorableMixin
from utils.erroring import get_traceback_info
from utils.registrar import registered_models, join_models

router = APIRouter()

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

    async def create_instance(data: param_class, parent_id: int = None) -> model_class:
        print(f"[CREATE] Attempting to create {model_class.__name__} with data: {data}, parent_id: {parent_id}", flush=True)
        try:
            if parent_id:
                fk_field = f"{model_class.__owner__.__name__.lower()}_id"
                data_dict = data.dict()
                data_dict[fk_field] = parent_id
                instance = model_class(**data_dict)
            else:
                instance = model_class(**data.dict())

            return model_class.create(instance)
        except Exception as e:
            raise HTTPException(status_code=400, detail=get_traceback_info(e) )
            raise HTTPException(status_code=400, detail=f"'error':{str(e)}, 'stacktrace': {str(e.__traceback__)}")

    return create_instance


def make_get_all_instances(model_class):
    async def list_all_instances(parent_id: int = None) -> List[model_class]:
        target_cls = model_class

        if parent_id:
            # Resolve join model based on registration
            for (parent_name, child_name), join_cls in join_models.items():
                if child_name == model_class.__name__:
                    target_cls = join_cls
                    break

        results = target_cls.list()
        print(f"[LIST] Fetching all instances of {target_cls.__name__} (parent_id={parent_id})")
        print(results)

        if parent_id:
            fk_field = f"{target_cls.__owner__.__name__.lower()}_id"
            return [r for r in results if getattr(r, fk_field, None) == parent_id]

        return results

    return list_all_instances


def make_get_schema(model_class):
    async def get_model_schema() -> Dict[str, Any]:
        print(f"[SCHEMA] Fetching schema for {model_class.__name__}")
        return model_class.schema()
    return get_model_schema


def make_get_instance(model_class):
    async def read_instance(id: int) -> model_class:
        print(f"[READ] Attempting to read {model_class.__name__} ID={id}")
        instance = model_class.get(id)
        if not instance:
            raise HTTPException(status_code=404, detail="Not found")
        return instance.model_dump()
    return read_instance


def make_update_instance(model_class):
    async def update_instance(id: int, data: model_class) -> model_class:
        try:
            print(f"[UPDATE] Attempting to update {model_class.__name__} ID={id} with data: {data}")
            updated = model_class.update(id, data)
            return updated
        except Exception as e:
            print(f"[ERROR] Failed to update {model_class.__name__} ID={id}: {e}")
            raise HTTPException(status_code=400, detail=str(e))
    return update_instance


def make_delete_instance(model_class):
    async def delete_instance(id: int) -> Dict[str, str]:
        print(f"[DELETE] Attempting to delete {model_class.__name__} ID={id}")
        model_class.delete(id)
        return {"message": "Deleted successfully"}
    return delete_instance

from fastapi import Body, Path
from inspect import signature
from pydantic import BaseModel
from typing import get_type_hints

def make_custom_post(attr, model_class, route_path):
    sig = signature(attr)
    type_hints = get_type_hints(attr)

    is_instance_method = 'self' in sig.parameters
    is_class_method = 'cls' in sig.parameters
    is_static_method = isinstance(attr, staticmethod)

    async def post_with_id(
        id: int = Path(..., description=f"{model_class.__name__} ID"),
        data: Dict[str, Any] = Body(...),
    ):
        instance = model_class.get(id)
        if not instance:
            raise HTTPException(status_code=404, detail="Not found")

        parsed_args = {}
        for name, param in sig.parameters.items():
            if name in ('self', 'cls'):
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

        return attr(instance, **parsed_args)

    async def post_no_id(
        data: Dict[str, Any] = Body(...),
    ):
        parsed_args = {}
        for name, param in sig.parameters.items():
            if name in ('self', 'cls'):
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

        if is_class_method:
            return attr(model_class, **parsed_args)
        else:
            return attr(**parsed_args)

    return post_with_id if is_instance_method else post_no_id


def register_routes():
    for model_name, model_class in registered_models.items():
        # Extract model metadata
        print(f"[ROUTES] Registering routes for model: {model_name} ({model_class.__name__})")
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
            endpoint_base = f"/{parent_class.__tablename__}/{{parent_id}}/{model_class.__tagname__}"

        # Register basic GET route for schema
        router.get(f"/{model_class.__name__}", tags=[tag])(make_get_schema(model_class))
        # Register basic CRUD routes
        if is_storable:
            router.post(endpoint_base, tags=[tag], status_code=201)(make_create_instance(model_class))
            router.get(endpoint_base, tags=[tag])(make_get_all_instances(model_class))
            router.get(f"{endpoint_base}/{{id}}", tags=[tag])(make_get_instance(model_class))
            router.put(f"{endpoint_base}/{{id}}", tags=[tag])(make_update_instance(model_class))
            router.delete(f"{endpoint_base}/{{id}}", tags=[tag])(make_delete_instance(model_class))

        # Custom @expose_route handlers
        for attr_name in dir(model_class):
            attr = getattr(model_class, attr_name)
            if callable(attr) and hasattr(attr, '__endpoint__'):
                # Check if method is classmethod or staticmethod
                route_info = attr.__endpoint__
                route = route_info['route']
                methods = route_info['methods']
                if isinstance(attr, (classmethod, staticmethod)):
                    full_route = f"{endpoint_base}{route}"
                else:
                    full_route = f"{endpoint_base}/{{id}}{route}"

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
                            print(f"[GET] Custom GET handler for {attr.__name__} at {full_route}")
                            return attr()
                        router.add_api_route(full_route, custom_get, methods=['GET'], tags=[model_title], name=attr.__name__)
                        custom_method = custom_get
                    elif 'POST' in methods:
                        async def custom_post(data: Dict[str, Any] = Body(...), attr=attr) -> return_type:
                            print(f"[POST] Custom POST handler for {attr.__name__} at {full_route} with data: {data}")
                            return attr(**data)
                        custom_method = custom_post
                else:
                    if 'GET' in methods:
                        async def custom_get(id: int = Path(..., description=f"{model_name.capitalize()} primary key"), attr=attr) -> return_type:
                            print(f"[GET] Custom GET handler for {attr.__name__} ID={id} at {full_route}")
                            instance = parent_class.get(id)
                            return attr(instance)
                        custom_method = custom_get

                    elif 'POST' in methods:
                        async def custom_post(
                                id: int = Path(..., description=f"{model_name.capitalize()} primary key"),
                                data: Dict[str, Any] = Body(...),
                                attr=attr
                        ) -> return_type:
                            print(f"[POST] Custom POST handler for {attr.__name__} ID={id} at {full_route} with data: {data}")
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
