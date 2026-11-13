"""Protect tool caller propagation with mandatory active canonical execution.

Trusted None remains distinct from an empty anonymous mapping. Native Matrix
and ActorModel own authorization/injection; no app guards or providers load."""

import json
from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry

from n3tx_actors.models.actor_model import ActorModel
from n3tx_agents.agent import AgentDeps
from n3tx_agents.threaded_mixin import current_execution
from n3tx_agents.tools import _route_tool_call
from n3tx_core.authorize import AUTHENTICATED
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.registrar import register_model


@pytest.mark.asyncio
async def test_tool_caller_and_causal_source_reach_native_policy(fresh_matrix):
    """Propagate None/authenticated callers while denying anonymous mappings."""
    # 0. Use a real class action and observe actual Matrix inbox arrivals.
    class ToolActor(ActorModel):
        """Expose one synthetic caller-aware native action."""

        __tablename__ = "authenticated_tool"
        __storable__ = False

        @classmethod
        @expose_route("/fetch", methods=["POST"], access=AUTHENTICATED)
        def fetch(cls, value: str, user: dict = None) -> dict[str, object]:
            """Return the native injected caller for a harmless local value."""
            return {"value": value, "user": user}

    seen = []
    ToolActor.use(lambda tx: seen.append(tx) or tx, on="inbox")
    owner = current_execution.get()
    # 1. Both trusted internal and authenticated execution preserve metadata.
    for user in (None, {"user_id": 1, "role": "user"}):
        ctx = SimpleNamespace(deps=AgentDeps(user, "synthetic-agent", owner))
        result = await _route_tool_call(
            ctx, ToolActor.addr, "fetch", {"value": "synthetic"},
        )
        assert json.loads(result) == {"value": "synthetic", "user": user}
        assert "user" in seen[-1].meta and seen[-1].meta["user"] == user
        assert seen[-1].source == f"ttx/{owner.id}"
    # 2. An empty external identity is not the trusted None execution case.
    ctx = SimpleNamespace(deps=AgentDeps({}, "synthetic-agent", owner))
    with pytest.raises(ModelRetry, match="Access denied"):
        await _route_tool_call(ctx, ToolActor.addr, "fetch", {"value": "deny"})


@pytest.mark.asyncio
async def test_internal_tool_crud_retains_native_none_semantics(
    fresh_matrix, memory_storage,
):
    """Keep trusted internal CRUD and its explicit None caller metadata."""
    # 0. Register disposable storage under the actual target actor.
    class Record(ActorModel):
        """Provide a harmless storable native CRUD target."""

        __tablename__ = "internal_tool_records"
        __storable__ = True
        __access__ = {"read": AUTHENTICATED, "create": AUTHENTICATED}
        name: str = "synthetic"

    register_model(Record, storage=memory_storage)
    saved = Record.create(Record())
    ctx = SimpleNamespace(deps=AgentDeps(
        None, "synthetic-agent", current_execution.get(),
    ))
    # 1. The native policy keeps internal None separate from ingress identity.
    result = json.loads(await _route_tool_call(
        ctx, Record.addr, "get", {"id": saved.id},
    ))
    assert result["id"] == saved.id and result["name"] == "synthetic"


# Changelog (Python has no native block-comment syntax).
# - 2026-11-12: Use mandatory TTX dependencies/context and retain native caller,
#   anonymous-denial and internal CRUD boundaries without swallowing failures.
