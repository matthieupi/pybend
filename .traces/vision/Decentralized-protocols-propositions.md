# 🔧 Decentralized Protocols × Our System: Technical Propositions

> *How decentralized protocol principles can improve our architecture.*
> *Based on research in `.traces/research/decentralized-protocols/` and codebase analysis.*

---

## 🎯 The Bridge

PyBend and decentralized protocols are solving the same problem from opposite ends. PyBend says: "Define a model once, derive the entire stack." Decentralized protocols say: "Carry a schema everywhere, and any node can participate." Both are schema-driven, self-describing, and derive behavior from data definitions. The difference is scope: PyBend operates within a single deployment; decentralized protocols operate across trust boundaries.

The deep structural convergence is not coincidence. `ProtoModel.schema()` generates JSON Schema with `$id` and `$schema` URLs on every entity -- the same self-describing pattern that ActivityPub uses (`@context` + `id`) and AT Protocol uses (`$type` + DID). Our `model_dump(response=True)` already injects globally-resolvable identifiers into every API response. Our Actor-based message bus (`Matrix.js`) routes messages by address in the same way Nostr relays route events by pubkey. The conceptual distance is shorter than it appears.

The propositions below are not about making PyBend a federation framework. They are about importing the *principles* that make decentralized systems resilient -- self-describing data, portable identity, content-addressable integrity, composable authorization -- and applying them where they make our centralized architecture demonstrably better. Some are afternoon changes. Some reshape entire subsystems. All trace directly to both the research and our codebase.

---

## 💡 Propositions

### Proposition 1: Make entity identity truly self-sovereign with content-addressable $id

> 🔧 **Proposition:** Enrich `model_dump(response=True)` so that every entity carries a cryptographic content hash alongside its URL-based `$id`, enabling tamper-evident verification without a trust chain.

**From the research:** AT Protocol's Merkle Search Tree stores every record as a content-addressed DAG-CBOR object. The content hash (CID) *is* the identity -- any two systems with the same data produce the same hash. This makes data self-verifying: you do not need to trust the server that sent it, only the math. Nostr takes the same approach: every event's `id` field is the SHA-256 of its serialized content. [02-technical-deep-dive.md, sections 2.3 and 3.2]

**In our system:** `proto_model.py` lines 117-137 inject `$schema` and `$id` as URL-based identifiers. These are *location-based* -- they tell you where to find the entity, but not whether the entity has been tampered with in transit or at rest. The storage layer (`sqlite_storage.py`) has no integrity verification mechanism. If the database is modified directly, there is no way to detect it.

**The idea:** Add an optional `__content_hash__` class variable to `ProtoModel`. When enabled, `model_dump(response=True)` computes a SHA-256 hash over the canonical JSON of the entity's data fields (excluding `$schema`, `$id`, and the hash itself) and includes it as `$hash` in the response. On subsequent reads, the hash can be recomputed and compared. This gives us:

1. **Tamper detection** -- any modification to stored data is detectable
2. **Cache validation** -- frontends can compare `$hash` to detect stale data without parsing the full payload
3. **Foundation for content-addressing** -- `$hash` becomes a stepping stone toward CID-based addressing if we ever need federation

```
Before:  { "$schema": ".../Product", "$id": ".../products/1", "name": "Widget", "price": 29.99 }
After:   { "$schema": ".../Product", "$id": ".../products/1", "$hash": "sha256:a1b2c3...", "name": "Widget", "price": 29.99 }
```

The `$hash` is informational in Phase 1 (clients can verify but servers do not enforce). In Phase 2, storage backends can optionally verify hashes on write, creating an audit trail.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- 20-30 lines in `model_dump()`, canonical JSON serialization is straightforward |
| Impact | **Medium** -- cache efficiency, data integrity, foundation for content-addressing |
| Risk | **Low** -- purely additive, no existing behavior changes |
| Timeline | **Days** (2-3 days) |

---

### Proposition 2: Add DID-like portable identity to BaseUser

> 🔧 **Proposition:** Add an optional `did` field to `BaseUser` and a DID-challenge login endpoint alongside email/password, enabling users to carry a cryptographic identity across deployments.

**From the research:** AT Protocol's `did:plc` method has 12M+ registered identifiers. The key insight is the "custodial by default, sovereign by choice" model: most users authenticate with email/password (the PDS manages keys), but power users can set their own rotation keys for full sovereignty. This is not either/or -- it is additive. [05-identity-data-portability.md, sections 1-2, 7]

