"""REST-backed remote Matrix adapter for distributed N3TX refs."""

from __future__ import annotations

import logging
import asyncio
import json
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
    _method_route_cache: dict = PrivateAttr(default_factory=dict)
    _transport: Any = PrivateAttr(default=None)

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

    async def _method_route_for(self, service: str, class_name: str, method: str) -> dict[str, Any] | None:
        """Resolve a remote exposed method from the model schema, caching results.

        The schema is the authoritative N3TX contract. It carries decorator route
        paths such as ``/upload-to-splat`` that cannot be derived safely from a
        Python method name like ``upload_to_splat``.
        """
        key = (service, class_name, method)
        if key in self._method_route_cache:
            return self._method_route_cache[key]

        remote = self._remotes[service]
        url = f"{remote['url']}/{class_name}"
        headers = {'Accept': 'application/json', 'X-N3TX-Service': self._service_name}
        token = remote.get('token') or self._service_token
        if token:
            headers['Authorization'] = f'Bearer {token}'

        client_kwargs = {'timeout': self._timeout}
        if self._transport is not None:
            client_kwargs['transport'] = self._transport

        async with httpx.AsyncClient(**client_kwargs) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            schema = response.json()

        route_info = (schema.get('methods') or {}).get(method)
        self._method_route_cache[key] = route_info
        return route_info

    async def _stream_url_for(self, tx: TX) -> str:
        """Resolve the remote streaming URL using schema metadata when possible."""
        service, class_name, ident = parse_ref_string(tx.target)
        if service not in self._remotes:
            raise ValueError(f"Remote service not configured: {service}")
        base = self._remotes[service]['url']

        try:
            route_info = await self._method_route_for(service, class_name, tx.name)
        except Exception as exc:
            logger.warning(
                "RemoteMatrix schema route lookup failed for %s.%s at %s/%s: %s; "
                "falling back to synthesized remote URL",
                class_name, tx.name, base, class_name, exc,
            )
            return self._url_for(tx)

        if not route_info:
            return self._url_for(tx)

        route = str(route_info.get('route') or f'/{tx.name}')
        if not route.startswith('/'):
            route = f'/{route}'
        scope = route_info.get('scope')
        if scope in ('instancemethod', 'instance', 'self'):
            return f'{base}/{class_name}/{ident}{route}'
        return f'{base}/{class_name}{route}'

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

        client_kwargs = {'timeout': self._timeout}
        if self._transport is not None:
            client_kwargs['transport'] = self._transport

        async with httpx.AsyncClient(**client_kwargs) as client:
            if tx.name == 'get':
                response = await client.get(url, headers=headers)
            else:
                response = await client.post(url, json=tx.data or {}, headers={**headers, 'Content-Type': 'application/json'})

        response.raise_for_status()
        if not response.content:
            return {}
        return self._canonicalize_response_ids(response.json(), service)

    async def _stream_response_text(self, tx: TX, url: str, headers: dict[str, str], timeout: float | None):
        """Yield text chunks from a remote SSE response."""
        client_kwargs = {'timeout': None if timeout is None else httpx.Timeout(timeout, read=timeout)}
        if self._transport is not None:
            client_kwargs['transport'] = self._transport

        async with httpx.AsyncClient(**client_kwargs) as client:
            async with client.stream(
                'POST',
                url,
                json=tx.data or {},
                headers={**headers, 'Accept': 'text/event-stream', 'Content-Type': 'application/json'},
            ) as response:
                response.raise_for_status()
                async for text in response.aiter_text():
                    yield text

    async def _iter_sse_payloads(self, text_iter):
        """Parse SSE frames and yield JSON payload objects from ``data:`` lines."""
        buffer = ''
        async for text in text_iter:
            buffer += text.replace('\r\n', '\n')
            frames = buffer.split('\n\n')
            buffer = frames.pop()
            for frame in frames:
                data_lines = []
                for line in frame.split('\n'):
                    if line.startswith(':') or not line:
                        continue
                    if line.startswith('data:'):
                        data_lines.append(line[5:].strip())
                if data_lines:
                    yield json.loads('\n'.join(data_lines))

    def _tx_from_payload(self, payload: Any, fallback: TX, service: str) -> TX:
        """Reconstruct a TX envelope from remote SSE payload data."""
        if isinstance(payload, TX):
            return payload
        if isinstance(payload, dict) and {'name', 'source', 'target'}.issubset(payload):
            data = self._canonicalize_response_ids(payload.get('data') or {}, service)
            tx_kwargs = dict(
                name=payload.get('name') or 'STREAM',
                source=payload.get('source') or fallback.target,
                target=payload.get('target') or fallback.source,
                data=data,
                meta=payload.get('meta') or {},
            )
            if payload.get('timestamp') is not None:
                tx_kwargs['timestamp'] = payload['timestamp']
            if payload.get('uuid') is not None:
                tx_kwargs['uuid'] = payload['uuid']
            return TX(**tx_kwargs)
        return fallback.chunk(payload if isinstance(payload, dict) else {'chunk': payload}, seq=0)

    async def stream(self, tx: TX, timeout: float = 120.0):
        """Stream a remote generated SSE route and yield TX chunks.

        Unlike the base ``NetworkAdapter.stream()``, this adapter does not route
        the TX locally and wait on ``inbox()`` correlation. It is itself the
        remote transport boundary for canonical distributed refs.
        """
        service, _class_name, _ident = parse_ref_string(tx.target)
        remote = self._remotes[service]
        try:
            url = await self._stream_url_for(tx)
            headers = self._headers(tx, remote)
            text_iter = self._stream_response_text(tx, url, headers, timeout)
            async for payload in self._iter_sse_payloads(text_iter):
                chunk = self._tx_from_payload(payload, tx, service)
                yield chunk
                if chunk.is_error or chunk.meta.get('stream_end'):
                    return
        except httpx.HTTPStatusError as exc:
            yield tx.error(str(exc), code=exc.response.status_code)
        except httpx.TimeoutException as exc:
            yield tx.error(str(exc) or f"Stream timed out after {timeout}s", code=504)
        except Exception as exc:
            logger.warning("RemoteMatrix stream failed for %s: %s", tx.target, exc)
            yield tx.error(str(exc), code=502)

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
