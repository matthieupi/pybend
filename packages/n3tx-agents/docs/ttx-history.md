# Canonical TTX agent history

## One storage and policy owner

Only `n3tx_threads.TTX` is registered. `n3tx_agents.history` owns
`HISTORY_CODEC = 'pydantic-ai/v1'`, agent-root policy and full SDK decoding.
`Thread`, `TXRecord`, their modules and `NotesMixin` are retired without aliases.
The separate `n3tx_threads.Thread` remains User-chat content, not agent storage.

Trusted server creation marks an agent root with `meta.agent_history=True` and
an explicitly present `data.scope`, containing a canonical local Ref or None.
`user_owner` is caller attribution; source is the active TTX, else `users/id`,
else Matrix for genuinely internal calls. Target is the actual executing actor.
No Account or fake business scope is synthesized.

```python
owner = Agent.create_history(target, user=caller, scope=None)
owner = Agent.get_history(ttx_ref, user=caller, action='read')
owner = Agent.authorize_history(owner, user=caller, action='update')
```

Every policy call freshly reloads the root and checks its declaration/scope
presence before applying native `OWNER | ROLE('admin')`. None callers retain
trusted native semantics. Generic TTX policy and owner-only User DM privacy are
unchanged. Generic mutation must not change the declaration, owner or binding.

History policy never depends on business-row existence or business update
permission. Execution independently requires callee AGENTIC admission and fresh
application guards. A non-null supplied scope asserts exact equality, never
rebinding. An application requiring explicit null equality compares
`owner.data['scope']` itself. Scope is never inferred from routing.

## Native execution

```python
owner = Agent.create_history(target, user=caller, scope=scope)
call = target.run_config(
    'Summarize', user=caller, scope=scope, llm='test', tools=[],
    constraints={'tool_retries': 0, 'output_retries': 0},
)
result = await Agent.invoke(target, call, ttx=owner)
assert result['ttx_ref']
```

This fragment assumes registered disposable storage and an initialized Matrix.
The callee must deliberately declare an AGENTIC AccessRule. Importing the mixin
or configuring a stored agent does not grant execution.

`agentic(..., ttx=None)` creates a new authorized root; a supplied TTX resumes
that exact owner. Both route through Matrix. The handler calls guarded
`target.run`, not recursive `target.agentic`, preserving application save logic.
`Agent.invoke` carries the backend-selected CallConfig in task-local Python state
and checks target, caller, task and scope agreement at the handler. Provider,
tools, output type and retry controls never enter command data or metadata.
Raw native commands resolve model-owned policy and ignore a body `user`.

Preparation requires `ttx`; AgentDeps and PreparedCall require it too. Results
contain `ttx_ref`, never numeric history identifiers or JSON-string wrappers.
Trusted `prepare/run` remains an internal engine seam, not an ingress grant.

## SDK evidence and capture

Finalized messages are dumped with ModelMessagesTypeAdapter into full raw JSON
dictionaries, tagged with HISTORY_CODEC and attached to their owner. Decoding
selects direct incoming codec records in insertion-ID order, including archived
evidence. Non-codec operations are ignored; malformed codec content raises.
Provider context is repaired only in memory; stored evidence remains unchanged.
An uncertain append stops later checkpoint attempts without replay.

`ThreadedMixin` captures only explicitly declared root actions or nested
participating destinations. `current_execution: ContextVar[TTX | None]` scopes
native execution. Agent commands reuse their authorized root. Other operations
save fresh child frames sourced from the current TTX; replies attach RETURN
evidence. Agent RETURN records are saved after guarded run completes. SDK tools
use the active TTX as source through unchanged Matrix request/stream routing.
Authentication/schema operations and credential/runtime metadata are excluded.
No UUID deduplication or inferred historical ancestry is added.

Native streaming uses the same journal and Matrix path. Explicit early SDK
stream close remains unsupported; cancellation does not roll back tools.
Same-owner turn serialization and business/history atomicity remain caller-owned.

## Cutover boundary

This source does not read or convert old tables. The consuming application must
refuse unconverted storage before registration and perform its approved offline
conversion. No runtime import, numeric lookup or dual write is retained.

## Changelog

- 2026-11-11: Replace intermediate opt-in behavior with one canonical policy,
  TTX-only SDK state, native Matrix invocation and execution-tree capture.
- 2026-11-11: Document the intermediate explicit TTX path and native example.
