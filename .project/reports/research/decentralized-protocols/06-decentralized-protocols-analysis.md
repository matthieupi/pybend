# 📋 Decentralized Protocols for N3TX: Strategic Analysis Report

## For: CEO & Engineering Team
## Date: February 2026

---

### How to Read This Document

This report synthesizes five research documents totaling ~4,700 lines into an actionable strategic analysis. It serves two audiences simultaneously:

- **CEO / Business Leadership**: Read the Executive Summary, sections 1-2 for context, sections 6-8 for the business case, and section 8 for the recommendation. Skim the rest.
- **Engineering Team**: Read everything. The technical architecture sections (3-5) contain the mapping details you need. The appendices have implementation timelines and code-level specifics.

> **Key conventions**: Plain-English "so what?" opens each section, followed by technical depth. Tables compress comparisons. ASCII diagrams show architecture. Inline citations reference both the research files (`[R1]`-`[R5]`) and external sources by URL.

**Research files referenced**:
- `[R1]` = `01-industry-landscape.md` -- Market data, adoption numbers, enterprise deployments
- `[R2]` = `02-technical-deep-dive.md` -- Protocol architectures, data formats, security models
- `[R3]` = `03-decision-framework.md` -- Build/integrate analysis, cost models, anti-patterns
- `[R4]` = `04-our-stack-relevance.md` -- N3TX architecture mapping, gap analysis, implementation plan
- `[R5]` = `05-identity-data-portability.md` -- DIDs, account portability, verifiable credentials, eIDAS 2.0

---

## 📋 Executive Summary

N3TX's schema-driven architecture -- where a Python model definition is the single source of truth for the entire stack -- is not just compatible with decentralized protocols. It is **convergent** with them. Both ActivityPub and ATProtocol are, at their core, schema-driven systems that derive behavior from data definitions. The structural parallels are deep enough that N3TX already has **60-70% of the conceptual machinery needed for federation**.

The remaining 30-40% is protocol-specific plumbing: cryptographic signatures, federation-specific serialization, delivery queues, and identity resolution. This can be built as additive modules without disrupting the existing architecture.

### The Bottom Line

| Question | Answer |
|----------|--------|
| Should we build federation support? | **Yes, but incrementally.** |
| Which protocol first? | **ActivityPub** (W3C standard, regulatory tailwinds, broadest ecosystem) |
| When? | **After core product stabilization.** Phase 1 can begin in Q2 2026. |
| How long? | **6-10 weeks** for ActivityPub. **14-20 weeks** for both protocols. |
| What makes us unique? | **No existing framework offers model-driven federation.** `__federated__ = True` on a model auto-generating federation endpoints is a capability that does not exist anywhere else. |
| What is the strategic driver? | **Identity portability + EU regulation.** DIDs and the EU DMA are converging to make federation a compliance and competitive necessity for social/content applications. |

### The Opportunity in One Sentence

N3TX can become the first framework where `class Post(ProtoModel): __federated__ = True` produces a working fediverse node -- bridging the gap between schema-driven frameworks and federated applications that no one else has filled.

---

## 1. 🔍 What Are Decentralized Protocols?

**So what?** Decentralized protocols let users on different servers talk to each other without a central platform controlling the conversation. Think email: you can send a message from Gmail to Outlook because both speak SMTP. These protocols do the same thing for social media, messaging, and content publishing.

### The Core Idea

Centralized platforms (Twitter/X, Instagram, TikTok) own your identity, your content, and your audience. If the platform changes its rules, raises its prices, or shuts down, you lose everything. Decentralized protocols break this dependency by separating three concerns:

1. **Identity**: Who you are (your handle, your followers, your reputation)
2. **Data**: What you have created (posts, photos, comments, likes)
3. **Application**: How you interact with it all (the UI, the algorithm, the experience)

In the centralized world, one company controls all three. In the decentralized world, each can be independent. You can move your identity from one provider to another, take your data with you, and use any compatible application.

### Why It Matters Now (Not Five Years Ago)

Three forces have converged to make this relevant in 2026:

```
Force 1: SCALE                    Force 2: REGULATION              Force 3: STANDARDS
Bluesky: 40.2M users              EU DMA review: May 2026          W3C DID v1.0 (2022)
Fediverse: 12M+ registered        eIDAS 2.0 wallets: Nov 2026      W3C VC 2.0 (May 2025)
Matrix: 25+ gov't deployments     EUR 500M+ fines already issued    ATProto IETF draft (2025)
Ghost + WordPress federating       Social interop under review       ActivityPub W3C standard
```

This is no longer a niche concern. When Meta's Threads (200M+ MAU) partially implements ActivityPub, when the European Commission runs its own Mastodon instance, and when Ghost and WordPress ship federation as a production feature, the early-adopter phase is ending. `[R1]`

---

## 2. 🏢 Industry Landscape

**So what?** The market is splitting into two major protocol camps with significant overlap. ActivityPub has institutional breadth (governments, publishers, the W3C). ATProtocol (Bluesky) has growth momentum and better developer experience. Neither has won. The window for strategic positioning is open now.

### The Numbers That Matter

| Protocol | Registered Users | Monthly Active | Key Signal |
|----------|-----------------|----------------|-----------|
| **ATProtocol (Bluesky)** | ~40.2M (Nov 2025) | ~3.5M DAU | +302% in 14 months. Event-driven spikes. |
| **ActivityPub (Fediverse)** | ~12M (excl. Threads) | ~1.2-1.5M MAU | Flat active users despite registration growth. |
| **Matrix** | Millions (fragmented) | ~50M+ estimated | 25+ government deployments. |
| **Nostr** | ~228K daily events | ~21K active | Niche but passionate. Native Bitcoin payments. |

