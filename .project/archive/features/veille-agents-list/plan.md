# Veille Agents Surface and `ntx-agents` Plan

## Purpose

This document is written for a memoryless implementation agent.

Its job is to capture the corrected user intent, the current N3TX and Veille
behavior, the architectural constraints already verified in the codebase, and
the exact implementation plan for adding a custom agents list without breaking
the existing grant analysis preview.

This plan is implementation-oriented. It is not the final product spec, and it
is not permission to change unrelated agent or grant UI behavior.

Note: the repository convention is `.traces/`, not `traces/`. This file lives
at `.traces/features/veille-agents-list/plan.md`.

---

## Goal

Add a Veille-facing Agents surface that combines:

- stored `AgentActor` records
- static built-in workflow agents used by the app

while preserving the existing grant card analysis preview in the Grants UI.

The new surface must be powered by a reusable frontend component named
`ntx-agents` that:

- lives in `packages/n3tx-agents/src/n3tx_agents/static/components/`
- extends `NTTList` from `ntx-list.js`
- can render normal stored `AgentActor` records
- can also render app-provided static agent entries

In Veille, the built-in static entries must cover at least:

- the pipeline-running agent flow
- the grant-analysis agent flow

---

## Corrected User Intent

These decisions are fixed for this plan unless the user explicitly changes them.

| Topic | Decision |
|------|----------|
| Grant cards | keep the analysis preview directly in Grants |
| Agents work | agents list is an addition, not a replacement for grant preview |
| New component name | `ntx-agents` |
| Component location | `packages/n3tx-agents/src/n3tx_agents/static/components/` |
| Base class | extend `NTTList` rather than `ListElement` directly |
| Veille scope | show both stored `AgentActor` rows and static built-in agents |
| Static built-ins | include pipeline execution and grant analysis |
| Static built-ins behavior | treat them as workflow launch entries, not fake editable DB records |
| Wave 1 source of static entries | app-provided catalog, not automatic global discovery |

Anything that removes the grant analysis preview from the grant cards is wrong.

---

## Non-Goals For This Wave

- do not turn `Run` or `Grant` into `AgentActor` records
- do not persist static built-in agent entries in the database
- do not make static built-in entries editable through CRUD forms
- do not globally replace every `AgentActor` list route in every app unless the
  app explicitly opts into `ntx-agents`
- do not redesign Veille's run panel or grant analysis flow itself
- do not auto-discover every `schema.agent.enabled` model across the entire app
  in wave 1

---

## Required Reading Order

Before making code changes, read these files in this order:

1. `/workspace/docs/ARCHITECTURE.md`
2. `/workspace/docs/AGENTS.md`
3. `/workspace/docs/frontend/COMPONENTS.md`
4. `/workspace/FRONTEND.md`
5. `/workspace/BACKEND.md`
6. `/workspace/packages/n3tx-agents/docs/agent-actor.md`
7. `/workspace/packages/n3tx-ui/docs/components.md`
8. `/workspace/packages/n3tx-agents/src/n3tx_agents/actor.py`
9. `/workspace/packages/n3tx-agents/src/n3tx_agents/schema_ext.py`
10. `/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agent.js`
11. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ListElement.js`
12. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-list.js`
13. `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js`
14. `/workspace/packages/n3tx-core/src/n3tx_core/static/core/Router.js`
15. `/workspace/apps/veille/main.py`
16. `/workspace/apps/veille/models/grant.py`
17. `/workspace/apps/veille/models/run.py`
18. `/workspace/apps/veille/static/index.html`
19. `/workspace/apps/veille/static/components/ntx-grant-item.js`
20. `/workspace/apps/veille/tests/test_grant_item_edit.mjs`
21. `/workspace/apps/veille/tests/test_agents_sidebar_route.mjs`
22. `/workspace/apps/veille/tests/test_agents_sidebar_expand.mjs`
23. `/workspace/apps/veille/tests/test_agents_sidebar_label.mjs`
24. `/workspace/apps/veille/tests/sidebar_agents_helpers.mjs`
25. `/workspace/tests/frontend/tests/components/ntx-sidebar.test.js`

Do not start by changing `Grant` semantics or by faking static agents as stored
rows. The requested feature is a hybrid agents surface, not a model rewrite.

---

## Current State Summary

### 1. Grant cards already own the analysis preview

