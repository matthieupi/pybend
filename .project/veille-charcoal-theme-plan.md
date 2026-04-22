# Veille Charcoal Theme Alignment Plan

## Goal

Bring `apps/veille/static/index.html` much closer to `.project/design/charcoal-theme.html` while preserving the framework boundary:

- framework CSS owns **structure + shared semantic tokens + defaults**
- `apps/veille/static/industrial-theme.css` owns the **actual charcoal/industrial values**
- Veille app CSS owns **layout/composition**, but should consume tokens instead of hard-coded visual values

This plan is screenshot-informed. Reference captures live in `.project/screenshots/`.

---

## Screenshot-verified gaps

### 1. Shell geometry

The mockup reads as:

- `16rem` fixed sidebar
- `4rem` fixed topbar
- one continuous dashboard canvas
- hero + contiguous 3-up metrics strip + `12-col` main grid with `8 / 4` split

Veille currently reads as:

- similar sidebar width and topbar height
- hero includes an extra right-side health card
- metrics are broken into separate rounded cards plus chart
- feed sits too low and too weak in hierarchy
- launcher / forecast / history / FAB dilute the first-screen silhouette

### 2. Shape language

The mockup is almost completely:

- zero-radius
- divider-led
- flat-fill
- grayscale

Veille still has:

- rounded shells
- rounded tags
- circular icon wells
- circular CTA buttons
- gradient highlights / soft glows

### 3. Typography hierarchy

The mockup uses a very disciplined hierarchy:

- oversized white display title
- tiny uppercase metadata labels
- bold but compact section headings
- restrained body copy

Veille is close on the title, but looser elsewhere:

- more body copy in cards
- weaker tiny-label rhythm
- several secondary blocks competing with the hero

---

## Core design rule

When converting framework surfaces, prefer this order:

1. use an existing global semantic token if it expresses the role clearly
2. add a new **global semantic token** if the role is broadly reusable
3. add a **component-specific variable** only if the concern is truly structural or behavioral

Avoid introducing narrowly scoped appearance vars like:

- `--ntx-stream-entry-border`
- `--ntx-item-card-shadow`
- `--ntx-item-card-border`

Prefer a shared taxonomy like:

- `--ntx-border-strong`
- `--ntx-border-subtle`
- `--ntx-border-active`
- `--ntx-surface-base`
- `--ntx-surface-raised`
- `--ntx-surface-hover`
- `--ntx-shadow-subtle`
- `--ntx-shadow-strong`
- `--ntx-radius-sm`

---

## Target token taxonomy

These tokens should become the shared appearance vocabulary.

### Radius

```css
--ntx-radius-xs
--ntx-radius-sm
--ntx-radius-md
--ntx-radius-lg
```

### Borders

```css
--ntx-border-strong
--ntx-border-default
--ntx-border-subtle
--ntx-border-muted
--ntx-border-hover
--ntx-border-active
--ntx-border-selected
```

### Surfaces

```css
--ntx-surface-base
--ntx-surface-raised
--ntx-surface-subtle
--ntx-surface-hover
--ntx-surface-selected
--ntx-surface-active
```

### Shadows

```css
--ntx-shadow-subtle
--ntx-shadow-strong
--ntx-shadow-active
```

### Optional app-level Veille tokens

These are acceptable in `industrial-theme.css` if reused only inside Veille:

```css
--ntx-veille-sidebar-rail-width
--ntx-veille-metric-strip-border
--ntx-veille-opportunity-score-bg
--ntx-veille-feed-dot-bg
--ntx-veille-chart-bar-strong
--ntx-veille-chart-bar-muted
```

Use them only when the concept is not general enough to belong in the shared system.

---

## Proposed industrial values

These values are intended to move Veille visibly closer to the mockup.

## `apps/veille/static/industrial-theme.css`

Replace the current softer values with this direction:

