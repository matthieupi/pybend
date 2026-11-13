"""Protect canonical TTX execution through native Matrix and SDK boundaries.

Fresh agent-root owner/admin policy protects one canonical protocol journal.
Real TestModel execution covers guarded context, continuation and tool routing.
No app activation, provider calls or legacy identity migration occurs."""

from contextlib import closing
from queue import Empty
import sqlite3
from types import SimpleNamespace

import pytest
from pydantic_ai import models
from pydantic_ai.messages import (
    ModelMessagesTypeAdapter, ModelRequest, ModelResponse, TextPart,
    UserPromptPart,
)
from pydantic_ai.models.test import TestModel as SDKTestModel

from n3tx_actors import Actor, Matrix, TX
from n3tx_actors.models.actor_model import ActorModel
from n3tx_agents import agent as agent_module
from n3tx_agents.agent import Agent
from n3tx_agents.history import HISTORY_CODEC
from n3tx_agents.threaded_mixin import ThreadedMixin, current_execution
from n3tx_core.authorize import AUTHENTICATED, OWNER
from n3tx_core.models import proto_dump
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.ref import public_id_url
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.descriptors import fullmethod
from n3tx_core.utils.registrar import register_model, registered_models
from n3tx_threads import TTX

USER = {"user_id": 1, "role": "user"}


@pytest.fixture
def execution(tmp_path, monkeypatch):
    """Isolate native scope storage, actor routing and provider-free policy."""
    # 0. Preserve global state before defining fixture-owned model classes.
    registries = (
        registered_models, ProtoModel._schema_cache,
        proto_dump._schema_url_cache, proto_dump._instance_url_cache,
    )
    snapshots = [dict(registry) for registry in registries]
    original_root = Actor.root()
    root = Matrix(addr="execution-root")
    Actor.root(root)
    token = current_execution.set(None)
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)
    for name, value in (
        ("__matrix__", root), ("__children__", {}),
        ("__interceptors__", {}), ("_subscribers", []), ("storage", None),
    ):
        monkeypatch.setattr(TTX, name, value)
    seen = []

    class Scope(ActorModel, auto_register=False):
        """Keep business permissions separate from history metadata."""

        __tablename__ = "execution_scopes"
        __storable__ = True
        __access__ = {"read": OWNER, "update": OWNER}
        user_owner: int

    class Echo(ThreadedMixin, ActorModel, auto_register=False):
        """Exercise native tools without creating a second legacy journal."""

        __tablename__ = "execution_echo"
        __storable__ = False
        __thread_roots__ = frozenset({"echo"})

        @classmethod
        @expose_route("/echo", methods=["POST"], access=AUTHENTICATED)
        def echo(cls, value: str, user: dict = None) -> dict[str, object]:
            """Return synthetic data with the transport-injected caller."""
            assert user == USER
            assert isinstance(current_execution.get(), TTX)
            return {"value": value}

    class Executor(ActorModel, auto_register=False):
        """Opt in and inspect context across the guarded run seam."""

        __tablename__ = "execution_executor"
        __storable__ = False
        __access__ = {"AGENTIC": AUTHENTICATED}
        __agent__ = {
            "llm": SDKTestModel(call_tools="all"), "self_tools": False,
            "neighbors": False, "tools": [Echo.addr],
        }

        @fullmethod
        async def run(target, **kwargs):
            """Require authorized context before the guarded override."""
            assert current_execution.get().id == kwargs["ttx"].id
            assert kwargs["user"] == USER
            if kwargs["task"] == "explode":
                raise RuntimeError("Synthetic guarded failure")
            return await super(Executor, target).run(**kwargs)

    def observe(tx):
        """Observe native commands, tools and unclaimed send responses only."""
        if tx.name in ("AGENTIC", "AGENTIC_RESPONSE", "echo"):
            seen.append(tx)
        return tx

    database = tmp_path / "execution.sqlite3"
    storage = SQLiteStorage(database=str(database), pool_size=1)
    try:
        # 1. Allocate one scope-bound owner, never a legacy conversation root.
        register_model(TTX, storage=storage)
        register_model(Scope, storage=storage)
        for actor in (TTX, Executor, Echo):
            root.register(actor)
        scope = Scope.create(Scope(user_owner=1))
        scope_ref = public_id_url(scope.id, target_cls=Scope)
        owner = Agent.create_history(Executor, user=USER, scope=scope_ref)
        root.use(observe, on="inbox")
        yield SimpleNamespace(
            root=root, executor=Executor, owner=owner, scope=scope_ref,
            seen=seen, database=database,
        )
    finally:
        # 2. Close owned handles and restore context, roots and shared caches.
        while True:
            try:
                connection = storage._pool.get_nowait()
            except Empty:
                break
            connection.rollback()
            connection.close()
        root.children.clear()
        root._interceptors.clear()
        Actor.__matrix__ = original_root
        current_execution.reset(token)
        for registry, snapshot in zip(registries, snapshots):
            registry.clear()
            registry.update(snapshot)


