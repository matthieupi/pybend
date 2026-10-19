import pytest

from n3tx_files import LocalFileStore


async def _collect(stream):
    chunks = []
    async for chunk in stream:
        chunks.append(chunk)
    return b"".join(chunks)


@pytest.mark.asyncio
async def test_local_file_store_writes_reads_and_stats_bytes(tmp_path):
    store = LocalFileStore(tmp_path)

    stat = await store.put_stream(b"hello files", meta={"content_type": "text/plain"})

    assert stat.size == len(b"hello files")
    assert stat.content_type == "text/plain"
    assert len(stat.sha256) == 64
    assert store.path_for(stat.key).exists()

    assert await _collect(store.open_stream(stat.key)) == b"hello files"

    fresh_stat = await store.stat(stat.key)
    assert fresh_stat.size == stat.size
    assert fresh_stat.sha256 == stat.sha256


@pytest.mark.asyncio
async def test_local_file_store_supports_inclusive_ranges(tmp_path):
    store = LocalFileStore(tmp_path)
    stat = await store.put_stream(b"0123456789")

    assert await _collect(store.open_stream(stat.key, start=2, end=5)) == b"2345"


@pytest.mark.asyncio
async def test_local_file_store_rejects_escaping_keys(tmp_path):
    store = LocalFileStore(tmp_path)

    with pytest.raises(ValueError):
        store.path_for("../escape")
