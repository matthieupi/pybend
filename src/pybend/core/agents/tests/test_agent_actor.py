"""Tests for AgentActor — the dynamic agent class."""

import json
import pytest
from pydantic import Field

from pybend.core.actors.actor import Actor
from pybend.core.actors.matrix import Matrix
from pybend.core.models.actor_model import ActorModel
from pybend.core.storage.sqlite_storage import SQLiteStorage
from pybend.core.utils.decorators import expose_route
from pybend.core.utils.registrar import register_model
from pybend.core.agents.actor import AgentActor

pytestmark = pytest.mark.unit


class TestAgentActorClass:
    """Tests for AgentActor class structure."""

    def test_has_agent_mixin(self, fresh_matrix):
        from pybend.core.agents.mixin import AgentMixin
        assert issubclass(AgentActor, AgentMixin)

    def test_has_storable_mixin(self, fresh_matrix):
        from pybend.core.models.storable_mixin import StorableMixin
        assert issubclass(AgentActor, StorableMixin)

    def test_is_actor_model(self, fresh_matrix):
        assert issubclass(AgentActor, ActorModel)

    def test_tablename(self, fresh_matrix):
        assert AgentActor.__tablename__ == 'agents'

    def test_fields(self, fresh_matrix):
        schema = AgentActor.model_json_schema()
        props = schema.get('properties', {})
        assert 'name' in props
        assert 'prompt' in props
        assert 'tools' in props
        assert 'llm' in props
        assert 'constraints' in props

    def test_mro_order(self, fresh_matrix):
        from pybend.core.agents.mixin import AgentMixin
        mro = [cls.__name__ for cls in AgentActor.__mro__]
        # AgentMixin should be before ActorModel
        assert mro.index('AgentMixin') < mro.index('ActorModel')


class TestAgentActorInstance:
    """Tests for creating AgentActor instances."""

    def test_create_instance(self, fresh_matrix):
        agent = AgentActor(
            name='Test Agent',
            prompt='You are a test agent.',
            tools=['web_tools'],
            addr='agents/1',
        )
        assert agent.name == 'Test Agent'
        assert agent.prompt == 'You are a test agent.'
        assert agent.tools == ['web_tools']
        assert agent.llm == 'ollama:llama3.1'
        assert agent.constraints == {}

    def test_custom_llm(self, fresh_matrix):
        agent = AgentActor(
            name='Custom LLM',
            prompt='test',
            llm='anthropic:claude-sonnet-4-5-20250929',
            addr='agents/2',
        )
        assert agent.llm == 'anthropic:claude-sonnet-4-5-20250929'

    def test_custom_constraints(self, fresh_matrix):
        agent = AgentActor(
            name='Constrained',
            prompt='test',
            constraints={'max_iterations': 10},
            addr='agents/3',
        )
        assert agent.constraints == {'max_iterations': 10}

    def test_has_run_method(self, fresh_matrix):
        agent = AgentActor(name='Test', prompt='test', addr='agents/4')
        assert hasattr(agent, 'run')
        assert hasattr(agent.run, '__endpoint__')  # @expose_route

    def test_has_agent_run_method(self, fresh_matrix):
        agent = AgentActor(name='Test', prompt='test', addr='agents/5')
        assert hasattr(agent, 'agent_run')


