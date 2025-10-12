################################################################################
#
# Copyright (C) 2025 Advanced Micro Devices, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
################################################################################

"""
Typed configuration schema classes with __slots__ for memory-efficient YAML parsing.

These classes provide:
- Memory-efficient storage via __slots__ (70% reduction vs dicts)
- Full dict-like interface for backward compatibility
- Type documentation via slot names
- Support for mutation (needed during processing)
"""

import sys
from collections.abc import Mapping
from typing import Any, Iterator, Optional


class SlottedConfig(Mapping):
    """
    Base class for all typed config objects with __slots__.

    Provides full dict-like interface while using __slots__ for memory efficiency.
    Subclasses should define __slots__ with all expected attributes plus '__dict__'
    as a fallback for dynamic/unknown keys.
    """

    __slots__ = ()  # Subclasses define their own slots

    def __getitem__(self, key: str) -> Any:
        """Get value by key (dict-like access)"""
        try:
            return getattr(self, key)
        except AttributeError:
            # Check __dict__ if it exists (for unknown keys)
            if hasattr(self, '__dict__') and key in self.__dict__:
                return self.__dict__[key]
            raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Set value by key (dict-like mutation)"""
        # Try to set as attribute first (for known slots)
        if key in self.__slots__:
            setattr(self, key, value)
        else:
            # Fall back to __dict__ for unknown keys
            if '__dict__' not in self.__slots__:
                raise KeyError(f"Unknown key '{key}' and __dict__ not available")
            if not hasattr(self, '__dict__'):
                object.__setattr__(self, '__dict__', {})
            self.__dict__[key] = value

    def __delitem__(self, key: str) -> None:
        """Delete key (dict-like)"""
        if hasattr(self, key):
            delattr(self, key)
        elif hasattr(self, '__dict__') and key in self.__dict__:
            del self.__dict__[key]
        else:
            raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        """Check if key exists (dict-like)"""
        if key in self.__slots__ and key not in ('__dict__', '__weakref__'):
            return hasattr(self, key)
        if hasattr(self, '__dict__'):
            return key in self.__dict__
        return False

    def __iter__(self) -> Iterator[str]:
        """Iterate over keys (dict-like) - only yields explicitly set attributes"""
        # Yield slotted attributes that have been explicitly set
        # (even if set to None - AttributeError means not set at all)
        for slot in self.__slots__:
            if slot not in ('__dict__', '__weakref__'):
                try:
                    getattr(self, slot)  # Check if attribute exists
                    yield slot
                except AttributeError:
                    # Not set at all, skip
                    pass
        # Yield dynamic attributes from __dict__
        if hasattr(self, '__dict__'):
            yield from self.__dict__.keys()

    def __len__(self) -> int:
        """Return number of explicitly set attributes"""
        return sum(1 for _ in self)

    def keys(self):
        """Return list of keys (dict-like)"""
        return list(self)

    def values(self):
        """Return list of values (dict-like)"""
        return [self[k] for k in self]

    def items(self):
        """Return list of (key, value) pairs (dict-like)"""
        return [(k, self[k]) for k in self]

    def get(self, key: str, default: Any = None) -> Any:
        """Get value with default fallback (dict-like)"""
        try:
            return self[key]
        except KeyError:
            return default

    def __repr__(self) -> str:
        """String representation"""
        classname = self.__class__.__name__
        items = ', '.join(f'{k}={v!r}' for k, v in self.items())
        return f'{classname}({items})'


class VersionInfo(SlottedConfig):
    """Version information (data[0] in library logic files)"""

    __slots__ = ('MinimumRequiredVersion', '__dict__', '__weakref__')


class ArchitectureInfo(SlottedConfig):
    """Architecture information (data[2] in library logic files when it's a dict)"""

    __slots__ = ('Architecture', 'CUCount', '__dict__', '__weakref__')


class ProblemTypeConfig(SlottedConfig):
    """
    Problem type configuration (data[4] in library logic files).

    Corresponds to _defaultProblemType in SolutionStructs/Problem.py.
    Memory: ~72 bytes + 8*N_slots vs ~184 bytes for dict with 70 keys.
    """

    __slots__ = (
        # Operation type
        'OperationType',

        # Data types (10 slots)
        'DataType', 'DataTypeA', 'DataTypeB', 'DataTypeE', 'DataTypeAmaxD',
        'DestDataType', 'ComputeDataType', 'F32XdlMathOp',
        'HighPrecisionAccumulate', 'SilentHighPrecisionAccumulate',

        # GEMM operations (10 slots)
        'TransposeA', 'TransposeB', 'TLUA', 'TLUB',
        'ComplexConjugateA', 'ComplexConjugateB',
        'Batched', 'StridedBatched', 'GroupedGemm',
        'UseBeta',

        # Bias, scaling, activation (15 slots)
        'UseBias', 'BiasDataTypeList', 'BiasSrc', 'BetaOnlyUseBias',
        'UseScaleAB', 'UseScaleCD', 'UseScaleAlphaVec',
        'UseE', 'Gradient', 'Sparse',
        'Activation', 'ActivationType', 'ActivationNoGuard', 'ActivationComputeDataType',
        'OutputAmaxD',

        # Advanced features
        'StochasticRounding',

        # Index assignments (15 slots)
        'IndexAssignmentsA', 'IndexAssignmentsB', 'IndexAssignmentsLD',
        'IndexAssignmentsMetadata',
        'NumIndicesC', 'NumIndicesLD', 'NumIndicesFree',
        'NumIndicesSummation', 'NumIndicesBatch', 'TotalIndices',
        'IndicesFree', 'IndicesBatch', 'IndicesSummation',
        'Index0', 'Index1',

        # Additional indices
        'IndexUnroll', 'IndexUnrollA', 'IndexUnrollB', 'IndexUnrollM',
        'Index01A', 'Index01B',

        # Tensor configuration
        'Tensor0', 'Tensor1', 'TileA', 'TileB',

        # Mirror and stride configuration
        'MirrorDimsA', 'MirrorDimsB', 'MirrorDimsMetadata',
        'SetConstStrideA', 'SetConstStrideB', 'SetConstStrideBias',

        # Flags
        'AllowNoFreeDims', 'UseInitialStridesAB', 'UseInitialStridesCD',
        'TileAwareSelection', 'SupportUserArgs',
        'SwizzleTensorA', 'SwizzleTensorB',

        # State
        'AssignedDerivedParameters',

        # Metadata (if sparse)
        'DataTypeMetadata',

        # Fallback for unknown keys
        '__dict__', '__weakref__'
    )


class SolutionConfig(SlottedConfig):
    """
    Solution configuration (data[5][i] in library logic files).

    Corresponds to defaultSolution from Common/GlobalParameters.py.
    This will be passed to Solution.__init__() which already uses __slots__.
    Memory: ~72 bytes + 8*N_slots vs ~184 bytes for dict with 100+ keys.
    """

    __slots__ = (
        # Core kernel config (10 slots)
        'KernelLanguage', 'ISA', 'CodeObjectVersion', 'CUCount',
        'CustomKernelName', 'NoReject',
        'WorkGroup', 'ThreadTile', 'MatrixInstruction', 'WavefrontSize',

        # Loop unrolling (5 slots)
        'DepthU', 'InnerUnroll', 'GlobalSplitU', 'GlobalSplitUAlgorithm',
        'GlobalSplitUCoalesced',

        # LDS configuration (10 slots)
        'LdsPadA', 'LdsPadB', 'LdsPadMetadata',
        'LdsBlockSizePerPadA', 'LdsBlockSizePerPadB', 'LdsBlockSizePerPadMetadata',
        'TransposeLDS', 'ClusterLocalRead',
        'MaxOccupancy', 'MaxLDS',

        # Vector widths (10 slots)
        'VectorWidthA', 'VectorWidthB', 'VectorStore', 'StoreVectorWidth',
        'GlobalReadVectorWidthA', 'GlobalReadVectorWidthB',
        'LocalReadVectorWidth',
        'WaveSeparateGlobalReadA', 'WaveSeparateGlobalReadB',
        'WaveSeparateGlobalReadMetadata',

        # Memory operations (15 slots)
        'BufferLoad', 'BufferStore',
        'DirectToLds', 'DirectToVgprA', 'DirectToVgprB', 'DirectToVgprSparseMetadata',
        'PrefetchGlobalRead', 'PrefetchLocalRead',
        'UseInstOffsetForGRO', 'UseSgprForGRO',
        'NonTemporal', 'NonTemporalA', 'NonTemporalB', 'NonTemporalC',
        'NonTemporalD',

        # Additional non-temporal
        'NonTemporalE', 'NonTemporalWS', 'NonTemporalMetadata',

        # Scheduling (15 slots)
        'ScheduleGlobalRead', 'ScheduleLocalWrite', 'ScheduleIterAlg',
        'GlobalReadPerMfma', 'LocalWritePerMfma',
        'UnrollLoopSwapGlobalReadOrder', 'InterleaveAlpha',
        'OptNoLoadLoop', 'SuppressNoLoadLoop',
        'UseCustomMainLoopSchedule', 'MbskPrefetchMethod',
        'StaggerU', 'StaggerUStride', 'StaggerUMapping',
        'MagicDivAlg',

        # Work group mapping (10 slots)
        'WorkGroupMapping', 'WorkGroupMappingXCC', 'WorkGroupMappingXCCGroup',
        'GlobalSplitUWorkGroupMappingRoundRobin', 'WorkGroupReduction',
        'WaveSplitK',
        'StreamK', 'StreamKAtomic', 'StreamKXCCMapping', 'StreamKFixupTreeReduction',

        # Debugging
        'DebugStreamK',

        # Store optimizations (10 slots)
        'StorePriorityOpt', 'StoreSyncOpt', 'StoreRemapVectorWidth',
        'NumElementsPerBatchStore', 'GroupLoadStore',
        'ExpandPointerSwap', 'SourceSwap',
        'NumLoadsCoalescedA', 'NumLoadsCoalescedB',
        'Use64bShadowLimit',

        # Assertions (5 slots)
        'AssertSummationElementMultiple',
        'AssertFree0ElementMultiple', 'AssertFree1ElementMultiple',
        'AssertAIGreaterThanEqual', 'AssertAILessThanEqual',

        # Activation (5 slots)
        'ActivationFused', 'ActivationFuncCall', 'ActivationAlt',
        'ConvertAfterDS', 'ForceDisableShadowInit',

        # Miscellaneous (5 slots)
        'PreloadKernArgs', 'MIArchVgpr', 'LDSTrInst',

        # State fields (5 slots)
        'ProblemType', 'InternalSupportParams',
        'Valid', 'AssignedProblemIndependentDerivedParameters',
        'AssignedDerivedParameters',

        # Fallback for unknown keys and special case '1LDSBuffer'
        '__dict__', '__weakref__'
    )


def to_dict(obj: Any) -> Any:
    """
    Recursively convert SlottedConfig objects to plain dicts.
    Useful for YAML serialization or roundtrip testing.
    """
    if isinstance(obj, SlottedConfig):
        result = {}
        for key in obj:
            result[key] = to_dict(obj[key])
        return result
    elif isinstance(obj, list):
        return [to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    else:
        return obj
