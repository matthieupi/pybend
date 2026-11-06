"""TXRecord — native stored snapshots of TX envelopes.

One TX, one record: copied envelope + Thread membership + caller attribution.
Rows live in tx_records. The TX timestamp is the only record clock.

API Surface (TXRecord methods; inherited CRUD remains trusted):
    from_tx()   @classmethod — Build a detached, unsaved envelope snapshot
    _records()  @classmethod — Internal timestamp-ordered SQLite row reader

The split: Thread owns authorization, caller attribution and SDK decoding.
TXRecord owns conversion and row selection. Use Thread.append/history/records
for caller checks; direct Python storage bypasses the declared deny-all policy.

Register Thread and TXRecord with native storage before persistence:
    Thread.append()          -> authorize -> from_tx -> user_owner -> create
    Thread.history/records() -> authorize -> _records -> decode/page

from_tx wraps copied TX data as {"payload": value}; it retains UUID, routing,
metadata and timestamp. Membership uses thread, not the transport target.
Links do not provide cascades; rows are mutable and appends persist separately.
UUIDs are not deduplicated. _records binds query values on configured SQLite.

Usage:
    # Registered storage, saved thread, and authenticated caller mapping.
    tx = TX("NOTE", "worker", "notes", data={"text": "Hello"})
    record = thread.append(tx, user=caller)
    assert record.data["payload"] == {"text": "Hello"}
    assert record.timestamp == tx.timestamp
    assert record.user_owner == caller["user_id"]

    # Conversion alone neither authorizes nor writes a row.
    draft = TXRecord.from_tx(tx, thread=record.thread)
    assert draft.id == 0 and draft.user_owner is None"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, TypeAdapter

from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core.authorize import NEVER
from n3tx_core.models.ref import Ref
from n3tx_core.storage.sqlite_storage import (
    _deserialize_json_fields,
    _validate_identifier,
)

from .thread import Thread


_TX_ADAPTER = TypeAdapter(TX)


class TXRecord(ActorModel):
    """TXRecord — ActorModel with __storable__ = True; table tx_records.

    Stores thread/predecessor links, the TX envelope and nullable user_owner.
    id/image come from ActorModel; timestamp retains the supplied TX time.

    API Surface (both @classmethod):
        from_tx()   — Copy envelope data into an unattributed draft
        _records()  — Select Thread members; caller must authorize first

    The split: Thread supplies policy and attribution; this model supplies
    trusted conversion/query operations and inherits ordinary native CRUD.
    user_owner identifies the appender, not a separate Thread access grant.
    predecessor is metadata, not a validated chain or ordering mechanism.

    from_tx wraps data under payload and copies meta. Direct construction does
    not enforce that wrapper. Register storage before create or _records;
    neither __storable__ nor __access__ makes Python CRUD authorized or atomic.

    Usage:
        # tx and thread_ref are an existing TX and saved Thread reference.
        draft = TXRecord.from_tx(tx, thread=thread_ref)
        assert draft.id == 0 and draft.user_owner is None"""

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
    user_owner: int | None = None

    @classmethod
    def from_tx(
        cls, tx: TX, *, thread: Ref[Thread],
        predecessor: Ref[TXRecord] | None = None,
    ) -> TXRecord:
        """Copy an envelope into a draft without attribution or persistence."""
        # 0. Serialize the native envelope without stringifying rich objects.
        envelope = _TX_ADAPTER.dump_python(tx, mode="json")
        envelope["data"] = {"payload": envelope["data"]}
        return cls(thread=thread, predecessor=predecessor, **envelope)

    @classmethod
    def _records(
        cls, thread: Ref[Thread], *, cursor: str = "",
        limit: int | None = None, descending: bool = False,
    ) -> list[TXRecord]:
        """Select Thread rows by TX timestamp after caller authorization.

        The calling Thread method owns authorization. A nonempty cursor is a
        numeric timestamp string, bound as a float for an exclusive upper bound.
        No extra transaction, population or secondary row reads occur."""
        # 0. Bind Thread, timestamp and limit values in one model-owned query.
        table = _validate_identifier(cls.__tablename__)
        sql = f"SELECT * FROM {table} WHERE thread = ?"
        parameters: list = [str(thread)]
        if cursor:
            sql += " AND timestamp < ?"
            parameters.append(float(cursor))
        sql += " ORDER BY timestamp " + ("DESC" if descending else "ASC")
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
# - 2026-11-06: Use TX timestamp for ordering/cursors; remove recorded_at and
#   rename recorded_by to user_owner for caller attribution.
#   Document the stored shape, API, authorization boundary and usage flow.
#   Use compact API-surface tables and examples in module/class overviews.
# - 2026-10-31: Store TX payloads inside a native JSON dictionary container.
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
