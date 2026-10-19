# Deep Refactor Plan for `n3tx_agents`

## ✅ Recommendation

Refactor `n3tx_agents` around one shared execution core.

Default path:

1. keep the public API stable
2. extract shared policy resolution from `agentic()` / `agentic_stream()`
3. extract shared runtime preparation from `run()` / `run_stream()`
4. turn `AgentActor` into a thin DB-config adapter over that same core
5. split `tools.py` by responsibility only after the runtime seams are in place

This trims the biggest entropy sources without changing the package’s contract.

---

## 📍 Current State

### What exists now

| Area | Today | Refactor pressure |
|---|---|---|
| `mixin.py` | policy, engine, thread IO, tool wiring, streaming event translation | too many responsibilities; sync/stream duplication |
| `actor.py` | persisted agent model + DB tool resolution + HTTP endpoints + stream event models | reaches into `AgentMixin.__dict__['run'].fn` internals |
| `tools.py` | schema discovery + tool transport + dynamic wrapper generation | mixed concerns, harder to test in isolation |
| `thread.py` | message history conversion and storage model | conceptually clean, but thread IO lives in `mixin.py` |

### High-confidence findings from exploration

- `run()` and `run_stream()` duplicate most setup logic.
- `agentic()` and `agentic_stream()` duplicate most config resolution logic.
- `AgentActor.agentic()` and `AgentActor.agentic_stream()` duplicate the same DB wrapper logic.
- `AgentActor` currently bypasses mixin dispatch via descriptor internals.
- The real compatibility surface is defined mainly by tests in:
  - `tests/test_mixin.py`
  - `tests/test_agent_actor.py`
  - `tests/test_tools.py`
  - `tests/test_thread.py`

---

## 🎯 Target State

Build a simpler internal shape while preserving external behavior.

```text
public policy methods
  agentic() / agentic_stream()
          |
          v
  resolve_call_config(...)
          |
          v
  prepare_execution(...)
          |
    +-----+------------------+
    |                        |
    v                        v
 execute_once(...)     execute_stream(...)
    |                        |
    +-----------+------------+
                |
                v
        persist thread history
```

### Keep stable

- `AgentMixin` public methods
- `AgentActor` as DB-backed runtime-configured agent model
- stream chunk names and payload shapes
- tool naming and schema-driven discovery behavior
- thread storage format
- `AgentActor.agentic()` returning JSON string

### Change internally

- one shared config resolver
- one shared runtime-preparation path
- one explicit engine entrypoint that `AgentActor` can call cleanly
- smaller modules with clearer boundaries

---

## 🧭 Proposed Module Shape

Recommended end state:

| Module | Responsibility |
|---|---|
| `mixin.py` | thin public facade only |
| `runtime.py` | shared execution preparation + shared helpers |
| `execution.py` | `execute_once()` and `execute_stream()` |
| `thread.py` | message conversion + optionally thread repository helpers |
| `actor.py` | `AgentActor` model + route adapters |
| `tools/discovery.py` | schema -> `ToolSpec` discovery |
| `tools/runtime.py` | TX routing + wrapper generation |

This can be reached incrementally without a big-bang rewrite.

---

## 🪜 Thin Implementation Slices

### Slice 1 — Freeze behavior with targeted regression coverage

Add/expand tests before moving code:

- `AgentActor.agentic()` and `.agentic_stream()` use same config merge semantics
- class-level `agentic_stream()` behavior is explicitly covered
- self-exclusion / agent exclusion behavior in `discover_tools()` is pinned
- thread ownership matching (`agents` vs `agents/1`) is pinned
- stream event ordering stays stable

Why first: this refactor is mostly structural, so test fences matter more than new features.

---

### Slice 2 — Extract shared policy resolution

Create one internal helper for config cascade and call normalization.

Representative shape:

