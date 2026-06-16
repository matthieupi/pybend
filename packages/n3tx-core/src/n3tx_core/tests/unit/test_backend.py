"""Tests for api/backend.py — BaseBackend and FastAPIBackend.

CG-1: Coverage gap — backend.py has zero test coverage.
Tests BaseBackend abstract interface and FastAPIBackend initialization.
"""

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from typing import ClassVar

from n3tx_core import config
from n3tx_core.api.backend import BaseBackend, FastAPIBackend

pytestmark = pytest.mark.unit



class TestBaseBackend:
    """BaseBackend is an abstract class — test via concrete subclass."""

    def test_cannot_instantiate_directly(self):
        """BaseBackend is abstract due to register_routes."""
        with pytest.raises(TypeError):
            BaseBackend(name="test", description="test", version="1.0.0")

    def test_register_routes_is_abstract(self):
        assert hasattr(BaseBackend, 'register_routes')


class TestFastAPIBackendInit:
    """FastAPIBackend creates a FastAPI app with CORS and JWT middleware."""

    def test_creates_fastapi_app(self):
        backend = FastAPIBackend(name="test", description="test", version="1.0.0")
        assert backend.app is not None

    def test_app_has_title(self):
        backend = FastAPIBackend(name="test", description="test", version="1.0.0")
        assert backend.app.title is not None

    def test_name_set_from_class(self):
        backend = FastAPIBackend(name="test", description="test", version="1.0.0")
        # __init__ sets name to lowercased class name
        assert backend.name == "fastapibackend"

    def test_version_set(self):
        backend = FastAPIBackend(name="test", description="test", version="1.0.0")
        assert backend.version == "1.0.0"

    def test_port_default(self):
        backend = FastAPIBackend(name="test", description="test", version="1.0.0")
        assert backend.port == 8000

    def test_registered_models_populated(self):
        backend = FastAPIBackend(name="test", description="test", version="1.0.0")
        assert isinstance(backend.registered_models, dict)


class TestFastAPIBackendAuthExempt:
    """AUTH_EXEMPT_PATHS and AUTH_EXEMPT_EXTENSIONS are class-level tuples."""

    def test_exempt_paths_include_login(self):
        assert "/login" in FastAPIBackend.AUTH_EXEMPT_PATHS

    def test_exempt_paths_include_register(self):
        assert "/register" in FastAPIBackend.AUTH_EXEMPT_PATHS

    def test_exempt_paths_include_docs(self):
        assert "/docs" in FastAPIBackend.AUTH_EXEMPT_PATHS

    def test_exempt_extensions_include_html(self):
        assert ".html" in FastAPIBackend.AUTH_EXEMPT_EXTENSIONS

    def test_exempt_extensions_include_js(self):
        assert ".js" in FastAPIBackend.AUTH_EXEMPT_EXTENSIONS

    def test_exempt_extensions_include_css(self):
        assert ".css" in FastAPIBackend.AUTH_EXEMPT_EXTENSIONS


class TestFastAPIBackendServiceAuth:
    """Service token requests can forward user context for distributed refs."""

    def test_service_token_sets_forwarded_user_context(self):
        old_token = config.SERVICE_TOKEN
        config.configure(service_token='service-secret')
        try:
            backend = FastAPIBackend(name="test", description="test", version="1.0.0")

            @backend.app.get('/service-whoami')
            async def service_whoami(request: Request):
                return {
                    'user': getattr(request.state, 'user', {}),
                    'service': getattr(request.state, 'service', None),
                }

            client = TestClient(backend.app)
            response = client.get('/service-whoami', headers={
                'Authorization': 'Bearer service-secret',
                'X-N3TX-Service': 'api-test',
                'X-N3TX-User': '{"user_id": 7, "role": "admin"}',
            })

            assert response.status_code == 200
            assert response.json() == {
                'user': {'user_id': 7, 'role': 'admin'},
                'service': 'api-test',
            }
        finally:
            config.configure(service_token=old_token)

    def test_service_header_requires_configured_token(self):
        old_token = config.SERVICE_TOKEN
        config.configure(service_token='service-secret')
        try:
            backend = FastAPIBackend(name="test", description="test", version="1.0.0")

            @backend.app.get('/service-protected')
            async def service_protected():
                return {'ok': True}

            client = TestClient(backend.app)
            response = client.get('/service-protected', headers={
                'Authorization': 'Bearer wrong',
                'X-N3TX-Service': 'api-test',
            })

            assert response.status_code == 401
            assert response.json() == {'detail': 'Invalid service token'}
        finally:
            config.configure(service_token=old_token)


class TestFastAPIBackendGetApp:
    """get_app() mounts static files and returns the app."""

    def test_get_app_returns_app(self):
        backend = FastAPIBackend(name="test", description="test", version="1.0.0")
        app = backend.get_app()
        assert app is backend.app

    def test_register_routes_is_callable(self):
        backend = FastAPIBackend(name="test", description="test", version="1.0.0")
        assert callable(backend.register_routes)
