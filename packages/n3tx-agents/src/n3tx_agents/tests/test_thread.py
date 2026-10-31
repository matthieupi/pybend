"""Native Thread metadata, persistence and provider-free agent history."""

from datetime import datetime, timedelta, timezone
from queue import Empty

import pytest
from pydantic_ai import models
from pydantic_ai.messages import (
    ModelMessagesTypeAdapter, ModelRequest, ModelResponse, TextPart,
    ToolCallPart, ToolReturnPart, UserPromptPart,
)
from pydantic_ai.models.test import TestModel

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core import config
from n3tx_core.api.routes_fastapi import router
from n3tx_core.app import create_app
from n3tx_core.authorize import auth
from n3tx_core.authorize.errors import AccessDenied
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.ref import Ref, public_id_url
from n3tx_core.storage.sqlite_storage import SQLiteStorage

from n3tx_agents.thread import HISTORY_CODEC, Thread
from n3tx_agents.tx_record import TXRecord


pytestmark = pytest.mark.unit
USER = {"user_id": 1, "role": "user"}
ADMIN = {"user_id": 3, "role": "admin"}
OTHER = {"user_id": 2, "role": "staff"}


class SimpleAgent(ActorModel):
    """Minimal flag-enabled agent without business tools or providers."""

    __tablename__ = "simple_agents"
    __storable__ = False
    __agent__ = True
    name: str = "Test Agent"


def _ref(record):
    """Return the canonical URL of a saved synthetic record."""
    return public_id_url(record.id, target_cls=type(record))


def _payload(messages):
    """Use native serialization to compare complete protocol messages."""
    return ModelMessagesTypeAdapter.dump_python(messages, mode="json")


def _messages():
    """Build a complete synthetic request and text response."""
    return [
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(parts=[TextPart(content="hi there")]),
    ]


def _protocol_txs(messages):
    """Encode test messages using the same native serializer as the runtime."""
    return [
        TX(message["kind"], "test", "agent", data=message,
           meta={"codec": HISTORY_CODEC})
        for message in _payload(messages)
    ]


@pytest.fixture
def native(tmp_path, monkeypatch):
    """Use native bootstrap with real models and disposable storage."""
    # 0. Preserve process globals and disable all real provider requests.
    saved_routes = list(router.routes)
    saved_cache = dict(ProtoModel._schema_cache)
    saved_auth = (auth._jwt_secret, auth._jwt_expiry_hours)
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)
    monkeypatch.setattr(config, "DEBUG", False)
    for model in (Thread, TXRecord, SimpleAgent):
        monkeypatch.setattr(
            model, "storage", getattr(model, "storage", None), raising=False,
        )
    storage = SQLiteStorage(str(tmp_path / "threads.db"))
    try:
        create_app(
            models=[SimpleAgent], storage=storage, static_dir=None,
            jwt_secret="synthetic-thread-secret-not-for-production",
            debug=False, ssr="off", remotes={},
        )
        root = Matrix()
        Actor.root(root)
        for model in (Thread, TXRecord, SimpleAgent):
            root._children[model.__addr__] = model
        yield storage
    finally:
        # 1. Release only owned connections and restore native factory globals.
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


def test_thread_fields_defaults_and_policy(native):
    """Keep owner/scope metadata without persisted messages or routing."""
    # 0. Inspect fields collected by the actual native model.
    assert set(Thread.model_json_schema()["properties"]) == {
        "id", "image", "user_owner", "scope",
    }
    assert issubclass(Thread, ActorModel) and Thread.__storable__
    assert Thread.__tablename__ == "threads"
    assert not getattr(Thread, "__agent__", False)
    assert {"user_owner", "scope"} <= Thread.__protected_fields__
    assert {"create", "read", "list", "update", "delete"} <= (
        Thread.__access__.keys()
    )
    assert Thread().user_owner is None and Thread().scope is None


def test_owner_scope_round_trip_and_thread_delete(native):
    """Retain ordinary trusted Thread create/get/update/delete persistence."""
    # 0. Scope is an opaque Ref, not a source lookup or permission grant.
    scope = Ref("https://elsewhere.example/Task/42")
    thread = Thread.create(Thread(user_owner=1, scope=scope))
    fetched = Thread.get(thread.id)
    assert fetched.user_owner == 1 and fetched.scope == scope
    Thread.update(thread.id, {"scope": None})
    assert Thread.get(thread.id).scope is None
    # 1. Trusted Python CRUD retains the native delete contract.
    Thread.delete(thread.id)
    assert Thread.get(thread.id) is None


