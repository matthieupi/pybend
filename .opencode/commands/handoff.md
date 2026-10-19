---
description: Create a comprehensive, styled handoff document that preserves task context, conversation state, decisions, risks, and next steps for a fresh agent.
agent: build
---

Write a comprehensive handoff document that lets a fresh agent continue this session with minimal rediscovery.

The handoff is not just a summary. It is an engineering continuation packet: preserve the user's goal, the conversational context that shaped decisions, current repo state, implementation progress, verification evidence, unresolved risks, and the exact recommended next moves.

Save the handoff document to /workspace/.project/handoffs/. Use an explicit, 
timestamped filename such as `handoff-YYYYMMDD-HHMMSS.md`.

If command arguments were provided, treat them as the requested next-session focus and tailor the handoff toward that continuation path.

Next-session focus:

```text
$ARGUMENTS
```

## Writing style

Match this project's build/plan artifact style:

- ✅ Lead with outcomes and current state.
- 📍 Make scope, files, modules, routes, commands, and artifacts easy to scan.
- 🧵 Preserve relevant conversational context, including user intent, preferences, corrections, and approvals.
- 🗺️ Include ASCII diagrams when they clarify architecture, flow, ownership, sequencing, or handoff boundaries.
- 📊 Use compact tables for changed files, decisions, risks, verification, and next steps when they reduce prose.
- 💻 Include concise code snippets, command examples, route shapes, payload examples, or pseudo-diffs when they help the next agent act safely.
- 🧪 Separate verified facts from assumptions and gaps.
- ⚠️ Surface blockers, risks, compatibility issues, and places where the next agent must verify before editing.
- ✨ End with concrete next steps in priority order.

Be precise and implementation-grade. Avoid vague statements like "fix remaining issues" unless you name the files, functions, tests, routes, or symptoms involved.

## Required handoff structure

Use this structure unless the current session clearly calls for a better one:

```md
# Handoff — <Project / Task Name>

Generated: <YYYY-MM-DD HH:MM:SS local time>
Session focus: <one sentence>

## ✅ Executive Snapshot

<3-6 bullets that explain what the next agent most needs to know.>

## 🎯 Current Goal and Next-Session Focus

- User goal: <what the user is ultimately trying to accomplish>
- Latest request: <what triggered this handoff>
- Recommended next focus: <what the next agent should do first>
- Definition of done: <observable success criteria, if known>

## 🧵 Conversation Context

Summarize the relevant conversation in chronological order. Preserve:

1. What the user asked for.
2. Important clarifications, preferences, and style directives.
3. Proposed approaches and whether the user accepted, rejected, or modified them.
4. Any points where the assistant intentionally paused for review.
5. Any user-reported runtime behavior, errors, screenshots, logs, or manual validation.

Do not include irrelevant chat. Do include context that affects future implementation choices.

## 📍 Repo / Workspace Context

| Concern | Value |
| --- | --- |
| Workspace | `/workspace` |
| Primary app/package | `<path>` |
| Relevant modules | `<paths>` |
| Important docs/plans | `<paths or URLs>` |
| Test commands | `<commands>` |

Include only context needed to continue. Reference canonical artifacts instead of copying them wholesale.

## 🗺️ Current Architecture / Flow

Use a diagram if a flow, subsystem, or ownership boundary matters. Example:

```text
browser
  -> app route/component
  -> N3TX schema/model/method
  -> actor/service boundary
  -> storage/compute/external system
  -> UI feedback
```

Explain the diagram in 2-5 bullets after it.

## ✅ Completed Work

Group completed work by coherent slice. Include files, routes, functions, tests, and decisions.

| Slice | Files / Areas | What changed | Status |
| --- | --- | --- | --- |
| <name> | `<path>` | <concrete change> | ✅ Done / 🟡 Partial |

If code changed, include representative snippets or pseudo-diffs only when they help continuation. Prefer links/paths over large duplicated diffs.

## 🔎 Current State

Describe the repo and product state at handoff time:

- What is known to work.
- What is known to fail.
- What is unverified.
- Any dirty working tree expectations, generated files, local runtime artifacts, or external state the next agent should not touch.

## 🧩 Important Decisions and Rationale

| Decision | Rationale | Consequence / Follow-up |
| --- | --- | --- |
| <decision> | <why> | <impact> |

Capture decisions that prevent the next agent from re-litigating settled choices.

## 🧪 Verification Evidence

List checks that were actually run. Do not claim verification that did not happen.

```bash
<exact command that was run>
```

| Check | Result | Notes |
| --- | --- | --- |
| `<command/test>` | ✅ Passed / ❌ Failed / ⚠️ Blocked | <details> |

If a check failed or could not run, include the actionable reason and the next verification path.

## ⚠️ Risks, Blockers, and Assumptions

| Type | Detail | Mitigation / Next action |
| --- | --- | --- |
| Risk | <risk> | <how to reduce it> |
| Blocker | <blocker> | <who/what unblocks it> |
| Assumption | <assumption> | <how to verify> |

## ✨ Recommended Next Steps

Give a prioritized, executable list. Each step should name the likely files and verification.

1. <First action>
   - Files: `<path>`, `<path>`
   - Verify: `<command>`
   - Watch for: <risk>
2. <Second action>

## 🧠 Suggested Skills / Context to Load

List skills or docs the next agent should load first, in order, and why.

1. `<skill-or-doc>` — <reason>
2. `<skill-or-doc>` — <reason>

## 📚 Artifact References

- `<path>` — <what it contains>
- `<path>` — <why it matters>

Do not duplicate large PRDs, plans, ADRs, diffs, issues, or existing handoffs. Reference them by path or URL.

## 🔐 Sensitive Content Handling

State whether sensitive material appeared in the session. Redact secrets as `[REDACTED]` and describe only their purpose.
```

## Content requirements

The handoff document must include, when relevant:

- current goal and requested next-session focus
- relevant conversation summary, including user preferences and approvals
- current repo/workspace context, only as needed to continue safely
- completed work and important decisions
- remaining work and recommended next steps with file/test specificity
- known risks, assumptions, blockers, or verification gaps
- suggested skills the next agent should invoke
- exact verification commands already run and their results
- artifact references for related plans, PRDs, issues, diffs, screenshots, logs, or prior handoffs

## Safety and redaction rules

- Do not duplicate content already captured in other artifacts such as PRDs, plans, ADRs, issues, commits, or diffs. Reference those artifacts by path or URL instead.
- Redact sensitive information, including API keys, passwords, tokens, secrets, credentials, private keys, session cookies, and personally identifiable information.
- If sensitive content is relevant, describe it generically as `[REDACTED]` and explain only the operational role, such as "service token" or "test user credential".
- Do not write local-only runtime state as if it were source truth. Clearly distinguish repo files from generated artifacts, runtime output, containers, browser state, and user-local environment.
- Do not fabricate test results, code behavior, or repo state. If unknown, say unknown and provide the verification step.

## Quality checklist before saving

Before writing the final file, check that a fresh agent can answer:

- What is the user trying to accomplish?
- What did this session already decide or change?
- Which files/modules/routes/components are relevant?
- What is the current known-good state?
- What is broken, risky, blocked, or unverified?
- What should the next agent do first, second, and third?
- Which commands should the next agent run to verify progress?
- Which skills/docs should the next agent load before editing?

After writing the file, report the absolute path to the handoff document and briefly summarize what it contains.

If you changed this command file or related opencode configuration, remind the user to restart opencode before relying on the updated command in a new session.
