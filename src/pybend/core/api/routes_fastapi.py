# app/api/routes.py

from fastapi import APIRouter, Request, HTTPException, status, Body
from typing import Dict, Type, Any, List
from models.storable_mixin import StorableMixin
from utils.registrar import registered_models

router = APIRouter()

def register_route(path, fn, method='GET'):
    """
    Register a route at the root path.
    """
    print(f"Registering route {path} with method {method}")
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


def register_routes():
    print("Route registration started")
    print(registered_models)
    for model_name, model_class in registered_models.items():
        endpoint_base = f"/{model_name}"
        is_storable = issubclass(model_class, StorableMixin)
        model_title = model_name.capitalize()

        print(f"Registering routes for {model_name} with storable={is_storable}")

        # Register the base route for the schema
        @router.get(f"/{model_class.__name__}", tags=[model_title], status_code=200)
        @router.get(f"/{model_class.__name__}/schema", tags=[model_title], status_code=200)
        async def get_model_schema(cls_=model_class) -> Dict[str, Any]:
            return cls_.schema()

        if is_storable:
            @router.post(endpoint_base, tags=[model_title], status_code=201)
            async def create_instance(data: model_class) -> model_class:
                try:
                    print(f"Creating instance of {model_name} with data: {data}")
                    instance = model_class(**data.dict())
                    instance = model_class.create(instance)
                    return instance
                except Exception as e:
                    print(f"Error creating instance of {model_name}: {e}")
                    raise HTTPException(status_code=400, detail=str(e))

            @router.get(endpoint_base, tags=[model_title])
            async def get_all_instances(cls_=model_class) -> List[model_class]:
                return cls_.list()

            @router.get(f"{endpoint_base}/schema", tags=[model_title])
            async def get_schema(cls_=model_class) -> Dict[str, Any]:
                return cls_.schema()

            @router.get(f"{endpoint_base}/{{id}}", tags=[model_title])
            async def get_instance(id: int, cls_=model_class) -> model_class:
                instance = cls_.get(id)
                if not instance:
                    raise HTTPException(status_code=404, detail="Not found")
                return instance.model_dump()

            @router.put(f"{endpoint_base}/{{id}}", tags=[model_title])
            async def update_instance(id: int, data: model_class, cls_=model_class) -> model_class:
                try:
                    cls_.update(id, data)
                    return model_class
                except Exception as e:
                    raise HTTPException(status_code=400, detail=str(e))

            @router.delete(f"{endpoint_base}/{{id}}", tags=[model_title])
            async def delete_instance(id: int) -> Dict[str, str]:
                model_class.delete(id)
                return {"message": "Deleted successfully"}

         # Handle @expose_route endpoints
        for attr_name in dir(model_class):
            attr = getattr(model_class, attr_name)
            if callable(attr) and hasattr(attr, '__endpoint__'):
                route = attr.__endpoint__['route']
                methods = attr.__endpoint__['methods']
                full_route = f"{endpoint_base}{route}"
                endpoint_name = f"{model_name}_{attr.__name__}"

                import typing
                from typing import get_origin, get_args, ForwardRef

                return_type = attr.__annotations__.get('return', None)

                # Resolve forward references
                if isinstance(return_type, str) or isinstance(return_type, ForwardRef):
                    return_type_str = str(return_type).replace('ForwardRef(', '').replace(')', '').replace("'", "")
                    if return_type_str == model_class.__name__:
                        return_type = model_class
                    elif return_type_str.startswith(f'List[{model_class.__name__}'):
                        return_type = List[model_class]
                elif get_origin(return_type) is list:
                    args = get_args(return_type)
                    if args and isinstance(args[0], str) and args[0] == model_class.__name__:
                        return_type = List[model_class]


                if 'GET' in methods:
                    async def custom_get(attr=attr) -> return_type:
                        return attr()
                    custom_get.__name__ = attr.__name__
                    router.add_api_route(
                        full_route,
                        custom_get,
                        methods=['GET'],
                        tags=[model_title],
                        name=attr.__name__
                    )

                if 'POST' in methods:
                    async def custom_post(data: Dict[str, Any] = Body(...), attr=attr) -> return_type:
                        return attr(data)
                    custom_post.__name__ = attr.__name__
                    router.add_api_route(
                        full_route,
                        custom_post,
                        methods=['POST'],
                        tags=[model_title],
                        name=attr.__name__
                    )

