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
    result = await scanner.run(task="Scan all sources for new grants")
    # or POST /agents/1/run {"task": "Scan all sources"}
"""

import json
import logging

from typing import Optional

from pydantic import Field

from n3tx.core.models.actor_model import ActorModel
from n3tx.core.models.ref import ListRef
from n3tx.core.utils.decorators import expose_route
from n3tx.core.agents.tool_model import AgentTool

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
    __agent__ = True  # injects AgentMixin → provides agent_run()

    name: str = Field(min_length=1, max_length=200)
    prompt: str = Field(default='')
    tools: Optional[ListRef[AgentTool]] = Field(default=[])
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
        for item in self.tools:
            if isinstance(item, AgentTool):
                tool_addrs.append(item.target)
            elif isinstance(item, str) and '/' in item:
                # href — extract ID, fetch via join model
                try:
                    tool_id = int(item.rstrip('/').split('/')[-1])
                    tool = tool_cls.get(tool_id)
                    if tool:
                        tool_addrs.append(tool.target)
                except (ValueError, TypeError):
                    logger.warning("Could not resolve tool href: %s", item)
            elif isinstance(item, str):
                # plain addr string (e.g., from in-memory construction)
                tool_addrs.append(item)
        return tool_addrs

    @expose_route('/run', methods=['POST'])
    async def run(self, task: str, **kwargs) -> str:
        """Execute the agent's reasoning loop.

        Args:
            task: The user task / query to execute.
            **kwargs: Passed to agent_run() (e.g., llm, constraints overrides).

        Returns:
            JSON string with {answer, usage, messages}.
        """
        tool_addrs = self._resolve_tool_addrs()
        result = await self.agent_run(
            prompt=self.prompt,
            tools=tool_addrs,
            task=task,
            **kwargs,
        )
        return json.dumps(result, default=str)
