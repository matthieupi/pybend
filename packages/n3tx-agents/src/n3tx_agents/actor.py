"""AgentActor — A model whose instances ARE agents.

Configuration lives in fields (DB-storable). Agents are data, not code.

    # In code
    scanner = AgentActor(
        name="Grant Scanner",
        prompt="You find government grants...",
        tools=[AgentTool(target="grants"), AgentTool(target="sources")],
        llm="anthropic:claude-sonnet-4-5-20250929",
    )

    # Via API (tools via join table)
    # POST /agents {"name": "Grant Scanner", "prompt": "...", "llm": "..."}
    # POST /agents/1/agent_tools {"addr": "grants"}

    # From DB
    scanner = AgentActor.get(1)

    # Trigger
    result = await scanner.agentic(task="Scan all sources for new grants")
    # or POST /agents/1/agentic {"task": "Scan all sources"}
"""

import json
import logging

from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.models.ref import ListRef
from n3tx_core.utils.decorators import expose_route
from n3tx_agents.tool_model import AgentTool

logger = logging.getLogger('n3tx.agents')


class AgentActor(ActorModel):
    """A model whose instances ARE agents. Configuration is data, not code.

    Fields:
        name: Human-readable agent name.
        prompt: System prompt for the LLM.
        tools: Collection of AgentTool records (via ListRef join table).
        llm: Pydantic AI provider:model string (e.g., 'ollama:llama3.1').
        constraints: Budget/safety limits dict.

    Storage: constraints is serialized to JSON TEXT for SQLite.
             tools uses the standard ListRef join-table pattern.
    """

    __tablename__ = 'agents'
    __storable__ = True
    __agent__ = True  # injects AgentMixin → provides agentic()

    name: str = Field(min_length=1, max_length=200)
    prompt: str = Field(default='')
    tools: ListRef[AgentTool] = Field(default=[])
    llm: str = Field(default='ollama:llama3.1')
    constraints: dict = Field(default={})

    def _resolve_tool_addrs(self) -> list:
        """Resolve tool addresses from ListRef hrefs or AgentTool instances.

        When loaded from DB, self.tools is hydrated as href arrays
        (e.g., ["http://.../agents/1/agent_tools/1", ...]). This method
        extracts the actor target from each tool reference.

        Returns:
            List of actor address strings (e.g., ['grants', 'sources']).
        """
        tool_addrs = []
        if not self.tools:
            return tool_addrs
        # Use the join model (from __fk_models__) for lookups since records
        # live in the join table, not the base agent_tools table.
        fk_models = getattr(self.__class__, '__fk_models__', {})
        tool_cls = fk_models.get('tools', AgentTool)

        # Collect href IDs for batch fetch instead of N+1 individual gets
        href_ids = []
        for item in self.tools:
            if isinstance(item, AgentTool):
                tool_addrs.append(item.target)
            elif isinstance(item, str) and '/' in item:
                try:
                    href_ids.append(int(item.rstrip('/').split('/')[-1]))
                except (ValueError, TypeError):
                    logger.warning("Could not resolve tool href: %s", item)
            elif isinstance(item, str):
                # plain addr string (e.g., from in-memory construction)
                tool_addrs.append(item)

        # Batch fetch all href-referenced tools in one query
        if href_ids:
            tools = tool_cls.list(ids=href_ids)
            records = tools['data'] if isinstance(tools, dict) else tools
            for tool in records:
                tool_addrs.append(tool.target)

        return tool_addrs

    @expose_route('/agentic', methods=['POST'])
    async def agentic(self, task: str, **kwargs) -> str:
        """Execute the agent's reasoning loop.

        Override — resolves tools from DB instead of __agent__ config.
        Calls AgentMixin.run() directly (pure engine), bypassing the
        mixin's agentic() config cascade since AgentActor has its own config
        (DB fields).

        Args:
            task: The user task / query to execute.
            **kwargs: Override llm, constraints, user, thread_id, result_type.

        Returns:
            JSON string with {answer, usage, messages, message_count}.
        """
        from n3tx_agents.mixin import AgentMixin
        tool_addrs = self._resolve_tool_addrs()
        # Call the mixin's run engine directly via the descriptor's
        # underlying function, bypassing the MRO override on self.
        run_fn = AgentMixin.__dict__['run'].fn
        result = await run_fn(
            self,
            task=task,
            prompt=self.prompt,
            tools=tool_addrs,
            llm=kwargs.get('llm', self.llm),
            constraints={**self.constraints, **kwargs.get('constraints', {})},
            user=kwargs.get('user'),
            thread_id=kwargs.get('thread_id'),
            result_type=kwargs.get('result_type'),
        )
        return json.dumps(result, default=str)

    @expose_route('/agentic_stream', methods=['POST'], stream=True)
    async def agentic_stream(self, task: str, **kwargs):
        """Streaming agent execution — resolves tools from DB.

        Override — same as agentic() but yields TX-aligned stream chunks.
        Calls AgentMixin.run_stream() directly, bypassing the mixin's
        agentic_stream() config cascade since AgentActor has its own config.

        Args:
            task: The user task / query to execute.
            **kwargs: Override llm, constraints, user, thread_id, result_type.

        Yields:
            TX-aligned dicts: text, tool_call, tool_result, thinking, done, error.
        """
        from n3tx_agents.mixin import AgentMixin
        tool_addrs = self._resolve_tool_addrs()
        run_stream_fn = AgentMixin.__dict__['run_stream'].fn
        async for chunk in run_stream_fn(
            self,
            task=task,
            prompt=self.prompt,
            tools=tool_addrs,
            llm=kwargs.get('llm', self.llm),
            constraints={**self.constraints, **kwargs.get('constraints', {})},
            user=kwargs.get('user'),
            thread_id=kwargs.get('thread_id'),
            result_type=kwargs.get('result_type'),
        ):
            yield chunk
