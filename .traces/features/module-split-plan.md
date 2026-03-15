# N3TX Module Split Plan

## Context

The `expose_route` debug envelope bug revealed a deeper issue: the backend and frontend need to communicate via a unified TX-based wire format, and achieving this cleanly requires the project to be split into composable, independently installable modules. The current monolithic `n3tx` package bundles everything (models, actors, agents, storage, auth, UI) into one install, making it impossible to use the actor system without the full framework or to add agents without pulling in everything.

The goal: split into **n3tx-core** (models, storage, auth, API), **n3tx-actors** (messaging), and **n3tx-agents** (LLM reasoning), where each package owns its backend code AND its UI primitives. Projects install only what they need.

---

## Decision: Actor Package Placement

### Option A: Actors as Separate Package (`n3tx-actors`)

**Structure:**
```
packages/
├── n3tx-core/       # pip install n3tx-core
├── n3tx-actors/     # pip install n3tx-actors  (depends on n3tx-core)
└── n3tx-agents/     # pip install n3tx-agents  (depends on n3tx-core + n3tx-actors)
```

**What moves to n3tx-actors:**
- `actor.py`, `tx.py`, `matrix.py`, `actor_proxy.py`
- `descriptors.py` (fullmethod/fullproperty)
- `actor_model.py` (the bridge class)
- Network adapters: `network_adapter.py`, `network_api.py`, `network_ws.py`, `network_mcp.py`, `network_ap.py`
- `auth_interceptor.py`
- Frontend: `Actor.js`, `TX.js`, `Matrix.js`

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
- Frontend Actor.js/TX.js/Matrix.js cleanly belong to this package

**Cons:**
- ActorModel needs to import ProtoModel from n3tx-core (cross-package dependency)
- Network adapters need both Actor (from self) AND storage/auth (from n3tx-core)
- `app.py` builder needs conditional imports from n3tx-actors
- 3 packages to manage instead of 2
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
    ├── static/                  # Core UI primitives
    │   ├── core/
    │   │   ├── NTT.js           # Entity class system
    │   │   ├── Component.js     # Web component base
    │   │   ├── Router.js        # Client-side navigation
    │   │   ├── Observable.js    # Observer pattern
    │   │   ├── Utils.js         # Utilities
    │   │   └── transport/
    │   │       ├── HTTP.js      # HTTP adapter
    │   │       └── NetworkAdapter.js
    │   ├── components/
    │   │   ├── NTTElement.js    # Single-entity base
    │   │   ├── ListElement.js   # Collection base
    │   │   ├── ntx-item.js     # Default entity renderer
    │   │   ├── ntx-list.js     # Default collection renderer
    │   │   ├── ntx-router.js   # Navigation container
    │   │   ├── ntx-topbar.js   # Header/nav
    │   │   ├── ntx-sidebar.js  # Side navigation
    │   │   ├── ntx-modal.js    # Modal overlay
    │   │   ├── ntx-method.js   # Method button
    │   │   ├── ntx-stream.js   # Streaming output (core, not agent-specific)
    │   │   ├── ntx-profile.js  # User profile
    │   │   ├── ntx-user.js     # User display
    │   │   ├── ntx-ref-picker.js
    │   │   ├── ntx-table.js
    │   │   └── ntx-row.js
    │   ├── generators/
    │   │   └── form.js          # Formidable (schema → form)
    │   ├── widgets/             # All built-in JS widgets
    │   │   ├── Widget.js
    │   │   ├── registry.js
    │   │   ├── index.js
    │   │   ├── UrlWidget.js
    │   │   ├── EmailWidget.js
    │   │   ├── DateWidget.js
    │   │   ├── MarkdownWidget.js
    │   │   ├── ConsoleWidget.js
    │   │   ├── ReferenceWidget.js
    │   │   ├── CurrencyWidget.js
    │   │   └── TextareaWidget.js
    │   ├── utils/               # All frontend utils
    │   │   ├── Logging.js
    │   │   ├── Permissions.js
    │   │   ├── Toast.js
    │   │   └── ...
    │   └── config.js
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

### 2. `n3tx-actors` — Actor Messaging System

```
packages/n3tx-actors/
├── pyproject.toml
└── src/n3tx_actors/
    ├── __init__.py              # Actor, TX, Matrix, ActorProxy, actormethod, actorproperty
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
    │   ├── network_api.py       # HTTP adapter (Level 3 routing)
    │   ├── network_ws.py        # WebSocket adapter
    │   ├── network_mcp.py       # MCP adapter (agent discovery)
    │   ├── network_ap.py        # ActivityPub adapter (federation)
    │   └── auth_interceptor.py  # Tier 1 auth gate
    │
    ├── static/                  # Actor UI primitives
    │   └── core/
    │       ├── Actor.js         # Frontend Actor class
    │       ├── TX.js            # Frontend TX envelope
    │       └── Matrix.js        # Frontend root actor
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

[tool.setuptools.package-data]
"n3tx_actors" = ["static/**/*"]
```

### 3. `n3tx-agents` — LLM-Powered Reasoning

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

### 4. `n3tx` — Meta-Package (Optional)

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

Each package bundles its own `static/` directory. At runtime, the `N3TXApp` builder discovers and merges them.

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

    # 2. Discover from installed packages via importlib.resources
    for pkg_name in ('n3tx_actors', 'n3tx_agents'):
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
2. Agent static (if installed) — `ntx-chat.js`
3. Actor static (if installed) — `Actor.js`, `TX.js`, `Matrix.js`
4. Core static (catch-all) — everything else

