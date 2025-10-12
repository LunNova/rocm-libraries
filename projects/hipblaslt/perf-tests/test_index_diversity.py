#!/usr/bin/env python3
"""
Check how many unique index instances are actually created during parsing.
"""

import sys
from pathlib import Path
from collections import defaultdict

# Add Tensile to path
script_dir = Path(__file__).parent.resolve()
tensile_path = script_dir.parent / "tensilelite"
sys.path.insert(0, str(tensile_path))

from Tensile import LibraryIO
from Tensile.Common.Architectures import gfxToIsa
from Tensile.Common.Capabilities import makeIsaInfoMap
from Tensile.Toolchain.Assembly import makeAssemblyToolchain
from Tensile.Toolchain.Validators import validateToolchain
from Tensile.Contractions import FreeIndex, BatchIndex, BoundIndex


def main():
    print("Loading library logic file...")

    # Find the largest logic file
    project_root = script_dir.parent
    logic_dir = project_root / "library/src/amd_detail/rocblaslt/src/Tensile/Logic"

    yaml_files = list(logic_dir.rglob("*.yaml"))
    yaml_files.sort(key=lambda f: f.stat().st_size, reverse=True)
    logic_file = yaml_files[0]

    print(f"File: {logic_file.name}")
    print(f"Size: {logic_file.stat().st_size / (1024*1024):.2f} MB")

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

    schedule, architecture, problem_type, solutions, exact_logic, library = result

    print(f"\nParsed: {len(solutions)} solutions")
    print(f"ProblemType: {problem_type}")

    # Inspect library structure to find indices
    print("\n" + "=" * 80)
    print("DEEP INSPECTION: Finding indices in library structure")
    print("=" * 80)

    def find_indices(obj, path="", depth=0, max_depth=10, visited=None):
        """Recursively find all index objects."""
        if visited is None:
            visited = set()

        if depth > max_depth or id(obj) in visited:
            return []
        visited.add(id(obj))

        indices_found = []

        # Check if this is an index
        if isinstance(obj, (FreeIndex, BatchIndex, BoundIndex)):
            attrs = {}
            for attr in ['isA', 'i', 'c', 'd', 'a', 'b', 'aMirror', 'bMirror']:
                if hasattr(obj, attr):
                    attrs[attr] = getattr(obj, attr)
            indices_found.append({
                'path': path,
                'type': type(obj).__name__,
                'id': id(obj),
                'attrs': attrs,
                'obj': obj
            })

        # Recurse
        if isinstance(obj, dict):
            for k, v in list(obj.items())[:100]:
                indices_found.extend(find_indices(v, f"{path}.{k}", depth+1, max_depth, visited))
        elif isinstance(obj, (list, tuple)):
            for i, v in enumerate(list(obj)[:100]):
                indices_found.extend(find_indices(v, f"{path}[{i}]", depth+1, max_depth, visited))
        elif hasattr(obj, '__dict__'):
            for k, v in obj.__dict__.items():
                indices_found.extend(find_indices(v, f"{path}.{k}", depth+1, max_depth, visited))

        return indices_found

    # Check library.solutions directly - much faster
    print("\nSearching library.solutions...")
    all_indices = []

    if hasattr(library, 'solutions'):
        print(f"Library has {len(library.solutions)} solutions")
        # Just check the first few solutions to find indices
        for i, (key, sol) in enumerate(list(library.solutions.items())[:100]):
            if hasattr(sol, '_problemType'):
                pt = sol._problemType
                if hasattr(pt, 'indices'):
                    for idx in pt.indices:
                        if isinstance(idx, (FreeIndex, BatchIndex, BoundIndex)):
                            attrs = {}
                            for attr in ['isA', 'i', 'c', 'd', 'a', 'b', 'aMirror', 'bMirror']:
                                if hasattr(idx, attr):
                                    attrs[attr] = getattr(idx, attr)
                            all_indices.append({
                                'path': f'solution[{key}]',
                                'type': type(idx).__name__,
                                'id': id(idx),
                                'attrs': attrs,
                                'obj': idx
                            })
    else:
        print("Library doesn't have solutions dict, doing deep search...")
        all_indices = find_indices(library, "library", max_depth=8)

    print(f"Found {len(all_indices)} index instances (sampled)")

    # Group by type
    by_type = defaultdict(list)
    for idx_info in all_indices:
        by_type[idx_info['type']].append(idx_info)

    for idx_type in ['FreeIndex', 'BatchIndex', 'BoundIndex']:
        if idx_type in by_type:
            instances = by_type[idx_type]
            unique_ids = len(set(i['id'] for i in instances))
            print(f"\n{idx_type}: {len(instances)} references, {unique_ids} unique instances")

            # Show unique instances with their attributes
            seen_ids = set()
            for idx_info in instances:
                if idx_info['id'] not in seen_ids:
                    seen_ids.add(idx_info['id'])
                    attrs_str = ', '.join(f"{k}={v}" for k, v in sorted(idx_info['attrs'].items()))
                    print(f"  id={idx_info['id']:16x}: {attrs_str}")
                    if len(seen_ids) >= 10:  # Limit output
                        remaining = unique_ids - len(seen_ids)
                        if remaining > 0:
                            print(f"  ... and {remaining} more unique instances")
                        break

    # Now cross-check with YAML file
    print("\n" + "=" * 80)
    print("YAML CROSS-CHECK")
    print("=" * 80)

    import yaml
    print(f"\nReading YAML file: {logic_file.name}")
    with open(logic_file, 'r') as f:
        yaml_data = yaml.safe_load(f)

    if 'ProblemType' in yaml_data:
        pt_data = yaml_data['ProblemType']
        print("\nProblemType from YAML:")
        print(f"  IndexAssignmentsA: {pt_data.get('IndexAssignmentsA')}")
        print(f"  IndexAssignmentsB: {pt_data.get('IndexAssignmentsB')}")
        print(f"  IndicesBatch: {pt_data.get('IndicesBatch')}")
        print(f"  IndicesFree: {pt_data.get('IndicesFree')}")
        print(f"  IndicesSummation: {pt_data.get('IndicesSummation')}")
        print(f"  NumIndicesC: {pt_data.get('NumIndicesC')}")

        # Expected index count
        total_expected = pt_data.get('TotalIndices', 0)
        free_expected = len(pt_data.get('IndicesFree', []))
        batch_expected = len(pt_data.get('IndicesBatch', []))
        bound_expected = len(pt_data.get('IndicesSummation', []))

        print(f"\nExpected indices:")
        print(f"  Total: {total_expected}")
        print(f"  Free: {free_expected}")
        print(f"  Batch: {batch_expected}")
        print(f"  Bound/Summation: {bound_expected}")

        # Cross-reference with what we found
        print(f"\nFound in loaded library:")
        for idx_type in ['FreeIndex', 'BatchIndex', 'BoundIndex']:
            if idx_type in by_type:
                instances = by_type[idx_type]
                unique_ids = len(set(i['id'] for i in instances))
                refs = len(instances)
                print(f"  {idx_type}: {refs} references → {unique_ids} unique instances")

        print("\n" + "=" * 80)
        print("ANALYSIS")
        print("=" * 80)

        # Since all solutions in this file have the same problem type,
        # we expect just 1 unique instance of each index with potentially many references
        print("\nThis YAML file contains one ProblemType configuration.")
        print("All solutions share the same index structure, so we expect:")
        print(f"  - {free_expected} unique FreeIndex instances (one per free dimension)")
        print(f"  - {batch_expected} unique BatchIndex instances (one per batch dimension)")
        print(f"  - {bound_expected} unique BoundIndex instances (one per summation dimension)")
        print("\nEach unique instance will be referenced many times across solutions.")

        # Verify
        success = True
        for idx_type, expected in [('FreeIndex', free_expected),
                                     ('BatchIndex', batch_expected),
                                     ('BoundIndex', bound_expected)]:
            if idx_type in by_type:
                unique_count = len(set(i['id'] for i in by_type[idx_type]))
                if unique_count == expected:
                    print(f"✓ {idx_type}: {unique_count} unique instances (matches expected {expected})")
                else:
                    print(f"✗ {idx_type}: {unique_count} unique instances (expected {expected})")
                    success = False
            elif expected == 0:
                print(f"✓ {idx_type}: 0 instances (expected {expected})")
            else:
                print(f"✗ {idx_type}: not found (expected {expected})")
                success = False

        return 0 if success else 1
    else:
        print("ERROR: No ProblemType in YAML")
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
