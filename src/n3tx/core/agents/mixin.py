"""AgentMixin — injected into models with __agent__ = True.

Self-aware models: one flag gives a model LLM-powered reasoning about itself.
``__agent__ = True`` is as powerful as ``__storable__ = True`` — zero config,
full capability.

API Surface (all @fullmethod — unified class/instance dispatch):
    ctx()            @fullmethod  — Build LLM context from schema (class or instance)
    tools()          @fullmethod  — Discover tool addresses (self + neighbors + extras)
    run()            @fullmethod  — Policy layer: config cascade, prompt/tool assembly
    agentic()        @fullmethod  — Engine: raw LLM loop, explicit params, no magic
    run_stream()     @fullmethod  — Streaming policy (delegates to agentic_stream)
    agentic_stream() @fullmethod  — Streaming engine: yields TX-aligned chunks

The split: run() is the boundary where you enforce constraints and resolve config.
agentic() is the engine that just works. Expose run() via HTTP, never agentic().

Injection follows the same pattern as StorableMixin:
    __storable__ = True  →  injects StorableMixin
    __agent__    = True  →  injects AgentMixin

Usage:
    class Product(ActorModel):
        __agent__ = True

        @expose_route('/analyze', methods=['POST'])
        async def analyze(self, query: str) -> str:
            result = await self.run(task=query)
            return result['answer']

    # Streaming variant
    class Product(ActorModel):
        __agent__ = True

        @expose_route('/analyze', methods=['POST'], stream=True)
        async def analyze(self, query: str):
            async for chunk in self.run_stream(task=query):
                yield chunk
"""

import json
import logging

from pydantic_ai import Agent, UsageLimits
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider

from n3tx.core import config
from n3tx.core.actors.actor import Actor
from n3tx.core.actors.tx import TX
from n3tx.core.agents.deps import AgentDeps
from n3tx.core.agents.tools import discover_tools, make_tool
from n3tx.core.api.network_adapter import NetworkAdapter
from n3tx.core.utils.descriptors import fullmethod
from n3tx.core.utils.introspection import get_list_fields

logger = logging.getLogger('n3tx.agents')


# ── LLM resolution (module-level) ────────────────────────────────

def _resolve_llm(llm):
    """Resolve an LLM string to a pydantic-ai model instance.

    Handles 'ollama:model' strings by creating an OpenAIChatModel with
    OllamaProvider(base_url=config.OLLAMA_BASE_URL) so we don't rely on
    environment variables being set.

    Passes through non-ollama strings and existing model instances as-is.
    """
    if not isinstance(llm, str) or not llm.startswith('ollama:'):
        return llm

    model_name = llm.split(':', 1)[1]
    base_url = config.OLLAMA_BASE_URL.rstrip('/')
    if not base_url.endswith('/v1'):
        base_url += '/v1'
    return OpenAIChatModel(
        model_name,
        provider=OllamaProvider(base_url=base_url),
    )


# ── Context helpers (module-level, used by ctx()) ─────────────────

def _build_schema_text(cls) -> str:
    """Generate LLM context from model schema as cleaned JSON."""
    from n3tx.core.models.proto_schema import run_pipeline
    cleaned = run_pipeline(cls, pipeline='llm')
    tablename = getattr(cls, '__tablename__', cls.__name__)
    return (f'You operate on {cls.__name__} entities (table: {tablename}).\n\n'
            f'Schema:\n{json.dumps(cleaned, indent=2)}')


def _build_instance_text(target) -> str:
    """Append current instance state to context."""
    try:
        data = target.model_dump()
    except Exception:
        return ''

    # Truncate long values
    truncated = {}
    for k, v in data.items():
        s = str(v)
        if len(s) > 200:
            s = s[:200] + '...'
        truncated[k] = v if len(str(v)) <= 200 else s

    try:
        data_str = json.dumps(truncated, indent=2, default=str)
    except Exception:
        data_str = str(truncated)

    instance_id = getattr(target, 'id', '?')
    return f'\n\nCurrent instance (id={instance_id}):\n{data_str}'


# ── AgentMixin ────────────────────────────────────────────────────

