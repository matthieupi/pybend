# Phase 1 Plan — `n3tx_agents` Runtime Refactor

## ✅ Recommendation

Phase 1 should be a **behavior-preserving internal refactor** focused on findings **2, 3, 4, 6, and 8** from the audit.

Default path:

1. freeze current behavior with focused tests
2. extract shared call/config resolution from `agentic()` / `agentic_stream()`
3. introduce `Agent` as the explicit shared runtime seam
4. move sync and stream execution behind `Agent`
5. turn `AgentActor` into a thin DB-config adapter over that same runtime
6. normalize return shape internally, while preserving the public JSON-string contract of `AgentActor.agentic()`

This attacks the highest-value duplication without taking on broader API or storage changes too early.

---

## 📍 Scope

### In scope

| Audit finding | Focus for Phase 1 |
|---|---|
| #2 | make the policy/engine split more real internally |
| #3 | remove duplicated setup between `run()` and `run_stream()` |
| #4 | remove duplicated config cascade between `agentic()` and `agentic_stream()` |
| #6 | remove duplicated `AgentActor` adapter logic |
| #8 | normalize return shape internally without breaking external callers |

### Out of scope

Leave these for a later phase:

- splitting `tools.py`
- changing agent endpoint discovery policy
- redesigning thread ownership semantics
- changing thread storage format
- changing stream chunk payload shapes
- changing `AgentActor.agentic()` away from JSON string output
- package/bootstrap cleanup (`__init__.py`, import-time registration)
- broader package/module reorganization

---

## 🎯 Target outcome

### Keep stable

- `AgentMixin` public method names
- `AgentActor` routes and stream payload shapes
- `AgentActor.agentic()` returning a JSON string
- current thread semantics
- current config precedence behavior
- current stream ordering behavior covered by tests

### Improve internally

- one call-config resolver
- one explicit `Agent` boundary
- one runtime-preparation path owned by `Agent`
- one sync/stream execution owner
- one `AgentActor` runtime-config adapter
- one internal Python result shape

---

## 🗺️ Current → target flow

```text
Today
-----
agentic() --------\
agentic_stream() --+--> duplicated config logic
run() ------------/
run_stream() -----\--> duplicated runtime setup
AgentActor.* -------> duplicated DB adapter + descriptor bypass

Phase 1 Target
--------------
agentic() --------\
agentic_stream() --+--> resolve_agent_call(...)
                    |
                    v
               Agent.prepare(...)
                    |
             +------+------+
             |             |
             v             v
             Agent.run()  Agent.run_stream()

AgentActor -> _agent_runtime_config(...) -> same `Agent` path
```

---

## 🪜 Implementation slices

## Slice 0 — Freeze behavior with test fences

Before moving code, pin the behaviors touched by this phase.

### Add or expand tests for

- `agentic()` vs `agentic_stream()` config cascade parity
- `run()` vs `run_stream()` thread / `create_thread` parity
- `AgentActor.agentic()` vs `.agentic_stream()` config merge parity
- `AgentActor.agentic()` JSON-string wrapper behavior
- class-level `agentic_stream()` behavior
- stream ordering / first-token regression

### Why first

This phase is structural. The main risk is behavior drift, not missing functionality.

---

## Slice 1 — Extract shared call resolution

Create one internal value object for public-call normalization.

Representative shape:

```python
@dataclass
class CallConfig:
    task: str
    prompt: str
    tools: list[str]
    user: dict | None
    constraints: dict
    thread_id: int | None
    create_thread: bool
    result_type: type | None

    def runtime_args(self) -> dict:
        ...


def resolve_agent_call(target, task: str, kwargs: dict) -> CallConfig:
    ...
```

### Move into this helper

- prompt resolution
- tools resolution
- constraint cascade
- `user`
- `thread_id`
- `create_thread`
- `result_type`

### Keep out of this helper

- concrete `llm` resolution
- conversion from `llm` string/override into a runnable model instance

### Use it from

- `AgentMixin.agentic()`
- `AgentMixin.agentic_stream()`

### Result

One source of truth for public-call behavior.

---

## Slice 2 — Extract shared runtime preparation

Introduce `Agent` as the explicit shared owner of runtime assembly and execution.

Representative shape:

```python
@dataclass
class PreparedCall:
    llm: object
    root: Actor
    agent_addr: str
    thread_id: int | None
    message_history: list | None
    ai_agent: PydanticAgent
    deps: AgentDeps
    usage_limits: UsageLimits | None


class Agent:
    @classmethod
    async def prepare(cls, target, call: CallConfig, **kwargs) -> PreparedCall:
        ...

    @classmethod
    async def run(cls, prepared: PreparedCall, task: str) -> dict:
        ...

    @classmethod
    async def run_stream(cls, prepared: PreparedCall, task: str):
        yield ...
```

### `Agent.prepare(...)` should own

- llm override handling
- llm resolution
- Matrix root lookup
- thread preload / create
- tool discovery
- tool wrapping
- `PydanticAgent` construction
- deps creation
- usage limits

### Result

`run()` and `run_stream()` stop rebuilding the same setup independently, and the package gains one explicit runtime owner.

---

## Slice 3 — Move terminal execution behind `Agent`

