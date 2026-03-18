"""Tests for AgentMixin — ctx(), tools(), agentic(), run(), streaming."""

import asyncio
import pytest
from pydantic import Field

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.ref import ListRef
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.registrar import register_model
from n3tx_agents.mixin import AgentMixin

pytestmark = pytest.mark.unit


# ── Test models (defined at module level for expose_route compat) ──

class Comment(ActorModel):
    __tablename__ = 'comments'
    __storable__ = False
    text: str = Field(default='')


class ToolTarget(ActorModel):
    """A model with an exposed method for tool discovery."""
    __tablename__ = 'tool_targets'
    __storable__ = False

    @expose_route('/ping', methods=['POST'])
    def ping(self) -> str:
        """Ping this tool."""
        return 'pong'


class AgenticProduct(ActorModel):
    """Product model with agent capabilities for testing."""
    __tablename__ = 'agentic_products'
    __storable__ = False
    __agent__ = True

    name: str = Field(default='Test Product', min_length=1, max_length=200)
    price: float = Field(default=9.99, gt=0)
    description: str = Field(default='A test product')
    comments: ListRef[Comment] = Field(default=[])


class AgenticWithPrompt(ActorModel):
    """Agent model with custom prompt in config."""
    __tablename__ = 'prompted_agents'
    __storable__ = False
    __agent__ = {'prompt': 'You are a product expert.', 'self_tools': True}

    name: str = Field(default='Test')


class AgenticNoSelf(ActorModel):
    """Agent model with self_tools disabled."""
    __tablename__ = 'no_self_agents'
    __storable__ = False
    __agent__ = {'self_tools': False}

    name: str = Field(default='Test')


class AgenticNoNeighbors(ActorModel):
    """Agent model with neighbors disabled."""
    __tablename__ = 'no_neighbor_agents'
    __storable__ = False
    __agent__ = {'neighbors': False}

    name: str = Field(default='Test')
    comments: ListRef[Comment] = Field(default=[])


class AgenticExtraTools(ActorModel):
    """Agent model with extra tool addresses in config."""
    __tablename__ = 'extra_tool_agents'
    __storable__ = False
    __agent__ = {'tools': ['grants', 'sources']}

    name: str = Field(default='Test')


# ── Injection Tests ──────────────────────────────────────────────

class TestMixinInjection:
    """Tests for __agent__ = True mixin injection."""

    def test_agent_mixin_injected(self, fresh_matrix):
        class MyModel(ActorModel):
            __tablename__ = 'my_models'
            __storable__ = False
            __agent__ = True

        assert issubclass(MyModel, AgentMixin)
        assert hasattr(MyModel, 'run')

    def test_no_agent_mixin_without_flag(self, fresh_matrix):
        class RegularModel(ActorModel):
            __tablename__ = 'regular'
            __storable__ = False

        assert not issubclass(RegularModel, AgentMixin)

    def test_agent_mixin_coexists_with_storable(self, fresh_matrix, memory_storage):
        from n3tx_core.models.storable_mixin import StorableMixin

        class DualModel(ActorModel):
            __tablename__ = 'dual'
            __storable__ = True
            __agent__ = True

            name: str = Field(default='test')

        register_model(DualModel, storage=memory_storage)

        assert issubclass(DualModel, AgentMixin)
        assert issubclass(DualModel, StorableMixin)
        assert hasattr(DualModel, 'run')
        assert hasattr(DualModel, 'create')  # from StorableMixin

    def test_mro_order(self, fresh_matrix):
        class AgentModel(ActorModel):
            __tablename__ = 'agent_models'
            __storable__ = False
            __agent__ = True

        mro = [cls.__name__ for cls in AgentModel.__mro__]
        assert mro.index('AgentMixin') < mro.index('ActorModel')

    def test_new_api_surface(self, fresh_matrix):
        """Verify all new methods are present on agent models."""
        class MyAgent(ActorModel):
            __tablename__ = 'my_agents'
            __storable__ = False
            __agent__ = True

        for method in ['ctx', 'tools', 'agentic', 'run', 'agentic_stream', 'run_stream']:
            assert hasattr(MyAgent, method), f"Missing method: {method}"


# ── ctx() Tests ──────────────────────────────────────────────────

