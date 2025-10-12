#!/usr/bin/env python3
"""
Test if pickle preserves object identity and deduplicates shared instances.
"""

import pickle
import sys


class SimpleObject:
    """A simple object for testing."""
    def __init__(self, data):
        self.data = data
        self.large_list = list(range(1000))  # Some bulk to measure


def test_pickle_identity():
    """Test if pickle deduplicates shared object instances."""

    # Test 1: Same object instance referenced multiple times
    print("=" * 80)
    print("TEST 1: Same object instance referenced multiple times")
    print("=" * 80)

    shared_obj = SimpleObject("shared")
    container1 = [shared_obj, shared_obj, shared_obj]  # 3 references to same object

    pickled1 = pickle.dumps(container1)
    print(f"Pickled size with shared instance: {len(pickled1):,} bytes")
    print(f"Object IDs before pickle: {[id(obj) for obj in container1]}")

    unpickled1 = pickle.loads(pickled1)
    print(f"Object IDs after unpickle: {[id(obj) for obj in unpickled1]}")
    print(f"Are they the same instance? {unpickled1[0] is unpickled1[1] is unpickled1[2]}")

    # Test 2: Different object instances with identical content
    print("\n" + "=" * 80)
    print("TEST 2: Different object instances with identical content")
    print("=" * 80)

    obj1 = SimpleObject("duplicate")
    obj2 = SimpleObject("duplicate")
    obj3 = SimpleObject("duplicate")
    container2 = [obj1, obj2, obj3]  # 3 different objects with same content

    pickled2 = pickle.dumps(container2)
    print(f"Pickled size with separate instances: {len(pickled2):,} bytes")
    print(f"Object IDs before pickle: {[id(obj) for obj in container2]}")

    unpickled2 = pickle.loads(pickled2)
    print(f"Object IDs after unpickle: {[id(obj) for obj in unpickled2]}")
    print(f"Are they the same instance? {unpickled2[0] is unpickled2[1] is unpickled2[2]}")

    # Compare sizes
    print("\n" + "=" * 80)
    print("SIZE COMPARISON")
    print("=" * 80)
    print(f"Shared instance:   {len(pickled1):>8,} bytes")
    print(f"Separate instances: {len(pickled2):>8,} bytes")
    ratio = len(pickled2) / len(pickled1)
    print(f"Separate/Shared ratio: {ratio:.2f}x")

    # Test 3: Large-scale test
    print("\n" + "=" * 80)
    print("TEST 3: Large-scale test (1000 references)")
    print("=" * 80)

    shared_large = SimpleObject("large")
    container_shared = [shared_large] * 1000
    pickled_shared = pickle.dumps(container_shared)
    print(f"1000 references to 1 shared instance: {len(pickled_shared):>10,} bytes")

    container_separate = [SimpleObject("large") for _ in range(1000)]
    pickled_separate = pickle.dumps(container_separate)
    print(f"1000 separate identical instances:    {len(pickled_separate):>10,} bytes")

    ratio_large = len(pickled_separate) / len(pickled_shared)
    print(f"Separate/Shared ratio: {ratio_large:.2f}x")

    savings = len(pickled_separate) - len(pickled_shared)
    print(f"Potential savings: {savings:>10,} bytes ({100*(1-1/ratio_large):.1f}%)")


def test_interning_pattern():
    """Test an interning pattern that could work with pickle."""

    print("\n" + "=" * 80)
    print("TEST 4: Object interning pattern")
    print("=" * 80)

    class InternedObject:
        """Object that uses interning pattern."""
        _instances = {}

        def __new__(cls, key):
            if key not in cls._instances:
                instance = super().__new__(cls)
                instance.key = key
                instance.data = list(range(1000))
                cls._instances[key] = instance
            return cls._instances[key]

        def __reduce__(self):
            # Return constructor and args for unpickling
            return (self.__class__, (self.key,))

    # Create instances - same key returns same object
    obj1 = InternedObject("A")
    obj2 = InternedObject("A")
    obj3 = InternedObject("B")

    print(f"obj1 is obj2: {obj1 is obj2} (same key)")
    print(f"obj1 is obj3: {obj1 is obj3} (different key)")

    # Pickle and unpickle
    container = [obj1, obj2, obj3]
    pickled = pickle.dumps(container)
    print(f"Pickled size: {len(pickled):,} bytes")

    # Clear instances to simulate fresh unpickle
    InternedObject._instances.clear()

    unpickled = pickle.loads(pickled)
    print(f"After unpickle:")
    print(f"  unpickled[0] is unpickled[1]: {unpickled[0] is unpickled[1]}")
    print(f"  unpickled[0] is unpickled[2]: {unpickled[0] is unpickled[2]}")


if __name__ == "__main__":
    test_pickle_identity()
    test_interning_pattern()
