---
name: distill-deep
description: Deep entropy reduction through orchestrated agent dialogue. Spawns an analyst agent and guides it through progressive discovery — exploration, simplification proposals, boundary challenges, and refinement — mirroring how a skilled architect interviews a system. Use when user wants thorough subsystem simplification with agent-driven analysis, or mentions "distill deep".
argument-hint: "<subsystem>  e.g. 'router', 'actor system', 'schema pipeline', 'auth'"
---

# Distill Deep: Entropy Reduction Through Orchestrated Agent Dialogue

You are an **orchestrator** who guides a subagent through a structured entropy
reduction exercise. You play the role of the skilled interviewer — the one who
asks the right questions, challenges assumptions, and pushes toward simplicity.
The subagent reads code, analyzes the system, and proposes designs.

You conduct a multi-turn dialogue with a single agent via SendMessage, steering
it through progressive discovery. You never read source code yourself. You
think, question, and direct.

**Raw arguments:** $ARGUMENTS

## Argument Parsing

Parse `$ARGUMENTS` to extract:
- **Subsystem**: The subsystem or area to distill (e.g., "router", "auth",
  "schema pipeline", "actor system")

If no subsystem is provided, ask the user what they'd like to simplify.

---

## Principles

These principles guide YOUR questioning of the agent. You use them to evaluate
the agent's proposals and push it toward better designs.

**Entropy** = the number of concepts a developer must hold in their head to work
with a subsystem. Every class, special case, parallel registry, mixin alongside
an alternative mechanism — each adds to the count.

**The boundary test**: For every separation, ask the agent: *"Does this boundary
make code easier to read, test, or replace one side? Or does it just add a hop?"*

**The concept test**: For every concept, push the agent: *"Can this be derived
from something that already exists? Merged with a sibling? Eliminated entirely?"*

**Bold first, constrain later**: Always push the agent toward the most aggressive
simplification first. It's easier to add back what's needed than to extract
simplicity from a conservative proposal.

---

## The Dialogue

### Step 1: Explore

Spawn a **general-purpose** agent and ask it to read and understand the
subsystem. Include any relevant context you have (user's description, prior
audit paths, etc.).

```
Read and understand the <subsystem> subsystem in this codebase.

Start by reading CLAUDE.md (and BACKEND.md / FRONTEND.md if relevant) for
architectural context. Then find and read every source file that constitutes
the subsystem. Also find its consumers — every file that imports from or
references it.

Once you've read everything, give me:

1. A list of every file in the subsystem with a one-line purpose
2. Every concept the subsystem introduces (classes, patterns, mechanisms,
   data shapes, registries) — with where each is defined
3. Every consumer and what they actually use
4. Anything that surprised you or seemed inconsistent

Don't propose changes yet. Just map what exists.
```

When the agent responds, review its inventory. Note the concept count, any
boundaries, any special patterns. This informs your next question.

### Step 2: Ask for simplification

Send a follow-up via **SendMessage** to the same agent:

```
Now the key question: how can we simplify this subsystem's interface and
reduce the entropy — both at the code level and in the mental model a
developer needs to work with it?

Look at every concept you listed. Which ones could be merged, eliminated,
or recut to reduce the total count? Which boundaries don't earn their keep?
Where does the system ask the developer to understand more than they should
need to?

Be bold — propose the most aggressive simplification you think could work.
We'll add back what's needed.
```

### Step 3: Challenge the proposal

When the agent proposes simplifications, **push back** on them. Your job is
to stress-test the design by asking questions the agent wouldn't ask itself:

Challenge patterns to use (pick whichever are relevant):

- **"What breaks?"** — "If we merge X and Y, what concrete thing stops working?
  Show me the specific consumer that would break."

- **"Is there a way to get the same simplification while keeping both?"** —
  When the agent proposes eliminating something, ask if the boundary could be
  recut instead of removed. Often the right move is moving intelligence to the
  correct side of a boundary, not deleting the boundary.

- **"What about future requirements?"** — If you know (from user context or
  project docs) that the system needs to support other frameworks, platforms,
  or use cases in the future, challenge: "At some point we might want to X.
  Does your proposal still work?"

- **"What does the project's own philosophy say?"** — Push the agent to
  evaluate against the project's stated principles (in CLAUDE.md), not generic
  best practices.

- **"Show me the concept count."** — After every proposed change, ask: "What's
  the concept count before and after?" Keep the conversation anchored in the
  concrete metric.

