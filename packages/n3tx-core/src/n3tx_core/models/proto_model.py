# app/models/base_model.py
import copy
import inspect
import json
import logging

from pydantic import BaseModel as PydanticBaseModel, ConfigDict, GetJsonSchemaHandler, BaseModel, Field
from typing import Any, ClassVar, Dict, Type, get_type_hints, get_origin, get_args, Union

from pydantic.json_schema import JsonSchemaValue, JsonSchemaMode, GenerateJsonSchema, DEFAULT_REF_TEMPLATE
from pydantic_core import CoreSchema

from n3tx_core import config
import n3tx_core.models.proto_schema as proto_schema
import n3tx_core.models.proto_dump as proto_dump
from n3tx_core.utils.decorators import expose_route, exposed_method_info
from n3tx_core.utils.descriptors import fullmethod
from n3tx_core.utils.introspection import pydantic_schema_for_type, record_model_type, _is_self_ref
from n3tx_core.utils.typer import Ref, _SelfRefMarker
from .storable_mixin import StorableMixin

logger = logging.getLogger('n3tx.models')


# ── Mixin registry ──────────────────────────────────────────────────────────
# External packages register mixins via register_mixin() at import time.
# ProtoModel.__init_subclass__ loops this registry to inject mixins.

_mixin_registry: list[tuple] = []  # (flag, mixin_cls, also_if)


def register_mixin(flag: str, mixin_cls: type, *, also_if: list[str] = None) -> None:
    """Register an external mixin for auto-injection via __init_subclass__.

    Args:
        flag:      ClassVar name that triggers injection (e.g. '__viewable__')
        mixin_cls: The mixin class to prepend to cls.__bases__
        also_if:   Additional ClassVar names that also trigger injection.
                   When any fires, flag is also set to True on the class.

    Called at import time by external packages (n3tx-ui, n3tx-agents).
    Packages must be imported before models with these flags are defined.
    """
    _mixin_registry.append((flag, mixin_cls, also_if or []))


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

    # --- Performance cache ---
    # Schema generation is expensive. Cache per model class so GET /{ClassName}
    # is a dict copy instead of a full rebuild. Response meta cache lives in
    # proto_dump module (dump pipeline stage).
    _schema_cache: ClassVar[dict] = {}

    id: int = Field(default=0)
    image: str = Field(default='')

    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # allows Ref through
        ignored_types=(fullmethod,),
        extra='allow',  # allows $schema/$id to pass through FastAPI response model
        json_encoders={
            Ref: lambda fk: int(fk),
        },
    )

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
                # Rewrite annotations dynamically
                if new_annotations:
                    cls.__annotations__ = dict(cls.__annotations__)  # make a copy
                    cls.__annotations__.update(new_annotations)
        # External mixin injection (register via register_mixin())
        for flag, mixin_cls, also_if in _mixin_registry:
            triggered = getattr(cls, flag, False)
            if not triggered and also_if:
                triggered = any(getattr(cls, alt, None) for alt in also_if)
                if triggered:
                    setattr(cls, flag, True)  # normalize the flag
            if triggered and not issubclass(cls, mixin_cls):
                cls.__bases__ = (mixin_cls,) + cls.__bases__

        super().__init_subclass__(**kwargs)


    def __init__(self, *args, **kwargs):
        """Initialize the model and hydrate local relationship fields."""
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
        params = self.__class__.hydrate_fk(params)
        super().__init__(*args, **params)


    def model_response(self, **kwargs) -> Dict[str, Any]:
        """Enriched data via dump pipeline. For HTTP API responses.

        Runs proto_dump stages: base → relationships → schema_url →
        instance_url → populate, plus registered extensions.
        """
        return proto_dump.run_pipeline(self, **kwargs)

    @classmethod
    def __n3tx_methods_json_signature__(cls) -> dict:
        """
        Returns a dictionary of exposed methods including their route, parameters, and return type.
        Also gathers all referenced Pydantic models for inclusion in $defs.
        """
        methods = {}

        for method_name in dir(cls):
            exposed = exposed_method_info(cls, method_name)
            if exposed is None:
                continue

            method = exposed.func
            sig = inspect.signature(method)
            type_hints = get_type_hints(method, globalns=method.__globals__, localns=locals())
            endpoint_info = exposed.endpoint

            # Extract parameter schemas and record model types
            parameters = {}
            required_params = []
            for name, param in sig.parameters.items():
                if name in ('cls', 'self', 'user'):
                    continue
                ptype = type_hints.get(name, param.annotation)
                parameters[name] = pydantic_schema_for_type(ptype)
                record_model_type(cls, ptype)
                if param.default is inspect.Parameter.empty:
                    required_params.append(name)

            # Return type schema
            rtype = type_hints.get('return', None)
            return_type_schema = pydantic_schema_for_type(rtype) if rtype else {}
            record_model_type(cls, rtype)
            method_entry = {
                'route': endpoint_info['route'],
                'methods': endpoint_info['methods'],
                'scope': exposed.scope,
                'requires_instance': exposed.requires_instance,
                'parameters': parameters,
                'required': required_params,
                'returns': return_type_schema,
            }
            if endpoint_info.get('stream'):
                method_entry['stream'] = True
            if endpoint_info.get('events'):
                method_entry['events'] = {
                    name: evt_cls.model_json_schema()
                    for name, evt_cls in endpoint_info['events'].items()
                }
            if endpoint_info.get('access') and hasattr(endpoint_info['access'], 'to_dict'):
                method_entry['access'] = endpoint_info['access'].to_dict()
            methods[method_name] = method_entry

        return methods

    @classmethod
    def invalidate_schema_cache(cls):
        """Clear cached schema for this model (e.g., during tests or after
        dynamic model redefinition). In normal operation schemas are immutable
        once the server starts, so this is rarely needed."""
        ProtoModel._schema_cache.pop(cls, None)

    @classmethod
    def schema(cls) -> Dict[str, Any]:
        """Returns the schema for this model via composable pipeline.

        Stages are registered in proto_schema (base, strip_hidden, methods,
        defs, access, ui, metadata). Extensions add stages via
        @schema_extension without modifying the core pipeline.
        """
        if cls in ProtoModel._schema_cache:
            return copy.deepcopy(ProtoModel._schema_cache[cls])

        s = proto_schema.run_pipeline(cls)

        ProtoModel._schema_cache[cls] = s
        return copy.deepcopy(s)


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
    def hydrate_fk(cls, data):
        """Hydrate local FK fields (``field: T`` and ``field: list[T]``)."""
        if not isinstance(data, dict):
            return data

        from n3tx_core.utils.introspection import get_fk_fields, get_fk_list_fields, get_json_fields

        updated = dict(data)
        json_fields = set(get_json_fields(cls))

        for field_name, target_cls in get_fk_fields(cls):
            if field_name in updated:
                updated[field_name] = _hydrate_fk_value(target_cls, updated.get(field_name))

        for field_name, target_cls in get_fk_list_fields(cls):
            if field_name not in json_fields:
                continue
            if field_name in updated:
                updated[field_name] = _hydrate_fk_list(target_cls, updated.get(field_name))

        return updated


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
        from n3tx_core.utils.registrar import registered_models
        blueprint = {}
        for model_name, model_cls in registered_models.items():
            blueprint[model_name] = model_cls.schema()
        return blueprint


