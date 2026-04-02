import logging

import pytest

from n3tx_actors.tx import TX
from n3tx_agents.actor import AgentActor


@pytest.mark.asyncio
async def test_agent_actor_drops_unhandled_lifecycle_response_without_error_log(fresh_matrix, caplog):
    agent = AgentActor(name="Delete Watcher", prompt="watch deletes", addr="agents/1")

    lifecycle_reply = TX(
        name="LIFECYCLE_RESPONSE",
        source="runs/runs",
        target=agent.addr,
        data={},
        meta={"req": "grant-delete"},
    )

    with caplog.at_level(logging.ERROR):
        await agent.inbox(lifecycle_reply)

    assert "Unhandled LIFECYCLE_RESPONSE" not in caplog.text
