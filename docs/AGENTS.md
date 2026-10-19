# Agents: model policy, stored configuration, and execution

`n3tx-agents` binds N3TX model schemas and actor tools to Pydantic AI. It does
not provide a scheduler, permission sandbox, or durable job queue. Start with
ordinary model CRUD and exposed domain methods; add reasoning only where needed.

## Choose the capability

| Need | Native mechanism | Configuration owner |
|---|---|---|
| Reason about an existing model or record | `__agent__` / AgentMixin | Model declaration and trusted call arguments |
| Store and edit agent configurations | `AgentActor` and `AgentTool` | Normal model storage |
| Offer a domain operation as a tool | `@expose_route` on an ActorModel | Model signature, schema and access rule |
| Persist conversation history | `Thread` | Runtime through Matrix CRUD |

Import `n3tx_agents` **before defining agent-enabled models**. Its initializer
registers AgentMixin with ProtoModel; importing it later does not retroactively
inject the mixin. A flag alone does not register storage or create HTTP endpoints
for the mixin methods.

```text
Model __agent__ policy             Stored AgentActor fields
        | agentic()                       | agentic()
        v                                 v
    run_config -> run()                 call_config
        +----------------+----------------+
                         v
                 Agent.prepare()
          LLM + Matrix + Thread + tools
                         |
              Pydantic AI execution
                         |
       tool -> TX -> Matrix -> ActorModel
                         |
                result + thread update
```

Construction (`create_app`, `N3TXApp`, raw registration) and HTTP routing
(`direct` or `actor`) are independent choices. Agents use Matrix for tools and
threads even when the application uses direct HTTP routes.

## Provider-free how-to

Prerequisites: Python 3.10+, installed `n3tx-agents` and its core/actors/Pydantic
AI dependencies. Save this as a Python script and run it in a fresh process.
It uses temporary file-backed SQLite, no server, credentials, or paid provider.
The supplied identity is a **trusted test fixture**, not an authentication recipe.

```python
import asyncio
import tempfile
from pathlib import Path

import n3tx_agents  # register the mixin before the class declaration
from n3tx_agents import AgentActor, AgentTool
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.app import create_app
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from pydantic_ai.models.test import TestModel

class Note(ActorModel):
    __tablename__ = 'notes'
    __storable__ = True
    __agent__ = True
    text: str = ''

async def main():
    with tempfile.TemporaryDirectory() as directory:
        create_app(
            models=[Note, AgentTool, AgentActor],
            storage=SQLiteStorage(str(Path(directory) / 'demo.db')),
            static_dir=None,
            jwt_secret='documentation-test-secret-not-for-production',
        )  # also registers Thread infrastructure
        result = await Note.agentic(
            task='Describe the model', tools=[],
            llm=TestModel(call_tools=[]),
            user={'user_id': 1, 'role': 'user'},
            constraints={'max_iterations': 3},
        )
        assert result['message_count'] == len(result['messages'])
        assert result['thread_id'] is not None
        print('agent result and stored thread verified')

asyncio.run(main())
```

For real providers, select a supported model, provision provider credentials or
a reachable Ollama service, review data disclosure, and impose application-level
budgets. `max_iterations` maps to a model-request limit, not a cost/token/time
budget. Do not replace `TestModel` during a documentation smoke test.

## app_agent startup configuration

`create_app(app_agent=...)` provisions stored configuration; it does not execute
a provider. Import `n3tx_agents` before declaring enabled models and explicitly
register both `AgentActor` and `AgentTool`, plus every tool target. For example,
continuing the provider-free example's `Note` declaration:

```python
# Bootstrap fragment: Note is already declared; use disposable storage.
create_app(
    models=[Note, AgentTool, AgentActor],
    storage='sqlite:///assistant-demo.db',
    static_dir=None,
    jwt_secret='documentation-test-secret-not-for-production',
    app_agent={
        'key': 'app-assistant',
        'name': 'App assistant',
        'prompt': 'Help with notes.',
        'llm': '',
        'constraints': {'max_iterations': 3},
        'tools': [{'target': 'notes', 'description': 'Note operations'}],
    },
)
```

