"""Native owner/admin Threads with record-backed conversation history.

Scope is business metadata, not permission inheritance. Record appends use
ordinary persistence: batches can partially succeed and retries can duplicate
records. History and pages have no transactional snapshot guarantee. Explicit
user=None denotes trusted internal Python execution, as in native ActorModel;
authenticated entrypoints remain responsible for supplying their caller."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, ClassVar

from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core.authorize import (
    AUTHENTICATED, OWNER, ROLE, AccessContext, DefaultResolver,
)
from n3tx_core.models.ref import Ref, public_id_url

if TYPE_CHECKING:
    from .tx_record import TXRecord


HISTORY_CODEC = "pydantic-ai/v1"


class Thread(ActorModel):
    """Store owner/scope metadata and expose authorized TX record operations."""

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
        """Authorize and save a snapshot without dispatch or deduplication."""
        from .tx_record import TXRecord
        # 0. Apply native update policy and convert the supplied envelope.
        self._authorize_records(user=user, action="update")
        record = TXRecord.from_tx(
            tx, thread=Ref[Thread](public_id_url(self.id, target_cls=Thread)),
            predecessor=predecessor,
        )
        # 1. Stamp this insertion and persist through ordinary native CRUD.
        record.recorded_at = datetime.now(timezone.utc)
        record.recorded_by = user["user_id"] if user is not None else None
        return TXRecord.create(record)

    def append_many(
        self, txs: list[TX], *, user: dict | None,
        predecessor: Ref[TXRecord] | None = None,
    ) -> list[TXRecord]:
        """Append sequentially, linking batch entries without atomicity.

        A later failure leaves earlier successful insertions saved. Retrying a
        batch creates new rows; no UUID deduplication is performed."""
        from .tx_record import TXRecord
        # 0. Chain each successful insertion to the preceding batch record.
        records = []
        for tx in txs:
            record = self.append(tx, user=user, predecessor=predecessor)
            records.append(record)
            predecessor = Ref[TXRecord](
                public_id_url(record.id, target_cls=TXRecord)
            )
        return records

    def history(
        self, *, user: dict | None, codec: str = HISTORY_CODEC,
    ) -> list:
        """Read codec-selected protocol messages under native Thread policy."""
        from pydantic_ai.messages import ModelMessagesTypeAdapter
        from .tx_record import TXRecord
        # 0. Authorize before selecting and ordering stored protocol messages.
        self._authorize_records(user=user)
        records = TXRecord._records(
            Ref[Thread](public_id_url(self.id, target_cls=Thread)),
        )
        # 1. Let the native adapter restore complete protocol message objects.
        return list(ModelMessagesTypeAdapter.validate_python([
            row.data for row in records if row.meta.get("codec") == codec
        ]))

    def records(
        self, *, user: dict | None, cursor: str = "", limit: int = 50,
    ) -> dict:
        """Read a descending timestamp page with an ISO timestamp cursor.

        Equal timestamps at a page boundary can be omitted from older pages;
        this is not an exhaustive or stable replay cursor."""
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
            last = page[-1]
            next_cursor = last.recorded_at.isoformat()
        return {"data": page, "cursor": next_cursor, "has_more": has_more}

# Changelog
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
