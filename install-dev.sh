#!/bin/bash
# Dev install: editable installs for all N3TX sub-packages
set -e

pip install -e packages/n3tx-core \
            -e packages/n3tx-actors \
            -e packages/n3tx-ui \
            -e packages/n3tx-agents \
            -e packages/n3tx

# Install esbuild for SSR bundling
CORE_STATIC="packages/n3tx-core/src/n3tx_core/static"
if [ -f "$CORE_STATIC/package.json" ]; then
    echo "Installing frontend build tools (esbuild)..."
    (cd "$CORE_STATIC" && npm install)
fi
