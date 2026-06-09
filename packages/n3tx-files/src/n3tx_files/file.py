"""Actor-backed file metadata model."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pydantic import Field

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.authorize import AccessContext, AccessDenied, ANYONE, AUTHENTICATED, DefaultResolver, OWNER, ROLE
from n3tx_core.utils.decorators import expose_route
from n3tx_core.utils.erroring import MethodError

from .address import parse_file_address
from .config import FILE_STORE_DIR
from .store import FileStore, LocalFileStore


_file_store: FileStore | None = None
_resolver = DefaultResolver()


def configure_file_store(store: FileStore) -> None:
    """Set the process-wide file byte store used by File methods."""

    global _file_store
    _file_store = store


def get_file_store() -> FileStore:
    """Return the configured file byte store, creating a local default if needed."""

    global _file_store
    if _file_store is None:
        _file_store = LocalFileStore(FILE_STORE_DIR)
    return _file_store


class File(ActorModel):
    """N3TX-native file resource.

    The model stores metadata. Blob bytes are owned by a FileStore provider.
    """

    __tablename__ = "files"
    __storable__ = True
    __protected_fields__: ClassVar[set[str]] = {
        "user_owner",
        "storage_key",
        "sha256",
        "size",
    }
    __access__: ClassVar[dict] = {
        "read": ANYONE,
        "create": AUTHENTICATED,
        "update": OWNER | ROLE("admin"),
        "delete": OWNER | ROLE("admin"),
    }
    __ui__: ClassVar[dict] = {
        "field_order": [
            "filename",
            "content_type",
            "size",
            "sha256",
            "origin",
            "public",
            "meta",
        ],
        "renderer": {"item": "ntx-item", "list": "ntx-list"},
    }

    filename: str = Field(min_length=1, description="Original or display filename")
    content_type: str = Field(default="application/octet-stream")
    size: int = Field(default=0, ge=0)
    sha256: str = Field(default="")
    storage_key: str = Field(default="")
    origin: str | None = Field(default=None)
    public: bool = Field(default=False)
    user_owner: int | None = Field(default=None)
    meta: dict = Field(default_factory=dict)

    @classmethod
    def register_extra_routes(cls, router, *, tag: str) -> None:
        """Mount package-owned byte routes for this File model."""

        from .routes import register_file_routes

        register_file_routes(router, cls, tag=tag)

    @classmethod
    @expose_route("/resolve", methods=["POST"])
    async def resolve(cls, address: str, user=None):
        """Resolve an internal address into an authorized File record."""

        try:
            parsed = parse_file_address(address)
        except ValueError as exc:
            raise MethodError(str(exc), 400) from exc

        file = cls.get(parsed.id)
        if not file:
            raise MethodError("File not found", 404)

        try:
            _resolver.authorize(
                AccessContext(
                    user=user or {},
                    action="read",
                    model_class=cls,
                    resource=file,
                )
            )
        except AccessDenied as exc:
            raise MethodError(str(exc), 403) from exc

        return file

    @expose_route("/ensure_local", methods=["POST"])
    async def ensure_local(self, user=None) -> dict:
        """Return the local path for locally stored bytes.

        Full projection/cache behavior is added in a later slice. For the local
        store tracer bullet, the blob is already local and can be exposed as a
        checked path.
        """

        store = get_file_store()
        if not isinstance(store, LocalFileStore):
            raise RuntimeError("ensure_local projection for remote stores is not implemented yet")
        path = store.path_for(self.storage_key)
        if not Path(path).exists():
            raise FileNotFoundError(self.storage_key)
        return {
            "path": str(path),
            "sha256": self.sha256,
            "size": self.size,
        }
