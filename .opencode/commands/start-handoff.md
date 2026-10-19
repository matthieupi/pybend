---
description: Load a recent handoff by ordinal, hydrate required context, inspect referenced docs/code, and prepare to continue from the prior session.
agent: build
argument-hint: "[-1 latest, -2 second latest, --list, or optional focus text]"
---

# Start From Handoff

Resume from a prior engineering handoff with minimal rediscovery. Select the
requested handoff, read it fully, load the skills and context it names, inspect
the referenced docs/code, and report readiness before making any changes.

**Arguments:** `$ARGUMENTS`

## Selection behavior

Handoffs live under:

```text
/workspace/.project/handoffs/
```

Supported arguments:

```text
/start-handoff        # latest handoff, same as -1
/start-handoff -1     # latest handoff
/start-handoff -2     # second latest handoff
/start-handoff -3     # third latest handoff
/start-handoff --list # list handoffs newest-first and stop
/start-handoff <text> # latest handoff, with <text> as continuation focus
```

Use this Python selector rather than shell truncation commands:

```bash
python - <<'PY'
from pathlib import Path

handoffs = sorted(
    Path('/workspace/.project/handoffs').glob('handoff-*.md'),
    key=lambda p: (p.stat().st_mtime, p.name),
    reverse=True,
)

for i, path in enumerate(handoffs, start=1):
    print(f'-{i} {path}')
PY
```

Then choose the handoff as follows:

1. If `$ARGUMENTS` is empty, select `-1`.
2. If `$ARGUMENTS` is `--list`, list handoffs newest-first and stop.
3. If `$ARGUMENTS` starts with `-N` where `N` is a positive integer, select
   the Nth newest handoff.
4. If `$ARGUMENTS` contains other text after the ordinal, preserve that text as
   the continuation focus.
5. If `$ARGUMENTS` is text without an ordinal, select `-1` and treat the text
   as the continuation focus.
6. If the selected ordinal does not exist, report the available handoffs and
   stop without guessing.

## Required startup workflow

1. **Find and select the handoff** using the selection behavior above.
2. **Read the selected handoff completely** into context.
3. **Load mandatory repo skills first**, in this order unless the handoff gives
   a more specific superset:
   - `n3tx-skill-routing`
   - `n3tx-principles`
   - `n3tx-build-app`
4. **Load every skill named by the handoff** under sections like:
   - `Suggested Skills / Context to Load`
   - `Recommended Next Steps`
   - `Risks, Blockers, and Assumptions`
5. **Read canonical docs before code**, following `AGENTS.md`:
   - `/workspace/lib/n3tx/docs/ARCHITECTURE.md`
   - `/workspace/lib/n3tx/docs/CORE.md`
   - `/workspace/lib/n3tx/docs/ACTORS.md`
   - `/workspace/lib/n3tx/docs/AGENTS.md`
   - `/workspace/lib/n3tx/docs/MODELS.md`
   - `/workspace/lib/n3tx/docs/AUTHORIZATION.md`
   - `/workspace/lib/n3tx/docs/API_REFERENCE.md`
   - `/workspace/lib/n3tx/BACKEND.md` and/or `/workspace/lib/n3tx/FRONTEND.md`
     when the handoff indicates backend/frontend scope.
6. **Read referenced artifacts** from the handoff, including plans, PRDs,
   prior handoffs, issues, logs, or implementation notes when they are relevant
   to the continuation focus.
7. **Inspect referenced code paths** and current neighboring code before
   proposing implementation.
8. **Inspect current repo state** with non-destructive git commands:
   - `git status --short`
   - `git diff --stat`
   - `git diff --name-status`
9. **Do not edit files automatically.** First report readiness and the proposed
   next implementation direction. Wait for explicit confirmation unless the
   user's command arguments clearly ask you to proceed with a specific change.

## Readiness report

After loading context, respond with a concise continuation packet:

```md
## ✅ Handoff Loaded

- Selected handoff: `<absolute path>`
- Selection argument: `<$ARGUMENTS or default -1>`
- Continuation focus: `<focus text or none>`

## 📍 Context Loaded

| Type | Loaded |
| --- | --- |
| Skills | `<skills>` |
| Docs | `<docs>` |
| Artifacts | `<paths>` |
| Code | `<paths>` |

## 🔎 Current Repo State

- Git status summary: `<summary>`
- Dirty files relevant to this continuation: `<files or none>`
- Risks/blockers from handoff: `<summary>`

## ✨ Recommended Next Move

1. `<first concrete action>`
2. `<second concrete action>`
3. `<verification step>`
```

Keep the report factual. Do not claim a doc, skill, artifact, file, or command
was loaded or checked unless it actually was.

## Safety rules

- Do not modify files during context hydration.
- Do not commit, amend, push, delete, or reset anything.
- Do not treat runtime output under `runs/` as source truth.
- Redact secrets if handoff references sensitive content.
- If the handoff conflicts with current repo state, say exactly what differs
  and recommend the safest next verification step.
- If no handoffs exist, report that clearly and suggest running `/handoff` at
  the end of the current working session.

If this command file or related opencode configuration was just changed, remind
the user to restart opencode before relying on `/start-handoff` in a new session.
