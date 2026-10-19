# app/models/storable_mixin.py

import logging
from typing import ClassVar, Any, List, Union

from pydantic import AliasChoices, BaseModel, ValidationError

from n3tx_core.storage.abstract_storage import AbstractStorage as StorageInterface
from n3tx_core.utils.typer import Ref
from n3tx_core.utils.descriptors import fullmethod
from n3tx_core.utils.introspection import get_fk_list_fields

logger = logging.getLogger('n3tx.models')



class StorableMixin:
    """
    Mixin that provides storage capabilities to models via dependency injection.
    """

    __pk__: ClassVar[str] = 'id'  # Primary key field name
    __tablename__: ClassVar[str]
    storage: ClassVar[StorageInterface] = None  # This will be injected

    @classmethod
    def _canonical_update_patch(cls, data: dict) -> dict:
        """Map accepted input aliases to model field names and reject ambiguity."""
        input_names = {}
        for name, field in cls.model_fields.items():
            input_names[name] = name
            for alias in (field.alias, field.validation_alias):
                if isinstance(alias, str):
                    input_names[alias] = name
                elif isinstance(alias, AliasChoices):
                    input_names.update({choice: name for choice in alias.choices if isinstance(choice, str)})

        patch = {}
        sources = {}
        for input_name, value in data.items():
            if input_name in ('$id', '$schema'):
                continue
            name = input_names.get(input_name, input_name)
            if name in patch and sources[name] != input_name:
                raise ValueError(
                    f"Update field {name!r} was supplied more than once "
                    f"({sources[name]!r}, {input_name!r})"
                )
            patch[name] = value
            sources[name] = input_name
        return patch

    def _storage_dict(self, exclude_unset: bool = True) -> dict:
        """Extract all field values for storage, including Pydantic-excluded fields."""
        data = self.model_dump(exclude_unset=exclude_unset)
        # Re-add any fields marked exclude=True (hidden from API but needed in DB)
        for name, fi in self.__class__.model_fields.items():
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
            logger.debug("Saving new %s instance", self.__class__.__name__)
            return self.create(self)
        else:
            # If ID exists, update the existing record
            logger.debug("Updating existing %s instance", self.__class__.__name__)
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
        data_dict = data._storage_dict(exclude_unset=True)
        for k, v in data_dict.items():
            if isinstance(v, Ref):
                data_dict[k] = v.model_dump()  # unwrap FK/ref address for storage

        logger.debug("Creating %s with data: %s", cls.__name__, data_dict)
        return cls.storage.create(cls, data_dict)

    @classmethod
    def list(cls, sql_filter: tuple = None, limit: int = None, offset: int = None,
             populate=None, ids: list = None) -> List[Any]:
        """
        Retrieves all records using the storage backend.
        Optional sql_filter: (where_clause, params) for authorization pushdown.
        Optional limit/offset for pagination — when provided, returns
        {data: [...], meta: {total, limit, offset, has_more}} instead of a plain list.
        Optional populate: PopulateSpec for eager loading of related entities.
        Optional ids: list of IDs to filter by (WHERE id IN (...)).
        """
        return cls.storage.list(cls, sql_filter=sql_filter, limit=limit, offset=offset,
                                populate=populate, ids=ids)

    @classmethod
    def get(cls, id: int, as_dict: bool = False, populate=None) -> Any:
        """
        Retrieves a record by ID using the storage backend.
        Optional populate: PopulateSpec for eager loading of related entities.
        """
        return cls.storage.get(cls, id, as_dict=as_dict, populate=populate)

    @fullmethod
    def update(target, id_or_data: Union[int, BaseModel, dict], data: Union[BaseModel, dict, None] = None):
        """
        Updates a record using the storage backend.

        Supports both class-level and instance-level call shapes:
        - Model.update(id, patch)
        - instance.update(patch)
        - instance.update(id, patch)  # compatibility

        ActorModel subclasses centralize after_update lifecycle publication here
        so direct actor updates and TX-routed updates behave consistently.
        """
        cls = target if isinstance(target, type) else target.__class__
        if isinstance(target, type):
            if data is None:
                raise ValueError(f"[UPDATING {cls.__name__}] Missing update data")
            id = id_or_data
            update_payload = data
        else:
            if data is None:
                id = getattr(target, 'id', None)
                update_payload = id_or_data
            else:
                id = id_or_data
                update_payload = data

            if not id:
                raise ValueError(f"[UPDATING {cls.__name__}] Cannot update unsaved instance without an id")

        logger.debug("Updating %s ID=%s", cls.__name__, id)
        if isinstance(update_payload, BaseModel):
            data_dict = update_payload.model_dump(exclude_unset=True)
        elif isinstance(update_payload, dict):
            data_dict = dict(update_payload)
        else:
            raise ValueError(f"[UPDATING {cls.__name__}-{id}] Invalid data type for update: {type(update_payload)}")

        current = target if not isinstance(target, type) and getattr(target, 'id', None) == id else cls.get(id)
        if current is None:
            logger.warning("Cannot update missing %s ID=%s", cls.__name__, id)
            return None

        # The model remains the only validation contract; no update-only model
        # or duplicate schema is created.
        patch = cls._canonical_update_patch(data_dict)
        patch.pop(cls.__pk__, None)
        if not patch:
            logger.debug("Skipping empty %s update ID=%s", cls.__name__, id)
            return current

        owned_list_fields = {name for name, _target_cls in get_fk_list_fields(cls)}
        for field_name in owned_list_fields & patch.keys():
            if not isinstance(patch[field_name], list):
                raise ValueError(
                    f"Invalid owned relationship {cls.__name__}.{field_name}: "
                    "expected a list"
                )

        current_data = current._storage_dict(exclude_unset=False)
        validation_data = {}
        for name, value in {**current_data, **patch}.items():
            field = cls.model_fields.get(name)
            if field is None:
                validation_data[name] = value
                continue
            validation_alias = field.validation_alias
            if isinstance(validation_alias, AliasChoices):
                validation_alias = next(
                    (choice for choice in validation_alias.choices if isinstance(choice, str)),
                    None,
                )
            validation_name = (
                validation_alias if isinstance(validation_alias, str)
                else field.alias if isinstance(field.alias, str)
                else name
            )
            validation_data[validation_name] = value
        try:
            validated = cls.model_validate(validation_data)
        except ValidationError as exc:
            errors = [
                {'loc': error['loc'], 'type': error['type'], 'msg': error['msg']}
                for error in exc.errors(include_url=False, include_input=False)
            ]
            logger.warning(
                "Rejected %s update ID=%s fields=%s: %s",
                cls.__name__, id, sorted(patch), errors,
            )
            raise

        for field_name in owned_list_fields:
            if field_name not in patch:
                continue
            supplied = patch[field_name]
            hydrated = getattr(validated, field_name)
            if isinstance(supplied, list) and len(hydrated) != len(supplied):
                raise ValueError(
                    f"Invalid owned relationship {cls.__name__}.{field_name}: "
                    "every supplied child must resolve"
                )

        validated_data = validated._storage_dict(exclude_unset=False)
        validated_patch = {
            name: validated_data[name]
            for name in patch
            if name in validated_data
        }
        cls.storage.update(cls, id, validated_patch)
        result = cls.get(id)
        if result and hasattr(cls, '_publish_lifecycle'):
            entity = result.model_response() if hasattr(result, 'model_response') else result
            cls._publish_lifecycle('after_update', entity)
        return result

    @classmethod
    def delete(cls, id: int):
        """
        Deletes a record using the storage backend.
        """
        cls.storage.delete(cls, id)
