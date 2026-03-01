"""Proto dump pipeline — composable stages for model serialization.

Each function is a pure dict → dict transformation:

    d = proto_dump.base(instance)
    d = proto_dump.response(instance, d)

Stages are registered in a pipeline so that external packages (federation,
agents, MCP) can insert new stages via @dump_extension without modifying
this module.

Mirrors proto_schema.py — same pattern, same extension mechanism:

    from pybend.core.models.proto_dump import dump_extension

    @dump_extension(after='response')
    def activity(instance, d: dict) -> dict:
        if getattr(instance.__class__, '__federated__', False):
            d['@context'] = 'https://www.w3.org/ns/activitystreams'
            d['type'] = instance.__class__.__name__
        return d
"""

import logging

from pydantic import BaseModel as PydanticBaseModel

from pybend.core import config

logger = logging.getLogger('pybend.dump')


# ── Pipeline registry ──────────────────────────────────────────────
# Ordered list of (name, callable). Extensions insert relative to
# named stages via register_stage() or @dump_extension.

_stages: list[tuple[str, callable]] = []

# ── Response meta cache ────────────────────────────────────────────
# Class-level URL parts ($schema URL, tablename prefix) never change
# at runtime, so we compute them once and reuse.

_response_meta_cache: dict = {}


def _find_stage(name: str) -> int:
    """Find stage index by name. Raises ValueError if not found."""
    for i, (stage_name, _) in enumerate(_stages):
        if stage_name == name:
            return i
    raise ValueError(
        f"Dump pipeline stage '{name}' not found. "
        f"Registered stages: {[n for n, _ in _stages]}"
    )


def register_stage(name: str, func, *, after: str = None, before: str = None):
    """Register a named stage into the dump pipeline.

    Args:
        name: Stage name (used for positioning and introspection).
        func: Stage callable. First stage: func(instance) -> dict.
              All others: func(instance, data) -> dict.
        after: Insert after this named stage.
        before: Insert before this named stage.

    If neither after nor before, appends to the end.
    """
    if after and before:
        raise ValueError("Specify 'after' or 'before', not both")

    existing = {n for n, _ in _stages}
    if name in existing:
        raise ValueError(
            f"Dump pipeline stage '{name}' already registered. "
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

    logger.debug("Registered dump stage '%s' -> pipeline: %s", name, get_pipeline())


def dump_extension(*, after: str = None, before: str = None):
    """Decorator to register a dump pipeline extension.

    Usage:
        from pybend.core.models.proto_dump import dump_extension

        @dump_extension(after='response')
        def activity(instance, d: dict) -> dict:
            if getattr(instance.__class__, '__federated__', False):
                d['@context'] = 'https://www.w3.org/ns/activitystreams'
                d['type'] = instance.__class__.__name__
            return d

    The function name becomes the stage name.
    """
    def decorator(func):
        register_stage(func.__name__, func, after=after, before=before)
        return func
    return decorator


def run_pipeline(instance, **kwargs) -> dict:
    """Execute the full dump pipeline for a model instance.

    The first stage (typically 'base') seeds the data: func(instance) -> dict.
    All subsequent stages transform it: func(instance, data) -> dict.
    """
    if not _stages:
        raise RuntimeError(
            "No dump pipeline stages registered. "
            "Ensure proto_dump is imported before calling model_response()."
        )

    # First stage seeds the data
    _, seed_fn = _stages[0]
    d = seed_fn(instance, **kwargs)

    # Remaining stages transform
    for _, stage_fn in _stages[1:]:
        d = stage_fn(instance, d)

    return d


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

def base(instance, **kwargs) -> dict:
    """Plain Pydantic data extraction."""
    return PydanticBaseModel.model_dump(instance, **kwargs)


def response(instance, d: dict) -> dict:
    """Inject $schema and $id for HTTP API responses."""
    cls = instance.__class__
    if cls not in _response_meta_cache:
        tablename = getattr(cls, '__tablename__', cls.__name__.lower())
        _response_meta_cache[cls] = {
            'schema_url': f"{config.API_URL}/{cls.__name__}",
            'base_url': f"{config.API_URL}/{tablename}",
        }
    meta = _response_meta_cache[cls]
    instance_id = getattr(instance, 'id', None)
    return {
        '$schema': meta['schema_url'],
        '$id': f"{meta['base_url']}/{instance_id}" if instance_id is not None else None,
        **d
    }


# ── Register default pipeline stages ──
# Order matters: base seeds, the rest transform sequentially.
# Extensions insert relative to these names via @dump_extension.
register_stage('base', base)
register_stage('response', response)
