# 🧭 Phase 1 Issue Implementation Plans

This document captures issue-by-issue implementation plans for Phase 1 of the
`n3tx_agents` runtime refactor.

## 📚 Primary references

- `.project/refactor/2-agents/2-phase-1-prd.md`
- `.project/refactor/2-agents/3-phase-1-issues.jsonl`
- `.project/refactor/2-agents/1-ntx-agent-phase-1-runtime-refactor-plan.md`
- `.project/refactor/2-agents/10-agents-refactor-audit.md`

## 🗺️ Phase 1 sequencing map

```text
+----------------------+     +----------------------+     +----------------------+
| #1 Regression fences | --> | #2 Resolved call     | --> | #3 Runtime prep      |
| tests only           |     | mixin policy cleanup |     | sync path            |
+----------------------+     +----------------------+     +----------------------+
                                      |
                                      v
                           +----------------------+
                           | #4 Stream runtime    |
                           | shared prep path     |
                           +----------------------+
                                      |
                                      v
                           +----------------------+
                           | #5 AgentActor seam   |
                           | DB adapter cleanup   |
                           +----------------------+
                                      |
                                      v
                           +----------------------+
                           | #6 Result shape      |
                           | internal normalize   |
                           +----------------------+
```

---

## 🧪 Issue #1 — Freeze Phase 1 compatibility with regression fences

### 🎯 Goal

Add the missing regression-fence tests needed before Phase 1 runtime refactoring
begins.

This issue should not change production behavior. It should only strengthen the
test envelope around the current externally visible contract so later refactor
slices can proceed safely.

### 🔎 What already exists

Current tests already cover:

- `agentic()` basic kwargs override behavior
- `agentic_stream()` basic chunking
- `run_stream()` ordering and first-token behavior
- thread behavior for `run()` and `run_stream()`
- `AgentActor.agentic()` JSON-string output
- `AgentActor.agentic_stream()` basic chunk behavior

### 🧩 Missing regression fences

The main uncovered areas are:

| Gap | Why it matters |
|---|---|
| `agentic()` vs `agentic_stream()` config parity | Phase 1 will centralize call normalization; parity must be pinned first |
| `AgentActor.agentic()` vs `agentic_stream()` config merge parity | Phase 1 will rewire the DB-backed adapter; parity needs explicit coverage |
| sync/stream thread and create-thread parity at the policy edge | engine behavior is covered, but adapter-level forwarding semantics need stronger fences |
| class-level `agentic_stream()` as a dedicated regression fence | current behavior exists, but should be pinned more explicitly |

### 🧱 Test fence architecture

```text
                 compatibility behaviors to freeze
                              |
      +-----------------------+-----------------------+
      |                       |                       |
      v                       v                       v
+-------------+       +----------------+       +----------------+
| AgentMixin  |       | AgentActor     |       | Streaming /    |
| policy edge |       | DB adapter     |       | thread edges   |
+-------------+       +----------------+       +----------------+
      |                       |                       |
      v                       v                       v
assert forwarded      assert merged DB        assert ordering,
runtime kwargs        config parity           thread and class-call
```

### 📍 Files likely to change

- `packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py`
- `packages/n3tx-agents/src/n3tx_agents/tests/test_agent_actor.py`
- possibly `packages/n3tx-agents/src/n3tx_agents/tests/test_thread.py` if one
  narrow adapter-level parity assertion belongs there

No production-code changes are expected for this issue.

### ✅ Test strategy

Focus on **external forwarding semantics**, not implementation details.

#### 1. 🔁 Mixin policy parity tests

Add tests that verify `agentic()` and `agentic_stream()` normalize and forward
the same values for:

- prompt
- tools
- constraints
- user
- thread_id
- result_type
- llm override

Recommended shape:

- define a small `__agent__ = True` test model
- patch or stub `run()` and `run_stream()` to capture forwarded kwargs
- assert the normalized payloads match where they should

#### 2. 🗄️ `AgentActor` adapter parity tests

Add tests that verify `AgentActor.agentic()` and `AgentActor.agentic_stream()`
apply the same DB-backed merge behavior for:

- resolved tool addresses
- instance prompt
- instance/default llm
- merged constraints
- forwarded user / thread_id / result_type

Recommended shape:

- create an `AgentActor`
- patch the underlying mixin engine calls
- assert both methods forward equivalent runtime inputs

#### 3. 🌊 Class-level `agentic_stream()` regression fence

Add a dedicated test that explicitly proves class-level streaming invocation
still works and reaches the stream engine with the expected normalized arguments.

### 🪜 Implementation sequence

```text
+------+----------------------------------------------------------+
| Step | Action                                                   |
+------+----------------------------------------------------------+
|  1   | Add mixin parity tests                                   |
|  2   | Add AgentActor parity tests                              |
|  3   | Add narrow thread-forwarding fence if still needed       |
|  4   | Run targeted agent test suites                           |
+------+----------------------------------------------------------+
```

### 🧪 Verification

Run at minimum:

1. `pytest packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py`
2. `pytest packages/n3tx-agents/src/n3tx_agents/tests/test_agent_actor.py`
3. `pytest packages/n3tx-agents/src/n3tx_agents/tests/test_thread.py`
4. `pytest packages/n3tx-agents/src/n3tx_agents/tests/test_run_stream_first_token.py`

### ⚠️ Risks and guardrails

| Risk | Guardrail |
|---|---|
| tests accidentally lock in implementation details | assert on normalized/forwarded behavior only |
| monkeypatching fullmethod-backed flows becomes brittle | patch stable call sites and compare argument payloads |
| current behavior differs from older planning language | treat current code + passing tests as the source of truth |

