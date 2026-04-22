# Frontend Static Split — Update to Module Split Plan

## Context

The existing module-split-plan.md places `Actor.js`, `TX.js`, `Matrix.js` in **n3tx-actors** static and everything else in **n3tx-core** static. Analysis of the actual frontend dependency graph shows this doesn't work — `Component.js` (the base for every web component) imports Actor, Matrix, AND TX. `NTT.js` extends Actor and uses Matrix. Every rendered component transitively depends on all three "actor" files.

The frontend needs a different split axis than the backend. The proposal: add **n3tx-ui** as a fourth package that owns the visual layer — all registered web components (`ntx-*.js`), their base classes, the form generator, and widgets. n3tx-actors becomes backend-only (no frontend static).

---

## Package Architecture (Revised)

### Backend packages (unchanged from existing plan)
```
n3tx-agents (Python) → n3tx-actors (Python) → n3tx-core (Python)
```

### Frontend packages (new)
```
n3tx-agents (JS: ntx-chat.js) → n3tx-core (JS: runtime)
                                       ↑
n3tx-ui (JS: components, widgets) ─────┘
```

### Full dependency graph
```
n3tx-core       standalone (Python + JS runtime)
n3tx-actors     depends on n3tx-core (Python only, no frontend static)
n3tx-ui         depends on n3tx-core (JS visual layer, minimal Python)
n3tx-agents     depends on n3tx-core + n3tx-actors (Python) + n3tx-core (JS)
n3tx            meta-package: all four
```

Note: n3tx-ui and n3tx-actors are independent of each other. A Level 3 actor app needs both, but neither depends on the other at the package level.

---

## Frontend File Distribution

### n3tx-core static — Non-visual runtime
The messaging backbone, entity system, transport, and utilities. Everything needed to create entities, route messages, and handle schemas — but nothing that renders to the DOM as a custom element.

```
static/
├── core/
│   ├── Actor.js              # Actor base class (messaging)
│   ├── TX.js                 # Message envelope
│   ├── Matrix.js             # Root actor + singleton
│   ├── NTT.js                # Entity registry + DynamicClass
│   ├── Component.js          # Abstract HTMLElement + Actor bridge
│   ├── Observable.js         # Observer mixin
│   ├── Router.js             # Client-side navigation state
│   ├── Utils.js              # Core utilities
│   └── transport/
│       ├── HTTP.js            # HTTP adapter
│       ├── Socket.js          # WebSocket transport
│       └── NetworkAdapter.js  # Matrix ↔ network bridge
├── utils/
│   ├── Assert.js
│   ├── Logging.js
│   ├── Permissions.js
│   ├── Toast.js
│   ├── DateFormat.js
│   ├── Snippets.js
│   ├── str_utils.js
│   ├── registrar.js
│   └── theme.js
├── config.js
├── schema.html               # Schema viewer (framework doc)
└── n3tx.svg                   # Branding
```

### n3tx-ui static — Visual layer
All registered custom elements, their abstract base classes, the form generator, widgets, themes, and the default index/login/register HTML pages.

```
static/
├── components/
│   ├── NTTElement.js          # Abstract single-entity base (extends Component)
│   ├── ListElement.js         # Abstract collection base (extends Component)
│   ├── ntx-item.js            # Single entity renderer
│   ├── ntx-list.js            # Collection grid
│   ├── ntx-table.js           # Collection table
│   ├── ntx-row.js             # Table row
│   ├── ntx-method.js          # Method call button
│   ├── ntx-stream.js          # Streaming method output
│   ├── ntx-router.js          # Navigation container
│   ├── ntx-modal.js           # Modal overlay
│   ├── ntx-ref-picker.js      # Reference field picker
│   ├── ntx-sidebar.js         # Model navigation sidebar
│   ├── ntx-topbar.js          # Header/nav bar
│   ├── ntx-profile.js         # User profile page
│   └── ntx-user.js            # User display
├── generators/
│   └── form.js                # Formidable (schema → HTML forms)
├── widgets/
│   ├── Widget.js              # Widget base class
│   ├── registry.js            # Widget registry
│   ├── index.js               # Re-exports all widgets
│   ├── UrlWidget.js
│   ├── EmailWidget.js
│   ├── DateWidget.js
│   ├── MarkdownWidget.js
│   ├── ConsoleWidget.js
│   ├── ReferenceWidget.js
│   ├── CurrencyWidget.js
│   └── TextareaWidget.js
├── index.html                 # Default app entry point
├── login.html                 # Default login page
├── register.html              # Default register page
├── dark-theme.css
├── light-theme.css
└── components/*.css           # Component stylesheets
```

### n3tx-agents static — Agent UI
```
static/
├── components/
│   └── ntx-chat.js            # Agent chat panel
```

### n3tx-actors static — None
n3tx-actors is backend-only. Actor.js, TX.js, Matrix.js stay in n3tx-core because they're foundational to the entire frontend (Component.js depends on all three).

---

## Why This Split Works

### The boundary: runtime vs. visual
- **Component.js** is the abstract bridge between Actor (messaging) and HTMLElement (DOM). It stays in core — it's infrastructure, not visual.
- **NTTElement.js** and **ListElement.js** add visual behavior (forms, edit modes, pagination, modals). They're the first layer that renders content → they go to ui.
- All `ntx-*.js` files are registered custom elements → ui.
- **form.js** creates DOM elements and references widgets + ntx-ref-picker → ui.
- **Widgets** are rendering utilities used by components → ui.

### Cross-package imports resolve at runtime
All static directories merge into the same URL namespace via `_mount_static()`. Browser ES module imports like `import Component from '../core/Component.js'` resolve from the merged URL space — the browser doesn't know which package shipped the file. Package boundaries control *distribution*, not *import isolation*.

