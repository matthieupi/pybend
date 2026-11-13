"""AgentActor — stored configuration for native TTX-only reasoning.

API: tool_addrs resolves stored AgentTool records; run_config supplies trusted
CallConfig to inherited Matrix agentic/agentic_stream and guarded run methods.
Stream DTOs describe native text, thinking, tool and completion events.

Boundary: configuration storage does not enable execution. Applications must
explicitly declare AGENTIC access; stock unrestricted HTTP execution endpoints
are not published. Register AgentActor/AgentTool normally and TTX only for
history. Results remain native dictionaries with canonical ttx_ref."""

from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.models.proto_model import ProtoModel

from .agent import CallConfig
from .mixin import _validate_options
from .tool_model import AgentTool


class TextChunk(ProtoModel):
    """Progressive native text output."""

    text: str = ""


class ToolCallEvent(ProtoModel):
    """A native SDK tool call and its complete arguments."""

    tool: str = ""
    args: dict = Field(default_factory=dict)
    call_id: str = ""


class ToolResultEvent(ProtoModel):
    """The native SDK tool result."""

    tool: str = ""
    result: str = ""
    call_id: str = ""


class ThinkingChunk(ProtoModel):
    """Progressive native reasoning output."""

    text: str = ""


class DoneChunk(ProtoModel):
    """Terminal native completion with canonical history identity."""

    answer: str = ""
    usage: dict = Field(default_factory=dict)
    tool_calls: int = 0
    ttx_ref: str = ""


class AgentActor(ActorModel):
    """Stored native agent policy, not an independently enabled execution API.

    API: tool_addrs selects stored tools; run_config resolves fields into the
    inherited Matrix execution seam. Prompt, LLM and constraints remain data.
    Applications own explicit action policy, caller ingress and fresh guards.
    Normal storage owns agent/tool configuration; TTX owns all history."""

    __tablename__ = "agents"
    __storable__ = True
    __agent__ = True
    __ui__ = {
        "renderer": {"item": "ntx-agent", "detail": "ntx-agent"},
    }

    system_key: str = Field(
        default="", description="Stable framework-provisioned agent identity",
    )
    name: str = Field(min_length=1, max_length=200)
    prompt: str = ""
    tools: list[AgentTool] = Field(default_factory=list)
    llm: str = "ollama:llama3.1"
    constraints: dict = Field(default_factory=dict)

    def tool_addrs(self) -> list:
        """Resolve the configured AgentTool records into ordered addresses."""
        return list(dict.fromkeys(tool.target for tool in self.tools))

    def run_config(self, task: str, **kwargs) -> CallConfig:
        """Resolve stored fields plus trusted Python runtime overrides."""
        # 0. Preserve all backend-selected bounded runtime controls.
        _validate_options(kwargs)
        return CallConfig(
            task=task, prompt=kwargs.get("prompt", self.prompt),
            tools=kwargs.get("tools", self.tool_addrs()),
            user=kwargs.get("user"),
            constraints={**self.constraints, **kwargs.get("constraints", {})},
            result_type=kwargs.get("result_type"),
            llm=kwargs.get("llm", self.llm), has_llm_override=True,
            scope=kwargs.get("scope"),
        )


# Changelog (Python has no block-comment syntax).
# - 2026-11-11: Replace numeric/JSON-text execution adapters with inherited
#   canonical TTX Matrix execution; remove unrestricted HTTP execution routes.
# - 2026-11-11: Carry explicit TTX history through stored-agent adapters while
#   preserving HTTP signatures, legacy IDs and scoped execution lifetime.
