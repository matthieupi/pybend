"""Persistence contract for model CRUD, filtering and list ordering."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type


class AbstractStorage(ABC):
    """Define the storage interface for model CRUD operations."""

    @abstractmethod
    def create_table(self, model_class: Type[Any]):
        """Create the persistent schema for a model."""
        pass

    @abstractmethod
    def create(self, model_class: Type[Any], data: Dict[str, Any]) -> Any:
        """Persist field data and return the created model instance."""
        pass

    @abstractmethod
    def list(self, model_class: Type[Any], sql_filter: tuple = None,
             limit: int = None, offset: int = None, populate=None,
             ids: list = None, *, order_asc: str | None = None,
             order_desc: str | None = None) -> List[Any]:
        """List models, optionally ordering by one stored field before paging.

        Directions are mutually exclusive. Invalid ordering raises ValueError.
        A limit returns a data/meta page with a count independent of order."""
        pass

    @abstractmethod
    def get(
        self, model_class: Type[Any], id_: int = None, as_dict: bool = False,
        populate=None, **kwargs,
    ) -> Any:
        """Retrieve a model or raw field data by identity."""
        pass

    @abstractmethod
    def update(self, model_class: Type[Any], id_: int, data: Dict[str, Any]):
        """Persist supplied field values for an existing model."""
        pass

    @abstractmethod
    def delete(self, model_class: Type[Any], id_: int):
        """Remove the model with the supplied identity."""
        pass


# Changelog
# - 2026-11-02: Define optional single-field native list ordering.
