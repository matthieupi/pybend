"""Relationship field primitives and metadata.

This module defines lightweight relationship descriptors used by the model,
schema, storage, and route layers. The first relationship primitive is
``ManyToMany[T]``: an explicit marker for shared collection relationships.
"""

from dataclasses import dataclass
from typing import Annotated, Literal, Union

from pydantic import Field


@dataclass(frozen=True)
class Relationship:
    """Framework metadata for a model relationship.

    Relationship is intentionally a plain value object, not an Actor. It is the
    shared contract that later storage, route, schema, and actor integrations can
    consume without each layer re-deriving relationship shape independently.
    """

    kind: Literal['many_to_many']
    owner: type
    field_name: str
    target: type
    through: type | None = None
    owner_fk: str | None = None
    target_fk: str | None = None
    table_name: str | None = None


class _ManyToManyMarker:
    """Metadata tag to identify ManyToMany fields during introspection."""

    def __init__(self, target_model, through_model=None):
        self.target_model = target_model
        self.through_model = through_model


class ManyToMany:
    """Type alias factory for shared collection relationship fields.

    Usage:
        tags: ManyToMany[Tag] = []
        tags: ManyToMany[Tag, ProductTag] = []  # future through-model support

    Produces Annotated[list[Union[T, str]], _ManyToManyMarker(T)] so Pydantic
    accepts a list of model instances or href strings while N3TX can distinguish
    this shared relationship from owned local model-list relationships.
    """

    def __class_getitem__(cls, args):
        if isinstance(args, tuple):
            target_model, through_model = args
        else:
            target_model, through_model = args, None
        return Annotated[list[Union[target_model, str]], _ManyToManyMarker(target_model, through_model)]


def _ensure_owner_relationships(owner_cls: type) -> dict:
    relationships = getattr(owner_cls, '__relationships__', None)
    if relationships is None:
        relationships = {}
        setattr(owner_cls, '__relationships__', relationships)
    return relationships


def generate_relationship_model(owner_cls: type, field_name: str, target_cls: type, through_model: type | None = None):
    """Generate a minimal link model and Relationship for ManyToMany fields.

    This function intentionally does not register the generated model or create
    storage tables. It only creates deterministic model metadata for later
    registration, storage, route, and schema slices.
    """
    owner_name = owner_cls.__name__
    target_name = target_cls.__name__
    owner_table = owner_cls.__tablename__
    target_table = target_cls.__tablename__
    class_name = f"{owner_name}{field_name[:1].upper()}{field_name[1:]}Link"
    table_name = f"{owner_table}_{target_table}"
    owner_fk = f"{owner_name.lower()}_id"
    target_fk = f"{target_name.lower()}_id"

    link_model = through_model
    if link_model is None:
        fields = {
            '__tablename__': table_name,
            '__storable__': True,
            '__module__': target_cls.__module__,
            '__annotations__': {
                owner_fk: int,
                target_fk: int,
            },
            owner_fk: Field(..., alias=owner_fk, description=f"FK to {owner_name}"),
            target_fk: Field(..., alias=target_fk, description=f"FK to {target_name}"),
        }
        from n3tx_core.models.proto_model import ProtoModel
        link_model = type(class_name, (ProtoModel,), fields)

    relationship = Relationship(
        kind='many_to_many',
        owner=owner_cls,
        field_name=field_name,
        target=target_cls,
        through=link_model,
        owner_fk=owner_fk,
        target_fk=target_fk,
        table_name=getattr(link_model, '__tablename__', table_name),
    )

    setattr(link_model, '__relationship__', relationship)
    _ensure_owner_relationships(owner_cls)[field_name] = relationship
    return link_model


def generate_relationship_models(model_classes: list[type]) -> list[type]:
    """Generate link models for ManyToMany fields on model_classes.

    This mirrors app bootstrap's explicit join-model generation, but discovers
    ManyToMany declarations directly from model fields so the Python model stays
    the source of truth.
    """
    from n3tx_core.utils.introspection import get_many_to_many_fields

    link_models = []
    seen_tables = set()
    for owner_cls in model_classes:
        for field_name, target_cls, through_model in get_many_to_many_fields(owner_cls):
            link_model = generate_relationship_model(owner_cls, field_name, target_cls, through_model)
            table_name = getattr(link_model, '__tablename__', None)
            if table_name in seen_tables:
                continue
            seen_tables.add(table_name)
            link_models.append(link_model)
    return link_models
