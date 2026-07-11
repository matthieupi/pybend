"""Canonical URL handling for N3TX file resources."""

from __future__ import annotations

from n3tx_core import config
from n3tx_core.models.ref import Ref


def file_id_from_ref(ref: str, *, api_url: str | None = None) -> int:
    """Extract a local integer File id from its canonical absolute URL."""
    try:
        url = Ref.url(ref)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid File ref: {ref!r}") from exc

    if Ref.schema(url) != "File":
        raise ValueError(f"File ref must target the File schema: {ref!r}")

    expected_base = (api_url or config.API_URL).rstrip("/")
    if Ref.base_url(url) != expected_base:
        raise ValueError(f"File ref must target the current API: {ref!r}")

    try:
        file_id = int(Ref.id(url))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid File id in ref: {ref!r}") from exc
    if file_id < 0:
        raise ValueError(f"Invalid File id in ref: {ref!r}")
    return file_id


__all__ = ["file_id_from_ref"]
