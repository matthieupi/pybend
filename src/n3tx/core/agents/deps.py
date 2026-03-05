"""AgentDeps — dependency injection for Pydantic AI agent tools.

Passed as deps to every Pydantic AI tool function via RunContext[AgentDeps].
Provides access to the Matrix (via adapter) and auth context.

Usage in tool functions:
    async def my_tool(ctx: RunContext[AgentDeps], ...) -> str:
        adapter = ctx.deps.adapter
        user = ctx.deps.user
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AgentDeps:
    """Context passed to Pydantic AI tool functions via RunContext."""

    adapter: Any                # NetworkAdapter for request/response correlation
    user: Optional[dict]        # JWT user dict for auth context
    agent_addr: str             # Agent's actor address (for TX.source)
