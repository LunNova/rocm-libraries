#!/usr/bin/env python3
"""
Test if solutions differing only in CUCount/codeObjectFile actually produce
different assembly code.
"""
import sys
import tempfile
from pathlib import Path
from collections import defaultdict

script_dir = Path(__file__).parent.resolve()
tensile_path = script_dir.parent / "tensilelite"
sys.path.insert(0, str(tensile_path))

import rocisa

from Tensile import LibraryIO
from Tensile.Common import DebugConfig
from Tensile.Common.Architectures import gfxToIsa
from Tensile.Common.Capabilities import makeIsaInfoMap
from Tensile.KernelWriterAssembly import KernelWriterAssembly
from Tensile.SolutionStructs.Naming import getKernelFileBase
from Tensile.Toolchain.Assembly import makeAssemblyToolchain
from Tensile.Toolchain.Validators import validateToolchain

# Setup
cxx_compiler = validateToolchain("amdclang++")
target_isa = gfxToIsa("gfx90a")
isa_info_map = makeIsaInfoMap([target_isa], cxx_compiler)
asm_toolchain = makeAssemblyToolchain(
    assembler_path=cxx_compiler,
    bundler_path="clang-offload-bundler",
    co_version="default",
    build_id_kind="sha256",
    debug=False
)

# Find yaml files that exist in both 104CU and 110CU directories
project_root = script_dir.parent
logic_base = project_root / "library/src/amd_detail/rocblaslt/src/Tensile/Logic/asm_full"

dir_104cu = logic_base / "aldebaran/104CU/GridBased"
dir_110cu = logic_base / "aldebaran/110CU/GridBased"

files_104 = set(f.name for f in dir_104cu.glob("*.yaml"))
files_110 = set(f.name for f in dir_110cu.glob("*.yaml"))
common_files = sorted(files_104 & files_110)

print(f"Files in 104CU: {len(files_104)}")
print(f"Files in 110CU: {len(files_110)}")
print(f"Common files: {len(common_files)}")
print(f"Files only in 104CU: {len(files_104 - files_110)}")
print(f"Files only in 110CU: {len(files_110 - files_104)}")

# Test first 5 common files from GridBased (which have parameter differences)
test_files = common_files[:5]
print(f"\nTesting {len(test_files)} GridBased files (known to have parameter differences):")
for f in test_files:
    print(f"  - {f}")

all_results = []

