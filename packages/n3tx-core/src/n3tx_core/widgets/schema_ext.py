"""Schema pipeline extension for widget metadata injection.

Registered via @schema_extension(before='ui') so it runs after access rules
but before UI config is applied. Reads Widget annotations from model fields
and injects ``ui.widget`` + ``ui.config`` into the JSON Schema properties.

Three detection cases:
  1. ``Annotated[str, <MarkdownField instance>]`` -- from ``MarkdownField(rows=10)``
  2. Bare ``MarkdownField`` class -- ``issubclass(annotation, Widget)``
  3. Auto-detect: bare ``AnyHttpUrl`` (not a Widget subclass) -> check AUTO_DETECT_MAP
"""

from __future__ import annotations

import logging
from typing import get_args, get_origin, get_type_hints, Annotated, Union

from n3tx_core.models.proto_schema import schema_extension
from n3tx_core.widgets.widget import Widget, get_auto_widget

logger = logging.getLogger('n3tx.widgets')


def _unwrap_optional(annotation):
    """Unwrap Optional[X] / Union[X, None] to X."""
    origin = get_origin(annotation)
    if origin is Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _extract_widget(annotation) -> Widget | None:
    """Extract widget info from a type annotation.

    Returns a Widget instance (with name + config) or None.
    """
    if annotation is None:
        return None

    # Unwrap Optional
    annotation = _unwrap_optional(annotation)

    # Case 1: Annotated[base_type, <Widget instance>]
    if get_origin(annotation) is Annotated:
        for arg in get_args(annotation):
            if isinstance(arg, Widget):
                return arg

    # Case 2: Bare Widget subclass (e.g. MarkdownField used as type annotation)
    try:
        if isinstance(annotation, type) and issubclass(annotation, Widget) and annotation is not Widget:
            # Create a marker instance with empty config
            instance = object.__new__(annotation)
            instance.config = {}
            return instance
    except TypeError:
        pass

    # Case 3: Auto-detect from Python type (e.g. AnyHttpUrl -> 'url')
    try:
        if isinstance(annotation, type):
            widget_name = get_auto_widget(annotation)
            if widget_name:
                instance = object.__new__(Widget)
                instance.name = widget_name
                instance.config = {}
                return instance
    except TypeError:
        pass

    return None


@schema_extension(before='ui')
def widget(cls, schema: dict) -> dict:
    """Inject ui.widget from Widget annotations into schema properties."""
    try:
        hints = get_type_hints(cls, include_extras=True)
    except Exception:
        logger.debug("Could not get type hints for %s, skipping widget injection", cls.__name__)
        return schema

    _inject_widgets(hints, schema)

    # Process $defs entries (referenced models like Comment inside Product)
    if '$defs' in schema:
        def_models = _collect_def_models(cls)
        for model in def_models:
            if model.__name__ not in schema['$defs']:
                continue
            try:
                model_hints = get_type_hints(model, include_extras=True)
            except Exception:
                continue
            _inject_widgets(model_hints, schema['$defs'][model.__name__])

    return schema


def _collect_def_models(cls, seen=None) -> set:
    """Collect all model classes that appear in $defs.

    Walks list[T], Ref[T] fields, and _referenced_models recursively.
    """
    if seen is None:
        seen = set()
    if cls in seen:
        return seen
    seen.add(cls)

    try:
        hints = get_type_hints(cls, include_extras=True)
    except Exception:
        return seen

    for ann in hints.values():
        model = _extract_model_from_annotation(ann)
        if model and model not in seen:
            _collect_def_models(model, seen)

    # Also include _referenced_models (from @expose_route signatures)
    for model in getattr(cls, '_referenced_models', set()).copy():
        if model not in seen:
            _collect_def_models(model, seen)

    return seen


def _extract_model_from_annotation(ann):
    """Extract a ProtoModel class from a type annotation."""
    origin = get_origin(ann)

    # Annotated wrappers such as relationship metadata.
    if origin is Annotated:
        inner_args = get_args(ann)
        if inner_args:
            return _extract_model_from_annotation(inner_args[0])

    # list[Union[T, str]] or list[T]
    if origin is list:
        args = get_args(ann)
        if args:
            return _extract_model_from_annotation(args[0])

    # Union[T, str] or Optional[T]
    if origin is Union:
        for arg in get_args(ann):
            if arg is type(None) or arg is str:
                continue
            result = _extract_model_from_annotation(arg)
            if result:
                return result

    # Bare model class with model_fields (Pydantic model)
    if isinstance(ann, type) and hasattr(ann, 'model_fields'):
        return ann

    return None


def _inject_widgets(hints: dict, schema: dict) -> None:
    """Inject ui.widget into schema properties based on type hints."""
    for field_name, field_schema in schema.get('properties', {}).items():
        if not isinstance(field_schema, dict):
            continue

        # Skip if ui.widget already set (respect explicit json_schema_extra config)
        if field_schema.get('ui', {}).get('widget'):
            continue

        annotation = hints.get(field_name)
        widget_info = _extract_widget(annotation)
        if widget_info:
            field_schema.setdefault('ui', {})['widget'] = widget_info.name
            if widget_info.config:
                field_schema['ui']['config'] = widget_info.config
