import logging
from typing import ClassVar

from pydantic import Field
from helpers import auth_header
from n3tx_actors.actor import Actor
from n3tx_actors.models.actor_model import ActorModel
from examples.grants.models import Grant


def test_delete_grant_does_not_emit_lifecycle_response_errors(client, alice_token, seed_data, caplog):
    grant = seed_data["grants"][0]

    class Runs(ActorModel):
        __tablename__: ClassVar[str] = "runs"
        __storable__: ClassVar[bool] = False
        marker: str = Field(default="")

        @classmethod
        def LIFECYCLE(cls, data, tx):
            return None

    root = Actor.root()
    original_subscribers = list(Grant._subscribers)
    Grant._subscribers = ["runs"]

    try:
        if root and not root.has("runs"):
            root.register(Runs)

        with caplog.at_level(logging.ERROR):
            response = client.delete(f"/grants/{grant.id}", headers=auth_header(alice_token))
    finally:
        Grant._subscribers = original_subscribers

    assert response.status_code == 200
    assert "Unhandled LIFECYCLE_RESPONSE" not in caplog.text
    assert "Cannot route to self at matrix" not in caplog.text
