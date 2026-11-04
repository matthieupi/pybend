"""Host-authorized Notes over TTX using disposable HTTP and Matrix storage."""

import json
from copy import deepcopy
from queue import Empty
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient

from n3tx_actors import Actor, Matrix, TX
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core import config
from n3tx_core.api.backend import FastAPIBackend
from n3tx_core.api.routes_fastapi import router
from n3tx_core.authorize import (
    NEVER, OWNER, ROLE, auth, configure, create_token,
)
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.ref import Ref, public_id_url
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.erroring import MethodError
from n3tx_core.utils.registrar import register_model
from n3tx_threads import NotesMixin, ThreadedMixin, TTX


pytestmark = pytest.mark.unit
WRITER = {"user_id": 1, "role": "staff"}
OTHER = {"user_id": 2, "role": "reader"}
ADMIN = {"user_id": 3, "role": "admin"}


class Notebook(ActorModel):
    """Separate host write and read authority without a Notes-specific ACL."""

    __tablename__ = "notes_examples"
    __storable__ = True
    __notes__ = True
    __protected_fields__: ClassVar[set] = {"user_owner", "locked"}
    __access__: ClassVar[dict] = {
        "*": NEVER,
        "create": ROLE("staff", "admin"),
        "read": ROLE("reader", "admin"),
        "update": OWNER & ROLE("staff", "admin"),
    }
    title: str = "Synthetic notebook"
    user_owner: int = 1
    locked: bool = False


class ChildNotebook(Notebook):
    """Override parent rules so inherited actions must remap per subclass."""

    __tablename__ = "child_notes_examples"
    __access__: ClassVar[dict] = {
        "*": NEVER, "read": ROLE("staff"), "update": ROLE("reader"),
    }


def _ref(record):
    """Return a saved host's canonical identity."""
    return public_id_url(record.id, target_cls=type(record))


def _headers(user):
    """Issue a native session token for a synthetic caller."""
    return {"x-access-token": create_token(
        user["user_id"], "notes@example.test", user["role"],
    )}


@pytest.fixture
def notes_runtime(tmp_path, monkeypatch):
    """Register real models/routes without invoking deferred app bootstrap."""
    # 0. Preserve routes, schemas and auth around disposable registration.
    saved_routes = list(router.routes)
    saved_cache = dict(ProtoModel._schema_cache)
    saved_auth = (auth._jwt_secret, auth._jwt_expiry_hours)
    monkeypatch.setattr(config, "DEBUG", False)
    router.routes[:] = []
    ProtoModel._schema_cache.clear()
    storage = SQLiteStorage(str(tmp_path / "notes.sqlite3"))
    try:
        configure(jwt_secret="synthetic-notes-secret-not-for-production")
        root = Matrix()
        Actor.root(root)
        for model in (Notebook, ChildNotebook, TTX):
            monkeypatch.setattr(
                model, "storage", getattr(model, "storage", None),
                raising=False,
            )
            monkeypatch.setattr(model, "__interceptors__", {
                key: list(value)
                for key, value in model.__interceptors__.items()
            })
            register_model(model, storage=storage)
            root._children[model.__addr__] = model
        backend = FastAPIBackend(
            name="Notes", version="1", description="Synthetic Notes tests",
        )
        backend.register_routes({})
        # 1. Exercise generated HTTP and the same registered Matrix hosts.
        with TestClient(backend.app) as client:
            yield root, client
    finally:
        # 2. Release owned connections and restore surrounding process state.
        while True:
            try:
                connection = storage._pool.get_nowait()
            except Empty:
                break
            connection.rollback()
            connection.close()
        router.routes[:] = saved_routes
        ProtoModel._schema_cache.clear()
        ProtoModel._schema_cache.update(saved_cache)
        auth._jwt_secret, auth._jwt_expiry_hours = saved_auth


