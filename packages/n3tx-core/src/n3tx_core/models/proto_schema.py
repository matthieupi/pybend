"""Proto schema pipeline — composable stages for ProtoModel schema generation.

Each function is a pure dict → dict transformation:

    s = proto_schema.base(cls)
    s = proto_schema.strip_hidden(cls, s)
    s = proto_schema.methods(cls, s)
    s = proto_schema.defs(cls, s)
    s = proto_schema.access(cls, s)
    s = proto_schema.ui(cls, s)
    s = proto_schema.metadata(cls, s)

Stages are registered in named pipelines so that external packages
(federation, agents, polymorphism) can insert new stages via
@schema_extension without modifying this module.

The 'default' pipeline produces the full frontend schema. Additional
pipelines (e.g., 'llm') can be registered for different consumers,
each with their own ordered stages.

access() and ui() will move to mixins (AccessMixin, ViewableMixin)
when those are introduced — each mixin's schema() will call super().schema()
then apply its own stage.
"""

import logging
from typing import get_origin, get_args

from n3tx_core import config
from n3tx_core.utils.introspection import collect_all_referenced_models, _is_self_ref
from n3tx_core.utils.typer import Ref

logger = logging.getLogger('n3tx.schema')


# ── Pipeline registry ──────────────────────────────────────────────
# Named pipelines — each is an ordered list of (name, callable).
# Extensions insert relative to named stages via register_stage()
# or @schema_extension.

_pipelines: dict[str, list[tuple[str, callable]]] = {'default': []}
_stages = _pipelines['default']  # backward compat — same list object


def _find_stage(name: str, pipeline: str = 'default') -> int:
    """Find stage index by name. Raises ValueError if not found."""
    stages = _pipelines.get(pipeline, [])
    for i, (stage_name, _) in enumerate(stages):
        if stage_name == name:
            return i
    raise ValueError(
        f"Schema pipeline stage '{name}' not found in '{pipeline}' pipeline. "
        f"Registered stages: {[n for n, _ in stages]}"
    )


def register_stage(name: str, func, *, after: str = None, before: str = None,
                    pipeline: str = 'default'):
    """Register a named stage into a schema pipeline.

    Args:
        name: Stage name (used for positioning and introspection).
        func: Stage callable. First stage: func(cls) -> dict.
              All others: func(cls, schema) -> dict.
        after: Insert after this named stage.
        before: Insert before this named stage.
        pipeline: Pipeline name (default: 'default').

    If neither after nor before, appends to the end.
    Non-existent pipelines are auto-created.
    """
    if after and before:
        raise ValueError("Specify 'after' or 'before', not both")

    stages = _pipelines.setdefault(pipeline, [])

    # Prevent duplicate stage names within a pipeline
    existing = {n for n, _ in stages}
    if name in existing:
        raise ValueError(
            f"Schema pipeline stage '{name}' already registered in '{pipeline}' pipeline. "
            f"Registered stages: {[n for n, _ in stages]}"
        )

    if after:
        idx = _find_stage(after, pipeline)
        stages.insert(idx + 1, (name, func))
    elif before:
        idx = _find_stage(before, pipeline)
        stages.insert(idx, (name, func))
    else:
        stages.append((name, func))

    logger.debug("Registered schema stage '%s' in '%s' pipeline -> %s",
                 name, pipeline, get_pipeline(pipeline))


