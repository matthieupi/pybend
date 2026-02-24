# Root conftest for test discovery at core/ level.
# Prevents the broken parent pybend/__init__.py from being imported.
import sys
import types
import os

# Pre-register package shims so Python won't attempt to load pybend/__init__.py
for name in ('pybend', 'pybend.core', 'pybend.core.api', 'pybend.core.models',
             'pybend.core.storage', 'pybend.core.utils', 'pybend.core.authorize',
             'pybend.core.tests', 'pybend.core.tests.unit'):
    if name not in sys.modules:
        m = types.ModuleType(name)
        m.__path__ = []
        m.__package__ = name
        sys.modules[name] = m

# Ensure core/ is on sys.path for direct imports
_core = os.path.dirname(os.path.abspath(__file__))
if _core not in sys.path:
    sys.path.insert(0, _core)