**In our system:** `base_user.py` defines identity as `email` + `password_hash`, with JWTs issued by `auth.py` using a shared server secret (`_jwt_secret`, HS256). Identity is server-bound: if the server disappears, user identity disappears. The `create_token()` function on line 46 of `auth.py` encodes `user_id`, `email`, and `role` -- all server-local values. There is no mechanism for a user to prove their identity to a different PyBend deployment.

**The idea:** Add three fields to `BaseUser`:

```python
did: Optional[str] = Field(default=None, json_schema_extra={'ui': {'display': False}})
did_public_key: Optional[str] = Field(default=None, json_schema_extra={'ui': {'display': False}})
did_method: Optional[str] = Field(default=None, json_schema_extra={'ui': {'display': False}})
```

Add a `login_did` class method that accepts a DID, a signed challenge, and verifies the signature against the DID document's public key. This produces the same server-issued JWT that `login()` produces -- downstream code (routes, ABAC rules, `_resolve_user()`) is completely unaware.

The `did:web` method is the natural fit: a PyBend deployment at `example.com` can serve `/.well-known/did.json` as a static route, making every user addressable as `did:web:example.com:users:alice`. This costs one new route handler and one JSON file.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- 3 new fields, 1 new login endpoint, DID resolution library integration |
| Impact | **High** -- portable user identity, cross-deployment authentication, eIDAS 2.0 readiness |
| Risk | **Low** -- purely additive, email/password remains the default |
| Timeline | **Weeks** (1-2 weeks) |

---

### Proposition 3: Extend the ABAC system with composable trust labels

> 🔧 **Proposition:** Add a `LABELED(label, source)` access rule to the `authorize` package, inspired by AT Protocol's stackable labeling architecture, enabling trust decisions based on external attestations rather than just local roles.

**From the research:** Bluesky's moderation model uses composable labeling services: any entity can run a labeler that tags content with semantic labels ("spam", "nsfw", "verified-business"). Users choose which labelers to trust. The labels are not binary (remove/keep) but semantic, and multiple labeling services can stack. This is architecturally the most sophisticated moderation system among the four protocols. [02-technical-deep-dive.md, sections 2.1, 8.2]

**In our system:** `rules.py` defines `ANYONE`, `AUTHENTICATED`, `OWNER`, `ROLE`, and `Where` as the complete set of leaf rules. These compose beautifully with `|`, `&`, `~`. But they are all *intrinsic* -- they evaluate properties that the system itself assigned (role, ownership, field values). There is no mechanism for *extrinsic* trust: "this user was verified by service X" or "this content was flagged by moderator Y."

**The idea:** Add a `Labeled` rule that evaluates whether an entity or user carries a specific label from a specific source:

```python
class _Labeled(AccessRule):
    def __init__(self, label: str, source: str = None):
        self.label = label
        self.source = source

    def evaluate(self, ctx: AccessContext) -> bool:
        labels = getattr(ctx.resource, '__labels__', [])
        return any(
            l['label'] == self.label and (self.source is None or l['source'] == self.source)
            for l in labels
        )
```

Usage: `__access__ = {'read': ANYONE, 'feature': LABELED('premium', source='billing-service')}`. Labels are stored as a JSON array on the entity and can be set by any authorized service -- not just the local system. This opens the door for:

- Cross-deployment trust (a user verified on one PyBend instance is recognized on another)
- External moderation services (content labeled by a moderation API)
- Graduated access (labels like "trusted-contributor" unlock capabilities)

The composability is key: `LABELED('verified') & AUTHENTICATED` or `OWNER | LABELED('moderator')` work with the existing `|` / `&` / `~` operators because `_Labeled` extends `AccessRule`.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low-Medium** -- new `AccessRule` subclass (~40 lines), label storage schema |
| Impact | **High** -- composable external trust, cross-deployment authorization, moderation foundation |
| Risk | **Low** -- new leaf rule, does not modify existing rules |
| Timeline | **Days** (3-5 days) |

---

### Proposition 4: Add WebFinger discovery to make PyBend entities addressable across the web

> 🔧 **Proposition:** Add a `/.well-known/webfinger` endpoint that resolves `acct:user@domain` to a user's actor URL and JSON Schema, making PyBend users discoverable by any federated system without implementing full federation.

**From the research:** WebFinger is the universal discovery layer for ActivityPub. A query to `/.well-known/webfinger?resource=acct:alice@mastodon.social` returns a JSON document with links to the user's actor profile. Ghost, WordPress, and every Fediverse server implements this. It is the cheapest possible federation touchpoint. [02-technical-deep-dive.md, section 1.5]

