from typing import ClassVar

from fastapi.testclient import TestClient

from n3tx_actors.models.actor_model import ActorModel
from n3tx_core.app import create_app
from n3tx_core.authorize import ANYONE, create_token
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.decorators import expose_route
from n3tx_files import File, LocalFileStore, configure_file_store


class FileConsumer(ActorModel, auto_register=False):
    __tablename__: ClassVar[str] = "file_consumers"
    __storable__: ClassVar[bool] = False
    __access__: ClassVar[dict] = {"*": ANYONE}

    @expose_route("/consume", methods=["POST"])
    async def consume(file: File) -> dict:
        return {"id": file.id, "filename": file.filename}

    @expose_route("/echo", methods=["POST"])
    async def echo(value: str) -> dict:
        return {"value": value}


def _client(tmp_path, *, routing="direct"):
    configure_file_store(LocalFileStore(tmp_path / f"{routing}-blobs"))
    secret = f"test-secret-for-n3tx-files-{routing}-32-bytes"
    app = create_app(
        models=[File, FileConsumer],
        storage=SQLiteStorage(str(tmp_path / f"{routing}.db")),
        routing=routing,
        static_dir=None,
        jwt_secret=secret,
    )
    token = create_token(1, "alice@example.com", "user")
    return TestClient(app), {"x-access-token": token}


def _create_file(filename="audio.wav"):
    return File.create(
        File(
            filename=filename,
            content_type="audio/wav",
            size=5,
            sha256="abc",
            storage_key="ab/abc",
            user_owner=1,
        )
    )


def test_direct_route_materializes_file_typed_argument(tmp_path):
    client, headers = _client(tmp_path, routing="direct")
    file = _create_file()

    response = client.post("/file_consumers/consume", json={"file": f"/File/{file.id}"}, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"id": file.id, "filename": "audio.wav"}


def test_actor_route_materializes_file_typed_argument(tmp_path):
    client, headers = _client(tmp_path, routing="actor")
    file = _create_file("actor-audio.wav")

    response = client.post(
        "/file_consumers/consume",
        json={"file": f"n3tx://files/{file.id}"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {"id": file.id, "filename": "actor-audio.wav"}


def test_plain_string_argument_is_not_materialized(tmp_path):
    client, headers = _client(tmp_path, routing="direct")

    response = client.post("/file_consumers/echo", json={"value": "/File/123"}, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"value": "/File/123"}
