"""Exercise trusted TTX child append and immediate timestamp-page reads."""

from copy import deepcopy
from queue import Empty

import pytest
from pydantic import ValidationError

from n3tx_actors.tx import TX
from n3tx_core.authorize import AccessContext, DefaultResolver
from n3tx_core.authorize.errors import AccessDenied
from n3tx_core.models.ref import public_id_url
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.decorators import exposed_method_info
from n3tx_core.utils.registrar import register_model
from n3tx_threads import TTX


pytestmark = pytest.mark.unit
EXTERNAL_TARGET = "https://synthetic.example.test/Notebook/17"


@pytest.fixture
def native_ttx(tmp_path, monkeypatch):
    """Register only TTX against disposable native file-backed SQLite."""
    # 0. Preserve the shared model binding without replacing native behavior.
    monkeypatch.setattr(TTX, "storage", TTX.storage)
    storage = SQLiteStorage(str(tmp_path / "ttx.sqlite3"))
    try:
        register_model(TTX, storage=storage)
        yield storage
    finally:
        # 1. Release only connections belonging to this disposable database.
        while True:
            try:
                connection = storage._pool.get_nowait()
            except Empty:
                break
            connection.rollback()
            connection.close()


def _tx(value, *, timestamp=100.0):
    """Build a synthetic envelope with an unrelated external destination."""
    return TX(
        "Message", "synthetic-sender", EXTERNAL_TARGET,
        data=value, timestamp=timestamp, uuid="synthetic-message-uuid",
    )


def _parent():
    """Persist a parent snapshot with an explicit synthetic owner."""
    return TTX.create(TTX(_tx({"parent": True}), user_owner=11))


def _ref(record):
    """Return the canonical native identity of a TTX record."""
    return public_id_url(record.id, target_cls=TTX)


def test_append_binds_child_without_changing_envelope_or_parent(native_ttx):
    """Copy the envelope while binding its snapshot to the saved parent."""
    # 0. Keep caller metadata distinct from explicit trusted attribution.
    parent = _parent()
    parent_before = deepcopy(parent.model_dump())
    tx = _tx({"nested": [{"value": 1}]}, timestamp=123.5)
    tx.meta = {
        "user": {"user_id": 99}, "token": "synthetic-not-a-credential",
        "req": "request-id", "seq": 2, "stream": True,
        "stream_end": False, "error": False,
    }
    original = deepcopy(tx)
    # 1. Append through the real constructor and native create path.
    child = parent.APPEND(tx, user_owner=23)
    assert tx == original
    assert child.target == _ref(parent)
    assert (child.name, child.source, child.uuid, child.timestamp) == (
        original.name, original.source, original.uuid, original.timestamp,
    )
    assert child.user_owner == 23
    assert child.meta == {
        "req": "request-id", "seq": 2, "stream": True,
        "stream_end": False, "error": False,
    }
    # 2. Input, returned values and parent state remain independent snapshots.
    tx.data["nested"][0]["value"] = 2
    value = child.value
    value["nested"][0]["value"] = 3
    assert child.value == {"nested": [{"value": 1}]}
    fetched = TTX.get(child.id)
    assert fetched.data == {"payload": {"nested": [{"value": 1}]}}
    assert fetched.user_owner == 23
    assert fetched.source == original.source and fetched.uuid == original.uuid
    assert parent.model_dump() == parent_before
    assert TTX.get(parent.id).model_dump() == parent_before


@pytest.mark.parametrize("owner", [None, 7])
def test_append_parses_once_and_round_trips_optional_integer_owner(
    native_ttx, owner,
):
    """Preserve quoted JSON text without inheriting untrusted attribution."""
    # 0. A parsed JSON string must not become a number on reconstruction.
    parent = _parent()
    tx = _tx('"123"')
    tx.meta = {"user": {"user_id": 99}}
    # 1. Exercise both default attribution and explicit integer attribution.
    child = (
        parent.APPEND(tx) if owner is None
        else parent.APPEND(tx, user_owner=owner)
    )
    fetched = TTX.get(child.id)
    assert fetched.user_owner == owner
    assert fetched.data == {"payload": "123"}
    assert fetched.value == "123"
    assert TTX(**fetched.model_dump()).value == "123"
    assert parent.threads()["data"][0].value == "123"


