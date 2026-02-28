"""Proto schema pipeline — composable stages for ProtoModel schema generation.

Each function is a pure dict → dict transformation:

    s = proto_schema.base(cls)
    s = proto_schema.strip_hidden(cls, s)
    s = proto_schema.methods(cls, s)
    s = proto_schema.defs(cls, s)
    s = proto_schema.access(cls, s)
    s = proto_schema.ui(cls, s)
    s = proto_schema.metadata(cls, s)

Stages are registered in a pipeline so that external packages (federation,
agents, polymorphism) can insert new stages via @schema_extension without
modifying this module.

access() and ui() will move to mixins (AccessMixin, ViewableMixin)
when those are introduced — each mixin's schema() will call super().schema()
then apply its own stage.
"""

import logging

from pybend.core import config
from pybend.core.utils.introspection import collect_all_referenced_models, _is_self_ref

logger = logging.getLogger('pybend.schema')


# ── Pipeline registry ──────────────────────────────────────────────
# Ordered list of (name, callable). Extensions insert relative to
# named stages via register_stage() or @schema_extension.

_stages: list[tuple[str, callable]] = []


def _find_stage(name: str) -> int:
    """Find stage index by name. Raises ValueError if not found."""
    for i, (stage_name, _) in enumerate(_stages):
        if stage_name == name:
            return i
    raise ValueError(
        f"Schema pipeline stage '{name}' not found. "
        f"Registered stages: {[n for n, _ in _stages]}"
    )


def register_stage(name: str, func, *, after: str = None, before: str = None):
    """Register a named stage into the schema pipeline.

    Args:
        name: Stage name (used for positioning and introspection).
        func: Stage callable. First stage: func(cls) -> dict.
              All others: func(cls, schema) -> dict.
        after: Insert after this named stage.
        before: Insert before this named stage.

    If neither after nor before, appends to the end.
    """
    if after and before:
        raise ValueError("Specify 'after' or 'before', not both")

    # Prevent duplicate stage names
    existing = {n for n, _ in _stages}
    if name in existing:
        raise ValueError(
            f"Schema pipeline stage '{name}' already registered. "
            f"Registered stages: {[n for n, _ in _stages]}"
        )

    if after:
        idx = _find_stage(after)
        _stages.insert(idx + 1, (name, func))
    elif before:
        idx = _find_stage(before)
        _stages.insert(idx, (name, func))
    else:
        _stages.append((name, func))

    logger.debug("Registered schema stage '%s' -> pipeline: %s", name, get_pipeline())


def schema_extension(*, after: str = None, before: str = None):
    """Decorator to register a schema pipeline extension.

    Usage:
        from pybend.core.models.proto_schema import schema_extension

        @schema_extension(after='methods')
        def federation(cls, schema: dict) -> dict:
            if getattr(cls, '__federated__', False):
                schema['federation'] = {...}
            return schema

    The function name becomes the stage name. This is how __federated__,
    __agent__, __discriminator__, and any future ClassVar-driven feature
    plugs in -- zero ProtoModel modifications needed.
    """
    def decorator(func):
        register_stage(func.__name__, func, after=after, before=before)
        return func
    return decorator


def run_pipeline(cls) -> dict:
    """Execute the full schema pipeline for a model class.

    The first stage (typically 'base') seeds the schema: func(cls) -> dict.
    All subsequent stages transform it: func(cls, schema) -> dict.
    """
    if not _stages:
        raise RuntimeError(
            "No schema pipeline stages registered. "
            "Ensure proto_schema is imported before calling schema()."
        )

    # First stage seeds the schema
    _, seed_fn = _stages[0]
    s = seed_fn(cls)

    # Remaining stages transform
    for _, stage_fn in _stages[1:]:
        s = stage_fn(cls, s)

    return s


def get_pipeline() -> list[str]:
    """Return current pipeline stage names (for debugging/introspection)."""
    return [name for name, _ in _stages]


def clear_pipeline():
    """Clear all registered stages. For testing only."""
    _stages.clear()


def remove_stage(name: str):
    """Remove a named stage from the pipeline."""
    idx = _find_stage(name)
    _stages.pop(idx)


# ── Default pipeline stages ───────────────────────────────────────

def base(cls) -> dict:
    """Pydantic core JSON Schema + Ref['self'] patches."""
    schema = cls.model_json_schema(ref_template="#/$defs/{model}")
    if 'properties' in schema:
        for field_name, field_info in cls.model_fields.items():
            if _is_self_ref(field_info.annotation):
                schema['properties'][field_name] = {"type": "selfref"}
    return schema


