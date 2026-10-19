# Getting Started with N3TX

Build a local issue tracker with authenticated users, private issues, public
labels, a resolution action, SQLite persistence and a schema-driven UI. No custom
CRUD routes, client-side model definitions or provider calls are needed.

⚠️ **Trusted-input local demo only—not a safe shared-content UI.** Formidable
currently interpolates some names/titles into HTML without escaping. Public
labels can be created by any registered user. The restricted name alphabet below
rejects HTML-bearing label and issue names; it does **not** sanitize arbitrary
fields, resolutions, existing data or schema text. Use only trusted test
content and do not expose this demo to untrusted users. Read the
[Formidable HTML safety limits](../packages/n3tx-ui/docs/formidable.md#custom-form-path).

## Prerequisites

Python 3.10+ is the package minimum. The documentation verifier uses Python 3.11.
Use a new directory and a virtual environment, not a production database.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install n3tx-core n3tx-ui
```

To use this checkout, substitute the editable install from the
[root README](../README.md#installation). Run subsequent commands in your app
directory with that environment active.

## Configuration

Set these before importing N3TX:

```bash
export N3TX_DEBUG=false
export N3TX_API_URL=http://localhost:5000
export N3TX_JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
```

Keep the same secret when restarting if you want existing tokens to remain valid.
It is not an application data encryption key. Do not commit it.

⚠️ Global DEBUG changes security behavior: `BaseUser.register_user()` grants
**admin** when it is true. Passing `debug=False` alone does not reset a global
DEBUG value previously enabled in the process.

## Your First API

Save this complete block as `main.py`. Import UI before declaring models so its
view capability is registered. Labels are intentionally public; do not put
private information in them. Issue lists use OWNER, not AUTHENTICATED: the latter
does not gate anonymous direct list reads in this checkout.

<!-- tutorial: main.py -->
```python
import n3tx_ui
from pathlib import Path
from typing import Literal
from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError
from n3tx_core import config
from n3tx_core.app import create_app
from n3tx_core.authorize import ANYONE, AUTHENTICATED, NEVER, OWNER, ROLE
from n3tx_core.models.base_user import BaseUser
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.models.ref import Ref
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.erroring import MethodError


class User(BaseUser):
    __tablename__ = 'users'
    __abstract__ = False
    __access__ = {'*': NEVER, 'read': OWNER, 'list': OWNER}


class Label(ProtoModel):
    __tablename__ = 'labels'
    __storable__ = True
    __access__ = {
        '*': NEVER, 'read': ANYONE, 'list': ANYONE,
        'create': AUTHENTICATED, 'update': ROLE('admin'), 'delete': ROLE('admin'),
    }
    __ui__ = {'field_order': ['name']}
    name: str = Field(min_length=1, max_length=40, pattern=r'^[A-Za-z0-9 _-]+$')


class Issue(ProtoModel):
    __tablename__ = 'issues'
    __storable__ = True
    __owner_field__ = 'user_owner'
    __protected_fields__ = {'user_owner'}
    __access__ = {
        '*': NEVER, 'create': AUTHENTICATED,
        'read': OWNER, 'list': OWNER, 'update': OWNER, 'delete': OWNER,
    }
    __ui__ = {
        'field_order': ['name', 'status', 'resolution', 'labels', 'related'],
        'renderer': {'list': 'ntx-list', 'item': 'ntx-item'},
    }
    name: str = Field(min_length=1, max_length=200, pattern=r'^[A-Za-z0-9 _-]+$')
    status: Literal['open', 'closed'] = 'open'
    resolution: str = Field(default='', max_length=2000,
                            json_schema_extra={'ui': {'widget': 'textarea'}})
    user_owner: int = 0
    labels: list[Label] = Field(default_factory=list)
    related: list[Ref[Label]] = Field(default_factory=list)

    @model_validator(mode='after')
    def valid_resolution(self):
        if self.status == 'closed' and not self.resolution.strip():
            raise PydanticCustomError('resolution_required', 'Closed issues require a resolution')
        return self

    @expose_route('/resolve', methods=['POST'], access=OWNER)
    def resolve(self, resolution: str, user: dict = None) -> dict:
        if self.status == 'closed':
            raise MethodError('Issue is already closed', status_code=409)
        if not resolution.strip() or len(resolution) > 2000:
            raise MethodError('Provide a resolution of 1–2000 characters', status_code=400)
        updated = self.update({'status': 'closed', 'resolution': resolution.strip()})
        return {'issue': updated.model_response(), 'resolved_by': user['user_id']}


app = create_app(
    models=[User, Label, Issue],
    storage='sqlite:///issues.db',
    static_dir=str(Path(__file__).parent / 'static'),
    jwt_secret=config.JWT_SECRET,
    debug=False,
    ssr='off',
    name='Issue tracker',
)
```

The issue heading deliberately uses `name`: the native collection create editor
starts with an empty value, and Formidable renders a `name` header input in that
case. A required `title` field would be excluded from the body without getting a
matching header input. This is a tutorial model choice, not a runtime fix.

The validator uses `PydanticCustomError` with JSON-safe context. In this checkout,
the direct PUT error handler can fail to serialize a validator's raw `ValueError`
context and return 500 instead of 422. This does not make the invalid write valid.

User CRUD is intentionally restricted: registration and login are inherited
public methods, while generic user create/update/delete are denied. This avoids
exposing a role-editing endpoint. The inherited registration flow does not verify
email addresses, rate-limit attempts or enforce a password-strength policy.

### Run Your API

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 5000
```

The server binds only to loopback. `N3TX_API_URL` controls advertised identities;
the Uvicorn command controls the listening address. Visit `/Issue` for schema and
`/openapi.json` for HTTP routes. `/docs` is disabled with DEBUG false.

## Test Your API

The commands below use curl from a second terminal. Python can also issue these
requests; the repository verification script uses an in-process HTTP client.

### Register and log in

```bash
curl -i http://localhost:5000/users/register \
  -H 'Content-Type: application/json' \
  -d '{"name":"Alice","email":"alice@example.com","password":"tutorial-only-password"}'

TOKEN=$(curl -fsS http://localhost:5000/users/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"tutorial-only-password"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["token"])')
```

Both successful calls return HTTP 200 with `token` and `user`; `user.role` is
`user`. Wrong credentials return 401; duplicate registration returns 409.
Send the JWT through `x-access-token`, not a user ID in a JSON body.

### Create a label and an issue

These IDs assume a fresh database. Otherwise substitute returned IDs.

```bash
curl -i http://localhost:5000/labels \
  -H "x-access-token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"bug"}'

curl -i http://localhost:5000/issues \
  -H "x-access-token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Fix keyboard navigation","labels":[1],"related":["https://example.invalid/Label/42"]}'
```

Creation returns 201. The issue response has `$schema` ending in `/Issue`, `$id`
ending in `/Issue/1`, and the authenticated user's ID in `user_owner`.

| Field | SQLite representation | Response |
|---|---|---|
| `labels: list[Label]` | Ordered local ID array | Hydrated Label objects; GET responses enrich them with flat `/Label/{id}` identity |
| `related: list[Ref[Label]]` | URL array | URL strings; no remote fetch on ordinary reads |

Direct create/update response validation can omit nested `$schema`/`$id` even
though the top-level identity remains. Use GET to inspect the enriched child
representation; do not assume identical nested metadata on every response path.

The `.invalid` URL demonstrates reference validation without contacting a server.
An integer is not a valid `Ref[Label]`. Referenced labels must be registered and
exist locally for local hydration. See [Models](MODELS.md#references) for scalar
annotation behavior and lifecycle limits.

### List, read and update

```bash
curl -i 'http://localhost:5000/issues?limit=20&offset=0' -H "x-access-token: $TOKEN"
curl -i http://localhost:5000/Issue/1 -H "x-access-token: $TOKEN"
curl -i -X PUT http://localhost:5000/issues/1 \
  -H "x-access-token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Fix keyboard focus order"}'
```

The paginated list is `{data: [...], meta: {total, limit, offset, has_more}}`.
Without `limit`, it is an array. A PUT is a patch: omitted fields remain unchanged;
supplied lists or dictionaries replace the entire field. `{"labels":[]}` clears
the association list, not the Label rows.

### Add custom logic

The model already declares `resolve`. It validates a domain operation, persists
the resolution and reports the caller. The same model validator also rejects a
CRUD patch that closes an issue without a resolution.

```bash
curl -i http://localhost:5000/issues/1/resolve \
  -H "x-access-token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"resolution":"Tab order now follows the visible controls"}'
```

The response is `{issue: {...}, resolved_by: ...}`. The `user` argument is
server-injected; it is absent from method input schema. Calling resolve again
returns 409. Ordinary edits still use CRUD; this action is not the only permitted
way to change status. It is also not an atomic compare-and-set: concurrent
resolution calls can race.

### Check denied and invalid requests

| Check | Expected in this app |
|---|---|
| Anonymous `GET /Issue` | 200, public schema |
| Anonymous `GET /issues` | 200 with `[]`, OWNER SQL filtering |
| Anonymous create with a valid body | 403 |
| Anonymous read of an existing issue | 403 |
| Another registered user's list | Does not include Alice's issue |
| Another user's read/update/resolve/delete of Alice's issue | 403 |
| PUT empty name | 422 |
| PUT `status=closed` without a resolution on an open issue | 422 |
| Action with missing resolution | 400 |
| Invalid token | 401 |

Try these against the generated endpoints, not just direct Python calls.
Direct Python CRUD is trusted application code and does not apply route policy.

## Open the Native UI

Create `static/` beside `main.py` and save this complete shell as
`static/index.html` before starting the server. Bootstrap merges app assets, UI
assets and core runtime into one namespace; no separate static mount is needed.

<!-- tutorial: static/index.html -->
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Issue tracker — local demo</title>
  <link rel="stylesheet" href="/theme-base.css">
  <link rel="stylesheet" href="/light-theme.css">
</head>
<body>
  <p>Trusted-input local demo. <a href="/login.html">Log in</a></p>
  <main id="app">Loading identity…</main>
  <script type="module">
    import { permissions } from '/utils/Permissions.js';
    await permissions.init();
    // No protected elements exist or upgrade before identity is ready.
    await import('/core/NTT.js');
    await import('/components/ntx-item.js');
    await import('/components/ntx-list.js');
    await import('/components/ntx-router.js');
    document.getElementById('app').innerHTML = `
      <ntx-router name="main">
        <ntx-list model="Issue" allow-create></ntx-list>
      </ntx-router>`;
  </script>
</body>
</html>
```

Open `http://localhost:5000/login.html`, log in with the same account, then
explicitly visit `http://localhost:5000/index.html`. Use the collection's create
control, enter a trusted name, and save. Open the new issue, edit its name and
save; use its `resolve` action with a nonempty resolution. Reload to check
persistence. A second account should see only its own issues and receive 403
when requesting the first account's issue through the API. These steps exercise
native entities/forms/actions, not custom data plumbing.

**Verification boundary:** generated HTTP login/create/edit/resolve and second-user
denials passed, but the browser journey is not yet verified: the verification
host cannot launch Chromium because `libglib-2.0.so.0` is absent. Do not interpret
HTTP success as evidence that native form saves/actions work end to end. See the
[T02E correction and verification report](../.project/documentation-overhaul/t02e-report.md).

`/Issue/@`, `/Issue/1/@` and `/Label/@` remain **minimal viewing-only shells for
this tutorial**, not the editing entrypoint: they do not initialize Permissions
on the new page, and the collection shell does not set `allow-create`. A login
token alone does not populate the permissions singleton on each new page.

The HTML shell is public; its data requests still use the generated API's policy.
UI hiding is not enforcement. For a custom renderer or widget, follow
[Frontend architecture](frontend/ARCHITECTURE.md) and preserve native
entity/schema/form handling rather than adding a second fetch-and-state layer.

## Persistence and Cleanup

Stop and restart with the same working directory and secret. `issues.db` retains
users, labels and issues. Confirm the name and resolution with GET. Delete the
issue through its generated route:

```bash
curl -i -X DELETE http://localhost:5000/issues/1 -H "x-access-token: $TOKEN"
```

Successful deletion returns 200 and `{"message":"Deleted successfully"}`;
the next read returns 404. Labels are separate records and remain. To reset the
whole tutorial, stop the server and remove only its disposable database and
SQLite sidecars, or start in a new directory. Never delete a live database.

## Next Steps

| Capability | Native path |
|---|---|
| Actor routing | [Actors](ACTORS.md), then [bootstrap](../packages/n3tx-core/docs/app-bootstrap.md); use ActorModel and verify the selected transport |
| File uploads | [File guide](../packages/n3tx-files/docs/file.md); metadata and bytes have separate storage |
| Agent execution | [Agents](AGENTS.md); use explicit tool scope and provider-free tests first |
| Streaming actions | [Custom endpoints](API_CUSTOM_ENDPOINTS.md#streaming-endpoints); terminal/error behavior is transport-specific |
| Deployment | [Operations](OPERATIONS.md); address list policies, CORS, backups and migrations before exposure |

The [verification artifact](../.project/documentation-overhaul/verify_tutorial.py)
extracts `main.py` from this page rather than maintaining a second application.
Its results and browser-verification limits are recorded in
[core-report](../.project/documentation-overhaul/core-report.md).
