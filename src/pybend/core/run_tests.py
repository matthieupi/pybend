#!/usr/bin/env python3
"""
Test runner that patches the module table before pytest loads.
Usage: cd /workspace/src/pybend/core && python3 run_tests.py [pytest args...]

Examples:
    python3 run_tests.py -v
    python3 run_tests.py tests/test_schema_endpoints.py -v
    python3 run_tests.py -x --tb=short
"""
import sys
import types
import os

# Ensure core/ is on path first
_core = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _core)

# Block broken parent __init__.py from loading by pre-registering dummy packages
for name, path in [
    ('pybend', os.path.dirname(_core)),
    ('pybend.core', _core),
]:
    m = types.ModuleType(name)
    m.__path__ = [path]
    m.__package__ = name
    sys.modules[name] = m

# Set rootdir so pytest doesn't traverse up
os.environ.setdefault('GENERATE_DOCS', 'false')

import pytest
args = sys.argv[1:] if len(sys.argv) > 1 else ['-v', 'tests/']
# Force rootdir to core to prevent traversal
args = ['--rootdir', _core] + args
sys.exit(pytest.main(args))
