"""Typed Thread root envelope over canonical TTX storage.

API: Thread inherits TTX conversion and exact-kind persistence operations.
Import from n3tx_threads; register only TTX, never a separate Thread table.
No legacy container, permission or execution-parent behavior is added."""

from __future__ import annotations

from .ttx import TTX


class Thread(TTX, auto_register=False):
    """Thread — typed root envelope, not the legacy persistent container.

    API Surface:
        tx() / ttx() — Inherited transport/storage conversion
        create() / get() / save() — Canonical typed persistence
        list() / update() / delete() — Exact-kind native-shaped projections

    The split: kind='Thread' identifies an empty root payload. No
    append, children, permission inheritance or execution-parent semantics are
    implied yet.

    Usage:
        root = Thread(source="users/1", target="emails/42")
        assert root.ttx().kind == 'Thread'"""

    name: str = "THREAD"


# Changelog (Python has no block-comment syntax).
# - 2026-11-10: Move Thread from ttx without behavior changes.
