## Problem Statement

The `n3tx_agents` package currently makes it too hard to safely evolve agent behavior because the implementation mixes too many responsibilities in the same places. Runtime orchestration is duplicated between sync and streaming flows, `AgentActor` has to reach into `AgentMixin` internals to reuse execution behavior, and the boundary between policy, runtime assembly, execution, persistence, and transport formatting is blurry.

From the developer's perspective, this creates a system that works but is costly to reason about. Changes that should be local frequently require understanding multiple overlapping code paths. Bug fixes risk drifting between sync and stream behavior. The current structure also makes it harder to test the important behaviors in isolation and harder to extend the package safely in later phases.

The immediate problem to solve is not missing end-user functionality. It is that the current implementation shape creates unnecessary complexity and risk for developers maintaining or extending `n3tx_agents`.

## Solution

Refactor Phase 1 of `n3tx_agents` into a cleaner internal architecture centered around an explicit internal `Agent` runtime abstraction, while preserving current observable behavior.

From the developer's perspective, the new shape should make the execution path obvious:

- `AgentMixin` and `AgentActor` remain the public-facing adapters
- a resolved call object represents the normalized invocation request
- an internal `Agent` abstraction owns runtime preparation and execution
- a prepared runtime bundle represents execution-ready state for one call

Phase 1 should preserve compatibility where current consumers may depend on it, especially:

- `AgentActor.agentic()` continuing to return a JSON string
- current stream chunk names and payload shapes
- current thread semantics and multi-turn behavior
- current config precedence and call semantics

This phase is intentionally internal. The goal is to reduce entropy, eliminate duplicated orchestration, make the policy/engine split real, and create a safer foundation for later refactors.

## User Stories

1. As a framework maintainer, I want a single shared runtime path for sync and streaming agent execution, so that behavior stays consistent and changes only need to be made once.
2. As a framework maintainer, I want `AgentMixin` to delegate runtime work to a dedicated runtime abstraction, so that the mixin stays focused on model-facing behavior.
3. As a framework maintainer, I want `AgentActor` to call an explicit runtime interface instead of descriptor internals, so that the architecture is understandable and less brittle.
4. As a framework maintainer, I want call normalization to happen in one place, so that prompt, tools, constraints, thread settings, and result-type behavior remain consistent across sync and stream entrypoints.
5. As a framework maintainer, I want runtime preparation to happen in one place, so that llm resolution, thread preload, tool discovery, and dependency setup do not drift between execution modes.
6. As a framework maintainer, I want the engine boundary to be explicit, so that policy concerns and execution concerns are not mixed together.
7. As a framework maintainer, I want to preserve current external behavior during this phase, so that refactoring does not unexpectedly break existing clients.
8. As a framework maintainer, I want `AgentActor.agentic()` to keep returning JSON during this phase, so that existing callers that parse string responses continue to work.
9. As a framework maintainer, I want streaming behavior to preserve current chunk ordering and payload shape, so that existing frontend and integration code remains compatible.
10. As a framework maintainer, I want thread creation, loading, and update semantics to remain stable in Phase 1, so that multi-turn behavior is preserved while the runtime is reshaped internally.
11. As a framework maintainer, I want sync and stream paths to share the same resolved call semantics, so that developers do not have to debug different precedence rules for nearly identical operations.
12. As a framework maintainer, I want a per-call prepared runtime object, so that runtime state is explicit, local, and testable.
13. As a framework maintainer, I want to avoid hidden mutable runtime state on models, so that concurrent or repeated calls do not rely on stale per-instance execution state.
14. As a framework maintainer, I want runtime preparation to explicitly own llm override handling and concrete llm resolution, so that this behavior is not split across policy and execution layers.
15. As a framework maintainer, I want the central runtime abstraction to be named clearly, so that developers can easily identify the true owner of execution behavior.
16. As a framework maintainer, I want upstream `pydantic_ai.Agent` usage to remain distinguishable from the package's own runtime abstraction, so that naming does not create confusion in implementation or reviews.
17. As a framework maintainer, I want dedicated tests around the new runtime seam, so that regressions in adapter behavior and execution behavior are caught quickly.
18. As a framework maintainer, I want class-level `agentic_stream()` behavior to remain covered, so that the refactor does not silently break the current class/instance dispatch model.
19. As a framework maintainer, I want `AgentActor.agentic()` and `AgentActor.agentic_stream()` to continue honoring the same config merge semantics, so that DB-backed agents remain predictable after the refactor.
20. As a framework maintainer, I want a single internal Python result shape for successful sync execution, so that adapters can present different external response forms without duplicating execution logic.
21. As a framework maintainer, I want sync execution and stream execution to be owned by the same runtime abstraction, so that future enhancements can build on a single architectural center.
22. As a framework maintainer, I want this phase to defer unrelated cleanup work, so that the refactor remains focused and reviewable.
23. As a future contributor, I want the codebase to expose an obvious path from invocation request to execution result, so that onboarding and debugging require less system-wide context.
24. As a future contributor, I want the runtime seam to be explicit enough that tool policy, thread design, and bootstrap cleanup can be tackled in later phases without first undoing Phase 1 structure.
25. As a reviewer, I want the refactor to proceed in small, behavior-preserving slices, so that the diff remains understandable and trustable.
26. As a test author, I want to verify external behavior rather than implementation details, so that tests remain stable while internal structure improves.
27. As a maintainer planning later refactors, I want `tools.py` cleanup, bootstrap cleanup, and thread redesign clearly deferred, so that the work can be sequenced rather than mixed into this phase.
28. As a framework maintainer, I want `AgentMixin` and `AgentActor` to share a real runtime boundary rather than a conceptual one, so that the code matches the intended architecture.
29. As a framework maintainer, I want duplicated orchestration removed before broader cleanup, so that later refactor phases start from a sounder execution model.
30. As a framework maintainer, I want the package to become easier to extend without changing external behavior first, so that future work can be lower-risk and more deliberate.

