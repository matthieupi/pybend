"""N3TX Files — actor-backed file metadata and byte stores.

The package is optional. Importing it exposes the public file primitives but
does not make n3tx-core depend on file storage.
"""

from .file import File, configure_file_store, get_file_store
from .store import FileStat, FileStore, LocalFileStore

# Register optional core extension hooks only when n3tx_files is imported.
from . import materialize as _materialize  # noqa: F401

__all__ = [
    "File",
    "FileStat",
    "FileStore",
    "LocalFileStore",
    "configure_file_store",
    "get_file_store",
]