**In our system:** Our entities are already globally addressable via `$id` URLs (`http://host/products/1`). Our schemas are served at `GET /{ClassName}`. But there is no standard discovery mechanism -- you need to know the URL structure. The `register_routes()` function in `routes_fastapi.py` generates CRUD endpoints but no discovery endpoints.

**The idea:** Add a single route handler in `routes_fastapi.py` or as a middleware:

```python
@app.get("/.well-known/webfinger")
async def webfinger(resource: str):
    # Parse acct:user@domain or https://domain/users/id
    # Look up the user model, return links to their profile and schema
    return {
        "subject": resource,
        "links": [
            {"rel": "self", "type": "application/activity+json", "href": f"{API_URL}/users/{user.id}"},
            {"rel": "describedby", "type": "application/schema+json", "href": f"{API_URL}/User"}
        ]
    }
```

This is the "publish-only" first step from the decision framework [03-decision-framework.md, section 10, Hybrid Model 1]. It makes PyBend users discoverable by Mastodon, Ghost, and any ActivityPub-compatible system -- without implementing inbox/outbox, HTTP Signatures, or any federation machinery. The cost is one route handler. The benefit is interoperability readiness.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- single route handler, ~30 lines |
| Impact | **Medium** -- standard web discovery, federation readiness without federation |
| Risk | **Very Low** -- read-only endpoint, no state changes |
| Timeline | **Days** (1 day) |

---

### Proposition 5: Enable schema-to-schema translation for protocol interoperability

> 🔧 **Proposition:** Build a `SchemaTranslator` that converts `ProtoModel.schema()` output into ActivityStreams JSON-LD and AT Protocol Lexicon formats, establishing the bridge between our schema system and federation protocols.

**From the research:** The structural parallels between PyBend's JSON Schema and federation schemas are documented in detail: `$schema`/`$id` maps to `@context`/`type`/`id` in ActivityStreams and to `$type`/NSID in Lexicons. The research explicitly maps every PyBend concept to its federation equivalents. [04-our-stack-relevance.md, section 1, the full mapping table]

**In our system:** `ProtoModel.schema()` (lines 197-316 of `proto_model.py`) generates a complete JSON Schema document with properties, methods, access rules, UI hints, and `$defs`. This schema carries *everything* -- it is the universal contract. The `model_dump(response=True)` method injects `$schema` and `$id` into every instance. The translation from our schema format to ActivityStreams or Lexicon is mechanical, not creative.

**The idea:** Create a `SchemaTranslator` protocol (Python Protocol class) with two concrete implementations:

```
ProtoModel.schema()
       |
       v
  SchemaTranslator
       |
       +--> ActivityStreamsTranslator  --> JSON-LD with @context, type, etc.
       |
       +--> LexiconTranslator          --> Lexicon document with NSID, defs, etc.
```

The translator maps:
- `properties` to ActivityStreams object properties or Lexicon record properties
- `methods` to ActivityStreams activity types or XRPC procedures
- `access.read: anyone` to ActivityStreams public addressing
- `$defs` to nested object types or Lexicon definitions

This does not implement federation. It establishes the *translation layer* that federation would use. And it has immediate non-federation value: any PyBend app can export its schema in standard formats for documentation, API catalogs, or third-party integrations.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- two translator implementations, mapping logic, tests |
| Impact | **High** -- foundation for federation, immediate value for API interoperability |
| Risk | **Low** -- additive module, no changes to existing code |
| Timeline | **Weeks** (1-2 weeks) |

---

### Proposition 6: Adopt event-sourced mutation logging inspired by append-only data structures

> 🔧 **Proposition:** Add an optional append-only event log to `StorableMixin` CRUD operations, recording every mutation as a signed event, inspired by AT Protocol's signed commit model and Nostr's event-based architecture.

**From the research:** AT Protocol repositories are append-only signed commit chains. Every mutation (create, update, delete) produces a new commit that references the previous state. Nostr events are similarly immutable -- the event `id` is a SHA-256 hash of the content, and events are never modified, only superseded. Matrix uses a DAG of signed events per room. All four protocols converge on the same pattern: **mutations are events, not overwrites**. [02-technical-deep-dive.md, sections 2.3, 3.2, 4.2]

**In our system:** `sqlite_storage.py` performs direct SQL INSERT/UPDATE/DELETE. There is no history, no audit trail, no way to answer "what was this entity's state yesterday?" or "who changed this field and when?" The storage layer is purely present-tense.

