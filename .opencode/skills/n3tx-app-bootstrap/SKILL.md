---
name: n3tx-app-bootstrap
description: N3TX application bootstrap with create_app, N3TXApp, routing levels, distributed remotes, package imports, static files, storage, ManyToMany relationship generation, n3tx-files, and model registration. Use when creating or wiring an N3TX app entrypoint.
argument-hint: "<app bootstrap task>"
---

# N3TX App Bootstrap

## Import order matters

Import packages that register mixins before defining/importing models that use their flags:

```python
import n3tx_ui      # enables __ui__ / ViewableMixin hooks
import n3tx_agents  # enables __agent__ / AgentMixin hooks
import n3tx_files   # enables File typed-argument materialization, when used

from models import Product, User
```

If a model with `__agent__ = True` is defined before `n3tx_agents` is imported, `AgentMixin` will not be injected.

## Level 1: one-liner direct app

```python
from n3tx_core.app import create_app

app = create_app(models=[Product, User], storage='sqlite:///app.db')
```

## Level 3: actor-routed app

```python
app = create_app(
    models=[Product, User],
    storage='sqlite:///app.db',
    routing='actor',
)
```

Use Level 3 when actor/network/agent integration matters. HTTP requests become TX messages routed through `NetworkAPI -> Matrix -> ActorModel`.

## Distributed remotes

Distributed refs use deployment config by default:

```text
N3TX_SERVICE_NAME=api
N3TX_SERVICE_TOKEN=...
N3TX_REMOTES={"storage":{"url":"http://storage:7100","token":"..."}}
```

Apps can override config during bootstrap:

```python
app = create_app(
    models=[Job],
    storage='sqlite:///app.db',
    routing='actor',
    remotes={'storage': {'url': 'http://storage:7100', 'token': '...'}},
    service_name='api',
    service_token='...',
)
```

With `routing='actor'` and configured `remotes`, bootstrap registers
`RemoteMatrix` and injects `MatrixReferenceResolver` into compatible storage
backends. Direct routing can store/canonicalize distributed refs, but remote
method calls and remote populate require actor routing/resolver wiring.

## Builder style

```python
from n3tx_core.app import N3TXApp

pb = N3TXApp(storage='sqlite:///app.db', routing='actor')
pb.model(Product).model(User)
app = pb.build()
```

## Relationships and join models

When manually registering raw primitives, generated join models must be registered too. With the builder/factory, prefer the highest-level API available.

```python
from n3tx_core.models.proto_model import generate_join_model

ProductComment = generate_join_model(Product, Comment)
```

For shared field-declared relationships, prefer `ManyToMany[T]`:

```python
from n3tx_core.models.relationships import ManyToMany

class Product(ActorModel):
    tags: ManyToMany[Tag] = []
```

`create_app()` / `N3TXApp` discover `ManyToMany` fields from the explicit model
classes and generate/register link models in the same preparation flow as join
models.

## File capability bootstrap

`n3tx-files` is absent by default. Add it only when the app uses files:

```python
from n3tx_files import File, LocalFileStore, configure_file_store

configure_file_store(LocalFileStore('./file-blobs'))
app = create_app(models=[File, Product], storage='sqlite:///app.db')
```

If `configure_file_store()` is omitted, `LocalFileStore` uses
`N3TX_FILE_STORE_DIR` or `.n3tx-files/blobs`.

## Static files

At runtime N3TX merges static directories from installed packages:

1. app-specific static dirs
2. `n3tx-agents`
3. `n3tx-ui`
4. `n3tx-core`

The browser sees one URL namespace.

## Bootstrap guardrails

- Do not hand-register duplicate routes for normal model CRUD/actions.
- Do not bypass `create_app()`/`N3TXApp` unless you need raw primitives.
- Keep actor-routed apps on `ActorModel` for addressable capabilities.
- Use actor routing when distributed refs must remote-populate or call methods.
- Keep package import order explicit for UI/agent mixins.
- Keep file byte storage behind `FileStore`; do not mount user uploads as static assets.

## Verification

- Server starts from the app directory.
- `GET /{ClassName}` returns schema.
- `GET /{tablename}` returns data or auth-gated response.
- Static shell loads frontend assets.
- In actor routing, generated HTTP behavior matches direct routes.
- With remotes configured, `RemoteMatrix` is registered and storage has a reference resolver.
- `ManyToMany` link models/tables are present when declared.
- File upload/download routes work when `File` is registered.

## Source-reading policy

Read `AGENTS.md`, app-bootstrap docs, `BACKEND.md`, and `FRONTEND.md` as
appropriate before source. Inspect framework source only when docs/skills are
insufficient, stale, or contradicted by observed behavior. Update or propose
docs/skills when gaps are found.
