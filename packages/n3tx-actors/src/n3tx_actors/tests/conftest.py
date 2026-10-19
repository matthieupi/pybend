"""Shared fixtures for actor system tests."""

from contextlib import contextmanager

import pytest

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix


@contextmanager
def mock_method(instance, name, replacement):
    """Temporarily replace a method on a Pydantic BaseModel instance.

    Pydantic's __setattr__/__delattr__ prevent normal mock patching.
    This uses object.__setattr__/delattr__ to bypass the protection.
    """
    object.__setattr__(instance, name, replacement)
    try:
        yield replacement
    finally:
        object.__delattr__(instance, name)


@pytest.fixture(autouse=True)
def reset_actor_state():
    """Save and restore Actor/Matrix class-level state between tests.

    Actor.__matrix__, Actor.__children__, and any subclass registrations
    must be isolated per test to prevent cross-contamination.
    Also saves/restores fullmethod descriptors that tests may monkey-patch.
    """
    saved_matrix = Actor.__matrix__
    saved_children = Actor.__children__.copy()
    saved_matrix_children = Matrix.__children__.copy()
    saved_send = Actor.__dict__['send']
    saved_inbox = Actor.__dict__['inbox']
    saved_handler = Actor.__dict__['handler']

    # Start clean
    Actor.__matrix__ = None
    Actor.__children__ = {}
    Matrix.__children__ = {}

    yield

    Actor.__matrix__ = saved_matrix
    Actor.__children__ = saved_children
    Matrix.__children__ = saved_matrix_children
    Actor.send = saved_send
    Actor.inbox = saved_inbox
    Actor.handler = saved_handler


@pytest.fixture
def fresh_matrix():
    """Create an isolated Matrix instance registered as root."""
    return Matrix()


def make_tx(name='TEST', source='client', target='target', data=None, meta=None):
    """Shorthand TX constructor for tests."""
    from n3tx_actors.tx import TX
    return TX(name=name, source=source, target=target,
              data=data or {}, meta=meta or {})
