# Decentralized Protocols and PyBend: Architecture Mapping and Integration Analysis

**Audience**: Technical CEO + Engineering Team
**Date**: 2026-02-25
**Scope**: How ActivityPub and ATProtocol map to PyBend's schema-driven architecture

---

## Executive Summary

PyBend's core premise -- "define a model, get a working full-stack application" -- positions it
unusually well for decentralized protocol integration. Both ActivityPub and ATProtocol are, at
their foundation, **schema-driven systems** that derive behavior from data definitions. The
structural parallels are striking:

| Concept | PyBend | ActivityPub | ATProtocol |
|---------|--------|-------------|------------|
| Schema format | JSON Schema | JSON-LD / ActivityStreams | Lexicon |
| Type identity | `$schema` + `$id` URLs | `@context` + `type` + `id` | `$type` NSID |
| Self-describing instances | `model_dump(response=True)` | Every object carries `@context` | Every record carries `$type` |
| Auto-generated endpoints | `register_routes()` | Inbox/Outbox per actor | XRPC per Lexicon |
| Access control | ABAC rules on models | Public/followers/direct addressing | PDS-level + app-level rules |
| Identity | `BaseUser` + JWT | Actor URIs + HTTP Signatures | DIDs + signing keys |

The thesis of this document: **PyBend already has 60-70% of the conceptual machinery needed
for federation**. The remaining 30-40% is protocol-specific plumbing (cryptographic signatures,
specific serialization formats, relay infrastructure) that can be built as additive modules
without disrupting the existing architecture. The result would be a unique value proposition:
*"Define a model, get a federated app."*

---

## 1. Schema Mapping: JSON Schema to ActivityStreams and Lexicons

### 1.1 PyBend's Schema Today

Every PyBend model produces a JSON Schema document via `ProtoModel.schema()`. From
`/workspace/src/pybend/core/models/proto_model.py`:

```python
@classmethod
def schema(cls) -> Dict[str, Any]:
    """Returns the schema for this model."""
    referenced_models = collect_all_referenced_models(cls)
    schema = cls.model_json_schema(ref_template="#/$defs/{model}")

    # Add methods signature to schema
    schema['methods'] = cls.__pybend_methods_json_signature__()

    # Add access rules to schema
    from pybend.core.authorize.schema import access_schema
    schema['access'] = access_schema(cls)

    # Inject __ui__ hints into schema (model-level)
    ui_config = getattr(cls, '__ui__', None)
    if ui_config:
        schema['ui'] = dict(ui_config)
    ...
```

A PyBend schema response looks like:

```json
{
  "$schema": "http://localhost:5000/Schema",
  "$id": "http://localhost:5000/Product",
  "__name__": "Product",
  "__tablename__": "products",
  "properties": {
    "name": {"type": "string", "minLength": 1, "maxLength": 200},
    "price": {"type": "number", "exclusiveMinimum": 0},
    "description": {"type": "string", "default": ""},
    "comments": {"type": "array", "items": {"$ref": "#/$defs/Comment"}}
  },
  "methods": {
    "comment": {"route": "/comment", "methods": ["POST"], "parameters": {...}},
    "favorite": {"route": "/favorite", "methods": ["POST"], "access": {...}}
  },
  "access": {
    "read": {"rule": "anyone"},
    "create": {"rule": "authenticated"},
    "update": {"op": "or", "rules": [{"rule": "owner"}, {"rule": "role", "roles": ["admin"]}]}
  },
  "$defs": {
    "Comment": {"$id": "http://localhost:5000/Comment", "properties": {...}, "methods": {...}}
  }
}
```

### 1.2 Mapping to ActivityStreams Objects

ActivityPub uses ActivityStreams 2.0, which is JSON-LD with a defined vocabulary. Every
object carries a `@context` and a `type`:

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "Note",
  "id": "https://example.com/notes/1",
  "attributedTo": "https://example.com/users/alice",
  "content": "Hello, fediverse!",
  "published": "2026-02-25T12:00:00Z",
  "to": ["https://www.w3.org/ns/activitystreams#Public"]
}
```

**The mapping**:

| PyBend Schema Element | ActivityStreams Equivalent | Transformation Required |
|-----------------------|--------------------------|------------------------|
| `$id` (instance URL) | `id` (object URI) | Direct rename, ensure globally resolvable |
| `$schema` (type URL) | `type` (AS vocabulary term) | Map to AS type vocabulary or extend with custom context |
| `properties.name` | `name` | Direct (AS has `name`) |
| `properties.description` | `content` or `summary` | Field name mapping |
| `model_dump(response=True)` | Object serialization | Add `@context`, map field names |
| `__tablename__` | Collection path in outbox | Conceptual alignment |
| `user_owner` field | `attributedTo` | Semantic mapping |
| `created_at` | `published` | Format alignment (ISO 8601) |
| `ListRef[Comment]` | `replies` collection | Map to AS Collection |

**Concrete translation -- PyBend Product to ActivityStreams Article**:

```python
# PyBend model (existing)
class Product(ProtoModel):
    __tablename__ = 'products'
    name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0)
    description: str = Field(default='')
    comments: ListRef[Comment] = Field(default=[])