`apps/veille/static/components/ntx-grant-item.js` currently renders an analysis
preview in `md()` and full markdown reasoning in `lg()`.

This is the correct product behavior for Veille. The earlier local edit that
removed the md preview was a mistake and must be reversed first.

### 2. Veille already has two kinds of agent-capable things

Stored dynamic agents:

- `AgentActor` in `packages/n3tx-agents/src/n3tx_agents/actor.py`
- registered in `apps/veille/main.py`
- seeded in `apps/veille/seed.py` as `Veille Scout`

Static built-in workflow agents:

- `Run` in `apps/veille/models/run.py` with `__agent__`
- `Grant` in `apps/veille/models/grant.py` with `__agent__`

Those static built-ins are real agent-capable models, but they are not stored
as agent records in the `agents` table.

### 3. The current Veille sidebar only shows stored `AgentActor` rows

`apps/veille/static/index.html` currently declares:

```html
<ntx-list model="AgentActor" sidebar-label="Agents"></ntx-list>
```

That means the current Agents entry exposes only the `AgentActor` collection.
It does not represent the pipeline runner or grant analyzer as first-class UI
entries.

### 4. Sidebar expansion currently hardcodes `ntx-list`

`packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js` currently lazy-
creates `ntx-list` inside `#ensureList()` when a model section expands.

That prevents a custom model list component such as `ntx-agents` from being used
for the expanded section, even though top-level route templates already support
custom tags.

### 5. Router support for custom list tags already exists

`packages/n3tx-core/src/n3tx_core/static/core/Router.js` already accepts a
custom `view` param and resolves it to `ntx-<view>`.

That means the main missing piece is not route resolution. The main missing
piece is:

- a real `ntx-agents` component
- sidebar expansion support for custom model-list tags
- Veille app config for static built-in entries

---

## Target User-Facing Behavior

### Agents main view

When the user opens the Agents section in Veille, they should see a single
Agents surface composed of two sections:

1. Built-in Agents
2. Stored Agents

### Built-in Agents section

This section must show workflow cards for static agent-backed behavior that is
part of the app, not part of the `AgentActor` table.

Initial Veille entries:

- Pipeline Agent
  - purpose: launch and monitor the run pipeline
  - navigation target: Veille dashboard / run panel
- Grant Analysis Agent
  - purpose: explain that analysis is run per grant and take the user to the
    Grants surface
  - navigation target: Grants list

These cards are not CRUD records. They are workflow launchers.

### Stored Agents section

This section must continue rendering real `AgentActor` records using the normal
stored data flow and the existing `ntx-agent` item renderer.

### Sidebar dropdown behavior

When the Agents section is expanded in the sidebar, the user should still get a
compact dropdown-like view, but it must be powered by `ntx-agents` rather than a
hardcoded `ntx-list` shell.

### Grants behavior

Grant cards must continue to show the analysis preview excerpt directly in the
grant cards. The new Agents surface must not remove or relocate that preview.

---

## Architectural Decisions

### 1. `ntx-agents` is package-owned but app-configurable

Add a framework-package component in `n3tx-agents`, not in the Veille app.

Reason:

- the stored-agent rendering concern is generic
- the hybrid list pattern is reusable
- package statics are already auto-mounted by the backend

But do not bake Veille's built-in entries into the package itself.

### 2. Static built-ins come from an app-provided catalog

Wave 1 default contract:

- `ntx-agents` accepts `catalog="veille"`
- it reads `window.NTX_AGENT_CATALOGS?.veille`

Reason:

- Veille's static built-ins are product-specific workflow entries
- generic schema discovery cannot infer the intended UX copy or navigation
  targets for those entries
- this keeps the package reusable without hardcoding Veille logic into it

### 3. `ntx-agents` extends `NTTList`, but owns a custom render tree

The component should inherit the collection lifecycle, model bootstrapping, and
pagination semantics from `NTTList`, but it should not try to force static
entries into `this.value`.

Expected implementation shape:

- reuse the normal stored `AgentActor` list flow for dynamic entries
- add a separate static section rendered from the app catalog
- render the two sections in one composed component

### 4. Static built-ins are workflow launchers, not fake refs

Do not invent synthetic refs like `Run/static-pipeline-agent`.

Instead, static entries should carry explicit navigation information such as:

- route to Veille home / dashboard
- route to `Grant` list

### 5. Sidebar expansion must honor declared template tags