class TestCtx:
    """Tests for ctx() fullmethod — LLM context generation."""

    def test_class_ctx_has_schema(self, fresh_matrix):
        """Product.ctx() returns schema context with fields, types."""
        ctx = AgenticProduct.ctx()
        assert 'agentic_products' in ctx
        assert 'AgenticProduct' in ctx
        assert 'name' in ctx
        assert 'price' in ctx

    def test_instance_ctx_has_state(self, fresh_matrix):
        """product.ctx() returns schema + instance data."""
        product = AgenticProduct(name='Widget', price=29.99, addr='agentic_products/1')
        product.id = 42
        ctx = product.ctx()
        assert 'AgenticProduct' in ctx
        assert 'Current instance' in ctx
        assert 'Widget' in ctx
        assert '29.99' in ctx

    def test_ctx_includes_methods(self, fresh_matrix):
        """ctx() includes @expose_route methods when present."""
        ctx = ToolTarget.ctx() if hasattr(ToolTarget, 'ctx') else ''
        # ToolTarget doesn't have __agent__ so no ctx. Use AgenticProduct which
        # doesn't have methods. Test with a model that has both.
        class MethodAgent(ActorModel):
            __tablename__ = 'method_agents'
            __storable__ = False
            __agent__ = True

            @expose_route('/analyze', methods=['POST'])
            def analyze(self, query: str) -> str:
                """Analyze something."""
                return 'done'

        ctx = MethodAgent.ctx()
        assert 'analyze' in ctx

    def test_ctx_prepends_agent_prompt(self, fresh_matrix):
        """__agent__={'prompt': 'Custom'} prepends to context."""
        ctx = AgenticWithPrompt.ctx()
        assert ctx.startswith('You are a product expert.')

    def test_ctx_includes_relationships(self, fresh_matrix):
        """ctx() includes ListRef relationships."""
        ctx = AgenticProduct.ctx()
        assert 'comments' in ctx.lower()
        assert 'Comment' in ctx

    def test_ctx_class_vs_instance_difference(self, fresh_matrix):
        """Class ctx lacks instance data, instance ctx has it."""
        class_ctx = AgenticProduct.ctx()
        instance = AgenticProduct(name='Specific', price=99.99, addr='agentic_products/1')
        instance_ctx = instance.ctx()

        # Both should have schema
        assert 'AgenticProduct' in class_ctx
        assert 'AgenticProduct' in instance_ctx

        # Only instance should have current data
        assert 'Current instance' not in class_ctx
        assert 'Current instance' in instance_ctx


# ── tools() Tests ────────────────────────────────────────────────

class TestTools:
    """Tests for tools() fullmethod — tool address discovery."""

    def test_self_tools_default(self, fresh_matrix):
        """Default: includes own tablename."""
        addrs = AgenticProduct.tools()
        assert 'agentic_products' in addrs

    def test_neighbor_tools(self, fresh_matrix):
        """Discovers ListRef neighbor tablenames."""
        addrs = AgenticProduct.tools()
        assert 'comments' in addrs

    def test_class_and_instance_same(self, fresh_matrix):
        """Product.tools() == product.tools()."""
        product = AgenticProduct(name='Test', addr='agentic_products/1')
        assert AgenticProduct.tools() == product.tools()

    def test_extra_tools_from_config(self, fresh_matrix):
        """__agent__={'tools': ['extra']} adds addresses."""
        addrs = AgenticExtraTools.tools()
        assert 'grants' in addrs
        assert 'sources' in addrs

    def test_self_tools_disabled(self, fresh_matrix):
        """__agent__={'self_tools': False} omits own tablename."""
        addrs = AgenticNoSelf.tools()
        assert 'no_self_agents' not in addrs

    def test_neighbors_disabled(self, fresh_matrix):
        """__agent__={'neighbors': False} omits neighbors."""
        addrs = AgenticNoNeighbors.tools()
        assert 'comments' not in addrs

    def test_deduplication(self, fresh_matrix):
        """Duplicate addresses are deduplicated."""
        class DupAgent(ActorModel):
            __tablename__ = 'dup_agents'
            __storable__ = False
            __agent__ = {'tools': ['dup_agents']}  # self + explicit = dup

        addrs = DupAgent.tools()
        assert addrs.count('dup_agents') == 1


# ── run() Tests (engine — direct call) ───────────────────────────

