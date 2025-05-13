# app/models/base_model.py
import json

from pydantic import BaseModel as PydanticBaseModel
from typing import Any, Dict, Type

from utils.decorators import expose_route
from .storable_mixin import StorableMixin

class ProtoModel(PydanticBaseModel):
    """
    Base model that optionally adds StorableMixin based on the 'storable' class attribute.
    """

    def __init_subclass__(cls, **kwargs):
        # Checks if the class has a 'storable' attribute, defaulting to False
        storable = getattr(cls, 'storable', False)
        # If 'storable' is True, injects StorableMixin into the class
        if storable and StorableMixin not in cls.__bases__:
            cls.__bases__ = (StorableMixin,) + cls.__bases__
        super().__init_subclass__(**kwargs)

    @classmethod
    def completion_cls(cls) -> Type:
        """
        Returns the completion class to be used for this model.
        """

        raise NotImplementedError

    @classmethod
    @expose_route('/schema', methods=['GET'])
    def schema(cls) -> Dict[str, Any]:
        """
        Returns the schema for this model.
        """
        print("Hello from ProtoModel.schema()")
        print(cls.schema_json())
        return json.loads(cls.schema_json())