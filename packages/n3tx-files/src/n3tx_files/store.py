"""Byte-store providers for N3TX files.

The store layer owns blob bytes. N3TX model storage owns metadata only.
"""

from __future__ import annotations

import inspect
import os
import shutil
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import AsyncIterator, Protocol


DEFAULT_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class FileStat:
    """Stored blob metadata returned by FileStore providers."""

    key: str
    size: int
    sha256: str
    content_type: str = "application/octet-stream"


class FileStore(Protocol):
    """Provider protocol for file bytes."""

    async def put_stream(self, source, *, key: str | None = None, meta: dict | None = None) -> FileStat:
        ...

    def open_stream(
        self,
        key: str,
        *,
        start: int | None = None,
        end: int | None = None,
    ) -> AsyncIterator[bytes]:
        ...

    async def stat(self, key: str) -> FileStat:
        ...

    async def delete(self, key: str) -> None:
        ...


class LocalFileStore:
    """Filesystem-backed FileStore.

    Keys are relative paths inside ``root``. When no key is provided,
    ``put_stream`` stores content under a checksum-derived key:
    ``sha256[:2]/sha256``.
    """

    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / ".tmp").mkdir(parents=True, exist_ok=True)

    async def put_stream(self, source, *, key: str | None = None, meta: dict | None = None) -> FileStat:
        hasher = sha256()
        size = 0
        fd, tmp_name = tempfile.mkstemp(prefix="upload-", dir=self.root / ".tmp")
        tmp_path = Path(tmp_name)
        os.close(fd)

        try:
            with tmp_path.open("wb") as target:
                async for chunk in _iter_source(source):
                    if not chunk:
                        continue
                    hasher.update(chunk)
                    size += len(chunk)
                    target.write(chunk)

            digest = hasher.hexdigest()
            final_key = key or f"{digest[:2]}/{digest}"
            final_path = self.path_for(final_key)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(tmp_path), final_path)

            return FileStat(
                key=final_key,
                size=size,
                sha256=digest,
                content_type=(meta or {}).get("content_type", "application/octet-stream"),
            )
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def open_stream(
        self,
        key: str,
        *,
        start: int | None = None,
        end: int | None = None,
    ) -> AsyncIterator[bytes]:
        """Open a byte stream.

        ``start`` and ``end`` are inclusive byte offsets when provided.
        """

        async def iterator():
            path = self.path_for(key)
            with path.open("rb") as source:
                if start is not None:
                    source.seek(start)
                remaining = None if end is None else end - (start or 0) + 1
                while True:
                    read_size = DEFAULT_CHUNK_SIZE if remaining is None else min(DEFAULT_CHUNK_SIZE, remaining)
                    if read_size <= 0:
                        break
                    chunk = source.read(read_size)
                    if not chunk:
                        break
                    if remaining is not None:
                        remaining -= len(chunk)
                    yield chunk

        return iterator()

    async def stat(self, key: str) -> FileStat:
        path = self.path_for(key)
        hasher = sha256()
        size = 0
        with path.open("rb") as source:
            while chunk := source.read(DEFAULT_CHUNK_SIZE):
                hasher.update(chunk)
                size += len(chunk)
        return FileStat(key=key, size=size, sha256=hasher.hexdigest())

    async def delete(self, key: str) -> None:
        self.path_for(key).unlink(missing_ok=True)

    def path_for(self, key: str) -> Path:
        path = (self.root / key).resolve()
        root = self.root.resolve()
        if path != root and root not in path.parents:
            raise ValueError(f"FileStore key escapes root: {key!r}")
        return path


async def _iter_source(source) -> AsyncIterator[bytes]:
    if isinstance(source, bytes):
        yield source
        return
    if isinstance(source, bytearray):
        yield bytes(source)
        return
    if isinstance(source, (str, os.PathLike, Path)):
        with Path(source).open("rb") as file_obj:
            while chunk := file_obj.read(DEFAULT_CHUNK_SIZE):
                yield chunk
        return

    read = getattr(source, "read", None)
    if callable(read):
        while True:
            chunk = read(DEFAULT_CHUNK_SIZE)
            if inspect.isawaitable(chunk):
                chunk = await chunk
            if not chunk:
                break
            yield chunk
        return

    raise TypeError(f"Unsupported file source: {type(source).__name__}")
