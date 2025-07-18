import inspect
import json
from typing import Dict, Any, Callable, get_type_hints

from pydantic import BaseModel, create_model
from pydantic.json_schema import model_json_schema
def pydantic_schema_for_type(t) -> Dict[str, Any]:
    """
    Extracts a Pydantic-style JSON schema or $ref for a given type.
    """
    if isinstance(t, type) and issubclass(t, BaseModel):
        return {"$ref": f"#/$defs/{t.__name__}"}
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


def collect_all_referenced_models(cls, seen: set = None) -> set:
    """
    Recursively collects all Pydantic models used in method signatures of this model and nested models.
    """
    if seen is None:
        seen = set()
    if cls in seen:
        return seen
    seen.add(cls)

    # Ensure current model's methods are parsed
    _ = cls.methods_json()

    # Recurse into referenced models
    for model in cls._referenced_models.copy():
        if model not in seen:
            collect_all_referenced_models(model, seen)

    return seen


def pydantic_method_signature(method: Callable) -> Dict[str, Any]:
    """
    Generates a signature for a method, including its parameters and return type.
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