def test_threads_selects_immediate_children_not_descendants(native_ttx):
    """Canonical target membership selects one level without flattening."""
    # 0. Build two roots and a child that itself owns a grandchild.
    parent = _parent()
    unrelated = _parent()
    child = parent.APPEND(_tx("child"))
    grandchild = child.APPEND(_tx("grandchild"))
    other_child = unrelated.APPEND(_tx("unrelated"))
    # 1. Each parent selects only its own immediate incoming targets.
    page = parent.threads()
    assert [row.id for row in page["data"]] == [child.id]
    assert page["cursor"] is None and page["has_more"] is False
    assert child.target == _ref(parent)
    assert grandchild.target == _ref(child)
    assert other_child.target == _ref(unrelated)
    assert [row.id for row in child.threads()["data"]] == [grandchild.id]
    assert [row.id for row in unrelated.threads()["data"]] == [other_child.id]
    assert grandchild.threads() == {
        "data": [], "cursor": None, "has_more": False,
    }


def test_threads_orders_by_tx_timestamp_and_uses_exclusive_cursor(native_ttx):
    """Page timestamps rather than IDs with a terminal null cursor."""
    # 0. Make insertion IDs disagree with the requested timestamp ordering.
    parent = _parent()
    children = [
        parent.APPEND(_tx(str(stamp), timestamp=stamp))
        for stamp in (20.5, 40.5, 10.5, 30.5)
    ]
    # 1. A latest page continues strictly before its last timestamp.
    page = parent.threads(limit=2)
    assert set(page) == {"data", "cursor", "has_more"}
    assert [row.timestamp for row in page["data"]] == [40.5, 30.5]
    assert [row.id for row in page["data"]] == [
        children[1].id, children[3].id,
    ]
    assert page["cursor"] == 30.5 and page["has_more"] is True
    older = parent.threads(cursor=page["cursor"], limit=2)
    assert [row.timestamp for row in older["data"]] == [20.5, 10.5]
    assert older["cursor"] is None and older["has_more"] is False
    # 2. Integer cursors work, and polling is not a consuming operation.
    assert parent.threads(cursor=20)["data"][0].timestamp == 10.5
    assert [row.id for row in parent.threads(limit=2)["data"]] == [
        row.id for row in page["data"]
    ]


def test_timestamp_ties_can_be_omitted_at_page_boundary(native_ttx):
    """Do not infer an ID continuation or a particular order within ties."""
    # 0. Two equal timestamps straddle a one-record page boundary.
    parent = _parent()
    tied = [parent.APPEND(_tx(value, timestamp=50)) for value in (1, 2)]
    oldest = parent.APPEND(_tx("older", timestamp=10))
    # 1. Either tied row may be first; continuation excludes both tied rows.
    page = parent.threads(limit=1)
    assert len(page["data"]) == 1
    assert page["data"][0].id in {row.id for row in tied}
    assert page["cursor"] == 50 and page["has_more"] is True
    older = parent.threads(cursor=page["cursor"], limit=10)
    assert [row.id for row in older["data"]] == [oldest.id]
    assert older["cursor"] is None and older["has_more"] is False


def test_duplicate_envelopes_append_distinct_rows(native_ttx):
    """Repeated UUIDs remain inserts without an exactly-once guarantee."""
    # 0. Reuse the exact same mutable envelope in sequential appends.
    parent = _parent()
    tx = _tx({"repeat": True})
    first = parent.APPEND(tx)
    second = parent.APPEND(tx)
    # 1. Both rows survive without relying on equal-timestamp ordering.
    assert first.id != second.id
    assert first.uuid == second.uuid == tx.uuid
    assert {row.id for row in parent.threads()["data"]} == {
        first.id, second.id,
    }


