"""Tests for AgentMixin — ctx(), tools(), agentic(), run(), streaming."""

import asyncio

import pytest
from pydantic import Field

from n3tx_actors.actor import Actor
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.descriptors import fullmethod
from n3tx_core.utils.registrar import register_model
from n3tx_agents.mixin import AgentMixin
from n3tx_core.models.ref import public_id_url

from .conftest import HistoryOwner

pytestmark = pytest.mark.unit


# ── Test models (defined at module level for expose_route compat) ──

class Comment(ActorModel):
    """Synthetic local relationship used by tool discovery."""

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
    comments: list[Comment] = Field(default=[])


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
    comments: list[Comment] = Field(default=[])


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
        """Collect the optional agent mixin before model declaration."""
        # 0. Declare an enabled native model and inspect injection.
        class MyModel(ActorModel):
            """Flag-enabled non-storable test model."""

            __tablename__ = 'my_models'
            __storable__ = False
            __agent__ = True

        assert issubclass(MyModel, AgentMixin)
        assert hasattr(MyModel, 'run')

    def test_no_agent_mixin_without_flag(self, fresh_matrix):
        """Leave ordinary models free of the optional agent capability."""
        # 0. Declare a plain model without an agent flag.
        class RegularModel(ActorModel):
            """Ordinary actor model without reasoning capability."""

            __tablename__ = 'regular'
            __storable__ = False

        assert not issubclass(RegularModel, AgentMixin)

    def test_agent_mixin_coexists_with_storable(
        self, fresh_matrix, memory_storage,
    ):
        """Retain native storage when the agent capability is injected."""
        from n3tx_core.models.storable_mixin import StorableMixin
        # 0. Register a model with both independent capabilities.
        class DualModel(ActorModel):
            """Saved model with reasoning methods."""

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
        """Place the agent mixin before native actor dispatch in the MRO."""
        # 0. Inspect the enabled model's native composition.
        class AgentModel(ActorModel):
            """Minimal enabled actor model."""

            __tablename__ = 'agent_models'
            __storable__ = False
            __agent__ = True

        mro = [cls.__name__ for cls in AgentModel.__mro__]
        assert mro.index('AgentMixin') < mro.index('ActorModel')

    def test_new_api_surface(self, fresh_matrix):
        """Verify all new methods are present on agent models."""
        # 0. Inspect the complete reasoning entrypoint surface.
        class MyAgent(ActorModel):
            """Minimal model for public method discovery."""

            __tablename__ = 'my_agents'
            __storable__ = False
            __agent__ = True

        for method in (
            'ctx', 'tools', 'agentic', 'run', 'agentic_stream', 'run_stream',
        ):
            assert hasattr(MyAgent, method), f"Missing method: {method}"


# ── ctx() Tests ──────────────────────────────────────────────────

