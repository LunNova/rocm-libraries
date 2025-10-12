#!/usr/bin/env python3
"""
Analyze the order .o files are placed in .co files during linking.
"""
import sys
from pathlib import Path

script_dir = Path(__file__).parent.resolve()
tensile_path = script_dir.parent / "tensilelite"
sys.path.insert(0, str(tensile_path))

from Tensile.TensileCreateLibrary import Run
from Tensile.Common.GlobalParameters import assignGlobalParameters, globalParameters
from Tensile.Common.Architectures import gfxToIsa
from Tensile.Common.Capabilities import makeIsaInfoMap
from Tensile.Toolchain.Validators import validateToolchain
from Tensile.Toolchain.Assembly import makeAssemblyToolchain

print("=" * 80)
print("Analyzing kernel ordering in linking process")
print("=" * 80)

# Find the logic files
logic_base = script_dir.parent / "library/src/amd_detail/rocblaslt/src/Tensile/Logic/asm_full"
aldebaran_dir = logic_base / "aldebaran"

logic_files = [
    aldebaran_dir / "104CU/GridBased/aldebaran_Cijk_Ailk_Bjlk_SB_Bias_HA_SAV.yaml",
    aldebaran_dir / "110CU/GridBased/aldebaran_Cijk_Ailk_Bjlk_SB_Bias_HA_SAV.yaml",
]

# Verify files exist
for f in logic_files:
    if not f.exists():
        raise FileNotFoundError(f"Logic file not found: {f}")

print(f"\nLogic files:")
for f in logic_files:
    print(f"  - {f.relative_to(logic_base)}")

# Setup arguments
arguments = {
    "OutputPath": "/tmp/test_order",
    "RuntimeLanguage": "HIP",
    "CodeObjectVersion": "default",
    "CxxCompiler": "amdclang++",
    "Architecture": "gfx90a",
    "LibraryFormat": "msgpack",
    "MergeFiles": True,
    "LazyLibraryLoading": True,
    "PrintLevel": 1,
    "ShortNames": False,
    "LibraryPrintDebug": False,
    "NumMergedFiles": 1,
    "UseCompression": True,
    "GenerateSourcesAndExit": False,
    "ErrorTolerant": False,
    "CpuThreads": 0,
    "GenSolTable": False,
}

globalParameters["PrintLevel"] = 0
globalParameters["CpuThreads"] = 0

# Setup toolchains
cxx_compiler = validateToolchain("amdclang++")
target_isas = [gfxToIsa("gfx90a")]
isa_info_map = makeIsaInfoMap(target_isas, cxx_compiler)

asm_toolchain = makeAssemblyToolchain(
    assembler_path=cxx_compiler,
    bundler_path="clang-offload-bundler",
    co_version="5",
    build_id_kind="sha1",
    debug=False
)

print("\n📖 Loading YAML files...")
solutions, masterLibraries, libraryMapping, solution_to_cofiles = Run.generateLogicDataAndSolutions(
    [str(f) for f in logic_files],
    arguments,
    asm_toolchain.assembler,
    isa_info_map
)

print(f"\n✅ Solutions loaded: {len(solutions)} unique solutions")

# Generate kernels
print("\n🔧 Analyzing kernel generation order...")
kernels = Run.generateKernelObjectsFromSolutions(solutions)
print(f"   Generated {len(kernels)} unique kernels")

# Analyze the order
print("\n" + "=" * 80)
print("Kernel Order Analysis")
print("=" * 80)

# Check if solutions have indices
print("\nFirst 10 solutions (showing SolutionIndex if available):")
for i, sol in enumerate(list(solutions)[:10]):
    sol_index = getattr(sol, 'index', 'N/A')
    sol_str = str(sol)[:80]
    print(f"  {i:3d}. Index={sol_index:4s} {sol_str}")

print("\nFirst 10 kernels (showing BaseName):")
from Tensile.SolutionStructs.Naming import getKernelFileBase
for i, kern in enumerate(kernels[:10]):
    base = getKernelFileBase(False, kern)
    sol_idx = kern.get('SolutionIndex', 'N/A')
    print(f"  {i:3d}. SolutionIndex={sol_idx:4s} BaseName={base}")

# Now simulate what happens in buildAssemblyCodeObjectFiles
print("\n" + "=" * 80)
print("Simulating buildAssemblyCodeObjectFiles ordering")
print("=" * 80)

import collections
from Tensile.Common.Architectures import isaToGfx

asmKernels = [k for k in kernels if k["KernelLanguage"] == "Assembly"]

# Group by architecture
archKernelMap = collections.defaultdict(list)
for k in asmKernels:
    archKernelMap[tuple(k['ISA'])].append(k)

for arch, archKernels in archKernelMap.items():
    gfx = isaToGfx(arch)
    print(f"\nArchitecture: {gfx}")
    print(f"Number of kernels: {len(archKernels)}")

    # Simulate what happens when we build the coFileMap
    coFileMap = collections.defaultdict(set)

    print("\nFirst 20 kernels added to coFileMap (in order):")
    for i, kernel in enumerate(archKernels[:20]):
        objFilePath = f"/tmp/{kernel['BaseName']}.o"
        kernel_key = str(kernel)

        # Track which .co file(s) this solution belongs to
        cofiles = solution_to_cofiles.get(kernel_key, {None})

        for cofile in cofiles:
            if cofile is None:
                cofile_name = f"TensileLibrary_{gfx}.co"
            else:
                cofile_name = f"{cofile}.co"
            coFileMap[cofile_name].add(objFilePath)

        sol_idx = kernel.get('SolutionIndex', 'N/A')
        print(f"  {i:3d}. SolutionIndex={sol_idx:4s} BaseName={kernel['BaseName'][:60]}")

    # Show what the set looks like after conversion
    print(f"\nNumber of unique .co files: {len(coFileMap)}")
    for cofile_name, obj_files in list(coFileMap.items())[:3]:
        print(f"\n{cofile_name}: {len(obj_files)} .o files")
        print("  First 10 .o files when iterating over the set:")
        for j, obj_file in enumerate(list(obj_files)[:10]):
            base_name = Path(obj_file).stem
            print(f"    {j:2d}. {base_name[:60]}")

print("\n" + "=" * 80)
print("Key insight: Sets in Python 3.7+ maintain insertion order,")
print("so the order should match the iteration order of archKernels,")
print("which comes from the kernels list, which comes from the")
print("solutions list in the order they were deduplicated.")
print("=" * 80)
