# Copyright © Advanced Micro Devices, Inc., or its affiliates.
# SPDX-License-Identifier: MIT

import sys
import yaml
from pathlib import Path
from enum import Enum
from typing import Optional

# Import typed config classes
from .ConfigSchema import (
    SlottedConfig,
    VersionInfo,
    ArchitectureInfo,
    ProblemTypeConfig,
    SolutionConfig
)

try:
    DEFAULT_YAML_LOADER = yaml.CSafeLoader
except:
    print('CSafeLoader is not installed.')
    DEFAULT_YAML_LOADER = yaml.SafeLoader


class ParseContext(Enum):
    """Context enum for schema-aware parsing"""
    UNKNOWN = 0
    VERSION_INFO = 1
    ARCHITECTURE_INFO = 2
    PROBLEM_TYPE = 3
    SOLUTION = 4
    LIBRARY_ROOT_SEQUENCE = 5


def parse_general(loader: yaml.Loader):
    if loader.check_event(yaml.MappingStartEvent):
        return parse_mapping(loader)
    elif loader.check_event(yaml.SequenceStartEvent):
        return parse_sequence(loader)
    elif loader.check_event(yaml.ScalarEvent):
        return parse_scalar(loader)

def parse_sequence(loader: yaml.Loader):
    ret = []
    #pop sequence start event
    loader.get_event()
    while not loader.check_event(yaml.SequenceEndEvent):
        ret.append(parse_general(loader))
    #pop sequence end event
    loader.get_event()
    return ret

def parse_mapping(loader: yaml.Loader):
    ret = {}
    k, v = None, None
    #pop mapping start event
    loader.get_event()
    while not loader.check_event(yaml.MappingEndEvent):
        if k is None:
            k = parse_scalar(loader)
        elif v is None:
            v = parse_general(loader)
            ret[k] = v
            k, v = None, None

    #pop mapping end event
    loader.get_event()
    return ret

def is_float(value):
    if not value:
        return False
    first_char = value[0]
    if not (first_char in '+-.' or first_char.isdigit()):
        return False
    try:
        float(value)
        return True
    except ValueError:
        return False

def parse_scalar(loader: yaml.Loader):
    assert loader.check_event(yaml.ScalarEvent)
    evt = loader.get_event()
    value: str = evt.value

    if not value:
        if not evt.style:
            return None
        return value

    first_char = value[0]
    if first_char in '+-' or first_char.isdigit():
        stripped = value.lstrip('+-')
        if stripped.isdigit():
            return int(value)
        elif is_float(value):
            return float(value)

    value_folded = value.casefold()

    if value_folded in ('true', 'yes'):
        return True
    elif value_folded in ('false', 'no'):
        return False
    elif value_folded in ('null', '~'):
        if not evt.style:
            return None

    return sys.intern(value)


################################################################################
# Schema-aware typed parsing
################################################################################

def parse_general_typed(loader: yaml.Loader, context: ParseContext):
    """Parse YAML with schema awareness based on context"""
    if loader.check_event(yaml.MappingStartEvent):
        return parse_mapping_typed(loader, context)
    elif loader.check_event(yaml.SequenceStartEvent):
        return parse_sequence_typed(loader, context)
    elif loader.check_event(yaml.ScalarEvent):
        return parse_scalar(loader)  # Scalars don't need typing
    return None


def parse_mapping_typed(loader: yaml.Loader, context: ParseContext):
    """
    Parse YAML mapping into appropriate typed config object based on context.

    This is the key function that eliminates temp dict allocations by parsing
    directly into slotted config objects.
    """
    # Create appropriate config object based on context
    if context == ParseContext.VERSION_INFO:
        obj = VersionInfo()
    elif context == ParseContext.ARCHITECTURE_INFO:
        obj = ArchitectureInfo()
    elif context == ParseContext.PROBLEM_TYPE:
        obj = ProblemTypeConfig()
    elif context == ParseContext.SOLUTION:
        obj = SolutionConfig()
    else:
        # Fallback to dict for unknown contexts (nested structures, etc.)
        obj = {}

    k, v = None, None
    loader.get_event()  # pop mapping start event

    while not loader.check_event(yaml.MappingEndEvent):
        if k is None:
            k = parse_scalar(loader)
        elif v is None:
            # Infer context for nested values
            nested_context = infer_nested_context(k, context)
            v = parse_general_typed(loader, nested_context)
            obj[k] = v
            k, v = None, None

    loader.get_event()  # pop mapping end event
    return obj


def parse_sequence_typed(loader: yaml.Loader, context: ParseContext):
    """Parse YAML sequence with context awareness"""
    ret = []
    loader.get_event()  # pop sequence start event

    while not loader.check_event(yaml.SequenceEndEvent):
        # For solution lists, each element is a Solution
        if context == ParseContext.LIBRARY_ROOT_SEQUENCE:
            # We don't know the item context until we see its position
            # This is handled by load_library_logic_typed
            item = parse_general_typed(loader, ParseContext.UNKNOWN)
        else:
            item = parse_general_typed(loader, context)
        ret.append(item)

    loader.get_event()  # pop sequence end event
    return ret


