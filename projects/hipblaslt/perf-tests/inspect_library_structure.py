#!/usr/bin/env python3
"""
Inspect the structure returned by parseLibraryLogicFile to understand what
LibraryLogic[3] and LibraryLogic[5] are.
"""

import sys
from pathlib import Path

# Add Tensile to path
script_dir = Path(__file__).parent.resolve()
tensile_path = script_dir.parent / "tensilelite"
sys.path.insert(0, str(tensile_path))

from Tensile import LibraryIO
from Tensile.Common.Architectures import gfxToIsa
from Tensile.Common.Capabilities import makeIsaInfoMap
from Tensile.Toolchain.Assembly import makeAssemblyToolchain
from Tensile.Toolchain.Validators import validateToolchain


def main():
    print("Loading library logic file...")

    # Find the largest logic file
    script_dir = Path(__file__).parent.resolve()
    project_root = script_dir.parent
    logic_dir = project_root / "library/src/amd_detail/rocblaslt/src/Tensile/Logic"

    yaml_files = list(logic_dir.rglob("*.yaml"))
    yaml_files.sort(key=lambda f: f.stat().st_size, reverse=True)
    logic_file = yaml_files[0]

    print(f"File: {logic_file.name}")

    # Setup environment
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

    # Parse the file
    print("\nParsing...")
    result = LibraryIO.parseLibraryLogicFile(
        str(logic_file),
        asm_toolchain.assembler,
        False,  # splitGSU
        False,  # printSolutionRejectionReason
        False,  # printIndexAssignmentInfo
        isa_info_map,
        False   # lazyLibraryLoading
    )

    print("\n" + "=" * 80)
    print("LIBRARY LOGIC FILE STRUCTURE")
    print("=" * 80)

    # Result is a tuple
    print(f"\nResult type: {type(result)}")
    print(f"Result length: {len(result)}")

    # Inspect each element
    for i, item in enumerate(result):
        print(f"\n[{i}] Type: {type(item).__name__}")
        print(f"    Value/Length: ", end="")

        if isinstance(item, (list, tuple)):
            print(f"{len(item)} items")
            if len(item) > 0:
                print(f"    First item type: {type(item[0]).__name__}")
                if hasattr(item[0], '__dict__'):
                    print(f"    First item attributes: {list(item[0].__dict__.keys())[:10]}")
        elif isinstance(item, dict):
            print(f"{len(item)} items")
            if len(item) > 0:
                first_key = next(iter(item.keys()))
                first_val = item[first_key]
                print(f"    First key: {first_key}")
                print(f"    First value type: {type(first_val).__name__}")
        elif hasattr(item, '__dict__'):
            print(f"{type(item).__name__}")
            print(f"    Attributes: {list(item.__dict__.keys())}")
        else:
            print(f"{str(item)[:100]}")

    # Focus on items 3 and 5
    print("\n" + "=" * 80)
    print("DETAILED INSPECTION: [3] and [5]")
    print("=" * 80)

    # [3] - Solutions list
    solutions_list = result[3]
    print(f"\n[3] Solutions list:")
    print(f"  Type: {type(solutions_list)}")
    print(f"  Length: {len(solutions_list)}")
    if len(solutions_list) > 0:
        first_sol = solutions_list[0]
        print(f"  First solution type: {type(first_sol).__name__}")
        print(f"  First solution id: {id(first_sol)}")
        if hasattr(first_sol, '__dict__'):
            print(f"  First solution attributes: {list(first_sol.__dict__.keys())}")
        if hasattr(first_sol, '_name'):
            print(f"  First solution name: {first_sol._name}")

    # [5] - Library object
    library = result[5]
    print(f"\n[5] Library object:")
    print(f"  Type: {type(library).__name__}")
    if hasattr(library, '__dict__'):
        print(f"  Attributes: {list(library.__dict__.keys())}")

    if hasattr(library, 'solutions'):
        print(f"\n  Library.solutions:")
        print(f"    Type: {type(library.solutions)}")
        print(f"    Length: {len(library.solutions)}")

        if isinstance(library.solutions, dict):
            first_key = next(iter(library.solutions.keys()))
            first_solution_obj = library.solutions[first_key]
            print(f"    First key: {first_key}")
            print(f"    First value type: {type(first_solution_obj).__name__}")
            print(f"    First value id: {id(first_solution_obj)}")

            if hasattr(first_solution_obj, '__dict__'):
                print(f"    First value attributes: {list(first_solution_obj.__dict__.keys())}")

            if hasattr(first_solution_obj, 'originalSolution'):
                orig = first_solution_obj.originalSolution
                print(f"\n    First value has 'originalSolution':")
                print(f"      Type: {type(orig).__name__}")
                print(f"      Id: {id(orig)}")
                print(f"      Same object as solutions_list[0]? {orig is solutions_list[0]}")
                print(f"      Same ID as solutions_list[0]? {id(orig) == id(solutions_list[0])}")

                # Check if originalSolution is actually a duplicate
                if hasattr(orig, '__dict__') and hasattr(solutions_list[0], '__dict__'):
                    # Compare _state if available
                    if hasattr(orig, '_state') and hasattr(solutions_list[0], '_state'):
                        print(f"      _state equal? {orig._state == solutions_list[0]._state}")
                        print(f"      _state is same object? {orig._state is solutions_list[0]._state}")

                # Count how many references point to the same object
                print(f"\n    Checking all solutions for reference sharing:")
                reference_count = 0
                for i in range(min(100, len(library.solutions))):
                    if i in library.solutions:
                        sol = library.solutions[i]
                        if hasattr(sol, 'originalSolution'):
                            if sol.originalSolution is solutions_list[i]:
                                reference_count += 1
                print(f"      First 100 wrapper solutions with correct references: {reference_count}/100")

    return 0


if __name__ == "__main__":
    sys.exit(main())
