# app/storage/sqlite_helpers.py

import logging
from typing import Any, List, Type, Union, get_args, get_origin

from pydantic import BaseModel

from n3tx_core.utils.registrar import registered_models
from n3tx_core.utils.introspection import get_fk_list_fields

logger = logging.getLogger('n3tx.storage')


def get_parent_fk_columns(child_model_class: Type[Any]) -> List[tuple]:
    """
    Scans *all* registered models to find parents that declare a
    list[child_model_class] field.
    Returns a list of (parent_class_name_lower, fk_column_name) that
    should exist on the child's table.

    Uses the parent class name (lowercased) for the FK column:
        Product  ->  product_id

    Example:
        class Product(BaseModel):
            comments: list[Comment] = []

        get_parent_fk_columns(Comment)  ->  [("product", "product_id")]
    """
    fk_columns = []
    for _tname, parent_cls in registered_models.items():
        for field_name, child_cls in get_fk_list_fields(parent_cls):
            if child_cls is child_model_class:
                fk_col = f"{parent_cls.__name__.lower()}_id"
                fk_columns.append((parent_cls.__name__.lower(), fk_col))
    return fk_columns
