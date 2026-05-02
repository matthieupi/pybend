## ✅ Verdict

`n3tx_agents` has a strong core idea, but the implementation carries too much mixed responsibility, duplicated orchestration, and boundary leakage.

The right refactor is not a rewrite. It is a **shape correction**:

- one shared runtime core
- thin adapters at the edges
- fewer internal representations
- clearer ownership boundaries
- preserved behavior where compatibility matters

---

# 📍 What was reviewed

Primary modules:

- `src/n3tx_agents/mixin.py`
- `src/n3tx_agents/actor.py`
- `src/n3tx_agents/tools.py`
- `src/n3tx_agents/thread.py`
- `src/n3tx_agents/schema_ext.py`
- `src/n3tx_agents/app_agent.py`
- `src/n3tx_agents/deps.py`

Supporting behavior checks:

- `src/n3tx_agents/tests/test_mixin.py`
- `src/n3tx_agents/tests/test_agent_actor.py`
- `src/n3tx_agents/tests/test_tools.py`
- `src/n3tx_agents/tests/test_thread.py`

---

# 🧭 Executive summary

## Main diagnosis

The package currently has three dominant structural problems:

1. **Runtime orchestration is duplicated** across sync and stream paths.
2. **Abstractions are incomplete**: `AgentActor` is forced to reach into mixin internals.
3. **Subsystem boundaries are blurry**: runtime, persistence, tools, schema policy, and transport concerns leak into each other.

## Default recommendation

Refactor around this core flow:

```text
adapter -> resolve config -> prepare runtime -> execute -> persist -> format response
```

with:

```text
AgentMixin   -> resolves config -> AgentRuntime
AgentActor   -> resolves config -> AgentRuntime
AgentRuntime -> executes and persists
```

## Important compatibility note

Some awkward behavior should be **preserved first, simplified later**, especially:

- stream chunk shapes
- thread behavior
- `AgentActor.agentic()` JSON-string contract, if callers rely on it

---

# 📊 Problem map

| Area | Main issue | Impact | Recommended direction | Status |
|---|---|---:|---|---|
| `mixin.py` | god module | High | split by ownership | planned |
| sync/stream runtime | duplicated setup | High | shared runtime preparation | **phase 1 in progress** |
| `AgentActor` | brittle descriptor bypass | High | thin adapter over explicit runtime | planned |
| tools | discovery/invocation/factory mixed | High | split tool subsystem | planned |
| threads | persistence mixed into runtime | High | extract conversation store boundary | planned |
| schema/tool policy | duplicated filtering rules | Medium | centralize exposure policy | planned |
| bootstrap/imports | side-effect heavy package init | Medium | explicit bootstrap | planned |
| API contracts | inconsistent return shapes | Medium | normalize internally, preserve compatibility carefully | **phase 1 in progress** |

---

# 🔎 Comprehensive findings

## 1) `mixin.py` is a god module

### Problem
`mixin.py` owns too many unrelated concerns:

- LLM resolution (`_resolve_llm`, lines 76–106)
- prompt/context generation (`_build_schema_text`, `_build_instance_text`, lines 110–140)
- thread lifecycle (`_get_thread`, `_create_thread`, `_load_or_create_thread`, `_update_thread`, lines 159–237)
- policy/config resolution (`agentic`, lines 318–365)
- sync execution (`run`, lines 368–503)
- stream execution (`run_stream`, lines 544–756)

### Why it matters
This is the package’s entropy center. Too much system context is required to safely change any one behavior.

### Evidence
- `src/n3tx_agents/mixin.py:76–237`
- `src/n3tx_agents/mixin.py:318–756`

### Possible solution
Split ownership into deeper modules:

- `runtime/config.py`
- `runtime/context.py`
- `runtime/runner.py`
- `runtime/history.py`
- `runtime/streaming.py`

Keep `AgentMixin` as a thin facade.

---

## 2) The advertised “policy vs engine” split is only partial  _(Phase 1: in progress)_

### Problem
The code and docs describe:

- `agentic()` as policy
- `run()` as engine

But `run()` still performs policy-adjacent orchestration:

- resolves llm from config
- resolves agent address
- couples directly to Matrix root
- loads and validates threads
- discovers tools
- creates Pydantic AI tools
- builds usage limits

### Why it matters
The current abstraction boundary is misleading. The engine is not fully resolved input + execution; it is still doing upstream orchestration work.

