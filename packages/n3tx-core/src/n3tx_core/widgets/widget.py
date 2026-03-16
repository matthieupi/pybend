"""Widget base class, built-in field types, and auto-detection registry.

A single Widget class hierarchy serves as:
  - Annotation marker (inside Annotated)
  - Type annotation (via WidgetMeta)
  - Metadata carrier (widget name + config)

Usage in models::

    class BlogPost(ProtoModel):
        title: str                           # plain -- no widget
        body: MarkdownField                  # bare -- validates as str, widget=markdown
        body: MarkdownField(rows=10)         # config -- Annotated[str, MarkdownField(rows=10)]
        website: UrlField                    # bare -- validates as AnyHttpUrl, widget=url
        published: DateField                 # bare -- validates as date, widget=date

App developer extension::

    class ColorField(Widget, name='color', base_type=str):
        pass

    class Theme(ProtoModel):
        primary: ColorField
        accent: ColorField(swatches=True)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any

from pydantic import AnyHttpUrl, EmailStr


class WidgetMeta(type):
    """Metaclass that makes Widget types work as both annotations and config factories.

    - ``MarkdownField`` (bare) -- usable as type annotation, Pydantic delegates to base_type.
    - ``MarkdownField(rows=10)`` -- returns ``Annotated[base_type, <instance with config>]``.
    """

    def __call__(cls, **config):
        # Create marker instance WITHOUT normal __init__ (avoids recursion)
        instance = object.__new__(cls)
        instance.config = config
        return Annotated[cls.base_type, instance]


class Widget(metaclass=WidgetMeta):
    """Base widget class. Subclass to create new widget field types.

    Class attributes:
        name: Widget identifier (auto-derived from class name minus 'Field' suffix).
        base_type: Pydantic type for validation (default: str).
        config: Dict of rendering hints passed to the frontend.
    """

    name: str = 'default'
    base_type: type = str
    config: dict[str, Any] = {}

    def __init_subclass__(cls, name: str = '', base_type: type = str, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.name = name or cls.__name__.lower().replace('field', '')
        cls.base_type = base_type

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        """When used bare as annotation, delegate validation to base_type."""
        return handler.generate_schema(cls.base_type)


# ── Built-in widget field types ─────────────────────────────────────

class UrlField(Widget, name='url', base_type=AnyHttpUrl):
    pass


class EmailField(Widget, name='email', base_type=EmailStr):
    pass


class DateField(Widget, name='date', base_type=date):
    pass


class DateTimeField(Widget, name='datetime', base_type=datetime):
    pass


class MarkdownField(Widget, name='markdown', base_type=str):
    pass


class ConsoleField(Widget, name='console', base_type=str):
    pass


class ReferenceField(Widget, name='reference', base_type=str):
    pass


class CurrencyField(Widget, name='currency', base_type=float):
    pass


class TextareaField(Widget, name='textarea', base_type=str):
    pass


# ── Auto-detection registry ─────────────────────────────────────────
# Maps Python types to widget names for fields without explicit Widget annotation.

AUTO_DETECT_MAP: list[tuple[type, str]] = [
    (AnyHttpUrl, 'url'),
    (EmailStr, 'email'),
    (datetime, 'datetime'),  # datetime before date (datetime is subclass of date)
    (date, 'date'),
]


def register_auto_detect(auto_detect_type: type, name: str):
    """Register a type for auto-detection. Called by app developers."""
    AUTO_DETECT_MAP.append((auto_detect_type, name))


def get_auto_widget(python_type: type) -> str | None:
    """Return widget name if python_type matches an auto-detect entry."""
    for check_type, widget_name in AUTO_DETECT_MAP:
        try:
            if issubclass(python_type, check_type):
                return widget_name
        except TypeError:
            continue
    return None
