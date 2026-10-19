"""Optional typed argument materialization registry.

Core owns the neutral extension seam. Optional packages register materializers
when explicitly imported; core never imports those packages directly.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any


_materializers: list[Callable[..., Any]] = []


def register_materializer(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Register a typed argument materializer.

    A materializer receives ``(value, expected_type, user=None, context=None)``
    and returns either:

    - ``(True, new_value)`` when it handled the value
    - ``(False, value)`` when the next materializer should try
    """

    if fn not in _materializers:
        _materializers.append(fn)
    return fn


async def materialize_arg(value, expected_type, *, user=None, context=None):
    """Materialize one argument value if a registered package handles it."""

    for fn in list(_materializers):
        result = fn(value, expected_type, user=user, context=context)
        if inspect.isawaitable(result):
            result = await result
        handled, new_value = result
        if handled:
            return new_value
    return value


def materializer_count() -> int:
    """Test helper: return the number of registered materializers."""

    return len(_materializers)
