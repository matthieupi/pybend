# app/models/base_model.py
import inspect
import json

from pydantic import BaseModel as PydanticBaseModel, GetJsonSchemaHandler, BaseModel, Field
from typing import Any, Dict, Type, get_type_hints, get_origin, get_args, Union

from pydantic.json_schema import JsonSchemaValue, JsonSchemaMode, GenerateJsonSchema, DEFAULT_REF_TEMPLATE
from pydantic_core import CoreSchema

import config
from utils.registrar import register_model
from utils.decorators import expose_route
from utils.introspection import pydantic_schema_for_type, collect_all_referenced_models, record_model_type
from utils.typer import ForeignKey
from .storable_mixin import StorableMixin


class ProtoModel(PydanticBaseModel):
    """
    Base model that optionally adds StorableMixin based on the 'storable' class attribute.
    """
    class Config:
        arbitrary_types_allowed = True  # allows ForeignKey through
        json_encoders = {
            ForeignKey: lambda fk: int(fk),
        }

    def __init_subclass__(cls, **kwargs):
        # Checks if the class has a 'storable' attribute, defaulting to False
        __storable__ = getattr(cls, '__storable__', False)
        cls._referenced_models = set()  # We'll gather referenced models here
        # If 'storable' is True, injects StorableMixin into the class
        if __storable__:
            if not issubclass(cls, StorableMixin):
                # Bases injection: add StorableMixin to the class bases
                cls.__bases__ = (StorableMixin,) + cls.__bases__
                # FK Injection: rewrite fields that are Pydantic models into ForeignKey
                new_annotations = {}
                for name, annotation in get_type_hints(cls, include_extras=True).items():
                    # If is list, get origin and args
                    if isinstance(annotation, type) and issubclass(annotation, BaseModel) and annotation != cls:
                        new_annotations[name] = ForeignKey[annotation]
                        # TODO - Differentiate between join model and ForeignKey and generate model programatically
                        #generate_join_model(owner_cls=cls, ref_model=annotation, field_name=name)
                # Rewrite annotations dynamically
                if new_annotations:
                    cls.__annotations__ = dict(cls.__annotations__)  # make a copy
                    cls.__annotations__.update(new_annotations)
        super().__init_subclass__(**kwargs)


    def __init__(self, *args, **kwargs):
        """
        Initializes the model and sets the __owner__ attribute if provided.
        """
        params = kwargs
        if getattr(self, '__storable__', False):
            # If the model is storable, it can be created by simply passing an id and it will be retrieved from the
            # storage
            if 'id' in kwargs and len(kwargs) == 1:
                # If 'id' is provided, ensure it's an integer
                kwargs['id'] = int(kwargs['id'])
                # Then retrieve this
                # instance from the storage
                print(f"Retrieving {self.__class__.__name__} with id {kwargs['id']} from storage.", flush=True)
                params = self.__class__.get(kwargs['id'], as_dict=True)  # This will call the get method of StorableMixin
                print(params, flush=True)
        super().__init__(*args, **params)
        # Set __owner__ if it exists in kwargs
        self.__owner__ = kwargs.get('__owner__', None)


    @classmethod
    def __pybend_methods_json_signature__(cls) -> dict:
        """
        Returns a dictionary of exposed methods including their route, parameters, and return type.
        Also gathers all referenced Pydantic models for inclusion in $defs.
        """
        methods = {}

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
                record_model_type(cls, ptype)

            # Return type schema
            rtype = type_hints.get('return', None)
            return_type_schema = pydantic_schema_for_type(rtype) if rtype else {}
            record_model_type(cls, rtype)
            # save method type (classmethod, staticmethod, or instance method)
            if isinstance(method, classmethod):
                method_type = 'classmethod'
            elif isinstance(method, staticmethod):
                method_type = 'staticmethod'
            else:
                method_type = 'instancemethod'

            methods[method_name] = {
                'route': endpoint_info['route'],
                'methods': endpoint_info['methods'],
                'scope': method_type,
                'parameters': parameters,
                'returns': return_type_schema,
            }

        return methods

    @classmethod
    #@expose_route('/schema', methods=['GET'])
    def schema(cls) -> Dict[str, Any]:
        """
        Returns the schema for this model.
        """
        referenced_models = collect_all_referenced_models(cls)
        schema = cls.model_json_schema(ref_template="#/$defs/{model}")

        # Add methods signature to schema
        schema['methods'] = cls.__pybend_methods_json_signature__()
        # Add referenced models to $defs
        if referenced_models:
            # Add $defs if it was not already present
            if not '$defs' in schema and referenced_models:
                schema['$defs'] = {}
            # Add all referenced models to $defs
            for model in referenced_models:
                #if model.__name__ not in schema['$defs']:
                # Bubble up the $defs from the referenced model
                ref_schema = model.referenced_json_schema()
                ref_methods = model.__pybend_methods_json_signature__()
                defs = ref_schema.pop('$defs', {})  # Remove $defs to avoid circular references
                schema['$defs'] = {**defs, **schema['$defs']} if defs else schema['$defs']
                schema['$defs'][model.__name__] = ref_schema
                # Add methods to the model's schema
                schema['$defs'][model.__name__]['methods'] = ref_methods

            # Add the model's JSON schema to the $defs
        # List all exposed method along with their doc
        return schema


    @classmethod
    def referenced_json_schema(cls) -> Dict[str, Any]:
        """
        Returns the schema for the ForeignKey field.
        This is a convenience method to expose the ForeignKey schema.
        """
        schema = cls.model_json_schema()
        # 💡 Resolve ForeignKey field schemas into proper $ref
        for field_name, field_info in cls.model_fields.items():
            field_type = field_info.annotation
            if get_origin(field_type) is ForeignKey:
                target = get_args(field_type)[0]
                if target.__name__ not in cls._referenced_models:
                    record_model_type(cls, target)
                schema['properties'][field_name] = {"type": "$ref", "$ref": f"#/$defs/{target.__name__}"}

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
        schema['__url__'] = f"{config.HOST}:{config.PORT}/{cls.__name__}"
        schema['__type__'] = 'schema'
        schema['__name__'] = cls.__name__
        schema['__owner__'] = cls.__owner__.__name__ if hasattr(cls, '__owner__') else None
        schema['__parent__'] = cls.__parent__.__name__ if hasattr(cls, '__parent__') else None
        schema['__tablename__'] = cls.__tablename__ if hasattr(cls, '__tablename__') else ""
        # Reset referenced models for the next call
        for field_name, field_info in cls.model_fields.items():
            field_type = field_info.annotation
            if get_origin(field_type) is ForeignKey:
                target = get_args(field_type)[0]
                if target.__name__ not in cls._referenced_models:
                    record_model_type(cls, target)

        return schema

    @staticmethod
    def blueprint():
        """
        Returns the blueprint of registered models
        """
        from utils.registrar import registered_models
        blueprint = {}
        for model_name, model_cls in registered_models.items():
            blueprint[model_name] = model_cls.schema()
        return blueprint