class TestAgentActorCRUD:
    """Tests for AgentActor storage operations."""

    def test_create_and_get(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentActor, storage=storage)
        storage.create_table(AgentActor)

        agent = AgentActor(
            name='Stored Agent',
            prompt='You help find grants.',
            tools=['grants', 'web_tools'],
            llm='ollama:llama3.1',
            constraints={'max_iterations': 20},
        )
        created = AgentActor.create(agent)
        assert created.id is not None

        fetched = AgentActor.get(created.id)
        assert fetched.name == 'Stored Agent'
        assert fetched.prompt == 'You help find grants.'
        assert fetched.tools == ['grants', 'web_tools']
        assert fetched.llm == 'ollama:llama3.1'
        assert fetched.constraints == {'max_iterations': 20}

    def test_list_agents(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentActor, storage=storage)
        storage.create_table(AgentActor)

        AgentActor.create(AgentActor(name='Agent 1', prompt='p1'))
        AgentActor.create(AgentActor(name='Agent 2', prompt='p2'))

        result = AgentActor.list()
        records = result['data'] if isinstance(result, dict) else result
        assert len(records) == 2

    def test_update_agent(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentActor, storage=storage)
        storage.create_table(AgentActor)

        agent = AgentActor.create(
            AgentActor(name='Original', prompt='original prompt')
        )
        updated = AgentActor.update(agent.id, {'prompt': 'updated prompt'})
        assert updated.prompt == 'updated prompt'

    def test_delete_agent(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentActor, storage=storage)
        storage.create_table(AgentActor)

        agent = AgentActor.create(AgentActor(name='ToDelete', prompt='bye'))
        AgentActor.delete(agent.id)
        assert AgentActor.get(agent.id) is None


class TestAgentActorRun:
    """Tests for AgentActor.run() — the LLM execution endpoint."""

    @pytest.mark.asyncio
    async def test_run_basic(self, fresh_matrix, tmp_path):
        """run() calls agent_run() with instance fields."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentActor, storage=storage)
        storage.create_table(AgentActor)

        agent = AgentActor.create(AgentActor(
            name='Runner',
            prompt='You are a helpful assistant.',
            tools=[],
            llm='test',  # will be overridden
        ))
        # Fetch from DB to get a proper instance
        agent = AgentActor.get(agent.id)

        result_str = await agent.run(
            task='Hello, world!',
            llm=TestModel(call_tools=[]),
        )
        result = json.loads(result_str)
        assert 'answer' in result
        assert 'usage' in result
        assert 'messages' in result

    @pytest.mark.asyncio
    async def test_run_with_tools(self, fresh_matrix, tmp_path):
        """run() discovers tools from actor addresses."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'agents.db'))

        class Grant(ActorModel):
            __tablename__ = 'grants'
            __storable__ = True
            title: str = Field(default='')

        register_model(Grant, storage=storage)
        register_model(AgentActor, storage=storage)
        storage.create_table(Grant)
        storage.create_table(AgentActor)

        agent = AgentActor.create(AgentActor(
            name='Grant Scanner',
            prompt='List all grants.',
            tools=['grants'],
        ))
        agent = AgentActor.get(agent.id)

        result_str = await agent.run(
            task='Find grants',
            llm=TestModel(call_tools=['grants_list']),
        )
        result = json.loads(result_str)
        assert 'answer' in result
        assert result['usage']['requests'] >= 1


class TestAgentActorSchema:
    """Tests for schema extension on AgentActor."""

    def test_schema_has_agent_section(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentActor, storage=storage)

        schema = AgentActor.schema()
        assert 'agent' in schema
        assert schema['agent']['enabled'] is True
        assert 'run_endpoint' in schema['agent']
        assert '/agents/{id}/run' == schema['agent']['run_endpoint']

    def test_schema_has_run_method(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentActor, storage=storage)

        schema = AgentActor.schema()
        assert 'run' in schema.get('methods', {})

    def test_non_agent_model_no_agent_section(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Plain(ActorModel):
            __tablename__ = 'plain'
            __storable__ = True
            name: str = Field(default='')

        register_model(Plain, storage=storage)

        schema = Plain.schema()
        assert 'agent' not in schema

    def test_agent_mixin_model_has_agent_section(self, fresh_matrix):
        """Models with __agent__=True (but not AgentActor) get enabled but no run_endpoint."""

        class Agentic(ActorModel):
            __tablename__ = 'agentic'
            __storable__ = False
            __agent__ = True

        schema = Agentic.schema()
        assert 'agent' in schema
        assert schema['agent']['enabled'] is True
        # Not an AgentActor subclass, so no run_endpoint
        assert 'run_endpoint' not in schema['agent']
