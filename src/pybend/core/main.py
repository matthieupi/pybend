"""
PyBend core main — delegates to example_api app for backward compatibility.
Run the example app directly: python -m pybend.example_api.main
"""
import os
import sys

# Backward compatibility: expose the example app so existing imports
# like ``from pybend.core.main import app`` continue to work.
os.environ.setdefault("GENERATE_DOCS", "false")

from pybend.example_api.main import app  # noqa: F401 — re-export for compat

if __name__ == '__main__':
    import uvicorn
    from pybend.core import config
    uvicorn.run(app, host=config.HOST, port=config.PORT)