### Frontend index.html
Currently, `index.html` imports JS files by relative path (`./core/Actor.js`). Since all static dirs are merged at the same URL namespace, this continues to work — the server resolves `GET /core/Actor.js` from whichever package provides it.

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
| `from n3tx.core.actors.actor import actormethod, actorproperty` | `from n3tx_actors import actormethod, actorproperty` |
| `from n3tx.core.models.actor_model import ActorModel` | `from n3tx_actors.models import ActorModel` |
| `from n3tx.core.api.network_adapter import NetworkAdapter` | `from n3tx_actors.api import NetworkAdapter` |
| `from n3tx.core.api.network_api import NetworkAPI` | `from n3tx_actors.api import NetworkAPI` |
| `from n3tx.core.api.network_ws import NetworkWebSocket` | `from n3tx_actors.api import NetworkWebSocket` |
| `from n3tx.core.api.auth_interceptor import auth_interceptor` | `from n3tx_actors.api import auth_interceptor` |
| `from n3tx.core.utils.descriptors import fullmethod` | `from n3tx_core.utils import fullmethod, fullproperty` |

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

### Phase 0: Preparation (Current PR)
- [x] Fix auth bug (frontend compat for debug envelope)
- [ ] Fix `tx.py` — remove MethodError import (duck-type instead)
- [ ] Audit all `from n3tx.core.*` imports and categorize by target package

### Phase 1: Create Package Directories
1. Create `packages/` directory at repo root
2. Create `packages/n3tx-core/`, `packages/n3tx-actors/`, `packages/n3tx-agents/`, `packages/n3tx/`
3. Create `src/` subdirectory in each with proper `__init__.py`
4. Write `pyproject.toml` for each package
5. Add root-level dev tooling (`Makefile` or script for `pip install -e ./packages/n3tx-core -e ./packages/n3tx-actors ...`)

### Phase 2: Move Core Files
1. Move `src/n3tx/core/models/` → `packages/n3tx-core/src/n3tx_core/models/` (minus actor_model.py)
2. Move `src/n3tx/core/storage/` → `packages/n3tx-core/src/n3tx_core/storage/`
3. Move `src/n3tx/core/authorize/` → `packages/n3tx-core/src/n3tx_core/authorize/`
4. Move `src/n3tx/core/api/backend.py`, `routes_fastapi.py`, `routes_flask.py`, `discovery.py` → `packages/n3tx-core/src/n3tx_core/api/`
5. Move `src/n3tx/core/utils/` → `packages/n3tx-core/src/n3tx_core/utils/` (minus descriptors.py)
6. Move `src/n3tx/core/widgets/` → `packages/n3tx-core/src/n3tx_core/widgets/`
7. Move `src/n3tx/core/ssr/` → `packages/n3tx-core/src/n3tx_core/ssr/`
8. Move `src/n3tx/core/swagger/` → `packages/n3tx-core/src/n3tx_core/swagger/`
9. Move `src/n3tx/core/config.py` → `packages/n3tx-core/src/n3tx_core/config.py`
10. Move `src/n3tx/core/app.py` → `packages/n3tx-core/src/n3tx_core/app.py`
11. Move core static files → `packages/n3tx-core/src/n3tx_core/static/`

### Phase 3: Move Actor Files
1. Move `src/n3tx/core/actors/actor.py` → `packages/n3tx-actors/src/n3tx_actors/actor.py`
2. Move `tx.py`, `matrix.py`, `actor_proxy.py` similarly
3. Move `src/n3tx/core/models/actor_model.py` → `packages/n3tx-actors/src/n3tx_actors/models/actor_model.py`
5. Move network adapters: `network_adapter.py`, `network_api.py`, `network_ws.py`, `network_mcp.py`, `network_ap.py`, `auth_interceptor.py` → `packages/n3tx-actors/src/n3tx_actors/api/`
6. Move `Actor.js`, `TX.js`, `Matrix.js` → `packages/n3tx-actors/src/n3tx_actors/static/core/`
7. Move actor-related unit tests → `packages/n3tx-actors/src/n3tx_actors/tests/`

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
1. Extend `backend.py._mount_static()` to discover static dirs from installed packages
2. Ensure mount order: app > agents > actors > core
3. Verify all `index.html` files still load correctly (JS imports are relative)

### Phase 8: Tests & Validation
1. Create dev install script: `pip install -e packages/n3tx-core -e packages/n3tx-actors -e packages/n3tx-agents`
2. Run framework unit tests per package
3. Run all integration tests (example_api, example_actor, example_chat, example_grants)
4. Verify `pip install n3tx-core` alone works for Level 1 apps
5. Verify `pip install n3tx` installs everything

---

## Verification Plan

### Per-Package Isolation Tests
```bash
# Test n3tx-core alone (Level 1 — no actors, no agents)
pip install -e packages/n3tx-core
cd example_api && python3 -m pytest tests/ -v

# Test n3tx-core + n3tx-actors (Level 3 — actor routing)
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
2. Open browser, verify all JS modules load (check Network tab for 404s)
3. Verify Actor.js/TX.js/Matrix.js resolve from n3tx-actors static dir
4. Verify ntx-chat.js resolves from n3tx-agents static dir (if installed)

---

## Resolved Decisions

1. **`descriptors.py` → n3tx-core** (in `n3tx_core/utils/descriptors.py`). Generic utility — both actors and agents import from core.
2. **`ntx-stream.js` → stays in n3tx-core**. Streaming is a general capability (Level 1/2 routes also support StreamingResponse).
3. **Tests**: Per-package unit tests. Integration tests stay in `example_*/tests/` (they test across packages by nature).
