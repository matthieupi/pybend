# app/models/base_model.py
import inspect
import json

from pydantic import BaseModel as PydanticBaseModel, GetJsonSchemaHandler, BaseModel
from typing import Any, Dict, Type, get_type_hints, get_origin, get_args, Union

from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from utils.decorators import expose_route
from utils.introspection import pydantic_schema_for_type, collect_all_referenced_models
from .storable_mixin import StorableMixin

import sys

sys.setrecursionlimit(150)

class ProtoModel(PydanticBaseModel):
    """
    Base model that optionally adds StorableMixin based on the 'storable' class attribute.
    """

    def __init_subclass__(cls, **kwargs):
        # Checks if the class has a 'storable' attribute, defaulting to False
        __storable__ = getattr(cls, '__storable__', False)
        # If 'storable' is True, injects StorableMixin into the class
        if __storable__ and StorableMixin not in cls.__bases__:
            cls.__bases__ = (StorableMixin,) + cls.__bases__
        super().__init_subclass__(**kwargs)

    @classmethod
    def completion_cls(cls) -> Type:
        """
        Returns the completion class to be used for this model.
        """

        raise NotImplementedError

    @classmethod
    def _record_model_type(cls, type_):
        """
        Collect Pydantic models from a type hint, recursively.
        """
        origin = get_origin(type_)
        args = get_args(type_)
        # If nested collection types, recursively record their models
        if origin in (list, tuple, set, dict, Union):
            for arg in args:
                cls._record_model_type(arg)
        # If we reached the root type or a Pydantic model, record it
        elif isinstance(type_, type) and issubclass(type_, BaseModel):
            cls._referenced_models.add(type_)

    @classmethod
    def methods_json(cls) -> dict:
        """
        Returns a dictionary of exposed methods including their route, parameters, and return type.
        Also gathers all referenced Pydantic models for inclusion in $defs.
        """
        methods = {}
        cls._referenced_models = set()  # We'll gather referenced models here

        for method_name in dir(cls):
            method = getattr(cls, method_name)
            if not (callable(method) and hasattr(method, '__endpoint__')):
                continue

            sig = inspect.signature(method)
            type_hints = get_type_hints(method, globalns=method.__globals__, localns=locals())
            endpoint_info = method.__endpoint__

            # Extract parameter schemas and record model types
            parameters = {}
            for name, param in sig.parameters.items():
                if name in ('cls', 'self'):
                    continue
                ptype = type_hints.get(name, param.annotation)
                parameters[name] = pydantic_schema_for_type(ptype)
                cls._record_model_type(ptype)

            # Return type schema
            rtype = type_hints.get('return', None)
            return_type_schema = pydantic_schema_for_type(rtype) if rtype else {}
            cls._record_model_type(rtype)

            methods[method_name] = {
                'route': endpoint_info['route'],
                'methods': endpoint_info['methods'],
                'parameters': parameters,
                'returns': return_type_schema,
                'validators': {
                    name: ["Not implemented yet."]
                    for name in parameters
                }
            }

        return methods

    @classmethod
    @expose_route('/schema', methods=['GET'])
    def schema(cls) -> Dict[str, Any]:
        """
        Returns the schema for this model.
        """
        print("Hello from ProtoModel.schema()")

        referenced_models = collect_all_referenced_models(cls)
        print(f"Collecting methods for {cls.__name__}, found {len(referenced_models)} referenced models.")
        print(f"Referenced models: {[model.__name__ for model in referenced_models]}")
        schema = cls.model_json_schema(ref_template="#/$defs/{model}")
        # Add methods signature to schema
        schema['methods'] = cls.methods_json()
        # Add referenced models to $defs
        if referenced_models:
            # Add $defs if it was not already present
            if not '$defs' in schema and referenced_models:
                schema['$defs'] = {}
            # Add all referenced models to $defs
            for model in referenced_models:
                if model.__name__ not in schema['$defs']:
                    # Bubble up the $defs from the referenced model
                    ref_schema = model.model_json_schema()
                    ref_methods = model.methods_json()
                    defs = ref_schema.pop('$defs', {})  # Remove $defs to avoid circular references
                    schema['$defs'] = {**schema['$defs'], **defs} if defs else schema['$defs']
                    schema['$defs'][model.__name__] = ref_schema
                    # Add methods to the model's schema
                    schema['$defs'][model.__name__]['methods'] = ref_methods

            # Add the model's JSON schema to the $defs
        # List all exposed method along with their doc
        return schema

    @classmethod
    def __get_pydantic_json_schema__(
            cls,
            core_schema: CoreSchema,
            handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        """
        Returns the JSON schema for this model, including method metadata and $defs for referenced models.
        """
        # Prevent infinite recursion when circular inclusion are present
        schema = super().__get_pydantic_json_schema__(core_schema, handler)
        # Add custom metadata
        schema['__type__'] = 'schema'
        schema['__name__'] = cls.__name__
        schema['__tablename__'] = cls.__tablename__ if hasattr(cls, '__tablename__') else ""
        # Reset referenced models for the next call
        return schema

    @staticmethod
    def blueprint():
        """
        Returns the blueprint of registered models
        """
        from utils.registrar import registered_models
        print("Hello from ProtoModel.blueprint()")
        blueprint = {}
        for model_name, model_cls in registered_models.items():
            blueprint[model_name] = model_cls.schema()
        return blueprint