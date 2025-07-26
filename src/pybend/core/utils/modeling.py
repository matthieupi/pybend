from pydantic import Field
from typing import Type
from models.proto_model import ProtoModel


def generate_join_model(owner_cls: Type[ProtoModel], ref_model: Type[ProtoModel], field_name: str = None):
    owner_name = owner_cls.__name__
    owner_tablename = owner_cls.__tablename__
    ref_tablename = ref_model.__tablename__
    class_name = f"{owner_name}{ref_model.__name__}"
    tablename = f"{owner_tablename}_{ref_tablename}"
    fk_field = f"{owner_name.lower()}_id"

    # Construct __annotations__ and field definitions separately
    annotations = dict(ref_model.__annotations__)
    annotations[fk_field] = int

    fields = {
        "__tablename__": tablename,
        "__tagname__": ref_model.__tablename__,
        "__storable__": True,
        "__owner__": owner_cls,
        "__parent__": ref_model,
        "__module__": ref_model.__module__,
        "__annotations__": annotations,
        fk_field: Field(..., alias=fk_field, description=f"FK to {owner_name}")
    }

    return type(class_name, (ref_model,), fields)
