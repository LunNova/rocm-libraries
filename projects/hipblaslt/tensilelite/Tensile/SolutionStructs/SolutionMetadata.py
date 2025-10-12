################################################################################
#
# Copyright (C) 2022-2025 Advanced Micro Devices, Inc. All rights reserved.
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
Lightweight metadata class for solution library organization.

This class holds only the fields needed for library structure, selection logic,
and serialization. It does NOT hold the heavyweight kernel generation parameters.
"""

from typing import Dict
from Tensile.SolutionStructs.Naming import getSolutionNameMin, getKernelNameMin, getKeyNoInternalArgs


class SolutionMetadata:
    """
    Lightweight metadata for library organization.

    This class contains only the information needed for:
    - Library structure and selection logic
    - Solution naming and identification
    - Post-kernel-generation updates (CUOccupancy)
    - Serialization

    It explicitly does NOT contain the ~100+ kernel generation parameters
    from SolutionStructs.Solution.
    """

    __slots__ = (
        # Identification
        'name',              # Solution name (from getSolutionNameMin)
        'kernelName',        # Kernel name (from getKernelNameMin)
        'solutionKey',       # Solution key for deduplication (from getKeyNoInternalArgs)

        # Library organization
        'index',             # Global solution index
        'libraryLogicIndex', # Index within source logic file
        'srcName',           # Source logic file name

        # Selection predicates
        'problemType',       # ProblemType for matching
        'hardwarePredicate', # Hardware requirements
        'problemPredicate',  # Problem-specific predicates
        'taskPredicate',     # Task-specific predicates

        # Size and argument support
        'sizeMapping',       # Size mapping information
        'internalArgsSupport', # Internal arguments support

        # Performance data
        'ideals',            # Ideal problem sizes
        'linearModel',       # Performance model

        # Other metadata
        'debugKernel',       # Debug flag
    )

    @classmethod
    def fromSolution(cls, solution, splitGSU: bool):
        """
        Extract lightweight metadata from SolutionStructs.Solution.

        Args:
            solution: SolutionStructs.Solution object (heavyweight kernel config)
            splitGSU: Whether GSU splitting is enabled

        Returns:
            SolutionMetadata with extracted fields
        """
        # Local imports to avoid circular dependency
        # Contractions.py imports SolutionStructs, so we can't import Contractions at module level
        from Tensile import Contractions
        from Tensile import Hardware

        metadata = cls()

        # Extract kernel for naming
        kernel = solution.getKernels()[0]

        # Generate names and key
        metadata.name = getSolutionNameMin(kernel, splitGSU)
        metadata.kernelName = getKernelNameMin(kernel, splitGSU)
        metadata.solutionKey = getKeyNoInternalArgs(solution, False)

        # Copy basic fields
        metadata.problemType = Contractions.ProblemType.FromOriginalState(solution['ProblemType'])
        metadata.srcName = solution.srcName
        metadata.debugKernel = solution.get('DebugKernel', False)

        # Extract ISA and CUCount for hardware predicate
        isa = solution['ISA']
        cuCount = solution.get('CUCount', None)
        metadata.hardwarePredicate = Hardware.HardwarePredicate.FromHardware(isa, cuCount)

        # Construct predicates from solution data
        # Since SolutionStructs.Solution implements Mapping, we can pass it directly
        metadata.problemPredicate = Contractions.ProblemPredicate.FromOriginalState(
            solution, metadata.problemType
        )
        metadata.taskPredicate = Contractions.TaskPredicate.FromOriginalState(
            solution, metadata.problemType
        )

        # Construct size mapping and internal args support
        metadata.sizeMapping = Contractions.SizeMapping.FromOriginalState(solution)
        metadata.internalArgsSupport = Contractions.InternalArgsSupport.FromOriginalState(solution)

        # Extract library logic index from solution info
        info = {key: str(value) for key, value in solution.items() if key != 'ProblemType'}
        metadata.libraryLogicIndex = int(info.get("SolutionIndex", -1))

        # Index will be set later during library construction
        metadata.index = None

        # Performance data
        metadata.ideals = solution.get('Ideals', {})
        metadata.linearModel = solution.get('LinearModel', {})

        return metadata

    def __repr__(self):
        return f"SolutionMetadata(name={self.name}, index={self.index}, srcName={self.srcName})"
