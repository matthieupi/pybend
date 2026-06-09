"""Configuration for the optional n3tx-files package."""

from __future__ import annotations

import os
from pathlib import Path


FILE_STORE_DIR = Path(os.getenv("N3TX_FILE_STORE_DIR", ".n3tx-files/blobs"))