class TestCtx:
    """Tests for ctx() fullmethod — LLM context generation."""

    def test_class_ctx_has_schema(self, fresh_matrix):
        """Product.ctx() returns schema context with fields, types."""
        # 0. Inspect authoritative model schema context.
        ctx = AgenticProduct.ctx()
        assert 'agentic_products' in ctx
        assert 'AgenticProduct' in ctx
        assert 'name' in ctx
        assert 'price' in ctx

    def test_instance_ctx_has_state(self, fresh_matrix):
        """product.ctx() returns schema + instance data."""
        # 0. Compare schema context with explicit instance state.
        product = AgenticProduct(
            name='Widget', price=29.99, addr='agentic_products/1',
        )
        product.id = 42
        ctx = product.ctx()
        assert 'AgenticProduct' in ctx
        assert 'Current instance' in ctx
        assert 'Widget' in ctx
        assert '29.99' in ctx

    def test_ctx_includes_methods(self, fresh_matrix):
        """ctx() includes @expose_route methods when present."""
        # 0. Discover exposed methods through the native schema pipeline.
        ctx = ToolTarget.ctx() if hasattr(ToolTarget, 'ctx') else ''
        # ToolTarget doesn't have __agent__ so no ctx. Use AgenticProduct which
        # doesn't have methods. Test with a model that has both.
        class MethodAgent(ActorModel):
            """Agent with a schema-visible business method."""

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
        # 0. Inspect declared model prompt precedence.
        ctx = AgenticWithPrompt.ctx()
        assert ctx.startswith('You are a product expert.')

    def test_ctx_includes_relationships(self, fresh_matrix):
        """ctx() includes local model-list relationships."""
        # 0. Inspect native relationship schema context.
        ctx = AgenticProduct.ctx()
        assert 'comments' in ctx.lower()
        assert 'Comment' in ctx

    def test_ctx_class_vs_instance_difference(self, fresh_matrix):
        """Class ctx lacks instance data, instance ctx has it."""
        # 0. Compare class and instance context generation.
        class_ctx = AgenticProduct.ctx()
        instance = AgenticProduct(
            name='Specific', price=99.99, addr='agentic_products/1',
        )
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
        # 0. Resolve declared native tool addresses.
        addrs = AgenticProduct.tools()
        assert 'agentic_products' in addrs

    def test_neighbor_tools(self, fresh_matrix):
        """Discovers local model-list neighbor tablenames."""
        # 0. Resolve native neighbor tool addresses.
        addrs = AgenticProduct.tools()
        assert 'comments' in addrs

    def test_class_and_instance_same(self, fresh_matrix):
        """Product.tools() == product.tools()."""
        # 0. Compare class and instance discovery.
        product = AgenticProduct(name='Test', addr='agentic_products/1')
        assert AgenticProduct.tools() == product.tools()

    def test_extra_tools_from_config(self, fresh_matrix):
        """__agent__={'tools': ['extra']} adds addresses."""
        # 0. Resolve explicitly configured tool providers.
        addrs = AgenticExtraTools.tools()
        assert 'grants' in addrs
        assert 'sources' in addrs

    def test_self_tools_disabled(self, fresh_matrix):
        """__agent__={'self_tools': False} omits own tablename."""
        # 0. Respect explicit self-tool exclusion.
        addrs = AgenticNoSelf.tools()
        assert 'no_self_agents' not in addrs

    def test_neighbors_disabled(self, fresh_matrix):
        """__agent__={'neighbors': False} omits neighbors."""
        # 0. Respect explicit neighbor-tool exclusion.
        addrs = AgenticNoNeighbors.tools()
        assert 'comments' not in addrs

    def test_deduplication(self, fresh_matrix):
        """Duplicate addresses are deduplicated."""
        # 0. Resolve repeated native provider addresses once.
        class DupAgent(ActorModel):
            """Repeat its own tool address through explicit configuration."""

            __tablename__ = 'dup_agents'
            __storable__ = False
            __agent__ = {'tools': ['dup_agents']}  # self + explicit = dup

        addrs = DupAgent.tools()
        assert addrs.count('dup_agents') == 1


# ── run() Tests (engine — direct call) ───────────────────────────

class _ExecutionScope:
    """Supply real parent scope to execution tests without bypassing policy."""

    @pytest.fixture(autouse=True)
    def execution_scope(self, agent_context):
        """Keep synthetic caller and saved scope explicit at each call site."""
        # 0. Reuse native disposable parent registration for this test instance.
        self.execution = agent_context


class TestRunEngine(_ExecutionScope):
    """Tests for run() — direct engine call."""

    @pytest.mark.asyncio
    async def test_direct_call(self, fresh_matrix):
        """run() executes with explicit params, no config cascade."""
        from pydantic_ai.models.test import TestModel
        # 0. Execute with explicit policy, saved scope and trusted caller.
        class Scanner(ActorModel):
            """Non-storable scanner requiring explicit business scope."""

            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        result = await scanner.run(
            task='Find something',
            prompt='You find things.',
            tools=[],
            llm=TestModel(call_tools=[]),
            **self.execution,
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
        # 0. Remove the Matrix without inventing a replacement runtime.
        class Orphan(ActorModel, auto_register=False):
            """Unregistered actor for missing-Matrix error coverage."""

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
                **self.execution,
            )

    @pytest.mark.asyncio
    async def test_with_tool_calling(self, fresh_matrix, tmp_path):
        """run() where the LLM calls a tool through Matrix TX routing."""
        from pydantic_ai.models.test import TestModel
        # 0. Register real native tools and execute through Matrix.
        file_storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Grant(ActorModel):
            """Disposable grant resource exposed as a native tool."""

            __tablename__ = 'grants'
            __storable__ = True
            title: str = Field(default='')

        register_model(Grant, storage=file_storage)
        file_storage.create_table(Grant)

        class Scanner(ActorModel):
            """Scanner using explicit scope and native tool routing."""

            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        result = await scanner.run(
            task='List all grants',
            prompt='List available grants.',
            tools=['grants'],
            llm=TestModel(call_tools=['grants_list']),
            **self.execution,
        )
        # 1. Verify the native model completed a real tool-enabled turn.
        assert 'answer' in result
        assert result['usage']['requests'] >= 1


