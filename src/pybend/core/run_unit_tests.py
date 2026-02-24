#!/usr/bin/env python3
"""
Runner script for PyBend unit tests.
Shims the broken pybend/__init__.py before pytest starts,
then invokes pytest on the unit test directory.
"""
import sys
import types
import os

# Shim the broken packages BEFORE pytest starts
for name in ('pybend', 'pybend.core'):
    m = types.ModuleType(name)
    m.__path__ = []
    m.__package__ = name
    sys.modules[name] = m

# Ensure core is on path
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

# Run pytest
sys.exit(
    __import__('pytest').main([
        'tests/unit/',
        '-v',
        '--tb=short',
        '--override-ini=pythonpath=.',
        '--rootdir=.',
        '-p', 'no:cacheprovider',
    ] + sys.argv[1:])
)