| Configuration | Contract |
|---|---|
| `key`, `name` | Required, nonempty; key becomes stored `system_key` |
| `prompt`, `llm` | Optional strings, default `''`; provisioning does not validate provider availability |
| `constraints` | Optional mapping, default `{}`; execution interprets it later |
| `tools` | Optional list of dictionaries, default `[]`; each needs a nonempty `target` matching a **registered table name**, not a class name or arbitrary URL; `description` defaults to `''` |

Startup finds an agent by system key, then by name, and creates or updates it.
It **overwrites** configured prompt/LLM/constraints/name/key fields (omitted
optional fields reset to defaults) and replaces the ordered tool links. Tool
rows are reused by target and their descriptions updated, potentially affecting
other agents sharing those rows. Removed links do not delete old tool rows.
Do not treat UI edits to this assistant as persistent across bootstrap runs.

Provisioning is neither execution nor a caller-safety boundary. Tool selection
does not grant permission or prove caller propagation; apply the execution
caveats below before exposing it. Source:
[app_agent.py](../packages/n3tx-agents/src/n3tx_agents/app_agent.py),
[provider-free provisioning tests](../packages/n3tx-agents/src/n3tx_agents/tests/test_app_agent.py).

## Execution and caller boundaries

| Boundary | Current behavior | Application responsibility |
|---|---|---|
| Mixin `agentic()` | Resolves prompt/tools/constraints, delegates to `run()` | Use as the policy extension point; it is not itself authorization |
| Mixin `run()` | Explicit task/prompt/tools; runtime still resolves the LLM | Keep internal; do not expose unrestricted configuration |
| AgentActor `/agentic` | Uses stored fields; Python returns JSON text | Verify actual HTTP response shape and caller propagation |
| Tool discovery | Reads supplied Matrix child schemas, not caller permissions | Select trusted tool providers; discovery is not a grant |
| Tool execution | `Matrix.request/stream`, `meta.user` from AgentDeps | Do not assume HTTP interceptors or list filters run |
| Missing/`None` caller | Actor handler treats it as internal | Never use this for untrusted user requests |

The stock AgentActor methods accept `user` only through `**kwargs`; generated
HTTP caller injection looks for a named `user` parameter. Authentication at the
route does **not** establish that the user reaches agent tools or threads.
Raw actor dispatch also does not inject a named method argument from `meta.user`.
Review and test the enabled entrypoint before using agents with private data.
See the precise [tool trust limits](../packages/n3tx-agents/docs/tool-discovery.md).
The direct HTTP parser also treats defaulted/variadic parameters as required;
the stock minimal task body is not a working direct-route contract. See
[AgentActor route caveats](../packages/n3tx-agents/docs/agent-actor.md#response-boundary).

## Streaming

Agent generators yield application events `{name, data, meta}`:

| Name | Data |
|---|---|
| `text`, `thinking` | `text` |
| `tool_call` | `tool`, `args`, `call_id` |
| `tool_result` | `tool`, `result`, `call_id` |
| `done` | `answer`, `usage`, `tool_calls`, runtime `thread_id` |
| `error` | `message`, `code` |

These are distinct from outer TX correlation and SSE `chunk/done/error` frames.
ActorModel wraps each yielded object in a TX chunk and emits transport completion
when the generator ends. An application `done` event is not the same layer as
transport completion. Cancellation does not roll back completed tool effects.

## References

| Guide | Responsibility |
|---|---|
| [Package orientation](../packages/n3tx-agents/README.md) | Dependencies and source map |
| [Mixin](../packages/n3tx-agents/docs/mixin.md) | Exact policy precedence, runtime and thread behavior |
| [AgentActor](../packages/n3tx-agents/docs/agent-actor.md) | Fields, routes, return shapes and UI integration |
| [Tools](../packages/n3tx-agents/docs/tool-discovery.md) | Discovery, generated signatures, execution limits |
| [Actors](ACTORS.md) | Messaging and transport boundaries |
