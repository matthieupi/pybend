# 📋 Decentralized Protocols for N3TX: Executive Summary

> *Full analysis: [decentralized-protocols-analysis.md](../research/decentralized-protocols/decentralized-protocols-analysis.md)*

---

**For:** CEO & Engineering Team
**Date:** February 2026
**Read time:** 10 minutes

---

## 🎯 The Question

Should N3TX add support for decentralized social protocols -- ActivityPub (the W3C standard powering Mastodon and the Fediverse), ATProtocol (powering Bluesky), or others -- and if so, which protocols, when, and how?

**The short answer:** Yes, starting with ActivityPub, using a phased approach that begins with publish-only federation and expands based on demand. The investment is modest (6-10 weeks for ActivityPub), the architectural fit is natural, and the competitive position it creates -- the only framework where a model definition produces federated endpoints -- is genuinely unique.

---

## 📊 Key Findings at a Glance

| Finding | Detail |
|---------|--------|
| **N3TX is 60-70% ready** | Our schema-driven architecture (JSON Schema, self-describing instances, auto-generated routes, ABAC rules) maps directly to what federation protocols need. The gap is protocol-specific plumbing, not architectural rework. |
| **No one else does this** | No existing framework offers model-driven federation. Every federated app today is either purpose-built (Mastodon, Lemmy) or assembled from low-level libraries. `__federated__ = True` producing federation endpoints is a first. |
| **ActivityPub first, ATProtocol second** | AP has W3C backing, regulatory alignment, lower cost. AT has better DX and schema fit. An abstraction layer lets us support both. |
| **The regulatory window is real** | EU DMA review (May 2026) may mandate social network interoperability. eIDAS 2.0 mandates digital identity wallets by November 2026. Building now means leading, not scrambling. |
| **DIDs + portability are the "why now"** | Decentralized Identifiers and account portability break platform lock-in. This is not theoretical: Bluesky's 40M users can migrate between providers today. |

---

## 🏢 What the Industry Tells Us

The decentralized protocol space has reached an inflection point. The numbers:

- **Bluesky**: 40.2 million registered users (up from 3M in Feb 2024). 3.5M daily active.
- **Fediverse** (ActivityPub): 12 million registered users. ~1.2M monthly active.
- **Matrix**: 25+ government deployments (Germany, France, Ukraine, Netherlands, EU Commission).
- **Enterprise adoption**: Ghost, WordPress, Flipboard, and Medium all shipping ActivityPub in production.

The publishing layer is federating whether social networks do or not. Ghost 6.0 and WordPress's ActivityPub plugin mean blog posts are now first-class fediverse content. For a framework that powers content-driven applications, this is the most directly relevant signal.

> **Regulatory catalyst**: The EU DMA review in May 2026 is assessing whether to extend interoperability mandates to social networks. If enacted, platforms like Instagram and TikTok could be required to support cross-platform social interactions -- likely via ActivityPub. Teams that architect for this now avoid expensive retrofits.

