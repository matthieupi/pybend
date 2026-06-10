import functools
import inspect
import json
import logging
from typing import Dict, Any, Callable, List, Tuple, Type, get_type_hints, get_args, get_origin, Union

from pydantic import BaseModel, create_model
from pydantic.json_schema import model_json_schema

from .typer import Ref, _SelfRefMarker

logger = logging.getLogger('n3tx.utils')


def pydantic_schema_for_type(t) -> Dict[str, Any]:
    """
    Extracts a Pydantic-style JSON schema or $ref for a given type.
    """
    if hasattr(t, '__origin__'):
        logger.debug("Processing type: %s, origin: %s", t, get_origin(t))
    if hasattr(t, '__origin__') and t.__origin__ is Ref:
        target_type = get_args(t)[0]
        return {"type": "$ref", "$ref": f"#/$defs/{target_type.__name__}"}


    if isinstance(t, type) and issubclass(t, BaseModel):
        return {"type": "$ref", "$ref": f"#/$defs/{t.__name__}"}
    elif t == str:
        return {"type": "string"}
    elif t == int:
        return {"type": "integer"}
    elif t == float:
        return {"type": "number"}
    elif t == bool:
        return {"type": "boolean"}
    elif getattr(t, '__origin__', None) is list:
        item_type = t.__args__[0]
        return {
            "type": "array",
            "items": pydantic_schema_for_type(item_type)
        }
    elif getattr(t, '__origin__', None) is dict:
        return {"type": "object"}

    return {"type": "string"}  # Fallback


def record_model_type(cls_, type_):
    """
    Collect the base Type from a type hint, recursively, and saves it in ther class's _referenced_models set.
    """
    origin = get_origin(type_)
    args = get_args(type_)
    # If nested collection types, recursively record their models
    if origin in (list, tuple, set, dict, Union):
        for arg in args:
            record_model_type(cls_, arg)
    # If we reached the root type or a Pydantic model, record it
    elif isinstance(type_, type) and issubclass(type_, BaseModel):
        cls_._referenced_models.add(type_)


def collect_all_referenced_models(cls_, seen: set = None) -> set:
    """
    Recursively collects all models referenced by the given ProtModel cls_.
    This recursively inspect classes in the method signatures of the exposed methods
    and Ref[T] field types (single FK references to other models).
    """
    assert issubclass(cls_, BaseModel), "cls_ must be a subclass of BaseModel"
    assert hasattr(cls_, '__n3tx_methods_json_signature__'), "cls_ must have a methods_json method to gather referenced models"

    if seen is None:
        seen = set()
    if cls_ in seen:
        return seen
    seen.add(cls_)

    # Ensure current model's methods are parsed
    # TODO - Updates the logic to remove the coupling side effect
    #        This walks the tree of methods and saves the discovered models into cls._referenced_models, but it should
    #        be optimized both for performance (it is called again in the cls.schema) and to remove the coupling with
    #        the cls._referenced_models, which could easily lead to bugs in the future.
    _ = cls_.__n3tx_methods_json_signature__()

    # Also collect Ref[T] targets (single FK references to other models)
    for field_name, target_cls in get_ref_fields(cls_):
        cls_._referenced_models.add(target_cls)

    # Also collect ListRef[T] targets (collection references) so their
    # schemas get the Ref[T] patching treatment in the defs() stage.
    for field_name, target_cls in get_list_fields(cls_):
        cls_._referenced_models.add(target_cls)

    # Recurse into referenced models
    for model in cls_._referenced_models.copy():
        if model not in seen:
            collect_all_referenced_models(model, seen)

    return seen


def pydantic_method_signature(method: Callable) -> Dict[str, Any]:
    """
    Generates a signature for a method, including its parameters and return type.
    TODO - Currently unused. In the future this should ber used in proto_model.methods_json() to generate the base
           signature
    """
    sig = inspect.signature(method)
    type_hints = get_type_hints(method)

    parameters = {}
    for name, param in sig.parameters.items():
        if name in ('cls', 'self'):
            continue
        ptype = type_hints.get(name, param.annotation)
        parameters[name] = pydantic_schema_for_type(ptype)

    rtype = type_hints.get('return', None)
    return_type_schema = pydantic_schema_for_type(rtype) if rtype else {}

    return {
        'parameters': parameters,
        'returns': return_type_schema
    }


def _unwrap_listref(field_type, field_metadata=None):
    """If field_type is ListRef[T] (Annotated with a model_type marker), return T.
    Checks both the type's __metadata__ (Annotated) and Pydantic's FieldInfo.metadata.
    Otherwise return None."""
    # Check type-level Annotated metadata
    if hasattr(field_type, '__metadata__'):
        for meta in field_type.__metadata__:
            if hasattr(meta, 'model_type'):
                return meta.model_type
    # Check Pydantic FieldInfo.metadata (Pydantic v2 separates Annotated metadata here)
    if field_metadata:
        for meta in field_metadata:
            if hasattr(meta, 'model_type'):
                return meta.model_type
    return None


