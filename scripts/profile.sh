#!/bin/bash
#
# Performance profiling pipeline for PyBend.
#
# Usage:
#   ./scripts/profile.sh baseline          # Run API + E2E profiling (all tiers)
#   ./scripts/profile.sh optimized         # Run API + E2E profiling (after optimizations)
#   ./scripts/profile.sh compare           # Compare baseline vs optimized
#   ./scripts/profile.sh full              # Stash -> baseline -> unstash -> optimized -> compare
#   ./scripts/profile.sh e2e <label>       # Run only Playwright E2E perf tests
#   ./scripts/profile.sh api-only <label>  # Run only API profiling (no E2E)
#   ./scripts/profile.sh dashboard         # Launch the profiling dashboard
#
# Output goes to .traces/.profiling/ in the workspace root.

set -euo pipefail

WORKSPACE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$WORKSPACE"

PROFILING_DIR=".traces/.profiling"
mkdir -p "$PROFILING_DIR"

PYTHON="${PYTHON:-python3}"
export PYTHONPATH="${WORKSPACE}/src${PYTHONPATH:+:$PYTHONPATH}"
E2E_DIR="src/pybend/static/tests/e2e"

run_api_profile() {
    local label="$1"
    echo ""
    echo "=========================================="
    echo " API Profiling: $label"
    echo "=========================================="
    $PYTHON -m pybend.core.tests.profiling.run_profile "$label"
}

run_e2e_profile() {
    local label="$1"
    local tier="${2:-full}"
    echo ""
    echo "=========================================="
    echo " Playwright E2E Profiling: $label (tier=$tier)"
    echo "=========================================="
    cd "$WORKSPACE/$E2E_DIR"
    PERF_LABEL="$label" PERF_TIER="$tier" PYBEND_PROFILING_DIR="$WORKSPACE/$PROFILING_DIR" npx playwright test --config playwright.perf.config.js
    cd "$WORKSPACE"
}

run_compare() {
    echo ""
    echo "=========================================="
    echo " Comparing baseline vs optimized"
    echo "=========================================="
    $PYTHON -m pybend.core.tests.profiling.compare \
        "$PROFILING_DIR/api_perf_baseline.json" \
        "$PROFILING_DIR/api_perf_optimized.json"
}

case "${1:-help}" in
    baseline)
        run_api_profile baseline
        run_e2e_profile baseline
        ;;
    optimized)
        run_api_profile optimized
        run_e2e_profile optimized
        ;;
    compare)
        run_compare
        ;;
    e2e)
        label="${2:-run}"
        tier="${3:-full}"
        run_e2e_profile "$label" "$tier"
        ;;
    dashboard)
        echo "Launching profiling dashboard at http://localhost:5555"
        $PYTHON -m pybend.core.tests.profiling.dashboard
        ;;
    full)
        echo "=== Full profiling pipeline ==="

        # 1. Stash current changes
        echo "Stashing current changes..."
        if ! git diff --quiet src/pybend/core/models/proto_model.py 2>/dev/null; then
            git stash push -m "perf: auto-stash for profiling" -- src/pybend/core/models/proto_model.py
            STASHED=1
        else
            echo "  (no changes to stash)"
            STASHED=0
        fi

        # 2. Run baseline (API + E2E)
        run_api_profile baseline
        run_e2e_profile baseline

        # 3. Unstash
        if [ "$STASHED" = "1" ]; then
            echo "Restoring stashed changes..."
            git stash pop
        fi

        # 4. Run optimized (API + E2E)
        run_api_profile optimized
        run_e2e_profile optimized

        # 5. Compare
        run_compare
        ;;
    api-only)
        echo "=== API-only profiling (no E2E) ==="
        label="${2:-baseline}"
        run_api_profile "$label"
        ;;
    help|--help|-h)
        echo "Usage: ./scripts/profile.sh <command>"
        echo ""
        echo "Commands:"
        echo "  baseline      Run API + E2E profiling at all data tiers"
        echo "  optimized     Run API + E2E profiling at all data tiers (after optimizations)"
        echo "  compare       Compare baseline vs optimized results"
        echo "  e2e <label>   Run only Playwright E2E performance tests"
        echo "  api-only <l>  Run only API profiling (no E2E)"
        echo "  full          Stash -> baseline -> unstash -> optimized -> compare (API + E2E)"
        echo "  dashboard     Launch the profiling dashboard web UI"
        echo ""
        echo "Output: .traces/.profiling/"
        ;;
    *)
        echo "Unknown command: $1"
        echo "Run ./scripts/profile.sh help for usage."
        exit 1
        ;;
esac
