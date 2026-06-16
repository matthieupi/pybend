"""Tests for RemoteMatrix distributed reference adapter."""

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