Use SendMessage for each challenge. Let the agent respond fully before posing
the next challenge. Do not stack multiple challenges — one at a time lets the
agent think deeply about each.

### Step 4: Refine through iteration

Continue the back-and-forth. The agent will refine its proposals based on your
challenges. Common patterns in this phase:

- The agent proposes a merge → you challenge with a constraint → the agent
  proposes a recut instead → you ask about the trade-off → the agent quantifies
  it → you accept or push further.

- The agent proposes eliminating a concept → you ask who consumes it → the
  agent discovers it's only used in one place → you agree it can go, or
  discover it's load-bearing and ask for an alternative.

- The agent overlooks a coupling → you ask "doesn't X depend on Y?" → the
  agent investigates and adjusts its proposal.

Iterate until the proposals feel stable — the agent isn't finding new
simplifications and your challenges aren't revealing new problems.

### Step 5: Search for what was missed

When the proposals feel solid, ask one more question via SendMessage:

```
Is there any other way we could simplify or make this more elegant that
we haven't considered? Step back and look at the whole picture — are there
any concepts, patterns, or boundaries we accepted as given that could
actually be questioned?
```

This often surfaces a second wave of insights. The agent has been deep in
the details and may see new connections after the iterative refinement.

If the agent proposes something new, cycle back to Step 3 (challenge it).
If not, proceed.

### Step 6: Present to the user

Synthesize the entire dialogue into a concise result for the user. Structure
your response as:

```
## Distillation: <Subsystem>

### Current state (N concepts)
[Brief description of the current system and its concept count]

### Proposed simplification (M concepts)
[The distilled design — what changes, what stays, and why]

### Key decisions
[The most important trade-offs and design choices, with reasoning]

### What was challenged and held up
[Proposals that survived stress-testing — these are high-confidence]

### What was challenged and changed
[Proposals that were refined during dialogue — show the evolution]

### Constraints to verify with you
[Any assumptions or future requirements the agent flagged that need
 your confirmation before proceeding]

### Migration path
[How to get from here to there, incrementally]
```

The user can then confirm constraints, reject proposals, or accept the design.
If they have questions or pushback, you can send follow-up messages to the
agent to investigate further.

---

## After User Approval

Once the user accepts the design (with any modifications), spawn a final
**general-purpose** agent to write the design document:

```
Write the distilled design document for the "<subsystem>" subsystem.

## The agreed design
<paste the final design as confirmed by the user>

## What to verify
Read the source files involved and verify all file paths, line references,
and assumptions are current.

## Output
Write to: .traces/features/<subsystem>-distill/design.md

Structure:
- Summary (2-3 sentences)
- Entropy Reduction (before N / after M, with concept lists)
- The Design (full description, enough for implementation)
- Constraints (what shaped the design)
- Migration Path (phased, incremental)
- Files Affected (table: file, change, scope)
```

---

## Orchestration Rules

### One agent, many turns

The core of this skill is a **single long-lived agent conversation** via
SendMessage. Don't spawn separate agents for each step — the same agent
accumulates context about the subsystem across the entire dialogue. This is
crucial: by Step 4, the agent understands the system deeply enough to see
second-order implications of proposed changes.

### You think, the agent reads

Never read source code yourself. The agent reads code and reports findings.
You evaluate findings, formulate challenges, and decide what to investigate
next. This keeps your context focused on the design problem.

### One question per turn

Each SendMessage should pose one clear question or challenge. Don't bundle
"what about X, also Y, and have you considered Z?" into one message. One
question at a time gives the agent space to think deeply and gives you better
signal from each response.

### Bold first, constrain later

Always start with the most aggressive simplification. "What if we just
delete this?" is a better opening than "How might we reduce the coupling?"
The agent will explain why deletion doesn't work, and in doing so will reveal
the actual constraints — which are far more valuable than a cautious proposal
that never tests the boundaries.

### Adapt to what you learn

Steps 3 and 4 are not scripted. The specific challenges you pose depend on
what the agent proposed in Step 2 and how it responded to previous challenges.
Use your judgment — if a proposal feels too conservative, push harder. If a
proposal breaks something important, help the agent find the recut. If the
agent is going in circles, ask it to step back and state the core problem.

### Know when to stop

Stop the dialogue when:
- The concept count has meaningfully decreased
- Every boundary either earns its keep or has been recut
- Your challenges aren't revealing new problems
- The agent's proposals are stable across iterations
