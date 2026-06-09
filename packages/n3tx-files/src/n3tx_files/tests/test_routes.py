from n3tx_core.app import create_app
from n3tx_core.authorize import create_token
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_files import File, LocalFileStore, configure_file_store
from fastapi.testclient import TestClient


JWT_SECRET = "test-secret-for-n3tx-files-routes-32-bytes"


def _client(tmp_path):
    configure_file_store(LocalFileStore(tmp_path / "blobs"))
    app = create_app(
        models=[File],
        storage=SQLiteStorage(str(tmp_path / "files.db")),
        static_dir=None,
        jwt_secret=JWT_SECRET,
    )
    token = create_token(1, "alice@example.com", "user")
    return TestClient(app), {"x-access-token": token}


def test_upload_requires_authentication(tmp_path):
    client, _headers = _client(tmp_path)

    response = client.post(
        "/files/upload",
        files={"upload": ("hello.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 403


def test_upload_creates_file_metadata_and_stores_bytes(tmp_path):
    client, headers = _client(tmp_path)

    response = client.post(
        "/files/upload",
        files={"upload": ("hello.txt", b"hello files", "text/plain")},
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "hello.txt"
    assert data["content_type"] == "text/plain"
    assert data["size"] == len(b"hello files")
    assert data["user_owner"] == 1
    assert data["$schema"].endswith("/File")


def test_download_streams_file_bytes(tmp_path):
    client, headers = _client(tmp_path)
    upload = client.post(
        "/files/upload",
        files={"upload": ("hello.txt", b"hello files", "text/plain")},
        headers=headers,
    )
    file_id = upload.json()["id"]

    response = client.get(f"/files/{file_id}/download")

    assert response.status_code == 200
    assert response.content == b"hello files"
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["content-length"] == str(len(b"hello files"))


def test_download_supports_inclusive_byte_ranges(tmp_path):
    client, headers = _client(tmp_path)
    upload = client.post(
        "/files/upload",
        files={"upload": ("numbers.txt", b"0123456789", "text/plain")},
        headers=headers,
    )
    file_id = upload.json()["id"]

    response = client.get(
        f"/File/{file_id}/download",
        headers={"range": "bytes=2-5"},
    )

    assert response.status_code == 206
    assert response.content == b"2345"
    assert response.headers["content-range"] == "bytes 2-5/10"
