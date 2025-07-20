import inspect
import json
from typing import Dict, Any, Callable, get_type_hints, get_args, get_origin, Union

from pydantic import BaseModel, create_model
from pydantic.json_schema import model_json_schema


def pydantic_schema_for_type(t) -> Dict[str, Any]:
    """
    Extracts a Pydantic-style JSON schema or $ref for a given type.
    """
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
    This recursively inspect classes in the method signatures of the exposed methods. It does not include the references
    from the class fields, as those are already included by pydantic's model_json_schema().
    """
    assert issubclass(cls_, BaseModel), "cls_ must be a subclass of BaseModel"
    assert hasattr(cls_, '__pybend_methods_json_signature__'), "cls_ must have a methods_json method to gather referenced models"

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
    _ = cls_.__pybend_methods_json_signature__()

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