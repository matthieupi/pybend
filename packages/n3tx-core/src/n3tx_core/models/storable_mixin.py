"""Provide persistence operations for registered N3TX models.

API: StorableMixin delegates CRUD to injected storage and validates updates.
Boundary: list compiles caller conditions alongside trusted SQL restrictions;
direct Python CRUD does not enforce route authorization.
Integration: registration attaches storage through set_storage()."""

import logging
from typing import ClassVar, Any, List, Union

from pydantic import AliasChoices, BaseModel, ValidationError

from n3tx_core.storage.abstract_storage import (
    AbstractStorage as StorageInterface,
)
from n3tx_core.utils.typer import Ref
from n3tx_core.utils.descriptors import fullmethod
from n3tx_core.utils.introspection import get_fk_list_fields
from n3tx_core.utils.where import compile_where

logger = logging.getLogger('n3tx.models')


class StorableMixin:
    """Provide model storage capabilities via dependency injection."""

    __pk__: ClassVar[str] = 'id'  # Primary key field name
    __tablename__: ClassVar[str]
    storage: ClassVar[StorageInterface] = None  # This will be injected

    @classmethod
    def _canonical_update_patch(cls, data: dict) -> dict:
        """Canonicalize aliases and reject ambiguous patch keys."""
        # 0. Build a lookup from accepted field names to model field names.
        input_names = {}
        for name, field in cls.model_fields.items():
            input_names[name] = name
            for alias in (field.alias, field.validation_alias):
                if isinstance(alias, str):
                    input_names[alias] = name
                elif isinstance(alias, AliasChoices):
                    input_names.update({
                        choice: name for choice in alias.choices
                        if isinstance(choice, str)
                    })
        # 1. Canonicalize keys while detecting duplicate field submissions.
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
        """Extract storage values, including Pydantic-excluded fields."""
        # 0. Dump explicitly set data and restore excluded persisted fields.
        data = self.model_dump(exclude_unset=exclude_unset)
        # Re-add fields hidden from the API but needed in storage.
        for name, fi in self.__class__.model_fields.items():
            if fi.exclude and name not in data:
                val = getattr(self, name, None)
                if val is not None or not exclude_unset:
                    data[name] = val
        return data

    def save(self):
        """Create this record when new; otherwise persist its current values."""
        # 0. Select create or update based on the current primary key.
        if not self.id:
            logger.debug("Saving new %s instance", self.__class__.__name__)
            return self.create(self)
        else:
            logger.debug(
                "Updating existing %s instance", self.__class__.__name__,
            )
            return self.update(self.id, self)

    @classmethod
    def set_storage(cls, storage: StorageInterface):
        """Set the storage backend for this model."""
        # 0. Attach the injected storage implementation to the model class.
        cls.storage = storage

    @classmethod
    def create_table(cls):
        """Create this model's table through the storage backend."""
        # 0. Delegate table creation to the configured backend.
        cls.storage.create_table(cls)

    @classmethod
    def create(cls, data: Any) -> Any:
        """Persist a model instance using its storage representation."""
        # 0. Extract fields and unwrap typed references for storage.
        data_dict = data._storage_dict(exclude_unset=True)
        for k, v in data_dict.items():
            if isinstance(v, Ref):
                data_dict[k] = v.model_dump()

        logger.debug("Creating %s with data: %s", cls.__name__, data_dict)
        return cls.storage.create(cls, data_dict)

    @classmethod
    def list(
        cls, sql_filter: tuple = None, limit: int = None, offset: int = None,
        populate=None, ids: list = None, *, order_asc: str | None = None,
        order_desc: str | None = None,
        where: dict[str, Any] | None = None,
    ) -> List[Any]:
        """Retrieve records, optionally filtered, paginated, or ordered.
        Optional sql_filter: (where_clause, params) for authorization pushdown.
        Optional limit/offset for pagination — when provided, returns
        {data: [...], meta: {...}} instead of a plain list.
        Optional populate: PopulateSpec for eager loading of related entities.
        Optional ids: list of IDs to filter by (WHERE id IN (...)).
        Optional where: field conditions ANDed with trusted sql_filter.
        Ordering accepts one stored field via order_asc or order_desc;
        invalid names or conflicting directions raise ValueError."""
        # 0. Compile caller conditions without replacing trusted restrictions.
        if where is not None:
            clause, params = compile_where(cls, where)
            if sql_filter and sql_filter[0]:
                clause = f'({sql_filter[0]}) AND ({clause})'
                params = [*(sql_filter[1] or []), *params]
            sql_filter = (clause, params)
        # 1. Preserve backend kwargs and forward only requested ordering.
        kwargs = {
            'sql_filter': sql_filter, 'limit': limit, 'offset': offset,
            'populate': populate, 'ids': ids,
        }
        if order_asc is not None:
            kwargs['order_asc'] = order_asc
        if order_desc is not None:
            kwargs['order_desc'] = order_desc
        return cls.storage.list(cls, **kwargs)

    @classmethod
    def get(cls, id: int, as_dict: bool = False, populate=None) -> Any:
        """Retrieve a record by ID through the storage backend.
        Optional populate: PopulateSpec for eager loading related entities."""
        # 0. Delegate the requested lookup and hydration options.
        return cls.storage.get(cls, id, as_dict=as_dict, populate=populate)

    @fullmethod
    def update(
        target,
        id_or_data: Union[int, BaseModel, dict],
        data: Union[BaseModel, dict, None] = None,
    ):
        """Update a record using the storage backend.

        Supports both class-level and instance-level call shapes:
        - Model.update(id, patch)
        - instance.update(patch)
        - instance.update(id, patch)  # compatibility

        ActorModel subclasses centralize after_update lifecycle publication here
        so direct actor updates and TX-routed updates behave consistently."""
        # 0. Normalize class and instance call shapes into an ID and payload.
        cls = target if isinstance(target, type) else target.__class__
        if isinstance(target, type):
            if data is None:
                raise ValueError(
                    f"[UPDATING {cls.__name__}] Missing update data",
                )
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
                raise ValueError(
                    f"[UPDATING {cls.__name__}] Cannot update unsaved "
                    "instance without an id"
                )

        logger.debug("Updating %s ID=%s", cls.__name__, id)
        if isinstance(update_payload, BaseModel):
            data_dict = update_payload.model_dump(exclude_unset=True)
        elif isinstance(update_payload, dict):
            data_dict = dict(update_payload)
        else:
            raise ValueError(
                f"[UPDATING {cls.__name__}-{id}] Invalid data type for "
                f"update: {type(update_payload)}"
            )

        current = (
            target
            if not isinstance(target, type)
            and getattr(target, 'id', None) == id
            else cls.get(id)
        )
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
        # 1. Validate merged data and preserve owned-relationship constraints.
        owned_list_fields = {
            name for name, _target_cls in get_fk_list_fields(cls)
        }
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
                    (
                        choice for choice in validation_alias.choices
                        if isinstance(choice, str)
                    ),
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
                {
                    'loc': error['loc'], 'type': error['type'],
                    'msg': error['msg'],
                }
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
        # 2. Persist supplied keys and publish the updated actor lifecycle.
        cls.storage.update(cls, id, validated_patch)
        result = cls.get(id)
        if result and hasattr(cls, '_publish_lifecycle'):
            entity = (
                result.model_response()
                if hasattr(result, 'model_response') else result
            )
            cls._publish_lifecycle('after_update', entity)
        return result

    @classmethod
    def delete(cls, id: int):
        """Delete a record using the storage backend."""
        # 0. Delegate deletion to the configured storage backend.
        cls.storage.delete(cls, id)


# Changelog
# - 2026-11-02: Forward optional list ordering to storage.
# - 2026-11-02: Compile optional where conditions before storage delegation.
# - 2026-11-10: Restore native list filtering and ordering from 123d825.
