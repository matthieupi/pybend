from fastapi import APIRouter, Request, HTTPException, status, Body
from typing import Dict, Type, Any, List
from models.storable_mixin import StorableMixin
from utils.registrar import registered_models

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
    async def create_instance(data: model_class, parent_id: int = None) -> model_class:
        try:
            instance = model_class(**data.dict())
            if parent_id:
                fk_field = f"{model_class.__parent__.__name__.lower()}_id"
                setattr(instance, fk_field, parent_id)
            return model_class.create(instance)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    return create_instance


def make_get_all_instances(model_class):
    async def list_all_instances(parent_id: int = None) -> List[model_class]:
        results = model_class.list()
        # TODO - Base MVP implementation with atrocious performance, to be improved
        if parent_id:
            fk_field = f"{model_class.__parent__.__name__.lower()}_id"
            return [r for r in results if getattr(r, fk_field) == parent_id]
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


def register_routes():
    for model_name, model_class in registered_models.items():
        # Check if has parent
        if not hasattr(model_class, '__parent__') or model_class.__parent__ is None:
            endpoint_base = f"/{model_name}"
        else:
            endpoint_base = f"/{model_class.__parent__.__tablename__}/{{parent_id}}/{model_class.__tagname__}"
        model_title = model_name.capitalize()
        is_storable = issubclass(model_class, StorableMixin)

        router.get(f"/{model_class.__name__}", tags=[model_title])(make_get_schema(model_class))

        if is_storable:
            router.post(endpoint_base, tags=[model_title], status_code=201)(make_create_instance(model_class))
            router.get(endpoint_base, tags=[model_title])(make_get_all_instances(model_class))
            # router.get(f"{endpoint_base}/schema", tags=[model_title])(make_get_schema(model_class))
            router.get(f"{endpoint_base}/{{id}}", tags=[model_title])(make_get_instance(model_class))
            router.put(f"{endpoint_base}/{{id}}", tags=[model_title])(make_update_instance(model_class))
            router.delete(f"{endpoint_base}/{{id}}", tags=[model_title])(make_delete_instance(model_class))

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

                if 'GET' in methods:
                    async def custom_get(attr=attr) -> return_type:
                        print(f"[GET] Custom GET handler for {attr.__name__} at {full_route}")
                        return attr()
                    router.add_api_route(full_route, custom_get, methods=['GET'], tags=[model_title], name=attr.__name__)

                if 'POST' in methods:
                    async def custom_post(data: Dict[str, Any] = Body(...), attr=attr) -> return_type:
                        print(f"[POST] Custom POST handler for {attr.__name__} at {full_route} with data: {data}")
                        return attr(data)
                    router.add_api_route(full_route, custom_post,
                                         methods=['POST'], tags=[model_title], name=attr.__name__,
                                         response_model=return_type if return_type else None,
                                         )


# Expose router to be used in FastAPI app
__all__ = ["router", "register_routes", "register_route"]
