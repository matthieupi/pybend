from typing import Generic, TypeVar, Optional, Any, get_args, get_origin
from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic_core import core_schema
from pydantic.json_schema import JsonSchemaValue

T = TypeVar("T", bound=BaseModel)



class ForeignKey(Generic[T]):
    """
    A generic wrapper for foreign key fields that enforces type safety,
    emits OpenAPI $ref, and stores just the FK id.
    """

    def __init__(self, value: Optional[Any] = None):
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
        return f"<ForeignKey id={self.id}>"

    def model_dump(self):
        return self.id

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.int_schema()
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
