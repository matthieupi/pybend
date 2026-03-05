import logging
import os

logger = logging.getLogger('n3tx.config')

#
BACKEND = "fastapi"  # or "flask"
VERSION = "0.7.0"
HOST = "0.0.0.0"
PORT = 5000
API_URL = f"http://localhost:{PORT}"

# Filesystem configuration
SQLITE_DB_FILE = "n3tx.db"

# Auth configuration
JWT_SECRET = os.getenv("N3TX_JWT_SECRET", "ntx-dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.getenv("N3TX_JWT_EXPIRY_HOURS", "24"))

# Debug mode — controls error detail in API responses
DEBUG = os.getenv("N3TX_DEBUG", "false").lower() in ("1", "true")

# SSR configuration
SSR = os.getenv("N3TX_SSR", "off").lower()  # "off" | "schema" | "bundle" | "full"

# Apply N3TX_* environment variable overrides (if set)
if os.getenv("N3TX_BACKEND"):
    BACKEND = os.environ["N3TX_BACKEND"]
if os.getenv("N3TX_HOST"):
    HOST = os.environ["N3TX_HOST"]
if os.getenv("N3TX_PORT"):
    PORT = int(os.environ["N3TX_PORT"])
    API_URL = f"http://localhost:{PORT}"
if os.getenv("N3TX_API_URL"):
    API_URL = os.environ["N3TX_API_URL"]
if os.getenv("N3TX_SQLITE_DB"):
    SQLITE_DB_FILE = os.environ["N3TX_SQLITE_DB"]
if os.getenv("N3TX_SSR"):
    SSR = os.environ["N3TX_SSR"].lower()


def configure(**kwargs):
    """Override config values programmatically.

    Example::

        from n3tx.core import config
        config.configure(host="127.0.0.1", port=8080, debug=False)
    """
    g = globals()
    for key, value in kwargs.items():
        key_upper = key.upper()
        if key_upper in g:
            g[key_upper] = value
        else:
            raise ValueError(f"Unknown config key: {key}")
