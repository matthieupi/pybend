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

from pydantic_ai import Agent, UsageLimits
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai._agent_graph import (
    ModelRequestNode, CallToolsNode, UserPromptNode, End,
)
from pydantic_ai.messages import (
    PartStartEvent, PartDeltaEvent, PartEndEvent,
    FunctionToolCallEvent, FunctionToolResultEvent,
    TextPart, ToolCallPart, ThinkingPart,
    TextPartDelta, ThinkingPartDelta, ToolCallPartDelta,
)

from n3tx_core import config
from n3tx_core.models.proto_schema import run_pipeline
from n3tx_core.utils.descriptors import fullmethod
from n3tx_core.utils.introspection import get_list_fields

from n3tx_actors.tx import TX
from n3tx_actors.actor import Actor

from n3tx_agents.deps import AgentDeps
from n3tx_agents.tools import discover_tools, make_tool
from n3tx_agents.thread import Thread



logger = logging.getLogger('n3tx.agents')


# ── LLM resolution (module-level) ────────────────────────────────

def _resolve_llm(llm):
    """Resolve an LLM string to a pydantic-ai model instance.

    Handles 'ollama:model' strings by creating an OpenAIChatModel with
    OllamaProvider(base_url=config.OLLAMA_BASE_URL) so we don't rely on
    environment variables being set.

    Raises ValueError if no LLM is provided.
    Passes through non-ollama strings and existing model instances as-is.
    """
    if not llm:
        raise ValueError(
            "No LLM provided. Pass an llm= argument "
            "(e.g., 'ollama:llama3.1', 'anthropic:claude-sonnet-4-5-20250929') "
            "or set it via __agent__['llm'] or config.AGENT_DEFAULTS['llm']."
        )
    if llm == 'test':
        from pydantic_ai.models.test import TestModel
        return TestModel(call_tools=[])
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
    # We will need to review the trucation to make sure we are not removing relevant context.
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


def _agent_scope(agent_addr: str, cls=None) -> str:
    if isinstance(agent_addr, str) and agent_addr:
        return agent_addr.split('/', 1)[0]
    if cls is not None:
        return getattr(cls, '__tablename__', cls.__name__)
    return ''


def _agent_addr(target, cls) -> str:
    """Resolve a concrete string actor address for class or instance calls."""
    addr = getattr(target, '_addr', '')
    if isinstance(addr, str) and addr:
        return addr

    addr = getattr(target, '__addr__', '')
    if isinstance(addr, str) and addr:
        return addr

    return getattr(cls, '__tablename__', cls.__name__)


def _thread_matches_agent(thread_data: dict, agent_addr: str, cls=None) -> bool:
    thread_agent = (thread_data or {}).get('agent_addr', '')
    if not thread_agent:
        return True
    scope = _agent_scope(agent_addr, cls=cls)
    return thread_agent == agent_addr or thread_agent == scope


def _thread_user(user):
    """Normalize route-injected users for Thread CRUD authorization.

    Custom model methods may receive a full User model instance while the
    Thread actor's ABAC rules expect the JWT-shaped dict carried by HTTP meta.
    """
    if user is None or isinstance(user, dict):
        return user
    user_id = getattr(user, 'id', None)
    if user_id is None:
        return user
    return {
        'user_id': user_id,
        'email': getattr(user, 'email', None),
        'role': getattr(user, 'role', 'user'),
    }


async def _get_thread(root, thread_id, user=None):
    auth_user = _thread_user(user)
    thread_tx = TX(
        name='get', source=root.addr, target='threads',
        data={'id': thread_id},
        meta={'user': auth_user} if auth_user else {},
    )
    thread_resp = await root.request(thread_tx)
    if thread_resp.is_error:
        raise RuntimeError(
            f"Thread {thread_id} not found or access denied: "
            f"{thread_resp.data.get('message', 'unknown error')}"
        )
    return thread_resp.data