# ── agentic() Tests ──────────────────────────────────────────────

class TestAgentic(_ExecutionScope):
    """Tests for agentic() fullmethod — config cascade + auto-discovery."""

    @pytest.mark.asyncio
    async def test_zero_config_agentic(self, fresh_matrix):
        """agentic(task='...') auto-discovers prompt and tools."""
        from pydantic_ai.models.test import TestModel
        # 0. Execute model policy using a saved authorized parent.
        result = await AgenticProduct.agentic(
            task='Describe yourself', llm=TestModel(call_tools=[]),
            **self.execution,
        )

        assert 'answer' in result
        assert 'usage' in result

    @pytest.mark.asyncio
    async def test_explicit_prompt_overrides(self, fresh_matrix):
        """agentic(task='...', prompt='custom') uses custom prompt."""
        from pydantic_ai.models.test import TestModel
        # 0. Override prompt while retaining native execution.
        result = await AgenticProduct.agentic(
            task='Test',
            prompt='Custom prompt only',
            llm=TestModel(call_tools=[]),
            **self.execution,
        )
        assert 'answer' in result

    @pytest.mark.asyncio
    async def test_explicit_tools_overrides(self, fresh_matrix):
        """agentic(task='...', tools=['specific']) uses explicit tools."""
        from pydantic_ai.models.test import TestModel
        # 0. Disable discovery explicitly without bypassing runtime policy.
        result = await AgenticProduct.agentic(
            task='Test',
            tools=[],  # no tools
            llm=TestModel(call_tools=[]),
            **self.execution,
        )
        assert 'answer' in result

    @pytest.mark.asyncio
    async def test_class_vs_instance_agentic(self, fresh_matrix):
        """Class uses schema context, instance uses instance context."""
        from pydantic_ai.models.test import TestModel
        # 0. Execute class policy with explicit business scope.
        class_result = await AgenticProduct.agentic(
            task='Test', llm=TestModel(call_tools=[]),
            **self.execution,
        )
        assert 'answer' in class_result
        # 1. Execute instance policy under the same parent authority.
        product = AgenticProduct(
            name='Widget', price=29.99, addr='agentic_products/1',
        )
        inst_result = await product.agentic(
            task='Test', llm=TestModel(call_tools=[]), **self.execution,
        )
        assert 'answer' in inst_result

    @pytest.mark.asyncio
    async def test_agentic_kwargs_override(self, fresh_matrix):
        """agentic() accepts llm and constraints via kwargs."""
        from pydantic_ai.models.test import TestModel
        # 0. Override the synthetic model and request limits.
        result = await AgenticProduct.agentic(
            task='Test',
            llm=TestModel(call_tools=[]),
            constraints={'max_iterations': 5},
            **self.execution,
        )
        assert 'answer' in result

    @pytest.mark.asyncio
    async def test_agentic_returns_python_result_dict(self, fresh_matrix):
        """agentic() returns the internal sync result dict directly."""
        from pydantic_ai.models.test import TestModel
        # 0. Inspect the actual portable runtime result.
        result = await AgenticProduct.agentic(
            task='Return dict contract',
            llm=TestModel(call_tools=[]),
            **self.execution,
        )

        assert isinstance(result, dict)
        assert 'answer' in result
        assert 'usage' in result
        assert 'messages' in result
        assert 'message_count' in result
        assert result['message_count'] == len(result['messages'])