```css
html[data-theme="industrial"] {
  --ntx-radius-xs: 0px;
  --ntx-radius-sm: 0px;
  --ntx-radius-md: 0px;
  --ntx-radius-lg: 0px;
  --ntx-radius-xl: 0px;

  --ntx-layout-topbar-height: 4rem;
  --ntx-layout-sidebar-width: 16rem;
  --ntx-layout-page-gutter: 2rem;

  --ntx-color-page: #131313;
  --ntx-color-surface-1: #0e0e0e;
  --ntx-color-surface-2: #1c1b1b;
  --ntx-color-surface-3: #201f1f;
  --ntx-color-surface-4: #2a2a2a;

  --ntx-color-text-strong: #ffffff;
  --ntx-color-text: #e5e2e1;
  --ntx-color-text-muted: #c6c6c6;
  --ntx-color-text-subtle: #919191;

  --ntx-border-muted: rgba(71, 71, 71, 0.12);
  --ntx-border-subtle: rgba(71, 71, 71, 0.2);
  --ntx-border-default: rgba(71, 71, 71, 0.32);
  --ntx-border-strong: rgba(145, 145, 145, 0.52);
  --ntx-border-hover: rgba(145, 145, 145, 0.36);
  --ntx-border-active: rgba(255, 255, 255, 0.72);
  --ntx-border-selected: rgba(255, 255, 255, 0.92);

  --ntx-surface-base: #131313;
  --ntx-surface-raised: #1c1b1b;
  --ntx-surface-subtle: #201f1f;
  --ntx-surface-hover: #2a2a2a;
  --ntx-surface-selected: #2a2a2a;
  --ntx-surface-active: #353534;

  --ntx-shadow-subtle: none;
  --ntx-shadow-strong: 0 6px 16px rgba(0, 0, 0, 0.16);
  --ntx-shadow-active: 0 10px 24px rgba(0, 0, 0, 0.18);

  --ntx-button-primary-bg: #ffffff;
  --ntx-button-primary-fg: #1a1c1c;
  --ntx-button-primary-border: transparent;
  --ntx-button-primary-hover-bg: #f1f1f1;

  --ntx-button-secondary-bg: #201f1f;
  --ntx-button-secondary-fg: #e5e2e1;
  --ntx-button-secondary-border: rgba(71, 71, 71, 0.32);
  --ntx-button-secondary-hover-bg: #2a2a2a;

  --ntx-input-bg: #0e0e0e;
  --ntx-input-fg: #e5e2e1;
  --ntx-input-border: rgba(71, 71, 71, 0.32);
  --ntx-input-placeholder: #919191;
  --ntx-input-focus-border: rgba(255, 255, 255, 0.28);
  --ntx-input-focus-ring: rgba(255, 255, 255, 0.08);
  --ntx-input-shadow: none;

  --ntx-card-bg: var(--ntx-surface-raised);
  --ntx-card-hover-bg: var(--ntx-surface-hover);
  --ntx-panel-bg: var(--ntx-surface-raised);
  --ntx-panel-strong-bg: var(--ntx-surface-base);
  --ntx-topbar-bg: #131313;
  --ntx-topbar-border: rgba(71, 71, 71, 0.12);
  --ntx-topbar-shadow: none;
  --ntx-sidebar-bg: #1c1b1b;
  --ntx-sidebar-overlay-bg: rgba(13, 14, 18, 0.76);

  --ntx-page-background: linear-gradient(180deg, #131313 0%, #131313 100%);
  --ntx-page-atmosphere: none;
  --ntx-page-grid: none;
}
```

### Why these values

- `#131313 / #1c1b1b / #201f1f / #2a2a2a` tracks the mockup much better than the current more cinematic gradient-heavy stack
- all radii at `0px` is required for a visible match
- shadows should be minimal; the mockup derives depth from contrast and separators, not glow
- the primary button should become flat white, not gradient white

---

## Framework implementation details

## 1. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-item.css`

### Current problem

`md/lg/xl` cards currently encode a rounded, borderless, soft-card language.

### Required changes

Replace direct appearance assumptions with shared tokens.

### Target code shape

```css
.card[data-display="md"],
.card[data-display="lg"],
.card[data-display="xl"] {
  background: var(--ntx-card-bg, var(--ntx-surface-raised, #ffffff));
  border: var(--ntx-border-width, 1px) solid var(--ntx-item-card-border, var(--ntx-border-subtle, transparent));
  border-radius: var(--ntx-item-card-radius, var(--ntx-radius-lg, 16px));
  box-shadow: var(--ntx-item-card-shadow, var(--ntx-shadow-subtle, none));
}

.card[data-display="md"]:hover,
.card[data-display="lg"]:hover,
.card[data-display="xl"]:hover {
  background: var(--ntx-card-hover-bg, var(--ntx-surface-hover, #ffffff));
  border-color: var(--ntx-item-card-hover-border, var(--ntx-border-hover, transparent));
  box-shadow: var(--ntx-item-card-hover-shadow, var(--ntx-shadow-strong, none));
}
```

