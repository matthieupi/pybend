"""
PyBend application builder and factory.

Provides three levels of bootstrapping:

    Level 1 -- One-liner via create_app():
        app = create_app(
            models=[Product, User],
            join_models=[(Product, Comment)],
            storage="sqlite:///app.db",
        )

    Level 2 -- Builder via PyBendApp:
        pb = PyBendApp(storage="sqlite:///app.db")
        pb.model(Product).model(User).join(Product, Comment)
        app = pb.build()

    Level 3 -- Raw primitives (existing code in main.py, unchanged).
"""

from typing import List, Optional, Tuple, Type, Union

_SSR_MODES = ('off', 'schema', 'bundle', 'full')

from pybend.core.storage.sqlite_storage import SQLiteStorage
from pybend.core.storage.abstract_storage import AbstractStorage
from pybend.core.utils.registrar import register_model, registered_models
from pybend.core.models.proto_model import generate_join_model
from pybend.core.api.backend import FastAPIBackend
from pybend.core import config
import pybend.core.authorize as authorize


def _resolve_storage(storage) -> AbstractStorage:
    """Turn a storage specifier into an AbstractStorage instance.

    Accepts:
        - An existing AbstractStorage instance (returned as-is).
        - A string like ``"sqlite:///path/to/db.sqlite"`` (parsed and
          instantiated).
        - ``None`` (falls back to ``config.SQLITE_DB_FILE``).
    """
    if storage is None:
        return SQLiteStorage(config.SQLITE_DB_FILE)
    if isinstance(storage, AbstractStorage):
        return storage
    if isinstance(storage, str):
        if storage.startswith("sqlite:///"):
            db_path = storage[len("sqlite:///"):]
            return SQLiteStorage(db_path)
        raise ValueError(
            f"Unsupported storage URI: {storage!r}. "
            "Currently only 'sqlite:///path' is supported."
        )
    raise TypeError(
        f"storage must be an AbstractStorage instance, a URI string, or None; "
        f"got {type(storage).__name__}"
    )


def _resolve_ssr(ssr) -> str:
    """Resolve the ``ssr`` parameter to a mode string.

    Accepts:
        - ``None`` → read from ``config.SSR``
        - ``True`` → ``"schema"`` (backward compatibility)
        - ``False`` → ``"off"``
        - A mode string (``"off"``, ``"schema"``, ``"bundle"``, ``"full"``)
    """
    if ssr is None:
        return config.SSR
    if ssr is True:
        return 'schema'
    if ssr is False:
        return 'off'
    if isinstance(ssr, str):
        mode = ssr.lower()
        if mode not in _SSR_MODES:
            raise ValueError(
                f"Invalid SSR mode: {ssr!r}. Must be one of {_SSR_MODES}"
            )
        return mode
    raise TypeError(f"ssr must be bool, str, or None; got {type(ssr).__name__}")