`ntx-sidebar` should stop assuming every expandable model section is backed by
`ntx-list`.

If the route template for a model is `ntx-agents`, the expanded section should
instantiate `ntx-agents` and forward the relevant attrs.

### 6. Keep `AgentActor.__ui__.renderer.list` unchanged in wave 1

Do not globally change `AgentActor` schema defaults yet.

Veille will opt into `ntx-agents` via its route template in
`apps/veille/static/index.html`. This keeps the hybrid behavior app-specific
while the component remains reusable.

---

## File-By-File Implementation Plan

## 1. Restore the mistaken grant preview removal

### File

- `/workspace/apps/veille/static/components/ntx-grant-item.js`
- `/workspace/apps/veille/tests/test_grant_item_edit.mjs`

### Required change

Reverse the mistaken local edit so that:

- `md()` again renders the `Analysis` preview block
- the reasoning preview helper is restored
- the test asserts that the default md display includes the preview rather than
  asserting its absence

This is not optional. It is the first corrective step before adding the new
agents surface.

---

## 2. Add the new package component

### Files to add

- `/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agents.js`
- `/workspace/packages/n3tx-agents/src/n3tx_agents/static/components/ntx-agents.css`

### Component responsibilities

`ntx-agents.js` should:

- extend `NTTList`
- accept normal list attrs such as `model`, `router`, `display`, `headless`,
  and `sidebar-dropdown`
- accept a new optional `catalog` attr
- read static built-ins from `window.NTX_AGENT_CATALOGS?.[catalog] || []`
- render a Built-in Agents section when the catalog is non-empty
- render a Stored Agents section from the normal `this.value` collection
- use `this.createChild(addr)` for stored entries so existing `ntx-agent`
  rendering continues to work

### Expected static catalog shape

Recommended wave 1 shape:

```js
window.NTX_AGENT_CATALOGS = {
  veille: [
    {
      id: 'pipeline',
      title: 'Pipeline Agent',
      summary: 'Runs the source-to-grant pipeline and orchestrates analysis.',
      icon: 'veille-execute',
      route: '',
      cta: 'Open Pipeline',
      kind: 'built-in',
    },
    {
      id: 'grant-analysis',
      title: 'Grant Analysis Agent',
      summary: 'Evaluates each grant from the Grants workflow rather than as a standalone record.',
      icon: 'veille-analyze',
      route: 'grants',
      cta: 'Open Grants',
      kind: 'built-in',
    },
  ],
};
```

The component should not mutate this catalog. It is configuration.

### Render behavior

For normal page mode:

- show section headers
- static built-ins render as compact cards with title, summary, and CTA
- stored agents render in the usual grid/list layout using the inherited list
  child flow

For `sidebar-dropdown` mode:

- use a compact section layout
- built-ins render as compact links or rows
- stored agents render as compact rows using the existing sidebar item tag flow

### Navigation behavior

The component should reuse router navigation patterns already used in the shell.

Preferred rule:

- if a static entry has a `route` string, dispatch `NAVIGATE` to the configured
  router with that route
- if no router is configured, fall back to `window.location.hash`

This keeps static entries aligned with the rest of the shell.

---

## 3. Update sidebar expansion to support custom list tags

### File

- `/workspace/packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js`

### Required change

Generalize `#ensureList()` so it instantiates the route template tag for the
model section instead of always hardcoding `ntx-list`.

### Required behavior

For a model section:

1. read the template from `#routeTemplates`
2. create the declared tag if one exists, otherwise fall back to `ntx-list`
3. forward template attrs
4. always set the model name
5. forward `router`
6. set dropdown-friendly attrs such as `sidebar-dropdown` and `headless`
7. preserve the current `ntx-list` defaults for `item-tag="ntx-sidebar-link-item"`
   and `item-display="sm"` when the mounted tag is plain `ntx-list`
8. allow custom components like `ntx-agents` to interpret dropdown attrs in
   their own render logic

### Important compatibility rule

This must not break existing sidebar behavior for:

- plain `ntx-list` model sections
- `ntx-table` route templates
- singleton `ntx-item` entries

---

## 4. Opt Veille into the new custom agents surface

### File

- `/workspace/apps/veille/static/index.html`

### Required changes

1. Add modulepreload/imports for `ntx-agents.js`
2. Replace the existing Agents route template:

```html
<ntx-list model="AgentActor" sidebar-label="Agents"></ntx-list>
```

