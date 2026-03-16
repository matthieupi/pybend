"""NetworkWebSocket -- WebSocket adapter for frontend Matrix bridge.

Bridges a persistent WebSocket connection to the backend Matrix via TX
messaging. Frontend TX messages arrive as JSON, get translated to
backend TX format, routed through Matrix, and responses sent back.

Lifecycle events (create/update/delete) from ActorModel._publish_lifecycle
are broadcast to all connected clients in real-time.

Protocol translation:
    Frontend target URLs (http://host:port/products/42) are stripped to
    local addresses (products) with id extracted into data. Frontend
    UPPERCASE event names are mapped to backend lowercase.

Usage:
    ws = NetworkWebSocket()
    matrix.register(ws)
    ws.use(auth_interceptor, on='request')
    app.include_router(create_ws_routes(ws))
"""

import asyncio
import dataclasses
import json
import logging
from uuid import uuid4

from pydantic import PrivateAttr

from n3tx_actors.tx import TX
from n3tx_actors.api.network_adapter import NetworkAdapter
from n3tx_core.utils.registrar import registered_models
from n3tx_core import config
from n3tx_core.authorize.auth import decode_token

logger = logging.getLogger('n3tx.network.ws')

# Frontend UPPERCASE -> backend lowercase name mapping
_NAME_MAP = {
    'SCHEMA': 'schema',
    'CREATE': 'create',
    'READ': 'list',       # Frontend READ on collection = list
    'UPDATE': 'update',
    'DELETE': 'delete',
    'LOAD': 'schema',     # Frontend LOAD = schema fetch
}

# Keys in tx.meta that are not JSON-serializable (class references, etc.)
_NON_SERIALIZABLE_META = frozenset({'model_cls', 'sql_filter'})


class NetworkWebSocket(NetworkAdapter, auto_register=False):
    """WebSocket adapter. Bridges frontend Matrix to backend Matrix.

    Maintains persistent connections per client. Each connection stores
    the authenticated user (from JWT at connect time). Lifecycle events
    are broadcast to all connected clients.
    """

    _connections: dict = PrivateAttr(default_factory=dict)

    def __init__(self, **kwargs):
        kwargs.setdefault('addr', 'ws')
        super().__init__(**kwargs)

    # ── Protocol translation ──

    def _translate_incoming(self, msg: dict, user: dict) -> TX:
        """Translate a frontend TX dict to a backend TX.

        Frontend targets include full API URLs:
            http://localhost:5000/Product      -> target='products', name='schema'
            http://localhost:5000/products     -> target='products', name='list'
            http://localhost:5000/products/42  -> target='products', data.id=42

        Returns a TX ready for self.request().
        """
        name = msg.get('name', '')
        source = msg.get('source', '')
        target = msg.get('target', '')
        data = msg.get('data') or {}
        meta = msg.get('meta') or {}

        # Preserve original event info for response reconstruction
        original_name = name
        original_target = target
        original_source = source

        # 1. Strip API_URL prefix from target
        api_url = config.API_URL
        if target.startswith(api_url):
            target = target[len(api_url):].lstrip('/')

        # 2. Map frontend UPPERCASE name to backend lowercase
        backend_name = _NAME_MAP.get(name.upper(), name.lower())

        # 3. Resolve target: could be ClassName or tablename/id
        model_cls = None
        entity_id = None

        # Check if target is a ClassName (e.g., "Product")
        for tablename, cls in registered_models.items():
            if cls.__name__ == target:
                target = tablename
                model_cls = cls
                # ClassName target = schema request
                if backend_name in ('list', 'schema'):
                    backend_name = 'schema'
                break
        else:
            # Target is tablename or tablename/id path
            parts = target.split('/')
            tablename = parts[0]
            if tablename in registered_models:
                model_cls = registered_models[tablename]
                target = tablename
                if len(parts) >= 2 and parts[1]:
                    try:
                        entity_id = int(parts[1])
                    except ValueError:
                        pass

        # 4. Extract id into data if found in path
        if entity_id is not None:
            if isinstance(data, dict):
                data = {**data, 'id': entity_id}
            # For READ with an id, it's a get (not list)
            if backend_name == 'list' and entity_id:
                backend_name = 'get'

        # 5. Build meta with auth context
        tx_meta = {
            'user': user,
            'ws_source': original_source,
            'ws_target': original_target,
            'ws_name': original_name,
        }
        if model_cls:
            tx_meta['model_cls'] = model_cls
        # Carry through frontend meta (e.g., inbox override)
        for k, v in meta.items():
            if k not in tx_meta:
                tx_meta[k] = v

        return TX(
            name=backend_name,
            source=self.addr,
            target=target,
            data=data if isinstance(data, dict) else {},
            meta=tx_meta,
        )

    def _translate_outgoing(self, response: TX) -> dict:
        """Translate a backend response TX to frontend-compatible JSON.

        Reconstructs the source/target swap and name that the frontend
        httpCallback expects.
        """
        meta = response.meta or {}
        ws_source = meta.get('ws_source', '')
        ws_target = meta.get('ws_target', '')
        ws_name = meta.get('ws_name', '')

        # Use inbox override if present (matches httpCallback behavior)
        name = meta.get('inbox', ws_name) if not response.is_error else 'ERROR'

        # Build clean meta for wire (strip non-serializable keys)
        wire_meta = {
            k: v for k, v in meta.items()
            if k not in _NON_SERIALIZABLE_META
            and k not in ('ws_source', 'ws_target', 'ws_name')
        }

        return {
            'name': name,
            'source': ws_target,   # Response source = original target
            'target': ws_source,   # Response target = original source
            'data': response.data,
            'meta': wire_meta,
            'timestamp': response.timestamp,
        }

    # ── Connection management ──

    async def handle_message(self, client_id: str, msg: dict) -> dict | None:
        """Process a single message from a WebSocket client.

        Translates frontend TX -> backend TX, routes through Matrix,
        translates response back to frontend format.

        Returns None for streaming requests (sent directly via background task).
        """
        conn = self._connections.get(client_id)
        user = conn['user'] if conn else {}

        tx = self._translate_incoming(msg, user)

        is_stream = msg.get('meta', {}).get('stream', False)
        if is_stream:
            ws = conn['ws']
            asyncio.create_task(self._stream_to_ws(ws, tx))
            return None

        response = await self.request(tx, timeout=30.0)
        return self._translate_outgoing(response)

    async def _stream_to_ws(self, ws, tx: TX):
        """Stream chunks directly to a WebSocket client.

        Runs as a background task so the WebSocket message loop remains
        free for heartbeats and other requests during streaming.
        """
        try:
            async for chunk in self.stream(tx, timeout=120.0):
                response = self._translate_outgoing(chunk)
                response['meta'] = response.get('meta', {})
                response['meta']['stream'] = True
                if chunk.meta.get('stream_end'):
                    response['meta']['stream_end'] = True
                await ws.send_json(response)
        except Exception as e:
            logger.error("WS stream error: %s", e)
            try:
                await ws.send_json({
                    'name': 'ERROR', 'source': 'ws', 'target': '',
                    'data': {'message': str(e), 'code': 500},
                    'meta': {'error': True, 'stream_end': True},
                })
            except Exception:
                pass

    # ── Lifecycle event handler ──

    async def LIFECYCLE(self, data: dict, tx: TX):
        """Handle lifecycle events from ActorModel._publish_lifecycle.

        Broadcasts create/update/delete events to all connected clients.
        """
        event = data.get('event', '')
        entity = data.get('entity', {})

        # Map lifecycle event to frontend event name
        event_map = {
            'after_create': 'CREATE',
            'after_update': 'UPDATE',
            'after_delete': 'DELETE',
        }
        frontend_name = event_map.get(event, event.upper())

        broadcast = {
            'name': frontend_name,
            'source': tx.source,
            'target': '*',
            'data': entity,
            'meta': {'push': True, 'lifecycle': True},
            'timestamp': tx.timestamp,
        }

        # Broadcast to all connected clients
        dead_clients = []
        for client_id, conn in self._connections.items():
            try:
                await conn['ws'].send_json(broadcast)
            except Exception:
                dead_clients.append(client_id)

        # Clean up dead connections
        for client_id in dead_clients:
            self._connections.pop(client_id, None)
            logger.debug("Removed dead WebSocket connection: %s", client_id)