def _hydrate_fk_value(target_cls: Type[PydanticBaseModel], value: Any) -> Any:
    """Hydrate one local model relationship value through the target model."""
    # Prevent re-hydration if value already cls instance
    if value is None or isinstance(value, target_cls):
        return value
    # Hydrate dict value
    if isinstance(value, dict):
        if 'id' in value:
            value = value.get('id')
        elif '$id' in value:
            value = value.get('$id')
        else:
            return target_cls(**value)
    # Hydrate from direct target id
    from n3tx_core.models.ref import local_ref_id
    target_id = local_ref_id(value, target_cls=target_cls)
    if target_id is None:
        return value
    try:
        return target_cls(id=target_id)
    except Exception:
        return None


def _hydrate_fk_list(target_cls: Type[PydanticBaseModel], values: Any) -> list:
    """Hydrate an ordered local model relationship list."""
    if values is None:
        return []
    if not isinstance(values, list):
        values = [values]

    from n3tx_core.models.ref import local_ref_id

    # Keep already-hydrated instances and inline child payloads without fetching
    # them again. Inline dicts without id/$id are construction payloads, not refs.
    hydrated = [value for value in values if isinstance(value, target_cls)]
    for value in values:
        if isinstance(value, dict) and 'id' not in value and '$id' not in value:
            try:
                hydrated.append(target_cls(**value))
            except Exception:
                pass

    # Extract local ids from raw ids, dicts, refs, and current-service URLs.
    ids = [
        local_id for local_id in (
            local_ref_id(value, target_cls=target_cls)
            for value in values
            if not isinstance(value, target_cls)
            and not (isinstance(value, dict) and 'id' not in value and '$id' not in value)
        )
        if local_id is not None
    ]

    # Batch-load ids once, then restore the JSON-stored order.
    try:
        fetched = target_cls.list(ids=ids) if ids else []
    except Exception:
        fetched = []
    fetched = fetched.get('data', []) if isinstance(fetched, dict) else fetched
    by_id = {getattr(item, 'id', None): item for item in fetched}
    hydrated.extend(by_id[id_] for id_ in ids if id_ in by_id)
    return hydrated
