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

print(f"Type of masterLibrary: {type(masterLibrary).__name__}")
print(f"Number of masterLibrary.solutions: {len(masterLibrary.solutions)}")

if len(masterLibrary.solutions) > 0:
    first_sol = next(iter(masterLibrary.solutions.values()))
    print(f"Type of solution in .solutions: {type(first_sol).__name__}")
    print(f"Has originalSolution? {hasattr(first_sol, 'originalSolution')}")

print(f"\nNumber of lazy libraries: {len(masterLibrary.lazyLibraries)}")
if len(masterLibrary.lazyLibraries) > 0:
    first_lazy_lib = next(iter(masterLibrary.lazyLibraries.values()))
    print(f"Type of lazy library: {type(first_lazy_lib).__name__}")
    print(f"Number of solutions in first lazy lib: {len(first_lazy_lib.solutions)}")
    if len(first_lazy_lib.solutions) > 0:
        first_lazy_sol = next(iter(first_lazy_lib.solutions.values()))
        print(f"Type of solution in lazy lib: {type(first_lazy_sol).__name__}")
        print(f"Has originalSolution? {hasattr(first_lazy_sol, 'originalSolution')}")
