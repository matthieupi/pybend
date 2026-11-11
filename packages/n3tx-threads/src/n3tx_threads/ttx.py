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
    TTX.OPEN_THREAD    — Find/create a local owner-specific conversation root
    TTX.ATTACH/MESSAGE/MARK_READ — Explicit local append, send and read actions
    .tx() / .ttx()       — Convert a typed object to transport or storage

Note and NoteMixin live in note.py; Thread lives in thread.py. Import public
types from n3tx_threads, which loads them before schema-stage registration.

The split: TTX owns persistence; typed objects own content validation.
The kind field identifies content by class name independently of operation name.
An empty kind denotes base TTX; unknown text remains opaque. Canonical metadata
excludes kind; ordinary TX transport packs it into meta['kind'] only.
Class names are stable storage/wire contracts; renaming needs migration review.
Conversion does not parse JSON text, hydrate references, dispatch or write.
Messaging actions explicitly persist history and route through native Matrix.
Content uses canonical field names; field aliases are an unsupported gap.
Only string $id/$schema response extras are accepted at the top level; they
are nonauthoritative and excluded from canonical storage writes.

Register only TTX against explicitly selected storage. Native CRUD is trusted
Python, not caller authorization; actions must authorize and remove secrets
from metadata before persistence. user_owner is explicit attribution only.
NoteMixin relies on native transport action authorization; direct Python calls
are trusted, with no extra host CRUD guard, saved-host check or fresh reload.
Legacy Thread/TXRecord, package wiring and archived files remain unchanged.
Actor.children remains a routing dictionary. Queries are trusted, unbounded
unless paged, and unordered unless requested; no recursive traversal or
implicit authorization is supplied. Native LIST predicates and ordering target
canonical envelope fields, not packed typed content.

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
import re
from time import time
from typing import ClassVar, Literal, Optional
from uuid import uuid4

from pydantic import (
    BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, field_validator,
    model_validator,
)

from n3tx_actors.actor import Actor
from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core.authorize import NEVER
from n3tx_core.models.storable_mixin import StorableMixin
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.utils.descriptors import fullmethod
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.erroring import MethodError
from n3tx_core.utils.registrar import registered_models


_KNOWN_KINDS: dict[str, type[TTX]] = {}


def _caller(user: dict | None) -> tuple[type[ActorModel], int, str]:
    """Resolve a positive injected caller against the registered local User."""
    # 0. Body identities are not authority; ingress supplies the named user.
    user_id = user.get("user_id") if isinstance(user, dict) else None
    if type(user_id) is not int or not 0 < user_id <= 2**63 - 1:
        raise MethodError("An authenticated caller is required", 401)
    users = registered_models.get("users")
    if users is None or not issubclass(users, ActorModel):
        raise MethodError("Local User storage is unavailable", 503)
    if users.get(user_id) is None:
        raise MethodError("Caller is unavailable", 403)
    return users, user_id, f"users/{user_id}"


def _local_user(address: str, users: type[ActorModel]) -> int:
    """Validate an existing local users/id address without reference I/O."""
    # 0. Reject remote, aliased, noncanonical and oversized peer identities.
    if not isinstance(address, str) or not re.fullmatch(
        r"users/[1-9][0-9]{0,18}", address,
    ):
        raise MethodError("Peer must be a local users/id address", 400)
    user_id = int(address.split("/")[1])
    if user_id > 2**63 - 1:
        raise MethodError("Peer ID is out of range", 400)
    if users.get(user_id) is None:
        raise MethodError("Peer is unavailable", 404)
    return user_id


