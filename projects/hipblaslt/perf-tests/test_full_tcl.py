#!/usr/bin/env python3
"""
Test TensileCreateLibrary with the full build pipeline.
Tests deduplication of solutions across multiple .co files.
"""
import sys
import os
import tempfile
import argparse
from pathlib import Path

script_dir = Path(__file__).parent.resolve()
tensile_path = script_dir.parent / "tensilelite"
sys.path.insert(0, str(tensile_path))

from Tensile.TensileCreateLibrary import Run

def test_tcl_build(show_full_kernels=False, logic_filter="*Cijk_Ailk_Bjlk_SB_Bias_HA_SAV"):
    print("=" * 80)
    print("Testing TensileCreateLibrary build with solution deduplication")
    print("=" * 80)

    # Create temporary output directory
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_library"
        output_path.mkdir()

        print(f"\nOutput directory: {output_path}")

        # Find the logic files for aldebaran (gfx90a)
        logic_base = script_dir.parent / "library/src/amd_detail/rocblaslt/src/Tensile/Logic/asm_full"

        print("Running TensileCreateLibrary...")

        # Build command-line arguments for TensileCreateLibrary
        # Using the normal CLI interface ensures we use the exact same code path
        # as production usage
        old_argv = sys.argv
        try:
            sys.argv = [
                "TensileCreateLibrary",
                str(logic_base),  # LogicPath
                str(output_path),    # OutputPath
                "HIP",               # RuntimeLanguage
                "--cxx-compiler=amdclang++",
                "--architecture=gfx1200;gfx1201",
                "--library-format=msgpack",
                "--code-object-version=default",
		"--no-compress",
		"--no-generate-solution-table",
                "--build-id=sha1",  # sha256 not supported by older linkers
                f"--logic-filter={logic_filter}",
            ]

            # Call the main entry point
            Run.run()

            # Verify output files exist
            library_dir = output_path / "library"
            if library_dir.exists():
                co_files = list(library_dir.glob("*.co"))
                print(f"\nGenerated .co files ({len(co_files)}):")
                for co_file in sorted(co_files):
                    size_mb = co_file.stat().st_size / (1024 * 1024)
                    # Show kernels in each .co file
                    import subprocess
                    result = subprocess.run(
                        ["strings", str(co_file)],
                        capture_output=True,
                        text=True
                    )
                    kernels = sorted(list(set([line for line in result.stdout.split('\n') if line.endswith(".kd")])))
                    print(f"   - {co_file.name:60s} {len(kernels)} ({size_mb:6.2f} MB)")
                    if show_full_kernels:
                        print(f"     Kernels:\n       {'\n       '.join(kernels)}")

        finally:
            sys.argv = old_argv

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test TensileCreateLibrary with solution deduplication"
    )
    parser.add_argument(
        "--show-full-kernels",
        action="store_true",
        help="Show full kernel names instead of just the count"
    )
    parser.add_argument(
        "--logic-filter",
        default="*Cijk_Ailk_Bjlk_SB_Bias_HA_SAV",
        help="Logic filter pattern for TensileCreateLibrary (default: %(default)s)"
    )
    args = parser.parse_args()
    test_tcl_build(show_full_kernels=args.show_full_kernels, logic_filter=args.logic_filter)
