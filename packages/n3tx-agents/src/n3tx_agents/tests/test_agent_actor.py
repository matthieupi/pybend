"""Tests for AgentActor — the dynamic agent class."""

import json

import pytest
from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import register_model
from n3tx_agents.agent import Agent, PreparedCall
from n3tx_agents.actor import AgentActor
from n3tx_agents.tool_model import AgentTool
from n3tx_threads import Thread, TTX
from n3tx_actors.tx import TX
from n3tx_core.models.ref import public_id_url

from .conftest import HistoryOwner

pytestmark = pytest.mark.unit


class TestAgentActorClass:
    """Tests for AgentActor class structure."""

    def test_has_agent_mixin(self, fresh_matrix):
        """Retain injected reasoning on stored agents."""
        from n3tx_agents.mixin import AgentMixin
        # 0. Inspect native capability inheritance without execution.
        assert issubclass(AgentActor, AgentMixin)

    def test_has_storable_mixin(self, fresh_matrix):
        """Retain native storage on agent configurations."""
        from n3tx_core.models.storable_mixin import StorableMixin
        # 0. Inspect native storage capability inheritance.
        assert issubclass(AgentActor, StorableMixin)

    def test_is_actor_model(self, fresh_matrix):
        """Retain the native actor/model base."""
        # 0. Inspect native actor/model inheritance.
        assert issubclass(AgentActor, ActorModel)

    def test_tablename(self, fresh_matrix):
        """Keep stored agent identities stable."""
        # 0. Inspect the authoritative native table declaration.
        assert AgentActor.__tablename__ == 'agents'

    def test_fields(self, fresh_matrix):
        """Expose configuration fields through native schema."""
        # 0. Inspect generated configuration properties.
        schema = AgentActor.model_json_schema()
        props = schema.get('properties', {})
        assert 'name' in props
        assert 'prompt' in props
        assert 'tools' in props
        assert 'llm' in props
        assert 'constraints' in props

    def test_mro_order(self, fresh_matrix):
        """Resolve reasoning methods before native model methods."""
        from n3tx_agents.mixin import AgentMixin
        # 0. Inspect model composition order.
        mro = [cls.__name__ for cls in AgentActor.__mro__]
        # AgentMixin should be before ActorModel
        assert mro.index('AgentMixin') < mro.index('ActorModel')


class TestAgentToolModel:
    """Tests for the AgentTool model."""

    def test_tablename(self, fresh_matrix):
        """Keep the native tool table identity stable."""
        # 0. Inspect the authoritative tool table declaration.
        assert AgentTool.__tablename__ == 'agent_tools'

    def test_is_actor_model(self, fresh_matrix):
        """Store tools as ordinary native actor models."""
        # 0. Inspect native actor/model inheritance.
        assert issubclass(AgentTool, ActorModel)

    def test_create_instance(self, fresh_matrix):
        """Preserve tool target and description fields."""
        # 0. Validate native configuration without inference.
        tool = AgentTool(target='grants', description='Grant CRUD')
        assert tool.target == 'grants'
        assert tool.description == 'Grant CRUD'

    def test_crud(self, fresh_matrix, tmp_path):
        """Persist and reload native tool configuration."""
        # 0. Register disposable tool storage and exercise native CRUD.
        storage = SQLiteStorage(str(tmp_path / 'tools.db'))
        register_model(AgentTool, storage=storage)
        storage.create_table(AgentTool)

        tool = AgentTool.create(AgentTool(
            target='grants', description='Grant operations',
        ))
        assert tool.id is not None

        fetched = AgentTool.get(tool.id)
        assert fetched.target == 'grants'
        assert fetched.description == 'Grant operations'


