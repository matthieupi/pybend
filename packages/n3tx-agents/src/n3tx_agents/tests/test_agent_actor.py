"""Protect stored agent configuration without restoring execution endpoints.

Canonical Matrix execution is covered by test_ttx_execution. These cohesive
tests retain native CRUD, hydrated tools, trusted policy overrides and the
absence of an unrestricted HTTP or implicit stock execution grant."""

import pytest

from n3tx_agents.actor import AgentActor
from n3tx_agents.tool_model import AgentTool
from n3tx_core.utils.registrar import register_model
from n3tx_threads import TTX


def test_stored_configuration_crud_and_hydrated_tools(
    fresh_matrix, memory_storage, monkeypatch,
):
    """Store, hydrate, update and delete agent policy through native CRUD."""
    # 0. Bind only disposable storage and retain caller-owned model bindings.
    for model in (AgentTool, AgentActor):
        monkeypatch.setattr(model, "storage", None)
        register_model(model, storage=memory_storage)
    tool = AgentTool.create(AgentTool(
        target="grants", description="Synthetic grant operations",
    ))
    created = AgentActor.create(AgentActor(
        name="Stored agent", prompt="Synthetic prompt", tools=[tool],
        constraints={"max_iterations": 4},
    ))
    # 1. Hydration preserves tool identities and all executable policy fields.
    fetched = AgentActor.get(created.id)
    assert fetched.name == "Stored agent"
    assert fetched.prompt == "Synthetic prompt"
    assert fetched.llm == "ollama:llama3.1"
    assert fetched.constraints == {"max_iterations": 4}
    assert fetched.tools[0].id == tool.id
    assert fetched.tools[0].description == "Synthetic grant operations"
    assert fetched.tool_addrs() == ["grants"]
    changed = AgentActor.update(created.id, {"prompt": "Revised"})
    assert changed.id == created.id and changed.prompt == "Revised"
    assert [row.id for row in AgentActor.list()] == [created.id]
    # 2. Deleting configuration does not implicitly delete selected tools.
    AgentActor.delete(created.id)
    assert AgentActor.get(created.id) is None
    assert AgentTool.get(tool.id).target == "grants"


def test_stored_policy_preserves_trusted_runtime_overrides(fresh_matrix):
    """Merge stored constraints while preserving explicit backend controls."""
    # 0. Stored tool relationships select addresses without granting access.
    agent = AgentActor(
        name="Configured", prompt="Stored prompt", llm="test",
        tools=[AgentTool(target="grants"), AgentTool(target="grants")],
        constraints={"max_iterations": 4, "tool_retries": 0},
    )
    assert agent.tool_addrs() == ["grants"]
    # 1. Backend overrides remain structured, not numeric/JSON-text wrappers.
    call = agent.run_config(
        "Task", prompt="Trusted prompt", tools=[], llm="test",
        constraints={"max_iterations": 2}, result_type=dict,
        user={"user_id": 1, "role": "staff"}, scope=None,
    )
    assert call.prompt == "Trusted prompt" and call.tools == []
    assert call.constraints == {"max_iterations": 2, "tool_retries": 0}
    assert call.has_llm_override and call.llm == "test"
    assert call.result_type is dict and call.scope is None
    assert call.user == {"user_id": 1, "role": "staff"}
    with pytest.raises(TypeError):
        agent.run_config("Retired handle", thread_id=0)


@pytest.mark.asyncio
async def test_stock_configuration_does_not_publish_or_grant_execution(
    fresh_matrix,
):
    """Keep stock configuration discoverable without unrestricted execution."""
    # 0. Capability metadata is not an execution endpoint or action policy.
    schema = AgentActor.schema()
    assert schema["agent"]["enabled"] is True
    assert "agentic_endpoint" not in schema["agent"]
    assert not {"agentic", "agentic_stream"} & schema.get("methods", {}).keys()
    before = [row.model_dump(mode="json") for row in TTX.list()]
    # 1. Even admins need a deliberate callee AGENTIC rule before allocation.
    agent = AgentActor(name="Not enabled", llm="test")
    with pytest.raises(PermissionError):
        await agent.agentic("Denied", user={"user_id": 1, "role": "admin"})
    assert [row.model_dump(mode="json") for row in TTX.list()] == before


# Changelog (Python has no native block-comment syntax).
# - 2026-11-12: Consolidate stored CRUD/configuration coverage; retire numeric
#   handles, JSON-text wrappers and unrestricted stock HTTP execution assertions.
