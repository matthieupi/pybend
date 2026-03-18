# Technical Deep Dive: Decentralized Social Protocols

**ActivityPub, AT Protocol, Nostr, and Matrix -- Architecture, Implementation, Security, and Interoperability**

---

## Executive Summary

Four protocols dominate the decentralized social landscape in 2025-2026: **ActivityPub** (powering the Fediverse / Mastodon), **AT Protocol** (powering Bluesky), **Nostr** (a minimalist relay-based system), and **Matrix** (decentralized encrypted messaging). Each embodies fundamentally different architectural philosophies -- from ActivityPub's W3C-standardized federation to Nostr's radical simplicity of keys-and-JSON. This document dissects their internal architectures, data formats, security models, scalability strategies, and the bridges emerging between them.

**Current scale (late 2025):** Bluesky has reached ~40 million registered users. Mastodon has ~10 million registered accounts with under 1 million monthly active users. Nostr has ~21,000 active users but growing relay infrastructure. Matrix serves millions of users across government, enterprise, and consumer deployments. [^sprout][^webpro][^glukhov]

---

## Table of Contents

1. [ActivityPub: W3C Spec Anatomy](#1-activitypub-w3c-spec-anatomy)
2. [AT Protocol: Bluesky's Architecture](#2-at-protocol-blueskys-architecture)
3. [Nostr: Minimalist Event Relay System](#3-nostr-minimalist-event-relay-system)
4. [Matrix: Encrypted Federation](#4-matrix-encrypted-federation)
5. [Protocol Comparison Matrix](#5-protocol-comparison-matrix)
6. [Data Format Philosophy](#6-data-format-philosophy)
7. [Implementation Complexity](#7-implementation-complexity)
8. [Security Considerations](#8-security-considerations)
9. [Scalability Analysis](#9-scalability-analysis)
10. [Interoperability and Bridges](#10-interoperability-and-bridges)
11. [Engineering Recommendations](#11-engineering-recommendations)

---

## 1. ActivityPub: W3C Spec Anatomy

ActivityPub is a [W3C Recommendation](https://www.w3.org/TR/activitypub/) (January 2018) built on top of [ActivityStreams 2.0](https://www.w3.org/TR/activitystreams-core/). It defines two sub-protocols: **Client-to-Server (C2S)** for user interactions and **Server-to-Server (S2S)** for federation between instances. In practice, S2S dominates -- Mastodon and nearly every major implementation ignores C2S entirely, relying on proprietary REST APIs for client communication. [^apwiki][^c2sbate]

### 1.1 Core Concepts: Actor, Inbox, Outbox

Every identity in ActivityPub is an **Actor** -- a JSON-LD document served at a URL:

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "Person",
  "id": "https://mastodon.social/users/alice",
  "preferredUsername": "alice",
  "inbox": "https://mastodon.social/users/alice/inbox",
  "outbox": "https://mastodon.social/users/alice/outbox",
  "followers": "https://mastodon.social/users/alice/followers",
  "following": "https://mastodon.social/users/alice/following",
  "publicKey": {
    "id": "https://mastodon.social/users/alice#main-key",
    "owner": "https://mastodon.social/users/alice",
    "publicKeyPem": "-----BEGIN PUBLIC KEY-----\n..."
  }
}
```

The three foundational data types are: [^apw3c]

| Type | Description | Examples |
|------|-------------|---------|
| **Object** | Any content entity | Note, Image, Video, Article, Event, Place |
| **Activity** | An action performed on/with an object | Create, Follow, Like, Announce, Delete, Update |
| **Actor** | An entity that performs activities | Person, Group, Application, Service, Organization |

**Inbox** (S2S): An `OrderedCollection` endpoint where other servers POST activities destined for this actor. This is the core federation mechanism -- when Bob on `server-b.social` follows Alice on `mastodon.social`, `server-b.social` POSTs a `Follow` activity to Alice's inbox.

**Outbox** (C2S): An `OrderedCollection` where the actor's own client POSTs activities. The server then handles side effects (storage, federation to followers). Since C2S adoption is minimal, most servers treat the outbox as read-only for external consumers.

### 1.2 Federation Flow: S2S Protocol

```
Server A (alice@a.social)              Server B (bob@b.social)
         |                                       |
         |  1. Alice creates a Note              |
         |  POST /users/alice/outbox              |
         |  (C2S -- or via proprietary API)       |
         |                                       |
         |  2. Server A resolves followers        |
         |  Finds bob@b.social in followers list  |
         |                                       |
         |  3. Server A signs & sends             |
         |  POST https://b.social/users/bob/inbox |
         |  Headers: Signature, Date, Digest      |
         |  Body: { Create { Note } }             |
         |-------------------------------------->|
         |                                       |
         |  4. Server B verifies HTTP Signature   |
         |  Fetches alice's publicKey from a.social|
         |  Validates Signature header             |
         |                                       |
         |  5. Server B stores Note in bob's feed |
         |  202 Accepted                          |
         |<--------------------------------------|
```

### 1.3 HTTP Signatures

ActivityPub relies on [HTTP Signatures](https://docs.joinmastodon.org/spec/activitypub/) for authentication. Every outgoing S2S request includes a `Signature` header constructed from: [^mastodonapspec]

1. **Key ID**: The URL of the sender's public key
2. **Algorithm**: Typically `rsa-sha256`
3. **Headers signed**: Usually `(request-target) host date digest`
4. **Signature value**: Base64-encoded RSA signature

```http
POST /users/bob/inbox HTTP/1.1
Host: b.social
Date: Mon, 15 Jan 2025 10:30:00 GMT
Digest: SHA-256=X48E9qOokqqrvdts8nOJRJN3OWDUoyWxBf7kbu9DBPE=
Signature: keyId="https://a.social/users/alice#main-key",
           algorithm="rsa-sha256",
           headers="(request-target) host date digest",
           signature="Y2FkYW..."
Content-Type: application/activity+json

{ "type": "Create", "actor": "https://a.social/users/alice", ... }
```

The receiving server validates the signature within a **30-second time window** (checking the `Date` header against current time). It fetches the sender's actor document to retrieve the public key, then verifies the cryptographic signature against the signed headers. [^mastodonapspec]

### 1.4 JSON-LD and ActivityStreams 2.0

ActivityPub content is serialized as **JSON-LD** (JavaScript Object Notation for Linked Data). The `@context` field maps short property names to globally unique URIs: [^as2core]

```json
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    "https://w3id.org/security/v1"
  ],
  "type": "Create",
  "actor": "https://a.social/users/alice",
  "object": {
    "type": "Note",
    "content": "<p>Hello, Fediverse!</p>",
    "attributedTo": "https://a.social/users/alice",
    "to": ["https://www.w3.org/ns/activitystreams#Public"],
    "cc": ["https://a.social/users/alice/followers"]
  }
}
```

ActivityStreams 2.0 comprises two parts: **Core** (JSON serialization rules) and **Vocabulary** (defined object types and properties). The vocabulary defines ~30 activity types (`Create`, `Delete`, `Follow`, `Like`, `Announce`, `Undo`, `Accept`, `Reject`, `Block`, `Update`, etc.) and ~20 object types (`Note`, `Article`, `Image`, `Video`, `Audio`, `Event`, `Place`, `Question`, `Collection`, etc.). [^as2core]

Importantly, AS2 can be treated as a **restricted profile of JSON-LD** -- implementations do not require full JSON-LD processing. Most implementations parse it as plain JSON with known field names. [^as2core]

### 1.5 WebFinger Discovery

[WebFinger](https://www.w3.org/community/reports/socialcg/CG-FINAL-apwf-20240608/) provides the discovery mechanism for resolving `user@domain` identifiers to actor URLs: [^apwf]

```
GET /.well-known/webfinger?resource=acct:alice@mastodon.social HTTP/1.1
Host: mastodon.social

{
  "subject": "acct:alice@mastodon.social",
  "links": [
    {
      "rel": "self",
      "type": "application/activity+json",
      "href": "https://mastodon.social/users/alice"
    }
  ]
}
```

The client extracts the `href` from the link with `rel: "self"` and `type: "application/activity+json"`, then fetches that URL to obtain the full actor document.

### 1.6 C2S vs S2S: The Specification Gap

| Aspect | Client-to-Server (C2S) | Server-to-Server (S2S) |
|--------|----------------------|----------------------|
| Purpose | Client creates/modifies content via actor's outbox | Servers deliver activities to remote inboxes |
| Transport | POST to outbox endpoint | POST to remote inbox endpoint |
| Auth | OAuth 2.0 Bearer tokens | HTTP Signatures |
| Adoption | Virtually none (Mastodon, Pleroma, Misskey all skip it) | Universal among Fediverse servers |
| Maturity | Underspecified; missing handling for Announce, Update, etc. | Well-tested across thousands of instances |
| Problem | Each server implements its own proprietary client API | No standard client API means vendor lock-in to server software |

The practical consequence: **there is no standard client API for the Fediverse**. A Mastodon client cannot talk to a Pleroma server without implementing Pleroma's proprietary API. [^c2sbate][^c2sblog]

---

## 2. AT Protocol: Bluesky's Architecture

The [Authenticated Transfer Protocol](https://atproto.com/specs/atp) (AT Protocol / atproto) was developed by Bluesky beginning in 2019 and launched publicly in 2024. In September 2025, the IETF published an Internet Draft for the core specification, and in January 2026 a working group charter was published for standardization. [^atpwiki]

### 2.1 Architectural Components

AT Protocol separates concerns into four distinct service roles:

```
+------------------+      +------------------+      +------------------+
|  Client (App)    |      |    App View      |      |    Labeler       |
|  (e.g., bsky.app)|      | (e.g., Bluesky   |      | (Moderation      |
|                  |      |  feed service)   |      |  service)        |
+--------+---------+      +--------+---------+      +--------+---------+
         |                         |                          |
         |    XRPC (HTTPS)         |    Subscribe to          |
         v                         v    firehose               v
+--------+---------+      +--------+---------+      Labels attached
|  PDS (Personal   |----->|  Relay / BGS     |      to responses
|  Data Server)    |      | (Big Graph       |
|  - Hosts repo    |      |  Service)        |
|  - Auth/identity |      | - Crawls repos   |
|  - Signs commits |      | - Verifies sigs  |
+------------------+      | - Emits firehose |
                          +------------------+
```

**Personal Data Server (PDS):** The user's trusted agent. Hosts the user's data repository, handles authentication, manages the user's DID, and routes XRPC requests. A PDS is conceptually similar to an email server -- it holds your data and speaks on your behalf. [^atpbluesky]

**Relay / Big Graph Service (BGS):** Crawls all PDS instances and outputs a unified event stream (the "firehose"). Relays verify cryptographic signatures and Merkle Search Tree proofs on all updates. The firehose currently sustains **over 2,000 events per second** with hundreds of active consumers. [^relayops]

**App View:** Consumes the firehose and builds application-specific indexes and aggregations. The Bluesky social app is one App View; search engines, analytics tools, and alternative social clients are others. Multiple App Views can coexist over the same data.

**Labeler:** Produces content moderation labels (spam, NSFW, misleading, etc.) that App Views and clients can subscribe to. Labels are associated with specific records or accounts. Users choose which labelers to trust -- a stackable, user-centric moderation model. [^bskylabels][^bskymod]

### 2.2 Identity: DID PLC and DID Web

AT Protocol uses two DID (Decentralized Identifier) methods for account identity: [^atpidentity]

**DID PLC** (`did:plc:...`): A self-authenticating DID designed for account portability. The DID document contains signing keys, rotation keys, and the PDS service endpoint. Updates require a rotation key signature. Bluesky operates `plc.directory` as the current resolution service.

**DID Web** (`did:web:...`): Uses standard DNS/HTTPS for DID document hosting. The user controls the DID document on their own domain. More self-sovereign but lacks the built-in key rotation of DID PLC.

**Handles** are DNS names (e.g., `alice.bsky.social` or `alice.com`) that resolve to a DID. The handle-to-DID mapping is verified via DNS TXT record or `.well-known/atproto-did` endpoint.

**Account migration** is a first-class operation: users can move their entire data repository from one PDS to another, with the DID pointing to the new PDS after migration. For DID PLC accounts, this requires the old PDS to sign a rotation operation (or the user to hold their own rotation key). [^atpmigration]

### 2.3 Data Repositories and Merkle Search Trees

Every user's data is stored in a **repository** -- a signed, content-addressed data structure serialized as [DAG-CBOR](https://atproto.com/specs/repository) and packaged in [CAR files](https://ipld.io/specs/transport/car/carv1/) (Content Addressable aRchives). [^atprepo]

```
Repository Structure:
+----------------------------------+
|  Signed Commit                   |
|  - version: 3                    |
|  - did: "did:plc:abc123"        |
|  - rev: "2024..."               |
|  - data: CID -> MST root        |
|  - sig: Ed25519 signature       |
+----------------------------------+
           |
           v
+----------------------------------+
|  Merkle Search Tree (MST)        |
|  Key: <collection>/<rkey>        |
|  Value: CID -> record data       |
|                                  |
|  e.g.:                           |
|  app.bsky.feed.post/3k...  -> CID|
|  app.bsky.actor.profile/self->CID|
|  app.bsky.graph.follow/3k...->CID|
+----------------------------------+
           |
           v
+----------------------------------+
|  Records (DAG-CBOR objects)      |
|  Each record is a Lexicon-typed  |
|  CBOR document with a CID        |
+----------------------------------+
```

The **Merkle Search Tree (MST)** is a deterministic, content-addressed B-tree variant. Keys are sorted lexicographically, and the tree structure is derived from key hashes -- this means any two repositories with the same key-value pairs produce identical tree structures (and thus identical root hashes). This property enables: [^mstrepo]

- **Efficient sync**: Two parties can compare root hashes and exchange only differing subtrees
- **Cryptographic verification**: The relay can verify that a reported update is consistent with the claimed repository state
- **Tamper evidence**: Any modification changes the root hash, propagating up through the signed commit

### 2.4 Lexicon Schema System and XRPC

**Lexicon** is AT Protocol's schema language. Every API endpoint, record type, and event stream is defined by a Lexicon document identified by a **Namespaced Identifier (NSID)** -- a reverse-DNS string like `app.bsky.feed.post` or `com.atproto.repo.createRecord`. [^lexicon][^nsid]

```json
{
  "lexicon": 1,
  "id": "app.bsky.feed.post",
  "defs": {
    "main": {
      "type": "record",
      "description": "Record containing a Bluesky post.",
      "key": "tid",
      "record": {
        "type": "object",
        "required": ["text", "createdAt"],
        "properties": {
          "text": { "type": "string", "maxLength": 3000, "maxGraphemes": 300 },
          "createdAt": { "type": "string", "format": "datetime" },
          "reply": { "type": "ref", "ref": "#replyRef" },
          "embed": { "type": "union", "refs": ["#imagesEmbed", "#externalEmbed"] },
          "langs": { "type": "array", "items": { "type": "string", "format": "language" } }
        }
      }
    }
  }
}
```

**XRPC** (Cross-organizational Remote Procedure Calls) is a thin wrapper around HTTPS. It maps Lexicon NSIDs to HTTP endpoints: [^atpbluesky]

- `com.atproto.repo.createRecord` -> `POST /xrpc/com.atproto.repo.createRecord`
- `app.bsky.feed.getTimeline` -> `GET /xrpc/app.bsky.feed.getTimeline`

Queries become GET requests with query parameters; procedures become POST requests with JSON bodies. Lexicon schemas validate both request and response payloads.

**Key design difference from ActivityPub**: Lexicon namespaces are **globally extensible without coordination**. Any organization can define new NSIDs under their domain (e.g., `org.example.custom.record`), and these records live in user repositories alongside Bluesky records. This enables multiple applications to share the same data layer.

### 2.5 Firehose and Event Streaming

The relay emits a **firehose** -- a WebSocket stream of every repository update across the network. Consumers (App Views, feed generators, analytics) subscribe and process events in real-time. [^firehose]

To reduce the cost of firehose consumption for lighter use cases, Bluesky introduced **Jetstream** -- a simplified, filtered event stream that does not require processing raw CAR file blocks. [^jetstream]

Scaling the firehose is achieved through: [^relayops]
- **Sharding by DID**: The account DID is a natural partition key; events for the same account always route to the same shard
- **Fan-out services (Rainbow)**: Servers that re-broadcast the firehose to many downstream consumers, reducing relay bandwidth
- **Non-archival relays**: Upcoming changes remove the requirement for relays to maintain full history, dramatically reducing storage costs

---

## 3. Nostr: Minimalist Event Relay System

[Nostr](https://nostr.com/) (Notes and Other Stuff Transmitted by Relays) is intentionally minimal. The entire core protocol fits in a single page ([NIP-01](https://nips.nostr.com/1)). There are no accounts, no servers with authority, no registration -- just cryptographic keys, JSON events, and relay servers. [^nostrproto]

### 3.1 Identity: Key Pairs

Identity is a **secp256k1 key pair** (the same curve Bitcoin uses). Your public key (32 bytes, hex-encoded) is your identity. There is no username registration, no server authority, no recovery mechanism beyond backing up your private key. [^nostrtech]

Human-readable names are layered on via **NIP-05**: a user claims `alice@example.com` by hosting a JSON file at `https://example.com/.well-known/nostr.json?name=alice` that maps the name to their public key.

### 3.2 Event Model

Every piece of data in Nostr is an **event** -- a signed JSON object: [^nip01]

```json
{
  "id": "4376c65d2f232afbe9b882a35baa4f6fe8667c4e684749af565f981833ed6a65",
  "pubkey": "6e468422dfb74a5738702a8823b9b28168abab8655faacb6853cd0ee15deee93",
  "created_at": 1673347337,
  "kind": 1,
  "tags": [
    ["e", "5c83da77af1dec6d7289834998ad7aafbd9e2191396d75ec3cc27f5a77226f36", "wss://nostr.example.com"],
    ["p", "f7234bd4c1394dda46d09f35bd384dd30cc552ad5541990f98844fb06676e9ca"]
  ],
  "content": "Hello, Nostr!",
  "sig": "908a15e46fb4d8675bab026fc230a0e3542bfade63da02d542fb78b2a8513fcd..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | 32-byte hex | SHA-256 hash of the serialized event (sans `id` and `sig`) |
| `pubkey` | 32-byte hex | Author's public key |
| `created_at` | Unix timestamp | Event creation time |
| `kind` | Integer | Event type (1=text note, 0=metadata, 3=contacts, 7=reaction, etc.) |
| `tags` | Array of arrays | Structured metadata (references, mentions, relays, etc.) |
| `content` | String | Event payload (interpretation depends on `kind`) |
| `sig` | 64-byte hex | Schnorr signature over the serialized event |

### 3.3 Event Kind Categories

Events are categorized by their `kind` number into three persistence classes: [^nip01]

| Category | Kind Range | Behavior |
|----------|-----------|----------|
| **Regular** | 1000-9999, 4-44, 1, 2 | Stored permanently by relays |
| **Replaceable** | 10000-19999, 0, 3 | Only latest per (pubkey, kind) is kept |
| **Ephemeral** | 20000-29999 | Not stored; real-time only |
| **Parameterized Replaceable** | 30000-39999 | Latest per (pubkey, kind, d-tag) |

This categorization is elegant in its simplicity -- the `kind` number alone determines storage semantics.

### 3.4 Relay Architecture and WebSocket Protocol

Clients connect to relays via **WebSockets**. The protocol defines three client message types and five relay message types: [^nip01]

**Client -> Relay:**
```
["EVENT", <event>]                    # Publish an event
["REQ", <sub_id>, <filter>, ...]      # Subscribe to events matching filters
["CLOSE", <sub_id>]                   # End a subscription
```

**Relay -> Client:**
```
["EVENT", <sub_id>, <event>]          # Deliver a matching event
["OK", <event_id>, <bool>, <msg>]     # Accept/reject acknowledgment
["EOSE", <sub_id>]                    # End of stored events (live mode begins)
["CLOSED", <sub_id>, <msg>]           # Subscription terminated
["NOTICE", <msg>]                     # Human-readable error/info
```

**Filters** specify what events a subscription wants:

```json
{
  "ids": ["<event_id_prefix>"],
  "authors": ["<pubkey_prefix>"],
  "kinds": [1, 7],
  "#e": ["<event_id>"],
  "#p": ["<pubkey>"],
  "since": 1673347337,
  "until": 1673433737,
  "limit": 100
}
```

### 3.5 Key NIPs (Nostr Implementation Possibilities)

The NIP system is Nostr's extension mechanism. Important NIPs include: [^nips]

| NIP | Name | Description |
|-----|------|-------------|
| NIP-01 | Basic Protocol | Core event structure, relay communication |
| NIP-02 | Follow List | Kind 3 event: contact list with relay hints |
| NIP-04 | Encrypted DM (deprecated) | AES-CBC with shared ECDH secret |
| NIP-05 | DNS Identity | Maps `user@domain` to pubkey via `.well-known` |
| NIP-17 | Private DMs | Gift-wrapped encrypted messages replacing NIP-04 |
| NIP-44 | Versioned Encryption | XChaCha20-Poly1305 v2 encryption standard |
| NIP-50 | Search | Human-readable text search queries |
| NIP-57 | Lightning Zaps | Bitcoin Lightning payment receipts on events |
| NIP-65 | Relay List Metadata | Declares user's preferred relays |

### 3.6 Lightning Integration (NIP-57)

Nostr is unique among social protocols in having **native payment integration**. NIP-57 defines two event kinds: [^nip57]

- **Kind 9734** (Zap Request): A payer's request to a recipient's Lightning wallet for an invoice
- **Kind 9735** (Zap Receipt): Confirmation that the invoice was paid

Zaps are publicly verifiable and linked to specific posts or users. This serves dual purposes: tipping/monetization and **spam deterrence** (requiring a small payment to interact raises the cost of spam).

---

## 4. Matrix: Encrypted Federation

[Matrix](https://spec.matrix.org/latest/) is a decentralized, encrypted communication protocol. Unlike the other three protocols (which target social media), Matrix targets **messaging and real-time communication** -- group chats, voice/video calls, and IoT device communication. [^matrixspec]

### 4.1 Homeserver Federation

Matrix operates through **homeservers** -- each user registers on a homeserver (e.g., `matrix.org`, `element.io`, or self-hosted). Homeservers communicate via the **Server-Server (Federation) API** using HTTPS with TLS and server-to-server authentication. [^matrixfed]

```
+-------------------+                    +-------------------+
|  Homeserver A     |                    |  Homeserver B     |
|  (matrix.org)     |                    |  (element.io)     |
|                   |   Federation API   |                   |
|  Users:           |<==================>|  Users:           |
|  @alice:matrix.org|   (HTTPS + TLS)    |  @bob:element.io  |
|                   |                    |                   |
|  Rooms: !abc:...  |  Event Graph (DAG) |  Rooms: !abc:...  |
|  (full replica)   |  synchronized via  |  (full replica)   |
|                   |  eventual consist. |                   |
+-------------------+                    +-------------------+
```

Every homeserver participating in a room maintains a **full replica** of the room's event history. Events are signed by the originating server (including parent relations, type, depth, and payload hash) and pushed via federation. [^matrixevents]

### 4.2 Event Model and Room DAG

Matrix models communication as a **directed acyclic graph (DAG)** of events per room. Each event references zero or more parent events, creating a partial ordering: [^matrixrooms]

```
Event DAG for Room !abc:matrix.org

    [m.room.create]
          |
    [m.room.join_rules]
          |
    [m.room.member: @alice joins]
         / \
        /   \
[msg: "Hi"] [m.room.member: @bob joins]
       \   /
        \ /
    [msg: "Hello!"]
         |
    [msg: "How are you?"]
```

**Event types** fall into two categories: [^matrixrooms]

| Category | Examples | Behavior |
|----------|----------|----------|
| **State events** | `m.room.create`, `m.room.name`, `m.room.topic`, `m.room.member`, `m.room.power_levels`, `m.room.join_rules`, `m.room.encryption` | Have a `state_key`; define current room state |
| **Timeline events** | `m.room.message`, `m.room.encrypted`, `m.reaction` | Messages and interactions; form the conversation timeline |
| **Ephemeral events** | `m.typing`, `m.receipt`, `m.presence` | Not persisted in the DAG; real-time notifications only |

Custom event types follow Java package naming convention (e.g., `com.example.custom.event`) and can be used without modifying the protocol. [^matrixrooms]

### 4.3 State Resolution Algorithm

When two homeservers independently generate events (a fork in the DAG), the **state resolution algorithm** deterministically merges the conflicting states. This is one of Matrix's most complex components. [^stateres]

**State Resolution v2** (used in room versions 2+, current as of v12): [^stateresv2]

1. Separate events into **unconflicted** (same event for a state key across all forks) and **conflicted** sets
2. Extract **power events** from the conflicted set (power levels, join rules, membership leaves)
3. Order power events by **auth chain depth** and timestamp
4. Apply iterative auth checks: walk through ordered events, applying each if authorized by the current resolved state
5. Then apply non-power conflicted events using the same process
6. Overlay unconflicted state on top

This ensures that access control events (who has power, who can join) are resolved before content events, preventing attacks where a user escalates privileges in one fork and uses them in another.

**2025 development**: The Matrix community has been working on **Project Hydra** to further improve state resolution and address "state resets" -- unintended rollbacks of room state caused by Byzantine actors. The [TARDIS](https://matrix.org/blog/2025/08/project-hydra-improving-state-res/) tool (Time Agnostic Room DAG Inspection Service) was created for debugging state resolution edge cases. [^hydra]

### 4.4 End-to-End Encryption: Olm and Megolm

Matrix provides E2E encryption via two cryptographic ratchets: [^olmmegolm]

**Olm** (1:1 encryption): Implements the Double Ratchet algorithm (same as Signal). An Olm session is a bidirectional encrypted channel between two devices. Used for key exchange and small payloads.

**Megolm** (group encryption): Designed for rooms with many participants where per-recipient Olm encryption would be prohibitively expensive. Each sending device maintains its own Megolm ratchet:

```
Megolm Session:
- Ratchet state (can advance forward, never backward)
- Ed25519 signing key pair (authenticity)
- Each message derives a unique key from the ratchet state
- Encryption: AES-256-CBC with PKCS#7 padding
- MAC: HMAC-SHA-256 (truncated to 64 bits)
```

Megolm session keys are distributed to room members via Olm-encrypted channels. A recipient who joins later can receive historical keys (if the sender's client supports it) to decrypt past messages.

### 4.5 Spaces and Sliding Sync

**Spaces** organize rooms hierarchically -- a Space is itself a room containing state events that reference child rooms, creating tree-like structures for communities, organizations, or topic groups.

**Simplified Sliding Sync** ([MSC4186](https://github.com/matrix-org/matrix-spec-proposals/blob/erikj/sss/proposals/4186-simplified-sliding-sync.md)) is a major performance improvement in Matrix 2.0. Instead of the original sync API (which dumps all room state on initial sync -- catastrophically slow for users in many rooms), Sliding Sync provides: [^slidingsync]

- Window-based room list loading (only sync rooms visible in the UI)
- Incremental updates via long-polling
- Native implementation in Synapse 1.114+ (no proxy needed)
- Order-of-magnitude faster initial sync times

---

## 5. Protocol Comparison Matrix

### 5.1 Feature Comparison

| Feature | ActivityPub | AT Protocol | Nostr | Matrix |
|---------|------------|-------------|-------|--------|
| **Specification body** | W3C Recommendation | IETF Internet Draft (2025) | Community NIPs | Matrix.org Foundation |
| **First stable release** | 2018 | 2024 | 2020 | 2019 (spec 1.0) |
| **Primary use case** | Social networking | Social networking | Social + payments | Messaging + comms |
| **Identity model** | WebFinger (`user@domain`) | DID (`did:plc:...`) + handle | secp256k1 key pair | `@user:homeserver` |
| **Identity portability** | None (tied to server) | Full (repo migration) | Full (keys are identity) | Partial (account migration exists but limited) |
| **Data format** | JSON-LD (ActivityStreams 2.0) | DAG-CBOR + Lexicon schemas | Plain JSON events | JSON events |
| **Transport** | HTTPS (push-based) | HTTPS (XRPC) + WebSocket firehose | WebSocket | HTTPS + optional WebSocket |
| **Federation model** | Server-to-server push | PDS -> Relay -> App View pipeline | Client -> Relay(s) pub/sub | Server-to-server (full mesh per room) |
| **Content addressing** | URL-based | Content hashes (CIDs) | Event ID (SHA-256 of content) | Event ID (hash of content + metadata) |
| **Encryption (E2E)** | None (proposed MLS extension) | None (in development) | NIP-44 (XChaCha20-Poly1305) | Olm/Megolm (Double Ratchet + group ratchet) |
| **Moderation** | Instance-level blocklists | Stackable labelers (user choice) | Relay-level filtering | Room-level power levels + moderation bots |
| **Payments** | None | None | NIP-57 Lightning Zaps | None |
| **Schema extensibility** | JSON-LD contexts | Lexicon NSID namespaces | NIP kind numbers | Custom event types |
| **Offline-first** | No | Partial (repo is portable) | No | Yes (local event store) |
| **Users (late 2025)** | ~10M registered (Mastodon) | ~40M registered (Bluesky) | ~21K active | Millions (fragmented across homeservers) |

### 5.2 Architecture Philosophy Comparison

| Dimension | ActivityPub | AT Protocol | Nostr | Matrix |
|-----------|------------|-------------|-------|--------|
| **Complexity** | Medium | High | Very Low | Very High |
| **Data ownership** | Server owns data | User owns repo (cryptographic) | User signs events (keys are sovereign) | Server stores replicas |
| **Discovery** | WebFinger + server relays | Relay firehose + App Views | Relay queries + NIP-05 | Room directory + identity servers |
| **Consistency** | Eventual (best-effort delivery) | Strong (signed commits, MST proofs) | Eventual (no guaranteed delivery) | Eventual (DAG convergence via state res) |
| **Trust model** | Trust your server admin | Trust your PDS (but can migrate) | Trust no one (verify signatures) | Trust your homeserver for unencrypted rooms |

---

## 6. Data Format Philosophy

The four protocols embody fundamentally different approaches to data modeling:

### 6.1 ActivityStreams 2.0 (ActivityPub)

**Philosophy**: Linked Data universality. Every entity is a URL. Every property maps to a globally unique URI via JSON-LD contexts. Extensibility comes from adding new JSON-LD contexts.

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "Note",
  "id": "https://server.example/notes/1",
  "attributedTo": "https://server.example/users/alice",
  "content": "Hello world",
  "published": "2025-01-15T10:30:00Z",
  "to": ["https://www.w3.org/ns/activitystreams#Public"]
}
```

**Strengths**: Semantic web compatibility; theoretically infinite extensibility; W3C backing.
**Weaknesses**: JSON-LD complexity (most implementations ignore it); no schema validation; ambiguous field semantics across implementations; verbose.

### 6.2 Lexicon (AT Protocol)

**Philosophy**: Contract-driven development. Every record type has a Lexicon schema that defines structure, validation rules, and documentation. Schemas are identified by reverse-DNS NSIDs and are globally resolvable.

```json
{
  "$type": "app.bsky.feed.post",
  "text": "Hello world",
  "createdAt": "2025-01-15T10:30:00.000Z",
  "langs": ["en"]
}
```

**Strengths**: Strong typing; automatic validation; code generation; clear namespace ownership; binary-efficient (CBOR).
**Weaknesses**: Centralized schema discovery (currently); more complex tooling required; Bluesky-centric ecosystem.

### 6.3 NIP Events (Nostr)

**Philosophy**: Radical simplicity. One data structure (the event) carries everything. The `kind` number determines interpretation. Tags provide structured metadata. Content is a string.

```json
{
  "kind": 1,
  "content": "Hello world",
  "tags": [["t", "greeting"]],
  "created_at": 1705312200,
  "pubkey": "abc123...",
  "id": "def456...",
  "sig": "789abc..."
}
```

**Strengths**: Trivial to implement; zero schema overhead; any relay can store any event without understanding it; maximum flexibility.
**Weaknesses**: No schema validation; semantic overloading of `content` field; tag conventions are fragile; clients must understand every `kind` they want to render.

### 6.4 Matrix Events

**Philosophy**: Extensible typed events in a DAG. Events have a `type` field (Java package convention), a `content` object, and DAG metadata (auth chain, depth, hashes). State events additionally have a `state_key`.

```json
{
  "type": "m.room.message",
  "content": {
    "msgtype": "m.text",
    "body": "Hello world"
  },
  "sender": "@alice:matrix.org",
  "room_id": "!abc:matrix.org",
  "event_id": "$xyz",
  "origin_server_ts": 1705312200000
}
```

**Strengths**: Rich event metadata; built-in DAG ordering; extensible without protocol changes; excellent for conversation-structured data.
**Weaknesses**: Heavy per-event overhead; DAG complexity; state resolution is non-trivial; event accumulation is storage-intensive.

---

## 7. Implementation Complexity

### 7.1 Effort to Implement a Minimal Server/Relay

| Protocol | Minimal Implementation | Dependencies | Estimated LOC | Learning Curve |
|----------|----------------------|-------------|---------------|----------------|
| **ActivityPub** (S2S only) | HTTP server + JSON-LD + HTTP Signatures + WebFinger | Crypto library (RSA), HTTP client, JSON-LD parser (optional) | ~2,000-5,000 | Medium: HTTP Signatures are tricky; JSON-LD edge cases; interop testing against Mastodon is essential |
| **AT Protocol** (PDS) | XRPC HTTP server + CBOR + MST + DID resolution + repo signing | CBOR library, secp256k1/Ed25519 crypto, MST implementation | ~10,000-20,000 | High: MST implementation is non-trivial; CBOR/CID handling; Lexicon validation; DID PLC integration |
| **Nostr** (Relay) | WebSocket server + JSON + event signature verification | secp256k1 Schnorr signatures, WebSocket library, database | ~500-2,000 | Low: The entire spec fits in one page; basic relay implementations exist in ~500 lines |
| **Matrix** (Homeserver) | HTTPS server + event DAG + state resolution + federation auth + sync API | TLS, JSON, canonical JSON, Ed25519, extensive room version logic | ~50,000-200,000 | Very High: State resolution alone is a research problem; federation auth; sync API; room versions |

### 7.2 Existing Implementation Sizes

| Implementation | Language | Approximate Size | Notes |
|---------------|----------|-----------------|-------|
| **Mastodon** | Ruby + React | ~150,000 LOC | Full social network; far exceeds ActivityPub minimum |
| **Pleroma** | Elixir | ~50,000 LOC | Lighter ActivityPub implementation; ~685MB RAM |
| **Misskey** | TypeScript | ~80,000 LOC | Feature-rich; ~848MB RAM |
| **Bluesky PDS** | TypeScript | ~30,000 LOC | Reference PDS implementation |
| **arroba** (PDS) | Python | ~5,000 LOC | Minimal Python AT Protocol implementation |
| **nostr-rs-relay** | Rust | ~5,000 LOC | Full-featured Nostr relay |
| **Synapse** (Matrix) | Python | ~300,000 LOC | Reference Matrix homeserver |
| **Conduit** (Matrix) | Rust | ~30,000 LOC | Lightweight Matrix homeserver |

### 7.3 Developer Experience Assessment

**ActivityPub**: The biggest challenge is not the spec itself but achieving **interoperability with existing implementations**. Mastodon's interpretation of ActivityPub has become the de facto standard, and its deviations from the spec (e.g., requiring specific HTTP Signature formats, specific JSON-LD contexts, treating `Note` as the primary content type) must be matched. The [guide for new implementers](https://socialhub.activitypub.rocks/t/guide-for-new-activitypub-implementers/479) and Mastodon's [ActivityPub documentation](https://docs.joinmastodon.org/spec/activitypub/) are essential reading.

**AT Protocol**: Well-documented with official specs at [atproto.com](https://atproto.com/specs/atp). The Lexicon system provides clear contracts. However, the number of moving parts (PDS, DID, CBOR, MST, XRPC) creates a steep initial learning curve. The [atproto Python SDK](https://atproto.blue/) and TypeScript SDK lower the barrier significantly.

**Nostr**: Lowest barrier to entry by far. A developer can build a working relay in an afternoon. The challenge shifts to building a good client (which must handle relay discovery, event ordering, profile resolution, and the growing NIP ecosystem).

**Matrix**: The highest barrier. Even the "simple" client-server API spans hundreds of pages. Building a homeserver that correctly federates requires implementing state resolution, which is a distributed systems research problem. Most teams should use existing homeservers (Synapse, Dendrite, Conduit) rather than building from scratch.

---

## 8. Security Considerations

### 8.1 Spam Prevention

| Protocol | Spam Defense Mechanisms |
|----------|----------------------|
| **ActivityPub** | Instance-level blocklists and allowlists; shared community blocklists (e.g., [Gardenfence](https://github.com/gardenfence/blocklist)); account approval on registration; rate limiting; "Limited Federation Mode" (allowlist-only). Reactive by nature -- admins scramble to block bad instances after incidents. [^fediblocklist] |
| **AT Protocol** | Labelers flag spam content; App Views can filter based on labels; PDS-level rate limiting; account creation requires invite codes or phone verification. The stackable labeler model allows third-party spam detection services. [^bskymod] |
| **Nostr** | Relay-level filtering (operators choose what to store); paid relays (requiring Lightning payment to publish); NIP-57 zaps as proof-of-payment; reputation systems built on follow graphs; client-side filtering. No protocol-level spam prevention. |
| **Matrix** | Room-level power levels (who can send messages); room moderators; moderation bots (e.g., Mjolnir); server-level rate limiting; room join restrictions (invite-only, knock-to-join). |

### 8.2 Content Moderation

**ActivityPub's moderation weakness**: Moderation is entirely server-level. If your admin does not block a harmful instance, you receive its content. There is no user-level moderation infrastructure beyond personal mute/block. Community blocklists help but require manual curation and adoption. [^fediblocklist]

**AT Protocol's moderation innovation**: The labeler architecture separates moderation from infrastructure. Users subscribe to labelers (e.g., Bluesky's default moderation service, community-run labelers, specialized anti-spam services) and configure how labeled content appears (hide, warn, blur). This is the most architecturally sophisticated moderation system among the four protocols. [^bskylabels]

**Nostr's moderation philosophy**: Moderation is emergent, not structural. Relay operators choose what to host. Clients choose what to display. No protocol-level concept of "banned content." This is both a feature (censorship resistance) and a liability (harmful content persists across relays).

**Matrix's moderation tooling**: Power levels within rooms provide fine-grained control (who can send, who can kick, who can change settings). The Mjolnir bot and Draupnir provide automated moderation. Server admins can defederate from problematic servers. Room version upgrades can reset compromised state.

### 8.3 Key Management and Recovery

| Protocol | Key Management | Recovery Options |
|----------|---------------|-----------------|
| **ActivityPub** | Server-managed RSA keys per actor | Password reset via server admin; keys are not user-facing |
| **AT Protocol** | DID PLC rotation keys + PDS signing keys | PDS holds rotation key (can update DID); user can hold their own rotation key for self-sovereign recovery; DID Web: user manages key directly [^atpidentity] |
| **Nostr** | User manages secp256k1 private key directly | **None**. Lost key = lost identity. NIP-46 (Nostr Connect) allows delegated signing to reduce exposure. Hardware key support is nascent. |
| **Matrix** | Per-device Ed25519 + Curve25519 keys; cross-signing keys | Security key backup; SSSS (Secure Secret Storage and Sharing); cross-signing verification between devices. Most mature key management among the four. |

### 8.4 Attack Surfaces

**Replay attacks**: ActivityPub mitigates via the 30-second signature window. AT Protocol's signed commits with monotonically increasing revision numbers prevent replay. Nostr events have unique IDs (content hashes) so duplicate events are idempotent. Matrix events are deduplicated by event ID in the DAG.

**DDoS of federation**: ActivityPub instances are vulnerable -- a malicious instance can flood another's inbox with activities. Rate limiting is implementation-specific, not protocol-mandated. AT Protocol's relay architecture provides a natural choke point (the relay can rate-limit PDS submissions). Nostr relays can independently rate-limit or require payment. Matrix homeservers face amplification risks in large rooms (every event must be sent to every participating server).

**Impersonation**: ActivityPub relies on server identity (if you control the server, you control all actor keys). AT Protocol's DID system provides cryptographic identity independent of the PDS. Nostr's identity is purely cryptographic (no server to compromise, but also no recovery). Matrix signs events with server keys, so server compromise enables impersonation.

**State manipulation (Matrix-specific)**: Malicious homeservers can attempt "state resets" by injecting carefully crafted events that exploit state resolution algorithm edge cases. Project Hydra is actively addressing this. [^hydra]

---

## 9. Scalability Analysis

### 9.1 ActivityPub Scalability

**Architecture**: Federated push-based. Each server independently manages its users' data and pushes activities to followers' servers.

**Scaling challenges**:
- **Fan-out problem**: A popular user with followers across 10,000 instances requires 10,000 HTTP requests per post. Mastodon uses a shared inbox optimization (one delivery per server), but this still scales linearly with unique server count.
- **Storage**: Each instance stores copies of all received activities. A large instance like `mastodon.social` stores the federated timeline of millions of users.
- **No global view**: There is no way to efficiently query "all posts mentioning X" across the entire network. Discovery is limited to what your instance has received.

**Practical limits**: The largest Mastodon instances (mastodon.social, mastodon.online) serve hundreds of thousands of users. The all-to-all federation model becomes increasingly expensive as instance count grows. Relay servers (like [relay.fedi.buzz](https://relay.fedi.buzz)) help with discovery but add bandwidth. [^parity]

### 9.2 AT Protocol Scalability

**Architecture**: Relay-aggregated. PDSes hold user data; relays crawl and aggregate into a firehose; App Views consume the firehose and build indexes.

**Current metrics**: The Bluesky relay sustains **2,000+ events/second** with hundreds of consumers, serving ~40M registered users. [^relayops]

**Scaling strategy**: [^relayops]
1. **Firehose sharding**: Partition by account DID (natural sharding key). Consumers subscribe to relevant shards.
2. **Fan-out servers (Rainbow)**: Re-broadcast the firehose to reduce relay bandwidth.
3. **Non-archival relays**: Drop the requirement for full history, making relay operation dramatically cheaper.
4. **Multiple independent relays**: The architecture supports multiple relay operators, though currently Bluesky operates the primary relay.

**Assessment**: The relay architecture provides a clear scaling path. The separation of PDS (user data) from App View (application logic) allows independent scaling of each tier. The primary risk is relay centralization -- currently, Bluesky's relay is the only production relay, making it a single point of failure for the network.

### 9.3 Nostr Scalability

**Architecture**: Client-relay pub/sub. No federation between relays. Each relay is independent.

**Academic analysis**: A 2025 empirical study found that Nostr achieves **superior decentralization** compared to the Fediverse, but relay availability remains a challenge -- financial sustainability (particularly for free relays) is a contributing factor. Post replication across relays enhances censorship resistance but introduces **significant overhead**. [^nostrempirical]

**Scaling characteristics**:
- **Horizontal**: Adding relays is trivial (no coordination required). Capacity scales with relay count.
- **Discovery**: Finding all of a user's events requires querying multiple relays (listed in NIP-65 relay metadata). No single relay has a global view.
- **Bandwidth**: Popular events are replicated across many relays, multiplying storage and bandwidth costs.
- **Relay economics**: Free relays struggle with sustainability. Paid relays (via Lightning) create a natural economic filter but fragment the network.

### 9.4 Matrix Scalability

**Architecture**: Full-mesh federation per room. Every homeserver in a room has a complete copy of the room's event DAG.

**Scaling challenges**:
- **Large rooms**: A room with participants from 1,000 homeservers requires each event to be sent to 999 other servers. The Matrix.org homeserver participates in the largest rooms and handles enormous fan-out.
- **State resolution**: CPU-intensive for rooms with complex DAGs and many state events. Hot rooms with rapid membership changes stress state resolution.
- **Sync API**: The original sync endpoint was notoriously slow for users in many rooms. Sliding Sync (MSC4186) addresses this by loading only visible rooms. [^slidingsync]
- **Database growth**: Event DAGs grow monotonically. State events accumulate. Media uploads compound storage requirements.

**Matrix 2.0 improvements**: Native Sliding Sync in Synapse 1.114+; Simplified Sliding Sync (MSC4186) for faster initial sync; ongoing state resolution improvements via Project Hydra. [^matrix2]

### 9.5 Scalability Summary

| Metric | ActivityPub | AT Protocol | Nostr | Matrix |
|--------|------------|-------------|-------|--------|
| **Bottleneck** | Fan-out to federated servers | Relay firehose bandwidth | Relay discovery + replication | Large room fan-out + state resolution |
| **Sharding** | Natural (per-instance) | DID-based firehose sharding | Natural (per-relay) | Per-room (but rooms can't be split) |
| **Caching** | Instance-level | App View level | Client-level | Homeserver-level |
| **Global query** | Not possible | Possible (via App View over firehose) | Not possible (relay-specific) | Not possible (room-specific) |
| **Theoretical max** | 10s of millions (federated) | 100s of millions (relay-aggregated) | Millions (relay-distributed) | 10s of millions (per-room constraints) |

---

## 10. Interoperability and Bridges

### 10.1 Bridgy Fed: ActivityPub <-> AT Protocol

[Bridgy Fed](https://fed.brid.gy/docs) is the most prominent bridge between decentralized protocols. It acts as a proxy that translates between ActivityPub and AT Protocol (and IndieWeb via webmentions). [^bridgyfed]

**How it works**: Bridgy Fed presents itself as an ActivityPub server to the Fediverse and as an AT Protocol identity to Bluesky. When a Mastodon user follows a Bluesky user via Bridgy Fed, the bridge:

1. Creates an ActivityPub actor representing the Bluesky user
2. Subscribes to the Bluesky user's repository updates via the firehose
3. Translates AT Protocol records into ActivityPub activities
4. Delivers activities to the Mastodon user's inbox

**Capabilities**: Profiles, posts, likes, reposts, mentions, follows -- all fully bidirectional. [^bridgyfed]

**Limitations**: Media handling, threading semantics, and content types do not always map cleanly between protocols. Moderation actions do not cross the bridge (a Mastodon block does not propagate to Bluesky). Currently handles approximately 100,000+ bridged accounts.

### 10.2 Mostr: Nostr <-> ActivityPub

[Mostr](https://gitlab.com/soapbox-pub/mostr) bridges Nostr and the Fediverse. It operates as: [^mostr]
- An **ActivityPub server** (receives activities, converts to Nostr events, publishes to relays)
- A **Nostr client** (subscribes to relay events, converts to ActivityPub activities, federates to Fediverse servers)

Mostr supports cross-protocol **Lightning Zaps** -- ActivityPub users can send zaps to Nostr users and vice versa. [^mostr]

**NIP-48 (Proxy Tags)** was developed specifically to support bridging: events that originate from another protocol include a tag linking to the original source, enabling clients to display proper attribution.

### 10.3 Matrix Bridges

Matrix has the most extensive bridge ecosystem, connecting to: IRC, Slack, Discord, Telegram, WhatsApp, Signal, and XMPP. These bridges operate as **application services** -- special Matrix users that puppet accounts from the bridged network.

Matrix bridges are fundamentally different from Bridgy Fed/Mostr: they bridge a **messaging protocol** to **messaging platforms**, not social protocols to social protocols. The semantics map much more cleanly (both sides have messages, rooms/channels, and user presence).

### 10.4 The Interoperability Landscape

```
                    Bridgy Fed
ActivityPub <========================> AT Protocol
     ^
     |  Mostr
     v
   Nostr

   Matrix  <--- bridges ---> IRC, Slack, Discord,
                              Telegram, Signal, XMPP
```

**The "protocol wars" reality**: Despite bridge efforts, the protocols are architecturally incompatible in important ways: [^interop]

1. **Identity**: ActivityPub identities are server-bound URLs. AT Protocol uses DIDs. Nostr uses raw keys. Bridges must maintain identity mapping tables.
2. **Content semantics**: A Bluesky post, a Mastodon toot, and a Nostr event have different threading models, character limits, and embedding capabilities. Translation is lossy.
3. **Moderation**: Each protocol's moderation model is fundamentally different. Cross-protocol moderation is unsolved.
4. **Encryption**: Matrix's E2E encryption cannot be bridged (by definition -- the bridge must decrypt and re-encrypt, breaking the trust model).

The practical outlook: bridges enable **read access** and **basic interaction** across protocols, but the experience is degraded compared to native usage. Users who care about features specific to one protocol will stay on that protocol.

---

## 11. Engineering Recommendations

### 11.1 Protocol Selection Guide

| If your goal is... | Choose | Why |
|--------------------|--------|-----|
| Social networking with existing Fediverse ecosystem | **ActivityPub** | Largest installed base; W3C standard; hundreds of compatible implementations |
| Social networking with data portability as a priority | **AT Protocol** | Cryptographic data ownership; account migration; growing rapidly |
| Maximum censorship resistance and simplicity | **Nostr** | No accounts, no servers with authority, no registration; trivial to implement |
| Secure messaging and real-time communication | **Matrix** | Best-in-class E2E encryption; rich messaging features; federation |
| Multi-protocol reach | **AT Protocol + ActivityPub bridge** | AT Protocol for primary; Bridgy Fed for Fediverse reach |

### 11.2 Implementation Priorities

**If building on ActivityPub:**
- Implement S2S only (ignore C2S)
- Test interoperability against Mastodon first, then Pleroma/Misskey
- Use HTTP Signatures draft-cavage-http-signatures-12 (Mastodon's version)
- Handle JSON-LD minimally (parse as plain JSON, include the standard context)
- Plan for the fan-out problem early (shared inbox, delivery queues, retry logic)

**If building on AT Protocol:**
- Start with the official TypeScript SDK or Python SDK (atproto.blue)
- Understand the PDS/Relay/App View separation -- decide which component you are building
- Lexicon schemas are non-negotiable; invest in understanding the type system
- The firehose is your primary data source for any aggregation or indexing service
- Plan for DID PLC dependency (currently single-operator at plc.directory)

**If building on Nostr:**
- Start with NIP-01 only; add NIPs incrementally based on your use case
- Implement relay discovery via NIP-65 early
- Handle relay unreliability gracefully (events may not reach all relays; query multiple)
- Consider NIP-57 (Lightning Zaps) for monetization or spam prevention
- The simplicity is deceptive: building a good Nostr client requires handling many edge cases

**If building on Matrix:**
- Use an existing homeserver (Synapse, Dendrite, or Conduit) unless you have very specific requirements
- Use a client SDK (matrix-js-sdk, matrix-rust-sdk, matrix-nio) rather than implementing the spec directly
- Understand room versions and state resolution -- bugs here cause data loss
- Plan for Sliding Sync support (MSC4186) for acceptable client performance
- E2E encryption is complex; use the SDK's crypto module rather than implementing Olm/Megolm yourself

### 11.3 Architectural Trade-off Summary

```
                     Simplicity
                         ^
                         |
                  Nostr  |
                    *    |
                         |
                         |
                         |
     ActivityPub *-------+-------* AT Protocol
                         |
                         |
                         |
                         |
                    *    |
                  Matrix |
                         v
                     Complexity
     <--- Decentralized    Aggregated --->
```

- **Nostr** maximizes simplicity and decentralization at the cost of discovery and consistency
- **ActivityPub** balances federation with practical social networking needs
- **AT Protocol** trades some simplicity for stronger data guarantees and global indexability
- **Matrix** accepts high complexity to deliver encrypted, real-time communication with strong consistency

Each protocol made rational trade-offs for its target use case. There is no universal winner -- the right choice depends on what you are building and what properties matter most to your users.

---

## References

[^apwiki]: [ActivityPub - Wikipedia](https://en.wikipedia.org/wiki/ActivityPub)
[^apw3c]: [ActivityPub - W3C Recommendation](https://www.w3.org/TR/activitypub/)
[^as2core]: [Activity Streams 2.0 - W3C](https://www.w3.org/TR/activitystreams-core/)
[^apwf]: [ActivityPub and WebFinger - W3C Community Report](https://www.w3.org/community/reports/socialcg/CG-FINAL-apwf-20240608/)
[^mastodonapspec]: [ActivityPub - Mastodon Documentation](https://docs.joinmastodon.org/spec/activitypub/)
[^c2sbate]: [ActivityPub Client API: A Way Forward - Steve Bate](https://www.stevebate.net/activitypub-client-api-a-way-forward/)
[^c2sblog]: [On the topic of ActivityPub: C2S](https://blog.nanoshinono.me/on-the-topic-of-activitypub-c2s-or-how-to-design-an-alright-protocol-and-have)
[^atpwiki]: [AT Protocol - Wikipedia](https://en.wikipedia.org/wiki/AT_Protocol)
[^atpbluesky]: [The AT Protocol - Bluesky Docs](https://docs.bsky.app/docs/advanced-guides/atproto)
[^atpidentity]: [Identity - AT Protocol](https://atproto.com/guides/identity)
[^atpmigration]: [Account Migration - AT Protocol](https://atproto.com/guides/account-migration)
[^atprepo]: [Repository - AT Protocol Specification](https://atproto.com/specs/repository)
[^mstrepo]: [Merkle Search Tree - GitHub (DavidBuchanan314)](https://github.com/DavidBuchanan314/merkle-search-tree)
[^lexicon]: [Lexicon - AT Protocol Specification](https://atproto.com/specs/lexicon)
[^nsid]: [Namespaced Identifiers (NSIDs) - AT Protocol](https://atproto.com/specs/nsid)
[^relayops]: [Relay Operational Updates - Bluesky Blog](https://docs.bsky.app/blog/relay-ops)
[^firehose]: [Firehose - Bluesky Docs](https://docs.bsky.app/docs/advanced-guides/firehose)
[^jetstream]: [Introducing Jetstream - Bluesky Blog](https://docs.bsky.app/blog/jetstream)
[^bskylabels]: [Labels - AT Protocol Specification](https://atproto.com/specs/label)
[^bskymod]: [Bluesky's Moderation Architecture - Bluesky Blog](https://docs.bsky.app/blog/blueskys-moderation-architecture)
[^nostrproto]: [The Nostr Protocol](https://nostr.how/en/the-protocol)
[^nostrtech]: [Nostr's Technical Architecture - Substack](https://onnostr.substack.com/p/nostrs-technical-architecture-the)
[^nip01]: [NIP-01 - Basic Protocol Flow](https://nips.nostr.com/1)
[^nips]: [NIPs - Nostr Implementation Possibilities](https://nips.nostr.com/)
[^nip57]: [NIP-57 - Lightning Zaps](https://nips.nostr.com/57)
[^matrixspec]: [Matrix Specification](https://spec.matrix.org/latest/)
[^matrixfed]: [Federation API - Matrix Specification](https://spec.matrix.org/legacy/server_server/r0.1.4.html)
[^matrixrooms]: [Rooms and Events - Matrix.org](https://matrix.org/docs/matrix-concepts/rooms_and_events/)
[^matrixevents]: [Enter the Matrix - Brendan Abolivier](https://brendan.abolivier.bzh/enter-the-matrix/)
[^stateres]: [State Resolution v2 for the Hopelessly Unmathematical - Matrix.org](https://matrix.org/docs/older/stateres-v2/)
[^stateresv2]: [Room Version 2 - Matrix Specification](https://spec.matrix.org/unstable/rooms/v2/)
[^hydra]: [Project Hydra: Improving State Resolution - Matrix.org Blog](https://matrix.org/blog/2025/08/project-hydra-improving-state-res/)
[^olmmegolm]: [Olm and Megolm - Matrix Specification](https://spec.matrix.org/v1.17/olm-megolm/)
[^slidingsync]: [Sunsetting the Sliding Sync Proxy - Matrix.org Blog](https://matrix.org/blog/2024/11/14/moving-to-native-sliding-sync/)
[^matrix2]: [Matrix 2.0 Is Here - Matrix.org Blog](https://matrix.org/blog/2024/10/29/matrix-2.0-is-here/)
[^bridgyfed]: [Bridgy Fed Documentation](https://fed.brid.gy/docs)
[^mostr]: [Introducing Mostr: a Fediverse Nostr Bridge - Soapbox Blog](https://soapbox.pub/blog/mostr-fediverse-nostr-bridge/)
[^interop]: [But First, Interoperability - Augment.ink](https://www.augment.ink/but-first-interoperability/)
[^nostrempirical]: [An Empirical Analysis of the Nostr Social Network - ACM](https://dl.acm.org/doi/10.1145/3768994)
[^fediblocklist]: [Gardenfence Blocklist - GitHub](https://github.com/gardenfence/blocklist)
[^parity]: [Mastodon Is Dead, Long Live Misskey - paritybit.ca](https://www.paritybit.ca/blog/mastodon-is-dead-long-live-misskey/)
[^sprout]: [Bluesky Growth Statistics - Sprout Social](https://sproutsocial.com/insights/bluesky-statistics/)
[^webpro]: [Mastodon Surges as Decentralized Alternative - WebProNews](https://www.webpronews.com/mastodon-surges-as-decentralized-alternative-to-x-doubles-users-by-2026/)
[^glukhov]: [Nostr Overview and Statistics - Glukhov.org](https://www.glukhov.org/post/2025/10/nostr-overview-and-statistics/)
[^sciencedirect]: [A Comparative Study of Decentralized Social Protocol Architectures - ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2405896325031489)

---

*Document produced February 2025. Protocol specifications and ecosystem data evolve rapidly; verify against current specs before making architectural decisions.*
