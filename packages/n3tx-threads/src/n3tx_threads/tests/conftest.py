"""Isolate native actor and registration state for provider-free threads."""

import pytest

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_core.utils.registrar import registered_models


@pytest.fixture(autouse=True)
def reset_actor_state():
    """Restore the caller's actor root and registry after each test."""
    # 0. Give each test a private actor root and registration map.
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()
    saved_models = dict(registered_models)
    Actor.__matrix__ = None
    Actor.__children__ = {}
    Matrix.__children__ = {}
    registered_models.clear()
    try:
        yield
    finally:
        # 1. Restore surrounding suites without retaining disposable actors.
        Actor.__matrix__ = saved_matrix
        Actor.__children__ = saved_children
        Matrix.__children__ = saved_matrix_children
        registered_models.clear()
        registered_models.update(saved_models)


# Changelog (Python has no native block-comment syntax).
# - 2026-11-02: Isolate threads without importing agents or its SDK.