### Keep local / component-specific

- `--ntx-item-card-padding-md`
- `--ntx-item-card-padding-lg`
- `--ntx-item-card-padding-xl`

These are structural display-mode concerns, not global appearance tokens.

### Industrial values to set in theme

```css
--ntx-item-card-border: rgba(71, 71, 71, 0.2);
--ntx-item-card-hover-border: rgba(71, 71, 71, 0.32);
--ntx-item-card-radius: 0px;
--ntx-item-card-shadow: none;
--ntx-item-card-hover-shadow: none;
```

---

## 2. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-method.css`

### Current problem

Method controls still default toward rounded, polished buttons.

### Required changes

Map button appearance to shared tokens.

### Target code shape

```css
.method-btn {
  border: 1px solid var(--ntx-method-button-border, var(--ntx-border-default, rgba(190,200,201,.85)));
  border-radius: var(--ntx-method-button-radius, var(--ntx-radius-sm, 10px));
  background: var(--ntx-method-button-bg, var(--ntx-button-secondary-bg, #fff));
  color: var(--ntx-method-button-fg, var(--ntx-color-text, #344041));
  box-shadow: var(--ntx-method-button-shadow, var(--ntx-shadow-subtle, none));
}

.method-btn:hover {
  border-color: var(--ntx-method-button-hover-border, var(--ntx-border-hover, rgba(20,105,109,.28)));
  background: var(--ntx-method-button-hover-bg, var(--ntx-surface-hover, #f2f4f5));
  box-shadow: var(--ntx-method-button-hover-shadow, var(--ntx-shadow-subtle, none));
}

.method-btn--labeled {
  border-radius: var(--ntx-method-labeled-radius, var(--ntx-radius-sm, 6px));
  border: 1px solid var(--ntx-method-labeled-border, transparent);
  background: var(--ntx-button-primary-bg, #fff);
  box-shadow: var(--ntx-method-labeled-shadow, none);
}
```

### Keep local / component-specific

- `--ntx-method-button-height`
- `--ntx-method-button-width`
- `--ntx-method-button-gap`
- `--ntx-method-button-padding`

### Industrial values to set in theme

```css
--ntx-method-button-radius: 0px;
--ntx-method-button-border: rgba(71, 71, 71, 0.32);
--ntx-method-button-shadow: none;
--ntx-method-button-hover-shadow: none;
--ntx-method-labeled-radius: 0px;
--ntx-method-labeled-border: transparent;
--ntx-method-labeled-shadow: none;
```

---

## 3. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.css`

### Current problem

Topbar controls read too rounded and too “app-shell”, especially:

- sidebar toggle
- user pill
- dropdown
- tag chip

### Required changes

Use shared tokens for borders, surfaces, shadows, radii, and keep blur local.

### Target code shape

```css
.sidebar-toggle,
.signin-link,
.user-pill,
.topbar-tag,
.user-dropdown {
  border-radius: var(--ntx-topbar-control-radius, var(--ntx-radius-sm, 10px));
}

.user-dropdown {
  border: 1px solid var(--ntx-topbar-dropdown-border, var(--ntx-border-subtle, transparent));
  background: var(--ntx-topbar-dropdown-bg, var(--ntx-surface-raised, #fff));
  box-shadow: var(--ntx-topbar-dropdown-shadow, var(--ntx-shadow-strong, none));
}

.topbar {
  backdrop-filter: blur(var(--ntx-topbar-backdrop-blur, var(--ntx-glass-blur-sm, 12px)));
}
```

### Keep local / component-specific

- `--ntx-topbar-backdrop-blur`

### Industrial values to set in theme