**The idea:** Add a `__auditable__ = True` flag to ProtoModel. When enabled, every CRUD operation in `StorableMixin` additionally writes an event record to an `_events` table:

```
_events table:
| id | model | entity_id | action | data_hash | user_id | timestamp | prev_hash |
```

Each event includes a hash of the entity's data at that point and a reference to the previous event's hash (`prev_hash`), forming a chain. This is not a blockchain -- it is a linked list of hashes that provides:

1. **Audit trail** -- who changed what, when
2. **Tamper evidence** -- if someone modifies the events table directly, the hash chain breaks
3. **Point-in-time state** -- replay events to reconstruct past state
4. **Foundation for sync** -- two PyBend deployments can compare hash chains to detect divergence

The storage cost is one row per mutation, stored in a single table shared across all auditable models. The runtime cost is one hash computation and one INSERT per write operation.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- event table, StorableMixin hooks, hash chain logic |
| Impact | **High** -- audit trail, tamper evidence, data sync foundation |
| Risk | **Low-Medium** -- write amplification, storage growth (mitigated by retention policies) |
| Timeline | **Weeks** (1-2 weeks) |

---

### Proposition 7: Add pub/sub channels to the Matrix.js message bus

> 🔧 **Proposition:** Extend `Matrix.js` with named channels that any Actor can subscribe to and publish events on, inspired by Nostr's relay subscription model and AT Protocol's firehose pattern.

**From the research:** Nostr's relay protocol defines `REQ` (subscribe to events matching filters) and `EVENT` (publish an event). Clients subscribe with filter criteria and receive matching events in real-time. AT Protocol's firehose emits every repository update as a stream event. Both patterns decouple publishers from subscribers -- the publisher does not need to know who is listening. [02-technical-deep-dive.md, sections 2.5, 3.4]

**In our system:** `Matrix.js` routes messages by target address. It is fundamentally point-to-point: a TX has one `target`, and the Matrix routes it to that target's inbox. The `DynamicClass._watchers` pattern in `NTT.js` (line 718+) adds basic observation, but it is per-type, not per-topic. There is no way for an Actor to say "I care about all CREATE events across all models" or "notify me when any Product with price > 100 is updated."

**The idea:** Add a `Channel` concept to Matrix:

```javascript
// Publisher (any Actor):
matrix.publish('product.created', { id: 1, name: 'Widget', price: 29.99 });

// Subscriber (any Actor):
matrix.subscribe('product.*', (event) => {
    // Receives product.created, product.updated, product.deleted
});
```

Channels use glob-like topic patterns. The Matrix maintains a subscription map (`Map<pattern, Set<callback>>`) and matches published events against subscribed patterns. This is lightweight -- no persistence, no replay, just in-memory pub/sub.

The immediate benefit is decoupling: components that need to react to entity changes no longer need to ATTACH to specific DynamicClasses. A notification component can subscribe to `*.created` and show toasts for any new entity. A dashboard can subscribe to `product.updated` without knowing about the Product DynamicClass.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low-Medium** -- subscription map, pattern matching, publish method |
| Impact | **Medium-High** -- decoupled event handling, cross-model reactivity, extensibility |
| Risk | **Low** -- additive, existing message routing unchanged |
| Timeline | **Days** (3-5 days) |

---

### Proposition 8: Introduce a FederationAdapter protocol as the abstraction boundary

> 🔧 **Proposition:** Define a `FederationAdapter` Python Protocol that formalizes the boundary between PyBend's core and any external protocol, enabling ActivityPub, AT Protocol, or future protocols to plug in without touching core code.

**From the research:** The decision framework explicitly recommends: "Build an abstraction layer first. Never couple your application logic to protocol specifics." The `AuthorizationResolver` Protocol pattern in our codebase is the template -- it works as a standalone ABAC library that happens to plug into PyBend. [03-decision-framework.md, section 13; 04-our-stack-relevance.md, Phase 0]

**In our system:** The `authorize` package demonstrates the pattern perfectly. `resolver.py` defines `AuthorizationResolver` as a runtime-checkable Protocol with three methods (`resolve_rule`, `authorize`, `sql_filter_for`). `DefaultResolver` implements it. The route layer consumes the Protocol, not the implementation. This is exactly the boundary we need for federation.

**The idea:**

