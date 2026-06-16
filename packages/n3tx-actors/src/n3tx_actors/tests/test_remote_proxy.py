"""Tests for explicit remote ref handle."""

import pytest
from pydantic import BaseModel

from n3tx_actors.api.remote_matrix import RemoteMatrix
from n3tx_actors.matrix import Matrix
from n3tx_actors.models.actor_model import ActorModel
from n3tx_actors.remote_proxy import RemoteRef, RemoteRefError

pytestmark = pytest.mark.unit


class File(BaseModel):
    id: int = 0


class Artifact(ActorModel):
    __tablename__ = 'test_remote_artifacts'
    __storable__ = False


class TestRemoteRef:

    @pytest.mark.asyncio
    async def test_get_routes_through_matrix(self):
        matrix = Matrix(addr='proxy-matrix')
        adapter = RemoteMatrix(remotes={'storage': 'http://storage:7100'})
        matrix.register(adapter)
        matrix.register_adapter(adapter)

        async def fake_request(tx):
            return {'$id': tx.target, 'name': 'remote-file'}

        adapter._request_remote_rest = fake_request
        proxy = RemoteRef('n3tx://storage/File/12', model_cls=File, matrix=matrix)

        assert await proxy.get() == {'$id': 'n3tx://storage/File/12', 'name': 'remote-file'}

    @pytest.mark.asyncio
    async def test_actor_model_ref_returns_callable_handle(self):
        matrix = Matrix(addr='actor-model-ref-matrix')
        adapter = RemoteMatrix(remotes={'storage': 'http://storage:7100'})
        matrix.register(adapter)
        matrix.register_adapter(adapter)

        async def fake_request(tx):
            return {'ok': True, 'target': tx.target, 'method': tx.name}

        adapter._request_remote_rest = fake_request
        artifact = Artifact.ref('n3tx://storage/Artifact/42', matrix=matrix)

        assert await artifact.call('process', mode='fast') == {
            'ok': True,
            'target': 'n3tx://storage/Artifact/42',
            'method': 'process',
        }

    @pytest.mark.asyncio
    async def test_call_routes_method_name_and_payload(self):
        matrix = Matrix(addr='proxy-method-matrix')
        adapter = RemoteMatrix(remotes={'storage': 'http://storage:7100'})
        matrix.register(adapter)
        matrix.register_adapter(adapter)
        seen = {}

        async def fake_request(tx):
            seen['name'] = tx.name
            seen['data'] = tx.data
            return {'ok': True}

        adapter._request_remote_rest = fake_request
        proxy = RemoteRef('n3tx://storage/File/12', model_cls=File, matrix=matrix)

        assert await proxy.call('process', mode='fast') == {'ok': True}
        assert seen == {'name': 'process', 'data': {'mode': 'fast'}}

    @pytest.mark.asyncio
    async def test_error_response_raises(self):
        matrix = Matrix(addr='proxy-error-matrix')
        proxy = RemoteRef('n3tx://storage/File/12', model_cls=File, matrix=matrix)

        with pytest.raises(RemoteRefError, match='No route'):
            await proxy.get()
