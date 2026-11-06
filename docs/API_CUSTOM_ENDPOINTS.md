# Custom Endpoints

Expose domain behavior on a model with `n3tx_core.utils.decorators.expose_route`.
Use generated CRUD for ordinary field changes. A method is appropriate when an
operation has domain inputs, validation or a distinct result, as with the
[tutorial's resolution action](GETTING_STARTED.md#add-custom-logic).

## Overview

```python
expose_route(route, methods=['POST'], access=None, stream=False, events=None)
```

The decorator attaches route metadata. Bootstrap generates the HTTP route;
schema generation publishes its contract; native UI can render method controls.
This does not make the method's internal writes authorized, atomic or retry-safe.

## Endpoint URL Patterns

| Declaration | Schema scope | requires_instance | Route suffix |
|---|---|---:|---|
| `def resolve(self, ...)` | instancemethod | true | `/{id}{route}` |
| `@classmethod def action(cls, ...)` | classmethod | false | `{route}` |
| `@staticmethod def action(...)` | staticmethod | false | `{route}` |
| Service-style function without self/cls | actormethod | false | `{route}` |

Both table and class-name prefixes are generated for literal exposed methods.
Use the schema's `route`, not a guessed conversion of the Python method name.
`/Issue/1/@resolve` is a view named resolve, not the action `/Issue/1/resolve`.

### Static Method

Use `@staticmethod` outside `@expose_route`. Static actions have no resource
instance for OWNER/Where checks. Choose a policy appropriate to class scope.

### Class Method

Use `@classmethod` outside `@expose_route`. BaseUser's login and register methods
are examples. Inherit them rather than implementing authentication as an email
lookup or creating a parallel session store.

### Instance Method

The generated handler loads the row, returns 404 if absent, and evaluates action
policy against the instance before invoking the method. A rule on an action
does not automatically authorize every other resource that its body reads or
writes. Batch operations must apply the relevant policy to each target.

## Automatic User Injection

`user` is reserved. Direct routing skips body-supplied user values and resolves
the authenticated identity:

| Annotation | Passed value |
|---|---|
| Concrete StorableMixin subclass, e.g. `User` | `User.get(user_id)` |
| `dict`, no recognized model annotation | JWT identity dictionary |
| No authenticated identity | No argument injected; provide `user=None` if needed |

The identity dictionary normally contains `user_id`, `email`, `role`, `iat` and
`exp`. Optional/union annotations are not the concrete-class branch. Prefer a
concrete annotation with a None default. Never fall back to user ID 1 or trust a
body-supplied owner as proof of authority.

The standalone authorization package knows dictionaries, not model classes.
`_resolve_user` is the bridge. Verify identity propagation separately when
enabling actor, service or tool entrypoints.

## Request Format

Send POST with a JSON object keyed by declared argument names. `self`, `cls` and
`user` are not body arguments. For a method without application parameters, `{}`
or an omitted body is accepted by the direct handler.

### Current direct-parser limits

| Case | Actual behavior |
|---|---|
| Missing/null ordinary argument | 400, including arguments with Python defaults |
| Concrete Pydantic model argument | Constructed/validated from a dict |
| Other annotated argument | Converted by calling its annotation with the raw value |
| Unsupported annotation/conversion | Usually 422 |
| GET action with parameters | Handler still expects a body; browser Fetch forbids GET bodies |

Schema `required` follows Python defaults, but the direct parser does not honor
those defaults. Supply each ordinary argument explicitly and use simple scalar
or concrete model inputs that have been tested through the route. Do not assume
`list[int]`, unions or boolean strings receive full TypeAdapter semantics.
These limitations are not a recommendation to build parallel routes; framework
parser improvements are separate work.

## Response Format

### Explicit interaction storage

The former `__thread_roots__` / `invoke_threaded` capture bridge is removed.
Generated direct routes call the Python action after their normal lookup,
authorization and input parsing; composing `ThreadedMixin` does not redirect
actions through Matrix or capture them automatically.

Model actions may explicitly append TTX interactions through the shared
parent-authorized helpers. Notes exposes `NOTE(message)` and `NOTES()`; agent
execution stores finalized Message TTXs under semantic Thread roots. These
operations do not provide automatic UPDATE history or transactional logging.
See [TTX storage and notes](../packages/n3tx-threads/docs/thread.md).

Direct routing returns the method result and FastAPI applies the declared return
model when present. It does not universally call `model_response()` on custom
results. For an enriched entity, explicitly include `entity.model_response()` in
a dictionary, as the tutorial does. Plain dictionaries and scalars are not
automatically given entity metadata. Returning a JSON string is different from
returning a dictionary.

Global DEBUG wraps synchronous method results in `{data, _debug}`; async
coroutines and generators pass through. Do not build a production client around
debug envelopes or assume action responses match across transports.

## Error Handling

For a deliberate domain rejection, raise the native error:

```python
from n3tx_core.utils.erroring import MethodError

# Inside an exposed method:
raise MethodError('Issue is already closed', status_code=409)
```

Direct handlers translate MethodError into HTTP status/detail. Ordinary
ValueError from the method body is not universally converted into 400. Request
conversion errors, missing arguments, missing instances and access denial have
their own status paths; see [API overview](API_OVERVIEW.md#error-handling).

## Discovering Custom Endpoints

`GET /Issue` publishes `methods.resolve` with route, HTTP methods, scope,
requires_instance, parameters, required, returns and explicit access metadata.
`stream` and `events` appear for declared streaming methods. Check the actual
schema and enabled transport rather than inferring behavior from a decorator
alone.

## Type-Driven File Materialization

Importing `n3tx_files` registers a type-gated method argument materializer. A File
parameter can receive a canonical local absolute File `$id`; an ordinary string
parameter remains a string. Materialization resolves authorized metadata, not
arbitrary external bytes. Byte access and caller propagation remain explicit.
See [File capability](../packages/n3tx-files/docs/file.md); do not return local
filesystem paths to untrusted callers as a processing result.

## Streaming Endpoints

Reference fragment inside a model, with `asyncio`, `expose_route` and the access
rule imported:

```python
@expose_route('/progress', methods=['POST'], stream=True, access=OWNER)
async def progress(self, count: int):
    if not 1 <= count <= 5:
        raise MethodError('count must be 1–5')
    for index in range(count):
        await asyncio.sleep(0)
        yield {'name': 'progress', 'data': {'completed': index + 1}}
```

An async generator's body starts during iteration, after HTTP headers may have
been sent. Consequently even this input guard can become a stream-time failure,
not a normal JSON error response. Test both paths before exposing a stream.

Direct routing wraps each yielded value in SSE `event: chunk`, then sends
`event: done` with `{}` on normal completion. Frames include comment padding and
anti-buffering headers. An application event named `done` inside chunk data is
not transport completion.

**Current direct-stream limit:** the generator wrapper does not catch iteration
exceptions and synthesize an SSE error event. A failure can terminate the
connection without `done`. Clients must distinguish clean completion from error
or disconnect. Actor streams have their own TX/error protocol; see the
[adapter reference](../packages/n3tx-actors/docs/network-adapters.md).

The native HTTP stream client returns a cancellation handle; `<ntx-stream>`
manages its lifecycle. Cancellation stops client consumption, not a guaranteed
rollback of completed writes or external work. Use
[frontend architecture](frontend/ARCHITECTURE.md) for imports and component
extension rather than duplicating the stream parser.

## Common Custom Endpoint Patterns

| Need | Guidance |
|---|---|
| Authentication | Inherit BaseUser; restrict generic User writes |
| Field/status edit | Use CRUD patch unless a domain operation adds meaning |
| State transition | Validate invariant at model boundary as well as action guard |
| Search/aggregation | Apply list policy; direct `Model.list()` is not an authorized query |
| Batch operation | Authorize targets and define partial-failure/retry behavior |
| Append/remove/toggle | Model-owned action; explicit concurrency design, no automatic atomicity |

## Troubleshooting

Check the literal schema route and scope for 404s; required arguments for 400s;
actual conversion rules for 422s; and both model and action policies for 403s.
Validate through HTTP with DEBUG false. A successful direct Python invocation
does not verify route parsing, caller injection, serialization or access control.