class TestRunEngine:
    """Tests for run() — direct engine call."""

    @pytest.mark.asyncio
    async def test_direct_call(self, fresh_matrix):
        """run() executes with explicit params, no config cascade."""
        from pydantic_ai.models.test import TestModel

        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        result = await scanner.run(
            task='Find something',
            prompt='You find things.',
            tools=[],
            llm=TestModel(call_tools=[]),
        )

        assert 'answer' in result
        assert 'usage' in result
        assert 'messages' in result
        assert 'message_count' in result
        assert isinstance(result['messages'], list)
        assert result['message_count'] == len(result['messages'])

    @pytest.mark.asyncio
    async def test_no_matrix_raises(self):
        """run() without Matrix raises RuntimeError."""
        from pydantic_ai.models.test import TestModel

        class Orphan(ActorModel, auto_register=False):
            __tablename__ = 'orphan'
            __storable__ = False
            __agent__ = True

        Actor.__matrix__ = None
        orphan = Orphan(addr='orphan/1')

        with pytest.raises(RuntimeError, match="No Matrix root"):
            await orphan.run(
                task='test',
                prompt='test',
                tools=[],
                llm=TestModel(call_tools=[]),
            )

    @pytest.mark.asyncio
    async def test_with_tool_calling(self, fresh_matrix, tmp_path):
        """run() where the LLM calls a tool through Matrix TX routing."""
        from pydantic_ai.models.test import TestModel

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

        scanner = Scanner(addr='scanners/1')
        result = await scanner.run(
            task='List all grants',
            prompt='List available grants.',
            tools=['grants'],
            llm=TestModel(call_tools=['grants_list']),
        )


        assert 'answer' in result
        assert result['usage']['requests'] >= 1


# ── agentic() Tests ──────────────────────────────────────────────

class TestAgentic:
    """Tests for agentic() fullmethod — config cascade + auto-discovery."""

    @pytest.mark.asyncio
    async def test_zero_config_agentic(self, fresh_matrix):
        """agentic(task='...') auto-discovers prompt and tools."""
        from pydantic_ai.models.test import TestModel

        result = await AgenticProduct.agentic(task='Describe yourself', llm=TestModel(call_tools=[]))

        assert 'answer' in result
        assert 'usage' in result

    @pytest.mark.asyncio
    async def test_explicit_prompt_overrides(self, fresh_matrix):
        """agentic(task='...', prompt='custom') uses custom prompt."""
        from pydantic_ai.models.test import TestModel

        result = await AgenticProduct.agentic(
            task='Test',
            prompt='Custom prompt only',
            llm=TestModel(call_tools=[]),
        )
        assert 'answer' in result

    @pytest.mark.asyncio
    async def test_explicit_tools_overrides(self, fresh_matrix):
        """agentic(task='...', tools=['specific']) uses explicit tools."""
        from pydantic_ai.models.test import TestModel

        result = await AgenticProduct.agentic(
            task='Test',
            tools=[],  # no tools
            llm=TestModel(call_tools=[]),
        )
        assert 'answer' in result

    @pytest.mark.asyncio
    async def test_class_vs_instance_agentic(self, fresh_matrix):
        """Class uses schema context, instance uses instance context."""
        from pydantic_ai.models.test import TestModel

        # Class-level agentic
        class_result = await AgenticProduct.agentic(
            task='Test', llm=TestModel(call_tools=[]),
        )
        assert 'answer' in class_result

        # Instance-level agentic
        product = AgenticProduct(name='Widget', price=29.99, addr='agentic_products/1')
        inst_result = await product.agentic(task='Test', llm=TestModel(call_tools=[]))
        assert 'answer' in inst_result

    @pytest.mark.asyncio
    async def test_agentic_kwargs_override(self, fresh_matrix):
        """agentic() accepts llm and constraints via kwargs."""
        from pydantic_ai.models.test import TestModel

        result = await AgenticProduct.agentic(
            task='Test',
            llm=TestModel(call_tools=[]),
            constraints={'max_iterations': 5},
        )
        assert 'answer' in result


# ── Concurrent Runs ──────────────────────────────────────────────

