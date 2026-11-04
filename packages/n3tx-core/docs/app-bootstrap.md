# App Bootstrap

Part of [n3tx-core](../README.md). Bootstrap assembles registrations, storage,
HTTP routes and static assets. It returns an ASGI FastAPI application; starting
the listener is a separate server command.

## Architecture

```text
config + capability imports -> model declarations
    -> prepare registrations -> apply storage/table/migration changes
    -> optional assistant provisioning -> FastAPIBackend
    -> direct routes OR actor adapter routes
    -> discovery -> static namespace -> ASGI app
```

## Interface

### Construction versus routing

| Decision | Options |
|---|---|
| Construction | create_app factory, N3TXApp builder, raw registration/backend |
| Model capability | ProtoModel or ActorModel plus optional mixins |
| HTTP execution | direct or actor routing |

Avoid “level 3” as a synonym for both raw construction and actor routing. The
factory and builder can select either routing mode. Actor mode requires suitable
actor-capable models; it does not convert every ProtoModel into an actor.

### create_app

Signature surface (reference):

```python
create_app(models=None, storage=None, routing='direct', ws=False,
           static_dir=None, jwt_secret=None, jwt_expiry_hours=24,
           cors_origins=None, debug=None, ssr=None, app_agent=None,
           app_meta=None, remotes=None, service_name=None, service_token=None,
           name='N3TX', version='1.0.0', description='', **kwargs)
```

Use [Getting started](../../../docs/GETTING_STARTED.md) for a runnable app.
Storage accepts an AbstractStorage instance, `sqlite:///path`, or None for
config.SQLITE_DB_FILE. Other URI schemes are rejected. Register every storable
related model explicitly. `join_models` is rejected; ordinary list[T] does not
need a builder relationship registration step.

### N3TXApp

```python
# Fragment: User and Issue are already declared.
from n3tx_core.app import N3TXApp

builder = N3TXApp(storage='sqlite:///app.db', routing='direct', debug=False)
builder.model(User).model(Issue)
app = builder.build(name='Issues')
```

`model(model_class, storage=None)` optionally overrides storage per model.
`static(directory)` appends an app asset directory. Both return the builder;
`build(name='N3TX', version='1.0.0', description='')` returns the app.

### Raw Primitives

Use native raw construction when you need explicit backend settings. This
fragment supplies CORS directly to FastAPIBackend; the current factory accepts
cors_origins but does **not** forward it to that constructor.

```python
from n3tx_core import config
from n3tx_core.authorize import configure
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import register_model, registered_models
from n3tx_core.api.backend import FastAPIBackend

# User and Issue are already declared. Run once in a fresh process.
configure(jwt_secret=config.JWT_SECRET, jwt_expiry_hours=24)
storage = SQLiteStorage('app.db')
register_model(User, storage=storage)
register_model(Issue, storage=storage)
backend = FastAPIBackend(name='Issues', version='1.0.0', description='',
                         cors_origins=['https://issues.example'])
backend.register_routes(registered_models)
app = backend.get_app()
```

Raw setup does not automatically reproduce factory discovery, actor wiring,
thread infrastructure, agent provisioning or relationship-helper preparation. Do not
claim all construction paths are identical without assembling those pieces.

### Config Module