```

```json
// Serialized as ActivityStreams object
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    {"pybend": "https://pybend.io/ns/v1"}
  ],
  "type": "Article",
  "id": "https://example.com/products/1",
  "name": "Widget Pro",
  "content": "A premium widget for professionals",
  "attributedTo": "https://example.com/users/alice",
  "published": "2026-02-25T12:00:00Z",
  "pybend:price": 29.99,
  "replies": {
    "type": "Collection",
    "id": "https://example.com/products/1/comments",
    "totalItems": 5,
    "first": "https://example.com/products/1/comments?page=1"
  }
}
```

Key observations:
- Standard fields (`name`, `content`, `published`) map directly to AS vocabulary.
- Domain-specific fields (`price`) require a custom JSON-LD extension context.
- `ListRef` collections map naturally to AS `Collection` / `OrderedCollection`.
- The `$id` / `$schema` pattern PyBend already uses is conceptually identical to
  ActivityStreams' `id` / `type` pattern. Both produce self-describing instances.

### 1.3 Mapping to ATProtocol Lexicons

ATProtocol uses Lexicon, its own schema language similar to JSON Schema. A Lexicon
definition for a post record:

```json
{
  "lexicon": 1,
  "id": "com.example.product",
  "defs": {
    "main": {
      "type": "record",
      "key": "tid",
      "record": {
        "type": "object",
        "required": ["name", "price", "createdAt"],
        "properties": {
          "name": {"type": "string", "maxLength": 200, "minLength": 1},
          "price": {"type": "integer", "minimum": 1},
          "description": {"type": "string", "maxLength": 10000, "default": ""},
          "createdAt": {"type": "string", "format": "datetime"}
        }
      }
    }
  }
}
```

**The mapping**:

| PyBend JSON Schema | ATProtocol Lexicon | Notes |
|-------------------|--------------------|-------|
| `$id` URL | `id` NSID (reverse-DNS) | URL vs NSID format difference |
| `$defs` | `defs` | Nearly identical concept |
| `properties` | `properties` | Same structure |
| `type: "string"` | `type: "string"` | Identical primitives |
| `minLength` / `maxLength` | `minLength` / `maxLength` | Identical constraints |
| `type: "number"` | `type: "integer"` | Lexicon distinguishes int/float |
| `type: "array"` + `$ref` | `type: "array"` + `ref` | Minor syntax difference |
| `methods` | `query` / `procedure` | Methods become XRPC defs |
| `access` rules | No direct equivalent | ATProto handles at PDS layer |

**This is the strongest alignment in the entire analysis.** PyBend's JSON Schema output
and ATProtocol's Lexicon are structurally similar enough that a mechanical translation
is feasible. A `lexicon_schema()` method on ProtoModel could generate valid Lexicon
definitions from the same model that produces JSON Schema today.

---

## 2. Route Mapping: CRUD to Federation Endpoints

### 2.1 PyBend's Route Generation

From `/workspace/src/pybend/core/api/routes_fastapi.py`, routes are auto-generated
from registered models:

```python
def register_routes():
    for model_name, model_class in registered_models.items():
        is_storable = issubclass(model_class, StorableMixin)
        parent_class = getattr(model_class, '__owner__', None)

        if not parent_class:
            tag = model_class.__tablename__.capitalize()
            endpoint_base = f"/{model_name}"
        else:
            tag = model_class.__owner__.__tablename__.capitalize()
            parent_name = parent_class.__name__.lower()
            endpoint_base = f"/{parent_class.__tablename__}/{{parent_id:int}}/{model_class.__tagname__}"

        # Schema endpoint
        router.get(f"/{model_class.__name__}", tags=[tag])(make_get_schema(model_class))

        # CRUD endpoints
        if is_storable:
            router.post(endpoint_base, tags=[tag], status_code=201)(make_create_instance(model_class))
            router.get(endpoint_base, tags=[tag])(make_get_all_instances(model_class))
            router.get(f"{endpoint_base}/{{id:int}}", tags=[tag])(make_get_instance(model_class))
            router.put(f"{endpoint_base}/{{id:int}}", tags=[tag])(make_update_instance(model_class))
            router.delete(f"{endpoint_base}/{{id:int}}", tags=[tag])(make_delete_instance(model_class))

        # Custom @expose_route methods
        for attr_name in dir(model_class):
            attr = getattr(model_class, attr_name)
            if callable(attr) and hasattr(attr, '__endpoint__'):
                ...
```

### 2.2 ActivityPub Endpoint Requirements

ActivityPub requires these endpoints per actor:

```
GET  /.well-known/webfinger?resource=acct:user@domain    # Discovery
GET  /users/{username}                                     # Actor profile
GET  /users/{username}/inbox                               # Inbox (read)
POST /users/{username}/inbox                               # Inbox (receive)
GET  /users/{username}/outbox                              # Outbox (read)
POST /users/{username}/outbox                              # Outbox (publish, C2S)
GET  /users/{username}/followers                           # Followers collection
GET  /users/{username}/following                           # Following collection
POST /inbox                                                # Shared inbox (S2S)
```

**Mapping to PyBend's route generation**:

```
PyBend Today                        ActivityPub Equivalent
-----------------------------------------------------------------
GET  /User                          (schema endpoint, no AP equiv)
GET  /users                         GET /users/{username}/outbox
GET  /users/{id}                    GET /users/{username} (actor)
POST /users                         POST /users/{username}/outbox (C2S)
PUT  /users/{id}                    POST /users/{username}/outbox (Update activity)
DELETE /users/{id}                  POST /users/{username}/outbox (Delete activity)
POST /users/{id}/comment            POST /users/{username}/outbox (Create Note)
--- Missing ---                     POST /users/{username}/inbox (S2S federation)
--- Missing ---                     GET  /.well-known/webfinger
--- Missing ---                     GET  /users/{username}/followers
--- Missing ---                     GET  /users/{username}/following
```

The pattern is clear: PyBend's CRUD maps to ActivityPub's Client-to-Server (C2S) API.
The Server-to-Server (S2S) federation layer is entirely additive.

### 2.3 ATProtocol XRPC Endpoint Requirements

ATProtocol uses XRPC -- HTTP endpoints named by Lexicon NSIDs:

```
GET  /xrpc/com.atproto.identity.resolveHandle    # Handle -> DID
POST /xrpc/com.atproto.repo.createRecord          # Create record
GET  /xrpc/com.atproto.repo.getRecord             # Read record
POST /xrpc/com.atproto.repo.putRecord             # Update record
POST /xrpc/com.atproto.repo.deleteRecord           # Delete record
GET  /xrpc/com.atproto.sync.getRepo               # Sync repository (CAR)
GET  /xrpc/com.atproto.sync.subscribeRepos         # Firehose (WebSocket)
```

**Mapping to PyBend**:

```
PyBend Today                        XRPC Equivalent
-----------------------------------------------------------------
GET  /Product                       GET /xrpc/com.example.getSchema (custom)
POST /products                      POST /xrpc/com.atproto.repo.createRecord
GET  /products                      GET /xrpc/com.example.product.list (custom query)
GET  /products/{id}                 GET /xrpc/com.atproto.repo.getRecord
PUT  /products/{id}                 POST /xrpc/com.atproto.repo.putRecord
DELETE /products/{id}               POST /xrpc/com.atproto.repo.deleteRecord
POST /products/{id}/favorite        POST /xrpc/com.example.product.favorite (custom proc)
--- Missing ---                     GET /xrpc/com.atproto.sync.getRepo (repository sync)
--- Missing ---                     WebSocket subscription firehose
```

PyBend's `@expose_route` decorator maps almost directly to XRPC procedure definitions.
From `/workspace/src/pybend/core/utils/decorators.py`:

```python
def expose_route(route, methods=["POST"], access=None):
    """Decorator to mark a method as an endpoint to be exposed via the API."""
    def decorator(func):
        func.__endpoint__ = {
            'route': route,
            'methods': methods,
            'access': access,
        }
        return func
    return decorator
