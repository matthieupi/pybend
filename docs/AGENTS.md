# Agents: model policy, stored configuration, and execution

> **Current contract — 2026-11-11:** [the agent package](../packages/n3tx-agents/README.md)
> and [canonical TTX history](../packages/n3tx-agents/docs/ttx-history.md) own the
> execution/history API. Thread/TXRecord exports, numeric history handles and
> runtime fallbacks are retired. November 6 recovery and intermediate opt-in
> descriptions are historical, not instructions for this checkout.

`n3tx-agents` binds N3TX model schemas and actor tools to Pydantic AI. It does
not provide a scheduler, permission sandbox, or durable job queue. Start with
ordinary model CRUD and exposed domain methods; add reasoning only where needed.

## Choose the capability

| Need | Native mechanism | Configuration owner |
|---|---|---|
| Reason about an existing model or record | `__agent__` / AgentMixin | Model declaration and trusted call arguments |
| Store and edit agent configurations | `AgentActor` and `AgentTool` | Normal model storage |
| Offer a domain operation as a tool | `@expose_route` on an ActorModel | Model signature, schema and access rule |
| Persist agent history | Declared canonical TTX roots and full codec-tagged SDK records | Agent history owner/admin policy, independently of business access |
| Offer User direct messaging | Typed `n3tx_threads.Thread` / `Message` views | Owner-local messaging policy; no agent-admin grant |

Import `n3tx_agents` **before defining agent-enabled models**. Its initializer
registers AgentMixin with ProtoModel; importing it later does not retroactively
inject the mixin. A flag alone does not register storage or create HTTP endpoints
for the mixin methods.

```text
model policy / bounded application entrypoint
                         |
                   Agent.invoke
                         |
                   Matrix AGENTIC
                         |
               guarded target.run
                         |
                prepare -> SDK loop
                              |
      authorized TTX <- ATTACH <- finalized SDK messages
             |
             +-> native Matrix tools -> child TTX -> RETURN
```

Construction (`create_app`, `N3TXApp`, raw registration) and HTTP routing
(`direct` or `actor`) are independent choices. Agents use Matrix for tools.
Register only `n3tx_threads.TTX` for history and use canonical `ttx_ref` URLs.
Agent roots explicitly declare protected `meta.agent_history=True` and nullable
`data.scope`. Fresh native owner/admin authorization governs their history;
scope is immutable compatibility metadata, never permission or an inferred
Account binding. History remains readable under that policy after business-row
deletion. Execution separately requires deliberate callee AGENTIC policy and
fresh application guards. User-DM kinds do not qualify as agent roots.

`Agent.chat_history` is trusted decoding, not an authorization entrypoint. Use
the package history guide for exact creation, authorization, invocation and
capture rules. There is no AgentSession or Conversation storage class.

## Provider-free how-to

