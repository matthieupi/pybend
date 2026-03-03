"""AgentMixin — injected into models with __agent__ = True.

Provides agent_run() for LLM-powered reasoning. Tool calls route through
Matrix as TX messages, preserving auth and interceptors. Uses Pydantic AI
as the LLM engine — PyBend only provides the binding layer.

Injection follows the same pattern as StorableMixin:
    __storable__ = True  →  injects StorableMixin
    __agent__    = True  →  injects AgentMixin

Usage:
    class Product(ActorModel):
        __agent__ = True

        @expose_route('/create_from_text', methods=['POST'])
        async def create_from_text(self, text: str, tools: list = []) -> str:
            result = await self.agent_run(
                prompt="Parse freeform text into a Product.",
                tools=["products"] + tools,
                task=text,
            )
            return result['answer']
"""

import logging

logger = logging.getLogger('pybend.agents')


class AgentMixin:
    """Provides agent_run() for LLM-powered method execution.

    Injected into any model with __agent__ = True via __init_subclass__.
    Creates a transient NetworkAdapter per run for request/response
    correlation, discovers tools from actor addresses, and delegates
    the LLM loop to Pydantic AI.
    """

    async def agent_run(self, prompt: str, tools: list, task: str,
                        user: dict = None, **kwargs) -> dict:
        """Execute an LLM reasoning loop with Matrix-routed tools.

        Creates a Pydantic AI Agent internally, discovers tools from the
        specified actor addresses, routes tool calls through Matrix as TX,
        and returns structured results.

        Args:
            prompt: System prompt for the LLM.
            tools: List of actor addresses whose @expose_route methods
                   become available tools for the LLM.
            task: The user task / query to execute.
            user: Auth context (JWT user dict). Passed to tool TXs.
            **kwargs:
                llm: Override LLM model (string or pydantic_ai.Model instance).
                constraints: Override constraints dict.

        Returns:
            dict with keys:
                answer: The LLM's final output (str).
                usage: {input_tokens, output_tokens, requests}
                messages: Total message count in the conversation.
        """
        from pydantic_ai import Agent, UsageLimits
        from pybend.core.api.network_adapter import NetworkAdapter
        from pybend.core.actors.actor import Actor
        from pybend.core.actors.tx import TX
        from pybend.core.agents.deps import AgentDeps
        from pybend.core.agents.tools import discover_tools, make_tool

        # ── Resolve config ──
        llm = kwargs.get('llm') or getattr(self, 'llm', 'ollama:llama3.1')
        constraints = dict(getattr(self, 'constraints', None) or {})
        constraints.update(kwargs.get('constraints', {}))

        # ── Agent address ──
        if isinstance(self, type):
            agent_addr = getattr(self, '__addr__', self.__name__)
        else:
            agent_addr = (
                getattr(self, '_addr', '')
                or getattr(self.__class__, '__addr__', '')
            )

        # ── Transient adapter for this run ──
        # Each agent_run() gets its own NetworkAdapter with its own
        # _pending dict for Future-based request/response correlation.
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
            tool_specs = discover_tools(tools, root)
            if not tool_specs:
                logger.warning(
                    "[%s] No tools discovered from addresses: %s", agent_addr, tools
                )
            ai_tools = [make_tool(spec) for spec in tool_specs]

            # ── Build Pydantic AI agent ──
            ai_agent = Agent(
                llm,
                system_prompt=prompt,
                deps_type=AgentDeps,
                tools=ai_tools,
            )

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
            result = await ai_agent.run(task, deps=deps, usage_limits=usage_limits)

            usage = result.usage()
            return {
                'answer': result.output,
                'usage': {
                    'input_tokens': usage.input_tokens,
                    'output_tokens': usage.output_tokens,
                    'requests': usage.requests,
                },
                'messages': len(result.all_messages()),
            }

        finally:
            # Cleanup: remove transient adapter from Matrix
            root._children.pop(adapter_addr, None)
