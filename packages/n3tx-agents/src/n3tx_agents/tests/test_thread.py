"""Parent-authorized conversation roots and exact provider-free SDK history."""

import importlib.util
from copy import deepcopy
from dataclasses import replace

import pytest
from pydantic import ValidationError
from pydantic_ai.messages import (
    ModelMessagesTypeAdapter, ModelRequest, ModelResponse, TextPart,
    ToolCallPart, ToolReturnPart, UserPromptPart,
)
from pydantic_ai.models.test import TestModel

import n3tx_agents
from n3tx_agents.agent import Agent, CallConfig
from n3tx_agents.history import open_thread, read_history
from n3tx_actors.api.auth_interceptor import auth_interceptor
from n3tx_actors.api.network_api import NetworkAPI
from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX
from n3tx_core.authorize import AUTHENTICATED, NEVER, OWNER
from n3tx_core.authorize.errors import AccessDenied
from n3tx_core.models.ref import Ref, public_id_url
from n3tx_core.utils.registrar import register_model
from n3tx_threads import Thread, TTX

from .conftest import HistoryOwner, USER


pytestmark = pytest.mark.unit
OTHER = {"user_id": 2, "role": "user"}


class SimpleAgent(ActorModel):
    """Require explicit saved scope for a non-storable execution target."""

    __tablename__ = "simple_agents"
    __storable__ = False
    __agent__ = True
    name: str = "Test Agent"


class SavedAgent(ActorModel):
    """Permit runtime scope inference only from a real registered entity."""

    __tablename__ = "saved_agents"
    __storable__ = True
    __agent__ = True
    __access__ = {"*": NEVER, "read": OWNER, "update": OWNER}
    user_owner: int = 1
    name: str


def _payload(messages):
    """Serialize typed messages for exact audit comparisons."""
    return ModelMessagesTypeAdapter.dump_python(messages, mode="json")


def _open(context, agent_addr="simple_agents"):
    """Create an authorized native root for the supplied saved host."""
    return open_thread(
        scope=Ref(context["scope"]), agent_addr=agent_addr,
        user=context["user"],
    )


def _append(thread, payload, timestamp):
    """Seed exact SDK evidence using trusted TTX persistence."""
    return thread.APPEND(TX(
        "Message", "synthetic", "ignored", data=payload,
        timestamp=float(timestamp),
    ), user_owner=USER["user_id"])


@pytest.mark.parametrize("module,export", [
    ("thread", "Thread"), ("tx_record", "TXRecord"),
    ("notes_mixin", "NotesMixin"), ("threaded_mixin", "ThreadedMixin"),
])
def test_legacy_agent_thread_api_is_absent(module, export):
    """The clean migration supplies no old modules or package shims."""
    # 0. Inspect removed agent-owned storage APIs without invoking a provider.
    assert importlib.util.find_spec(f"n3tx_agents.{module}") is None
    assert not hasattr(n3tx_agents, export)
    assert not hasattr(n3tx_agents.history, "HISTORY_CODEC")


def test_root_identity_and_shared_ttx_storage(agent_context, monkeypatch):
    """Conversation roots are semantic TTX rows, not separate containers."""
    # 0. Open through real parent policy and inspect canonical persistence.
    thread = _open(agent_context)
    assert isinstance(thread, Thread)
    assert Thread.storage is TTX.storage
    saved = TTX.get(thread.id)
    assert saved.name == "Conversation" and saved.value is None
    assert saved.target == agent_context["scope"]
    assert saved.source == "simple_agents" and saved.user_owner == 1
    # 1. Explicit handoff can reuse a root without owner/source equality gates.
    monkeypatch.setattr(HistoryOwner, "__access__", {
        **HistoryOwner.__access__,
        "read": AUTHENTICATED, "update": AUTHENTICATED,
    })
    resumed = open_thread(
        scope=Ref(agent_context["scope"]), agent_addr="other_agent",
        user=OTHER, thread_id=thread.id,
    )
    assert resumed.id == thread.id
    assert public_id_url(thread.id, target_cls=TTX).endswith(
        f"/TTX/{thread.id}",
    )


