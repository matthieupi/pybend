"""Shared fixtures for agent system tests."""

import pytest

from pybend.core.actors.actor import Actor
from pybend.core.actors.matrix import Matrix
from pybend.core.storage.sqlite_storage import SQLiteStorage
from pybend.core.utils.registrar import registered_models


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
def fresh_matrix():
    """Create an isolated Matrix instance."""
    return Matrix()


@pytest.fixture
def memory_storage():
    """In-memory SQLite storage for tests."""
    return SQLiteStorage(':memory:')
