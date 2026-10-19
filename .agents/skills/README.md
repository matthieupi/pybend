# Agent Workflow Inventory

The shared `.agents/` tree now uses a **hybrid model**:

- **Common explicitly invoked workflows** live in `.agents/prompts/`
- **Heavyweight specialized capabilities** remain real skills in `.agents/skills/`
- **Support/reference material** for those workflows also lives in `.agents/skills/`

These are reusable workflow sources, not proof that every harness has loaded
them. Check the active harness's available tools, agents and discovery settings
before invocation. Do not change permissions to make a workflow fit.

## Shared harness wiring

- **shared commands view**: `.agents/commands -> prompts`
- `.opencode/commands/` is a separate directory in this checkout, not this alias.
- Claude/OpenCode/pi discovery and any external symlinks are installation-specific.
- Legacy workflow templates mentioning `.traces/` use `.project/` for working
  artifacts here. Resolve code paths against this checkout's `AGENTS.md`,
  `BACKEND.md`, `FRONTEND.md` and `docs/README.md`, not a fixed `/workspace` root.
- Tool names such as `Task`, `Agent`, `SendMessage` and `AskUserQuestion` are
  harness-specific. If unavailable, report the limitation rather than claiming
  a delegation occurred. Research size targets never justify invented evidence.

## Real skills

These remain canonical skills because they are larger, specialized workflow
packages rather than lightweight explicit prompts:

- `.agents/skills/plan/SKILL.md` → `/skill:plan`
- `.agents/skills/research/ideation/SKILL.md` → `/skill:ideation`
- `.agents/skills/perf/perf-analysis/SKILL.md` → `/skill:perf-analysis`
- `.agents/skills/dev/fix-test/SKILL.md` → `/skill:fix-test`

## Prompt / command names

The filename in `.agents/prompts/` is the invoked prompt/command name.
Examples:

- `.agents/prompts/git-status.md` → `/git-status`
- `.agents/prompts/bugfix.md` → `/bugfix`
- `.agents/prompts/fix-test.md` → `/fix-test`
- `.agents/prompts/deep-audit.md` → `/deep-audit`
- `.agents/prompts/write-a-prd.md` → `/write-a-prd`

## Support docs in `.agents/skills/`

This directory also contains non-invoked reference material used by prompts or
skills, such as:

- `.agents/skills/dev/tdd/*.md`
- `.agents/skills/arch/improve-codebase-architecture/REFERENCE.md`

These files are not themselves invoked directly as prompts or standalone skills.

## Important constraints

### `.agents/prompts/`
Keep this directory flat.

- pi prompt discovery is non-recursive
- a root markdown file there becomes an invokable prompt/command
- do not add `README.md` or nested documentation trees inside `.agents/prompts/`

### `.agents/skills/`
A real skill must live in its own directory with `SKILL.md`, and the skill
frontmatter `name:` must match the immediate parent directory exactly.
