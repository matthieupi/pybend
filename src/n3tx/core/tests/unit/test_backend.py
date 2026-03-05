"""Tests for api/backend.py — BaseBackend and FastAPIBackend.

CG-1: Coverage gap — backend.py has zero test coverage.
Tests BaseBackend abstract interface and FastAPIBackend initialization.
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import ClassVar

from n3tx.core.api.backend import BaseBackend, FastAPIBackend

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


class TestFastAPIBackendGetApp:
    """get_app() mounts static files and returns the app."""

    def test_get_app_returns_app(self):
        backend = FastAPIBackend(name="test", description="test", version="1.0.0")
        app = backend.get_app()
        assert app is backend.app

    def test_register_routes_is_callable(self):
        backend = FastAPIBackend(name="test", description="test", version="1.0.0")
        assert callable(backend.register_routes)
