# N3TX Pattern Consistency Audit -- Global Synthesis

**Date**: 2026-03-26
**Branch**: v0.9
**Auditors**: 5 parallel analysis agents
**Scope**: Full codebase -- packages/, examples/, apps/

---

## Audit Structure

This audit was conducted by 5 specialized agents running in parallel, each examining a different dimension of the codebase:

| # | Report | Focus |
|---|--------|-------|
| [01](01-model-definitions.md) | Model Definitions | Base classes, ClassVars, fields, decorators |
| [02](02-frontend-components.md) | Frontend Components | Class hierarchy, lifecycle, CSS, events |
| [03](03-test-patterns.md) | Test Patterns | Fixtures, isolation, mocking, markers |
| [04](04-imports-and-packages.md) | Imports & Packages | Import styles, dependency graph, build system |
| [05](05-api-routes-and-auth.md) | API Routes & Auth | Route generation, auth tiers, streaming, responses |

---

## Overall Consistency Scores

| Area | Score | Trend |
|------|-------|-------|
| Package structure & dependency graph | **95%** | Stable -- clean acyclic graph |
| Logging conventions | **100%** | Stable -- `n3tx.<subsystem>` everywhere |
| Build system (pyproject.toml) | **95%** | Stable -- identical configs |
| Import patterns | **93%** | Degraded -- chat example uses old paths |
| Frontend core components | **85%** | Stable in core, degraded at edges |
| Model definitions | **70%** | Degraded -- access, agent, defaults drift |
| API routes & auth | **75%** | Mixed -- streaming format split |
| Test patterns | **75%** | Mixed -- good unit, fragile integration |

### Key Observation