```css
--ntx-topbar-control-radius: 0px;
--ntx-topbar-dropdown-border: rgba(71, 71, 71, 0.2);
--ntx-topbar-dropdown-bg: #1c1b1b;
--ntx-topbar-dropdown-shadow: none;
--ntx-topbar-backdrop-blur: 0px;
```

---

## 4. `packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.css`

### Current problem

The sidebar still contains framework-native softness:

- hover translate
- hover shadow
- icon motion
- selected state not strong enough for the mockup

### Required changes

Use shared tokens for the row appearance. Keep mechanics local.

### Target code shape

```css
.model-header {
  padding: var(--ntx-sidebar-item-padding, 0.75rem 1.5rem);
  border-radius: var(--ntx-sidebar-item-radius, var(--ntx-radius-sm, 10px));
  background: var(--ntx-sidebar-item-bg, transparent);
  box-shadow: var(--ntx-sidebar-item-shadow, none);
}

.model-header:hover,
.model-header:focus-visible {
  background: var(--ntx-sidebar-item-hover-bg, var(--ntx-surface-hover, rgba(20,105,109,.08)));
  box-shadow: var(--ntx-sidebar-item-hover-shadow, none);
  transform: var(--ntx-sidebar-item-hover-transform, none);
}

.model-section--selected > .model-header,
.sidebar-link--selected .model-header {
  background: var(--ntx-sidebar-item-selected-bg, var(--ntx-surface-selected, rgba(20,105,109,.1)));
  box-shadow: var(--ntx-sidebar-item-selected-shadow, none);
}

.model-header::before {
  width: var(--ntx-sidebar-item-selected-rail-width, 0.22rem);
  background: var(--ntx-sidebar-item-selected-rail-color, var(--ntx-border-selected, #fff));
}
```

### Keep local / component-specific

- `--ntx-sidebar-item-padding`
- `--ntx-sidebar-item-hover-transform`
- `--ntx-sidebar-item-selected-rail-width`
- `--ntx-sidebar-close-radius`

### Industrial values to set in theme

```css
--ntx-sidebar-item-padding: 0.95rem 1.5rem;
--ntx-sidebar-item-radius: 0px;
--ntx-sidebar-item-hover-transform: none;
--ntx-sidebar-item-hover-shadow: none;
--ntx-sidebar-item-hover-bg: #2a2a2a;
--ntx-sidebar-item-selected-bg: #2a2a2a;
--ntx-sidebar-item-selected-shadow: none;
--ntx-sidebar-item-selected-rail-width: 2px;
--ntx-sidebar-item-selected-rail-color: rgba(255,255,255,.92);
--ntx-sidebar-close-radius: 0px;
```

---

## 5. `packages/n3tx-agents/src/n3tx_agents/static/components/ntx-stream-agent.css`

### Current problem

Agent output still reads like soft chat cards.

### Required changes

Use shared tokens for entry shells and keep only entry-type accent rails local.

### Target code shape

```css
.entry-content {
  padding: 0.85rem 0.95rem;
  border: 1px solid var(--ntx-stream-entry-border, var(--ntx-border-subtle, rgba(255,255,255,.08)));
  border-radius: var(--ntx-stream-entry-radius, var(--ntx-radius-sm, 10px));
  background: var(--ntx-stream-entry-bg, var(--ntx-surface-raised, rgba(15,22,38,.92)));
}

.entry-thinking .entry-content { border-left: 2px solid var(--ntx-stream-entry-thinking-rail, var(--ntx-status-success-fg)); }
.entry-tool-call .entry-content { border-left: 2px solid var(--ntx-stream-entry-tool-rail, var(--ntx-status-warning-fg)); }
.entry-text-output .entry-content { border-left: 2px solid var(--ntx-stream-entry-text-rail, var(--ntx-color-accent)); }
.entry-error .entry-content { border-left: 2px solid var(--ntx-stream-entry-error-rail, var(--ntx-status-error-fg)); }
```

### Keep local / component-specific

- rail colors for thinking/tool/text/error

### Industrial values to set in theme

```css
--ntx-stream-entry-border: rgba(71, 71, 71, 0.2);
--ntx-stream-entry-radius: 0px;
--ntx-stream-entry-bg: #1c1b1b;
--ntx-stream-entry-code-bg: #0e0e0e;
```

---

## Veille app implementation details

