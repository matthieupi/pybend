"""Protect trusted TTX history decoding without running an agent or provider.

Canonical SQLite rows carry complete SDK messages, not presentation summaries.
The caller owns authorization and business-scope binding before decoding; these
tests cover replay fidelity, root policy and corrupt evidence without providers.
User DM content remains separate from explicitly declared agent roots."""

from queue import Empty

import pytest
from pydantic import ValidationError
from pydantic_ai.messages import (
    ModelMessagesTypeAdapter, ModelRequest, ModelResponse, TextPart,
    ToolCallPart, ToolReturnPart, UserPromptPart,
)

from n3tx_actors import Actor, Matrix, TX
from n3tx_agents.agent import Agent
from n3tx_agents.history import HISTORY_CODEC
from n3tx_core.models import proto_dump
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.ref import public_id_url
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import register_model, registered_models
from n3tx_threads import Thread, TTX


@pytest.fixture
def history_db(tmp_path, monkeypatch):
    """Register only TTX and restore storage, lifecycle state and caches."""
    # 0. Existing agent conftest isolates actors; no Matrix is needed here.
    registries = (
        registered_models, ProtoModel._schema_cache,
        proto_dump._schema_url_cache, proto_dump._instance_url_cache,
    )
    snapshots = [dict(registry) for registry in registries]
    Actor.root(Matrix())
    monkeypatch.setattr(TTX, "storage", None)
    monkeypatch.setattr(TTX, "_subscribers", [])
    storage = SQLiteStorage(
        database=str(tmp_path / "ttx-history.sqlite3"), pool_size=1,
    )
    try:
        register_model(TTX, storage=storage)
        yield
    finally:
        # 1. Close disposable handles before restoring shared native bindings.
        while True:
            try:
                connection = storage._pool.get_nowait()
            except Empty:
                break
            connection.rollback()
            connection.close()
        for registry, snapshot in zip(registries, snapshots):
            registry.clear()
            registry.update(snapshot)


def _entry(payload, *, timestamp=100.0, codec=HISTORY_CODEC):
    """Pack a JSON-object payload into a canonical TX snapshot."""
    return TTX.from_tx(TX(
        "RETURN", "synthetic-agent", "unused-target", data=payload,
        meta={"codec": codec}, timestamp=timestamp,
    ))


def _rows():
    """Snapshot every canonical row, including archived evidence."""
    return [
        row.model_dump(mode="json")
        for row in TTX.list(archived=True, order_asc="id")
    ]


def test_history_round_trip_selects_complete_messages_in_id_order(history_db):
    """Replay complete protocol records for one exact owner in append order."""
    # 0. Construct a complete tool exchange using the installed SDK contracts.
    owner = Agent.create_history(Actor(addr="synthetic-agent"), user=None)
    other = TTX.create(_entry({}, codec=None))
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Read synthetic data")]),
        ModelResponse(
            parts=[
                TextPart(content="Checking"),
                ToolCallPart(
                    tool_name="lookup", args={"ids": [17, 29]},
                    tool_call_id="synthetic-call",
                ),
            ],
            model_name="synthetic-model", provider_name="synthetic-provider",
            provider_response_id="synthetic-response",
            metadata={"trace": {"items": ["original"]}},
        ),
        ModelRequest(parts=[ToolReturnPart(
            tool_name="lookup", tool_call_id="synthetic-call",
            content={"rows": [{"id": 17, "value": "123"}]},
        )]),
        ModelResponse(parts=[TextPart(content="Complete")]),
    ]
    payloads = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
    for index, payload in enumerate(payloads):
        record = owner.ATTACH(_entry(payload, timestamp=100.0 - index))
        if index == 0:
            TTX.update(record.id, {"archived": True})
    for name in ("RETURN", "NOTE"):
        audit = _entry({"audit": "not an SDK message"}, codec=None)
        audit.name = name
        owner.ATTACH(audit)
    owner.ATTACH(_entry({"audit": "different codec"}, codec="other/v1"))
    other.ATTACH(_entry(payloads[-1]))
    before = _rows()
    # 1. Insertion order wins over reversed TX timestamps and codec noise.
    history = Agent.chat_history(owner)
    assert ModelMessagesTypeAdapter.dump_python(
        history, mode="json",
    ) == payloads
    assert _rows() == before
    # 2. Decoded edits cannot rewrite SDK inputs or persisted replay evidence.
    history[1].parts[1].args["ids"].append(99)
    history[1].metadata["trace"]["items"].append("decoded-only")
    history[2].parts[0].content["rows"][0]["value"] = "decoded-only"
    assert ModelMessagesTypeAdapter.dump_python(
        messages, mode="json",
    ) == payloads
    assert _rows() == before
    assert ModelMessagesTypeAdapter.dump_python(
        Agent.chat_history(owner), mode="json",
    ) == payloads


def test_history_policy_reloads_owner_and_excludes_user_dms(history_db):
    """Keep nullable scope, fresh owner/admin access and strict DM isolation."""
    # 0. Nullable scope is explicit metadata, not inferred business ownership.
    user = {"user_id": 1, "role": "user"}
    admin = {"user_id": 3, "role": "admin"}
    other = {"user_id": 2, "role": "staff"}
    target = Actor(addr="synthetic-agent")
    owner = Agent.create_history(target, user=user)
    reference = public_id_url(owner.id, target_cls=TTX)
    assert owner.data == {"scope": None}
    assert owner.meta["agent_history"] is True
    assert Agent.get_history(reference, user=user).id == owner.id
    assert Agent.get_history(reference, user=admin).id == owner.id
    with pytest.raises(PermissionError):
        Agent.get_history(reference, user=other)
    # 1. Fresh policy sees ownership changes despite a stale Python view.
    TTX.update(owner.id, {"user_owner": 2, "archived": True})
    with pytest.raises(PermissionError):
        Agent.authorize_history(owner, user=user)
    assert Agent.get_history(reference, user=admin).archived
    retained = Agent.create_history(target, user=admin, scope=reference)
    TTX.delete(owner.id)
    assert Agent.authorize_history(retained, user=admin).data["scope"] == (
        reference
    )
    with pytest.raises(ValueError):
        Agent.get_history(reference, user=admin)
    # 2. Admin agent-history access never upgrades an ordinary User DM root.
    dm = Thread.create(Thread(source="users/2", target="users/1"))
    with pytest.raises(ValueError, match="not an agent history root"):
        Agent.get_history(public_id_url(dm.id, target_cls=TTX), user=admin)


def test_malformed_codec_payload_raises_without_repair(history_db):
    """Raise on corrupt tagged evidence rather than returning a prefix."""
    # 0. Retain a valid prefix followed by a deliberately invalid SDK payload.
    owner = Agent.create_history(Actor(addr="synthetic-agent"), user=None)
    payload = ModelMessagesTypeAdapter.dump_python([
        ModelRequest(parts=[UserPromptPart(content="Valid prefix")]),
    ], mode="json")[0]
    owner.ATTACH(_entry(payload))
    owner.ATTACH(_entry({"kind": "request", "parts": "not a parts list"}))
    before = _rows()
    # 1. Decoder validation must not silently skip or rewrite the invalid row.
    with pytest.raises(ValidationError):
        Agent.chat_history(owner)
    assert _rows() == before


# Changelog (Python has no native block-comment syntax).
# - 2026-11-11: Cover TTX SDK replay fidelity, insertion-order selection,
#   saved/archive owner checks and corrupt evidence without provider execution.
# - 2026-11-12: Use canonical codec policy, retain archived SDK evidence and
#   consolidate fresh owner/admin, nullable-scope and User DM isolation checks.
