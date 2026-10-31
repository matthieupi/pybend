# Thread and TXRecord

Thread is the owner-associated container for agent history. It no longer stores
`messages` or `agent_addr`; runtime `agent_addr` remains routing state, not a
Thread field or authorization input. `scope` is optional business metadata only.

## Snapshot history

TXRecord represents a copied native TX envelope, Thread membership and optional
predecessor, TX timestamp, and server `recorded_at`/`recorded_by` provenance.
Original TX source is envelope content, not caller identity; `recorded_by` is not
copied from the TX/body. `from_tx` uses the native TX type adapter and its
enabled object handling. This snapshot representation does not guarantee object
immutability or SQL-level mutation prevention.

`Thread.append` / `append_many` persist via ordinary native TXRecord creation;
they do not dispatch. Do not assume UUID deduplication, atomic batches, stale
history compare-and-swap, a validated predecessor graph, or database-level
immutability enforcement. Failures can leave partial or duplicate inserts.
Predecessor is optional metadata, not ordering.

`Thread.history()` converts protocol rows directly to Pydantic AI history using
the single `HISTORY_CODEC` constant in `thread.py`. The native agent serializes
only its new suffix through that same codec. Existing message/history bounds are
application behavior; no extra native PreparedCall bound is implied. The
application independently verifies saved history and retains its existing error
handling; this storage description does not promise persistence success.

`Thread.records(user, cursor, limit)` is the model-owned timestamp query. It
returns record metadata newest first; `cursor` is an ISO timestamp. History
conversion is oldest first. The query has no ID tie-breaker for equal timestamps,
so pagination/polling does not promise complete replay at a shared timestamp.
The application latest-update action returns the latest page (`data`,
`has_more`) from this query. This is not an event log cursor or a catch-up
guarantee.

## Authorization

Native Thread policy is create=authenticated and read/update/delete=OWNER,
including native administrator access. `scope` does not alter this policy. In
Colgen, the explicitly approved removal of its previous Thread-specific policy
override restores native Thread routes. Generic TXRecord CRUD remains denied.

Do not add scope inheritance, private scoped-history exceptions, root-marker
grants, projection authorization, TTL bindings, or extra Thread capability
wrappers. Activity filtering is presentation, not authorization. Notes uses
trusted `tx.meta.user` on the actual native route and named HTTP `user` injection;
its existing explicit action policy and parent read/update checks remain. No
separate Notes caller-binding capability is used.

## Status

Source cleanup is stable for read-only review; focused tests are being written.
Historical tests from earlier source/policy snapshots are not current acceptance.
Colgen's 017 readiness refusal is a separate source-cutover/data-disposition
gate, not a new Thread startup guard. No live database change, migration, or
cutover is claimed. Existing-data disposition remains unresolved.

Implementation references: [Thread](../src/n3tx_agents/thread.py) and
[TXRecord](../src/n3tx_agents/tx_record.py).
