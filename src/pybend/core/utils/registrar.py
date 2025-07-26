# app/utils/registrar.py

from typing import Dict, Type, Any
from storage.abstract_storage import AbstractStorage as StorageInterface

registered_models: Dict[str, Type[Any]] = {}

join_models: Dict[tuple[str, str], Type[Any]] = {}


def register_model(model_class: Type[Any], storage: StorageInterface = None ):

    if hasattr(model_class, '__owner__'):
        parent = model_class.__owner__
        base = model_class.__bases__[-1]  # Assuming join model inherits from base
        join_models[(parent.__name__, base.__name__)] = model_class

    if hasattr(model_class, '__storable__') and model_class.__storable__:
        if storage is None:
            raise ValueError(f"Storage backend must be provided for model '{model_class.__name__}'")
        model_class.set_storage(storage)
        model_class.create_table()
        if hasattr(storage, 'migrate_table'):
            storage.migrate_table(model_class)  # <--- run auto-migration
    registered_models[model_class.__tablename__] = model_class