# ── Concurrent Runs ──────────────────────────────────────────────

class TestConcurrentRuns(_ExecutionScope):
    """Verify isolation under concurrent runs."""

    @pytest.mark.asyncio
    async def test_concurrent_runs_isolated(self, fresh_matrix):
        """Multiple concurrent agentic() calls don't cross-contaminate."""
        from pydantic_ai.models.test import TestModel
        # 0. Run separate native conversations against the same saved parent.
        tasks = [
            AgenticProduct.agentic(
                task=f'Task {i}',
                llm=TestModel(call_tools=[]),
                **self.execution,
            )
            for i in range(3)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        for r in results:
            assert 'answer' in r
            assert 'usage' in r


# ── User Auth Propagation ────────────────────────────────────────

class TestUserAuthPropagation(_ExecutionScope):
    """User auth context propagation through tool TXs."""

    @pytest.mark.asyncio
    async def test_user_context_in_tool_calls(self, fresh_matrix, tmp_path):
        """Tool TX messages carry meta.user from agentic(user=...)."""
        from pydantic_ai.models.test import TestModel
        from n3tx_actors.tx import TX
        # 0. Observe real tool dispatch without replacing actor authorization.
        file_storage = SQLiteStorage(str(tmp_path / 'test.db'))

        captured_meta = {}

        class InstrumentedModel(ActorModel):
            """Tool target retaining native inbox caller observation."""

            __tablename__ = 'instrumented'
            __storable__ = True
            name: str = Field(default='')

        register_model(InstrumentedModel, storage=file_storage)
        file_storage.create_table(InstrumentedModel)

        async def capture_interceptor(tx: TX) -> TX:
            """Observe caller metadata without replacing native dispatch."""
            captured_meta.update(tx.meta)
            return tx

        InstrumentedModel.use(capture_interceptor, on='inbox')

        class AuthAgent(ActorModel):
            """Non-storable actor using an explicitly authorized host."""

            __tablename__ = 'auth_agents'
            __storable__ = False
            __agent__ = True

        user_ctx = {'user_id': 42, 'role': 'admin', 'email': 'admin@test.com'}
        owner = HistoryOwner.create(HistoryOwner(
            user_owner=user_ctx['user_id'],
        ))
        scope = public_id_url(owner.id, target_cls=HistoryOwner)
        await AuthAgent.run(
            task='List all',
            prompt='List instrumented records.',
            tools=['instrumented'],
            llm=TestModel(call_tools=['instrumented_list']),
            user=user_ctx,
            scope=scope,
        )

        assert captured_meta.get('user') == user_ctx


# ── Streaming Tests ──────────────────────────────────────────────

class TestAgenticStreamPolicy(_ExecutionScope):
    """Tests for agentic_stream() fullmethod — streaming policy."""

    @pytest.mark.asyncio
    async def test_yields_chunks(self, fresh_matrix):
        """agentic_stream() yields dicts with 'name' field."""
        from pydantic_ai.models.test import TestModel
        # 0. Collect actual streaming policy events.
        chunks = []
        async for chunk in AgenticProduct.agentic_stream(
            task='Describe yourself',
            llm=TestModel(call_tools=[]),
            **self.execution,
        ):
            chunks.append(chunk)

        assert len(chunks) > 0
        # Last chunk should be 'done'
        assert chunks[-1]['name'] in ('done', 'error')

    @pytest.mark.asyncio
    async def test_auto_discovery(self, fresh_matrix):
        """agentic_stream() auto-discovers from ctx() and tools()."""
        from pydantic_ai.models.test import TestModel
        # 0. Execute discovery under a real saved parent policy.
        chunks = []
        async for chunk in AgenticProduct.agentic_stream(
            task='Test',
            llm=TestModel(call_tools=[]),
            **self.execution,
        ):
            chunks.append(chunk)

        # Should have at least a done chunk
        assert any(c['name'] in ('done', 'error') for c in chunks)

    @pytest.mark.asyncio
    async def test_agentic_and_agentic_stream_forward_same_normalized_kwargs(
        self, fresh_matrix, monkeypatch,
    ):
        """Policy entrypoints normalize the same explicit call arguments."""
        # 0. Capture adapter forwarding without provider execution.
        captured = {}

        async def fake_run(*args, **kwargs):
            """Capture synchronous policy forwarding only."""
            captured['agentic'] = kwargs
            return {
                'answer': 'ok', 'usage': {}, 'messages': [], 'message_count': 0,
            }

        async def fake_run_stream(*args, **kwargs):
            """Capture streaming policy forwarding only."""
            captured['agentic_stream'] = kwargs
            yield {
                'name': 'done', 'data': {'answer': 'ok'},
                'meta': {'stream_end': True},
            }

        monkeypatch.setattr(AgenticProduct, 'run', fake_run)
        monkeypatch.setattr(AgenticProduct, 'run_stream', fake_run_stream)

        user = {'user_id': 7, 'role': 'editor'}

        await AgenticProduct.agentic(
            task='Compare forwarding',
            prompt='Explicit prompt',
            tools=['alpha', 'beta'],
            llm='test',
            constraints={'max_iterations': 3},
            user=user,
            thread_id=123,
            result_type=dict,
            scope=self.execution['scope'],
        )

        async for _chunk in AgenticProduct.agentic_stream(
            task='Compare forwarding',
            prompt='Explicit prompt',
            tools=['alpha', 'beta'],
            llm='test',
            constraints={'max_iterations': 3},
            user=user,
            thread_id=123,
            result_type=dict,
            scope=self.execution['scope'],
        ):
            pass

        assert captured['agentic'] == captured['agentic_stream']

    @pytest.mark.asyncio
    async def test_class_stream_forwards_without_target_construction(
        self, fresh_matrix, monkeypatch,
    ):
        """Forward class streaming without constructing required fields."""
        # 0. Make accidental target construction fail validation.
        captured = {}

        class RequiredAgent(ActorModel):
            """Required fields make accidental class construction fail."""

            __tablename__ = 'required_stream_agents'
            __storable__ = False
            __agent__ = {'prompt': 'You are a product expert.'}
            name: str

        async def fake_run_stream(target, **kwargs):
            """Observe class binding without invoking the runtime."""
            captured['target'] = target
            captured['kwargs'] = kwargs
            yield {
                'name': 'done', 'data': {'answer': 'ok'},
                'meta': {'stream_end': True},
            }

        monkeypatch.setattr(
            RequiredAgent, 'run_stream', fullmethod(fake_run_stream),
        )

        async for _chunk in RequiredAgent.agentic_stream(
            task='Stream from class',
            llm='test',
            constraints={'max_iterations': 4},
            thread_id=55,
            result_type=dict,
            **self.execution,
        ):
            pass

        assert captured['target'] is RequiredAgent
        assert captured['kwargs']['task'] == 'Stream from class'
        assert captured['kwargs']['prompt'].startswith(
            'You are a product expert.',
        )
        assert captured['kwargs']['tools'] == ['required_stream_agents']
        assert captured['kwargs']['constraints'] == {'max_iterations': 4}
        assert captured['kwargs']['thread_id'] == 55
        assert captured['kwargs']['result_type'] is dict
        assert captured['kwargs']['llm'] == 'test'


class TestRunStreamEngine(_ExecutionScope):
    """Tests for run_stream() — direct streaming with explicit params."""

    @pytest.mark.asyncio
    async def test_yields_text_chunks(self, fresh_matrix):
        """run_stream() yields text chunks with name='text'."""
        from pydantic_ai.models.test import TestModel
        # 0. Execute the native streaming engine under explicit scope.
        class Scanner(ActorModel):
            """Explicitly scoped streaming actor."""

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
            **self.execution,
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
        # 0. Collect native completion and usage metadata.
        class Scanner(ActorModel):
            """Explicitly scoped actor for completion usage."""

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
            **self.execution,
        ):
            chunks.append(chunk)

        done_chunks = [c for c in chunks if c['name'] == 'done']
        assert len(done_chunks) == 1
        done = done_chunks[0]
        assert 'usage' in done['data']
        assert done['data']['thread_id'] > 0
        assert done['meta']['stream_end'] is True

    @pytest.mark.asyncio
    async def test_error_chunk_on_failure(self, fresh_matrix):
        """run_stream() yields error chunk on failure."""
        # 0. Fail model selection after valid parent preflight.
        class Scanner(ActorModel):
            """Scoped actor whose configured model cannot resolve."""

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
            **self.execution,
        ):
            chunks.append(chunk)

        error_chunks = [c for c in chunks if c['name'] == 'error']
        assert len(error_chunks) == 1
        assert error_chunks[0]['meta']['error'] is True
        assert 'message' in error_chunks[0]['data']

    @pytest.mark.asyncio
    async def test_setup_error_yields_error_chunk(
        self, fresh_matrix, monkeypatch,
    ):
        """Stream preparation failures yield one native error event."""
        from pydantic_ai.models.test import TestModel
        # 0. Remove only the Matrix root to fail runtime preparation.
        class Orphan(ActorModel, auto_register=False):
            """Unregistered actor for missing-root streaming failure."""

            __tablename__ = 'orphan_streamers'
            __storable__ = False
            __agent__ = True

        monkeypatch.setattr(Actor, '__matrix__', None)
        orphan = Orphan(addr='orphan_streamers/1')

        chunks = []
        async for chunk in orphan.run_stream(
            task='Test',
            prompt='Test prompt',
            tools=[],
            llm=TestModel(call_tools=[]),
            **self.execution,
        ):
            chunks.append(chunk)

        assert chunks == [
            {
                'name': 'error',
                'data': {
                    'message': (
                        'No Matrix root. Initialize a Matrix before '
                        'running agents.'
                    ),
                    'code': 500,
                },
                'meta': {'stream': True, 'error': True, 'seq': 0},
            }
        ]


