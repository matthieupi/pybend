# app/models/storable_mixin.py

from typing import ClassVar, Any, List, Union

from pydantic import BaseModel

from storage.abstract_storage import AbstractStorage as StorageInterface
from utils.registrar import join_models
from utils.typer import Ref



class StorableMixin:
    """
    Mixin that provides storage capabilities to models via dependency injection.
    """

    __pk__: ClassVar[str] = 'id'  # Primary key field name
    __tablename__: ClassVar[str]
    storage: ClassVar[StorageInterface] = None  # This will be injected

    def _storage_dict(self, exclude_unset: bool = True) -> dict:
        """Extract all field values for storage, including Pydantic-excluded fields."""
        data = self.model_dump(exclude_unset=exclude_unset)
        # Re-add any fields marked exclude=True (hidden from API but needed in DB)
        for name, fi in self.model_fields.items():
            if fi.exclude and name not in data:
                val = getattr(self, name, None)
                if val is not None or not exclude_unset:
                    data[name] = val
        return data

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
                join_data = {**data._storage_dict(exclude_unset=True), fk_field: parent.id}
                for k, v in join_data.items():
                    if isinstance(v, Ref):
                        join_data[k] = int(v)  # unwrap FK to plain int

                return join_cls.create(join_cls(**join_data))

        # Fallback to normal behavior
        data_dict = data._storage_dict(exclude_unset=True)
        for k, v in data_dict.items():
            if isinstance(v, Ref):
                data_dict[k] = int(v)  # unwrap FK to plain int

        print(f'Creating {cls.__name__} with data: {data_dict}')
        return cls.storage.create(cls, data_dict)

    @classmethod
    def list(cls, sql_filter: tuple = None) -> List[Any]:
        """
        Retrieves all records using the storage backend.
        Optional sql_filter: (where_clause, params) for authorization pushdown.
        """
        return cls.storage.list(cls, sql_filter=sql_filter)

    @classmethod
    def get(cls, id: int, as_dict: bool = False) -> Any:
        """
        Retrieves a record by ID using the storage backend.
        """
        return cls.storage.get(cls, id, as_dict=as_dict)

    @classmethod
    def update(cls, id: int, data: Union[BaseModel, dict]):
        """
        Updates a record using the storage backend.
        """
        print(f'Updating {cls.__name__} ID={id} with data: {data}')
        if isinstance(data, BaseModel):
            data_dict = data.model_dump(exclude_unset=True)
        elif isinstance(data, dict):
            data_dict = data
        else:
            raise ValueError(f"[UPDATING {cls.__name__}-{id}] Invalid data type for update: {type(data)}")
        cls.storage.update(cls, id, data_dict)
        return cls.get(id)

    @classmethod
    def delete(cls, id: int):
        """
        Deletes a record using the storage backend.
        """
        cls.storage.delete(cls, id)
