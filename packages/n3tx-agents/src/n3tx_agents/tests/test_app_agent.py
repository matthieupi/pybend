"""Tests for framework bootstrap app-agent provisioning."""

from queue import Empty

import pytest
from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.app import N3TXApp, create_app
from n3tx_core.api.routes_fastapi import router
from n3tx_core.authorize import auth
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import register_model, registered_models
from n3tx_agents.actor import AgentActor
from n3tx_agents.app_agent import provision_app_agent
from n3tx_agents.tool_model import AgentTool
from n3tx_threads import Thread, TTX

pytestmark = pytest.mark.unit


class GrantTool(ActorModel):
    """Registered non-storable grant tool provider."""

    __tablename__ = 'grants'
    __storable__ = False
    name: str = Field(default='grants')


class SourceTool(ActorModel):
    """Registered non-storable source tool provider."""

    __tablename__ = 'sources'
    __storable__ = False
    name: str = Field(default='sources')


class WebToolProvider(ActorModel):
    """Registered non-storable web tool provider."""

    __tablename__ = 'web_tools'
    __storable__ = False
    name: str = Field(default='web_tools')


def _register_agent_models(storage):
    """Bind provisioning models to disposable native storage."""
    # 0. Register configuration and tool targets without executing a model.
    register_model(GrantTool, storage=storage)
    register_model(SourceTool, storage=storage)
    register_model(WebToolProvider, storage=storage)
    register_model(AgentTool, storage=storage)
    register_model(AgentActor, storage=storage)


def _assistant_config(tools=None):
    """Return synthetic stored-assistant configuration with native targets."""
    return {
        'key': 'assistant',
        'name': 'Assistant',
        'prompt': 'Help with grants.',
        'llm': 'test',
        'constraints': {'max_iterations': 5},
        'tools': tools or [
            {'target': 'grants', 'description': 'Grant CRUD'},
            {'target': 'sources', 'description': 'Source listing'},
        ],
        'featured': True,
    }


class TestProvisionAppAgent:
    """Provision and reconcile stored assistants without provider requests."""

    def test_creates_and_reconciles_agent(self, fresh_matrix, tmp_path):
        """Reuse one assistant while replacing its configured tool links."""
        # 0. Provision the initial native configuration.
        storage = SQLiteStorage(str(tmp_path / 'provision.db'))
        _register_agent_models(storage)

        created = provision_app_agent(_assistant_config(), registered_models)
        assert created.system_key == 'assistant'
        assert created.name == 'Assistant'

        assert sorted(tool.target for tool in created.tools) == [
            'grants', 'sources',
        ]

        updated = provision_app_agent(
            _assistant_config(tools=[{
                'target': 'web_tools', 'description': 'Web ops',
            }]),
            registered_models,
        )
        assert updated.id == created.id

        agents = AgentActor.list()
        agent_rows = (
            agents.get('data', agents) if isinstance(agents, dict) else agents
        )
        assert len(agent_rows) == 1

        assert [tool.target for tool in updated.tools] == ['web_tools']

    def test_rejects_unknown_tool_target(self, fresh_matrix, tmp_path):
        """Refuse unregistered tool targets during provisioning."""
        # 0. Use only disposable model registrations.
        storage = SQLiteStorage(str(tmp_path / 'invalid-target.db'))
        _register_agent_models(storage)

        with pytest.raises(RuntimeError, match='unknown tool targets'):
            provision_app_agent(
                _assistant_config(tools=[{
                    'target': 'organizations', 'description': 'Org access',
                }]),
                registered_models,
            )

    def test_create_app_bootstrap_provisions_agent(self, bootstrap_state):
        """Bootstrap one assistant with canonical TTX infrastructure."""
        _, storage = bootstrap_state
        # 0. Build the real framework application with a synthetic assistant.
        app = create_app(
            models=[
                GrantTool, SourceTool, WebToolProvider, AgentTool, AgentActor,
            ],
            storage=storage,
            app_agent=_assistant_config(),
            name='Provision Test',
            static_dir=None, ssr='off', remotes={}, debug=False,
        )

        assert app is not None

        agents = AgentActor.list()
        rows = (
            agents.get('data', agents) if isinstance(agents, dict) else agents
        )
        assert len(rows) == 1
        assert rows[0].system_key == 'assistant'
        assert registered_models['tx_records'] is TTX
        assert list(registered_models.values()).count(TTX) == 1
        assert Thread not in registered_models.values()
        assert all(
            model.__name__ != 'TXRecord'
            for model in registered_models.values()
        )
        assert Thread.storage is TTX.storage is storage
        assert 'threads' not in _tables(storage)


