"""
N3TX application builder and factory.

Provides three levels of bootstrapping:

    Level 1 -- One-liner via create_app():
        app = create_app(models=[Product, User], storage="sqlite:///app.db")

    Level 2 -- Builder via N3TXApp:
        pb = N3TXApp(storage="sqlite:///app.db")
        pb.model(Product).model(User)
        app = pb.build()

    Level 3 -- Raw primitives (existing code in main.py, unchanged).
"""

from types import MethodType
from typing import List, Optional, Tuple, Type, Union

_SSR_MODES = ('off', 'schema', 'bundle', 'full')

from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.storage.abstract_storage import AbstractStorage
from n3tx_core.utils.registrar import registered_models, prepare_model, apply_registration
from n3tx_core.utils.logging import setup_logging
from n3tx_core.models.relationships import generate_relationship_models
from n3tx_core.api.backend import FastAPIBackend
from n3tx_core import config
import n3tx_core.authorize as authorize


def _uses_agents(model_classes: List[Type]) -> bool:
    """Return True when an app registers an agent-enabled model.

    Agent execution persists conversation history in n3tx_agents.thread.Thread.
    Core keeps the dependency optional by detecting agent models structurally
    and importing Thread only when needed.
    """
    for model_class in model_classes:
        if getattr(model_class, '__agent__', False):
            return True
        if (
            getattr(model_class, '__module__', '').startswith('n3tx_agents')
            and getattr(model_class, '__tablename__', '') == 'agents'
        ):
            return True
    return False


def _agent_infrastructure_models(model_classes: List[Type]) -> List[Type]:
    """Return required agent infrastructure models not already registered."""
    if not _uses_agents(model_classes):
        return []

    try:
        from n3tx_agents.thread import Thread
    except ImportError:
        return []

    if any(model_class is Thread for model_class in model_classes):
        return []
    if any(getattr(model_class, '__tablename__', None) == Thread.__tablename__
           for model_class in model_classes):
        return []
    return [Thread]


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


def _set_reference_resolver(storages, resolver) -> None:
    """Inject an optional reference resolver into storage backends that support it."""
    seen = set()
    for storage in storages:
        if storage is None or id(storage) in seen:
            continue
        seen.add(id(storage))
        setter = getattr(storage, 'set_reference_resolver', None)
        if callable(setter):
            setter(resolver)