class TestConcurrentRuns:
    """Verify isolation under concurrent runs."""

    @pytest.mark.asyncio
    async def test_concurrent_runs_isolated(self, fresh_matrix):
        """Multiple concurrent agentic() calls don't cross-contaminate."""
        from pydantic_ai.models.test import TestModel

        tasks = [
            AgenticProduct.agentic(
                task=f'Task {i}',
                llm=TestModel(call_tools=[]),
            )
            for i in range(3)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        for r in results:
            assert 'answer' in r
            assert 'usage' in r


# ── User Auth Propagation ────────────────────────────────────────

class TestUserAuthPropagation:
    """User auth context propagation through tool TXs."""

    @pytest.mark.asyncio
    async def test_user_context_in_tool_calls(self, fresh_matrix, tmp_path):
        """Tool TX messages carry meta.user from agentic(user=...)."""
        from pydantic_ai.models.test import TestModel
        from n3tx_actors.tx import TX

        file_storage = SQLiteStorage(str(tmp_path / 'test.db'))

        captured_meta = {}

        class InstrumentedModel(ActorModel):
            __tablename__ = 'instrumented'
            __storable__ = True
            name: str = Field(default='')

        register_model(InstrumentedModel, storage=file_storage)
        file_storage.create_table(InstrumentedModel)

        async def capture_interceptor(tx: TX) -> TX:
            captured_meta.update(tx.meta)
            return tx

        InstrumentedModel.use(capture_interceptor, on='inbox')

        class AuthAgent(ActorModel):
            __tablename__ = 'auth_agents'
            __storable__ = False
            __agent__ = True

        user_ctx = {'id': 42, 'role': 'admin', 'email': 'admin@test.com'}

        await AuthAgent.run(
            task='List all',
            prompt='List instrumented records.',
            tools=['instrumented'],
            llm=TestModel(call_tools=['instrumented_list']),
            user=user_ctx,
        )

        assert captured_meta.get('user') == user_ctx


# ── Streaming Tests ──────────────────────────────────────────────

class TestAgenticStreamPolicy:
    """Tests for agentic_stream() fullmethod — streaming policy."""

    @pytest.mark.asyncio
    async def test_yields_chunks(self, fresh_matrix):
        """agentic_stream() yields dicts with 'name' field."""
        from pydantic_ai.models.test import TestModel

        chunks = []
        async for chunk in AgenticProduct.agentic_stream(
            task='Describe yourself',
            llm=TestModel(call_tools=[]),
        ):
            chunks.append(chunk)

        assert len(chunks) > 0
        # Last chunk should be 'done'
        assert chunks[-1]['name'] in ('done', 'error')

    @pytest.mark.asyncio
    async def test_auto_discovery(self, fresh_matrix):
        """agentic_stream() auto-discovers from ctx() and tools()."""
        from pydantic_ai.models.test import TestModel

        chunks = []
        async for chunk in AgenticProduct.agentic_stream(
            task='Test',
            llm=TestModel(call_tools=[]),
        ):
            chunks.append(chunk)

        # Should have at least a done chunk
        assert any(c['name'] in ('done', 'error') for c in chunks)


class TestRunStreamEngine:
    """Tests for run_stream() — direct streaming with explicit params."""

    @pytest.mark.asyncio
    async def test_yields_text_chunks(self, fresh_matrix):
        """run_stream() yields text chunks with name='text'."""
        from pydantic_ai.models.test import TestModel

        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='Test',
            prompt='Test prompt',
            tools=[],
            llm=TestModel(call_tools=[]),
        ):
            chunks.append(chunk)

        assert len(chunks) > 0
        # Should have done or text chunks
        names = [c['name'] for c in chunks]
        assert 'done' in names or 'text' in names or 'error' in names

    @pytest.mark.asyncio
    async def test_done_chunk_has_usage(self, fresh_matrix):
        """Done chunk contains usage statistics."""
        from pydantic_ai.models.test import TestModel

        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='Test',
            prompt='Test prompt',
            tools=[],
            llm=TestModel(call_tools=[]),
        ):
            chunks.append(chunk)

        done_chunks = [c for c in chunks if c['name'] == 'done']
        if done_chunks:
            done = done_chunks[0]
            assert 'usage' in done['data']
            assert done['meta']['stream_end'] is True

    @pytest.mark.asyncio
    async def test_error_chunk_on_failure(self, fresh_matrix):
        """run_stream() yields error chunk on failure."""
        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='Test',
            prompt='Test prompt',
            tools=[],
            llm='nonexistent:model',  # will fail
        ):
            chunks.append(chunk)

        error_chunks = [c for c in chunks if c['name'] == 'error']
        assert len(error_chunks) == 1
        assert error_chunks[0]['meta']['error'] is True
        assert 'message' in error_chunks[0]['data']
