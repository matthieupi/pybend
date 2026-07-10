"""Tests for AgentActor — the dynamic agent class."""

import json
import pytest
from pydantic import Field

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.registrar import register_model
from n3tx_agents.agent import Agent, PreparedCall
from n3tx_agents.actor import AgentActor
from n3tx_agents.tool_model import AgentTool

pytestmark = pytest.mark.unit


class TestAgentActorClass:
    """Tests for AgentActor class structure."""

    def test_has_agent_mixin(self, fresh_matrix):
        from n3tx_agents.mixin import AgentMixin
        assert issubclass(AgentActor, AgentMixin)

    def test_has_storable_mixin(self, fresh_matrix):
        from n3tx_core.models.storable_mixin import StorableMixin
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
        from n3tx_agents.mixin import AgentMixin
        mro = [cls.__name__ for cls in AgentActor.__mro__]
        # AgentMixin should be before ActorModel
        assert mro.index('AgentMixin') < mro.index('ActorModel')


class TestAgentToolModel:
    """Tests for the AgentTool model."""

    def test_tablename(self, fresh_matrix):
        assert AgentTool.__tablename__ == 'agent_tools'

    def test_is_actor_model(self, fresh_matrix):
        assert issubclass(AgentTool, ActorModel)

    def test_create_instance(self, fresh_matrix):
        tool = AgentTool(target='grants', description='Grant CRUD')
        assert tool.target == 'grants'
        assert tool.description == 'Grant CRUD'

    def test_crud(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'tools.db'))
        register_model(AgentTool, storage=storage)
        storage.create_table(AgentTool)

        tool = AgentTool.create(AgentTool(target='grants', description='Grant operations'))
        assert tool.id is not None

        fetched = AgentTool.get(tool.id)
        assert fetched.target == 'grants'
        assert fetched.description == 'Grant operations'


class TestAgentActorInstance:
    """Tests for creating AgentActor instances."""

    def test_create_instance(self, fresh_matrix):
        agent = AgentActor(
            name='Test Agent',
            prompt='You are a test agent.',
            tools=[AgentTool(target='web_tools')],
            addr='agents/1',
        )
        assert agent.name == 'Test Agent'
        assert agent.prompt == 'You are a test agent.'
        assert len(agent.tools) == 1
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

    def test_has_agentic_method(self, fresh_matrix):
        agent = AgentActor(name='Test', prompt='test', addr='agents/4')
        assert hasattr(agent, 'agentic')
        assert hasattr(agent.agentic, '__endpoint__')  # @expose_route

    def test_has_run_method(self, fresh_matrix):
        agent = AgentActor(name='Test', prompt='test', addr='agents/5')
        assert hasattr(agent, 'run')