Sources: [FediDB](https://fedidb.org/), [Backlinko](https://backlinko.com/bluesky-statistics), [Sprout Social](https://sproutsocial.com/insights/bluesky-statistics/) `[R1]`

### Enterprise Adoption: Who Is Already In

The most significant development of 2024-2025 was established publishing platforms shipping ActivityPub support as **production features**, not experiments:

| Company | Product | Status | Significance |
|---------|---------|--------|-------------|
| **Meta** | Threads | Partial, opt-in | 200M+ MAU platform. Compliance hedge, not strategic commitment. |
| **Automattic** | WordPress.com | Production | Official ActivityPub plugin. Any WordPress blog can federate. |
| **Ghost** | Ghost 6.0 | Production (beta) | ActivityPub integration shipped Aug 2025. Social web alliance with WordPress. |
| **Flipboard** | Flipboard | Production | Full ActivityPub federation since late 2023. |
| **Medium** | Medium | Partial | Mastodon server launched; ActivityPub integration active. |

Source: [TechCrunch](https://techcrunch.com/2025/08/05/substack-rival-ghost-connects-to-the-open-social-web-with-its-latest-public-release/) `[R1]`

> 💡 **Key insight**: The publishing layer is federating whether social networks do or not. Ghost and WordPress together power a massive share of the open web's publishing infrastructure. Their ActivityPub implementations mean blog posts become first-class fediverse content -- discoverable, followable, interactable from Mastodon and other clients. For a framework that powers content-driven applications, this is the most directly relevant signal.

### Government Adoption

Governments are unexpectedly strong early adopters, driven by digital sovereignty concerns:

- **European Commission**: Operates its own Mastodon instance (social.network.europa.eu)
- **Germany**: social.bund.de (production), Bundeswehr using Matrix for military comms
- **France**: Tchap (Matrix chat) + Visio (Matrix video) as part of "La Suite" digital workspace
- **Netherlands, Switzerland, Austria**: All operating government fediverse instances
- **Ukraine**: Government communications infrastructure on Matrix

The pattern: **when depending on US-based companies for communications infrastructure becomes politically untenable, decentralized protocols win.** `[R1]`

### The Regulatory Catalyst

The EU Digital Markets Act (DMA) is the single most important force acting on this space:

- **Messaging interoperability**: Already mandated for designated gatekeepers. WhatsApp enabled third-party chats in Nov 2025.
- **Social network interoperability**: **Not currently required.** But the May 2026 DMA review will assess whether to extend interoperability mandates to social networking services. This is one of four main aspects under assessment.
- **If mandated**: Platforms like Instagram, TikTok, and X could be required to support cross-platform social interactions -- likely via ActivityPub, given its W3C standard status.

Source: [Digital Markets Act Portal](https://digital-markets-act.ec.europa.eu/index_en), [Lexology](https://www.lexology.com/library/detail.aspx?g=9fc2889d-a0f3-4207-a14a-24769969cc77) `[R1]`

> ⚠️ **Strategic implication**: If the May 2026 review extends interoperability mandates to social networks, it would be **transformative** for decentralized protocol adoption. Teams building social features should architect for protocol-level interoperability now, even if mandates have not yet arrived. The cost of retrofitting is far higher than designing for it.

### Market Sizing

The blockchain-based decentralized social media platform market: **$2.38B (2024) -> $2.91B (2025) -> $6.41B (2029)** at 21.9% CAGR. The decentralized identity market: **$2.56B (2025) -> $4.6B (2026)** at 80% CAGR. Sources: [Research and Markets](https://www.researchandmarkets.com/reports/6215126/blockchain-based-decentralized-social-media), [GM Insights](https://www.gminsights.com/industry-analysis/decentralized-identity-market) `[R1][R5]`

---

## 3. ⚡ Technical Architecture

**So what?** The four protocols represent fundamentally different architectural philosophies. Understanding which one fits your use case is the difference between a natural extension of your stack and a painful bolted-on integration. For N3TX specifically, ActivityPub and ATProtocol are the relevant choices -- and they map to our architecture in different but complementary ways.

### Protocol Architecture Comparison

```
                     Simplicity
                         ^
                         |
                  Nostr  |
                    *    |
                         |
                         |
     ActivityPub *-------+-------* AT Protocol
                         |
                         |
                  Matrix |
                    *    |
                         v
                     Complexity
     <--- Decentralized    Aggregated --->
```

`[R2]`

### ActivityPub: Email for Social Media

ActivityPub is a W3C Recommendation (2018) built on ActivityStreams 2.0. It uses a **federated push model**: servers send activities (posts, likes, follows) directly to other servers' inboxes via signed HTTP requests.

```
Server A (alice@a.social)              Server B (bob@b.social)
         |                                       |
         |  1. Alice creates a Post              |
         |  2. Server A wraps it in Create {}    |
         |  3. Signs with HTTP Signature         |
         |  4. POST to bob's inbox               |
         |-------------------------------------->|
         |  5. Server B verifies signature       |
         |  6. Stores in bob's feed              |
         |  202 Accepted                         |
         |<--------------------------------------|
```

**Key technical characteristics** `[R2]`:

| Aspect | Detail |
|--------|--------|
| Data format | JSON-LD (ActivityStreams 2.0) |
| Identity | Actor URIs + WebFinger discovery (`@user@server.social`) |
| Authentication (S2S) | HTTP Signatures (RSA-SHA256) |
| Content types | ~30 activity types (Create, Follow, Like, Announce, etc.), ~20 object types (Note, Article, Image, etc.) |
| Encryption | None (E2E encryption proposed but not implemented) |
| Spec stability | HIGH -- W3C Recommendation, multi-stakeholder governance |
| Implementation effort | 2,000-5,000 LOC for minimal S2S; 3-6 months to production |
| Key challenge | Spec ambiguity. Mastodon's interpretation is the de facto standard. |

### ATProtocol: Global Database with Portable Identity

ATProtocol separates concerns into four service roles: PDS (user data), Relay (aggregation), App View (application logic), and Labeler (moderation). Identity is DID-based and fully portable.

```
+------------------+      +------------------+      +------------------+
|  Client (App)    |      |    App View      |      |    Labeler       |
|  (e.g., bsky.app)|      | (feed service)   |      | (moderation)     |
+--------+---------+      +--------+---------+      +--------+---------+
         |                         |                          |
         |    XRPC (HTTPS)         |    Subscribe to          |
         v                         v    firehose               v
+--------+---------+      +--------+---------+
|  PDS (Personal   |----->|  Relay / BGS     |
|  Data Server)    |      | (aggregator)     |
|  - Hosts repo    |      | - Crawls repos   |
|  - Signs commits |      | - Emits firehose |
+------------------+      +------------------+
```

**Key technical characteristics** `[R2]`:

| Aspect | Detail |
|--------|--------|
| Data format | DAG-CBOR + Lexicon schemas (strongly typed) |
| Identity | DIDs (did:plc / did:web) + domain handles (@you.com) |
| Authentication | DID-based signing + OAuth |
| Schema system | Lexicon -- reverse-DNS namespaced, auto-validating |
| Data structure | Merkle Search Tree -- content-addressed, cryptographically verifiable |
| Encryption | None yet (in development) |
| Spec stability | MEDIUM -- pre-1.0, IETF draft submitted Sep 2025 |
| Implementation effort | 10,000-20,000 LOC for PDS; 2-4 months with SDK |
| Key challenge | Single-vendor governance (Bluesky). Infrastructure centralized in practice. |

### Matrix: The Messaging Standard

Matrix is the clear choice for real-time encrypted messaging, not social networking. 25+ government deployments validate it. Element (the primary client company) is reaching financial sustainability. The protocol's complexity (state resolution is a research problem) means building a homeserver from scratch is impractical -- use Synapse or Dendrite. `[R1][R2]`

### Nostr: Interesting but Niche

Nostr's radical simplicity (entire core spec fits on one page) and native Bitcoin Lightning payments are genuinely novel. But the user base is tiny (~21K active), the protocol lacks schema validation, and the community skews heavily toward cryptocurrency enthusiasts. Not a strategic fit for N3TX. `[R1][R2]`

### Head-to-Head: ActivityPub vs ATProtocol

| Dimension | ActivityPub | ATProtocol | Winner for N3TX |
|-----------|-------------|------------|-------------------|
| **Schema compatibility** | JSON-LD maps loosely to JSON Schema | Lexicons are structurally similar to JSON Schema | ATProtocol |
| **Ecosystem maturity** | 8+ years, W3C standard, many implementations | 2 years, single company, growing fast | ActivityPub |
| **Governance risk** | Multi-stakeholder (W3C, Social Web Foundation) | Single company (Bluesky PBC) | ActivityPub |
| **Identity portability** | None (tied to server) | Full (DID-based, PDS migration) | ATProtocol |
| **Developer experience** | Fragmented libraries, spec ambiguity | Well-typed SDKs, comprehensive docs | ATProtocol |
| **User reach** | ~12M + potential Threads (200M+) interop | ~40M Bluesky | Tie (different audiences) |
| **Regulatory alignment** | W3C standard = strongest DMA candidate | IETF draft = credible but newer | ActivityPub |
| **Python SDK** | Bovine (beta), various others | atproto (PyPI, production, auto-generated) | ATProtocol |
| **Implementation cost** | 6-10 weeks | 10-16 weeks | ActivityPub |

`[R2][R3][R4]`

> 💡 **Assessment**: ActivityPub is the safer first bet: W3C standard, regulatory tailwinds, lower implementation cost, broader ecosystem. ATProtocol is the stronger long-term play: better DX, schema alignment with N3TX, portable identity. **Implement ActivityPub first, ATProtocol second.** The abstraction layer makes both possible without doubling the work.

---

## 4. 🔍 Our Current Architecture Assessment

**So what?** N3TX's architecture is not just compatible with federation -- it is *convergent* with it. The parallels between our schema-driven model and what federation protocols need are deep enough that most of the conceptual work is already done. What remains is protocol-specific plumbing.

### The Structural Parallels

| Concept | N3TX Today | ActivityPub Needs | ATProtocol Needs |
|---------|-------------|-------------------|------------------|
| **Schema format** | JSON Schema via `ProtoModel.schema()` | JSON-LD / ActivityStreams | Lexicon definitions |
| **Self-describing instances** | `model_dump(response=True)` injects `$schema` + `$id` | Every object carries `@context` + `type` + `id` | Every record carries `$type` |
| **Auto-generated endpoints** | `register_routes()` produces CRUD + custom methods | Inbox/Outbox per actor | XRPC per Lexicon |
| **Access control** | ABAC rules (`ANYONE`, `AUTHENTICATED`, `OWNER`, `ROLE`) | Public/followers/direct addressing | PDS-level + app-level rules |
| **Identity** | `BaseUser` + JWT tokens | Actor URIs + HTTP Signatures | DIDs + signing keys |
| **Parent-child relations** | `ListRef[T]` + join models | ActivityStreams Collections | Record references |
| **Type identity** | `$schema` URL + `$id` URL | `@context` + `type` | `$type` NSID |

Source: N3TX codebase analysis, `[R4]`

### What We Already Have (60-70%)

The following existing N3TX patterns **directly enable federation** with minimal modification:

**1. Self-Describing Instances** (`proto_model.py`, line 117-137)

```python
def model_dump(self, *, response: bool = False, **kwargs) -> Dict[str, Any]:
    data = super().model_dump(**kwargs)
    if response:
        data = {
            '$schema': f"{config.API_URL}/{cls.__name__}",
            '$id': f"{config.API_URL}/{tablename}/{instance_id}",
            **data
        }
    return data
```

This is the **same pattern** as ActivityStreams' `id` + `type` and ATProtocol's `$type`. N3TX entities already carry their own identity and type information. The `$id` on every entity is already a globally-resolvable URL -- exactly what ActivityPub requires for every object.

**2. Schema as Universal Contract** (`proto_model.py`, line 197-200+)

N3TX's schema already carries everything federation needs:
- **Type information** (`properties`, `$defs`) -- maps to AS types / Lexicon defs
- **Method signatures** (`methods`) -- maps to Activities / XRPC procedures
- **Access rules** (`access`) -- maps to federation visibility
- **UI hints** (`ui`) -- used locally, ignored by federation (clean separation)

**3. Route Generation** (`routes_fastapi.py`, line 56-89+)

N3TX's `register_routes()` auto-generates CRUD endpoints from model registration. The federation layer adds new routes alongside existing ones -- it does not replace them.

**4. ABAC Authorization** (`authorize/rules.py`, line 13-40+)

The composable rule system (`|`, `&`, `~`) naturally extends to federation concepts. New rules like `FEDERATED`, `LOCAL`, `FOLLOWER` compose with existing rules seamlessly:

```python
# Only local authenticated users can create; anyone (including federated) can read
__access__ = {
    'read': ANYONE,
    'create': LOCAL & AUTHENTICATED,
    'update': OWNER,
}
```

**5. Pluggable Storage** (`abstract_storage.py`)

The `AbstractStorage` interface means federation storage (activity store, MST repo) can be implemented without touching `SQLiteStorage`.

**6. Standalone Auth Package** (`authorize/`)

Zero N3TX imports. Federation auth (HTTP Signatures, DID verification) can plug into the same `AccessContext`/`AccessRule` system without coupling.

### What We Need to Build (30-40%)

| Capability | Effort | Required For |
|-----------|--------|-------------|
| WebFinger endpoint | Medium | ActivityPub discovery |
| HTTP Signature middleware | High | ActivityPub S2S authentication |
| ActivityStreams serializer | Low | Translate `model_dump()` to AS2 JSON-LD |
| Actor endpoint per user | Medium | ActivityPub identity |
| Inbox/Outbox endpoints | Medium | ActivityPub message exchange |
| Delivery queue (async) | Medium | ActivityPub outbound delivery |
| Follower/Following model | Medium | ActivityPub social graph |
| Lexicon generator | Low | Translate `ProtoModel.schema()` to ATProto Lexicon |
| DID support | High | ATProtocol identity |
| Merkle Search Tree | High | ATProtocol data repositories |
| XRPC router | Medium | ATProtocol endpoint format |
| Content addressing (CIDs) | High | ATProtocol data integrity |

`[R4]`

### The `__federated__` Pattern

Following N3TX's convention of model-level declarations (`__storable__`, `__access__`, `__ui__`), federation would be declared the same way:

```python
class Post(ProtoModel):
    __tablename__ = 'posts'
    __storable__ = True
    __federated__ = True  # <-- That is it.
    __access__ = {
        'read': ANYONE,
        'create': AUTHENTICATED,
    }

    body: str = Field(max_length=500)
    user_owner: int = Field(default=0)
```

What `__federated__ = True` would auto-generate:

| For ActivityPub | For ATProtocol |
|----------------|----------------|
| Actor endpoint for post author | Lexicon definition from schema |
| WebFinger response | XRPC procedure endpoints |
| Inbox/Outbox endpoints | DID document |
| HTTP Signature middleware | Repository (MST) storage |
| `Create`/`Update`/`Delete` activity wrapping | Signed commits |
| Delivery to followers | Firehose events |

`[R4]`

### Route Mapping: CRUD to Federation

```
N3TX Today                        ActivityPub Equivalent
-----------------------------------------------------------------
GET  /User                          (schema -- no AP equiv)
GET  /users                         GET /users/{username}/outbox
GET  /users/{id}                    GET /users/{username} (actor)
POST /users                         POST /users/{username}/outbox
PUT  /users/{id}                    Update activity via outbox
DELETE /users/{id}                  Delete activity via outbox
POST /users/{id}/comment            Create Note activity
--- Missing ---                     POST /users/{username}/inbox (S2S)
--- Missing ---                     GET  /.well-known/webfinger
--- Missing ---                     GET  /users/{username}/followers
```

N3TX's CRUD maps to ActivityPub's Client-to-Server API. The Server-to-Server federation layer is entirely additive. `[R4]`

---

## 5. 🎯 Identity & Data Portability

**So what?** This is the strategic reason decentralization matters *now*. Identity portability -- the ability to take your handle, your followers, your content, and your reputation from one provider to another -- breaks platform lock-in. Combined with EU regulation mandating digital identity wallets by November 2026, this is not a theoretical future. It is a near-term reality.

### Why Identity Is the Strategic Differentiator

Platform risk is not theoretical. The 2023-2025 period produced a cascade of events:

| Event | Impact | What portability would have changed |
|-------|--------|-------------------------------------|
| Twitter -> X policy upheaval | 40M+ users migrated to Bluesky | Users lost followers, content, verification |
| Reddit API pricing changes | Third-party apps killed | Developers lost access to audiences they built |
| Instagram algorithm shifts | 80%+ organic reach reduction | Businesses discovered their audience was rented, not owned |
| TikTok ban threats | Creator uncertainty | Content libraries at risk of evaporation |

In every case, the users and creators who suffered did so because **their identity was a row in someone else's database**. `[R5]`

### Decentralized Identifiers (DIDs)

A DID is a globally unique, cryptographically verifiable identifier that does not require a centralized registry:

```
did:plc:z72i7hdynmk6r22z27h6tvur
 |   |   |
 |   |   +-- Method-specific identifier
 |   +------ DID Method (resolution mechanism)
 +---------- Scheme (always "did")
```

Each DID resolves to a DID Document containing public keys, service endpoints, and controller information. The key DID methods:

| Method | Resolution | Key Rotation | Production Users |
|--------|-----------|-------------|-----------------|
| `did:web` | HTTPS + DNS | Manual | Enterprise, organizations |
| `did:plc` | PLC Directory | Built-in rotation keys | 12M+ (Bluesky) |
| `did:key` | Self-resolving | None (key = identity) | Dev/testing |

Source: [W3C DID v1.0](https://www.w3.org/TR/did-1.0/), `[R5]`

### ATProtocol's Account Portability: How It Actually Works

ATProtocol separates identity from hosting through a layered architecture. Migration is a first-class operation:

1. **Create account on new PDS** -- prove identity via signed token
2. **Export repository** -- fetch complete data as CAR file
3. **Import to new PDS** -- upload CAR file, re-upload media
4. **Update DID document** -- point to new PDS
5. **Handle continues working** -- resolves to DID, not PDS directly

**The critical property**: The old PDS cannot prevent migration. Even if hostile, the user's rotation keys override PDS control. `[R5]`

### Verifiable Credentials (VC 2.0)

The W3C published Verifiable Credentials 2.0 as a **full W3C Recommendation** in May 2025 -- the same standards authority as HTML. VCs enable **portable reputation**:

- A freelancer's ratings travel across platforms
- A developer's track record is verifiable by any employer
- A user's moderation standing on one network is recognized by another

Enterprise adoption is accelerating: **60%+ of enterprises** globally are projected to use VCs by 2026. Verification workflow cost reductions of **70-90%** are reported by early adopters. `[R5]`

### eIDAS 2.0: The Regulatory Tailwind

The EU eIDAS 2.0 regulation mandates:

- **November 2026**: Every EU member state must offer a certified digital identity wallet
- **November 2027**: Businesses requiring customer identification must accept the wallet
- **Standards**: Built on W3C Verifiable Credentials + OpenID4VC

This is not aspirational. It is law. And it creates infrastructure (verifier networks, credential issuance, revocation services) that private-sector applications can leverage. `[R5]`

### What DID-Augmented Auth Would Look Like in N3TX

DIDs do not replace JWTs -- they change who issues them and what they prove:

```
Current:    Server creates JWT about user  ->  Server verifies JWT
DID-based:  User signs JWT with DID key    ->  Server verifies via DID resolution
```

The migration path:

```
Phase 0 (Now):     JWT-only auth. BaseUser with email/password.
Phase 1 (Near):    Add optional DID field to BaseUser. DID-challenge login
                   alongside email/password. Both produce server-issued JWTs.
Phase 2 (Medium):  Support DID-JWTs as alternative to server-issued JWTs.
Phase 3 (Future):  Verifiable Credential-based authorization. Access rules
                   reference VC claims: VC_CLAIM('AdminCredential', issuer='...')
```

This aligns with N3TX's "zero to working, then customize" principle: email/password works by default; DID is additive. `[R5]`

---

## 6. 📊 Cost-Benefit Analysis

**So what?** Federation is not free, but it is not as expensive as it looks -- especially for a schema-driven framework that already has most of the primitives. The key is to start small (publish-only) and expand based on demand.

### Implementation Cost

| Phase | Scope | Engineering Weeks | Team Size |
|-------|-------|-------------------|-----------|
| **Phase 1**: Federation primitives | `__federated__` metadata, WebFinger, Actor endpoint, serializers | 2-4 weeks | 1-2 engineers |
| **Phase 2**: ActivityPub S2S | Inbox, outbox, HTTP Signatures, delivery queue, followers | 4-6 weeks | 2-3 engineers |
| **Phase 3**: ATProtocol support | Lexicon generation, DID, XRPC, MST storage (can parallel Phase 2) | 4-6 weeks | 2-3 engineers |
| **Total for AP only** | Phases 1-2 | **6-10 weeks** | 2-3 engineers |
| **Total for both** | Phases 1-3 | **14-20 weeks** | 2-3 engineers |

`[R4]`

### Infrastructure Cost (Monthly)

| Component | ActivityPub (small, <500 users) | ATProtocol PDS (<10 accounts) | Both |
|-----------|-------------------------------|-------------------------------|------|
| Compute | $14-35 | $6-8 | $20-43 |
| Storage | $5-15 | Included | $5-15 |
| Media (S3) | $5-10 | N/A | $5-10 |
| Bandwidth | $0-10 | Minimal | $0-10 |
| **Total** | **$25-72/mo** | **$6-10/mo** | **$31-78/mo** |

Source: [WeHaveServers](https://wehaveservers.com/blog/dev-use-cases/deploying-a-mastodon-activitypub-server-hardware-setup-guide/), [ATProto docs](https://atproto.com/guides/self-hosting) `[R3]`

### Hidden Costs

| Cost | Description | Mitigation |
|------|-------------|-----------|
| **Moderation** | Federated content needs moderation. You are liable for content you relay. | Allow-list federation (Hybrid Model 2). Start with trusted peers only. |
| **Security** | Each federation endpoint is an attack surface. | Treat federation boundary as security boundary. Rate limiting. Input validation. |
| **Compliance** | GDPR across federated data. | Retention policies, deletion propagation hooks, allow-list of federated servers. |
| **Maintenance** | Spec tracking, compatibility testing, library updates. | Abstraction layer insulates from protocol churn. |

`[R3]`

### The 80/20 Rule

For most applications, **RSS + webhooks + REST API** covers 80% of interoperability needs. The remaining 20% -- social interactions, identity portability, decentralized discovery -- is what federation adds.

| Approach | Implementation Cost | Coverage |
|----------|-------------------|----------|
| RSS + webhooks + REST API | 1-2 weeks | ~80% |
| + ActivityPub (publish-only) | + 2-4 weeks | ~90% |
| + Full ActivityPub (inbox + outbox) | + 3-6 months | ~95% |
| + ATProto support | + 2-4 months additional | ~98% |

`[R3]`

### Return on Investment

| Benefit | Value | Timeline |
|---------|-------|----------|
| **Unique market position** | Only framework with model-driven federation | Immediate upon release |
| **Regulatory readiness** | DMA compliance path for framework users | 2026-2027 |
| **Enterprise sales** | "Federation-ready" is a checkbox for EU customers | 2026+ |
| **Developer adoption** | Significant draw for framework evaluation | Immediate |
| **Content distribution** | Apps built with N3TX reach Fediverse + Bluesky audiences | Upon AP integration |

---

## 7. 🗺️ Decision Framework

**So what?** Not every application should federate. Most should not. But N3TX as a *framework* should provide federation as an opt-in capability, because the applications that need it have no clean alternative today.

### The Federation Litmus Test

Answer these five questions. If you cannot answer YES to at least three, federation is premature:

1. **Cross-boundary interaction**: Do users need to interact across deployments or platforms?
2. **Data portability demand**: Are users asking to own their data and move it between providers?
3. **Network effects**: Does value increase with interconnected nodes?
4. **Censorship/resilience**: Is resistance to single-point-of-failure a core requirement?
5. **Regulatory pressure**: Are you subject to interoperability mandates (e.g., EU DMA)?

`[R3]`

### Application Category Assessment

| Category | Federation Value | Rationale |
|----------|-----------------|-----------|
| Social networking | HIGH | Core product is cross-boundary interaction |
| Content publishing | HIGH | Authors want maximum distribution |
| Messaging | MEDIUM-HIGH | Cross-platform messaging has clear user demand |
| Collaboration | MEDIUM | Useful for cross-org coordination |
| Marketplace | LOW-MEDIUM | Trust and payments require central authority |
| Internal tools | VERY LOW | No cross-org interaction. Just adds cost. |

### Anti-Patterns: When NOT to Federate

These deserve explicit callout because they are common mistakes `[R3]`:

| Anti-Pattern | Symptom | What to Do Instead |
|-------------|---------|-------------------|
| **Feature checkbox** | "Competitors mention federation" | Validate user demand first |
| **Premature federation** | Schema changing weekly | Stabilize data model, then federate |
| **Internal tool federation** | Federating admin panels | Use OIDC/SAML for cross-org access |
| **Real-time-critical federation** | Federating gaming or trading state | Use WebSocket/WebRTC directly |
| **Federation instead of an API** | Using AP for service-to-service comms | Use REST/gRPC/message queues |

### Decision: Framework vs. Application

The decision for N3TX specifically is different from the decision for an individual app:

> N3TX is a **framework**. The question is not "should our app federate?" but "should our framework give developers the ability to federate?" The answer is yes, because:
> 1. No one else offers this -- it is a genuine differentiator.
> 2. The schema-driven architecture makes it natural, not bolted-on.
> 3. The `__federated__ = True` pattern is consistent with N3TX's philosophy.
> 4. The opt-in model means zero cost for apps that do not need it.

### Hybrid Approaches

Full federation and zero federation are not the only options. Recommended progression:

| Model | Description | When |
|-------|-------------|------|
| **Publish-only** | Outbound ActivityPub. No inbox. | Phase 1. Lowest risk. |
| **Allow-list** | Full federation, but only with trusted peers. | Enterprise use. GDPR tractable. |
| **Bridge layer** | App speaks REST; separate service translates to AP/AT. | Maximum decoupling. |
| **Full bidirectional** | Complete ActivityPub + optional ATProtocol. | Mature deployment. |

`[R3]`

---

## 8. 💡 Recommendation

### The Strategy: Phased, Protocol-Abstracted, Opt-In

We recommend building federation support as an additive module using a phased approach, starting with ActivityPub and adding ATProtocol second, behind a protocol abstraction layer.

### Phase 0: Foundation (Weeks 1-2)

**No protocol commitment. Design the abstraction.**

- Add `__federated__` metadata to `ProtoModel` (opt-in per model)
- Define a `FederationAdapter` Protocol (Python Protocol class)
- Ensure all entity IDs are globally resolvable (already true in production)
- New module: `src/n3tx/core/federation/`

```python
# The abstraction layer
class FederationAdapter(Protocol):
    def serialize_object(self, instance: ProtoModel) -> dict: ...
    def serialize_activity(self, action: str, instance: ProtoModel) -> dict: ...
    def deserialize_activity(self, data: dict) -> Tuple[str, dict]: ...
    def verify_request(self, request: Request) -> dict: ...
```

### Phase 1: ActivityPub Publish-Only (Weeks 3-6)

**Get content onto the Fediverse with minimal commitment.**

- WebFinger endpoint (`/.well-known/webfinger`)
- ActivityPub Actor endpoint for each user model
- Outbox endpoint that serializes `model_dump(response=True)` as ActivityStreams
- HTTP Signature support (use [Bovine](https://pypi.org/project/bovine/) library)
- No inbox processing yet

**Key deliverable**: A model with `__federated__ = True` produces a valid ActivityPub Actor. Other Fediverse servers can follow a N3TX user and see their content.

### Phase 2: Full ActivityPub (Weeks 7-10)

**Complete S2S bidirectional federation.**

- Inbox endpoint for receiving activities
- Follow/Accept flow
- Activity routing to model methods (`Like` activity -> `product.like()`)
- Delivery queue (async outbound)
- Follower/Following models

```python
# After Phase 2:
class Post(ProtoModel):
    __tablename__ = 'posts'
    __storable__ = True
    __federated__ = True

    body: str
    user_owner: int

# Creating a Post automatically:
# 1. Stores in SQLite (existing)
# 2. Wraps in Create activity
# 3. Signs with HTTP Signature
# 4. Delivers to followers' inboxes
```

### Phase 3: ATProtocol Support (Weeks 11-20, can parallel Phase 2)

**Add the second protocol behind the same abstraction layer.**

- Lexicon generation from `ProtoModel.schema()`
- DID registration and resolution
- XRPC endpoint mapping
- PDS-compatible record storage (dual storage: SQLite for queries, MST for sync)

### Phase 4: Multi-Protocol Configuration (Ongoing)

**Unified configuration in `create_app()`:**

```python
app = create_app(
    models=[Product, User],
    storage="sqlite:///app.db",
    federation={
        'activitypub': {'enabled': True, 'mode': 'publish_only'},
        'atproto': {'enabled': False},
    }
)
```

### Why ActivityPub First

| Factor | ActivityPub | ATProtocol |
|--------|-------------|------------|
| Implementation weeks | 6-10 | 10-16 |
| Governance risk | LOW (W3C, multi-stakeholder) | HIGH (single company) |
| Regulatory alignment | STRONGEST (W3C standard = DMA candidate) | Growing (IETF draft) |
| Spec stability | HIGH | MEDIUM (pre-1.0) |
| User reach | 12M + Threads potential | 40M Bluesky |
| Library maturity (Python) | Medium (Bovine) | Medium-High (atproto) |

`[R3][R4]`

ActivityPub is the lower-risk, lower-cost, higher-regulatory-alignment choice for Phase 1. ATProtocol's stronger schema compatibility and identity portability make it the right Phase 3 addition. The abstraction layer ensures we do not have to choose one forever.

---

## 9. 🛡️ Risk Register

| # | Risk | Probability | Impact | Mitigation |
|---|------|------------|--------|-----------|
| 1 | **Protocol spec change breaks our integration** | MEDIUM (AP) / HIGH (AT) | HIGH | Pin to stable spec version. Abstraction layer between our code and protocol specifics. AT is pre-1.0 -- isolate in adapter. |
| 2 | **ATProtocol single-vendor governance** -- Bluesky could change direction, get acquired, or fold | MEDIUM | CRITICAL | Start with ActivityPub (multi-stakeholder). Monitor [Free Our Feeds](https://freeourfeeds.com/) initiative. Do not couple to AT-specific infrastructure. MIT Tech Review: ["We need to protect the protocol that runs Bluesky"](https://www.technologyreview.com/2025/01/17/1110063/we-need-to-protect-the-protocol-that-runs-bluesky/) |
| 3 | **Library abandonment** -- Bovine or atproto SDK stops being maintained | MEDIUM | HIGH | Thin adapter layer. Multiple Python libs exist. Worst case: fork and maintain. |
| 4 | **GDPR compliance across federation** -- right to erasure is hard when data is distributed | MEDIUM | HIGH | Allow-list federation. Deletion propagation hooks. Legal review before launch. |
| 5 | **Security vulnerability in federation endpoints** -- each endpoint is an attack surface | MEDIUM | CRITICAL | Treat federation boundary as security boundary. Regular security audits. Rate limiting. Input validation. HTTP Signature verification is non-negotiable. |
| 6 | **Scope creep** -- federation work expands beyond planned phases | HIGH | MEDIUM | Phase strictly. Each phase produces a testable, deployable increment. Review gates between phases. |
| 7 | **User confusion** -- federation adds complexity that confuses developers using N3TX | HIGH | MEDIUM | Federation is entirely opt-in. `__federated__` defaults to nothing. Documentation must be clear. Zero behavior change for apps that do not opt in. |
| 8 | **Moderation cascade** -- federated content brings abuse/spam into N3TX apps | MEDIUM | HIGH | Allow-list mode by default. Content filtering at federation boundary. ABAC rules apply to federated content same as local. |
| 9 | **Interoperability testing burden** -- must test against Mastodon, Misskey, Pleroma individually | MEDIUM | MEDIUM | Target Mastodon compatibility first (75% of fediverse). Use [ActivityPub Fuzzer](https://activitypub.rocks/) for automated testing. |
| 10 | **Market timing** -- build federation and the market does not materialize | LOW-MEDIUM | MEDIUM | Phased approach limits downside. Phase 1 (publish-only) is 2-4 weeks of work. If adoption is low, stop there. The abstraction layer has value even if full federation is deferred. |

`[R3][R4]`

---

## 10. 📎 Appendices

### Appendix A: Architecture Diagram -- Federated N3TX

```
                                    External Fediverse
                                    (Mastodon, Lemmy, Ghost, etc.)
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
|                    EXISTING N3TX CORE (unchanged)                |
|                                                                    |
|  ProtoModel -----> JSON Schema -----> register_routes()            |
|       |                                     |                      |
|       v                                     v                      |
|  StorableMixin          FastAPI Router (CRUD + custom methods)     |
|       |                      |                                     |
|       v                      v                                     |
|  SQLiteStorage          JWTAuthMiddleware -> AccessContext -> ABAC  |
+------------------------------------------------------------------+
                            |
                            v
+------------------------------------------------------------------+
|                    FRONTEND (N3TX.js) (minimal changes)             |
|                                                                    |
|  N3TX.SCHEMA() ---> prototype() ---> DynamicClass                  |
|  Schema-driven rendering + federation status indicators (new)      |
+------------------------------------------------------------------+
```

`[R4]`

### Appendix B: Schema Translation Examples

**N3TX Product -> ActivityStreams Article**:

```json
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    {"n3tx": "https://n3tx.io/ns/v1"}
  ],
  "type": "Article",
  "id": "https://example.com/products/1",
  "name": "Widget Pro",
  "content": "A premium widget for professionals",
  "attributedTo": "https://example.com/users/alice",
  "published": "2026-02-25T12:00:00Z",
  "n3tx:price": 29.99,
  "replies": {
    "type": "Collection",
    "id": "https://example.com/products/1/comments",
    "totalItems": 5
  }
}
```

**N3TX Product -> ATProtocol Lexicon**:

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

`[R4]`

### Appendix C: Competitive Landscape

**No existing framework offers model-driven federation.** Every current federated application is either:

1. **A purpose-built application** (Mastodon, Lemmy, GoToSocial) where federation is hard-coded for one use case
2. **A library** (Bovine, arroba, Fedify) that provides protocol primitives but no schema-to-endpoint generation

```
           Schema-driven                    Federation
           +----------+                    +----------+
           | Django    |                    | Mastodon |
           | FastAPI   |                    | Lemmy    |
           | Rails     |                    | GoToSocial|
           | N3TX    |<---- gap ------>   | Takahee  |
           +----------+                    +----------+

    N3TX with __federated__ bridges this gap.
```

`[R4]`

### Appendix D: Effort Breakdown by Category

| Category | Items | Estimated Effort |
|----------|-------|-----------------|
| **Already aligned** (minor adapters) | Schema translation, self-describing instances, access rule extension, model registry | 2-3 weeks |
| **Medium additions** (new modules) | WebFinger, federation routes, delivery queue, JSON-LD context, follower model, XRPC router | 4-6 weeks |
| **Major additions** (new subsystems) | HTTP Signatures, DID support, MST storage, content addressing, repo sync, key management | 8-12 weeks |
| **ActivityPub only** | All AP items | **6-10 weeks** |
| **ATProtocol only** | All AT items | **10-16 weeks** |
| **Both protocols** (with shared infra) | All items | **14-20 weeks** |

`[R4]`

### Appendix E: Protocol Selection Scoring (Weighted)

| Criterion | Weight | ActivityPub (1-5) | ATProtocol (1-5) |
|-----------|--------|-------------------|-------------------|
| Use case fit | 25 | 4 | 4 |
| Ecosystem maturity | 20 | 5 | 3 |
| Spec governance | 15 | 5 | 2 |
| Developer experience | 15 | 3 | 4 |
| Data model compatibility | 10 | 3 | 5 |
| User base reach | 10 | 4 | 4 |
| Operational cost | 5 | 3 | 4 |
| **Weighted total** | **100** | **4.00** | **3.50** |

ActivityPub wins on governance and maturity. ATProtocol wins on DX and schema compatibility. Both score well on use case fit and user reach. The phased approach captures both. `[R3]`

### Appendix F: Key Dates to Watch

| Date | Event | Impact |
|------|-------|--------|
| **May 2026** | EU DMA review -- social network interoperability assessment | Could mandate ActivityPub support for major platforms |
| **Nov 2026** | eIDAS 2.0 -- EU digital identity wallets mandatory | Creates DID/VC infrastructure for private-sector use |
| **Q3 2026** | W3C Social Web Working Group -- updated ActivityPub specs | New AP features, backward-compatible |
| **2026** | ATProtocol IETF Working Group formation (projected) | Standards credibility for ATProto |
| **Nov 2027** | eIDAS 2.0 -- businesses must accept digital wallet | Hard compliance deadline |
| **2026-2027** | Bluesky subscription launch | Tests ATProto sustainability |

### Appendix G: Source Index

**Research Documents**:
- `[R1]` `/workspace/.traces/research/decentralized-protocols/01-industry-landscape.md` -- 665 lines. Market data, platform numbers, enterprise adoption, regulatory landscape, monetization.
- `[R2]` `/workspace/.traces/research/decentralized-protocols/02-technical-deep-dive.md` -- 980 lines. Protocol architectures, data formats, security, scalability, interoperability.
- `[R3]` `/workspace/.traces/research/decentralized-protocols/03-decision-framework.md` -- 844 lines. When to federate, build/integrate analysis, cost models, anti-patterns, decision tree.
- `[R4]` `/workspace/.traces/research/decentralized-protocols/04-our-stack-relevance.md` -- 1,219 lines. N3TX architecture mapping, gap analysis, `__federated__` design, competitive analysis.
- `[R5]` `/workspace/.traces/research/decentralized-protocols/05-identity-data-portability.md` -- 1,010 lines. DIDs, account portability, VCs, platform risk, eIDAS 2.0, DID-JWT integration.

**Key External Sources**:
- [W3C ActivityPub Specification](https://www.w3.org/TR/activitypub/)
- [AT Protocol Documentation](https://atproto.com/)
- [W3C DID v1.0 Recommendation](https://www.w3.org/TR/did-1.0/)
- [W3C Verifiable Credentials 2.0](https://www.w3.org/press-releases/2025/verifiable-credentials-2-0/)
- [EU Digital Markets Act Portal](https://digital-markets-act.ec.europa.eu/index_en)
- [eIDAS 2.0 Compliance](https://yousign.com/blog/eidas-2-0-digital-identity-wallet-compliance-requirements)
- [Bluesky Statistics 2026](https://backlinko.com/bluesky-statistics)
- [FediDB -- Fediverse Statistics](https://fedidb.org/)
- [MIT Technology Review -- Protecting ATProtocol](https://www.technologyreview.com/2025/01/17/1110063/we-need-to-protect-the-protocol-that-runs-bluesky/)
- [Ghost 6.0 ActivityPub](https://techcrunch.com/2025/08/05/substack-rival-ghost-connects-to-the-open-social-web-with-its-latest-public-release/)
- [WordPress ActivityPub Plugin](https://wordpress.org/plugins/activitypub/)
- [Social Web Foundation -- W3C Working Group](https://socialwebfoundation.org/2026/01/15/new-social-web-working-group-at-w3c/)
- [Bovine -- Python ActivityPub Library](https://pypi.org/project/bovine/)
- [atproto -- Python ATProtocol SDK](https://pypi.org/project/atproto/)
- [Bridgy Fed -- Cross-Protocol Bridge](https://fed.brid.gy/docs)
- [Research and Markets -- Decentralized Social Media](https://www.researchandmarkets.com/reports/6215126/blockchain-based-decentralized-social-media)
- [GM Insights -- Decentralized Identity Market](https://www.gminsights.com/industry-analysis/decentralized-identity-market)

---

*This analysis reflects data available as of February 25, 2026. Key review dates: May 2026 (DMA review), November 2026 (eIDAS wallets), Q3 2026 (W3C spec updates). Revisit this document at each milestone.*
