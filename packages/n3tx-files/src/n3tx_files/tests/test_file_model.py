from n3tx_files import File


def test_file_schema_exposes_metadata_contract():
    schema = File.schema()

    assert schema["__name__"] == "File"
    assert schema["__tablename__"] == "files"
    assert "filename" in schema["properties"]
    assert "storage_key" in schema["properties"]
    assert "resolve" in schema["methods"]
    assert "ensure_local" in schema["methods"]


def test_file_model_stores_metadata_not_bytes():
    file = File(
        filename="sample.txt",
        content_type="text/plain",
        size=12,
        sha256="abc",
        storage_key="ab/abc",
    )

    data = file.model_dump()

    assert data["filename"] == "sample.txt"
    assert data["storage_key"] == "ab/abc"
    assert "bytes" not in data
    assert "content" not in data
