#!/usr/bin/env python3
"""
Full TensileCreateLibrary test for performance profiling.

Tests the complete TensileCreateLibrary pipeline on a single large YAML file
for gfx942, ideal for profiling YAML parsing and memory optimization.
"""

import argparse
import os
import sys
import tempfile
import shutil
from pathlib import Path
from timeit import default_timer as timer

# Add Tensile to path if not already available
try:
    from Tensile.TensileCreateLibrary import ParseArguments
except ImportError:
    script_dir = Path(__file__).parent.resolve()
    tensile_path = script_dir.parent / "tensilelite"
    sys.path.insert(0, str(tensile_path))
    from Tensile.TensileCreateLibrary import ParseArguments


def find_largest_gfx942_logic_file(base_dir):
    """Find the largest gfx942 .yaml logic file in the repository."""
    logic_dir = base_dir / "library/src/amd_detail/rocblaslt/src/Tensile/Logic"

    if not logic_dir.exists():
        raise FileNotFoundError(f"Logic directory not found: {logic_dir}")

    # Look specifically in gfx942 directories
    gfx942_files = list(logic_dir.glob("**/gfx942/**/*.yaml"))

    if not gfx942_files:
        raise FileNotFoundError(f"No gfx942 YAML files found in {logic_dir}")

    # Sort by file size to find the largest
    gfx942_files.sort(key=lambda f: f.stat().st_size, reverse=True)

    largest = gfx942_files[0]
    size_mb = largest.stat().st_size / (1024 * 1024)

    print(f"Found largest gfx942 logic file: {largest.name}")
    print(f"Size: {size_mb:.2f} MB")
    print(f"Full path: {largest}")

    return largest


def construct_logic_filter(logic_file: Path, logic_dir: Path) -> str:
    """
    Construct a --logic-filter pattern that matches only the specific file.

    Args:
        logic_file: Full path to the logic file
        logic_dir: Base logic directory path

    Returns:
        A glob pattern that matches only this file
    """
    # Get the relative path from logic_dir to logic_file
    rel_path = logic_file.relative_to(logic_dir)

    # Convert to a filter pattern (remove the .yaml extension for the filter)
    # The filter is appended with the extension by TensileCreateLibrary
    filter_pattern = str(rel_path.parent / rel_path.stem)

    return filter_pattern


def run_tensile_create_library(
    logic_dir: Path,
    logic_filter: str,
    output_dir: Path,
    architecture: str = "gfx942",
    jobs: int = -1,
    verbose: int = 1,
    no_compress: bool = True,
    lazy_loading: bool = True,
    use_threading: bool = False,
):
    """
    Run TensileCreateLibrary with specified parameters.

    Args:
        logic_dir: Directory containing logic files
        logic_filter: Filter pattern for logic files
        output_dir: Output directory for generated files
        architecture: Target architecture (default: gfx942)
        jobs: Number of parallel jobs (-1 for auto)
        verbose: Verbosity level (0-2)
        no_compress: If True, disable compression
        lazy_loading: If True, enable lazy library loading
        use_threading: If True, use threading instead of multiprocessing for Loading Logics
    """
    print("\n" + "=" * 70)
    print("Running TensileCreateLibrary")
    print("=" * 70)

    # Construct arguments for TensileCreateLibrary
    # These match the command line arguments defined in ParseArguments.py
    args_list = [
        str(logic_dir),                    # LogicPath
        str(output_dir),                   # OutputPath
        "HIP",                             # RuntimeLanguage
        f"--architecture={architecture}",
        f"--logic-filter={logic_filter}",
        f"--jobs={jobs}",
        f"--verbose={verbose}",
        "--code-object-version=default",
        "--library-format=msgpack",
        "--logic-format=yaml",
    ]

    if no_compress:
        args_list.append("--no-compress")

    if not lazy_loading:
        args_list.append("--no-lazy-library-loading")

    print(f"\nArguments:")
    for arg in args_list:
        print(f"  {arg}")

    print("\n" + "-" * 70)

    # Now run the actual TensileCreateLibrary flow
    # We import here after arguments are set up
    from Tensile.TensileCreateLibrary.Run import (
        run as tensile_run,
    )

    # Override sys.argv so that parseArguments inside run() gets our args
    old_argv = sys.argv
    old_environ = os.environ.copy()
    try:
        sys.argv = ["TensileCreateLibrary"] + args_list

        # Set environment variable to control threading vs multiprocessing
        if use_threading:
            os.environ["TENSILE_USE_THREADING"] = "1"
            print("Using THREADING for Loading Logics stage")
        else:
            os.environ.pop("TENSILE_USE_THREADING", None)
            print("Using MULTIPROCESSING for Loading Logics stage")

        print("\n" + "=" * 70)
        print("Starting TensileCreateLibrary.run()")
        print("=" * 70 + "\n")

        start_time = timer()

        # This calls the main TensileCreateLibrary function
        tensile_run()

        end_time = timer()
        elapsed = end_time - start_time

        print("\n" + "=" * 70)
        print(f"TensileCreateLibrary completed in {elapsed:.2f} seconds")
        print("=" * 70)

        return elapsed

    finally:
        sys.argv = old_argv
        os.environ.clear()
        os.environ.update(old_environ)


def main():
    """Main test entry point."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Full TensileCreateLibrary Performance Test"
    )
    parser.add_argument(
        "--load-all-logics",
        action="store_true",
        help="Load all logic files instead of just the largest one"
    )
    parser.add_argument(
        "--use-threading",
        action="store_true",
        help="Use threading instead of multiprocessing for Loading Logics stage"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("Full TensileCreateLibrary Performance Test")
    print("=" * 70)

    # Find project root and logic file
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent

    # Determine the logic directory
    logic_dir = project_root / "library/src/amd_detail/rocblaslt/src/Tensile/Logic"

    if args.load_all_logics:
        # Load all logic files - use wildcard filter
        logic_filter = "*"
        print(f"\nLoading ALL logic files (no filter)")
    else:
        # Find the largest gfx942 logic file
        try:
            logic_file = find_largest_gfx942_logic_file(project_root)
        except FileNotFoundError as e:
            print(f"ERROR: {e}")
            return 1

        # Construct the logic filter
        logic_filter = construct_logic_filter(logic_file, logic_dir)
        print(f"\nLogic filter pattern: {logic_filter}")

    # Create output directory
    output_dir = script_dir / "tcl_output"
    if output_dir.exists():
        print(f"\nRemoving existing output directory: {output_dir}")
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Run TensileCreateLibrary
    try:
        elapsed = run_tensile_create_library(
            logic_dir=logic_dir,
            logic_filter=logic_filter,
            output_dir=output_dir,
            architecture="gfx942",
            jobs=-1,  # Use CMAKE_BUILD_PARALLEL_LEVEL to control parallelism
            verbose=1,  # Standard verbosity (0=quiet, 1=normal, 2=verbose)
            no_compress=True,  # Faster, no compression
            lazy_loading=True,  # Enable lazy loading
            use_threading=args.use_threading,
        )

        print("\n" + "=" * 70)
        print(f"SUCCESS: Test completed in {elapsed:.2f} seconds")
        print("=" * 70)

        return 0

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
