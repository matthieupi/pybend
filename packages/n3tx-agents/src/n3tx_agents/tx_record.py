"""Native stored snapshots of TX envelopes.

Snapshot conversion copies JSON data without dispatching or persisting it.
Rows use ordinary model storage; database immutability, UUID deduplication and
atomic batch persistence are not supplied by this model."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from pydantic import Field, TypeAdapter

from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core.authorize import NEVER
from n3tx_core.models.ref import Ref
from n3tx_core.storage.sqlite_storage import (
    _deserialize_json_fields, _validate_identifier,
)

from .thread import Thread


_TX_ADAPTER = TypeAdapter(TX)


class TXRecord(ActorModel):
    """Store a copied TX envelope with Thread links and insertion provenance.

    Generic transport access is denied. Thread methods authorize access before
    calling the inherited trusted Python storage operations."""

    __tablename__: ClassVar[str] = "tx_records"
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {"*": NEVER}

    thread: Ref[Thread]
    predecessor: Ref[TXRecord] | None = None
    uuid: str
    name: str
    source: str
    target: str
    data: dict = Field(default_factory=dict)
    meta: dict = Field(default_factory=dict)
    timestamp: float
    recorded_at: datetime | None = None
    recorded_by: int | None = None

    @classmethod
    def from_tx(
        cls, tx: TX, *, thread: Ref[Thread],
        predecessor: Ref[TXRecord] | None = None,
    ) -> TXRecord:
        """Copy an envelope into an unstamped draft without persistence."""
        # 0. Serialize the native envelope without stringifying rich objects.
        envelope = _TX_ADAPTER.dump_python(tx, mode="json")
        return cls(thread=thread, predecessor=predecessor, **envelope)

    @classmethod
    def _records(
        cls, thread: Ref[Thread], *, cursor: str = "",
        limit: int | None = None, descending: bool = False,
    ) -> list[TXRecord]:
        """Select authorized Thread rows by timestamp with optional paging.

        The calling Thread method owns authorization. Timestamp cursors bind as
        datetimes, using the same SQLite adapter as native timestamp writes.
        No extra transaction, population or secondary row reads occur."""
        # 0. Bind Thread, timestamp and limit values in one model-owned query.
        table = _validate_identifier(cls.__tablename__)
        sql = f"SELECT * FROM {table} WHERE thread = ?"
        parameters: list = [str(thread)]
        if cursor:
            sql += " AND recorded_at < ?"
            parameters.append(datetime.fromisoformat(cursor))
        sql += " ORDER BY recorded_at " + ("DESC" if descending else "ASC")
        if limit is not None:
            sql += " LIMIT ?"
            parameters.append(limit)
        # 1. Decode native JSON and omit SQL NULLs so model defaults apply.
        with cls.storage._connection() as connection:
            result = connection.execute(sql, parameters)
            columns = [column[0] for column in result.description]
            records = []
            for row in result.fetchall():
                data = {
                    name: value for name, value in zip(columns, row)
                    if name in cls.model_fields and value is not None
                }
                _deserialize_json_fields(cls, data)
                records.append(cls(**data))
        return records


TXRecord.model_rebuild()


# Changelog
# - 2026-10-31: Add TX snapshots, atomic append and bound record reads.
#   Validate exact SQL guards and use targeted append/codec queries; bound
#   encoded envelopes independently of application history to 200000 bytes.
#   Reuse native get row decoding for SQL NULL/default consistency.
#   Use Thread._authorize_records without overriding native actor CRUD policy.
#   Require source update policy for append, distinct from record read policy.
#   Restore ordinary native persistence; remove schema policing, CRUD overrides,
#   transactional append, deduplication and record paging machinery.
#   Serialize copied TX envelopes with the native Pydantic dataclass adapter.
#   Reuse the TX adapter and select timestamp-ordered pages in one SQL query.
