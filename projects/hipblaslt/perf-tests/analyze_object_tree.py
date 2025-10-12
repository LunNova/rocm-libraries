#!/usr/bin/env python3
"""
Analyze the object tree returned by parseLibraryLogicFile to identify
where strings appear and which ones get auto-interned by pickle.
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


class StringLocationTracker:
    """Track where strings appear in an object tree."""

    def __init__(self):
        self.locations = defaultdict(int)
        self.sample_strings = defaultdict(set)
        self.visited_ids = set()

    def analyze(self, obj, path="root", depth=0, max_depth=10):
        """Recursively analyze an object tree."""
        if depth > max_depth:
            return

        # Avoid infinite recursion
        obj_id = id(obj)
        if obj_id in self.visited_ids:
            return
        self.visited_ids.add(obj_id)

        if isinstance(obj, str):
            location = f"{path} (str)"
            self.locations[location] += 1
            if len(self.sample_strings[location]) < 5:
                self.sample_strings[location].add(obj[:50])  # First 50 chars

        elif isinstance(obj, dict):
            # Dictionary keys - these GET auto-interned by pickle
            for key in obj.keys():
                if isinstance(key, str):
                    location = f"{path}.__dict__[key]"
                    self.locations[location] += 1
                    if len(self.sample_strings[location]) < 5:
                        self.sample_strings[location].add(key[:50])

            # Dictionary values - these DON'T get auto-interned
            for key, value in obj.items():
                self.analyze(value, f"{path}[{repr(key)[:30]}]", depth + 1, max_depth)

        elif isinstance(obj, (list, tuple)):
            # List/tuple elements - these DON'T get auto-interned
            for i, item in enumerate(obj):
                if i < 100:  # Limit to first 100 items for performance
                    self.analyze(item, f"{path}[{i}]", depth + 1, max_depth)

        elif hasattr(obj, '__dict__'):
            # Object attributes via __dict__ - keys GET auto-interned, values don't
            for key, value in obj.__dict__.items():
                if isinstance(key, str):
                    location = f"{type(obj).__name__}.__dict__[key]"
                    self.locations[location] += 1
                    if len(self.sample_strings[location]) < 5:
                        self.sample_strings[location].add(key[:50])
                self.analyze(value, f"{path}.{key}", depth + 1, max_depth)

        elif hasattr(obj, '_asdict'):  # NamedTuple
            # NamedTuple fields - field names are in __dict__ keys
            for key, value in obj._asdict().items():
                self.analyze(value, f"{path}.{key}", depth + 1, max_depth)

        # Check for common container types
        if hasattr(obj, 'state'):
            self.analyze(obj.state, f"{path}.state", depth + 1, max_depth)
        if hasattr(obj, '_state'):
            self.analyze(obj._state, f"{path}._state", depth + 1, max_depth)

    def report(self):
        """Print analysis report."""
        print("\n" + "=" * 80)
        print("STRING LOCATION ANALYSIS")
        print("=" * 80)

        # Separate into auto-interned and non-interned
        auto_interned = {}
        non_interned = {}

        for location, count in self.locations.items():
            if "__dict__[key]" in location:
                auto_interned[location] = count
            else:
                non_interned[location] = count

        print("\n🟢 AUTO-INTERNED by Python's pickle (dict keys in __dict__):")
        print("-" * 80)
        if auto_interned:
            for location in sorted(auto_interned.items(), key=lambda x: -x[1])[:20]:
                loc, count = location
                print(f"  {count:>8,} strings: {loc}")
                if self.sample_strings[loc]:
                    samples = list(self.sample_strings[loc])[:3]
                    print(f"           Samples: {samples}")
        else:
            print("  (none found)")

        print("\n🔴 NOT AUTO-INTERNED (dict values, list elements, etc.):")
        print("-" * 80)
        if non_interned:
            for location in sorted(non_interned.items(), key=lambda x: -x[1])[:20]:
                loc, count = location
                print(f"  {count:>8,} strings: {loc}")
                if self.sample_strings[loc]:
                    samples = list(self.sample_strings[loc])[:3]
                    print(f"           Samples: {samples}")
        else:
            print("  (none found)")

        total_interned = sum(auto_interned.values())
        total_not_interned = sum(non_interned.values())
        total = total_interned + total_not_interned

        print("\n" + "=" * 80)
        print(f"SUMMARY:")
        print(f"  Auto-interned strings: {total_interned:>12,} ({100*total_interned/total:>5.1f}%)")
        print(f"  Not auto-interned:     {total_not_interned:>12,} ({100*total_not_interned/total:>5.1f}%)")
        print(f"  Total strings:         {total:>12,}")
        print("=" * 80)


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

    print("Parse complete. Analyzing object tree...")

    # Analyze the result
    tracker = StringLocationTracker()
    tracker.analyze(result, path="LibraryLogic", max_depth=15)

    # Print report
    tracker.report()

    return 0


if __name__ == "__main__":
    sys.exit(main())