@pytest.mark.parametrize("owner", [True, False, 0, -1, "7", 7.0])
def test_append_rejects_invalid_owner_without_writing(native_ttx, owner):
    """Attribution accepts positive strict integers or None only."""
    # 0. Retain the native persisted baseline before invalid attribution.
    parent = _parent()
    before = {row.id for row in TTX.list()}
    # 1. Constructor validation must precede creation of any child row.
    with pytest.raises(ValidationError):
        parent.APPEND(_tx("invalid owner"), user_owner=owner)
    assert {row.id for row in TTX.list()} == before


@pytest.mark.parametrize("value", [None, {}, "message", 1])
def test_append_requires_actual_tx_without_writing(native_ttx, value):
    """Reject non-TX values rather than coercing them into envelopes."""
    # 0. Save a valid parent independently of the invalid envelope input.
    parent = _parent()
    before = {row.id for row in TTX.list()}
    # 1. Invalid input must leave native storage unchanged.
    with pytest.raises(TypeError):
        parent.APPEND(value)
    assert {row.id for row in TTX.list()} == before


@pytest.mark.parametrize("state", [
    "unsaved", "negative", "missing", "deleted",
])
def test_helpers_require_parent_still_persisted(native_ttx, state):
    """Both helpers reject unsaved, fabricated and stale deleted parents."""
    # 0. Retain full envelope fields rather than triggering ID-only loading.
    if state == "deleted":
        parent = _parent()
        TTX.delete(parent.id)
    else:
        parent = TTX(_tx("not persisted"))
        parent.id = {"unsaved": 0, "negative": -1, "missing": 999}[state]
    before = {row.id for row in TTX.list()}
    # 1. Neither child insertion nor empty-page success may hide a stale root.
    with pytest.raises(ValueError):
        parent.APPEND(_tx("child"))
    with pytest.raises(ValueError):
        parent.threads()
    assert {row.id for row in TTX.list()} == before


@pytest.mark.parametrize("limit", [True, False, 0, -1, "2", 2.0, None])
def test_threads_rejects_invalid_limits(native_ttx, limit):
    """Page limits are positive integers and never booleans or coercions."""
    # 0. A valid parent isolates argument validation from existence checks.
    parent = _parent()
    # 1. Invalid reads cannot insert rows or return a misleading empty page.
    with pytest.raises(ValueError):
        parent.threads(limit=limit)
    assert len(TTX.list()) == 1


@pytest.mark.parametrize("cursor", [
    True, False, "100", [], {}, float("nan"),
    float("inf"), float("-inf"),
])
def test_threads_rejects_invalid_cursors(native_ttx, cursor):
    """Cursors are finite numeric timestamps, excluding booleans."""
    # 0. A valid parent isolates cursor validation from existence checks.
    parent = _parent()
    # 1. Invalid reads leave the parent as the only stored record.
    with pytest.raises(ValueError):
        parent.threads(cursor=cursor)
    assert len(TTX.list()) == 1


def test_helpers_do_not_expose_generic_transport_writes(native_ttx):
    """Trusted Python helpers do not become exposed HTTP model actions."""
    # 0. Keep the low-level deny policy separate from Python storage calls.
    assert exposed_method_info(TTX, "APPEND") is None
    assert exposed_method_info(TTX, "threads") is None
    # 1. Inspect the effective native deny rule without an ingress bypass.
    for action in ("create", "read", "list", "update", "delete"):
        with pytest.raises(AccessDenied):
            DefaultResolver().authorize(AccessContext(
                user={"user_id": 11, "role": "admin"},
                action=action, model_class=TTX,
            ))


# Changelog (Python has no block-comment syntax).
# - 2026-11-04: Cover trusted TTX child appends and immediate timestamp pages
#   with disposable native SQLite, strict attribution and no graph traversal.
