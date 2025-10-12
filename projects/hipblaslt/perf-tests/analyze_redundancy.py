#!/usr/bin/env python3
"""
Analyze redundancy in object instances returned by parseLibraryLogicFile.
Identify duplicate ProblemType, ProblemPredicate, DataType, etc. instances
that could potentially be deduplicated.
"""

import sys
from pathlib import Path
from collections import defaultdict, Counter

# Add Tensile to path
script_dir = Path(__file__).parent.resolve()
tensile_path = script_dir.parent / "tensilelite"
sys.path.insert(0, str(tensile_path))

from Tensile import LibraryIO
from Tensile.Common.Architectures import gfxToIsa
from Tensile.Common.Capabilities import makeIsaInfoMap
from Tensile.Toolchain.Assembly import makeAssemblyToolchain
from Tensile.Toolchain.Validators import validateToolchain


class InstanceTracker:
    """Track instances of objects to find redundancy."""

    def __init__(self):
        self.instances_by_type = defaultdict(list)
        self.visited_ids = set()

    def track(self, obj, path="root", depth=0, max_depth=15):
        """Recursively track object instances."""
        if depth > max_depth:
            return

        obj_id = id(obj)
        if obj_id in self.visited_ids:
            return
        self.visited_ids.add(obj_id)

        # Track interesting types
        type_name = type(obj).__name__
        if type_name in ['ProblemType', 'ProblemPredicate', 'DataType',
                         'SizeMapping', 'Solution', 'HardwarePredicate',
                         'TaskPredicate', 'ActivationType', 'FreeIndex',
                         'BatchIndex', 'BoundIndex']:
            # Store object and its hashable representation
            try:
                # Try to create a hashable representation
                if hasattr(obj, 'state'):
                    rep = self._make_hashable(obj.state)
                elif hasattr(obj, '_state'):
                    rep = self._make_hashable(obj._state)
                elif hasattr(obj, '__dict__'):
                    rep = self._make_hashable(obj.__dict__)
                else:
                    rep = str(obj)

                self.instances_by_type[type_name].append({
                    'id': obj_id,
                    'representation': rep,
                    'path': path,
                    'obj': obj
                })
            except Exception as e:
                # If we can't hash it, just count it
                self.instances_by_type[type_name].append({
                    'id': obj_id,
                    'representation': None,
                    'path': path,
                    'obj': obj
                })

        # Recurse into container types
        if isinstance(obj, dict):
            for key, value in obj.items():
                self.track(value, f"{path}[{repr(key)[:30]}]", depth + 1, max_depth)
        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                if i < 1000:  # Limit for performance
                    self.track(item, f"{path}[{i}]", depth + 1, max_depth)
        elif hasattr(obj, '__dict__'):
            for key, value in obj.__dict__.items():
                self.track(value, f"{path}.{key}", depth + 1, max_depth)
        elif hasattr(obj, '_asdict'):  # NamedTuple
            for key, value in obj._asdict().items():
                self.track(value, f"{path}.{key}", depth + 1, max_depth)

        # Check for common attributes
        if hasattr(obj, 'state'):
            self.track(obj.state, f"{path}.state", depth + 1, max_depth)
        if hasattr(obj, '_state'):
            self.track(obj._state, f"{path}._state", depth + 1, max_depth)
        if hasattr(obj, 'solutions') and isinstance(obj.solutions, dict):
            for key, value in list(obj.solutions.items())[:100]:
                self.track(value, f"{path}.solutions[{key}]", depth + 1, max_depth)

    def _make_hashable(self, obj):
        """Convert object to hashable representation."""
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

    def analyze_redundancy(self):
        """Analyze and report redundancy for each type."""
        print("\n" + "=" * 80)
        print("INSTANCE REDUNDANCY ANALYSIS")
        print("=" * 80)

        for type_name in sorted(self.instances_by_type.keys()):
            instances = self.instances_by_type[type_name]
            total_count = len(instances)

            # Count unique representations
            rep_counts = Counter()
            for inst in instances:
                if inst['representation'] is not None:
                    rep_counts[inst['representation']] += 1

            unique_count = len(rep_counts)

            print(f"\n{type_name}:")
            print(f"  Total instances:  {total_count:>8,}")
            print(f"  Unique instances: {unique_count:>8,}")

            if unique_count > 0 and total_count > unique_count:
                redundancy = total_count - unique_count
                redundancy_pct = 100 * redundancy / total_count
                print(f"  Redundant:        {redundancy:>8,} ({redundancy_pct:.1f}%)")

                # Show most common duplicates
                most_common = rep_counts.most_common(5)
                if len(most_common) > 1 and most_common[0][1] > 1:
                    print(f"  Most duplicated instances:")
                    for rep, count in most_common:
                        if count > 1:
                            # Find an example instance
                            example = next(inst for inst in instances
                                         if inst['representation'] == rep)

                            # Try to show a meaningful sample
                            if hasattr(example['obj'], '__dict__'):
                                sample_keys = list(example['obj'].__dict__.keys())[:5]
                                print(f"    - {count:>6,}x: {sample_keys}")
                            else:
                                print(f"    - {count:>6,}x duplicates")

            # Memory estimate
            if hasattr(instances[0]['obj'], '__sizeof__'):
                try:
                    avg_size = sum(inst['obj'].__sizeof__() for inst in instances[:100]) / min(100, len(instances))
                    total_memory_mb = (avg_size * total_count) / (1024 * 1024)
                    if unique_count > 0:
                        optimal_memory_mb = (avg_size * unique_count) / (1024 * 1024)
                        potential_savings_mb = total_memory_mb - optimal_memory_mb
                        print(f"  Estimated memory: {total_memory_mb:.2f} MB")
                        if potential_savings_mb > 0.1:
                            print(f"  Potential savings: {potential_savings_mb:.2f} MB " +
                                  f"({100*potential_savings_mb/total_memory_mb:.1f}%)")
                except:
                    pass

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        total_instances = sum(len(insts) for insts in self.instances_by_type.values())
        total_unique = sum(len(set(inst['representation'] for inst in insts
                                   if inst['representation'] is not None))
                          for insts in self.instances_by_type.values())

        print(f"Total instances across all types: {total_instances:>10,}")
        print(f"Unique instances:                 {total_unique:>10,}")
        if total_unique > 0:
            print(f"Redundant instances:              {total_instances - total_unique:>10,} " +
                  f"({100*(total_instances - total_unique)/total_instances:.1f}%)")


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

    print("Parse complete. Analyzing instances...")

    # Track instances
    tracker = InstanceTracker()
    tracker.track(result, path="LibraryLogic", max_depth=20)

    # Analyze redundancy
    tracker.analyze_redundancy()

    return 0


if __name__ == "__main__":
    sys.exit(main())