Sources: [FediDB](https://fedidb.org/), [Backlinko](https://backlinko.com/bluesky-statistics), [TechCrunch](https://techcrunch.com/2025/08/05/substack-rival-ghost-connects-to-the-open-social-web-with-its-latest-public-release/), [DMA Portal](https://digital-markets-act.ec.europa.eu/index_en)

---

## 🔍 Where We Stand Today

### What We Already Have

N3TX's architecture is not just compatible with federation -- it is **convergent** with it:

| N3TX Concept | What Federation Needs | Gap |
|---------------|----------------------|-----|
| `ProtoModel.schema()` produces JSON Schema | ActivityPub needs JSON-LD types; ATProto needs Lexicon schemas | Small -- translation layer, not rewrite |
| `model_dump(response=True)` injects `$schema` + `$id` | Both protocols require self-describing, self-addressed objects | Already there -- rename `$id` to `id` |
| `register_routes()` auto-generates CRUD endpoints | Federation needs inbox/outbox/actor endpoints | Additive -- new routes alongside existing |
| ABAC rules (`ANYONE`, `OWNER`, `ROLE`) compose with `\|`, `&` | Federation needs visibility rules (public, followers, local) | Natural extension -- add `FEDERATED`, `LOCAL`, `FOLLOWER` rules |
| `BaseUser` + JWT auth | Federation needs actor identity + HTTP Signatures or DIDs | Medium -- new identity layer alongside existing auth |

### What We Need to Build

| Component | Effort | Protocol |
|-----------|--------|----------|
| WebFinger discovery endpoint | Medium | ActivityPub |
| HTTP Signature middleware | High | ActivityPub |
| ActivityStreams serializer | Low | ActivityPub |
| Actor / inbox / outbox endpoints | Medium | ActivityPub |
| Async delivery queue | Medium | ActivityPub |
| Lexicon generator from JSON Schema | Low | ATProtocol |
| DID support | High | ATProtocol |
| Merkle Search Tree storage | High | ATProtocol |

The structural parallels mean that most work is protocol-specific serialization and crypto, not architectural change.

---

## 📊 The Numbers

### Implementation Cost

| Scope | Weeks | Engineers |
|-------|-------|----------|
| ActivityPub only (publish + receive) | **6-10** | 2-3 |
| Both protocols (with shared abstraction) | **14-20** | 2-3 |

### Monthly Infrastructure

| Scale | ActivityPub | ATProtocol PDS | Both |
|-------|-------------|----------------|------|
| Small (<500 users) | $25-72/mo | $6-10/mo | $31-78/mo |
| Medium (500-5K users) | $104-280/mo | $20-50/mo | $124-330/mo |

### Market Context

| Metric | Value |
|--------|-------|
| Decentralized social media market | $2.38B (2024) -> $6.41B (2029), 21.9% CAGR |
| Decentralized identity market | $2.56B (2025) -> $4.6B (2026), 80% CAGR |
| Enterprise VC adoption (projected 2026) | 60%+ |

Sources: [Research and Markets](https://www.researchandmarkets.com/reports/6215126/blockchain-based-decentralized-social-media), [GM Insights](https://www.gminsights.com/industry-analysis/decentralized-identity-market)

---

## 💡 The Recommendation

### Strategy: Phased, Protocol-Abstracted, Opt-In

```
Phase 0 (Weeks 1-2)     Foundation
                         Define FederationAdapter abstraction
                         Add __federated__ to ProtoModel
                         No protocol commitment yet
                              |
Phase 1 (Weeks 3-6)     ActivityPub Publish-Only
                         WebFinger + Actor + Outbox
                         N3TX content appears on Fediverse
                         Other servers can follow N3TX users
                              |
Phase 2 (Weeks 7-10)    Full ActivityPub
                         Inbox + delivery queue + followers
                         Bidirectional federation
                         Create/Update/Delete activities
                              |
Phase 3 (Weeks 11-20)   ATProtocol Support
                         Lexicon generation + DID + XRPC
                         Can parallel Phase 2
                              |
Phase 4 (Ongoing)        Multi-Protocol Configuration
                         create_app(federation={...})
                         Unified developer experience
```

### Why ActivityPub First

| Factor | ActivityPub | ATProtocol |
|--------|-------------|------------|
| Governance | W3C multi-stakeholder | Single company (Bluesky) |
| Regulatory alignment | Strongest DMA candidate | Growing (IETF draft) |
| Implementation cost | 6-10 weeks | 10-16 weeks |
| Spec stability | High (8 years) | Medium (pre-1.0) |

### Why Not Wait

1. **The DMA review is May 2026.** If social interoperability is mandated, being ready is a competitive advantage.
2. **Ghost and WordPress are federating now.** The publishing ecosystem is moving.
3. **The competitive gap is open.** No framework offers model-driven federation. First-mover advantage is real.
4. **The phased approach limits downside.** Phase 1 is 2-4 weeks. If adoption is low, stop there.

### The Unique Value Proposition

```python
# Before (today's world -- any framework):
# Step 1: Define your model
# Step 2: Write ActivityPub serializers manually
# Step 3: Implement inbox/outbox endpoints manually
# Step 4: Add HTTP Signature verification manually
# Step 5: Build delivery queue manually
# Step 6: Keep all of this in sync with model changes

# After (N3TX with federation):
class Post(ProtoModel):
    __tablename__ = 'posts'
    __storable__ = True
    __federated__ = True  # That is it.

    body: str
    user_owner: int
```

---

## ⚠️ Top 3 Risks

| # | Risk | Probability | Impact | Mitigation |
|---|------|------------|--------|-----------|
| 1 | **ATProtocol governance** -- Bluesky is a single company with no revenue model and $36M in VC funding. The protocol could change direction. | MEDIUM | CRITICAL | Start with ActivityPub (multi-stakeholder W3C). Add ATProto behind abstraction layer. Do not couple to AT-specific infrastructure. |
| 2 | **Scope creep** -- Federation work expands beyond planned phases, consuming engineering bandwidth. | HIGH | MEDIUM | Phase strictly. Each phase is independently deployable. Review gates between phases. Stop at Phase 1 if adoption does not justify continuing. |
| 3 | **Security surface expansion** -- Every federation endpoint is untrusted input from the open internet. | MEDIUM | CRITICAL | Treat federation boundary as security boundary. Rate limiting, signature verification, input validation are non-negotiable. Budget for security audit ($5-20K). |

---

## 🗺️ Next Steps

### Immediate (This Quarter)

1. **Validate the abstraction**: Design the `FederationAdapter` Protocol. Ensure it can accommodate both ActivityPub and ATProtocol without protocol-specific leakage.
2. **Prototype the mapping**: Build a standalone script that takes a `ProtoModel.schema()` output and produces a valid ActivityStreams object. Confirm the translation is mechanical, not creative.
3. **Evaluate libraries**: Test [Bovine](https://pypi.org/project/bovine/) (Python/ActivityPub) and [atproto](https://pypi.org/project/atproto/) (Python/ATProtocol) against our use cases.

### Near-Term (Q2 2026)

4. **Build Phase 0-1**: Federation primitives + ActivityPub publish-only. Target: a N3TX app whose content appears on Mastodon.
5. **Test interoperability**: Verify against Mastodon, Pleroma, and Ghost. Use [ActivityPub Fuzzer](https://activitypub.rocks/).

### Key Dates to Watch

| Date | Event | Why It Matters |
|------|-------|---------------|
| **May 2026** | EU DMA review | Could mandate social network interoperability |
| **Nov 2026** | eIDAS 2.0 wallets mandatory | Creates DID/VC infrastructure |
| **Q3 2026** | W3C updated ActivityPub specs | New features, backward-compatible |
| **Nov 2027** | eIDAS business acceptance deadline | Hard compliance constraint |

---

> **The bottom line**: N3TX's schema-driven architecture gives us a natural path to federation that no other framework has. The investment is modest, the timing is right, and the market position -- "define a model, get a federated app" -- is genuinely differentiated. Start with ActivityPub, phase carefully, and build behind an abstraction that lets us add ATProtocol when the governance risk settles.

---

*This summary synthesizes five research documents (4,700+ lines) into actionable findings. For technical depth, protocol comparisons, implementation code, and the full risk register, see the [complete analysis](../research/decentralized-protocols/decentralized-protocols-analysis.md).*
