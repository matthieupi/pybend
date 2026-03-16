"""Local deployment config — edit these values per deployment."""
import os

# Import framework config and override
from n3tx_core import config as _fw

# Deployment settings (edit these)
HOST = os.environ.get("N3TX_HOST", "0.0.0.0")
PORT = int(os.environ.get("N3TX_PORT", "5000"))
API_URL = os.environ.get("N3TX_API_URL", f"http://localhost:{PORT}")
SQLITE_DB_FILE = os.environ.get("N3TX_SQLITE_DB", "n3tx.db")
JWT_SECRET = os.environ.get("N3TX_JWT_SECRET", "ntx-dev-secret-change-in-production")
JWT_EXPIRY_HOURS = int(os.environ.get("N3TX_JWT_EXPIRY_HOURS", "24"))
DEBUG = os.environ.get("N3TX_DEBUG", "true").lower() == "true"
SSR = os.environ.get("N3TX_SSR", "full")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://172.20.0.1:11434")
DEFAULT_LLM = os.environ.get("N3TX_CHAT_LLM", "ollama:qwen3.5:9b")
# Agent LLM — default to qwen via Ollama, override with N3TX_AGENT_DEFAULTS env
if not os.environ.get("N3TX_AGENT_DEFAULTS"):
    os.environ["N3TX_AGENT_DEFAULTS"] = '{"llm": "ollama:qwen3.5:9b"}'

# Propagate to framework (required for schema URLs, etc.)
_fw.configure(host=HOST, port=PORT, api_url=API_URL,
              sqlite_db_file=SQLITE_DB_FILE, jwt_secret=JWT_SECRET,
              jwt_expiry_hours=JWT_EXPIRY_HOURS, debug=DEBUG, ssr=SSR,
              ollama_base_url=OLLAMA_BASE_URL)