```

An ATProto-aware version could additionally register XRPC Lexicon definitions:

```python
# Hypothetical extension
@expose_route('/favorite', methods=['POST'], access=AUTHENTICATED)
@xrpc_procedure('com.example.product.favorite')  # New: XRPC registration
def favorite(self, user: User = None) -> str:
    ...
```

---

## 3. Federated Model Design: What Would It Look Like?

### 3.1 The `__federated__` Class Variable

Following PyBend's pattern of model-level declarations (`__storable__`, `__access__`,
`__ui__`), federation would be declared the same way:

```python
from pybend.core.models.proto_model import ProtoModel
from pybend.core.models.base_user import BaseUser
from pybend.core.models.ref import ListRef
from pybend.federation import Federated, ACTIVITYPUB, ATPROTO
from pybend.core.authorize import ANYONE, AUTHENTICATED, OWNER, ROLE
from pydantic import Field
from typing import ClassVar, Optional


class Post(ProtoModel):
    """A federated post that syncs to ActivityPub and/or ATProtocol."""

    __tablename__: ClassVar[str] = 'posts'
    __storable__: ClassVar[bool] = True
    __federated__: ClassVar[dict] = {
        'protocols': [ACTIVITYPUB, ATPROTO],
        'type_mapping': {
            ACTIVITYPUB: 'Note',      # AS2 object type
            ATPROTO: 'app.example.feed.post',  # Lexicon NSID
        },
        'field_mapping': {
            ACTIVITYPUB: {
                'body': 'content',          # Post.body -> AS Note.content
                'user_owner': 'attributedTo',
                'created_at': 'published',
            },
        },
        'visibility': 'public',  # Default federation scope
    }
    __access__: ClassVar[dict] = {
        'read': ANYONE,
        'create': AUTHENTICATED,
        'update': OWNER,
        'delete': OWNER | ROLE('admin'),
    }

    title: str = Field(max_length=300)
    body: str = Field(default='', json_schema_extra={'ui': {'widget': 'textarea'}})
    user_owner: int = Field(default=0)
    created_at: str = Field(default='')
    comments: ListRef['Comment'] = Field(default=[])
```

### 3.2 What `__federated__ = True` Would Auto-Generate

Following the pattern where `__storable__ = True` auto-injects StorableMixin and
`register_routes()` auto-generates CRUD endpoints, `__federated__` would trigger:

**For ActivityPub**:

| Auto-generated | Source | Implementation |
|---------------|--------|----------------|
| Actor endpoint for post author | `BaseUser` model + `__federated__` | GET `/users/{username}` returns AS Actor |
| Inbox endpoint | Model registration | POST `/users/{username}/inbox` |
| Outbox endpoint | Model registration | GET/POST `/users/{username}/outbox` |
| WebFinger response | `BaseUser.email` or handle field | GET `/.well-known/webfinger` |
| HTTP Signature middleware | Auth layer extension | Sign outgoing, verify incoming |
| Followers/Following collections | New relation model | GET `/users/{username}/followers` |
| Activity wrapping on create | `make_create_instance` hook | Wrap in `Create` activity, deliver to followers |
| Activity wrapping on update | `make_update_instance` hook | Wrap in `Update` activity |
| Activity wrapping on delete | `make_delete_instance` hook | Wrap in `Delete` activity |

**For ATProtocol**:

| Auto-generated | Source | Implementation |
|---------------|--------|----------------|
| Lexicon definition | `ProtoModel.schema()` translation | `lexicon_schema()` method |
| XRPC procedure endpoints | `@expose_route` methods | Namespaced XRPC routes |
| DID document | `BaseUser` + key generation | `/.well-known/did.json` |
| Repository (MST) storage | New storage adapter | Merkle Search Tree alongside SQLite |
| Record creation with CID | `StorableMixin.create` hook | Content-addressed records |
| Repo sync endpoint | New route | GET `/xrpc/com.atproto.sync.getRepo` |
| Subscription firehose | New WebSocket route | Event stream of repo changes |

### 3.3 Federated User Model

From `/workspace/src/pybend/core/models/base_user.py`, PyBend's BaseUser provides
authentication primitives. A federated user extends this:

```python
class BaseUser(ProtoModel):
    __storable__: ClassVar[bool] = True
    __abstract__: ClassVar[bool] = True
    __owner_field__: ClassVar[str] = 'id'
    __hidden_fields__: ClassVar[set] = {'password_hash'}

    name: str
    email: str
    role: str = Field(default='user')
    password_hash: Optional[str] = Field(default=None, exclude=True)

    @classmethod
    @expose_route('/login', methods=['POST'], access=ANYONE)
    def login(cls, email: str, password: str) -> dict: ...

    @classmethod
    @expose_route('/register', methods=['POST'], access=ANYONE)
    def register(cls, name: str, email: str, password: str) -> dict: ...
