import pytest

from n3tx_core.app import create_app
from n3tx_core.authorize import OWNER
from n3tx_core.storage.sqlite_storage import SQLiteStorage
from n3tx_core.utils.erroring import MethodError
from n3tx_files import File, LocalFileStore, configure_file_store


def _app(tmp_path):
    configure_file_store(LocalFileStore(tmp_path / "blobs"))
    return create_app(
        models=[File],
        storage=SQLiteStorage(str(tmp_path / "files.db")),
        static_dir=None,
        jwt_secret="test-secret-for-n3tx-files-resolve-32-bytes",
    )


def _create_file(**overrides):
    data = {
        "filename": "sample.txt",
        "content_type": "text/plain",
        "size": 5,
        "sha256": "abc",
        "storage_key": "ab/abc",
        "user_owner": 1,
    }
    data.update(overrides)
    return File.create(File(**data))


@pytest.mark.asyncio
async def test_resolve_returns_file_for_canonical_url(tmp_path):
    _app(tmp_path)
    created = _create_file()

    ref = created.model_response()["$id"]
    resolved = await File.resolve(ref, user={"user_id": 1, "role": "user"})
    assert resolved.id == created.id
    assert resolved.filename == "sample.txt"


@pytest.mark.asyncio
async def test_resolve_rejects_invalid_address(tmp_path):
    _app(tmp_path)

    with pytest.raises(MethodError) as exc:
        await File.resolve("/File/1", user={"user_id": 1})

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_resolve_rejects_missing_file(tmp_path):
    _app(tmp_path)

    with pytest.raises(MethodError) as exc:
        await File.resolve("http://localhost:5000/File/999", user={"user_id": 1})

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_resolve_enforces_read_access(tmp_path):
    _app(tmp_path)
    created = _create_file(user_owner=1)
    original_access = File.__access__
    File.__access__ = {**original_access, "read": OWNER}
    try:
        with pytest.raises(MethodError) as exc:
            await File.resolve(created.model_response()["$id"], user={"user_id": 2, "role": "user"})
    finally:
        File.__access__ = original_access

    assert exc.value.status_code == 403
