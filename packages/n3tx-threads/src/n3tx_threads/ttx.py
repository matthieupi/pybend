"""TTX — canonical storage and shared typed transaction operations.

One table stores the envelope, kind, JSON metadata and JSON object data. Typed
objects declare content fields; conversion packs them into ordinary TX.data.
Note and Thread inherit TTX directly; only TTX may use native storage.

API Surface:
    TTX.from_tx()       — Copy a TX into an unsaved canonical record
    TTX.tx()            — Project a record into an ordinary transport TX
    TTX.value           — Decode known kinds; copy unknown content unchanged
    TTX.threads()       — Direct outgoing records for a saved canonical row
    TTX.history()       — Direct incoming records for a saved canonical row
    TTX.create/get/save  — Raw native or exact-kind projected persistence
    TTX.list/update/delete — Native-shaped, exact-kind typed projections
    .tx() / .ttx()       — Convert a typed object to transport or storage

Note and NoteMixin live in note.py; Thread lives in thread.py. Import public
types from n3tx_threads, which loads them before schema-stage registration.

The split: TTX owns persistence; typed objects own content validation.
The kind field identifies content by class name independently of operation name.
An empty kind denotes base TTX; unknown text remains opaque. Canonical metadata
excludes kind; ordinary TX transport packs it into meta['kind'] only.
Class names are stable storage/wire contracts; renaming needs migration review.
No JSON-text parsing, reference hydration, dispatch or implicit writes occur.
Content uses canonical field names; field aliases are an unsupported gap.

Register only TTX against explicitly selected storage. Native CRUD is trusted
Python, not caller authorization; actions must authorize and remove secrets
from metadata before persistence. user_owner is explicit attribution only.
NoteMixin relies on native transport action authorization; direct Python calls
are trusted, with no extra host CRUD guard, saved-host check or fresh reload.
Legacy Thread/TXRecord, package wiring and archived files remain unchanged.
Actor.children remains a routing dictionary. Queries are trusted, unbounded
and unordered; no recursive traversal or implicit authorization is supplied.

Usage:
    from n3tx_threads import TTX, Note

    note = Note(source="users/1", target="emails/42", desc="Hello")
    assert note.tx().data == {"desc": "Hello"}
    draft = note.ttx(user_owner=1)
    assert draft.value.desc == note.desc
    # After registering TTX with disposable/native storage:
    saved = TTX.create(draft)
    assert TTX.get(saved.id).value.desc == note.desc"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from time import time
from typing import ClassVar, Optional
from uuid import uuid4

from pydantic import (
    BaseModel, ConfigDict, Field, JsonValue, field_validator,
    model_validator,
)

from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core.authorize import NEVER
from n3tx_core.models.storable_mixin import StorableMixin
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.utils.descriptors import fullmethod


_KNOWN_KINDS: dict[str, type[TTX]] = {}


def _canonical_only(native):
    """Guard a native descriptor while retaining class/instance binding."""

    @fullmethod
    def guarded(target, *args, **kwargs):
        """Bind native storage only to the canonical class or its instance."""
        # 0. Reject typed operations before registration or SQL is possible.
        cls = target if isinstance(target, type) else type(target)
        if cls is not TTX:
            raise TypeError("Use canonical TTX storage after typed.ttx()")
        instance = None if isinstance(target, type) else target
        return native.__get__(instance, TTX)(*args, **kwargs)

    return guarded


class TTX(ActorModel, auto_register=False):
    """TTX — the only registered storage model; table ttx, not tx_records.

    Stores TX fields, kind and nullable user_owner plus inherited id/image.
    Only kind selects a content type; name remains the operation. Metadata
    excludes the reserved kind key, which exists only in TX transport.

    API Surface:
        from_tx() @classmethod — Build a detached draft without saving
        tx()                  — Copy envelope/content into transport form
        value                 — Validate known content or copy unknown data
        create() / get() / save() — Raw or exact-kind projected persistence
        list() / update() / delete() — Native-shaped exact-kind projections
        ttx()                 — Copy into canonical storage form without I/O
        model_response()      — Canonical identity/schema for typed objects
        _storage_dict()       — Include defaults in native row writes
        threads() / history() — Query direct outgoing/incoming records

    The split: register this model, never the typed representations. Native
    CRUD does not enforce __access__; deny-all is a transport declaration.
    Missing/unknown kinds stay opaque. Invalid known content raises rather
    than silently downgrading to raw. Conversion preserves UUID and TX time.
    Subclass fields are authoritative; nonempty packed data is rejected.
    Field aliases are unsupported; ordinary Pydantic rules apply on decoding.
    Typed save replaces only a live same-kind row and returns a persisted view.
    Writes are trusted, last-write-wins, not authorization or compare-and-swap.
    Typed lists bind kind before pagination/counting. Update/delete kind checks
    are read-then-write, not atomic guards; no HTTP registration is implied.

    Usage:
        draft = TTX.from_tx(TX("EVENT", "worker", "sink", data={"n": 1}))
        assert draft.value == {"n": 1}"""

    __tablename__: ClassVar[str] = "ttx"
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {"*": NEVER}
    _content_fields: ClassVar[tuple[str, ...]] = ()
    model_config = ConfigDict(
        extra="forbid", validate_assignment=True, allow_inf_nan=False,
        populate_by_name=True, validate_by_name=True,
    )

    uuid: str
    name: str
    source: str
    target: str
    kind: str = Field(default="", strict=True, validate_default=True)
    data: dict[str, JsonValue] = Field(default_factory=dict)
    meta: dict[str, JsonValue] = Field(
        default_factory=dict, validate_default=True,
    )
    timestamp: float = Field(allow_inf_nan=False)
    user_owner: Optional[int] = Field(default=None, ge=1, strict=True)

    @classmethod
    def hydrate_fk(cls, data):
        """Leave embedded transaction JSON to ordinary Pydantic validation.

        Content models are not local storage relationships. ProtoModel still
        handles explicit ID-only construction before invoking this hook."""
        return data

    def _storage_dict(self, exclude_unset: bool = True) -> dict:
        """Materialize defaults so native create never writes missing JSON."""
        if type(self) is not TTX:
            raise TypeError("Use canonical TTX storage after typed.ttx()")
        # 0. SQLite inserts all columns, even when native create omits defaults.
        values = super()._storage_dict(exclude_unset=False)
        values["meta"] = self._projection_meta()
        return values

    @classmethod
    def from_tx(
        cls, tx: TX, *,
        user_owner: Optional[int] = None,
    ) -> TTX:
        """Copy a JSON-object TX, preserving its self-describing metadata."""
        # 0. Detach the envelope; do not infer authority or parse text as JSON.
        if not isinstance(tx, TX):
            raise TypeError("Expected a TX envelope")
        if not isinstance(tx.data, dict):
            raise TypeError("TX data must be a JSON object")
        return cls(user_owner=user_owner, **asdict(tx))

    def tx(self) -> TX:
        """Copy seven native TX fields, including the metadata discriminator."""
        # 0. Exclude storage identity and caller attribution from transport.
        return TX(
            name=self.name, source=self.source, target=self.target,
            uuid=self.uuid, timestamp=self.timestamp,
            data=self._payload(), meta=self._projection_meta(transport=True),
        )

    def _projection_meta(
        self, *, transport: bool = False,
    ) -> dict[str, JsonValue]:
        """Detach metadata and check reserved edits before projection."""
        # 0. In-place dict edits cannot introduce a second writable authority.
        meta = deepcopy(self.meta)
        if "kind" in meta:
            reserved = meta.pop("kind")
            if not isinstance(reserved, str) or reserved != self.kind:
                raise ValueError("meta.kind must match the stored kind field")
        if transport:
            meta["kind"] = self.kind
        return meta

    def _payload(self) -> dict[str, JsonValue]:
        """Pack content using ordinary Pydantic exclusion semantics.

        Excluded fields are omitted, including from persistence. A required
        excluded field can prevent decoding; a defaulted one can reconstruct
        its default instead of the original value. Preservation is deferred."""
        if type(self) is TTX:
            return deepcopy(self.data)
        # 0. Detect in-place packed-data edits before projecting typed fields.
        self._empty_data(self.data)
        return deepcopy(self.model_dump(
            mode="json", include=set(self._content_fields),
        ))

    @property
    def value(self) -> TTX | dict[str, JsonValue]:
        """Decode canonical names normally; field aliases are unsupported."""
        # 0. Decode only explicit local types, never names from dynamic imports.
        typed = _KNOWN_KINDS.get(self.kind)
        if typed is None:
            return deepcopy(self.data)
        # 1. Payload fields cannot replace routing or transport identity.
        envelope = asdict(self.tx())
        payload = envelope.pop("data")
        if payload.keys() & TTX.model_fields.keys():
            raise ValueError("Payload cannot override TTX envelope fields")
        if payload.keys() - set(typed._content_fields):
            raise ValueError("Payload contains undeclared typed content fields")
        return typed(**{
            **envelope, **payload, "id": self.id,
            "image": self.image, "user_owner": self.user_owner,
        })

    def _saved_addr(self) -> str:
        """Require an existing row and use its canonical local identity."""
        # 0. Actor addresses can be overridden; stored graph links cannot.
        if self.id <= 0:
            raise ValueError("Queries require a saved TTX identity")
        if TTX.get(self.id) is None:
            raise ValueError("Canonical TTX no longer exists")
        return f"{TTX.__tablename__}/{self.id}"

    def threads(self) -> list[TTX]:
        """Return all direct outgoing rows; caller owns authorization."""
        # 0. Native storage binds the canonical local address as a value.
        return TTX.list(sql_filter=("source = ?", [self._saved_addr()]))

    def history(self) -> list[TTX]:
        """Return all direct incoming rows; no ordering or recursion implied."""
        return TTX.list(sql_filter=("target = ?", [self._saved_addr()]))


    @model_validator(mode="before")
    @classmethod
    def _typed_defaults(cls, value):
        """Normalize kind once; generate identity/time only for typed input."""
        if not isinstance(value, dict):
            return value
        # 0. Keep canonical UUID/time required; never mutate caller input.
        values = dict(value)
        meta = values.get("meta", {})
        if isinstance(meta, dict):
            meta = deepcopy(meta)
            if "kind" in meta:
                reserved = meta.pop("kind")
                if not isinstance(reserved, str):
                    raise ValueError("meta.kind must be text")
                if "kind" in values and values["kind"] != reserved:
                    raise ValueError("kind and meta.kind must agree")
                values["kind"] = reserved
            values["meta"] = meta
        # 1. Missing raw kinds stay empty; typed defaults use the concrete name.
        if "kind" not in values:
            values["kind"] = "" if cls is TTX else cls.__name__
        if cls is not TTX:
            if "uuid" not in values:
                values["uuid"] = uuid4().hex[:12]
            if "timestamp" not in values:
                values["timestamp"] = time()
        return values

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs) -> None:
        """Discover typed content only after Pydantic has built all fields."""
        # 0. Inherited envelope fields never become packed content.
        super().__pydantic_init_subclass__(**kwargs)
        cls._content_fields = tuple(
            field for field in cls.model_fields if field not in TTX.model_fields
        )
        # 1. Persistent names must resolve to exactly one local schema.
        previous = _KNOWN_KINDS.get(cls.__name__)
        if previous is not None and previous is not cls:
            raise ValueError(f"Duplicate typed TX class name: {cls.__name__}")
        _KNOWN_KINDS[cls.__name__] = cls
        # 2. New kinds change canonical schemas, including cached host defs.
        for owner, schema in tuple(ProtoModel._schema_cache.items()):
            if owner is TTX or "TTX" in schema.get("$defs", {}):
                owner.invalidate_schema_cache()

    @field_validator("data")
    @classmethod
    def _empty_data(cls, value: dict) -> dict:
        """Reject packed input; supply declared typed fields instead."""
        if cls is not TTX and value:
            raise ValueError("Typed TTX data must be empty; use content fields")
        return value

    @field_validator("kind")
    @classmethod
    def _valid_kind(cls, value: str) -> str:
        """Require the concrete class discriminator, including on assignment."""
        if cls is not TTX and value != cls.__name__:
            raise ValueError("Typed TTX kind must match its class name")
        return value

    @classmethod
    def create(cls, data: TTX) -> TTX:
        """Create a canonical row or persist an unsaved exact typed kind."""
        if cls is TTX:
            if isinstance(data, TTX) and type(data) is not TTX:
                raise TypeError("Use typed.ttx() before canonical TTX.create")
            return super(TTX, TTX).create(data)
        # 0. A persisted identity is an update request, never an implicit clone.
        if type(data) is not cls:
            raise TypeError("create requires the requested concrete typed TX")
        if data.id != 0:
            raise ValueError("create requires an unsaved typed TX with id=0")
        record = data.ttx()
        record.value
        # 1. Only the canonical model reaches native storage.
        return TTX.create(record).value

    @classmethod
    def get(cls, id: int, as_dict: bool = False, populate=None):
        """Load raw canonical data or an exact-kind typed persisted view."""
        if cls is TTX:
            return super(TTX, TTX).get(
                id, as_dict=as_dict, populate=populate,
            )
        if as_dict or populate is not None:
            raise TypeError("Use canonical TTX.get for native read options")
        # 0. Decode only after checking the canonical discriminator.
        record = TTX.get(id)
        if record is None or record.kind != cls.__name__:
            return None
        return record.value

    @classmethod
    def list(
        cls, sql_filter: tuple = None, limit: int = None,
        offset: int = None, populate=None, ids: list = None,
    ):
        """List exact typed kinds, retaining native pagination and counts."""
        if cls is TTX:
            return super(TTX, TTX).list(
                sql_filter=sql_filter, limit=limit, offset=offset,
                populate=populate, ids=ids,
            )
        if populate is not None:
            raise TypeError("Use canonical TTX.list for native population")
        # 0. Push the discriminator into SQL before counting or pagination.
        clause, params = "kind = ?", [cls.__name__]
        if sql_filter is not None and sql_filter[0]:
            clause = f"({sql_filter[0]}) AND {clause}"
            params = list(sql_filter[1] or []) + params
        records = TTX.list(
            sql_filter=(clause, params), limit=limit, offset=offset, ids=ids,
        )
        # 1. Preserve native metadata; only data rows become typed views.
        if isinstance(records, dict):
            return {
                **records, "data": [record.value for record in records["data"]],
            }
        return [record.value for record in records]

    @fullmethod
    def update(
        target, id_or_data: int | BaseModel | dict,
        data: BaseModel | dict | None = None,
    ):
        """Update a fresh exact-kind row with native class/instance shapes."""
        cls = target if isinstance(target, type) else type(target)
        if cls is TTX:
            instance = None if isinstance(target, type) else target
            native = StorableMixin.__dict__["update"].__get__(instance, TTX)
            return native(id_or_data, data)
        # 0. Resolve native call shapes without trusting a stale instance view.
        if isinstance(target, type):
            if data is None:
                raise ValueError(
                    f"[UPDATING {cls.__name__}] Missing update data"
                )
            id, supplied = id_or_data, data
        else:
            id = target.id if data is None else id_or_data
            supplied = id_or_data if data is None else data
            if not id:
                raise ValueError("Cannot update unsaved instance without an id")
        if isinstance(supplied, BaseModel):
            supplied = supplied.model_dump(exclude_unset=True)
        elif isinstance(supplied, dict):
            supplied = dict(supplied)
        else:
            raise ValueError("Update data must be a model or dictionary")
        current = cls.get(id)
        if current is None:
            return None
        # 1. Canonicalize aliases; identity input never changes the target row.
        patch = cls._canonical_update_patch(supplied)
        patch.pop(cls.__pk__, None)
        if not patch:
            return current
        validation_data = {**current.model_dump(), **patch}
        # 2. Validate content and kind before packing one canonical row update.
        validated = cls(**validation_data)
        record = validated.ttx()
        packed = record._storage_dict()
        packed.pop(TTX.__pk__, None)
        saved = TTX.update(id, packed)
        return None if saved is None else saved.value

    @classmethod
    def delete(cls, id: int):
        """Delete only an exact-kind row; native deletion returns None."""
        if cls is TTX:
            return super(TTX, TTX).delete(id)
        # 0. This read-before-delete is a type check, not an atomic predicate.
        record = TTX.get(id)
        if record is None or record.kind != cls.__name__:
            return None
        return TTX.delete(id)

    def save(self) -> TTX:
        """Save raw natively or a typed draft/live same-kind row."""
        if type(self) is TTX:
            return super().save()
        if self.id == 0:
            return type(self).create(self)
        if self.id < 0:
            raise ValueError("save requires a nonnegative canonical identity")
        # 0. Validate both snapshots before any write; no type promotion occurs.
        record = self.ttx()
        record.value
        current = TTX.get(self.id)
        if current is None:
            raise ValueError("Canonical TTX no longer exists")
        if current.kind != type(self).__name__:
            raise ValueError("Cannot change an existing canonical TTX kind")
        current.value
        # 1. Native update preserves row identity and returns the stored view.
        saved = TTX.update(self.id, record._storage_dict())
        if saved is None:
            raise ValueError("Canonical TTX no longer exists")
        return saved.value

    # 0. Only canonical TTX may bind storage or create its table.
    set_storage = _canonical_only(StorableMixin.__dict__["set_storage"])
    create_table = _canonical_only(StorableMixin.__dict__["create_table"])

    def ttx(self, *, user_owner: Optional[int] = None) -> TTX:
        """Project without writing; retain ID/image and existing attribution.

        None retains user_owner; a positive override replaces attribution.
        A decoded persisted value keeps its ID, so save updates that row,
        rather than silently cloning its persisted identity."""
        # 0. Type selection survives storage without changing the TX protocol.
        record = TTX.from_tx(
            self.tx(),
            user_owner=self.user_owner if user_owner is None else user_owner,
        )
        # 1. Projection preserves identity; it is not an insert/clone request.
        record.id, record.image = self.id, self.image
        return record

    def model_response(self, **kwargs) -> dict:
        """Serialize a canonical public identity, never a separate typed row."""
        # 0. Mutable metadata must obey the same rule on every projection.
        self._projection_meta()
        if type(self) is TTX:
            response = super().model_response(**kwargs)
            selected = response.get("meta")
            if isinstance(selected, dict):
                selected.pop("kind", None)
            return response
        return self.ttx().model_response(**kwargs)


# Changelog
# - 2026-11-10: Move Note/NoteMixin to note.py and Thread to thread.py;
#   retain canonical TTX operations and the shared kind registry here.
# - 2026-11-09: Scaffold one canonical TTX table and non-storable Note/Thread
#   representations with explicit TX conversion and versioned content kinds.
#   Materialize storage defaults for native create/get/list consistency.
#   Share TTX inheritance, pack declared fields, guard typed storage misuse,
#   and query direct outgoing/incoming canonical local links.
#   Replace versioned kinds with self-describing class-name metadata; discover
#   local typed schemas and project create/get/save through canonical storage.
#   Reject undeclared payload keys and preserve canonical response identities.
#   Consolidate typed policies into TTX; Note and Thread inherit it directly.
#   Preserve required raw UUID/time and canonical native descriptor binding.
#   Persist strict kind on TTX; normalize wire metadata and reject conflicts.
#   Keep canonical metadata kind-free and pack kind only into TX transport.
#   Project typed list/update/delete through canonical storage; bind kind before
#   pagination and preserve native call shapes, counts and missing-row results.
#   Add explicit NoteMixin NOTE/NOTES with fresh host and action authorization;
#   use generic named-caller injection without Notes-specific actor handling.
#   Recheck public metadata; validate embedded models without FK hydration;
#   accept canonical content names alongside aliases during reconstruction.
#   Invalidate cached canonical schemas when newly declared kinds are added.
#   Document deferred excluded-content loss; retain Pydantic dump semantics.
#   Validate canonical embedded names recursively before typed construction;
#   preserve serializer include/exclude selections when sanitizing metadata.
#   Replace annotation prevalidation with structural alias-key translation;
#   preserve strict checks, field before validators and original scalar values.
#   Reject ambiguous union mappings, key collisions and alias-path synthesis.
#   Prefer active input aliases to preserve overlapping field-name snapshots;
#   retain canonical names when alias validation is explicitly disabled.
#   Remove alias translation and its reconstruction wrapper; field aliases
#   remain an unsupported content gap. Use ordinary model validation directly.
# - 2026-11-09: Remove _note_owner; rely on native action authorization and
#   trusted Python calls. Target self.addr without extra CRUD or host reloads.
