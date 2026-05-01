# App Bootstrap

> Part of [n3tx-core](../README.md)

## What This Covers

Application initialization: `create_app()` one-liner, `N3TXApp` builder, routing modes, SSR configuration, static file mounting, and the `config` module. Does not cover Level 3 actor routing (see n3tx-actors docs).

## Architecture

```
create_app() / N3TXApp.build()
  |
  1. Configure auth (jwt_secret, expiry)
  2. Prepare model registrations (pure -- no side effects)
  3. Generate join models
  4. Apply registrations (storage, tables, migrations, global dicts)
  5. Provision app assistant (optional, if app_agent=...)
  6. Create FastAPIBackend (JWT middleware, CORS, SSR)
  7. Register routes (direct or actor)
     - actor mode re-syncs Matrix children to the finalized registered model classes
     - view-capability hooks may add /{ClassName}/@... HTML routes
  8. Mount discovery endpoints (/_meta, /.well-known/agent.json)
  9. Mount static files (framework + app)
  |
  v
FastAPI app (ASGI)
```

## Interface

### create_app() -- Level 1

```python
from n3tx_core.app import create_app

app = create_app(
    models=[Product, User, Comment],
    join_models=[(Product, Comment)],
    storage="sqlite:///app.db",      # URI string or AbstractStorage instance
    routing='direct',                 # 'direct' (Level 1/2) or 'actor' (Level 3)
    ws=False,                         # WebSocket bridge (requires routing='actor')
    static_dir='./static',           # App-specific static files
    jwt_secret='production-secret',
    jwt_expiry_hours=24,
    cors_origins=['https://myapp.com'],
    debug=False,
    ssr=None,                         # None | True | False | 'off'|'schema'|'bundle'|'full'
    app_agent=None,                  # Optional framework-provisioned Assistant config
    name='MyApp',
    version='1.0.0',
    description='A product catalog',
)
```

### N3TXApp -- Level 2

```python
from n3tx_core.app import N3TXApp

builder = N3TXApp(
    storage="sqlite:///app.db",
    routing='direct',
    debug=True,
    app_agent=None,
)
builder.model(Product)
builder.model(User)
builder.join(Product, Comment)
builder.static('./static')
app = builder.build(name='MyApp')
```

All builder methods return `self` for chaining:

```python
app = (N3TXApp(storage="sqlite:///app.db")
    .model(Product)
    .model(User)
    .join(Product, Comment)
    .static('./static')
    .build())
```

### Level 3 -- Raw Primitives

```python
from n3tx_core import register_model, SQLiteStorage
from n3tx_core.api.routes_fastapi import register_routes, router
from n3tx_core.api.backend import FastAPIBackend

storage = SQLiteStorage('app.db')
register_model(Product, storage=storage)
register_model(Comment, storage=storage)

backend = FastAPIBackend(name='MyApp', version='1.0.0', description='', port=5000)
backend.register_routes(registered_models)
app = backend.get_app()
```

### Config Module

```python
from n3tx_core import config

# Defaults (overridable via N3TX_* env vars)
config.BACKEND        # "fastapi"
config.HOST           # "0.0.0.0"
config.PORT           # 5000
config.API_URL        # "http://localhost:5000"
config.SQLITE_DB_FILE # "n3tx.db"
config.JWT_SECRET     # dev default (override in production)
config.DEBUG          # False
config.SSR            # "off"

# Programmatic override
config.configure(host="127.0.0.1", port=8080, debug=True)
```

| Env Var | Config Key | Default |
|---------|-----------|---------|
| `N3TX_BACKEND` | `BACKEND` | `"fastapi"` |
| `N3TX_HOST` | `HOST` | `"0.0.0.0"` |
| `N3TX_PORT` | `PORT` | `5000` |
| `N3TX_API_URL` | `API_URL` | `"http://localhost:{PORT}"` |
| `N3TX_SQLITE_DB` | `SQLITE_DB_FILE` | `"n3tx.db"` |
| `N3TX_JWT_SECRET` | `JWT_SECRET` | dev default |
| `N3TX_DEBUG` | `DEBUG` | `false` |
| `N3TX_SSR` | `SSR` | `"off"` |
| `N3TX_LOG_LEVEL` | `LOG_LEVEL` | `"WARNING"` (or `"DEBUG"` if DEBUG) |

### SSR Modes

| Mode | Behavior |
|------|----------|
| `"off"` | Serve static index.html as-is |
| `"schema"` | Inject model schema `<script>` tags + CSS preloads into HTML |
| `"bundle"` | Replace module imports with a single bundled JS file |
| `"full"` | Both schema injection and JS bundling |

