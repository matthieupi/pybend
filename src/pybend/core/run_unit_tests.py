#!/usr/bin/env python3
"""
Runner script for PyBend unit tests only.

Bootstraps the same shims as run_tests.py / conftest.py (TI-3).

Usage: cd /workspace/src/pybend/core && python3 run_unit_tests.py [pytest args...]
"""
import sys
import types
import os

_core = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _core)
_src = os.path.dirname(os.path.dirname(_core))

# Pre-register namespace shims (mirrors conftest.py — TI-3 canonical source)
_namespace_shims = {
    'pybend':           os.path.join(_src, 'pybend'),
    'pybend.core':      _core,
    'pybend.example_api':   os.path.join(_src, 'pybend', 'example_api'),
    'pybend.example_actor':   os.path.join(_src, 'pybend', 'example_actor'),
}

for name, path in _namespace_shims.items():
    if name not in sys.modules:
        m = types.ModuleType(name)
        m.__path__ = [path]
        m.__package__ = name
        sys.modules[name] = m

os.environ.setdefault('GENERATE_DOCS', 'false')

import pytest
sys.exit(
    pytest.main([
        'tests/unit/',
        '-v',
        '--tb=short',
        '--rootdir', _core,
        '-p', 'no:cacheprovider',
    ] + sys.argv[1:])
)
