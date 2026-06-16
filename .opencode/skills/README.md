# N3TX OpenCode Skills Catalog

This directory contains project-local OpenCode skills for N3TX development.
Skills are agent-facing routing and execution aids; canonical framework
contracts still live in `AGENTS.md`, `BACKEND.md`, `FRONTEND.md`, `/workspace/docs/`,
and package docs.

## Maintenance rules

- Each skill lives at `.opencode/skills/<name>/SKILL.md`.
- Frontmatter `name:` must match the folder name.
- Frontmatter `description:` should front-load concrete trigger keywords and say
  when to use the skill.
- Narrow/high-risk skills should use `Use ONLY when...` or equivalent negative
  routing language.
- Broad skills should orient and delegate instead of duplicating specialist
  contracts.
- Do not duplicate long route tables, test command lists, or package maps unless
  the skill also includes a clear drift anchor to the canonical doc.

## Shared sections to prefer

```markdown
## Use first
- `n3tx-principles` for architectural intent.
- `n3tx-skill-routing` when task scope or skill choice is ambiguous.

## Combine with
- `n3tx-testing` for behavior-changing work.
- Area-specific companion skills for cross-boundary work.

## Do not use for
- Adjacent task types that should route elsewhere.

## Read first
1. `AGENTS.md` and relevant docs/package docs.
2. `BACKEND.md`, `FRONTEND.md`, or both by scope.
3. Source only when docs/skills are insufficient or contradicted.

## Drift anchors
- Canonical docs or files that own the contract summarized by this skill.
```

## Drift checklist

Run `.opencode/scripts/lint-skills.mjs` after skill edits. Then restart
OpenCode; running sessions keep the already-loaded skill catalog.

Manual checks:

- New package added? Update `n3tx-skill-routing`, `n3tx-framework-maintenance`,
  and relevant workflow skills.
- New route grammar or frontend route semantics? Update or anchor frontend,
  UI-schema, and methods-route skills.
- New verification command? Prefer linking to `AGENTS.md`, `BACKEND.md`, or
  `FRONTEND.md` instead of duplicating it broadly.
- New extension point? Update `n3tx-extension-patterns` and area-specific skills.
