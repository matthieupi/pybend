---
name: n3tx-agents
description: N3TX AgentActor, AgentMixin, tool discovery, persistent threads and streaming reasoning. Use when building LLM-powered model capabilities.
argument-hint: "<agent feature>"
---

# N3TX Agents

Read [agents](../../../docs/AGENTS.md), [stored agents](../../../packages/n3tx-agents/docs/agent-actor.md),
[mixin](../../../packages/n3tx-agents/docs/mixin.md) and
[tool discovery](../../../packages/n3tx-agents/docs/tool-discovery.md).

- Import n3tx_agents before defining `__agent__` models. Register models and
  storage; calls need the actor runtime and persistent Thread support.
- AgentActor is stored configuration. Its `tools` field is `list[AgentTool]`,
  not a plain address-array storage contract. AgentTool.target selects actors.
- Use `agentic`/`agentic_stream` for policy-driven calls. Lower-level `run` and
  `run_stream` require resolved runtime inputs; they are not interchangeable.
- AgentActor.agentic returns JSON text at the Python boundary. HTTP and actor
  response/parser behavior differ; follow the guide's verified limits rather
  than assuming a task-only request works identically on every transport.
- Threads are created when no thread ID is supplied. Verify ownership and
  concurrent-write behavior; there is no create_thread switch in CallConfig.
- Discovery is not permission enforcement. Verify raw-TX list filtering and
  caller injection separately. Do not let untrusted callers expand tool scope
  or scrape arbitrary destinations without policy.
- Stream event schemas describe vocabulary, not guaranteed validation or backend
  cancellation. NTTChat and NTTAgentLive extend NTTStreamAgent.

Use Pydantic AI TestModel and isolated file storage for provider-free tests.
The overview owns the complete example. Do not make paid calls or install missing
dependencies without authorization. Inspect source/tests and report limitations.
