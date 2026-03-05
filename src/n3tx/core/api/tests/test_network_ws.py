"""Tests for NetworkWebSocket adapter.

UNIT TESTS — protocol translation
  - test_init_default_addr_is_ws
  - test_init_custom_addr
  - test_translate_incoming_schema_from_classname
  - test_translate_incoming_list_from_tablename
  - test_translate_incoming_get_with_id_in_path
  - test_translate_incoming_create
  - test_translate_incoming_update_with_id
  - test_translate_incoming_delete_with_id
  - test_translate_incoming_strips_api_url
  - test_translate_incoming_custom_method
  - test_translate_incoming_preserves_meta
  - test_translate_outgoing_swaps_source_target
  - test_translate_outgoing_uses_inbox_override
  - test_translate_outgoing_error_sets_name_error
  - test_translate_outgoing_strips_non_serializable_meta

LIFECYCLE
  - test_lifecycle_broadcast_to_clients
  - test_lifecycle_cleans_dead_connections

INTEGRATION — full WebSocket round-trip
  - test_ws_connect_anonymous
  - test_ws_connect_with_token
  - test_ws_heartbeat
  - test_ws_schema_request
  - test_ws_crud_create
  - test_ws_crud_list
  - test_ws_crud_get
  - test_ws_crud_update
  - test_ws_crud_delete
  - test_ws_error_response
"""

import asyncio
import pytest
from contextlib import contextmanager
from typing import ClassVar, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import Field

from n3tx.core.actors.actor import Actor
from n3tx.core.actors.matrix import Matrix
from n3tx.core.actors.tx import TX
from n3tx.core.api.network_ws import (
    NetworkWebSocket,
    create_ws_routes,
    _NAME_MAP,
    _NON_SERIALIZABLE_META,
)
from n3tx.core.models.storable_mixin import StorableMixin
from n3tx.core.utils.decorators import expose_route

pytestmark = pytest.mark.unit


# ===================================================================
# Helpers
# ===================================================================

@contextmanager
def mock_method(instance, name, replacement):
    """Temporarily replace a method on a Pydantic BaseModel instance."""
    object.__setattr__(instance, name, replacement)
    try:
        yield replacement
    finally:
        object.__delattr__(instance, name)


class Product(StorableMixin, Actor, auto_register=False):
    """Mock product model for testing (named Product to match frontend targets)."""
    __tablename__: ClassVar[str] = 'products'
    __storable__: ClassVar[bool] = True

    name: str = Field(min_length=1, max_length=100)
    price: float = Field(ge=0, default=0)

    @classmethod
    def schema(cls):
        return {
            '__name__': 'Product',
            '__tablename__': 'products',
            'properties': {
                'id': {'type': 'integer'},
                'name': {'type': 'string'},
                'price': {'type': 'number'},
            },
            'required': ['name'],
        }

    @expose_route('/favorite', methods=['POST'])
    def favorite(self) -> str:
        return '{"status": "ok"}'

MockModel = Product  # Alias for backward reference


# ===================================================================
# TestNetworkWebSocketInit
# ===================================================================

class TestNetworkWebSocketInit:

    def test_init_default_addr_is_ws(self):
        ws = NetworkWebSocket()
        assert ws.addr == 'ws'

    def test_init_custom_addr(self):
        ws = NetworkWebSocket(addr='ws_custom')
        assert ws.addr == 'ws_custom'


# ===================================================================
# TestTranslateIncoming
# ===================================================================

