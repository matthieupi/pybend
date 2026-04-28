import logging
import os
from typing import Any, ClassVar

from n3tx_core.utils.registrar import registered_models

# app/adapters/base_adapter.py

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger('n3tx.api')

class BaseBackend(ABC, BaseModel):
    """
    Base model for backend adapters.
    """
    name: str
    description: str
    version: str
    port: int = 8000

    app: Any = None
    registered_models: dict[str, type] = {}

    model_config = ConfigDict(from_attributes=True)

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.registered_models = registered_models
        self.name = self.__class__.__name__.lower()
        self.description = f"{self.__class__.__name__} backend"
        self.version = "1.0.0"
        self.port = 8000

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)


    @abstractmethod
    def register_routes(self, registered_models: dict[str, type]):
        pass


class _CascadingStaticFiles:
    """ASGI handler that searches multiple directories for static files.

    Looks up the requested path across all directories; the first match
    wins.  This allows split packages (n3tx-agents, n3tx-ui, n3tx-core)
    to each contribute static assets under the same URL namespace.
    """

    def __init__(self, directories):
        from pathlib import Path
        self._directories = [Path(d) for d in directories]
        # Keep a single StaticFiles per directory for proper MIME handling
        from fastapi.staticfiles import StaticFiles
        self._apps = {
            str(d): StaticFiles(directory=str(d))
            for d in self._directories
        }

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return

        path = scope.get("path", "/").lstrip("/")
        if not path:
            path = "index.html"

        # Find which directory contains this file
        for d in self._directories:
            candidate = d / path
            if candidate.is_file():
                await self._apps[str(d)](scope, receive, send)
                return

        # Not found in any directory — let last dir's StaticFiles handle 404
        if self._apps:
            last = list(self._apps.values())[-1]
            await last(scope, receive, send)