def schema_extension(*, after: str = None, before: str = None,
                     pipeline: str = 'default'):
    """Decorator to register a schema pipeline extension.

    Usage:
        from n3tx_core.models.proto_schema import schema_extension

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
        register_stage(func.__name__, func, after=after, before=before,
                       pipeline=pipeline)
        return func
    return decorator


def run_pipeline(cls, pipeline: str = 'default') -> dict:
    """Execute a named schema pipeline for a model class.

    The first stage (typically 'base') seeds the schema: func(cls) -> dict.
    All subsequent stages transform it: func(cls, schema) -> dict.

    Args:
        cls: The model class to generate schema for.
        pipeline: Pipeline name (default: 'default').
    """
    stages = _pipelines.get(pipeline)
    if not stages:
        raise RuntimeError(
            f"No schema pipeline stages registered for '{pipeline}' pipeline. "
            f"Registered pipelines: {list(_pipelines.keys())}"
        )

    # First stage seeds the schema
    _, seed_fn = stages[0]
    s = seed_fn(cls)

    # Remaining stages transform
    for _, stage_fn in stages[1:]:
        s = stage_fn(cls, s)

    return s


def get_pipeline(pipeline: str = 'default') -> list[str]:
    """Return pipeline stage names (for debugging/introspection)."""
    return [name for name, _ in _pipelines.get(pipeline, [])]


def clear_pipeline(pipeline: str = None):
    """Clear pipeline stages. For testing only.

    Args:
        pipeline: Specific pipeline to clear, or None to clear all.
    """
    if pipeline is None:
        for stages in _pipelines.values():
            stages.clear()
    else:
        stages = _pipelines.get(pipeline)
        if stages is not None:
            stages.clear()


def remove_stage(name: str, pipeline: str = 'default'):
    """Remove a named stage from a pipeline."""
    idx = _find_stage(name, pipeline)
    _pipelines[pipeline].pop(idx)


# ── Default pipeline stages ───────────────────────────────────────

def base(cls) -> dict:
    """Pydantic core JSON Schema + Ref['self'] and Ref[T] patches.

    Pydantic's model_json_schema() serializes Ref[T] as {"type": "integer"}
    because the core schema uses int serialization. We patch those back to
    {"type": "$ref", "$ref": "#/$defs/{TargetName}"} so the frontend can
    resolve them as rich child components.
    """
    schema = cls.model_json_schema(ref_template="#/$defs/{model}")
    if 'properties' in schema:
        for field_name, field_info in cls.model_fields.items():
            if _is_self_ref(field_info.annotation):
                schema['properties'][field_name] = {"type": "selfref"}
            elif get_origin(field_info.annotation) is Ref:
                target = get_args(field_info.annotation)[0]
                schema['properties'][field_name] = {
                    "type": "$ref",
                    "$ref": f"#/$defs/{target.__name__}"
                }
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
    s['methods'] = cls.__n3tx_methods_json_signature__()
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
        ref_methods = model.__n3tx_methods_json_signature__()
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
    from n3tx_core.authorize.schema import access_schema
    s['access'] = access_schema(cls)

    if '$defs' in s:
        for model in collect_all_referenced_models(cls):
            if model.__name__ in s['$defs']:
                s['$defs'][model.__name__]['access'] = access_schema(model)
    return s


def ui(cls, s: dict) -> dict:
    """Inject field-level UI hints: auto-hide and protected fields.

    Handles both top-level and $defs. __ui__ class config is handled by
    ViewableMixin's schema extension (n3tx-ui).
    """
    from n3tx_core.models.proto_model import _apply_field_exclusion

    # Field exclusion + protected fields (top-level)
    _apply_field_exclusion(s)
    protected = getattr(cls, '__protected_fields__', set())
    if protected and 'properties' in s:
        for field_name in protected:
            if field_name in s['properties']:
                s['properties'][field_name].setdefault('ui', {})['protected'] = True

    # $defs: field exclusion + protected fields
    if '$defs' in s:
        for def_schema in s['$defs'].values():
            _apply_field_exclusion(def_schema)

        for model in collect_all_referenced_models(cls):
            if model.__name__ not in s['$defs']:
                continue
            ref_protected = getattr(model, '__protected_fields__', set())
            if ref_protected:
                def_props = s['$defs'][model.__name__].get('properties', {})
                for field_name in ref_protected:
                    if field_name in def_props:
                        def_props[field_name].setdefault('ui', {})['protected'] = True
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