### ✅ Definition of done

- regression fences exist for the missing parity behaviors
- no production code changes were needed
- targeted suites pass
- the resulting tests clearly protect the upcoming Phase 1 runtime refactor

---

## 🧱 Issue #2 — Introduce `CallConfig` and unify mixin call normalization

### 🎯 Goal

Create one shared call-normalization path for `AgentMixin.agentic()` and
`AgentMixin.agentic_stream()`.

This issue should preserve all externally visible behavior while removing the
duplicated policy/config resolution currently implemented separately in the sync
and streaming entrypoints.

### 🗺️ Target flow

```text
+------------------------------------+
| AgentMixin.agentic(task, **kwargs)  |
+------------------------------------+
                  |
                  | same policy resolver
                  v
+------------------------------------+       +-----------------------------------------+
| resolve_agent_call(target, task,    | <---  | AgentMixin.agentic_stream(task, **kwargs)|
|                    kwargs)          |       +-----------------------------------------+
+------------------------------------+
                  |
                  v
+------------------------------------+
| CallConfig                  |
| - task                             |
| - prompt                           |
| - tools                            |
| - constraints                      |
| - user / thread / result_type      |
| - optional llm override marker     |
+------------------------------------+
                  |
       +----------+-----------+
       |                      |
       v                      v
+-------------------+  +---------------------------+
| target.run(...)   |  | instance.run_stream(...)   |
+-------------------+  +---------------------------+
```

### 💡 Why this issue matters

`agentic()` and `agentic_stream()` are the public policy layer for
class-configured agent models. Today they independently resolve the same call
inputs:

- prompt
- tool addresses
- merged constraints
- user context
- thread id
- result type
- optional llm override

Phase 1 will later introduce a shared runtime seam behind `run()` and
`run_stream()`. Before doing that, the policy layer needs a single internal
representation of a resolved call so future runtime work has one clean input
shape instead of two nearly-identical branches.

### 🔎 What already exists

Current code in `packages/n3tx-agents/src/n3tx_agents/mixin.py` has the relevant
duplication in:

- `AgentMixin.agentic()` — resolves config and calls `target.run(...)`
- `AgentMixin.agentic_stream()` — resolves nearly the same config and calls
  `instance.run_stream(...)`

Current tests already cover many external behaviors, including:

- basic `agentic()` execution
- explicit prompt override
- explicit `tools=[]` override behavior
- basic constraint override behavior
- class vs instance `agentic()` behavior
- basic `agentic_stream()` chunking
- class-level streaming behavior indirectly through existing stream tests

Issue #1 should add the missing regression fences before this refactor lands.
Issue #2 should then make the smallest behavior-preserving production change
that satisfies those tests.

### 📍 Files likely to change

- `packages/n3tx-agents/src/n3tx_agents/mixin.py`
- `packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py` if issue #1 tests
  need small follow-up adjustment after the production refactor
- `packages/n3tx-agents/docs/mixin.md` if documenting the new internal resolved
  call seam is useful after implementation

No `AgentActor` production changes should be made in this issue. `AgentActor`
rewiring belongs to issue #5 after the shared runtime seam exists.

### ✅ In scope

| Area | Change |
|---|---|
| call normalization | introduce a shared `CallConfig` value object |
| config cascade | move duplicated prompt/tools/constraints/user/thread/result-type resolution into one helper |
| sync policy | make `agentic()` call the shared resolver and forward `runtime_args()` to `run()` |
| stream policy | make `agentic_stream()` call the same resolver and forward `runtime_args()` to `run_stream()` |
| compatibility | preserve current prompt, tools, constraints, llm, thread, result-type, and class-level stream behavior |

### 🚫 Out of scope

- extracting runtime preparation from `run()` / `run_stream()`
- introducing the internal runtime `Agent` abstraction
- changing `run()` or `run_stream()` signatures
- changing `AgentActor.agentic()` / `AgentActor.agentic_stream()`
- changing thread creation/loading/update semantics
- changing stream event names, payload shapes, or ordering
- changing the public return shape of any method
- changing tool discovery policy

### 🔒 Current behavior to preserve

| Behavior | Current rule | Required preservation |
|---|---|---|
| prompt resolution | `kwargs.get('prompt') or target.ctx()` | keep truthiness behavior exactly |
| tools resolution | `kwargs['tools'] if 'tools' in kwargs else target.tools()` | keep explicit `tools=[]` as valid “no tools” |
| constraints cascade | `config.AGENT_DEFAULTS['constraints'] < __agent__['constraints'] < kwargs['constraints']` | preserve merge order |
| user forwarding | `kwargs.get('user')` | preserve value and omission behavior |
| thread forwarding | `kwargs.get('thread_id')` | preserve `None` / omitted behavior |
| result type | `kwargs.get('result_type') or model_conf.get('result_type')` | preserve fallback behavior |
| llm forwarding | only include `llm` in engine kwargs when `'llm' in kwargs` | preserve distinction between omitted and explicit override |
| class-level stream | `target()` is instantiated before `run_stream()` | preserve for Phase 1 |

### 🧬 Proposed implementation shape

Add a small immutable value object in `mixin.py` near the existing module-level
helpers. Keep it internal to the module for now; it does not need to be exported
from `n3tx_agents.__init__`.

Representative shape:

```python
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CallConfig:
    task: str
    prompt: str
    tools: list
    user: dict | None
    constraints: dict
    thread_id: int | None
    result_type: Any = None
    llm: Any = None
    has_llm_override: bool = False

    def runtime_args(self) -> dict:
        args = {
            'task': self.task,
            'prompt': self.prompt,
            'tools': self.tools,
            'user': self.user,
            'constraints': self.constraints,
            'thread_id': self.thread_id,
            'result_type': self.result_type,
        }
        if self.has_llm_override:
            args['llm'] = self.llm
        return args
```