```

A federated extension:

```python
class FederatedUser(BaseUser):
    """User model with federation identity support."""

    __tablename__: ClassVar[str] = 'users'
    __abstract__: ClassVar[bool] = False
    __federated__: ClassVar[dict] = {
        'protocols': [ACTIVITYPUB, ATPROTO],
        'actor_type': 'Person',        # ActivityPub actor type
    }
    __hidden_fields__: ClassVar[set] = {
        'password_hash', 'private_key', 'did_signing_key'
    }

    # Existing BaseUser fields: name, email, role, password_hash

    # Federation identity fields
    handle: str = Field(default='', description="Federated handle (e.g., user@domain.com)")
    public_key: Optional[str] = Field(default=None, description="RSA public key (PEM)")
    private_key: Optional[str] = Field(default=None, exclude=True)
    did: Optional[str] = Field(default=None, description="Decentralized Identifier")
    did_signing_key: Optional[str] = Field(default=None, exclude=True)

    # Federation collections (auto-populated)
    followers: ListRef['FederatedUser'] = Field(default=[])
    following: ListRef['FederatedUser'] = Field(default=[])
```

---

## 4. Identity Mapping

### 4.1 Current: PyBend BaseUser + JWT

PyBend's identity system from `base_user.py` and `backend.py`:

```
Registration:   POST /users/register  -->  create user  -->  return JWT
Login:          POST /users/login     -->  verify password --> return JWT
Auth:           x-access-token header -->  JWTAuthMiddleware decodes -->  request.state.user
Resolution:     _resolve_user() bridges JWT dict to model instance
```

The JWT payload carries `{user_id, email, role}`. The middleware in
`/workspace/src/pybend/core/api/backend.py` extracts it:

```python
class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        token = request.headers.get("x-access-token")
        if token:
            payload = decode_token(token)
            request.state.user = payload
        else:
            request.state.user = {}
        return await call_next(request)
```

### 4.2 ActivityPub Identity: Actors + HTTP Signatures

ActivityPub identifies users as **Actors** -- JSON-LD objects with unique URIs:

```json
{
  "@context": ["https://www.w3.org/ns/activitystreams", "https://w3id.org/security/v1"],
  "type": "Person",
  "id": "https://example.com/users/alice",
  "preferredUsername": "alice",
  "inbox": "https://example.com/users/alice/inbox",
  "outbox": "https://example.com/users/alice/outbox",
  "followers": "https://example.com/users/alice/followers",
  "publicKey": {
    "id": "https://example.com/users/alice#main-key",
    "owner": "https://example.com/users/alice",
    "publicKeyPem": "-----BEGIN PUBLIC KEY-----\n..."
  }
}
```

Discovery happens via WebFinger:

```
GET /.well-known/webfinger?resource=acct:alice@example.com
-->
{
  "subject": "acct:alice@example.com",
  "links": [
    {"rel": "self", "type": "application/activity+json",
     "href": "https://example.com/users/alice"}
  ]
}
```

### 4.3 ATProtocol Identity: DIDs + Signing Keys

ATProtocol uses Decentralized Identifiers (DIDs):

```
Handle:     alice.bsky.social
DID:        did:plc:abc123xyz
DID Doc:    {
              "id": "did:plc:abc123xyz",
              "alsoKnownAs": ["at://alice.bsky.social"],
              "verificationMethod": [{
                "id": "#atproto",
                "type": "Multikey",
                "publicKeyMultibase": "z..."
              }],
              "service": [{
                "id": "#atproto_pds",
                "type": "AtprotoPersonalDataServer",
                "serviceEndpoint": "https://pds.example.com"
              }]
            }
```

### 4.4 Integration Architecture

```
                    PyBend BaseUser
                    (name, email, role, password_hash)
                          |
            +-------------+-------------+
            |                           |
    ActivityPub Identity         ATProtocol Identity
    (public_key, private_key,    (did, did_signing_key,
     actor_uri, webfinger)        handle, pds_endpoint)
            |                           |
    HTTP Signature Auth          DID-based Auth
    (verify incoming POST        (verify record signatures
     to inbox)                    against DID document)
```

The critical insight: **local authentication (JWT) and federated authentication
(HTTP Signatures / DID verification) can coexist**. Local users authenticate via JWT
as today. Incoming federated requests authenticate via HTTP Signature verification
(ActivityPub) or DID key verification (ATProtocol). Both resolve to the same
`AccessContext` that PyBend's ABAC system already uses.

---

## 5. Authorization Interaction: ABAC Meets Federation

### 5.1 Current ABAC System

From `/workspace/src/pybend/core/authorize/rules.py`:

```python
class AccessRule(ABC):
    @abstractmethod
    def evaluate(self, ctx: AccessContext) -> bool: ...

    def sql_filter(self, ctx: AccessContext) -> Optional[Tuple[str, List[Any]]]: ...

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]: ...

    def __or__(self, other): return OrRule(self, other)
    def __and__(self, other): return AndRule(self, other)
    def __invert__(self): return NotRule(self)

ANYONE = _Anyone()          # Always grants access
AUTHENTICATED = _Authenticated()  # Any authenticated user
OWNER = _Owner()            # Resource owner only
```

From `/workspace/src/pybend/core/authorize/context.py`:

```python
@dataclass(frozen=True)
class AccessContext:
    user: Dict[str, Any]    # {"user_id": int, "email": str, "role": str}
    action: str             # "create", "read", "update", "delete"
    model_class: Type[Any]
    resource: Optional[Any] = None
    parent_id: Optional[int] = None
