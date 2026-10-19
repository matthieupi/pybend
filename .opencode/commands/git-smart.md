---
description: Analyzes dirty working tree, groups changes into logically cohesive commits by scope/type/dependency, and executes them with proper conventions.
agent: build
argument-hint: "[--dry-run to stop after grouping, or blank to execute]"
---

# Smart Commit

## Checkout And Safety

Only execute commits when the user requested them. Before staging, inspect both
`git diff` and `git diff --cached`, including content for secrets, not just names.
Derive current scopes from the package map below and recent history. Use only
verified authorship. Stop for ownership clarification on mixed-concern files;
do not silently include another contributor's edits in a commit group.

You are a release engineer. Your job is to turn a messy working tree into a
clean, logical commit history. You analyze all pending changes, group them
by scope and type, order by dependency, and execute focused commits.

**Arguments:** $ARGUMENTS

If `--dry-run` is passed, stop after Phase 2 (show the plan but don't commit).

---

## Phase 1: Context Gathering

Run these commands in parallel using the Bash tool:

1. `git log --oneline -20` — understand the current wave, conventions, and recent context
2. `git status` — see all modified, staged, and untracked files (never use `-uall`)
3. `git diff --stat` — see the scope of changes across files
4. `git diff --name-status` — see which files are modified (M), added (A), deleted (D), renamed (R)

After gathering, do a **secrets scan**: check untracked files for dangerous
patterns (`.env`, `*.key`, `*.pem`, `*.secret`, `credentials*`, `*token*`).
If any are found, **exclude them** from all commit groups and warn the user.

Also check for any **large binary files** (images, compiled assets, databases)
in untracked files — flag these for the user but don't auto-exclude.

---

## Phase 2: Intelligent Grouping

### Step 1 — Detect wave tag

Read the most recent commits from Phase 1 output. Extract the wave tag
(e.g., `[0.9.6]`, `[0.10]`). Use this tag on all commits unless a group
clearly belongs to a different wave.

### Step 2 — Map files to scopes

Use current package paths; confirm scope names against recent history:

| Directory pattern | Scope |
|---|---|
| `packages/n3tx-core/` | affected subsystem: models, storage, api, auth, frontend |
| `packages/n3tx-actors/`, `packages/n3tx-agents/` | actors, agents |
| `packages/n3tx-ui/`, `packages/n3tx-files/` | frontend, files |
| `examples/` | example or affected subsystem |
| `tests/` | inherits scope from what it tests |
| `docs/`, package docs, root guides | docs type; affected subsystem scope |
| Agent/tool configuration | chore type; derive scope from history |

### Step 3 — Group by cohesion

Apply these grouping rules in order:

1. **Implementation + its tests together**: If `foo.py` changed and
   `test_foo.py` also changed, they belong in the same commit.

2. **Separate by commit type**: Don't mix these types in one commit:
   - `feat` — new functionality
   - `fix` — bug fixes
   - `refactor` — restructuring without behavior change
   - `test` — test-only changes (no implementation counterpart)
   - `docs` — documentation-only changes
   - `chore` — tooling, config, meta-files

3. **Bulk mechanical changes together**: If many files have the same kind
   of change (e.g., all e2e tests updated for a rename, all example apps
   getting the same HTML change), group them into one commit even if they
   span multiple scopes.

4. **New files vs modified files**: Untracked files that constitute a new
   feature should be grouped with related modified files. Standalone new
   files get their own commit.

### Step 4 — Order by dependency

Sort commit groups in this order:
1. Core framework changes (models, storage, utils, actors)
2. Feature implementations (agents, api, files)
3. Frontend changes (package static directories)
4. Example app changes (examples/)
5. Test-only changes
6. Documentation
7. Chore (meta-files, config, traces)

### Step 5 — Flag mixed-concern files

Inspect staged and unstaged hunks for mixed concerns or ownership. Stop and ask
which hunks belong to each approved group. Never assign a whole mixed file by
its dominant change. Use an explicitly approved noninteractive hunk split, or
defer the file; do not overwrite or unstage another contributor's work.

### Step 6 — Draft commit messages

For each group, draft a message following project conventions:
```
type(scope): Description [wave]
```

- **type**: feat, fix, refactor, test, docs, chore
- **scope**: from the scope mapping above
- **Description**: imperative mood, capitalized, concise (under 70 chars)
- **[wave]**: detected wave tag
- Add attribution trailers only for verified authorship; none are automatic.

### Step 7 — Present the plan

Display the commit plan as a numbered list:

```
Commit plan (N commits):

1. type(scope): Message [wave]
   Files: file1.py, file2.py, test_file1.py

2. type(scope): Message [wave]
   Files: file3.js, file4.css

...

Total: N commits, M files
```

If `--dry-run` was passed, **STOP HERE**. Do not proceed to Phase 3.

---

## Phase 3: Execute Commits

Execute each commit group sequentially. For each group:

1. **Reconcile ownership and index before each commit**: inspect `git status`,
   `git diff` and `git diff --cached`. Existing staged hunks must belong to the
   approved group. Otherwise stop for explicit reconciliation; never silently
   unstage, overwrite or include unrelated work. Stage only approved paths/hunks:
   `git add file1.py file2.py` is safe only when each entire file is approved.
   **NEVER use `git add .` or `git add -A`.** Re-read the complete cached diff
   after staging and require it to equal the approved group before committing.

2. **Commit with HEREDOC format**:
   ```bash
   git commit -m "$(cat <<'EOF'
   type(scope): Description [wave]
   EOF
   )"
   ```

3. **Verify**: Inspect `git show --stat` and the committed diff, then `git status`
   and remaining staged/unstaged diffs to confirm only approved work was committed.

4. If a **pre-commit hook fails**: fix the issue, re-stage, and create a
   **NEW** commit (never `--amend`).

After all commits are done, run `git log --oneline -N` (where N = number
of commits created) to show the final result.

---

## Safety Rails — NEVER Do These

- **NEVER** `git add .` or `git add -A` — always stage specific files
- **NEVER** `git commit --amend` — always create new commits
- **NEVER** `git push` — unless the user explicitly requests it
- **NEVER** `git push --force` — refuse even if asked, warn instead
- **NEVER** commit files matching: `.env*`, `*.key`, `*.pem`, `*.secret`,
  `credentials*`, `*token*` (file-path patterns, not content)
- **NEVER** use `--no-verify` to skip pre-commit hooks
- **NEVER** use `-i` flag (interactive mode is unsupported)
