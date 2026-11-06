# Thread and TXRecord

Current contract for the October 31 restored source (updated 2026-11-06).
`Thread` and `TXRecord` are distinct storable ActorModels in `n3tx_agents`, in
tables `threads` and `tx_records`; register both. This is not TTX and has no
TTX-compatible model/identity alias. `Thread` owns protected nullable
`user_owner` and `scope`; scope is business metadata, not parent authorization.
Native owner/admin policy applies to Thread. `TXRecord` declares deny-all CRUD;
use Thread operations for authorization. Trusted internal `user=None` calls
bypass Thread record policy and are not an HTTP caller identity.
Application parent/action checks are separate and do not grant access to the
Thread. `NotesMixin` checks the host model/action independently, then calls the
Thread operation; `scope` remains descriptive business metadata.

```python
record = thread.append(tx, user=caller)  # one record; TX timestamp retained
page = thread.records(user=caller, limit=20)
if page["has_more"]:
    older = thread.records(user=caller, cursor=page["cursor"], limit=20)
messages = thread.history(user=caller)  # codec-selected Pydantic AI history
```

Append copies TX envelope data under `data.payload`; it retains the original
numeric `TX.timestamp`. `Thread.append` assigns nullable `user_owner` from the
caller (`user["user_id"]`, or `None` for trusted internal calls). No separate
`recorded_at` or `recorded_by` fields exist. Timestamp orders history and latest
records. Native cursors are strings containing epoch timestamps; `""` starts a
page. There is no ISO cursor alias, ID tie-break, or exhaustive replay guarantee
across equal timestamps. `append_many` is not available: repeat `append`; provide
each predecessor explicitly when chaining is desired. Appends are independent,
not atomic as a batch. Predecessor is metadata, not validated ordering.

`NotesMixin` exposes a paged read projection with unchanged outer
`{data,cursor,has_more}` and rows `{id,kind,content,timestamp,user_owner}`.
The application retains its own parent authorization; Thread scope metadata does
not authorize a parent. Payload codecs and independent evidence verification
remain distinct from generic record paging. See source
[`thread.py`](../src/n3tx_agents/thread.py),
[`tx_record.py`](../src/n3tx_agents/tx_record.py), and
[`notes_mixin.py`](../src/n3tx_agents/notes_mixin.py).

## Changelog

- 2026-11-06: Document restored Thread/TXRecord and caller-attributed append;
  use TX timestamps for history/pages and remove the old TTX contract.