class AgentMixin:
    """Provides self-aware agent capabilities for models with __agent__ = True.

    Injected into any model with __agent__ = True via __init_subclass__.
    Zero config required — ctx(), tools(), and run() auto-discover everything
    from the model's schema, relationships, and config.

    API Surface (all @fullmethod — unified class/instance dispatch):
        ctx()            — LLM context from schema (class) or schema+data (instance)
        tools()          — Tool addresses: self + neighbors + extras
        run(task=...)    — Policy: config cascade → agentic()
        agentic(...)     — Engine: raw LLM loop with explicit params
        run_stream(...)  — Streaming policy → agentic_stream()
        agentic_stream() — Streaming engine: TX-aligned chunks
    """

    @fullmethod
    def ctx(target) -> str:
        """Build LLM context from model schema.

        Class:    Product.ctx()  → schema context (fields, types, methods)
        Instance: product.ctx() → schema context + current instance data

        If __agent__['prompt'] is set, it is prepended to the auto-generated context.
        """
        cls = target if isinstance(target, type) else target.__class__
        agent_flag = getattr(cls, '__agent__', False)
        conf = agent_flag if isinstance(agent_flag, dict) else {}

        context = _build_schema_text(cls)

        # Prepend __agent__['prompt'] if configured
        prompt_prefix = conf.get('prompt', '')
        if prompt_prefix:
            context = prompt_prefix + '\n\n' + context

        # Instance context: append current state
        if not isinstance(target, type):
            context += _build_instance_text(target)

        return context

    @fullmethod
    def tools(target) -> list:
        """Discover tool actor addresses for this model.

        Returns list[str] of actor addresses. Tool resolution (addr → ToolSpec)
        is deferred to agentic() where discover_tools() is called.

        Product.tools()  → ['products', 'comments']
        product.tools()  → same (tools come from schema, not instance)
        """
        cls = target if isinstance(target, type) else target.__class__
        agent_flag = getattr(cls, '__agent__', False)
        conf = agent_flag if isinstance(agent_flag, dict) else {}

        addrs = []

        # Self tools (own CRUD + methods)
        if conf.get('self_tools', True):
            tablename = getattr(cls, '__tablename__', cls.__name__)
            addrs.append(tablename)

        # Neighbor tools (ListRef relationships)
        if conf.get('neighbors', True):
            for field_name, model_cls in get_list_fields(cls):
                if hasattr(model_cls, '__tablename__'):
                    addrs.append(model_cls.__tablename__)

        # Extra tools from __agent__ config
        extra = conf.get('tools', [])
        if extra:
            addrs.extend(extra)

        # Deduplicate, preserve order
        return list(dict.fromkeys(addrs))

    @fullmethod
    async def run(target, task: str, **kwargs) -> dict:
        """Public entry point for agent reasoning.

        Resolves config via 3-tier cascade, builds prompt, discovers tools,
        manages adapter lifecycle, delegates to agentic().

        Config resolution (3-tier cascade):
            config.AGENT_DEFAULTS < __agent__ dict < run() kwargs

        Product.run(task='...')   → class-level (schema context)
        product.run(task='...')   → instance-level (schema + instance data)

        Override this to add guardrails, audit logging, or rate limiting.
        Call agentic() directly to bypass this layer entirely.
        """
        cls = target if isinstance(target, type) else target.__class__
        agent_flag = getattr(cls, '__agent__', False)
        model_conf = agent_flag if isinstance(agent_flag, dict) else {}

        # 3-tier cascade: config.AGENT_DEFAULTS < __agent__ dict < kwargs
        defaults = config.AGENT_DEFAULTS

        # Prompt: kwargs > auto-generated ctx
        prompt = kwargs.get('prompt') or target.ctx()

        # Tools: kwargs > auto-discovered (use 'in' check — [] is valid)
        tools = kwargs['tools'] if 'tools' in kwargs else target.tools()

        # LLM: kwargs > __agent__['llm'] > instance attr > defaults
        llm = (kwargs.get('llm')
               or model_conf.get('llm')
               or getattr(target, 'llm', None)
               or defaults.get('llm', 'ollama:llama3.1'))

        # Constraints: merge all tiers
        constraints = dict(defaults.get('constraints', {}))
        constraints.update(model_conf.get('constraints', {}))
        constraints.update(kwargs.get('constraints', {}))

        # Pass-through params
        user = kwargs.get('user')
        message_history = kwargs.get('message_history')
        result_type = kwargs.get('result_type') or model_conf.get('result_type')

        # Adapter lifecycle: create transient adapter for this run
        run_id = TX(name='', source='', target='').uuid
        adapter_addr = f'_agent_{run_id}'
        adapter = NetworkAdapter(addr=adapter_addr)
        root = Actor.root()
        if not root:
            raise RuntimeError(
                "No Matrix root. Initialize a Matrix before running agents."
            )
        root.register(adapter)

        try:
            # Resolve target for agentic() — need an instance
            if isinstance(target, type):
                instance = target()
            else:
                instance = target

            return await instance.agentic(
                task=task,
                prompt=prompt,
                tools=tools,
                user=user,
                llm=llm,
                constraints=constraints,
                adapter=adapter,
                message_history=message_history,
                result_type=result_type,
            )
        finally:
            root._children.pop(adapter_addr, None)

    @fullmethod
    async def agentic(target, task: str, prompt: str, tools: list,
                      user: dict = None, llm=None, constraints: dict = None,
                      adapter=None, message_history=None,
                      result_type=None, **kwargs) -> dict:
        """Execute the LLM agent loop. Pure execution — no config resolution.

        Receives fully resolved params from run(). Can also be called directly
        for advanced use cases (testing, pipelines, custom workflows).

        Product.agentic(task=..., prompt=..., tools=...) → class-level
        product.agentic(task=..., prompt=..., tools=...) → instance-level

        Args:
            task: The user task / query to execute.
            prompt: System prompt for the LLM.
            tools: List of actor addresses whose methods become tools.
            user: Auth context (JWT user dict).
            llm: LLM model string or pydantic_ai Model instance.
            constraints: Budget/safety limits dict.
            adapter: NetworkAdapter for TX routing (created if None).
            message_history: Previous messages for multi-turn.
            result_type: Pydantic model for structured output.

        Returns:
            dict with keys:
                answer: The LLM's final output (str or structured type).
                usage: {input_tokens, output_tokens, requests}
                messages: All conversation messages (list).
                message_count: Number of messages (backward compat).
        """
        cls = target if isinstance(target, type) else target.__class__
        instance = target if not isinstance(target, type) else target()

        # ── Defaults ──
        llm = _resolve_llm(llm or 'ollama:llama3.1')
        constraints = constraints or {}

        # ── Agent address ──
        agent_addr = (
            getattr(instance, '_addr', '')
            or getattr(cls, '__addr__', '')
        )

        # ── Adapter lifecycle ──
        owns_adapter = adapter is None
        if owns_adapter:
            run_id = TX(name='', source='', target='').uuid
            adapter_addr = f'_agent_{run_id}'
            adapter = NetworkAdapter(addr=adapter_addr)
            root = Actor.root()
            if not root:
                raise RuntimeError(
                    "No Matrix root. Initialize a Matrix before running agents."
                )
            root.register(adapter)

        try:
            # ── Discover tools from actor addresses ──
            root = Actor.root()
            tool_specs = discover_tools(tools, root, caller_addr=agent_addr)
            if not tool_specs:
                logger.warning(
                    "[%s] No tools discovered from addresses: %s", agent_addr, tools
                )
            ai_tools = [make_tool(spec) for spec in tool_specs]

            # ── Build Pydantic AI agent ──
            agent_kwargs = {
                'system_prompt': prompt,
                'deps_type': AgentDeps,
                'tools': ai_tools,
            }
            if result_type:
                agent_kwargs['output_type'] = result_type

            ai_agent = Agent(llm, **agent_kwargs)

            # ── Deps ──
            deps = AgentDeps(
                adapter=adapter,
                user=user,
                agent_addr=agent_addr,
            )

            # ── Usage limits ──
            usage_limits = None
            if constraints.get('max_iterations'):
                usage_limits = UsageLimits(
                    request_limit=constraints['max_iterations'],
                )

            # ── Run ──
            run_kwargs = {'deps': deps}
            if usage_limits:
                run_kwargs['usage_limits'] = usage_limits
            if message_history:
                run_kwargs['message_history'] = message_history

            result = await ai_agent.run(task, **run_kwargs)

            usage = result.usage()
            all_messages = result.all_messages()
            return {
                'answer': result.output,
                'usage': {
                    'input_tokens': usage.input_tokens,
                    'output_tokens': usage.output_tokens,
                    'requests': usage.requests,
                },
                'messages': all_messages,
                'message_count': len(all_messages),
            }

        finally:
            if owns_adapter:
                root._children.pop(adapter._addr, None)

    @fullmethod
    async def run_stream(target, task: str, **kwargs):
        """Streaming orchestration — same config cascade as run(), yields chunks.

        Product.run_stream(task='...')  → async gen of TX-aligned chunks
        product.run_stream(task='...')  → async gen with instance context
        """
        cls = target if isinstance(target, type) else target.__class__
        agent_flag = getattr(cls, '__agent__', False)
        model_conf = agent_flag if isinstance(agent_flag, dict) else {}

        # 3-tier cascade (same as run())
        defaults = config.AGENT_DEFAULTS
        prompt = kwargs.get('prompt') or target.ctx()
        # Tools: kwargs > auto-discovered (use 'in' check — [] is valid)
        tools = kwargs['tools'] if 'tools' in kwargs else target.tools()
        llm = (kwargs.get('llm')
               or model_conf.get('llm')
               or getattr(target, 'llm', None)
               or defaults.get('llm', 'ollama:llama3.1'))
        constraints = dict(defaults.get('constraints', {}))
        constraints.update(model_conf.get('constraints', {}))
        constraints.update(kwargs.get('constraints', {}))
        user = kwargs.get('user')
        message_history = kwargs.get('message_history')
        result_type = kwargs.get('result_type') or model_conf.get('result_type')

        # Adapter lifecycle
        run_id = TX(name='', source='', target='').uuid
        adapter_addr = f'_agent_{run_id}'
        adapter = NetworkAdapter(addr=adapter_addr)
        root = Actor.root()
        if not root:
            raise RuntimeError(
                "No Matrix root. Initialize a Matrix before running agents."
            )
        root.register(adapter)

        try:
            if isinstance(target, type):
                instance = target()
            else:
                instance = target

            async for chunk in instance.agentic_stream(
                task=task,
                prompt=prompt,
                tools=tools,
                user=user,
                llm=llm,
                constraints=constraints,
                adapter=adapter,
                message_history=message_history,
                result_type=result_type,
            ):
                # TODO Returns should be wrapped in proper TX, even for stream chunks
                yield chunk
        finally:
            root._children.pop(adapter_addr, None)

    @fullmethod
    async def agentic_stream(target, task: str, prompt: str, tools: list,
                             user: dict = None, llm=None, constraints: dict = None,
                             adapter=None, message_history=None,
                             result_type=None, **kwargs):
        """Streaming agent loop — yields TX-aligned chunks.

        Pure execution — no config resolution. Same params as agentic()
        but returns an async generator instead of a dict.

        Product.agentic_stream(task=..., prompt=..., tools=...) → class-level
        product.agentic_stream(task=..., prompt=..., tools=...) → instance-level

        TX-Aligned Chunk Format:
            {'name': 'text',        'data': {'text': '...'}, 'meta': {'stream': True, 'seq': N}}
            {'name': 'done',        'data': {'answer': '...', 'usage': {...}}, 'meta': {'stream_end': True}}
            {'name': 'error',       'data': {'message': '...'}, 'meta': {'error': True}}
        """
        cls = target if isinstance(target, type) else target.__class__
        instance = target if not isinstance(target, type) else target()

        # TODO Should not resolve to default LLM, should throw instead to send an error into the actor system to have \
        #  visibility on missing var
        llm = _resolve_llm(llm or 'ollama:llama3.1')
        constraints = constraints or {}

        agent_addr = (
            getattr(instance, '_addr', '')
            or getattr(cls, '__addr__', '')
        )

        owns_adapter = adapter is None
        if owns_adapter:
            run_id = TX(name='', source='', target='').uuid
            adapter_addr = f'_agent_{run_id}'
            adapter = NetworkAdapter(addr=adapter_addr)
            root = Actor.root()
            if not root:
                raise RuntimeError(
                    "No Matrix root. Initialize a Matrix before running agents."
                )
            root.register(adapter)

        seq = 0
        try:
            root = Actor.root()
            tool_specs = discover_tools(tools, root, caller_addr=agent_addr)
            ai_tools = [make_tool(spec) for spec in tool_specs]

            agent_kwargs = {
                'system_prompt': prompt,
                'deps_type': AgentDeps,
                'tools': ai_tools,
            }
            if result_type:
                agent_kwargs['output_type'] = result_type

            ai_agent = Agent(llm, **agent_kwargs)

            deps = AgentDeps(
                adapter=adapter,
                user=user,
                agent_addr=agent_addr,
            )

            usage_limits = None
            if constraints.get('max_iterations'):
                usage_limits = UsageLimits(
                    request_limit=constraints['max_iterations'],
                )

            run_kwargs = {'deps': deps}
            if usage_limits:
                run_kwargs['usage_limits'] = usage_limits
            if message_history:
                run_kwargs['message_history'] = message_history

            # Use Agent.run_stream() for token-level streaming
            streamed_text = ''
            async with ai_agent.run_stream(task, **run_kwargs) as result:
                async for text in result.stream_text(delta=True):
                    streamed_text += text
                    yield {
                        # TODO Add type (tool call, thinking, response etc)
                        'name': 'text',
                        'data': {'text': text},
                        'meta': {'stream': True, 'seq': seq},
                    }
                    seq += 1

                # Stream complete — emit final done chunk
                usage = result.usage()
                try:
                    output = await result.get_output()
                except Exception:
                    output = ''
                if not output and streamed_text:
                    output = streamed_text
                # TODO
                #  Replace by returning full output (text, thinking, tool calls, any other relevant info
                #  We can probably remove streamed_text and use output.
                yield {
                    'name': 'done',
                    'data': {
                        'answer': str(output),
                        'usage': {
                            'input_tokens': usage.input_tokens,
                            'output_tokens': usage.output_tokens,
                            'requests': usage.requests,
                        },
                    },
                    'meta': {
                        'stream': True,
                        'stream_end': True,
                        'seq': seq,
                    },
                }

        except Exception as e:

            yield {
                'name': 'error',
                'data': {'message': str(e), 'code': 500},
                'meta': {'stream': True, 'error': True, 'seq': seq},
            }
        finally:
            if owns_adapter:
                root._children.pop(adapter._addr, None)