def _unwrap_many_to_many(field_type, field_metadata=None):
    """If field_type is ManyToMany[T], return (target, through).

    Checks both the type's __metadata__ (Annotated) and Pydantic's
    FieldInfo.metadata. Otherwise returns None.
    """
    metadata = []
    if hasattr(field_type, '__metadata__'):
        metadata.extend(field_type.__metadata__)
    if field_metadata:
        metadata.extend(field_metadata)

    for meta in metadata:
        if hasattr(meta, 'target_model'):
            return meta.target_model, getattr(meta, 'through_model', None)
    return None


@functools.lru_cache(maxsize=None)
def get_many_to_many_fields(model_class: Type[Any]) -> List[Tuple[str, Type, Type | None]]:
    """Return (field_name, target_model, through_model) for ManyToMany fields."""
    results = []
    for field_name, field_info in model_class.model_fields.items():
        field_type = field_info.annotation
        origin = get_origin(field_type)
        if origin is Union and type(None) in get_args(field_type):
            field_type = get_args(field_type)[0]

        relation = _unwrap_many_to_many(field_type, getattr(field_info, 'metadata', None))
        if relation is None:
            continue

        target_model, through_model = relation
        if isinstance(target_model, str):
            import sys
            module = sys.modules.get(model_class.__module__)
            target_model = getattr(module, target_model, None) if module else None
        if isinstance(through_model, str):
            import sys
            module = sys.modules.get(model_class.__module__)
            through_model = getattr(module, through_model, None) if module else None
        if target_model is not None:
            results.append((field_name, target_model, through_model))
    return results


@functools.lru_cache(maxsize=None)
def get_list_fields(model_class: Type[Any]) -> List[Tuple[str, Type]]:
    """
    Returns a list of (field_name, child_model_class) for every
    field typed as ListRef[SomeBaseModel] or List[SomeBaseModel]
    on *model_class*.  Unwraps Optional transparently.

    Example:
        class Product(BaseModel):
            comments: Optional[ListRef[Comment]] = []

        get_list_fields(Product)  ->  [("comments", Comment)]
    """
    results = []
    for field_name, field_info in model_class.model_fields.items():
        field_type = field_info.annotation

        origin = get_origin(field_type)
        # Unwrap Optional[...]
        if origin is Union and type(None) in get_args(field_type):
            field_type = get_args(field_type)[0]
            origin = get_origin(field_type)

        # Check for ListRef[T] (Annotated with _ListRefMarker)
        ref_model = _unwrap_listref(field_type, getattr(field_info, 'metadata', None))
        if ref_model is not None:
            # Resolve forward reference strings to actual classes
            if isinstance(ref_model, str):
                import sys
                module = sys.modules.get(model_class.__module__)
                ref_model = getattr(module, ref_model, None) if module else None
                if ref_model is None:
                    continue
            results.append((field_name, ref_model))
            continue

        # Fallback: plain List[BaseModel]
        if origin is list:
            args = get_args(field_type)
            if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
                results.append((field_name, args[0]))
    return results


@functools.lru_cache(maxsize=None)
def get_ref_fields(model_class: Type[Any]) -> List[Tuple[str, Type]]:
    """
    Returns a list of (field_name, target_model_class) for every
    field typed as Ref[SomeBaseModel] (single FK reference, not self-ref).
    Unwraps Optional transparently.
    """
    results = []
    for field_name, field_info in model_class.model_fields.items():
        field_type = field_info.annotation
        origin = get_origin(field_type)
        # Unwrap Optional[...]
        if origin is Union and type(None) in get_args(field_type):
            field_type = get_args(field_type)[0]
            origin = get_origin(field_type)
        # Skip self-refs
        if _is_self_ref(field_info.annotation):
            continue
        # Check for Ref[T] (generic alias with origin Ref)
        if origin is Ref:
            args = get_args(field_type)
            if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
                results.append((field_name, args[0]))
    return results


@functools.lru_cache(maxsize=None)
def get_json_fields(model_class: Type[Any]) -> List[str]:
    """Return field names that should be stored as JSON TEXT in SQLite.

    Matches dict (any variant) and list (bare or typed like List[str], List[int])
    but NOT ListRef[T] or List[BaseModel] which use FK join tables.
    """
    results = []
    for field_name, field_info in model_class.model_fields.items():
        field_type = field_info.annotation
        origin = get_origin(field_type)
        # Unwrap Optional[T]
        if origin is Union and type(None) in get_args(field_type):
            field_type = get_args(field_type)[0]
            origin = get_origin(field_type)
        # dict (any variant)
        if field_type is dict or origin is dict:
            results.append(field_name)
            continue
        # list — only if NOT ListRef and NOT List[BaseModel]
        if field_type is list or origin is list:
            ref_model = _unwrap_listref(field_type, getattr(field_info, 'metadata', None))
            if ref_model is not None:
                continue
            if _unwrap_many_to_many(field_type, getattr(field_info, 'metadata', None)) is not None:
                continue
            args = get_args(field_type)
            if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
                continue
            results.append(field_name)
    return results


def _is_self_ref(field_type) -> bool:
    """Check if a field type is Ref['self'] (Annotated[int, _SelfRefMarker]).
    Unwraps Optional transparently."""
    origin = get_origin(field_type)
    # Unwrap Optional[...]
    if origin is Union and type(None) in get_args(field_type):
        field_type = get_args(field_type)[0]
    if hasattr(field_type, '__metadata__'):
        for meta in field_type.__metadata__:
            if isinstance(meta, _SelfRefMarker):
                return True
    return False