# app/backends/fastapi_backend.py
class FastAPIBackend(BaseBackend):
    # Paths that do not require authentication
    AUTH_EXEMPT_PATHS: ClassVar[tuple] = ("/login", "/register", "/docs", "/openapi.json", "/redoc")
    AUTH_EXEMPT_EXTENSIONS: ClassVar[tuple] = (".html", ".js", ".css", ".png", ".ico", ".svg", ".woff", ".woff2", ".ttf")

    def __init__(self, cors_origins: list = None, ssr_mode: str = 'off', **data):
        super().__init__(**data)
        self._ssr_mode = ssr_mode
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        if cors_origins is None:
            cors_origins = ["*"]

        if "*" in cors_origins:
            logger.warning("CORS allows all origins ('*'). Set explicit origins for production.")

        from n3tx_core.config import DEBUG
        self.app = FastAPI(
            title=self.name,
            version=self.version,
            description=self.description,
            docs_url="/docs" if DEBUG else None,
            redoc_url="/redoc" if DEBUG else None,
        )
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials="*" not in cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._add_auth_middleware()

        if os.getenv('N3TX_PROFILING', '').lower() in ('1', 'true'):
            from n3tx_core.tests.profiling.middleware import ProfilingMiddleware
            self.app.add_middleware(ProfilingMiddleware)

        if DEBUG:
            self._add_debug_logging_middleware()

    def _add_auth_middleware(self):
        from starlette.responses import JSONResponse
        from starlette.types import ASGIApp, Receive, Scope, Send
        from n3tx_core.authorize import decode_token

        exempt_extensions = self.AUTH_EXEMPT_EXTENSIONS

        class JWTAuthMiddleware:
            """Pure ASGI middleware — no BaseHTTPMiddleware buffering.

            BaseHTTPMiddleware buffers response bodies through an intermediate
            channel, which breaks SSE / StreamingResponse.  This raw ASGI
            implementation passes responses straight through.
            """

            def __init__(self, app: ASGIApp):
                self.app = app

            async def __call__(self, scope: Scope, receive: Receive, send: Send):
                if scope["type"] != "http":
                    await self.app(scope, receive, send)
                    return

                path = scope.get("path", "")

                # Skip token processing for static files
                if any(path.endswith(ext) for ext in exempt_extensions):
                    await self.app(scope, receive, send)
                    return

                # Extract and validate token if present.
                headers = dict(
                    (k.decode(), v.decode())
                    for k, v in scope.get("headers", [])
                )
                token = headers.get("x-access-token")
                state = scope.setdefault("state", {})

                if token:
                    try:
                        payload = decode_token(token)
                        state["user"] = payload
                    except Exception:
                        response = JSONResponse(
                            status_code=401,
                            content={"detail": "Invalid or expired token"},
                        )
                        await response(scope, receive, send)
                        return
                else:
                    state["user"] = {}

                await self.app(scope, receive, send)

        self.app.add_middleware(JWTAuthMiddleware)

    def _add_debug_logging_middleware(self):
        import time
        from starlette.types import ASGIApp, Receive, Scope, Send

        exempt_extensions = self.AUTH_EXEMPT_EXTENSIONS

        class DebugLoggingMiddleware:
            """Pure ASGI debug logger — no BaseHTTPMiddleware buffering."""

            def __init__(self, app: ASGIApp):
                self.app = app

            async def __call__(self, scope: Scope, receive: Receive, send: Send):
                if scope["type"] != "http":
                    await self.app(scope, receive, send)
                    return

                path = scope.get("path", "")
                if any(path.endswith(ext) for ext in exempt_extensions):
                    await self.app(scope, receive, send)
                    return

                start = time.monotonic()
                status_code = None

                async def send_wrapper(message):
                    nonlocal status_code
                    if message["type"] == "http.response.start":
                        status_code = message.get("status", 0)
                    await send(message)

                await self.app(scope, receive, send_wrapper)

                elapsed = (time.monotonic() - start) * 1000
                state = scope.get("state", {})
                user = state.get("user", {}) if isinstance(state, dict) else {}
                user_id = user.get('user_id', '-')
                method = scope.get("method", "?")

                logger.info(
                    "[DEBUG] %s %s -> %s (%.1fms) user=%s",
                    method, path, status_code, elapsed, user_id,
                )

        self.app.add_middleware(DebugLoggingMiddleware)

    def register_routes(self, registered_models: dict[str, type]):
        from n3tx_core.api.routes_fastapi import register_routes, register_route
        from n3tx_core.api.routes_fastapi import router
        register_routes()
        self.app.include_router(router)

    @staticmethod
    def _discover_static_dirs():
        """Discover static directories from installed N3TX packages.

        Returns directories in priority order (highest first):
            1. n3tx-agents static (if installed)
            2. n3tx-ui static (if installed)
            3. n3tx-core static (always present)
        """
        import importlib
        from pathlib import Path

        dirs = []
        # Optional packages first (higher priority)
        for pkg_name in ('n3tx_agents', 'n3tx_ui'):
            try:
                mod = importlib.import_module(pkg_name)
                pkg_static = Path(mod.__file__).parent / "static"
                if pkg_static.is_dir():
                    dirs.append(pkg_static)
            except ImportError:
                pass
        # Core static last (catch-all)
        core_static = Path(__file__).resolve().parent.parent / "static"
        if core_static.is_dir():
            dirs.append(core_static)
        return dirs

    def _mount_static(self, app_static_dirs=None):
        from pathlib import Path
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import FileResponse

        ssr_active = self._ssr_mode != 'off'
        framework_dirs = self._discover_static_dirs()
        index_html_path = None  # Track for SSR and GET / route

        # Serve files from app-specific static directories as explicit routes.
        # These take precedence over the framework catch-all mount, allowing
        # app HTML pages and components to live alongside framework statics.
        for app_dir in (app_static_dirs or []):
            app_path = Path(app_dir)
            if not app_path.is_dir():
                continue
            for file_path in app_path.rglob("*"):
                if not file_path.is_file():
                    continue
                # URL path relative to the app static root
                rel = file_path.relative_to(app_path)
                url_path = "/" + "/".join(rel.parts)
                # Track index.html for SSR interception and GET / route
                if file_path.name == 'index.html' and len(rel.parts) == 1:
                    index_html_path = file_path
                    if ssr_active:
                        continue  # SSR route handles it
                self.app.get(url_path, include_in_schema=False)(
                    lambda _path=str(file_path): FileResponse(_path)
                )

        if not framework_dirs:
            if ssr_active and index_html_path:
                self._mount_ssr_route(index_html_path, app_static_dirs)
            elif index_html_path:
                # Non-SSR: serve index.html at GET /
                self.app.get("/", include_in_schema=False)(
                    lambda _path=str(index_html_path): FileResponse(_path)
                )
            return

        # Serve framework HTML pages at the root (search all package dirs)
        for html_file in ("schema.html", "example.html", "index.html", "login.html", "register.html"):
            for static_dir in framework_dirs:
                html_path = static_dir / html_file
                if html_path.exists():
                    # Track index.html for SSR interception and GET / route
                    if html_file == 'index.html':
                        if index_html_path is None:
                            index_html_path = html_path
                        if ssr_active:
                            break  # SSR route handles it
                    self.app.get(f"/{html_file}", include_in_schema=False)(
                        lambda _path=str(html_path): FileResponse(_path)
                    )
                    break  # First match wins

        # Mount SSR route for index.html (dynamic, with injected content)
        if ssr_active and index_html_path:
            self._mount_ssr_route(index_html_path, app_static_dirs)
        elif index_html_path:
            # Non-SSR: serve index.html at GET /
            self.app.get("/", include_in_schema=False)(
                lambda _path=str(index_html_path): FileResponse(_path)
            )

        # Mount framework static directories so JS/CSS imports resolve.
        # Use a cascading handler that searches all package dirs.
        if len(framework_dirs) == 1:
            self.app.mount("/", StaticFiles(directory=str(framework_dirs[0])), name="static")
        else:
            self.app.mount("/", _CascadingStaticFiles(directories=framework_dirs), name="static")

    def _mount_ssr_route(self, html_path, app_static_dirs=None):
        """Mount a dynamic route for index.html with SSR content injection.

        Supports four modes via ``self._ssr_mode``:
        - ``"schema"`` — inject model schema tags
        - ``"bundle"`` — replace module imports with a single JS bundle
        - ``"full"`` — both schema tags and JS bundle
        """
        from pathlib import Path
        from fastapi.responses import HTMLResponse
        from n3tx_core.ssr import inject_schemas, inject_bundle, inject_full, inject_css_preloads
        from n3tx_core.ssr.bundler import build_bundle, discover_css_deps

        # Read HTML once at startup
        with open(html_path) as f:
            html_template = f.read()

        models = self.registered_models
        mode = self._ssr_mode
        cache = {}

        # Build the list of static directories for the bundler
        static_dirs = list(app_static_dirs or [])
        for fdir in self._discover_static_dirs():
            static_dirs.append(str(fdir))

        def _build_ssr_html():
            if 'html' not in cache:
                html = html_template

                if mode == 'schema':
                    css_deps = discover_css_deps(static_dirs)
                    html = inject_css_preloads(html, css_deps)
                    html = inject_schemas(html, models)
                elif mode == 'bundle':
                    bundle_js = build_bundle(
                        html_path, static_dirs,
                    )
                    html = inject_bundle(html, bundle_js)
                elif mode == 'full':
                    bundle_js = build_bundle(
                        html_path, static_dirs,
                    )
                    html = inject_full(html, models, bundle_js)

                cache['html'] = html
            return cache['html']

        async def ssr_handler():
            return HTMLResponse(_build_ssr_html())

        self.app.get("/", include_in_schema=False)(ssr_handler)
        self.app.get("/index.html", include_in_schema=False)(ssr_handler)

    def get_app(self, app_static_dirs=None):
        # Mount static last so HTML routes take precedence over the catch-all mount
        self._mount_static(app_static_dirs=app_static_dirs)
        return self.app


# app/backends/flask_backend.py
class FlaskBackend(BaseBackend):
    def __init__(self, **data):
        super().__init__(**data)
        from flask import Flask
        from flasgger import Swagger
        self.app = Flask(__name__, static_url_path='/static', static_folder='static', template_folder='templates')
        self.app.config['SWAGGER'] = {'title': 'N3TX Flask API', 'uiversion': 3}
        Swagger(self.app)

    def register_routes(self, registered_models: dict[str, type]):
        from n3tx_core.api.routes_flask import create_api_blueprint
        blueprint = create_api_blueprint(registered_models)
        self.app.register_blueprint(blueprint)

    def get_app(self):
        from asgiref.wsgi import WsgiToAsgi
        return WsgiToAsgi(self.app)
