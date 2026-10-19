# N3TX API Documentation Index

| Question | Reference |
|---|---|
| Which URL, headers and error shapes? | [API overview](API_OVERVIEW.md) |
| How do I create, list, read, patch or delete? | [CRUD endpoints](API_CRUD_ENDPOINTS.md) |
| How do I invoke a domain action or stream? | [Custom endpoints](API_CUSTOM_ENDPOINTS.md) |
| Where are actual model fields and methods? | [Data models / schema discovery](API_DATA_MODELS.md) |
| Which Python modules own the API? | [Python API reference](API_REFERENCE.md) |
| What is authorized? | [Authorization](AUTHORIZATION.md) |
| How do I build an application? | [Getting started](GETTING_STARTED.md) |

## Quick Reference

For `Issue` with `__tablename__ = 'issues'`:

| Purpose | Route |
|---|---|
| Schema | `GET /Issue` |
| Collection | `GET /issues` or `GET /Issue/_` |
| Create | `POST /issues` or `POST /Issue` |
| Read/update/delete | `GET/PUT/DELETE /issues/{id}` or `/Issue/{id}` |
| Instance action | Declared path, e.g. `POST /Issue/{id}/resolve` |
| Native HTML view | `GET /Issue/@` or `/Issue/{id}/@`, if viewable |

`@` means a view, not an action. Class-name `$id` values remain flat even when
an entity is rendered inside another entity. See [CRUD](API_CRUD_ENDPOINTS.md)
for pagination, population and replacement semantics.

## Tools & Resources

Inspect `GET /ClassName` and `/openapi.json` on the running app. FastAPI's `/docs`
and `/redoc` are enabled only under global DEBUG in this checkout. Do not enable
DEBUG on an exposed service just to get the explorer: registration then grants
admin. Use the schema endpoints and [operations guidance](OPERATIONS.md).
