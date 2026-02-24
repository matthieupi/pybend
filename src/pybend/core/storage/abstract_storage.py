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
    def list(self, model_class: Type[Any], sql_filter: tuple = None,
             limit: int = None, offset: int = None, populate=None) -> List[Any]:
        pass

    @abstractmethod
    def get(self, model_class: Type[Any], id_: int = None, as_dict: bool = False,
            populate=None, **kwargs) -> Any:
        pass

    @abstractmethod
    def update(self, model_class: Type[Any], id_: int, data: Dict[str, Any]):
        pass

    @abstractmethod
    def delete(self, model_class: Type[Any], id_: int):
        pass
