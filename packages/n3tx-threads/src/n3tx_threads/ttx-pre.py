"""Model-targeted TX snapshots with JSON payloads and unhydrated references.

The destination identifies the owning entity, not a separate container.
Model actions own authorization, payload validation and target-scoped reads.
user_owner records the trusted appender; neither it nor source grants access.
Native create/list operations supply storage, not caller authorization.
APPEND binds a child to this record; threads pages immediate children by
timestamp. Neither operation resolves graph permissions. Migration, SQL
immutability, execution capture and consumer integration remain separate."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import fields as dataclass_fields, replace
from math import isfinite
from typing import ClassVar, Optional

from pydantic import Field, JsonValue

from n3tx_actors.actor import Actor
from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core.authorize import NEVER
from n3tx_core.models.ref import Ref, is_ref_url, public_id_url


class TTX(ActorModel):
    """Store normalized JSON without resolving names to payload classes.

    TTX(tx, user_owner=caller_id) constructs an unsaved snapshot. TTX(**fields)
    follows native model reconstruction without re-encoding stored content.
    JSON text is parsed once at input; other strings remain text. Native
    reference URLs become Ref values on access. The internal payload wrapper
    preserves JSON scalars through storage. Register this model explicitly;
    generic transport CRUD is denied. Trusted native storage calls must follow
    the host model's checks. The table still needs migration."""

    __tablename__: ClassVar[str] = "tx_records"
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {"*": NEVER}

    uuid: str
    name: str
    source: str
    target: str
    data: dict = Field(default_factory=dict)
    meta: dict = Field(default_factory=dict)
    timestamp: float = Field(allow_inf_nan=False)
    # Native SQLite schema inference unwraps typing.Optional, not PEP 604.
    user_owner: Optional[int] = Field(default=None, ge=1, strict=True)

    def __init__(self, tx: TX | None = None, **fields):
        """Adapt an optional TX and forward all model/runtime fields via MRO.

        Envelope overrides are rejected. Trusted callers supply user_owner
        separately; tx.meta.user is never used for attribution. Construction
        preserves the envelope target without resolving or authorizing it.
        It does not save, dispatch, or fetch referenced entities. Existing
        native ID-only construction retains its inherited lookup behavior."""
        # 0. Native reconstruction must not wrap or serialize stored data again.
        if tx is not None:
            if not isinstance(tx, TX):
                raise TypeError("Expected a TX envelope")
            envelope = {
                field.name: getattr(tx, field.name)
                for field in dataclass_fields(TX)
            }
            if fields.keys() & envelope.keys():
                raise TypeError("TX envelope fields cannot be overridden")
            payload = tx.data
            # 1. Explicit objects serialize without a content-type registry.
            if isinstance(payload, ActorModel):
                model = type(payload)
                if (
                    not getattr(model, "__storable__", False)
                    or not payload.id
                ):
                    raise ValueError("Persisted content needs a saved entity")
                payload = Ref(public_id_url(payload.id, target_cls=model))
            elif isinstance(payload, Actor):
                payload = payload.model_dump(
                    mode="json", by_alias=True,
                    include=set(type(payload).model_fields),
                )
            # 2. Parse JSON input once; retain non-JSON text verbatim.
            if isinstance(payload, Ref):
                payload = str(payload)
            elif isinstance(payload, str):
                try:
                    parsed = json.loads(payload)
                    json.dumps(parsed, allow_nan=False)
                except ValueError:
                    pass
                else:
                    payload = parsed
            if isinstance(payload, str) and is_ref_url(payload):
                payload = str(Ref(payload))
            # 3. Detach JSON content and exclude caller/runtime metadata.
            envelope["data"] = {
                "payload": json.loads(json.dumps(payload, allow_nan=False)),
            }
            keys = {"req", "seq", "stream", "stream_end", "error"}
            envelope["meta"] = {
                key: value for key, value in tx.meta.items()
                if key in keys and type(value) in (str, int, float, bool)
            }
            fields = {**envelope, **fields}
        # 4. Preserve Actor and ProtoModel initialization, including addr.
        super().__init__(**fields)

    @property
    def value(self) -> JsonValue | Ref:
        """Return detached JSON content or an unhydrated native reference.

        Stored strings are not JSON-parsed again. Reference recognition uses
        the native URL shape, not a model lookup. Nested JSON remains ordinary
        data; callers own casting, recursive interpretation and expansion."""
        # 0. Recognize top-level references without fetching their targets.
        payload = self.data["payload"]
        if isinstance(payload, str) and is_ref_url(payload):
            return Ref(payload)
        # 1. Mutating a returned object must not mutate the stored snapshot.
        return deepcopy(payload)

    def APPEND(self, tx: TX, *, user_owner: int | None = None) -> TTX:
        """Persist a child envelope targeting this saved TTX.

        This is trusted Python storage, not an authorized transport action.
        Callers must authorize first and supply appender attribution explicitly;
        the parent's owner and tx.meta.user are not inherited. Only target is
        rebound. The existence check and insert are not one transaction."""
        # 0. Reject invalid envelopes and absent parents before writing.
        if not isinstance(tx, TX):
            raise TypeError("Expected a TX envelope")
        if not self.id or TTX.get(self.id) is None:
            raise ValueError("Save the parent TTX before appending")
        # 1. Preserve envelope identity and normalize through native creation.
        snapshot = replace(
            tx, target=public_id_url(self.id, target_cls=TTX),
        )
        return TTX.create(TTX(snapshot, user_owner=user_owner))

    def threads(
        self, *, cursor: float | None = None, limit: int = 50,
    ) -> dict:
        """Page immediate children newest first using an exclusive timestamp.

        Callers own authorization. Returns data, cursor and has_more; the cursor
        is None on the last page. Equal timestamps have no secondary ordering
        and can be omitted at page boundaries. Reads provide no recursive
        expansion, stable concurrent snapshot or complete replay guarantee."""
        # 0. Validate paging and require an existing parent before querying.
        if type(limit) is not int or limit < 1:
            raise ValueError("Page limit must be a positive integer")
        if cursor is not None and (
            type(cursor) not in (int, float) or not isfinite(cursor)
        ):
            raise ValueError("Cursor must be a finite timestamp")
        if not self.id or TTX.get(self.id) is None:
            raise ValueError("Save the parent TTX before reading children")
        # 1. Scope native storage to direct children without an ID tie-breaker.
        where = {"target": public_id_url(self.id, target_cls=TTX)}
        if cursor is not None:
            where["timestamp__lt"] = cursor
        result = TTX.list(
            where=where, order_desc="timestamp", limit=limit,
        )
        # 2. Continue strictly before the final timestamp on a nonterminal page.
        page = result["data"]
        has_more = result["meta"]["has_more"]
        next_cursor = page[-1].timestamp if has_more and page else None
        return {"data": page, "cursor": next_cursor, "has_more": has_more}


# Changelog (Python has no block-comment syntax).
# - 2026-11-04: Document entity-targeted streams and host-owned access checks
#   after removing the separate Thread container; keep serialization intact.
#   Use native-supported Optional[int] for strict integer owner storage.
#   Add trusted child APPEND and timestamp-only threads paging directly on TTX.
# - 2026-11-03: Rename TXRecord to TTX with target membership and user_owner.
#   Adapt TX construction through native MRO and reconstruct lazy values.
#   Remove recording fields, predecessor, factories and custom SQL readers.
#   Accept raw JSON, JSON text, plain strings, references and Actor objects;
#   retain the payload wrapper and remove automatic payload-class resolution.
# - 2026-11-02: Move TX snapshots into the standalone threads package.
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
