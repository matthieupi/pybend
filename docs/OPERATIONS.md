# Operations

This is a deployment checklist, not a claim that the tutorial is production-ready.
Start with the [runnable application](GETTING_STARTED.md) and
[bootstrap reference](../packages/n3tx-core/docs/app-bootstrap.md).

## Configuration

Set environment values before importing N3TX or declaring models. Keep secrets
outside Git, static directories, images and public discovery metadata.

| Variable | Default | Operational meaning |
|---|---|---|
| `N3TX_API_URL` | `http://localhost:5000` (port override applies) | Public canonical schema/entity URL; set explicitly behind a proxy |
| `N3TX_HOST`, `N3TX_PORT` | `0.0.0.0`, `5000` | Framework address configuration; separately configure your ASGI listener |
| `N3TX_SQLITE_DB` | `n3tx.db` | Database path when bootstrap does not supply storage |
| `N3TX_JWT_SECRET` | Development secret | Replace with a strong deployment secret |
| `N3TX_JWT_EXPIRY_HOURS` | `24` | Auth configuration; factory defaults to 24 unless explicitly passed |
| `N3TX_DEBUG` | `false` | Keep false: DEBUG registration grants admin and errors expose more detail |
| `N3TX_LOG_LEVEL` | WARNING, DEBUG when debug enabled | Framework logger verbosity |
| `N3TX_SSR` | `off` | Bootstrap optimization mode; validate bundle prerequisites before enabling |
| `N3TX_SERVICE_NAME` | `api` | Distributed service identity |
| `N3TX_SERVICE_TOKEN` | Empty | Trusted service credential; do not expose to browsers |
| `N3TX_REMOTES` | `{}` | JSON remote-service configuration; review trust and network destinations |

`config.configure()` changes globals, not all derived values or already-built
routes. Changing port does not recompute API_URL there. Factory `debug=False`
does not reset an already true global DEBUG. Start a fresh process with reviewed
environment values rather than toggling production settings after import.

## Before exposing HTTP

1. Terminate TLS and verify canonical URLs, proxy routing and discovery output.
2. Use native BaseUser authentication; restrict generic user CRUD and public
   registration according to your application policy. Rotate leaked credentials.
3. Test anonymous, owner, other-user and administrator requests on every enabled
   transport. Direct lists use SQL policy alone: AUTHENTICATED is not a safe
   private-list gate in this revision. See [Authorization](AUTHORIZATION.md).
4. Test actual CORS headers. Factory/builder `cors_origins` is not forwarded to
   FastAPIBackend; use the [raw backend setup](../packages/n3tx-core/docs/app-bootstrap.md#raw-primitives)
   when explicit backend CORS is required. CORS is not authorization.
5. Review public schemas/discovery for sensitive metadata. Hiding a form field
   does not remove it from data responses or enforce write restrictions.
6. Keep credentials, SQLite files and private uploads outside static directories.
   App static files override package files by name; audit collisions.
7. Configure operational limits at the appropriate boundary: request sizes,
   authentication throttling, timeouts and agent budgets are not supplied by a
   model declaration. Do not enable paid providers during smoke tests.

## Migrations

Registration changes the database. SQLite auto-migration adds missing columns
and attempts to drop columns absent from the model; it is **not additive-only**.
Renames, type changes, backfills and legacy join-to-JSON transitions require
explicit review. See the [storage migration contract](../packages/n3tx-core/docs/storage.md#migrations).

```text
review model/schema diff -> consistent backup -> restore into isolated database
    -> run new registration/migrations -> verify data and permissions
    -> approve rollout -> start reviewed release -> smoke checks
```

Coordinate writers during migration; do not rely on every worker independently
starting against an old database. Preserve a compatible application release and
tested restore procedure. A migration `down()` cannot reconstruct dropped data.

## Persistence and recovery

- Use a durable, writable volume with restricted access and monitor free space.
- SQLite WAL/busy timeout reduces some contention; it does not remove single-writer
  limits or guarantee lock-free operation. Domain methods are not automatically
  transactions, and updates are last-write-wins.
- Use a SQLite-consistent backup mechanism or stop writers before copying the
  database and required journal state. A casual live copy of only the main file
  is not a verified backup.
- Restore into isolation and check integrity, representative records, relationships,
  auth and a real process restart. Record recovery time and data-loss expectations.
- Keep backups and request logs free of avoidable tokens, passwords and private
  payloads. Protect them according to the data they actually contain.

## Release verification

| Check | Required evidence |
|---|---|
| Schema and CRUD | Correct canonical identities, validation and persisted values |
| Authorization | Allowed and denied requests, including private lists and actions |
| Relationships | Saved local children, replacements, unresolved targets and URL refs |
| Browser | Login, generated forms/actions, collection/member rendering and console errors |
| Restart | Existing data readable after stopping and restarting the process |
| Recovery | Restored backup works with the intended application release |
| Optional transports | Separate actor/WebSocket/tool caller and policy checks |

The tutorial verifier checks in-process HTTP, SQLite values and HTML/asset
delivery. Those checks do not establish browser rendering, restart durability,
concurrency safety, remote-reference behavior or production readiness.
