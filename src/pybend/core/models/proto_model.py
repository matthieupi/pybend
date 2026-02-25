# app/models/base_model.py
import inspect
import json
import logging

from pydantic import BaseModel as PydanticBaseModel, GetJsonSchemaHandler, BaseModel, Field
from typing import Any, ClassVar, Dict, Type, get_type_hints, get_origin, get_args, Union

from pydantic.json_schema import JsonSchemaValue, JsonSchemaMode, GenerateJsonSchema, DEFAULT_REF_TEMPLATE
from pydantic_core import CoreSchema

from pybend.core import config
from pybend.core.utils.registrar import register_model
from pybend.core.utils.decorators import expose_route
from pybend.core.utils.introspection import pydantic_schema_for_type, collect_all_referenced_models, record_model_type, _is_self_ref
from pybend.core.utils.typer import Ref, _SelfRefMarker
from .storable_mixin import StorableMixin

logger = logging.getLogger('pybend.models')


_AUTO_HIDE_FIELDS = {'id', 'image', 'created_at', 'updated_at'}

def _apply_field_exclusion(schema: dict):
    """Apply ui.display=false convention to *_id, id, and timestamp fields."""
    if 'properties' not in schema:
        return
    for field_name, field_def in schema['properties'].items():
        if not isinstance(field_def, dict):
            continue
        is_auto_hide = (
            field_name in _AUTO_HIDE_FIELDS
            or (field_name.endswith('_id') and field_name != 'id')
        )
        if is_auto_hide:
            existing_ui = field_def.get('ui', {})
            if 'display' not in existing_ui:
                if 'ui' not in field_def:
                    field_def['ui'] = {}
                field_def['ui']['display'] = False


