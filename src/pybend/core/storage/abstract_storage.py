# app/storage/storage_interface.py

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type


class AbstractStorage(ABC):
    """
    Abstract base class defining the storage interface for CRUD operations.
    """

    @abstractmethod
    def create_table(self, model_class: Type[Any]):
        pass

    @abstractmethod
    def create(self, model_class: Type[Any], data: Dict[str, Any]) -> Any:
        pass

    @abstractmethod
    def list(self, model_class: Type[Any]) -> List[Any]:
        pass

    @abstractmethod
    def get(self, model_class: Type[Any], id_: int = None, **kwargs) -> Any:
        pass

    @abstractmethod
    def update(self, model_class: Type[Any], id_: int, data: Dict[str, Any]):
        pass

    @abstractmethod
    def delete(self, model_class: Type[Any], id_: int):
        pass
