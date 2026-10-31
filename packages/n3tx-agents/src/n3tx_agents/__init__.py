"""N3TX Agents — LLM-powered reasoning via the actor system.

Agents are actors that reason. An Agent has a prompt, an LLM, and a list
of other actors it can talk to. The union of all @expose_route methods on
those actors forms the agent's available tool set.

Core components:
    AgentMixin  — injected when __agent__ = True, provides agentic()
    AgentActor  — concrete model whose instances ARE agents (data, not code)
    AgentDeps   — dependency injection for Pydantic AI RunContext
    ToolSpec    — specification for a discovered tool
    Thread     — native owner/admin history with optional scope metadata
    TXRecord   — stored TX snapshots and insertion provenance
    NotesMixin — opt-in owner-authorized notes via __notes__ declarations

Import before declaring agent/notes models. Importing declarations does not
install schema, open storage or replace Thread's native access policy."""

from .mixin import AgentMixin
from .notes_mixin import NotesMixin
from .thread import Thread
# 0. Register opt-in mixins before AgentActor or application model declarations.
from n3tx_core.models.proto_model import register_mixin
register_mixin('__agent__', AgentMixin)
register_mixin('__notes__', NotesMixin)
# 1. Export declarations without installing storage or replacing native policy.
from .actor import AgentActor
from .agent import AgentDeps
from .tool_model import AgentTool
from .tools import ToolSpec, discover_tools, make_tool
from .tx_record import TXRecord
from .app_agent import provision_app_agent

# Register schema extension (side-effect import)
from . import schema_ext as _schema_ext  # noqa: F401

__all__ = [
    'AgentMixin', 'AgentActor', 'AgentTool', 'AgentDeps',
    'ToolSpec', 'discover_tools', 'make_tool',
    'Thread', 'TXRecord',
    'NotesMixin',
    'provision_app_agent',
]


# Changelog (Python has no block-comment syntax):
# - 2026-10-31: Export Thread and TXRecord without initializing storage;
#   retain AgentMixin registration before AgentActor declaration.
#   Register/export opt-in NotesMixin and its explicit caller/access helpers.
#   Compose exact notes access with the existing Thread read rule only.
#   Remove notes-specific ACL composition in favor of native scope policy.
#   Export the shared ThreadScopeAccess rule without changing model policy.
#   Remove scope-policy exports and retain native owner/admin Thread policy.
#   Remove the retired notes caller-binding export.
