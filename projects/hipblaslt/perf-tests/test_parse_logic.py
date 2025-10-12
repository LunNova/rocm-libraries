#!/usr/bin/env python3
"""
Performance test for LibraryIO.parseLibraryLogicFile

Tests parsing performance on the largest logic YAML file in the repository.
"""

import os
import sys
import time
from pathlib import Path

# Add Tensile to path if not already available
try:
    from Tensile import LibraryIO
except ImportError:
    script_dir = Path(__file__).parent.resolve()
    tensile_path = script_dir.parent / "tensilelite"
    sys.path.insert(0, str(tensile_path))
    from Tensile import LibraryIO

from Tensile.Common.Architectures import gfxToIsa
from Tensile.Common.Capabilities import makeIsaInfoMap
from Tensile.Toolchain.Assembly import makeAssemblyToolchain
from Tensile.Toolchain.Validators import validateToolchain


def find_largest_logic_file(base_dir):
    """Find the largest .yaml logic file in the repository."""
    logic_dir = base_dir / "library/src/amd_detail/rocblaslt/src/Tensile/Logic"

    if not logic_dir.exists():
        raise FileNotFoundError(f"Logic directory not found: {logic_dir}")

    yaml_files = list(logic_dir.rglob("*.yaml"))
    if not yaml_files:
        raise FileNotFoundError(f"No YAML files found in {logic_dir}")

    # Sort by file size
    yaml_files.sort(key=lambda f: f.stat().st_size, reverse=True)

    largest = yaml_files[0]
    size_mb = largest.stat().st_size / (1024 * 1024)

    print(f"Found largest logic file: {largest.name}")
    print(f"Size: {size_mb:.2f} MB")
    print(f"Full path: {largest}")

    return largest


def setup_test_environment():
    """Set up the test environment with required parameters."""
    print("\n=== Setting up test environment ===")

    # Validate toolchain
    cxx_compiler = validateToolchain("amdclang++")
    print(f"C++ Compiler: {cxx_compiler}")

    # Target architecture (gfx942 since that's what the largest file targets)
    target_arch = "gfx942"
    target_isa = gfxToIsa(target_arch)
    print(f"Target Architecture: {target_arch} (ISA: {target_isa})")

    # Create ISA info map
    print("Creating ISA info map...")
    isa_info_map = makeIsaInfoMap([target_isa], cxx_compiler)

    # Create assembler toolchain
    print("Creating assembler toolchain...")
    asm_toolchain = makeAssemblyToolchain(
        assembler_path=cxx_compiler,
        bundler_path="clang-offload-bundler",
        co_version="default",
        build_id_kind="sha256",
        debug=False
    )

    return {
        "assembler": asm_toolchain.assembler,
        "isaInfoMap": isa_info_map,
        "splitGSU": False,
        "printSolutionRejectionReason": False,
        "printIndexAssignmentInfo": False,
        "lazyLibraryLoading": False
    }


def run_parse_test(logic_file, params):
    """Run the parse test and measure performance."""
    print("\n=== Running parse test ===")
    print(f"File: {logic_file}")
    print(f"Parameters:")
    print(f"  - splitGSU: {params['splitGSU']}")
    print(f"  - lazyLibraryLoading: {params['lazyLibraryLoading']}")
    print(f"  - printSolutionRejectionReason: {params['printSolutionRejectionReason']}")

    # Add profiling instrumentation to the YAML parser if in debug mode
    call_counts = {}
    if os.environ.get('DEBUG_YAML_PARSE'):
        from Tensile import CustomYamlLoader

        # Monkey-patch to count calls
        original_is_float = CustomYamlLoader.is_float
        original_parse_scalar = CustomYamlLoader.parse_scalar
        original_parse_mapping = CustomYamlLoader.parse_mapping

        call_counts = {'is_float': 0, 'parse_scalar': 0, 'parse_mapping': 0}

        def instrumented_is_float(value):
            call_counts['is_float'] += 1
            return original_is_float(value)

        def instrumented_parse_scalar(loader):
            call_counts['parse_scalar'] += 1
            return original_parse_scalar(loader)

        def instrumented_parse_mapping(loader):
            call_counts['parse_mapping'] += 1
            return original_parse_mapping(loader)

        CustomYamlLoader.is_float = instrumented_is_float
        CustomYamlLoader.parse_scalar = instrumented_parse_scalar
        CustomYamlLoader.parse_mapping = instrumented_parse_mapping

        print("\n[DEBUG] Instrumented YAML parser functions")

    print("\nStarting parse...")
    start_time = time.time()

    try:
        result = LibraryIO.parseLibraryLogicFile(
            str(logic_file),
            params["assembler"],
            params["splitGSU"],
            params["printSolutionRejectionReason"],
            params["printIndexAssignmentInfo"],
            params["isaInfoMap"],
            params["lazyLibraryLoading"]
        )

        end_time = time.time()
        elapsed = end_time - start_time

        print(f"\n=== Parse completed successfully ===")
        print(f"Time elapsed: {elapsed:.3f} seconds")

        # Extract results
        schedule, architecture, problem_type, solutions, exact_logic, library = result

        print(f"\nResults:")
        print(f"  - Schedule: {schedule}")
        print(f"  - Architecture: {architecture}")
        print(f"  - Number of solutions: {len(solutions)}")
        print(f"  - Problem type: {problem_type}")

        if exact_logic:
            print(f"  - Exact logic entries: {len(exact_logic)}")

        print(f"\nLibrary info:")
        print(f"  - Type: {type(library).__name__}")
        if hasattr(library, 'solutions'):
            print(f"  - Solutions in library: {len(library.solutions)}")

        # Print debug call counts if instrumented
        if call_counts:
            print(f"\n[DEBUG] YAML Parser Call Counts:")
            print(f"  - parse_mapping: {call_counts['parse_mapping']:,}")
            print(f"  - parse_scalar: {call_counts['parse_scalar']:,}")
            print(f"  - is_float: {call_counts['is_float']:,}")

        return elapsed, result

    except Exception as e:
        end_time = time.time()
        elapsed = end_time - start_time
        print(f"\n=== Parse failed after {elapsed:.3f} seconds ===")
        print(f"Error: {e}")
        raise


def main():
    """Main test entry point."""
    print("=" * 70)
    print("LibraryIO.parseLibraryLogicFile Performance Test")
    print("=" * 70)

    # Find project root and logic file
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent

    try:
        logic_file = find_largest_logic_file(project_root)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return 1

    # Set up test environment
    try:
        params = setup_test_environment()
    except Exception as e:
        print(f"ERROR setting up environment: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Run the test
    try:
        elapsed, result = run_parse_test(logic_file, params)

        print("\n" + "=" * 70)
        print(f"SUCCESS: Parse completed in {elapsed:.3f} seconds")
        print("=" * 70)

        return 0

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
