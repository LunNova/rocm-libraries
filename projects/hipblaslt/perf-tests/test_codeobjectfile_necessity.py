#!/usr/bin/env python3
"""
Test if codeObjectFile is necessary in hash to distinguish solutions.
Loads all gfx942 YAML files and checks for duplicates.
"""
import sys
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

# Setup
cxx_compiler = validateToolchain("amdclang++")
target_isa = gfxToIsa("gfx942")
isa_info_map = makeIsaInfoMap([target_isa], cxx_compiler)
asm_toolchain = makeAssemblyToolchain(
    assembler_path=cxx_compiler,
    bundler_path="clang-offload-bundler",
    co_version="default",
    build_id_kind="sha256",
    debug=False
)

# Find all gfx942 YAML files
project_root = script_dir.parent
logic_dir = project_root / "library/src/amd_detail/rocblaslt/src/Tensile/Logic"
aqua_dir = logic_dir / "asm_full" / "aquavanjaram"

yaml_files = list(aqua_dir.rglob("*.yaml"))
print(f"Found {len(yaml_files)} YAML files in {aqua_dir}")

# Collect all solutions from all files
all_solutions = []
all_solutions_with_cofile = []  # (solution, codeObjectFile or None)

for i, yaml_file in enumerate(yaml_files):
    print(f"Loading {i+1}/{len(yaml_files)}: {yaml_file.name}...")
    
    result = LibraryIO.parseLibraryLogicFile(
        str(yaml_file),
        asm_toolchain.assembler,
        False, False, False,
        isa_info_map,
        True  # lazyLibraryLoading
    )
    
    _, _, _, _, _, masterLibrary = result
    
    # Regular solutions (no codeObjectFile)
    for _, sol in masterLibrary.solutions.items():
        all_solutions.append(sol.originalSolution)
        all_solutions_with_cofile.append((sol.originalSolution, None))
    
    # Lazy solutions (have codeObjectFile)
    for name, lib in masterLibrary.lazyLibraries.items():
        for _, sol in lib.solutions.items():
            # Simulate what Run.py does
            sol.originalSolution._state["codeObjectFile"] = name
            all_solutions.append(sol.originalSolution)
            all_solutions_with_cofile.append((sol.originalSolution, name))

print(f"\nTotal solutions collected: {len(all_solutions)}")

# Test 1: Dedup with current hash (includes codeObjectFile)
unique_with_cofile = list(dict.fromkeys(all_solutions).keys())
print(f"Unique by hash (with codeObjectFile): {len(unique_with_cofile)}")

# Test 2: Dedup by object ID
unique_by_id = len(set(id(s) for s in all_solutions))
print(f"Unique by object ID: {unique_by_id}")

# Test 3: Find solutions that hash differently only due to codeObjectFile
# Group by str(solution) - this is what __eq__ uses
by_str = defaultdict(list)
for sol, cofile in all_solutions_with_cofile:
    by_str[str(sol)].append((sol, cofile))

# Find groups with same str() but different hashes
hash_collision_groups = []
for sol_str, items in by_str.items():
    if len(items) > 1:
        # Check if they have different hashes
        hashes = set(hash(sol) for sol, _ in items)
        if len(hashes) > 1:
            hash_collision_groups.append((sol_str, items))

print(f"\nSolutions with same str() but different hashes: {len(hash_collision_groups)}")

if hash_collision_groups:
    print("\nFirst few examples:")
    for i, (sol_str, items) in enumerate(hash_collision_groups[:3]):
        print(f"\nGroup {i+1}: {len(items)} solutions")
        print(f"  str(): {sol_str[:100]}...")
        for sol, cofile in items[:3]:
            print(f"    hash={hash(sol)}, codeObjectFile={cofile}")

# Test 4: What happens with dict.fromkeys if we remove codeObjectFile from hash?
print("\n" + "="*60)
print("SIMULATING: What if codeObjectFile was NOT in hash?")
print("="*60)

# Remove codeObjectFile temporarily
for sol, _ in all_solutions_with_cofile:
    if "codeObjectFile" in sol._state:
        del sol._state["codeObjectFile"]

# Now test without codeObjectFile
unique_without_cofile = list(dict.fromkeys(all_solutions).keys())
print(f"Unique by hash (WITHOUT codeObjectFile): {len(unique_without_cofile)}")
print(f"Difference: {len(unique_with_cofile) - len(unique_without_cofile)} solutions would be incorrectly deduped")
