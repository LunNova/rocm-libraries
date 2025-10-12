#!/usr/bin/env python3
"""
Roundtrip test harness for typed config parsing.

Tests: typed YAML → typed config → dict → YAML → typed config
Verifies that typed parsing produces identical results to dict parsing.
"""

import sys
import yaml
from pathlib import Path
from typing import Any, Dict

# Add Tensile to path
script_dir = Path(__file__).parent.resolve()
tensile_path = script_dir.parent / "tensilelite"
sys.path.insert(0, str(tensile_path))

from Tensile.CustomYamlLoader import (
    load_yaml_stream,
    load_library_logic_typed,
    DEFAULT_YAML_LOADER
)
from Tensile.ConfigSchema import (
    SlottedConfig,
    to_dict,
    VersionInfo,
    ArchitectureInfo,
    ProblemTypeConfig,
    SolutionConfig
)


def compare_values(v1: Any, v2: Any, path: str = "") -> list:
    """
    Recursively compare two values and return list of differences.

    Args:
        v1: First value (from typed parsing)
        v2: Second value (from dict parsing)
        path: Current path in the structure (for error messages)

    Returns:
        List of difference strings
    """
    diffs = []

    # Handle None cases
    if v1 is None and v2 is None:
        return []
    if v1 is None or v2 is None:
        diffs.append(f"{path}: {v1} != {v2}")
        return diffs

    # Handle SlottedConfig vs dict
    if isinstance(v1, SlottedConfig) and isinstance(v2, dict):
        # Convert SlottedConfig to dict for comparison
        v1_dict = dict(v1.items())
        return compare_values(v1_dict, v2, path)

    # Handle dict comparison
    if isinstance(v1, dict) and isinstance(v2, dict):
        # Check keys
        keys1 = set(v1.keys())
        keys2 = set(v2.keys())

        if keys1 != keys2:
            missing_in_1 = keys2 - keys1
            missing_in_2 = keys1 - keys2
            if missing_in_1:
                diffs.append(f"{path}: Missing keys in typed: {missing_in_1}")
            if missing_in_2:
                diffs.append(f"{path}: Extra keys in typed: {missing_in_2}")

        # Compare common keys
        for key in keys1 & keys2:
            key_path = f"{path}.{key}" if path else key
            diffs.extend(compare_values(v1[key], v2[key], key_path))

        return diffs

    # Handle list comparison
    if isinstance(v1, list) and isinstance(v2, list):
        if len(v1) != len(v2):
            diffs.append(f"{path}: List lengths differ: {len(v1)} != {len(v2)}")
            return diffs

        for i, (item1, item2) in enumerate(zip(v1, v2)):
            item_path = f"{path}[{i}]"
            diffs.extend(compare_values(item1, item2, item_path))

        return diffs

    # Handle scalar comparison
    if v1 != v2:
        # Special handling for numeric types that might differ slightly
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            if abs(v1 - v2) < 1e-9:
                return []
        diffs.append(f"{path}: {v1!r} != {v2!r}")

    return diffs


