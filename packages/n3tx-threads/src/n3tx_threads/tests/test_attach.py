"""Protect generic ATTACH cloning through disposable native SQLite storage.

Only canonical TTX is registered. Direct Python ATTACH is trusted: these tests
cover persistence and local state, not HTTP authorization or delivery. Thread
entries never replace a Thread parent's latest preview, including None.
Snapshots detach without cloning descendants; later maintenance is unchanged.
No application, provider, credentials or project verification artifacts load."""

from copy import deepcopy
from queue import Empty
import sqlite3

import pytest
from pydantic import ValidationError

from n3tx_actors.tx import TX
from n3tx_core.models import proto_dump
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.erroring import MethodError
from n3tx_core.utils.registrar import register_model, registered_models
from n3tx_threads import Message, Note, Thread, TTX


@pytest.fixture
def attach_db(tmp_path):
    """Use runner-owned temporary storage and restore native state."""
    # 0. Preserve bindings and caches that native registration can populate.
    original_storage = TTX.storage
    registries = (
        registered_models, ProtoModel._schema_cache,
        proto_dump._schema_url_cache, proto_dump._instance_url_cache,
    )
    snapshots = [dict(registry) for registry in registries]
    database = tmp_path / "attach.sqlite3"
    storage = SQLiteStorage(database=str(database), pool_size=1)
    try:
        register_model(TTX, storage=storage)
        yield database
    finally:
        # 1. Release fixture-owned connections before pytest removes the files.
        while True:
            try:
                connection = storage._pool.get_nowait()
            except Empty:
                break
            connection.rollback()
            connection.close()
        TTX.storage = original_storage
        for registry, snapshot in zip(registries, snapshots):
            registry.clear()
            registry.update(snapshot)


def _draft(cls=TTX, **changes):
    """Build a synthetic raw or typed envelope with nested mutable evidence."""
    # 0. Keep envelope identity explicit for canonical and typed construction.
    values = {
        "uuid": "synthetic-attach-event", "timestamp": 123.75,
        "source": "users/2", "target": "synthetic/9",
        "data": {"opaque": {"items": [1, None]}},
        "meta": {
            "user": {"user_id": 99},
            "trace": {"items": ["synthetic-correlation"]},
        },
        "user_owner": 99, "archived": True, "status": "ASK",
    }
    if cls is TTX:
        values["name"] = "EVENT"
    elif cls in (Message, Note):
        values["desc"] = "  literal attachment  "
    values.update(changes)
    return cls(**values)


def _rows():
    """Read all canonical rows, including archives, as detached snapshots."""
    return {
        row.id: deepcopy(row.model_dump(mode="json"))
        for row in TTX.list(archived=True)
    }


def _insert_sequence(database):
    """Read the native sequence, including previously deleted committed rows."""
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = ?", ("ttx",),
        ).fetchone()
    return None if row is None else row[0]


def _assert_clone(saved, entry, parent, status):
    """Compare the complete persisted clone with its authoritative inputs."""
    # 0. Compare all fields, allowing only the contracted local changes.
    expected = entry.ttx().model_dump(mode="json")
    expected.update(
        id=saved.id, target=f"ttx/{parent.id}",
        user_owner=parent.user_owner, archived=False, status=status,
    )
    expected["meta"].pop("user", None)
    assert type(saved) is TTX
    assert saved.id > 0 and saved.id not in (entry.id, parent.id)
    assert saved.model_dump(mode="json") == expected
    assert TTX.get(saved.id).model_dump(mode="json") == expected