Add one resolver function:

```python
def resolve_agent_call(target, task: str, kwargs: dict) -> CallConfig:
    cls = target if isinstance(target, type) else target.__class__
    agent_flag = getattr(cls, '__agent__', False)
    model_conf = agent_flag if isinstance(agent_flag, dict) else {}
    defaults = config.AGENT_DEFAULTS

    prompt = kwargs.get('prompt') or target.ctx()
    tools = kwargs['tools'] if 'tools' in kwargs else target.tools()

    constraints = dict(defaults.get('constraints', {}))
    constraints.update(model_conf.get('constraints', {}))
    constraints.update(kwargs.get('constraints', {}))

    return CallConfig(
        task=task,
        prompt=prompt,
        tools=tools,
        user=kwargs.get('user'),
        constraints=constraints,
        thread_id=kwargs.get('thread_id'),
        result_type=kwargs.get('result_type') or model_conf.get('result_type'),
        llm=kwargs.get('llm'),
        has_llm_override='llm' in kwargs,
    )
```

Then simplify `agentic()`:

```python
@fullmethod
async def agentic(target, task: str, **kwargs) -> dict:
  call = resolve_agent_call(target, task, kwargs)
  return await target.call(**call.runtime_args())
```

And simplify `agentic_stream()` while preserving the current class-level
instantiation behavior:

```python
@fullmethod
async def agentic_stream(target, task: str, **kwargs):
  call = resolve_agent_call(target, task, kwargs)
  instance = target() if isinstance(target, type) else target

  async for chunk in instance.call_stream(**call.runtime_args()):
    yield chunk
```

### 🧠 Design notes

#### ⚙️ `has_llm_override` is intentional

Do not simply include `llm=kwargs.get('llm')` in every runtime call. Current
behavior only forwards `llm` to `run()` / `run_stream()` when the caller supplied
the kwarg. If omitted, the engine resolves llm from:

```text
+-------------------+     +-------------------+     +-----------------------------+
| __agent__['llm']  | --> | instance.llm      | --> | config.AGENT_DEFAULTS['llm'] |
+-------------------+     +-------------------+     +-----------------------------+
```

Always forwarding `llm=None` would be easy to misread and could become dangerous
when later runtime extraction changes resolution code. The explicit
`has_llm_override` flag preserves the current distinction.

#### 🧯 Keep concrete LLM resolution out of this issue

`resolve_agent_call()` should normalize policy-layer inputs only. It should not
call `_resolve_llm()` and should not instantiate or validate model providers.
Concrete llm resolution remains in `run()` / `run_stream()` until the runtime
preparation issue.

#### 🌊 Keep class-level stream instantiation unchanged

The current `agentic_stream()` implementation instantiates `target()` when called
on a class. This may be revisited later because it assumes zero-argument model
construction, but Phase 1 intentionally preserves it. Issue #2 should move that
behavior without redesigning it.

#### 📦 Keep the helper module-local for now

`CallConfig` will become more important once `AgentActor` and the runtime
seam use it in later issues. For issue #2, keep it in `mixin.py` unless the
implementation becomes too large. Avoid creating new modules before the runtime
boundary is ready; this keeps the diff small and reviewable.

### 🪜 Implementation sequence

```text
+------+--------------------------------------------------------------------------+
| Step | Action                                                                   |
+------+--------------------------------------------------------------------------+
|  1   | Confirm issue #1 regression-fence tests are available and passing        |
|  2   | Add `CallConfig` and `resolve_agent_call(...)` to `mixin.py`      |
|  3   | Refactor `AgentMixin.agentic()` to use the resolver                      |
|  4   | Run `test_mixin.py` and fix behavior drift if any                        |
|  5   | Refactor `AgentMixin.agentic_stream()` to use the same resolver          |
|  6   | Run `test_mixin.py`, then `test_agent_actor.py` as a smoke check         |
|  7   | Inspect final diff to ensure only call-normalization code changed        |
|  8   | Update `packages/n3tx-agents/docs/mixin.md` only if useful now           |
+------+--------------------------------------------------------------------------+
```

### 🧪 Suggested test coverage for this issue

Issue #1 should already add most of these. If not, add the minimum missing tests
before changing production code.

#### 🔁 Mixin call-normalization parity

Assert that `agentic()` and `agentic_stream()` forward equivalent normalized
arguments for:

- explicit prompt
- explicit `tools=[]`
- merged constraints
- user
- thread_id
- result_type
- llm override

Recommended test style:

- define a small `__agent__ = True` model with model-level constraints and result type
- monkeypatch or override stable engine methods (`run` / `run_stream`) to capture kwargs
- compare captured runtime payloads rather than internal helper fields

#### ⚙️ Omitted vs explicit `llm`

Add or preserve a test that proves omitted `llm` is not forwarded as an explicit
override, while provided `llm` is forwarded.

This is the most important subtle compatibility point in the issue.

#### 🧰 `tools=[]` remains explicit

Add or preserve a test that proves `tools=[]` does not fall back to
`target.tools()`.

#### 🌊 Class-level streaming behavior

Preserve a test proving class-level `AgenticModel.agentic_stream(...)` still
reaches the stream engine successfully after the resolver extraction.

### 🧪 Verification

Run the narrow agent tests first:

```bash
python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py -q
python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_agent_actor.py -q
```

Then run the broader agent package suite if the narrow tests pass:

```bash
python3 scripts/test-backend.py --suite agents -- -q
```