### Internal dependency analysis

**n3tx-core static imports**: All self-contained. No file in core/ or utils/ imports from components/, generators/, or widgets/.

**n3tx-ui static imports**:
- NTTElement → Component (core), NTT (core), TX (core), Utils (core), Logging (core), Toast (core), Assert (core) — all in core ✓
- ListElement → Component (core), TX (core), Logging (core), Permissions (core), ntx-modal (ui) — ntx-modal in same package ✓
- ntx-item → NTTElement (ui), NTT (core), Formidable (ui), Permissions (core), Widgets (ui), TX (core), ntx-method (ui), ntx-stream (ui) ✓
- form.js → Permissions (core), NTT (core), Logging (core), Widgets (ui), ntx-ref-picker (ui) — within ui ✓
- ntx-ref-picker → NTT (core), config (core), Formidable (ui), TX (core) — within ui ✓

**n3tx-agents static imports**:
- ntx-chat → HTTP (core), config (core), NTT (core) — all in core ✓ (does NOT depend on n3tx-ui)

### No circular dependencies across packages
```
core ← ui (ui imports from core, never reverse)
core ← agents (agents imports from core, never reverse)
ui and agents are independent of each other
```

---

## n3tx-ui Python Package

Minimal Python — just enough to export the static directory path for the discovery mechanism.

```
packages/n3tx-ui/
├── pyproject.toml
└── src/n3tx_ui/
    ├── __init__.py
    └── static/
        └── (all files listed above)
```

```toml
# pyproject.toml
[project]
name = "n3tx-ui"
version = "0.10.0"
dependencies = [
    "n3tx-core>=0.10.0",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
"n3tx_ui" = ["static/**/*"]
```

```python
# n3tx_ui/__init__.py
from pathlib import Path

def get_static_dir():
    """Return path to n3tx-ui static directory."""
    return Path(__file__).parent / "static"
```

---

## Changes to Static Discovery Mechanism

Update `_discover_static_dirs()` in `n3tx_core/api/backend.py` to include n3tx-ui:

```python
def _discover_static_dirs():
    """Discover static directories from all installed n3tx packages."""
    dirs = []
    # Core static (always present)
    core_static = Path(__file__).resolve().parent.parent / "static"
    if core_static.is_dir():
        dirs.append(core_static)

    # Discover from installed packages
    for pkg_name in ('n3tx_ui', 'n3tx_agents'):
        try:
            mod = importlib.import_module(pkg_name)
            pkg_static = Path(mod.__file__).parent / "static"
            if pkg_static.is_dir():
                dirs.append(pkg_static)
        except ImportError:
            pass

    return dirs
```

Mount order (highest to lowest precedence):
1. App-specific static dirs (from `create_app(static_dir=...)`)
2. n3tx-agents static (if installed) — `ntx-chat.js`
3. n3tx-ui static (if installed) — all components, widgets, themes, default HTML
4. n3tx-core static (catch-all) — runtime JS, utils, config

---

## Updates to module-split-plan.md

### Package Layout section
- Add n3tx-ui as new package (section 2.5, between core and actors)
- Remove `static/` section from n3tx-actors (backend-only package)
- Update n3tx-core static to show only runtime files (no components, widgets, generators)
- Update n3tx-agents static to show only ntx-chat.js

### Static File Serving section
- Update `_discover_static_dirs()` to include `n3tx_ui`
- Update mount order to 4 tiers (app > agents > ui > core)

### Migration Steps
- Add Phase 2.5: Move UI files — components, generators, widgets, themes, default HTML pages
- Update Phase 3 to note n3tx-actors has no static directory
- Update Phase 7 static serving to handle 4 package layers

### Resolved Decisions
- Add: "Actor.js/TX.js/Matrix.js → n3tx-core (not n3tx-actors). They're foundational to the entire frontend — Component.js depends on all three."
- Add: "n3tx-actors is backend-only. No frontend static."
- Add: "NTTElement.js/ListElement.js → n3tx-ui (not n3tx-core). They add visual behavior; the runtime/visual boundary is at Component.js."
- Add: "form.js → n3tx-ui. It creates DOM elements and references widgets + ntx-ref-picker."
- Add: "index.html/login.html/register.html → n3tx-ui. Default visual entry points; example apps override."

### Meta-package update
```toml
[project]
name = "n3tx"
version = "0.10.0"
dependencies = [
    "n3tx-core>=0.10.0",
    "n3tx-actors>=0.10.0",
    "n3tx-ui>=0.10.0",
    "n3tx-agents>=0.10.0",
]
```

---

## Verification

### Per-package isolation
```bash
# Core only — no UI, just runtime (useful for headless/API-only apps)
pip install n3tx-core
# Verify: Actor, TX, NTT, Component classes available in JS
# Verify: No 404s for core/ or utils/ files

# Core + UI — full visual layer, no actors or agents
pip install n3tx-ui
# Verify: All ntx-* components render
# Verify: Formidable generates forms
# Verify: Widgets render correctly

# Core + Actors + UI — Level 3 actor routing with UI
pip install n3tx-actors n3tx-ui
# Verify: example_actor app works end to end

# Everything
pip install n3tx
# Verify: example_grants app works (agents + actors + UI)
```

### Import resolution
After static merge, verify in browser DevTools Network tab:
- `./core/Actor.js` resolves from n3tx-core
- `./components/ntx-item.js` resolves from n3tx-ui
- `./components/ntx-chat.js` resolves from n3tx-agents
- No 404s in any example app