async def _create_thread(root, agent_addr: str, user=None, cls=None):
    auth_user = _thread_user(user)
    payload = {
        'agent_addr': agent_addr or _agent_scope(agent_addr, cls=cls),
        'messages': [],
    }
    if isinstance(auth_user, dict) and auth_user.get('user_id') is not None:
        payload['user_owner'] = auth_user['user_id']

    create_tx = TX(
        name='create', source=root.addr, target='threads',
        data=payload,
        meta={'user': auth_user} if auth_user else {},
    )
    create_resp = await root.request(create_tx)
    if create_resp.is_error:
        raise RuntimeError(
            "Failed to create thread: "
            f"{create_resp.data.get('message', 'unknown error')}"
        )
    return create_resp.data


async def _load_or_create_thread(root, agent_addr: str, user=None,
                                 thread_id=None, cls=None):
    thread_data = None
    if thread_id is not None:
        thread_data = await _get_thread(root, thread_id, user=user)
        if not _thread_matches_agent(thread_data, agent_addr, cls=cls):
            raise RuntimeError(
                f"Thread {thread_id} belongs to {thread_data.get('agent_addr', 'another agent')}, "
                f"not {agent_addr or _agent_scope(agent_addr, cls=cls)}"
            )
    else:
        thread_data = await _create_thread(root, agent_addr, user=user, cls=cls)
        thread_id = thread_data.get('id')

    message_history = None
    if thread_data is not None:
        message_history = Thread.to_history(thread_data.get('messages', []))

    return thread_data, thread_id, message_history