If issue #1 added or emphasized stream-first-token coverage, include:

```bash
python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_run_stream_first_token.py -q
```

### ⚠️ Risks and guardrails

| Risk | Why it matters | Guardrail |
|---|---|---|
| `llm` override semantics drift | later runtime extraction depends on exact override behavior | use `has_llm_override`; test omitted vs explicit llm |
| `tools=[]` accidentally falls back to auto-discovery | empty tools is a supported explicit call shape | keep `'tools' in kwargs` check |
| stream policy changes class-level behavior | current code instantiates `target()` | preserve the instantiation exactly |
| helper becomes a premature public API | this is an internal refactor slice | keep `CallConfig` module-local and unexported |
| tests assert helper internals | would make later reshaping harder | assert forwarded runtime behavior instead |

### ✅ Definition of done

- `CallConfig` exists as the single internal call-normalization shape for
  `AgentMixin` policy methods.
- `AgentMixin.agentic()` and `AgentMixin.agentic_stream()` both use
  `resolve_agent_call(...)`.
- Current public behavior is unchanged.
- `llm` override semantics, `tools=[]`, config cascade, result type fallback,
  thread forwarding, and class-level stream behavior are preserved.
- Targeted agent tests pass.
- No `AgentActor` runtime rewiring is included in this issue.

---

## 🌊 Issue #4 — Move streaming execution behind the shared `Agent` runtime

### 🎯 Goal

Route streaming execution through the same runtime-preparation seam introduced by
Issue #3.

This issue should move terminal stream execution out of `AgentMixin.run_stream()`
and behind the internal `Agent.run_stream(...)` runtime method while preserving
the exact stream contract.

### 🗺️ Target flow

```text
+-----------------------------------------+
| AgentMixin.agentic_stream(task, **kwargs)|
+-----------------------------------------+
                    |
                    v
+-----------------------------------------+
| CallConfig                       |
+-----------------------------------------+
                    |
                    v
+-----------------------------------------+
| Agent.prepare(target, call)             |
+-----------------------------------------+
                    |
                    v
+-----------------------------------------+
| PreparedCall                        |
| - root                                  |
| - agent_addr                            |
| - thread_id                             |
| - message_history                       |
| - ai_agent                              |
| - deps                                  |
| - usage_limits                          |
+-----------------------------------------+
                    |
                    v
+-----------------------------------------+
| Agent.run_stream(prepared, call.task)   |
+-----------------------------------------+
                    |
                    v
       text / tool_call / tool_result / thinking / done / error
```

### 🔎 Current streaming path

`AgentMixin.run_stream()` currently owns both runtime preparation and terminal
stream execution:

```text
AgentMixin.run_stream(...)
        |
        +--> resolve llm
        +--> Actor.root()
        +--> load/create thread
        +--> discover_tools(...)
        +--> make_tool(...)
        +--> build PydanticAgent
        +--> build AgentDeps
        +--> build UsageLimits
        +--> ai_agent.iter(...)
        +--> translate graph events to chunks
        +--> persist thread
        +--> yield done/error
```

After Issue #3, runtime preparation should already be represented by
`Agent.prepare(...)`. Issue #4 should reuse that seam instead of rebuilding the
same setup inside the streaming path.

### 📍 Files likely to change

- `packages/n3tx-agents/src/n3tx_agents/mixin.py`
- `packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py`
- `packages/n3tx-agents/src/n3tx_agents/tests/test_thread.py`
- `packages/n3tx-agents/docs/mixin.md` if documenting the shared runtime seam is useful after implementation

### ✅ In scope

| Area | Change |
|---|---|
| stream runtime | add `Agent.run_stream(prepared, task)` |
| stream preparation | route `AgentMixin.run_stream()` through `Agent.prepare(...)` |
| stream chunks | move existing graph-event translation without changing payloads |
| thread persistence | keep post-stream `_update_thread(...)` behavior unchanged |
| error behavior | preserve yielded error chunks instead of raised exceptions |

### 🚫 Out of scope

- changing stream event names or payload shapes
- changing stream ordering or seq behavior
- changing `AgentActor` streaming adapter logic
- changing `AgentActor.agentic()` JSON-string behavior
- splitting runtime code into new modules
- redesigning thread identity or storage semantics

### 🔒 Stream behavior to preserve exactly

| Contract | Required preservation |
|---|---|
| `text` chunks | `{'name': 'text', 'data': {'text': ...}, 'meta': {'stream': True, 'seq': N}}` |
| `tool_call` chunks | same `tool`, `args`, `call_id` shape |
| `tool_result` chunks | same `tool`, `result`, `call_id` shape |
| `thinking` chunks | same `{'text': ...}` shape |
| `done` data | includes `answer`, `usage`, `tool_calls`, optional `thread_id` |
| `done.meta` | includes `stream=True`, `stream_end=True`, `seq` |
| `error` chunks | yielded with `name='error'`, `code=500`, `meta.error=True` |
| ordering | `tool_call` before matching `tool_result`, `done` last |
| seq | monotonically increasing integer sequence |
| output fallback | preserve `streamed_text` fallback when final output is empty |
| thread persistence | update thread after stream completion |

### 🧬 Proposed implementation shape

Assuming Issue #3 provides:

```python
@dataclass(frozen=True)
class PreparedCall:
    root: Actor
    agent_addr: str
    thread_id: int | None
    message_history: list | None
    ai_agent: PydanticAgent
    deps: AgentDeps
    usage_limits: UsageLimits | None
```

Add terminal streaming execution to the internal runtime class:

