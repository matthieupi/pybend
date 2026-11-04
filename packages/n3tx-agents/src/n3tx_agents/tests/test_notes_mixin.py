"""Provider-free generated agent tools over the extracted Notes capability."""

import json

import pytest
from pydantic_ai import Agent as PydanticAgent, models
from pydantic_ai.messages import ModelRequest, ToolReturnPart
from pydantic_ai.models.test import TestModel

from n3tx_agents import AgentDeps, discover_tools, make_tool
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AUTHENTICATED, NEVER, OWNER
from n3tx_core.models.ref import public_id_url
from n3tx_core.utils.registrar import register_model
from n3tx_threads import TTX

from .conftest import USER as WRITER


pytestmark = pytest.mark.unit
ADMIN = {"user_id": 3, "role": "admin"}


class Notebook(ActorModel):
    """Expose lean notes under the actual parent's native policy."""

    __tablename__ = "agent_notebooks"
    __storable__ = True
    __notes__ = True
    __access__ = {"*": NEVER, "read": AUTHENTICATED, "update": OWNER}
    user_owner: int = 1


@pytest.fixture
def notes_runtime(fresh_matrix):
    """Register a real Notes host without borrowing locked package fixtures."""
    # 0. Share the disposable native storage and Matrix infrastructure.
    register_model(Notebook, storage=TTX.storage)
    fresh_matrix._children[Notebook.__addr__] = Notebook
    return fresh_matrix


@pytest.mark.asyncio
async def test_discovered_testmodel_tools_note_and_admin_read(
    notes_runtime, monkeypatch,
):
    """Use generated tools with native actor caller metadata and TestModel."""
    # 0. Discover real signatures without exposing the injected user argument.
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)
    root = notes_runtime
    owner = Notebook.create(Notebook())
    specs = {
        spec.method_name: spec
        for spec in discover_tools([Notebook.__addr__], root)
        if spec.method_name in {"NOTE", "NOTES"}
    }
    assert set(specs) == {"NOTE", "NOTES"}
    for spec in specs.values():
        assert "user" not in spec.parameters.get("properties", {})

    class FixedNotesModel(TestModel):
        """Supply valid synthetic IDs through the native TestModel loop."""

        def gen_tool_args(self, tool_def):
            """Generate only the discovered business arguments."""
            if tool_def.name == specs["NOTE"].tool_name:
                return {"id": owner.id, "message": "agent tool note"}
            assert tool_def.name == specs["NOTES"].tool_name
            return {"id": owner.id}
    # 1. Commit the writer's note before a separate admin reader tool runs.
    returns = {}
    for action, user in (("NOTE", WRITER), ("NOTES", ADMIN)):
        spec = specs[action]
        agent = PydanticAgent(
            FixedNotesModel(call_tools=[spec.tool_name]),
            tools=[make_tool(spec)], deps_type=AgentDeps, retries=0,
        )
        result = await agent.run(
            "Synthetic notes request",
            deps=AgentDeps(user=user, agent_addr="notes_test_agent"),
        )
        parts = [
            part for message in result.all_messages()
            if isinstance(message, ModelRequest)
            for part in message.parts if isinstance(part, ToolReturnPart)
        ]
        assert len(parts) == 1
        assert parts[0].tool_name == spec.tool_name
        returns[action] = json.loads(parts[0].content)
    # 2. Generated tools use the same saved notes and native admin read policy.
    saved = returns["NOTE"]
    assert saved["target"] == public_id_url(owner.id, target_cls=Notebook)
    assert saved["user_owner"] == WRITER["user_id"]
    assert saved["data"] == {"payload": "agent tool note"}
    assert [row["id"] for row in returns["NOTES"]] == [saved["id"]]
    assert "notes" not in Notebook.model_fields


# Changelog (Python has no native block-comment syntax).
# - 2026-11-04: Use NOTE(message)/NOTES and parent-authorized TTX results;
#   own integration fixtures independently of the locked threads tests.
# - 2026-11-02: Keep SDK tool integration separate from generic Notes tests.
