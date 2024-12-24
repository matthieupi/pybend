# app/models/storable_mixin.py

from typing import ClassVar, Any, List
from server.storage.abstract_storage import AbstractStorage as StorageInterface


class StorableMixin:
    """
    Mixin that provides storage capabilities to models via dependency injection.
    """

    __tablename__: ClassVar[str]
    storage: ClassVar[StorageInterface] = None  # This will be injected

    @classmethod
    def set_storage(cls, storage: StorageInterface):
        """
        Sets the storage backend for the model.
        """
        cls.storage = storage

    @classmethod
    def create_table(cls):
        """
        Delegates table creation to the storage backend.
        """
        cls.storage.create_table(cls)

    @classmethod
    def create(cls, data: Any) -> Any:
        """
        Creates a new record using the storage backend.
        """
        data_dict = data.model_dump(exclude_unset=True)
        print(f'Creating {cls.__name__} with data: {data_dict}')
        print(data_dict)
        return cls.storage.create(cls, data_dict)

    @classmethod
    def list(cls) -> List[Any]:
        """
        Retrieves all records using the storage backend.
        """
        return cls.storage.list(cls)

    @classmethod
    def get(cls, id: int) -> Any:
        """
        Retrieves a record by ID using the storage backend.
        """
        return cls.storage.get(cls, id)

    @classmethod
    def update(cls, id: int, data: Any):
        """
        Updates a record using the storage backend.
        """
        data_dict = data.model_dump(exclude_unset=True)
        cls.storage.update(cls, id, data_dict)

    @classmethod
    def delete(cls, id: int):
        """
        Deletes a record using the storage backend.
        """
        cls.storage.delete(cls, id)
