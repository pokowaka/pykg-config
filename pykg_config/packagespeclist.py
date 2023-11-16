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

# File: packagespeclist.py
# Author: Geoffrey Biggs
# Part of pykg-config.

"""Parses a textual list of packages with optional version constraints.

"""

__version__ = "$Revision: $"
# $Source$

import re

from pykg_config.version import Version
from pykg_config.dependency import text_to_operator, Dependency


def parse_package_spec_list(value):
    """Parses a textual list of package specs into a list of Dependency
    objects containing name, and possibly a version restriction.

    """
    result = []
    matches = re.findall(
        r"(?P<name>[^\s,!=<>]+)(,|\s*(?P<operator>[!=<>]+)\s*(?P<version>[^\s,]+))?",
        value.strip(),
        re.U,
    )

    for package in matches:
        name = package[0]
        operator = text_to_operator(package[2])
        if package[3]:
            version = Version(package[3])
        else:
            version = Version()
        result.append(Dependency(name, operator, version))
    return result


# vim: tw=79
