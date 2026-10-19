---
name: n3tx-agents
description: N3TX agents, AgentActor, AgentMixin, agentic models, tool discovery, Pydantic AI, actor tools, thread context, and agent streaming. Use when building LLM-powered N3TX features.
argument-hint: "<agent feature>"
---

# N3TX Agents

Agents are actors that reason. Actors are tool collections. `@expose_route` methods are tools.

## Import order

```python
import n3tx_agents  # before defining/importing __agent__ models
```

## Path A: dynamic agents

```python
from n3tx_agents import AgentActor

scanner = AgentActor(
    name='Grant Scanner',
    prompt='Find grants and create records for new opportunities.',
    tools=['grants', 'web_tools'],
    llm='anthropic:claude-sonnet-4-5-20250929',
    constraints={'max_iterations': 30},
)

result = await scanner.run(task='Find renewable energy grants')
```

Via API:

```text
POST /agents
POST /agents/{id}/run
```

## Path B: agentic model methods

```python
class Product(ActorModel):
    __tablename__ = 'products'
    __storable__ = True
    __agent__ = True

    @expose_route('/create_from_text', methods=['POST'])
    async def create_from_text(self, text: str, tools: list = []) -> str:
        result = await self.agentic(
            task=text,
            prompt='Parse text into a Product and save it.',
            tools=['products'] + tools,
        )
        return result['answer']
```

## Tool discovery

An agent's `tools` list contains actor addresses. For each actor:

- storable models produce CRUD tools: list/get/create/update/delete
- `@expose_route` methods become method tools
- tool names follow `{tablename}_{method}`
- `user` parameters are injected and not exposed to LLM args

## Tool actor pattern

```python
class WebTools(ActorModel):
    __tablename__ = 'web_tools'
    __storable__ = False

    @expose_route('/scrape', methods=['POST'])
    async def scrape(self, url: str) -> dict:
        ...
```

Do not create separate ad-hoc LLM tool registries when an actor method can expose the capability.

## Streaming agents

Agent stream methods declare event schemas: `text`, `tool_call`, `tool_result`, `thinking`, `done`. Frontend components such as `ntx-chat` and `ntx-agent-live` handle typed stream events.

## Testing agents

Use Pydantic AI `TestModel` instead of real LLMs:

```python
from pydantic_ai.models.test import TestModel

result = await agent.run(task='Hello', llm=TestModel(call_tools=[]))
```

Use file-based SQLite, not `:memory:`, when migrations are involved.

## Guardrails

- Agents are data, not hardcoded bespoke workflows unless truly static.
- Tools are actor/model methods, not separate tool decorators.
- External APIs used by agents must be wrapped in tool actors/adapters.
- Keep prompts/config in fields for dynamic agents when possible.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
