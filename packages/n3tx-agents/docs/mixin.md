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

See [Thread and TXRecord](thread.md) for the current storage, codec, authorization,
owner/admin policy and timestamp-based record pagination. Thread stores owner and
optional business scope; TXRecord rows snapshot native TXs. `Thread.history()`
converts records directly to Pydantic AI history via `HISTORY_CODEC`; runtime
`agent_addr` still routes tools but is not persisted on Thread. Scope does not
inherit source permissions. The approved Colgen exception removes its prior
Thread-specific policy override; generic TXRecord CRUD remains denied. Preserve
the actual authenticated caller on HTTP/Matrix execution; do not trust body
identity or claim that a trusted internal call proves an external caller.

## Streaming and errors

See [event vocabulary](../../../docs/AGENTS.md#streaming). Runtime execution
errors become `error` events. Mixin `run_stream()` also catches preparation
errors; policy resolution and class instantiation occur outside that catch.
AgentActor prepares outside the runtime generator and can raise before yielding.
Do not treat every stream failure as a clean `done` event.

Tests: [test_mixin.py](../src/n3tx_agents/tests/test_mixin.py),
[test_thread.py](../src/n3tx_agents/tests/test_thread.py), and
[runtime source](../src/n3tx_agents/agent.py).
