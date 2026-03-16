"""N3TX -- Schema-driven full-stack framework for Python.

This is the legacy package location. The framework has been split into:
    - n3tx-core: Models, storage, API, auth, utils
    - n3tx-actors: Actor system, network adapters
    - n3tx-ui: Frontend components and themes
    - n3tx-agents: LLM-powered agent system
    - n3tx (meta-package): Re-exports from all packages

Install the meta-package: pip install n3tx
Or install individual packages: pip install n3tx-core n3tx-actors
"""

# Redirect to new package locations
from n3tx_core import *  # noqa: F401,F403
from n3tx_actors import *  # noqa: F401,F403

try:
    from n3tx_agents import *  # noqa: F401,F403
except ImportError:
    pass  # n3tx-agents is optional (requires pydantic-ai)

__version__ = "0.10.0"
