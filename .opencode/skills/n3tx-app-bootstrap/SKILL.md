---
name: n3tx-app-bootstrap
description: N3TX application bootstrap with create_app, N3TXApp, routing levels, package imports, static files, storage, and model registration. Use when creating or wiring an N3TX app entrypoint.
argument-hint: "<app bootstrap task>"
---

# N3TX App Bootstrap

## Import order matters

Import packages that register mixins before defining/importing models that use their flags:

```python
import n3tx_ui      # enables __ui__ / ViewableMixin hooks
import n3tx_agents  # enables __agent__ / AgentMixin hooks

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
- Keep package import order explicit for UI/agent mixins.

## Verification

- Server starts from the app directory.
- `GET /{ClassName}` returns schema.
- `GET /{tablename}` returns data or auth-gated response.
- Static shell loads frontend assets.
- In actor routing, generated HTTP behavior matches direct routes.

## Source-reading policy

Inspect framework source only when docs/skills are insufficient, do not cover the intended implementation, or observed behavior contradicts docs. Update/propose docs when gaps are found.