```python
class Agent:
    @classmethod
    async def run_stream(cls, prepared: PreparedCall, task: str):
        seq = 0
        try:
            run_kwargs = {'deps': prepared.deps}
            if prepared.usage_limits:
                run_kwargs['usage_limits'] = prepared.usage_limits
            if prepared.message_history:
                run_kwargs['message_history'] = prepared.message_history

            streamed_text = ''
            tool_call_count = 0

            async with prepared.ai_agent.iter(task, **run_kwargs) as agent_run:
                async for node in agent_run:
                    ...  # existing graph-event translation moved unchanged

                ...  # existing done-chunk construction moved unchanged

        except Exception as e:
            yield {
                'name': 'error',
                'data': {'message': str(e), 'code': 500},
                'meta': {'stream': True, 'error': True, 'seq': seq},
            }
```

Then shrink `AgentMixin.run_stream()` to a thin delegate:

```python
@fullmethod
async def run_stream(target, task: str, prompt: str, tools: list,
                     user: dict = None, constraints: dict = None,
                     thread_id=None, result_type=None, **kwargs):
  call = CallConfig(
    task=task,
    prompt=prompt,
    tools=tools,
    user=user,
    constraints=constraints or {},
    thread_id=thread_id,
    result_type=result_type,
    llm=kwargs.get('llm'),
    has_llm_override='llm' in kwargs,
  )
  prepared = await Agent.prepare(target, call)
  async for chunk in Agent.call_stream(prepared, call.task):
    yield chunk
```

### 🧠 Design notes

#### 🧯 Move code mechanically first

The safest implementation is a mechanical extraction: copy the existing
`run_stream()` terminal logic into `Agent.run_stream(...)`, replace local runtime
variables with `prepared.*`, then shrink the mixin method. Avoid opportunistic
cleanup until stream tests are green.

#### 🔁 Preserve the sync/runtime boundary

Issue #3 makes `Agent.prepare(...)` the owner of LLM resolution, root lookup,
thread preload/create, tools, deps, usage limits, and `PydanticAgent`
construction. Issue #4 should not duplicate any of that setup in
`AgentMixin.run_stream()`.

#### ⚠️ Keep broad exception handling stream-only

Current streaming catches exceptions and yields an error chunk. Sync execution
does not do that. Preserve this distinction: `Agent.run_stream(...)` should keep
the stream error chunk behavior, while `Agent.run(...)` should continue raising
sync exceptions normally.

### 🪜 Implementation sequence

```text
+------+--------------------------------------------------------------------------+
| Step | Action                                                                   |
+------+--------------------------------------------------------------------------+
|  1   | Confirm Issue #3 runtime seam has landed                                 |
|  2   | Add `Agent.run_stream(prepared, task)`                                    |
|  3   | Move run_kwargs construction into `Agent.run_stream(...)`                 |
|  4   | Move graph iteration and event translation unchanged                      |
|  5   | Move thread update and done/error chunk generation unchanged              |
|  6   | Refactor `AgentMixin.run_stream()` into thin delegate                     |
|  7   | Run streaming, thread, and AgentActor smoke tests                         |
+------+--------------------------------------------------------------------------+
```

### 🧪 Suggested test coverage

Existing tests should cover most of this issue if the extraction is truly
behavior-preserving:

- `test_yields_text_chunks`
- `test_done_chunk_has_usage`
- `test_error_chunk_on_failure`
- `test_text_chunks_backward_compat`
- `test_tool_call_event`
- `test_tool_result_event`
- `test_done_chunk_has_tool_calls_count`
- `test_seq_monotonically_increasing`
- `test_event_ordering_tool_call_before_result`
- `test_done_always_last`
- thread streaming tests in `test_thread.py`

If adding a seam-specific test, prefer checking observable behavior through
`AgentMixin.run_stream()` rather than asserting private fields on
`PreparedCall`.

### 🧪 Verification

Run streaming-focused tests first:

```bash
python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py -q
python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_thread.py -q
```

Then run AgentActor smoke coverage:

```bash
python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_agent_actor.py -q
```

Then run the full agents suite:

```bash
python3 scripts/test-backend.py --suite agents -- -q
```

### ⚠️ Risks and guardrails

| Risk | Why it matters | Guardrail |
|---|---|---|
| stream chunk drift | frontend depends on names and payloads | move event translation mechanically |
| done/error semantics drift | stream lifecycle depends on terminal chunks | preserve done/error construction exactly |
| seq drift | frontend ordering and tests rely on monotonic seq | keep one local `seq` counter in `Agent.run_stream()` |
| thread update drift | multi-turn streaming depends on persisted history | keep `_update_thread(...)` call unchanged |
| broad refactor creep | Issue #5 owns AgentActor rewiring | do not touch `AgentActor` here |

### ✅ Definition of done

- `Agent.run_stream(...)` owns terminal streaming execution.
- `AgentMixin.run_stream()` delegates to `Agent.prepare(...)` and
  `Agent.run_stream(...)`.
- `AgentMixin.agentic_stream()` continues using `CallConfig`.
- Existing stream chunk names, payloads, ordering, and error behavior are
  unchanged.
- Streaming thread behavior remains unchanged.
- Targeted streaming tests pass.

---

## 🧩 Issue #5 — Rewire `AgentActor` onto the explicit `Agent` runtime seam

### 🎯 Goal

Remove `AgentActor`'s descriptor-internal reach-in:

```python
AgentMixin.__dict__['run'].fn
AgentMixin.__dict__['run_stream'].fn
```

and replace it with a thin DB-backed adapter over the shared runtime seam used by
`AgentMixin`.

### 🗺️ Target flow