class TestTranslateIncoming:
    """_translate_incoming() protocol translation."""

    def _make_ws(self):
        return NetworkWebSocket()

    @patch('n3tx.core.api.network_ws.config')
    @patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel})
    def test_translate_incoming_schema_from_classname(self, mock_config):
        """Target=ClassName should resolve to schema request on tablename."""
        mock_config.API_URL = 'http://localhost:5000'
        ws = self._make_ws()
        msg = {
            'name': 'SCHEMA',
            'source': 'N3TX/Product',
            'target': 'http://localhost:5000/Product',
            'data': {},
            'meta': {},
        }
        tx = ws._translate_incoming(msg, {'user_id': 1})
        assert tx.name == 'schema'
        assert tx.target == 'products'
        assert tx.source == 'ws'

    @patch('n3tx.core.api.network_ws.config')
    @patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel})
    def test_translate_incoming_list_from_tablename(self, mock_config):
        """Target=tablename with READ should become 'list'."""
        mock_config.API_URL = 'http://localhost:5000'
        ws = self._make_ws()
        msg = {
            'name': 'READ',
            'source': 'N3TX/Product',
            'target': 'http://localhost:5000/products',
            'data': {'limit': 20, 'offset': 0},
            'meta': {},
        }
        tx = ws._translate_incoming(msg, {})
        assert tx.name == 'list'
        assert tx.target == 'products'
        assert tx.data.get('limit') == 20

    @patch('n3tx.core.api.network_ws.config')
    @patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel})
    def test_translate_incoming_get_with_id_in_path(self, mock_config):
        """Target=tablename/42 with READ should become 'get' with id=42."""
        mock_config.API_URL = 'http://localhost:5000'
        ws = self._make_ws()
        msg = {
            'name': 'READ',
            'source': 'N3TX/Product',
            'target': 'http://localhost:5000/products/42',
            'data': {},
            'meta': {},
        }
        tx = ws._translate_incoming(msg, {})
        assert tx.name == 'get'
        assert tx.target == 'products'
        assert tx.data.get('id') == 42

    @patch('n3tx.core.api.network_ws.config')
    @patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel})
    def test_translate_incoming_create(self, mock_config):
        mock_config.API_URL = 'http://localhost:5000'
        ws = self._make_ws()
        msg = {
            'name': 'CREATE',
            'source': 'N3TX/Product',
            'target': 'http://localhost:5000/products',
            'data': {'name': 'Widget', 'price': 9.99},
            'meta': {},
        }
        tx = ws._translate_incoming(msg, {'user_id': 1})
        assert tx.name == 'create'
        assert tx.target == 'products'
        assert tx.data['name'] == 'Widget'

    @patch('n3tx.core.api.network_ws.config')
    @patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel})
    def test_translate_incoming_update_with_id(self, mock_config):
        mock_config.API_URL = 'http://localhost:5000'
        ws = self._make_ws()
        msg = {
            'name': 'UPDATE',
            'source': 'N3TX/Product',
            'target': 'http://localhost:5000/products/5',
            'data': {'name': 'Updated'},
            'meta': {},
        }
        tx = ws._translate_incoming(msg, {})
        assert tx.name == 'update'
        assert tx.target == 'products'
        assert tx.data['id'] == 5
        assert tx.data['name'] == 'Updated'

    @patch('n3tx.core.api.network_ws.config')
    @patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel})
    def test_translate_incoming_delete_with_id(self, mock_config):
        mock_config.API_URL = 'http://localhost:5000'
        ws = self._make_ws()
        msg = {
            'name': 'DELETE',
            'source': 'N3TX/Product',
            'target': 'http://localhost:5000/products/10',
            'data': {},
            'meta': {},
        }
        tx = ws._translate_incoming(msg, {})
        assert tx.name == 'delete'
        assert tx.target == 'products'
        assert tx.data['id'] == 10

    @patch('n3tx.core.api.network_ws.config')
    @patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel})
    def test_translate_incoming_strips_api_url(self, mock_config):
        """Should strip the API URL prefix from target."""
        mock_config.API_URL = 'http://localhost:5000'
        ws = self._make_ws()
        msg = {
            'name': 'SCHEMA',
            'source': 'N3TX/Product',
            'target': 'http://localhost:5000/Product',
            'data': {},
            'meta': {},
        }
        tx = ws._translate_incoming(msg, {})
        assert tx.target == 'products'

    @patch('n3tx.core.api.network_ws.config')
    @patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel})
    def test_translate_incoming_custom_method(self, mock_config):
        """Non-CRUD names should pass through as lowercase."""
        mock_config.API_URL = 'http://localhost:5000'
        ws = self._make_ws()
        msg = {
            'name': 'favorite',
            'source': 'N3TX/Product',
            'target': 'http://localhost:5000/products/3',
            'data': {},
            'meta': {},
        }
        tx = ws._translate_incoming(msg, {'user_id': 1})
        assert tx.name == 'favorite'
        assert tx.data['id'] == 3

    @patch('n3tx.core.api.network_ws.config')
    @patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel})
    def test_translate_incoming_preserves_meta(self, mock_config):
        """Frontend meta fields should carry through."""
        mock_config.API_URL = 'http://localhost:5000'
        ws = self._make_ws()
        msg = {
            'name': 'READ',
            'source': 'N3TX/Product',
            'target': 'http://localhost:5000/products',
            'data': {},
            'meta': {'inbox': 'DESCRIBE', 'custom_key': 'custom_value'},
        }
        tx = ws._translate_incoming(msg, {})
        assert tx.meta.get('inbox') == 'DESCRIBE'
        assert tx.meta.get('custom_key') == 'custom_value'


