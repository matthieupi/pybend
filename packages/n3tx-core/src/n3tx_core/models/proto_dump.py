"""Proto dump pipeline — composable stages for model serialization.

Each function is a pure dict → dict transformation:

    d = proto_dump.base(instance)
    d = proto_dump.schema_url(instance, d)
    d = proto_dump.instance_url(instance, d)
    d = proto_dump.populate(instance, d)

Stages are registered in a pipeline so that external packages (federation,
agents, MCP) can insert new stages via @dump_extension without modifying
this module.

Mirrors proto_schema.py — same pattern, same extension mechanism:

    from n3tx_core.models.proto_dump import dump_extension

    @dump_extension(after='instance_url')
    def activity(instance, d: dict) -> dict:
        if getattr(instance.__class__, '__federated__', False):
            d['@context'] = 'https://www.w3.org/ns/activitystreams'
            d['type'] = instance.__class__.__name__
        return d
"""

import logging

from pydantic import BaseModel as PydanticBaseModel

from n3tx_core import config

logger = logging.getLogger('n3tx.dump')


# ── Pipeline registry ──────────────────────────────────────────────
# Ordered list of (name, callable). Extensions insert relative to
# named stages via register_stage() or @dump_extension.

_stages: list[tuple[str, callable]] = []

# ── URL caches ────────────────────────────────────────────────────
# Class-level URL parts never change at runtime, so we compute once.

_schema_url_cache: dict = {}
_instance_url_cache: dict = {}


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
        from n3tx_core.models.proto_dump import dump_extension

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


def schema_url(instance, d: dict) -> dict:
    """Inject $schema — the URL to the model's JSON Schema."""
    cls = instance.__class__
    if cls not in _schema_url_cache:
        _schema_url_cache[cls] = f"{config.API_URL}/{cls.__name__}"
    return {'$schema': _schema_url_cache[cls], **d}


def instance_url(instance, d: dict) -> dict:
    """Inject $id — the resolvable URL to this specific instance.

    Join models (with __owner__ + __tagname__) get parent-scoped URLs:
        {API_URL}/{owner_table}/{parent_id}/{tagname}/{id}
    Regular models get flat URLs:
        {API_URL}/{tablename}/{id}
    """
    cls = instance.__class__
    if cls not in _instance_url_cache:
        owner_cls = getattr(cls, '__owner__', None)
        tagname = getattr(cls, '__tagname__', None)
        if owner_cls and tagname:
            _instance_url_cache[cls] = {
                'owner_base': f"{config.API_URL}/{owner_cls.__tablename__}",
                'tagname': tagname,
                'fk_field': f"{owner_cls.__name__.lower()}_id",
            }
        else:
            tablename = getattr(cls, '__tablename__', cls.__name__.lower())
            _instance_url_cache[cls] = {
                'base_url': f"{config.API_URL}/{tablename}",
            }
    meta = _instance_url_cache[cls]
    instance_id = getattr(instance, 'id', None)

    if 'fk_field' in meta:
        parent_id = getattr(instance, meta['fk_field'], None) or d.get(meta['fk_field'])
        url = (
            f"{meta['owner_base']}/{parent_id}/{meta['tagname']}/{instance_id}"
            if instance_id is not None and parent_id is not None
            else None
        )
    else:
        url = f"{meta['base_url']}/{instance_id}" if instance_id is not None else None

    d['$id'] = url
    return d


def populate(instance, d: dict) -> dict:
    """Overlay eager-loaded related data from the storage layer.

    When storage.get() or storage.list() is called with a PopulateSpec,
    _populate_fields() attaches resolved child data to
    instance.__dict__['_populated'].  This stage merges that data into
    the serialized dict so model_response() produces the full output
    without callers needing a manual overlay.
    """
    populated = instance.__dict__.get('_populated')
    if populated:
        d.update(populated)
    return d


# ── Register default pipeline stages ──
# Order matters: base seeds, the rest transform sequentially.
# Extensions insert relative to these names via @dump_extension.
register_stage('base', base)
register_stage('schema_url', schema_url)
register_stage('instance_url', instance_url)
register_stage('populate', populate)