def test_flag_schema_and_inherited_policy_mapping(notes_runtime):
    """Inject Notes once, map host rules and add no pointer or extra ACL."""
    # 0. Inspect capability injection and unchanged parent declarations.
    assert issubclass(NotesMixin, ThreadedMixin)
    for model in (Notebook, ChildNotebook):
        assert model.__mro__.count(NotesMixin) == 1
        assert "notes" not in model.model_fields
        assert model.__protected_fields__ == {"user_owner", "locked"}
        for action, parent in (("NOTE", "update"), ("NOTES", "read")):
            assert model.__access__[action].to_dict() == (
                model.__access__[parent].to_dict()
            )
        schema = model.schema()
        assert "notes" not in schema["properties"]
        for action, parameters in (("NOTE", {"message"}), ("NOTES", set())):
            method = schema["methods"][action]
            assert set(method["parameters"]) == parameters
            assert method["methods"] == ["POST"]
            assert method["requires_instance"]
    assert Notebook.__access__["*"].to_dict() == NEVER.to_dict()
    # 1. Subclass rules replace inherited action mappings, not parent rules.
    child = ChildNotebook.create(ChildNotebook())
    record = child.NOTE("child note", OTHER)
    assert [row.id for row in child.NOTES(WRITER)] == [record.id]
    with pytest.raises(MethodError) as caught:
        child.NOTE("not a reader", WRITER)
    assert caught.value.status_code == 403
    with pytest.raises(MethodError) as caught:
        child.NOTES(OTHER)
    assert caught.value.status_code == 403


def test_direct_notes_use_only_current_parent_permission(notes_runtime):
    """Writers need update only; permitted readers share all host notes."""
    # 0. Append without read permission or a parent-row mutation.
    owner = Notebook.create(Notebook())
    before = Notebook.get(owner.id).model_dump()
    record = owner.NOTE("shared note", WRITER)
    assert isinstance(record, TTX)
    assert record.name == "NOTE" and record.target == _ref(owner)
    assert record.source == "users/1" and record.user_owner == 1
    assert record.value == "shared note"
    assert Notebook.get(owner.id).model_dump() == before
    # 1. Appender ownership is not a separate read grant or restriction.
    for reader in (OTHER, ADMIN):
        assert [row.id for row in owner.NOTES(reader)] == [record.id]
    with pytest.raises(MethodError) as caught:
        owner.NOTES(WRITER)
    assert caught.value.status_code == 403
    with pytest.raises(MethodError) as caught:
        owner.NOTE("reader cannot write", OTHER)
    assert caught.value.status_code == 403
    assert len(TTX.list()) == 1
    # 2. Notes add neither a host column nor a Thread table.
    with TTX.storage._connection() as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'",
        )}
        columns = {row[1] for row in connection.execute(
            'PRAGMA table_info("notes_examples")',
        )}
    assert "threads" not in tables and "notes" not in columns


@pytest.mark.parametrize("base", ["Notebook", "notes_examples"])
def test_http_message_injection_and_raw_record_response(notes_runtime, base):
    """Generated mirrors inject callers and serialize native TTX results."""
    # 0. Body identities cannot replace the authenticated writer or reader.
    _, client = notes_runtime
    owner = Notebook.create(Notebook())
    path = f"/{base}/{owner.id}"
    response = client.post(
        path + "/NOTE", headers=_headers(WRITER),
        json={"message": "123", "user": ADMIN},
    )
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["data"] == {"payload": 123}
    assert saved["target"] == _ref(owner)
    assert saved["source"] == "users/1" and saved["user_owner"] == 1
    # 1. NOTES returns records, not a projected or paginated envelope.
    response = client.post(
        path + "/NOTES", headers=_headers(OTHER), json={"user": WRITER},
    )
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()] == [saved["id"]]
    assert response.json()[0]["data"] == {"payload": 123}
    for action, body, headers in (
        ("NOTE", {"message": "denied", "user": WRITER}, _headers(OTHER)),
        ("NOTES", {"user": ADMIN}, _headers(WRITER)),
        ("NOTE", {"message": "anonymous", "user": WRITER}, {}),
        ("NOTES", {"user": ADMIN}, {}),
    ):
        denied = client.post(path + "/" + action, headers=headers, json=body)
        assert denied.status_code == 403, denied.text
    assert len(TTX.list()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("instance_target", [False, True])
async def test_routed_note_preserves_envelope_once(
    notes_runtime, instance_target,
):
    """Store incoming identity once with canonical host membership."""
    # 0. Route a trusted caller separately from the recordable message.
    root, _ = notes_runtime
    owner = Notebook.create(Notebook())
    target = Notebook.__addr__
    data = {"id": owner.id, "message": "null"}
    if instance_target:
        owner._addr = "pinned_notes_owner"
        root.register(owner)
        target = owner.addr
        data.pop("id")
    tx = TX(
        "NOTE", "original_sender", target, data=data,
        meta={"user": WRITER, "token": "synthetic-secret"},
        timestamp=1234.5, uuid="original-note-uuid",
    )
    original = deepcopy(tx)
    sent = []

    def observe(response):
        """Count only responses correlated to the incoming request."""
        if response.meta.get("req") == tx.uuid:
            sent.append(response)
        return response
    # 1. Acknowledge once without mutating or replaying the source TX.
    Notebook.use(observe, on="send")
    reply = await root.request(tx, timeout=2)
    assert not reply.is_error and reply.meta["req"] == tx.uuid
    assert len(sent) == 1 and tx == original
    records = owner.NOTES(OTHER)
    assert len(records) == 1
    record = records[0]
    assert (record.uuid, record.source, record.timestamp) == (
        original.uuid, original.source, original.timestamp,
    )
    assert record.target == _ref(owner) and record.user_owner == 1
    assert record.data == {"payload": None} and record.meta == {}
    assert reply.data["id"] == record.id
    read = await root.request(TX(
        "NOTES", "reader", Notebook.__addr__, data={"id": owner.id},
        meta={"user": OTHER},
    ), timeout=2)
    assert not read.is_error
    assert [row["id"] for row in read.data] == [record.id]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [
    "missing_user", "body_user", "missing_id", "conflicting_id",
    "old_content", "extra_read_argument", "reader_write",
])
async def test_routed_spoof_and_redirect_rejected_without_writes(
    notes_runtime, case,
):
    """Reject routed host redirection and manufactured caller authority."""
    # 0. Prepare invalid ingress with real host storage and caller rules.
    root, _ = notes_runtime
    owner = Notebook.create(Notebook())
    target = Notebook.__addr__
    action = "NOTE"
    data = {"id": owner.id, "message": "must not save"}
    user = WRITER
    if case == "missing_user":
        user = None
    elif case == "body_user":
        data["user"] = ADMIN
    elif case == "missing_id":
        data.pop("id")
    elif case == "conflicting_id":
        owner._addr = "fixed_notes_owner"
        root.register(owner)
        target = owner.addr
        data["id"] = owner.id + 1
    elif case == "old_content":
        data = {"id": owner.id, "content": "retired argument"}
    elif case == "extra_read_argument":
        action, user = "NOTES", OTHER
        data = {"id": owner.id, "limit": 10}
    else:
        user = OTHER
    # 1. Reject rather than recording a claimed caller or redirected payload.
    reply = await root.request(TX(
        action, "sender", target, data=data, meta={"user": user},
    ), timeout=2)
    assert reply.is_error
    if case in {"missing_user", "reader_write"}:
        assert reply.data["code"] == 403
    assert TTX.list() == []