for test_file in test_files:
    print(f"\n{'='*80}")
    print(f"Testing file: {test_file}")
    print('='*80)

    file_104cu = dir_104cu / test_file
    file_110cu = dir_110cu / test_file

    print(f"Loading from 104CU directory...")
    result_104 = LibraryIO.parseLibraryLogicFile(
        str(file_104cu),
        asm_toolchain.assembler,
        False, False, False,
        isa_info_map,
        True
    )
    _, _, _, _, _, lib_104 = result_104

    print(f"Loading from 110CU directory...")
    result_110 = LibraryIO.parseLibraryLogicFile(
        str(file_110cu),
        asm_toolchain.assembler,
        False, False, False,
        isa_info_map,
        True
    )
    _, _, _, _, _, lib_110 = result_110

    # Collect solutions from both libraries
    solutions_104 = {}
    for _, sol in lib_104.solutions.items():
        sol_str = str(sol.originalSolution)
        solutions_104[sol_str] = sol.originalSolution

    for name, lib in lib_104.lazyLibraries.items():
        for _, sol in lib.solutions.items():
            sol.originalSolution._state["codeObjectFile"] = name
            sol_str = str(sol.originalSolution)
            solutions_104[sol_str] = sol.originalSolution

    solutions_110 = {}
    for _, sol in lib_110.solutions.items():
        sol_str = str(sol.originalSolution)
        solutions_110[sol_str] = sol.originalSolution

    for name, lib in lib_110.lazyLibraries.items():
        for _, sol in lib.solutions.items():
            sol.originalSolution._state["codeObjectFile"] = name
            sol_str = str(sol.originalSolution)
            solutions_110[sol_str] = sol.originalSolution

    print(f"\n104CU solutions: {len(solutions_104)}")
    print(f"110CU solutions: {len(solutions_110)}")

    # Find solutions with matching str() but potentially different CUCount
    common_keys = set(solutions_104.keys()) & set(solutions_110.keys())
    only_104 = set(solutions_104.keys()) - set(solutions_110.keys())
    only_110 = set(solutions_110.keys()) - set(solutions_104.keys())

    print(f"Solutions with matching str(): {len(common_keys)}")
    print(f"Solutions only in 104CU: {len(only_104)}")
    print(f"Solutions only in 110CU: {len(only_110)}")

    if only_104:
        print(f"  First 104CU only sol str(): {list(only_104)[0]}")
    if only_110:
        print(f"  First 110CU only sol str(): {list(only_110)[0]}")

    if not common_keys:
        print("No common solutions found in this file!")
        continue

    common_keys = list(common_keys)
    # Take first solution and generate assembly
    sol_str = common_keys[0]
    print(f"\nGenerating assembly for first common solution {sol_str}")

    debug_config = DebugConfig()
    kernelWriter = KernelWriterAssembly(asm_toolchain.assembler, debug_config)

    sol_104 = solutions_104[sol_str]
    sol_110 = solutions_110[sol_str]

    print(f"  Name: {sol_str}...")
    print(f"  104CU CUCount: {sol_104._state.get('CUCount', 'None')}")
    print(f"  110CU CUCount: {sol_110._state.get('CUCount', 'None')}")

    # Check if the solutions have different parameters (not just CUCount/codeObjectFile)
    state_104 = {k: v for k, v in sol_104._state.items() if k not in ['CUCount', 'codeObjectFile']}
    state_110 = {k: v for k, v in sol_110._state.items() if k not in ['CUCount', 'codeObjectFile']}
    if state_104 != state_110:
        print(f"  ⚠️  Solutions have DIFFERENT parameters (beyond CUCount):")
        # Find all keys that differ
        all_keys = set(state_104.keys()) | set(state_110.keys())
        diff_keys = []
        for key in sorted(all_keys):
            val_104 = state_104.get(key, '<missing>')
            val_110 = state_110.get(key, '<missing>')
            if val_104 != val_110:
                diff_keys.append((key, val_104, val_110))

        for key, val_104, val_110 in diff_keys[:10]:  # Show first 10 differences
            print(f"     {key}: 104CU={val_104}, 110CU={val_110}")
        if len(diff_keys) > 10:
            print(f"     ... and {len(diff_keys) - 10} more differences")
    else:
        print(f"  ✅ Solutions have identical parameters (except CUCount/codeObjectFile)")

    # Generate kernels
    kernels_104 = sol_104.getKernels()
    kernels_110 = sol_110.getKernels()

    if not kernels_104 or not kernels_110:
        print("  Skipping - no kernels generated")
        continue

    kernel_104 = kernels_104[0]
    kernel_110 = kernels_110[0]

    # Generate assembly
    try:
        # setRocIsa needs rocIsa data
        rocisa_data = rocisa.rocIsa.getInstance().getData()
        kernelWriter.setRocIsa(rocisa_data)
        err_104, asm_104 = kernelWriter.getSourceFileString(kernel_104)
        err_110, asm_110 = kernelWriter.getSourceFileString(kernel_110)

        if err_104 or err_110:
            print(f"  Error generating assembly: 104CU={err_104}, 110CU={err_110}")
            continue

        # Check what assembler command would be run
        # The assembler uses: targetGfx (from ISA), wavefrontSize, srcPath, destPath
        # CUCount is NOT passed to assembler
        from Tensile.Common.Architectures import isaToGfx
        gfx_104 = isaToGfx(tuple(kernel_104["ISA"]))
        gfx_110 = isaToGfx(tuple(kernel_110["ISA"]))
        wf_104 = kernel_104.get("WavefrontSize", 64)
        wf_110 = kernel_110.get("WavefrontSize", 64)

        print(f"  Assembler params:")
        print(f"     104CU: gfx={gfx_104}, wavefront={wf_104}")
        print(f"     110CU: gfx={gfx_110}, wavefront={wf_110}")

        # Compare assembly - first check byte-for-byte
        asm_identical = (asm_104 == asm_110)

        # Also compare with labels filtered out
        import re
        def filter_labels(asm_text):
            # Remove lines containing label_ (label definitions and references)
            lines = asm_text.split('\n')
            filtered = [line for line in lines if 'label_' not in line]
            return '\n'.join(filtered)

        asm_104_filtered = filter_labels(asm_104)
        asm_110_filtered = filter_labels(asm_110)
        asm_identical_no_labels = (asm_104_filtered == asm_110_filtered)

        if asm_identical:
            print(f"  ✅ Assembly source is IDENTICAL ({len(asm_104)} bytes)")
            all_results.append((test_file, "identical", len(asm_104)))
        elif asm_identical_no_labels:
            print(f"  ✅ Assembly identical after filtering labels ({len(asm_104)} bytes)")
            all_results.append((test_file, "identical-no-labels", len(asm_104)))
        else:
            print(f"  ⚠️  Assembly DIFFERS even after filtering labels!")
            print(f"     104CU: {len(asm_104)} bytes ({len(asm_104_filtered)} filtered)")
            print(f"     110CU: {len(asm_110)} bytes ({len(asm_110_filtered)} filtered)")
            all_results.append((test_file, "different", len(asm_104)))

            # Write to temp files for diffing
            with tempfile.NamedTemporaryFile(mode='w', suffix='_104cu.s', delete=False) as f1:
                f1.write(asm_104)
                temp_104 = f1.name

            with tempfile.NamedTemporaryFile(mode='w', suffix='_110cu.s', delete=False) as f2:
                f2.write(asm_110)
                temp_110 = f2.name

            print(f"\n  Diff preview (first 50 lines):")
            import subprocess
            try:
                result = subprocess.run(['diff', '-u', temp_104, temp_110],
                                      capture_output=True, text=True)
                diff_lines = result.stdout.split('\n')[:50]
                for line in diff_lines:
                    print(f"    {line}")
            except Exception as e:
                print(f"    Could not run diff: {e}")
            finally:
                Path(temp_104).unlink()
                Path(temp_110).unlink()

    except Exception as e:
        print(f"  Exception: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
identical_count = sum(1 for _, status, _ in all_results if status == "identical")
different_count = sum(1 for _, status, _ in all_results if status == "different")
print(f"Files tested: {len(all_results)}")
print(f"Assembly identical: {identical_count}")
print(f"Assembly different: {different_count}")
if different_count > 0:
    print(f"\nFiles with different assembly:")
    for fname, status, _ in all_results:
        if status == "different":
            print(f"  - {fname}")
print("\n" + "="*80)
print("Done!")
