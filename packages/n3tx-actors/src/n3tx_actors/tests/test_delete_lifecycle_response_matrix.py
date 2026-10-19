import logging
from typing import ClassVar

import pytest
from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.tx import TX


@pytest.mark.asyncio
async def test_actor_model_drops_lifecycle_response_instead_of_bubbling_to_matrix(fresh_matrix, caplog):
    class Run(ActorModel):
        __tablename__: ClassVar[str] = "runs"
        __storable__: ClassVar[bool] = False
        name: str = Field(default="")

    lifecycle_reply = TX(
        name="LIFECYCLE_RESPONSE",
        source="runs/runs",
        target="runs",
        data={},
        meta={"req": "delete-grant-req"},
    )

    with caplog.at_level(logging.ERROR):
        await Run.inbox(lifecycle_reply)

    assert "Unhandled LIFECYCLE_RESPONSE" not in caplog.text
    assert "Cannot route to self at matrix" not in caplog.text
