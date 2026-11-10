"""ThreadedMixin — explicit receiver and root-list action contracts.

API: MESSAGE receives text at a host; THREADS lists its conversation roots.
Compose before a host ActorModel, such as public User. Native ingress supplies
named user; the implementation slice must require a positive caller ID.
No flags, inbox handler, send override, registration or policy widening is
installed. Contract-only actions raise until behavior is implemented."""

from __future__ import annotations

from n3tx_core.utils.decorators import expose_route


class ThreadedMixin:
    """Receiver-only MESSAGE and THREADS contracts for an actor host.

    API: MESSAGE(desc, uuid, timestamp, user) -> dict; THREADS(user) -> list.
    Boundary: host receipt does not send onward. Native Actor.send remains the
    transport; owned-root TTX.MESSAGE is the separate sending action. No REPLY,
    _receive_message helper or automatic conversation capture is introduced.
    Integration: compose before User's ActorModel base; policy follows in the
    application slice, not by changing existing Note access."""

    @expose_route("/message", methods=["POST"])
    def MESSAGE(
        self, desc: str, uuid: str = "", timestamp: float = 0,
        user: dict | None = None,
    ) -> dict:
        """Receive once and return the receiver root's canonical response dict.

        uuid/time are forwarded from wire data by the sending action. Native
        user injection is mandatory authority, never an action-body identity.
        Raises NotImplementedError until receiving behavior is implemented."""
        raise NotImplementedError("ThreadedMixin.MESSAGE is not implemented")

    @expose_route("/threads", methods=["POST"])
    def THREADS(self, user: dict | None = None) -> list[dict]:
        """Return explicit canonical root response dicts, never typed models.

        Native ingress injects user; selection and policy belong to the next
        slice. Raises NotImplementedError until listing is implemented."""
        raise NotImplementedError("ThreadedMixin.THREADS is not implemented")


# Changelog (Python has no block-comment syntax).
# - 2026-11-10: Declare lowercase receiver/list action contracts as stubs.
