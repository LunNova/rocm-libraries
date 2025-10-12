#!/usr/bin/env python3
import sys
import time
import argparse
from pathlib import Path
from collections import defaultdict

script_dir = Path(__file__).parent.resolve()
tensile_path = script_dir.parent / "tensilelite"
sys.path.insert(0, str(tensile_path))

from Tensile import LibraryIO
from Tensile.Common.Architectures import gfxToIsa
from Tensile.Common.Capabilities import makeIsaInfoMap
from Tensile.Toolchain.Assembly import makeAssemblyToolchain
from Tensile.Toolchain.Validators import validateToolchain

# Parse arguments
parser = argparse.ArgumentParser(description='Test for duplicate solutions across multiple YAML files')
parser.add_argument('--filter', '-f', type=str, default=None,
                    help='Filter files by pattern (e.g., "aldebaran_Cijk_Ailk_Bjlk_SB_Bias_HA_SAV")')
args = parser.parse_args()

# Setup
cxx_compiler = validateToolchain("amdclang++")

# Create isaInfoMap for both gfx90a and gfx942 (like Run.py does for multiple archs)
target_isas = [gfxToIsa("gfx90a"), gfxToIsa("gfx942")]
isa_info_map = makeIsaInfoMap(target_isas, cxx_compiler)

asm_toolchain = makeAssemblyToolchain(
    assembler_path=cxx_compiler,
    bundler_path="clang-offload-bundler",
    co_version="default",
    build_id_kind="sha256",
    debug=False
)

# Find logic files for both architectures
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent
logic_base = project_root / "library/src/amd_detail/rocblaslt/src/Tensile/Logic/asm_full"

# aldebaran = gfx90a, aquavanjaram = gfx942
aldebaran_dir = logic_base / "aldebaran"
aquavanjaram_dir = logic_base / "aquavanjaram"

aldebaran_files = list(aldebaran_dir.glob("**/*.yaml"))
aquavanjaram_files = list(aquavanjaram_dir.glob("**/*.yaml"))

# Apply filter if specified
if args.filter:
    aldebaran_files = [f for f in aldebaran_files if args.filter in f.name]
    aquavanjaram_files = [f for f in aquavanjaram_files if args.filter in f.name]
    print(f"Filtering files by pattern: '{args.filter}'")

logic_files = aldebaran_files + aquavanjaram_files

print(f"Found {len(aldebaran_files)} aldebaran (gfx90a) logic files")
print(f"Found {len(aquavanjaram_files)} aquavanjaram (gfx942) logic files")
print(f"Total: {len(logic_files)} logic files")

# Simulate Run.py's collection logic - load ALL files
all_solutions = []
solution_to_files = defaultdict(list)  # solution_str -> list of (file, codeObjectFile)
file_load_times = []  # List of (filename, load_time, file_size, arch)

print(f"\nLoading all {len(logic_files)} files...")
for i, logic_file in enumerate(logic_files):
    if (i+1) % 10 == 0:
        print(f"  Progress: {i+1}/{len(logic_files)}")

    # Determine architecture from path
    arch = "gfx90a" if "aldebaran" in str(logic_file) else "gfx942"
    print(f"Loading [{arch}]: {logic_file.name}")

    # Track load time and file size
    file_size = logic_file.stat().st_size
    start_time = time.time()

    result = LibraryIO.parseLibraryLogicFile(
        str(logic_file),
        asm_toolchain.assembler,
        False, False, False,
        isa_info_map,
        True
    )

    load_time = time.time() - start_time
    file_load_times.append((logic_file.name, load_time, file_size, arch))

    _, _, _, _, _, masterLibrary = result
    
    # Collect solutions like Run.py does
    for _, sol in masterLibrary.solutions.items():
        sol_str = str(sol.originalSolution)
        all_solutions.append(sol.originalSolution)
        solution_to_files[sol_str].append((logic_file.name, None))
    
    for name, lib in masterLibrary.lazyLibraries.items():
        for _, sol in lib.solutions.items():
            # Simulate setting codeObjectFile
            sol.originalSolution._state["codeObjectFile"] = name
            sol_str = str(sol.originalSolution)
            all_solutions.append(sol.originalSolution)
            solution_to_files[sol_str].append((logic_file.name, name))

print(f"\n{'='*80}")
print(f"Total solutions collected: {len(all_solutions)}")

# Report top 10 slowest files to load
print(f"\n{'='*80}")
print("Top 10 slowest YAML files to load:")
sorted_times = sorted(file_load_times, key=lambda x: x[1], reverse=True)
for i, (filename, load_time, file_size, arch) in enumerate(sorted_times[:10], 1):
    size_mb = file_size / (1024 * 1024)
    print(f"  {i:2d}. [{arch}] {filename:45s} - {load_time:6.2f}s - {size_mb:7.2f} MB")

# Find duplicates by str() (which is what __eq__ uses)
duplicates = {k: v for k, v in solution_to_files.items() if len(v) > 1}

print(f"Solutions appearing multiple times: {len(duplicates)}")

if duplicates:
    print(f"\nShowing first 5 duplicates:")
    diff_cofile_only = 0

    for i, (sol_str, occurrences) in enumerate(list(duplicates.items())[:5]):
        print(f"\nDuplicate {i+1}:")
        print(f"  Solution: {sol_str[:80]}...")
        print(f"  Appears in:")
        for file, cofile in occurrences:
            print(f"    - {file} (cofile: {cofile})")

        # Check if they differ ONLY in codeObjectFile
        cofiles = [co for _, co in occurrences if co is not None]
        unique_cofiles = set(cofiles)
        if len(unique_cofiles) > 1:
            print(f"  ⚠️  Same solution, different codeObjectFile values: {unique_cofiles}")
            diff_cofile_only += 1

    # Count total cases where same solution has different codeObjectFile
    for sol_str, occurrences in duplicates.items():
        cofiles = [co for _, co in occurrences if co is not None]
        if len(set(cofiles)) > 1:
            diff_cofile_only += 1

    print(f"\n⚠️  Total duplicates differing ONLY by codeObjectFile: {diff_cofile_only}")

# Test hash-based dedup WITH codeObjectFile
print(f"\n{'='*80}")
print("WITH codeObjectFile in hash (current behavior):")
before_dedup = len(all_solutions)
unique_with_co = list(dict.fromkeys(all_solutions).keys())
after_with_co = len(unique_with_co)
print(f"  Before dedup: {before_dedup} solutions")
print(f"  After dedup:  {after_with_co} solutions")
print(f"  Removed:      {before_dedup - after_with_co} duplicates")

# Now test WITHOUT codeObjectFile in hash
print("\nWITHOUT codeObjectFile in hash (proposed change):")
for sol in all_solutions:
    if "codeObjectFile" in sol._state:
        del sol._state["codeObjectFile"]
unique_without_co = list(dict.fromkeys(all_solutions).keys())
after_without_co = len(unique_without_co)
print(f"  After dedup:  {after_without_co} solutions")
print(f"  Removed:      {before_dedup - after_without_co} duplicates")

if after_with_co == after_without_co:
    print("\n✅ No difference! Removing codeObjectFile from hash is safe.")
else:
    print(f"\n⚠️  Difference: {abs(after_with_co - after_without_co)} solutions")
