# Import Patterns & Package Structure Audit

**Date**: 2026-03-26
**Scope**: All Python files across packages/, examples/, and apps/
**Focus**: Import styles, dependency graph, __init__.py exports, build system, logging, static files

---

## Executive Summary

The N3TX codebase demonstrates **excellent structural discipline** overall (95%+ correct). The dependency graph is clean and acyclic, logging is perfectly consistent, and package organization is sound. **One significant outlier**: `examples/chat/` uses 25 old-style imports (`from n3tx.core.*`). One minor gap: n3tx-trace is missing from the meta-package.

---

## Import Style Audit

### Old-Style Imports (VIOLATIONS)

**Location**: `examples/chat/` only (7 files, 25 imports)

| File | Old Import | Should Be |
|------|-----------|-----------|
| `config.py` | `from n3tx.core import config as _fw` | `from n3tx_core import config as _fw` |
| `main.py` | `from n3tx.core.app import create_app` | `from n3tx_core.app import create_app` |
| `main.py` | `from n3tx.core.storage.sqlite_storage import SQLiteStorage` | `from n3tx_core.storage.sqlite_storage import SQLiteStorage` |
| `main.py` | `from n3tx.core.agents.tool_model import AgentTool` | `from n3tx_agents.tool_model import AgentTool` |
| `models/user.py` | `from n3tx.core.models.actor_model import ActorModel` | `from n3tx_actors.models.actor_model import ActorModel` |
| `models/user.py` | `from n3tx.core.models.base_user import BaseUser` | `from n3tx_core.models.base_user import BaseUser` |
| `models/message.py` | `from n3tx.core.models.actor_model import ActorModel` | `from n3tx_actors.models.actor_model import ActorModel` |
| `models/message.py` | `from n3tx.core.authorize import ...` | `from n3tx_core.authorize import ...` |
| `models/conversation.py` | `from n3tx.core.agents.actor import AgentActor` | `from n3tx_agents.actor import AgentActor` |
| `models/conversation.py` | `from n3tx.core.models.ref import ListRef` | `from n3tx_core.models.ref import ListRef` |
| `models/conversation.py` | `from n3tx.core.authorize import ...` | `from n3tx_core.authorize import ...` |
| `models/conversation.py` | `from n3tx.core.utils.decorators import expose_route` | `from n3tx_core.utils.decorators import expose_route` |
| `seed.py` | `from n3tx.core.storage.sqlite_storage import SQLiteStorage` | `from n3tx_core.storage.sqlite_storage import SQLiteStorage` |
| `seed.py` | `from n3tx.core.utils.registrar import register_model` | `from n3tx_core.utils.registrar import register_model` |
| `seed.py` | `from n3tx.core.models.proto_model import generate_join_model` | `from n3tx_core.models.proto_model import generate_join_model` |
| `tests/conftest.py` | `from n3tx.core.storage.sqlite_storage import SQLiteStorage` | `from n3tx_core.storage.sqlite_storage import SQLiteStorage` |
| `tests/conftest.py` | `from n3tx.core.utils.registrar import registered_models` | `from n3tx_core.utils.registrar import registered_models` |
| `tests/conftest.py` | `from n3tx.core.authorize import create_token` | `from n3tx_core.authorize import create_token` |
| `tests/test_*.py` | Same pattern | Same fixes |

### New-Style Imports (CORRECT)

- Framework packages: **435+ correct imports** (100%)
- examples/core, actors, grants, pygentic: **131+ correct imports** (100%)
- apps/veille: **100% correct**

### Relative vs Absolute

- **Relative imports**: Used correctly only in `__init__.py` files and example `models/__init__.py`
- **Absolute imports**: 100% of production code in packages/
- **No violations**

### Import Ordering

Consistent across all checked files:
1. `import logging` and stdlib
2. Third-party (pydantic, fastapi, etc.)
3. `from n3tx_*` framework imports
4. Relative/local imports

---

## Package __init__.py Analysis

### n3tx-core
- **Exports**: `ProtoModel`, `N3TXApp`, `create_app`, `SQLiteStorage`, `Field`, `BaseUser`, `config`
- **Pattern**: Clean, explicit exports
- **Status**: GOOD

### n3tx-actors
- **Exports**: `Actor`, `TX`, `Matrix`, `matrix`, `ActorProxy`
- **Pattern**: Minimal, clean
- **Status**: GOOD

### n3tx-agents
- **Exports**: `AgentMixin`, `AgentActor`, `AgentDeps`, `AgentTool`, + tool functions
- **Pattern**: Calls `register_mixin('__agent__', AgentMixin)` at import time
- **Status**: GOOD (registration before model imports is critical)

### n3tx-ui
- **Exports**: `get_static_dir` function
- **Pattern**: Calls `register_mixin('__viewable__', ViewableMixin)` at import time
- **Status**: GOOD

### n3tx-trace
- **Exports**: `install_trace`, `get_collector` + private `_collector`
- **Pattern**: Module-level functions for debug tracing
- **Status**: GOOD

### n3tx (meta-package)
- **Pattern**: Re-exports from all sub-packages with fallback
- **Optional handling**: `try/except ImportError` for n3tx-agents (correct)
- **Issue**: Does NOT re-export n3tx-trace

