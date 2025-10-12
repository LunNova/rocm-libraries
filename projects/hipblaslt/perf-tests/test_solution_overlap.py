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
    True  # lazyLibraryLoading
)

_, _, _, _, _, masterLibrary = result

# Check if same solutions appear in both places
regular_solution_ids = set()
for _, sol in masterLibrary.solutions.items():
    regular_solution_ids.add(id(sol.originalSolution))

lazy_solution_ids = set()
for name, lib in masterLibrary.lazyLibraries.items():
    for _, sol in lib.solutions.items():
        lazy_solution_ids.add(id(sol.originalSolution))

overlap = regular_solution_ids & lazy_solution_ids

print(f"Regular solutions: {len(regular_solution_ids)}")
print(f"Lazy solutions: {len(lazy_solution_ids)}")
print(f"Overlap (same object IDs): {len(overlap)}")
