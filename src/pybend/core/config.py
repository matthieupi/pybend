import logging
import os

logger = logging.getLogger('pybend.config')

#
BACKEND = "fastapi"  # or "flask"
VERSION = "0.7.0"
HOST = "0.0.0.0"
PORT = 5000
API_URL = f"http://localhost:{PORT}"

# Filesystem configuration
SQLITE_DB_FILE = "pybend.db"

# Auth configuration
JWT_SECRET = os.getenv("PYBEND_JWT_SECRET", "pybend-dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.getenv("PYBEND_JWT_EXPIRY_HOURS", "24"))

# Debug mode — controls error detail in API responses
DEBUG = os.getenv("PYBEND_DEBUG", "false").lower() in ("1", "true")

# SSR configuration
SSR = os.getenv("PYBEND_SSR", "off").lower()  # "off" | "schema" | "bundle" | "full"

# Apply PYBEND_* environment variable overrides (if set)
if os.getenv("PYBEND_BACKEND"):
    BACKEND = os.environ["PYBEND_BACKEND"]
if os.getenv("PYBEND_HOST"):
    HOST = os.environ["PYBEND_HOST"]
if os.getenv("PYBEND_PORT"):
    PORT = int(os.environ["PYBEND_PORT"])
    API_URL = f"http://localhost:{PORT}"
if os.getenv("PYBEND_API_URL"):
    API_URL = os.environ["PYBEND_API_URL"]
if os.getenv("PYBEND_SQLITE_DB"):
    SQLITE_DB_FILE = os.environ["PYBEND_SQLITE_DB"]
if os.getenv("PYBEND_SSR"):
    SSR = os.environ["PYBEND_SSR"].lower()


def configure(**kwargs):
    """Override config values programmatically.

    Example::

        from pybend.core import config
        config.configure(host="127.0.0.1", port=8080, debug=False)
    """
    g = globals()
    for key, value in kwargs.items():
        key_upper = key.upper()
        if key_upper in g:
            g[key_upper] = value
        else:
            raise ValueError(f"Unknown config key: {key}")
