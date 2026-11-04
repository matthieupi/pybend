#!/bin/bash
# Dev install: editable installs for all N3TX sub-packages
set -e
# 0. Install local packages with threads before its agent consumers.
pip install -e packages/n3tx-core \
            -e packages/n3tx-actors \
            -e packages/n3tx-ui \
            -e packages/n3tx-threads \
            -e packages/n3tx-agents \
            -e packages/n3tx-files \
            -e packages/n3tx
# 1. Install esbuild for SSR bundling when core declares frontend tooling.
CORE_STATIC="packages/n3tx-core/src/n3tx_core/static"
if [ -f "$CORE_STATIC/package.json" ]; then
    echo "Installing frontend build tools (esbuild)..."
    (cd "$CORE_STATIC" && npm install)
fi

# Changelog
# - 2026-11-02: Include n3tx-threads before n3tx-agents in editable installs.
