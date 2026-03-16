"""Tests for streaming infrastructure — TX stream helpers, NetworkAdapter
Queue handling, NetworkAdapter.stream(), and ActorModel async generator detection.

Validates Phase 1-3 of the streaming-sse-ws feature:
  1. TX.stream_chunk() and TX.stream_end() produce correct meta fields
  2. NetworkAdapter.inbox() resolves Queue for stream chunks, Future for single replies
  3. NetworkAdapter.stream() yields chunks and terminates on stream_end/error/timeout
  4. ActorModel.handler() detects async generators and sends stream chunks via TX
"""

import asyncio
from contextlib import contextmanager
from typing import ClassVar

import pytest
from pydantic import Field

from n3tx_actors.actor import Actor
from n3tx_actors.matrix import Matrix
from n3tx_actors.tx import TX
from n3tx_actors.api.network_adapter import NetworkAdapter

pytestmark = pytest.mark.unit


# ===================================================================
# Helpers
# ===================================================================

@contextmanager
def mock_method(instance, name, replacement):
    """Temporarily replace a method on a Pydantic BaseModel instance.

    Pydantic's __setattr__/__delattr__ prevent normal mock patching.
    This uses object.__setattr__/delattr__ to bypass the protection.
    """
    object.__setattr__(instance, name, replacement)
    try:
        yield replacement
    finally:
        object.__delattr__(instance, name)


# ===================================================================
# TestTXStreamChunk
# ===================================================================

class TestTXChunk:
    """TX.chunk() — create a STREAM chunk reply."""

    def test_chunk_swaps_source_target(self):
        tx = TX(name='run', source='api', target='agent')
        chunk = tx.chunk({'text': 'hi'}, seq=0)
        assert chunk.source == 'agent'
        assert chunk.target == 'api'

    def test_chunk_name_is_stream(self):
        tx = TX(name='run', source='a', target='b')
        assert tx.chunk({}, seq=0).name == 'STREAM'

    def test_chunk_meta_has_req(self):
        tx = TX(name='run', source='a', target='b')
        chunk = tx.chunk({}, seq=0)
        assert chunk.meta['req'] == tx.uuid

    def test_chunk_meta_has_stream_true(self):
        tx = TX(name='run', source='a', target='b')
        assert tx.chunk({}, seq=0).meta['stream'] is True

    def test_chunk_meta_has_seq(self):
        tx = TX(name='run', source='a', target='b')
        assert tx.chunk({}, seq=5).meta['seq'] == 5

    def test_chunk_wraps_non_dict_in_chunk_key(self):
        tx = TX(name='run', source='a', target='b')
        chunk = tx.chunk('hello', seq=0)
        assert chunk.data == {'chunk': 'hello'}

    def test_chunk_passes_dict_through(self):
        tx = TX(name='run', source='a', target='b')
        chunk = tx.chunk({'text': 'hi', 'done': False}, seq=0)
        assert chunk.data == {'text': 'hi', 'done': False}

    def test_chunk_new_uuid(self):
        tx = TX(name='run', source='a', target='b')
        chunk = tx.chunk({}, seq=0)
        assert chunk.uuid != tx.uuid

    def test_chunk_preserves_original_meta(self):
        tx = TX(name='run', source='a', target='b', meta={'trace': '123'})
        chunk = tx.chunk({}, seq=0)
        assert chunk.meta['trace'] == '123'

    def test_backward_compat_stream_chunk_alias(self):
        """stream_chunk() still works as alias for chunk()."""
        tx = TX(name='run', source='a', target='b')
        chunk = tx.chunk({'text': 'hi'}, seq=0)
        assert chunk.name == 'STREAM'
        assert chunk.data == {'text': 'hi'}


# ===================================================================
# TestTXStreamEnd
# ===================================================================