@pytest.mark.asyncio
async def test_configured_ttx_boundary_denies_get_and_filters_list(
    agent_context, fresh_matrix,
):
    """Configured Tier 1/2 guards restrict generic snapshot reads.

    Raw trusted Matrix LIST does not derive an authorization filter merely
    from meta.user. This test exercises the configured native adapter instead.
    """
    # 0. Configure the actual native boundary with trusted model/caller inputs.
    thread = _open(agent_context)
    adapter = NetworkAPI()
    fresh_matrix.register(adapter)
    adapter.use(auth_interceptor, on="request")
    # 1. Native resource authorization denies a generic GET of the saved root.
    denied = await adapter.request(TX(
        "get", adapter.addr, TTX.__addr__, data={"id": thread.id},
        meta={"user": dict(USER), "model_cls": TTX},
    ), timeout=2)
    assert denied.is_error and denied.data["code"] == 403
    # 2. Native Tier 1 supplies the NEVER predicate for a filtered empty LIST.
    listed = await adapter.request(TX(
        "list", adapter.addr, TTX.__addr__, data={},
        meta={"user": dict(USER), "model_cls": TTX},
    ), timeout=2)
    assert not listed.is_error and listed.data == []
    assert len(TTX.list()) == 1


def test_typed_history_authorization_and_unchanged_raw_payloads(
    agent_context, monkeypatch,
):
    """Read exact evidence without codec selection or repair."""
    # 0. Insert in reverse time order, preserving mismatched protocol evidence.
    thread = _open(agent_context)
    raw = _payload([
        ModelRequest(parts=[UserPromptPart(content="hello")]),
        ModelResponse(parts=[TextPart(content="hi there")]),
        ModelResponse(parts=[ToolCallPart(
            "lookup", {"key": "synthetic"}, tool_call_id="unanswered",
        )]),
        ModelRequest(parts=[ToolReturnPart(
            "other", {"found": True}, tool_call_id="different-call",
        )]),
    ])
    for index in reversed(range(len(raw))):
        message = _append(thread, raw[index], index + 1)
    message.APPEND(TX(
        "Message", "synthetic", "ignored", data={"invalid": "grandchild"},
    ))
    thread.APPEND(TX("NOTE", "synthetic", "ignored", data="not SDK"))
    other = _open(agent_context)
    _append(other, raw[0], 0)
    before = [row.model_dump() for row in TTX.list()]
    # 1. Parent read is sufficient without update or appender equality.
    monkeypatch.setattr(HistoryOwner, "__access__", {
        **HistoryOwner.__access__, "read": AUTHENTICATED, "update": NEVER,
    })
    for caller in (USER, OTHER):
        assert _payload(read_history(thread, user=caller)) == raw
    # 2. Reads cannot normalize, repair, remove or rewrite stored evidence.
    assert [row.model_dump() for row in TTX.list()] == before
    with pytest.raises(AccessDenied):
        read_history(thread, user=None)


def test_malformed_history_authorizes_before_decoding(agent_context):
    """Malformed evidence cannot leak past parent authorization."""
    # 0. Trusted storage accepts JSON without claiming SDK validity.
    thread = _open(agent_context)
    payload = {"kind": "not-an-sdk-message", "parts": []}
    record = _append(thread, payload, 1)
    # 1. Denied identities see authorization rather than protocol details.
    for caller in (OTHER, {}, None):
        with pytest.raises(AccessDenied):
            read_history(thread, user=caller)
    with pytest.raises(ValidationError):
        read_history(thread, user=USER)
    assert TTX.get(record.id).value == payload


