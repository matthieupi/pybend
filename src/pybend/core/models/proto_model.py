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
        __storable__ = getattr(cls, '__storable__', False)
        # If 'storable' is True, injects StorableMixin into the class
        if __storable__ and StorableMixin not in cls.__bases__:
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
        schema = json.loads(cls.schema_json())
        schema['__type__'] = 'schema'
        schema['__name__'] = cls.__name__
        schema['__tablename__'] = cls.__tablename__ if hasattr(cls, '__tablename__') else ""
        return schema

    @staticmethod
    def blueprint():
        """
        Returns the blueprint of registered models
        """
        from utils.registrar import registered_models
        print("Hello from ProtoModel.blueprint()")
        blueprint = {}
        for model_name, model_cls in registered_models.items():
            blueprint[model_name] = model_cls.schema()
        return blueprint