def _command(env, task="Synthetic task", *, user=USER):
    """Build a bounded command with trusted metadata and a spoofed body user."""
    return TX(
        "AGENTIC", f"ttx/{env.owner.id}", env.executor.addr,
        data={
            "task": task,
            "ttx_ref": public_id_url(env.owner.id, target_cls=TTX),
            "user": {"user_id": 999, "role": "admin"},
        },
        meta={"user": user},
    )


@pytest.mark.asyncio
async def test_matrix_continuation_uses_one_ttx_and_causal_tools(execution):
    """Two native turns preserve guarded context and one protocol journal."""
    # 0. An outer execution context must survive the entire guarded call.
    env = execution
    parent = env.owner
    token = current_execution.set(parent)
    try:
        # 1. Native sender delivery returns None; capture its actual response.
        assert await env.owner.send(_command(env)) is None
        first = [t for t in env.seen if t.name == "AGENTIC_RESPONSE"]
        assert len(first) == 1
        assert current_execution.get() is parent
        initial = ModelMessagesTypeAdapter.dump_python(
            Agent.chat_history(env.owner), mode="json",
        )
        assert initial and len(initial) == first[0].data["message_count"]
        reply = await env.root.request(_command(env, "Continue"), timeout=2.0)
        assert not reply.is_error, reply.data
        assert current_execution.get() is parent
    finally:
        current_execution.reset(token)
    # 2. Preserve raw SDK history and route tools with canonical causal source.
    result = reply.data
    assert result["ttx_ref"] == public_id_url(env.owner.id, target_cls=TTX)
    assert "thread_id" not in result and len(result["messages"]) > len(initial)
    assert ModelMessagesTypeAdapter.dump_python(
        Agent.chat_history(env.owner), mode="json",
    ) == ModelMessagesTypeAdapter.dump_python(result["messages"], mode="json")
    tools = [tx for tx in env.seen if tx.name == "echo"]
    assert tools and all(tx.source == f"ttx/{env.owner.id}" for tx in tools)
    assert all(tx.meta["user"] == USER for tx in tools)
    records = TTX.list(archived=True)
    roots = [row.id for row in records if row.meta.get("agent_history") is True]
    assert roots == [env.owner.id]
    assert any(row.meta.get("codec") == HISTORY_CODEC for row in records)
    assert any(row.name == "RETURN" for row in records)
    assert any(
        row.name == "echo" and row.source == f"ttx/{env.owner.id}"
        for row in records
    )
    assert all("user" not in row.meta for row in records)
    with closing(sqlite3.connect(env.database)) as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'",
        )}
    assert not {"threads", "tx_records"} & tables


