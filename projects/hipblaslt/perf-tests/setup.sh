#!/usr/bin/env bash
# Copyright Advanced Micro Devices, Inc., or its affiliates.
# SPDX-License-Identifier: MIT

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ROCISA_DIR="$PROJECT_ROOT/tensilelite/rocisa"
BUILD_DIR="$SCRIPT_DIR/build"

# Check if rocisa.so already exists
ROCISA_MODULE=$(find "$BUILD_DIR" -name "rocisa*.so" 2>/dev/null | head -1)

if [ -z "$ROCISA_MODULE" ]; then
    # Need to build
    # Check for ROCM_PATH
    if [ -z "${ROCM_PATH:-}" ]; then
        if [ -d "/opt/rocm" ]; then
            export ROCM_PATH="/opt/rocm"
        else
            echo "ERROR: Could not find ROCm installation. Please set ROCM_PATH."
            exit 1
        fi
    fi

    # Check for compiler
    CXX_COMPILER="${ROCM_PATH}/bin/amdclang++"
    if [ ! -x "$CXX_COMPILER" ]; then
        echo "ERROR: amdclang++ not found at $CXX_COMPILER"
        exit 1
    fi

    # Create a wrapper CMakeLists.txt for standalone rocisa build
    mkdir -p "$BUILD_DIR"
    cat > "$BUILD_DIR/CMakeLists.txt" << 'EOF'
cmake_minimum_required(VERSION 3.16)
project(rocisa_standalone LANGUAGES CXX)

# Find Python with development components
find_package(Python 3.8 REQUIRED COMPONENTS Interpreter Development.Module)

set(HIPBLASLT_BUNDLE_PYTHON_DEPS ON)
add_subdirectory("${ROCISA_SOURCE_DIR}" rocisa)
EOF

    cd "$BUILD_DIR"

    cmake \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CXX_COMPILER="$CXX_COMPILER" \
        -DROCISA_SOURCE_DIR="$ROCISA_DIR" \
        . > /dev/null

    make -j$(nproc) > /dev/null

    # Check if rocisa.so was built
    ROCISA_MODULE=$(find "$BUILD_DIR" -name "rocisa*.so" 2>/dev/null | head -1)
    if [ -z "$ROCISA_MODULE" ]; then
        echo "ERROR: rocisa module not built successfully"
        exit 1
    fi
fi

ROCISA_LIB_DIR=$(dirname "$ROCISA_MODULE")

# Set up Python path and run the test
export PYTHONPATH="$ROCISA_LIB_DIR:$PROJECT_ROOT/tensilelite:${PYTHONPATH:-}"

cd "$SCRIPT_DIR"

# Check if first argument is "exec" for passthrough command execution
if [ "${1:-}" = "exec" ]; then
    shift  # Remove "exec" from arguments
    echo "=== Executing command with configured environment ==="
    echo "Command: $*"
    echo ""
    exec "$@"
fi

# Check for profiler flags
PROFILER="${PROFILER:-}"
TEST_SCRIPT="${TEST_SCRIPT:-test_parse_logic.py}"

# Extract script name without extension for output filenames
SCRIPT_BASENAME=$(basename "$TEST_SCRIPT" .py)
# Generate timestamp in MMDDHHMMSS format
TIMESTAMP=$(date +"%m%d%H%M%S")

if [ "$PROFILER" = "memray" ]; then
    echo "Running with memray profiler..."
    if ! command -v memray &> /dev/null; then
        echo "ERROR: memray not found. Install with: pip install memray"
        exit 1
    fi
    MEMRAY_OUTPUT="${SCRIPT_BASENAME}_${TIMESTAMP}.bin"
    python3 -O -m memray run --output "$MEMRAY_OUTPUT" "$TEST_SCRIPT" "$@"
    echo ""
    echo "Memray output saved to: $MEMRAY_OUTPUT"
elif [ "$PROFILER" = "py-spy" ]; then
    echo "Running with py-spy profiler..."
    if ! command -v py-spy &> /dev/null; then
        echo "ERROR: py-spy not found. Install with: pip install py-spy"
        exit 1
    fi
    PYSPY_JSON="${SCRIPT_BASENAME}_${TIMESTAMP}_profile.json"
    PYSPY_SVG="${SCRIPT_BASENAME}_${TIMESTAMP}_flamegraph.svg"
    py-spy record --format speedscope --output "$PYSPY_JSON" -- python3 -O "$TEST_SCRIPT" "$@"
    py-spy record --format flamegraph --output "$PYSPY_SVG" -- python3 -O "$TEST_SCRIPT" "$@"
    echo ""
    echo "Saved: $PYSPY_SVG, $PYSPY_JSON"
else
    python3 -O "$TEST_SCRIPT" "$@"
fi