```

### 5.2 Federation Expands the Access Model

Federation introduces new access scopes that map naturally to ABAC rules:

```python
# New federation-aware access rules
class _Federated(AccessRule):
    """Grants access to any authenticated federated actor."""
    def evaluate(self, ctx: AccessContext) -> bool:
        return ctx.is_federated  # New property on AccessContext

    def to_dict(self):
        return {"rule": "federated"}

class _Local(AccessRule):
    """Grants access only to local (non-federated) users."""
    def evaluate(self, ctx: AccessContext) -> bool:
        return ctx.is_authenticated and not ctx.is_federated

    def to_dict(self):
        return {"rule": "local"}

class _Follower(AccessRule):
    """Grants access to followers of the resource owner."""
    def evaluate(self, ctx: AccessContext) -> bool:
        if not ctx.is_authenticated:
            return False
        owner_id = getattr(ctx.resource, ctx.model_class.__owner_field__, None)
        return ctx.user_id in get_follower_ids(owner_id)

    def to_dict(self):
        return {"rule": "follower"}

FEDERATED = _Federated()
LOCAL = _Local()
FOLLOWER = _Follower()
```

**Model-level access with federation**:

```python
class Post(ProtoModel):
    __federated__ = True
    __access__ = {
        'read': ANYONE,                          # Public posts visible to fediverse
        'create': LOCAL & AUTHENTICATED,          # Only local users can create
        'update': OWNER,                          # Only owner can edit
        'delete': OWNER | ROLE('admin'),          # Owner or admin can delete
        'federate': AUTHENTICATED,                # Any local user's posts federate
    }
```

The composability of PyBend's rule system (`|`, `&`, `~`) is a natural fit:

```python
# Only followers can see, but admins always can
__access__ = {
    'read': FOLLOWER | ROLE('admin'),
}

# Federated actors can read but not modify
__access__ = {
    'read': ANYONE,
    'create': LOCAL & AUTHENTICATED,
    'update': LOCAL & OWNER,
}
```

### 5.3 AccessContext Extension

```python
@dataclass(frozen=True)
class AccessContext:
    user: Dict[str, Any]
    action: str
    model_class: Type[Any]
    resource: Optional[Any] = None
    parent_id: Optional[int] = None

    # New federation properties
    @property
    def is_federated(self) -> bool:
        return bool(self.user.get("federated"))

    @property
    def origin_domain(self) -> Optional[str]:
        return self.user.get("origin_domain")

    @property
    def actor_uri(self) -> Optional[str]:
        return self.user.get("actor_uri")
```

The middleware would populate this from HTTP Signature verification:

```python
# In federation middleware (extends existing JWTAuthMiddleware)
if request.headers.get("signature"):
    # Verify HTTP Signature, resolve actor
    actor = await verify_http_signature(request)
    request.state.user = {
        "user_id": actor.local_id or None,
        "email": None,
        "role": "federated",
        "federated": True,
        "origin_domain": actor.domain,
        "actor_uri": actor.uri,
    }
```

---

## 6. Storage Implications

### 6.1 Current Storage Architecture

From `/workspace/src/pybend/core/storage/sqlite_storage.py`:

```python
class SQLiteStorage(AbstractStorage):
    def __init__(self, database: str = 'database.db', pool_size: int = 4):
        self.database = database
        self._migration = SQLiteMigration(database=database)
        self._pool = queue.Queue(maxsize=pool_size)
        init_conn = sqlite3.connect(database, check_same_thread=False)
        init_conn.execute("PRAGMA journal_mode=WAL")
        ...

    def create(self, model_class, data):
        table_name = _validate_identifier(model_class.__tablename__)
        fields = [f for f in model_class.model_fields.keys() if f != 'id' ...]
        insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        ...

    def list(self, model_class, sql_filter=None, limit=None, offset=None, populate=None):
        ...
```

### 6.2 ActivityPub Storage Requirements

ActivityPub needs to store:

| Data | Purpose | PyBend Mapping |
|------|---------|---------------|
| Inbox activities | Received federated content | New `Activity` model, `__tablename__ = 'inbox'` |
| Outbox activities | Published federated content | New `Activity` model, `__tablename__ = 'outbox'` |
| Remote actors | Cached federated users | Extension of `BaseUser` or separate `RemoteActor` model |
| Follow relationships | Follower/following graph | Join model: `UserFollower` |
| Delivery queue | Async outbound delivery | New table or use existing task queue |
| HTTP Signature keys | Per-user keypairs | Fields on `BaseUser` |

All of these fit within PyBend's existing storage model. The inbox/outbox are just
storable models:

```python
class Activity(ProtoModel):
    """Stored ActivityPub activity (inbox or outbox)."""
    __tablename__ = 'activities'
    __storable__ = True

    type: str          # Create, Follow, Like, Announce, etc.
    actor: str         # Actor URI
    object_uri: str    # Target object URI
    object_data: str   # JSON blob of the activity
    direction: str     # 'inbox' or 'outbox'
    delivered: bool = Field(default=False)
    created_at: str = Field(default='')