async def _update_thread(root, thread_id, all_messages, user=None, source='', target=''):
    auth_user = _thread_user(user)
    update_tx = TX(
        name='update', source=root.addr, target='threads',
        data={
            'id': thread_id,
            'messages': Thread.from_history(
                all_messages,
                source=source,
                target=target,
            ),
        },
        meta={'user': auth_user} if auth_user else {},
    )
    update_resp = await root.request(update_tx)
    if update_resp.is_error:
        logger.warning(
            "Failed to update thread %s: %s",
            thread_id,
            update_resp.data.get('message', 'unknown'),
        )


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
    async def agentic(target, task: str, **kwargs) -> dict:
        """Public entry point for agent reasoning.

        Resolves config via 3-tier cascade, builds prompt, discovers tools,
        delegates to run().

        Config resolution (3-tier cascade):
            config.AGENT_DEFAULTS < __agent__ dict < agentic() kwargs

        Product.agentic(task='...')   → class-level (schema context)
        product.agentic(task='...')   → instance-level (schema + instance data)

        Override this to add guardrails, audit logging, or rate limiting.
        Call run() directly to bypass this layer entirely.
        """
        cls = target if isinstance(target, type) else target.__class__
        agent_flag = getattr(cls, '__agent__', False)
        model_conf = agent_flag if isinstance(agent_flag, dict) else {}
        defaults = config.AGENT_DEFAULTS

        # Prompt: kwargs > auto-generated ctx
        prompt = kwargs.get('prompt') or target.ctx()

        # Tools: kwargs > auto-discovered (use 'in' check — [] is valid)
        tools = kwargs['tools'] if 'tools' in kwargs else target.tools()

        # Constraints: merge all tiers
        constraints = dict(defaults.get('constraints', {}))
        constraints.update(model_conf.get('constraints', {}))
        constraints.update(kwargs.get('constraints', {}))

        # Pass-through params
        user = kwargs.get('user')
        thread_id = kwargs.get('thread_id')
        result_type = kwargs.get('result_type') or model_conf.get('result_type')

        # LLM resolved by run() from conf; pass explicit override if any
        run_kwargs = dict(
            task=task, prompt=prompt, tools=tools,
            user=user, constraints=constraints,
            thread_id=thread_id, result_type=result_type,
        )
        if 'llm' in kwargs:
            run_kwargs['llm'] = kwargs['llm']

        return await target.run(**run_kwargs)


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
        cls = target if isinstance(target, type) else target.__class__

        # ── LLM: kwargs > __agent__['llm'] > instance attr > AGENT_DEFAULTS ──
        agent_flag = getattr(cls, '__agent__', False)
        model_conf = agent_flag if isinstance(agent_flag, dict) else {}
        llm = _resolve_llm(
            kwargs.get('llm')
            or model_conf.get('llm')
            or getattr(target, 'llm', None)
            or config.AGENT_DEFAULTS.get('llm')
        )
        constraints = constraints or {}

        # ── Agent address ──
        agent_addr = _agent_addr(target, cls)

        # ── Matrix root (for request-response) ──
        root = Actor.root()
        if not root:
            raise RuntimeError(
                "No Matrix root. Initialize a Matrix before running agents."
            )

        # ── Thread: pre-run read ──
        _, thread_id, message_history = await _load_or_create_thread(
            root=root,
            agent_addr=agent_addr,
            user=user,
            thread_id=thread_id,
            cls=cls,
        )

        # ── Discover tools from actor addresses ──
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

        # ── Thread: post-run update ──
        if thread_id is not None:
            await _update_thread(
                root=root,
                thread_id=thread_id,
                all_messages=all_messages,
                user=user,
                source=root.addr,
                target=agent_addr,
            )

        result_dict = {
            'answer': result.output,
            'usage': {
                'input_tokens': usage.input_tokens,
                'output_tokens': usage.output_tokens,
                'requests': usage.requests,
            },
            'messages': all_messages,
            'message_count': len(all_messages),
        }
        if thread_id is not None:
            result_dict['thread_id'] = thread_id
        return result_dict

    @fullmethod
    async def agentic_stream(target, task: str, **kwargs):
        """Streaming orchestration — same config cascade as agentic(), yields chunks.

        Product.agentic_stream(task='...')  → async gen of TX-aligned chunks
        product.agentic_stream(task='...')  → async gen with instance context
        """
        cls = target if isinstance(target, type) else target.__class__
        agent_flag = getattr(cls, '__agent__', False)
        model_conf = agent_flag if isinstance(agent_flag, dict) else {}
        defaults = config.AGENT_DEFAULTS

        prompt = kwargs.get('prompt') or target.ctx()
        tools = kwargs['tools'] if 'tools' in kwargs else target.tools()
        constraints = dict(defaults.get('constraints', {}))
        constraints.update(model_conf.get('constraints', {}))
        constraints.update(kwargs.get('constraints', {}))
        user = kwargs.get('user')
        thread_id = kwargs.get('thread_id')
        result_type = kwargs.get('result_type') or model_conf.get('result_type')

        if isinstance(target, type):
            instance = target()
        else:
            instance = target

        # LLM resolved by run_stream() from conf; pass explicit override if any
        stream_kwargs = dict(
            task=task, prompt=prompt, tools=tools,
            user=user, constraints=constraints,
            thread_id=thread_id, result_type=result_type,
        )
        if 'llm' in kwargs:
            stream_kwargs['llm'] = kwargs['llm']

        async for chunk in instance.run_stream(**stream_kwargs):
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
        cls = target if isinstance(target, type) else target.__class__

        # ── LLM: kwargs > __agent__['llm'] > instance attr > AGENT_DEFAULTS ──
        agent_flag = getattr(cls, '__agent__', False)
        model_conf = agent_flag if isinstance(agent_flag, dict) else {}
        llm = _resolve_llm(
            kwargs.get('llm')
            or model_conf.get('llm')
            or getattr(target, 'llm', None)
            or config.AGENT_DEFAULTS.get('llm')
        )
        constraints = constraints or {}

        agent_addr = _agent_addr(target, cls)

        # ── Matrix root (for request-response) ──
        root = Actor.root()
        if not root:
            raise RuntimeError(
                "No Matrix root. Initialize a Matrix before running agents."
            )

        seq = 0
        try:
            # ── Thread: pre-run read ──
            _, thread_id, message_history = await _load_or_create_thread(
                root=root,
                agent_addr=agent_addr,
                user=user,
                thread_id=thread_id,
                cls=cls,
            )

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

            # ── Rich streaming via agent.iter() graph API ──
            streamed_text = ''
            tool_call_count = 0

            async with ai_agent.iter(task, **run_kwargs) as agent_run:
                async for node in agent_run:
                    if isinstance(node, ModelRequestNode):
                        async with node.stream(agent_run.ctx) as request_stream:
                            async for event in request_stream:
                                if isinstance(event, PartStartEvent):
                                    if isinstance(event.part, ToolCallPart):
                                        tool_call_count += 1
                                        # Normalize args: pydantic-ai ToolCallPart.args
                                        # can be str (raw JSON) or dict depending on the model.
                                        args = event.part.args
                                        if isinstance(args, str):
                                            try:
                                                args = json.loads(args)
                                            except (json.JSONDecodeError, TypeError):
                                                args = {'raw': args}
                                        yield {
                                            'name': 'tool_call',
                                            'data': {
                                                'tool': event.part.tool_name,
                                                'args': args,
                                                'call_id': event.part.tool_call_id,
                                            },
                                            'meta': {'stream': True, 'seq': seq},
                                        }
                                        seq += 1
                                    elif isinstance(event.part, ThinkingPart):
                                        if event.part.content:
                                            yield {
                                                'name': 'thinking',
                                                'data': {'text': event.part.content},
                                                'meta': {'stream': True, 'seq': seq},
                                            }
                                            seq += 1
                                    elif isinstance(event.part, TextPart):
                                        if event.part.content:
                                            streamed_text += event.part.content
                                            yield {
                                                'name': 'text',
                                                'data': {'text': event.part.content},
                                                'meta': {'stream': True, 'seq': seq},
                                            }
                                            seq += 1
                                elif isinstance(event, PartDeltaEvent):
                                    if isinstance(event.delta, TextPartDelta):
                                        streamed_text += event.delta.content_delta
                                        yield {
                                            'name': 'text',
                                            'data': {'text': event.delta.content_delta},
                                            'meta': {'stream': True, 'seq': seq},
                                        }
                                        seq += 1
                                    elif isinstance(event.delta, ThinkingPartDelta):
                                        yield {
                                            'name': 'thinking',
                                            'data': {'text': event.delta.content_delta},
                                            'meta': {'stream': True, 'seq': seq},
                                        }
                                        seq += 1
                    elif isinstance(node, CallToolsNode):
                        async with node.stream(agent_run.ctx) as tools_stream:
                            async for event in tools_stream:
                                if isinstance(event, FunctionToolResultEvent):
                                    yield {
                                        'name': 'tool_result',
                                        'data': {
                                            'tool': event.result.tool_name,
                                            'result': str(event.result.content),
                                            'call_id': event.result.tool_call_id,
                                        },
                                        'meta': {'stream': True, 'seq': seq},
                                    }
                                    seq += 1

                # ── Iteration complete — build done chunk ──
                run_result = agent_run.result
                usage = agent_run.usage()
                output = run_result.output if run_result else ''
                if not output and streamed_text:
                    output = streamed_text
                all_messages = agent_run.all_messages()

                # ── Thread: post-stream update ──
                if thread_id is not None:
                    await _update_thread(
                        root=root,
                        thread_id=thread_id,
                        all_messages=all_messages,
                        user=user,
                        source=root.addr,
                        target=agent_addr,
                    )

                done_data = {
                    'answer': str(output),
                    'usage': {
                        'input_tokens': usage.input_tokens,
                        'output_tokens': usage.output_tokens,
                        'requests': usage.requests,
                    },
                    'tool_calls': tool_call_count,
                }
                if thread_id is not None:
                    done_data['thread_id'] = thread_id

                yield {
                    'name': 'done',
                    'data': done_data,
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