@pytest.mark.parametrize(
    "parent_cls,canonical,unknown,saved_entry,status,owner",
    [
        (TTX, True, False, False, "READ", 17),
        (TTX, True, True, True, "ASK", None),
        (Message, False, False, False, "UNREAD", 17),
        (Message, True, False, True, "ASK", 17),
        (Note, False, False, True, "READ", 17),
    ],
    ids=["raw", "unknown-ownerless", "message", "raw-message", "note"],
)
def test_nonthread_parent_is_unchanged(
    attach_db, parent_cls, canonical, unknown, saved_entry, status, owner,
):
    """Generic parents retain archive, status and exact data without latest."""
    # 0. Retain a stale parent while storage changes owner and opaque content.
    parent = parent_cls.create(_draft(
        parent_cls, archived=False, user_owner=1,
        **({"kind": "OpaqueAttachParent"} if unknown else {}),
    ))
    if canonical:
        parent = parent.ttx()
    TTX.update(parent.id, {
        "user_owner": owner, "archived": True, "status": "UNREAD",
        "data": {**parent.ttx().data, "fresh": {"revision": 2}},
    })
    fresh_parent = TTX.get(parent.id, archived=True)
    parent_input = deepcopy(parent.model_dump(mode="json"))
    entry = _draft(Message, status=status)
    if saved_entry:
        entry = Message.create(entry)
    entry_input = deepcopy(entry.model_dump(mode="json"))
    before = _rows()
    # 1. A single ATTACH inserts one clone without updating any existing row.
    saved = parent.ATTACH(entry)
    _assert_clone(saved, entry, fresh_parent, status)
    after = _rows()
    assert set(after) == set(before) | {saved.id}
    assert {key: after[key] for key in before} == before
    assert "latest" not in after[parent.id]["data"]
    assert parent.model_dump(mode="json") == parent_input
    assert entry.model_dump(mode="json") == entry_input
    # 2. Returned content and metadata detach from input and native persistence.
    saved.data["opaque"]["items"].append("returned-only")
    saved.meta["trace"]["items"].append("returned-only")
    entry.data["opaque"]["items"].append("input-only")
    assert _rows() == after
    assert entry.meta == entry_input["meta"]
    assert saved.data["opaque"]["items"] == [1, None, "returned-only"]


@pytest.mark.parametrize(
    "inbound,status,canonical",
    [
        (True, "READ", False), (True, "ASK", True),
        (False, "UNREAD", False), (False, "ASK", True),
    ],
    ids=["inbound-read", "inbound-ask", "outbound-unread", "outbound-ask"],
)
def test_thread_parent_retains_messaging_state(
    attach_db, inbound, status, canonical,
):
    """Thread parents reopen, cache clones and retain directional read rules."""
    # 0. Fresh storage, not the stale typed/canonical object, defines the owner.
    parent = Thread.create(_draft(
        Thread, target="users/1", user_owner=1, archived=False,
    ))
    if canonical:
        parent = parent.ttx()
    TTX.update(parent.id, {
        "target": "users/17", "user_owner": 17, "archived": True,
        "status": status,
        "data": {**parent.ttx().data, "fresh": {"revision": 2}},
    })
    fresh_parent = TTX.get(parent.id, archived=True)
    entry = TTX.create(_draft(
        kind="OpaqueAttachEntry", status="ASK",
        source="users/2" if inbound else "users/17",
    ))
    entry_input = deepcopy(entry.model_dump(mode="json"))
    parent_input = deepcopy(parent.model_dump(mode="json"))
    before = _rows()
    # 1. ATTACH changes only the new clone and the persisted Thread state.
    saved = parent.ATTACH(entry)
    _assert_clone(
        saved, entry, fresh_parent, "UNREAD" if inbound else "READ",
    )
    expected_parent = deepcopy(before[parent.id])
    expected_parent.update(
        archived=False, status="UNREAD" if inbound else status,
    )
    expected_parent["data"]["latest"] = saved.model_dump(mode="json")
    after = _rows()
    assert set(after) == set(before) | {saved.id}
    assert after[parent.id] == expected_parent
    assert after[entry.id] == before[entry.id]
    assert Thread.get(parent.id).latest.model_dump(mode="json") == after[
        saved.id
    ]
    assert entry.model_dump(mode="json") == entry_input
    assert parent.model_dump(mode="json") == parent_input
    # 2. Returned mutations cannot alter the cached snapshot or original row.
    saved.data["opaque"]["items"].append("returned-only")
    saved.meta["trace"]["items"].append("returned-only")
    assert _rows() == after
    assert entry.model_dump(mode="json") == entry_input