def test_stale_parent_authorization_and_missing_host(
    notes_runtime, monkeypatch,
):
    """Refetch hosts before authorization and reject deleted parents."""
    # 0. Revoke the stale instance's write ownership in persisted host state.
    owner = Notebook.create(Notebook())
    owner.NOTE("retained", WRITER)
    Notebook.update(owner.id, {"user_owner": 99})
    with pytest.raises(MethodError) as caught:
        owner.NOTE("stale write", WRITER)
    assert caught.value.status_code == 403
    with monkeypatch.context() as patch:
        patch.setattr(Notebook, "__access__", {
            **Notebook.__access__, "read": NEVER,
        })
        with pytest.raises(MethodError) as caught:
            owner.NOTES(OTHER)
        assert caught.value.status_code == 403
    assert len(TTX.list()) == 1
    # 1. A stale instance cannot append or read after host deletion.
    Notebook.delete(owner.id)
    for operation in (
        lambda: owner.NOTE("orphan write", WRITER),
        lambda: owner.NOTES(OTHER),
    ):
        with pytest.raises(MethodError) as caught:
            operation()
        assert caught.value.status_code == 404
    assert len(TTX.list()) == 1


def test_entries_filter_target_and_name_in_timestamp_order(notes_runtime):
    """Select all host NOTE rows in TX-time order without unrelated entries."""
    # 0. Make insertion order disagree with time and include unrelated rows.
    owner = Notebook.create(Notebook())
    other = Notebook.create(Notebook(title="Other host"))
    for host, name, message, timestamp in (
        (owner, "NOTE", "late", 30.0),
        (other, "NOTE", "foreign", 5.0),
        (owner, "OTHER", "not a note", 8.0),
        (owner, "NOTE", "early", 10.0),
        (owner, "NOTE", "middle", 20.0),
    ):
        host._append_entry(TX(
            name, "synthetic", _ref(host), data=message,
            timestamp=timestamp,
            meta={"user": ADMIN, "token": "secret", "seq": 1},
        ), user=WRITER)
    # 1. Shared helpers retain native normalization and trusted attribution.
    records = owner._entries(name="NOTE", user=OTHER)
    assert [row.value for row in records] == ["early", "middle", "late"]
    assert [row.id for row in owner.NOTES(ADMIN)] == [
        row.id for row in records
    ]
    assert all(row.target == _ref(owner) for row in records)
    assert all(row.user_owner == 1 for row in records)
    assert all(row.meta == {"seq": 1} for row in records)