class TestAgentActorInstance:
    """Tests for creating AgentActor instances."""

    def test_create_instance(self, fresh_matrix):
        """Retain stored defaults without executing a provider."""
        # 0. Inspect a validated in-memory configuration.
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
        """Preserve configured model strings without resolving providers."""
        # 0. Validate explicit configuration without provider resolution.
        agent = AgentActor(
            name='Custom LLM',
            prompt='test',
            llm='anthropic:claude-sonnet-4-5-20250929',
            addr='agents/2',
        )
        assert agent.llm == 'anthropic:claude-sonnet-4-5-20250929'

    def test_custom_constraints(self, fresh_matrix):
        """Retain model-request constraints as configuration data."""
        # 0. Validate explicit model-request limits.
        agent = AgentActor(
            name='Constrained',
            prompt='test',
            constraints={'max_iterations': 10},
            addr='agents/3',
        )
        assert agent.constraints == {'max_iterations': 10}

    def test_has_agentic_method(self, fresh_matrix):
        """Keep the existing exposed synchronous adapter."""
        # 0. Inspect exposed method metadata.
        agent = AgentActor(name='Test', prompt='test', addr='agents/4')
        assert hasattr(agent, 'agentic')
        assert hasattr(agent.agentic, '__endpoint__')  # @expose_route

    def test_has_run_method(self, fresh_matrix):
        """Retain the explicit runtime entrypoint."""
        # 0. Inspect the explicit execution method.
        agent = AgentActor(name='Test', prompt='test', addr='agents/5')
        assert hasattr(agent, 'run')


class TestResolveToolAddrs:
    """Resolve configured tools without the retired private alias."""

    def test_from_agent_tool_instances(self, fresh_matrix):
        """Extract native tool targets in their configured order."""
        # 0. Resolve the declared ordered native tool objects.
        agent = AgentActor(
            name='Test',
            prompt='test',
            tools=[AgentTool(target='grants'), AgentTool(target='sources')],
            addr='agents/1',
        )
        addrs = agent.tool_addrs()
        assert addrs == ['grants', 'sources']

    def test_from_dicts(self, fresh_matrix):
        """Resolve validated tool dictionaries through native fields."""
        # 0. Resolve dictionaries after normal model validation.
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
        # 0. Save and reload real native tool relationships.
        storage = SQLiteStorage(str(tmp_path / 'tools.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        tool = AgentTool.create(AgentTool(
            target='grants', description='Grant ops',
        ))
        created = AgentActor.create(AgentActor(
            name='Test', prompt='test', tools=[tool], addr='agents/3',
        ))
        agent = AgentActor.get(created.id)
        addrs = agent.tool_addrs()
        assert addrs == ['grants']

    def test_empty_tools(self, fresh_matrix):
        """Keep empty tool configuration explicit."""
        # 0. Resolve an empty native tool collection.
        agent = AgentActor(name='Test', prompt='test', addr='agents/4')
        assert agent.tool_addrs() == []


class TestAgentActorCRUD:
    """Tests for AgentActor storage operations."""

    def test_create_and_get(self, fresh_matrix, tmp_path):
        """Reload agent fields and ordered native tool relationships."""
        # 0. Save configuration and native relationship targets.
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
        tool_grants = AgentTool.create(AgentTool(
            target='grants', description='Grant ops',
        ))
        tool_web = AgentTool.create(AgentTool(
            target='web_tools', description='Web ops',
        ))
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
        """List independently saved native agent configurations."""
        # 0. Save distinct configurations in disposable storage.
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        AgentActor.create(AgentActor(name='Agent 1', prompt='p1'))
        AgentActor.create(AgentActor(name='Agent 2', prompt='p2'))

        result = AgentActor.list()
        records = result['data'] if isinstance(result, dict) else result
        assert len(records) == 2

    def test_update_agent(self, fresh_matrix, tmp_path):
        """Apply ordinary configuration updates without execution."""
        # 0. Exercise native saved configuration updates.
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        agent = AgentActor.create(
            AgentActor(name='Original', prompt='original prompt')
        )
        updated = AgentActor.update(agent.id, {'prompt': 'updated prompt'})
        assert updated.prompt == 'updated prompt'

    def test_delete_agent(self, fresh_matrix, tmp_path):
        """Delete saved configuration through trusted native storage."""
        # 0. Delete one disposable configuration through native CRUD.
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        agent = AgentActor.create(AgentActor(name='ToDelete', prompt='bye'))
        AgentActor.delete(agent.id)
        assert AgentActor.get(agent.id) is None


