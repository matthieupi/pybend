# N3TX Core

Core turns model declarations into schema, storage operations and direct HTTP
routes. It also ships the non-visual JavaScript entity/messaging runtime.
Visual components belong to `n3tx-ui`; Python actor messaging belongs to
`n3tx-actors`.

## Schema-Driven Development

| Declare | Derived behavior | Application responsibility |
|---|---|---|
| Pydantic fields and validators | Input validation and property schema | Domain constraints and migration review |
| `__storable__`, `__tablename__` | StorableMixin and generated CRUD after registration | Storage choice and registration |
| `__access__` | Policy metadata and route/handler checks | Explicit policy and denied-access tests |
| `@expose_route` | Method schema and HTTP action | Domain logic, validation and side effects |
| `__ui__` with UI imported first | Viewable capability and rendering hints | Presentation customization, not duplicate schemas |
| `list[T]` | Ordered local relationship IDs and hydrated responses | Child lifecycle and access design |
| `Ref[T]` | Typed HTTP(S) identity URL | Explicit dereference and remote trust |

## Schema as Universal Contract

```text
Model.schema() -> properties + methods + access + ui + $defs
                                      |
                                      v
                     runtime entity classes -> native forms/components
Model.model_response() -> fields + $schema + $id
```

The schema carries validation and presentation information. It does not execute
authorization in a client. Read the [enforcement matrix](AUTHORIZATION.md#architecture)
before relying on a policy across different entrypoints.

## Key Patterns

Use generated CRUD for ordinary changes. A custom action belongs on the model
when it expresses domain behavior beyond a field edit. Neither an action nor a
complete-object save makes concurrent writes atomic.

Local objects and URL pointers are separate primitives. The first injection of
StorableMixin rewrites some bare scalar annotations; see the exact
[relationship contract](MODELS.md#references) before choosing a scalar field.

## Directory Structure

Implementation lives in `packages/n3tx-core/src/n3tx_core/`:

| Directory/file | Responsibility |
|---|---|
| `app.py`, `config.py` | Construction and process configuration |
| `models/` | ProtoModel, StorableMixin, BaseUser, schema/dump pipelines, refs |
| `api/` | FastAPI routes, identity middleware, static serving, discovery |
| `storage/` | Storage interface, SQLite and migrations |
| `authorize/` | Model-independent rules, JWT and resolver APIs |
| `utils/`, `widgets/` | Registration, introspection, decorators and field extensions |
| `static/` | JavaScript runtime and transport |

## Running

Follow the [tutorial](GETTING_STARTED.md), not a framework-internal `main.py`.
For checked-in applications see [Examples](EXAMPLES.md).

## Testing

The [root README](../README.md#testing) gives suite commands. Mechanism references:
[bootstrap](../packages/n3tx-core/docs/app-bootstrap.md),
[storage](../packages/n3tx-core/docs/storage.md),
[schema pipeline](../packages/n3tx-core/docs/schema-pipeline.md).