---

## Dependency Graph

### Declared Dependencies (pyproject.toml)

```
n3tx-core        -> pydantic, fastapi, uvicorn, PyJWT, bcrypt
n3tx-actors      -> n3tx-core, pydantic
n3tx-ui          -> n3tx-core
n3tx-agents      -> n3tx-core, n3tx-actors, pydantic-ai
n3tx-trace       -> n3tx-core, n3tx-actors
n3tx (meta)      -> n3tx-core, n3tx-actors, n3tx-ui, n3tx-agents
                    (MISSING: n3tx-trace)
```

### Actual Import Dependencies (verified)

| Package | Imports from | Status |
|---------|-------------|--------|
| n3tx-core | stdlib, pydantic, fastapi only | CLEAN |
| n3tx-actors | n3tx-core only | CLEAN |
| n3tx-ui | n3tx-core only | CLEAN |
| n3tx-agents | n3tx-core, n3tx-actors only | CLEAN |
| n3tx-trace | n3tx-core, n3tx-actors only | CLEAN |

### Violations Found
- **Upward**: NONE (n3tx-core never imports from other packages)
- **Sideways**: NONE (n3tx-ui doesn't import n3tx-actors, etc.)
- **Circular**: NONE

---

## Build System

### Pyproject.toml Consistency

All 6 packages use identical build configuration:

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

**Status**: 100% consistent.

### Version Pinning

| Dependency | Pin | Consistent |
|------------|-----|------------|
| pydantic | >=2.7,<3.0 | Yes |
| fastapi | >=0.115,<1.0 | Yes |
| uvicorn | >=0.34,<1.0 | Yes |
| PyJWT | >=2.8.0 | Yes |
| bcrypt | >=4.0.0 | Yes |
| pydantic-ai | >=1.0 | Yes (agents only) |

---

## Static File Organization

### Package Data Declarations

| Package | Static Files | Declaration |
|---------|-------------|-------------|
| n3tx-core | ~50 files (core JS runtime) | `"n3tx_core" = ["static/**/*"]` |
| n3tx-actors | None | N/A |
| n3tx-ui | ~40 files (components, themes) | `"n3tx_ui" = ["static/**/*"]` |
| n3tx-agents | 4 files (agent components) | `"n3tx_agents" = ["static/**/*"]` |
| n3tx-trace | 7 files (debug inspector) | `"n3tx_trace" = ["static/**/*"]` |

**Duplication check**: CLEAN -- each filename appears exactly once across all packages.

### Static File Path Convention
All follow: `/packages/<pkg>/src/<pkg>/static/`

---

## Logging Patterns

### Logger Naming

All 56 loggers follow: `logging.getLogger('n3tx.<subsystem>')`

| Subsystem | Logger Names |
|-----------|--------------|
| models | `n3tx.models`, `n3tx.config` |
| schema | `n3tx.schema` |
| dump | `n3tx.dump` |
| actors | `n3tx.actors`, `n3tx.actors.*` |
| network | `n3tx.network`, `n3tx.network.api`, `.ws`, `.ap`, `.mcp` |
| storage | `n3tx.storage` |
| utils | `n3tx.utils` |
| ssr | `n3tx.ssr`, `n3tx.ssr.bundler` |
| agents | `n3tx.agents`, `n3tx.agents.thread` |

**Status**: 100% consistent.

### Logger Setup

Root logger in `n3tx_core/config.py`:
```python
_n3tx_logger = logging.getLogger('n3tx')
if not _n3tx_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(levelname)s %(name)s: %(message)s'))
    _n3tx_logger.addHandler(_handler)
```

**Status**: Correct -- handler dedup prevents duplicates on re-import.

---

## Configuration Patterns

### Framework Config (n3tx-core/config.py)
- Reads env vars: `N3TX_HOST`, `N3TX_PORT`, `N3TX_DEBUG`, etc.
- `configure(**kwargs)` for runtime overrides
- Module-level globals

### App Config (examples/chat/config.py)
- Same env var pattern
- Calls `_fw.configure(...)` to update framework config
- **Issue**: Uses old import `from n3tx.core import config as _fw`

### Other Examples
- Most use `n3tx_core.config` directly or via `create_app()` parameters
- Consistent N3TX_* env var prefix

---

## Issues Summary

| # | Issue | Severity | Location |
|---|-------|----------|----------|
| 1 | Old-style imports (`n3tx.core.*`) | HIGH | examples/chat/ (25 imports) |
| 2 | n3tx-trace missing from meta-package | MEDIUM | packages/n3tx/pyproject.toml |
| 3 | No other import violations found | -- | -- |

---

## Recommendations

### Priority 1: Fix examples/chat/ Imports
Migrate all 25 imports from `from n3tx.core.*` to `from n3tx_core.*` / `from n3tx_agents.*`.

### Priority 2: Add n3tx-trace to Meta-Package
Add to `packages/n3tx/pyproject.toml`:
```toml
dependencies = [
    ...,
    "n3tx-trace>=0.10.0",
]
```

### Priority 3: Verification
After fixes, run:
```bash
grep -r "from n3tx\.core\|import n3tx\.core" examples/
# Should return 0 results
```
