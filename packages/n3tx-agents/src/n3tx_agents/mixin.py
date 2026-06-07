"""AgentMixin — injected into models with __agent__ = True.

Self-aware models: one flag gives a model LLM-powered reasoning about itself.
``__agent__ = True`` is as powerful as ``__storable__ = True`` — zero config,
full capability.

API Surface (all @fullmethod — unified class/instance dispatch):
    ctx()            @fullmethod  — Build LLM context from schema (class or instance)
    tools()          @fullmethod  — Discover tool addresses (self + neighbors + extras)
    agentic()        @fullmethod  — Policy layer: config cascade, prompt/tool assembly
    run()            @fullmethod  — Engine: raw LLM loop, explicit params, no magic
    agentic_stream() @fullmethod  — Streaming policy (delegates to run_stream)
    run_stream()     @fullmethod  — Streaming engine: yields TX-aligned chunks

The split: agentic() is the boundary where you enforce constraints and resolve config.
run() is the engine that just works. Expose agentic() via HTTP, never run().

Injection follows the same pattern as StorableMixin:
    __storable__ = True  →  injects StorableMixin
    __agent__    = True  →  injects AgentMixin

Usage:
    class Product(ActorModel):
        __agent__ = True

        @expose_route('/analyze', methods=['POST'])
        async def analyze(self, query: str) -> str:
            result = await self.agentic(task=query)
            return result['answer']

    # Streaming variant
    class Product(ActorModel):
        __agent__ = True

        @expose_route('/analyze', methods=['POST'], stream=True)
        async def analyze(self, query: str):
            async for chunk in self.agentic_stream(task=query):
                yield chunk
"""

import json
import logging

from n3tx_core.models.proto_schema import run_pipeline
from n3tx_core import config
from n3tx_core.utils.descriptors import fullmethod
from n3tx_core.utils.introspection import get_list_fields

from n3tx_agents.agent import Agent, CallConfig
from n3tx_agents.utils import (
    _build_instance_text,
)



logger = logging.getLogger('n3tx.agents')


# ── AgentMixin ────────────────────────────────────────────────────

