# AgentActor: stored configuration

[Package](../README.md) · [Runtime and threads](mixin.md) · [Tool limits](tool-discovery.md)

AgentActor is a storable ActorModel with table `agents`. Use it when agent
configuration is application data; use AgentMixin when an existing domain model
needs reasoning. Neither implies background execution.

## Fields and relationships

| Field | Type / default | Meaning |
|---|---|---|
| `system_key` | `str`, `''` | Stable identity used by application-agent provisioning |
| `name` | Required string, 1–200 characters | Display name |
| `prompt` | `str`, `''` | System prompt |
| `tools` | `list[AgentTool]`, `[]` | Ordered local relationship, not a list of URL refs |
| `llm` | `str`, `'ollama:llama3.1'` | Model selection; default still needs a running provider |
| `constraints` | `dict`, `{}` | Runtime currently interprets `max_iterations` |

AgentTool is a storable ActorModel (`agent_tools`) with `target` (actor address)
and `description`. Register AgentTool and each tool-providing model with storage
as applicable. Stored `tools` uses local relationship IDs and hydrates records;
`tool_addrs()` extracts and deduplicates their targets. Although that helper also
handles strings/dictionaries, prefer typed records rather than relying on raw
string construction of a `list[AgentTool]` field.

Ordinary configuration edits use CRUD patches. Omitting `tools` preserves it;
supplying `tools` replaces the entire collection. This is not atomic append.

## Execution API

```text
tool_addrs(self) -> list
call_config(self, task: str, thread_id: int = 0, **kwargs) -> CallConfig
async agentic(self, task: str, thread_id: int = 0, **kwargs) -> str
agentic_stream(self, task: str, thread_id: int = 0, **kwargs) -> async generator
```

| Route | Request | Result |
|---|---|---|
| `POST /agents/{id}/agentic` | `task`, optional `thread_id` in actor routing | See response boundary and direct-parser caveat below |
| `POST /agents/{id}/agentic_stream` | Same | SSE stream |
| Class-name mirrors | `/AgentActor/{id}/agentic[_stream]` | Same routing-mode-specific behavior |

`call_config()` reads stored prompt and tool targets. Trusted Python kwargs can
override LLM/output type/user/scope and merge constraints over stored constraints;
they do **not** override prompt or tools. `thread_id=0` becomes `None`, causing a
new conversation root. Scope is forwarded unchanged to runtime: a saved registered
agent infers its own parent Ref when scope is absent; an unsaved agent requires
an explicit saved local parent scope. No global root is synthesized. Do not assume
arbitrary Python kwargs are accepted by HTTP routes. The former private
`_resolve_tool_addrs` alias is removed; `call_config()` uses `tool_addrs()` directly.

### Response boundary

| Entry point | Shape |
|---|---|
| Mixin Python `agentic()` | Dictionary with `answer`, `usage`, message list, count, thread ID |
| AgentActor Python `agentic()` | `json.dumps(result, default=str)`; decode with `json.loads` |
| Direct generated HTTP | JSON string value from the string-returning method |
| Actor-generated HTTP | ActorModel parses JSON strings before replying, yielding an object |

The current direct custom-route parser treats every non-reserved signature
parameter as required, including defaults and `**kwargs`. Consequently a minimal
`{"task": "Hello"}` call to this signature fails with `Missing field: thread_id`
before execution; supplying that field then encounters the `kwargs` parameter.
Do not invent a dummy-body workaround as a public contract. The string response
above describes successful invocation, not a claim that this minimal direct
HTTP request works. Actor HTTP skips absent arguments and reaches Python defaults.

Thus HTTP clients must not assume routing-mode parity. The `messages` count is
`message_count`; `messages` is a list. JSON `default=str` is not structured
serialization of Pydantic AI message objects; persisted `Message` children use
the SDK's JSON serializer. `thread_id` remains an opaque conversation-root TTX ID;
chat request/result fields and the Python string response are unchanged. The
native direct-parser fix is explicitly outside this persistence change.

