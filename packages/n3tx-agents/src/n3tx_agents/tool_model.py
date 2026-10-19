"""AgentTool — a tool reference for AgentActor.

Each AgentTool record stores an actor address (e.g. 'grants', 'web_tools')
that the agent can call. AgentActor keeps an ordered list[AgentTool] collection.

    # Via API
    # POST /AgentActor/1 with tools containing AgentTool refs or objects

    # From code
    tool = AgentTool(target="grants", description="Grant CRUD operations")
"""

from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel


class AgentTool(ActorModel):
    """A tool reference that an agent can use.

    Fields:
        target: Actor address whose @expose_route methods become tools.
                Named 'target' to avoid collision with Actor.addr (private attr).
        description: Human-readable description of what this tool provides.
    """

    __tablename__ = 'agent_tools'
    __storable__ = True

    target: str = Field(min_length=1, description="Actor address (e.g. 'grants', 'web_tools')")
    description: str = Field(default='', description="What this tool provides")
