# Agents: model policy, stored configuration, and execution

> Current Thread/TXRecord reference: [thread guide](../packages/n3tx-agents/docs/thread.md).
> TTX sections below are retained historical implementation, not current API
> authority for the restored October 31 source.

`n3tx-agents` binds N3TX model schemas and actor tools to Pydantic AI. It does
not provide a scheduler, permission sandbox, or durable job queue. Start with
ordinary model CRUD and exposed domain methods; add reasoning only where needed.

## Choose the capability

| Need | Native mechanism | Configuration owner |
|---|---|---|
| Reason about an existing model or record | `__agent__` / AgentMixin | Model declaration and trusted call arguments |
| Store and edit agent configurations | `AgentActor` and `AgentTool` | Normal model storage |
| Offer a domain operation as a tool | `@expose_route` on an ActorModel | Model signature, schema and access rule |
| Persist conversation history | Semantic `Thread(TTX)` roots and TTX messages | Agent-owned parent authorization followed by native storage |

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
            authorize owning entity
                         |
              open/read Thread(TTX)
                         |
              LLM + Matrix + tools
                         |
              Pydantic AI execution
                         |
       tool -> TX -> Matrix -> ActorModel
                         |
                result + TTX appends
```

Construction (`create_app`, `N3TXApp`, raw registration) and HTTP routing
(`direct` or `actor`) are independent choices. Agents use Matrix for tools.
Conversation storage uses native TTX operations after explicit parent checks,
not Matrix CRUD against a separate `threads` actor.

Each conversation is a TTX named `Conversation`; finalized SDK messages are
immediate child TTXs named `Message`. `Thread` is an empty semantic subclass for
Python readability. Register only TTX, and retain canonical `/TTX/<id>` links.
The public `thread_id` identifies the root TTX; old container IDs are not
interchangeable with these IDs.

An explicit `scope` must identify a real saved local owner. Without one, a saved
registered ActorModel instance supplies its own canonical reference. Class-level,
non-storable and unsaved actors need an explicit scope; there is no fabricated
global parent. Executing/resuming requires parent read and update access, while
history-only reads require read. Conversation attribution is not an independent
access grant or a private-owner restriction.

## Provider-free how-to

Prerequisites: Python 3.10+, installed `n3tx-agents` and its
core/actors/threads/Pydantic AI dependencies. Save this as a Python script and run
it in a fresh process.
It uses temporary file-backed SQLite, no server, credentials, or paid provider.
The supplied identity is a **trusted test fixture**, not an authentication recipe.

```python
import asyncio
import tempfile
from pathlib import Path

import n3tx_agents  # register the mixin before the class declaration
from n3tx_agents import AgentActor, AgentTool
from n3tx_actors import Actor, Matrix
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
        )  # also registers the canonical TTX model
        root = Matrix()
        Actor.root(root)
        root.register(Note)
        note = Note.create(Note(text='Synthetic example'))
        result = await note.agentic(
            task='Describe this record', tools=[],
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
| Missing/`None` caller | Agent history checks treat it as anonymous | Native tool dispatch has separate trusted-internal semantics; do not infer a universal ingress guard |

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

History reads select all immediate `Message` rows in ascending TX timestamp
order. They do not page through exclusive timestamp cursors, which can omit ties.
Equal timestamps have no defined secondary order; no ID tie-breaker is added.
The SDK receives a repaired copy of history, while stored and returned evidence
remains unchanged. Checkpoints append only newly finalized messages and stop
after an uncertain write; they do not replay inference or tool effects.

Automatic execution-manifest capture and parent `.THREAD(...)` links are
removed. Handoffs must explicitly pass a conversation identity and the same
expected owning scope. Parent-TTX permission traversal is not supplied.

## References

| Guide | Responsibility |
|---|---|
| [Package orientation](../packages/n3tx-agents/README.md) | Dependencies and source map |
| [Mixin](../packages/n3tx-agents/docs/mixin.md) | Exact policy precedence, runtime and thread behavior |
| [AgentActor](../packages/n3tx-agents/docs/agent-actor.md) | Fields, routes, return shapes and UI integration |
| [Tools](../packages/n3tx-agents/docs/tool-discovery.md) | Discovery, generated signatures, execution limits |
| [Threads](../packages/n3tx-threads/README.md) | Provider-neutral TTX storage and notes; agent-specific authorization/decoding stays in `n3tx_agents.history` |
| [Actors](ACTORS.md) | Messaging and transport boundaries |

## Integration boundary

This source migration does not transform existing Thread containers, snapshot
targets or browser-held IDs. Collagen's application-specific history/activity
adapters and their data cutover remain separate work. Source changes and
provider-free tests do not authorize a database migration or deployment.