# ===================================================================
# TestTranslateOutgoing
# ===================================================================

class TestTranslateOutgoing:
    """_translate_outgoing() response translation."""

    def _make_ws(self):
        return NetworkWebSocket()

    def test_translate_outgoing_swaps_source_target(self):
        """Response should swap source/target to match frontend expectation."""
        ws = self._make_ws()
        response = TX(
            name='list_RESPONSE',
            source='products',
            target='ws',
            data={'data': [], 'meta': {'total': 0}},
            meta={
                'ws_source': 'N3TX/Product',
                'ws_target': 'http://localhost:5000/products',
                'ws_name': 'READ',
            },
        )
        result = ws._translate_outgoing(response)
        assert result['source'] == 'http://localhost:5000/products'
        assert result['target'] == 'N3TX/Product'

    def test_translate_outgoing_uses_inbox_override(self):
        """When meta.inbox is set, use it as the response name."""
        ws = self._make_ws()
        response = TX(
            name='list_RESPONSE',
            source='products',
            target='ws',
            data=[],
            meta={
                'ws_source': 'N3TX/Product',
                'ws_target': 'http://localhost:5000/products',
                'ws_name': 'READ',
                'inbox': 'DESCRIBE',
            },
        )
        result = ws._translate_outgoing(response)
        assert result['name'] == 'DESCRIBE'

    def test_translate_outgoing_error_sets_name_error(self):
        """Error TX should produce name='ERROR'."""
        ws = self._make_ws()
        response = TX(
            name='ERROR',
            source='products',
            target='ws',
            data={'message': 'Not found', 'code': 404},
            meta={
                'error': True,
                'ws_source': 'N3TX/Product',
                'ws_target': 'http://localhost:5000/products/999',
                'ws_name': 'READ',
            },
        )
        result = ws._translate_outgoing(response)
        assert result['name'] == 'ERROR'
        assert result['data']['code'] == 404

    def test_translate_outgoing_strips_non_serializable_meta(self):
        """model_cls and sql_filter should not appear in wire meta."""
        ws = self._make_ws()
        response = TX(
            name='list_RESPONSE',
            source='products',
            target='ws',
            data=[],
            meta={
                'ws_source': 'N3TX/Product',
                'ws_target': 'http://localhost:5000/products',
                'ws_name': 'READ',
                'model_cls': MockModel,
                'sql_filter': 'user_owner = 1',
                'user': {'user_id': 1},
            },
        )
        result = ws._translate_outgoing(response)
        assert 'model_cls' not in result['meta']
        assert 'sql_filter' not in result['meta']
        assert result['meta'].get('user') == {'user_id': 1}


# ===================================================================
# TestLifecycleBroadcast
# ===================================================================

