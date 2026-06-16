"""REST-backed remote Matrix adapter for distributed N3TX refs."""

from __future__ import annotations

import logging
import asyncio
import threading
from typing import Any

import httpx
from pydantic import PrivateAttr

from n3tx_core import config
from n3tx_core.models.ref import canonicalize_ref, is_distributed_ref, parse_ref_string
from n3tx_actors.api.network_adapter import NetworkAdapter
from n3tx_actors.tx import TX

logger = logging.getLogger('n3tx.network.remote')


def normalize_remotes(remotes=None) -> dict[str, dict[str, Any]]:
    """Normalize remote service config into ``{name: {url, token}}``."""
    source = remotes if remotes is not None else getattr(config, 'REMOTES', {})
    normalized = {}
    for name, entry in (source or {}).items():
        if isinstance(entry, str):
            url = entry
            token = ''
        elif isinstance(entry, dict):
            url = entry.get('url') or entry.get('base_url')
            token = entry.get('token', '')
        else:
            continue
        if not url:
            continue
        normalized[name] = {
            'url': str(url).rstrip('/'),
            'token': token,
        }
    return normalized


class RemoteMatrix(NetworkAdapter, auto_register=False):
    """Map canonical ``n3tx://service/Class/id`` targets to remote REST calls."""

    _remotes: dict = PrivateAttr(default_factory=dict)
    _service_name: str = PrivateAttr(default='api')
    _service_token: str = PrivateAttr(default='')
    _timeout: float = PrivateAttr(default=30.0)

    def __init__(self, remotes=None, service_name=None, service_token=None, timeout: float = 30.0, **kwargs):
        kwargs.setdefault('addr', 'remote')
        super().__init__(**kwargs)
        self._remotes = normalize_remotes(remotes)
        self._service_name = service_name if service_name is not None else getattr(config, 'SERVICE_NAME', 'api')
        self._service_token = service_token if service_token is not None else getattr(config, 'SERVICE_TOKEN', '')
        self._timeout = timeout

    def can_handle(self, tx: TX) -> bool:
        return is_distributed_ref(tx.target)

    def _headers(self, tx: TX, remote: dict[str, Any]) -> dict[str, str]:
        headers = {
            'Accept': 'application/json',
            'X-N3TX-Service': self._service_name,
        }
        token = remote.get('token') or self._service_token
        if token:
            headers['Authorization'] = f'Bearer {token}'

        user = tx.meta.get('user')
        if user is not None:
            import json
            headers['X-N3TX-User'] = json.dumps(user, default=str)
        return headers

    def _url_for(self, tx: TX) -> str:
        service, class_name, ident = parse_ref_string(tx.target)
        if service not in self._remotes:
            raise ValueError(f"Remote service not configured: {service}")
        base = self._remotes[service]['url']
        if tx.name == 'get':
            return f'{base}/{class_name}/{ident}'
        return f'{base}/{class_name}/{ident}/{tx.name}'

    def _canonicalize_remote_id(self, value: Any, service: str) -> Any:
        """Convert remote-local response identities into canonical n3tx refs."""
        if not isinstance(value, str):
            return value
        if is_distributed_ref(value):
            return value
        if value.startswith('/'):
            try:
                _service, class_name, ident = parse_ref_string(value)
            except ValueError:
                return value
            return f'n3tx://{service}/{class_name}/{ident}'
        try:
            canonical = canonicalize_ref(value, remotes={service: self._remotes.get(service)})
        except ValueError:
            return value
        return canonical if is_distributed_ref(canonical) else value

    def _canonicalize_response_ids(self, data: Any, service: str) -> Any:
        """Recursively canonicalize ``$id`` values from a remote service."""
        if isinstance(data, dict):
            return {
                key: self._canonicalize_remote_id(value, service) if key == '$id'
                else self._canonicalize_response_ids(value, service)
                for key, value in data.items()
            }
        if isinstance(data, list):
            return [self._canonicalize_response_ids(item, service) for item in data]
        return data

    async def _request_remote_rest(self, tx: TX) -> dict:
        service, _class_name, _ident = parse_ref_string(tx.target)
        remote = self._remotes[service]
        url = self._url_for(tx)
        headers = self._headers(tx, remote)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            if tx.name == 'get':
                response = await client.get(url, headers=headers)
            else:
                response = await client.post(url, json=tx.data or {}, headers={**headers, 'Content-Type': 'application/json'})

        response.raise_for_status()
        if not response.content:
            return {}
        return self._canonicalize_response_ids(response.json(), service)

    async def send(self, tx: TX) -> None:
        try:
            data = await self._request_remote_rest(tx)
            response = tx.reply(data=data)
        except httpx.HTTPStatusError as exc:
            response = tx.error(str(exc), code=exc.response.status_code)
        except Exception as exc:
            logger.warning("RemoteMatrix request failed for %s: %s", tx.target, exc)
            response = tx.error(str(exc), code=502)

        parent = self.parent
        if parent:
            await parent.inbox(response)
        else:
            await self.inbox(response)


class MatrixReferenceResolver:
    """Storage reference resolver backed by Matrix request routing."""

    def __init__(self, matrix, *, source: str = '', timeout: float = 30.0):
        self.matrix = matrix
        self.source = source
        self.timeout = timeout

    async def _resolve_async(self, ref, *, target_cls=None, user=None, context=None):
        tx = TX(
            name='get',
            source=self.source,
            target=ref,
            data={},
            meta={'user': user, 'context': context or {}},
        )
        response = await self.matrix.request(tx, timeout=self.timeout)
        if response.is_error:
            raise RuntimeError(response.data.get('message', 'Remote reference resolution failed'))
        return response.data

    def resolve(self, ref, *, target_cls=None, user=None, context=None):
        """Resolve from synchronous storage code while reusing async Matrix IO."""
        coro = self._resolve_async(ref, target_cls=target_cls, user=user, context=context)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        result = {}

        def run_in_thread():
            try:
                result['value'] = asyncio.run(coro)
            except Exception as exc:
                result['error'] = exc

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        thread.join()
        if 'error' in result:
            raise result['error']
        return result.get('value')


__all__ = ['RemoteMatrix', 'MatrixReferenceResolver', 'normalize_remotes']
