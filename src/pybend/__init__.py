"""PyBend -- Schema-driven full-stack framework for Python."""

from .core.models.proto_model import ProtoModel, generate_join_model
from .core.models.storable_mixin import StorableMixin
from .core.models.viewable_mixin import ViewableMixin
from .core.models.base_user import BaseUser
from .core.models.ref import ListRef
from .core.utils.decorators import expose_route
from .core.utils.erroring import MethodError
from .core.utils.registrar import register_model, registered_models
from .core.utils.typer import Ref
from .core.storage.sqlite_storage import SQLiteStorage
from .core.storage.json_storage import JSONStorage
from .core.storage.abstract_storage import AbstractStorage
from .core.api.backend import FastAPIBackend
from .core.app import create_app, PyBendApp
from .core.models.proto_schema import schema_extension
from .core.actors import Actor, Matrix, TX, matrix
from .core.api.network_adapter import NetworkAdapter
from .core.api.network_api import NetworkAPI
from .core.api.network_ws import NetworkWebSocket, create_ws_routes

__version__ = "0.8.0b"

__all__ = [
    "ProtoModel", "generate_join_model", "StorableMixin", "ViewableMixin",
    "BaseUser", "ListRef", "Ref", "expose_route", "MethodError",
    "register_model", "registered_models",
    "SQLiteStorage", "JSONStorage", "AbstractStorage", "FastAPIBackend",
    "create_app", "PyBendApp", "schema_extension",
    "Actor", "Matrix", "TX", "matrix", "NetworkAdapter", "NetworkAPI",
    "NetworkWebSocket", "create_ws_routes",
    "__version__",
]
