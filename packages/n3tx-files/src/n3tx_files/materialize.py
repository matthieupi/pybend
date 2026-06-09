"""File argument materialization registration."""

from __future__ import annotations

from n3tx_core.utils.materialize import register_materializer

from .file import File


@register_materializer
async def materialize_file(value, expected_type, *, user=None, context=None):
    """Resolve address strings only for parameters annotated as File."""

    if expected_type is not File:
        return False, value
    if isinstance(value, File):
        return True, value
    if isinstance(value, str):
        return True, await File.resolve(value, user=user)
    if isinstance(value, dict):
        return True, File.model_validate(value)
    return False, value
