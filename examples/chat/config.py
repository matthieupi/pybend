"""Local deployment config for the chat example."""
import os

from n3tx.core import config as _fw

HOST = os.environ.get("N3TX_HOST", "0.0.0.0")
PORT = int(os.environ.get("N3TX_PORT", "5000"))
API_URL = os.environ.get("N3TX_API_URL", f"http://localhost:{PORT}")
SQLITE_DB_FILE = os.environ.get("N3TX_SQLITE_DB", "chat.db")
JWT_SECRET = os.environ.get("N3TX_JWT_SECRET", "ntx-chat-dev-secret")
JWT_EXPIRY_HOURS = int(os.environ.get("N3TX_JWT_EXPIRY_HOURS", "24"))
DEBUG = os.environ.get("N3TX_DEBUG", "true").lower() == "true"
SSR = os.environ.get("N3TX_SSR", "full")

# LLM
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://172.20.0.1:11434")
DEFAULT_LLM = os.environ.get("N3TX_CHAT_LLM", "ollama:qwen3.5:9b")

_fw.configure(host=HOST, port=PORT, api_url=API_URL,
              sqlite_db_file=SQLITE_DB_FILE, jwt_secret=JWT_SECRET,
              jwt_expiry_hours=JWT_EXPIRY_HOURS, debug=DEBUG, ssr=SSR,
              ollama_base_url=OLLAMA_BASE_URL)
