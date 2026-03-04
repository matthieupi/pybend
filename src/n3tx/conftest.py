# conftest.py at n3tx level — prevents broken __init__.py from interfering.
# This conftest is loaded by pytest BEFORE __init__.py gets auto-imported.
import sys
import types
import os

_n3tx = os.path.dirname(os.path.abspath(__file__))
_core = os.path.join(_n3tx, 'core')

# Pre-register n3tx and its subpackages as namespace shims with real paths
# so Python will NOT load the broken __init__.py files but CAN resolve submodules.
_namespace_shims = {
    'n3tx':               _n3tx,
    'n3tx.core':          _core,
    'n3tx.core.api':      os.path.join(_core, 'api'),
    'n3tx.core.models':   os.path.join(_core, 'models'),
    'n3tx.core.storage':  os.path.join(_core, 'storage'),
    'n3tx.core.utils':    os.path.join(_core, 'utils'),
    'n3tx.core.authorize': os.path.join(_core, 'authorize'),
    'n3tx.core.tests':    os.path.join(_core, 'tests'),
    'n3tx.core.tests.unit': os.path.join(_core, 'tests', 'unit'),
}

for name, path in _namespace_shims.items():
    if name not in sys.modules:
        m = types.ModuleType(name)
        m.__path__ = [path]
        m.__package__ = name
        sys.modules[name] = m

# Ensure core/ is on sys.path for direct imports
if _core not in sys.path:
    sys.path.insert(0, _core)