def _tables(storage):
    """Inspect table names only in disposable test storage."""
    with storage._connection() as connection:
        return {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'",
        )}


@pytest.fixture
def bootstrap_state(tmp_path, monkeypatch):
    """Isolate bootstrap router, schemas, auth and native model storage."""
    # 0. Save process globals before constructing any native app.
    saved_routes = list(router.routes)
    saved_cache = dict(ProtoModel._schema_cache)
    saved_auth = (auth._jwt_secret, auth._jwt_expiry_hours)
    storage = SQLiteStorage(str(tmp_path / 'bootstrap.sqlite3'))
    for model in (AgentActor, AgentTool, TTX):
        monkeypatch.setattr(model, 'storage', getattr(model, 'storage', None))
    router.routes[:] = []
    ProtoModel._schema_cache.clear()
    try:
        yield tmp_path, storage
    finally:
        # 1. Close owned storage and restore the surrounding route/cache state.
        while True:
            try:
                connection = storage._pool.get_nowait()
            except Empty:
                break
            connection.rollback()
            connection.close()
        router.routes[:] = saved_routes
        ProtoModel._schema_cache.clear()
        ProtoModel._schema_cache.update(saved_cache)
        auth._jwt_secret, auth._jwt_expiry_hours = saved_auth


def test_unrelated_app_does_not_activate_history(bootstrap_state):
    """Agent imports and retired capture flags do not create history tables."""

    class Plain(ActorModel):
        """Ordinary saved model with an ignored historical capture flag."""

        __tablename__ = 'plain_bootstrap_models'
        __storable__ = True
        __thread_roots__ = frozenset({'ping'})
    # 0. Build without selecting any agent or entry capability.
    _, storage = bootstrap_state
    create_app(
        models=[Plain], storage=storage, static_dir=None,
        ssr='off', remotes={}, debug=False,
    )
    # 1. Optional imports cannot activate history for an unrelated app.
    assert 'tx_records' not in registered_models
    assert not {'threads', 'tx_records'} & _tables(storage)


def test_repeated_explicit_ttx_keeps_first_storage(bootstrap_state, tmp_path):
    """Deduplicate explicit TTX while preserving its first storage override."""
    # 0. Select TTX twice through the supported native builder API.
    _, storage = bootstrap_state
    first = SQLiteStorage(str(tmp_path / 'first-history.sqlite3'))
    try:
        builder = N3TXApp(
            storage=storage, ssr='off', remotes={},
        )
        builder.model(TTX, storage=first).model(TTX, storage=storage)
        builder.build()
        # 1. Canonical identity has one owner and keeps the first binding.
        assert list(registered_models.values()).count(TTX) == 1
        assert TTX.storage is first and Thread.storage is first
        assert 'tx_records' in _tables(first)
        assert 'tx_records' not in _tables(storage)
    finally:
        # 2. Release the independent explicitly overridden test storage.
        while True:
            try:
                connection = first._pool.get_nowait()
            except Empty:
                break
            connection.rollback()
            connection.close()


@pytest.mark.parametrize('kind', ['semantic', 'subclass', 'conflict'])
def test_bootstrap_refuses_noncanonical_history(bootstrap_state, kind):
    """Reject competing history registrations before any table is created."""

    class Semantic(Thread, auto_register=False):
        """Semantic root subtype that must not own a separate registration."""

    class Conflict(ActorModel):
        """Unrelated model attempting to own the canonical history table."""

        __tablename__ = 'tx_records'
        __storable__ = True
    # 0. Activate history explicitly alongside the invalid selected model.
    _, storage = bootstrap_state
    selected = {'semantic': Thread, 'subclass': Semantic, 'conflict': Conflict}
    with pytest.raises(ValueError, match='register TTX only'):
        create_app(
            models=[TTX, selected[kind]], storage=storage,
            static_dir=None, ssr='off', remotes={},
        )
    # 1. Invalid selection fails before registration can alter native tables.
    assert not {'threads', 'tx_records'} & _tables(storage)


# Changelog (Python has no block-comment syntax).
# - 2026-11-04: Verify canonical TTX bootstrap and unchanged provisioning;
#   reject semantic/table conflicts and preserve explicit storage ownership.