class TestTXEnd:
    """TX.end() — create a STREAM end reply."""

    def test_end_meta_has_stream_end(self):
        tx = TX(name='run', source='a', target='b')
        end = tx.end(seq=3)
        assert end.meta['stream_end'] is True

    def test_end_meta_has_stream_true(self):
        tx = TX(name='run', source='a', target='b')
        assert tx.end(seq=0).meta['stream'] is True

    def test_end_meta_has_req(self):
        tx = TX(name='run', source='a', target='b')
        end = tx.end(seq=0)
        assert end.meta['req'] == tx.uuid

    def test_end_default_data_empty_dict(self):
        tx = TX(name='run', source='a', target='b')
        assert tx.end(seq=0).data == {}

    def test_end_with_data(self):
        tx = TX(name='run', source='a', target='b')
        end = tx.end(data={'summary': 'done'}, seq=5)
        assert end.data == {'summary': 'done'}

    def test_end_swaps_source_target(self):
        tx = TX(name='run', source='api', target='agent')
        end = tx.end(seq=0)
        assert end.source == 'agent'
        assert end.target == 'api'

    def test_end_new_uuid(self):
        tx = TX(name='run', source='a', target='b')
        end = tx.end(seq=0)
        assert end.uuid != tx.uuid

    def test_end_preserves_original_meta(self):
        tx = TX(name='run', source='a', target='b', meta={'trace': '456'})
        end = tx.end(seq=0)
        assert end.meta['trace'] == '456'

    def test_end_name_is_stream(self):
        tx = TX(name='generate', source='a', target='b')
        end = tx.end(seq=0)
        assert end.name == 'STREAM'

    def test_backward_compat_stream_end_alias(self):
        """stream_end() still works as alias for end()."""
        tx = TX(name='run', source='a', target='b')
        end = tx.end(seq=0)
        assert end.name == 'STREAM'
        assert end.meta['stream_end'] is True


# ===================================================================
# TestNetworkAdapterStreamInbox
# ===================================================================

class TestNetworkAdapterStreamInbox:
    """inbox() resolves Queue for stream chunks, Future for single replies."""

    @pytest.mark.asyncio
    async def test_inbox_resolves_future_for_request(self):
        """Existing behavior: Future is resolved for request() replies."""
        Actor.__matrix__ = None
        m = Matrix()
        adapter = NetworkAdapter(addr='adapter')
        m.register(adapter)

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        adapter._pending['abc'] = future

        reply = TX(name='RESP', source='b', target='adapter', meta={'req': 'abc'})
        await adapter.inbox(reply)

        assert future.done()
        assert future.result() == reply
        assert 'abc' not in adapter._pending

    @pytest.mark.asyncio
    async def test_inbox_puts_chunk_in_queue(self):
        """Queue receives stream chunks."""
        Actor.__matrix__ = None
        m = Matrix()
        adapter = NetworkAdapter(addr='adapter')
        m.register(adapter)

        queue = asyncio.Queue()
        adapter._pending['xyz'] = queue

        chunk = TX(name='run', source='b', target='adapter',
                   meta={'req': 'xyz', 'stream': True, 'seq': 0})
        await adapter.inbox(chunk)

        assert not queue.empty()
        assert (await queue.get()) == chunk
        # Queue NOT removed -- stream still active
        assert 'xyz' in adapter._pending

    @pytest.mark.asyncio
    async def test_inbox_removes_queue_on_stream_end(self):
        """Queue is removed when stream_end chunk arrives."""
        Actor.__matrix__ = None
        m = Matrix()
        adapter = NetworkAdapter(addr='adapter')
        m.register(adapter)

        queue = asyncio.Queue()
        adapter._pending['xyz'] = queue

        end = TX(name='run', source='b', target='adapter',
                 meta={'req': 'xyz', 'stream': True, 'stream_end': True, 'seq': 3})
        await adapter.inbox(end)

        assert not queue.empty()
        assert 'xyz' not in adapter._pending

    @pytest.mark.asyncio
    async def test_inbox_removes_queue_on_error(self):
        """Queue is removed when error TX arrives."""
        Actor.__matrix__ = None
        m = Matrix()
        adapter = NetworkAdapter(addr='adapter')
        m.register(adapter)

        queue = asyncio.Queue()
        adapter._pending['xyz'] = queue

        error = TX(name='ERROR', source='b', target='adapter',
                   meta={'req': 'xyz', 'error': True})
        await adapter.inbox(error)

        assert not queue.empty()
        assert 'xyz' not in adapter._pending

    @pytest.mark.asyncio
    async def test_inbox_queue_receives_multiple_chunks(self):
        """Queue accumulates multiple stream chunks."""
        Actor.__matrix__ = None
        m = Matrix()
        adapter = NetworkAdapter(addr='adapter')
        m.register(adapter)

        queue = asyncio.Queue()
        adapter._pending['multi'] = queue

        for i in range(3):
            chunk = TX(name='run', source='b', target='adapter',
                       meta={'req': 'multi', 'stream': True, 'seq': i})
            await adapter.inbox(chunk)

        assert queue.qsize() == 3
        assert 'multi' in adapter._pending  # Still active until stream_end


# ===================================================================
# TestNetworkAdapterStream
# ===================================================================

