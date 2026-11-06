# AgentMixin reference

[Overview](../../../docs/AGENTS.md) · [AgentActor](agent-actor.md)

Import `n3tx_agents` before declaring `__agent__ = True` or a nonempty config
dictionary. ProtoModel injects the registered mixin at class construction time.
The mixin does not decorate its methods as HTTP endpoints; expose a deliberate
domain method if an existing model needs a reasoning action.

## Public Python surface

Signatures below are reference declarations, not a runnable class:

```text
ctx(target) -> str
tools(target) -> list
run_config(target, task: str, **kwargs) -> CallConfig
async agentic(target, task: str, **kwargs) -> dict
async run(target, task: str, prompt: str, tools: list,
          user: dict = None, constraints: dict = None,
          thread_id=None, result_type=None,
          scope: Ref | None = None, **kwargs) -> dict
agentic_stream(target, task: str, **kwargs) -> async generator
run_stream(target, task: str, prompt: str, tools: list,
           user: dict = None, constraints: dict = None,
           thread_id=None, result_type=None,
           scope: Ref | None = None, **kwargs) -> async generator
```

`fullmethod` binds `target` to a class or instance. `agentic_stream()` forwards
directly to `target.run_stream()` without constructing `target()`, so required
model fields do not prevent class-level streaming. Runtime still requires a
saved local parent scope for class calls.

## Policy resolution

| Input | Actual precedence / behavior |
|---|---|
| Prompt | Truthy call `prompt`, otherwise `ctx()`; class config prompt prefixes schema context |
| Tools | Explicit call `tools` including `[]`, otherwise `tools()` |
| Constraints | Merge global `AGENT_DEFAULTS`, class `__agent__`, then call dictionary |
| LLM | Explicit override if supplied; otherwise class config, target `llm`, global default |
| Output type | Truthy call `result_type`, otherwise class config |
| User, thread ID, scope | Call arguments; runtime infers missing scope only from a saved registered ActorModel instance |

There is no universal dictionary cascade for every key. `tools()` includes the
own table unless `self_tools=False`, local `list[T]` neighbors unless
`neighbors=False`, then class-config extra addresses; it deduplicates in order.
Discovery subsequently applies its own exact caller-address exclusion.
`neighbor_depth` is published as safe schema metadata but is not a traversal
control in this implementation.

`ctx()` uses the `llm` schema pipeline. Instance context appends the full
`model_dump()` serialized with `default=str`; it is **not** truncated to 200
characters and is not a permission-filtered/redacted view. Review sensitive
fields before sending this context to a provider.

## Runtime ownership

```text
agentic -> run_config -> run -> CallConfig -> Agent.prepare -> Agent.run
streaming policy ------------------------------+----------> Agent.run_stream
```

`run()` bypasses policy assembly, not runtime preparation. Preparation gets
`Actor.root()`, authorizes and opens a conversation, reads history, then resolves
the LLM, discovers tools, builds a Pydantic AI agent and AgentDeps, and creates
`UsageLimits(request_limit=max_iterations)`. A missing LLM raises `ValueError`;
a missing root raises `RuntimeError`. `llm='test'` resolves to
`TestModel(call_tools=[])`; `ollama:<model>` uses `config.OLLAMA_BASE_URL` with
`/v1` appended when necessary.

`CallConfig` retains its input `thread_id` and optional `scope: Ref | None`.
`PreparedCall` holds a semantic `thread: Thread` and a message-history list,
not a separate stored-container ID. Public results continue to expose
`thread_id = prepared.thread.id`.

Sync result:

```text
{answer, usage: {input_tokens, output_tokens, requests},
 messages: list[ModelMessage], message_count: len(messages), thread_id}
```

`answer` can be a structured output object. Messages are Pydantic AI objects,
not already a portable JSON history. `messages` is evidence-aligned: the raw
loaded Thread history followed by this invocation's new SDK messages. It is not
the SDK-normalized full context. The SDK receives a separately repaired deep
copy; saved records and typed audit inputs are not rewritten or normalized.
AgentActor separately JSON-serializes the result with `default=str`.

## Thread lifecycle

See [TTX storage](../../n3tx-threads/docs/thread.md). `Thread` is an empty semantic
TTX subclass with automatic actor registration disabled; both share TTX storage.
Register **TTX only**. Canonical public references always use `/TTX/<id>`;
`Thread.get(id)` alone does not prove the row is a conversation.