After shared preparation exists, keep two small terminal execution methods on `Agent`.

Representative shape:

```python
class Agent:
    @classmethod
    async def run(cls, prepared: PreparedCall, task: str) -> dict:
        ...

    @classmethod
    async def run_stream(cls, prepared: PreparedCall, task: str):
        yield ...
```

### `Agent.run()` should own only

- `ai_agent.run(...)`
- usage extraction
- final result dict creation
- thread persistence

### `Agent.run_stream()` should own only

- `agent.iter(...)`
- graph event translation
- streamed text accumulation
- final `done`
- `error`
- thread persistence after stream completion

### Result

This is the real internal boundary for sync vs stream behavior.

---

## Slice 4 — Clean up `AgentActor` as a thin adapter

Remove the duplicated bridge logic and descriptor reach-in.

Add:

```python
def _agent_runtime_config(self, task: str, **kwargs) -> CallConfig:
    ...
```

### This helper should own

- `self.prompt`
- `self._resolve_tool_addrs()`
- merged constraints
- `user`, `thread_id`, `result_type`
- llm override/defaulting

### Target shape

```python
@expose_route('/agentic', methods=['POST'])
async def agentic(self, task: str, **kwargs) -> str:
    call = self._agent_runtime_config(task, **kwargs)
    prepared = await Agent.prepare(self, call)
    result = await Agent.call(prepared, call.task)
    return json.dumps(result, default=str)
```

And similarly for stream.

### Result

`AgentActor` becomes a clean adapter instead of a special-case bypass.

---

## Slice 5 — Normalize return shape internally

Do **not** change public return contracts in Phase 1.

Instead:

- standardize on one internal Python result dict from `execute_once()`
- standardize on one internal Python result dict from `Agent.run()`
- let `AgentMixin.agentic()` return that dict directly
- let `AgentActor.agentic()` remain a thin JSON serializer over that dict

### Result

We improve coherence without breaking current callers.

---

## 💻 Code-shape preview

### `mixin.py`

```python
class AgentMixin:
    @fullmethod
    async def agentic(target, task: str, **kwargs) -> dict:
        call = resolve_agent_call(target, task, kwargs)
        prepared = await Agent.prepare(target, call)
        return await Agent.call(prepared, call.task)

    @fullmethod
    async def agentic_stream(target, task: str, **kwargs):
        call = resolve_agent_call(target, task, kwargs)
        prepared = await Agent.prepare(target, call)
        async for chunk in Agent.call_stream(prepared, call.task):
            yield chunk
```

### `actor.py`

```python
class AgentActor(ActorModel):
    def _agent_runtime_config(self, task: str, **kwargs) -> CallConfig:
        ...

    @expose_route('/agentic', methods=['POST'])
    async def agentic(self, task: str, **kwargs) -> str:
        call = self._agent_runtime_config(task, **kwargs)
        prepared = await Agent.prepare(self, call)
        return json.dumps(await Agent.call(prepared, call.task), default=str)
```

### Naming note

To avoid confusion with `pydantic_ai.Agent`, import the upstream class as:

```python
from pydantic_ai import Agent as PydanticAgent
```

Then reserve `Agent` for the package’s own runtime abstraction.

---

## 📊 Risks and defaults

| Risk | Why it matters | Default |
|---|---|---|
| config cascade drift | subtle user-facing behavior changes | pin with tests first |
| stream contract drift | frontend likely depends on chunk shapes | preserve exactly |
| `AgentActor` return-type break | existing callers/tests parse JSON | keep JSON string |
| class-level stream behavior | current code instantiates `target()` | preserve in phase 1 |
| thread behavior drift | tests rely on subtle semantics | preserve first |

---

## 🧪 Verification plan

Run at each slice:

1. `pytest src/n3tx_agents/tests/test_mixin.py`
2. `pytest src/n3tx_agents/tests/test_agent_actor.py`
3. `pytest src/n3tx_agents/tests/test_thread.py`
4. `pytest src/n3tx_agents/tests/test_run_stream_first_token.py`

Run targeted `test_tools.py` cases only if tool wiring changes indirectly.

### Add focused tests for

- extracted `resolve_agent_call(...)`
- extracted `Agent.prepare(...)`
- `AgentActor` adapter parity
- JSON wrapper preservation for `AgentActor.agentic()`

---

## 📌 Recommended execution order

```text
tests
 -> resolve_agent_call
 -> Agent.prepare
 -> Agent.run / Agent.run_stream
 -> AgentActor adapter cleanup
 -> internal return normalization
```

---

## ❓Open decisions already resolved for this phase

| Question | Default answer |
|---|---|
| Preserve `AgentActor.agentic()` JSON string output? | Yes |
| Avoid file/module churn and mostly refactor in place? | Yes |
| Include agent-endpoint exclusion cleanup now? | No, defer to tools-focused phase |

---

## Critical files for implementation

- `src/n3tx_agents/mixin.py`
- `src/n3tx_agents/actor.py`
- `src/n3tx_agents/tests/test_mixin.py`
- `src/n3tx_agents/tests/test_agent_actor.py`
- `src/n3tx_agents/tests/test_thread.py`

---

## Saved plan

- `.project/refactor/2-agents/1-ntx-agent-phase-1-runtime-refactor-plan.md`
