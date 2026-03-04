import logging
import os
from typing import Any, ClassVar

from n3tx.core.utils.registrar import registered_models

# app/adapters/base_adapter.py

from abc import ABC, abstractmethod

from pydantic import BaseModel

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

    class Config:
        orm_mode = True

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

        from n3tx.core.config import DEBUG
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
            from n3tx.core.tests.profiling.middleware import ProfilingMiddleware
            self.app.add_middleware(ProfilingMiddleware)

    def _add_auth_middleware(self):
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import JSONResponse
        from n3tx.core.authorize import decode_token

        exempt_paths = self.AUTH_EXEMPT_PATHS
        exempt_extensions = self.AUTH_EXEMPT_EXTENSIONS
        models = self.registered_models

        class JWTAuthMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                path = request.url.path

                # Skip token processing for static files
                if any(path.endswith(ext) for ext in exempt_extensions):
                    return await call_next(request)

                # Extract and validate token if present.
                # Route handlers enforce authorization via ABAC rules;
                # the middleware only decodes identity.
                token = request.headers.get("x-access-token")
                if token:
                    try:
                        payload = decode_token(token)
                        request.state.user = payload
                    except Exception:
                        return JSONResponse(
                            status_code=401,
                            content={"detail": "Invalid or expired token"},
                        )
                else:
                    request.state.user = {}

                return await call_next(request)

        self.app.add_middleware(JWTAuthMiddleware)

    def register_routes(self, registered_models: dict[str, type]):
        from n3tx.core.api.routes_fastapi import register_routes, register_route
        from n3tx.core.api.routes_fastapi import router
        register_routes()
        self.app.include_router(router)

    def _mount_static(self, app_static_dirs=None):
        import os
        from pathlib import Path
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import FileResponse

        ssr_active = self._ssr_mode != 'off'
        static_dir = Path(__file__).resolve().parent.parent.parent / "static"
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

        if not static_dir.is_dir():
            if ssr_active and index_html_path:
                self._mount_ssr_route(index_html_path, app_static_dirs)
            elif index_html_path:
                # Non-SSR: serve index.html at GET /
                self.app.get("/", include_in_schema=False)(
                    lambda _path=str(index_html_path): FileResponse(_path)
                )
            return

        # Serve framework HTML pages at the root
        for html_file in ("schema.html", "example.html", "index.html", "login.html", "register.html"):
            html_path = static_dir / html_file
            if html_path.exists():
                # Track index.html for SSR interception and GET / route
                if html_file == 'index.html':
                    if index_html_path is None:
                        index_html_path = html_path
                    if ssr_active:
                        continue  # SSR route handles it
                self.app.get(f"/{html_file}", include_in_schema=False)(
                    lambda _path=str(html_path): FileResponse(_path)
                )

        # Mount SSR route for index.html (dynamic, with injected content)
        if ssr_active and index_html_path:
            self._mount_ssr_route(index_html_path, app_static_dirs)
        elif index_html_path:
            # Non-SSR: serve index.html at GET /
            self.app.get("/", include_in_schema=False)(
                lambda _path=str(index_html_path): FileResponse(_path)
            )

        # Mount the framework static directory so JS/CSS imports resolve
        self.app.mount("/", StaticFiles(directory=str(static_dir)), name="static")

    def _mount_ssr_route(self, html_path, app_static_dirs=None):
        """Mount a dynamic route for index.html with SSR content injection.

        Supports four modes via ``self._ssr_mode``:
        - ``"schema"`` — inject model schema tags
        - ``"bundle"`` — replace module imports with a single JS bundle
        - ``"full"`` — both schema tags and JS bundle
        """
        from pathlib import Path
        from fastapi.responses import HTMLResponse
        from n3tx.core.ssr import inject_schemas, inject_bundle, inject_full, inject_css_preloads
        from n3tx.core.ssr.bundler import build_bundle, discover_css_deps

        # Read HTML once at startup
        with open(html_path) as f:
            html_template = f.read()

        models = self.registered_models
        mode = self._ssr_mode
        cache = {}

        # Build the list of static directories for the bundler
        static_dirs = list(app_static_dirs or [])
        framework_static = Path(__file__).resolve().parent.parent.parent / "static"
        if framework_static.is_dir():
            static_dirs.append(str(framework_static))

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
        from n3tx.core.api.routes_flask import create_api_blueprint
        blueprint = create_api_blueprint(registered_models)
        self.app.register_blueprint(blueprint)

    def get_app(self):
        from asgiref.wsgi import WsgiToAsgi
        return WsgiToAsgi(self.app)