```

### 6.3 ATProtocol Storage Requirements

ATProtocol's storage model is fundamentally different from a relational database:

| Requirement | Description | Challenge for PyBend |
|------------|-------------|---------------------|
| Merkle Search Tree (MST) | Content-addressed tree of all user records | New data structure, not SQL |
| CIDs (Content Identifiers) | Hash-based record addressing | New field type |
| Signed commits | Cryptographic chain of repository state | New commit model |
| CAR file export | Repository serialization for portability | New serialization format |
| Record keys (TIDs) | Time-ordered record identifiers | New key generation |
| Blob storage | Binary media (images, etc.) | New storage layer |

This is the **hardest integration point**. PyBend's `SQLiteStorage` manages flat tables.
ATProtocol requires a Merkle Search Tree that produces deterministic hashes. Options:

**Option A: Dual storage** -- SQLite for local CRUD (unchanged), MST as a read-only
projection for ATProto sync. Records are written to SQLite normally; a background
process maintains the MST for repository export and sync.

**Option B: MST-native storage** -- Replace SQLiteStorage with an MST-backed store
that also supports SQL queries. The Python library `arroba` (github.com/snarfed/arroba)
implements ATProto repositories in Python and could serve as a foundation.

**Option C: Adapter pattern** -- Keep SQLiteStorage, add an `ATProtoRepositoryAdapter`
that wraps existing storage operations with MST bookkeeping. This follows PyBend's
existing pattern of `AbstractStorage` implementations.

Recommendation: **Option A or C**. Dual storage preserves PyBend's simplicity for the
90% case while enabling ATProto interop for applications that opt in.

---

## 7. Architecture Diagram: Federated PyBend

```
                                    External Fediverse
                                    (Mastodon, Lemmy, etc.)
                                          |
                                    HTTP Signatures
                                          |
                            +-------------+-------------+
                            |                           |
                    ActivityPub S2S              ATProto Relay/BGS
                    (inbox/outbox)              (firehose subscription)
                            |                           |
                            v                           v
+------------------------------------------------------------------+
|                    FEDERATION LAYER (new)                          |
|                                                                    |
|  WebFinger   HTTP Sig     DID          Lexicon      XRPC          |
|  Handler     Middleware   Resolver     Generator    Router         |
|                                                                    |
|  Activity    Activity     Repository   Firehose     Delivery      |
|  Serializer  Deserializer Adapter      Publisher    Queue          |
+------------------------------------------------------------------+
                            |
                            v
+------------------------------------------------------------------+
|                    EXISTING PYBEND CORE                            |
|                                                                    |
|  ProtoModel -----> JSON Schema -----> register_routes()            |
|       |                                     |                      |
|       v                                     v                      |
|  StorableMixin          FastAPI Router (CRUD + custom methods)     |
|       |                      |                                     |
|       v                      v                                     |
|  SQLiteStorage          JWTAuthMiddleware                          |
|       |                      |                                     |
|       v                      v                                     |
|  SQLite DB              AccessContext --> ABAC Rules                |
+------------------------------------------------------------------+
                            |
                            v
+------------------------------------------------------------------+
|                    FRONTEND (NTT.js)                               |
|                                                                    |
|  NTT.SCHEMA() ---> prototype() ---> DynamicClass                  |
|       |                                    |                       |
|       v                                    v                       |
|  Schema-driven rendering    Federation status indicators           |
|  (unchanged for local)      (new: show federated origin,           |
|                              remote actor info, boost/share)       |
+------------------------------------------------------------------+
```

---

## 8. Gap Analysis: What PyBend Has vs. What's Needed

### 8.1 Comprehensive Gap Table

| Capability | PyBend Has Today | ActivityPub Needs | ATProtocol Needs | Effort |
|-----------|-----------------|-------------------|------------------|--------|
| **Schema system** | JSON Schema with `$id`, `$defs` | JSON-LD with `@context` | Lexicon with NSID | Low: translation layer |
| **Self-describing instances** | `model_dump(response=True)` with `$schema`/`$id` | Objects with `@context`/`type`/`id` | Records with `$type` | Low: serializer adapters |
| **REST API** | Auto-generated CRUD + custom routes | Inbox/outbox POST endpoints | XRPC procedures | Medium: new route generator |
| **User model** | `BaseUser` with JWT auth | Actor objects with public keys | DID documents with signing keys | Medium: new fields + key mgmt |
| **Access control** | ABAC rules (ANYONE, AUTHENTICATED, OWNER, ROLE) | Public/followers/direct addressing | PDS-level access | Low: new rule types |
| **Parent-child relations** | `ListRef[T]` + join models | AS Collections + replies | Record references | Low: serialization mapping |
| **Model registry** | `registered_models` dict | N/A (implicit from actors) | Lexicon registry | Already present |
| **WebFinger** | Not present | Required for discovery | Not used | Medium: new endpoint |
| **HTTP Signatures** | Not present | Required for S2S federation | Not used | High: crypto library |
| **JSON-LD** | Not present | Required for ActivityStreams | Not used | Medium: context injection |
| **DID support** | Not present | Not required (uses URIs) | Required for identity | High: DID resolution |
| **Merkle Search Tree** | Not present | Not needed | Required for data repos | High: new data structure |
| **Cryptographic signing** | JWT only | HTTP Signatures (RSA/Ed25519) | Commit signing (secp256k1) | High: key management |
| **Delivery queue** | Not present | Required for async S2S delivery | Not required (relay-based) | Medium: background tasks |
| **Followers/Following** | Not present as first-class | Required collections | Not required (graph on relay) | Medium: new relation model |
| **Content addressing** | Not present | Not required | Required (CIDs) | High: new ID scheme |
| **Repository sync** | Not present | Not needed | Required (CAR export) | High: new protocol |
| **Subscription/firehose** | Not present | Not required | Required (WebSocket) | Medium: new transport |
| **Shared inbox** | Not present | Recommended for efficiency | Not applicable | Low: single new route |

### 8.2 Effort Summary

| Category | Items | Estimated Effort |
|----------|-------|-----------------|
| **Already aligned** (minor adapters) | Schema translation, self-describing instances, access rule extension, model registry | 2-3 weeks |
| **Medium additions** (new modules) | WebFinger, federation routes, delivery queue, JSON-LD context, follower model, XRPC router | 4-6 weeks |
| **Major additions** (new subsystems) | HTTP Signatures, DID support, MST storage, content addressing, repo sync, key management | 8-12 weeks |
| **Total for ActivityPub only** | All AP items | 6-10 weeks |
| **Total for ATProtocol only** | All AT items | 10-16 weeks |
| **Total for both protocols** | All items (with shared infra) | 14-20 weeks |

---

## 9. Implementation Strategy: Phased Approach

### Phase 1: Federation Primitives (Weeks 1-4)

Add the foundational building blocks without changing existing behavior.

**New module**: `src/pybend/core/federation/`

```
federation/
    __init__.py           # Public API: ACTIVITYPUB, ATPROTO constants
    base.py               # FederationMixin (injected like StorableMixin)
    serializers/
        activitystreams.py  # ProtoModel -> AS2 JSON-LD
        lexicon.py          # ProtoModel.schema() -> Lexicon definition
    identity/
        webfinger.py        # WebFinger endpoint handler
        actor.py            # ActivityPub Actor serializer
        did.py              # DID document generation
    crypto/
        http_signatures.py  # Sign/verify HTTP requests
        keys.py             # RSA/Ed25519 key generation and storage
