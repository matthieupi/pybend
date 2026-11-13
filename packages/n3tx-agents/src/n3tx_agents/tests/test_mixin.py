"""Protect agent policy, concurrent invocation and normal stream boundaries.

Canonical runtime tests own admission/checkpoint failures. This suite retains
schema/state projection, tool selection, trusted configuration precedence and
SDK stream semantics without numeric handles or permissive legacy adapters."""

import asyncio

import pytest
from pydantic import Field
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_ai.models.test import TestModel as SDKTestModel

from n3tx_actors import Actor
from n3tx_actors.models.actor_model import ActorModel
from n3tx_agents.agent import Agent
from n3tx_agents.mixin import AgentMixin
from n3tx_agents.threaded_mixin import current_execution
from n3tx_core import config
from n3tx_core.authorize import AUTHENTICATED
from n3tx_core.utils.decorators import expose_route

USER = {"user_id": 1, "role": "staff"}


@pytest.fixture
def policy_model(fresh_matrix):
    """Declare one native model with neighbors, tools and explicit admission."""
    # 0. Keep model declarations local to the isolated native actor root.
    class Comment(ActorModel, auto_register=False):
        """Supply a local list relationship for native schema/tool discovery."""

        __tablename__ = "policy_comments"
        __storable__ = False
        text: str = ""

        @classmethod
        @expose_route("/ping", methods=["POST"], access=AUTHENTICATED)
        def ping(cls, user: dict = None) -> dict[str, object]:
            """Exercise a separate native tool with the injected caller."""
            assert user == USER
            assert current_execution.get() is not None
            return {"value": "pong"}

    class Product(ActorModel, auto_register=False):
        """Expose policy and one synthetic tool, never an external provider."""

        __tablename__ = "policy_products"
        __storable__ = False
        __access__ = {"AGENTIC": AUTHENTICATED}
        __agent__ = {
            "prompt": "Synthetic product expert.", "llm": "test",
            "tools": ["policy_comments"],
            "constraints": {"max_iterations": 4},
        }
        name: str = "Synthetic product"
        price: float = 9.99
        comments: list[Comment] = Field(default_factory=list)

        @classmethod
        @expose_route("/ping", methods=["POST"], access=AUTHENTICATED)
        def ping(cls, user: dict = None) -> dict[str, object]:
            """Return synthetic data using the actual injected caller."""
            assert user == USER
            return {"value": "pong"}

    fresh_matrix.register(Product)
    fresh_matrix.register(Comment)
    return Product


def test_context_and_tool_policy_share_native_schema(policy_model):
    """Keep class schema, instance state and deduplicated neighbor discovery."""
    # 0. Native flag injection supplies policy without altering model fields.
    model = policy_model
    assert issubclass(model, AgentMixin)
    instance = model(name="Widget", price=29.99)
    class_context, instance_context = model.ctx(), instance.ctx()
    # 1. Declared context and methods remain available to model-owned policy.
    assert class_context.startswith("Synthetic product expert.")
    assert all(key in class_context for key in ("name", "price", "ping"))
    assert "Current instance" not in class_context
    assert "Current instance" in instance_context
    assert "Widget" in instance_context
    assert "29.99" in instance_context
    assert model.tools() == ["policy_products", "policy_comments"]
    assert instance.tools() == model.tools()
    assert model.schema()["agent"]["enabled"] is True


def test_trusted_configuration_precedence(policy_model, monkeypatch):
    """Preserve defaults/model/backend precedence and reject numeric handles."""
    # 0. Configuration selection is pure and does not allocate a history root.
    monkeypatch.setattr(config, "AGENT_DEFAULTS", {
        "constraints": {"max_iterations": 9, "tool_retries": 0},
    })
    inherited = policy_model.run_config("Task", user=USER)
    assert inherited.constraints == {"max_iterations": 4, "tool_retries": 0}
    # 1. Explicit backend choices retain their exact structured values.
    llm = SDKTestModel(call_tools=[])
    call = policy_model.run_config(
        "Task", prompt="Exact prompt", tools=[], llm=llm, user=USER,
        constraints={"max_iterations": 2}, result_type=dict, scope=None,
    )
    assert call.prompt == "Exact prompt" and call.tools == []
    assert call.constraints == {"max_iterations": 2, "tool_retries": 0}
    assert call.llm is llm and call.has_llm_override
    assert call.result_type is dict and call.user == USER
    assert call.scope is None
    with pytest.raises(TypeError):
        policy_model.run_config("Retired", thread_id=7)


