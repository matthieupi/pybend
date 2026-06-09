"""Address parsing for N3TX file resources."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class FileAddress:
    """Parsed internal file address."""

    id: int
    kind: str


def parse_file_address(address: str) -> FileAddress:
    """Parse an internal N3TX file address.

    Supported forms:

    - ``n3tx://files/{id}``
    - ``/files/{id}``
    - ``/File/{id}``

    External HTTP imports are intentionally not supported in this slice.
    """

    if not isinstance(address, str) or not address.strip():
        raise ValueError("File address must be a non-empty string")

    value = address.strip()
    if value.startswith("n3tx://"):
        return _parse_n3tx_url(value)
    if value.startswith("/"):
        return _parse_path(value)
    raise ValueError(f"Unsupported file address: {address!r}")


def _parse_n3tx_url(value: str) -> FileAddress:
    parsed = urlparse(value)
    if parsed.scheme != "n3tx" or parsed.netloc != "files":
        raise ValueError(f"Unsupported file address: {value!r}")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 1:
        raise ValueError(f"Invalid file address: {value!r}")
    return FileAddress(id=_parse_id(parts[0]), kind="n3tx")


def _parse_path(value: str) -> FileAddress:
    parts = [part for part in value.split("/") if part]
    if len(parts) != 2 or parts[0] not in {"files", "File"}:
        raise ValueError(f"Unsupported file address: {value!r}")
    return FileAddress(id=_parse_id(parts[1]), kind=parts[0])


def _parse_id(value: str) -> int:
    try:
        file_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid file id: {value!r}") from exc
    if file_id < 0:
        raise ValueError(f"Invalid file id: {value!r}")
    return file_id