def generate_join_model(owner_cls: Type[ProtoModel], ref_model: Type[ProtoModel], field_name: str = None):
    assert issubclass(owner_cls, ProtoModel), \
        f"[{owner_cls.__name__}.{ref_model.__name__}] Join Model - owner_cls must be a subclass of ProtoModel"
    assert issubclass(ref_model, ProtoModel), \
        f"[{owner_cls.__name__}.{ref_model.__name__}] Join Model - ref_model must be a subclass of ProtoModel"
    assert hasattr(owner_cls, 'storage'), \
        f"[{owner_cls.__name__}.{ref_model.__name__}] Join Model - owner_cls must have a storage backend set"
    owner_name = owner_cls.__name__
    owner_tablename = owner_cls.__tablename__
    ref_tablename = ref_model.__tablename__
    class_name = f"{owner_name}{ref_model.__name__}"
    tablename = f"{owner_tablename}_{ref_tablename}"
    fk_field = f"{owner_name.lower()}_id"

    print(f"[{owner_cls.__name__}.{ref_model.__name__}] Generating join model '{class_name}' with table '{tablename}'", flush=True)
    # Construct __annotations__ and field definitions separately
    annotations = dict(ref_model.__annotations__)
    annotations[fk_field] = int

    fields = {
        "__tablename__": tablename,
        "__tagname__": ref_model.__tablename__,
        "__storable__": True,
        "__owner__": owner_cls,
        "__parent__": ref_model,
        "__module__": ref_model.__module__,
        "__annotations__": annotations,
        fk_field: Field(..., alias=fk_field, description=f"FK to {owner_name}")
    }
    join_model = type(class_name, (ref_model,), fields)

    return join_model