```text
+--------------------------+
| AgentActor DB record     |
| - prompt                 |
| - llm                    |
| - tools                  |
| - constraints            |
+------------+-------------+
             |
             v
+--------------------------+
| _agent_runtime_call(...) |
| - resolve tool addrs     |
| - merge constraints      |
| - normalize thread_id    |
| - choose llm override    |
+------------+-------------+
             |
             v
+--------------------------+
| CallConfig        |
+------------+-------------+
             |
             v
+--------------------------+
| Agent.prepare(self, call)|
+------------+-------------+
             |
      +------+------+
      |             |
      v             v
+------------+ +--------------------+
| Agent.run  | | Agent.run_stream   |
+------------+ +--------------------+
      |             |
      v             v
 JSON string    stream chunks
```

### 🔎 Current smell

`AgentActor` currently bypasses normal interfaces by reaching into the
`fullmethod` descriptor internals:

```python
run_fn = AgentMixin.__dict__['run'].fn
result = await run_fn(self, ...)
```

That means DB-backed agents are not true peers of class-configured agents; they
depend on implementation details of the mixin descriptor rather than an explicit
runtime contract.

### 📍 Files likely to change

- `packages/n3tx-agents/src/n3tx_agents/actor.py`
- `packages/n3tx-agents/src/n3tx_agents/tests/test_agent_actor.py`
- `packages/n3tx-agents/docs/agent-actor.md`
- `docs/AGENTS.md` if cross-cutting architecture text still references the old bypass path

### ✅ In scope

| Area | Change |
|---|---|
| DB-backed call normalization | add an `AgentActor` helper that builds `CallConfig` |
| sync adapter | route `agentic()` through `Agent.prepare(...)` + `Agent.run(...)` |
| stream adapter | route `agentic_stream()` through `Agent.prepare(...)` + `Agent.run_stream(...)` |
| descriptor cleanup | remove `AgentMixin.__dict__['run'].fn` and `.run_stream.fn` usage |
| compatibility | preserve JSON string sync output and stream chunk contract |

### 🚫 Out of scope

- changing `AgentActor.agentic()` away from JSON string output
- changing stream chunk shapes or ordering
- changing `_resolve_tool_addrs()` behavior
- redesigning `AgentTool` / `ListRef` storage
- changing tool discovery policy
- normalizing result contracts beyond the existing JSON wrapper

### 🔒 Behavior to preserve

| Contract | Required preservation |
|---|---|
| `AgentActor.agentic()` return type | JSON string |
| sync result content | same internal result dict serialized with `json.dumps(..., default=str)` |
| `AgentActor.agentic_stream()` | same chunk names, payloads, ordering, done/error behavior |
| tool resolution | still via `_resolve_tool_addrs()` |
| prompt | `self.prompt` |
| default llm | `self.llm` unless kwargs override |
| constraints | `{**self.constraints, **kwargs.get('constraints', {})}` |
| thread id | `0` becomes `None` |
| user/result_type | forwarded unchanged |
| routes/schema | no public endpoint or schema changes |

### 🧬 Proposed implementation shape

Import the explicit runtime pieces in `actor.py`:

```python
from n3tx_agents.mixin import Agent, CallConfig
```

Add a thin DB-backed adapter helper:

```python
def _agent_runtime_call(self, task: str, thread_id: int = 0,
                        **kwargs) -> CallConfig:
  return CallConfig(
    task=task,
    prompt=self.prompt,
    tools=self.tool_addrs(),
    user=kwargs.get('user'),
    constraints={**self.constraints, **kwargs.get('constraints', {})},
    thread_id=thread_id or None,
    result_type=kwargs.get('result_type'),
    llm=kwargs.get('llm', self.llm),
    has_llm_override=True,
  )
```

`has_llm_override=True` is intentional because current `AgentActor` behavior
always passes an llm into the engine:

```python
llm=kwargs.get('llm', self.llm)
```

Then refactor sync execution:

```python
@expose_route('/agentic', methods=['POST'])
async def agentic(self, task: str, thread_id: int = 0, **kwargs) -> str:
    call = self.call_config(task, thread_id=thread_id, **kwargs)
    prepared = await Agent.prepare(self, call)
    result = await Agent.call(prepared, call.task)
    return json.dumps(result, default=str)
```

And refactor streaming after Issue #4 provides `Agent.run_stream(...)`:

```python
@expose_route('/agentic_stream', methods=['POST'], stream=True, events={...})
async def agentic_stream(self, task: str, thread_id: int = 0, **kwargs):
  call = self.call_config(task, thread_id=thread_id, **kwargs)
  prepared = await Agent.prepare(self, call)

  async for chunk in Agent.call_stream(prepared, call.task):
    yield chunk
```

### 🧠 Design notes

#### 🗄️ `AgentActor` is a DB-config adapter, not a runtime owner

`AgentActor` should own only DB-backed configuration resolution:

- `self.prompt`
- `self.llm`
- `self.constraints`
- `_resolve_tool_addrs()`
- endpoint compatibility wrappers

Runtime setup and execution should belong to `Agent`.

#### ⚙️ Preserve explicit llm behavior

Class-configured `AgentMixin` calls only forward `llm` when the caller provides
one. `AgentActor` is different: it has an `llm` field, and current code always
passes either `kwargs['llm']` or `self.llm`. Keep that behavior by setting
`has_llm_override=True` on the resolved call.

#### 📦 Keep JSON wrapping here for Phase 1

Issue #6 owns internal result-shape normalization and public contract cleanup.
For Issue #5, keep `AgentActor.agentic()` as a JSON string wrapper around the
same runtime result dict.

### 🧪 Test updates

Existing adapter parity tests that patch descriptor internals should move to the
explicit runtime seam.

