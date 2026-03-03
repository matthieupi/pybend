"""AgentActor — A model whose instances ARE agents.

Configuration lives in fields (DB-storable). Agents are data, not code.

    # In code
    scanner = AgentActor(
        name="Grant Scanner",
        prompt="You find government grants...",
        tools=["grants", "sources", "web_tools"],
        llm="anthropic:claude-sonnet-4-5-20250929",
    )

    # Via API
    # POST /agents {"name": "Grant Scanner", "prompt": "...", "tools": [...]}

    # From DB
    scanner = AgentActor.get(1)

    # Trigger
    result = await scanner.run(task="Scan all sources for new grants")
    # or POST /agents/1/run {"task": "Scan all sources"}
"""

import json
import logging

from pydantic import Field, model_validator

from pybend.core.models.actor_model import ActorModel
from pybend.core.utils.decorators import expose_route

logger = logging.getLogger('pybend.agents')

# Fields stored as JSON TEXT in SQLite (list/dict → str roundtrip)
_JSON_FIELDS = ('tools', 'constraints')


class AgentActor(ActorModel):
    """A model whose instances ARE agents. Configuration is data, not code.

    Fields:
        name: Human-readable agent name.
        prompt: System prompt for the LLM.
        tools: List of actor addresses whose @expose_route methods
               become available tools for the agent.
        llm: Pydantic AI provider:model string (e.g., 'ollama:llama3.1').
        constraints: Budget/safety limits dict.

    Storage: tools and constraints are serialized to JSON TEXT for SQLite.
    """

    __tablename__ = 'agents'
    __storable__ = True
    __agent__ = True  # injects AgentMixin → provides agent_run()

    name: str = Field(min_length=1, max_length=200)
    prompt: str = Field(default='')
    tools: list = Field(default=[])
    llm: str = Field(default='ollama:llama3.1')
    constraints: dict = Field(default={})

    @model_validator(mode='before')
    @classmethod
    def _deserialize_json_fields(cls, data):
        """Deserialize JSON TEXT strings from SQLite back to Python objects."""
        if isinstance(data, dict):
            for field in _JSON_FIELDS:
                val = data.get(field)
                if isinstance(val, str):
                    try:
                        data[field] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
        return data

    def _storage_dict(self, exclude_unset: bool = True) -> dict:
        """Serialize list/dict fields to JSON strings for SQLite storage."""
        d = super()._storage_dict(exclude_unset=exclude_unset)
        for field in _JSON_FIELDS:
            if field in d and not isinstance(d[field], str):
                d[field] = json.dumps(d[field], default=str)
        return d

    @expose_route('/run', methods=['POST'])
    async def run(self, task: str, **kwargs) -> str:
        """Execute the agent's reasoning loop.

        Args:
            task: The user task / query to execute.
            **kwargs: Passed to agent_run() (e.g., llm, constraints overrides).

        Returns:
            JSON string with {answer, usage, messages}.
        """
        result = await self.agent_run(
            prompt=self.prompt,
            tools=self.tools,
            task=task,
            **kwargs,
        )
        return json.dumps(result, default=str)