## 1. `apps/veille/static/components/ntx-run-panel.js`

### Target dashboard structure

The first screen should become:

```text
Hero
Metrics strip (3-up contiguous)
Main 12-col grid
  left 8 cols:
    opportunities section
    chart panel
  right 4 cols:
    feed/timeline panel
Lower section(s)
  launcher
  archive/history
```

### Required markup changes

#### Hero
- keep kicker
- keep main title
- keep statusline
- **remove `dashboard-health-card` from the hero**

#### Metrics strip
Replace the current `dashboard-metrics-grid` content with three contiguous cells:

1. tracked opportunities
2. active sources
3. system status / pipeline health

The chart should move below into the left `8-col` area.

#### Main grid
Change from current stacked layout to:

```html
<section class="dashboard-main-grid">
  <div class="dashboard-main-left">
    <section class="dashboard-section dashboard-section--opportunities">...</section>
    <section class="dashboard-chart-panel">...</section>
  </div>
  <aside class="dashboard-feed-panel">...</aside>
</section>
```

#### Lower hierarchy
- move `run-launcher` below the main grid
- move `dashboard-history` below launcher
- remove `dashboard-insight-card` from the first-screen composition
- remove or demote `veille-fab`

### Concrete layout targets

```css
.dashboard-main-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 2rem;
}

.dashboard-main-left { grid-column: span 8; }
.dashboard-feed-panel { grid-column: span 4; }
```

At `<= 1080px`, collapse to single column.

---

## 2. `apps/veille/static/veille.css`

### Primary structural changes

#### Hero

Target values:

```css
.dashboard-hero {
  display: block;
  margin-bottom: 3rem;
}

.dashboard-kicker {
  font-size: 10px;
  letter-spacing: 0.4em;
  opacity: 0.4;
}

.run-launcher-title {
  font-size: clamp(4.2rem, 6vw, 4.8rem);
  line-height: 0.92;
  letter-spacing: -0.07em;
}
```

#### Metrics strip

Replace rounded cards with one flat strip:

```css
.dashboard-metrics-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border: 1px solid var(--ntx-border-muted);
  background: var(--ntx-surface-raised);
}

.dashboard-metric-cell {
  min-height: 9.5rem;
  padding: 2rem;
  border-right: 1px solid var(--ntx-border-muted);
}

.dashboard-metric-cell:last-child {
  border-right: 0;
}
```

#### Opportunities section

The screenshot gap here is large. Make these changes:

- outer section container should be much flatter and less dominant
- cards should become square
- circular icon wells removed
- score chip becomes rectangular and small
- CTA becomes flat inline/square, not circular

Target values:

```css
.dashboard-opportunity-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1.5rem;
}

.dashboard-opportunity-card {
  padding: 0;
  border: 1px solid var(--ntx-border-subtle);
  border-radius: 0;
  background: var(--ntx-surface-raised);
}

.dashboard-opportunity-inner {
  padding: 1.5rem;
  border-radius: 0;
  background: var(--ntx-surface-raised);
}

.dashboard-opportunity-badge {
  min-height: 1.45rem;
  padding: 0 0.45rem;
  border-radius: 0;
}

.dashboard-opportunity-link {
  width: 2rem;
  height: 2rem;
  border-radius: 0;
}
```

#### Feed panel

Make it read as a dominant right rail:

```css
.dashboard-feed-panel {
  min-height: 39rem;
  border: 1px solid var(--ntx-border-muted);
  border-radius: 0;
  background: var(--ntx-surface-raised);
}

.dashboard-feed-item {
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.9rem;
  padding: 1.35rem 0;
  border-top: 1px solid var(--ntx-border-muted);
}
```

Timestamps should sit as tiny muted metadata, not a third dominant column.

#### Remove or flatten decorative treatments

Delete or neutralize:

- radial highlight overlays on card `::before`
- status-dot glow halo
- opportunity gradient frame
- insight-art gradients
- FAB lift/shadow emphasis

### Literal-to-token replacements required in `veille.css`

Replace direct values such as:

- `border-radius: 999px`
- `background: linear-gradient(...)`
- `box-shadow: var(--ntx-shadow-sm)` where the surface should be flat

with tokens or flat values from `industrial-theme.css`.

---