### Evidence
- `src/n3tx_agents/mixin.py:368–489`
- `src/n3tx_agents/mixin.py:545–726`

### Possible solution
Introduce one canonical resolved runtime input, e.g. `ResolvedAgentConfig`, and move `run()` onto that shape.

Target flow:

```text
adapter -> resolve config -> build runtime context -> execute -> persist -> format result
```

---

## 3) `run()` and `run_stream()` duplicate too much logic  _(Phase 1: in progress)_

### Problem
Both paths repeat nearly the same setup:

- resolve llm
- get Matrix root
- load/create thread
- discover tools
- create `Tool` objects
- create `AgentDeps`
- apply usage limits

### Why it matters
This creates drift risk and makes the real runtime shape hard to see.

### Evidence
- `run`: `src/n3tx_agents/mixin.py:402–489`
- `run_stream`: `src/n3tx_agents/mixin.py:566–726`

### Possible solution
Extract a shared runtime builder such as `_prepare_runtime(...)` returning:

- `llm`
- `root`
- `thread_id`
- `message_history`
- `ai_agent`
- `deps`
- `usage_limits`

Then:

- `run()` handles terminal completion only
- `run_stream()` handles streaming/event translation only

---

## 4) `agentic()` and `agentic_stream()` duplicate config cascade logic  _(Phase 1: in progress)_

### Problem
Both methods separately resolve:

- prompt
- tools
- constraints
- user
- thread_id
- create_thread
- result_type
- llm override

### Why it matters
This duplicates public policy logic and makes option behavior harder to evolve safely.

### Evidence
- `src/n3tx_agents/mixin.py:334–365`
- `src/n3tx_agents/mixin.py:512–541`

### Possible solution
Extract one `_resolve_agent_call_config(target, kwargs)` helper or equivalent `AgentCallConfig` object.

---

## 5) `AgentActor` is not a clean peer abstraction

### Problem
`AgentActor.agentic()` and `agentic_stream()` bypass normal dispatch and call underlying mixin functions directly:

- `AgentMixin.__dict__['run'].fn`
- `AgentMixin.__dict__['run_stream'].fn`

### Why it matters
This is both brittle and revealing: the abstraction line is wrong if callers need descriptor internals to reach the actual engine.

### Evidence
- `src/n3tx_agents/actor.py:156–172`
- `src/n3tx_agents/actor.py:194–208`

### Possible solution
Make both `AgentMixin` and `AgentActor` thin adapters over the same explicit runtime service.

---

## 6) `AgentActor` duplicates bridge logic twice  _(Phase 1: in progress)_

### Problem
Both `agentic()` and `agentic_stream()` in `AgentActor` repeat:

- tool resolution from join refs
- constraints merge
- prompt/llm selection
- user/thread/result_type forwarding
- mixin-engine bridging

### Why it matters
This is duplicated adapter logic layered on top of duplicated runtime logic.

### Evidence
- `src/n3tx_agents/actor.py:140–172`
- `src/n3tx_agents/actor.py:174–208`

### Possible solution
Add one internal helper that converts an `AgentActor` instance into canonical runtime config.

---

## 7) Two configuration systems exist, but no canonical internal representation does

### Problem
There are two agent-definition modes:

1. class-based config via `__agent__`
2. DB-based config via `AgentActor` fields

But there is no single internal representation of a resolved agent call.

### Why it matters
This creates repeated branching around:

- where prompt comes from
- where tools come from
- which llm wins
- how constraints merge

### Evidence
- `src/n3tx_agents/mixin.py:334–365`
- `src/n3tx_agents/actor.py:68–208`

### Possible solution
Introduce a canonical internal object:

```python
ResolvedAgentConfig(
    prompt,
    llm,
    tool_addrs,
    constraints,
    result_type,
    agent_addr,
)
```

---

## 8) Public return contracts are inconsistent  _(Phase 1: in progress)_

### Problem

- `AgentMixin.agentic()` returns a Python `dict`
- `AgentActor.agentic()` returns a JSON `str`

### Why it matters
This is unnecessary API inconsistency and mixes transport serialization into domain logic.

### Evidence
- `src/n3tx_agents/mixin.py:491–503`
- `src/n3tx_agents/actor.py:141–172`
- `src/n3tx_agents/tests/test_agent_actor.py:264–268`

### Possible solution
Normalize on Python objects internally. Let HTTP/transport code serialize.