def strip_hidden(cls, s: dict) -> dict:
    """Remove __hidden_fields__ from properties and required."""
    hidden = getattr(cls, '__hidden_fields__', set())
    if hidden and 'properties' in s:
        for name in hidden:
            s['properties'].pop(name, None)
        if 'required' in s:
            s['required'] = [r for r in s['required'] if r not in hidden]
    return s


def methods(cls, s: dict) -> dict:
    """Inject @expose_route method signatures."""
    s['methods'] = cls.__pybend_methods_json_signature__()
    return s


def defs(cls, s: dict) -> dict:
    """Collect referenced models and build $defs with schemas, methods, and $id."""
    referenced_models = collect_all_referenced_models(cls)
    if not referenced_models:
        return s

    if '$defs' not in s:
        s['$defs'] = {}

    for model in referenced_models:
        ref_schema = model.referenced_json_schema()
        ref_methods = model.__pybend_methods_json_signature__()
        defs_from_ref = ref_schema.pop('$defs', {})
        s['$defs'] = {**defs_from_ref, **s['$defs']} if defs_from_ref else s['$defs']

        if 'properties' in ref_schema:
            s['$defs'][model.__name__] = ref_schema
        elif model.__name__ not in s['$defs']:
            s['$defs'][model.__name__] = ref_schema

        if model.__name__ in s['$defs']:
            s['$defs'][model.__name__]['methods'] = ref_methods

    for model in referenced_models:
        if model.__name__ in s['$defs']:
            s['$defs'][model.__name__]['$id'] = f"{config.API_URL}/{model.__name__}"

    return s


def access(cls, s: dict) -> dict:
    """Serialize ABAC rules into schema (top-level + $defs)."""
    from pybend.core.authorize.schema import access_schema
    s['access'] = access_schema(cls)

    if '$defs' in s:
        for model in collect_all_referenced_models(cls):
            if model.__name__ in s['$defs']:
                s['$defs'][model.__name__]['access'] = access_schema(model)
    return s


def ui(cls, s: dict) -> dict:
    """Inject UI hints: field exclusion, protected fields, __ui__ config.
    Handles both top-level and $defs."""
    from pybend.core.models.proto_model import _apply_field_exclusion

    # Field exclusion + protected fields (top-level)
    _apply_field_exclusion(s)
    protected = getattr(cls, '__protected_fields__', set())
    if protected and 'properties' in s:
        for field_name in protected:
            if field_name in s['properties']:
                s['properties'][field_name].setdefault('ui', {})['protected'] = True

    # __ui__ config (top-level)
    ui_config = getattr(cls, '__ui__', None)
    if ui_config:
        s['ui'] = dict(ui_config)
        method_ui = ui_config.get('methods', {})
        for method_name, hints in method_ui.items():
            if method_name in s.get('methods', {}):
                s['methods'][method_name]['ui'] = dict(hints)

    # $defs: field exclusion, protected, __ui__
    if '$defs' in s:
        for def_schema in s['$defs'].values():
            _apply_field_exclusion(def_schema)

        for model in collect_all_referenced_models(cls):
            if model.__name__ not in s['$defs']:
                continue
            # Protected fields
            ref_protected = getattr(model, '__protected_fields__', set())
            if ref_protected:
                def_props = s['$defs'][model.__name__].get('properties', {})
                for field_name in ref_protected:
                    if field_name in def_props:
                        def_props[field_name].setdefault('ui', {})['protected'] = True
            # __ui__
            ref_ui = getattr(model, '__ui__', None)
            if ref_ui:
                s['$defs'][model.__name__]['ui'] = dict(ref_ui)
                ref_method_ui = ref_ui.get('methods', {})
                def_methods = s['$defs'][model.__name__].get('methods', {})
                for method_name, hints in ref_method_ui.items():
                    if method_name in def_methods:
                        def_methods[method_name]['ui'] = dict(hints)
    return s


def metadata(cls, s: dict) -> dict:
    """Stamp $schema and $id."""
    s['$schema'] = f"{config.API_URL}/Schema"
    s['$id'] = f"{config.API_URL}/{cls.__name__}"
    return s


# ── Register default pipeline stages ──
# Order matters: base seeds, the rest transform sequentially.
# Extensions insert relative to these names via @schema_extension.
register_stage('base', base)
register_stage('strip_hidden', strip_hidden)
register_stage('methods', methods)
register_stage('defs', defs)
register_stage('access', access)
register_stage('ui', ui)
register_stage('metadata', metadata)
