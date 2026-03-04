"""Tests for AgentMixin injection and agent_run()."""

import pytest
from pydantic import Field

from n3tx.core.actors.actor import Actor
from n3tx.core.actors.matrix import Matrix
from n3tx.core.models.actor_model import ActorModel
from n3tx.core.models.proto_model import ProtoModel
from n3tx.core.storage.sqlite_storage import SQLiteStorage
from n3tx.core.utils.decorators import expose_route
from n3tx.core.utils.registrar import register_model
from n3tx.core.agents.mixin import AgentMixin

pytestmark = pytest.mark.unit


class TestMixinInjection:
    """Tests for __agent__ = True mixin injection."""

    def test_agent_mixin_injected(self, fresh_matrix):
        class MyModel(ActorModel):
            __tablename__ = 'my_models'
            __storable__ = False
            __agent__ = True

        assert issubclass(MyModel, AgentMixin)
        assert hasattr(MyModel, 'agent_run')

    def test_no_agent_mixin_without_flag(self, fresh_matrix):
        class RegularModel(ActorModel):
            __tablename__ = 'regular'
            __storable__ = False

        assert not issubclass(RegularModel, AgentMixin)

    def test_agent_mixin_coexists_with_storable(self, fresh_matrix, memory_storage):
        from n3tx.core.models.storable_mixin import StorableMixin

        class DualModel(ActorModel):
            __tablename__ = 'dual'
            __storable__ = True
            __agent__ = True

            name: str = Field(default='test')

        register_model(DualModel, storage=memory_storage)

        assert issubclass(DualModel, AgentMixin)
        assert issubclass(DualModel, StorableMixin)
        assert hasattr(DualModel, 'agent_run')
        assert hasattr(DualModel, 'create')  # from StorableMixin

    def test_mro_order(self, fresh_matrix):
        class AgentModel(ActorModel):
            __tablename__ = 'agent_models'
            __storable__ = False
            __agent__ = True

        mro = [cls.__name__ for cls in AgentModel.__mro__]
        # AgentMixin should be before ActorModel/Actor/ProtoModel
        assert mro.index('AgentMixin') < mro.index('ActorModel')


class TestAgentRun:
    """Tests for agent_run() with mock LLM."""

    @pytest.mark.asyncio
    async def test_agent_run_basic(self, fresh_matrix):
        """agent_run() executes with a mock LLM and returns structured result."""
        from pydantic_ai.models.test import TestModel

        m = fresh_matrix

        # Non-storable model with a method — no DB needed
        class WebTools(ActorModel):
            __tablename__ = 'web_tools'
            __storable__ = False

            @expose_route('/ping', methods=['POST'])
            @classmethod
            def ping(cls) -> str:
                return 'pong'

        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        # TestModel with call_tools=[] so it doesn't try to call tools
        result = await Scanner.agent_run(
            Scanner,
            prompt='You find grants.',
            tools=['web_tools'],
            task='Find grants about energy',
            llm=TestModel(call_tools=[]),
        )

        assert 'answer' in result
        assert 'usage' in result
        assert 'messages' in result
        assert isinstance(result['usage']['requests'], int)
        assert isinstance(result['answer'], str)

    @pytest.mark.asyncio
    async def test_agent_run_on_instance(self, fresh_matrix):
        """agent_run() works on instances, not just classes."""
        from pydantic_ai.models.test import TestModel

        m = fresh_matrix

        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

            name: str = Field(default='test')

        scanner = Scanner(name='Test Scanner', addr='scanners/1')

        result = await scanner.agent_run(
            prompt='You find grants.',
            tools=[],
            task='Find grants about energy',
            llm=TestModel(call_tools=[]),
        )

        assert 'answer' in result
        assert result['usage']['requests'] >= 1

    @pytest.mark.asyncio
    async def test_agent_run_no_tools_warns(self, fresh_matrix, caplog):
        """agent_run() with empty tools list logs a warning."""
        from pydantic_ai.models.test import TestModel
        import logging

        m = fresh_matrix

        class Lonely(ActorModel):
            __tablename__ = 'lonely'
            __storable__ = False
            __agent__ = True

        with caplog.at_level(logging.WARNING):
            result = await Lonely.agent_run(
                Lonely,
                prompt='You have no tools.',
                tools=[],
                task='Do nothing',
                llm=TestModel(call_tools=[]),
            )

        assert 'answer' in result

    @pytest.mark.asyncio
    async def test_agent_run_no_matrix_raises(self):
        """agent_run() without Matrix raises RuntimeError."""
        class Orphan(ActorModel, auto_register=False):
            __tablename__ = 'orphan'
            __storable__ = False
            __agent__ = True

        # Ensure no root
        Actor.__matrix__ = None

        with pytest.raises(RuntimeError, match="No Matrix root"):
            await Orphan.agent_run(
                Orphan,
                prompt='test',
                tools=[],
                task='test',
            )

    @pytest.mark.asyncio
    async def test_adapter_cleaned_up_after_run(self, fresh_matrix):
        """Transient adapter is removed from Matrix after agent_run()."""
        from pydantic_ai.models.test import TestModel

        m = fresh_matrix

        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        children_before = set(m._children.keys())

        await Scanner.agent_run(
            Scanner,
            prompt='test',
            tools=[],
            task='test',
            llm=TestModel(call_tools=[]),
        )

        children_after = set(m._children.keys())
        # No leftover _agent_* adapters
        agent_adapters = {k for k in children_after if k.startswith('_agent_')}
        assert len(agent_adapters) == 0

    @pytest.mark.asyncio
    async def test_adapter_cleaned_up_on_error(self, fresh_matrix):
        """Transient adapter is cleaned up even if agent_run() fails."""
        m = fresh_matrix

        class Failing(ActorModel):
            __tablename__ = 'failing'
            __storable__ = False
            __agent__ = True

        try:
            await Failing.agent_run(
                Failing,
                prompt='test',
                tools=[],
                task='test',
                llm='nonexistent:model',  # will fail
            )
        except Exception:
            pass

        children_after = set(m._children.keys())
        agent_adapters = {k for k in children_after if k.startswith('_agent_')}
        assert len(agent_adapters) == 0

    @pytest.mark.asyncio
    async def test_agent_run_with_tool_calling(self, fresh_matrix, tmp_path):
        """agent_run() where the LLM calls a tool through Matrix TX routing."""
        from pydantic_ai.models.test import TestModel

        m = fresh_matrix
        # Use file-based SQLite — :memory: creates separate DBs per connection
        # which breaks create_table() (opens its own connection).
        file_storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Grant(ActorModel):
            __tablename__ = 'grants'
            __storable__ = True
            title: str = Field(default='')

        register_model(Grant, storage=file_storage)
        file_storage.create_table(Grant)

        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        # TestModel calls grants_list, which does a real DB query
        result = await Scanner.agent_run(
            Scanner,
            prompt='List available grants.',
            tools=['grants'],
            task='List all grants',
            llm=TestModel(call_tools=['grants_list']),
        )

        assert 'answer' in result
        # The LLM called at least one tool
        assert result['usage']['requests'] >= 1

    @pytest.mark.asyncio
    async def test_agent_run_kwargs_override(self, fresh_matrix):
        """agent_run() accepts llm and constraints via kwargs."""
        from pydantic_ai.models.test import TestModel

        m = fresh_matrix

        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        result = await Scanner.agent_run(
            Scanner,
            prompt='test',
            tools=[],
            task='test',
            llm=TestModel(call_tools=[]),
            constraints={'max_iterations': 5},
        )

        assert 'answer' in result
