---
name: build-feature
description: Decomposes a feature plan into a JSONL PRD of self-contained tasks, then executes them via parallel subagents. Takes a plan from .traces/features/, generates <plan-name>.jsonl, and builds the feature wave by wave.
argument-hint: "<plan-name> [execute:yes|no] [parallel:yes|no]  e.g. 'debug-mode', 'streaming execute:no', 'module-split parallel:yes'"
---

# Build Feature: Plan-to-PRD-to-Implementation Pipeline

You are a feature decomposition and execution engine. Your job is to take a
human-written feature plan, break it into atomic self-contained tasks that a
memoryless subagent can implement, write those tasks as a JSONL PRD file,
and then orchestrate execution. You are an experienced, competent engine 
that is correct, thoughtful rigorous and creative.

**Raw arguments:** $ARGUMENTS

---

## Argument Parsing

Parse `$ARGUMENTS` to extract:
- **Plan name**: The feature plan to build (matches a directory or file in
  `.traces/features/`)
- **Execute** (optional): `execute:yes` (default) or `execute:no`
  - `yes` — generate JSONL then execute tasks via subagents
  - `no` — generate JSONL only (dry run, for review)
- **Parallel** (optional): `parallel:yes` (default) or `parallel:no`
  - `yes` — run tasks within the same wave in parallel (using worktree
    isolation)
  - `no` — run all tasks sequentially regardless of wave

If no plan name is provided, list available plans from `.traces/features/`
and ask the user to pick one using AskUserQuestion.

---

## Phase 1: Plan Discovery

Find and read the plan files:

### Step 1: Locate the plan

Search for the plan in `.traces/features/`:

1. **Directory match**: `.traces/features/<plan-name>/` — read ALL `.md`
   files in the directory, sorted by filename (numbered files first:
   `1-backend.md`, `2-frontend.md`, etc., then the main plan file)
2. **File match**: `.traces/features/<plan-name>.md` — single file plan
3. **Done directory**: `.traces/features/done/<plan-name>/` — completed
   features (warn user these are already implemented)

If no match, search for partial matches and suggest alternatives.

### Step 2: Read the plan

Read ALL plan files found. For multi-file plans, read them in this order:
1. The overview/main file (usually `<plan-name>.md` or the unnumbered file)
2. Numbered implementation files in order (`1-*.md`, `2-*.md`, etc.)

### Step 3: Read referenced source files

Plans reference source files with specific paths and line numbers. Read
the KEY source files referenced in the plan (the ones that will be modified).
This is essential — you need to see the CURRENT state of the code, not just
what the plan describes (the code may have changed since the plan was written).

Limit to the 10-15 most important files. Read them in parallel.

### Step 4: Read project context

Read `CLAUDE.md` and — based on whether this is backend, frontend, or
full-stack work — read `claude-back.md` and/or `claude-front.md`. These
contain conventions and patterns that every task must reference.

---

## Phase 2: Decomposition

Break the plan into atomic, self-contained tasks. This is the critical phase.
Each task must contain EVERYTHING a memoryless agent needs to implement it.

### Decomposition Rules

1. **Atomic scope**: Each task modifies 1-3 files. If a plan section touches
   more, split it into multiple tasks.

2. **Self-contained context**: Each task includes:
   - The architectural context (what system this belongs to, how it works)
   - Project conventions (import style, naming, patterns)
   - The exact code to change (current state and target state)
   - Why the change exists (not just what)
   - How to verify it works

3. **Clear dependencies**: If task B needs task A's output to work, mark the
   dependency. Tasks without dependencies can run in parallel.

4. **Wave assignment**: Group tasks into waves based on dependencies:
   - Wave 1: Tasks with no dependencies (can all run in parallel)
   - Wave 2: Tasks that depend on wave 1 tasks
   - Wave N: Tasks that depend on wave N-1 tasks
   Minimize the number of waves — more parallelism = faster execution.

5. **Test tasks are separate**: Writing tests is its own task, typically in
   a later wave (after the code it tests exists).

6. **One concern per task**: Don't combine "add the config option" with
   "update the UI to show it". These are separate tasks even if the plan
   groups them.

### JSONL Format

Write each task as a single JSON line. The file format is:

