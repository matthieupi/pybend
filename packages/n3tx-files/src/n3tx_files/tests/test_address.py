import pytest

from n3tx_files.address import parse_file_address


@pytest.mark.parametrize(
    ("address", "file_id"),
    [
        ("n3tx://files/42", 42),
        ("/files/42", 42),
        ("/File/42", 42),
    ],
)
def test_parse_file_address_accepts_internal_addresses(address, file_id):
    parsed = parse_file_address(address)

    assert parsed.id == file_id


@pytest.mark.parametrize(
    "address",
    [
        "",
        "https://example.com/File/1",
        "n3tx://products/1",
        "/Product/1",
        "/files/not-an-id",
        "/files/-1",
    ],
)
def test_parse_file_address_rejects_unsupported_addresses(address):
    with pytest.raises(ValueError):
        parse_file_address(address)
