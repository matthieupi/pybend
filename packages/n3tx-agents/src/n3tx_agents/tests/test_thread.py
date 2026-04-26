"""Tests for Thread — conversation history persistence via ActorModel CRUD."""

import pytest
from pydantic import Field

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.registrar import register_model
from n3tx_agents.thread import Thread

pytestmark = pytest.mark.unit


# ── Test models ──────────────────────────────────────────────────

class SimpleAgent(ActorModel):
    """Minimal agent model for thread integration tests."""
    __tablename__ = 'simple_agents'
    __storable__ = False
    __agent__ = True

    name: str = Field(default='Test Agent')


def _register_actor(cls):
    """Re-register a module-level ActorModel with the root Matrix.

    Needed because the autouse reset_actor_state fixture clears
    actor state between tests, but module-level classes (Thread,
    SimpleAgent) were registered at import time. Matrix routes via
    its instance-level _children, so we register there.
    """
    root = Actor.root()
    if root:
        root._children[cls.__addr__] = cls


# ── Thread Model Tests ───────────────────────────────────────────

class TestThreadModel:
    """Tests for Thread model definition and metadata."""

    def test_tablename(self, fresh_matrix):
        assert Thread.__tablename__ == 'threads'

    def test_is_actor_model(self, fresh_matrix):
        assert issubclass(Thread, ActorModel)

    def test_is_storable(self, fresh_matrix):
        assert getattr(Thread, '__storable__', False) is True

    def test_not_agent(self, fresh_matrix):
        assert not getattr(Thread, '__agent__', False)

    def test_fields(self, fresh_matrix):
        schema = Thread.model_json_schema()
        props = schema.get('properties', {})
        assert 'agent_addr' in props
        assert 'messages' in props
        assert 'user_owner' in props

    def test_access_rules(self, fresh_matrix):
        access = getattr(Thread, '__access__', {})
        assert 'read' in access
        assert 'create' in access
        assert 'update' in access
        assert 'delete' in access

    def test_protected_fields(self, fresh_matrix):
        assert 'user_owner' in getattr(Thread, '__protected_fields__', set())

    def test_default_values(self, fresh_matrix):
        t = Thread()
        assert t.agent_addr == ''
        assert t.messages == []
        assert t.user_owner is None


# ── Thread CRUD Tests ────────────────────────────────────────────

class TestThreadCRUD:
    """Tests for Thread persistence via standard ActorModel CRUD."""

    def test_create_and_get(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'threads.db'))
        register_model(Thread, storage=storage)
        storage.create_table(Thread)

        thread = Thread(agent_addr='agents/1', user_owner=1)
        created = Thread.create(thread)
        assert created.id is not None

        fetched = Thread.get(created.id)
        assert fetched is not None
        assert fetched.agent_addr == 'agents/1'
        assert fetched.messages == []
        assert fetched.user_owner == 1

    def test_update_messages(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'threads.db'))
        register_model(Thread, storage=storage)
        storage.create_table(Thread)

        thread = Thread.create(Thread(agent_addr='agents/1', user_owner=1))
        msg_data = [
            {'name': 'request', 'source': 'user', 'target': 'agents/1',
             'data': {'kind': 'request', 'parts': [{'part_kind': 'user-prompt', 'content': 'hi'}]},
             'meta': {}, 'timestamp': 1234567890.0},
        ]
        updated = Thread.update(thread.id, {'messages': msg_data})
        assert len(updated.messages) == 1
        assert updated.messages[0]['name'] == 'request'

    def test_messages_persist_as_json(self, fresh_matrix, tmp_path):
        """messages field round-trips through SQLite JSON serialization."""
        storage = SQLiteStorage(str(tmp_path / 'threads.db'))
        register_model(Thread, storage=storage)
        storage.create_table(Thread)

        msg_data = [
            {'name': 'request', 'source': 'user', 'target': 'agents/1',
             'data': {'kind': 'request', 'parts': [{'part_kind': 'user-prompt', 'content': 'hello'}]},
             'meta': {}, 'timestamp': 1000.0},
            {'name': 'response', 'source': 'agents/1', 'target': 'user',
             'data': {'kind': 'response', 'parts': [{'part_kind': 'text', 'content': 'hi there'}]},
             'meta': {}, 'timestamp': 1001.0},
        ]
        thread = Thread.create(Thread(agent_addr='agents/1', messages=msg_data, user_owner=1))

        fetched = Thread.get(thread.id)
        assert len(fetched.messages) == 2
        assert fetched.messages[0]['data']['parts'][0]['content'] == 'hello'
        assert fetched.messages[1]['data']['parts'][0]['content'] == 'hi there'

    def test_delete(self, fresh_matrix, tmp_path):
        storage = SQLiteStorage(str(tmp_path / 'threads.db'))
        register_model(Thread, storage=storage)
        storage.create_table(Thread)

        thread = Thread.create(Thread(agent_addr='agents/1', user_owner=1))
        Thread.delete(thread.id)
        assert Thread.get(thread.id) is None