Set N3TX_* environment values before import. `config.configure(**kwargs)` updates
known globals by uppercase key and rejects unknown keys. It does not recompute
all derived values: changing port alone does not update API_URL. See
[Operations](../../../docs/OPERATIONS.md#configuration) for the configuration table.

Known wiring limits:

- Factory/builder cors_origins is stored but not forwarded. Check actual response
  headers before claiming an origin restriction.
- debug=True sets global DEBUG; debug=False does not reset a previously true
  value. Set N3TX_DEBUG=false before import for non-debug use.
- The factory expiry default is 24 even if config.JWT_EXPIRY_HOURS differs;
  pass jwt_expiry_hours explicitly.
- create_app constructs FastAPIBackend directly; N3TX_BACKEND does not select
  Flask through this API.
- `build()` clears the model registry but does not provide process isolation for
  routers, caches, actor roots or package registries. Use separate processes or
  the existing test fixtures for multiple apps.

### SSR Modes

| Value | Behavior |
|---|---|
| off | Static HTML |
| schema | Schema injection and preload preparation |
| bundle | JS bundling path |
| full | Schema injection plus bundling |

None reads config.SSR; True maps to schema; False maps to off. The tutorial uses
off so it does not require bundling tools. SSR here is bootstrap optimization,
not a separate server-rendered entity UI. Verify bundle prerequisites and output
for your shell before deployment.

### Discovery Endpoints

Factory build mounts `/_meta` and `/.well-known/agent.json`. Treat app_meta and
discovery descriptions as public metadata, not secret configuration. Discovery
is not authorization. Discovery uses `config.API_URL` for its public base URL,
model links and login URL, preserving the configured HTTP or HTTPS origin rather
than deriving it from the listener's HOST/PORT.

### Optional TTX Infrastructure and App Assistant Provisioning

Bootstrap registers only canonical `n3tx_threads.TTX` when selected models use
`__agent__`, `__notes__`, agent ancestry, or the threads package's `TTX`,
`Thread`, `NotesMixin` or `ThreadedMixin` ancestry. Explicit `app_agent`
configuration also selects TTX. Selection depends on the app's capabilities,
not whether an optional package was imported elsewhere. Plain core/actor apps
do not activate history storage. Notes/entry capabilities do not require core
to import `n3tx_agents` or Pydantic AI.

Import `n3tx_threads` before declaring `__notes__` models. `NotesMixin` owns
`NOTE`/`NOTES`; shared entry helpers belong to `ThreadedMixin` in
`n3tx_threads.mixin`. Selecting these capabilities without the installed threads
package raises an explicit dependency error before storage registration.

`Thread(TTX, auto_register=False)` is an empty semantic Python subclass, not a
second container or registered model. **Register TTX only; Thread is semantic.**
It inherits TTX's storage, whose table is `tx_records` and canonical record
identity is `/TTX/<id>`. Explicit Thread/subclass registration and competing
`tx_records` models are rejected before applying registrations in a TTX-enabled
app. An explicit TTX registration retains its storage override; bootstrap does
not add another. Repeated explicit TTX entries use the first registration.

The retired `__thread_roots__` declaration no longer selects infrastructure or
bridges direct HTTP actions through `invoke_threaded`. Generated actions retain
normal native authorization, parsing and direct method invocation. No automatic
capture replacement is installed; future execution history is separate work.

`app_agent` delegates to the agents package's provisioner, which reconciles the
system-key/name-backed assistant and tool links. This is startup database work,
not an LLM run. Configuration and tool selection are described in the
[app_agent configuration](../../../docs/AGENTS.md#app_agent-startup-configuration).
Do not add a second agent runtime.

### Actor and remote setup

Actor mode registers finalized actor classes with Matrix, adds NetworkAPI and
its request auth interceptor, and can add a WebSocket bridge with ws=True.
Configured remotes add RemoteMatrix and inject a reference resolver into compatible
storage. Those are explicit trust/network capabilities. ws=True is only wired
inside actor mode; do not assume it enables a direct-mode socket bridge.

### Static File Resolution

Priority is app directories, agents assets if importable, UI assets if importable,
then core assets. All share one URL namespace; first file match wins. API routes
precede the final catch-all static mount. App assets can override framework files,
so audit collisions and never include secrets or uploaded user content there.

Import `n3tx_ui` before declaring __ui__ models and `n3tx_agents` before declaring
__agent__ models. Static discovery can import packages too late for mixin injection
into models already defined. Missing optional packages mean missing capabilities,
not a guaranteed usable UI or agent fallback.

### Generated Route Grammar

See [CRUD](../../../docs/API_CRUD_ENDPOINTS.md) for exact schema, table/class
mirrors and collection markers. `register_view_routes(router, tag=...)` supplies
optional HTML shells; `register_extra_routes(router, tag=...)` supplies package
wire formats such as multipart/binary file routes. Core calls these hooks without
hard-importing their owning package.

Local list[T] fields do not generate nested CRUD or parent-scoped identity.
View `@` paths never invoke actions. Package-owned routes must enforce their
capability's authorization before metadata or byte operations.

## Gotchas

Registration can drop obsolete columns during migration. Legacy join-backed
collections require an explicit data migration to JSON ID arrays. Uvicorn reload,
multiple workers and multiple app construction are not substitutes for a
single reviewed migration procedure. Read [Operations](../../../docs/OPERATIONS.md).

## Changelog

- 2026-11-04: Document capability-selected TTX-only registration, semantic Thread
  restrictions, mixin ownership and removal of the direct capture bridge.
