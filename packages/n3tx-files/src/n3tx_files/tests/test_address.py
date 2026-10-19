import pytest

from n3tx_files.address import file_id_from_ref
def test_file_id_from_ref_accepts_current_service_file_url():
    assert file_id_from_ref(
        "https://api.example.com/api/v1/File/42",
        api_url="https://api.example.com/api/v1",
    ) == 42


@pytest.mark.parametrize(
    "ref",
    [
        "",
        "n3tx://files/42",
        "/files/42",
        "/File/42",
        "https://api.example.com/Product/1",
        "https://remote.example.com/File/1",
        "https://api.example.com/File/not-an-int",
    ],
)
def test_file_id_from_ref_rejects_non_local_file_urls(ref):
    with pytest.raises(ValueError):
        file_id_from_ref(ref, api_url="https://api.example.com")