```python
@runtime_checkable
class FederationAdapter(Protocol):
    def serialize_object(self, instance: ProtoModel) -> dict: ...
    def serialize_activity(self, action: str, instance: ProtoModel) -> dict: ...
    def deserialize_activity(self, data: dict) -> Tuple[str, dict]: ...
    def verify_request(self, request: Request) -> Optional[dict]: ...
    def discovery_endpoint(self, user: Any) -> dict: ...
```

Concrete implementations: `ActivityPubAdapter`, `ATProtoAdapter`. The `create_app()` factory accepts an optional `federation=` parameter. When provided, `register_routes()` generates additional endpoints (inbox, outbox, webfinger) that delegate to the adapter. When not provided, zero federation code runs.

This is Phase 0 of the integration path -- no protocol implementation, just the interface. It can be built today, tested today, and it constrains how protocol-specific code is structured when it arrives.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- Protocol definition, configuration plumbing |
| Impact | **High** -- architectural guardrail, prevents protocol coupling, enables incremental adoption |
| Risk | **Very Low** -- no behavioral changes, just interface definition |
| Timeline | **Days** (2-3 days) |

---

### Proposition 9: Make the `__access__` system DID-aware for cross-deployment authorization

> 🔧 **Proposition:** Extend `AccessContext` to carry a DID alongside `user_id`, and add a `DID_OWNER` rule that evaluates ownership against a DID rather than a server-local integer ID.

**From the research:** In decentralized systems, the integer `user_id` is meaningless -- it is local to one database. AT Protocol uses DIDs as the universal identity anchor. A `did:plc:abc123` is the same identity regardless of which PDS hosts the account. Verifiable Credentials enable portable trust: a credential issued by one system is verifiable by any other. [05-identity-data-portability.md, sections 1, 4, 11]

**In our system:** `context.py` defines `AccessContext` with `user_id` (integer, from JWT), `user_role` (string), and `user_email` (string). The `_Owner` rule in `rules.py` compares `ctx.user_id` to the resource's `user_owner` field. This is inherently local -- if the same person authenticates against two different PyBend deployments, they have different `user_id` values and OWNER checks fail across deployments.

**The idea:** Add `user_did: Optional[str]` to `AccessContext`:

```python
@dataclass(frozen=True)
class AccessContext:
    user: Dict[str, Any]
    action: str
    model_class: Type[Any]
    resource: Optional[Any] = None
    parent_id: Optional[int] = None

    @property
    def user_did(self) -> Optional[str]:
        return self.user.get("did")
```

Add a `DID_OWNER` rule:

```python
class _DIDOwner(AccessRule):
    def evaluate(self, ctx: AccessContext) -> bool:
        if not ctx.user_did:
            return False
        owner_did = getattr(ctx.resource, 'owner_did', None)
        return owner_did == ctx.user_did
```

Usage: `__access__ = {'update': OWNER | DID_OWNER}` -- local users match by integer ID, DID-authenticated users match by DID string. The composability of the existing rule system makes this seamless.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Low** -- one property on AccessContext, one new AccessRule |
| Impact | **Medium-High** -- cross-deployment authorization, DID integration pathway |
| Risk | **Low** -- additive, existing OWNER rule unchanged |
| Timeline | **Days** (1-2 days) |

---

### Proposition 10: Build exportable entity repositories for data portability

> 🔧 **Proposition:** Add an export endpoint that packages a user's complete data (entities, relationships, schemas) into a self-contained, portable archive, inspired by AT Protocol's CAR file export and GDPR Article 20.

**From the research:** AT Protocol's `com.atproto.sync.getRepo` endpoint returns a user's complete data repository as a CAR (Content Addressable aRchive) file. This is the foundation of account portability -- the user can take their data to any compatible PDS. GDPR Article 20 (Right to Data Portability) requires this capability. [05-identity-data-portability.md, sections 2, 3]

**In our system:** There is no export mechanism. A user's data is scattered across multiple tables (products they own, comments they wrote, likes they gave). Reconstructing a complete picture requires querying multiple models with FK hydration. The information needed to do this is already in the schema: `__owner_field__` tells us which entities belong to a user, `ListRef` tells us about child relationships, and `$defs` describe the full type graph.

**The idea:** Add an export endpoint to `BaseUser`:

```python
@expose_route('/export', methods=['GET'], access=OWNER)
def export(self, user: User = None) -> dict:
    """Export all entities owned by this user as a portable archive."""
    archive = {
        '$schema': f'{config.API_URL}/UserExport',
        'user': self.model_dump(response=True),
        'entities': {},
        'schemas': {},
    }
    for model_name, model_cls in registered_models.items():
        owner_field = getattr(model_cls, '__owner_field__', 'user_owner')
        if owner_field in model_cls.model_fields:
            owned = model_cls.list(sql_filter=(f'{owner_field} = ?', [self.id]))
            archive['entities'][model_name] = [e.model_dump(response=True) for e in owned]
            archive['schemas'][model_name] = model_cls.schema()
    return archive
```

