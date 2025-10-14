#!/usr/bin/env bash
# Copyright Advanced Micro Devices, Inc., or its affiliates.
# SPDX-License-Identifier: MIT
#
# Benchmark test_parse_logic.py across a range of commits
# Usage: ./benchmark_commits.sh [base_ref] [head_ref]
#   base_ref: Starting commit/branch (default: develop)
#   head_ref: Ending commit/branch (default: HEAD)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_REF="${1:-develop}"
HEAD_REF="${2:-HEAD}"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================================================"
echo "Benchmarking test_parse_logic.py across commits"
echo "========================================================================"
echo "Range: ${BASE_REF}..${HEAD_REF}"
echo ""

# Get list of commits in reverse order (oldest first)
COMMITS=$(git rev-list --reverse "${BASE_REF}..${HEAD_REF}")

if [ -z "$COMMITS" ]; then
    echo "No commits found in range ${BASE_REF}..${HEAD_REF}"
    exit 1
fi

COMMIT_COUNT=$(echo "$COMMITS" | wc -l)
echo "Found ${COMMIT_COUNT} commits to benchmark"
echo ""

# Store current branch/commit to restore later
ORIGINAL_HEAD=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || git rev-parse HEAD)

# Function to restore original state on exit
cleanup() {
    echo ""
    echo "Restoring original state..."
    git checkout -q "$ORIGINAL_HEAD"
}
trap cleanup EXIT

CURRENT=1
for COMMIT in $COMMITS; do
    echo "========================================================================"
    echo -e "${BLUE}[${CURRENT}/${COMMIT_COUNT}]${NC} Benchmarking commit $(git rev-parse --short "$COMMIT")"
    echo "========================================================================"

    # Show commit info
    git log -1 --pretty=format:"Commit: %h%nAuthor: %an%nDate:   %ad%nSubject: %s%n" --date=short "$COMMIT"
    echo ""

    # Checkout the commit
    git checkout -q "$COMMIT"

    # Run the benchmark with quiet mode enabled
    echo ""
    echo "Running test_parse_logic.py..."
    QUIET=1 "$SCRIPT_DIR/setup.sh" exec python3 "$SCRIPT_DIR/test_parse_logic.py" 2>&1 | \
        grep -E "(SUCCESS:|Peak memory usage:|Time elapsed:)" || true

    echo ""
    CURRENT=$((CURRENT + 1))
done

echo "========================================================================"
echo -e "${GREEN}Benchmark complete!${NC}"
echo "========================================================================"
