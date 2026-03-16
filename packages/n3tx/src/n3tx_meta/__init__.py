"""N3TX meta-package — re-exports from n3tx_core, n3tx_actors, n3tx_agents."""

from n3tx_core import *  # noqa: F401,F403
from n3tx_actors import *  # noqa: F401,F403

try:
    from n3tx_agents import *  # noqa: F401,F403
except ImportError:
    pass  # n3tx-agents is optional (requires pydantic-ai)