### Compatibility note
This is likely a **phase-2 cleanup**, not the first move.

---

## 9) Streaming event models live in the wrong module

### Problem
`TextChunk`, `ToolCallEvent`, `ToolResultEvent`, `ThinkingChunk`, and `DoneChunk` are defined in `actor.py`.

### Why it matters
These describe runtime stream protocol, not the DB-backed `AgentActor` model itself.

### Evidence
- `src/n3tx_agents/actor.py:39–67`

### Possible solution
Move them to `models/stream_events.py` or `runtime/streaming.py`.

---

## 10) Tool discovery depends on Matrix private internals

### Problem
`discover_tools()` reads:

- `root._children`
- `root.__children__`

### Why it matters
This leaks framework internals into the tool subsystem and makes tests more awkward.

### Evidence
- `src/n3tx_agents/tools.py:61`
- `src/n3tx_agents/tests/test_tools.py:436–439`

### Possible solution
Depend on a public registry interface, or wrap lookup behind a package-owned resolver.

---

## 11) Tool discovery likely has a stale exclusion mismatch for agent endpoints  ← missed finding added

### Problem
`discover_tools()` excludes `{'run', 'stream_run'}` for `AgentActor` subclasses.

But the public agent-facing endpoints are:

- `agentic`
- `agentic_stream`

### Why it matters
This suggests one of two problems:

1. the exclusion rule was written against older names and is now stale, or
2. agent endpoints are currently discoverable as tools when they should not be

That can create recursion, confusing agent-to-agent delegation, or accidental tool exposure.

### Evidence
- exclusion set: `src/n3tx_agents/tools.py:92–99`
- public methods: `src/n3tx_agents/actor.py:140–208`

### Possible solution
Make this an explicit design decision:

| Decision | Default recommendation |
|---|---|
| Should agent endpoints be tool-discoverable? | **No, not by default** |

If agent-to-agent delegation is desired later, it should be an intentional feature with explicit policy, not an accidental consequence of schema exposure.

---

## 12) `tools.py` mixes too many responsibilities

### Problem
`tools.py` currently owns:

- discovery
- CRUD tool synthesis
- method tool synthesis
- TX routing
- dynamic function generation
- Pydantic `Tool` wrapping

### Why it matters
This module has too many reasons to change.

### Evidence
- `src/n3tx_agents/tools.py:43–313`

### Possible solution
Split into:

- `tools/types.py`
- `tools/discovery.py`
- `tools/specs.py`
- `tools/invocation.py`
- `tools/factory.py`

---

## 13) Tool visibility rules are split across modules

### Problem
Tool exposure and schema cleaning are governed in multiple places:

- writable CRUD field filtering in `tools.py`
- method `user` param stripping in `tools.py`
- hidden/protected field removal in `schema_ext.py`
- LLM schema cleanup in `schema_ext.py`

### Why it matters
This invites policy drift.

### Evidence
- `src/n3tx_agents/tools.py:104–196`
- `src/n3tx_agents/schema_ext.py:63–97`

### Possible solution
Centralize tool-visible schema policy and have both discovery and schema export reuse it.

---

## 14) Tool references have too many internal shapes

### Problem
Tool refs currently appear as:

- `AgentTool` instances
- href strings
- plain actor addr strings
- app-agent tool dicts containing `target`

### Why it matters
Flexible edge inputs are fine, but internal runtime code should not need to recover from multiple formats everywhere.

### Evidence
- `src/n3tx_agents/actor.py:99–138`
- `src/n3tx_agents/app_agent.py:117–119`

### Possible solution
Normalize immediately to one internal form: `list[str]` actor addresses.

---

## 15) `AgentDeps.agent_addr` is documented as meaningful, but not actually used correctly

### Problem
`AgentDeps` says `agent_addr` is for `TX.source`, but tool calls actually use `root.addr` as source.

### Why it matters
This is a documentation/implementation mismatch and a sign of a leaky boundary.

### Evidence
- `src/n3tx_agents/deps.py:21–22`
- `src/n3tx_agents/tools.py:209–217`

### Possible solution
Either:

- actually use `ctx.deps.agent_addr` as the tool-call source, or
- remove the field if it is not meaningful

Prefer the first if source identity matters.

---

## 16) Thread persistence is too tightly coupled to runtime orchestration

### Problem
Thread load/create/validate/update all happen inside the runtime path.