def test_from_tx_is_pure_deep_copy(native):
    """Snapshot conversion copies native JSON without saving or dispatching."""
    # 0. Convert a native envelope without server persistence stamps.
    thread = Thread.create(Thread(user_owner=1))
    tx = TX("NOTE", "original", "sink", data={"items": [{"value": 1}]})
    draft = TXRecord.from_tx(tx, thread=Ref[Thread](_ref(thread)))
    assert draft.id == 0 and draft.recorded_at is None
    assert draft.recorded_by is None and draft.uuid == tx.uuid
    assert draft.source == tx.source and draft.timestamp == tx.timestamp
    # 1. The copy is detached, and conversion alone creates no records.
    tx.data["items"][0]["value"] = 2
    assert draft.data == {"items": [{"value": 1}]}
    assert thread.records(user=USER)["data"] == []


def test_append_many_persists_links_and_accepts_duplicate_uuids(native):
    """Append ordinary rows sequentially without dispatch or retry dedup."""
    # 0. Persist a batch, then append the same envelopes as another batch.
    thread = Thread.create(Thread(user_owner=1))
    txs = [TX("NOTE", "test", "sink", data={"n": n}) for n in (1, 2)]
    first = thread.append_many(txs, user=USER)
    repeated = thread.append_many(txs, user=USER)
    assert [row.uuid for row in repeated] == [row.uuid for row in first]
    assert set(row.id for row in first).isdisjoint(
        row.id for row in repeated
    )
    assert first[0].predecessor is None
    assert first[1].predecessor == _ref(first[0])
    assert all(row.recorded_by == 1 for row in first)
    assert all(row.recorded_at is not None for row in first)
    # 1. An explicit predecessor remains reference metadata for the batch.
    linked = thread.append_many(
        [TX("NOTE", "test", "sink")], user=USER,
        predecessor=_ref(first[-1]),
    )
    assert linked[0].predecessor == _ref(first[-1])
    assert len(thread.records(user=USER)["data"]) == 5


@pytest.mark.parametrize("scope", [None, "https://elsewhere.example/Task/42"])
def test_owner_admin_policy_not_scope_inheritance(native, scope):
    """Owner/admin access is independent of scope and source permissions."""
    # 0. An owner and an admin can append/read the same saved Thread.
    thread = Thread.create(Thread(user_owner=1, scope=scope))
    thread.append(TX("NOTE", "owner", "sink"), user=USER)
    saved = thread.append(TX("NOTE", "admin", "sink"), user=ADMIN)
    assert saved.recorded_by == ADMIN["user_id"]
    assert len(thread.records(user=ADMIN)["data"]) == 2
    assert thread.history(user=ADMIN, codec=HISTORY_CODEC) == []
    # 1. Another staff caller has no access through a matching scope alone.
    for operation in (
        lambda: thread.records(user=OTHER),
        lambda: thread.history(user=OTHER),
        lambda: thread.append(TX("NOTE", "other", "sink"), user=OTHER),
    ):
        with pytest.raises(AccessDenied):
            operation()


def test_explicit_none_is_trusted_internal_python(native):
    """Native internal None bypass is separate from authenticated transport."""
    # 0. Internal Python calls need no caller provenance stamp.
    thread = Thread.create(Thread(user_owner=1))
    saved = thread.append(TX("NOTE", "internal", "sink"), user=None)
    assert saved.recorded_by is None
    assert thread.records(user=None)["data"][0].id == saved.id
    assert thread.history(user=None) == []
    # 1. An anonymous transport-shaped dictionary is not internal None.
    with pytest.raises(AccessDenied):
        thread.records(user={})


def test_history_native_codec_round_trip_and_timestamp_order(native):
    """Restore complete protocol messages and exclude nonprotocol records."""
    # 0. Save protocol out of insertion order with distinct server timestamps.
    thread = Thread.create(Thread(user_owner=1))
    messages = _messages() + [
        ModelResponse(parts=[ToolCallPart(
            "lookup", {"key": "synthetic"}, tool_call_id="paired-call",
        )]),
        ModelRequest(parts=[ToolReturnPart(
            "lookup", {"found": True}, tool_call_id="paired-call",
        )]),
    ]
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for index in reversed(range(len(messages))):
        saved = thread.append(_protocol_txs([messages[index]])[0], user=USER)
        TXRecord.update(saved.id, {"recorded_at": base + timedelta(
            seconds=index,
        )})
    thread.append(TX("activity", "host", "sink"), user=USER)
    # 1. Native serialization agrees on prompts, text and paired tool IDs.
    assert _payload(thread.history(user=USER)) == _payload(messages)


