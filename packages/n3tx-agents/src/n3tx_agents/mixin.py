"""Model policy adapters for the single native agent preparation/run seam.

Agent-enabled models contribute schema context and tool selection. Trusted
callers supply identity and parent scope. A missing scope is inferred only from
a saved registered ActorModel instance; there is no implicit global Thread."""

import json
import logging

from n3tx_core import config
from n3tx_core.models.proto_schema import run_pipeline
from n3tx_core.models.ref import Ref
from n3tx_core.utils.descriptors import fullmethod
from n3tx_core.utils.introspection import get_fk_list_fields

from n3tx_agents.agent import Agent, CallConfig
from n3tx_agents.utils import _build_instance_text


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
        """Resolve policy while forwarding caller, thread ID and parent scope.

        An explicit empty tool list disables discovery. Scope inference and
        parent authorization belong to runtime preparation, not this adapter."""
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
        """Resolve model policy and execute a parent-scoped conversation.

        Constraints merge global, model and call dictionaries in that order.
        Prompt and tools follow run_config precedence. Class-level calls need
        an explicit saved parent scope; saved instances can infer their scope.
        Override this for guardrails, auditing or rate limits. Calling run()
        bypasses policy assembly, not runtime parent authorization."""
        # 0. Delegate resolved policy to the shared execution seam.
        config = target.run_config(task, **kwargs)
        return await target.run(**config.runtime_args())

    @fullmethod
    async def run(target, task: str, prompt: str, tools: list,
                  user: dict = None, constraints: dict = None,
                  thread_id=None, result_type=None,
                  scope: Ref | None = None, **kwargs) -> dict:
        """Execute the LLM agent loop.

        Resolves LLM from model config, target and global defaults unless
        kwargs['llm'] supplies an explicit override.

        Args:
            task: The user task / query to execute.
            prompt: System prompt for the LLM.
            tools: List of actor addresses whose methods become tools.
            user: Trusted caller context; None is anonymous for history access.
            constraints: Budget/safety limits dict.
            thread_id: Opaque conversation-root TTX ID for continuation.
            result_type: Pydantic model for structured output.
            scope: Saved local parent Ref. None infers a saved registered
                ActorModel target; other targets require an explicit scope.
            **kwargs: Override llm (LLM model string or pydantic_ai Model).

        Returns:
            dict with keys:
                answer: The LLM's final output (str or structured type).
                usage: {input_tokens, output_tokens, requests}
                messages: Raw loaded history followed by new SDK messages.
                message_count: Number of messages (backward compat).
                thread_id: Conversation-root TTX ID."""
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

        Class calls retain schema context without constructing an instance;
        they require an explicit saved local parent scope."""
        # 0. Resolve policy without constructing a model instance.
        call = target.run_config(task, **kwargs)
        # 1. Forward native events without a second execution loop.
        async for chunk in target.run_stream(**call.runtime_args()):
            yield chunk

    @fullmethod
    async def run_stream(target, task: str, prompt: str, tools: list,
                         user: dict = None, constraints: dict = None,
                         thread_id=None, result_type=None,
                         scope: Ref | None = None, **kwargs):
        """Streaming agent loop — yields TX-aligned chunks.

        Same LLM resolution as run(). Returns an async generator.

        Events retain name/data/meta and native text/tool/done/error semantics.
        Arguments follow run(): scope is a saved local parent Ref, and None
        infers only a saved registered ActorModel target, never a global root.
        Preparation errors become error events; policy errors occur upstream."""
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
# - 2026-11-04: Forward class streaming directly through fullmethod and document
#   saved parent scope inference and TTX-backed conversation identity.
