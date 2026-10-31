"""Model policy adapters for the single native agent preparation/run seam.

Agent-enabled models contribute schema context and tool selection. Trusted
callers supply identity and business scope; None means an explicit global
Thread, never implicit authorization from an actor address."""

import json
import logging

from n3tx_core.models.proto_schema import run_pipeline
from n3tx_core.models.ref import Ref
from n3tx_core import config
from n3tx_core.utils.descriptors import fullmethod
from n3tx_core.utils.introspection import get_fk_list_fields

from n3tx_agents.agent import Agent, CallConfig
from n3tx_agents.utils import (
    _build_instance_text,
)
logger = logging.getLogger('n3tx.agents')


class AgentMixin:
    """Resolve model policy while retaining native execution and access."""

    @fullmethod
    def ctx(target) -> str:
        """Build LLM context from model schema.

        Class:    Product.ctx()  → schema context (fields, types, methods)
        Instance: product.ctx() → schema context + current instance data

        The configured prompt prefixes the generated schema context."""
        # 0. Resolve the model policy and its schema pipeline.
        cls = target if isinstance(target, type) else target.__class__
        agent_flag = getattr(cls, '__agent__', False)
        conf = agent_flag if isinstance(agent_flag, dict) else {}
        # 1. Build schema context, then add configured and instance context.
        cleaned = run_pipeline(cls, pipeline='llm')
        tablename = getattr(cls, '__tablename__', cls.__name__)
        context = (
            f'You operate on {cls.__name__} entities '
            f'(table: {tablename}).\n\n'
            f'Schema:\n{json.dumps(cleaned, indent=2)}'
        )

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

        Returns list[str] of actor addresses. Tool resolution into ToolSpecs
        is deferred to agentic() where discover_tools() is called.

        Product.tools()  → ['products', 'comments']
        product.tools()  → same (tools come from schema, not instance)"""
        # 0. Resolve model-level discovery policy.
        cls = target if isinstance(target, type) else target.__class__
        agent_flag = getattr(cls, '__agent__', False)
        conf = agent_flag if isinstance(agent_flag, dict) else {}

        addrs = []
        # 1. Collect selected own, neighboring and explicit tool addresses.
        if conf.get('self_tools', True):
            tablename = getattr(cls, '__tablename__', cls.__name__)
            addrs.append(tablename)

        # Neighbor tools from local model-list relationships.
        if conf.get('neighbors', True):
            for field_name, model_cls in get_fk_list_fields(cls):
                if hasattr(model_cls, '__tablename__'):
                    addrs.append(model_cls.__tablename__)

        # Extra tools from __agent__ config
        extra = conf.get('tools', [])
        if extra:
            addrs.extend(extra)
        # 2. Deduplicate while preserving native discovery order.
        return list(dict.fromkeys(addrs))

    @fullmethod
    def run_config(target, task: str, **kwargs) -> CallConfig:
        """Resolve one policy-layer agent call from target + kwargs."""
        # 0. Merge model policy and explicit per-call configuration.
        cls = target if isinstance(target, type) else target.__class__
        agent_flag = getattr(cls, '__agent__', False)
        model_conf = agent_flag if isinstance(agent_flag, dict) else {}
        defaults = config.AGENT_DEFAULTS

        prompt = kwargs.get('prompt') or target.ctx()
        tools = kwargs['tools'] if 'tools' in kwargs else target.tools()

        constraints = dict(defaults.get('constraints', {}))
        constraints.update(model_conf.get('constraints', {}))
        constraints.update(kwargs.get('constraints', {}))
        # 1. Keep business scope separate from executing actor routing.
        return CallConfig(
            task=task,
            prompt=prompt,
            tools=tools,
            user=kwargs.get('user'),
            constraints=constraints,
            thread_id=kwargs.get('thread_id'),
            result_type=(
                kwargs.get('result_type') or model_conf.get('result_type')
            ),
            llm=kwargs.get('llm'),
            has_llm_override='llm' in kwargs,
            scope=kwargs.get('scope'),
        )

    @fullmethod
    async def agentic(target, task: str, **kwargs) -> dict:
        """Public entry point for agent reasoning threaded conversation.

        Resolves config via 3-tier cascade, builds prompt, discovers tools,
        delegates to run().

        Config resolution (3-tier cascade):
            config.AGENT_DEFAULTS < __agent__ dict < agentic() kwargs

        Product.agentic(task='...')   → class-level (schema context)
        product.agentic(task='...') -> instance-level schema and instance data

        Override this to add guardrails, audit logging, or rate limiting.
        Call run() directly to bypass this layer entirely."""
        # 0. Delegate resolved policy to the shared execution seam.
        config = target.run_config(task, **kwargs)
        return await target.run(**config.runtime_args())

    @fullmethod
    async def run(target, task: str, prompt: str, tools: list,
                  user: dict = None, constraints: dict = None,
                  thread_id=None, result_type=None,
                  scope: Ref | None = None, **kwargs) -> dict:
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
                       Reads native record-backed history for continuation.
            result_type: Pydantic model for structured output.
            scope: Trusted business reference, or None for a global Thread.
            **kwargs: Override llm (LLM model string or pydantic_ai Model).

        Returns:
            dict with keys:
                answer: The LLM's final output (str or structured type).
                usage: {input_tokens, output_tokens, requests}
                messages: All conversation messages (list).
                message_count: Number of messages (backward compat).
                thread_id: Thread ID (when thread was used)."""
        # 0. Preserve explicit runtime inputs rather than re-resolving policy.
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
            scope=scope,
        )
        # 1. Prepare once and execute through the native runtime.
        prepared = await Agent.prepare(target, call)
        return await Agent.run(prepared, call.task)

    @fullmethod
    async def agentic_stream(target, task: str, **kwargs):
        """Apply the agentic policy cascade and yield native streaming events.

        Product.agentic_stream(task='...')  → async gen of TX-aligned chunks
        product.agentic_stream(task='...') -> instance-context events"""
        # 0. Resolve policy and retain the existing instance streaming adapter.
        call = target.run_config(task, **kwargs)

        if isinstance(target, type):
            instance = target()
        else:
            instance = target
        # 1. Forward native events without a second execution loop.
        async for chunk in instance.run_stream(**call.runtime_args()):
            yield chunk

    @fullmethod
    async def run_stream(target, task: str, prompt: str, tools: list,
                         user: dict = None, constraints: dict = None,
                         thread_id=None, result_type=None,
                         scope: Ref | None = None, **kwargs):
        """Streaming agent loop — yields TX-aligned chunks.

        Same LLM resolution as run(). Returns an async generator.

        Product.run_stream(task=..., prompt=..., tools=...) → class-level
        product.run_stream(task=..., prompt=..., tools=...) → instance-level

        Events retain name/data/meta and native text/tool/done/error semantics.
        Scope is a trusted business Ref; None selects a global Thread."""
        # 0. Preserve explicit runtime inputs, including the business scope.
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
            scope=scope,
        )
        # 1. Delegate native preparation/execution and retain the error event.
        try:
            prepared = await Agent.prepare(target, call)
            async for chunk in Agent.run_stream(prepared, call.task):
                yield chunk
        except Exception as e:
            yield {
                'name': 'error',
                'data': {'message': str(e), 'code': 500},
                'meta': {'stream': True, 'error': True, 'seq': 0},
            }


# Changelog (Python has no block-comment syntax):
# - 2026-10-31: Forward explicit business scope through native agent adapters.
#   Normalize documentation and source layout.
