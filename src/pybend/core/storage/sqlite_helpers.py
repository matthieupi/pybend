# app/storage/sqlite_helpers.py

from typing import Any, List, Type, Union, get_args, get_origin

from pydantic import BaseModel

from utils.registrar import registered_models


def get_list_fields(model_class: Type[Any]) -> List[tuple]:
    """
    Returns a list of (field_name, child_model_class) for every
    field typed as List[SomeBaseModel] on *model_class*.

    Example:
        class Product(BaseModel):
            comments: List[Comment] = []

        get_list_fields(Product)  ->  [("comments", Comment)]
    """
    results = []
    for field_name, field_info in model_class.model_fields.items():
        field_type = field_info.annotation

        origin = get_origin(field_type)
        # Unwrap Optional[List[...]]
        if origin is Union and type(None) in get_args(field_type):
            field_type = get_args(field_type)[0]
            origin = get_origin(field_type)

        if origin is list:
            args = get_args(field_type)
            if args and isinstance(args[0], type) and issubclass(args[0], BaseModel):
                results.append((field_name, args[0]))
    return results


def get_parent_fk_columns(child_model_class: Type[Any]) -> List[tuple]:
    """
    Scans *all* registered models to find parents that declare a
    List[child_model_class] field.  Returns a list of
    (parent_class_name_lower, fk_column_name) that should exist on the
    child's table.

    Uses the parent class name (lowercased) for the FK column:
        Product  ->  product_id

    Example:
        class Product(BaseModel):
            comments: List[Comment] = []

        get_parent_fk_columns(Comment)  ->  [("product", "product_id")]
    """
    fk_columns = []
    for _tname, parent_cls in registered_models.items():
        for field_name, field_info in parent_cls.model_fields.items():
            field_type = field_info.annotation
            origin = get_origin(field_type)
            if origin is Union and type(None) in get_args(field_type):
                field_type = get_args(field_type)[0]
                origin = get_origin(field_type)

            if origin is list:
                args = get_args(field_type)
                if args and args[0] is child_model_class:
                    fk_col = f"{parent_cls.__name__.lower()}_id"
                    fk_columns.append((parent_cls.__name__.lower(), fk_col))
    return fk_columns