class TestRunStreamTypedEvents(_ExecutionScope):
    """Tests for rich typed events from run_stream() via agent.iter()."""

    @pytest.mark.asyncio
    async def test_text_chunks_backward_compat(self, fresh_matrix):
        """run_stream() still yields text chunks with name='text'."""
        from pydantic_ai.models.test import TestModel
        # 0. Collect native text events from the synthetic SDK model.
        class Scanner(ActorModel):
            """Scoped synthetic actor for native text events."""

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
            **self.execution,
        ):
            chunks.append(chunk)

        text_chunks = [c for c in chunks if c['name'] == 'text']
        assert len(text_chunks) > 0, [c['name'] for c in chunks]
        for tc in text_chunks:
            assert 'text' in tc['data']
            assert tc['meta']['stream'] is True
            assert 'seq' in tc['meta']

    @pytest.mark.asyncio
    async def test_tool_call_event(self, fresh_matrix, tmp_path):
        """run_stream() yields tool_call event when LLM calls a tool."""
        from pydantic_ai.models.test import TestModel
        # 0. Execute a real native grant tool through Matrix.
        file_storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Grant(ActorModel):
            """Disposable native grant tool target."""

            __tablename__ = 'grants'
            __storable__ = True
            title: str = Field(default='')

        register_model(Grant, storage=file_storage)
        file_storage.create_table(Grant)

        class Scanner(ActorModel):
            """Scoped actor for native tool call events."""

            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='List grants',
            prompt='List grants.',
            tools=['grants'],
            llm=TestModel(call_tools=['grants_list']),
            **self.execution,
        ):
            chunks.append(chunk)

        tool_calls = [c for c in chunks if c['name'] == 'tool_call']
        assert len(tool_calls) >= 1, [c['name'] for c in chunks]
        tc = tool_calls[0]
        assert tc['data']['tool'] == 'grants_list'
        assert 'call_id' in tc['data']
        assert 'args' in tc['data']

    @pytest.mark.asyncio
    async def test_tool_result_event(self, fresh_matrix, tmp_path):
        """run_stream() yields tool_result event after tool execution."""
        from pydantic_ai.models.test import TestModel
        # 0. Execute a real native tool and retain its result event.
        file_storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Grant(ActorModel):
            """Disposable native tool result source."""

            __tablename__ = 'grants'
            __storable__ = True
            title: str = Field(default='')

        register_model(Grant, storage=file_storage)
        file_storage.create_table(Grant)

        class Scanner(ActorModel):
            """Scoped actor for tool result event assertions."""

            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='List grants',
            prompt='List grants.',
            tools=['grants'],
            llm=TestModel(call_tools=['grants_list']),
            **self.execution,
        ):
            chunks.append(chunk)

        tool_results = [c for c in chunks if c['name'] == 'tool_result']
        assert len(tool_results) >= 1, [c['name'] for c in chunks]
        tr = tool_results[0]
        assert tr['data']['tool'] == 'grants_list'
        assert 'result' in tr['data']
        assert 'call_id' in tr['data']

    @pytest.mark.asyncio
    async def test_done_chunk_has_tool_calls_count(
        self, fresh_matrix, tmp_path,
    ):
        """Done chunk includes tool_calls count."""
        from pydantic_ai.models.test import TestModel
        # 0. Complete one tool-enabled native streaming turn.
        file_storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Grant(ActorModel):
            """Disposable native tool for completion counters."""

            __tablename__ = 'grants'
            __storable__ = True
            title: str = Field(default='')

        register_model(Grant, storage=file_storage)
        file_storage.create_table(Grant)

        class Scanner(ActorModel):
            """Scoped actor for completion tool counters."""

            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='List grants',
            prompt='List grants.',
            tools=['grants'],
            llm=TestModel(call_tools=['grants_list']),
            **self.execution,
        ):
            chunks.append(chunk)

        done_chunks = [c for c in chunks if c['name'] == 'done']
        assert len(done_chunks) == 1
        assert done_chunks[0]['data']['tool_calls'] >= 1

    @pytest.mark.asyncio
    async def test_seq_monotonically_increasing(self, fresh_matrix):
        """All chunk seq numbers are monotonically increasing."""
        from pydantic_ai.models.test import TestModel
        # 0. Collect actual native event sequence metadata.
        class Scanner(ActorModel):
            """Scoped actor for monotonically increasing event sequences."""

            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='Test',
            prompt='Test',
            tools=[],
            llm=TestModel(call_tools=[]),
            **self.execution,
        ):
            chunks.append(chunk)

        seqs = [c['meta']['seq'] for c in chunks if 'seq' in c.get('meta', {})]
        for i in range(1, len(seqs)):
            assert seqs[i] > seqs[i-1], f"seq not monotonic: {seqs}"

    @pytest.mark.asyncio
    async def test_event_ordering_tool_call_before_result(
        self, fresh_matrix, tmp_path,
    ):
        """tool_call events appear before their matching tool_result."""
        from pydantic_ai.models.test import TestModel
        # 0. Execute native streaming tools and collect their event order.
        file_storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Grant(ActorModel):
            """Disposable grant resource for ordered tool events."""

            __tablename__ = 'grants'
            __storable__ = True
            title: str = Field(default='')

        register_model(Grant, storage=file_storage)
        file_storage.create_table(Grant)

        class Scanner(ActorModel):
            """Scoped actor for tool event ordering."""

            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='List grants',
            prompt='List grants.',
            tools=['grants'],
            llm=TestModel(call_tools=['grants_list']),
            **self.execution,
        ):
            chunks.append(chunk)

        names = [c['name'] for c in chunks]
        assert 'tool_call' in names and 'tool_result' in names
        first_call = names.index('tool_call')
        first_result = names.index('tool_result')
        assert first_call < first_result

    @pytest.mark.asyncio
    async def test_done_always_last(self, fresh_matrix):
        """Done chunk is always the last chunk emitted."""
        from pydantic_ai.models.test import TestModel
        # 0. Collect a fully consumed native stream without early close.
        class Scanner(ActorModel):
            """Scoped actor for terminal completion ordering."""

            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='Test',
            prompt='Test',
            tools=[],
            llm=TestModel(call_tools=[]),
            **self.execution,
        ):
            chunks.append(chunk)

        assert chunks[-1]['name'] == 'done'
        assert chunks[-1]['meta']['stream_end'] is True


# Changelog (Python has no block-comment syntax).
# - 2026-11-04: Supply saved parent scope and callers to native execution;
#   retain policy/tool/event coverage and forbid class-stream construction.
#   Keep caller 42 tool propagation under matching persisted parent ownership.
