---
name: improve-n3tx-alignement
description: Improve codebase architecture by aligning it with N3TX patterns, primitives, architecture, intent, and philosophy. Use when the user wants N3TX-oriented architecture review, refactoring opportunities, framework-aligned simplification, or asks to improve N3TX alignment.
---

# Improve N3TX Alignement

Explore a codebase through the lens of N3TX architecture, surface places where the implementation fights or bypasses the framework, and propose refactors that make the system more aligned with N3TX patterns, primitives, intent, and philosophy.

This skill is inspired by `improve-codebase-architecture`, but the improvement target is more specific: **make the codebase feel like an idiomatic N3TX system rather than an application that merely happens to run on top of N3TX**.

The goal of N3TX is to provide patterns and primitives that **simplify systems and improve maintainability**. Treat N3TX alignment as a simplification exercise first: prefer removing duplicated concepts, bespoke glue, local mini-frameworks, and accidental complexity over adding new layers. In most good N3TX refactors, the net result should be **less code, fewer concepts, and clearer ownership**.

## North Star

Prefer architecture that is:

- **N3TX-native**: behavior is expressed through N3TX primitives instead of parallel custom mechanisms.
- **Declarative where possible**: intent is captured in stable definitions, metadata, schemas, routes, methods, resources, or framework-owned registration points.
- **Composable**: application behavior emerges from small N3TX-aligned parts rather than bespoke one-off flows.
- **Boundary-oriented**: modules expose intent and hide incidental mechanics.
- **Convention-friendly**: new code follows the framework's established file shapes, lifecycle, naming, and extension points.
- **Testable at the right boundary**: tests validate N3TX-visible behavior rather than internal glue.
- **Removal-first**: remove more than you add whenever possible; use N3TX primitives to collapse bespoke code paths.
- **Entropy-reducing**: refactors remove duplicate concepts, local mini-frameworks, and accidental divergence from N3TX's mental model.

## Process

### 1. Explore the codebase

Use the Agent tool with `subagent_type=explore` to navigate the codebase naturally. Do not follow rigid heuristics — explore organically and note where the system feels less N3TX-native than it could be.

Look for friction such as:

- Where does application code recreate behavior that N3TX already has a primitive for?
- Where are routes, methods, resources, schemas, forms, metadata, permissions, discovery, lifecycle hooks, or UI integration handled by ad hoc glue?
- Where does caller code need to know too much about framework internals or implementation details?
- Where do modules expose mechanics instead of N3TX-level intent?
- Where is configuration duplicated across Python, frontend assets, schemas, tests, or docs?
- Where are naming, registration, discovery, or lifecycle patterns inconsistent with nearby N3TX modules?
- Where do tests assert local implementation details instead of externally observable N3TX behavior?
- Where would a new contributor familiar with N3TX expect a concept to live somewhere else?

The friction you encounter is the signal. Treat repeated confusion, code bouncing, local conventions, and duplicated framework concepts as architectural evidence.

### 2. Identify N3TX alignment candidates

Present a numbered list of improvement candidates. This section must be **fairly detailed**; it should be useful enough for the user to compare candidate refactor directions without needing to inspect the code immediately.

For each candidate, include:

1. **Candidate title**: A concise name for the alignment opportunity.
2. **Current shape**: The modules, files, concepts, and execution paths involved.
3. **Observed friction**: What felt hard to understand, test, extend, or reason about.
4. **N3TX misalignment**: Which N3TX pattern, primitive, architectural intent, or philosophy the current shape appears to fight, bypass, duplicate, or underuse.
5. **Motive for change**: Why this matters now — maintainability, extensibility, correctness, testability, user experience, contributor onboarding, or framework coherence.
6. **Improvement options**: Present 2-3 plausible directions, such as:
   - adopt an existing N3TX primitive directly
   - move behavior behind a N3TX-owned boundary
   - consolidate duplicated definitions into a single source of truth
   - replace imperative glue with declarative registration or metadata
   - introduce a thin adapter around non-N3TX concerns
   - deepen a module so callers speak in N3TX concepts
   - delete a custom abstraction because a N3TX primitive already expresses the intent
7. **Recommended direction**: Choose the strongest option and explain why.
8. **Why this is a good N3TX approach**: Explain how the recommendation improves alignment with N3TX's architecture, primitives, and philosophy.
9. **Work overview**: Summarize the concrete work required to move in that direction:
   - files or modules likely to change
   - new or changed interfaces
   - migration sequence
   - tests to add, rewrite, or delete
   - documentation or examples to update
   - compatibility or rollout concerns
10. **Expected outcome**: What becomes simpler, more declarative, more composable, or more framework-native after the change.
11. **Risk / uncertainty**: Any unknowns that need confirmation before implementation.

When comparing options, strongly prefer the path that removes the most accidental complexity while preserving behavior. Adding a new abstraction is only a good N3TX alignment move when it lets the system delete more scattered logic, duplicated definitions, or caller knowledge elsewhere.