```text
saved local scope <- Conversation TTX (semantic Thread)
                        ^
                        +-- Message TTX: SDK JSON
                        +-- Message TTX: SDK JSON
```

The root has `name='Conversation'`, a null payload, source equal to the executing
agent address and target equal to the resolved scope. Each finalized SDK message
is an immediate child named `Message`; its target is the canonical root TTX Ref.
The public integer `thread_id` is this root's opaque ID, not a message ID or a
separate Thread container. TTX physically wraps payloads in `data.payload`;
`value` exposes the payload, including the root's `None`.

Agent-owned `open_thread` validates new/resumed roots and exact scope binding.
Preparation requires parent `read` and `update`; `read_history(thread, *, user)`
requires parent `read`. Checkpoints reauthorize parent update access. Missing
callers become anonymous `{}`, never a history bypass. Root `source` and
`user_owner` are attribution, not a separate private-thread permission grant.
Another caller with the required parent access can access the same conversation.
TTX declares deny-all access. Configured HTTP boundaries enforce that policy,
including an empty filtered LIST. Raw Matrix LIST is a trusted internal path
that does not derive its own authorization filter; do not expose it as a TTX
collection tool. Parent-history checks do not repair transport caller injection
or grant tool permissions.

Import `Thread` and `TTX` from `n3tx_threads`, and `open_thread` / `read_history`
from `n3tx_agents.history`. History selects immediate `Message` children and
decodes their payloads with Pydantic AI's `ModelMessagesTypeAdapter`. There is no
`HISTORY_CODEC`, codec argument, `Thread.payloads()` or capture API. The decoder
does not repair messages, rewrite records or call a provider. Malformed payloads
and access denials propagate to the caller.

The runtime checkpoints finalized messages through SDK node hooks and flushes
final results. A cursor counts only new messages in this invocation; after a
short/failed append it stops further checkpoints without replaying tools or
inference. SDK context receives `repair_messages(deepcopy(history))`, while
returned evidence remains the raw loaded prefix plus new messages. Prompt-less
continuation and rewriting already-checkpointed messages remain unsupported.
Persistence is not an atomic multi-message append, provider replay, tool rollback
or durable delivery guarantee. Parent permission checks and writes are not a
single transaction. Native timestamp-only child paging has no ID tie-breaker or
concurrent snapshot guarantee; do not infer complete replay from that helper.

## Scope examples

These are trusted Python fragments after registering a storable agent-enabled
`Note` model and TTX with disposable storage. `caller` is server-authenticated
context with read/update access to `note`, not client-supplied identity:

```python
from n3tx_core.models.ref import Ref, public_id_url

note = Note.create(Note(text='Documentation context'))
result = await note.agentic(task='Summarize', tools=[], llm='test', user=caller)

# Class context uses an actual saved parent, not an invented URL/global root.
scope = Ref(public_id_url(note.id, target_cls=Note))
async for event in Note.agentic_stream(
    task='Describe this model', tools=[], llm='test', user=caller, scope=scope,
):
    print(event['name'])
```

The saved instance infers its own canonical Ref. Class, non-storable and unsaved
targets must supply a real saved local scope. Omitting `scope` never creates a
global conversation. Resume must use the same resolved scope, including when
the caller is an administrator. Legacy container histories require a separately
reviewed migration; this source contract does not migrate storage or deploy it.

## Streaming and errors

**Unsupported:** explicit early `aclose()` of a partially consumed runtime
stream. With the installed SDK it can fail async-generator/AnyIO cleanup and
leave protocol history incomplete. Do not interpret closing as rollback or
retry execution to compensate. Normal stream completion and separately tested
cancellation paths do not establish early-close support. This limitation is also
documented on `Agent.run_stream()` in the runtime source.

See [event vocabulary](../../../docs/AGENTS.md#streaming). Runtime execution
errors become `error` events. Mixin `run_stream()` also catches preparation
errors; policy resolution occurs outside that catch.
AgentActor prepares outside the runtime generator and can raise before yielding.
Do not treat every stream failure as a clean `done` event.

Tests: [test_mixin.py](../src/n3tx_agents/tests/test_mixin.py),
[test_thread.py](../src/n3tx_agents/tests/test_thread.py), and
[runtime source](../src/n3tx_agents/agent.py).

## Changelog

- 2026-11-04: Document direct class streaming, saved-parent scope resolution,
  semantic Thread/TTX identity and parent-authorized SDK history without codecs.
