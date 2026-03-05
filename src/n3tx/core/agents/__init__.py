"""N3TX Agents — LLM-powered reasoning via the actor system.

Agents are actors that reason. An Agent has a prompt, an LLM, and a list
of other actors it can talk to. The union of all @expose_route methods on
those actors forms the agent's available tool set.

Core components:
    AgentMixin  — injected when __agent__ = True, provides agent_run()
    AgentActor  — concrete model whose instances ARE agents (data, not code)
    AgentDeps   — dependency injection for Pydantic AI RunContext
    ToolSpec    — specification for a discovered tool
"""

from .mixin import AgentMixin
from .actor import AgentActor
from .tool_model import AgentTool
from .deps import AgentDeps
from .tools import ToolSpec, discover_tools, make_tool

# Register schema extension (side-effect import)
from . import schema_ext as _schema_ext  # noqa: F401

__all__ = [
    'AgentMixin', 'AgentActor', 'AgentTool', 'AgentDeps',
    'ToolSpec', 'discover_tools', 'make_tool',
]
