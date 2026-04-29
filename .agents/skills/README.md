# Agent Workflow Inventory

The shared `.agents/` tree now uses a **hybrid model**:

- **Common explicitly invoked workflows** live in `.agents/prompts/`
- **Heavyweight specialized capabilities** remain real skills in `.agents/skills/`
- **Support/reference material** for those workflows also lives in `.agents/skills/`

This keeps the portable source compatible across all three harnesses while
preserving a distinction between lightweight commands-as-prompts and larger
capability packages.

## Shared harness wiring

- **pi prompts**: `.pi/prompts -> /workspace/.agents/prompts`
- **shared commands view**: `.agents/commands -> prompts`
- **Claude Code commands**: `.claude/commands -> /workspace/.agents/commands`
- **OpenCode commands**: `.opencode/commands -> /workspace/.agents/commands`
- **Claude/OpenCode/pi skills** continue to read from `.agents/skills/` via their skill discovery paths or symlinks

## Real skills

These remain canonical skills because they are larger, specialized workflow
packages rather than lightweight explicit prompts:

- `.agents/skills/planning/plan/SKILL.md` → `/skill:plan`
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
