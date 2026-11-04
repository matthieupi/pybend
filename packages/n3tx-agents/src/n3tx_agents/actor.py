"""Stored agent configuration adapters and published stream event schemas.

Execution uses the shared parent-authorized runtime; saved agents can infer
their own parent scope. Stock exposed methods accept user only through kwargs:
HTTP authentication does not prove caller propagation. Direct HTTP also has
default/variadic argument parser limitations; see docs/agent-actor.md. These
adapters are not a safe arbitrary external execution boundary."""

import json
import logging
from typing import Optional

from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.models.proto_model import ProtoModel
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
    thread_id: Optional[int] = Field(default=None)


class AgentActor(ActorModel):
    """A model whose instances ARE agents. Configuration is data, not code.

    Fields:
        name: Human-readable agent name.
        prompt: System prompt for the LLM.
        tools: Collection of AgentTool records.
        llm: Pydantic AI provider:model string (e.g., 'ollama:llama3.1').
        constraints: Budget/safety limits dict.

    Storage: constraints is serialized to JSON TEXT for SQLite.
             tools uses the standard local model-list relationship pattern."""

    __tablename__ = 'agents'
    __storable__ = True
    __agent__ = True  # injects AgentMixin → provides agentic()
    __ui__ = {
        'renderer': {'item': 'ntx-agent', 'detail': 'ntx-agent'},
    }

    system_key: str = Field(
        default='',
        description=(
            'Stable machine identity for framework-provisioned app agents'
        ),
    )
    name: str = Field(min_length=1, max_length=200)
    prompt: str = Field(default='')
    tools: list[AgentTool] = Field(default=[])
    llm: str = Field(default='ollama:llama3.1')
    constraints: dict = Field(default={})

    def tool_addrs(self) -> list:
        """Resolve tool addresses from AgentTool records or plain addr strings.

        When loaded from DB, ``self.tools`` is a shallow-hydrated
        ``list[AgentTool]``. Plain strings are accepted for in-memory
        construction and tests.

        Returns:
            List of actor address strings (e.g., ['grants', 'sources'])."""
        # 0. Extract supported target representations from stored tools.
        tool_addrs = []
        if not self.tools:
            return tool_addrs
        for item in self.tools:
            if isinstance(item, AgentTool):
                tool_addrs.append(item.target)
            elif isinstance(item, dict) and item.get('target'):
                tool_addrs.append(item['target'])
            elif isinstance(item, str):
                tool_addrs.append(item)
        # 1. Deduplicate while preserving configured order.
        return list(dict.fromkeys(tool_addrs))

    def call_config(
        self, task: str, thread_id: int = 0, **kwargs,
    ) -> CallConfig:
        """Build a stored-policy call, forwarding trusted caller and scope.

        Zero starts a conversation. A missing scope is inferred from a saved
        registered agent; unsaved agents need an explicit saved parent Ref.
        Prompt and tools remain stored policy, not per-call overrides."""
        # 0. Resolve stored policy and preserve explicit runtime overrides.
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
            scope=kwargs.get('scope'),
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
            **kwargs: Override llm, constraints, user, result_type and scope.
                Caller and scope must come from trusted server context.

        Returns:
            JSON text with answer, usage, messages, message_count and the
            opaque conversation-root TTX thread_id."""
        # 0. Prepare and execute once through the shared native runtime.
        call = self.call_config(task, thread_id=thread_id, **kwargs)
        prepared = await Agent.prepare(self, call)
        result = await Agent.run(prepared, call.task)
        # 1. Retain the existing Python JSON-string response contract.
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
            **kwargs: Override llm, constraints, user, result_type and scope.
                Caller and scope must come from trusted server context.

        Yields:
            Native text, tool_call, tool_result, thinking, done and error
            dictionaries. Preparation errors propagate before yielding."""
        # 0. Prepare the stored-policy call without another execution loop.
        call = self.call_config(task, thread_id=thread_id, **kwargs)
        prepared = await Agent.prepare(self, call)
        # 1. Forward runtime events without changing the chat wire protocol.
        async for chunk in Agent.run_stream(prepared, call.task):
            yield chunk


# Changelog (Python has no block-comment syntax).
# - 2026-11-04: Forward parent scope, remove the tool-address compatibility
#   alias and publish the existing optional thread_id completion field.
#   Document caller/parser limits without changing exposed method signatures.