class TestLifecycleBroadcast:
    """LIFECYCLE event broadcasting."""

    @pytest.mark.asyncio
    async def test_lifecycle_broadcast_to_clients(self):
        """LIFECYCLE TX should broadcast to all connected clients."""
        ws = NetworkWebSocket()
        # Mock two connected clients
        ws1_mock = AsyncMock()
        ws2_mock = AsyncMock()
        ws._connections = {
            'client1': {'ws': ws1_mock, 'user': {}},
            'client2': {'ws': ws2_mock, 'user': {}},
        }

        tx = TX(
            name='LIFECYCLE',
            source='products',
            target='ws',
            data={'event': 'after_create', 'entity': {'id': 1, 'name': 'New'}},
        )

        await ws.LIFECYCLE(tx.data, tx)

        # Both clients should receive the broadcast
        assert ws1_mock.send_json.call_count == 1
        assert ws2_mock.send_json.call_count == 1
        sent = ws1_mock.send_json.call_args[0][0]
        assert sent['name'] == 'CREATE'
        assert sent['meta']['push'] is True
        assert sent['data']['id'] == 1

    @pytest.mark.asyncio
    async def test_lifecycle_cleans_dead_connections(self):
        """Dead connections should be removed during broadcast."""
        ws = NetworkWebSocket()
        live_mock = AsyncMock()
        dead_mock = AsyncMock()
        dead_mock.send_json.side_effect = Exception("Connection closed")
        ws._connections = {
            'live': {'ws': live_mock, 'user': {}},
            'dead': {'ws': dead_mock, 'user': {}},
        }

        tx = TX(
            name='LIFECYCLE',
            source='products',
            target='ws',
            data={'event': 'after_delete', 'entity': {'id': 5}},
        )

        await ws.LIFECYCLE(tx.data, tx)

        # Dead client should be removed
        assert 'dead' not in ws._connections
        assert 'live' in ws._connections
        assert live_mock.send_json.call_count == 1


# ===================================================================
# TestHandleMessage
# ===================================================================

class TestHandleMessage:
    """handle_message() end-to-end message processing."""

    @pytest.mark.asyncio
    async def test_handle_message_schema(self):
        """Should process a schema request and return translated response."""
        ws = NetworkWebSocket()
        ws._connections = {
            'test': {'ws': AsyncMock(), 'user': {'user_id': 1}},
        }
        schema_data = MockModel.schema()

        async def mock_request(tx, timeout=30.0):
            assert tx.name == 'schema'
            assert tx.target == 'products'
            return tx.reply(data=schema_data)

        with mock_method(ws, 'request', mock_request), \
             patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel}), \
             patch('n3tx.core.api.network_ws.config') as mock_config:
            mock_config.API_URL = 'http://localhost:5000'
            result = await ws.handle_message('test', {
                'name': 'SCHEMA',
                'source': 'N3TX/Product',
                'target': 'http://localhost:5000/Product',
                'data': {},
                'meta': {},
            })

        assert result['source'] == 'http://localhost:5000/Product'
        assert result['target'] == 'N3TX/Product'
        assert result['data']['__tablename__'] == 'products'


# ===================================================================
# TestIntegrationWebSocket
# ===================================================================

