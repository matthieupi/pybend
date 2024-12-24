# app/utils/registrar.py

from typing import Dict, Type, Any
from server.storage.abstract_storage import AbstractStorage as StorageInterface
from server.models.storable_mixin import StorableMixin

registered_models: Dict[str, Type[Any]] = {}


def register_model(model_class: Type[Any], storage: StorageInterface = None):
    """
    Registers a model class with the system. If the model is storable, injects the storage backend.
    """
    if hasattr(model_class, 'storable') and model_class.storable:
        if storage is None:
            raise ValueError(f"Storage backend must be provided for model '{model_class.__name__}'")
        model_class.set_storage(storage)
        model_class.create_table()
    registered_models[model_class.__tablename__] = model_class
