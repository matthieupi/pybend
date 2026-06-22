"""Tests for RemoteMatrix distributed reference adapter."""

import json

import httpx
import pytest

from n3tx_actors.api.remote_matrix import MatrixReferenceResolver, RemoteMatrix, normalize_remotes
from n3tx_actors.matrix import Matrix
from n3tx_actors.tx import TX

pytestmark = pytest.mark.unit


class TestNormalizeRemotes:

    def test_accepts_string_and_dict_entries(self):
        remotes = normalize_remotes({
            'storage': 'http://storage:7100/',
            'files': {'url': 'http://files:7200/', 'token': 'secret'},
        })
        assert remotes == {
            'storage': {'url': 'http://storage:7100', 'token': ''},
            'files': {'url': 'http://files:7200', 'token': 'secret'},
        }


class TestRemoteMatrix:

    def test_can_handle_only_canonical_distributed_refs(self):
        adapter = RemoteMatrix(remotes={'storage': 'http://storage:7100'})
        assert adapter.can_handle(TX(name='get', source='test', target='n3tx://storage/File/12')) is True
        assert adapter.can_handle(TX(name='reindex', source='test', target='n3tx://storage/File')) is True
        assert adapter.can_handle(TX(name='get', source='test', target='/File/12')) is False
        assert adapter.can_handle(TX(name='get', source='test', target='https://example.com/File/12')) is False

    def test_url_mapping_for_get_and_methods(self):
        adapter = RemoteMatrix(remotes={'storage': 'http://storage:7100/'})
        assert adapter._url_for(TX(name='get', source='test', target='n3tx://storage/File/12')) == 'http://storage:7100/File/12'
        assert adapter._url_for(TX(name='process', source='test', target='n3tx://storage/File/12')) == 'http://storage:7100/File/12/process'

    def test_headers_include_service_token_and_user_context(self):
        adapter = RemoteMatrix(
            remotes={'storage': {'url': 'http://storage:7100', 'token': 'remote-token'}},
            service_name='api-test',
        )
        tx = TX(
            name='get',
            source='test',
            target='n3tx://storage/File/12',
            meta={'user': {'id': 7, 'role': 'admin'}},
        )
        headers = adapter._headers(tx, adapter._remotes['storage'])
        assert headers['Authorization'] == 'Bearer remote-token'
        assert headers['X-N3TX-Service'] == 'api-test'
        assert '"id": 7' in headers['X-N3TX-User']

    def test_canonicalizes_remote_response_ids(self):
        adapter = RemoteMatrix(remotes={'storage': 'http://storage:7100'})

        data = adapter._canonicalize_response_ids({
            '$id': 'http://storage:7100/File/12',
            'children': [{'$id': '/Artifact/42'}],
        }, 'storage')

        assert data == {
            '$id': 'n3tx://storage/File/12',
            'children': [{'$id': 'n3tx://storage/Artifact/42'}],
        }

    @pytest.mark.asyncio
    async def test_send_replies_to_matrix_pending_request(self):
        matrix = Matrix(addr='test-matrix')
        adapter = RemoteMatrix(remotes={'storage': 'http://storage:7100'})
        matrix.register(adapter)
        matrix.register_adapter(adapter)

        async def fake_request(tx):
            return {'$id': tx.target, 'name': 'remote-file'}

        adapter._request_remote_rest = fake_request

        response = await matrix.request(
            TX(name='get', source='test', target='n3tx://storage/File/12'),
            timeout=1,
        )

        assert response.is_error is False
        assert response.data == {'$id': 'n3tx://storage/File/12', 'name': 'remote-file'}

    @pytest.mark.asyncio
    async def test_stream_parses_remote_sse_tx_envelopes(self):
        adapter = RemoteMatrix(remotes={'compute': 'http://compute:7200'})
        tx = TX(
            name='generate',
            source='app',
            target='n3tx://compute/ComputePipeline/0',
            data={'prompt': 'hi'},
            meta={'stream': True},
        )

        payloads = [
            tx.chunk({'text': 'one'}, seq=0),
            tx.chunk({'text': 'two'}, seq=1),
            tx.end({'summary': 'done'}, seq=2),
        ]
        body = ''.join(
            f': padding\n'
            f'event: {"done" if item.meta.get("stream_end") else "chunk"}\n'
            f'data: {json.dumps(item.__dict__)}\n\n'
            for item in payloads
        )

        async def fake_stream_response(_tx, url, headers, timeout):
            assert url == 'http://compute:7200/ComputePipeline/0/generate'
            yield body

        adapter._stream_response_text = fake_stream_response

        chunks = []
        async for chunk in adapter.stream(tx, timeout=1):
            chunks.append(chunk)

        assert [chunk.data for chunk in chunks] == [
            {'text': 'one'},
            {'text': 'two'},
            {'summary': 'done'},
        ]
        assert chunks[-1].meta['stream_end'] is True

    @pytest.mark.asyncio
    async def test_stream_uses_schema_route_for_class_method(self):
        requests = []

        def handler(request):
            requests.append((request.method, str(request.url), dict(request.headers)))
            if request.method == 'GET':
                return httpx.Response(200, json={
                    'methods': {
                        'upload_to_splat': {
                            'route': '/upload-to-splat',
                            'scope': 'class',
                            'stream': True,
                        }
                    }
                })
            return httpx.Response(
                200,
                content=(
                    'event: done\n'
                    f'data: {json.dumps(TX(name="STREAM", source="remote", target="app", data={}, meta={"stream_end": True, "stream": True}).__dict__)}\n\n'
                ),
            )

        adapter = RemoteMatrix(
            remotes={'compute': {'url': 'http://compute:7200', 'token': 'remote-token'}},
            service_name='app-service',
        )
        adapter._transport = httpx.MockTransport(handler)
        tx = TX(
            name='upload_to_splat',
            source='app',
            target='n3tx://compute/ComputePipeline',
            data={'run_id': 'run-1'},
            meta={'stream': True, 'user': {'user_id': 7}},
        )

        chunks = []
        async for chunk in adapter.stream(tx, timeout=1):
            chunks.append(chunk)

        assert chunks[-1].meta['stream_end'] is True
        assert requests[0][:2] == ('GET', 'http://compute:7200/ComputePipeline')
        assert requests[1][:2] == ('POST', 'http://compute:7200/ComputePipeline/upload-to-splat')
        assert requests[1][2]['authorization'] == 'Bearer remote-token'
        assert requests[1][2]['x-n3tx-service'] == 'app-service'
        assert '"user_id": 7' in requests[1][2]['x-n3tx-user']

    @pytest.mark.asyncio
    async def test_stream_uses_schema_route_for_static_method_without_instance_id(self):
        requests = []

        def handler(request):
            requests.append((request.method, str(request.url)))
            if request.method == 'GET':
                return httpx.Response(200, json={
                    'methods': {
                        'upload_to_splat': {
                            'route': '/upload-to-splat',
                            'scope': 'staticmethod',
                            'stream': True,
                            'methods': ['POST'],
                        }
                    }
                })
            if str(request.url).endswith('/ComputePipeline/0/upload_to_splat'):
                return httpx.Response(405, text='wrong fallback route')
            return httpx.Response(
                200,
                content=(
                    'event: done\n'
                    f'data: {json.dumps(TX(name="STREAM", source="remote", target="app", data={}, meta={"stream_end": True, "stream": True}).__dict__)}\n\n'
                ),
            )

        adapter = RemoteMatrix(remotes={'compute': {'url': 'http://compute:7200', 'token': 'token'}})
        adapter._transport = httpx.MockTransport(handler)
        tx = TX(
            name='upload_to_splat',
            source='app',
            target='n3tx://compute/ComputePipeline',
            data={'run_id': 'run-1'},
            meta={'stream': True},
        )

        chunks = [chunk async for chunk in adapter.stream(tx, timeout=1)]

        assert chunks[-1].meta['stream_end'] is True
        assert requests[0] == ('GET', 'http://compute:7200/ComputePipeline')
        assert requests[1] == ('POST', 'http://compute:7200/ComputePipeline/upload-to-splat')

    @pytest.mark.asyncio
    async def test_send_uses_schema_route_for_static_method_without_instance_id(self):
        requests = []

        def handler(request):
            requests.append((request.method, str(request.url), json.loads(request.content or b'{}')))
            if request.method == 'GET':
                return httpx.Response(200, json={
                    'methods': {
                        'reindex': {
                            'route': '/reindex',
                            'scope': 'staticmethod',
                            'methods': ['POST'],
                        }
                    }
                })
            if str(request.url).endswith('/ComputePipeline/0/reindex'):
                return httpx.Response(405, text='wrong instance route')
            return httpx.Response(200, json={'ok': True})

        adapter = RemoteMatrix(remotes={'compute': 'http://compute:7200'})
        adapter._transport = httpx.MockTransport(handler)
        tx = TX(
            name='reindex',
            source='app',
            target='n3tx://compute/ComputePipeline',
            data={'force': True},
        )

        result = await adapter._request_remote_rest(tx)

        assert result == {'ok': True}
        assert requests[0][:2] == ('GET', 'http://compute:7200/ComputePipeline')
        assert requests[1] == ('POST', 'http://compute:7200/ComputePipeline/reindex', {'force': True})

    @pytest.mark.asyncio
    async def test_stream_yields_error_tx_for_remote_error_frame(self):
        adapter = RemoteMatrix(remotes={'compute': 'http://compute:7200'})
        tx = TX(name='generate', source='app', target='n3tx://compute/ComputePipeline/0')
        error = tx.error('remote failed', code=500)

        async def fake_stream_response(_tx, url, headers, timeout):
            yield f'event: error\ndata: {json.dumps(error.__dict__)}\n\n'

        adapter._stream_response_text = fake_stream_response

        chunks = []
        async for chunk in adapter.stream(tx, timeout=1):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert chunks[0].is_error
        assert chunks[0].data['message'] == 'remote failed'


class TestMatrixReferenceResolver:

    @pytest.mark.asyncio
    async def test_resolves_through_matrix_remote_adapter(self):
        matrix = Matrix(addr='resolver-matrix')
        adapter = RemoteMatrix(remotes={'storage': 'http://storage:7100'})
        matrix.register(adapter)
        matrix.register_adapter(adapter)

        async def fake_request(tx):
            return {'$id': tx.target, 'name': 'remote-file'}

        adapter._request_remote_rest = fake_request
        resolver = MatrixReferenceResolver(matrix, timeout=1)

        result = resolver.resolve('n3tx://storage/File/12')

        assert result == {'$id': 'n3tx://storage/File/12', 'name': 'remote-file'}

    @pytest.mark.asyncio
    async def test_raises_for_remote_errors(self):
        matrix = Matrix(addr='resolver-error-matrix')
        resolver = MatrixReferenceResolver(matrix, timeout=1)

        with pytest.raises(RuntimeError, match='No route'):
            resolver.resolve('n3tx://storage/File/12')