### Discovery Endpoints

Automatically mounted by `build()`:

- `GET /_meta` -- Model registry, capabilities, health status
- `GET /.well-known/agent.json` -- A2A Agent Card for agent discovery

### Optional App Assistant Provisioning

`create_app()` and `N3TXApp` accept an optional `app_agent` dict that can
provision a static `AgentActor` during bootstrap. This is additive: existing
seed scripts and runtime-created agents continue to work unchanged.

When any registered model is agent-enabled (`__agent__ = True`, including
`AgentActor`), bootstrap also registers the agents package's `Thread` model as
framework infrastructure. Agent `run()` / `run_stream()` use `Thread` for
persistent conversation history, so applications do not need to list it in
`models=[...]` manually.

```python
app = create_app(
    models=[Grant, Source, AgentTool, AgentActor],
    join_models=[(AgentActor, AgentTool)],
    storage="sqlite:///app.db",
    app_agent={
        "key": "assistant",
        "name": "Assistant",
        "prompt": "Help operators understand the system.",
        "llm": "ollama:qwen3.5:9b",
        "constraints": {"max_iterations": 12},
        "tools": [
            {"target": "grants", "description": "Grant CRUD"},
            {"target": "sources", "description": "Source management"},
        ],
    },
)
```

Bootstrap looks up the agent by `system_key` first, then falls back to `name`
for compatibility. Tool links are reconciled idempotently on each startup.

### Static File Resolution

Multiple packages can contribute static assets. Resolution order (highest priority first):

1. App-specific directories (via `static_dir` / `.static()`)
2. `n3tx-agents` static (if installed)
3. `n3tx-ui` static (if installed)
4. `n3tx-core` static (always present, catch-all)

When multiple directories exist, a `_CascadingStaticFiles` ASGI handler searches all of them. First file match wins.

### Generated Route Grammar

Direct routing registers table-name data routes, class-name schema/read routes,
and optional model view routes:

```text
GET    /{ClassName}                  # schema
GET    /{ClassName}/{id:int}         # read-only class-name mirror
GET    /{ClassName}/@                # collection default HTML view, if viewable
GET    /{ClassName}/@{view}          # collection named HTML view, if viewable
GET    /{ClassName}/{id:int}/@       # member default HTML view, if viewable
GET    /{ClassName}/{id:int}/@{view} # member named HTML view, if viewable

GET    /{tablename}                  # list
POST   /{tablename}                  # create
GET    /{tablename}/{id:int}         # read
PUT    /{tablename}/{id:int}         # update
DELETE /{tablename}/{id:int}         # delete
POST   /{tablename}/{id:int}/method  # custom instance methods
```

The read mirror delegates to the table-name read handler, so authorization,
population, error handling, and `$id` generation stay identical. HTML routes are
registered through `register_view_routes()` when a model capability provides it;
`n3tx-core` only depends on that small hook and remains UI-package neutral.

## Gotchas

- **`build()` clears global registries.** `registered_models.clear()` and `join_models.clear()` are called at the start of `build()` to support uvicorn `--reload`. This means multiple `build()` calls do not accumulate models.
- **Actor routing re-registers finalized actor models into Matrix.** Actor subclasses may auto-register with the root Matrix at import time, before storage/test bootstrap is finalized. During `build(routing='actor')`, the finalized `registered_models` actor classes are re-registered into Matrix so routing uses the same live classes that storage was attached to.
- **Storage URI parsing is limited.** Only `sqlite:///path` is currently supported. Passing an unrecognized URI raises `ValueError`.
- **SSR parameter accepts multiple types.** `None` reads from config, `True` maps to `"schema"`, `False` maps to `"off"`, strings are validated against `('off', 'schema', 'bundle', 'full')`.
- **JWT middleware is pure ASGI.** It does not use `BaseHTTPMiddleware` (which buffers response bodies and breaks SSE streaming). The token is extracted from the `x-access-token` header, not `Authorization: Bearer`.
- **Streaming routes emit anti-buffered SSE frames.** Each frame includes a comment padding line so proxy/browser buffers flush progressive chunks instead of waiting for the stream to complete.
- **CORS defaults to `["*"]`.** This is intentional for development. Set explicit origins in production. When `"*"` is in the origins list, `allow_credentials` is automatically set to `False`.
- **Static files are mounted last.** `get_app()` mounts the framework static directory as a catch-all ASGI mount. All API routes and explicit file routes take precedence.
- **`@` routes are HTML/view routes.** `/Product/@table` is a view shell, not a JSON data route. Invalid or unknown view names should fail before renderer tags are injected into HTML.