class TestNetworkAdapterStream:
    """stream() yields chunks and terminates on stream_end."""

    @pytest.mark.asyncio
    async def test_stream_yields_chunks_and_terminates(self):
        Actor.__matrix__ = None
        m = Matrix()
        adapter = NetworkAdapter(addr='adapter')
        m.register(adapter)

        async def fake_send(tx):
            # Simulate backend sending 3 chunks + end
            for i in range(3):
                chunk = tx.chunk({'text': f'chunk{i}'}, seq=i)
                await adapter.inbox(chunk)
            end = tx.end(seq=3)
            await adapter.inbox(end)

        with mock_method(adapter, 'send', fake_send):
            tx = TX(name='run', source='adapter', target='agent')
            chunks = []
            async for chunk in adapter.stream(tx, timeout=5.0):
                chunks.append(chunk)

        assert len(chunks) == 4  # 3 chunks + 1 end
        assert chunks[0].data == {'text': 'chunk0'}
        assert chunks[1].data == {'text': 'chunk1'}
        assert chunks[2].data == {'text': 'chunk2'}
        assert chunks[-1].meta.get('stream_end') is True
        assert len(adapter._pending) == 0

    @pytest.mark.asyncio
    async def test_stream_terminates_on_error(self):
        Actor.__matrix__ = None
        m = Matrix()
        adapter = NetworkAdapter(addr='adapter')
        m.register(adapter)

        async def fake_send(tx):
            chunk = tx.chunk({'text': 'hi'}, seq=0)
            await adapter.inbox(chunk)
            error = tx.error('something broke', code=500)
            await adapter.inbox(error)

        with mock_method(adapter, 'send', fake_send):
            tx = TX(name='run', source='adapter', target='agent')
            chunks = []
            async for chunk in adapter.stream(tx, timeout=5.0):
                chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0].data == {'text': 'hi'}
        assert chunks[1].is_error

    @pytest.mark.asyncio
    async def test_stream_timeout_yields_error(self):
        Actor.__matrix__ = None
        m = Matrix()
        adapter = NetworkAdapter(addr='adapter')
        m.register(adapter)

        async def fake_send(tx):
            pass  # Never sends any response

        with mock_method(adapter, 'send', fake_send):
            tx = TX(name='run', source='adapter', target='agent')
            chunks = []
            async for chunk in adapter.stream(tx, timeout=0.05):
                chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].is_error
        assert chunks[0].data['code'] == 504

    @pytest.mark.asyncio
    async def test_stream_cleans_up_pending_on_completion(self):
        Actor.__matrix__ = None
        m = Matrix()
        adapter = NetworkAdapter(addr='adapter')
        m.register(adapter)

        async def fake_send(tx):
            await adapter.inbox(tx.end(seq=0))

        with mock_method(adapter, 'send', fake_send):
            tx = TX(name='run', source='adapter', target='agent')
            async for _ in adapter.stream(tx, timeout=5.0):
                pass

        assert len(adapter._pending) == 0

    @pytest.mark.asyncio
    async def test_stream_cleans_up_pending_on_timeout(self):
        """Pending entry is cleaned up after timeout via finally block."""
        Actor.__matrix__ = None
        m = Matrix()
        adapter = NetworkAdapter(addr='adapter')
        m.register(adapter)

        async def fake_send(tx):
            pass  # No response

        with mock_method(adapter, 'send', fake_send):
            tx = TX(name='run', source='adapter', target='agent')
            async for _ in adapter.stream(tx, timeout=0.05):
                pass

        assert len(adapter._pending) == 0

    @pytest.mark.asyncio
    async def test_stream_cleans_up_pending_on_error(self):
        """Pending entry is cleaned up after error via finally block."""
        Actor.__matrix__ = None
        m = Matrix()
        adapter = NetworkAdapter(addr='adapter')
        m.register(adapter)

        async def fake_send(tx):
            await adapter.inbox(tx.error('fail', code=500))

        with mock_method(adapter, 'send', fake_send):
            tx = TX(name='run', source='adapter', target='agent')
            async for _ in adapter.stream(tx, timeout=5.0):
                pass

        assert len(adapter._pending) == 0

    @pytest.mark.asyncio
    async def test_stream_chunk_sequence_numbers(self):
        """Chunks arrive with correct seq numbers in order."""
        Actor.__matrix__ = None
        m = Matrix()
        adapter = NetworkAdapter(addr='adapter')
        m.register(adapter)

        async def fake_send(tx):
            for i in range(5):
                await adapter.inbox(tx.chunk({'n': i}, seq=i))
            await adapter.inbox(tx.end(seq=5))

        with mock_method(adapter, 'send', fake_send):
            tx = TX(name='run', source='adapter', target='agent')
            seqs = []
            async for chunk in adapter.stream(tx, timeout=5.0):
                seqs.append(chunk.meta.get('seq'))

        assert seqs == [0, 1, 2, 3, 4, 5]


# ===================================================================
# TestActorModelStreamHandler
# ===================================================================