class TestAgentActorAgentic:
    """Tests for AgentActor.agentic() — the LLM execution endpoint."""

    @pytest.mark.asyncio
    async def test_agentic_basic(self, fresh_matrix, tmp_path, agent_context):
        """agentic() resolves tools from DB and calls run() engine."""
        from pydantic_ai.models.test import TestModel
        # 0. Execute the stored adapter against an authorized real parent.
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
            **agent_context,
        )
        result = json.loads(result_str)
        assert 'answer' in result
        assert 'usage' in result
        assert 'messages' in result

    @pytest.mark.asyncio
    async def test_agentic_with_tools(
        self, fresh_matrix, tmp_path, agent_context,
    ):
        """agentic() discovers tools from actor addresses via list[T]."""
        from pydantic_ai.models.test import TestModel
        # 0. Configure real native tools and authorized saved scope.
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))

        class Grant(ActorModel):
            """Disposable native grant resource for tool discovery."""

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
            **agent_context,
        )
        result = json.loads(result_str)
        assert 'answer' in result
        assert result['usage']['requests'] >= 1

    @pytest.mark.asyncio
    async def test_agentic_passes_user(
        self, fresh_matrix, tmp_path, agent_context,
    ):
        """agentic(task=..., user={...}) passes user to run() engine."""
        from pydantic_ai.models.test import TestModel
        # 0. Execute with an explicit trusted Python caller.
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        agent = AgentActor.create(AgentActor(
            name='User Agent',
            prompt='Test user propagation.',
        ))
        agent = AgentActor.get(agent.id)

        user = {'user_id': 99, 'role': 'admin'}
        owner = HistoryOwner.create(HistoryOwner(user_owner=user['user_id']))
        scope = public_id_url(owner.id, target_cls=HistoryOwner)
        result_str = await agent.agentic(
            task='Test',
            llm=TestModel(call_tools=[]),
            user=user,
            scope=scope,
        )
        result = json.loads(result_str)
        assert 'answer' in result
        # 1. Trusted Python caller reaches root attribution intact.
        root = TTX.get(result['thread_id'])
        assert root.user_owner == user['user_id']
        assert root.target == scope

    @pytest.mark.asyncio
    async def test_agentic_passes_constraints_override(
        self, fresh_matrix, tmp_path, agent_context,
    ):
        """Explicit constraints override stored model-request limits."""
        from pydantic_ai.models.test import TestModel
        # 0. Keep native execution while overriding stored limits.
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
            **agent_context,
        )
        result = json.loads(result_str)
        assert 'answer' in result

    @pytest.mark.asyncio
    async def test_agentic_returns_json_string_wrapper_of_sync_result(
        self, fresh_matrix, monkeypatch,
    ):
        """agentic() JSON-serializes the shared internal sync result dict."""
        # 0. Isolate adapter serialization at its explicit runtime seam.
        captured = {}

        async def fake_prepare(cls, target, call):
            """Supply a prepared semantic root at the adapter-only seam."""
            return PreparedCall(
                root=fresh_matrix,
                agent_addr='agents/1',
                thread=Thread(TX(
                    'Conversation', 'agents/1',
                    'https://agents.example.test/HistoryOwner/1', data=None,
                ), id=55),
                message_history=[],
                ai_agent=None,
                deps=None,
                usage_limits=None,
            )

        async def fake_run(cls, prepared, task):
            """Return portable fields for exact string serialization."""
            result = {
                'answer': {'summary': 'done'},
                'usage': {'input_tokens': 1, 'output_tokens': 2, 'requests': 3},
                'messages': [{'kind': 'request'}, {'kind': 'response'}],
                'message_count': 2,
                'thread_id': prepared.thread.id,
            }
            captured['result'] = result
            return result

        monkeypatch.setattr(Agent, 'prepare', classmethod(fake_prepare))
        monkeypatch.setattr(Agent, 'run', classmethod(fake_run))
        monkeypatch.setattr(AgentActor, 'tool_addrs', lambda self: [])

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
    """Stream native events with stored tool configuration."""

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(
        self, fresh_matrix, tmp_path, agent_context,
    ):
        """agentic_stream() yields TX-aligned chunks."""
        from pydantic_ai.models.test import TestModel
        # 0. Execute the native streaming adapter with explicit saved scope.
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
            **agent_context,
        ):
            chunks.append(chunk)

        assert len(chunks) > 0
        names = [c['name'] for c in chunks]
        assert 'done' in names or 'text' in names

    @pytest.mark.asyncio
    async def test_stream_with_tool_resolution(
        self, fresh_matrix, tmp_path, agent_context,
    ):
        """agentic_stream() resolves tools from DB and yields tool events."""
        from pydantic_ai.models.test import TestModel
        # 0. Save native tool relationships before streaming execution.
        storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Item(ActorModel):
            """Disposable native item exposed through stored tools."""

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
        tool_record = AgentTool.create(AgentTool(
            target='items', description='Item CRUD',
        ))
        AgentActor.update(created.id, {'tools': [tool_record]})

        # Reload to get hydrated tool records
        agent = AgentActor.get(created.id)

        chunks = []
        async for chunk in agent.agentic_stream(
            task='List items',
            llm=TestModel(call_tools=['items_list']),
            **agent_context,
        ):
            chunks.append(chunk)

        names = [c['name'] for c in chunks]
        assert 'tool_call' in names, f"No tool_call in: {names}"
        assert 'tool_result' in names, f"No tool_result in: {names}"
        assert 'done' in names

    @pytest.mark.asyncio
    async def test_stream_schema_has_method(self, fresh_matrix, tmp_path):
        """Publish the existing native streaming action schema."""
        # 0. Inspect generated streaming schema after native registration.
        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        schema = AgentActor.schema()
        methods = schema.get('methods', {})
        assert 'agentic_stream' in methods, list(methods)
        assert methods['agentic_stream'].get('stream') is True


