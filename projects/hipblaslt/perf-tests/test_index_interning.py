#!/usr/bin/env python3
"""
Test that index interning is working correctly and not over-deduplicating.
"""

import sys
from pathlib import Path

# Add Tensile to path
script_dir = Path(__file__).parent.resolve()
tensile_path = script_dir.parent / "tensilelite"
sys.path.insert(0, str(tensile_path))

from Tensile.Contractions import FreeIndex, BatchIndex, BoundIndex
from Tensile.Contractions import intern_free_index, intern_batch_index, intern_bound_index


def test_interning_basic():
    """Test that interning works correctly."""
    print("=" * 80)
    print("TEST: Basic interning functionality")
    print("=" * 80)

    # Test 1: Same parameters should return same instance
    print("\n1. Same parameters should return same instance:")
    fi1 = intern_free_index(True, 0, 1, 1, 0, None)
    fi2 = intern_free_index(True, 0, 1, 1, 0, None)
    print(f"   fi1 is fi2: {fi1 is fi2} (should be True)")
    print(f"   fi1.isA={fi1.isA}, fi1.a={fi1.a}, fi1.i={fi1.i}")
    assert fi1 is fi2, "Same parameters should return same instance!"

    # Test 2: Different parameters should return different instances
    print("\n2. Different parameters should return different instances:")
    fi3 = intern_free_index(True, 1, 1, 1, 0, None)  # Different i
    print(f"   fi1 is fi3: {fi1 is fi3} (should be False)")
    print(f"   fi1.i={fi1.i}, fi3.i={fi3.i}")
    assert fi1 is not fi3, "Different parameters should return different instances!"

    fi4 = intern_free_index(True, 0, 1, 1, 1, None)  # Different a
    print(f"   fi1 is fi4: {fi1 is fi4} (should be False)")
    print(f"   fi1.a={fi1.a}, fi4.a={fi4.a}")
    assert fi1 is not fi4, "Different .a should return different instances!"

    # Test 3: BatchIndex interning
    print("\n3. BatchIndex interning:")
    bi1 = intern_batch_index(0, 0, 1, 1)
    bi2 = intern_batch_index(0, 0, 1, 1)
    bi3 = intern_batch_index(1, 0, 1, 1)  # Different a
    print(f"   bi1 is bi2: {bi1 is bi2} (should be True)")
    print(f"   bi1 is bi3: {bi1 is bi3} (should be False)")
    print(f"   bi1.a={bi1.a}, bi3.a={bi3.a}")
    assert bi1 is bi2, "Same BatchIndex params should return same instance!"
    assert bi1 is not bi3, "Different BatchIndex params should return different instances!"

    # Test 4: BoundIndex interning
    print("\n4. BoundIndex interning:")
    bnd1 = intern_bound_index(0, 0, False, False)
    bnd2 = intern_bound_index(0, 0, False, False)
    bnd3 = intern_bound_index(0, 0, True, False)  # Different aMirror
    print(f"   bnd1 is bnd2: {bnd1 is bnd2} (should be True)")
    print(f"   bnd1 is bnd3: {bnd1 is bnd3} (should be False)")
    print(f"   bnd1.aMirror={bnd1.aMirror}, bnd3.aMirror={bnd3.aMirror}")
    assert bnd1 is bnd2, "Same BoundIndex params should return same instance!"
    assert bnd1 is not bnd3, "Different BoundIndex params should return different instances!"

    print("\n✓ All basic interning tests passed!")