# ── Conversion Utility Tests ─────────────────────────────────────

class TestConversionUtilities:
    """Tests for Thread.to_history() and Thread.from_history() static methods."""

    def test_to_history_empty(self):
        assert Thread.to_history([]) == []

    def test_from_history_empty(self):
        assert Thread.from_history([]) == []

    def test_round_trip_request(self):
        """Convert a user message TX → ModelMessage → TX and verify structure."""
        tx_msgs = [
            {'name': 'request', 'source': 'user', 'target': 'agents/1',
             'data': {
                 'kind': 'request',
                 'parts': [{'part_kind': 'user-prompt', 'content': 'hello'}],
             },
             'meta': {}, 'timestamp': 1000.0},
        ]
        # TX → ModelMessage
        history = Thread.to_history(tx_msgs)
        assert len(history) == 1

        # ModelMessage → TX
        back = Thread.from_history(history, source='user', target='agents/1')
        assert len(back) == 1
        assert back[0]['name'] == 'request'
        assert back[0]['source'] == 'user'
        assert back[0]['target'] == 'agents/1'
        assert back[0]['data']['kind'] == 'request'
        assert 'timestamp' in back[0]

    def test_round_trip_response(self):
        """Convert an assistant response TX → ModelMessage → TX."""
        tx_msgs = [
            {'name': 'response', 'source': 'agents/1', 'target': 'user',
             'data': {
                 'kind': 'response',
                 'parts': [{'part_kind': 'text', 'content': 'hi there'}],
                 'model_name': 'test',
                 'timestamp': '2026-01-01T00:00:00Z',
             },
             'meta': {}, 'timestamp': 1001.0},
        ]
        history = Thread.to_history(tx_msgs)
        assert len(history) == 1

        back = Thread.from_history(history, source='agents/1', target='user')
        assert len(back) == 1
        assert back[0]['name'] == 'response'
        assert back[0]['data']['kind'] == 'response'

    def test_round_trip_multi_turn(self):
        """Convert a multi-turn conversation and verify all messages survive."""
        tx_msgs = [
            {'name': 'request', 'source': 'user', 'target': 'agents/1',
             'data': {'kind': 'request', 'parts': [{'part_kind': 'user-prompt', 'content': 'q1'}]},
             'meta': {}, 'timestamp': 1000.0},
            {'name': 'response', 'source': 'agents/1', 'target': 'user',
             'data': {'kind': 'response', 'parts': [{'part_kind': 'text', 'content': 'a1'}],
                      'model_name': 'test', 'timestamp': '2026-01-01T00:00:00Z'},
             'meta': {}, 'timestamp': 1001.0},
            {'name': 'request', 'source': 'user', 'target': 'agents/1',
             'data': {'kind': 'request', 'parts': [{'part_kind': 'user-prompt', 'content': 'q2'}]},
             'meta': {}, 'timestamp': 1002.0},
        ]
        history = Thread.to_history(tx_msgs)
        assert len(history) == 3

        back = Thread.from_history(history)
        assert len(back) == 3

    def test_from_history_with_real_messages(self):
        """from_history works with actual pydantic-ai ModelMessage objects."""
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        msg = ModelRequest(parts=[UserPromptPart(content='test')])
        result = Thread.from_history([msg], source='user', target='agent')
        assert len(result) == 1
        assert result[0]['name'] == 'request'
        assert result[0]['data']['parts'][0]['content'] == 'test'


# ── Integration with run() ───────────────────────────────────────

