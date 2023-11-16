# Copyright (c) 2009-2012, Geoffrey Biggs
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the Geoffrey Biggs nor the names of its
#      contributors may be used to endorse or promote products derived from
#      this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# File: pcfile.py
# Author: Geoffrey Biggs
# Part of pykg-config.

"""Parse pkg-config files.

Contains functions that read and parse metadata files in the format
used by pkg-config.

"""

__version__ = "$Revision: $"
# $Source$

import re
from typing import Any, Dict, List, Optional, Tuple, Union

from pykg_config.errorprinter import ErrorPrinter
from pykg_config.exceptions import ParseError
from pykg_config.props import empty_raw_props
from pykg_config.substitute import substitute

# Constants
VARIABLE = 0
PROPERTY = 1
empty_vars = {}

##############################################################################
# Exceptions


class EmptyPackageFileError(ParseError):
    """The given pkg-config file had no lines in it."""


class MalformedLineError(ParseError):
    """The line is not a correctly-formatted variable or a property.

    Attributes:
        line -- The incorrectly-formatted line.

    """

    def __init__(self, line):
        self.line = line

    def __str__(self):
        return self.line


class MultiplyDefinedValueError(ParseError):
    """A value has been defined more than once.

    Attributes:
        line -- The line containing the duplicate value.

    """

    def __init__(self, line):
        self.line = line

    def __str__(self):
        return self.line


class TrailingContinuationCharError(ParseError):
    """The last line in a file has a trailing continuation character.

    Attributes:
        line -- The line containing the trailing character.

    """

    def __init__(self, line):
        self.line = line

    def __str__(self):
        return self.line


##############################################################################
# Public functions


def read_pc_file(
    filename: str, global_variables: Dict[str, str]
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    """
    Read and parse a pkg-config file.

    Args:
        filename (str): The path to the pkg-config file.
        global_variables (Dict[str, str]): Global variables.

    Returns:
        Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]: A tuple containing raw variables, variables, and properties.
    """
    ErrorPrinter().set_variable("filename", filename)
    ErrorPrinter().debug_print(f"Parsing {filename}")

    with open(filename, "r", encoding="utf-8") as pcfile:
        lines = pcfile.readlines()

    if not lines:
        raise EmptyPackageFileError(filename)

    return parse_pc_file_lines(lines, global_variables)


##############################################################################
# Private functions

def parse_pc_file_lines(
    lines: List[str], globals: Dict[str, Any]
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, Any]]:
    """
    Parse all lines from a pkg-config file, building vars and props dictionaries.

    Args:
        lines (List[str]): List of lines from the pkg-config file.
        globals (Dict[str, Any]): Global variables.

    Returns:
        Tuple[Dict[str, str], Dict[str, str], Dict[str, Any]]: Tuple containing raw_vars, vars, and props dictionaries.
    """
    raw_vars = {}
    vars = {}
    props = empty_raw_props.copy()
    seen_props = []

    for line in merge_lines(lines, "\\"):
        raw_vars, vars, props, seen_props = parse_line(
            strip_comments(line).strip(), raw_vars, vars, props, seen_props, globals
        )

    return raw_vars, vars, props


def merge_lines(lines: List[str], cont_char: str) -> List[str]:
    """
    Merge any lines ending with the given character with the following line.
    Return a list of lines. Raises TrailingContinuationCharError if the
    final line has the continuation character.

    Args:
        lines (List[str]): List of lines to merge.
        cont_char (str): Continuation character.

    Returns:
        List[str]: Merged lines.

    Raises:
        TrailingContinuationCharError: If the final line has the continuation character.
    """
    if lines[-1][-1] == cont_char:
        raise TrailingContinuationCharError(lines[-1])

    result = []
    ii = 0
    while ii < len(lines):
        new_line = lines[ii].rstrip()
        if new_line == "":
            ii += 1
            continue

        while new_line[-1] == cont_char:
            # Drop the \n and the continuation char
            new_line = new_line[:-2] + " "
            ii += 1
            new_line += lines[ii].rstrip()

        result.append(new_line)
        ii += 1

    return result


def parse_line(
    line: str,
    raw_vars: Dict[str, str],
    vars: Dict[str, str],
    props: Dict[str, Union[str, None]],
    seen_props: List[str],
    globals: Dict[str, str],
) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, Union[str, None]], List[str]]:
    """
    Parse a single line from the file, adding its value to the props or vars dictionary as appropriate.

    Args:
        line (str): The input line.
        raw_vars (Dict[str, str]): Dictionary to store raw variables.
        vars (Dict[str, str]): Dictionary to store substituted variables.
        props (Dict[str, Union[str, None]]): Dictionary to store properties.
        seen_props (List[str]): List to keep track of seen properties.
        globals (Dict[str, str]): Dictionary of global variables.

    Returns:
        Tuple[Dict[str, str], Dict[str, str], Dict[str, Union[str, None]], List[str]]:
        Updated raw_vars, vars, props, and seen_props.
    """
    if not line:
        return raw_vars, vars, props, seen_props

    key, value, type = split_pc_file_line(line)

    # Check first if it's one of the known keys.
    if type == VARIABLE:
        # Perform substitution using variables found so far and global variables, then store the result.
        if key in vars:
            raise MultiplyDefinedValueError(key)
        if key in globals:
            ErrorPrinter().debug_print(
                "Adding %s -> %s to vars from globals", (key, value)
            )
            raw_vars[key] = value.strip()
            vars[key] = substitute(globals[key], vars, globals)
        else:
            ErrorPrinter().debug_print("Adding %s -> %s to vars", (key, value))
            raw_vars[key] = value.strip()
            vars[key] = substitute(value.strip(), vars, globals)

    elif type == PROPERTY:
        if key in seen_props:
            raise MultiplyDefinedValueError(key)
        if key.lower() in empty_raw_props:
            if value is None:
                value = empty_raw_props[key.lower()]
            ErrorPrinter().debug_print("Adding %s -> %s to props", (key, value))
            props[key.lower()] = value
            seen_props.append(key)
        else:
            # As per the original pkg-config, don't raise errors on unknown
            # keys because they may be from future additions to the file
            # format. But log an error
            ErrorPrinter().debug_print(
                "Unknown key/value in %(filename)s:\n%s: %s", (key, value)
            )

    else:
        # Probably a malformed line. Ignore it.
        pass

    return raw_vars, vars, props, seen_props


def strip_comments(line: str) -> str:
    """
    Strip comments from a line, returning the uncommented part or a blank
    string if the whole line was a comment.

    Args:
        line (str): The input line.

    Returns:
        str: The uncommented part of the line.
    """
    comment_start = line.find("#")
    if comment_start == -1:
        return line
    else:
        return line[:comment_start]


property_re = re.compile(r"(?P<key>[\w.]+):\s*(?P<value>.+)?", re.U)
variable_re = re.compile(r"(?P<var>[\w.]+)=\s*(?P<value>.+)?", re.U)


def split_pc_file_line(line: str) -> Optional[Tuple[str, str, str]]:
    """
    Split a line into key and value and determine if it is a property or a variable.

    Args:
        line (str): The input line.

    Returns:
        Optional[Tuple[str, str, str]]: A tuple containing key, value, and type (PROPERTY or VARIABLE).
    """
    m = property_re.match(line)
    if m is not None:
        return m.group("key"), m.group("value") or "", PROPERTY

    m = variable_re.match(line)
    if m is not None:
        return m.group("var"), m.group("value") or "", VARIABLE

    # Gloss over malformed lines (that's what pkg-config does).
    ErrorPrinter().debug_print(f"Malformed line: {line}")
    return None, None, None


# vim: tw=79
