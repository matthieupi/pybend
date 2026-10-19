# N3TX Examples

Start with [Getting started](GETTING_STARTED.md): one complete issue application
with native authentication, explicit owner policy, local relationships, URL
references, a domain action and generated UI shells. Its code is extracted by
the documentation verifier rather than duplicated in a separate test model.

## Checked-in applications

| Directory | Purpose | Boundary |
|---|---|---|
| [core](../examples/core/) | ProtoModel and direct HTTP routes | Inspect setup/seed code before using its database or demo accounts |
| [actors](../examples/actors/) | ActorModel with actor HTTP routing | Also imports agent capabilities; not the minimal provider-free tutorial |
| [chat](../examples/chat/) | Streaming application | Review provider/service prerequisites before executing |
| [grants](../examples/grants/) | Agent-enabled domain application | Not a production deployment or permission template |

Run each application from its own directory after reviewing its entrypoint and
dependencies. Keep test storage separate from application data. See the root
[test instructions](../README.md#testing) for suite isolation.

## E-commerce Platform

Use ordinary model fields for product state, saved local relationships for
independent order items, and exposed methods for genuine domain transitions.
An inventory decrement plus order creation needs an explicit consistency
strategy: multiple saves in one method are not one transaction. Currency,
idempotency, payment handling and stock concurrency are application design work.

## Social Media API

Use protected server-derived ownership and test private feeds at the list
boundary. A body-supplied user ID is not caller identity. Denormalized counters
need concurrency/reconciliation design; a read-increment-save example does not
provide atomic likes or follows.

## Content Management System

Declare content fields and validation on the model; use a publish action only
when publication is a domain operation beyond ordinary CRUD. A publication date
does not create a scheduler. Sanitize untrusted content at its rendering boundary
and keep private drafts protected in both member and collection requests.

## Task Management

The [issue tutorial](GETTING_STARTED.md) is the executable starting point. It
demonstrates merged-state validation and an owner-authorized resolve action.
Assignment, due dates and status fields do not themselves run jobs or agents.

## Authentication System

Reuse BaseUser and the native JWT functions instead of maintaining a second
session model or custom password protocol. See [Authorization](AUTHORIZATION.md).
Keep DEBUG false, review registration policy and restrict generic user CRUD.

## File Upload Service

Use [n3tx-files](../packages/n3tx-files/README.md) for metadata and byte-store
capabilities. A URL string alone does not implement upload validation, protected
downloads or filesystem isolation. Follow the package-owned multipart/binary
routes rather than implementing parallel generic CRUD for bytes.

## Real-time Chat

Read [custom endpoint streaming](API_CUSTOM_ENDPOINTS.md) and
[actor transports](ACTORS.md). Application events, SSE frames and TX envelopes
are different layers. Disconnecting a stream does not undo completed effects.

## Multi-tenant SaaS

A tenant field is not a tenant boundary. Define policy for every enabled read,
list, write, action, file and tool entrypoint. Private direct lists need correct
SQL filtering; AUTHENTICATED alone does not restrict anonymous lists in this
revision. Do not treat an unchecked example as an isolation guarantee.

## Tips for Building APIs

Keep models authoritative, use generated CRUD for ordinary state changes, and
reserve exposed actions for domain behavior. Inspect live schema rather than
duplicating it in frontend types. Test allowed and denied requests, malformed
inputs and persisted values through the intended transport. Complete the
[operations checklist](OPERATIONS.md) before deployment; these examples are not
production-readiness certifications.
