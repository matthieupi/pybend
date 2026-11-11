"""Typed Thread root envelope over canonical TTX storage.

API: Thread inherits TTX conversion, persistence and explicit messaging actions.
Import from n3tx_threads; register only TTX, never a separate Thread table.
latest is an embedded canonical snapshot, not a Ref or local foreign key.
No legacy container, permission or execution-parent behavior is added."""

from __future__ import annotations

from .ttx import TTX


class Thread(TTX, auto_register=False):
    """Thread — typed root envelope, not the legacy persistent container.

    API Surface:
        tx() / ttx() — Inherited transport/storage conversion
        create() / get() / save() — Canonical typed persistence
        list() / update() / delete() — Exact-kind native-shaped projections
        OPEN_THREAD() — Inherited local pair bootstrap, not generic create
        ATTACH() / MESSAGE() / MARK_READ() — Inherited local messaging actions
        latest — Cached canonical embedded TTX snapshot, or None

    The split: kind='Thread' identifies root content. latest is packed into
    canonical data; inherited TTX hydration leaves it embedded. It is not an
    independently hydrated relationship. Messaging actions enforce local owner
    identity; native ingress owns role policy. There is no implicit delivery,
    graph permission inheritance or execution-parent behavior.

    Usage:
        root = Thread(source="users/2", target="users/1", user_owner=1)
        assert root.ttx().kind == 'Thread'"""

    name: str = "THREAD"
    latest: TTX | None = None


# Changelog (Python has no block-comment syntax).
# - 2026-11-10: Document inherited messaging behavior and peer/owner direction.
# - 2026-11-10: Add embedded latest snapshot and inherit messaging contracts.
# - 2026-11-10: Move Thread from ttx without behavior changes.
