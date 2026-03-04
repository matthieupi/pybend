# Technology Stack

**Analysis Date:** 2026-03-04

## Languages

**Primary:**
- Python 3.11.2 (`requires-python = ">=3.10"` in `pyproject.toml`) — all backend, framework core, models, actors, agents, storage, API routing
- JavaScript (ES Modules, vanilla) — frontend Web Components, no transpilation, no framework

**Secondary:**
- SQL (SQLite dialect) — schema creation, migrations, queries in `src/pybend/core/storage/sqlite_storage.py`
- HTML/CSS — static frontend pages in `src/pybend/static/` and `example_grants/static/`

## Runtime

**Environment:**
- CPython 3.11+ (uses `match` statements, `type` union syntax `list | None`, f-strings)
- Node.js (for frontend testing only — vitest, jsdom, Playwright)

**Package Manager:**
- pip with setuptools (build backend: `setuptools.build_meta` in `pyproject.toml`)
- npm (frontend tests only, `src/pybend/static/package.json`)
- Lockfile: `package-lock.json` present for frontend; no `requirements.txt` lock — dependencies specified in `pyproject.toml`

## Frameworks

**Core:**
- FastAPI 0.129.0 (spec: `>=0.115,<1.0`) — ASGI web framework, auto OpenAPI docs. Entry: `src/pybend/core/api/backend.py`
- Pydantic 2.12.5 (spec: `>=2.7,<3.0`) — model validation, JSON Schema generation, BaseModel inheritance. Entry: `src/pybend/core/models/proto_model.py`
- pydantic-ai 1.64.0 (spec: `>=1.0`, optional `[agents]` extra) — LLM agent framework. Entry: `src/pybend/core/agents/mixin.py`
- Uvicorn 0.41.0 (spec: `>=0.34,<1.0`) — ASGI server

**Testing:**
- pytest 8.4.2 (spec: `>=8.2`) — Python test runner. Config: `src/pybend/core/pytest.ini`
- pytest-asyncio 0.24.0 — async test support
- pytest-cov 7.0.0 (spec: `>=6.0`) — coverage reporting
- httpx 0.28.1 (spec: `>=0.27`) — async HTTP client for test requests and `FastAPI.TestClient`
- vitest 1.6.0 — frontend JS unit tests. Config: `src/pybend/static/vitest.config.js`
- Playwright 1.44.0 — frontend E2E tests. Config: `src/pybend/static/tests/e2e/playwright.config.js`

**Build/Dev:**
- setuptools >=68.0 — Python build backend (`pyproject.toml`)
- pyinstrument >=4.6 — performance profiling (dev dependency)
- esbuild — JS bundling for SSR mode (installed in `src/pybend/static/node_modules/`)

## Key Dependencies

**Critical:**
- `pydantic>=2.7,<3.0` — the entire framework is built on Pydantic V2 BaseModel. ProtoModel, Actor, ActorModel all extend PydanticBaseModel. JSON Schema generation, validation, serialization, and the schema pipeline all depend on Pydantic V2 internals (`pydantic.json_schema`, `pydantic_core.CoreSchema`).
- `fastapi>=0.115,<1.0` — all HTTP routing, middleware (CORS, JWT auth), static file serving. Both direct routes (`routes_fastapi.py`) and actor routes (`network_api.py`) produce FastAPI routers.
- `pydantic-ai>=1.0` — LLM agent execution engine. `AgentMixin.agent_run()` creates a `pydantic_ai.Agent` per invocation, uses `pydantic_ai.tools.Tool` wrappers, `pydantic_ai.UsageLimits`, and `pydantic_ai.ModelRetry` for error handling.

**Authentication & Security:**
- `PyJWT>=2.8.0` (installed: 2.11.0) — JWT token creation/verification in `src/pybend/core/authorize/auth.py`. Algorithm: HS256.
- `bcrypt>=4.0.0` (installed: 5.0.0) — password hashing in `src/pybend/core/authorize/auth.py`

**HTTP & Networking:**
- `httpx>=0.27` (installed: 0.28.1) — async HTTP client used by `WebTools.scrape()` for web scraping and by `FastAPI.TestClient` in tests
- `requests>=2.31` (installed: 2.32.5) — dev dependency, used in some test utilities

**Data Processing:**
- `beautifulsoup4` (installed: 4.14.3) — HTML parsing in `example_grants/models/web_tools.py` for grant extraction (CSS selector-based)

**Infrastructure:**
- `uvicorn>=0.34,<1.0` (installed: 0.41.0) — ASGI server, runs the app

**Optional (Framework Extensions):**
- `Flask>=3.1` + `flasgger>=0.9` — alternative Flask backend (optional `[flask]` extra), route layer in `src/pybend/core/api/routes_flask.py`

## Configuration

**Environment:**
- All configuration via `PYBEND_*` environment variables, with defaults in `src/pybend/core/config.py`
- Key env vars:
  - `PYBEND_HOST` (default: `0.0.0.0`)
  - `PYBEND_PORT` (default: `5000`)
  - `PYBEND_SQLITE_DB` (default: `pybend.db`, grants app uses `grants.db`)
  - `PYBEND_JWT_SECRET` (default: dev secret — warns if insecure)
  - `PYBEND_JWT_EXPIRY_HOURS` (default: `24`)
  - `PYBEND_DEBUG` (default: `false` — controls OpenAPI docs visibility, error detail)
  - `PYBEND_SSR` (default: `off` — modes: `off`, `schema`, `bundle`, `full`)
  - `PYBEND_API_URL` (default: `http://localhost:{PORT}`)
  - `PYBEND_BACKEND` (default: `fastapi`)
- Per-app config override: `example_grants/config.py` imports framework config and calls `_fw.configure(...)` to propagate settings

**Build:**
- `pyproject.toml` — single source for Python build config, dependencies, setuptools package discovery
- `src/pybend/static/package.json` — frontend test dependencies only (no build step for production)
- `src/pybend/static/vitest.config.js` — frontend test configuration (jsdom environment)

## Database

**SQLite:**
- Default storage backend. Only backend currently supported.
- Connection pooling via `queue.Queue` in `src/pybend/core/storage/sqlite_storage.py`
- WAL mode enabled by default for concurrent read/write
- `PRAGMA busy_timeout=5000` for lock contention
- Auto-migration on startup via `src/pybend/core/storage/sqlite_migration.py`
- Manual migrations via `example_grants/migrations/` directory (SQL files)
- JSON fields stored as TEXT with manual serialization (e.g., `AgentActor.constraints`)

## Platform Requirements

**Development:**
- Python 3.10+ (3.11 recommended, 3.11.2 in current environment)
- Node.js (for frontend tests — vitest, Playwright)
- SQLite 3.x (ships with Python stdlib)
- No Docker required for development

**Production:**
- ASGI-capable server (Uvicorn included)
- SQLite database file (or any future AbstractStorage implementation)
- LLM provider access (for agent features):
  - Ollama (local, default: `ollama:llama3.1`)
  - Anthropic API (used in seed: `anthropic:claude-sonnet-4-5-20250929`)
  - Any provider supported by pydantic-ai

**LLM Providers (via pydantic-ai):**
- Ollama — local LLM server, default model string: `ollama:llama3.1`
- Anthropic — cloud API, model string: `anthropic:claude-sonnet-4-5-20250929`
- pydantic-ai TestModel — for testing (`from pydantic_ai.models.test import TestModel`)
- Model string format: `provider:model_name` (resolved by pydantic-ai)

---

*Stack analysis: 2026-03-04*