class TestResolveToolAddrs:
    """Tests for AgentActor._resolve_tool_addrs()."""

    def test_from_agent_tool_instances(self, fresh_matrix):
        agent = AgentActor(
            name='Test',
            prompt='test',
            tools=[AgentTool(target='grants'), AgentTool(target='sources')],
            addr='agents/1',
        )
        addrs = agent.tool_addrs()
        assert addrs == ['grants', 'sources']

    def test_from_dicts(self, fresh_matrix):
        agent = AgentActor(
            name='Test',
            prompt='test',
            tools=[{'target': 'grants'}, {'target': 'sources'}],
            addr='agents/2',
        )
        addrs = agent.tool_addrs()
        assert addrs == ['grants', 'sources']

    def test_from_hydrated_list_relationship(self, fresh_matrix, tmp_path):
        """Resolve tool addrs from a hydrated list[AgentTool] relationship."""
        storage = SQLiteStorage(str(tmp_path / 'tools.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        tool = AgentTool.create(AgentTool(target='grants', description='Grant ops'))
        created = AgentActor.create(AgentActor(name='Test', prompt='test', tools=[tool], addr='agents/3'))
        agent = AgentActor.get(created.id)
        addrs = agent.tool_addrs()
        assert addrs == ['grants']

    def test_empty_tools(self, fresh_matrix):
        agent = AgentActor(name='Test', prompt='test', addr='agents/4')
        assert agent.tool_addrs() == []


class TestAgentActorCRUD:
    """Tests for AgentActor storage operations."""

    def test_create_and_get(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        agent = AgentActor(
            name='Stored Agent',
            prompt='You help find grants.',
            llm='ollama:llama3.1',
            constraints={'max_iterations': 20},
        )
        created = AgentActor.create(agent)
        assert created.id is not None

        # Create tools via list[T]
        tool_grants = AgentTool.create(AgentTool(target='grants', description='Grant ops'))
        tool_web = AgentTool.create(AgentTool(target='web_tools', description='Web ops'))
        AgentActor.update(created.id, {'tools': [tool_grants, tool_web]})

        fetched = AgentActor.get(created.id)
        assert fetched.name == 'Stored Agent'
        assert fetched.prompt == 'You help find grants.'
        assert fetched.llm == 'ollama:llama3.1'
        assert fetched.constraints == {'max_iterations': 20}
        # tools are hydrated as AgentTool objects
        assert len(fetched.tools) == 2
        tool_addrs = fetched.tool_addrs()
        assert 'grants' in tool_addrs
        assert 'web_tools' in tool_addrs

    def test_list_agents(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        AgentActor.create(AgentActor(name='Agent 1', prompt='p1'))
        AgentActor.create(AgentActor(name='Agent 2', prompt='p2'))

        result = AgentActor.list()
        records = result['data'] if isinstance(result, dict) else result
        assert len(records) == 2

    def test_update_agent(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        agent = AgentActor.create(
            AgentActor(name='Original', prompt='original prompt')
        )
        updated = AgentActor.update(agent.id, {'prompt': 'updated prompt'})
        assert updated.prompt == 'updated prompt'

    def test_delete_agent(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        agent = AgentActor.create(AgentActor(name='ToDelete', prompt='bye'))
        AgentActor.delete(agent.id)
        assert AgentActor.get(agent.id) is None


class TestAgentActorAgentic:
    """Tests for AgentActor.agentic() — the LLM execution endpoint."""

    @pytest.mark.asyncio
    async def test_agentic_basic(self, fresh_matrix, tmp_path):
        """agentic() resolves tools from DB and calls run() engine."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        agent = AgentActor.create(AgentActor(
            name='Runner',
            prompt='You are a helpful assistant.',
            llm='test',  # will be overridden
        ))
        # Fetch from DB to get a proper instance
        agent = AgentActor.get(agent.id)

        result_str = await agent.agentic(
            task='Hello, world!',
            llm=TestModel(call_tools=[]),
        )
        result = json.loads(result_str)
        assert 'answer' in result
        assert 'usage' in result
        assert 'messages' in result

    @pytest.mark.asyncio
    async def test_agentic_with_tools(self, fresh_matrix, tmp_path):
        """agentic() discovers tools from actor addresses via list[T]."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'agents.db'))

        class Grant(ActorModel):
            __tablename__ = 'grants'
            __storable__ = True
            title: str = Field(default='')

        register_model(Grant, storage=storage)
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        agent = AgentActor.create(AgentActor(
            name='Grant Scanner',
            prompt='List all grants.',
        ))
        # Add tool via list[T]
        tool = AgentTool.create(AgentTool(target='grants'))
        AgentActor.update(agent.id, {'tools': [tool]})

        agent = AgentActor.get(agent.id)

        result_str = await agent.agentic(
            task='Find grants',
            llm=TestModel(call_tools=['grants_list']),
        )
        result = json.loads(result_str)
        assert 'answer' in result
        assert result['usage']['requests'] >= 1

    @pytest.mark.asyncio
    async def test_agentic_passes_user(self, fresh_matrix, tmp_path):
        """agentic(task=..., user={...}) passes user to run() engine."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        agent = AgentActor.create(AgentActor(
            name='User Agent',
            prompt='Test user propagation.',
        ))
        agent = AgentActor.get(agent.id)

        user = {'user_id': 99, 'role': 'admin'}
        result_str = await agent.agentic(
            task='Test',
            llm=TestModel(call_tools=[]),
            user=user,
        )
        result = json.loads(result_str)
        assert 'answer' in result

    @pytest.mark.asyncio
    async def test_agentic_passes_constraints_override(self, fresh_matrix, tmp_path):
        """agentic(task=..., constraints={...}) overrides instance constraints."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        agent = AgentActor.create(AgentActor(
            name='Constrained Agent',
            prompt='Test constraints.',
            constraints={'max_iterations': 100},
        ))
        agent = AgentActor.get(agent.id)

        # Override constraints at call time
        result_str = await agent.agentic(
            task='Test',
            llm=TestModel(call_tools=[]),
            constraints={'max_iterations': 2},
        )
        result = json.loads(result_str)
        assert 'answer' in result

    @pytest.mark.asyncio
    async def test_agentic_returns_json_string_wrapper_of_sync_result(self, fresh_matrix, monkeypatch):
        """agentic() JSON-serializes the shared internal sync result dict."""
        captured = {}

        async def fake_prepare(cls, target, call):
            return PreparedCall(
                root=fresh_matrix,
                agent_addr='agents/1',
                thread_id=55,
                message_history=None,
                ai_agent=None,
                deps=None,
                usage_limits=None,
            )

        async def fake_run(cls, prepared, task):
            result = {
                'answer': {'summary': 'done'},
                'usage': {'input_tokens': 1, 'output_tokens': 2, 'requests': 3},
                'messages': [{'kind': 'request'}, {'kind': 'response'}],
                'message_count': 2,
                'thread_id': prepared.thread_id,
            }
            captured['result'] = result
            return result

        monkeypatch.setattr(Agent, 'prepare', classmethod(fake_prepare))
        monkeypatch.setattr(Agent, 'run', classmethod(fake_run))
        monkeypatch.setattr(AgentActor, '_resolve_tool_addrs', lambda self: [])

        agent = AgentActor(
            name='JSON Wrapper Agent',
            prompt='Agent prompt',
            llm='test',
            addr='agents/1',
        )

        result_str = await agent.agentic(task='Serialize me')

        assert isinstance(result_str, str)
        decoded = json.loads(result_str)
        assert decoded == captured['result']
        assert decoded['message_count'] == len(decoded['messages'])
        assert decoded['thread_id'] == 55


class TestAgentActorStream:
    """Tests for AgentActor.agentic_stream() — streaming with DB tool resolution."""

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self, fresh_matrix, tmp_path):
        """agentic_stream() yields TX-aligned chunks."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        agent = AgentActor(
            name='Test Streamer',
            prompt='You are a test agent.',
            llm='test',
        )
        created = AgentActor.create(agent)

        chunks = []
        async for chunk in created.agentic_stream(
            task='Hello',
            llm=TestModel(call_tools=[]),
        ):
            chunks.append(chunk)

        assert len(chunks) > 0
        names = [c['name'] for c in chunks]
        assert 'done' in names or 'text' in names

    @pytest.mark.asyncio
    async def test_stream_with_tool_resolution(self, fresh_matrix, tmp_path):
        """agentic_stream() resolves tools from DB and yields tool events."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Item(ActorModel):
            __tablename__ = 'items'
            __storable__ = True
            title: str = Field(default='')

        register_model(Item, storage=storage)
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        agent = AgentActor(
            name='Tool Streamer',
            prompt='You list items.',
            llm='test',
        )
        created = AgentActor.create(agent)

        # Add tool record via list[T]
        tool_record = AgentTool.create(AgentTool(target='items', description='Item CRUD'))
        AgentActor.update(created.id, {'tools': [tool_record]})

        # Reload to get hydrated tool records
        agent = AgentActor.get(created.id)

        chunks = []
        async for chunk in agent.agentic_stream(
            task='List items',
            llm=TestModel(call_tools=['items_list']),
        ):
            chunks.append(chunk)

        names = [c['name'] for c in chunks]
        assert 'tool_call' in names, f"No tool_call in: {names}"
        assert 'tool_result' in names, f"No tool_result in: {names}"
        assert 'done' in names

    @pytest.mark.asyncio
    async def test_stream_schema_has_method(self, fresh_matrix, tmp_path):
        """AgentActor schema includes agentic_stream in methods with stream=True."""
        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        schema = AgentActor.schema()
        methods = schema.get('methods', {})
        assert 'agentic_stream' in methods, f"agentic_stream not in: {list(methods.keys())}"
        assert methods['agentic_stream'].get('stream') is True


class TestAgentActorAdapterParity:
    """Regression fences for AgentActor sync/stream adapter parity."""

    @pytest.mark.asyncio
    async def test_agentic_and_agentic_stream_use_explicit_runtime_seam(self, fresh_matrix, monkeypatch):
        captured = {}

        async def fake_prepare(cls, target, call):
            captured.setdefault('calls', []).append(call)
            return PreparedCall(
                root=fresh_matrix,
                agent_addr='agents/1',
                thread_id=call.thread_id,
                message_history=None,
                ai_agent=None,
                deps=None,
                usage_limits=None,
            )

        async def fake_run(cls, prepared, task):
            captured['sync_task'] = task
            captured['sync_thread_id'] = prepared.thread_id
            return {'answer': 'sync', 'usage': {}, 'messages': [], 'message_count': 0}

        async def fake_run_stream(cls, prepared, task):
            captured['stream_task'] = task
            captured['stream_thread_id'] = prepared.thread_id
            yield {'name': 'done', 'data': {'answer': 'stream'}, 'meta': {'stream_end': True}}

        monkeypatch.setattr(Agent, 'prepare', classmethod(fake_prepare))
        monkeypatch.setattr(Agent, 'run', classmethod(fake_run))
        monkeypatch.setattr(Agent, 'run_stream', classmethod(fake_run_stream))
        monkeypatch.setattr(AgentActor, '_resolve_tool_addrs', lambda self: ['grants', 'sources'])

        agent = AgentActor(
            name='Parity Agent',
            prompt='Agent prompt',
            llm='test',
            constraints={'max_iterations': 9},
            addr='agents/1',
        )

        user = {'user_id': 42, 'role': 'admin'}

        result = await agent.agentic(
            task='Do it',
            thread_id=77,
            llm='override:model',
            constraints={'max_iterations': 2},
            user=user,
            result_type=dict,
        )

        async for _chunk in agent.agentic_stream(
            task='Do it',
            thread_id=77,
            llm='override:model',
            constraints={'max_iterations': 2},
            user=user,
            result_type=dict,
        ):
            pass

        assert json.loads(result)['answer'] == 'sync'
        assert captured['sync_task'] == 'Do it'
        assert captured['stream_task'] == 'Do it'
        assert captured['sync_thread_id'] == 77
        assert captured['stream_thread_id'] == 77

        sync_call, stream_call = captured['calls']
        for call in (sync_call, stream_call):
            assert call.prompt == 'Agent prompt'
            assert call.tools == ['grants', 'sources']
            assert call.constraints == {'max_iterations': 2}
            assert call.user == user
            assert call.thread_id == 77
            assert call.result_type is dict
            assert call.llm == 'override:model'
            assert call.has_llm_override is True

    @pytest.mark.asyncio
    async def test_agent_runtime_call_normalizes_zero_thread_id_to_none(self, fresh_matrix, monkeypatch):
        captured = {}

        async def fake_prepare(cls, target, call):
            captured['call'] = call
            return PreparedCall(
                root=fresh_matrix,
                agent_addr='agents/1',
                thread_id=call.thread_id,
                message_history=None,
                ai_agent=None,
                deps=None,
                usage_limits=None,
            )

        async def fake_run(cls, prepared, task):
            return {'answer': 'sync', 'usage': {}, 'messages': [], 'message_count': 0}

        monkeypatch.setattr(Agent, 'prepare', classmethod(fake_prepare))
        monkeypatch.setattr(Agent, 'run', classmethod(fake_run))
        monkeypatch.setattr(AgentActor, '_resolve_tool_addrs', lambda self: [])

        agent = AgentActor(
            name='Zero Thread Agent',
            prompt='Agent prompt',
            llm='test',
            addr='agents/1',
        )

        await agent.agentic(task='Do it', thread_id=0)

        assert captured['call'].thread_id is None


class TestAgentActorSchema:
    """Tests for schema extension on AgentActor."""

    def test_schema_has_agent_section(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        schema = AgentActor.schema()
        assert 'agent' in schema
        assert schema['agent']['enabled'] is True
        assert 'agentic_endpoint' in schema['agent']
        assert '/agents/{id}/agentic' == schema['agent']['agentic_endpoint']

    def test_schema_has_agentic_method(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        schema = AgentActor.schema()
        assert 'agentic' in schema.get('methods', {})

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