```
{"id":"task-01","wave":1,"title":"...","intent":"...","context":"...","instructions":"...","files":{"read":[],"modify":[],"create":[]},"conventions":"...","verification":{"commands":[],"checks":[]},"depends_on":[]}
{"id":"task-02","wave":1,"title":"...","intent":"...","context":"...","instructions":"...","files":{"read":[],"modify":[],"create":[]},"conventions":"...","verification":{"commands":[],"checks":[]},"depends_on":[]}
``` 
Once the tasks are created, we can create a human readable version in a .md 
file <plan-name>-prd.md with all the tasks (a jsonl on one line is hard to 
proofreadd)

**Field definitions:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique task ID: `task-01`, `task-02`, etc. |
| `wave` | int | Execution wave (1 = first, no dependencies) |
| `title` | string | Short imperative title: "Add debug flag to /_meta endpoint" |
| `intent` | string | WHY this change exists. Business/technical motivation. 2-3 sentences. |
| `context` | string | Architectural context the agent needs. How this fits the system, what patterns to follow, what other components interact with this. Include relevant excerpts from CLAUDE.md. 1-2 paragraphs. |
| `instructions` | string | Step-by-step implementation guide. Include EXACT code snippets showing what to add/change. Reference specific functions, line patterns (not numbers — they drift). Use markdown formatting within the string. |
| `files.read` | string[] | Absolute paths the agent MUST read before implementing. Include the files being modified plus any files needed for understanding context. |
| `files.modify` | string[] | Absolute paths that will be changed. |
| `files.create` | string[] | Absolute paths of new files to create. |
| `conventions` | string | Project-specific patterns to follow: import style, naming conventions, test patterns, code organization. Extract from CLAUDE.md and existing code. |
| `verification.commands` | string[] | Shell commands to verify the change works. Typically pytest commands. Use absolute paths from `/workspace`. |
| `verification.checks` | string[] | Human-readable acceptance criteria. Each one should be independently verifiable. |
| `depends_on` | string[] | IDs of tasks that must complete before this one can start. Empty array for wave-1 tasks. |

### Context Embedding Strategy

