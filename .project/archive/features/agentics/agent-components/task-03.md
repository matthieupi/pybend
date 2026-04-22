# Write unit tests for rich streaming events

**ID:** task-03 | **Wave:** 2 | **Depends on:** task-01

## Intent

The run_stream() rewrite introduces new event types (tool_call, tool_result, thinking) that need test coverage. Tests validate that the iter()-based streaming produces the correct event spectrum when tools are called, and that backward-compatible text/done events still work.

## Context

Agent tests live in packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py. Existing streaming tests (TestRunStreamEngine class, lines 521-596) verify text chunks and done/error chunks. New tests should be added to this class or a new class.

Key testing patterns:
- Use `from pydantic_ai.models.test import TestModel` for mock LLM
- `TestModel(call_tools=[])` for no tool calls (text-only response)
- `TestModel(call_tools=['tool_name'])` to trigger a specific tool call
- Agent models need `__agent__ = True` for mixin injection
- Tool models need `__storable__ = True` and registration with `register_model()`
- Use `tmp_path` fixture for file-based SQLite (not :memory: — create_table needs same connection)
- Markers: `pytestmark = pytest.mark.unit` at module level, `@pytest.mark.asyncio` per test
- Fixtures: `fresh_matrix` for isolated Matrix, `memory_storage` for in-memory SQLite

TestModel behavior with agent.iter(): it generates synthetic events — PartStartEvent with TextPart, then PartDeltaEvent with TextPartDelta tokens as individual words. When call_tools is specified, first iteration has ToolCallPart events, then after tool execution, second iteration has TextPart response.

## Instructions

Read `/workspace/packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py`.

Add the following new test class after the existing TestRunStreamEngine class (after line 596):

