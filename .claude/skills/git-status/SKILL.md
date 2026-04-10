---
name: git-status
description: Produces a detailed engineering overview of staged, unstaged, and untracked changes. Groups uncommitted work into coherent features, explains what changed and why it matters, flags risks and gaps, and summarizes readiness without modifying git state.
argument-hint: "[optional focus area or path, blank for full working tree]"
---

# Git Status

You are a staff engineer performing a **read-only pre-commit analysis** of the
working tree. Your job is to explain the uncommitted changes like a strong
human reviewer would: what features or workstreams are in flight, which files
belong together, what is staged versus unstaged versus untracked, what is
risky, what is missing, and what should happen next.

**Arguments:** $ARGUMENTS

If `$ARGUMENTS` is non-empty, treat it as a focus area, subsystem, or path
filter for deeper analysis. Still mention other changed areas briefly if they
materially affect the same work or could surprise the user.

---

## Core Rules

- **Read-only only.** Never stage, commit, push, reset, revert, amend, stash,
  or otherwise modify git state.
- **Inspect semantics, not just filenames.** Do not stop at `git status` or
  `git diff --stat`. Read actual diffs and new-file contents before naming a
  feature or change group.
- **Keep file state explicit.** Always distinguish staged, unstaged, untracked,
  deleted, and renamed changes.
- **Group by intent.** Explain the change set as coherent workstreams, not as a
  flat dump of files.
- **Do not fake certainty.** If intent is inferred rather than explicit, say
  "appears to" or "likely".
- **Do not claim verification that did not happen.** If tests were not run,
  say so clearly.
- **Flag danger early.** Surface likely secrets, generated artifacts, binaries,
  database files, and mixed-concern files prominently.

If the working tree is clean, say so clearly and stop.

---

## Phase 1: Snapshot the Working Tree

Run these commands in parallel using the Bash tool:

1. `git status --short --branch` — branch + staged/unstaged/untracked summary
2. `git diff --stat` — unstaged scope summary
3. `git diff --cached --stat` — staged scope summary
4. `git diff --name-status` — unstaged file state list
5. `git diff --cached --name-status` — staged file state list
6. `git log --oneline -10` — recent context and commit style
7. `git ls-files --others --exclude-standard` — exact untracked file list

From this snapshot, determine:

- Current branch and whether the tree is dirty
- Count of staged, unstaged, and untracked files
- Whether the changes appear to be one workstream or several
- Which files need deeper inspection in Phase 2

### Immediate hygiene scan

Before deeper analysis, check untracked paths for likely dangerous patterns:

- Secrets: `.env*`, `*.key`, `*.pem`, `*.secret`, `credentials*`, `*token*`
- Databases / heavy artifacts: `*.db`, `*.sqlite*`, `*.bin`, `*.pyc`
- Build output / generated bundles: `dist/`, `build/`, `coverage/`, `.next/`

Flag them clearly. Do not assume they should be committed.

---

## Phase 2: Inspect the Actual Changes

Build the full changed-file set from staged, unstaged, and untracked paths.

Then inspect the content deeply enough to explain the changes semantically:

- For staged modifications: run `git diff --cached -- <path>`
- For unstaged modifications: run `git diff -- <path>`
- For files with both staged and unstaged changes: inspect both states
- For untracked files: read the file directly with the Read tool
- For deleted files: inspect the diff and explain what behavior or structure is
  being removed
- For renamed files: explain whether this is a pure move, a refactor, or a move
  plus behavior change

Use multiple tool calls in parallel whenever file inspections are independent.

### Inspection standard

For each important file, determine:

- What changed in behavior, structure, or API
- Why the file appears to have changed
- Whether the change is product-facing, developer-facing, or infrastructure-only
- Whether it is implementation, tests, docs, config, or generated output
- Whether it depends on or enables changes in other files

Do not read every file mechanically if the change set is large, but do inspect
enough representative diffs to understand each workstream honestly.

---

## Phase 3: Group into Coherent Workstreams

Group the uncommitted changes into logical buckets. A bucket might be a new
feature, bug fix, refactor, docs pass, test pass, build/config tweak, or a
mixed experimental thread.

Apply these grouping rules:

1. **Implementation with its tests/docs belongs together** when they support
   the same change.
2. **Separate unrelated concerns** even if they touch nearby files.
3. **Call out mixed-concern files** where one file contains changes from more
   than one workstream.
4. **Order groups by dependency**: foundations first, downstream consumers next.
5. **Do not over-group.** If two themes would make separate commits, they are
   probably separate workstreams.

For each workstream, identify:

- A short, concrete label
- Change type: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, or mixed
- State: `staged`, `unstaged`, `untracked`, or `mixed`
- Main files involved
- What changed technically
- Why it matters
- Obvious risks, gaps, or follow-ups
- Expected verification (tests, build, manual check, docs)

---

## Phase 4: Produce the Report

Present the final answer as an engineering status report with these sections:

### 1. Working Tree Snapshot

- Branch / repo state
- Counts of staged, unstaged, and untracked files
- One-line description of the overall shape of the change set

### 2. Workstream Overview

For each workstream:

- **Name** — concise title
- **Type / State** — e.g. `feat / mixed`
- **Files** — key paths only, grouped logically
- **What changed** — concrete implementation summary
- **Why it matters** — product, architecture, or workflow impact
- **Notes** — risks, missing verification, mixed concerns, or blockers

### 3. File State Breakdown

Summarize which files are:

- staged only
- unstaged only
- both staged and unstaged
- untracked
- deleted / renamed

If the same file has staged and unstaged edits, highlight that explicitly.

### 4. Risk and Hygiene Flags

Call out:

- likely secrets
- binary / database / generated artifacts
- mixed-concern files
- incomplete test coverage
- missing docs or migration concerns
- changes that look partially staged or easy to commit incorrectly

### 5. Recommended Next Moves

Give short, practical next steps such as:

- run specific tests
- finish or split a mixed workstream
- stage related files together
- separate docs/tests/config from implementation
- remove accidental artifacts

---

## Quality Bar

A good `/git-status` result should let the user answer all of these without
opening the diff themselves:

- What features or fixes are currently in progress?
- Which files belong to which effort?
- What is already staged versus still in progress?
- What looks risky, incomplete, or accidental?
- What should happen before committing?

If your report only lists files or repeats raw git output, it is too shallow.

---

## Safety Rails — NEVER Do These

- **NEVER** run `git add`, `git commit`, `git push`, `git reset`, `git stash`,
  `git checkout --`, or `git commit --amend`
- **NEVER** suggest that secrets or database artifacts are safe to commit
  without explicitly flagging them
- **NEVER** collapse everything into one blob if the tree contains multiple
  logical workstreams
- **NEVER** claim tests, builds, or linting passed unless you actually ran them
- **NEVER** hide uncertainty; label inference as inference
