# N3TX API Overview

This reference describes generated FastAPI HTTP routes. The running application's
model schemas and `/openapi.json` identify its concrete fields and methods.

## Routing Modes

| Mode | Execution path |
|---|---|
| `direct` | HTTP route factory -> policy/model call -> storage |
| `actor` | HTTP -> NetworkAPI -> TX -> Matrix -> actor-capable model |

Construction via factory, builder or raw primitives is a separate decision.
Shared model operations do not imply universal transport parity. This guide and
the [tutorial](GETTING_STARTED.md) primarily verify direct routing.

## General API Conventions

### Base URL and request format

Core defaults `API_URL` to `http://localhost:5000`. Set `N3TX_API_URL` before
import to the externally reachable origin/prefix. This controls advertised
identities, not Uvicorn's bind address. JSON APIs use `Content-Type:
application/json`. Use POST for parameterized domain actions; current direct
action handlers parse a body even for declared GET methods, which is not a
portable browser request shape.

### Authentication

`BaseUser` subclasses provide register/login. Send returned JWTs through
`x-access-token`. Missing tokens produce empty identity, then the route policy
decides access; malformed/expired tokens return 401. A bearer token alone is not
the normal user-auth header. Service authentication uses a distinct trusted
forwarding protocol; see [remote trust](../packages/n3tx-actors/docs/network-adapters.md#remotematrix-and-remoteref).

### Response format

| Operation | Shape |
|---|---|
| Schema | JSON Schema with N3TX extensions |
| Create/read/update | Entity fields plus top-level `$schema` and `$id` |
| List without limit | Array of entities |
| List with limit | `{data: [...], meta: {total, limit, offset, has_more}}` |
| Delete | `{"message":"Deleted successfully"}` |
| Action | Declared method result; not universally an entity or envelope |
| Stream | `text/event-stream`, not one JSON document |

Direct GET serialization enriches local children. Direct create/update response
validation can omit nested identity metadata. Consumers must not assume that
every nested dict in every response includes `$id`.

### `$id` migration note

An issue fetched at `/issues/1` advertises `/Issue/1`. A child keeps flat identity
such as `/Label/1`, not a parent-scoped URL. Table routes remain available.
`GET /Issue` is schema; `GET /Issue/_` is collection data; `GET /Issue/@` is an
optional HTML shell. Use returned identities rather than reconstructing nested
resource paths.

## Foreign Keys & Relationships

Local `list[T]` stores IDs and returns hydrated models. `Ref[T]` is an absolute
HTTP(S) URL, not an integer foreign key. Scalar model annotation rewriting depends
on inheritance; see [Models](MODELS.md#references). A relation does not generate
parent-scoped nested CRUD or imply child authorization/cascade deletion.

## Data Types

| Python shape | JSON shape |
|---|---|
| str / int / float / bool | String / number / number / boolean |
| Optional value | Value or null if supported by the operation |
| list / dict | Array / object |
| Local model collection | Array of hydrated model objects on reads |
| Ref / list of Ref | URL string / URL array |
| datetime | Serialized timestamp; use explicit timezone-aware application values |
| Enum / Literal | Declared values; inspect schema |

Pydantic validates model input. Direct custom argument conversion is narrower
than general Pydantic validation; see [Actions](API_CUSTOM_ENDPOINTS.md#request-format).

## Error Handling

Check HTTP status before treating a body as success. Error `detail` may be a
string or a validation-error list. Unexpected failures need not return JSON.
Do not display internal traces or source lines to end users.

### Status codes

| Status | Typical direct-route use |
|---|---|
| 200 | Read/list/update/delete and successful custom methods, including login/register |
| 201 | Generated CRUD create |
| 400 | Missing action argument, rejected update shape, MethodError default |
| 401 | Invalid token or invalid login |
| 403 | Evaluated access rule denies |
| 404 | Missing resource |
| 409 | Duplicate registration or explicit action conflict |
| 422 | Pydantic request/update validation or direct action conversion failure |
| 500 | Unhandled server error; not a stable domain validation contract |

Current caveat: direct PUT forwards Pydantic errors into HTTPException detail.
Raw exception objects in validator error context can fail JSON serialization,
turning rejection into 500. JSON-safe `PydanticCustomError` context is used in the
tutorial. A list policy can return an empty result instead of 403; see
[Authorization](AUTHORIZATION.md).

## OpenAPI / Swagger Documentation

`GET /ClassName` is public schema discovery. `/openapi.json` remains available;
`/docs` and `/redoc` are configured only with DEBUG true. Do not enable DEBUG on
an exposed application merely for interactive documentation.

## Optional File API (`n3tx-files`)

Registering File adds metadata CRUD and package-owned byte routes:

| Route | Wire format |
|---|---|
| `POST /files/upload` | Multipart field `upload`; returns File metadata |
| `GET /files/{id}/download` | Binary bytes |
| `GET /File/{id}/download` | Class-name binary mirror |

Range reads and canonical File materialization are covered by the
[File guide](../packages/n3tx-files/docs/file.md). Do not treat binary endpoints
as JSON actions or mount uploaded files in static assets.

## CORS

The backend defaults to wildcard origins with credentials disabled. At this
revision, factory/builder `cors_origins` is not forwarded to FastAPIBackend.
Use the reviewed native backend setup described in
[bootstrap](../packages/n3tx-core/docs/app-bootstrap.md#raw-primitives) or fix
the framework wiring separately before relying on an origin restriction.
CORS is not authorization.

## Rate Limiting and Versioning

Generated APIs do not provide a general rate limiter or application API version
policy. Configure ingress limits and plan schema/client compatibility explicitly.
See [Operations](OPERATIONS.md) and [CRUD](API_CRUD_ENDPOINTS.md).
