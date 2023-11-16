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

# File: pkgconfig.py
# Author: KOLANICH
# Part of pykg-config.

"""Used to extract some required info (such as compiled-in paths) from real pkg-config installed in a system.
"""

__version__ = "$Revision: $"
# $Source$

import os
import subprocess
import sys
from shutil import which
from typing import Dict, List, Optional, Tuple

pykg_config_package_name: str = "pykg_config"
defaultImplsList: List[str] = ["pkgconf", "pkg-config"]


def discover_pkg_config_impl(
    path: Optional[str] = None, impls: Optional[List[str]] = None
) -> str:
    """
    Discover the installed pkg-config implementation.

    Args:
        path (Optional[str]): Optional path to search for pkg-config implementations.
        impls (Optional[List[str]]): Optional list of pkg-config implementation names.

    Returns:
        str: The path to the discovered pkg-config implementation.

    Raises:
        FileNotFoundError: If no pkg-config implementation is found.
    """
    if impls is None:
        impls = defaultImplsList

    for impl in impls:
        res = which(impl, path=path)
        if res:
            return res
    raise FileNotFoundError("No pkg-config impl is installed in your system")


discovered_pkg_config_command: Optional[str] = None


def _get_pkg_config_impl() -> str:
    """
    Get the path to the pkg-config implementation.

    Returns:
        str: The path to the pkg-config implementation.
    """
    global discovered_pkg_config_command
    if discovered_pkg_config_command is None:
        discovered_pkg_config_command = discover_pkg_config_impl()
    return discovered_pkg_config_command


class Env:
    """
    A context manager for modifying environment variables.

    Attributes:
        patch (Dict[str, str]): Dictionary of environment variable modifications.
        backup (Optional[Dict[str, str]]): Backup of the original environment variables.

    Usage:
    ```
    with Env(VAR1="value1", VAR2="value2"):
        # Code block with modified environment variables
    # Original environment variables are restored outside the block.
    ```
    """
    __slots__ = ("patch", "backup")

    def __init__(self, **kwargs: str):
        self.patch: Dict[str, str] = kwargs
        self.backup: Optional[Dict[str, str]] = None

    def __enter__(self) -> "Env":
        self.backup = os.environ.copy()
        os.environ.update(self.patch)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        os.environ = self.backup


def _call_process(args: List[str]) -> Tuple[str, str, int]:
    """
    Call a subprocess and capture its output.

    Args:
        args (List[str]): List of command-line arguments.

    Returns:
        Tuple[str, str, int]: Tuple containing stdout, stderr, and return code.
    """
    process = subprocess.run(args, capture_output=True, text=True, check=False)
    return process.stdout.strip(), process.stderr.strip(), process.returncode


def call_process(args: List[str], **env: str) -> Tuple[str, str, int]:
    """
    Call a process with optional environment variable modifications.

    Args:
        args (List[str]): List of command-line arguments.
        **env (str): Keyword arguments for environment variable modifications.

    Returns:
        Tuple[str, str, int]: Tuple containing stdout, stderr, and return code.
    """
    if env:
        with Env(**env):
            return _call_process(args)
    else:
        return _call_process(args)


def call_pkgconfig(*args: str, **env: str) -> Tuple[str, str, int]:
    """
    Call pkg-config with optional environment variable modifications.

    Args:
        *args (str): Variable length arguments for pkg-config.
        **env (str): Keyword arguments for environment variable modifications.

    Returns:
        Tuple[str, str, int]: Tuple containing stdout, stderr, and return code.
    """
    return call_process([_get_pkg_config_impl()] + list(args), **env)


def call_pykgconfig(*args: str, **env: str) -> Tuple[str, str, int]:
    """
    Call pykg-config with optional environment variable modifications.

    Args:
        *args (str): Variable length arguments for pykg-config.
        **env (str): Keyword arguments for environment variable modifications.

    Returns:
        Tuple[str, str, int]: Tuple containing stdout, stderr, and return code.
    """
    return call_process(
        [sys.executable, "-m", pykg_config_package_name] + list(args), **env
    )


def call_pkgconfig_get_lines(*args: str, **env: str) -> List[str]:
    """
    Call pkg-config and get the output lines as a list.

    Args:
        *args (str): Variable length arguments for pkg-config.
        **env (str): Keyword arguments for environment variable modifications.

    Returns:
        List[str]: List of output lines.
    """
    return call_pkgconfig(*args, **env)[0].splitlines()


def get_default_pc_vars_names() -> List[str]:
    """
    Get the default pkg-config variable names.

    Returns:
        List[str]: List of default pkg-config variable names.
    """
    return call_pkgconfig_get_lines("--print-variables", "pkg-config")


def get_default_pc_vars_kv_pairs(*var_names: str) -> Dict[str, Optional[str]]:
    """
    Get key-value pairs for default pkg-config variables.

    Args:
        *var_names (str): Variable length arguments for specific variable names.

    Returns:
        Dict[str, Optional[str]]: Dictionary containing key-value pairs for default pkg-config variables.
    """
    if not var_names:
        var_names = get_default_pc_vars_names()

    for var_name in var_names:
        res = call_pkgconfig_get_lines("--variable", var_name, "pkg-config")[0]
        if res:
            yield var_name, res
        else:
            yield var_name, None


def get_default_pc_vars_dict(*var_names: str) -> Dict[str, Optional[str]]:
    """
    Get a dictionary of default pkg-config variables.

    Args:
        *var_names (str): Variable length arguments for specific variable names.

    Returns:
        Dict[str, Optional[str]]: Dictionary containing default pkg-config variables and their values.
    """
    return dict(get_default_pc_vars_kv_pairs(*var_names))


# vim: tw=79
