#!/usr/bin/env python3
import sys
from pathlib import Path

script_dir = Path(__file__).parent.resolve()
tensile_path = script_dir.parent / "tensilelite"
sys.path.insert(0, str(tensile_path))

from Tensile import LibraryIO
from Tensile.Common.Architectures import gfxToIsa
from Tensile.Common.Capabilities import makeIsaInfoMap
from Tensile.Toolchain.Assembly import makeAssemblyToolchain
from Tensile.Toolchain.Validators import validateToolchain

# Load logic file  
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent
logic_dir = project_root / "library/src/amd_detail/rocblaslt/src/Tensile/Logic"
yaml_files = list(logic_dir.rglob("*.yaml"))
yaml_files.sort(key=lambda f: f.stat().st_size, reverse=True)
logic_file = yaml_files[0]

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

result = LibraryIO.parseLibraryLogicFile(
    str(logic_file),
    asm_toolchain.assembler,
    False, False, False,
    isa_info_map,
    True
)

_, _, _, _, _, masterLibrary = result

# Simulate the collection logic from Run.py
solutions = []
seen_ids = set()
duplicates_by_id = 0

for _, sol in masterLibrary.solutions.items():
    sol_id = id(sol.originalSolution)
    if sol_id in seen_ids:
        duplicates_by_id += 1
    seen_ids.add(sol_id)
    solutions.append(sol.originalSolution)

for name, lib in masterLibrary.lazyLibraries.items():
    for _, sol in lib.solutions.items():
        sol_id = id(sol.originalSolution)
        if sol_id in seen_ids:
            duplicates_by_id += 1
        seen_ids.add(sol_id)
        solutions.append(sol.originalSolution)

print(f"Total solutions collected: {len(solutions)}")
print(f"Unique by object ID: {len(seen_ids)}")
print(f"Duplicates by object ID: {duplicates_by_id}")

# Now test deduplication by hash (like dict.fromkeys does)
unique_by_hash = dict.fromkeys(solutions).keys()
print(f"\nUnique by hash (dict.fromkeys): {len(list(unique_by_hash))}")
print(f"Removed by hash-based dedup: {len(solutions) - len(list(dict.fromkeys(solutions)))}")