```python
class TestRunStreamTypedEvents:
    """Tests for rich typed events from run_stream() via agent.iter()."""

    @pytest.mark.asyncio
    async def test_text_chunks_backward_compat(self, fresh_matrix):
        """run_stream() still yields text chunks with name='text'."""
        from pydantic_ai.models.test import TestModel

        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='Test',
            prompt='Test prompt',
            tools=[],
            llm=TestModel(call_tools=[]),
        ):
            chunks.append(chunk)

        text_chunks = [c for c in chunks if c['name'] == 'text']
        assert len(text_chunks) > 0, f"No text chunks. Got: {[c['name'] for c in chunks]}"
        for tc in text_chunks:
            assert 'text' in tc['data']
            assert tc['meta']['stream'] is True
            assert 'seq' in tc['meta']

    @pytest.mark.asyncio
    async def test_tool_call_event(self, fresh_matrix, tmp_path):
        """run_stream() yields tool_call event when LLM calls a tool."""
        from pydantic_ai.models.test import TestModel

        file_storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Grant(ActorModel):
            __tablename__ = 'grants'
            __storable__ = True
            title: str = Field(default='')

        register_model(Grant, storage=file_storage)
        file_storage.create_table(Grant)

        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='List grants',
            prompt='List grants.',
            tools=['grants'],
            llm=TestModel(call_tools=['grants_list']),
        ):
            chunks.append(chunk)

        tool_calls = [c for c in chunks if c['name'] == 'tool_call']
        assert len(tool_calls) >= 1, f"No tool_call events. Got: {[c['name'] for c in chunks]}"
        tc = tool_calls[0]
        assert tc['data']['tool'] == 'grants_list'
        assert 'call_id' in tc['data']
        assert 'args' in tc['data']

    @pytest.mark.asyncio
    async def test_tool_result_event(self, fresh_matrix, tmp_path):
        """run_stream() yields tool_result event after tool execution."""
        from pydantic_ai.models.test import TestModel

        file_storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Grant(ActorModel):
            __tablename__ = 'grants'
            __storable__ = True
            title: str = Field(default='')

        register_model(Grant, storage=file_storage)
        file_storage.create_table(Grant)

        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='List grants',
            prompt='List grants.',
            tools=['grants'],
            llm=TestModel(call_tools=['grants_list']),
        ):
            chunks.append(chunk)

        tool_results = [c for c in chunks if c['name'] == 'tool_result']
        assert len(tool_results) >= 1, f"No tool_result events. Got: {[c['name'] for c in chunks]}"
        tr = tool_results[0]
        assert tr['data']['tool'] == 'grants_list'
        assert 'result' in tr['data']
        assert 'call_id' in tr['data']

    @pytest.mark.asyncio
    async def test_done_chunk_has_tool_calls_count(self, fresh_matrix, tmp_path):
        """Done chunk includes tool_calls count."""
        from pydantic_ai.models.test import TestModel

        file_storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Grant(ActorModel):
            __tablename__ = 'grants'
            __storable__ = True
            title: str = Field(default='')

        register_model(Grant, storage=file_storage)
        file_storage.create_table(Grant)

        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='List grants',
            prompt='List grants.',
            tools=['grants'],
            llm=TestModel(call_tools=['grants_list']),
        ):
            chunks.append(chunk)

        done_chunks = [c for c in chunks if c['name'] == 'done']
        assert len(done_chunks) == 1
        assert done_chunks[0]['data']['tool_calls'] >= 1

    @pytest.mark.asyncio
    async def test_seq_monotonically_increasing(self, fresh_matrix):
        """All chunk seq numbers are monotonically increasing."""
        from pydantic_ai.models.test import TestModel

        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='Test',
            prompt='Test',
            tools=[],
            llm=TestModel(call_tools=[]),
        ):
            chunks.append(chunk)

        seqs = [c['meta']['seq'] for c in chunks if 'seq' in c.get('meta', {})]
        for i in range(1, len(seqs)):
            assert seqs[i] > seqs[i-1], f"seq not monotonic: {seqs}"

    @pytest.mark.asyncio
    async def test_event_ordering_tool_call_before_result(self, fresh_matrix, tmp_path):
        """tool_call events appear before their matching tool_result."""
        from pydantic_ai.models.test import TestModel

        file_storage = SQLiteStorage(str(tmp_path / 'test.db'))

        class Grant(ActorModel):
            __tablename__ = 'grants'
            __storable__ = True
            title: str = Field(default='')

        register_model(Grant, storage=file_storage)
        file_storage.create_table(Grant)

        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='List grants',
            prompt='List grants.',
            tools=['grants'],
            llm=TestModel(call_tools=['grants_list']),
        ):
            chunks.append(chunk)

        names = [c['name'] for c in chunks]
        if 'tool_call' in names and 'tool_result' in names:
            first_call = names.index('tool_call')
            first_result = names.index('tool_result')
            assert first_call < first_result, f"tool_call at {first_call} but tool_result at {first_result}"

    @pytest.mark.asyncio
    async def test_done_always_last(self, fresh_matrix):
        """Done chunk is always the last chunk emitted."""
        from pydantic_ai.models.test import TestModel

        class Scanner(ActorModel):
            __tablename__ = 'scanners'
            __storable__ = False
            __agent__ = True

        scanner = Scanner(addr='scanners/1')
        chunks = []
        async for chunk in scanner.run_stream(
            task='Test',
            prompt='Test',
            tools=[],
            llm=TestModel(call_tools=[]),
        ):
            chunks.append(chunk)

        assert chunks[-1]['name'] == 'done'
        assert chunks[-1]['meta']['stream_end'] is True
```

## Conventions

Test naming: test_{feature}_{scenario}. Class grouping: TestFeatureName. Marker: pytestmark = pytest.mark.unit at module level. Use @pytest.mark.asyncio for async tests. Use tmp_path fixture for file-based SQLite in tests that need real DB operations. Fixtures: fresh_matrix for isolated Matrix.

## Files

**Read:** - /workspace/packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py
- /workspace/packages/n3tx-agents/src/n3tx_agents/tests/conftest.py

**Modify:** - /workspace/packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py

**Create:** none

## Verification

**Commands:**
- `cd /workspace && python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py::TestRunStreamTypedEvents -v --tb=short -x`
- `cd /workspace && python3 -m pytest packages/n3tx-agents/src/n3tx_agents/tests/test_mixin.py -v --tb=short`

**Checks:**
- All new typed event tests pass
- All existing streaming tests still pass
- No regressions in other mixin tests
