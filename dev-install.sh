#!/bin/bash
# Dev install: editable installs for all N3TX sub-packages
set -e

pip install -e packages/n3tx-core \
            -e packages/n3tx-actors \
            -e packages/n3tx-ui \
            -e packages/n3tx-agents \
            -e packages/n3tx
