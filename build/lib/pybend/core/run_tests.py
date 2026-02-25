#!/usr/bin/env python3
"""
Test runner for ALL PyBend tests (unit + integration).

The shims MUST be registered BEFORE pytest starts, because pytest may
discover pybend/__init__.py during collection (before conftest.py runs).
conftest.py at core/ level is the canonical reference, but this file
bootstraps the same shims to ensure they're in place before pytest.main().

Usage: cd /workspace/src/pybend/core && python3 run_tests.py [pytest args...]

Examples:
    python3 run_tests.py -v
    python3 run_tests.py tests/test_schema_endpoints.py -v
    python3 run_tests.py -x --tb=short
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
    'pybend.example':   os.path.join(_src, 'pybend', 'example'),
}

for name, path in _namespace_shims.items():
    if name not in sys.modules:
        m = types.ModuleType(name)
        m.__path__ = [path]
        m.__package__ = name
        sys.modules[name] = m

os.environ.setdefault('GENERATE_DOCS', 'false')

import pytest
args = sys.argv[1:] if len(sys.argv) > 1 else ['-v', 'tests/']
args = ['--rootdir', _core] + args
sys.exit(pytest.main(args))