def _refresh_latest(target: str) -> None:
    """Refresh one direct Thread cache after a child mutation or deletion."""
    # 0. Only canonical immediate root links participate; never traverse graphs.
    if not re.fullmatch(r"ttx/[1-9][0-9]{0,18}", target):
        return
    root_id = int(target.split("/")[1])
    if root_id > 2**63 - 1:
        return
    root = TTX.get(root_id, archived=True)
    if root is None or root.kind != "Thread":
        return
    # 1. Keep one visible direct snapshot, excluding nested Thread containers.
    page = TTX.list(
        sql_filter=("target = ? AND kind != ?", [target, "Thread"]),
        order_desc="timestamp", limit=1,
    )
    latest = page["data"][0] if page["data"] else None
    data = deepcopy(root.data)
    data["latest"] = None if latest is None else latest.model_dump(mode="json")
    # 2. Root updates do not refresh another root or propagate recursively.
    TTX.update(root.id, {"data": data})


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

    Stores TX fields, kind, archive/read state and nullable user_owner plus
    inherited id/image. Reads hide archived rows; mutations include them.
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
        OPEN_THREAD()         — Bootstrap an owner-local peer conversation
        ATTACH()              — Trusted clone/cache append, without dispatch
        MESSAGE() / MARK_READ() — Owned-root sending and shared read state

    The split: register this model, never the typed representations. Native
    CRUD does not enforce __access__; deny-all is a transport declaration.
    Missing/unknown kinds stay opaque. Invalid known content raises rather
    than silently downgrading to raw. Conversion preserves UUID and TX time.
    Subclass fields override raw data keys; other raw keys remain detached.
    Field aliases are unsupported; ordinary Pydantic rules apply on decoding.
    Typed save replaces only a live same-kind row and returns a persisted view.
    Writes are trusted, last-write-wins, not authorization or compare-and-swap.
    Typed lists bind kind before pagination/counting. Update/delete kind checks
    are read-then-write, not atomic guards. Exposed messaging actions also
    enforce saved local owner identity; ingress still owns role policy.

    Usage:
        draft = TTX.from_tx(TX("EVENT", "worker", "sink", data={"n": 1}))
        assert draft.value == {"n": 1}"""

    __tablename__: ClassVar[str] = "ttx"
    __storable__: ClassVar[bool] = True
    __access__: ClassVar[dict] = {"*": NEVER}
    _content_fields: ClassVar[tuple[str, ...]] = ()
    model_config = ConfigDict(
        extra="allow", validate_assignment=True, allow_inf_nan=False,
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
    archived: bool = False
    status: Literal["READ", "UNREAD", "ASK"] = "READ"

    @classmethod
    def hydrate_fk(cls, data):
        """Leave embedded transaction JSON to ordinary Pydantic validation.

        Content models are not local storage relationships. ProtoModel still
        handles explicit ID-only construction before invoking this hook."""
        return data

    def _storage_dict(self, exclude_unset: bool = True) -> dict:
        """Materialize defaults without persisting response identity extras."""
        if type(self) is not TTX:
            raise TypeError("Use canonical TTX storage after typed.ttx()")
        # 0. SQLite inserts all columns, even when native create omits defaults.
        values = {
            name: value
            for name, value in super()._storage_dict(
                exclude_unset=False,
            ).items()
            if name in TTX.model_fields
        }
        values["meta"] = self._projection_meta()
        return values

    @classmethod
    def from_tx(
        cls, tx: TX, *,
        user_owner: Optional[int] = None,
        archived: bool = False,
        status: Literal["READ", "UNREAD", "ASK"] = "READ",
    ) -> TTX:
        """Copy a JSON-object TX, preserving its self-describing metadata."""
        # 0. Detach the envelope; do not infer authority or parse text as JSON.
        if not isinstance(tx, TX):
            raise TypeError("Expected a TX envelope")
        if not isinstance(tx.data, dict):
            raise TypeError("TX data must be a JSON object")
        return cls(
            user_owner=user_owner, archived=archived, status=status,
            **asdict(tx),
        )

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
        """Merge detached raw data with authoritative declared content.

        Excluded fields are omitted, including from persistence. A required
        excluded field can prevent decoding; a defaulted one can reconstruct
        its default instead of the original value. Raw extras remain raw."""
        if type(self) is TTX:
            return deepcopy(self.data)
        # 0. Declared content wins; unknown raw keys never become attributes.
        declared = self.model_dump(
            mode="json", include=set(self._content_fields),
        )
        return {**deepcopy(self.data), **deepcopy(declared)}

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
        declared = {
            key: value for key, value in payload.items()
            if key in typed._content_fields
        }
        raw = {
            key: value for key, value in payload.items()
            if key not in typed._content_fields
        }
        return typed(**{
            **envelope, **declared, "data": raw, "id": self.id,
            "image": self.image, "user_owner": self.user_owner,
            "archived": self.archived, "status": self.status,
        })

    def ATTACH(self, entry: TTX) -> TTX:
        """Clone an entry into this saved Thread and update its local cache.

        Trusted Python only; caller owns authorization. Attribution belongs to
        the root owner, not the author. Inbound content marks the root UNREAD;
        outbound content preserves existing state. Writes are not atomic."""
        # 0. Reload even archived roots; no nested Thread caches are permitted.
        root = TTX.get(self.id, archived=True) if self.id > 0 else None
        if root is None or root.kind != "Thread":
            raise MethodError("ATTACH requires a saved Thread root", 400)
        if not isinstance(entry, TTX) or entry.kind == "Thread":
            raise MethodError("Attach a TTX entry, not a Thread root", 400)
        # 1. Clone identity locally, retaining UUID/time and detached content.
        clone = entry.ttx()
        clone.id = 0
        clone.target = f"ttx/{root.id}"
        clone.user_owner = root.user_owner
        clone.archived = False
        clone.meta.pop("user", None)
        inbound = clone.source != root.target
        clone.status = "UNREAD" if inbound else "READ"
        saved = TTX.create(clone)
        # 2. Reopen on append; sending must not clear an unread incoming turn.
        data = deepcopy(root.data)
        data["latest"] = saved.model_dump(mode="json")
        TTX.update(root.id, {
            "data": data, "archived": False,
            "status": "UNREAD" if inbound else root.status,
        })
        return saved

    @classmethod
    @expose_route("/open_thread", methods=["POST"])
    def OPEN_THREAD(
        cls, peer: str, user: dict | None = None,
    ) -> dict[str, object]:
        """Find/create an owner-local peer Thread without granting generic CRUD.

        Peer must be an existing different local User. Archived matches reopen
        without clearing read state. Pair lookup/create is not a unique or
        concurrent transaction guarantee. Return a canonical root dictionary."""
        from .thread import Thread

        # 0. Native named caller injection defines the owner, never the body.
        users, owner_id, owner = _caller(user)
        peer_id = _local_user(peer, users)
        if peer_id == owner_id:
            raise MethodError("A conversation requires a different peer", 400)
        # 1. Reuse both archive states; pair predicates run before selection.
        roots = Thread.list(
            where={"source": peer, "target": owner, "user_owner": owner_id},
            archived=True, limit=1,
        )["data"]
        if roots:
            root = roots[0].ttx()
            if root.archived:
                root = TTX.update(root.id, {"archived": False})
        else:
            root = Thread.create(Thread(
                source=peer, target=owner, user_owner=owner_id,
            )).ttx()
        return root.model_response()

    def _owned_root(self, user: dict | None) -> TTX:
        """Reload a saved Thread and enforce ownership on every transport."""
        # 0. Raw Matrix may omit HTTP policy fallback; enforce domain ownership.
        users, owner_id, owner = _caller(user)
        root = TTX.get(self.id, archived=True) if self.id > 0 else None
        if root is None or root.kind != "Thread":
            raise MethodError("A saved Thread root is required", 404)
        if root.user_owner != owner_id or root.target != owner:
            raise MethodError("Thread ownership is required", 403)
        if _local_user(root.source, users) == owner_id:
            raise MethodError("A conversation requires a different peer", 400)
        return root

    @expose_route("/message", methods=["POST"])
    async def MESSAGE(
        self, desc: str, user: dict | None = None,
    ) -> dict[str, object]:
        """Send from an owned root and return its canonical response dict.

        Native ingress injects user. Local history is saved before native send;
        the returned root is not evidence of durable delivery. Failure or
        response loss can leave partial history; never retry automatically."""
        from .message import Message

        # 0. Validate ownership, content and the existing native User actor.
        root = self._owned_root(user)
        router = Actor.root()
        users = registered_models["users"]
        if router is None or router.children.get("users") is not users:
            raise MethodError("Local User actor is unavailable", 503)
        message = Message(source=root.target, target=root.source, desc=desc)
        # 1. Persist a local copy; transport keeps the logical peer addressing.
        root.ATTACH(message)
        wire = TX(
            "MESSAGE", source=message.source, target="users",
            data={
                "id": int(root.source.split("/")[1]), "desc": message.desc,
                "uuid": message.uuid, "timestamp": message.timestamp,
            },
            uuid=message.uuid, timestamp=message.timestamp,
            meta={"user": deepcopy(user)},
        )
        # 2. Route through Matrix directly to avoid TTX actor source prefixes.
        await router.send(wire)
        return TTX.get(root.id, archived=True).model_response()

    @expose_route("/mark_read", methods=["POST"])
    def MARK_READ(self, user: dict | None = None) -> dict[str, object]:
        """Mark this root READ and return an explicit canonical response dict.

        Native ingress injects user; raw Matrix and Python receive the same
        owner check. Only root state changes; no per-user receipt is added."""
        # 0. Reload and authorize the saved root before its state transition.
        root = self._owned_root(user)
        return TTX.update(root.id, {"status": "READ"}).model_response()

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
        """Check top-level input and normalize typed envelope defaults."""
        if not isinstance(value, dict):
            return value
        # 0. Native response validation needs only two reserved string extras.
        extra = value.keys() - cls.model_fields.keys()
        if extra - {"$id", "$schema"}:
            raise ValueError("Undeclared TTX top-level fields are not allowed")
        for name in extra:
            if not isinstance(value[name], str):
                raise ValueError(f"{name} response metadata must be text")
        # 1. Keep canonical UUID/time required; never mutate caller input.
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
        # 2. Missing raw kinds stay empty; typed defaults use the concrete name.
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
    def get(
        cls, id: int, as_dict: bool = False, populate=None,
        *, archived: bool = False,
    ) -> TTX | dict | None:
        """Load a visible row; archived=True includes both archive states.

        as_dict preserves canonical storage dictionaries with a decoded archive
        boolean, even for typed lookup. Typed population remains unsupported."""
        if cls is TTX:
            record = super(TTX, TTX).get(
                id, as_dict=as_dict, populate=populate,
            )
            # 0. New native tables use TEXT for bool; decode raw "0" first.
            if isinstance(record, dict):
                record["archived"] = TypeAdapter(bool).validate_python(
                    record.get("archived", False),
                )
                hidden = record["archived"]
            else:
                hidden = getattr(record, "archived", False)
            return None if hidden and not archived else record
        if populate is not None:
            raise TypeError("Use canonical TTX.get for native population")
        # 0. Decode only after checking the canonical discriminator.
        record = TTX.get(id, as_dict=as_dict, archived=archived)
        kind = (
            record.get("kind") if isinstance(record, dict)
            else getattr(record, "kind", None)
        )
        if record is None or kind != cls.__name__:
            return None
        if as_dict:
            return record
        return record.value

    @classmethod
    def list(
        cls, sql_filter: tuple = None, limit: int = None,
        offset: int = None, populate=None, ids: list = None,
        *, order_asc: str | None = None, order_desc: str | None = None,
        where: dict | None = None,
        archived: bool = False,
    ):
        """List exact kinds with native envelope filters, ordering and pages.

        Typed content fields are not queryable. Canonical TTX compiles where
        within trusted SQL, archive and exact-kind restrictions before counts.
        archived=False hides archived rows; True includes both states."""
        # 0. Archive visibility is a SQL restriction before native counts.
        if not archived:
            clause, params = "archived = ?", [False]
            if sql_filter is not None and sql_filter[0]:
                clause = f"({sql_filter[0]}) AND {clause}"
                params = list(sql_filter[1] or []) + params
            sql_filter = (clause, params)
        if cls is TTX:
            return super(TTX, TTX).list(
                sql_filter=sql_filter, limit=limit, offset=offset,
                populate=populate, ids=ids,
                order_asc=order_asc, order_desc=order_desc, where=where,
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
            order_asc=order_asc, order_desc=order_desc, where=where,
            archived=True,
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
            # 0. Bind a fresh row so native update can see archived state.
            if isinstance(target, type):
                if data is None:
                    raise ValueError("[UPDATING TTX] Missing update data")
                id, supplied = id_or_data, data
            else:
                id = target.id if data is None else id_or_data
                supplied = id_or_data if data is None else data
                if not id:
                    raise ValueError("Cannot update unsaved TTX without an id")
            current = TTX.get(id, archived=True)
            if current is None:
                return None
            native = StorableMixin.__dict__["update"].__get__(current, TTX)
            result = native(supplied)
            # 1. Native's final get hides archived rows; return the actual row.
            saved = TTX.get(id, archived=True)
            if result is None and saved is not None:
                TTX._publish_lifecycle("after_update", saved.model_response())
            # 2. Child edits refresh only direct caches, never root ancestors.
            if current.kind != "Thread":
                _refresh_latest(current.target)
                if saved is not None and saved.target != current.target:
                    _refresh_latest(saved.target)
            return saved
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
        current = cls.get(id, archived=True)
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
            # 0. Retain one old link for direct cache repair after deletion.
            current = TTX.get(id, archived=True)
            result = super(TTX, TTX).delete(id)
            if current is not None and current.kind != "Thread":
                _refresh_latest(current.target)
            return result
        # 0. This read-before-delete is a type check, not an atomic predicate.
        record = TTX.get(id, archived=True)
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
        current = TTX.get(self.id, archived=True)
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
            archived=self.archived, status=self.status,
        )
        # 1. Projection preserves identity; it is not an insert/clone request.
        record.id, record.image = self.id, self.image
        return record

    def model_response(self, **kwargs) -> dict:
        """Serialize a canonical public identity, never a separate typed row."""
        # 0. Mutable metadata must obey the same rule on every projection.
        self._projection_meta()
        if type(self) is TTX and not self.model_extra:
            response = super().model_response(**kwargs)
            selected = response.get("meta")
            if isinstance(selected, dict):
                selected.pop("kind", None)
            return response
        # 1. Reproject response extras before native stages synthesize identity.
        return self.ttx().model_response(**kwargs)


# Changelog
# - 2026-11-10:
#   - Accept only string response identity extras for native CRUD validation;
#     omit them from storage and rederive canonical response identity.
#   - Implement local OPEN_THREAD, attach/latest, owned send and read actions.
#   - Refresh direct root caches on child mutations without graph propagation.
#   - Keep caller metadata transient and use native Matrix send unchanged.
#   - Parameterize public dict returns for native object schema discovery.
#   - Decode raw stored archive booleans before dictionary-read visibility.
#   - Add archive/read state, detached raw extras and declared-field precedence.
#   - Filter archived reads before list counts; include archived mutation rows.
#   - Declare internal attach and lowercase messaging/read action stubs.
#   - Move Note/NoteMixin to note.py and Thread to thread.py;
#     retain canonical TTX operations and the shared kind registry here.
#   - Forward native LIST envelope predicates and ordering through canonical
#     storage while retaining typed kind-before-count restrictions.
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