### Why it matters
Conversation persistence is a real subsystem, but it currently has no dedicated owner.

### Evidence
- `src/n3tx_agents/mixin.py:159–237`
- `src/n3tx_agents/mixin.py:426–489`
- `src/n3tx_agents/mixin.py:591–726`

### Possible solution
Extract a `ConversationStore` / `ThreadStore` boundary that owns:

- load
- create
- validate ownership
- serialize/deserialize history
- persist transcript

---

## 17) Thread ownership semantics are ambiguous

### Problem
Threads may belong to:

- a specific agent instance address (`simple_agents/1`)
- or only a scope (`simple_agents`)

and the matching logic accepts both.

### Why it matters
This weakens invariants and makes multi-turn ownership semantics harder to reason about.

### Evidence
- `_thread_matches_agent`: `src/n3tx_agents/mixin.py:151–157`
- `_create_thread`: `src/n3tx_agents/mixin.py:174–193`
- tests rely on both: `src/n3tx_agents/tests/test_thread.py:250`, `281`, `366`, `411`

### Possible solution
Choose one canonical ownership model for new writes, while keeping compatibility readers if needed.

---

## 18) `Thread.from_history()` loses directional fidelity

### Problem
It wraps every persisted message with the same `source` and `target`.

### Why it matters
This turns live conversation direction into synthetic storage envelopes.

### Evidence
- `src/n3tx_agents/thread.py:75–103`
- callers pass fixed values: `src/n3tx_agents/mixin.py:482–489`, `719–726`

### Possible solution
Either:

- store raw model messages only, or
- define a clearer transcript-storage format that distinguishes metadata from live TX envelopes

---

## 19) Class-level `agentic_stream()` assumes zero-argument construction

### Problem
When called on a class, `agentic_stream()` does `instance = target()`.

### Why it matters
This silently assumes zero-arg instantiation and may fail on legitimate models with required constructor args.

### Evidence
- `src/n3tx_agents/mixin.py:527–530`

### Possible solution
Avoid implicit instance construction; either support class targets directly or make instance context explicit.

---

## 20) Prompt/context generation is simplistic and partly ad hoc

### Problem
`_build_instance_text()` truncates field values over 200 chars, with an in-code note that this policy needs review.

### Why it matters
This is important LLM-context behavior hiding as a local heuristic.

### Evidence
- `src/n3tx_agents/mixin.py:125–132`

### Possible solution
Move prompt/context shaping into its own module with explicit policies:

- max field length
- field inclusion rules
- summarization strategy for long values

---

## 21) Schema extension relies on import-time side effects

### Problem
Importing the package:

- registers the mixin
- imports `schema_ext` for side effects
- registers llm pipeline stages

### Why it matters
This creates hidden global mutation and startup-order coupling.

### Evidence
- `src/n3tx_agents/__init__.py:16–28`
- `src/n3tx_agents/schema_ext.py:100–101`

### Possible solution
Move bootstrapping into an explicit `bootstrap.py` or `register_agents()` function.

---

## 22) `__init__.py` mixes exports with global registration behavior

### Problem
The package root currently acts as both:

- public API
- initialization routine
- side-effect loader

### Why it matters
That makes imports heavier and less predictable.

### Evidence
- `src/n3tx_agents/__init__.py:14–28`

### Possible solution
Make `__init__.py` export-only and move registration into explicit bootstrap code.

---

## 23) Docs/comments mismatches weaken trust in the codebase

### Problem
Several comments/docs disagree with implementation:

- `__init__.py` mentions `agent_run()` but real API is `agentic()` / `run()`
- `actor.py` example comment says `{"addr": "grants"}` while the model uses `target`
- `AgentDeps.agent_addr` doc mismatches actual behavior
- `AgentActor.agentic()` returns JSON string, unlike the mixin dict contract

### Why it matters
This is not just polish; drift in docs usually means the conceptual boundaries are already unstable.

### Evidence
- `src/n3tx_agents/__init__.py:8`
- `src/n3tx_agents/actor.py:15`
- `src/n3tx_agents/deps.py:21–22`

### Possible solution
Reconcile docs after the internal boundaries are reshaped.

---

## 24) The tool invocation layer returns JSON strings too early

### Problem
`_route_tool_call()` always returns `json.dumps(response.data, default=str)`.

### Why it matters
This collapses structured tool results into text too early in the pipeline.

