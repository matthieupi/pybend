"""Widget system -- field-type-aware rendering for N3TX models.

Re-exports the public API so consumers can write::

    from n3tx.core.widgets import Widget, MarkdownField, UrlField, ...
"""

from .widget import (
    Widget,
    WidgetMeta,
    UrlField,
    EmailField,
    DateField,
    DateTimeField,
    MarkdownField,
    ConsoleField,
    ReferenceField,
    CurrencyField,
    TextareaField,
    register_auto_detect,
    get_auto_widget,
    AUTO_DETECT_MAP,
)

# Import schema_ext to register the pipeline stage at import time
from . import schema_ext  # noqa: F401

__all__ = [
    "Widget", "WidgetMeta",
    "UrlField", "EmailField", "DateField", "DateTimeField",
    "MarkdownField", "ConsoleField", "ReferenceField",
    "CurrencyField", "TextareaField",
    "register_auto_detect", "get_auto_widget", "AUTO_DETECT_MAP",
]
