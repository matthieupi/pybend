"""N3TX Agents — LLM-powered reasoning via the actor system.

Agents are actors that reason. An Agent has a prompt, an LLM, and a list
of other actors it can talk to. The union of all @expose_route methods on
those actors forms the agent's available tool set.

Core components:
    AgentMixin  — injected when __agent__ = True, provides agentic()
    AgentActor  — concrete model whose instances ARE agents (data, not code)
    AgentDeps   — dependency injection for Pydantic AI RunContext
    ToolSpec    — specification for a discovered tool
    Conversation authorization and decoding live in n3tx_agents.history;
    generic TTX storage and notes belong to the n3tx_threads package.

Import before declaring agent models. Importing declarations does not install
schema or open storage. Conversation access follows the saved parent's policy;
TTX attribution and agent provenance do not grant access."""

from .mixin import AgentMixin
# 0. Register opt-in mixins before AgentActor or application model declarations.
from n3tx_core.models.proto_model import register_mixin
register_mixin('__agent__', AgentMixin)
# 1. Export declarations without installing storage or replacing native policy.
from .actor import AgentActor
from .agent import AgentDeps
from .tool_model import AgentTool
from .tools import ToolSpec, discover_tools, make_tool
from .app_agent import provision_app_agent

# Register schema extension (side-effect import)
from . import schema_ext as _schema_ext  # noqa: F401

__all__ = [
    'AgentMixin', 'AgentActor', 'AgentTool', 'AgentDeps',
    'ToolSpec', 'discover_tools', 'make_tool',
    'provision_app_agent',
]


# Changelog (Python has no block-comment syntax):
# - 2026-11-04: Document parent-authorized conversations without capture hooks.
# - 2026-11-02: Move thread/notes exports and registration to n3tx_threads.
# - 2026-10-31: Export Thread and TXRecord without initializing storage;
#   retain AgentMixin registration before AgentActor declaration.
#   Register/export opt-in NotesMixin and its explicit caller/access helpers.
#   Compose exact notes access with the existing Thread read rule only.
#   Remove notes-specific ACL composition in favor of native scope policy.
#   Export the shared ThreadScopeAccess rule without changing model policy.
#   Remove scope-policy exports and retain native owner/admin Thread policy.
#   Remove the retired notes caller-binding export.