class TestIntegrationWebSocket:
    """Integration tests using FastAPI TestClient.websocket_connect()."""

    def _make_app(self, ws_adapter):
        """Create a FastAPI app with WS route."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(create_ws_routes(ws_adapter))
        return app

    def test_ws_connect_anonymous(self):
        """Should accept connection without token."""
        Actor.__matrix__ = None
        m = Matrix()
        ws = NetworkWebSocket()
        m.register(ws)

        app = self._make_app(ws)
        from fastapi.testclient import TestClient
        client = TestClient(app)

        with client.websocket_connect('/ws') as websocket:
            # Send heartbeat to confirm connection works
            websocket.send_json({'heartbeat': True})
            resp = websocket.receive_json()
            assert resp.get('heartbeat') is True

    def test_ws_connect_with_token(self):
        """Should accept connection with valid JWT token."""
        Actor.__matrix__ = None
        m = Matrix()
        ws = NetworkWebSocket()
        m.register(ws)

        # Mock token decoding
        app = self._make_app(ws)
        from fastapi.testclient import TestClient
        client = TestClient(app)

        with patch('n3tx.core.api.network_ws.decode_token',
                   return_value={'user_id': 1, 'email': 'test@example.com'}):
            with client.websocket_connect('/ws?token=valid_jwt') as websocket:
                websocket.send_json({'heartbeat': True})
                resp = websocket.receive_json()
                assert resp.get('heartbeat') is True

    def test_ws_heartbeat(self):
        """Heartbeat messages should get heartbeat response."""
        Actor.__matrix__ = None
        m = Matrix()
        ws = NetworkWebSocket()
        m.register(ws)

        app = self._make_app(ws)
        from fastapi.testclient import TestClient
        client = TestClient(app)

        with client.websocket_connect('/ws') as websocket:
            websocket.send_json({'heartbeat': True})
            resp = websocket.receive_json()
            assert resp == {'heartbeat': True}

    def test_ws_schema_request(self):
        """SCHEMA request should return model schema."""
        Actor.__matrix__ = None
        m = Matrix()
        ws = NetworkWebSocket()
        m.register(ws)

        schema_data = MockModel.schema()

        async def mock_request(tx, timeout=30.0):
            return tx.reply(data=schema_data)

        app = self._make_app(ws)
        from fastapi.testclient import TestClient
        client = TestClient(app)

        with mock_method(ws, 'request', mock_request), \
             patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel}), \
             patch('n3tx.core.api.network_ws.config') as mock_config:
            mock_config.API_URL = 'http://localhost:5000'

            with client.websocket_connect('/ws') as websocket:
                websocket.send_json({
                    'name': 'SCHEMA',
                    'source': 'N3TX/Product',
                    'target': 'http://localhost:5000/Product',
                    'data': {},
                    'meta': {},
                })
                resp = websocket.receive_json()

        assert resp['data']['__tablename__'] == 'products'
        assert resp['source'] == 'http://localhost:5000/Product'
        assert resp['target'] == 'N3TX/Product'

    def test_ws_crud_create(self):
        """CREATE request should route through adapter."""
        Actor.__matrix__ = None
        m = Matrix()
        ws = NetworkWebSocket()
        m.register(ws)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'id': 1, 'name': 'Widget', 'price': 9.99})

        app = self._make_app(ws)
        from fastapi.testclient import TestClient
        client = TestClient(app)

        with mock_method(ws, 'request', mock_request), \
             patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel}), \
             patch('n3tx.core.api.network_ws.config') as mock_config:
            mock_config.API_URL = 'http://localhost:5000'

            with client.websocket_connect('/ws') as websocket:
                websocket.send_json({
                    'name': 'CREATE',
                    'source': 'N3TX/Product',
                    'target': 'http://localhost:5000/products',
                    'data': {'name': 'Widget', 'price': 9.99},
                    'meta': {},
                })
                resp = websocket.receive_json()

        assert captured_tx.name == 'create'
        assert captured_tx.target == 'products'
        assert resp['data']['id'] == 1

    def test_ws_crud_list(self):
        """READ on collection should produce list TX."""
        Actor.__matrix__ = None
        m = Matrix()
        ws = NetworkWebSocket()
        m.register(ws)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'data': [], 'meta': {'total': 0}})

        app = self._make_app(ws)
        from fastapi.testclient import TestClient
        client = TestClient(app)

        with mock_method(ws, 'request', mock_request), \
             patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel}), \
             patch('n3tx.core.api.network_ws.config') as mock_config:
            mock_config.API_URL = 'http://localhost:5000'

            with client.websocket_connect('/ws') as websocket:
                websocket.send_json({
                    'name': 'READ',
                    'source': 'N3TX/Product',
                    'target': 'http://localhost:5000/products',
                    'data': {'limit': 20},
                    'meta': {},
                })
                resp = websocket.receive_json()

        assert captured_tx.name == 'list'
        assert captured_tx.data.get('limit') == 20

    def test_ws_crud_get(self):
        """READ with id in path should produce get TX."""
        Actor.__matrix__ = None
        m = Matrix()
        ws = NetworkWebSocket()
        m.register(ws)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'id': 5, 'name': 'Item', 'price': 10.0})

        app = self._make_app(ws)
        from fastapi.testclient import TestClient
        client = TestClient(app)

        with mock_method(ws, 'request', mock_request), \
             patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel}), \
             patch('n3tx.core.api.network_ws.config') as mock_config:
            mock_config.API_URL = 'http://localhost:5000'

            with client.websocket_connect('/ws') as websocket:
                websocket.send_json({
                    'name': 'READ',
                    'source': 'N3TX/Product',
                    'target': 'http://localhost:5000/products/5',
                    'data': {},
                    'meta': {},
                })
                resp = websocket.receive_json()

        assert captured_tx.name == 'get'
        assert captured_tx.data['id'] == 5

    def test_ws_crud_update(self):
        """UPDATE with id should route correctly."""
        Actor.__matrix__ = None
        m = Matrix()
        ws = NetworkWebSocket()
        m.register(ws)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'id': 5, 'name': 'Updated'})

        app = self._make_app(ws)
        from fastapi.testclient import TestClient
        client = TestClient(app)

        with mock_method(ws, 'request', mock_request), \
             patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel}), \
             patch('n3tx.core.api.network_ws.config') as mock_config:
            mock_config.API_URL = 'http://localhost:5000'

            with client.websocket_connect('/ws') as websocket:
                websocket.send_json({
                    'name': 'UPDATE',
                    'source': 'N3TX/Product',
                    'target': 'http://localhost:5000/products/5',
                    'data': {'name': 'Updated'},
                    'meta': {},
                })
                resp = websocket.receive_json()

        assert captured_tx.name == 'update'
        assert captured_tx.data['id'] == 5
        assert captured_tx.data['name'] == 'Updated'

    def test_ws_crud_delete(self):
        """DELETE with id should route correctly."""
        Actor.__matrix__ = None
        m = Matrix()
        ws = NetworkWebSocket()
        m.register(ws)

        captured_tx = None

        async def mock_request(tx, timeout=30.0):
            nonlocal captured_tx
            captured_tx = tx
            return tx.reply(data={'deleted': 10})

        app = self._make_app(ws)
        from fastapi.testclient import TestClient
        client = TestClient(app)

        with mock_method(ws, 'request', mock_request), \
             patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel}), \
             patch('n3tx.core.api.network_ws.config') as mock_config:
            mock_config.API_URL = 'http://localhost:5000'

            with client.websocket_connect('/ws') as websocket:
                websocket.send_json({
                    'name': 'DELETE',
                    'source': 'N3TX/Product',
                    'target': 'http://localhost:5000/products/10',
                    'data': {},
                    'meta': {},
                })
                resp = websocket.receive_json()

        assert captured_tx.name == 'delete'
        assert captured_tx.data['id'] == 10

    def test_ws_error_response(self):
        """Error TX should produce ERROR response over WS."""
        Actor.__matrix__ = None
        m = Matrix()
        ws = NetworkWebSocket()
        m.register(ws)

        async def mock_request(tx, timeout=30.0):
            return tx.error('Not found', code=404)

        app = self._make_app(ws)
        from fastapi.testclient import TestClient
        client = TestClient(app)

        with mock_method(ws, 'request', mock_request), \
             patch('n3tx.core.api.network_ws.registered_models', {'products': MockModel}), \
             patch('n3tx.core.api.network_ws.config') as mock_config:
            mock_config.API_URL = 'http://localhost:5000'

            with client.websocket_connect('/ws') as websocket:
                websocket.send_json({
                    'name': 'READ',
                    'source': 'N3TX/Product',
                    'target': 'http://localhost:5000/products/999',
                    'data': {},
                    'meta': {},
                })
                resp = websocket.receive_json()

        assert resp['name'] == 'ERROR'
        assert resp['data']['code'] == 404
        assert 'Not found' in resp['data']['message']
