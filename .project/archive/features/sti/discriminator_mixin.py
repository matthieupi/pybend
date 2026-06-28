"""DiscriminatorMixin — Single Table Inheritance (STI) support.

Auto-injected by ProtoModel.__init_subclass__ when __discriminator__ is detected.
Manages __subtypes__ registry, __sti_root__ tracking, and CRUD overrides.

The discriminator is a REAL Pydantic field dynamically added to model annotations,
so storage handles it naturally via existing model_fields iteration.
sqlite_storage.py is NOT modified — all STI logic lives here.
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger('n3tx.models')


class DiscriminatorMixin:
    """Mixin for Single Table Inheritance (STI) support.

    Provides CRUD overrides that wrap super() calls with STI logic:
    - _storage_dict(): ensures discriminator is always included
    - list(): adds WHERE discriminator = ClassName for subtypes
    - get(): reads discriminator, returns correct subtype instance
    - update(): strips discriminator from update data
    - create(): no override — discriminator flows through _storage_dict
    """

    def _storage_dict(self, exclude_unset: bool = True) -> dict:
        """Ensure discriminator is always included in storage data.

        The discriminator uses Field(default=ClassName) which means it is
        'unset' unless explicitly passed. exclude_unset=True would skip it,
        causing NULL in the DB. This override ensures it's always present.
        """
        data = super()._storage_dict(exclude_unset=exclude_unset)
        disc = getattr(self.__class__, '__discriminator__', None)
        if disc:
            data[disc] = getattr(self, disc)
        return data

    @classmethod
    def list(cls, sql_filter=None, **kwargs):
        """STI-aware list: subtypes filter by discriminator, root returns all."""
        disc = getattr(cls, '__discriminator__', None)
        root = getattr(cls, '__sti_root__', None)
        if not disc or not root:
            return super().list(sql_filter=sql_filter, **kwargs)

        if cls is not root:
            # Subtype query: merge WHERE discriminator = ClassName
            type_filter = (f"{disc} = ?", [cls.__name__])
            if sql_filter:
                clause, params = sql_filter
                merged = (
                    f"({clause}) AND {disc} = ?",
                    list(params) + [cls.__name__]
                )
                return super().list(sql_filter=merged, **kwargs)
            return super().list(sql_filter=type_filter, **kwargs)

        # Root query: no type filter — returns root-class instances
        # with discriminator set for frontend type dispatch
        return super().list(sql_filter=sql_filter, **kwargs)

    @classmethod
    def get(cls, id: int, as_dict: bool = False, **kwargs):
        """STI-aware get: returns correct subtype instance."""
        disc = getattr(cls, '__discriminator__', None)
        root = getattr(cls, '__sti_root__', None)
        if not disc or not root:
            return super().get(id, as_dict=as_dict, **kwargs)

        # Get as dict to read discriminator value
        data = super().get(id, as_dict=True, **kwargs)
        if data is None:
            return None

        # Determine correct subtype
        type_name = data.get(disc)
        target_cls = root.__subtypes__.get(type_name, cls) if type_name else cls

        if target_cls is cls:
            # Already the correct class
            return data if as_dict else cls(**data)

        # Delegate to target subtype — re-enters this method with cls=target_cls,
        # where target_cls IS cls on the second call, so no infinite recursion
        return target_cls.get(id, as_dict=as_dict, **kwargs)

    @classmethod
    def update(cls, id: int, data: Any):
        """STI-aware update: strip discriminator from update data."""
        disc = getattr(cls, '__discriminator__', None)
        if not disc:
            return super().update(id, data)

        if isinstance(data, BaseModel):
            data_dict = data.model_dump(exclude_unset=True)
        elif isinstance(data, dict):
            data_dict = dict(data)
        else:
            return super().update(id, data)

        data_dict.pop(disc, None)
        return super().update(id, data_dict)


def setup_sti(cls):
    """Configure STI on a class. Called from ProtoModel.__init_subclass__.

    Three branches:
    1. __discriminator__ in cls.__dict__ → STI root
    2. Ancestor in MRO has __discriminator__ → STI subtype
    3. Neither → should not reach here (caller checks first)
    """
    disc_name = cls.__dict__.get('__discriminator__')

    if disc_name is not None:
        # Branch 1: STI root
        cls.__subtypes__ = {}
        cls.__sti_root__ = cls
        _add_discriminator_field(cls, disc_name)
        logger.debug("STI root: %s (discriminator=%s)", cls.__name__, disc_name)
    else:
        # Branch 2: Find ancestor with __discriminator__
        for base in cls.__mro__[1:]:
            if '__discriminator__' in base.__dict__:
                disc_name = base.__discriminator__
                root = base.__sti_root__
                cls.__sti_root__ = root
                cls.__tablename__ = root.__tablename__
                root.__subtypes__[cls.__name__] = cls
                _add_discriminator_field(cls, disc_name)
                logger.debug(
                    "STI subtype: %s -> %s (root=%s)",
                    cls.__name__, disc_name, root.__name__
                )
                return
        # Branch 3: shouldn't reach here if caller checks correctly


def _add_discriminator_field(cls, disc_name: str):
    """Dynamically add discriminator as a Pydantic field annotation.

    Must be called BEFORE super().__init_subclass__() (Pydantic processing)
    so that Pydantic picks up the field in model_fields.
    """
    cls.__annotations__ = dict(getattr(cls, '__annotations__', {}))
    cls.__annotations__[disc_name] = str
    setattr(cls, disc_name, Field(default=cls.__name__))
