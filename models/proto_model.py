# app/models/base_model.py

from pydantic import BaseModel as PydanticBaseModel
from typing import Any, Dict, Type

from .storable_mixin import StorableMixin

class ProtoModel(PydanticBaseModel):
    """
    Base model that optionally adds StorableMixin based on the 'storable' class attribute.
    """

    def __init_subclass__(cls, **kwargs):
        storable = getattr(cls, 'storable', False)
        if storable and StorableMixin not in cls.__bases__:
            cls.__bases__ = (StorableMixin,) + cls.__bases__
        super().__init_subclass__(**kwargs)

    @classmethod
    def completion_cls(cls) -> Type:
        """
        Returns the completion class to be used for this model.
        """

        raise NotImplementedError