Use this compact format when helpful:

```markdown
### Candidate N: <title>

**Current shape**
- ...

**Observed friction**
- ...

**N3TX misalignment**
- ...

**Motive for change**
- ...

**Improvement options**
| Option | Shape | Pros | Trade-offs |
|---|---|---|---|
| A | ... | ... | ... |
| B | ... | ... | ... |

**Recommended direction**
- ...

**Why this is a good N3TX approach**
- ...

**Work overview**
1. ...
2. ...
3. ...

**Expected outcome**
- ...

**Risk / uncertainty**
- ...
```

After presenting candidates, ask the user: **"Which N3TX alignment candidate would you like to explore?"**

Do not design the final interface or implementation plan yet. The candidate section should be detailed, but still directional.

### 3. User picks a candidate

When the user selects a candidate, restate the selected problem in N3TX terms:

- Which N3TX concepts are involved?
- What is currently misaligned?
- What should become the framework-native source of truth?
- Which callers, tests, and docs are likely affected?

### 4. Frame the problem space

Before spawning sub-agents or proposing a final shape, write a user-facing explanation of the selected candidate:

- The N3TX philosophy or primitive the refactor should align with.
- The constraints any new interface or module shape must satisfy.
- The dependencies it needs to rely on or hide.
- A rough illustrative code sketch to ground the constraints. This is not a proposal; it is only a way to make the problem concrete.
- A compact work map showing likely implementation phases.

Show this to the user, then proceed to Step 5. The user can read and think while the sub-agents work in parallel.

### 5. Design multiple N3TX-aligned approaches

Spawn 3+ sub-agents in parallel using the Agent tool. Each must produce a meaningfully different N3TX-aligned approach for the selected refactor.

Prompt each sub-agent with a technical brief containing:

- relevant file paths and execution paths
- the current non-idiomatic shape
- the N3TX primitives, conventions, or philosophy involved
- what complexity should be hidden
- what must remain stable for callers
- test and migration constraints

Give each agent a different design constraint:

- Agent 1: **Maximize N3TX idiomaticity** — use existing framework primitives as directly as possible.
- Agent 2: **Minimize migration risk** — preserve call sites and introduce alignment incrementally.
- Agent 3: **Maximize declarative clarity** — move behavior into schemas, metadata, registration, or definitions where appropriate.
- Agent 4, if applicable: **Optimize for extension** — create a composable N3TX-native seam for future features.

Each sub-agent outputs:

1. Proposed architecture or interface shape.
2. Usage example showing how N3TX-facing callers would use it.
3. What N3TX primitive or philosophy it aligns with.
4. What complexity it hides or removes.
5. Migration path.
6. Test strategy.
7. Trade-offs and risks.

Present the designs sequentially, then compare them in prose.

After comparing, give your own recommendation. Be opinionated: choose the design that best improves N3TX alignment while keeping the implementation practical. If elements from different designs combine well, propose a hybrid.

### 6. User picks an approach

If the user accepts the recommendation or chooses an approach, produce a concrete refactor RFC or implementation plan.

The plan should include:

- problem statement
- N3TX alignment goal
- proposed architecture
- affected files and modules
- migration sequence
- compatibility notes
- testing strategy
- risks and open questions
- small, reviewable implementation steps

If the user asks for implementation, follow the build agent workflow: present an implementation overview, wait for validation, implement in small steps, show diffs, and verify.

## Evaluation Lens

When judging whether a change is truly N3TX-aligned, ask:

- Does it make the framework's intended mental model more visible?
- Does it remove application-specific reinventions of N3TX behavior?
- Does it remove more code, concepts, or special cases than it adds?
- Does it reduce the number of places a concept must be updated?
- Does it make common N3TX use cases easier while keeping advanced cases possible?
- Does it make behavior discoverable through normal N3TX entry points?
- Does it preserve or improve compatibility for existing callers?
- Does it shift tests toward stable behavior boundaries?
- Does it make future features easier to express in N3TX terms?

## Anti-Patterns to Watch For

- Local mini-frameworks that duplicate N3TX primitives.
- Imperative orchestration where declarative registration would be clearer.
- Repeated metadata, schema, or configuration definitions across layers.
- Callers reaching through N3TX abstractions into implementation details.
- Tests coupled to internals that should be hidden by a N3TX boundary.
- Feature code that bypasses discovery, lifecycle, routing, or resource conventions.
- Naming or file placement that makes N3TX concepts hard to recognize.
- Adapters that leak external service details into N3TX-facing modules.

## Output Style

Use concise, structured, high-signal engineering artifacts:

- Lead with the strongest candidate or recommendation when one is clear.
- Use compact tables for improvement options and trade-offs.
- Include ASCII flow diagrams when they clarify ownership or migration.
- Separate evidence from inference.
- Say what is unknown rather than pretending certainty.
- Keep proposals grounded in actual files, call paths, and tests.