with:

```html
<ntx-agents model="AgentActor" sidebar-label="Agents" catalog="veille"></ntx-agents>
```

3. Declare the Veille static catalog on `window.NTX_AGENT_CATALOGS`

### Important integration rule

Do not merge the catalog into `window.NTX_THEME_CONFIG`. Keep theme config and
agent catalog config separate.

---

## 5. Tests to add and update

### Veille app tests

Update:

- `/workspace/apps/veille/tests/test_grant_item_edit.mjs`
- `/workspace/apps/veille/tests/test_agents_sidebar_route.mjs`
- `/workspace/apps/veille/tests/test_agents_sidebar_expand.mjs`

Expected new assertions:

- grant md display includes the analysis preview again
- Veille sidebar route template for Agents is `ntx-agents`
- expanding the Agents section mounts `ntx-agents` rather than `ntx-list`

Keep:

- `/workspace/apps/veille/tests/test_agents_sidebar_label.mjs`

### New frontend component tests

Add:

- `/workspace/tests/frontend/tests/components/ntx-agents.test.js`

Cover at least:

- renders built-in entries from `window.NTX_AGENT_CATALOGS`
- renders stored entries from the inherited list flow
- behaves sensibly when `catalog` is absent or empty
- respects `sidebar-dropdown`
- dispatches navigation for built-in entry clicks when `router` is configured

### Update generic sidebar tests

Update:

- `/workspace/tests/frontend/tests/components/ntx-sidebar.test.js`

Add coverage that a custom model route template can be expanded into its own tag
instead of always producing `ntx-list`.

---

## 6. Documentation updates required after implementation

Update the relevant docs once the implementation lands:

- `/workspace/docs/AGENTS.md`
- `/workspace/docs/frontend/COMPONENTS.md`
- `/workspace/packages/n3tx-ui/docs/components.md`
- `/workspace/packages/n3tx-agents/docs/agent-actor.md`

Documentation should describe:

- what `ntx-agents` is
- that it extends `NTTList`
- the app-catalog contract for static built-ins
- the new sidebar ability to expand custom model list tags

---

## Implementation Sequence

Execute in this order:

1. Restore the grant preview mistake in `ntx-grant-item.js` and its test
2. Implement `ntx-agents.js` and `ntx-agents.css`
3. Generalize `ntx-sidebar.js` custom list expansion
4. Wire Veille `index.html` to use `ntx-agents` with a `veille` catalog
5. Update Veille sidebar tests
6. Add frontend tests for `ntx-agents` and the sidebar custom-tag expansion
7. Run targeted test suites
8. Update docs

Do not start by editing docs or by changing `AgentActor` schema defaults.

---

## Verification Commands

At minimum, run the most relevant targeted suites:

```bash
node --test apps/veille/tests/test_grant_item_edit.mjs
node --test apps/veille/tests/test_agents_sidebar_route.mjs
node --test apps/veille/tests/test_agents_sidebar_expand.mjs
node --test apps/veille/tests/test_agents_sidebar_label.mjs
cd /workspace/tests/frontend && npx vitest run tests/components/ntx-sidebar.test.js tests/components/ntx-agents.test.js
```

If one of the existing Veille sidebar tests depends on minimal helper imports,
update the helper or test harness instead of weakening the assertions.

---

## Risks And Guardrails

### Risk 1: confusing static built-ins with stored records

Guardrail:

- do not give static built-ins fake refs or CRUD affordances
- make their CTA and copy clearly workflow-oriented

### Risk 2: breaking plain sidebar model expansion

Guardrail:

- preserve the current `ntx-list` fallback path
- add explicit tests for both plain `ntx-list` and custom `ntx-agents`

### Risk 3: accidentally removing the grant preview again

Guardrail:

- restore the positive test for the preview and keep it in the Veille suite

### Risk 4: over-generalizing wave 1

Guardrail:

- use the app-catalog contract now
- defer global schema-based static agent discovery to a future feature if it is
  still needed

---

## Final Deliverable

When this plan is fully implemented, Veille should have:

- the original grant analysis preview still visible in grant cards
- a new Agents surface powered by `ntx-agents`
- both stored `AgentActor` entries and static built-in workflow agents in that
  surface
- sidebar expansion that honors custom list components instead of forcing
  `ntx-list`

That is the intended feature. Anything less is incomplete.