@pytest.mark.parametrize(
    "thread_parent,has_preview",
    [(True, True), (True, False), (False, False)],
    ids=["thread-keeps-preview", "thread-keeps-none", "generic-parent"],
)
def test_thread_entry_is_a_detached_supported_snapshot(
    attach_db, thread_parent, has_preview,
):
    """Attach Thread snapshots without replacing previews or cloning children.

    Existing and empty previews survive while nested content stays detached."""
    # 0. Seed a stored descendant and optional non-Thread parent preview.
    parent_cls = Thread if thread_parent else Message
    parent = parent_cls.create(_draft(
        parent_cls, target="users/17", user_owner=17,
    ))
    entry = _draft(Thread, latest=_draft(Message).ttx())
    if thread_parent:
        entry = Thread.create(entry)
        descendant = Message.create(_draft(
            Message, target=f"ttx/{entry.id}", archived=False,
            uuid="synthetic-nested-descendant",
        ))
        entry = Thread.update(entry.id, {"latest": descendant.ttx()})
    if has_preview:
        preview = Message.create(_draft(
            Message, target=f"ttx/{parent.id}", archived=False,
            uuid="synthetic-parent-preview",
        ))
        TTX.update(parent.id, {
            "data": {
                **parent.ttx().data,
                "latest": preview.ttx().model_dump(mode="json"),
            },
        })
    before_entry = deepcopy(entry.model_dump(mode="json"))
    before_parent = deepcopy(parent.model_dump(mode="json"))
    before = _rows()
    # 1. Clone exactly one row; Thread containers never become parent previews.
    saved = parent.ATTACH(entry)
    _assert_clone(
        saved, entry, parent, "UNREAD" if thread_parent else entry.status,
    )
    after = _rows()
    assert set(after) == set(before) | {saved.id}
    assert len(after) == len(before) + 1
    assert {key: after[key] for key in before if key != parent.id} == {
        key: value for key, value in before.items() if key != parent.id
    }
    assert entry.model_dump(mode="json") == before_entry
    assert parent.model_dump(mode="json") == before_parent
    if thread_parent:
        expected_parent = deepcopy(before[parent.id])
        expected_parent.update(archived=False, status="UNREAD")
        assert after[parent.id] == expected_parent
        loaded = Thread.get(parent.id)
        if has_preview:
            assert loaded.latest.model_dump(mode="json") == before[preview.id]
        else:
            assert loaded.latest is None
        assert after[descendant.id] == before[descendant.id]
        assert sum(
            row["uuid"] == descendant.uuid for row in after.values()
        ) == 1
    else:
        assert after[parent.id] == before[parent.id]
        assert "latest" not in after[parent.id]["data"]
    # 2. Both nested content and metadata are independent of the source object.
    saved.data["latest"]["data"]["opaque"]["items"].append("returned")
    saved.meta["trace"]["items"].append("returned")
    assert entry.model_dump(mode="json") == before_entry
    entry.latest.data["opaque"]["items"].append("input")
    assert _rows() == after
    assert saved.data["latest"]["data"]["opaque"]["items"] == [
        1, None, "returned",
    ]


@pytest.mark.parametrize(
    "invalid", ["unsaved-parent", "deleted-parent", "tx", "dict", "none"],
)
def test_invalid_attach_rejects_before_insert(attach_db, invalid):
    """Missing parents and non-TTX entries fail without any native insert."""
    # 0. Seed unrelated evidence that missing-parent rejection must preserve.
    TTX.create(_draft())
    parent = _draft(Thread)
    if invalid != "unsaved-parent":
        parent = Thread.create(parent)
    if invalid == "deleted-parent":
        TTX.delete(parent.id)
    entry = _draft(Message)
    if invalid == "tx":
        entry = TX("EVENT", "users/2", "synthetic/9", data={})
    elif invalid == "dict":
        entry = entry.model_dump()
    elif invalid == "none":
        entry = None
    before = _rows()
    sequence = _insert_sequence(attach_db)
    statements = []
    connection = TTX.storage._pool.get_nowait()
    connection.set_trace_callback(statements.append)
    TTX.storage._pool.put(connection)
    # 1. Public ATTACH rejects invalid inputs before a SQL insert can persist.
    try:
        with pytest.raises(MethodError):
            parent.ATTACH(entry)
    finally:
        connection.set_trace_callback(None)
    assert not any(
        statement.lstrip().upper().startswith("INSERT")
        for statement in statements
    )
    assert _rows() == before
    assert _insert_sequence(attach_db) == sequence


@pytest.mark.parametrize("timestamp", [float("nan"), float("inf")])
def test_nonfinite_entry_time_remains_model_validation(attach_db, timestamp):
    """Nonfinite envelope time is rejected by the native model before ATTACH."""
    # 0. The generic attach contract does not replace envelope validation.
    Thread.create(_draft(Thread))
    before = _rows()
    sequence = _insert_sequence(attach_db)
    with pytest.raises(ValidationError):
        _draft(Message, timestamp=timestamp)
    assert _rows() == before
    assert _insert_sequence(attach_db) == sequence


# Changelog (Python has no native block-comment syntax).
# - 2026-11-11:
#   - Cover generic ATTACH cloning, native persistence, fresh parents,
#     Thread-only state/cache effects, nested Thread snapshots and rejection.
#   - Preserve existing or empty previews on Thread entry attachment;
#     assert inbound reopen/read behavior and no descendant-row cloning.
#   - Use runner-controlled pytest temporary storage across runner identities.
#   - Seed previews as canonical TTX snapshots rather than typed Message dumps.
