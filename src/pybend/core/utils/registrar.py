# app/utils/registrar.py

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Type, Any
from pybend.core.storage.abstract_storage import AbstractStorage as StorageInterface

logger = logging.getLogger('pybend.utils')

registered_models: Dict[str, Type[Any]] = {}

join_models: Dict[tuple[str, str], Type[Any]] = {}


@dataclass
class RegistrationResult:
    """Pure description of what register_model() will do."""
    model_class: Type[Any]
    tablename: str
    storage: Optional[StorageInterface]
    is_storable: bool
    is_join: bool
    join_key: Optional[Tuple[str, str]]


def prepare_model(model_class: Type[Any], storage: StorageInterface = None) -> RegistrationResult:
    """Inspect a model and compute registration metadata. Pure — no side effects."""
    is_storable = getattr(model_class, '__storable__', False)
    if is_storable and storage is None:
        raise ValueError(f"Storage backend must be provided for model '{model_class.__name__}'")

    is_join = hasattr(model_class, '__owner__')
    join_key = None
    if is_join:
        parent = model_class.__owner__
        base = model_class.__bases__[-1]
        join_key = (parent.__name__, base.__name__)

    return RegistrationResult(
        model_class=model_class,
        tablename=model_class.__tablename__,
        storage=storage,
        is_storable=is_storable,
        is_join=is_join,
        join_key=join_key,
    )


def apply_registration(result: RegistrationResult) -> None:
    """Execute the side effects described by a RegistrationResult."""
    logger.info("Registering model: %s", result.model_class.__name__)

    if result.is_join and result.join_key:
        join_models[result.join_key] = result.model_class

    if result.is_storable:
        result.model_class.set_storage(result.storage)
        result.model_class.create_table()
        if hasattr(result.storage, 'migrate_table'):
            result.storage.migrate_table(result.model_class)

    registered_models[result.tablename] = result.model_class


def register_model(model_class: Type[Any], storage: StorageInterface = None):
    """Backward-compatible wrapper: prepare + apply in one call."""
    result = prepare_model(model_class, storage)
    apply_registration(result)
