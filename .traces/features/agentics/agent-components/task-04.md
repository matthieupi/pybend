# Write unit tests for AgentActor agentic_stream()

**ID:** task-04 | **Wave:** 2 | **Depends on:** task-02

## Intent

The new agentic_stream() override on AgentActor needs test coverage to verify it resolves tools from DB, delegates to run_stream(), and yields typed events correctly. These tests complement the grants example integration tests by testing the unit in isolation.

## Context

Agent actor tests live in packages/n3tx-agents/src/n3tx_agents/tests/test_agent_actor.py. The test pattern follows the existing agentic() tests in the grants example: create an AgentActor instance with 'test' LLM, seed tool records via join table, then call the method.

Key testing patterns:
- AgentActor needs registration with storage and join model generation
- Tool records are created via the join table class (AgentActorAgentTool)
- Use `from pydantic_ai.models.test import TestModel` with `call_tools=['tool_name']`
- AgentActor's agentic_stream() returns an async generator of TX-aligned chunks
- The method uses `self._resolve_tool_addrs()` to get tool addresses from DB

## Instructions

Read `/workspace/packages/n3tx-agents/src/n3tx_agents/tests/test_agent_actor.py`.

Add a new test class for agentic_stream(). The exact insertion point depends on what's already in the file — add after any existing test classes:

```python
class TestAgentActorStream:
    """Tests for AgentActor.agentic_stream() — streaming with DB tool resolution."""

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self, fresh_matrix, tmp_path):
        """agentic_stream() yields TX-aligned chunks."""
        from pydantic_ai.models.test import TestModel
        from n3tx_agents.actor import AgentActor
        from n3tx_agents.tool_model import AgentTool
        from n3tx_core.models.proto_model import generate_join_model
        from n3tx_core.storage.sqlite_storage import SQLiteStorage
        from n3tx_core.utils.registrar import register_model

        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)
        join_cls = generate_join_model(AgentActor, AgentTool)
        register_model(join_cls, storage=storage)

        agent = AgentActor(
            name='Test Streamer',
            prompt='You are a test agent.',
            llm='test',
        )
        created = AgentActor.create(agent)

        chunks = []
        async for chunk in created.agentic_stream(
            task='Hello',
            llm=TestModel(call_tools=[]),
        ):
            chunks.append(chunk)

        assert len(chunks) > 0
        names = [c['name'] for c in chunks]
        assert 'done' in names or 'text' in names

    @pytest.mark.asyncio
    async def test_stream_with_tool_resolution(self, fresh_matrix, tmp_path):
        """agentic_stream() resolves tools from DB and yields tool events."""
        from pydantic_ai.models.test import TestModel
        from pydantic import Field
        from n3tx_agents.actor import AgentActor
        from n3tx_agents.tool_model import AgentTool
        from n3tx_actors.models.actor_model import ActorModel
        from n3tx_core.models.proto_model import generate_join_model
        from n3tx_core.storage.sqlite_storage import SQLiteStorage
        from n3tx_core.utils.registrar import register_model

        storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Item(ActorModel):
            __tablename__ = 'items'
            __storable__ = True
            title: str = Field(default='')

        register_model(Item, storage=storage)
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)
        join_cls = generate_join_model(AgentActor, AgentTool)
        register_model(join_cls, storage=storage)

        agent = AgentActor(
            name='Tool Streamer',
            prompt='You list items.',
            llm='test',
        )
        created = AgentActor.create(agent)

        # Add tool record
        tool_record = join_cls(target='items', description='Item CRUD', agentactor_id=created.id)
        join_cls.create(tool_record)

        # Reload to get tool hrefs
        agent = AgentActor.get(created.id)

        chunks = []
        async for chunk in agent.agentic_stream(
            task='List items',
            llm=TestModel(call_tools=['items_list']),
        ):
            chunks.append(chunk)

        names = [c['name'] for c in chunks]
        assert 'tool_call' in names, f"No tool_call in: {names}"
        assert 'tool_result' in names, f"No tool_result in: {names}"
        assert 'done' in names

    @pytest.mark.asyncio
    async def test_stream_schema_has_method(self, fresh_matrix, tmp_path):
        """AgentActor schema includes agentic_stream in methods with stream=True."""
        from n3tx_agents.actor import AgentActor
        from n3tx_agents.tool_model import AgentTool
        from n3tx_core.storage.sqlite_storage import SQLiteStorage
        from n3tx_core.utils.registrar import register_model

        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(AgentTool, storage=storage)
        register_model(AgentActor, storage=storage)

        schema = AgentActor.schema()
        methods = schema.get('methods', {})
        assert 'agentic_stream' in methods, f"agentic_stream not in: {list(methods.keys())}"
        assert methods['agentic_stream'].get('stream') is True
```

Note: The exact imports and fixture usage may need adjustment based on what's already in test_agent_actor.py. The agent model tests typically need file-based storage (tmp_path) because create_table needs a persistent connection.

## Conventions

Test naming: test_{feature}_{scenario}. Use @pytest.mark.asyncio for async tests. Use tmp_path for file-based SQLite. Register models in test setup. Follow the same pattern as existing AgentActor tests in the file.

## Files

**Read:** - /workspace/packages/n3tx-agents/src/n3tx_agents/tests/test_agent_actor.py
- /workspace/packages/n3tx-agents/src/n3tx_agents/tests/conftest.py
- /workspace/packages/n3tx-agents/src/n3tx_agents/actor.py

**Modify:** - /workspace/packages/n3tx-agents/src/n3tx_agents/tests/test_agent_actor.py

**Create:** none

## Verification

**Commands:**
- `cd /workspace && python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_agent_actor.py -v --tb=short -x`

**Checks:**
- agentic_stream yields chunks
- agentic_stream resolves tools from DB
- AgentActor schema includes agentic_stream with stream=True
- All existing agent actor tests still pass
