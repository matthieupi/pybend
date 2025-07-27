# app/models/storable_mixin.py

from typing import ClassVar, Any, List
from storage.abstract_storage import AbstractStorage as StorageInterface
from utils.registrar import join_models



class StorableMixin:
    """
    Mixin that provides storage capabilities to models via dependency injection.
    """

    __pk__: ClassVar[str] = 'id'  # Primary key field name
    __tablename__: ClassVar[str]
    storage: ClassVar[StorageInterface] = None  # This will be injected

    def save(self):
        """
        Saves the current instance using the storage backend.
        """
        if not self.id:
            # If no ID, create a new record
            print(f'Saving new {self.__class__.__name__} instance: {self}')
            return self.create(self)
        else:
            # If ID exists, update the existing record
            print(f'Updating existing {self.__class__.__name__} instance: {self}')
            return self.update(self.id, self)

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
        parent = getattr(data, '__owner__', None)

        if parent:
            key = (parent.__class__.__name__, cls.__name__)
            if key in join_models:
                join_cls = join_models[key]
                fk_field = f"{parent.__class__.__name__.lower()}_id"
                join_data = {**data.model_dump(exclude_unset=True), fk_field: parent.id}
                for k, v in join_data.items():
                    if hasattr(v, '__class__') and v.__class__.__name__ == "ForeignKey":
                        join_data[k] = int(v)  # unwrap FK to plain int

                return join_cls.create(join_cls(**join_data))

        # Fallback to normal behavior
        data_dict = data.model_dump(exclude_unset=True)
        for k, v in data_dict.items():
            if hasattr(v, '__class__') and v.__class__.__name__ == "ForeignKey":
                data_dict[k] = int(v)  # unwrap FK to plain int

        print(f'Creating {cls.__name__} with data: {data_dict}')
        return cls.storage.create(cls, data_dict)

    @classmethod
    def list(cls) -> List[Any]:
        """
        Retrieves all records using the storage backend.
        """
        return cls.storage.list(cls)

    @classmethod
    def get(cls, id: int, as_dict: bool = False) -> Any:
        """
        Retrieves a record by ID using the storage backend.
        """
        return cls.storage.get(cls, id, as_dict=as_dict)

    @classmethod
    def update(cls, id: int, data: Any):
        """
        Updates a record using the storage backend.
        """
        print(f'Updating {cls.__name__} ID={id} with data: {data}')
        print(data.model_dump(exclude_unset=True))
        data_dict = data.model_dump(exclude_unset=True)
        cls.storage.update(cls, id, data_dict)
        return cls.get(id)

    @classmethod
    def delete(cls, id: int):
        """
        Deletes a record using the storage backend.
        """
        cls.storage.delete(cls, id)