class PyBendApp:
    """Builder for PyBend applications.

    Collects model registrations and configuration, then produces a
    fully configured ASGI application via :meth:`build`.

    Supports three routing modes:
        - ``'direct'`` (default): routes_fastapi.py route factories (Level 1/2)
        - ``'actor'``: NetworkAPI adapter routes everything through Matrix (Level 3)
    """

    def __init__(
        self,
        storage=None,
        routing: str = 'direct',
        jwt_secret: Optional[str] = None,
        jwt_expiry_hours: int = 24,
        cors_origins: Optional[List[str]] = None,
        debug: bool = False,
        ssr: Union[bool, str, None] = None,
    ):
        """
        Args:
            storage: A storage backend instance (e.g. ``SQLiteStorage``) or a
                string like ``"sqlite:///path/to/db.sqlite"`` that will be
                auto-resolved.  If ``None``, uses ``config.SQLITE_DB_FILE``.
            routing: Routing mode — ``'direct'`` for plain FastAPI routes,
                ``'actor'`` for full actor routing via NetworkAPI adapter.
            jwt_secret: Secret for JWT tokens.  If ``None``, uses
                ``config.JWT_SECRET``.
            jwt_expiry_hours: JWT token expiry in hours.
            cors_origins: List of allowed CORS origins.  Defaults to
                ``["*"]``.
            debug: Enable debug mode.
            ssr: SSR mode. Accepts:
                - ``None`` (default): read from ``config.SSR``
                - ``True``: shorthand for ``"schema"`` (backward compat)
                - ``False``: shorthand for ``"off"``
                - A string: ``"off"``, ``"schema"``, ``"bundle"``, ``"full"``
        """
        self._storage = _resolve_storage(storage)
        self._routing = routing
        self._jwt_secret = jwt_secret
        self._jwt_expiry_hours = jwt_expiry_hours
        self._cors_origins = cors_origins
        self._debug = debug
        self._ssr_mode = _resolve_ssr(ssr)

        self._models: List[Tuple[Type, Optional[AbstractStorage]]] = []
        self._join_pairs: List[Tuple[Type, Type]] = []
        self._static_dirs: List[str] = []

    # ── Builder methods (chainable) ──────────────────────

    def model(self, model_class: Type, storage=None) -> "PyBendApp":
        """Register a model.  Returns ``self`` for chaining.

        Args:
            model_class: A ``ProtoModel`` subclass to register.
            storage: Optional per-model storage override.  If ``None``,
                the builder-level storage is used.
        """
        self._models.append((model_class, storage))
        return self

    def join(self, parent: Type, child: Type) -> "PyBendApp":
        """Register a parent-child join relationship.  Returns ``self``
        for chaining.

        This calls ``generate_join_model(parent, child)`` during
        :meth:`build` and registers the resulting model.
        """
        self._join_pairs.append((parent, child))
        return self

    def static(self, directory: str) -> "PyBendApp":
        """Mount an additional static-file directory for app-specific
        frontend assets.  Returns ``self`` for chaining.
        """
        self._static_dirs.append(directory)
        return self

    # ── Build ────────────────────────────────────────────

    def build(
        self,
        name: str = "PyBend",
        version: str = "1.0.0",
        description: str = "",
    ):
        """Build and return the configured ASGI application (FastAPI
        instance).

        The returned object is a standard FastAPI ``app`` that can be
        served with Uvicorn or any ASGI server.
        """

        # 1. Configure auth
        authorize.configure(
            jwt_secret=self._jwt_secret or config.JWT_SECRET,
            jwt_expiry_hours=self._jwt_expiry_hours,
        )

        # 2. Register all models with storage backend
        for model_class, per_model_storage in self._models:
            effective_storage = (
                _resolve_storage(per_model_storage)
                if per_model_storage is not None
                else self._storage
            )
            register_model(model_class, storage=effective_storage)

        # 3. Generate and register join models
        for parent, child in self._join_pairs:
            join_model = generate_join_model(parent, child)
            register_model(join_model, storage=self._storage)

        # 4. Create FastAPIBackend instance
        backend = FastAPIBackend(
            name=name,
            version=version,
            description=description,
            port=config.PORT,
            ssr_mode=self._ssr_mode,
        )

        # 5. Register routes — direct (Level 1/2) or actor (Level 3)
        if self._routing == 'actor':
            from pybend.core.api.network_api import NetworkAPI, create_api_routes
            from pybend.core.api.auth_interceptor import auth_interceptor
            from pybend.core.actors.matrix import matrix

            api = NetworkAPI()
            matrix.register(api)
            api.use(auth_interceptor, on='request')
            backend.app.include_router(
                create_api_routes(api, registered_models)
            )
        else:
            backend.register_routes(registered_models)

        # 6. Return the FastAPI app instance
        #    get_app() mounts the framework's own static directory last
        #    so that HTML routes take precedence over the catch-all mount.
        #    Pass app-specific static directories so their files are served
        #    alongside the framework statics (explicit routes before catch-all).
        return backend.get_app(app_static_dirs=self._static_dirs)


def create_app(
    models=None,
    join_models=None,
    storage=None,
    routing='direct',
    static_dir=None,
    jwt_secret=None,
    jwt_expiry_hours=24,
    cors_origins=None,
    debug=False,
    ssr=None,
    name="PyBend",
    version="1.0.0",
    description="",
    **kwargs,
):
    """Convenience wrapper -- creates a ``PyBendApp``, registers
    everything, and returns the ASGI app.

    Args:
        models: List of ``ProtoModel`` subclasses to register.
        join_models: List of ``(parent, child)`` tuples for join
            relationships.
        storage: Storage backend or URI string (see :class:`PyBendApp`).
        routing: ``'direct'`` for plain FastAPI routes (Level 1/2),
            ``'actor'`` for full actor routing via NetworkAPI (Level 3).
        static_dir: Path to an additional static-file directory.
        jwt_secret: JWT signing secret.
        jwt_expiry_hours: JWT token expiry in hours.
        cors_origins: Allowed CORS origins.
        debug: Enable debug mode.
        ssr: SSR mode (``None``, ``True``, ``False``, or a mode string).
        name: Application name (appears in OpenAPI docs).
        version: Application version string.
        description: Application description.

    Returns:
        A configured FastAPI application instance.
    """
    builder = PyBendApp(
        storage=storage,
        routing=routing,
        jwt_secret=jwt_secret,
        jwt_expiry_hours=jwt_expiry_hours,
        cors_origins=cors_origins,
        debug=debug,
        ssr=ssr,
    )
    for m in (models or []):
        builder.model(m)
    for parent, child in (join_models or []):
        builder.join(parent, child)
    if static_dir:
        builder.static(static_dir)
    return builder.build(name=name, version=version, description=description)