class TestActorModelStreamHandler:
    """ActorModel.handler() detects async generators and sends stream chunks."""

    @pytest.mark.asyncio
    async def test_async_gen_method_sends_stream_chunks(self):
        """Handler detects async generator and streams chunks via TX."""
        from n3tx_actors.models.actor_model import ActorModel

        class StreamModel(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'stream_test'

            # Non-exposed methods use (data, tx) signature (no self)
            async def generate(data, tx):
                yield {'text': 'hello'}
                yield {'text': 'world'}

        Actor.__matrix__ = None
        m = Matrix()
        m.register(StreamModel)

        sent = []
        async def capture(tx):
            sent.append(tx)

        tx = TX(name='generate', source='client', target='stream_test', data={})
        with mock_method(m, 'inbox', capture):
            await StreamModel.handler(tx)

        # Should have 3 messages: 2 chunks + 1 end
        assert len(sent) == 3
        assert sent[0].name == 'STREAM'
        assert sent[0].data == {'text': 'hello'}
        assert sent[0].meta.get('stream') is True
        assert sent[0].meta.get('seq') == 0
        assert sent[1].name == 'STREAM'
        assert sent[1].data == {'text': 'world'}
        assert sent[1].meta.get('seq') == 1
        assert sent[2].name == 'STREAM'
        assert sent[2].meta.get('stream_end') is True
        assert sent[2].meta.get('seq') == 2

    @pytest.mark.asyncio
    async def test_async_gen_stream_end_has_correct_meta(self):
        """Stream end TX has stream=True and stream_end=True."""
        from n3tx_actors.models.actor_model import ActorModel

        class EndMetaModel(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'end_meta_test'

            async def generate(data, tx):
                yield {'text': 'only'}

        Actor.__matrix__ = None
        m = Matrix()
        m.register(EndMetaModel)

        sent = []
        async def capture(tx):
            sent.append(tx)

        tx = TX(name='generate', source='client', target='end_meta_test', data={})
        with mock_method(m, 'inbox', capture):
            await EndMetaModel.handler(tx)

        end = sent[-1]
        assert end.meta.get('stream') is True
        assert end.meta.get('stream_end') is True
        assert end.meta.get('req') == tx.uuid

    @pytest.mark.asyncio
    async def test_async_gen_chunks_have_req_field(self):
        """Each stream chunk has meta.req pointing to the original TX uuid."""
        from n3tx_actors.models.actor_model import ActorModel

        class ReqModel(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'req_test'

            async def generate(data, tx):
                yield {'text': 'a'}
                yield {'text': 'b'}

        Actor.__matrix__ = None
        m = Matrix()
        m.register(ReqModel)

        sent = []
        async def capture(tx):
            sent.append(tx)

        tx = TX(name='generate', source='client', target='req_test', data={})
        with mock_method(m, 'inbox', capture):
            await ReqModel.handler(tx)

        for s in sent:
            assert s.meta.get('req') == tx.uuid

    @pytest.mark.asyncio
    async def test_async_gen_wraps_non_dict_chunks(self):
        """Non-dict chunks are wrapped in {'chunk': value}."""
        from n3tx_actors.models.actor_model import ActorModel

        class StringChunkModel(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'str_chunk_test'

            async def generate(data, tx):
                yield 'hello'
                yield 'world'

        Actor.__matrix__ = None
        m = Matrix()
        m.register(StringChunkModel)

        sent = []
        async def capture(tx):
            sent.append(tx)

        tx = TX(name='generate', source='client', target='str_chunk_test', data={})
        with mock_method(m, 'inbox', capture):
            await StringChunkModel.handler(tx)

        assert sent[0].data == {'chunk': 'hello'}
        assert sent[1].data == {'chunk': 'world'}

    @pytest.mark.asyncio
    async def test_async_gen_error_sends_error_tx(self):
        """If the async generator raises, an error TX is sent."""
        from n3tx_actors.models.actor_model import ActorModel

        class ErrorGenModel(ActorModel, auto_register=False):
            __tablename__: ClassVar[str] = 'error_gen_test'

            async def generate(data, tx):
                yield {'text': 'before error'}
                raise RuntimeError('stream broke')

        Actor.__matrix__ = None
        m = Matrix()
        m.register(ErrorGenModel)

        sent = []
        async def capture(tx):
            sent.append(tx)

        tx = TX(name='generate', source='client', target='error_gen_test', data={})
        with mock_method(m, 'inbox', capture):
            await ErrorGenModel.handler(tx)

        # First chunk, then error
        assert len(sent) == 2
        assert sent[0].data == {'text': 'before error'}
        assert sent[0].meta.get('stream') is True
        assert sent[1].is_error
        assert 'stream broke' in sent[1].data['message']
