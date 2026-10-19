from __future__ import annotations

from typing import ClassVar

from fastapi import APIRouter, File as FastAPIFile, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.testclient import TestClient

from n3tx_core.app import create_app
from n3tx_core.authorize import ANYONE, create_token
from n3tx_core.models.proto_model import ProtoModel
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_files import File, LocalFileStore, configure_file_store


NODE_SECRET = "test-secret-for-two-node-files-flow-32-bytes"


class StorageNodeClient:
    """Test seam representing an app node's client for a storage node."""

    def __init__(self, client: TestClient, headers: dict[str, str]):
        self.client = client
        self.headers = headers

    def upload(self, upload: UploadFile) -> dict:
        content = upload.file.read()
        response = self.client.post(
            "/files/upload",
            files={
                "upload": (
                    upload.filename,
                    content,
                    upload.content_type or "application/octet-stream",
                )
            },
            headers=self.headers,
        )
        if response.status_code != 201:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()

    def download(self, file_id: int) -> Response:
        response = self.client.get(f"/files/{file_id}/download")
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return Response(
            content=response.content,
            media_type=response.headers.get("content-type", "application/octet-stream"),
            headers={
                "Content-Length": response.headers.get("content-length", str(len(response.content))),
                "ETag": response.headers.get("etag", ""),
            },
        )


class AppFileGateway(ProtoModel):
    """Test-only app-node gateway that delegates file bytes to storage node."""

    __tablename__: ClassVar[str] = "app_file_gateway"
    __storable__: ClassVar[bool] = False
    __access__: ClassVar[dict] = {"*": ANYONE}
    storage_node: ClassVar[StorageNodeClient | None] = None

    @classmethod
    def register_extra_routes(cls, router: APIRouter, *, tag: str) -> None:
        @router.post("/app/files/upload", tags=[tag], status_code=201)
        async def upload_to_storage_node(upload: UploadFile = FastAPIFile(...)):
            if cls.storage_node is None:
                raise HTTPException(status_code=503, detail="Storage node unavailable")
            return cls.storage_node.upload(upload)

        @router.get("/app/files/{id:int}/download", tags=[tag])
        async def download_from_storage_node(id: int):
            if cls.storage_node is None:
                raise HTTPException(status_code=503, detail="Storage node unavailable")
            return cls.storage_node.download(id)


def _storage_node(tmp_path):
    configure_file_store(LocalFileStore(tmp_path / "storage-blobs"))
    app = create_app(
        models=[File],
        storage=SQLiteStorage(str(tmp_path / "storage.db")),
        static_dir=None,
        jwt_secret=NODE_SECRET,
    )
    headers = {"x-access-token": create_token(1, "storage@example.com", "user")}
    return TestClient(app), headers


def _app_node(tmp_path, storage_client: StorageNodeClient):
    AppFileGateway.storage_node = storage_client
    app = create_app(
        models=[AppFileGateway],
        storage=SQLiteStorage(str(tmp_path / "app.db")),
        static_dir=None,
        jwt_secret=NODE_SECRET,
    )
    return TestClient(app)


def test_app_node_upload_saves_file_on_storage_node(tmp_path):
    storage_client, storage_headers = _storage_node(tmp_path)
    app_client = _app_node(tmp_path, StorageNodeClient(storage_client, storage_headers))

    response = app_client.post(
        "/app/files/upload",
        files={"upload": ("remote.txt", b"stored remotely", "text/plain")},
    )

    assert response.status_code == 201
    uploaded = response.json()
    assert uploaded["filename"] == "remote.txt"
    assert uploaded["size"] == len(b"stored remotely")

    storage_download = storage_client.get(f"/files/{uploaded['id']}/download")
    assert storage_download.status_code == 200
    assert storage_download.content == b"stored remotely"


def test_app_node_download_loads_file_from_storage_node(tmp_path):
    storage_client, storage_headers = _storage_node(tmp_path)
    app_client = _app_node(tmp_path, StorageNodeClient(storage_client, storage_headers))

    upload = app_client.post(
        "/app/files/upload",
        files={"upload": ("remote.txt", b"loaded from storage", "text/plain")},
    )
    file_id = upload.json()["id"]

    response = app_client.get(f"/app/files/{file_id}/download")

    assert response.status_code == 200
    assert response.content == b"loaded from storage"
    assert response.headers["content-type"].startswith("text/plain")