@pytest.mark.asyncio
async def test_concurrent_native_calls_keep_distinct_history(policy_model):
    """Task-local native configuration cannot cross-contaminate separate runs."""
    # 0. Each call owns a newly declared root; the inherited context stays put.
    parent = current_execution.get()
    calls = [
        policy_model.agentic(
            task=task, user=USER, llm=SDKTestModel(call_tools=[]), tools=[],
        )
        for task in ("First synthetic task", "Second synthetic task")
    ]
    # 1. Real SDK execution returns exact independently persisted evidence.
    results = await asyncio.gather(*calls)
    assert results[0]["ttx_ref"] != results[1]["ttx_ref"]
    for result in results:
        owner = Agent.get_history(result["ttx_ref"], user=USER)
        assert result["message_count"] == len(result["messages"])
        assert ModelMessagesTypeAdapter.dump_python(
            Agent.chat_history(owner), mode="json",
        ) == ModelMessagesTypeAdapter.dump_python(
            result["messages"], mode="json",
        )
    assert current_execution.get() is parent


@pytest.mark.asyncio
async def test_native_stream_preserves_tool_events_and_completion(
    policy_model, fresh_matrix,
):
    """Normal completion preserves caller, tool ordering, sequence and usage."""
    # 0. Observe actual native tool arrivals without replacing the SDK loop.
    seen = []
    tool_actor = fresh_matrix.children["policy_comments"]
    tool_actor.use(lambda tx: seen.append(tx) or tx, on="inbox")
    chunks = [chunk async for chunk in policy_model.agentic_stream(
        "Use the synthetic tool", user=USER, tools=[tool_actor.addr],
        llm=SDKTestModel(call_tools=["policy_comments_ping"]),
    )]
    # 1. Do not accept error events as substitutes for successful completion.
    names = [chunk["name"] for chunk in chunks]
    assert "error" not in names and names[-1] == "done"
    assert names.index("tool_call") < names.index("tool_result")
    calls = [chunk for chunk in chunks if chunk["name"] == "tool_call"]
    returns = [chunk for chunk in chunks if chunk["name"] == "tool_result"]
    assert calls[0]["data"]["tool"] == "policy_comments_ping"
    assert "args" in calls[0]["data"] and "result" in returns[0]["data"]
    assert calls[0]["data"]["call_id"] == returns[0]["data"]["call_id"]
    sequences = [chunk["meta"]["seq"] for chunk in chunks]
    assert all(a < b for a, b in zip(sequences, sequences[1:]))
    done = chunks[-1]
    assert done["meta"]["stream_end"] is True
    assert done["data"]["tool_calls"] >= 1
    assert "usage" in done["data"]
    owner = Agent.get_history(done["data"]["ttx_ref"], user=USER)
    tools = [tx for tx in seen if tx.name == "ping"]
    assert tools and all(tx.meta["user"] == USER for tx in tools)
    assert all(tx.source == f"ttx/{owner.id}" for tx in tools)
    assert Agent.chat_history(owner)


@pytest.mark.asyncio
async def test_stream_preparation_failure_is_one_native_error(
    policy_model, monkeypatch,
):
    """Missing routing emits one terminal setup error, never fake completion."""
    # 0. Prepare a legitimate saved owner before removing the native root.
    owner = current_execution.get()
    monkeypatch.setattr(Actor, "__matrix__", None)
    # 1. The trusted engine seam retains native setup-error semantics.
    chunks = [chunk async for chunk in policy_model.run_stream(
        task="Synthetic task", prompt="Synthetic prompt", tools=[],
        llm=SDKTestModel(call_tools=[]), ttx=owner,
    )]
    assert len(chunks) == 1 and chunks[0]["name"] == "error"
    assert chunks[0]["meta"]["error"] is True
    assert "No Matrix root" in chunks[0]["data"]["message"]


# Changelog (Python has no native block-comment syntax).
# - 2026-11-12: Consolidate policy and streaming assertions around canonical
#   Matrix invocation; retain configuration, concurrency, tool and failure fences.
#   Use a separate neighbor tool without changing native self-exclusion.
