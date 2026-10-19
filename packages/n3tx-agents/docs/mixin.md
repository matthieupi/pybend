# AgentMixin reference

[Overview and runnable example](../../../docs/AGENTS.md) · [AgentActor](agent-actor.md)

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
          thread_id=None, result_type=None, **kwargs) -> dict
agentic_stream(target, task: str, **kwargs) -> async generator
run_stream(target, task: str, prompt: str, tools: list,
           user: dict = None, constraints: dict = None,
           thread_id=None, result_type=None, **kwargs) -> async generator
```

`fullmethod` binds `target` to a class or instance. Class-level
`agentic_stream()` constructs `target()` before calling the engine: it can fail
for models with required fields. Use a populated instance in that case.

## Policy resolution

| Input | Actual precedence / behavior |
|---|---|
| Prompt | Truthy call `prompt`, otherwise `ctx()`; class config prompt prefixes schema context |
| Tools | Explicit call `tools` including `[]`, otherwise `tools()` |
| Constraints | Merge global `AGENT_DEFAULTS`, class `__agent__`, then call dictionary |
| LLM | Explicit override if supplied; otherwise class config, target `llm`, global default |
| Output type | Truthy call `result_type`, otherwise class config |
| User, thread ID | Call arguments |

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

`run()` bypasses policy assembly, not runtime preparation. Preparation resolves
the LLM, gets `Actor.root()`, loads/creates a thread, discovers tools, builds a
Pydantic AI agent and AgentDeps, and optionally creates
`UsageLimits(request_limit=max_iterations)`. A missing LLM raises `ValueError`;
a missing root raises `RuntimeError`. `llm='test'` resolves to
`TestModel(call_tools=[])`; `ollama:<model>` uses `config.OLLAMA_BASE_URL` with
`/v1` appended when necessary.

Sync result:

```text
{answer, usage: {input_tokens, output_tokens, requests},
 messages: list[ModelMessage], message_count: len(messages), thread_id}
```

`answer` can be a structured output object. Messages are Pydantic AI objects,
not already a portable JSON history. AgentActor separately JSON-serializes the
result with `default=str`.

## Thread lifecycle

Every prepared run loads the supplied thread or creates one when `thread_id`
is absent. There is no `create_thread` switch in CallConfig. `N3TXApp.build()`
adds Thread infrastructure when an agent-enabled model is registered; raw
registration must register Thread with storage and the active Matrix itself.

- Thread fields: `agent_addr`, `messages`, `user_owner`. Messages are persisted
  as TX-shaped dictionaries containing serialized Pydantic AI messages in `data`.
- `Thread.to_history()` and `from_history()` convert stored and runtime forms.
- Declared policy is authenticated creation, owner-or-admin read/update/delete.
  Runtime `user=None` still takes the actor internal bypass.
- Reuse checks exact agent address **or its table scope**; legacy empty agent
  addresses are accepted. This is not strict per-instance thread isolation.
- User-model normalization to `{user_id, email, role}` occurs for thread CRUD;
  tool AgentDeps retains the original caller value.
- History is replaced after execution. Concurrent turns on the same thread can
  overwrite one another; serialize turns in the application. Update errors are
  logged, not raised as a failed agent result.

## Streaming and errors

See [event vocabulary](../../../docs/AGENTS.md#streaming). Runtime execution
errors become `error` events. Mixin `run_stream()` also catches preparation
errors; policy resolution and class instantiation occur outside that catch.
AgentActor prepares outside the runtime generator and can raise before yielding.
Do not treat every stream failure as a clean `done` event.

Tests: [test_mixin.py](../src/n3tx_agents/tests/test_mixin.py),
[test_thread.py](../src/n3tx_agents/tests/test_thread.py), and
[runtime source](../src/n3tx_agents/agent.py).