class TestRunWithThread:
    """Tests for thread_id parameter in AgentMixin.run()."""

    @pytest.mark.asyncio
    async def test_thread_reads_and_updates(self, fresh_matrix, tmp_path):
        """run() with thread_id reads thread before, updates after."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(Thread, storage=storage)
        register_model(SimpleAgent, storage=storage)
        _register_actor(Thread)
        _register_actor(SimpleAgent)
        storage.create_table(Thread)

        # Create thread with empty history
        thread = Thread.create(Thread(agent_addr='simple_agents', user_owner=1))
        assert thread.messages == []

        agent = SimpleAgent(addr='simple_agents/1')
        result = await agent.run(
            task='Hello',
            prompt='You are helpful.',
            tools=[],
            llm=TestModel(call_tools=[]),
            thread_id=thread.id,
        )

        assert 'answer' in result
        assert result.get('thread_id') == thread.id

        # Thread should now have messages
        updated = Thread.get(thread.id)
        assert len(updated.messages) > 0

    @pytest.mark.asyncio
    async def test_thread_continues_conversation(self, fresh_matrix, tmp_path):
        """Second run with same thread_id grows the message history."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(Thread, storage=storage)
        register_model(SimpleAgent, storage=storage)
        _register_actor(Thread)
        _register_actor(SimpleAgent)
        storage.create_table(Thread)

        thread = Thread.create(Thread(agent_addr='simple_agents', user_owner=1))
        agent = SimpleAgent(addr='simple_agents/1')

        # First turn
        await agent.run(
            task='Question 1',
            prompt='You are helpful.',
            tools=[], llm=TestModel(call_tools=[]),
            thread_id=thread.id,
        )
        count_1 = len(Thread.get(thread.id).messages)

        # Second turn
        await agent.run(
            task='Question 2',
            prompt='You are helpful.',
            tools=[], llm=TestModel(call_tools=[]),
            thread_id=thread.id,
        )
        count_2 = len(Thread.get(thread.id).messages)

        assert count_2 > count_1

    @pytest.mark.asyncio
    async def test_invalid_thread_id_raises(self, fresh_matrix, tmp_path):
        """run() with non-existent thread_id raises RuntimeError."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(Thread, storage=storage)
        register_model(SimpleAgent, storage=storage)
        _register_actor(Thread)
        _register_actor(SimpleAgent)
        storage.create_table(Thread)

        agent = SimpleAgent(addr='simple_agents/1')
        with pytest.raises(RuntimeError, match="Thread.*not found"):
            await agent.run(
                task='Test', prompt='Test.', tools=[],
                llm=TestModel(call_tools=[]),
                thread_id=99999,
            )

    @pytest.mark.asyncio
    async def test_no_thread_id_no_thread(self, fresh_matrix, tmp_path):
        """run() without thread_id creates a new thread automatically."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(Thread, storage=storage)
        register_model(SimpleAgent, storage=storage)
        _register_actor(Thread)
        _register_actor(SimpleAgent)
        storage.create_table(Thread)

        agent = SimpleAgent(addr='simple_agents/1')
        result = await agent.run(
            task='Test',
            prompt='Test.',
            tools=[], llm=TestModel(call_tools=[]),
        )
        assert 'answer' in result
        assert result.get('thread_id') is not None

    @pytest.mark.asyncio
    async def test_run_without_thread_id_creates_and_returns_thread_id(self, fresh_matrix, tmp_path):
        """run() provisions a thread automatically when thread_id is absent."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(Thread, storage=storage)
        register_model(SimpleAgent, storage=storage)
        _register_actor(Thread)
        _register_actor(SimpleAgent)
        storage.create_table(Thread)

        agent = SimpleAgent(addr='simple_agents/1')
        result = await agent.run(
            task='Test',
            prompt='Test.',
            tools=[],
            llm=TestModel(call_tools=[]),
            user={'user_id': 1, 'role': 'user'},
        )

        assert 'thread_id' in result
        created = Thread.get(result['thread_id'])
        assert created.agent_addr == 'simple_agents/1'
        assert len(created.messages) > 0

    @pytest.mark.asyncio
    async def test_rejects_thread_from_other_agent(self, fresh_matrix, tmp_path):
        """run() rejects a thread that belongs to a different agent address."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(Thread, storage=storage)
        register_model(SimpleAgent, storage=storage)
        _register_actor(Thread)
        _register_actor(SimpleAgent)
        storage.create_table(Thread)

        thread = Thread.create(Thread(agent_addr='other_agents/1', user_owner=1))
        agent = SimpleAgent(addr='simple_agents/1')
        with pytest.raises(RuntimeError, match='belongs to'):
            await agent.run(
                task='Test',
                prompt='Test.',
                tools=[],
                llm=TestModel(call_tools=[]),
                thread_id=thread.id,
                user={'user_id': 1, 'role': 'user'},
            )


# ── Integration with agentic() ───────────────────────────────────

