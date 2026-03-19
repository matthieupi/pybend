# N3TX Module Split Plan

## Context

The `expose_route` debug envelope bug revealed a deeper issue: the backend and frontend need to communicate via a unified TX-based wire format, and achieving this cleanly requires the project to be split into composable, independently installable modules. The current monolithic `n3tx` package bundles everything (models, actors, agents, storage, auth, UI) into one install, making it impossible to use the actor system without the full framework or to add agents without pulling in everything.

The goal: split into **n3tx-core** (models, storage, auth, API + JS runtime), **n3tx-actors** (messaging, backend only), **n3tx-ui** (visual components, widgets, themes), and **n3tx-agents** (LLM reasoning). The frontend split axis differs from the backend — Actor.js/TX.js/Matrix.js are foundational to every component and stay in n3tx-core, while the visual layer (registered web components, form generator, widgets) moves to n3tx-ui. Projects install only what they need.

---

## Decision: Actor Package Placement

### Option A: Actors as Separate Package (`n3tx-actors`)

**Structure:**
```
packages/
├── n3tx-core/       # pip install n3tx-core   (Python + JS runtime)
├── n3tx-actors/     # pip install n3tx-actors  (Python only, depends on n3tx-core)
├── n3tx-ui/         # pip install n3tx-ui      (JS visual layer, depends on n3tx-core)
└── n3tx-agents/     # pip install n3tx-agents  (depends on n3tx-core + n3tx-actors)
```

**What moves to n3tx-actors (backend only):**
- `actor.py`, `tx.py`, `matrix.py`, `actor_proxy.py`
- `actor_model.py` (the bridge class)
- Network adapters: `network_adapter.py`, `network_api.py` (includes `create_api_routes()`), `network_ws.py`, `network_mcp.py`, `network_ap.py`
- `auth_interceptor.py`
- No frontend static — Actor.js/TX.js/Matrix.js stay in n3tx-core (see Frontend Split below)

**What moves to n3tx-ui (frontend only):**
- All registered web components (`ntx-*.js`): ntx-item, ntx-list, ntx-table, ntx-row, ntx-method, ntx-stream, ntx-router, ntx-modal, ntx-ref-picker, ntx-sidebar, ntx-topbar, ntx-profile, ntx-user
- Abstract component base classes: `NTTElement.js`, `ListElement.js`
- Form generator: `generators/form.js`
- Widgets: `widgets/` (Widget.js, registry.js, all widget classes)
- Default HTML: `index.html`, `login.html`, `register.html`
- Themes: `dark-theme.css`, `light-theme.css`, component CSS

**What stays in n3tx-core:**
- `descriptors.py` (`fullmethod`/`fullproperty`) — generic descriptors used by both actors and agents
- `routes_fastapi.py` (includes `register_routes()`) — Level 1/2 direct routing
- Frontend JS runtime: Actor.js, TX.js, Matrix.js, NTT.js, Component.js, Observable.js, Router.js, Utils.js, transport/, utils/, config.js

**Import paths:**
```python
from n3tx_actors import Actor, TX, Matrix, ActorProxy
from n3tx_actors import ActorModel
from n3tx_actors.api import NetworkAPI, NetworkWebSocket
```

**Pros:**
- Actor system is genuinely standalone (zero model/storage deps in core actors)
- Projects can use actors without the full framework
- Enforces the messaging boundary architecturally

**Cons:**
- ActorModel needs to import ProtoModel from n3tx-core (cross-package dependency)
- Network adapters need both Actor (from self) AND storage/auth (from n3tx-core)
- `app.py` builder needs conditional imports from n3tx-actors
- 4 packages to manage (with n3tx-ui)
- Actor routing (Level 3) requires BOTH packages

### Option B: Actors as Subpackage in Core

**Structure:**
```
packages/
├── n3tx-core/       # pip install n3tx-core (includes actors)
└── n3tx-agents/     # pip install n3tx-agents (depends on n3tx-core)
```

**Import paths (same as today):**
```python
from n3tx_core.actors import Actor, TX, Matrix
from n3tx_core.models import ActorModel, ProtoModel
from n3tx_core.api import NetworkAPI
```

**Pros:**
- Simpler dependency graph (2 packages, not 3)
- ActorModel bridge stays in same package as both Actor and ProtoModel
- Network adapters naturally access both actor and storage layers
- app.py builder has no conditional imports
- Less migration work

**Cons:**
- Can't install actors without the full core
- Actor system boundary is convention, not enforced by packaging
- Larger core package

### Recommendation: **Option A (Separate Package)**

Rationale: The actor system IS genuinely standalone — the exploration confirmed zero model/storage dependencies in `actor.py`, `tx.py`, `matrix.py`, `actor_proxy.py`. The bridge classes (ActorModel, network adapters) have cross-package deps, but that's normal and expected — they exist precisely to bridge the two systems. The overhead of a 3rd package is minimal (one more `pyproject.toml`) and the architectural clarity is significant. It also enables future use of the actor messaging system in non-N3TX projects.

