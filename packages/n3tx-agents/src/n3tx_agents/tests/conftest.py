"""Shared fixtures for agent system tests."""

import pytest

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import registered_models, register_model
from n3tx_agents.thread import Thread


@pytest.fixture(autouse=True)
def reset_actor_state():
    """Isolate actor/matrix state between tests."""
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()
    saved_models = dict(registered_models)

    Actor.__matrix__ = None
    Actor.__children__ = {}
    Matrix.__children__ = {}
    registered_models.clear()

    yield

    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_children
    Matrix.__children__ = saved_matrix_children
    registered_models.clear()
    registered_models.update(saved_models)


@pytest.fixture
def fresh_matrix(tmp_path):
    """Create an isolated Matrix instance with agent thread routing."""
    matrix = Matrix()
    storage = SQLiteStorage(str(tmp_path / 'threads.db'))
    register_model(Thread, storage=storage)
    matrix._children[Thread.__addr__] = Thread
    return matrix


@pytest.fixture
def memory_storage():
    """In-memory SQLite storage for tests."""
    return SQLiteStorage(':memory:')