def test_notes_read_is_not_a_default_page(notes_runtime):
    """Return every matching entry rather than truncating at a page boundary."""
    # 0. Store more notes than the retired fifty-record default page.
    owner = Notebook.create(Notebook())
    for index in range(51):
        owner._append_entry(TX(
            "NOTE", "synthetic", _ref(owner), data=f"note {index}",
            timestamp=float(index),
        ), user=WRITER)
    # 1. The reader returns the complete timestamp-ordered list.
    assert [row.value for row in owner.NOTES(OTHER)] == [
        f"note {index}" for index in range(51)
    ]


@pytest.mark.parametrize("message,expected", [
    ("123", 123), ("null", None), ("plain text", "plain text"),
    ("x" * 16000, "x" * 16000),
])
def test_note_raw_serialization(notes_runtime, message, expected):
    """Validate plain input before native one-time JSON normalization."""
    # 0. Persist the message through Notes, not a test serializer.
    owner = Notebook.create(Notebook())
    record = owner.NOTE(message, WRITER)
    # 1. The wrapper stores normalized raw data, not content DTOs.
    assert record.data == {"payload": expected}
    assert owner.NOTES(OTHER)[0].value == expected


def test_note_reference_stays_unhydrated(notes_runtime, monkeypatch):
    """Native-looking message URLs stay pointers without fetching entities."""

    def forbidden(*args, **kwargs):
        """Fail if Notes attempts explicit reference hydration."""
        pytest.fail("Notes must not hydrate message references")
    # 0. Use an unavailable entity URL to distinguish pointers from hydration.
    monkeypatch.setattr(Ref, "hydrate", forbidden)
    owner = Notebook.create(Notebook())
    reference = "https://notes.example.test/Notebook/987654"
    record = owner.NOTE(reference, WRITER)
    # 1. Lazy reference recognition never resolves its target.
    assert isinstance(record.value, Ref)
    assert str(owner.NOTES(OTHER)[0].value) == reference


@pytest.mark.parametrize("payload", [
    "'); DROP TABLE notes_examples; DROP TABLE tx_records; --",
    {
        "nested": [
            "'); DROP TABLE tx_records; --",
            {"query": "' OR 1=1 --"},
        ],
        "target": "https://notes.example.test/Notebook/999",
        "name": "OTHER", "id": 999,
    },
])
def test_sql_injection_messages_remain_bound_data(
    notes_runtime, payload,
):
    """Preserve SQL-shaped text and parsed JSON as literal native data."""
    # 0. Save unrelated host/name rows and snapshot the disposable table set.
    _, client = notes_runtime
    owner = Notebook.create(Notebook())
    other = Notebook.create(Notebook(title="Unrelated host"))
    sentinel = other.NOTE("unrelated note", WRITER)
    unrelated = owner._append_entry(TX(
        "OTHER", "synthetic", _ref(other), data="unrelated entry",
    ), user=WRITER)
    before = [row.model_dump() for row in Notebook.list()]
    with TTX.storage._connection() as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
        ).fetchall()
    message = payload if isinstance(payload, str) else json.dumps(payload)
    path = f"/Notebook/{owner.id}"
    # 1. Native generated routes preserve literal SQL-shaped payload values.
    response = client.post(
        path + "/NOTE", headers=_headers(WRITER), json={"message": message},
    )
    assert response.status_code == 200, response.text
    saved = json.loads(response.content)
    assert saved["data"] == {"payload": payload}
    assert saved["target"] == _ref(owner) and saved["name"] == "NOTE"
    page = client.post(path + "/NOTES", headers=_headers(OTHER), json={})
    assert page.status_code == 200, page.text
    assert [row["id"] for row in json.loads(page.content)] == [saved["id"]]
    assert json.loads(page.content)[0]["data"] == {"payload": payload}
    # 2. Bound native writes preserve literals, tables and unrelated records.
    with TTX.storage._connection() as connection:
        row = connection.execute(
            "SELECT data, target, name FROM tx_records WHERE id = ?",
            [saved["id"]],
        ).fetchone()
        remaining = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
        ).fetchall()
    assert json.loads(row[0]) == {"payload": payload}
    assert row[1:] == (_ref(owner), "NOTE")
    assert remaining == tables
    assert [row.model_dump() for row in Notebook.list()] == before
    assert TTX.get(sentinel.id).value == "unrelated note"
    assert TTX.get(unrelated.id).value == "unrelated entry"
    assert TTX.get(unrelated.id).target == _ref(owner)
    assert [row.id for row in other.NOTES(OTHER)] == [sentinel.id]
    assert owner._entries(name="NOTE' OR 1=1 --", user=OTHER) == []