```

**Key deliverable**: A model with `__federated__ = True` auto-generates an
ActivityPub Actor endpoint and WebFinger response. No S2S delivery yet.

### Phase 2: ActivityPub Federation (Weeks 5-10)

Complete ActivityPub Server-to-Server protocol.

```python
# After Phase 2, this works:

class Post(ProtoModel):
    __tablename__ = 'posts'
    __storable__ = True
    __federated__ = {'protocols': [ACTIVITYPUB], 'type': 'Note'}
    __access__ = {'read': ANYONE, 'create': AUTHENTICATED}

    body: str = Field(max_length=500)
    user_owner: int = Field(default=0)

# Creating a Post automatically:
# 1. Stores in SQLite (existing)
# 2. Wraps in Create activity
# 3. Signs with HTTP Signature
# 4. Delivers to followers' inboxes
# 5. Appears in author's outbox

# Receiving a remote post:
# 1. Verifies HTTP Signature
# 2. Resolves remote actor
# 3. Stores activity in inbox
# 4. Creates local representation
# 5. Accessible via normal CRUD routes
```

### Phase 3: ATProtocol Support (Weeks 11-20)

Add ATProtocol as a second federation backend.

This is the harder phase due to MST requirements. Consider using the `arroba`
Python library for repository operations.

---

## 10. Competitive Analysis: "Define a Model, Get a Federated App"

### 10.1 Existing Approaches

| Project | Language | Approach | Federation Story |
|---------|----------|----------|-----------------|
| **Mastodon** | Ruby | Monolithic app | Hard-coded ActivityPub for microblogging |
| **Lemmy** | Rust | Monolithic app | Hard-coded ActivityPub for link aggregation |
| **GoToSocial** | Go | Single-purpose server | Hard-coded ActivityPub for microblogging |
| **federation (Python lib)** | Python | Protocol abstraction library | Abstracts AP/Diaspora but no model-to-federation |
| **bovine** | Python | ActivityPub library | Low-level AP client, no schema-driven generation |
| **arroba** | Python | ATProto PDS library | Repository operations, no schema-driven generation |
| **Django + manual AP** | Python | Manual implementation | Requires hand-wiring every endpoint |
| **Takahē** | Python/Django | Mastodon-compatible server | Purpose-built AP implementation |

### 10.2 What Makes PyBend's Approach Unique

**No existing framework offers model-driven federation.** Every current federated
application is either:
1. A purpose-built application (Mastodon, Lemmy) where federation is hard-coded, or
2. A library (federation, bovine, arroba) that provides protocol primitives but no
   schema-to-endpoint generation.

PyBend's unique position:

```
           Schema-driven                    Federation
           ┌──────────┐                    ┌──────────┐
           │ Django    │                    │ Mastodon │
           │ FastAPI   │                    │ Lemmy    │
           │ Rails     │                    │ GoToSocial│
           │ PyBend    │◄──── gap ────►     │ Takahē  │
           └──────────┘                    └──────────┘

    PyBend with __federated__ bridges this gap:
    The ONLY framework where a model definition produces
    both a local CRUD app AND federated endpoints.
```

The value proposition for a technical audience:

**Before (today's world):**
```python
# Step 1: Define your model (Django/FastAPI/PyBend)
# Step 2: Write ActivityPub serializers manually
# Step 3: Implement inbox/outbox endpoints manually
# Step 4: Add HTTP Signature verification manually
# Step 5: Build delivery queue manually
# Step 6: Write WebFinger handler manually
# Step 7: Keep all of this in sync with model changes
```

**After (PyBend with federation):**
```python
class Post(ProtoModel):
    __tablename__ = 'posts'
    __storable__ = True
    __federated__ = True  # That's it.

    body: str
    user_owner: int
```

---

## 11. What PyBend Already Has That Matters

The following existing PyBend patterns directly enable federation with minimal
modification:

### 11.1 Self-Describing Instances

```python
# From proto_model.py - already injects identity metadata
def model_dump(self, *, response: bool = False, **kwargs):
    data = super().model_dump(**kwargs)
    if response:
        data = {
            '$schema': f"{config.API_URL}/{cls.__name__}",
            '$id': f"{config.API_URL}/{tablename}/{instance_id}",
            **data
        }
    return data
```

This is the same pattern as ActivityStreams' `id` + `type` and ATProtocol's `$type`.
PyBend entities already carry their own identity and type information.

### 11.2 Schema as Universal Contract

PyBend's schema already carries everything federation needs to know:

- **Type information** (`properties`, `$defs`) -- maps to AS types / Lexicon defs
- **Method signatures** (`methods`) -- maps to Activities / XRPC procedures
- **Access rules** (`access`) -- maps to federation visibility
- **UI hints** (`ui`) -- used locally, ignored by federation (clean separation)

### 11.3 Pluggable Storage

The `AbstractStorage` interface means federation storage (MST, activity store)
can be implemented without touching SQLiteStorage:

```python
# Existing abstraction from abstract_storage.py
class AbstractStorage(ABC):
    def create(self, model_class, data): ...
    def list(self, model_class, sql_filter, limit, offset): ...
    def get(self, model_class, id): ...
    def update(self, model_class, id, data): ...
    def delete(self, model_class, id): ...