def infer_nested_context(key: str, parent_context: ParseContext) -> ParseContext:
    """
    Infer parsing context from key name and parent context.

    This allows us to know what type of object to create for nested structures
    without needing explicit type annotations in the YAML.
    """
    # Top-level keys
    if key == "MinimumRequiredVersion":
        return ParseContext.VERSION_INFO
    elif key in ("Architecture", "CUCount"):
        return ParseContext.ARCHITECTURE_INFO
    elif key == "ProblemType":
        return ParseContext.PROBLEM_TYPE

    # Nested contexts - mostly fall back to unknown/dict
    # (most nested structures are simple values or small dicts that don't need typing)
    return ParseContext.UNKNOWN


def load_library_logic_typed(yaml_path: Path, loader_type: yaml.Loader):
    """
    Load a library logic YAML file using typed config objects.

    This is the main entry point for schema-aware parsing of library logic files.
    Returns a list matching the original format (for compatibility), but with
    typed config objects at appropriate positions.
    """
    with open(yaml_path, 'r') as f:
        loader = loader_type(f)
        assert loader.check_event(yaml.StreamStartEvent)
        loader.get_event()
        assert loader.check_event(yaml.DocumentStartEvent)
        loader.get_event()

        # Library logic files have a root sequence
        if not loader.check_event(yaml.SequenceStartEvent):
            # Might be a different format, fall back to generic parsing
            return parse_general(loader)

        loader.get_event()  # pop sequence start event
        items = []

        while not loader.check_event(yaml.SequenceEndEvent):
            idx = len(items)

            # Determine context based on position in library logic structure
            if idx == 0:
                # data[0]: {MinimumRequiredVersion: ...}
                context = ParseContext.VERSION_INFO
            elif idx == 2:
                # data[2]: {Architecture: ..., CUCount: ...} or string
                # Peek to see if it's a mapping
                if loader.check_event(yaml.MappingStartEvent):
                    context = ParseContext.ARCHITECTURE_INFO
                else:
                    context = ParseContext.UNKNOWN
            elif idx == 4:
                # data[4]: ProblemType configuration (large dict)
                context = ParseContext.PROBLEM_TYPE
            elif idx == 5:
                # data[5]: Solutions list - each element is a Solution
                # Parse the sequence of solutions
                if loader.check_event(yaml.SequenceStartEvent):
                    solutions = []
                    loader.get_event()  # pop sequence start
                    while not loader.check_event(yaml.SequenceEndEvent):
                        sol = parse_mapping_typed(loader, ParseContext.SOLUTION)
                        solutions.append(sol)
                    loader.get_event()  # pop sequence end
                    items.append(solutions)
                    continue  # Skip the normal parse path
                else:
                    context = ParseContext.UNKNOWN
            else:
                # Other positions: scalars, lists, or small dicts - use generic parsing
                context = ParseContext.UNKNOWN

            obj = parse_general_typed(loader, context)
            items.append(obj)

        loader.get_event()  # pop sequence end event
        assert loader.check_event(yaml.DocumentEndEvent)
        loader.get_event()
        assert loader.check_event(yaml.StreamEndEvent)

        return items


################################################################################
# Original generic parsing functions (kept for compatibility)
################################################################################

def load_yaml_stream(yaml_path: Path, loader_type: yaml.Loader):
    with open(yaml_path, 'r') as f:
        loader = loader_type(f)
        assert loader.check_event(yaml.StreamStartEvent)
        loader.get_event()
        assert loader.check_event(yaml.DocumentStartEvent)
        loader.get_event()
        logic = parse_general(loader)
        assert loader.check_event(yaml.DocumentEndEvent)
        loader.get_event()
        assert loader.check_event(yaml.StreamEndEvent)
        return logic

def load_yaml_sequence_item(yaml_path: Path, loader_type: yaml.Loader, idx: int):
    with open(yaml_path, 'r') as f:
        loader = loader_type(f)
        assert loader.check_event(yaml.StreamStartEvent)
        loader.get_event()
        assert loader.check_event(yaml.DocumentStartEvent)
        loader.get_event()

        # assume the root element is a sequence
        if not loader.check_event(yaml.SequenceStartEvent):
            raise RuntimeError('Root of YAML is not a sequence')

        loader.get_event()
        cur_idx = 0
        ret = None

        while not loader.check_event(yaml.SequenceEndEvent):
            obj = parse_general(loader)

            if cur_idx == idx:
                ret = obj
                break

            cur_idx += 1

        return ret

def load_yaml_dict_item(yaml_path: Path, loader_type: yaml.Loader, key: str):
    with open(yaml_path, 'r') as f:
        loader = loader_type(f)
        assert loader.check_event(yaml.StreamStartEvent)
        loader.get_event()
        assert loader.check_event(yaml.DocumentStartEvent)
        loader.get_event()

        # assume the root element is a map
        if not loader.check_event(yaml.MappingStartEvent):
            raise RuntimeError('Root of YAML is not a map')

        loader.get_event()
        k, v = None, None

        while not loader.check_event(yaml.MappingEndEvent):
            if k is None:
                k = parse_scalar(loader)
            else:
                value = parse_general(loader)

                if k == key:
                    v = value
                    break
                k = None

        return v

def load_logic_gfx_arch(yaml_path: Path, loader_type: yaml.Loader = DEFAULT_YAML_LOADER):
    try:
        GFX_ARCH_IDX = 2
        arch = load_yaml_sequence_item(yaml_path, loader_type, GFX_ARCH_IDX)

        if isinstance(arch, dict):
            return arch['Architecture']
        else:
            return arch
    except RuntimeError as e:
        return load_yaml_dict_item(yaml_path, loader_type, 'ArchitectureName')