**Key insight**: `ActorModel` lives in **n3tx-actors** (not n3tx-core), because its primary identity is "a model that IS an actor." It imports ProtoModel from n3tx-core — that's a clean dependency direction (actors depend on core, not the reverse).

---

## Package Layout

### 1. `n3tx-core` — Framework Foundation

```
packages/n3tx-core/
├── pyproject.toml
└── src/n3tx_core/
    ├── __init__.py              # Public API re-exports
    ├── config.py                # Global config (env vars, defaults)
    ├── app.py                   # N3TXApp builder, create_app()
    │
    ├── models/
    │   ├── __init__.py
    │   ├── proto_model.py       # ProtoModel base class
    │   ├── proto_schema.py      # Schema pipeline
    │   ├── proto_dump.py        # Dump/serialization pipeline
    │   ├── storable_mixin.py    # Storage injection
    │   ├── viewable_mixin.py    # Display hints
    │   ├── base_user.py         # BaseUser (login, register, JWT)
    │   └── ref.py               # ListRef[T]
    │
    ├── storage/
    │   ├── __init__.py
    │   ├── abstract_storage.py  # Strategy interface (ABC)
    │   ├── sqlite_storage.py    # SQLite implementation
    │   ├── sqlite_migration.py
    │   ├── sqlite_helpers.py
    │   └── json_storage.py      # JSON file storage
    │
    ├── authorize/               # Fully standalone (zero N3TX imports)
    │   ├── __init__.py
    │   ├── auth.py              # JWT, bcrypt
    │   ├── rules.py             # ANYONE, OWNER, ROLE, etc.
    │   ├── context.py           # AccessContext
    │   ├── resolver.py          # ABAC evaluation
    │   ├── errors.py            # AccessDenied
    │   └── schema.py            # Schema-level rules
    │
    ├── api/
    │   ├── __init__.py
    │   ├── backend.py           # FastAPIBackend, static mounting
    │   ├── routes_fastapi.py    # Level 1/2 direct routes
    │   ├── routes_flask.py      # Flask alternative
    │   ├── discovery.py         # /_meta, /.well-known/agent.json
    │   └── tests/
    │
    ├── utils/
    │   ├── __init__.py
    │   ├── decorators.py        # @expose_route, @schema_extension
    │   ├── registrar.py         # register_model, registered_models
    │   ├── introspection.py     # Type inspection helpers
    │   ├── typer.py             # Ref[T] type system
    │   ├── populate.py          # FK hydration
    │   ├── erroring.py          # Error helpers, MethodError
    │   ├── modeling.py          # Model utilities
    │   ├── scaffold.py          # Model generator
    │   └── generate_docs.py     # Auto-doc generator
    │
    ├── widgets/
    │   ├── __init__.py
    │   ├── widget.py            # Widget base + auto-detection
    │   └── schema_ext.py        # Widget schema pipeline stage
    │
    ├── ssr/
    │   ├── __init__.py
    │   ├── html.py
    │   └── bundler.py
    │
    ├── swagger/
    │   ├── __init__.py
    │   └── swagger_setup.py
    │
    ├── static/                  # JS runtime (non-visual — no components, widgets, or generators)
    │   ├── core/
    │   │   ├── Actor.js         # Actor base class (messaging)
    │   │   ├── TX.js            # Message envelope
    │   │   ├── Matrix.js        # Root actor + singleton
    │   │   ├── NTT.js           # Entity registry + DynamicClass
    │   │   ├── Component.js     # Abstract HTMLElement + Actor bridge
    │   │   ├── Observable.js    # Observer mixin
    │   │   ├── Router.js        # Client-side navigation state
    │   │   ├── Utils.js         # Core utilities
    │   │   └── transport/
    │   │       ├── HTTP.js      # HTTP adapter
    │   │       ├── Socket.js    # WebSocket transport
    │   │       └── NetworkAdapter.js  # Matrix ↔ network bridge
    │   ├── utils/               # Frontend utils (all non-visual)
    │   │   ├── Assert.js
    │   │   ├── Logging.js
    │   │   ├── Permissions.js
    │   │   ├── Toast.js
    │   │   ├── DateFormat.js
    │   │   ├── Snippets.js
    │   │   ├── str_utils.js
    │   │   ├── registrar.js
    │   │   └── theme.js
    │   ├── config.js
    │   ├── schema.html          # Schema viewer (framework doc)
    │   └── n3tx.svg             # Branding
    │
    └── tests/
        ├── unit/                # All current unit tests
        └── conftest.py
```