def test_complete_history_keeps_all_messages_and_timestamp_ties(
    agent_context,
):
    """Decode all immediate Messages without paging or tie losses."""
    # 0. Store over fifty SDK messages with four entries at each timestamp.
    thread = _open(agent_context)
    messages = [
        ModelRequest(parts=[UserPromptPart(content=f"synthetic {index}")])
        for index in range(64)
    ]
    payloads = _payload(messages)
    for index in reversed(range(len(payloads))):
        _append(thread, payloads[index], index // 4)
    # 1. All entries decode; no ordering assertion is made within time ties.
    history = read_history(thread, user=USER)
    assert len(history) == len(messages) == 64
    assert {message.parts[0].content for message in history} == {
        message.parts[0].content for message in messages
    }


@pytest.mark.parametrize("change", ["target", "name", "delete"])
def test_history_rechecks_prepared_root_identity(agent_context, change):
    """Stale roots cannot redirect authorized reads to another record."""
    # 0. Retain a loaded root while changing its persisted identity or target.
    thread = _open(agent_context)
    if change == "delete":
        TTX.delete(thread.id)
    elif change == "name":
        TTX.update(thread.id, {"name": "NOTE"})
    else:
        other = HistoryOwner.create(HistoryOwner())
        TTX.update(thread.id, {
            "target": public_id_url(other.id, target_cls=HistoryOwner),
        })
    # 1. Reads reject stale identity instead of following changed ownership.
    with pytest.raises(ValueError):
        read_history(thread, user=USER)


@pytest.mark.parametrize("case", [
    "missing", "missing_root", "remote", "unregistered", "wrong_scope",
    "wrong_name", "child",
])
@pytest.mark.asyncio
async def test_open_rejects_invalid_parent_or_root(
    agent_context, monkeypatch, case,
):
    """Resume checks exact root kind and host without graph traversal."""
    # 0. Construct an invalid scope or a non-root record ID.
    scope = Ref(agent_context["scope"])
    thread = _open(agent_context)
    identity = thread.id
    if case == "missing":
        scope = Ref(public_id_url(999999, target_cls=HistoryOwner))
    elif case == "missing_root":
        identity += 999999
    elif case == "remote":
        scope = Ref("https://remote.example.test/HistoryOwner/1")
    elif case == "unregistered":
        scope = Ref("https://agents.example.test/UnknownOwner/1")
    elif case == "wrong_scope":
        owner = HistoryOwner.create(HistoryOwner())
        scope = Ref(public_id_url(owner.id, target_cls=HistoryOwner))
    elif case == "wrong_name":
        identity = TTX.create(TTX(TX(
            "NOTE", "synthetic", scope, data=None,
        ))).id
    else:
        identity = _append(thread, {"kind": "request", "parts": []}, 1).id
    before = len(TTX.list())
    # 1. Invalid roots are rejected, never replaced or followed recursively.
    with pytest.raises(ValueError):
        open_thread(
            scope=scope, agent_addr="simple_agents", user=USER,
            thread_id=identity,
        )
    assert len(TTX.list()) == before

    def forbidden(*args, **kwargs):
        """Fail if invalid root identity reaches provider setup."""
        pytest.fail("Invalid conversation reached model resolution")
    # 2. The actual runtime preserves this preflight before provider setup.
    monkeypatch.setattr("n3tx_agents.agent._resolve_llm", forbidden)
    with pytest.raises(ValueError):
        await Agent.prepare(SimpleAgent, CallConfig(
            task="Invalid", prompt="Synthetic", tools=[], user=USER,
            constraints={}, thread_id=identity, scope=scope,
            llm="must-not-resolve", has_llm_override=True,
        ))
    assert len(TTX.list()) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("permission", ["read", "update"])
@pytest.mark.parametrize("caller", [USER, None])
async def test_prepare_authorizes_before_model_setup(
    agent_context, monkeypatch, permission, caller,
):
    """Check both parent rights before provider setup for every caller."""

    def forbidden(*args, **kwargs):
        """Fail if a denied parent reaches model resolution."""
        pytest.fail("Denied parent reached model resolution")
    # 0. Deny one required parent right while retaining real native lookup.
    monkeypatch.setattr(HistoryOwner, "__access__", {
        **HistoryOwner.__access__, permission: NEVER,
    })
    monkeypatch.setattr("n3tx_agents.agent._resolve_llm", forbidden)
    call = CallConfig(
        task="Denied", prompt="Synthetic", tools=[], user=caller,
        constraints={}, thread_id=None,
        scope=Ref(agent_context["scope"]), llm="must-not-resolve",
        has_llm_override=True,
    )
    # 1. Neither root allocation nor provider setup occurs after denial.
    with pytest.raises(AccessDenied):
        await Agent.prepare(SimpleAgent, call)
    assert TTX.list() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_native_turns_create_resume_and_persist(agent_context, stream):
    """Retain exact root IDs and saved messages through both adapters."""
    # 0. Execute two native turns using explicit saved scope and TestModel.
    agent = SimpleAgent(addr="simple_agents/1")
    thread_id = None
    counts = []
    for task in ("Question 1", "Question 2"):
        kwargs = dict(
            task=task, prompt="Synthetic instructions", tools=[],
            llm=TestModel(call_tools=[]), thread_id=thread_id,
            **agent_context,
        )
        if stream:
            chunks = [chunk async for chunk in agent.run_stream(**kwargs)]
            assert not [c for c in chunks if c["name"] == "error"]
            done = [c for c in chunks if c["name"] == "done"]
            assert len(done) == 1 and chunks[-1]["name"] == "done"
            result = done[0]["data"]
        else:
            result = await agent.run(**kwargs)
            assert result["message_count"] == len(result["messages"])
        # 1. Resume the same root and compare real native persisted evidence.
        if thread_id is not None:
            assert result["thread_id"] == thread_id
        thread_id = result["thread_id"]
        thread = Thread.get(thread_id)
        assert thread.target == agent_context["scope"]
        history = read_history(thread, user=USER)
        counts.append(len(history))
        if not stream:
            assert _payload(history) == _payload(result["messages"])
        rows = TTX.list(where={
            "name": "Message",
            "target": public_id_url(thread_id, target_cls=TTX),
        })
        assert len(rows) == len(history)
        assert all(row.user_owner == 1 for row in rows)
        assert all("codec" not in row.meta for row in rows)
    assert counts[0] > 0 and counts[1] > counts[0]


@pytest.mark.asyncio
async def test_saved_instance_scope_inference(agent_context):
    """Infer scope only from a registered saved execution target."""
    # 0. Register and save the agent itself with a real parent policy.
    register_model(SavedAgent, storage=TTX.storage)
    saved = SavedAgent.create(SavedAgent(name="Saved synthetic agent"))
    result = await saved.agentic(
        task="Hello", tools=[], llm=TestModel(call_tools=[]), user=USER,
    )
    # 1. Runtime inference selects that entity, not its actor address string.
    assert Thread.get(result["thread_id"]).target == public_id_url(
        saved.id, target_cls=SavedAgent,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("case", [
    "class", "nonstored", "saved_class", "unsaved", "unregistered",
])
async def test_unsaved_or_class_target_requires_scope(
    agent_context, monkeypatch, case,
):
    """Class and non-storable calls cannot invent a business owner."""
    # 0. Execute without scope while provider requests remain disabled.
    target = SimpleAgent
    if case == "nonstored":
        target = SimpleAgent()
    elif case == "saved_class":
        target = SavedAgent
    elif case == "unsaved":
        target = SavedAgent(name="Unsaved")
    elif case == "unregistered":
        target = SavedAgent(id=999, name="Unregistered saved-looking target")

    def forbidden(*args, **kwargs):
        """Fail if missing ownership reaches provider resolution."""
        pytest.fail("Missing business scope reached model resolution")
    monkeypatch.setattr("n3tx_agents.agent._resolve_llm", forbidden)
    with pytest.raises(ValueError):
        await target.agentic(
            task="No scope", tools=[], llm="test", user=USER,
        )
    # 1. Invalid scope inference must not create an orphan root.
    assert TTX.list() == []


def test_checkpoint_failure_latches_successful_prefix(
    agent_context, monkeypatch,
):
    """Stop later checkpoints after uncertainty without retrying writes."""
    from types import SimpleNamespace
    # 0. Keep real first-row persistence and fail the second native append.
    thread = _open(agent_context)
    original = Thread.APPEND
    calls = []

    def append(self, tx, *, user_owner=None):
        """Save one row and fail the next uncertain storage attempt."""
        calls.append(deepcopy(tx.data))
        if len(calls) == 2:
            raise RuntimeError("Synthetic persistence uncertainty")
        return original(self, tx, user_owner=user_owner)
    monkeypatch.setattr(Thread, "APPEND", append)
    prepared = SimpleNamespace(
        thread=thread, deps=SimpleNamespace(user=USER),
        agent_addr="simple_agents", root=None,
    )
    messages = [
        ModelRequest(parts=[UserPromptPart(content="one")]),
        ModelResponse(parts=[TextPart(content="two")]),
    ]
    # 1. Subsequent flushes must neither retry nor extend the uncertain prefix.
    _, flush = Agent._history_hooks(prepared)
    flush(messages)
    flush([*messages, ModelResponse(parts=[TextPart(content="three")])])
    assert len(calls) == 2
    assert _payload(read_history(thread, user=USER)) == _payload(messages[:1])


@pytest.mark.parametrize("action", ["read", "update"])
def test_checkpoint_rechecks_current_parent_permissions(
    agent_context, monkeypatch, action,
):
    """Revoking either parent right stops all later checkpoint writes."""
    from types import SimpleNamespace
    # 0. Keep a valid root but revoke one persisted-owner policy action.
    thread = _open(agent_context)
    prepared = SimpleNamespace(
        thread=thread, deps=SimpleNamespace(user=USER),
        agent_addr="simple_agents",
    )
    monkeypatch.setattr(HistoryOwner, "__access__", {
        **HistoryOwner.__access__, action: NEVER,
    })
    _, flush = Agent._history_hooks(prepared)
    messages = [ModelRequest(parts=[UserPromptPart(content="denied")])]
    # 1. A denied checkpoint persists nothing and cannot resume after recovery.
    flush(messages)
    monkeypatch.setattr(HistoryOwner, "__access__", {
        "*": NEVER, "read": OWNER, "update": OWNER,
    })
    flush(messages)
    assert len(TTX.list()) == 1


@pytest.mark.asyncio
async def test_provider_context_repair_cannot_rewrite_audit_evidence(
    agent_context, monkeypatch,
):
    """Repair a copy while returned and saved evidence stays raw."""
    from types import SimpleNamespace
    # 0. Prepare real authorized history before isolating the SDK run seam.
    thread = _open(agent_context)
    old = ModelRequest(parts=[UserPromptPart(content="raw audit input")])
    _append(thread, _payload([old])[0], 1)
    prepared = await Agent.prepare(SimpleAgent, CallConfig(
        task="Continue", prompt="Synthetic", tools=[],
        constraints={},
        scope=Ref(agent_context["scope"]), user=USER, thread_id=thread.id,
        llm=TestModel(call_tools=[]), has_llm_override=True,
    ))
    before = _payload(prepared.message_history)
    new = ModelResponse(parts=[TextPart(content="new answer")])
    calls = []

    def repair(messages):
        """Mutate provider context to expose evidence aliasing."""
        assert messages is not prepared.message_history
        assert messages[0] is not prepared.message_history[0]
        assert messages[0].parts[0] is not prepared.message_history[0].parts[0]
        messages[0].parts[0].content = "provider-only repaired input"
        return messages

    async def run(task, **kwargs):
        """Observe provider context without inference or tool execution."""
        calls.append(task)
        assert kwargs["message_history"][0].parts[0].content == (
            "provider-only repaired input"
        )
        return SimpleNamespace(
            output="new answer", new_messages=lambda: [new],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1, requests=1),
        )
    # 1. Exercise runtime copy/flush behavior with native persistence intact.
    monkeypatch.setattr("n3tx_agents.agent.repair_messages", repair)
    prepared = replace(prepared, ai_agent=SimpleNamespace(run=run))
    result = await Agent.run(prepared, "Continue")
    # 2. Repair cannot alter the raw prefix or cause another execution attempt.
    assert calls == ["Continue"]
    assert _payload(prepared.message_history) == before
    assert _payload(result["messages"]) == [*before, *_payload([new])]
    assert _payload(read_history(thread, user=USER)) == _payload(
        result["messages"],
    )


# Changelog (Python has no native block-comment syntax).
# - 2026-11-04: Use parent-authorized semantic TTX roots and Message children;
#   preserve raw audit data, scope and failed-checkpoint stop latches.
#   Exercise configured native read guards, not raw trusted Matrix LIST;
#   require complete Message history beyond fifty rows and timestamp ties.
# - 2026-11-02: Retain SDK integration after generic Thread extraction;
#   authorize typed reads and require exact unchanged raw audit payloads.