class TestAgentActorAdapterParity:
    """Regression fences for AgentActor sync/stream adapter parity."""

    @pytest.mark.asyncio
    async def test_agentic_and_agentic_stream_use_explicit_runtime_seam(
        self, fresh_matrix, monkeypatch, agent_context,
    ):
        """Forward stored policy and explicit scope to both adapters."""
        # 0. Capture both adapters at the shared runtime boundary.
        captured = {}

        async def fake_prepare(cls, target, call):
            """Capture resolved adapter input without provider execution."""
            captured.setdefault('calls', []).append(call)
            return PreparedCall(
                root=fresh_matrix,
                agent_addr='agents/1',
                thread=Thread(TX(
                    'Conversation', 'agents/1', agent_context['scope'],
                    data=None,
                ), id=call.thread_id),
                message_history=[],
                ai_agent=None,
                deps=None,
                usage_limits=None,
            )

        async def fake_run(cls, prepared, task):
            """Expose the sync task and selected semantic root."""
            captured['sync_task'] = task
            captured['sync_thread_id'] = prepared.thread.id
            return {
                'answer': 'sync', 'usage': {}, 'messages': [],
                'message_count': 0,
            }

        async def fake_run_stream(cls, prepared, task):
            """Expose the streaming task and native event shape."""
            captured['stream_task'] = task
            captured['stream_thread_id'] = prepared.thread.id
            yield {
                'name': 'done', 'data': {'answer': 'stream'},
                'meta': {'stream_end': True},
            }

        monkeypatch.setattr(Agent, 'prepare', classmethod(fake_prepare))
        monkeypatch.setattr(Agent, 'run', classmethod(fake_run))
        monkeypatch.setattr(Agent, 'run_stream', classmethod(fake_run_stream))
        monkeypatch.setattr(
            AgentActor, 'tool_addrs', lambda self: ['grants', 'sources'],
        )

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
            scope=agent_context['scope'],
        )

        async for _chunk in agent.agentic_stream(
            task='Do it',
            thread_id=77,
            llm='override:model',
            constraints={'max_iterations': 2},
            user=user,
            result_type=dict,
            scope=agent_context['scope'],
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
            assert call.scope == agent_context['scope']

    @pytest.mark.asyncio
    async def test_agent_runtime_call_normalizes_zero_thread_id_to_none(
        self, fresh_matrix, monkeypatch,
    ):
        """Preserve the public zero-ID new-conversation sentinel."""
        # 0. Observe adapter normalization without preparing a provider.
        captured = {}

        async def fake_prepare(cls, target, call):
            """Observe the sentinel and supply a synthetic prepared root."""
            captured['call'] = call
            return PreparedCall(
                root=fresh_matrix,
                agent_addr='agents/1',
                thread=Thread(TX(
                    'Conversation', 'agents/1',
                    'https://agents.example.test/HistoryOwner/1', data=None,
                ), id=1),
                message_history=[],
                ai_agent=None,
                deps=None,
                usage_limits=None,
            )

        async def fake_run(cls, prepared, task):
            """Return the unchanged portable adapter result contract."""
            return {
                'answer': 'sync', 'usage': {}, 'messages': [],
                'message_count': 0,
            }

        monkeypatch.setattr(Agent, 'prepare', classmethod(fake_prepare))
        monkeypatch.setattr(Agent, 'run', classmethod(fake_run))
        monkeypatch.setattr(AgentActor, 'tool_addrs', lambda self: [])

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
        """Publish stored-agent execution endpoints through native schema."""
        # 0. Inspect generated stored-agent schema.
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        schema = AgentActor.schema()
        assert 'agent' in schema
        assert schema['agent']['enabled'] is True
        assert 'agentic_endpoint' in schema['agent']
        assert '/agents/{id}/agentic' == schema['agent']['agentic_endpoint']

    def test_schema_has_agentic_method(self, fresh_matrix, tmp_path):
        """Keep the existing synchronous action discoverable."""
        # 0. Inspect generated action metadata.
        storage = SQLiteStorage(str(tmp_path / 'agents.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        schema = AgentActor.schema()
        assert 'agentic' in schema.get('methods', {})

    def test_non_agent_model_no_agent_section(self, fresh_matrix, tmp_path):
        """Do not advertise reasoning for plain actor models."""
        # 0. Register an ordinary model without agent capability.
        storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Plain(ActorModel):
            """Ordinary persisted model without an agent flag."""

            __tablename__ = 'plain'
            __storable__ = True
            name: str = Field(default='')

        register_model(Plain, storage=storage)

        schema = Plain.schema()
        assert 'agent' not in schema

    def test_agent_mixin_model_has_agent_section(self, fresh_matrix):
        """Enable mixin schemas without inventing stored-agent endpoints."""
        # 0. Inspect a mixin-enabled model that is not a stored AgentActor.
        class Agentic(ActorModel):
            """Non-storable mixin-enabled model for schema discovery."""

            __tablename__ = 'agentic'
            __storable__ = False
            __agent__ = True

        schema = Agentic.schema()
        assert 'agent' in schema
        assert schema['agent']['enabled'] is True
        # Not an AgentActor subclass, so no run_endpoint
        assert 'run_endpoint' not in schema['agent']


def test_done_schema_includes_optional_root_id():
    """Completion schema carries the unchanged opaque conversation root ID."""
    from n3tx_agents.actor import DoneChunk
    # 0. Inspect native event fields without invoking either execution adapter.
    assert DoneChunk().thread_id is None
    assert DoneChunk(thread_id=7).thread_id == 7
    assert 'thread_id' in DoneChunk.model_json_schema()['properties']
    assert not hasattr(AgentActor, '_resolve_tool_addrs')


# Changelog (Python has no block-comment syntax).
# - 2026-11-04: Forward saved scope through native adapters and prepared roots;
#   retain JSON-string results, stored tools and completion event identity.
#   Keep caller 99 propagation under its own persisted parent ownership.