### Evidence
- `src/n3tx_agents/tools.py:201–223`

### Possible solution
Keep structured results internally longer and stringify only at the LLM-facing boundary.

---

## 25) Too much behavior is hidden in clever machinery instead of stable interfaces

### Problem
The package relies on several clever mechanisms at once:

- descriptor internals (`.fn`)
- `exec()`-generated functions
- private actor registry structures
- implicit side-effect registration

### Why it matters
Any one of these may be defensible. Together, they raise the cognitive load too much.

### Evidence
- `src/n3tx_agents/actor.py:160`, `196`
- `src/n3tx_agents/tools.py:225–296`
- `src/n3tx_agents/tools.py:61`
- `src/n3tx_agents/__init__.py:16–28`

### Possible solution
Keep dynamic tool signatures if they are required, but simplify the rest of the system so “cleverness” is concentrated in one place.

---

## 26) The package surface is broader than the conceptual core

### Problem
The package exports:

- mixin
- actor
- tool model
- deps
- tool primitives
- thread
- provisioning
- schema side effects via import

### Why it matters
The conceptual center is “agent runtime on top of actors,” but the public surface exposes too many internal pieces without clear layering.

### Evidence
- `src/n3tx_agents/__init__.py:20–35`

### Possible solution
Reclassify modules into:

- public API
- framework integration
- internal runtime

and export fewer internal details by default.

---

# ✅ What should stay

These parts are worth preserving:

- the core package idea: **agents as actor-native reasoning surfaces**
- `ToolSpec` as an intermediate concept
- schema-driven tool discovery
- thread persistence as a plain model rather than a large manager abstraction
- support for both class-configured agents and DB-backed agents
- streaming support and its tested event contract

This is not a rewrite recommendation. It is a **deep reshape around a good core**.

---

# 🗺️ Recommended target shape

```text
n3tx_agents/
  __init__.py
  bootstrap.py

  mixins.py
  deps.py

  models/
    agent.py
    tool_ref.py
    thread.py
    stream_events.py

  runtime/
    config.py
    context.py
    runner.py
    history.py
    streaming.py

  tools/
    types.py
    discovery.py
    specs.py
    invocation.py
    factory.py

  schema.py
  provisioning.py
```

---

# 📌 Priority order

## P0 — highest leverage

1. Split `mixin.py`
2. Unify runtime setup for `run()` and `run_stream()`  **(Phase 1: in progress)**
3. Introduce canonical `ResolvedAgentConfig`  **(Phase 1: in progress)**
4. Remove `AgentActor` reach-in to mixin internals
5. Decide whether agent endpoints should ever be tool-discoverable

## P1

6. Normalize return contracts internally  **(Phase 1: in progress)**
7. Split `tools.py`
8. Extract `ThreadStore` / conversation persistence module
9. Normalize tool references

### Current implementation note

Phase 1 planning is complete and currently targets findings **2, 3, 4, 6, and 8**.

Use this audit together with:

- `.project/refactor/2-agents/1-ntx-agent-phase-1-runtime-refactor-plan.md` for execution order
- `.project/refactor/2-agents/0-ntx-agent-deep-refactor-plan.md` for the broader roadmap

## P2

10. Clean up schema/tool visibility policy
11. Remove import-time side effects from `__init__.py`
12. Move stream event models out of `actor.py`
13. Reconcile docs/comments

---

# 📋 Key decisions to make explicitly

| Decision | Why it matters | Default recommendation |
|---|---|---|
| Should agent endpoints be tool-discoverable? | recursion / delegation semantics | No, not by default |
| Should `AgentActor.agentic()` keep returning JSON? | compatibility vs API coherence | preserve first, normalize later |
| Should thread identity remain dual-mode? | multi-turn ownership semantics | preserve first, simplify later |

---

# ✨ Simplest high-value direction

If there is one principle to drive the refactor, it is this:

> **Make runtime explicit, then make adapters thin.**

Concretely:

```text
AgentMixin   -> resolves config -> AgentRuntime
AgentActor   -> resolves config -> AgentRuntime
AgentRuntime -> executes and persists
```

That one decision collapses most of the current duplication.

---

# Next useful follow-up

Best next artifact:

1. a phased implementation plan
2. a problem tracker table with severity / files / PR order
3. a merged design note combining this audit with the execution slices from the existing plan

Default recommendation: **produce the merged design + execution note next**.