Use the [native execution fragment](../packages/n3tx-agents/docs/ttx-history.md#native-execution)
with disposable storage, initialized Matrix, registered targets/TTX and an
explicit callee AGENTIC AccessRule. Import the agent package before declaring
enabled models. Select Pydantic AI `TestModel` with no tools for an approved
provider-free check; a trusted synthetic caller is a fixture, not authentication.
The fragment is not a standalone application or a grant to run against live data.

For real providers, select a supported model, provision provider credentials or
a reachable Ollama service, review data disclosure, and impose application-level
budgets. `max_iterations` maps to a model-request limit, not a cost/token/time
budget. A documentation review does not authorize provider execution.

## app_agent startup configuration

`create_app(app_agent=...)` provisions stored configuration; it does not execute
a provider. Import `n3tx_agents` before declaring enabled models and explicitly
register both `AgentActor` and `AgentTool`, plus every tool target. For example,
after declaring the application's `Note` tool model:

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
| Mixin `agentic()` | Checks callee policy, creates/authorizes TTX and invokes Matrix | Preserve explicit AGENTIC admission and bounded server policy |
| Guarded `run()` | Application seam before mandatory TTX preparation and one SDK loop | Keep fresh domain guards and whole-save behavior here |
| AgentActor | Stored configuration; no unrestricted HTTP execution routes | Publish only deliberate bounded domain actions when needed |
| Tool discovery | Reads supplied Matrix child schemas, not caller permissions | Select trusted tool providers; discovery is not a grant |
| Tool execution | `Matrix.request/stream`, `meta.user` from AgentDeps | Do not assume HTTP interceptors or list filters run |
| Explicit `user=None` | Native trusted-internal Python semantics | Never equate this with anonymous public ingress |

Native AGENTIC uses trusted transport caller metadata, never a body identity.
`Agent.invoke` carries server-selected CallConfig in task-local Python state;
client commands cannot select provider, prompt, tools, output type or retries.
Deliberate application HTTP actions still need native named caller injection and
entrypoint-specific checks. Review the [tool trust limits](../packages/n3tx-agents/docs/tool-discovery.md)
and [stored-agent boundary](../packages/n3tx-agents/docs/agent-actor.md) before
using private data or enabling another transport.

## Streaming

Agent generators yield application events `{name, data, meta}`:

| Name | Data |
|---|---|
| `text`, `thinking` | `text` |
| `tool_call` | `tool`, `args`, `call_id` |
| `tool_result` | `tool`, `result`, `call_id` |
| `done` | `answer`, `usage`, `tool_calls`, canonical `ttx_ref` |
| `error` | `message`, `code` |

These are distinct from outer TX correlation and SSE `chunk/done/error` frames.
ActorModel wraps each yielded object in a TX chunk and emits transport completion
when the generator ends. An application `done` event is not the same layer as
transport completion. Cancellation does not roll back completed tool effects.

SDK decoding selects direct incoming codec-tagged records in insertion-ID order,
including archived evidence. It ignores non-codec operations and raises on malformed
codec content; ordinary TTX graph queries are not a substitute for this decoder.
The SDK receives a repaired copy of history, while stored and returned evidence
remains unchanged. Checkpoints append only newly finalized messages and stop
after an uncertain write; they do not replay inference or tool effects.

Declared execution capture reuses authorized roots and participating child TTXs;
it does not reconstruct historical ancestry or add graph ACL traversal. See the
package guide for capture exclusions and current task-local context rules.
Explicit early SDK stream close remains unsupported. Cancellation does not undo
tools, and neither durable replay nor atomic business/history writes is supplied.

## References

| Guide | Responsibility |
|---|---|
| [Package orientation](../packages/n3tx-agents/README.md) | Dependencies and source map |
| [Canonical TTX history](../packages/n3tx-agents/docs/ttx-history.md) | Root policy, native invocation, SDK evidence and capture |
| [Mixin](../packages/n3tx-agents/docs/mixin.md) | Exact policy precedence and guarded runtime seam |
| [AgentActor](../packages/n3tx-agents/docs/agent-actor.md) | Fields, routes, return shapes and UI integration |
| [Tools](../packages/n3tx-agents/docs/tool-discovery.md) | Discovery, generated signatures, execution limits |
| [TTX storage and User messaging](../packages/n3tx-threads/README.md) | Provider-neutral storage, typed DMs and explicit Notes; agent policy/decoding stays in `n3tx_agents.history` |
| [Actors](ACTORS.md) | Messaging and transport boundaries |

## Integration boundary

Framework registration does not convert legacy tables, checkpoints or browser-held
IDs. Consuming applications must refuse unconverted existing storage and perform
their separately approved offline cutover. No old-ID alias or runtime fallback is
available. Source changes and provider-free checks do not authorize migration or
deployment; consult the application's current runbook and dated evidence.

## Changelog

- 2026-11-12: Correct current TTX-only navigation and cross-cutting guidance;
  retire the stale numeric-history example while preserving dated recovery records.