class AgentMixin:
    """Provides self-aware agent capabilities for models with __agent__ = True.

    Injected into any model with __agent__ = True via __init_subclass__.
    Zero config required — ctx(), tools(), and agentic() auto-discover everything
    from the model's schema, relationships, and config.

    API Surface (all @fullmethod — unified class/instance dispatch):
        ctx()              — LLM context from schema (class) or schema+data (instance)
        tools()            — Tool addresses: self + neighbors + extras
        agentic(task=...)  — Policy: config cascade → run()
        run(...)           — Engine: raw LLM loop with explicit params
        agentic_stream()   — Streaming policy → run_stream()
        run_stream()       — Streaming engine: TX-aligned chunks
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

        # Generate LLM context from model schema as cleaned JSON.
        cleaned = run_pipeline(cls, pipeline='llm')
        tablename = getattr(cls, '__tablename__', cls.__name__)
        context = (f'You operate on {cls.__name__} entities (table: {tablename}).\n\n'
                f'Schema:\n{json.dumps(cleaned, indent=2)}')

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
    def run_config(target, task: str, **kwargs) -> CallConfig:
        """Resolve one policy-layer agent call from target + kwargs."""
        cls = target if isinstance(target, type) else target.__class__
        agent_flag = getattr(cls, '__agent__', False)
        model_conf = agent_flag if isinstance(agent_flag, dict) else {}
        defaults = config.AGENT_DEFAULTS

        prompt = kwargs.get('prompt') or target.ctx()
        tools = kwargs['tools'] if 'tools' in kwargs else target.tools()

        constraints = dict(defaults.get('constraints', {}))
        constraints.update(model_conf.get('constraints', {}))
        constraints.update(kwargs.get('constraints', {}))

        return CallConfig(
            task=task,
            prompt=prompt,
            tools=tools,
            user=kwargs.get('user'),
            constraints=constraints,
            thread_id=kwargs.get('thread_id'),
            result_type=kwargs.get('result_type') or model_conf.get('result_type'),
            llm=kwargs.get('llm'),
            has_llm_override='llm' in kwargs,
        )

    @fullmethod
    async def agentic(target, task: str, **kwargs) -> dict:
        """Public entry point for agent reasoning threaded conversation.

        Resolves config via 3-tier cascade, builds prompt, discovers tools,
        delegates to run().

        Config resolution (3-tier cascade):
            config.AGENT_DEFAULTS < __agent__ dict < agentic() kwargs

        Product.agentic(task='...')   → class-level (schema context)
        product.agentic(task='...')   → instance-level (schema + instance data)

        Override this to add guardrails, audit logging, or rate limiting.
        Call run() directly to bypass this layer entirely.
        """
        config = target.run_config(task, **kwargs)
        return await target.run(**config.runtime_args())


    @fullmethod
    async def run(target, task: str, prompt: str, tools: list,
                  user: dict = None, constraints: dict = None,
                  thread_id=None, result_type=None, **kwargs) -> dict:
        """Execute the LLM agent loop.

        Resolves LLM from model config (3-tier cascade), can be overridden
        via kwargs['llm'] (used by agentic() and tests).

        Product.run(task=..., prompt=..., tools=...) → class-level
        product.run(task=..., prompt=..., tools=...) → instance-level

        Args:
            task: The user task / query to execute.
            prompt: System prompt for the LLM.
            tools: List of actor addresses whose methods become tools.
            user: Auth context (JWT user dict).
            constraints: Budget/safety limits dict.
            thread_id: Thread ID for persistent conversation history.
                       Reads/updates Thread via TX for multi-turn support.
            result_type: Pydantic model for structured output.
            **kwargs: Override llm (LLM model string or pydantic_ai Model).

        Returns:
            dict with keys:
                answer: The LLM's final output (str or structured type).
                usage: {input_tokens, output_tokens, requests}
                messages: All conversation messages (list).
                message_count: Number of messages (backward compat).
                thread_id: Thread ID (when thread was used).
        """
        call = CallConfig(
            task=task,
            prompt=prompt,
            tools=tools,
            user=user,
            constraints=constraints or {},
            thread_id=thread_id,
            result_type=result_type,
            llm=kwargs.get('llm'),
            has_llm_override='llm' in kwargs,
        )
        prepared = await Agent.prepare(target, call)
        return await Agent.call(prepared, call.task)

    @fullmethod
    async def agentic_stream(target, task: str, **kwargs):
        """Streaming orchestration — same config cascade as agentic(), yields chunks.

        Product.agentic_stream(task='...')  → async gen of TX-aligned chunks
        product.agentic_stream(task='...')  → async gen with instance context
        """
        call = target.run_config(task, **kwargs)

        if isinstance(target, type):
            instance = target()
        else:
            instance = target

        async for chunk in instance.run_stream(**call.runtime_args()):
            yield chunk

    @fullmethod
    async def run_stream(target, task: str, prompt: str, tools: list,
                         user: dict = None, constraints: dict = None,
                         thread_id=None, result_type=None, **kwargs):
        """Streaming agent loop — yields TX-aligned chunks.

        Same LLM resolution as run(). Returns an async generator.

        Product.run_stream(task=..., prompt=..., tools=...) → class-level
        product.run_stream(task=..., prompt=..., tools=...) → instance-level

        TX-Aligned Chunk Format:
            {'name': 'text',        'data': {'text': '...'}, 'meta': {'stream': True, 'seq': N}}
            {'name': 'tool_call',   'data': {'tool': '...', 'args': {...}, 'call_id': '...'}, 'meta': {'stream': True, 'seq': N}}
            {'name': 'tool_result', 'data': {'tool': '...', 'result': '...', 'call_id': '...'}, 'meta': {'stream': True, 'seq': N}}
            {'name': 'thinking',    'data': {'text': '...'}, 'meta': {'stream': True, 'seq': N}}
            {'name': 'done',        'data': {'answer': '...', 'usage': {...}, 'tool_calls': N}, 'meta': {'stream_end': True}}
            {'name': 'error',       'data': {'message': '...'}, 'meta': {'error': True}}
        """
        call = CallConfig(
            task=task,
            prompt=prompt,
            tools=tools,
            user=user,
            constraints=constraints or {},
            thread_id=thread_id,
            result_type=result_type,
            llm=kwargs.get('llm'),
            has_llm_override='llm' in kwargs,
        )
        try:
            prepared = await Agent.prepare(target, call)
            async for chunk in Agent.call_stream(prepared, call.task):
                yield chunk
        except Exception as e:
            yield {
                'name': 'error',
                'data': {'message': str(e), 'code': 500},
                'meta': {'stream': True, 'error': True, 'seq': 0},
            }
