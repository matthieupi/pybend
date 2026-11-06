"""Thread — owner/admin conversations backed by separate TXRecord rows.

One container owns identity, owner/scope metadata and authorized record access.
Thread rows live in threads; their copied TX envelopes live in tx_records.

API Surface (instance methods unless marked):
    append()              — Authorize and save one caller-attributed snapshot
    history()             — Decode codec-selected SDK messages in TX time order
    records()             — Read a newest-first page with a numeric time cursor
    THREAD()              — Read-check child, update-check parent, save link
    handler() @fullmethod — Async class/instance adapter for THREAD commands
    _authorize_records()  — Internal native-policy gate for record operations
    HISTORY_CODEC         — Default meta.codec selector: "pydantic-ai/v1"

The split: Thread owns authorization, attribution, decoding and page responses.

TXRecord owns envelope conversion and row selection. Use Thread methods for
caller checks; direct record CRUD bypasses them. Thread.user_owner grants owner
access; TXRecord.user_owner identifies the appender. Scope grants no access.

Register both models with storage; add Thread to the actor tree for routed TXs:
    Thread.append/history/records -> policy -> TXRecord -> native storage
    Thread.handler               -> THREAD adapter or inherited actor CRUD

Usage:
    # Registered storage, saved thread/child, authenticated caller mapping.
    record = thread.append(
        TX("NOTE", "worker", "notes", data={"text": "Hello"}), user=caller,
    )
    page = thread.records(user=caller, limit=20)
    if page["has_more"]:
        older = thread.records(user=caller, cursor=page["cursor"], limit=20)
    link = thread.THREAD(child, user=caller)

    # Only matching codec-tagged SDK payloads participate in agent history.
    messages = thread.history(user=caller)"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, ClassVar

from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core.authorize import (
    AUTHENTICATED,
    OWNER,
    ROLE,
    AccessContext,
    DefaultResolver,
)
from n3tx_core.models.ref import Ref, local_ref_id, public_id_url
from n3tx_core.utils.descriptors import fullmethod

if TYPE_CHECKING:
    from .tx_record import TXRecord


HISTORY_CODEC = "pydantic-ai/v1"


class Thread(ActorModel):
    """Thread — ActorModel with __storable__ = True; table threads.

    Stores protected user_owner/scope plus inherited id/image. Conversation
    entries are separate TXRecords, not an embedded messages collection.

    API Surface (instance methods; handler is async @fullmethod):
        append()                 — Save one snapshot under update policy
        history()                — Decode SDK history under read policy
        records()                — Return {data, cursor, has_more}
        THREAD()                 — Record an independently read-checked child
        handler()                — Adapt THREAD; delegate ordinary actor CRUD
        _authorize_records()     — Check this instance, without reloading it

    The split: this container owns policy; TXRecord owns stored envelopes.
    __access__ declares authenticated create and owner/admin read/list/update/
    delete. Explicit user=None bypasses record policy for trusted Python calls.
    THREAD checks child read plus parent update without changing either scope.

    Register both models before use. Appends retain TX timestamps. Repeated
    append calls are not atomic; callers supply predecessor links if needed.
    Timestamp pages are not exhaustive replay.

    Usage:
        # Saved thread with registered storage and authenticated caller.
        page = thread.records(user=caller, limit=20)
        if page["has_more"]:
            older = thread.records(user=caller, cursor=page["cursor"])"""

    __tablename__: ClassVar[str] = "threads"
    __storable__: ClassVar[bool] = True
    __protected_fields__: ClassVar[set] = {"user_owner", "scope"}
    __access__: ClassVar[dict] = {
        "read": OWNER | ROLE("admin"),
        "list": OWNER | ROLE("admin"),
        "create": AUTHENTICATED,
        "update": OWNER | ROLE("admin"),
        "delete": OWNER | ROLE("admin"),
    }

    user_owner: int | None = Field(default=None, description="Owner user ID")
    scope: Ref | None = Field(default=None, description="Business scope")

    def THREAD(
        self, child: Thread, *, user: dict | None, tx: TX | None = None,
    ) -> TXRecord:
        """Append a self-addressed child link without changing either scope."""
        # 0. Read the saved child under its independent native permission.
        child = Thread.get(child.id)
        if child is None:
            raise ValueError("Child Thread is unavailable")
        child._authorize_records(user=user)
        # 1. Store one explicit THREAD command in the parent's TX history.
        address = public_id_url(self.id, target_cls=Thread)
        data = {"child": public_id_url(child.id, target_cls=Thread)}
        snapshot = (
            TX("THREAD", address, address, data=data) if tx is None else
            replace(tx, source=address, target=address, data=data, meta={})
        )
        return self.append(snapshot, user=user)

    @fullmethod
    async def handler(target, tx: TX) -> None:
        """Adapt explicit THREAD commands; leave ordinary native CRUD intact."""
        # 0. Only child-link commands need this typed-argument adapter.
        if tx.name != "THREAD":
            await super(Thread, target).handler(tx)
            return
        try:
            parent = target.get(tx.data["id"]) if isinstance(
                target, type,
            ) else target
            child_id = local_ref_id(tx.data["child"], target_cls=Thread)
            child = Thread.get(child_id) if child_id is not None else None
            if parent is None or child is None:
                raise ValueError("Parent or child Thread is unavailable")
            record = parent.THREAD(child, user=tx.meta.get("user"), tx=tx)
            response = tx.reply(data={"id": record.id})
        except Exception as error:
            response = tx.exception(error)
        # 1. Send one reply without capturing persistence infrastructure.
        await target.send(response)

    def _authorize_records(
        self, *, user: dict | None, action: str = "read",
    ) -> Thread:
        """Apply native policy, retaining trusted internal calls for None."""
        # 0. Match the native actor boundary without changing public ingress.
        if user is not None:
            DefaultResolver().authorize(AccessContext(
                user=user, action=action, model_class=type(self), resource=self,
            ))
        return self

    def append(
        self, tx: TX, *, user: dict | None,
        predecessor: Ref[TXRecord] | None = None,
    ) -> TXRecord:
        """Save a caller-attributed snapshot retaining the supplied TX time."""
        from .tx_record import TXRecord
        # 0. Apply native update policy and convert the supplied envelope.
        self._authorize_records(user=user, action="update")
        record = TXRecord.from_tx(
            tx, thread=Ref[Thread](public_id_url(self.id, target_cls=Thread)),
            predecessor=predecessor,
        )
        # 1. Attribute the caller and persist through ordinary native CRUD.
        record.user_owner = user["user_id"] if user is not None else None
        return TXRecord.create(record)

    def history(
        self, *, user: dict | None, codec: str = HISTORY_CODEC,
    ) -> list:
        """Read codec-selected messages in ascending TX timestamp order."""
        from pydantic_ai.messages import ModelMessagesTypeAdapter
        from .tx_record import TXRecord
        # 0. Authorize before selecting and ordering stored protocol messages.
        self._authorize_records(user=user)
        records = TXRecord._records(
            Ref[Thread](public_id_url(self.id, target_cls=Thread)),
        )
        # 1. Let the native adapter restore complete protocol message objects.
        return list(ModelMessagesTypeAdapter.validate_python([
            row.data["payload"]
            for row in records if row.meta.get("codec") == codec
        ]))

    def records(
        self, *, user: dict | None, cursor: str = "", limit: int = 50,
    ) -> dict:
        """Read a descending TX timestamp page with a numeric string cursor."""
        from .tx_record import TXRecord
        # 0. Authorize and fetch one timestamp-ordered page plus its lookahead.
        self._authorize_records(user=user)
        records = TXRecord._records(
            Ref[Thread](public_id_url(self.id, target_cls=Thread)),
            cursor=cursor, limit=limit + 1, descending=True,
        )
        # 1. Return a timestamp-only continuation for older records.
        page = records[:limit]
        has_more = len(records) > len(page)
        next_cursor = ""
        if has_more and page:
            next_cursor = str(page[-1].timestamp)
        return {"data": page, "cursor": next_cursor, "has_more": has_more}


# Changelog
# - 2026-11-06: Attribute appended records with user_owner and use the supplied
#   TX timestamp for history ordering and numeric string page cursors.
#   Document the container API, record flow, policy and usage examples.
#   Use compact API-surface tables and examples in module/class overviews.
#   Remove append_many; callers repeat append and manage optional predecessors.
# - 2026-10-31: Add explicit self-addressed THREAD child-link commands.
# - 2026-10-31: Decode protocol messages from their payload containers.
# - 2026-10-31: Apply owner/admin policy to collection reads as well as members.
# - 2026-10-31: Replace mutable messages/routing fields with scoped TX records.
#   - Preserve the supplied transaction during native read-policy evaluation.
#   - Separate private record authorization from the native actor CRUD hook.
#   - Share native row decoding for transactional NULL/default parity.
#   - Replace binding grants with uniform source-read/source-update policy.
#   - Restore native owner/admin policy and ordinary sequential persistence;
#     remove basis checks, transaction binding and high-water cursor machinery.
#   - Decode history directly with the native Pydantic AI message adapter.
#   - Remove ID ordering and incremental tails; poll a latest timestamp window.
#   - Retain native trusted-internal user=None behavior and unset provenance.
#   - Query timestamp pages in SQLite and remove the redundant updates method.