**The framework core (packages/) is tight and consistent.** The drift is concentrated in **examples/, apps/, and n3tx-trace/** -- code written at different times with different assumptions, not yet brought into alignment with current patterns.

---

## Critical Issues (Fix Before Next Release)

### 1. Chat Example Uses Old Import Paths
- **Where**: `examples/chat/` (7 files, 25 imports)
- **What**: `from n3tx.core.*` instead of `from n3tx_core.*` / `from n3tx_agents.*`
- **Impact**: Will break on clean installs. Confuses developers using chat as reference.
- **Fix**: Search-replace all old imports. Verify with grep.
- **Reports**: [04-imports](04-imports-and-packages.md)

### 2. Missing `__access__` on Many Models
- **Where**: Like, Bot, WebTools, Source (grants), AgentTool, AgentActor, Product (core/actors), User (all)
- **What**: No explicit access control declarations
- **Impact**: Security risk. Unknown default behavior. Developers copying these models inherit the gap.
- **Fix**: Define `__access__` on every storable model. Document the default when omitted.
- **Reports**: [01-models](01-model-definitions.md)

### 3. `__agent__` Value Type Inconsistency
- **Where**: Product/Task use `True` (bool), Grant/Run/Conversation use `{...}` (dict)
- **What**: No documented standard for when to use bool vs dict
- **Impact**: Developers don't know which pattern to follow. Dict keys undocumented.
- **Fix**: Document both forms. Standardize in examples (prefer dict for production).
- **Reports**: [01-models](01-model-definitions.md)

### 4. Mutable Default Anti-Pattern
- **Where**: Multiple models: `Field(default=[])` on ListRef fields
- **What**: Shared mutable list across instances
- **Impact**: Subtle bugs when instances share default lists
- **Fix**: Replace all `default=[]` with `default_factory=list`, `default={}` with `default_factory=dict`
- **Reports**: [01-models](01-model-definitions.md)

### 5. Streaming Format Divergence Between Levels
- **Where**: `routes_fastapi.py` vs `network_api.py`
- **What**: Level 1/2 streams simple `{count: 5}` chunks. Level 3 streams full TX envelopes `{name, source, target, data, meta, timestamp}`.
- **Impact**: Frontend must handle two completely different streaming protocols.
- **Fix**: Standardize on one format, or document both and let NetworkAdapter.js translate.
- **Reports**: [05-api-routes](05-api-routes-and-auth.md)

---

## High-Priority Issues

### 6. Veille Document Routes Bypass Framework
- **Where**: `apps/veille/main.py` lines 149-217
- **What**: Hand-rolled file upload/download/delete routes with duplicate JWT extraction
- **Fix**: Convert to `@expose_route` methods on Organization model
- **Reports**: [05-api-routes](05-api-routes-and-auth.md)

### 7. Five UI Components Extend HTMLElement Instead of Component
- **Where**: NTTSidebar, NTTModal, NTTProfile, NTTTopbar, NTTRefPicker
- **What**: Miss lifecycle management, adaptive display modes, stylesheet adoption
- **Fix**: Change `extends HTMLElement` to `extends Component`
- **Reports**: [02-frontend](02-frontend-components.md)

### 8. Entire n3tx-trace Package Pattern Deviation
- **Where**: All 4 trace components
- **What**: Plain HTMLElement, inline CSS, manual DOM, no TX messaging, no prerender/render
- **Fix**: Refactor to use Component pattern (lower priority -- debug tools)
- **Reports**: [02-frontend](02-frontend-components.md)

### 9. Stale JSON Serialization in Chat Message Model
- **Where**: `examples/chat/models/message.py`
- **What**: Custom `_storage_dict()` and `_deserialize_json_fields()` -- pre-v0.9 patterns now handled by framework
- **Fix**: Remove custom serialization, rely on framework v0.9+ JSON field handling
- **Reports**: [01-models](01-model-definitions.md)

### 10. Session-Scoped Shared DB in Integration Tests
- **Where**: All `examples/*/tests/conftest.py`
- **What**: One DB per session, tests share state, no per-test cleanup
- **Impact**: Tests that write data affect subsequent tests. Can't run in parallel.
- **Fix**: Move to module-scoped fixtures or implement transaction rollback
- **Reports**: [03-tests](03-test-patterns.md)

---

## Medium-Priority Issues

### 11. Global Config Mutation in Tests
- **Where**: `config.SQLITE_DB_FILE = db_path` in all integration conftest files
- **Impact**: Not thread-safe, blocks parallel test execution
- **Reports**: [03-tests](03-test-patterns.md)

### 12. `mock_method()` Duplicated 3+ Times
- **Where**: n3tx-actors/tests, n3tx-actors/api/tests, n3tx-agents/tests
- **Fix**: Centralize in `n3tx_core/tests/conftest_utils.py`
- **Reports**: [03-tests](03-test-patterns.md)

### 13. Missing Test Markers
- **Where**: E2E tests lack `pytest.mark.e2e`, apps/veille has no markers
- **Impact**: Can't selectively run `pytest -m e2e` or `pytest -m integration`
- **Reports**: [03-tests](03-test-patterns.md)

### 14. Raw `list`/`dict` Types Without Parameters
- **Where**: `tags: list`, `constraints: dict`, `parts: list` in various models
- **Fix**: Use `list[str]`, `dict[str, Any]`, etc.
- **Reports**: [01-models](01-model-definitions.md)

### 15. Error Response Format Divergence
- **Where**: Level 1/2 `{detail: "..."}` vs Level 3 TX `{is_error, data: {code, message}}`
- **Impact**: WS vs HTTP clients see different error structures
- **Reports**: [05-api-routes](05-api-routes-and-auth.md)

### 16. Event Model Definitions Scattered
- **Where**: TextChunk/DoneChunk in n3tx-agents/actor.py, veille/run.py, veille/grant.py
- **Fix**: Centralize event models in n3tx-agents (already the canonical location)
- **Reports**: [01-models](01-model-definitions.md)

### 17. User Injection Asymmetry Between Levels
- **Where**: Level 1/2 resolves to full User instance, Level 3 passes raw dict
- **Impact**: Custom methods must handle both types
- **Reports**: [05-api-routes](05-api-routes-and-auth.md)

### 18. n3tx-trace Missing from Meta-Package
- **Where**: `packages/n3tx/pyproject.toml`
- **Fix**: Add `n3tx-trace>=0.10.0` to dependencies
- **Reports**: [04-imports](04-imports-and-packages.md)

---

## Low-Priority Issues

### 19. Field-Level Access Declared but Not Enforced
- Schema carries `access: {view, edit}` metadata; frontend respects it; backend ignores it
- **Reports**: [05-api-routes](05-api-routes-and-auth.md)

### 20. Delete Response Format Inconsistency
- Level 1/2: `{message: "Deleted successfully"}`, Level 3: `{deleted: id}`
- **Reports**: [05-api-routes](05-api-routes-and-auth.md)

### 21. Inconsistent Test Naming
- Packages: `test_feature`, Examples: `test_action_scenario_result`
- **Reports**: [03-tests](03-test-patterns.md)

### 22. Missing Model Docstrings
- Comment, Like, Bot, Source (grants), Organization -- no class docstrings
- **Reports**: [01-models](01-model-definitions.md)

### 23. Direct fetch() in Some Frontend Components
- NTTChatView, NTXRunPanel bypass TX/Matrix routing
- **Reports**: [02-frontend](02-frontend-components.md)

### 24. Dead Code in Frontend
- Actor.js lines 104-116, NTT.js lines 84-147 (commented legacy)
- **Reports**: [02-frontend](02-frontend-components.md)

### 25. NTT.js Lacks Explicit Exports
- Classes defined but no `export` statement -- relies on implicit globals
- **Reports**: [02-frontend](02-frontend-components.md)

---

## What's Working Well

These patterns are strong and should be preserved:

1. **Dependency graph is clean** -- No circular deps, no upward violations, clear package boundaries
2. **Logging is perfect** -- 100% consistent `n3tx.<subsystem>` naming
3. **Build system is uniform** -- Identical pyproject.toml structure across all packages
4. **`__tablename__` convention** -- Universally plural snake_case
5. **Core UI component hierarchy** -- Component -> NTTElement -> NTTItem chain is exemplary
6. **UPPERCASE handler convention** -- Consistent TX inbox handler naming
7. **prerender/render lifecycle** -- Clean separation where Component is used
8. **Schema as universal contract** -- Frontend reads schema at runtime, adapts automatically
9. **@expose_route adoption** -- 49 files, 100% of custom methods use the decorator
10. **Two-tier auth at Level 3** -- Clean separation of protocol gate and resource-level checks

---

## Recommended Fix Order

### Wave 1: Quick Wins (< 1 day)
1. Fix chat example imports (search-replace)
2. Replace all `Field(default=[])` with `Field(default_factory=list)`
3. Add `__access__` to models missing it
4. Remove stale JSON serialization from chat Message model
5. Add test markers (unit, integration, e2e)

### Wave 2: Standards Alignment (1-2 days)
6. Document `__agent__` dict keys and standardize usage
7. Centralize `mock_method()` utility
8. Convert veille document routes to @expose_route
9. Add n3tx-trace to meta-package
10. Type-annotate raw list/dict fields

### Wave 3: Architecture Consistency (3-5 days)
11. Convert 5 UI components to extend Component
12. Standardize streaming format between levels
13. Unify user injection (User instance vs dict)
14. Refactor trace components toward Component pattern
15. Implement test isolation for integration tests

### Wave 4: Documentation (1-2 days)
16. Document canonical model template in docs/
17. Document widget system (CurrencyField, TextareaField, etc.)
18. Document streaming contract (SSE events, formats, termination)
19. Add pytest configuration (markers, asyncio_mode)
20. Update CLAUDE.md with patterns from this audit

---

## Appendix: Files Requiring Changes

### Critical Path Files
```
examples/chat/config.py
examples/chat/main.py
examples/chat/models/user.py
examples/chat/models/message.py
examples/chat/models/conversation.py
examples/chat/seed.py
examples/chat/tests/conftest.py
examples/chat/tests/test_*.py
```

### Models Needing `__access__`
```
examples/core/models/product.py
examples/core/models/like.py
examples/core/models/user.py
examples/actors/models/product.py
examples/actors/models/like.py
examples/actors/models/user.py
examples/grants/models/source.py
packages/n3tx-agents/src/n3tx_agents/actor.py
packages/n3tx-agents/src/n3tx_agents/tool_model.py
```

### Models Needing `default_factory`
```
examples/core/models/product.py (comments, favorites)
examples/core/models/comment.py (likes)
examples/actors/models/product.py (comments, favorites)
examples/actors/models/comment.py (likes)
examples/chat/models/conversation.py (messages)
```

### Frontend Components Needing Hierarchy Fix
```
packages/n3tx-ui/src/n3tx_ui/static/components/ntx-sidebar.js
packages/n3tx-ui/src/n3tx_ui/static/components/ntx-modal.js
packages/n3tx-ui/src/n3tx_ui/static/components/ntx-profile.js
packages/n3tx-ui/src/n3tx_ui/static/components/ntx-topbar.js
packages/n3tx-ui/src/n3tx_ui/static/components/ntx-ref-picker.js
```
