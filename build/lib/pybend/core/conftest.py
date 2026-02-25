# Root conftest for test discovery at core/ level.
#
# This is the SINGLE AUTHORITY for import path setup (TI-3).
# run_tests.py and run_unit_tests.py delegate to this via pytest's conftest
# chain.  No other file should duplicate this logic.
#
# Prevents the parent pybend/__init__.py and pybend/core/__init__.py from
# being imported (they contain real imports that cause circular issues during
# test discovery).  Only top-level namespace packages are shimmed; subpackages
# (authorize, models, api, etc.) load their real __init__.py from disk.
import sys
import types
import os

# Ensure core/ is on sys.path for direct imports
_core = os.path.dirname(os.path.abspath(__file__))
if _core not in sys.path:
    sys.path.insert(0, _core)

# Derive the src/ directory for resolving package paths
_src = os.path.dirname(os.path.dirname(_core))

# Only shim the top-level namespace packages whose __init__.py would cause
# circular import issues.  Subpackages (authorize, models, storage, etc.)
# have valid __init__.py files and should load normally from disk.
_namespace_shims = {
    'pybend':               os.path.join(_src, 'pybend'),
    'pybend.core':          _core,
    'pybend.core.tests':    os.path.join(_core, 'tests'),
    'pybend.core.tests.unit': os.path.join(_core, 'tests', 'unit'),
    'pybend.example':       os.path.join(_src, 'pybend', 'example'),
    'pybend.example.tests': os.path.join(_src, 'pybend', 'example', 'tests'),
}

for name, path in _namespace_shims.items():
    if name not in sys.modules:
        m = types.ModuleType(name)
        m.__path__ = [path]
        m.__package__ = name
        sys.modules[name] = m