@pytest.mark.parametrize("message", [None, 123, {}, "", " \n\t"])
def test_invalid_note_input_never_writes(notes_runtime, message):
    """Reject nontext or blank direct inputs without changing storage."""
    # 0. Direct Python calls must not stringify invalid message inputs.
    owner = Notebook.create(Notebook())
    with pytest.raises(MethodError) as caught:
        owner.NOTE(message, WRITER)
    assert caught.value.status_code == 400
    # 1. Invalid content leaves neither a note nor a parent mutation.
    assert TTX.list() == []
    assert Notebook.get(owner.id).title == owner.title


@pytest.mark.parametrize("message", ["", " \n\t"])
def test_http_blank_note_returns_400_without_mutation(notes_runtime, message):
    """Reject blank HTTP messages without changing host or entry storage."""
    # 0. Snapshot the actual host before an authenticated invalid request.
    _, client = notes_runtime
    owner = Notebook.create(Notebook())
    before = Notebook.get(owner.id).model_dump()
    # 1. Use the real action route with normal server-exception propagation.
    response = client.post(
        f"/Notebook/{owner.id}/NOTE", headers=_headers(WRITER),
        json={"message": message},
    )
    # 2. Invalid client input is a 400 and cannot mutate either storage model.
    assert response.status_code == 400, response.text
    assert TTX.list() == []
    assert Notebook.get(owner.id).model_dump() == before


def test_oversized_and_anonymous_direct_calls_fail_closed(notes_runtime):
    """Retain message bounds and treat None as anonymous, never internal."""
    # 0. Reject oversize input and absent caller authority independently.
    owner = Notebook.create(Notebook())
    with pytest.raises(MethodError) as caught:
        owner.NOTE("x" * 16001, WRITER)
    assert caught.value.status_code == 413
    for operation in (
        lambda: owner.NOTE("anonymous", None),
        lambda: owner.NOTES(None),
        lambda: owner._append_entry(
            TX("NOTE", "sender", _ref(owner), data="anonymous"), user=None,
        ),
        lambda: owner._entries(name="NOTE", user=None),
    ):
        with pytest.raises(MethodError) as caught:
            operation()
        assert caught.value.status_code == 403
    # 1. Rejected operations allocate no snapshots.
    assert TTX.list() == []


@pytest.mark.asyncio
async def test_other_native_actions_delegate_without_recording(notes_runtime):
    """Preserve native CRUD dispatch without capturing unrelated actions."""
    # 0. Exercise get and update through independently permitted callers.
    root, _ = notes_runtime
    owner = Notebook.create(Notebook())
    for action, values, user in (
        ("get", {"id": owner.id}, OTHER),
        ("update", {"id": owner.id, "title": "changed"}, WRITER),
    ):
        reply = await root.request(TX(
            action, root.addr, Notebook.__addr__, data=values,
            meta={"user": user},
        ), timeout=2)
        assert not reply.is_error, reply.data
    # 1. Ordinary host mutations produce no Notes or execution snapshots.
    assert Notebook.get(owner.id).title == "changed"
    assert TTX.list() == []


# Changelog (Python has no native block-comment syntax).
# - 2026-11-04: Replace Thread notes with host-authorized TTX integration;
#   cover native HTTP/Matrix callers, raw values and timestamp selection.
#   Preserve SQL injection strings/nested JSON as native bound SQLite data.
#   Require HTTP 400 for blank messages and direct invalid-input errors,
#   with no host changes or TTX inserts.
# - 2026-11-02: Move generic Notes HTTP/TX coverage out of agents;
#   retain independent guards and require exactly-once flag injection.
# - 2026-10-31: Cover flag-based notes fields, HTTP/tool/raw caller boundaries,
#   native action policies, immutable snapshots and transaction-time revocation.
#   - Use notes-only native bootstrap without fixture policy replacements.
#   - Replace Thread grants with inherited scope policy; retain transport-only
#     Notes caller expiry and preflight notes-pointer integrity checks.
# - 2026-10-31: Align with approved native owner/admin Notes cleanup.
#   - Retire removed caller-capability expiry, UUID pinning, scope-inherited
#     access and transactional pointer/source checks; scope is metadata only.
#   - Retain named HTTP caller injection, native raw caller metadata, snapshot
#     conversion, protected notes fields and parent/action/Thread permissions.
