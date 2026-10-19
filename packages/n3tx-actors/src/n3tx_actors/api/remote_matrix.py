"""REST-backed Matrix adapter for absolute HTTP(S) actor targets."""

from __future__ import annotations

import logging
import asyncio
import json
import threading
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import PrivateAttr

from n3tx_core import config
from n3tx_core.models.ref import Ref, is_ref_url
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
    """Route absolute HTTP(S) entity/class targets through N3TX REST APIs."""

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
        try:
            self._parse_target(tx.target)
        except ValueError:
            return False
        return True

    def _parse_target(self, target: str) -> tuple[str, str, str | None]:
        """Return ``(base_url, class_name, id)`` for an HTTP(S) target.

        Entity targets use ``.../{Class}/{id}``; class capability targets use
        ``.../{Class}``. Configured remote base URLs disambiguate API prefixes.
        """
        if not isinstance(target, str):
            raise ValueError(f"Unsupported remote target: {target!r}")
        parsed = urlsplit(target.strip())
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError(f"Unsupported remote target: {target!r}")

        canonical = urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip('/'), '', ''))
        for remote in sorted(self._remotes.values(), key=lambda item: len(item['url']), reverse=True):
            base = remote['url']
            prefix = f'{base}/'
            if canonical.startswith(prefix):
                relative = canonical[len(prefix):].split('/')
                if len(relative) == 1 and relative[0]:
                    return base, relative[0], None
                if len(relative) == 2 and all(relative):
                    return base, relative[0], relative[1]

        if is_ref_url(canonical):
            return Ref.base_url(canonical), Ref.schema(canonical), Ref.id(canonical)
        raise ValueError(
            'Class-level HTTP targets with API path prefixes require a configured remote base URL'
        )

    def _remote_for(self, base_url: str) -> dict[str, Any]:
        for remote in self._remotes.values():
            if remote['url'] == base_url:
                return remote
        return {'url': base_url, 'token': ''}

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
        base, class_name, ident = self._parse_target(tx.target)
        if ident is None:
            raise ValueError(f"Remote target requires an id for {tx.name}: {tx.target}")
        if tx.name == 'get':
            return f'{base}/{class_name}/{ident}'
        return f'{base}/{class_name}/{ident}/{tx.name}'

    async def _method_route_for(self, base: str, class_name: str, method: str) -> dict[str, Any] | None:
        """Resolve a remote exposed method from the model schema, caching results.

        The schema is the authoritative N3TX contract. It carries decorator route
        paths such as ``/upload-to-splat`` that cannot be derived safely from a
        Python method name like ``upload_to_splat``.
        """
        key = (base, class_name, method)
        if key in self._method_route_cache:
            return self._method_route_cache[key]

        remote = self._remote_for(base)
        url = f"{base}/{class_name}"
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

    async def _method_url_for(self, tx: TX) -> str:
        """Resolve a remote operation URL using schema metadata when possible."""
        base, class_name, ident = self._parse_target(tx.target)

        if tx.name == 'get':
            return self._url_for(tx)

        try:
            route_info = await self._method_route_for(base, class_name, tx.name)
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
            if ident is None:
                raise ValueError(f"Remote instance method requires an id: {tx.target}")
            return f'{base}/{class_name}/{ident}{route}'
        return f'{base}/{class_name}{route}'

    async def _request_remote_rest(self, tx: TX) -> dict:
        base, _class_name, _ident = self._parse_target(tx.target)
        remote = self._remote_for(base)
        url = await self._method_url_for(tx)
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
        return response.json()

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

    def _tx_from_payload(self, payload: Any, fallback: TX) -> TX:
        """Reconstruct a TX envelope from remote SSE payload data."""
        if isinstance(payload, TX):
            return payload
        if isinstance(payload, dict) and {'name', 'source', 'target'}.issubset(payload):
            tx_kwargs = dict(
                name=payload.get('name') or 'STREAM',
                source=payload.get('source') or fallback.target,
                target=payload.get('target') or fallback.source,
                data=payload.get('data') or {},
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
        remote transport boundary for canonical HTTP(S) targets.
        """
        base, _class_name, _ident = self._parse_target(tx.target)
        remote = self._remote_for(base)
        try:
            url = await self._method_url_for(tx)
            headers = self._headers(tx, remote)
            text_iter = self._stream_response_text(tx, url, headers, timeout)
            async for payload in self._iter_sse_payloads(text_iter):
                chunk = self._tx_from_payload(payload, tx)
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