def test_timestamp_cursor_and_latest_window(native):
    """Page distinct timestamps and replace the latest bounded window."""
    # 0. Deliberately make insertion IDs disagree with timestamp ordering.
    thread = Thread.create(Thread(user_owner=1))
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for second in (2, 0, 1):
        record = thread.append(TX(
            "NOTE", "test", "sink", data={"second": second},
        ), user=USER)
        TXRecord.update(record.id, {"recorded_at": base + timedelta(
            seconds=second,
        )})
    # 1. The cursor is a timestamp, without a high-water or ID continuation.
    page = thread.records(user=USER, limit=2)
    assert [row.data["second"] for row in page["data"]] == [2, 1]
    assert set(page) == {"data", "cursor", "has_more"}
    assert datetime.fromisoformat(page["cursor"]) == base + timedelta(seconds=1)
    older = thread.records(user=USER, cursor=page["cursor"], limit=2)
    assert [row.data["second"] for row in older["data"]] == [0]
    assert older["cursor"] == "" and older["has_more"] is False
    latest = thread.records(user=USER, limit=2)
    assert [row.data["second"] for row in latest["data"]] == [2, 1]
    assert latest["cursor"] == page["cursor"]
    assert latest["has_more"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("caller", [USER, None])
async def test_native_turns_create_resume_and_persist(native, stream, caller):
    """Both adapters create and reuse record-backed native conversations."""
    # 0. Run the real mixin/runtime twice using only the native TestModel.
    agent = SimpleAgent(addr="simple_agents/1")
    thread_id = None
    counts = []
    for task in ("Question 1", "Question 2"):
        kwargs = dict(
            task=task, prompt="Synthetic instructions", tools=[],
            llm=TestModel(call_tools=[]), user=caller, thread_id=thread_id,
        )
        if stream:
            chunks = [chunk async for chunk in agent.run_stream(**kwargs)]
            assert not [c for c in chunks if c["name"] == "error"]
            done = [c for c in chunks if c["name"] == "done"]
            assert len(done) == 1
            result = done[0]["data"]
        else:
            result = await agent.run(**kwargs)
            assert result["message_count"] == len(result["messages"])
        # 1. Verify exact identity and the persisted native message contents.
        if thread_id is not None:
            assert result["thread_id"] == thread_id
        thread_id = result["thread_id"]
        thread = Thread.get(thread_id)
        assert thread.user_owner == (1 if caller is not None else None)
        assert thread.scope is None
        history = thread.history(user=caller)
        counts.append(len(history))
        if not stream:
            assert _payload(history) == _payload(result["messages"])
    assert counts[0] > 0 and counts[1] > counts[0]


@pytest.mark.asyncio
async def test_agentic_passes_existing_thread_id(native):
    """Class-level agentic forwards the existing native Thread ID."""
    # 0. Exercise actual policy assembly, preparation and execution.
    thread = Thread.create(Thread(user_owner=1))
    result = await SimpleAgent.agentic(
        task="Hello", tools=[], llm=TestModel(call_tools=[]),
        thread_id=thread.id, user=USER,
    )
    # 1. The result and complete native persisted history agree.
    assert result["thread_id"] == thread.id
    assert _payload(thread.history(user=USER)) == _payload(result["messages"])


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["missing", "other_owner"])
async def test_agent_rejects_missing_or_denied_thread(native, case):
    """Preserve native Matrix missing-member and owner-denial failures."""
    # 0. Prepare an unavailable ID or an existing record owned by another user.
    thread = Thread.create(Thread(user_owner=2))
    with pytest.raises(RuntimeError, match="not found or access denied"):
        await SimpleAgent.agentic(
            task="Hello", tools=[], llm=TestModel(call_tools=[]), user=USER,
            thread_id=thread.id + 1000 if case == "missing" else thread.id,
        )


# Changelog (Python has no native block-comment syntax).
# - 2026-10-31: Replace obsolete mutable Thread assertions with scoped records,
#   strict disposable bootstrap, immutable append and native history coverage.
#   - Cover complete output overflow, successful transaction-policy connection
#     reuse and controlled parallel observation-failure interleavings.
#   - Replace Thread grant/expiry checks with uniform saved-source read/update
#     authorization, real transaction tracing and pre-inference revocation.
# - 2026-10-31: Align with approved minimalist owner/admin cleanup.
#   - Retire task-added schema guards, immutability/dedup/atomicity, basis and
#     branch/CAS, inherited scope ACL, grant expiry and observer-latch tests
#     because those mechanisms were explicitly removed by approved cleanup.
#   - Retain ordinary model/CRUD, conversion, append and native agent cases;
#     verify owner/admin policy and timestamp-only latest-window pagination.
