"""ThreadedMixin — explicit receiver and owner-scoped root-list actions.

API: MESSAGE receives text at a host; THREADS lists its conversation roots.
Compose before a host ActorModel, such as public User. Native ingress supplies
named user; actions require a positive existing local caller ID.
No flags, inbox handler, send override, registration or policy widening is
installed. Only receiving creates the opposite owner-local conversation view;
it never sends onward. Storage/cache writes are not a shared transaction."""

from __future__ import annotations

from math import isfinite

from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.erroring import MethodError

from .message import Message
from .thread import Thread
from .ttx import TTX, _caller


class ThreadedMixin:
    """Receiver-only MESSAGE and owner-scoped THREADS for a local User host.

    API: MESSAGE(desc, uuid, timestamp, user) -> dict; THREADS(user) -> list.
    Boundary: host receipt does not send onward. Native Actor.send remains the
    transport; owned-root TTX.MESSAGE is the separate sending action. No REPLY,
    _receive_message helper or automatic conversation capture is introduced.
    Integration: compose before User's ActorModel base and register local users
    storage/actor plus canonical TTX. Ingress owns role policy; these actions
    also enforce local caller/host identity. Existing Note access is unchanged.
    Direct Python calls need the same explicit trusted user dictionary."""

    @expose_route("/message", methods=["POST"])
    def MESSAGE(
        self, desc: str, uuid: str = "", timestamp: float = 0,
        user: dict | None = None,
    ) -> dict[str, object]:
        """Receive once and return the receiver root's canonical response dict.

        uuid/time are forwarded from wire data by the sending action. Native
        user injection is mandatory authority, never an action-body identity.
        Empty uuid generates a fresh identity; finite nonnegative event time
        is retained, including zero. No deduplication or echo is performed."""
        # 0. Validate both endpoints and envelope inputs before creating rows.
        users, author_id, author = _caller(user)
        if not isinstance(self, users) or users.get(self.id) is None:
            raise MethodError("A saved local User receiver is required", 404)
        if self.id == author_id:
            raise MethodError("A conversation requires a different peer", 400)
        if not isinstance(uuid, str) or (uuid and not uuid.strip()):
            raise MethodError("Message UUID must be nonblank text", 422)
        if (
            type(timestamp) not in (int, float)
            or not isfinite(timestamp) or timestamp < 0
        ):
            raise MethodError(
                "Message time must be finite and nonnegative", 422,
            )
        owner = f"users/{self.id}"
        fields = {"uuid": uuid} if uuid else {}
        message = Message(
            source=author, target=owner, desc=desc,
            timestamp=timestamp, **fields,
        )
        # 1. Find the receiver-owned full view, including archived roots.
        roots = Thread.list(
            where={
                "source": author, "target": owner, "user_owner": self.id,
            },
            archived=True, limit=1,
        )["data"]
        root = roots[0] if roots else Thread.create(Thread(
            source=author, target=owner, user_owner=self.id,
        ))
        # 2. ATTACH reopens the root and marks inbound content unread, no send.
        root.ATTACH(message)
        return TTX.get(root.id, archived=True).model_response()

    @expose_route("/threads", methods=["POST"])
    def THREADS(self, user: dict | None = None) -> list[dict[str, object]]:
        """Return explicit canonical root response dicts, never typed models.

        Native ingress injects user. Owner, host target and Thread kind are
        filtered in SQL; archived rows stay hidden. Results are unbounded."""
        # 0. A caller cannot use another User host as a conversation index.
        users, owner_id, owner = _caller(user)
        if not isinstance(self, users) or self.id != owner_id:
            raise MethodError("User ownership is required", 403)
        # 1. Native selection precedes explicit canonical serialization.
        roots = Thread.list(
            where={"target": owner, "user_owner": owner_id},
            order_desc="timestamp",
        )
        return [root.model_response() for root in roots]


# Changelog (Python has no block-comment syntax).
# - 2026-11-10: Implement receiver-only local messages and owner-scoped roots;
#   preserve wire UUID/time and delegate cache/unread state to internal ATTACH.
# - 2026-11-10: Parameterize dict returns for native object schema discovery.
# - 2026-11-10: Declare lowercase receiver/list action contracts as stubs.