def test_roundtrip(yaml_file: Path) -> bool:
    """
    Test roundtrip: YAML → typed config → dict → YAML → typed config

    Args:
        yaml_file: Path to YAML file to test

    Returns:
        True if test passes, False otherwise
    """
    print(f"\n{'='*70}")
    print(f"Testing: {yaml_file.name}")
    print(f"{'='*70}")

    # Step 1: Load with generic dict parser (baseline)
    print("\n1. Loading with generic dict parser...")
    try:
        data_dict = load_yaml_stream(yaml_file, DEFAULT_YAML_LOADER)
        print(f"   ✓ Loaded {len(data_dict)} top-level items")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False

    # Step 2: Load with typed parser
    print("\n2. Loading with typed parser...")
    try:
        data_typed = load_library_logic_typed(yaml_file, DEFAULT_YAML_LOADER)
        print(f"   ✓ Loaded {len(data_typed)} top-level items")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 3: Check types
    print("\n3. Checking types...")
    type_checks = []

    if len(data_typed) > 0 and isinstance(data_typed[0], VersionInfo):
        type_checks.append("data[0]: VersionInfo ✓")
    else:
        type_checks.append(f"data[0]: Expected VersionInfo, got {type(data_typed[0]).__name__} ✗")

    if len(data_typed) > 2:
        if isinstance(data_typed[2], (ArchitectureInfo, str)):
            type_checks.append(f"data[2]: {type(data_typed[2]).__name__} ✓")
        else:
            type_checks.append(f"data[2]: Expected ArchitectureInfo or str, got {type(data_typed[2]).__name__} ✗")

    if len(data_typed) > 4 and isinstance(data_typed[4], ProblemTypeConfig):
        type_checks.append("data[4]: ProblemTypeConfig ✓")
    else:
        type_checks.append(f"data[4]: Expected ProblemTypeConfig, got {type(data_typed[4]).__name__} ✗")

    if len(data_typed) > 5 and isinstance(data_typed[5], list):
        if len(data_typed[5]) > 0:
            if isinstance(data_typed[5][0], SolutionConfig):
                type_checks.append(f"data[5][0]: SolutionConfig ✓ ({len(data_typed[5])} solutions)")
            else:
                type_checks.append(f"data[5][0]: Expected SolutionConfig, got {type(data_typed[5][0]).__name__} ✗")

    for check in type_checks:
        print(f"   {check}")

    # Step 4: Compare typed vs dict parsing
    print("\n4. Comparing typed vs dict parsing...")
    diffs = compare_values(data_typed, data_dict)

    if diffs:
        print(f"   ✗ Found {len(diffs)} differences:")
        for diff in diffs[:10]:  # Show first 10 differences
            print(f"     - {diff}")
        if len(diffs) > 10:
            print(f"     ... and {len(diffs) - 10} more")
        return False
    else:
        print("   ✓ Typed and dict parsing produce identical results")

    # Step 5: Convert to dict and write to YAML
    print("\n5. Converting to dict and writing to YAML...")
    try:
        data_as_dict = to_dict(data_typed)
        output_file = yaml_file.parent / f"{yaml_file.stem}_roundtrip.yaml"

        with open(output_file, 'w') as f:
            yaml.dump(data_as_dict, f,
                      explicit_start=True,
                      explicit_end=True,
                      default_flow_style=None)
        print(f"   ✓ Wrote to {output_file.name}")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 6: Re-load the written YAML with typed parser
    print("\n6. Re-loading written YAML with typed parser...")
    try:
        data_reloaded = load_library_logic_typed(output_file, DEFAULT_YAML_LOADER)
        print(f"   ✓ Reloaded {len(data_reloaded)} top-level items")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 7: Compare reloaded vs original typed
    print("\n7. Comparing reloaded vs original typed...")
    diffs = compare_values(data_reloaded, data_typed)

    if diffs:
        print(f"   ✗ Found {len(diffs)} differences after roundtrip:")
        for diff in diffs[:10]:
            print(f"     - {diff}")
        if len(diffs) > 10:
            print(f"     ... and {len(diffs) - 10} more")
        return False
    else:
        print("   ✓ Roundtrip successful - data identical")

    print(f"\n{'='*70}")
    print("✓ ROUNDTRIP TEST PASSED")
    print(f"{'='*70}\n")

    return True


def main():
    """Main entry point"""
    print("="*70)
    print("Typed Config Roundtrip Test Harness")
    print("="*70)

    # Find test file
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    logic_dir = project_root / "library/src/amd_detail/rocblaslt/src/Tensile/Logic"

    if not logic_dir.exists():
        print(f"ERROR: Logic directory not found: {logic_dir}")
        return 1

    # Find a test YAML file
    yaml_files = list(logic_dir.rglob("*.yaml"))
    if not yaml_files:
        print(f"ERROR: No YAML files found in {logic_dir}")
        return 1

    # Sort by size and pick a medium-sized one (not the largest, for faster testing)
    yaml_files.sort(key=lambda f: f.stat().st_size)

    # Pick a file that's around 10-20 MB for testing
    test_file = None
    for f in yaml_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        if 10 < size_mb < 30:
            test_file = f
            break

    if not test_file:
        # Fall back to smallest file
        test_file = yaml_files[0]

    print(f"\nTest file: {test_file}")
    print(f"Size: {test_file.stat().st_size / (1024 * 1024):.2f} MB")

    # Run test
    success = test_roundtrip(test_file)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
