# n3tx-core

Models, schema and response pipelines, SQLite storage, authorization, generated
FastAPI routes, and the non-visual JavaScript runtime. Core has no dependency on
the other N3TX packages.

## Installation

In a Python 3.10+ virtual environment:

```bash
python -m pip install n3tx-core
```

For development, run `python -m pip install -e 'packages/n3tx-core[dev]'` from
the repository root. Install `n3tx-ui` separately for native visual components.

## Quick Start

This is a public, read-only catalog. It intentionally denies HTTP writes and
does not provision authentication users. Save as `main.py`:

```python
from n3tx_core.app import create_app
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.authorize import ANYONE, NEVER

class Entry(ProtoModel):
    __storable__ = True
    __tablename__ = 'entries'
    __access__ = {'*': NEVER, 'read': ANYONE, 'list': ANYONE}
    name: str

app = create_app(models=[Entry], storage='sqlite:///catalog.db', debug=False)
```

Run `python -m uvicorn main:app --host 127.0.0.1 --port 5000` with
`N3TX_DEBUG=false` and `N3TX_API_URL=http://localhost:5000` set before import.
`GET /Entry` returns schema; `GET /entries` returns an initially empty list.
For a writable app with users, relations and UI, use the
[complete tutorial](../../docs/GETTING_STARTED.md).

## API Reference

| Import | Purpose |
|---|---|
| `n3tx_core.models.proto_model.ProtoModel` | Fields, schema and response serialization |
| `n3tx_core.models.base_user.BaseUser` | Inherited registration/login and password hashing |
| `n3tx_core.models.ref.Ref` | Typed HTTP(S) entity URL |
| `n3tx_core.models.storable_mixin.StorableMixin` | Injected CRUD and save operations |
| `n3tx_core.app.create_app`, `N3TXApp` | FastAPI construction |
| `n3tx_core.utils.decorators.expose_route` | Domain-action exposure |
| `n3tx_core.utils.registrar.register_model` | Storage-backed registration |
| `n3tx_core.storage.sqlite_storage.SQLiteStorage` | SQLite backend |
| `n3tx_core.authorize` | Rules, context, resolver and JWT helpers |

`ViewableMixin` belongs to `n3tx_ui`, not core. Use package-qualified imports to
make optional dependencies visible. See [Models](../../docs/MODELS.md) for
annotation rewriting and [Authorization](../../docs/AUTHORIZATION.md) for the
direct-list policy limitation. Direct Python CRUD does not enforce HTTP policy.

## Deep Dives

| Guide | Scope |
|---|---|
| [App bootstrap](docs/app-bootstrap.md) | Factory, builder, raw setup and static assets |
| [Storage](docs/storage.md) | Updates, hydration, JSON, population and migrations |
| [Schema pipeline](docs/schema-pipeline.md) | Stages, cache and package extensions |
| [Authorization](docs/authorization.md) | Rules, context and resolver API |
| [Operations](../../docs/OPERATIONS.md) | Deployment defaults and known limits |
