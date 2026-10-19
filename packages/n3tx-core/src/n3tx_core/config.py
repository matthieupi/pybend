import logging
import os
import json as _json

# Configure root 'n3tx' logger so all child loggers emit to console.
# Default level: WARNING. Set N3TX_LOG_LEVEL=DEBUG (or INFO, ERROR, etc.) to change.

#
BACKEND = "fastapi"  # or "flask"
VERSION = "0.7.0"
HOST = "0.0.0.0"
PORT = 5000
API_URL = f"http://localhost:{PORT}"

# Distributed service identity / remote service configuration
SERVICE_NAME = os.getenv("N3TX_SERVICE_NAME", "api")
SERVICE_TOKEN = os.getenv("N3TX_SERVICE_TOKEN", "")
REMOTES = _json.loads(os.getenv("N3TX_REMOTES", "{}") or "{}")

# Filesystem configuration
SQLITE_DB_FILE = "n3tx.db"

# Auth configuration
JWT_SECRET = os.getenv("N3TX_JWT_SECRET", "ntx-dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.getenv("N3TX_JWT_EXPIRY_HOURS", "24"))

# Debug mode — controls error detail in API responses
DEBUG = os.getenv("N3TX_DEBUG", "false").lower() in ("1", "true")

# SSR configuration
SSR = os.getenv("N3TX_SSR", "off").lower()  # "off" | "schema" | "bundle" | "full"

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Agent configuration (global defaults, overridable per-model via __agent__)
AGENT_DEFAULTS = {
    'self_tools': True,       # auto-discover own CRUD + methods
    'neighbors': True,        # auto-discover relationship neighbor tools
    'neighbor_depth': 1,      # levels of relationships to follow
    'llm': 'ollama:llama3.1', # default LLM provider:model string
}

if os.getenv("N3TX_AGENT_DEFAULTS"):
    AGENT_DEFAULTS.update(_json.loads(os.environ["N3TX_AGENT_DEFAULTS"]))

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
if os.getenv("N3TX_SERVICE_NAME"):
    SERVICE_NAME = os.environ["N3TX_SERVICE_NAME"]
if os.getenv("N3TX_SERVICE_TOKEN"):
    SERVICE_TOKEN = os.environ["N3TX_SERVICE_TOKEN"]
if os.getenv("N3TX_REMOTES"):
    REMOTES = _json.loads(os.environ["N3TX_REMOTES"] or "{}")
if os.getenv("N3TX_SQLITE_DB"):
    SQLITE_DB_FILE = os.environ["N3TX_SQLITE_DB"]
if os.getenv("N3TX_SSR"):
    SSR = os.environ["N3TX_SSR"].lower()
if os.getenv("OLLAMA_BASE_URL"):
    OLLAMA_BASE_URL = os.environ["OLLAMA_BASE_URL"]

LOG_LEVEL = "DEBUG" if DEBUG else "WARNING"
LOG_LEVEL = os.getenv("N3TX_LOG_LEVEL", LOG_LEVEL).upper()
_n3tx_logger = logging.getLogger('n3tx')
if not _n3tx_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(levelname)s %(name)s: %(message)s'))
    _n3tx_logger.addHandler(_handler)
_n3tx_logger.setLevel(getattr(logging, LOG_LEVEL, logging.WARNING))

logger = logging.getLogger('n3tx.config')

def configure(**kwargs):
    """Override config values programmatically.

    Example::

        from n3tx_core import config
        config.configure(host="127.0.0.1", port=8080, debug=False)
    """
    g = globals()
    for key, value in kwargs.items():
        key_upper = key.upper()
        if key_upper in g:
            g[key_upper] = value
        else:
            raise ValueError(f"Unknown config key: {key}")