## 3. `apps/veille/static/components/ntx-grant-item.css`

### Required changes

- `.grant-status` -> rectangular tag
- action controls -> square / flatter
- reduce card softness inherited from framework item shell

### Target values

```css
.grant-status {
  padding: 0.25rem 0.45rem;
  border-radius: 0;
}

.grant-open-link {
  width: 1.2rem;
  height: 1.2rem;
}
```

### Copy density

Clamp secondary text more aggressively so the list reads closer to the mockup’s denser cards.

---

## 4. `apps/veille/static/components/ntx-run-item.css`

### Required changes

- `.run-type`, `.run-status` -> rectangular tags
- `.run-report-link` -> flat white or flat dark button depending on action hierarchy
- `.run-error` -> square shell

### Target values

```css
.run-type,
.run-status {
  padding: 0.24rem 0.5rem;
  border-radius: 0;
}

.run-report-link {
  padding: 0.75rem 1rem;
  border-radius: 0;
  background: var(--ntx-button-primary-bg);
  box-shadow: none;
}

.run-error {
  border-radius: 0;
}
```

---

## 5. `apps/veille/static/components/ntx-run-output.css`

### Required changes

- `.ro-progress`, `.ro-source-card`, `.ro-analysis-card` -> square shells
- progress bar ends -> square
- badges and pills -> rectangular tags
- active-state elevation reduced

### Target values

```css
.ro-progress,
.ro-source-card,
.ro-analysis-card,
.ro-error {
  border-radius: 0;
  box-shadow: none;
}

.ro-progress-bar,
.ro-source-count,
.ro-analysis-badge,
.ro-grant-pill {
  border-radius: 0;
}

.ro-source-active {
  box-shadow: none;
  border-color: var(--ntx-border-default);
}
```

---

## 6. `apps/veille/static/components/ntx-run-report.css`

### Required changes

- report panel shell -> square
- report grant cards -> square and flatter
- all pills / badges -> rectangular tags

### Target values

```css
.panel,
.grant-card {
  border-radius: 0;
  box-shadow: none;
}

.status-badge,
.type-pill,
.score-pill,
.section-count {
  min-height: 1.4rem;
  padding: 0 0.45rem;
  border-radius: 0;
}
```

---

## Concrete rollout order

## Phase 1 — shared theme groundwork

1. update `industrial-theme.css` values
2. add any missing shared semantic tokens there

## Phase 2 — framework tokenization

3. update `ntx-item.css`
4. update `ntx-method.css`
5. update `ntx-topbar.css`
6. update `ntx-sidebar.css`
7. update `ntx-stream-agent.css`

## Phase 3 — dashboard restructure

8. refactor `ntx-run-panel.js` hero / metrics / main grid
9. refactor `veille.css` to match the new layout

## Phase 4 — surface normalization

10. update `ntx-grant-item.css`
11. update `ntx-run-item.css`
12. update `ntx-run-output.css`
13. update `ntx-run-report.css`

## Phase 5 — final sweep

14. remove stale literals and decorative treatments
15. re-capture screenshots for comparison

---

## Verification plan

## Visual verification

Re-capture these after implementation and compare against `.project/screenshots/charcoal-*.png`:

- full dashboard
- sidebar
- topbar
- hero
- metrics
- main-left opportunities/chart
- feed panel

## Browser checks

```bash
cd /workspace/tests/frontend && npx vitest run
cd /workspace/tests/frontend && npx playwright test --config=tests/e2e/playwright.config.js tests/e2e/theme-toggle.spec.js
```

## Manual checklist

- sidebar active state has a visible left rail
- topbar controls are square / flatter
- hero has no competing health card
- metrics are one contiguous strip
- feed is in right rail on desktop
- opportunity cards no longer use circular icon wells or circular CTA buttons
- FAB is removed or visually demoted

---

## Acceptance criteria

The implementation is successful when:

1. Veille’s industrial theme reads as a hard-edged charcoal admin surface, not a rounded premium dark dashboard
2. the first screen matches the mockup’s hierarchy: hero -> metrics strip -> opportunities/chart + right feed
3. the framework remains generic and Veille-specific values live in `industrial-theme.css`
4. app/component CSS consumes shared tokens instead of repeating raw appearance literals