```

### 11.4 Standalone Auth Package

From `/workspace/src/pybend/core/authorize/`, the auth package has zero PyBend
imports. This means federation auth (HTTP Signatures, DID verification) can plug
into the same `AccessContext`/`AccessRule` system without any coupling to the
federation layer itself.

### 11.5 Model Registration System

From `/workspace/src/pybend/core/utils/registrar.py`:

```python
registered_models: Dict[str, Type[Any]] = {}
join_models: Dict[tuple[str, str], Type[Any]] = {}

def register_model(model_class, storage=None):
    if hasattr(model_class, '__storable__') and model_class.__storable__:
        model_class.set_storage(storage)
        model_class.create_table()
    registered_models[model_class.__tablename__] = model_class
```

A `register_federation()` step would naturally follow `register_model()` and
`register_routes()`, generating federation endpoints for models with
`__federated__` set.

### 11.6 The @expose_route Pattern

```python
def expose_route(route, methods=["POST"], access=None):
    def decorator(func):
        func.__endpoint__ = {
            'route': route,
            'methods': methods,
            'access': access,
        }
        return func
    return decorator
```

Federation activities (Follow, Like, Announce) could be declared the same way:

```python
@expose_route('/follow', methods=['POST'], access=AUTHENTICATED)
@federated_activity('Follow')  # Wraps in Follow activity, delivers to target
def follow(self, target_uri: str, user: User = None) -> str:
    ...
```

---

## 12. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Protocol complexity underestimated | High | Start with ActivityPub C2S only (simplest), validate before S2S |
| ActivityPub spec ambiguity | Medium | Follow Mastodon's implementation as de facto standard |
| ATProto breaking changes | Medium | ATProto is still evolving; IETF standardization underway. Isolate in adapter |
| Performance of MST operations | Medium | Dual storage (SQLite for queries, MST for sync) avoids performance hit |
| Key management security | High | Use established crypto libraries (cryptography, PyNaCl), never roll own |
| Scope creep | High | Phase strictly; Phase 1 deliverable is testable independently |
| Interop testing | Medium | Use ActivityPub test suite (activitypub.rocks) and ATProto PDS test tools |

---

## 13. Conclusion and Recommendation

PyBend's architecture is not just compatible with decentralized protocols -- it is
**convergent** with them. Both ActivityPub and ATProtocol are schema-driven systems
where data definitions determine behavior, which is exactly PyBend's core philosophy.

The structural parallels are deep:

1. **JSON Schema ~ ActivityStreams vocabulary ~ Lexicon definitions** -- all describe
   data shape and behavior from a single source of truth.
2. **`model_dump(response=True)` ~ AS Object serialization ~ ATProto record creation** --
   all produce self-describing, self-addressed data.
3. **`register_routes()` ~ Actor endpoint generation ~ XRPC route registration** --
   all derive API surface from schema.
4. **ABAC rules ~ AP addressing (public/followers/direct) ~ ATProto PDS access** --
   all control visibility declaratively.

**Recommendation**: Begin with Phase 1 (federation primitives) as a low-risk investment
that validates the architectural fit. The key deliverable -- a model with `__federated__`
producing a valid ActivityPub Actor endpoint -- would demonstrate the "define a model,
get a federated app" value proposition with minimal code.

If Phase 1 confirms the mapping (expected: it will), Phase 2 (full ActivityPub) would
make PyBend the first framework where `class Post(ProtoModel): __federated__ = True`
produces a working fediverse node. That is a genuinely unique capability in the current
landscape.

---

## Sources

- [W3C ActivityPub Specification](https://www.w3.org/TR/activitypub/)
- [Understanding ActivityPub - Protocol Fundamentals](https://seb.jambor.dev/posts/understanding-activitypub/)
- [ActivityPub - Mastodon Documentation](https://docs.joinmastodon.org/spec/activitypub/)
- [How to Implement a Basic ActivityPub Server](https://blog.joinmastodon.org/2018/06/how-to-implement-a-basic-activitypub-server/)
- [AT Protocol Lexicon Specification](https://atproto.com/specs/lexicon)
- [AT Protocol Data Repositories Guide](https://atproto.com/guides/data-repos)
- [AT Protocol Repository Specification](https://atproto.com/specs/repository)
- [ATProto PDS Community Wiki](https://atproto.wiki/en/wiki/reference/core-architecture/pds)
- [Bluesky Custom Schemas Guide](https://docs.bsky.app/docs/advanced-guides/custom-schemas)
- [AT Protocol - Wikipedia](https://en.wikipedia.org/wiki/AT_Protocol)
- [ActivityPub - Wikipedia](https://en.wikipedia.org/wiki/ActivityPub)
- [Fediverse Protocol Stack (Codeberg)](https://codeberg.org/GuildAlpha/LibRate/wiki/The+Fediverse+Protocol%3A+ActivityPub%2C+AS2+%2C+Webfinger%2C+HTTP+Signature%2C+Nodeinfo%2C+JSON-LD+-+and+what+else%3F.-)
- [Python federation library (GitHub)](https://github.com/jaywink/federation)
- [arroba - Python ATProto PDS implementation (GitHub)](https://github.com/snarfed/arroba)
- [Experiences writing an ActivityPub server in Python with Django](https://checkmyworking.com/posts/2023/02/experiences-writing-an-activitypub-server-in-python-with-django/)
