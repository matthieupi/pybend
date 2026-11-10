"""Parent-authorized TTX writes and reads for model-owned interaction streams.

Explicit model actions select the entry name and validate domain input. This
plain mixin adds no fields, container, routing hook or automatic execution
capture. Native storage remains trusted; these helpers enforce parent access."""

from dataclasses import replace

from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core.authorize import (
    AccessContext, AccessDenied, DefaultResolver,
)
from n3tx_core.models.ref import public_id_url
from n3tx_core.utils.erroring import MethodError

from .ttx import TTX


class ThreadedMixin:
    """Share explicit entry operations using the current host's native policy.

    Append requires parent update; reads require parent read. Attribution does
    not grant entry access. A missing caller is anonymous, not an internal
    authorization bypass. Supplied callers must come from a trusted boundary."""

    def _entry_owner(
        self, *, action: str, user: dict | None,
    ) -> ActorModel:
        """Reload the host and authorize against its current persisted state."""
        # 0. An unsaved or deleted host cannot own an interaction stream.
        if type(self.id) is not int or self.id <= 0:
            raise MethodError("Entry owner is unavailable", 404)
        owner = type(self).get(self.id)
        if owner is None:
            raise MethodError("Entry owner is unavailable", 404)
        # 1. Reuse parent policy without granting access from attribution.
        try:
            DefaultResolver().authorize(AccessContext(
                user=user or {}, action=action,
                model_class=type(owner), resource=owner,
            ))
        except AccessDenied:
            raise MethodError("Entry access denied", 403) from None
        return owner

    def _append_entry(self, tx: TX, *, user: dict | None) -> TTX:
        """Save one envelope under the authorized host without changing it.

        Canonical parent targeting replaces transport addressing. UUID, source
        and timestamp survive; TTX normalizes data and strips caller metadata.
        Inserts are not deduplicated or atomic with business effects."""
        # 0. Check current parent update access before constructing a snapshot.
        owner = self._entry_owner(action="update", user=user)
        if not isinstance(tx, TX):
            raise TypeError("Expected a TX envelope")
        # 1. Bind the target to the host, never to a supplied payload identity.
        snapshot = replace(
            tx, target=public_id_url(owner.id, target_cls=type(owner)),
        )
        return TTX.create(TTX(
            snapshot, user_owner=(user or {}).get("user_id"),
        ))

    def _entries(self, *, name: str, user: dict | None) -> list[TTX]:
        """Read named host entries by timestamp, without hydration or paging.

        Equal timestamps have no defined relative order. The returned list is
        unbounded; it is not a replay cursor or a concurrent snapshot."""
        # 0. Authorize even an empty stream against the current parent record.
        owner = self._entry_owner(action="read", user=user)
        # 1. Scope and select the entry name before native storage reads.
        return TTX.list(
            where={
                "target": public_id_url(owner.id, target_cls=type(owner)),
                "name": name,
            },
            order_asc="timestamp",
        )


# Changelog (Python has no block-comment syntax).
# - 2026-11-04: Replace manifest capture with parent-authorized TTX helpers;
#   remove container creation, context propagation and execution interception.
#   Rename the implementation module to mixin.py.
# - 2026-11-02: Move execution capture into the standalone threads package.
# - 2026-10-31: Bridge selected authenticated actions into native TX dispatch.
# - 2026-10-31: Record arrivals only at the envelope's exact destination.
# - 2026-10-31: Record only inbox arrivals; remove send capture and its guard.
# - 2026-10-31: Add opt-in native TX capture without global Matrix observation.
