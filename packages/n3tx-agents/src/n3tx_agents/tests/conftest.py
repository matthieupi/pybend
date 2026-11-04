"""Shared fixtures for agent system tests."""

from queue import Empty
from typing import ClassVar

import pytest
from pydantic_ai import models

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import NEVER, OWNER
from n3tx_core.models.ref import public_id_url
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import registered_models, register_model
from n3tx_threads import TTX


USER = {"user_id": 1, "role": "user"}


class HistoryOwner(ActorModel):
    """Synthetic saved entity whose native policy owns conversation access."""

    __tablename__ = "history_owners"
    __storable__ = True
    __access__: ClassVar[dict] = {
        "*": NEVER, "read": OWNER, "update": OWNER,
    }
    user_owner: int = 1
    name: str = "Synthetic owner"


@pytest.fixture(autouse=True)
def reset_actor_state(monkeypatch):
    """Isolate actor/matrix state between tests."""
    # 0. Save and reset shared actor registrations.
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()
    saved_models = dict(registered_models)
    saved_storages = {
        model: getattr(model, "storage", None)
        for model in (*saved_models.values(), TTX, HistoryOwner)
    }
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)
    Actor.__matrix__ = None
    Actor.__children__ = {}
    Matrix.__children__ = {}
    registered_models.clear()

    try:
        yield
    finally:
        # 1. Restore the surrounding suite's registrations and model storage.
        restored_models = set(saved_storages) | set(registered_models.values())
        storages = {
            getattr(model, "storage", None)
            for model in restored_models
        }
        storages.difference_update(saved_storages.values())
        storages.discard(None)
        for storage in storages:
            pool = getattr(storage, "_pool", None)
            if pool is None:
                continue
            while True:
                try:
                    connection = pool.get_nowait()
                except Empty:
                    break
                connection.rollback()
                connection.close()
        for model in restored_models:
            if hasattr(model, "set_storage"):
                model.set_storage(saved_storages.get(model))
        Actor.__matrix__ = saved_matrix
        Actor.__children__ = saved_children
        Matrix.__children__ = saved_matrix_children
        registered_models.clear()
        registered_models.update(saved_models)


@pytest.fixture
def fresh_matrix(tmp_path):
    """Create a Matrix with only canonical TTX history infrastructure."""
    # 0. Register canonical snapshots on disposable file-backed storage.
    matrix = Matrix()
    storage = SQLiteStorage(str(tmp_path / 'threads.db'))
    register_model(TTX, storage=storage)
    matrix._children[TTX.__addr__] = TTX
    try:
        yield matrix
    finally:
        # 1. Release only this fixture's pooled SQLite connections.
        while True:
            try:
                connection = storage._pool.get_nowait()
            except Empty:
                break
            connection.rollback()
            connection.close()


@pytest.fixture
def agent_context(fresh_matrix):
    """Supply real saved scope and trusted synthetic caller inputs."""
    # 0. Register a policy-bearing parent, not a private history access bypass.
    register_model(HistoryOwner, storage=TTX.storage)
    fresh_matrix._children[HistoryOwner.__addr__] = HistoryOwner
    owner = HistoryOwner.create(HistoryOwner())
    return {
        "scope": public_id_url(owner.id, target_cls=HistoryOwner),
        "user": dict(USER),
    }


@pytest.fixture
def memory_storage():
    """In-memory SQLite storage for tests."""
    return SQLiteStorage(':memory:')


# Changelog (Python has no native block-comment syntax).
# - 2026-11-04: Register only TTX and provide parent-authorized saved scope;
#   forbid provider requests and restore shared registration/storage state.
#   Restore and dispose bindings for both initial and final registry models.
# - 2026-11-02: Register extracted Thread and TXRecord in native test routing.
