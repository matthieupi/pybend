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
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.ref import ListRef
from n3tx_core.utils.decorators import expose_route
from n3tx_agents.agent import Agent, CallConfig
from n3tx_agents.tool_model import AgentTool

logger = logging.getLogger('n3tx.agents')


# -- Stream event models (non-storable -- pure schema) ----------------------

class TextChunk(ProtoModel):
    """Progressive text output from the LLM."""
    text: str = Field(default='')

class ToolCallEvent(ProtoModel):
    """Agent is calling a tool."""
    tool: str = Field(default='')
    args: dict = Field(default={})
    call_id: str = Field(default='')

class ToolResultEvent(ProtoModel):
    """Result returned from a tool call."""
    tool: str = Field(default='')
    result: str = Field(default='')
    call_id: str = Field(default='')

class ThinkingChunk(ProtoModel):
    """Agent is in a thinking/reasoning phase."""
    text: str = Field(default='')

class DoneChunk(ProtoModel):
    """Terminal event -- agent completed the task."""
    answer: str = Field(default='')
    usage: dict = Field(default={})
    tool_calls: int = Field(default=0)


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
    __ui__ = {
        'renderer': {'item': 'ntx-agent', 'detail': 'ntx-agent'},
    }

    system_key: str = Field(
        default='',
        description='Stable machine identity for framework-provisioned app agents',
    )
    name: str = Field(min_length=1, max_length=200)
    prompt: str = Field(default='')
    tools: ListRef[AgentTool] = Field(default=[])
    llm: str = Field(default='ollama:llama3.1')
    constraints: dict = Field(default={})

    def tool_addrs(self) -> list:
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

    def call_config(self, task: str, thread_id: int = 0, **kwargs) -> CallConfig:
        """Build a DB-backed resolved call for the shared runtime seam."""
        return CallConfig(
            task=task,
            prompt=self.prompt,
            tools=self.tool_addrs(),
            user=kwargs.get('user'),
            constraints={**self.constraints, **kwargs.get('constraints', {})},
            thread_id=thread_id or None,
            result_type=kwargs.get('result_type'),
            llm=kwargs.get('llm', self.llm),
            has_llm_override=True,
        )

    @expose_route('/agentic', methods=['POST'])
    async def agentic(self, task: str, thread_id: int = 0, **kwargs) -> str:
        """Execute the agent's reasoning loop.

        Override — resolves DB-backed config, then delegates to the shared
        runtime seam used by mixin-based agents.

        Args:
            task: The user task / query to execute.
            thread_id: Existing conversation thread to continue. If omitted,
                a new thread is created automatically.
            **kwargs: Override llm, constraints, user, result_type.

        Returns:
            JSON string with {answer, usage, messages, message_count}.
        """
        call = self.call_config(task, thread_id=thread_id, **kwargs)
        prepared = await Agent.prepare(self, call)
        result = await Agent.call(prepared, call.task)
        return json.dumps(result, default=str)

    @expose_route('/agentic_stream', methods=['POST'], stream=True,
                  events={
                      'text': TextChunk, 'tool_call': ToolCallEvent,
                      'tool_result': ToolResultEvent, 'thinking': ThinkingChunk,
                      'done': DoneChunk,
                  })
    async def agentic_stream(self, task: str, thread_id: int = 0, **kwargs):
        """Streaming agent execution — resolves tools from DB.

        Override — same as agentic() but yields TX-aligned stream chunks via
        the shared runtime seam.

        Args:
            task: The user task / query to execute.
            thread_id: Existing conversation thread to continue. If omitted,
                a new thread is created automatically.
            **kwargs: Override llm, constraints, user, result_type.

        Yields:
            TX-aligned dicts: text, tool_call, tool_result, thinking, done, error.
        """
        call = self.call_config(task, thread_id=thread_id, **kwargs)
        prepared = await Agent.prepare(self, call)
        async for chunk in Agent.call_stream(prepared, call.task):
            yield chunk