Replace this style:

```python
monkeypatch.setattr(AgentMixin.__dict__['run'], 'fn', fake_run)
monkeypatch.setattr(AgentMixin.__dict__['run_stream'], 'fn', fake_run_stream)
```

with this style:

```python
monkeypatch.setattr(Agent, 'prepare', fake_prepare)
monkeypatch.setattr(Agent, 'run', fake_run)
monkeypatch.setattr(Agent, 'run_stream', fake_run_stream)
```

Recommended assertions:

- `actor.py` no longer references `AgentMixin.__dict__['run'].fn`
- `actor.py` no longer references `AgentMixin.__dict__['run_stream'].fn`
- `AgentActor.agentic()` returns a JSON string
- `AgentActor.agentic_stream()` yields chunks
- `Agent.prepare(...)` receives a `CallConfig` with:
  - `prompt == self.prompt`
  - `tools == self._resolve_tool_addrs()`
  - merged constraints
  - `llm == kwargs.get('llm', self.llm)`
  - `has_llm_override is True`
  - `thread_id is None` when input is `0`

### 🪜 Implementation sequence

```text
+------+--------------------------------------------------------------------------+
| Step | Action                                                                   |
+------+--------------------------------------------------------------------------+
|  1   | Confirm Issue #4 landed with `Agent.run_stream(...)`                     |
|  2   | Add `_agent_runtime_call(...)` helper to `AgentActor`                    |
|  3   | Rewire `agentic()` to `Agent.prepare(...)` + `Agent.run(...)`            |
|  4   | Rewire `agentic_stream()` to `Agent.prepare(...)` + `Agent.run_stream()` |
|  5   | Update adapter parity tests to patch the explicit `Agent` seam           |
|  6   | Remove descriptor-bypass docs/comments                                   |
|  7   | Run AgentActor, mixin, and thread tests                                  |
+------+--------------------------------------------------------------------------+
```

### 🧪 Verification

Run AgentActor tests first:

```bash
python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_agent_actor.py -q
```

Then run adjacent runtime tests:

```bash
python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py -q
python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_thread.py -q
```

Then run the full agents suite:

```bash
python3 scripts/test-backend.py --suite agents -- -q
```

### ⚠️ Risks and guardrails

| Risk | Why it matters | Guardrail |
|---|---|---|
| breaking JSON string contract | callers/tests parse the string | keep `json.dumps(result, default=str)` in `agentic()` |
| llm behavior drift | DB-backed agents use `self.llm` as config | use `llm=kwargs.get('llm', self.llm)` and `has_llm_override=True` |
| stream chunk drift | frontend depends on event contract | do not alter `Agent.run_stream()` behavior |
| tool resolution drift | DB tools may be hrefs or models | keep `_resolve_tool_addrs()` as sole tool adapter |
| premature Issue #6 work | public contracts should not change yet | leave result normalization for Issue #6 |

### ✅ Definition of done

- `AgentActor` no longer references `AgentMixin.__dict__['run'].fn`.
- `AgentActor` no longer references `AgentMixin.__dict__['run_stream'].fn`.
- `AgentActor` uses `_agent_runtime_call(...)` to build `CallConfig`.
- `AgentActor.agentic()` uses `Agent.prepare(...)` and `Agent.run(...)`.
- `AgentActor.agentic_stream()` uses `Agent.prepare(...)` and
  `Agent.run_stream(...)`.
- `AgentActor.agentic()` still returns a JSON string.
- AgentActor tests pass.

---

## 🧾 Issue #6 — Normalize sync result shape internally while preserving external contracts

### 🎯 Goal

Make `Agent.run(...)` the single source of truth for sync result shape, while
preserving the public adapter contracts:

```text
+---------------------+
| Agent.run(...)      |
| builds result dict  |
+----------+----------+
           |
           v
+---------------------+
| AgentResult dict    |
+----------+----------+
           |
     +-----+------+
     |            |
     v            v
+-----------+  +----------------+
| AgentMixin|  | AgentActor     |
| returns   |  | json.dumps(...)|
| dict      |  | returns string |
+-----------+  +----------------+
```

This issue should clarify and lock in the internal result boundary without
changing any externally visible behavior.

### 🔎 Current state

`Agent.run(...)` already produces the desired internal result shape:

```python
{
    'answer': result.output,
    'usage': {
        'input_tokens': usage.input_tokens,
        'output_tokens': usage.output_tokens,
        'requests': usage.requests,
    },
    'messages': all_messages,
    'message_count': len(all_messages),
    'thread_id': thread_id,  # when present
}
```

So Issue #6 is intentionally small. It should make this internal shape explicit
and ensure both adapters consume the same result object:

- `AgentMixin.agentic()` returns the Python dict directly.
- `AgentActor.agentic()` serializes that same dict with
  `json.dumps(result, default=str)`.

### 📍 Files likely to change

- `packages/n3tx-agents/src/n3tx_agents/mixin.py`
- `packages/n3tx-agents/src/n3tx_agents/actor.py`
- `packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py`
- `packages/n3tx-agents/src/n3tx_agents/tests/test_agent_actor.py`
- `packages/n3tx-agents/docs/mixin.md`
- `packages/n3tx-agents/docs/agent-actor.md`

### ✅ In scope

| Area | Change |
|---|---|
| internal result shape | ensure `Agent.run(...)` is the only builder of the sync result dict |
| mixin adapter | keep `AgentMixin.agentic()` returning the Python dict directly |
| actor adapter | keep `AgentActor.agentic()` JSON-serializing the same dict |
| tests | pin dict-vs-JSON adapter behavior |
| docs | document the internal result and public adapter contracts |

