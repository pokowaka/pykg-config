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

# File: dependency.py
# Author: Geoffrey Biggs
# Part of pykg-config.

"""Dependency object.

This object is used to store other packages that are depended on by a
package, both positive (need) and negative (conflict).

"""

__version__ = "$Revision: $"
# $Source$

from pykg_config.operators import *
from pykg_config.version import Version

##############################################################################
# Dependency class


class Dependency:
    def __init__(self, name: str, operator: str, version: Version) -> None:
        self.name = name
        self.operator = operator
        self.version = version

    def __eq__(self, other: "Dependency") -> bool:
        return (
            self.name == other.name
            and self.operator == other.operator
            and self.version == other.version
        )

    def __ne__(self, other: "Dependency") -> bool:
        return (
            self.name != other.name
            or self.operator != other.operator
            or self.version != other.version
        )

    def __str__(self) -> str:
        if self.version.is_empty():
            return self.name
        return f"{self.name}{operator_to_text(self.operator)}{self.version}"

    def meets_requirement(self, other_version: Version) -> bool:
        if self.operator == ALWAYS_MATCH:
            return True
        elif self.operator == LESS_THAN:
            return other_version < self.version
        elif self.operator == LESS_THAN_EQUAL:
            return other_version <= self.version
        elif self.operator == EQUAL:
            return other_version == self.version
        elif self.operator == NOT_EQUAL:
            return other_version != self.version
        elif self.operator == GREATER_THAN_EQUAL:
            return other_version >= self.version
        elif self.operator == GREATER_THAN:
            return other_version > self.version
        return False


# vim: tw=79