def test_real_problem_type():
    """Test with actual ProblemType creation."""
    print("\n" + "=" * 80)
    print("TEST: Real ProblemType creation")
    print("=" * 80)

    from Tensile.Contractions import ProblemType

    # Create two ProblemTypes with identical index configurations
    problem_data_1 = {
        'OperationType': 'GEMM',
        'DataType': 0,
        'DestDataType': 0,
        'ComputeDataType': 0,
        'UseBeta': True,
        'UseScaleAB': '',
        'UseScaleAlphaVec': 0,
        'UseScaleCD': False,
        'UseBias': 0,
        'UseE': False,
        'UseGradient': False,
        'UseInitialStridesAB': False,
        'UseInitialStridesCD': False,
        'Sparse': 0,
        'ActivationType': 'none',
        'ActivationComputeDataType': 0,
        'ActivationHPA': False,
        'BiasDataTypeList': [],
        'HighPrecisionAccumulate': False,
        'StridedBatched': True,
        'GroupedGemm': False,
        'OutputAmaxD': False,
        'SwizzleTensorA': False,
        'SwizzleTensorB': False,
        'F32XdlMathOp': 0,
        'ComplexConjugateA': False,
        'ComplexConjugateB': False,
        'SupportDeviceUserArguments': False,
        'TotalIndices': 4,
        'NumIndicesC': 2,
        'IndexAssignmentsA': [0, 3],
        'IndexAssignmentsB': [3, 1],
        'IndicesBatch': [2],
        'IndicesFree': [0, 1],
        'IndicesSummation': [3],
        'NumIndicesLD': {0: 3, 1: 3, 'C': 3, 'D': 3},
        'SetConstStrideA': [],
        'SetConstStrideB': [],
    }

    problem_data_2 = problem_data_1.copy()

    print("\nCreating two ProblemTypes with identical configurations...")
    pt1 = ProblemType.FromOriginalState(problem_data_1)
    pt2 = ProblemType.FromOriginalState(problem_data_2)

    print(f"\nProblemType 1 indices:")
    for i, idx in enumerate(pt1.indices):
        print(f"  indices[{i}]: {type(idx).__name__} - id={id(idx)}")
        if hasattr(idx, 'a'):
            print(f"    .a={idx.a}, .b={getattr(idx, 'b', 'N/A')}")

    print(f"\nProblemType 2 indices:")
    for i, idx in enumerate(pt2.indices):
        print(f"  indices[{i}]: {type(idx).__name__} - id={id(idx)}")
        if hasattr(idx, 'a'):
            print(f"    .a={idx.a}, .b={getattr(idx, 'b', 'N/A')}")

    print(f"\nChecking if identical indices are interned:")
    for i in range(len(pt1.indices)):
        same_instance = pt1.indices[i] is pt2.indices[i]
        print(f"  indices[{i}]: {same_instance} (should be True)")
        assert same_instance, f"Identical indices should be interned to same instance!"

    print("\n✓ ProblemType interning test passed!")

    # Now test with different configurations
    print("\n" + "=" * 80)
    print("TEST: Different ProblemType configurations")
    print("=" * 80)

    problem_data_3 = problem_data_1.copy()
    problem_data_3['IndexAssignmentsA'] = [3, 0]  # Swapped order

    print("\nCreating ProblemType with different index assignments...")
    pt3 = ProblemType.FromOriginalState(problem_data_3)

    print(f"\nProblemType 3 indices:")
    for i, idx in enumerate(pt3.indices):
        print(f"  indices[{i}]: {type(idx).__name__} - id={id(idx)}")
        if hasattr(idx, 'a'):
            print(f"    .a={idx.a}, .b={getattr(idx, 'b', 'N/A')}")

    # Check that at least one index is different
    different_found = False
    for i in range(len(pt1.indices)):
        if pt1.indices[i] is not pt3.indices[i]:
            different_found = True
            print(f"\n  indices[{i}] is different (as expected)")
            print(f"    pt1: .a={getattr(pt1.indices[i], 'a', 'N/A')}")
            print(f"    pt3: .a={getattr(pt3.indices[i], 'a', 'N/A')}")

    assert different_found, "Different configurations should produce different index instances!"
    print("\n✓ Different configuration test passed!")


if __name__ == "__main__":
    try:
        test_interning_basic()
        test_real_problem_type()
        print("\n" + "=" * 80)
        print("ALL TESTS PASSED!")
        print("=" * 80)
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