### Provider-free stored-agent example

This trusted Python fragment assumes disposable storage with AgentActor,
AgentTool and TTX registered, plus an initialized Matrix. `caller` is trusted
server context with read/update access to the saved agent. `llm='test'` uses the
provider-free model; no network call is needed:

```python
import json

created = AgentActor.create(AgentActor(
    name='Documentation assistant', prompt='Describe the task.',
    llm='test', tools=[], constraints={'max_iterations': 3},
))
agent = AgentActor.get(created.id)
result = json.loads(await agent.agentic(
    task='Hello', user=caller,
))
assert result['message_count'] == len(result['messages'])
assert result['thread_id'] is not None
```

To configure tools, create AgentTool records, patch the agent's `tools` with
those records, and reload. Discovery does not enforce permissions; read the
[execution boundary table](tool-discovery.md#execution-and-security-limits)
before enabling private or mutating tools.

## Caller and persistence cautions

The stock exposed methods have no explicit named `user` parameter. Generated
HTTP injection checks for that parameter, so route authentication alone does
not propagate a caller into `kwargs`. Actor dispatch also does not inject method
arguments from metadata. History treats a missing caller as anonymous `{}`;
existing tool dispatch can still treat missing caller context as internal.
Do not expose these routes to untrusted clients with sensitive tool collections
until the actual caller path is verified and secured.

AgentActor declares no owner-specific model access policy. The resolved parent's
read/update rules now authorize execution/resume, and its read rule authorizes
history. Update is rechecked at checkpoints. There is no separate root-owner
grant: attribution does not make conversations private from other authorized
parent users. Scope binding must match exactly on resume. This parent policy
does not repair missing caller propagation or secure arbitrary HTTP/actor
external execution. Collagen stock AgentActor execution remains separately
denied. Treat configuration and tool selection as privileged operations; do not
use body identities or dummy arguments to conceal the existing route limits.

Current storage uses separate registered Thread and TXRecord models. See the
[Thread/TXRecord guide](thread.md) for record access and timestamp semantics.
The TTX `Conversation`/`Message` description above in older examples is
historical and is not the restored API.

## Streaming and browser integration

The method publishes event schemas for TextChunk, ToolCallEvent,
ToolResultEvent, ThinkingChunk and DoneChunk. DoneChunk declares the runtime's
existing `thread_id` as an optional integer defaulting to `None`; this is schema
alignment, not a chat-wire change. Schema publication does not validate every
yielded dictionary.

```text
NTTStream -> NTTStreamAgent -> ntx-chat
                          -> ntx-agent-live
NTTItem   -> ntx-agent
NTTList   -> ntx-agents
```

Use N3TX's merged static namespace with core, UI and agents assets available.
The shell must import `./components/ntx-agent.js` for the model's `item`/`detail`
renderer; it imports chat/live components. Import `ntx-agents.js` for the optional
hybrid collection. Its `window.NTX_AGENT_CATALOGS[catalog]` entries are workflow
launchers, not stored AgentActor records.

`NTTStreamAgent` renders typed entries, markdown and tool cards. UPPERCASE
handlers (`TEXT`, `TOOL_CALL`, `TOOL_RESULT`, `THINKING`, `DONE`) handle events;
`STREAM_END`/`STREAM_ERROR` handle stream lifecycle. Preserve structural DOM from
`prerender()` when extending rendering. Chat reuses the returned `thread_id`.
Browser cancellation is not a guarantee that provider work or committed tools
are undone.

Sources: [actor.py](../src/n3tx_agents/actor.py),
[tests](../src/n3tx_agents/tests/test_agent_actor.py),
[components](../src/n3tx_agents/static/components/).

## Changelog

- 2026-11-04: Document scope forwarding, semantic TTX conversations and the
  existing completion thread ID; retain response and caller/parser caveats.