def create_ws_routes(ws_adapter: NetworkWebSocket):
    """Create FastAPI routes for WebSocket endpoint.

    Returns a FastAPI APIRouter with a single WebSocket endpoint at /ws.
    Clients connect with optional ?token=JWT for authentication.
    """
    from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

    router = APIRouter()

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket, token: str = Query(default=None)):
        # 1. Validate JWT if provided
        user = {}
        if token:
            try:
                user = decode_token(token)
            except Exception as e:
                logger.warning("WS auth failed: %s", e)
                # Accept anyway — anonymous access (schema requests etc.)

        # 2. Accept the connection
        await websocket.accept()
        client_id = uuid4().hex[:12]
        ws_adapter._connections[client_id] = {'ws': websocket, 'user': user}
        logger.info("WebSocket connected: %s (user=%s)", client_id,
                     user.get('email', 'anonymous'))

        try:
            while True:
                # 3. Receive and process messages
                raw = await websocket.receive_json()

                # Heartbeat handling
                if isinstance(raw, dict) and raw.get('heartbeat'):
                    await websocket.send_json({'heartbeat': True})
                    continue

                # Process TX message
                try:
                    response = await ws_adapter.handle_message(client_id, raw)
                    if response is not None:
                        await websocket.send_json(response)
                except Exception as e:
                    logger.error("WS message handling error: %s", e)
                    await websocket.send_json({
                        'name': 'ERROR',
                        'source': 'ws',
                        'target': raw.get('source', ''),
                        'data': {'message': str(e), 'code': 500},
                        'meta': {'error': True},
                    })

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected: %s", client_id)
        except Exception as e:
            logger.error("WebSocket error: %s", e)
        finally:
            ws_adapter._connections.pop(client_id, None)

    return router
