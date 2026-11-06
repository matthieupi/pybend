# N3TX

> **Recovery checkpoint — 2026-11-06:** executable source is restored from
> `d75bee4` plus the October 31 deployment's dirty changes, on `reconciliation`.
> Thread/TXRecord live in `n3tx_agents`; canonical TTX and the separate threads
> package are absent. Later documentation below is retained historical material,
> not this runtime's contract. See the
> [application recovery report](../../../.project/docs/reconciliation-20261106.md).

Schema Driven Development (SDD) framework with native agentic integration, for building and extending systems in the AI era software.

N3TX derives storage operations, HTTP routes, JSON Schema and UI contracts from
Python models. Models declare fields, validation, access rules and domain actions.
Optional packages add Web Components, actor messaging, agents and file resources.

## Quick Start

Start with the [issue-tracker tutorial](docs/GETTING_STARTED.md). It includes
registration/login, private issues, public labels, local relationships, URL
references, a validated action, SQLite persistence and the native UI shell.

```text
Python model -> schema + generated routes -> runtime entities + forms
                     |
                     +-> access checks -> model operations -> storage
```

The application still owns its permission policy, domain invariants, deployment
configuration and migration review. UI visibility is not server authorization.

## Installation

Package metadata requires Python 3.10 or newer. Use a virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install n3tx-core n3tx-ui
```

For this checkout, install from the repository root instead:

```bash
python -m pip install -e packages/n3tx-core -e packages/n3tx-ui
```

`python -m pip install n3tx` installs all published packages, including agent
dependencies. Prefer the smaller install when you do not need those capabilities.

## Package Landscape

| Package | Responsibility | N3TX dependencies |
|---|---|---|
| [n3tx-core](packages/n3tx-core/README.md) | Models, SQLite, authorization, FastAPI, non-visual JS runtime | None |
| [n3tx-ui](packages/n3tx-ui/README.md) | Web Components, forms, widgets, model view shells | Core |
| [n3tx-actors](packages/n3tx-actors/README.md) | Actor, Matrix, TX and protocol adapters | Core |
| [n3tx-threads](packages/n3tx-threads/README.md) | TTX interaction storage, semantic Thread roots and model-owned notes | Core, actors |
| [n3tx-agents](packages/n3tx-agents/README.md) | Pydantic AI integration and model-derived tools | Core, actors, threads |
| [n3tx-files](packages/n3tx-files/README.md) | File metadata and separate byte stores | Core, actors |
| [n3tx](packages/n3tx/README.md) | Installation meta-package; `n3tx_meta` re-exports | All above |

## Architecture

| Decision | Options | Guidance |
|---|---|---|
| Construction API | `create_app`, `N3TXApp`, raw registration | Factory for ordinary apps; builder for staged setup |
| Model capability | `ProtoModel`, `ActorModel`, optional mixins | Add only the capabilities the application needs |
| HTTP routing | `direct`, `actor` | Separate from construction; actor routing needs actor-capable models |
| Data change | CRUD patch or exposed method | CRUD for ordinary edits; methods for domain operations |
| Relationship | Local `T`/`list[T]` or URL `Ref[T]` | Read the scalar annotation caveat in [Models](docs/MODELS.md#references) |

An exposed method is not a transaction. SQLite updates are last-write-wins;
read-modify-write actions need an explicit concurrency design when correctness
depends on concurrent writers.

## Documentation

| Need | Guide |
|---|---|
| Learning path and reference map | [Documentation index](docs/README.md) |
| System boundaries | [Architecture](docs/ARCHITECTURE.md) |
| Models and relationships | [Models](docs/MODELS.md) |
| HTTP contract | [API index](docs/API_INDEX.md) |
| Security and enforcement limits | [Authorization](docs/AUTHORIZATION.md) |
| Configuration, backups and migrations | [Operations](docs/OPERATIONS.md) |
| UI extension | [Frontend architecture](docs/frontend/ARCHITECTURE.md) |
| Checked-in applications | [Examples](docs/EXAMPLES.md) |

⚠️ Keep `N3TX_DEBUG=false` for ordinary application use. Built-in registration
assigns **admin** when global DEBUG is true. See Operations for current list-policy
and CORS wiring limitations before exposing a server.

## Testing

From the repository root, with test dependencies installed in your environment:

```bash
python scripts/test-backend.py --list
python scripts/test-backend.py --suite core -- -q
```

The runner isolates suites with different import layouts. Frontend commands and
browser prerequisites are in [tests/frontend](tests/frontend/README.md).
For agent work in this environment, use `/workspace/.venv-agents/bin/python`, not
the surrounding application's environment. Test results for this documentation
rewrite are recorded in [core-report](.project/documentation-overhaul/core-report.md).

## License

[MIT](LICENSE).
