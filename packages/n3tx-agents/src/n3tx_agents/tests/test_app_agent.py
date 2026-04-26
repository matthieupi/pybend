"""Tests for framework bootstrap app-agent provisioning."""

import pytest
from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.app import create_app
from n3tx_core.models.proto_model import generate_join_model
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import register_model, registered_models
from n3tx_agents.actor import AgentActor
from n3tx_agents.app_agent import provision_app_agent
from n3tx_agents.tool_model import AgentTool

pytestmark = pytest.mark.unit


class GrantTool(ActorModel):
    __tablename__ = 'grants'
    __storable__ = False
    name: str = Field(default='grants')


class SourceTool(ActorModel):
    __tablename__ = 'sources'
    __storable__ = False
    name: str = Field(default='sources')


class WebToolProvider(ActorModel):
    __tablename__ = 'web_tools'
    __storable__ = False
    name: str = Field(default='web_tools')


def _register_agent_models(storage):
    register_model(GrantTool, storage=storage)
    register_model(SourceTool, storage=storage)
    register_model(WebToolProvider, storage=storage)
    register_model(AgentTool, storage=storage)
    register_model(AgentActor, storage=storage)
    join_cls = generate_join_model(AgentActor, AgentTool)
    register_model(join_cls, storage=storage)
    return join_cls


def _assistant_config(tools=None):
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
    def test_creates_and_reconciles_agent(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'provision.db'))
        join_cls = _register_agent_models(storage)

        created = provision_app_agent(_assistant_config(), registered_models)
        assert created.system_key == 'assistant'
        assert created.name == 'Assistant'

        rows = join_cls.list(sql_filter=('agentactor_id = ?', [created.id]))
        links = rows.get('data', rows) if isinstance(rows, dict) else rows
        assert sorted(row.target for row in links) == ['grants', 'sources']

        updated = provision_app_agent(
            _assistant_config(tools=[{'target': 'web_tools', 'description': 'Web ops'}]),
            registered_models,
        )
        assert updated.id == created.id

        agents = AgentActor.list()
        agent_rows = agents.get('data', agents) if isinstance(agents, dict) else agents
        assert len(agent_rows) == 1

        rows = join_cls.list(sql_filter=('agentactor_id = ?', [created.id]))
        links = rows.get('data', rows) if isinstance(rows, dict) else rows
        assert [row.target for row in links] == ['web_tools']

    def test_rejects_unknown_tool_target(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'invalid-target.db'))
        _register_agent_models(storage)

        with pytest.raises(RuntimeError, match='unknown tool targets'):
            provision_app_agent(
                _assistant_config(tools=[{'target': 'organizations', 'description': 'Org access'}]),
                registered_models,
            )

    def test_create_app_bootstrap_provisions_agent(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'app-agent.db'))
        app = create_app(
            models=[GrantTool, SourceTool, WebToolProvider, AgentTool, AgentActor],
            join_models=[(AgentActor, AgentTool)],
            storage=storage,
            app_agent=_assistant_config(),
            name='Provision Test',
        )

        assert app is not None

        agents = AgentActor.list()
        rows = agents.get('data', agents) if isinstance(agents, dict) else agents
        assert len(rows) == 1
        assert rows[0].system_key == 'assistant'