## Implementation Decisions

- Phase 1 is an internal refactor, not a user-visible feature phase.
- The central runtime abstraction will be named `Agent`.
- The package's internal `Agent` abstraction is distinct from `pydantic_ai.Agent`; the upstream type should be clearly aliased to avoid confusion.
- `AgentMixin` and `AgentActor` remain the public-facing adapters and should both route into the same runtime abstraction.
- A resolved call object will represent the normalized invocation request before runtime preparation.
- A prepared runtime bundle will represent execution-ready state for a single call.
- The resolved call object will include normalized invocation inputs such as task, prompt, tools, constraints, user context, thread context, create-thread behavior, and result type.
- Concrete llm resolution and llm override handling belong to runtime preparation, not call normalization.
- The runtime abstraction will own sync execution and stream execution.
- Runtime preparation will own root lookup, thread preload/create behavior, tool discovery and wrapping, dependency construction, usage limit construction, and runnable agent construction.
- `AgentActor` will stop reaching into `AgentMixin` descriptor internals.
- `AgentActor` will gain a thin adapter-level helper for converting DB-backed agent configuration into the resolved call shape.
- Sync and stream entrypoints on `AgentMixin` will share the same call-normalization path.
- Sync and stream execution will share the same runtime-preparation path.
- A single internal Python result shape will be used for sync execution results.
- `AgentMixin.agentic()` will continue returning a Python object result.
- `AgentActor.agentic()` will continue returning a JSON string in Phase 1 for compatibility.
- Stream chunk names, ordering expectations, and payload shapes will remain unchanged in Phase 1.
- Existing thread semantics, including current multi-turn behavior and current ownership behavior, will be preserved during this phase.
- This phase intentionally does not redesign tool exposure policy, tool discovery boundaries, thread identity semantics, thread storage format, bootstrap side effects, or overall package/module layout.
- The refactor should be executed in small, reviewable slices beginning with test fences and then moving through call resolution, runtime preparation, runtime execution, adapter cleanup, and internal result normalization.

## Testing Decisions

- Good tests should validate observable behavior and compatibility, not internal implementation details.
- Tests should confirm that sync and stream entrypoints preserve the same externally visible semantics after the refactor.
- Dedicated testing focus in Phase 1 should cover the central `Agent` runtime abstraction and the adapter behavior in `AgentMixin` and `AgentActor`.
- Regression coverage should explicitly pin config cascade parity across sync and stream entrypoints.
- Regression coverage should explicitly pin thread and create-thread behavior across sync and stream paths.
- Regression coverage should explicitly pin `AgentActor` JSON-string wrapper behavior.
- Regression coverage should explicitly pin class-level streaming behavior.
- Regression coverage should explicitly pin stream ordering and first-token behavior.
- Prior art for these tests exists in the package's current mixin, actor, thread, and stream-related test suites.
- Tests should continue to prefer external behavior assertions such as outputs, chunk shapes, result fields, and persisted effects over assertions about internal helper structure.

## Out of Scope

- Changing `AgentActor.agentic()` from JSON string output to a Python object response.
- Redesigning thread ownership or thread identity semantics.
- Changing thread storage format.
- Changing stream event shapes, names, or ordering contracts.
- Splitting `tools.py` or reworking tool exposure policy.
- Deciding or implementing whether `agentic` / `agentic_stream` should be tool-discoverable.
- Bootstrap and import-side-effect cleanup.
- Broader package/module relocation beyond what is necessary to land the Phase 1 runtime seam.
- User-visible product behavior changes.

## Further Notes

- The purpose of this PRD is to define the first execution-focused refactor wave, not the full end-state cleanup of the `n3tx_agents` package.
- The broader refactor roadmap and audit findings should continue to guide later phases, especially around tools, threads, bootstrap behavior, and package boundaries.
- This phase should optimize for architectural clarity without sacrificing compatibility.
- The success condition for Phase 1 is that the code becomes easier to reason about and safer to extend, while tests continue to validate the same external behavior.
