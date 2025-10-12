#!/usr/bin/env python3
"""
Enhanced analysis of duplicate Solution instances.
Shows attribute paths to duplicates and analyzes whether they indicate a bug.
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


class SolutionDuplicateTracker:
    """Track Solution instances and their attribute paths."""

    def __init__(self):
        # Map from (hashable representation) -> list of (obj_id, path, obj)
        self.solutions_by_content = defaultdict(list)
        self.visited_ids = set()

    def track(self, obj, path="root", depth=0, max_depth=15):
        """Recursively track Solution instances."""
        if depth > max_depth:
            return

        obj_id = id(obj)
        if obj_id in self.visited_ids:
            return
        self.visited_ids.add(obj_id)

        # Track Solution instances
        if type(obj).__name__ == 'Solution':
            try:
                # Create a hashable representation based on solution state
                rep = self._make_solution_repr(obj)
                self.solutions_by_content[rep].append({
                    'id': obj_id,
                    'path': path,
                    'obj': obj
                })
            except Exception as e:
                print(f"Warning: Could not hash Solution at {path}: {e}")

        # Recurse into container types
        if isinstance(obj, dict):
            for key, value in obj.items():
                self.track(value, f"{path}[{repr(key)[:50]}]", depth + 1, max_depth)
        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                if i < 1000:  # Limit for performance (matches original)
                    self.track(item, f"{path}[{i}]", depth + 1, max_depth)
        elif hasattr(obj, '__dict__'):
            for key, value in obj.__dict__.items():
                self.track(value, f"{path}.{key}", depth + 1, max_depth)
        elif hasattr(obj, '_asdict'):  # NamedTuple
            for key, value in obj._asdict().items():
                self.track(value, f"{path}.{key}", depth + 1, max_depth)

        # Check for common attributes (matches original)
        if hasattr(obj, 'state'):
            self.track(obj.state, f"{path}.state", depth + 1, max_depth)
        if hasattr(obj, '_state'):
            self.track(obj._state, f"{path}._state", depth + 1, max_depth)
        if hasattr(obj, 'solutions') and isinstance(obj.solutions, dict):
            for key, value in list(obj.solutions.items())[:100]:
                self.track(value, f"{path}.solutions[{repr(key)[:30]}]", depth + 1, max_depth)

    def _make_solution_repr(self, solution):
        """Create a hashable representation of a Solution (matches original logic)."""
        # Use exact same logic as original analyze_redundancy.py
        if hasattr(solution, 'state'):
            return self._make_hashable(solution.state)
        elif hasattr(solution, '_state'):
            return self._make_hashable(solution._state)
        elif hasattr(solution, '__dict__'):
            return self._make_hashable(solution.__dict__)
        else:
            return str(solution)

    def _make_hashable(self, obj):
        """Convert object to hashable representation (matches original logic)."""
        if isinstance(obj, dict):
            items = []
            for k, v in sorted(obj.items()):
                if isinstance(k, str):
                    items.append((k, self._make_hashable(v)))
            return tuple(items)
        elif isinstance(obj, list):
            return tuple(self._make_hashable(x) for x in obj)
        elif isinstance(obj, tuple):
            return tuple(self._make_hashable(x) for x in obj)
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        elif hasattr(obj, '__hash__') and callable(obj.__hash__):
            try:
                return hash(obj)
            except:
                return id(obj)
        else:
            return id(obj)

    def analyze_duplicates(self):
        """Analyze and report duplicate Solutions."""
        print("\n" + "=" * 80)
        print("DUPLICATE SOLUTION ANALYSIS")
        print("=" * 80)

        total_solutions = sum(len(instances) for instances in self.solutions_by_content.values())
        unique_contents = len(self.solutions_by_content)
        duplicate_count = total_solutions - unique_contents

        print(f"\nTotal Solution instances:     {total_solutions:>10,}")
        print(f"Unique contents:              {unique_contents:>10,}")
        print(f"Duplicate instances:          {duplicate_count:>10,}")

        if duplicate_count == 0:
            print("\nNo duplicates found!")
            return

        # Find duplicate groups
        duplicate_groups = {rep: instances for rep, instances in self.solutions_by_content.items()
                          if len(instances) > 1}

        print(f"Duplicate groups:             {len(duplicate_groups):>10,}")

        # Analyze duplicate groups
        print("\n" + "=" * 80)
        print("DUPLICATE GROUPS DETAIL")
        print("=" * 80)

        # Show first few duplicate groups
        for i, (rep, instances) in enumerate(sorted(duplicate_groups.items(),
                                                    key=lambda x: -len(x[1]))[:10]):
            print(f"\nGroup {i+1}: {len(instances)} identical Solutions")
            print("-" * 80)

            # Show paths to all instances in this group
            for j, inst in enumerate(instances):
                print(f"  Instance {j+1} (id={inst['id']}): {inst['path']}")

            # Show solution details from first instance
            solution = instances[0]['obj']
            print(f"\n  Solution details:")

            # Show basic attributes
            if hasattr(solution, '_name'):
                print(f"    Name: {solution._name}")
            if hasattr(solution, 'index'):
                print(f"    Index: {solution.index}")

            # Show state details
            if hasattr(solution, 'state'):
                state = solution.state
                print(f"    State keys: {list(state.keys())[:10]}")
                # Show a few important state values
                for key in ['ProblemType', 'KernelLanguage', 'LoopTail', 'NumLoadsCoalescedA', 'NumLoadsCoalescedB']:
                    if key in state:
                        print(f"      {key}: {state[key]}")
            elif hasattr(solution, '__dict__'):
                print(f"    __dict__ keys: {list(solution.__dict__.keys())[:10]}")

            # Check if these are the SAME object (same id) or DIFFERENT objects with identical content
            same_object = len(set(inst['id'] for inst in instances)) == 1
            print(f"\n  Are these the same object instance? {same_object}")
            if same_object:
                print("    ⚠️  This is the SAME object referenced multiple times (not a problem)")
            else:
                print("    ⚠️  These are DIFFERENT objects with IDENTICAL content (memory waste!)")

            # Check if all paths are in the same parent structure
            paths = [inst['path'] for inst in instances]
            print(f"\n  Paths:")
            for path in paths:
                print(f"    - {path}")

        # Summary by path pattern
        print("\n" + "=" * 80)
        print("DUPLICATE LOCATION PATTERNS")
        print("=" * 80)

        path_patterns = defaultdict(int)
        for instances in duplicate_groups.values():
            for inst in instances:
                path = inst['path']
                # Extract path pattern (e.g., root[4].solutions[...])
                parts = path.split('.')
                if len(parts) >= 2:
                    pattern = '.'.join(parts[:2])
                else:
                    pattern = parts[0]
                path_patterns[pattern] += 1

        print("\nDuplicate instances by path pattern:")
        for pattern, count in sorted(path_patterns.items(), key=lambda x: -x[1])[:20]:
            print(f"  {count:>6} duplicates in: {pattern}")


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

    print("Parse complete. Tracking Solution instances...")

    # Track Solution instances
    tracker = SolutionDuplicateTracker()
    tracker.track(result, path="LibraryLogic", max_depth=20)

    # Analyze duplicates
    tracker.analyze_duplicates()

    return 0


if __name__ == "__main__":
    sys.exit(main())