class N3TXApp:
    """Builder for N3TX applications.

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
        ws: bool = False,
        jwt_secret: Optional[str] = None,
        jwt_expiry_hours: int = 24,
        cors_origins: Optional[List[str]] = None,
        debug: bool = None,
        ssr: Union[bool, str, None] = None,
        app_agent: Optional[dict] = None,
        app_meta: Optional[dict] = None,
        remotes: Optional[dict] = None,
        service_name: Optional[str] = None,
        service_token: Optional[str] = None,
    ):
        """
        Args:
            storage: A storage backend instance (e.g. ``SQLiteStorage``) or a
                string like ``"sqlite:///path/to/db.sqlite"`` that will be
                auto-resolved.  If ``None``, uses ``config.SQLITE_DB_FILE``.
            routing: Routing mode — ``'direct'`` for plain FastAPI routes,
                ``'actor'`` for full actor routing via NetworkAPI adapter.
            ws: Enable WebSocket bridge (requires ``routing='actor'``).
                When ``True``, a ``NetworkWebSocket`` adapter is registered
                with the Matrix and a ``/ws`` endpoint is mounted.
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
            app_agent: Optional dict describing a framework-provisioned static
                app assistant. Requires ``n3tx-agents`` models to be registered.
            app_meta: Optional app-specific metadata exposed via ``/_meta``.
            remotes: Optional distributed N3TX service map. Overrides
                ``config.REMOTES`` when provided.
            service_name: Optional local distributed service name. Overrides
                ``config.SERVICE_NAME`` when provided.
            service_token: Optional local service token. Overrides
                ``config.SERVICE_TOKEN`` when provided.
        """
        setup_logging()
        if remotes is not None:
            config.configure(remotes=remotes)
        if service_name is not None:
            config.configure(service_name=service_name)
        if service_token is not None:
            config.configure(service_token=service_token)

        self._storage = _resolve_storage(storage)
        self._routing = routing
        self._ws = ws
        self._jwt_secret = jwt_secret
        self._jwt_expiry_hours = jwt_expiry_hours
        self._cors_origins = cors_origins
        self._debug = debug if debug is not None else config.DEBUG
        if self._debug:
            config.configure(debug=True)
        self._ssr_mode = _resolve_ssr(ssr)
        self._app_agent = app_agent
        self._app_meta = app_meta or {}
        self._remotes = remotes if remotes is not None else config.REMOTES

        self._models: List[Tuple[Type, Optional[AbstractStorage]]] = []
        self._static_dirs: List[str] = []

    # ── Builder methods (chainable) ──────────────────────

    def model(self, model_class: Type, storage=None) -> "N3TXApp":
        """Register a model.  Returns ``self`` for chaining.

        Args:
            model_class: A ``ProtoModel`` subclass to register.
            storage: Optional per-model storage override.  If ``None``,
                the builder-level storage is used.
        """
        self._models.append((model_class, storage))
        return self

    def static(self, directory: str) -> "N3TXApp":
        """Mount an additional static-file directory for app-specific
        frontend assets.  Returns ``self`` for chaining.
        """
        self._static_dirs.append(directory)
        return self

    # ── Build ────────────────────────────────────────────

    def build(
        self,
        name: str = "N3TX",
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

        # 2. Prepare all model registrations (pure — no side effects)
        preparations = []
        explicit_model_classes = [model_class for model_class, _ in self._models]

        for model_class, per_model_storage in self._models:
            effective_storage = (
                _resolve_storage(per_model_storage)
                if per_model_storage is not None
                else self._storage
            )
            preparations.append(prepare_model(model_class, storage=effective_storage))

        for model_class in _agent_infrastructure_models(explicit_model_classes):
            preparations.append(prepare_model(model_class, storage=self._storage))

        # 3. Generate and prepare field-declared relationship link models.
        #    Generation is deterministic; registration/table side effects are
        #    still centralized in apply_registration().
        for relationship_model in generate_relationship_models(explicit_model_classes):
            preparations.append(prepare_model(relationship_model, storage=self._storage))

        # 4. Apply all registrations (side effects: storage, tables, global dicts)
        #    Clear first so reloads (e.g. uvicorn --reload) start from a clean
        #    slate.  Using .clear() preserves dict identity — existing references
        #    (e.g. FastAPIBackend.registered_models) see the updated contents.
        registered_models.clear()
        for result in preparations:
            apply_registration(result)

        if self._app_agent:
            from n3tx_agents.app_agent import provision_app_agent
            provision_app_agent(self._app_agent, registered_models)

        # 5. Create FastAPIBackend instance
        backend = FastAPIBackend(
            name=name,
            version=version,
            description=description,
            port=config.PORT,
            ssr_mode=self._ssr_mode,
        )

        # 6. Register routes — direct (Level 1/2) or actor (Level 3)
        if self._routing == 'actor':
            from n3tx_actors.actor import Actor
            from n3tx_actors.api.network_api import NetworkAPI, create_api_routes
            from n3tx_actors.api.auth_interceptor import auth_interceptor
            from n3tx_actors.matrix import matrix

            matrix.add_alias(config.API_URL)

            def add_alias(app, url: str):
                """Register a local Matrix URL alias and return this app."""
                matrix.add_alias(url)
                return app

            backend.app.add_alias = MethodType(add_alias, backend.app)

            # Sync Matrix children to the fully-registered model classes.
            # Actor subclasses may have auto-registered earlier during import,
            # but registered_models is the canonical post-bootstrap class set
            # with storage attached. Re-registering here ensures actor routing
            # uses those live classes instead of stale import-time ones.
            for model_cls in registered_models.values():
                if isinstance(model_cls, type) and issubclass(model_cls, Actor):
                    matrix.register(model_cls)

            api = NetworkAPI()
            matrix.register(api)
            api.use(auth_interceptor, on='request')

            if self._remotes:
                from n3tx_actors.api.remote_matrix import RemoteMatrix, MatrixReferenceResolver

                remote = RemoteMatrix(
                    remotes=self._remotes,
                    service_name=config.SERVICE_NAME,
                    service_token=config.SERVICE_TOKEN,
                )
                matrix.register(remote)
                matrix.register_adapter(remote)
                resolver = MatrixReferenceResolver(matrix)
                _set_reference_resolver(
                    [self._storage]
                    + [storage for _model, storage in self._models]
                    + [getattr(model_cls, 'storage', None) for model_cls in registered_models.values()],
                    resolver,
                )

            backend.app.include_router(
                create_api_routes(api, registered_models)
            )

            # 6a. WebSocket bridge (requires actor routing)
            if self._ws:
                from n3tx_actors.api.network_ws import (
                    NetworkWebSocket, create_ws_routes,
                )
                ws_adapter = NetworkWebSocket()
                matrix.register(ws_adapter)
                ws_adapter.use(auth_interceptor, on='request')
                backend.app.include_router(create_ws_routes(ws_adapter))
                # Subscribe all ActorModels to push lifecycle events via WS
                for model_cls in registered_models.values():
                    if hasattr(model_cls, '_subscribers'):
                        model_cls._subscribers.append('ws')
        else:
            backend.register_routes(registered_models)

        # 6b. TX Inspector (optional — requires n3tx-trace installed)
        if self._debug and self._routing == 'actor':
            try:
                from n3tx_trace import enable_tracing
                enable_tracing(backend.app, matrix)
            except ImportError:
                pass  # n3tx-trace not installed — skip

        # 6c. Mount discovery endpoints (/_meta, /.well-known/agent.json)
        from n3tx_core.api.discovery import create_discovery_routes

        base_url = f'http://{config.HOST}:{config.PORT}'
        backend.app.include_router(create_discovery_routes(
            registered_models=registered_models,
            name=name,
            version=version,
            base_url=base_url,
            description=description,
            app_meta=self._app_meta,
        ))

        # 7. Return the FastAPI app instance
        #    get_app() mounts the framework's own static directory last
        #    so that HTML routes take precedence over the catch-all mount.
        #    Pass app-specific static directories so their files are served
        #    alongside the framework statics (explicit routes before catch-all).
        return backend.get_app(app_static_dirs=self._static_dirs)


def create_app(
    models=None,
    storage=None,
    routing='direct',
    ws=False,
    static_dir=None,
    jwt_secret=None,
    jwt_expiry_hours=24,
    cors_origins=None,
    debug=None,
    ssr=None,
    app_agent=None,
    app_meta=None,
    remotes=None,
    service_name=None,
    service_token=None,
    name="N3TX",
    version="1.0.0",
    description="",
    **kwargs,
):
    """Convenience wrapper -- creates a ``N3TXApp``, registers
    everything, and returns the ASGI app.

    Args:
        models: List of ``ProtoModel`` subclasses to register.
        storage: Storage backend or URI string (see :class:`N3TXApp`).
        routing: ``'direct'`` for plain FastAPI routes (Level 1/2),
            ``'actor'`` for full actor routing via NetworkAPI (Level 3).
        ws: Enable WebSocket bridge (requires ``routing='actor'``).
        static_dir: Path to an additional static-file directory.
        jwt_secret: JWT signing secret.
        jwt_expiry_hours: JWT token expiry in hours.
        cors_origins: Allowed CORS origins.
        debug: Enable debug mode.
        ssr: SSR mode (``None``, ``True``, ``False``, or a mode string).
        app_agent: Optional dict describing a framework-provisioned static
            app assistant.
        app_meta: Optional app-specific metadata exposed via ``/_meta``.
        remotes: Optional distributed N3TX service map. Overrides
            ``config.REMOTES`` for this process.
        service_name: Optional local distributed service name.
        service_token: Optional local service token.
        name: Application name (appears in OpenAPI docs).
        version: Application version string.
        description: Application description.

    Returns:
        A configured FastAPI application instance.
    """
    if 'join_models' in kwargs:
        raise TypeError(
            "create_app() no longer accepts join_models; declare owned "
            "collections as list[T] on the parent model instead."
        )

    builder = N3TXApp(
        storage=storage,
        routing=routing,
        ws=ws,
        jwt_secret=jwt_secret,
        jwt_expiry_hours=jwt_expiry_hours,
        cors_origins=cors_origins,
        debug=debug,
        ssr=ssr,
        app_agent=app_agent,
        app_meta=app_meta,
        remotes=remotes,
        service_name=service_name,
        service_token=service_token,
    )
    for m in (models or []):
        builder.model(m)
    if static_dir:
        builder.static(static_dir)
    return builder.build(name=name, version=version, description=description)
