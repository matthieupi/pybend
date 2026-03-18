"""AgentDeps — dependency injection for Pydantic AI agent tools.

Passed as deps to every Pydantic AI tool function via RunContext[AgentDeps].
Provides auth context for tool calls.

Usage in tool functions:
    async def my_tool(ctx: RunContext[AgentDeps], ...) -> str:
        user = ctx.deps.user
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentDeps:
    """Context passed to Pydantic AI tool functions via RunContext."""

    user: Optional[dict]        # JWT user dict for auth context
    agent_addr: str             # Agent's actor address (for TX.source)
