# conftest.py at pybend level — prevents broken __init__.py from interfering.
# This conftest is loaded by pytest BEFORE __init__.py gets auto-imported.
import sys
import types
import os

_pybend = os.path.dirname(os.path.abspath(__file__))
_core = os.path.join(_pybend, 'core')
_example = os.path.join(_pybend, 'example')

# Pre-register pybend and its subpackages as namespace shims with real paths
# so Python will NOT load the broken __init__.py files but CAN resolve submodules.
_namespace_shims = {
    'pybend':               _pybend,
    'pybend.core':          _core,
    'pybend.core.api':      os.path.join(_core, 'api'),
    'pybend.core.models':   os.path.join(_core, 'models'),
    'pybend.core.storage':  os.path.join(_core, 'storage'),
    'pybend.core.utils':    os.path.join(_core, 'utils'),
    'pybend.core.authorize': os.path.join(_core, 'authorize'),
    'pybend.core.tests':    os.path.join(_core, 'tests'),
    'pybend.core.tests.unit': os.path.join(_core, 'tests', 'unit'),
    'pybend.example':       _example,
    'pybend.example.tests': os.path.join(_example, 'tests'),
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