```python
@dataclass
class AgentCallConfig:
    task: str
    prompt: str
    tools: list[str]
    user: dict | None
    constraints: dict
    thread_id: int | None
    create_thread: bool
    result_type: type | None
    llm_override: object | None


def resolve_agent_call(target, task: str, kwargs: dict) -> AgentCallConfig:
    ...
```

Use it from both:

- `AgentMixin.agentic()`
- `AgentMixin.agentic_stream()`

Result: one source of truth for prompt/tool/constraint resolution.

---

### Slice 3 — Extract shared runtime preparation

Create one internal object for all repeated setup done in `run()` and `run_stream()`.

Representative shape:

```python
@dataclass
class PreparedExecution:
    llm: object
    root: Actor
    agent_addr: str
    thread_id: int | None
    message_history: list | None
    ai_agent: Agent
    deps: AgentDeps
    usage_limits: UsageLimits | None


async def prepare_execution(target, *, prompt, tools, user,
                            constraints, thread_id,
                            create_thread, result_type, llm=None) -> PreparedExecution:
    ...
```

This helper should own:

- llm resolution
- matrix root lookup
- thread preload/create
- tool discovery
- tool wrapping
- pydantic-ai `Agent` creation
- deps and usage limits

Result: `run()` and `run_stream()` differ only at the terminal execution mode.

---

### Slice 4 — Split terminal execution paths cleanly

Keep two small execution functions:

```python
async def execute_once(prepared: PreparedExecution, task: str) -> dict:
    ...

async def execute_stream(prepared: PreparedExecution, task: str):
    yield ...
```

`execute_stream()` should own only stream-specific concerns:

- graph iteration
- event-to-chunk translation
- streamed text fallback
- final `done` / `error` chunks

`execute_once()` should own only:

- `ai_agent.run(...)`
- result serialization
- thread persistence

---

### Slice 5 — Clean up `AgentActor` boundary

Replace descriptor bypassing with an explicit engine call.

Current smell:

```python
run_fn = AgentMixin.__dict__['run'].fn
```

Target shape:

```python
config = self._build_agent_call_config(task, kwargs)
result = await execute_once(await prepare_execution(self, **config.runtime_args()), config.task)
```

Recommended extra extraction inside `actor.py`:

```python
def _agent_runtime_config(self, task: str, **kwargs) -> AgentCallConfig:
    ...
```

Also extract the duplicated wrapper shared by:

- `agentic()`
- `agentic_stream()`

This makes `AgentActor` a clean adapter instead of a special-case hack.

---

### Slice 6 — Simplify `tools.py`

After runtime extraction, split `tools.py` by concern.

Recommended split:

- discovery: schema reading, CRUD specs, exposed-method specs
- runtime: TX routing, generated function creation, `make_tool`

Also review one likely bug / stale naming mismatch:

- `discover_tools()` excludes `{'run', 'stream_run'}` for `AgentActor`
- actual public methods are `agentic` / `agentic_stream`

Decide explicitly whether agents should expose agent-calling endpoints as tools at all.

Default recommendation: **do not auto-expose agentic endpoints as tools** unless agent-to-agent delegation is a deliberate feature.

---

### Slice 7 — Re-evaluate tiny modules and noisy concepts

After the core extraction lands:

- consider moving `AgentDeps` into runtime if it remains tiny and package-private
- consider colocating stream event models with a dedicated stream schema module if `actor.py` still feels overloaded
- keep `thread.py` separate; it is already a good deep module

Do **not** merge files just to reduce count; merge only where it reduces conceptual hops.

---

## 💻 Code-Shape Preview

### `mixin.py` after refactor

```python
class AgentMixin:
    @fullmethod
    async def agentic(target, task: str, **kwargs) -> dict:
        call = resolve_agent_call(target, task, kwargs)
        prepared = await prepare_execution(target, **call.runtime_args())
        return await execute_once(prepared, call.task)

    @fullmethod
    async def agentic_stream(target, task: str, **kwargs):
        call = resolve_agent_call(target, task, kwargs)
        prepared = await prepare_execution(target, **call.runtime_args())
        async for chunk in execute_stream(prepared, call.task):
            yield chunk
```