class TestAgenticWithThread:
    """Tests for thread_id pass-through in agentic()."""

    @pytest.mark.asyncio
    async def test_agentic_passes_thread_id(self, fresh_matrix, tmp_path):
        """agentic(thread_id=N) forwards to run() and updates thread."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(Thread, storage=storage)
        register_model(SimpleAgent, storage=storage)
        _register_actor(Thread)
        _register_actor(SimpleAgent)
        storage.create_table(Thread)

        thread = Thread.create(Thread(agent_addr='simple_agents', user_owner=1))
        result = await SimpleAgent.agentic(
            task='Hello',
            llm=TestModel(call_tools=[]),
            thread_id=thread.id,
        )
        assert 'answer' in result
        assert len(Thread.get(thread.id).messages) > 0


# ── Integration with run_stream() ────────────────────────────────

class TestRunStreamWithThread:
    """Tests for thread_id in streaming agent loop."""

    @pytest.mark.asyncio
    async def test_stream_updates_thread(self, fresh_matrix, tmp_path):
        """run_stream() with thread_id updates thread after stream completes."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(Thread, storage=storage)
        register_model(SimpleAgent, storage=storage)
        _register_actor(Thread)
        _register_actor(SimpleAgent)
        storage.create_table(Thread)

        thread = Thread.create(Thread(agent_addr='simple_agents', user_owner=1))
        agent = SimpleAgent(addr='simple_agents/1')

        chunks = []
        async for chunk in agent.run_stream(
            task='Hello',
            prompt='You are helpful.',
            tools=[], llm=TestModel(call_tools=[]),
            thread_id=thread.id,
        ):
            chunks.append(chunk)

        # Thread should have messages after stream completes
        updated = Thread.get(thread.id)
        assert len(updated.messages) > 0

        # Done chunk should include thread_id
        done_chunks = [c for c in chunks if c.get('name') == 'done']
        assert len(done_chunks) == 1
        assert done_chunks[0]['data'].get('thread_id') == thread.id

    @pytest.mark.asyncio
    async def test_stream_without_thread_id_returns_thread_id(self, fresh_matrix, tmp_path):
        """run_stream() provisions a thread automatically when thread_id is absent."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(Thread, storage=storage)
        register_model(SimpleAgent, storage=storage)
        _register_actor(Thread)
        _register_actor(SimpleAgent)
        storage.create_table(Thread)

        agent = SimpleAgent(addr='simple_agents/1')
        chunks = []
        async for chunk in agent.run_stream(
            task='Hello',
            prompt='You are helpful.',
            tools=[], llm=TestModel(call_tools=[]),
            user={'user_id': 1, 'role': 'user'},
        ):
            chunks.append(chunk)

        done_chunk = [c for c in chunks if c.get('name') == 'done'][0]
        thread_id = done_chunk['data'].get('thread_id')
        assert thread_id is not None
        updated = Thread.get(thread_id)
        assert updated.agent_addr == 'simple_agents/1'
        assert len(updated.messages) > 0

    @pytest.mark.asyncio
    async def test_second_stream_turn_reuses_created_thread(self, fresh_matrix, tmp_path):
        """A follow-up streamed turn can reuse the returned thread_id."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(Thread, storage=storage)
        register_model(SimpleAgent, storage=storage)
        _register_actor(Thread)
        _register_actor(SimpleAgent)
        storage.create_table(Thread)

        agent = SimpleAgent(addr='simple_agents/1')

        first_chunks = []
        async for chunk in agent.run_stream(
            task='Hello',
            prompt='You are helpful.',
            tools=[], llm=TestModel(call_tools=[]),
            user={'user_id': 1, 'role': 'user'},
        ):
            first_chunks.append(chunk)

        first_done = [c for c in first_chunks if c.get('name') == 'done'][0]
        thread_id = first_done['data'].get('thread_id')
        assert thread_id is not None

        second_chunks = []
        async for chunk in agent.run_stream(
            task='What did I just ask you?',
            prompt='You are helpful.',
            tools=[], llm=TestModel(call_tools=[]),
            thread_id=thread_id,
            user={'user_id': 1, 'role': 'user'},
        ):
            second_chunks.append(chunk)

        second_done = [c for c in second_chunks if c.get('name') == 'done'][0]
        assert second_done['data'].get('thread_id') == thread_id

        updated = Thread.get(thread_id)
        assert updated.agent_addr == 'simple_agents/1'
        assert len(updated.messages) >= 4

    @pytest.mark.asyncio
    async def test_reused_stream_thread_grows_history(self, fresh_matrix, tmp_path):
        """Reusing a streamed thread appends to the same persisted history."""
        from pydantic_ai.models.test import TestModel

        storage = SQLiteStorage(str(tmp_path / 'test.db'))
        register_model(Thread, storage=storage)
        register_model(SimpleAgent, storage=storage)
        _register_actor(Thread)
        _register_actor(SimpleAgent)
        storage.create_table(Thread)

        agent = SimpleAgent(addr='simple_agents/1')

        first_chunks = []
        async for chunk in agent.run_stream(
            task='Hello',
            prompt='You are helpful.',
            tools=[], llm=TestModel(call_tools=[]),
            user={'user_id': 1, 'role': 'user'},
        ):
            first_chunks.append(chunk)

        thread_id = [c for c in first_chunks if c.get('name') == 'done'][0]['data'].get('thread_id')
        before = Thread.get(thread_id)
        before_count = len(before.messages)

        async for _chunk in agent.run_stream(
            task='And again',
            prompt='You are helpful.',
            tools=[], llm=TestModel(call_tools=[]),
            thread_id=thread_id,
            user={'user_id': 1, 'role': 'user'},
        ):
            pass

        after = Thread.get(thread_id)
        assert len(after.messages) > before_count
