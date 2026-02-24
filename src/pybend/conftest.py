# conftest.py at pybend level — prevents broken __init__.py from interfering.
# This conftest is loaded by pytest BEFORE __init__.py gets auto-imported.
import sys
import types
import os

# Pre-register pybend and its subpackages as dummy modules
# so Python will NOT load the broken __init__.py files.
for name in ('pybend', 'pybend.core', 'pybend.core.api',
             'pybend.core.models', 'pybend.core.storage',
             'pybend.core.utils', 'pybend.core.authorize',
             'pybend.core.tests', 'pybend.core.tests.unit'):
    if name not in sys.modules:
        m = types.ModuleType(name)
        m.__path__ = []
        m.__package__ = name
        sys.modules[name] = m

# Ensure core/ is on sys.path for direct imports
_core = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'core')
if _core not in sys.path:
    sys.path.insert(0, _core)
