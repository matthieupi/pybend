from typing import Generic, TypeVar, Optional, Any, get_args, get_origin
from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic_core import core_schema
from pydantic.json_schema import JsonSchemaValue
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

def flatten_foreign_keys(obj: BaseModel) -> dict:
    """
    Recursively flatten any ForeignKey[...] fields to plain ints for storage/validation purposes.
    """
    flat = obj.model_dump()
    for field, value in flat.items():
        if isinstance(value, ForeignKey):
            flat[field] = int(value)
        elif isinstance(value, BaseModel):
            flat[field] = flatten_foreign_keys(value)
        elif isinstance(value, list):
            flat[field] = [
                int(v) if isinstance(v, ForeignKey) else v for v in value
            ]
    return flat


class ForeignKey(Generic[T]):
    """
    A generic wrapper for foreign key fields that enforces type safety,
    emits OpenAPI $ref, and stores just the FK id.
    """

    def __init__(self, value: Optional[Any] = None):
        print(f"[FOREIGNKEY] Initializing with value: {value}")
        if isinstance(value, BaseModel):
            self.id = getattr(value, 'id', None)
            self._model = value
        elif isinstance(value, int):
            self.id = value
            self._model = None
        elif isinstance(value, dict):
            self.id = value.get("id", None)
            self._model = None
        else:
            raise ValueError(f"Invalid FK assignment: {value}")

    def __int__(self):
        return self.id

    def __repr__(self):
        return str(self.id)

    def __str__(self):
        return f"<ForeignKey id={self.id}>"

    def __json__(self):
        """
        Custom JSON serialization to return just the id.
        """
        return self.id

    def model_dump(self):
        return self.id

    def to_python(self, *args, **kwargs):
        return self.id  # last-ditch serializer fallback



    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        return core_schema.json_or_python_schema(
            python_schema=core_schema.no_info_plain_validator_function(
                lambda v: int(v) if isinstance(v, ForeignKey) else v
            ),
            json_schema=core_schema.int_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: int(v) if v is not None else None
            )
        )


    @classmethod
    def validate(cls, v):
        return cls(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: core_schema.CoreSchema, handler) -> JsonSchemaValue:
        # Defensive resolution of T
        args = get_args(cls)
        if not args:
            # No target type = fallback to int
            return {"type": "integer"}

        target = args[0]
        if not isinstance(target, type) or not issubclass(target, BaseModel):
            return {"type": "integer"}

        return {
            "type": "$ref",
            "$ref": f"#/$defs/{target.__name__}"
        }