### `actor.py` after refactor

```python
class AgentActor(ActorModel):
    def _resolve_tool_addrs(self) -> list[str]: ...

    def _agent_runtime_config(self, task: str, **kwargs) -> AgentCallConfig:
        ...

    @expose_route('/agentic', methods=['POST'])
    async def agentic(self, task: str, **kwargs) -> str:
        call = self._agent_runtime_config(task, **kwargs)
        prepared = await prepare_execution(self, **call.runtime_args())
        return json.dumps(await execute_once(prepared, call.task), default=str)
```

### `tools` split

```text
tools/
  __init__.py
  discovery.py    # ToolSpec, discover_tools, _crud_tool_specs, _method_tool_specs
  runtime.py      # _route_tool_call, create_tool_function, make_tool
```

---

## 📊 Trade-offs

| Option | Pros | Cons | Recommendation |
|---|---|---|---|
| Small internal extraction only | low risk, keeps public API stable | less dramatic cleanup | ✅ start here |
| Rewrite around a new agent service layer immediately | cleanest final architecture | larger diff, more breakage risk | not first move |
| Merge AgentActor into generic mixin model | fewer concepts | breaks important “agents are data” boundary | avoid |

---

## ⚠️ Risks and Design Decisions

| Risk / decision | Why it matters | Default path |
|---|---|---|
| `AgentActor.agentic()` returns JSON string | externally tested and documented | preserve for now |
| thread ownership by scope vs exact addr | subtle multi-turn behavior | preserve semantics first, simplify later |
| stream event chunk shape | frontend likely depends on it | preserve exactly |
| class-level `agentic_stream()` instantiates `target()` | may be brittle for models with required init args | test it, then decide whether to keep or deprecate |
| agent tools exposing agent endpoints | can create loops / confusing recursion | disable unless explicitly intended |

---

## 🧪 Verification Plan

Run at each slice:

1. `pytest src/n3tx_agents/tests/test_mixin.py`
2. `pytest src/n3tx_agents/tests/test_agent_actor.py`
3. `pytest src/n3tx_agents/tests/test_tools.py`
4. `pytest src/n3tx_agents/tests/test_thread.py`
5. full package test run

Add focused tests for:

- extracted config resolver behavior
- extracted runtime preparation behavior
- `AgentActor` adapter behavior
- tool exclusion rules for agent endpoints
- streaming first-token regression

---

## 🗺️ Recommended Execution Order

```text
tests -> shared call config -> shared runtime prep ->
sync/stream executors -> AgentActor adapter cleanup ->
tools split -> optional final module tidy-up
```

This order minimizes blast radius and keeps each commit reviewable.

---

## ❓Open Questions

These are not blockers for the first refactor wave, but they should be decided before the later cleanup slices:

1. Should agent-to-agent delegation exist as a first-class feature, or should agent endpoints be excluded from tool discovery entirely?
2. Do you want static frontend components under `static/components/` in scope for this simplification pass, or should this stay backend/runtime-only?
3. Should thread ownership remain dual-mode (`agents` and `agents/1`), or do you want a stricter identity model after parity is preserved?

---

## Next Steps

1. implement slice 1 test fences
2. extract `resolve_agent_call(...)`
3. extract `prepare_execution(...)`
4. move `run()` and `run_stream()` onto shared execution prep
5. remove `AgentMixin.__dict__['run'].fn` bypasses

### Critical Files for Implementation

- src/n3tx_agents/mixin.py
- src/n3tx_agents/actor.py
- src/n3tx_agents/tools.py
- src/n3tx_agents/thread.py
- src/n3tx_agents/tests/test_mixin.py

### Saved Plan

- `.project/refactor/2-agents/0-ntx-agent-deep-refactor-plan.md`