The archive is self-describing (includes schemas) and self-contained (includes all referenced data). It can be imported into another PyBend deployment or consumed by any tool that reads JSON Schema.

**Effort/Impact:**

| Dimension | Assessment |
|-----------|-----------|
| Effort | **Medium** -- export endpoint, cross-model query logic, archive format |
| Impact | **High** -- data portability, GDPR compliance, user trust |
| Risk | **Low-Medium** -- performance for large datasets (mitigated by streaming) |
| Timeline | **Weeks** (1 week) |

---

## 🏗️ Proposition Map

### Quick Wins (Days, Low Effort, Immediate Value)

| # | Proposition | Effort | Impact |
|---|------------|--------|--------|
| 4 | WebFinger discovery endpoint | Low | Medium |
| 1 | Content-addressable `$hash` on entities | Low | Medium |
| 8 | FederationAdapter Protocol definition | Low | High |
| 9 | DID-aware AccessContext + DID_OWNER rule | Low | Medium-High |

### Strategic Investments (Weeks, Medium Effort, High Value)

| # | Proposition | Effort | Impact |
|---|------------|--------|--------|
| 2 | DID-based portable identity on BaseUser | Medium | High |
| 3 | Composable trust labels in ABAC | Low-Medium | High |
| 5 | Schema-to-schema translation layer | Medium | High |
| 7 | Pub/sub channels in Matrix.js | Low-Medium | Medium-High |
| 10 | Exportable entity repositories | Medium | High |

### Moonshots (Months, High Effort, Transformative)

| # | Proposition | Effort | Impact |
|---|------------|--------|--------|
| 6 | Event-sourced mutation logging | Medium | High |
| -- | Full ActivityPub S2S (builds on 4, 5, 8) | High | Transformative |
| -- | AT Protocol PDS integration (builds on 2, 5, 6, 8) | Very High | Transformative |

---

## ⚠️ What NOT to Do

**1. Do not implement full federation before the core product stabilizes.** The research is explicit: Ghost spent years perfecting publishing before adding ActivityPub. WordPress iterated for years on their plugin. Premature federation means every schema change breaks remote peers. Build the abstraction layer (Proposition 8) and the translation layer (Proposition 5), but do not flip the switch until the model surface is stable.

**2. Do not replace JWT authentication with DID authentication.** DIDs are additive, not a replacement. The "custodial by default, sovereign by choice" model from AT Protocol is the right pattern. Most users will never manage cryptographic keys. Add DID as an alternative login path (Proposition 2), but keep email/password as the primary experience. Forcing cryptographic identity on mainstream users is a UX dead end.

**3. Do not adopt Nostr's "trust nobody" model.** Nostr's radical minimalism -- no accounts, no servers with authority, no recovery -- is philosophically interesting but operationally hostile. PyBend's strength is that the backend is authoritative. Importing selective decentralization (content hashes, portable identity, composable labels) strengthens the system. Importing full trustlessness would undermine the "backend is authoritative" principle that makes the framework coherent.

---

## 🎯 Recommended Starting Point

**Start with Propositions 8, 4, and 1 -- in that order.**

**Proposition 8 (FederationAdapter Protocol)** costs 2-3 days and establishes the architectural guardrail. Every subsequent federation-related change slots into this boundary. It also validates the design pattern -- if the Protocol definition feels wrong, we learn that before building anything behind it.

**Proposition 4 (WebFinger)** costs 1 day and produces an immediately visible result: any Fediverse user can discover PyBend users. This is the minimum viable interoperability step that the decision framework recommends [03-decision-framework.md, Hybrid Model 1].

**Proposition 1 (Content-addressable `$hash`)** costs 2-3 days and provides non-federation value immediately (cache validation, data integrity) while laying groundwork for content-addressing.

**Validation approach:** Deploy a PyBend instance with WebFinger enabled. Search for a PyBend user from a Mastodon instance. If the discovery resolves correctly, the interoperability path is validated. Measure: can a Mastodon user find a PyBend user without knowing the URL structure?

Total investment: **~1 week**. Total risk: **near zero** (all changes are additive). Signal strength: **high** (real interoperability test with real Fediverse servers).