class ProtoModel(PydanticBaseModel):
    """
    Base model that optionally adds StorableMixin based on the 'storable' class attribute.
    """
    __fk_models__: ClassVar[Dict[str, Type]] = {}
    id: int = Field(default=0)
    image: str = Field(default='')

    class Config:
        arbitrary_types_allowed = True  # allows Ref through
        extra = 'allow'  # allows $schema/$id to pass through FastAPI response model
        json_encoders = {
            Ref: lambda fk: int(fk),
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
                for name, annotation in get_type_hints(cls, localns={cls.__name__: cls}, include_extras=True).items():
                    # If is list, get origin and args
                    if isinstance(annotation, type) and issubclass(annotation, BaseModel) and annotation != cls:
                        new_annotations[name] = Ref[annotation]
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
                logger.debug("Retrieving %s with id %s from storage", self.__class__.__name__, kwargs['id'])
                params = self.__class__.get(kwargs['id'], as_dict=True)  # This will call the get method of StorableMixin
                logger.debug("Retrieved params: %s", params)
        super().__init__(*args, **params)
        # Set __owner__ if it exists in kwargs
        self.__owner__ = kwargs.get('__owner__', None)


    def model_dump(self, *, response: bool = False, **kwargs) -> Dict[str, Any]:
        """Override to optionally inject $schema and $id for API responses.
        Default returns plain data for DB. response=True adds JSON Schema metadata."""
        data = super().model_dump(**kwargs)
        if response:
            tablename = getattr(self.__class__, '__tablename__', self.__class__.__name__.lower())
            instance_id = getattr(self, 'id', None)
            data = {
                '$schema': f"{config.API_URL}/{self.__class__.__name__}",
                '$id': f"{config.API_URL}/{tablename}/{instance_id}" if instance_id is not None else None,
                **data
            }
        return data

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
                if name in ('cls', 'self', 'user'):
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

            method_entry = {
                'route': endpoint_info['route'],
                'methods': endpoint_info['methods'],
                'scope': method_type,
                'parameters': parameters,
                'returns': return_type_schema,
            }
            if endpoint_info.get('access') and hasattr(endpoint_info['access'], 'to_dict'):
                method_entry['access'] = endpoint_info['access'].to_dict()
            methods[method_name] = method_entry

        return methods

    @classmethod
    #@expose_route('/schema', methods=['GET'])
    def schema(cls) -> Dict[str, Any]:
        """
        Returns the schema for this model.
        """
        referenced_models = collect_all_referenced_models(cls)
        schema = cls.model_json_schema(ref_template="#/$defs/{model}")

        # Strip hidden fields from schema properties
        hidden = getattr(cls, '__hidden_fields__', set())
        if hidden and 'properties' in schema:
            for name in hidden:
                schema['properties'].pop(name, None)
            if 'required' in schema:
                schema['required'] = [r for r in schema['required'] if r not in hidden]

        # Add methods signature to schema
        schema['methods'] = cls.__pybend_methods_json_signature__()
        # Add referenced models to $defs
        if referenced_models:
            # Add $defs if it was not already present
            if not '$defs' in schema and referenced_models:
                schema['$defs'] = {}
            # Add all referenced models to $defs
            for model in referenced_models:
                # Bubble up the $defs from the referenced model
                ref_schema = model.referenced_json_schema()
                ref_methods = model.__pybend_methods_json_signature__()
                defs = ref_schema.pop('$defs', {})  # Remove $defs to avoid circular references
                schema['$defs'] = {**defs, **schema['$defs']} if defs else schema['$defs']
                # Only overwrite if ref_schema has actual properties
                # (self-referencing models like Comment become bare $refs after pop)
                if 'properties' in ref_schema:
                    schema['$defs'][model.__name__] = ref_schema
                elif model.__name__ not in schema['$defs']:
                    schema['$defs'][model.__name__] = ref_schema
                # Add methods to the model's $def entry
                if model.__name__ in schema['$defs']:
                    schema['$defs'][model.__name__]['methods'] = ref_methods

            # Add $id to each $defs entry
            for model in referenced_models:
                if model.__name__ in schema['$defs']:
                    schema['$defs'][model.__name__]['$id'] = f"{config.API_URL}/{model.__name__}"

        # Patch Ref['self'] fields to emit {"type": "selfref"}
        if 'properties' in schema:
            for field_name, field_info in cls.model_fields.items():
                if _is_self_ref(field_info.annotation):
                    schema['properties'][field_name] = {"type": "selfref"}

        # Add access rules to schema
        from pybend.core.authorize.schema import access_schema
        schema['access'] = access_schema(cls)

        # Apply field exclusion conventions: auto-set ui.display=false for internal fields
        _apply_field_exclusion(schema)

        # Mark protected fields in schema
        protected = getattr(cls, '__protected_fields__', set())
        if protected and 'properties' in schema:
            for field_name in protected:
                if field_name in schema['properties']:
                    schema['properties'][field_name].setdefault('ui', {})['protected'] = True

        # Also apply to $defs entries
        if '$defs' in schema:
            for def_schema in schema['$defs'].values():
                _apply_field_exclusion(def_schema)

            # Mark protected fields in $defs entries
            if referenced_models:
                for model in referenced_models:
                    ref_protected = getattr(model, '__protected_fields__', set())
                    if ref_protected and model.__name__ in schema['$defs']:
                        def_props = schema['$defs'][model.__name__].get('properties', {})
                        for field_name in ref_protected:
                            if field_name in def_props:
                                def_props[field_name].setdefault('ui', {})['protected'] = True

        # Inject __ui__ hints into schema (model-level)
        ui_config = getattr(cls, '__ui__', None)
        if ui_config:
            schema['ui'] = dict(ui_config)
            # Inject method UI hints into method schema entries
            method_ui = ui_config.get('methods', {})
            for method_name, hints in method_ui.items():
                if method_name in schema.get('methods', {}):
                    schema['methods'][method_name]['ui'] = dict(hints)

        # Inject __ui__ and access rules from referenced models into their $defs entries
        if referenced_models and '$defs' in schema:
            for model in referenced_models:
                if model.__name__ not in schema['$defs']:
                    continue
                ref_ui = getattr(model, '__ui__', None)
                if ref_ui:
                    schema['$defs'][model.__name__]['ui'] = dict(ref_ui)
                    # Also inject method UI hints into this $def's method entries
                    ref_method_ui = ref_ui.get('methods', {})
                    def_methods = schema['$defs'][model.__name__].get('methods', {})
                    for method_name, hints in ref_method_ui.items():
                        if method_name in def_methods:
                            def_methods[method_name]['ui'] = dict(hints)
                schema['$defs'][model.__name__]['access'] = access_schema(model)

        # Add JSON Schema metadata
        schema['$schema'] = f"{config.API_URL}/Schema"
        schema['$id'] = f"{config.API_URL}/{cls.__name__}"

        return schema


    @classmethod
    def referenced_json_schema(cls) -> Dict[str, Any]:
        """
        Returns the schema for the Ref field.
        This is a convenience method to expose the Ref schema.
        """
        schema = cls.model_json_schema()
        # Resolve Ref field schemas into proper $ref
        if 'properties' in schema:
            for field_name, field_info in cls.model_fields.items():
                field_type = field_info.annotation
                if _is_self_ref(field_type):
                    schema['properties'][field_name] = {"type": "selfref"}
                elif get_origin(field_type) is Ref:
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
        schema['$schema'] = f"{config.API_URL}/Schema"
        schema['$id'] = f"{config.API_URL}/{cls.__name__}"
        schema['__name__'] = cls.__name__
        schema['__owner__'] = cls.__owner__.__name__ if hasattr(cls, '__owner__') else None
        schema['__parent__'] = cls.__parent__.__name__ if hasattr(cls, '__parent__') else None
        schema['__tablename__'] = cls.__tablename__ if hasattr(cls, '__tablename__') else ""
        # Reset referenced models for the next call
        for field_name, field_info in cls.model_fields.items():
            field_type = field_info.annotation
            if _is_self_ref(field_type):
                continue
            if get_origin(field_type) is Ref:
                target = get_args(field_type)[0]
                if target.__name__ not in cls._referenced_models:
                    record_model_type(cls, target)

        return schema

    @staticmethod
    def blueprint():
        """
        Returns the blueprint of registered models
        """
        from pybend.core.utils.registrar import registered_models
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

    logger.info("[%s.%s] Generating join model '%s' with table '%s'",
                owner_cls.__name__, ref_model.__name__, class_name, tablename)

    # Resolve field_name before creating the model — it determines the URL
    # segment used in routes (e.g., "favorites" vs "likes")
    if not field_name:
        from pybend.core.utils.introspection import get_list_fields
        for fname, child_cls in get_list_fields(owner_cls):
            if child_cls is ref_model:
                field_name = fname
                break

    # Only annotate the new FK field — inherited fields keep their defaults
    annotations = {fk_field: int}

    fields = {
        "__tablename__": tablename,
        "__tagname__": field_name or ref_model.__tablename__,
        "__storable__": True,
        "__owner__": owner_cls,
        "__parent__": ref_model,
        "__module__": ref_model.__module__,
        "__annotations__": annotations,
        fk_field: Field(..., alias=fk_field, description=f"FK to {owner_name}")
    }
    join_model = type(class_name, (ref_model,), fields)

    # Cache join model on the parent class for FK hydration
    if field_name:
        if not hasattr(owner_cls, '__fk_models__') or owner_cls.__fk_models__ is ProtoModel.__fk_models__:
            owner_cls.__fk_models__ = {}
        owner_cls.__fk_models__[field_name] = join_model

    return join_model

