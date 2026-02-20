from typing import Any, ClassVar

from utils.registrar import registered_models

# app/adapters/base_adapter.py

from abc import ABC, abstractmethod

from pydantic import BaseModel

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

    def __init__(self, **data):
        super().__init__(**data)
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        self.app = FastAPI(
            title=self.name,
            version=self.version,
            description=self.description
        )
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._add_auth_middleware()

    def _add_auth_middleware(self):
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import JSONResponse
        from authorize import decode_token

        exempt_paths = self.AUTH_EXEMPT_PATHS
        exempt_extensions = self.AUTH_EXEMPT_EXTENSIONS

        class JWTAuthMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                path = request.url.path

                # Skip auth for exempt paths and static files
                if any(path.endswith(ext) for ext in exempt_extensions):
                    return await call_next(request)
                if any(exempt in path for exempt in exempt_paths):
                    return await call_next(request)

                token = request.headers.get("x-access-token")
                if not token:
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Missing authentication token"},
                    )
                try:
                    payload = decode_token(token)
                    request.state.user = payload
                except Exception:
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid or expired token"},
                    )
                return await call_next(request)

        self.app.add_middleware(JWTAuthMiddleware)

    def register_routes(self, registered_models: dict[str, type]):
        from api.routes_fastapi import register_routes, register_route
        from api.routes_fastapi import router
        register_routes()
        self.app.include_router(router)

    def _mount_static(self):
        import os
        from pathlib import Path
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import FileResponse

        static_dir = Path(__file__).resolve().parent.parent.parent / "static" / "NTT0.6"
        if not static_dir.is_dir():
            return

        # Serve HTML pages at the root
        for html_file in ("schema.html", "example.html", "matrix.html", "login.html", "register.html"):
            html_path = static_dir / html_file
            if html_path.exists():
                self.app.get(f"/{html_file}", include_in_schema=False)(
                    lambda _path=str(html_path): FileResponse(_path)
                )

        # Mount the rest of NTT0.6 so JS/CSS imports resolve
        self.app.mount("/", StaticFiles(directory=str(static_dir)), name="static")

    def get_app(self):
        # Mount static last so HTML routes take precedence over the catch-all mount
        self._mount_static()
        return self.app


# app/backends/flask_backend.py
class FlaskBackend(BaseBackend):
    def __init__(self, **data):
        super().__init__(**data)
        from flask import Flask
        from flasgger import Swagger
        self.app = Flask(__name__, static_url_path='/static', static_folder='static', template_folder='templates')
        self.app.config['SWAGGER'] = {'title': 'PyBend Flask API', 'uiversion': 3}
        Swagger(self.app)

    def register_routes(self, registered_models: dict[str, type]):
        from api.routes_flask import create_api_blueprint
        blueprint = create_api_blueprint(registered_models)
        self.app.register_blueprint(blueprint)

    def get_app(self):
        from asgiref.wsgi import WsgiToAsgi
        return WsgiToAsgi(self.app)