**pyproject.toml:**
```toml
[project]
name = "n3tx-core"
version = "0.10.0"
dependencies = [
    "pydantic>=2.7,<3.0",
    "fastapi>=0.115,<1.0",
    "uvicorn>=0.34,<1.0",
    "PyJWT>=2.8.0",
    "bcrypt>=4.0.0",
]
[project.optional-dependencies]
flask = ["Flask>=3.1", "flasgger>=0.9"]
dev = ["pytest>=8.2", "httpx>=0.27"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
"n3tx_core" = ["static/**/*"]
```

### 2. `n3tx-actors` — Actor Messaging System (Backend Only)

No frontend static — Actor.js/TX.js/Matrix.js stay in n3tx-core because Component.js (the base for every web component) depends on all three. See [Frontend Split](#frontend-split) for rationale.

```
packages/n3tx-actors/
├── pyproject.toml
└── src/n3tx_actors/
    ├── __init__.py              # Actor, TX, Matrix, ActorProxy
    │
    ├── actor.py                 # Actor base class (ActorMeta metaclass)
    ├── tx.py                    # TX message envelope (dataclass)
    ├── matrix.py                # Root actor and message router
    ├── actor_proxy.py           # Generic actor wrapper (non-inheritance)
    │
    ├── models/
    │   └── actor_model.py       # ActorModel bridge (Actor + ProtoModel)
    │
    ├── api/                     # Protocol adapters (all extend Actor)
    │   ├── __init__.py
    │   ├── network_adapter.py   # Base adapter class
    │   ├── network_api.py       # HTTP adapter + create_api_routes() (Level 3 routing)
    │   ├── network_ws.py        # WebSocket adapter
    │   ├── network_mcp.py       # MCP adapter (agent discovery)
    │   ├── network_ap.py        # ActivityPub adapter (federation)
    │   └── auth_interceptor.py  # Tier 1 auth gate
    │
    └── tests/
        ├── unit/
        │   ├── test_actor.py
        │   ├── test_tx.py
        │   ├── test_matrix.py
        │   ├── test_actor_proxy.py
        │   ├── test_actor_system.py
        │   ├── test_interceptors.py
        │   ├── test_actor_model.py       (etc.)
        │   ├── test_auth_interceptor.py
        │   └── ...
        └── conftest.py
```

**pyproject.toml:**
```toml
[project]
name = "n3tx-actors"
version = "0.10.0"
dependencies = [
    "n3tx-core>=0.10.0",
    "pydantic>=2.7,<3.0",
]
[tool.setuptools.packages.find]
where = ["src"]
```

### 3. `n3tx-ui` — Visual Component Layer (Frontend Only)

All registered web components, their base classes, form generator, widgets, themes, and default HTML pages. Minimal Python — just enough to export the static directory path.

```
packages/n3tx-ui/
├── pyproject.toml
└── src/n3tx_ui/
    ├── __init__.py              # get_static_dir() helper
    └── static/
        ├── components/
        │   ├── NTTElement.js    # Abstract single-entity base (extends Component)
        │   ├── ListElement.js   # Abstract collection base (extends Component)
        │   ├── ntx-item.js      # Single entity renderer
        │   ├── ntx-list.js      # Collection grid
        │   ├── ntx-table.js     # Collection table
        │   ├── ntx-row.js       # Table row
        │   ├── ntx-method.js    # Method call button
        │   ├── ntx-stream.js    # Streaming method output
        │   ├── ntx-router.js    # Navigation container
        │   ├── ntx-modal.js     # Modal overlay
        │   ├── ntx-ref-picker.js # Reference field picker
        │   ├── ntx-sidebar.js   # Model navigation sidebar
        │   ├── ntx-topbar.js    # Header/nav bar
        │   ├── ntx-profile.js   # User profile page
        │   └── ntx-user.js      # User display
        ├── generators/
        │   └── form.js           # Formidable (schema → HTML forms)
        ├── widgets/
        │   ├── Widget.js         # Widget base class
        │   ├── registry.js       # Widget registry
        │   ├── index.js          # Re-exports all widgets
        │   ├── UrlWidget.js
        │   ├── EmailWidget.js
        │   ├── DateWidget.js
        │   ├── MarkdownWidget.js
        │   ├── ConsoleWidget.js
        │   ├── ReferenceWidget.js
        │   ├── CurrencyWidget.js
        │   └── TextareaWidget.js
        ├── index.html            # Default app entry point
        ├── login.html            # Default login page
        ├── register.html         # Default register page
        ├── dark-theme.css
        ├── light-theme.css
        └── components/*.css      # Component stylesheets
```

**pyproject.toml:**
```toml
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

### 4. `n3tx-agents` — LLM-Powered Reasoning

```
packages/n3tx-agents/
├── pyproject.toml
└── src/n3tx_agents/
    ├── __init__.py              # AgentMixin, AgentActor, AgentDeps
    │
    ├── mixin.py                 # AgentMixin (injected via __agent__ = True)
    ├── actor.py                 # AgentActor concrete model
    ├── tool_model.py            # AgentTool join model
    ├── deps.py                  # AgentDeps (pydantic-ai context)
    ├── tools.py                 # Tool discovery and generation
    ├── schema_ext.py            # Schema pipeline extension (agent metadata)
    │
    ├── static/                  # Agent UI primitives
    │   └── components/
    │       └── ntx-chat.js      # Agent chat panel
    │
    └── tests/
        ├── unit/
        │   ├── test_mixin.py
        │   ├── test_agent_actor.py
        │   ├── test_tools.py
        │   └── test_schema_ext.py
        └── conftest.py
```

**pyproject.toml:**
```toml
[project]
name = "n3tx-agents"
version = "0.10.0"
dependencies = [
    "n3tx-core>=0.10.0",
    "n3tx-actors>=0.10.0",
    "pydantic-ai>=1.0",
]
[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
"n3tx_agents" = ["static/**/*"]
```

### 5. `n3tx` — Meta-Package (Optional)

```
packages/n3tx/
├── pyproject.toml
└── src/n3tx/__init__.py         # Re-exports everything for convenience
```

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

```python
# n3tx/__init__.py
"""N3TX — install all framework modules."""
from n3tx_core import *
from n3tx_actors import *
from n3tx_agents import *
```

---

## Static File Serving (Multi-Package)

Three packages bundle `static/` directories (n3tx-core, n3tx-ui, n3tx-agents). n3tx-actors is backend-only. At runtime, the `N3TXApp` builder discovers and merges them into a single URL namespace.

### Discovery Mechanism

Add to `n3tx_core/api/backend.py`:
```python
def _discover_static_dirs():
    """Discover static directories from all installed n3tx packages."""
    dirs = []
    # 1. Core static (always present)
    core_static = Path(__file__).resolve().parent.parent / "static"
    if core_static.is_dir():
        dirs.append(core_static)

    # 2. Discover from installed packages
    for pkg_name in ('n3tx_ui', 'n3tx_agents'):
        try:
            mod = importlib.import_module(pkg_name)
            pkg_static = Path(mod.__file__).parent / "static"
            if pkg_static.is_dir():
                dirs.append(pkg_static)
        except ImportError:
            pass  # Package not installed

    return dirs
```

### Mount Order
1. App-specific static dirs (from `create_app(static_dir=...)`) — highest priority
2. n3tx-agents static (if installed) — `ntx-chat.js`
3. n3tx-ui static (if installed) — all components, widgets, themes, default HTML
4. n3tx-core static (catch-all) — JS runtime, utils, config

### Frontend index.html
`index.html` lives in n3tx-ui and imports from both core and ui directories (`./core/Actor.js`, `./components/NTTElement.js`, `./generators/form.js`). Since all static dirs merge into the same URL namespace via `_mount_static()`, relative imports resolve correctly — the browser doesn't know which package shipped each file.

Example apps already override `index.html` with their own versions (existing pattern, unchanged).

### Frontend Split Rationale

<a id="frontend-split"></a>

The backend split axis (core/actors/agents) doesn't map to the frontend. Analysis of the JS import graph reveals:

- **Component.js** imports Actor, Matrix, AND TX — it's the base for every web component
- **NTT.js** extends Actor and uses Matrix — it's the entity registry
- Every `ntx-*` component transitively depends on all three "actor" files

The frontend split axis is **runtime vs. visual**:
- **n3tx-core**: Non-visual runtime — messaging (Actor/TX/Matrix), entity system (NTT), abstract component bridge (Component), transport, utils
- **n3tx-ui**: Visual layer — registered custom elements, base classes that add visual behavior (NTTElement, ListElement), form generator, widgets, themes
- **n3tx-agents**: Agent-specific UI — `ntx-chat.js` only (imports from core, NOT from ui)

No circular dependencies across packages:
```
core ← ui (ui imports from core, never reverse)
core ← agents (agents imports from core, never reverse)
ui and agents are independent of each other
```

---

## Import Path Changes (Clean Break)

### n3tx-core
| Old | New |
|-----|-----|
| `from n3tx.core.models.proto_model import ProtoModel` | `from n3tx_core.models import ProtoModel` |
| `from n3tx.core.models.base_user import BaseUser` | `from n3tx_core.models import BaseUser` |
| `from n3tx.core.storage.sqlite_storage import SQLiteStorage` | `from n3tx_core.storage import SQLiteStorage` |
| `from n3tx.core.storage.abstract_storage import AbstractStorage` | `from n3tx_core.storage import AbstractStorage` |
| `from n3tx.core.authorize import ANYONE, OWNER, ROLE` | `from n3tx_core.authorize import ANYONE, OWNER, ROLE` |
| `from n3tx.core.utils.decorators import expose_route` | `from n3tx_core.utils import expose_route` |
| `from n3tx.core.utils.registrar import register_model` | `from n3tx_core.utils import register_model` |
| `from n3tx.core.app import create_app, N3TXApp` | `from n3tx_core import create_app, N3TXApp` |
| `from n3tx.core import config` | `from n3tx_core import config` |
| `from n3tx.core.widgets import UrlField` | `from n3tx_core.widgets import UrlField` |

### n3tx-actors
| Old | New |
|-----|-----|
| `from n3tx.core.actors import Actor, TX, Matrix, matrix` | `from n3tx_actors import Actor, TX, Matrix, matrix` |
| `from n3tx.core.actors.actor import actormethod, actorproperty` | `from n3tx_core.utils import fullmethod, fullproperty` |
| `from n3tx.core.models.actor_model import ActorModel` | `from n3tx_actors.models import ActorModel` |
| `from n3tx.core.api.network_adapter import NetworkAdapter` | `from n3tx_actors.api import NetworkAdapter` |
| `from n3tx.core.api.network_api import NetworkAPI` | `from n3tx_actors.api import NetworkAPI` |
| `from n3tx.core.api.network_ws import NetworkWebSocket` | `from n3tx_actors.api import NetworkWebSocket` |
| `from n3tx.core.api.auth_interceptor import auth_interceptor` | `from n3tx_actors.api import auth_interceptor` |

Note: `actormethod`/`actorproperty` aliases are removed during Phase 0. All code uses `fullmethod`/`fullproperty` from `n3tx_core.utils.descriptors`.

### n3tx-agents
| Old | New |
|-----|-----|
| `from n3tx.core.agents import AgentMixin, AgentActor` | `from n3tx_agents import AgentMixin, AgentActor` |
| `from n3tx.core.agents.deps import AgentDeps` | `from n3tx_agents import AgentDeps` |
| `from n3tx.core.agents.tools import discover_tools` | `from n3tx_agents.tools import discover_tools` |

---

## Critical Cross-Package Dependencies

### 1. `n3tx_actors.models.actor_model` → imports from `n3tx_core`
```python
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.authorize import AccessContext
```
This is a normal "actors depends on core" dependency.

### 2. `n3tx_actors.api.network_api` → imports from `n3tx_core`
```python
from n3tx_core.models.storable_mixin import StorableMixin
from n3tx_core.utils.registrar import registered_models
```
Network adapters bridge actors to the API layer — they naturally need both.

### 3. `n3tx_core.app` → conditionally imports from `n3tx_actors`
```python
# In N3TXApp.build():
if self._routing == 'actor':
    from n3tx_actors.api import NetworkAPI, create_api_routes
    from n3tx_actors.api import auth_interceptor
    from n3tx_actors import matrix
```
This is a **soft dependency** — core works without actors for Level 1/2 routing.

### 4. `n3tx_core.models.proto_model` → conditionally imports from `n3tx_agents`
```python
# In ProtoModel.__init_subclass__():
if cls_dict.get('__agent__') or getattr(cls, '__agent__', False):
    try:
        from n3tx_agents.mixin import AgentMixin
        cls.__bases__ = (AgentMixin,) + cls.__bases__
    except ImportError:
        raise ImportError(
            f"{cls.__name__} has __agent__ = True but n3tx-agents is not installed. "
            "Install it with: pip install n3tx-agents"
        )
```
This keeps the magic injection pattern but makes the dependency explicit.

### 5. `tx.py` — Remove the one internal import
Currently `TX.from_exception()` imports `MethodError` from `n3tx.core.utils.erroring`. Fix: use duck-typing (`hasattr(e, 'status_code')`) instead of type-checking. This makes TX truly zero-dependency.

---

## Migration Steps

### Phase 0: Pre-Migration Refactors (Before Split)

These changes are made in the current monolith, verified by existing tests, committed separately. They eliminate technical debt that would complicate the split.

#### 0a. Remove `actormethod`/`actorproperty` aliases
Rename all usages to `fullmethod`/`fullproperty` across the codebase. The aliases were backward-compat shims; `fullmethod`/`fullproperty` are the canonical names (already used by `agents/mixin.py`).

**Framework files to update (4):**
- `actors/actor.py` — remove alias lines, replace all `@actormethod` → `@fullmethod`, `@actorproperty` → `@fullproperty`
- `models/actor_model.py` — update import, update `ConfigDict(ignored_types=(fullmethod, fullproperty))`
- `actors/__init__.py` — update re-exports if applicable
- `actors/README.md` — update documentation references

**Test files to update (7):**
- `actors/tests/test_actor.py`
- `actors/tests/test_integration.py`
- `tests/unit/test_actor_model.py`
- `tests/unit/test_actor_model_integration.py`
- `tests/unit/test_actor_model_handler.py`
- `tests/unit/test_actor_model_lifecycle.py`
- `tests/unit/test_like_favorite_response_format.py`

**Verification:** Run full test suite — behavior is identical, only names change.

#### 0b. Fix `tx.py` — remove MethodError import
`TX.from_exception()` imports `MethodError` from `n3tx.core.utils.erroring`. Replace with duck-typing: `hasattr(e, 'status_code')`. This makes TX truly zero-dependency, ready for n3tx-actors.

#### 0c. Audit all `from n3tx.core.*` imports
Categorize every import by target package (core/actors/agents). Produce a checklist for Phase 5.

### Phase 1: Create Package Directories
1. Create `packages/` directory at repo root
2. Create `packages/n3tx-core/`, `packages/n3tx-actors/`, `packages/n3tx-ui/`, `packages/n3tx-agents/`, `packages/n3tx/`
3. Create `src/` subdirectory in each with proper `__init__.py`
4. Write `pyproject.toml` for each package
5. Add root-level dev tooling (`Makefile` or script for `pip install -e ./packages/n3tx-core -e ./packages/n3tx-actors -e ./packages/n3tx-ui ...`)

### Phase 2: Move Core Files
1. Move `src/n3tx/core/models/` → `packages/n3tx-core/src/n3tx_core/models/` (minus actor_model.py)
2. Move `src/n3tx/core/storage/` → `packages/n3tx-core/src/n3tx_core/storage/`
3. Move `src/n3tx/core/authorize/` → `packages/n3tx-core/src/n3tx_core/authorize/`
4. Move `src/n3tx/core/api/backend.py`, `routes_fastapi.py`, `routes_flask.py`, `discovery.py` → `packages/n3tx-core/src/n3tx_core/api/`
5. Move `src/n3tx/core/utils/` → `packages/n3tx-core/src/n3tx_core/utils/` (including `descriptors.py`)
6. Move `src/n3tx/core/widgets/` → `packages/n3tx-core/src/n3tx_core/widgets/`
7. Move `src/n3tx/core/ssr/` → `packages/n3tx-core/src/n3tx_core/ssr/`
8. Move `src/n3tx/core/swagger/` → `packages/n3tx-core/src/n3tx_core/swagger/`
9. Move `src/n3tx/core/config.py` → `packages/n3tx-core/src/n3tx_core/config.py`
10. Move `src/n3tx/core/app.py` → `packages/n3tx-core/src/n3tx_core/app.py`
11. Move core static files → `packages/n3tx-core/src/n3tx_core/static/`

### Phase 2.5: Move UI Files
1. Move `src/n3tx/static/components/NTTElement.js`, `ListElement.js` → `packages/n3tx-ui/src/n3tx_ui/static/components/`
2. Move all `src/n3tx/static/components/ntx-*.js` (except `ntx-chat.js`) → `packages/n3tx-ui/src/n3tx_ui/static/components/`
3. Move `src/n3tx/static/generators/` → `packages/n3tx-ui/src/n3tx_ui/static/generators/`
4. Move `src/n3tx/static/widgets/` → `packages/n3tx-ui/src/n3tx_ui/static/widgets/`
5. Move `src/n3tx/static/index.html`, `login.html`, `register.html` → `packages/n3tx-ui/src/n3tx_ui/static/`
6. Move `src/n3tx/static/dark-theme.css`, `light-theme.css`, component CSS → `packages/n3tx-ui/src/n3tx_ui/static/`

### Phase 3: Move Actor Files (Backend Only)
1. Move `src/n3tx/core/actors/actor.py` → `packages/n3tx-actors/src/n3tx_actors/actor.py`
2. Move `tx.py`, `matrix.py`, `actor_proxy.py` similarly
3. Move `src/n3tx/core/models/actor_model.py` → `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`
4. Move network adapters: `network_adapter.py`, `network_api.py`, `network_ws.py`, `network_mcp.py`, `network_ap.py`, `auth_interceptor.py` → `packages/n3tx-actors/src/n3tx_actors/api/`
5. Move actor-related unit tests → `packages/n3tx-actors/src/n3tx_actors/tests/`
6. No frontend files to move — Actor.js/TX.js/Matrix.js stay in n3tx-core

### Phase 4: Move Agent Files
1. Move `src/n3tx/core/agents/` → `packages/n3tx-agents/src/n3tx_agents/`
2. Move `ntx-chat.js` → `packages/n3tx-agents/src/n3tx_agents/static/components/`
3. Move agent-related tests → `packages/n3tx-agents/src/n3tx_agents/tests/`

### Phase 5: Update All Imports
1. Rewrite all `from n3tx.core.xxx` imports in framework code (per mapping table above)
2. Rewrite all `from n3tx.xxx` imports in example apps
3. Rewrite all `from n3tx.xxx` imports in test files
4. Update `app.py` conditional imports for actor/agent features
5. Update `proto_model.py` agent injection to try-import from `n3tx_agents`

### Phase 6: Update Example Apps
1. Update `example_api/` imports (n3tx_core only, no actors needed for Level 1)
2. Update `example_actor/` imports (n3tx_core + n3tx_actors)
3. Update `example_chat/` imports (all three packages)
4. Update `example_grants/` imports (all three packages)
5. Update each app's `main.py`, `models/`, `config.py`, `seed.py`

### Phase 7: Update Static File Serving
1. Implement `_discover_static_dirs()` in `backend.py` to auto-locate n3tx-ui and n3tx-agents static dirs
2. Update `_mount_static()` to handle 4 tiers: app > agents > ui > core
3. Update SSR `_merge_static_dirs()` to include discovered package dirs
4. Verify all `index.html` files still load correctly (JS imports resolve across merged namespace)

### Phase 8: Tests & Validation
1. Create dev install script: `pip install -e packages/n3tx-core -e packages/n3tx-actors -e packages/n3tx-ui -e packages/n3tx-agents`
2. Run framework unit tests per package
3. Run all integration tests (example_api, example_actor, example_chat, example_grants)
4. Verify `pip install n3tx-core` alone works for headless/API-only apps
5. Verify `pip install n3tx-core n3tx-ui` works for Level 1/2 apps with UI
6. Verify `pip install n3tx` installs everything
7. Verify browser DevTools: no 404s, correct file resolution per package

---

## Verification Plan

### Per-Package Isolation Tests
```bash
# Test n3tx-core alone (headless/API-only — no UI, no actors, no agents)
pip install -e packages/n3tx-core
# Backend tests pass, JS runtime files served (core/, utils/, config.js)

# Test n3tx-core + n3tx-ui (Level 1/2 with full UI)
pip install -e packages/n3tx-ui
cd example_api && python3 -m pytest tests/ -v

# Test n3tx-core + n3tx-actors + n3tx-ui (Level 3 — actor routing with UI)
pip install -e packages/n3tx-actors
cd example_actor && python3 -m pytest tests/ -v

# Test all (Level 3 + agents)
pip install -e packages/n3tx-agents
cd example_chat && python3 -m pytest tests/ -v
cd example_grants && python3 -m pytest tests/ -v
```

### Full Suite
```bash
pip install -e packages/n3tx  # meta-package
python3 -m pytest packages/n3tx-core/src/n3tx_core/tests/unit/ -v
python3 -m pytest packages/n3tx-actors/src/n3tx_actors/tests/ -v
python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/ -v
python3 -m pytest example_api/tests/ -v
python3 -m pytest example_actor/tests/ -v
```

### Static File Serving
1. Start each example app
2. Open browser DevTools Network tab, verify zero 404s
3. Verify `./core/Actor.js` resolves from n3tx-core static
4. Verify `./components/ntx-item.js` resolves from n3tx-ui static
5. Verify `./components/ntx-chat.js` resolves from n3tx-agents static (if installed)
6. Verify example app `index.html` overrides n3tx-ui default `index.html`

---

## Research Findings

### Route Registration Functions — No Circular Risk

The two route registration functions split cleanly by package:

| Function | Location | Package | What it does |
|----------|----------|---------|-------------|
| `register_routes()` | `routes_fastapi.py:418` | **n3tx-core** | Level 1/2 direct CRUD routes. Imports: models, utils, authorize, config — all core. No actor imports. |
| `create_api_routes(api, models)` | `network_api.py:57` | **n3tx-actors** | Level 3 actor-routed CRUD. Imports: TX + NetworkAdapter (actors) + StorableMixin (core). Returns APIRouter. |

**Dependency graph is acyclic:**
- `actors/` never imports from `api/routes_fastapi.py`
- `api/network_api.py` imports from `actors/` (TX, NetworkAdapter) — one direction only
- `app.py` conditionally imports `create_api_routes` only when `routing=='actor'`

No changes needed — the current file layout already maps 1:1 to the package split.

### `generate_join_model()` — Already Generic, No Changes Needed

`generate_join_model()` in `proto_model.py:273` uses dynamic class creation:
```python
join_model = type(class_name, (ref_model,), fields)
```

It inherits from whatever `ref_model` is passed at runtime — `ProtoModel`, `ActorModel`, or any subclass. The type assertion only checks `issubclass(ref_model, ProtoModel)`, which `ActorModel` satisfies via MRO. Zero hard-coded imports of Actor or ActorModel.

Already proven: `test_agent_actor.py` calls `generate_join_model(AgentActor, AgentTool)` — works seamlessly. **Stays in n3tx-core, zero modifications.**

### `actormethod`/`actorproperty` — Remove Before Split

Current state: `fullmethod`/`fullproperty` are the canonical descriptors in `descriptors.py`. `actormethod`/`actorproperty` are simple aliases in `actor.py` (`actormethod = fullmethod`). The agents package already uses `fullmethod` directly.

**4 framework files + 7 test files** use the aliases. Mechanical rename — no behavioral change. Doing this before the split avoids carrying alias baggage into n3tx-actors and removes a confusing indirection where actors re-export descriptors that live in core.

### No Backward-Compatibility Shim

The split is a clean break. The meta-package (`pip install n3tx`) re-exports from all three packages via `from n3tx_core import *` etc., but deep import paths like `from n3tx.core.models.proto_model import ProtoModel` are not shimmed. Users must update to the new paths.

### Matrix Singleton Lifetime

The module-level `matrix = Matrix()` instance is created when `n3tx_actors` is imported. For Level 1/2 apps that never import `n3tx_actors`, no Matrix exists — this is correct, since they don't use actor routing. For Level 3 apps, `app.py`'s conditional `from n3tx_actors import matrix` triggers the import and creates the singleton.

---

## Resolved Decisions

### Backend
1. **`descriptors.py` → n3tx-core** (in `n3tx_core/utils/descriptors.py`). Generic utility — both actors and agents import from core. The `actormethod`/`actorproperty` aliases are removed in Phase 0a; all code uses `fullmethod`/`fullproperty`.
2. **`register_routes()` → n3tx-core** (in `routes_fastapi.py`). Level 1/2 direct routing — no actor dependencies.
3. **`create_api_routes()` → n3tx-actors** (in `network_api.py`). Level 3 actor routing — bridges HTTP to TX messaging.
4. **`generate_join_model()` → n3tx-core** (in `proto_model.py`). Already generic via dynamic `type()` — works with any ProtoModel subclass including ActorModel.
5. **No backward-compat shim.** Clean break on import paths. Meta-package provides convenience re-exports only.
6. **Matrix created on `import n3tx_actors`**. Level 1/2 apps never import it, Level 3 apps get it via `app.py`'s conditional import.
7. **Tests**: Per-package unit tests. Integration tests stay in `example_*/tests/` (they test across packages by nature).

### Frontend
8. **Actor.js/TX.js/Matrix.js → n3tx-core** (not n3tx-actors). They're foundational to the entire frontend — Component.js depends on all three. The frontend "actor" files are runtime infrastructure, not optional.
9. **n3tx-actors is backend-only.** No frontend static directory.
10. **NTTElement.js/ListElement.js → n3tx-ui** (not n3tx-core). They add visual behavior (forms, edit modes, pagination, modals); the runtime/visual boundary is at Component.js.
11. **form.js → n3tx-ui.** Creates DOM elements and references widgets + ntx-ref-picker — all within the same package.
12. **Widgets → n3tx-ui.** Rendering utilities used only by components.
13. **ntx-stream.js → n3tx-ui** (not n3tx-core). It's a registered custom element, follows the rule: all `ntx-*` → ui.
14. **index.html/login.html/register.html → n3tx-ui.** Default visual entry points; example apps override them (existing pattern).
15. **ntx-chat.js → n3tx-agents.** The only agent-specific frontend file. Imports from core only (HTTP, config, NTT), does NOT depend on n3tx-ui.

---

## Implementation Order

The migration phases (0–8) define WHAT moves WHERE. But we should also decide WHICH plan to start with — the pre-migration refactors or the full split.

### Recommended: Phase 0 First (Pre-Migration Refactors)

Phase 0 can be done immediately in the current monolith with zero risk:

1. **Phase 0a**: Rename `actormethod`/`actorproperty` → `fullmethod`/`fullproperty` (mechanical, 11 files)
2. **Phase 0b**: Fix `tx.py` MethodError import → duck-typing (1 file)
3. **Phase 0c**: Audit all imports, categorize by target package (research, produces checklist)

Each sub-phase is a single commit, verified by existing tests. No package structure changes. This cleans up technical debt and produces the import audit that Phase 5 depends on.

### Then: Phases 1–4 Together (Create + Move)

Phases 1–4 are tightly coupled — creating empty package dirs without moving files is useless. Execute them as a single sprint:

1. Create all 5 package directories with `pyproject.toml` (Phase 1)
2. Move core Python + JS runtime static (Phase 2)
3. Move UI static files (Phase 2.5)
4. Move actor Python files (Phase 3)
5. Move agent Python + static files (Phase 4)

### Then: Phases 5–6 (Rewrite Imports)

The big mechanical phase. Use the audit from Phase 0c as a checklist. Phase 5 (framework imports) and Phase 6 (example app imports) can run in parallel.

### Finally: Phases 7–8 (Static Serving + Validation)

Wire up the static discovery mechanism and run the full verification plan.

### Summary

```
Phase 0  →  Phase 1-4  →  Phase 5-6  →  Phase 7-8
(cleanup)   (move files)   (fix imports)  (wire + verify)
  safe       big bang        mechanical     integration
```

Phase 0 is the only phase that can be shipped independently. Phases 1–8 are a single coordinated migration — shipping partial moves would break everything.
