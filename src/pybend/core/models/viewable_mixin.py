# app/models/storable_mixin.py

from typing import ClassVar, Any, List
from ..storage.abstract_storage import AbstractStorage as StorageInterface


class ViewableMixin:
    """
    Mixin that provides storage capabilities to models via dependency injection.
    """

    name: str
    desc: str


    @classmethod
    def view(cls, storage: StorageInterface):
        """
        View function for the model.
        """
        raise NotImplementedError

