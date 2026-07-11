"""Explicit remote handle for HTTP(S) N3TX entity refs."""

from __future__ import annotations

from n3tx_core.models.ref import Ref
from n3tx_actors.actor import Actor
from n3tx_actors.tx import TX


class RemoteRefError(RuntimeError):
    """Raised when a remote ref call returns an error TX."""


class RemoteRef:
    """Explicit async API for method calls on remote actor/model refs."""

    def __init__(self, ref, *, model_cls=None, matrix=None, user=None, source: str = ''):
        self.ref = Ref.url(ref)
        if model_cls is not None and Ref.schema(self.ref) != model_cls.__name__:
            raise ValueError(
                f'Reference target mismatch: expected {model_cls.__name__}, '
                f'got {Ref.schema(self.ref)}'
            )
        self.model_cls = model_cls
        self.matrix = matrix or Actor.root()
        self.user = user
        self.source = source
        if self.matrix is None:
            raise RuntimeError('RemoteRef requires a Matrix root or explicit matrix')

    async def get(self):
        return await self.call('get')

    async def call(self, method: str, **data):
        tx = TX(
            name=method,
            source=self.source,
            target=self.ref,
            data=data,
            meta={'user': self.user} if self.user is not None else {},
        )
        response = await self.matrix.request(tx)
        if response.is_error:
            raise RemoteRefError(response.data.get('message', 'Remote ref call failed'))
        return response.data


__all__ = ['RemoteRef', 'RemoteRefError']
