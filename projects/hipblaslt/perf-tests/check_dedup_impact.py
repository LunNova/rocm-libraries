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

solutions = []
for name, lib in masterLibrary.lazyLibraries.items():
    for _, sol in lib.solutions.items():
        # DON'T set codeObjectFile
        solutions.append(sol.originalSolution)

print(f"Total solutions: {len(solutions)}")

# Deduplicate WITHOUT codeObjectFile in hash
# (temporarily remove it from hash)
original_hash = solutions[0].__class__.__hash__

def hash_without_cofile(self):
    return hash(str(self))

solutions[0].__class__.__hash__ = hash_without_cofile

unique_without_cofile = len(list(dict.fromkeys(solutions)))

# Restore
solutions[0].__class__.__hash__ = original_hash

# Now set codeObjectFile and deduplicate WITH it
for name, lib in masterLibrary.lazyLibraries.items():
    for _, sol in lib.solutions.items():
        sol.originalSolution._state["codeObjectFile"] = name

unique_with_cofile = len(list(dict.fromkeys(solutions)))

print(f"Unique WITHOUT codeObjectFile in hash: {unique_without_cofile}")
print(f"Unique WITH codeObjectFile in hash: {unique_with_cofile}")
print(f"Difference: {unique_with_cofile - unique_without_cofile}")
