# skill-path-aliases

Project-local pi extension that enforces path-shaped skill commands.

## Why

Pi exposes skills as flat commands like `/skill:git-status`.
This extension adds a folder-shaped alias layer so nested skills are invoked by
where they live on disk, not only by their flat leaf name.

## Supported form

Only the path form is accepted for nested skills:

- `git/git-status` → `/skill:git:git-status`
- `architecture/deep-audit` → `/skill:architecture:deep-audit`
- `dev/bugfix` → `/skill:dev:bugfix`

Aliases preserve the full nested folder name exactly:

- `/skill:git:git-status` → canonical `/skill:git-status`
- `/skill:design:interface-design` → canonical `/skill:interface-design`

## Behavior

- Path aliases are rewritten to pi's canonical skill command before expansion.
- The extension also registers real slash commands for nested path aliases, so both the canonical flat command and the path alias can appear in the TUI autocomplete.
- Direct canonical use of nested skills, like `/skill:git-status`, is blocked in-session and the extension warns with the preferred path form.
- Top-level skills with no folder path, like `/skill:review`, are left alone.

## Important limitation

This does **not** remove pi's underlying built-in skill command registration.
The canonical command will still appear in pi's command list or completion UI.
The extension adds path aliases alongside it; it does not replace the native flat command.

## Location

Pi auto-discovers this extension from:

- `.pi/extensions/skill-path-aliases/index.ts`

No pi internals are modified.

## Verification

```bash
cd /workspace/.pi/extensions/skill-path-aliases
node --test skill-aliases.test.mjs
```