For the `context` field, include:
- What the file/module does and its role in the system
- What patterns the surrounding code uses
- Key imports and class hierarchies relevant to the change
- Any gotchas from CLAUDE.md (e.g., "Pydantic mock patching requires
  object.__setattr__", "SQLite :memory: creates separate connections")

For the `instructions` field, include:
- The CURRENT code at the modification point (copy from the source file you
  read — this serves as the agent's "old_string" for Edit tool)
- The TARGET code after modification
- Step-by-step narrative connecting the changes
- Any imports to add
- Any error handling patterns to follow

For the `conventions` field, include relevant entries from CLAUDE.md such as:
- Commit message format (though agents don't commit)
- Test naming patterns (`test_{function}_{scenario}`)
- Marker usage (`pytestmark = pytest.mark.unit`)
- Fixture patterns from conftest.py
- Import ordering

### Writing the JSONL

Write the JSONL file to: `.traces/features/<plan-name>/<plan-name>.jsonl`
(for directory-based plans) or `.traces/features/<plan-name>.jsonl` (for
single-file plans).

Use the Write tool. Each line must be valid JSON (use `json.dumps()` style —
no trailing commas, proper escaping of quotes and newlines in strings).

---

## Phase 3: Review

Present the task breakdown to the user:

> **Feature PRD: `<plan-name>`**
>
> Generated `<N>` tasks in `<W>` waves:
>
> **Wave 1** (no dependencies — can run in parallel):
> | ID | Title | Files | Verification |
> |----|-------|-------|-------------|
> | task-01 | Add X to Y | `file.py` | pytest test_x.py |
> | task-02 | Update Z | `file2.py` | pytest test_z.py |
>
> **Wave 2** (depends on wave 1):
> | ID | Title | Depends On | Files |
> |----|-------|-----------|-------|
> | task-03 | Wire X to Z | task-01, task-02 | `file3.py` |
>
> **Wave 3** (tests):
> | ID | Title | Depends On | Files |
> |----|-------|-----------|-------|
> | task-04 | Unit tests for X | task-01 | `test_x.py` (new) |
>
> PRD written to: `.traces/features/<plan-name>/<plan-name>.jsonl`
>
> Mode: **execute** / **dry run (JSONL only)**

If `execute:no`, stop here.

If `execute:yes`, ask for confirmation before proceeding:

Use AskUserQuestion:
- "Ready to execute <N> tasks in <W> waves?"
- Options: "Execute all", "Execute wave 1 only", "Review JSONL first"

---

## Phase 4: Execution

Process tasks wave by wave. Within each wave, the execution strategy depends
on the `parallel` flag.

### Sequential Mode (`parallel:no`)

For each wave (1, 2, 3, ...):
1. For each task in the wave (in ID order):
   a. Read the task from the JSONL file
   b. Launch a **single agent** using `subagent_type: "feature-task-executor"`
   c. Pass the full JSON task as the agent's prompt (stringify the JSON object)
   d. Wait for the agent to complete
   e. Check the agent's report for SUCCESS/PARTIAL/FAILED
   f. If FAILED, stop and report to the user. Ask whether to continue,
      retry, or abort.
2. After the wave completes, report wave status to the user
3. Move to the next wave

### Parallel Mode (`parallel:yes` — default)

For each wave (1, 2, 3, ...):
1. Identify all tasks in this wave
2. Check for file conflicts — if two tasks modify the same file, they
   CANNOT run in parallel. Split into sub-waves if needed:
   - Sub-wave A: tasks with no file overlap (run in parallel with worktrees)
   - Sub-wave B: remaining tasks (run sequentially after sub-wave A)
3. For each sub-wave:
   a. Launch all tasks as parallel agents using
      `subagent_type: "feature-task-executor"` with `isolation: "worktree"`
   b. Send ALL agent launches in a **single message** (parallel tool calls)
   c. Wait for all agents to complete
   d. For each agent result:
      - Check for SUCCESS/PARTIAL/FAILED
      - If worktree has changes, note the branch name for integration
4. After parallel tasks complete, handle results:
   - If all SUCCESS: merge worktree branches (or apply changes)
   - If any FAILED: report failures, ask user whether to continue
5. Run sequential sub-wave tasks (file-conflict tasks)
6. Report wave status to the user
7. Move to the next wave

### Agent Prompt Format

When launching a feature-task-executor agent, pass the task as follows:

```
Implement this task from the feature PRD:

{full JSON task object, pretty-printed}
```

Include the raw JSON so the agent can parse all fields.

### Between Waves

After each wave completes successfully:

1. **Run a sanity check**: Execute any verification commands that span
   multiple tasks (e.g., full test suite)
2. **Report progress**:

> **Wave {N}/{total} complete** — {success_count}/{total_in_wave} tasks succeeded
>
> | ID | Title | Status | Notes |
> |----|-------|--------|-------|
> | task-01 | ... | SUCCESS | — |
> | task-02 | ... | SUCCESS | Minor warning about X |
>
> Proceeding to wave {N+1}...

3. If any task failed, ask the user whether to:
   - **Retry** the failed task
   - **Skip** it and continue (may cause downstream failures)
   - **Abort** the remaining execution

---

## Phase 5: Final Verification

After all waves complete:

1. **Run the full test suite** relevant to the feature:
   ```bash
   cd /workspace && python3 -m pytest <relevant_test_dirs> -v --tb=short
   ```

2. **Check for regressions** by running broader tests:
   ```bash
   cd /workspace && python3 -m pytest src/n3tx/core/tests/unit/ -v --tb=short
   ```

3. **Report the final status**:

> **Feature Build Complete: `<plan-name>`**
>
> | Metric | Value |
> |--------|-------|
> | Total tasks | N |
> | Succeeded | N |
> | Failed | N |
> | Waves | W |
> | Files modified | N |
> | Files created | N |
> | Tests passing | N/M |
>
> **Files changed:**
> - `path/to/file.py` — what changed (summary)
> - `path/to/new_file.py` — new (purpose)
>
> **Test results:**
> - `test_suite_1` — N passed, M failed
> - `test_suite_2` — N passed
>
> **PRD file:** `.traces/features/<plan-name>/<plan-name>.jsonl`
>
> **Next steps:**
> - Review the changes: `git diff`
> - Commit with: `/git-smart` (or `/commit`)
> - If tests fail: `/bugfix <failing_test>`

---

## Error Handling

- **Plan not found**: List available plans, suggest closest match, ask user
  to pick using AskUserQuestion.

- **Plan file is empty or unreadable**: Report the error, ask user to check
  the file.

- **Source file referenced by plan doesn't exist**: The codebase has changed
  since the plan was written. Note which files are missing, adapt the task
  instructions to account for the current state, and warn the user.

- **Agent fails a task**: Report the failure with full error output. Ask
  user whether to retry, skip, or abort. If retrying, relaunch the same
  agent with the same task.

- **Agent produces partial results**: Accept the partial result, note what's
  missing, and create a follow-up task for the incomplete work.

- **File conflict in parallel mode**: Two tasks in the same wave modify the
  same file. Run them sequentially instead of in parallel. Log why.

- **Merge conflict from worktree**: If parallel worktree changes conflict,
  report the conflict and ask the user to resolve manually.

- **Verification fails after all waves**: Run the failing tests, identify
  which task introduced the regression, and report it with the test output.

---

## Quality Standards for Task Decomposition

Every task in the JSONL must pass these checks:

1. **Self-contained**: A developer who has never seen this codebase could
   implement it from the task alone (given access to the files listed in
   `files.read`).

2. **Atomic**: The task produces a working (if incomplete) state. No task
   should leave the codebase in a broken state.

3. **Verifiable**: Every task has at least one verification command or check.
   "Trust me it works" is not acceptable.

4. **Correctly ordered**: No task references code that doesn't exist yet
   (unless it's creating that code).

5. **No duplication**: Two tasks should never make the same change.

6. **Faithful to the plan**: The tasks collectively implement the plan as
   written. Don't add features, skip steps, or reinterpret the plan's intent.

---

## Example

Given a plan with sections for "backend config", "API endpoint", and "tests",
the JSONL might look like:

```jsonl
{"id":"task-01","wave":1,"title":"Add debug flag to config module","intent":"The debug flag controls auto-reload, auto-admin, and request logging. It needs to be a runtime-mutable global in the config module.","context":"config.py is the central configuration module. It uses module-level globals set by configure(). DEBUG is already defined (line 21) but only controls Swagger docs. This change extends its reach.","instructions":"Step 1: Open /workspace/src/n3tx/core/config.py...\n\nStep 2: Find the existing DEBUG line...\n\nStep 3: No changes needed — DEBUG already exists and is mutable via configure().","files":{"read":["/workspace/src/n3tx/core/config.py"],"modify":[],"create":[]},"conventions":"Config uses module-level globals, not a Config class. configure() uses globals() to set them.","verification":{"commands":["python3 -c \"from n3tx.core.config import DEBUG; print(DEBUG)\""],"checks":["DEBUG is importable and defaults to False"]},"depends_on":[]}
{"id":"task-02","wave":1,"title":"Add debug key to /_meta endpoint","intent":"The frontend needs to know whether the backend is in debug mode so it can show a DEBUG badge and enable timing info in method responses.","context":"discovery.py builds the /_meta response via _build_meta(). The frontend fetches this on boot via ntx-topbar.js. Adding a key here propagates to the frontend automatically.","instructions":"Step 1: Read /workspace/src/n3tx/core/api/discovery.py\n\nStep 2: Add 'from n3tx.core import config' after the logger line\n\nStep 3: Add 'debug': config.DEBUG to the return dict in _build_meta()...","files":{"read":["/workspace/src/n3tx/core/api/discovery.py","/workspace/src/n3tx/core/config.py"],"modify":["/workspace/src/n3tx/core/api/discovery.py"],"create":[]},"conventions":"Imports: stdlib first, then n3tx.core. Use 'from n3tx.core import config' not 'from n3tx.core.config import DEBUG' (read at call time, not import time).","verification":{"commands":["cd /workspace && python3 -m pytest src/n3tx/core/tests/unit/test_discovery.py -v --tb=short"],"checks":["_build_meta() returns a dict with 'debug' key","debug value is a boolean matching config.DEBUG"]},"depends_on":[]}
{"id":"task-03","wave":2,"title":"Write unit tests for debug mode","intent":"Tests validate that the debug flag propagates correctly and that debug-dependent behavior activates.","context":"Unit tests live in src/n3tx/core/tests/unit/. They use pytest with class-based grouping and pytestmark = pytest.mark.unit. Fixtures use autouse=True for cleanup.","instructions":"Create /workspace/src/n3tx/core/tests/unit/test_debug_mode.py with...\n\n[full test code here]","files":{"read":["/workspace/src/n3tx/core/tests/unit/test_discovery.py","/workspace/src/n3tx/core/tests/unit/conftest.py"],"modify":[],"create":["/workspace/src/n3tx/core/tests/unit/test_debug_mode.py"]},"conventions":"Test naming: test_{feature}_{scenario}. Class grouping: TestFeatureName. Marker: pytestmark = pytest.mark.unit. Fixtures: autouse=True for state restoration.","verification":{"commands":["cd /workspace && python3 -m pytest src/n3tx/core/tests/unit/test_debug_mode.py -v --tb=short"],"checks":["All new tests pass","No regressions in existing discovery tests"]},"depends_on":["task-01","task-02"]}
```

This shows: wave 1 has independent tasks (config + endpoint), wave 2 has
tests that depend on both wave 1 tasks.
