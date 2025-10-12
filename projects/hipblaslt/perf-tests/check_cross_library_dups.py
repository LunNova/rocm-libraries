#!/usr/bin/env python3
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

# Group solutions by their string representation (without codeObjectFile)
solution_to_libraries = defaultdict(set)

for name, lib in masterLibrary.lazyLibraries.items():
    for _, sol in lib.solutions.items():
        sol_str = str(sol.originalSolution)  # String repr doesn't include codeObjectFile
        solution_to_libraries[sol_str].add(name)

# Find solutions that appear in multiple libraries
cross_library_dups = {sol_str: libs for sol_str, libs in solution_to_libraries.items() if len(libs) > 1}

print(f"Total unique solution configurations: {len(solution_to_libraries)}")
print(f"Solutions appearing in multiple libraries: {len(cross_library_dups)}")

if cross_library_dups:
    print("\nExamples of cross-library duplicates:")
    for i, (sol_str, libs) in enumerate(list(cross_library_dups.items())[:3]):
        print(f"\n  Solution {i+1} appears in {len(libs)} libraries: {sorted(libs)}")
        print(f"    Config: {sol_str[:100]}...")
