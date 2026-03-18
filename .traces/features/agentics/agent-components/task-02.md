# Add agentic_stream() override to AgentActor

**ID:** task-02 | **Wave:** 1 | **Depends on:** none

## Intent

AgentActor already overrides agentic() to resolve tools from DB fields instead of __agent__ config. The streaming variant (agentic_stream()) needs the same treatment — it should resolve tool addresses from the DB, then delegate to AgentMixin.run_stream() directly, bypassing the mixin's agentic_stream() config cascade.

## Context

AgentActor in packages/n3tx-agents/src/n3tx_agents/actor.py overrides agentic() at lines 103-135. It calls `AgentMixin.__dict__['run'].fn` directly to bypass the MRO. The same pattern is needed for agentic_stream() → run_stream().

The key difference from mixin's agentic_stream(): AgentActor resolves tool addresses from self._resolve_tool_addrs() (which reads from the DB join table) rather than from __agent__ config or tools() discovery.

The streaming override must be an async generator that yields chunks, unlike the non-streaming agentic() which returns a JSON string. It should use @expose_route with stream=True so the route layer generates an SSE endpoint.

Note: AgentActor's existing agentic() is decorated with @expose_route('/agentic', methods=['POST']) but NOT stream=True. The new agentic_stream() should use a separate route '/agentic_stream' with stream=True.

## Instructions

Read `/workspace/packages/n3tx-agents/src/n3tx_agents/actor.py`.

Step 1: Add the agentic_stream() method to AgentActor class, after the existing agentic() method (after line 135):

```python
    @expose_route('/agentic_stream', methods=['POST'], stream=True)
    async def agentic_stream(self, task: str, **kwargs):
        """Streaming agent execution — resolves tools from DB.

        Override — same as agentic() but yields TX-aligned stream chunks.
        Calls AgentMixin.run_stream() directly, bypassing the mixin's
        agentic_stream() config cascade since AgentActor has its own config.

        Args:
            task: The user task / query to execute.
            **kwargs: Override llm, constraints, user, thread_id, result_type.

        Yields:
            TX-aligned dicts: text, tool_call, tool_result, thinking, done, error.
        """
        from n3tx_agents.mixin import AgentMixin
        tool_addrs = self._resolve_tool_addrs()
        run_stream_fn = AgentMixin.__dict__['run_stream'].fn
        async for chunk in run_stream_fn(
            self,
            task=task,
            prompt=self.prompt,
            tools=tool_addrs,
            llm=kwargs.get('llm', self.llm),
            constraints={**self.constraints, **kwargs.get('constraints', {})},
            user=kwargs.get('user'),
            thread_id=kwargs.get('thread_id'),
            result_type=kwargs.get('result_type'),
        ):
            yield chunk
```

This follows the exact same pattern as the existing agentic() override:
- Resolves tools from DB via _resolve_tool_addrs()
- Calls AgentMixin engine directly via descriptor's .fn
- Merges constraints from self.constraints and kwargs
- Passes through llm, user, thread_id, result_type

## Conventions

Imports: use `from n3tx_agents.mixin import AgentMixin` inside the method to avoid circular imports (same as existing agentic() pattern). @expose_route requires stream=True for SSE endpoints. Method naming: agentic_stream matches the mixin's convention.

## Files

**Read:** - /workspace/packages/n3tx-agents/src/n3tx_agents/actor.py
- /workspace/packages/n3tx-agents/src/n3tx_agents/mixin.py

**Modify:** - /workspace/packages/n3tx-agents/src/n3tx_agents/actor.py

**Create:** none

## Verification

**Commands:**
- `cd /workspace && python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_agent_actor.py -v --tb=short -x`
- `cd /workspace && python3 -c "from n3tx_agents.actor import AgentActor; print('agentic_stream' in AgentActor.schema().get('methods', {}))"`

**Checks:**
- AgentActor has agentic_stream method
- AgentActor.schema() includes agentic_stream in methods with stream=True
- agentic_stream yields TX-aligned chunks
- agentic_stream resolves tools from DB (same as agentic)
