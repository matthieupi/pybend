"""Isolate canonical agent storage and native actor state between tests."""

from queue import Empty

import pytest
from pydantic_ai import models

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_agents.history import create_history
from n3tx_agents.threaded_mixin import current_execution
from n3tx_core.models import proto_dump
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import registered_models, register_model
from n3tx_threads import TTX


@pytest.fixture(autouse=True)
def reset_actor_state(monkeypatch):
    """Restore actor routing, registries and schema caches after each test."""
    # 0. Preserve surrounding suites without enabling real provider requests.
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()
    registries = (
        registered_models, ProtoModel._schema_cache,
        proto_dump._schema_url_cache, proto_dump._instance_url_cache,
    )
    snapshots = [dict(registry) for registry in registries]
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)

    Actor.__matrix__ = None
    Actor.__children__ = {}
    Matrix.__children__ = {}
    registered_models.clear()

    try:
        yield
    finally:
        # 1. Discard disposable registrations and restore prior native state.
        Actor.__matrix__ = saved_matrix
        Actor.__children__ = saved_children
        Matrix.__children__ = saved_matrix_children
        for registry, snapshot in zip(registries, snapshots):
            registry.clear()
            registry.update(snapshot)


@pytest.fixture
def fresh_matrix(memory_storage, monkeypatch):
    """Register canonical TTX routing against disposable native storage."""
    # 0. Register only the current history model, never retired containers.
    matrix = Matrix()
    monkeypatch.setattr(TTX, "storage", None)
    monkeypatch.setattr(TTX, "__matrix__", matrix)
    monkeypatch.setattr(TTX, "_subscribers", [])
    register_model(TTX, storage=memory_storage)
    matrix.register(TTX)
    owner = create_history(Actor(addr="synthetic-test-agent"), user=None)
    token = current_execution.set(owner)
    try:
        yield matrix
    finally:
        current_execution.reset(token)


@pytest.fixture
def memory_storage(tmp_path):
    """Keep the existing fixture name while using safe file-backed SQLite."""
    # 0. Native migration and pooled connections must share the same database.
    storage = SQLiteStorage(str(tmp_path / "agents.sqlite3"), pool_size=1)
    try:
        yield storage
    finally:
        # 1. Release owned handles before pytest removes temporary files.
        while True:
            try:
                connection = storage._pool.get_nowait()
            except Empty:
                break
            connection.rollback()
            connection.close()


# Changelog (Python has no native block-comment syntax).
# - 2026-11-12: Replace retired registration with TTX and isolate disposable
#   SQLite, provider guards and native routing/schema state across suites.