@pytest.mark.asyncio
async def test_admission_denies_before_provider_history_or_tools(
    execution, monkeypatch,
):
    """Private root policy and explicit opt-in precede preparation."""
    # 0. Any preparation beyond the admission boundary is an immediate failure.
    env = execution
    touched = []

    def forbidden(*args, **kwargs):
        """Detect provider resolution, history reads or tool discovery."""
        touched.append(True)
        raise AssertionError("Preflight must reject first")

    monkeypatch.setattr(agent_module, "_resolve_llm", forbidden)
    monkeypatch.setattr(agent_module, "discover_tools", forbidden)
    monkeypatch.setattr(Agent, "chat_history", forbidden)
    overrides = []

    @fullmethod
    async def forbidden_override(target, *args, **kwargs):
        """Detect configuration projection before private root admission."""
        overrides.append(target)
        raise AssertionError("Private root denial must precede configuration")

    # 1. Private history admission precedes overridable configuration.
    with monkeypatch.context() as patch:
        patch.setattr(env.executor, "run_config", forbidden_override)
        denied = await env.root.request(
            _command(env, user={"user_id": 2, "role": "user"}), timeout=0.25,
        )
        assert denied.is_error and denied.data["code"] == 403
        assert overrides == []
    with pytest.raises(ValueError, match="scope does not match"):
        await env.executor.agentic(
            "Mismatch", ttx=env.owner, user=USER,
            scope=public_id_url(999, target_cls=TTX),
        )
    with pytest.raises(TypeError):
        env.executor.run_config("Retired numeric handle", thread_id=7)
    command = _command(env)
    command.data["llm"] = "test"
    rejected = await env.root.request(command, timeout=0.25)
    assert rejected.is_error and rejected.data["code"] == 400
    # 2. A wildcard rule is not an explicit AGENTIC execution grant.
    monkeypatch.setattr(env.executor, "__access__", {"*": AUTHENTICATED})
    denied = await env.root.request(_command(env), timeout=0.25)
    assert denied.is_error and denied.data["code"] == 403
    assert touched == []
    assert len(TTX.list(archived=True)) == 1


@pytest.mark.asyncio
async def test_append_failure_stops_flush_and_guarded_failure_resets_context(
    execution, monkeypatch,
):
    """Stop checkpoint retries and restore context after guarded failure."""
    # 0. Use real authorized preparation and three complete SDK messages.
    env = execution
    prepared = await Agent.prepare(
        env.executor, env.executor.run_config("Checkpoint", user=USER),
        ttx=env.owner,
    )
    messages = [
        ModelRequest(parts=[UserPromptPart(content="First")]),
        ModelResponse(parts=[TextPart(content="Second")]),
        ModelRequest(parts=[UserPromptPart(content="Third")]),
    ]
    native_attach, attempts = TTX.ATTACH, []

    def append_once(target, entry):
        """Save one prefix record, then model an uncertain append failure."""
        attempts.append(entry.uuid)
        if len(attempts) > 1:
            raise RuntimeError("Synthetic uncertain write")
        return native_attach(target, entry)

    monkeypatch.setattr(TTX, "ATTACH", append_once)
    _, flush = Agent._history_hooks(prepared)
    # 1. Later flushes cannot retry the failed suffix or duplicate the prefix.
    flush(messages)
    flush(messages)
    assert len(attempts) == 2
    assert ModelMessagesTypeAdapter.dump_python(
        Agent.chat_history(env.owner), mode="json",
    ) == ModelMessagesTypeAdapter.dump_python(messages[:1], mode="json")
    # 2. Native Matrix error replies retain the inherited outer context.
    parent = env.owner
    token = current_execution.set(parent)
    try:
        reply = await env.root.request(_command(env, "explode"), timeout=0.25)
        assert reply.is_error
        assert "Synthetic guarded failure" in reply.data["message"]
        assert current_execution.get() is parent
    finally:
        current_execution.reset(token)
    assert len(attempts) == 2


# Changelog (Python has no native block-comment syntax).
# - 2026-11-11: Protect opt-in Matrix execution, scope admission, causal tools,
#   single-journal continuation and stop-after-failure checkpoint/context rules.
#   Prove AGENTIC scope denial precedes overridable agentic dispatch.
# - 2026-11-12: Require declared owner/admin roots, canonical context and
#   child/RETURN capture; reject retired numeric options before preparation.