### 🚫 Out of scope

- changing `AgentActor.agentic()` from JSON string to Python dict
- changing stream result or done chunk shape
- removing `messages` or `message_count`
- changing thread result behavior
- changing endpoint routes or schema metadata
- broad runtime/module reorganization

### 🔒 Compatibility to preserve

| Contract | Required preservation |
|---|---|
| `AgentMixin.agentic()` | returns Python dict |
| `AgentActor.agentic()` | returns JSON string |
| sync result keys | `answer`, `usage`, `messages`, `message_count`, optional `thread_id` |
| `message_count` | equals `len(messages)` |
| thread result | includes `thread_id` when a thread is used/created |
| JSON serialization | uses `json.dumps(result, default=str)` |
| structured output | remains carried in `answer` for mixin path; actor path serializes with `default=str` |

### 🧬 Proposed implementation shape

If `Agent.run(...)` already owns all result construction after Issues #3–#5, the
implementation may only need tests and documentation.

If a tiny helper improves clarity, add one near the internal runtime code:

```python
def _agent_result_dict(result, all_messages: list, thread_id=None) -> dict:
    usage = result.usage()
    result_dict = {
        'answer': result.output,
        'usage': {
            'input_tokens': usage.input_tokens,
            'output_tokens': usage.output_tokens,
            'requests': usage.requests,
        },
        'messages': all_messages,
        'message_count': len(all_messages),
    }
    if thread_id is not None:
        result_dict['thread_id'] = thread_id
    return result_dict
```

Then `Agent.run(...)` becomes:

```python
result = await prepared.ai_agent.call(task, **run_kwargs)
all_messages = result.all_messages()

if prepared.thread_id is not None:
  await _update_thread(...)

return _agent_result_dict(result, all_messages, prepared.thread_id)
```

Only extract this helper if it makes the result boundary clearer. Do not add a
new abstraction just to satisfy the issue if `Agent.run(...)` is already clean.

### 🧠 Design notes

#### 📦 Keep public inconsistency for compatibility

The internal system should normalize on a Python dict, but public adapters still
differ in Phase 1:

```text
AgentMixin.agentic()  -> dict
AgentActor.agentic()  -> JSON string
```

This is intentional. Changing `AgentActor.agentic()` to return a dict is a later
compatibility-breaking cleanup, not part of Phase 1.

#### 🧯 Avoid over-refactoring

This issue is mostly a contract-normalization checkpoint. If after Issue #5 the
code already has one internal result shape, the best implementation may be:

1. add/adjust tests
2. update docs
3. make only small naming/helper changes if needed

#### 🧪 Test public adapter behavior, not private internals

Tests should assert externally visible contracts:

- mixin returns a dict with expected keys
- actor returns a JSON string whose parsed content has the same keys
- `message_count == len(messages)`
- `thread_id` appears when expected

They should not require a specific private helper or dataclass unless such a
helper becomes part of the intended internal contract.

### 🧪 Suggested test coverage

#### 1. `AgentMixin.agentic()` returns normalized Python result

Assert:

- result is a `dict`
- contains `answer`, `usage`, `messages`, `message_count`
- `message_count == len(messages)`

#### 2. `AgentActor.agentic()` serializes same normalized shape

Assert:

- return value is `str`
- `json.loads(result_str)` contains the same normalized keys
- `message_count == len(messages)`

#### 3. Thread id preservation

For a threaded run, assert:

- mixin result includes `thread_id`
- actor JSON payload includes `thread_id`

#### 4. Structured output compatibility

If existing structured-output tests are present, preserve them. If not, avoid
adding broad new structured-output coverage unless it is cheap and stable with
`TestModel`.

### 🪜 Implementation sequence

```text
+------+--------------------------------------------------------------------------+
| Step | Action                                                                   |
+------+--------------------------------------------------------------------------+
|  1   | Confirm Issue #5 landed and AgentActor uses the explicit runtime seam     |
|  2   | Inspect `Agent.run(...)` result construction                              |
|  3   | Extract `_agent_result_dict(...)` only if it improves clarity             |
|  4   | Ensure `AgentMixin.agentic()` returns the result dict unchanged           |
|  5   | Ensure `AgentActor.agentic()` serializes that same result dict            |
|  6   | Add or tighten result-contract tests                                      |
|  7   | Update mixin and AgentActor docs                                          |
|  8   | Run targeted and full agent tests                                         |
+------+--------------------------------------------------------------------------+
```

### 🧪 Verification

Run targeted result-contract suites first:

```bash
python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py -q
python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_agent_actor.py -q
```

Then run the broader agent suite:

```bash
python3 scripts/test-backend.py --suite agents -- -q
```

### ⚠️ Risks and guardrails

| Risk | Why it matters | Guardrail |
|---|---|---|
| breaking JSON string contract | existing callers parse `AgentActor.agentic()` output | keep `json.dumps(..., default=str)` |
| over-refactoring | this issue may already be mostly satisfied after #5 | only extract helper if it reduces duplication/clarifies ownership |
| brittle tests | private helper names may change later | assert public adapter behavior |
| premature API cleanup | changing actor return type is compatibility-sensitive | defer public dict return to later phase |
| dropping `message_count` | tests/docs rely on backward compatibility | preserve `messages` and `message_count` |

### ✅ Definition of done

- `Agent.run(...)` produces one internal Python sync-result shape.
- `AgentMixin.agentic()` returns that Python result directly.
- `AgentActor.agentic()` serializes the same result to JSON.
- External result contracts remain unchanged.
- Result-shape tests pass.
- Docs clearly explain the internal dict vs public JSON wrapper distinction.
