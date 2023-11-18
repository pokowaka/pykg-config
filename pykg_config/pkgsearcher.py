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

# File: pkgsearcher.py
# Author: Geoffrey Biggs
# Part of pykg-config.

"""Searches for a pkg-config file matching a given specification.

"""

__version__ = "$Revision: $"
# $Source$

from os.path import isdir, isfile, join, split, splitext
from os import listdir
from typing import List, Dict, Optional, Tuple
import sys
import platform

if sys.platform == "win32":
    import winreg


from pykg_config.exceptions import PykgConfigError
from pykg_config.options import Options
from pykg_config.errorprinter import ErrorPrinter
from pykg_config.package import Package
from pykg_config.substitute import UndefinedVarError

try:
    from pykg_config.install_config import pc_path
except ImportError:
    # If the install_config module is not available (which is the case when
    # running from the source instead of an installed version), use defaults
    pc_path = None

##############################################################################
# Exceptions


class PackageNotFoundError(PykgConfigError):
    """A .pc file matching the given package name could not be found.

    Attributes:
        pkgname (str): The name of the package that could not be found.
    """

    def __init__(self, pkgname):
        self.pkgname = pkgname

    def __str__(self):
        return f"No package '{self.pkgname}' found"


class NoOpenableFilesError(PackageNotFoundError):
    pass


class BadPathError(PykgConfigError):
    """A specified path is bad in some way.

    Attributes:
        path (str): The bad path.
    """

    def __init__(self, path):
        self.path = path

    def __str__(self):
        return f"Bad path: {self.path}"


class NotAFileError(BadPathError):
    pass


class NotAPCFileError(BadPathError):
    pass


##############################################################################
# PkgSearcher object


class PkgSearcher:
    def __init__(self, globals: Dict[str, List[str]]) -> None:
        """Initialize the PkgSearcher.

        Args:
            globals: A dictionary containing global variables.

        """
        # This is a dictionary of packages found in the search path. Each
        # package name is linked to a list of full paths to .pc files, in
        # order of priority. Earlier in the list is preferred over later.
        self._known_pkgs: Dict[str, List[str]] = {}
        self.globals: Dict[str, List[str]] = globals

        self._init_search_dirs()

    def search_for_package(self, dep, globals) -> "Package":
        """Search for a package matching the given dependency specification
        (name and version restriction). Raise PackageNotFoundError if no
        matching package is found.

        Returns:
            A parsed package object.

        """
        # Get a list of pc files matching the package name
        if isfile(dep.name) and splitext(dep.name)[1] == ".pc":
            # No need to search for a pc file
            ErrorPrinter().debug_print(f"Using provided pc file {dep.name}")
            pcfiles = [dep.name]
        else:
            ErrorPrinter().debug_print(f"Searching for package matching {dep}")
            pcfiles = self.search_for_pcfile(dep.name)
        ErrorPrinter().debug_print(f"Found .pc files: {str(pcfiles)}")
        if not pcfiles:
            raise PackageNotFoundError(str(dep))
        # Filter the list by those files that meet the version specification
        pkgs = []
        for pcfile in pcfiles:
            try:
                pkgs.append(Package(pcfile, globals))
            except IOError as e:
                ErrorPrinter().verbose_error(f"Failed to open '{pcfile}': {e.strerror}")
                continue
            except UndefinedVarError as e:
                raise UndefinedVarError(e.variable, pcfile)
        if not pkgs and pcfiles:
            # Raise an error indicating that all pc files we could try were
            # unopenable. This is necessary to match pkg-config's odd lack of
            # the standard "Package not found" error when a bad file is
            # encountred.
            raise NoOpenableFilesError(str(dep))
        pkgs = [pkg for pkg in pkgs if dep.meets_requirement(pkg.properties["version"])]
        ErrorPrinter().debug_print(
            f"Filtered to {[pkg.properties['name'] for pkg in pkgs]}"
        )
        if not pkgs:
            raise PackageNotFoundError(str(dep))
        return pkgs[0]

    def search_for_pcfile(self, pkgname: str) -> List[str]:
        """Search for one or more pkg-config files matching the given
        package name. If a matching pkg-config file cannot be found,
        an empty list will be returned.

        The dictionary of known packages is stored in _known_pkgs and is
        initialised by calling init_search_dirs().

        Args:
            pkgname: The name of the package.

        Returns:
            A list of paths to matching pkg-config files.

        """
        ErrorPrinter().debug_print(f"Looking for files matching {pkgname}")
        if Options().get_option("prefer_uninstalled"):
            if pkgname + "-uninstalled" in self._known_pkgs:
                # Prefer uninstalled version of a package
                ErrorPrinter().debug_print(
                    f"Using uninstalled package {self._known_pkgs[pkgname + '-uninstalled']}"
                )
                return self._known_pkgs[pkgname + "-uninstalled"]
            elif Options().get_option("uninstalled_only"):
                ErrorPrinter().debug_print("Uninstalled only, no suitable package.")
                return []
        if pkgname in self._known_pkgs:
            ErrorPrinter().debug_print(
                f"Using any package: {self._known_pkgs[pkgname]}"
            )
            return self._known_pkgs[pkgname]
        else:
            ErrorPrinter().debug_print("No suitable package found")
            return []

    def known_packages_list(self):
        """Return a list of all packages found on the system, giving a name and
        a description (from the .pc file) for each, and also a list of any
        errors encountered.

        Returns:
            A tuple containing a list of packages and a list of errors.

        """
        result = []
        errors = []
        for pkgname in self._known_pkgs:
            # Use the highest-priority version of the package
            try:
                pkg = Package(self._known_pkgs[pkgname][0])
            except IOError as e:
                ErrorPrinter().verbose_error(
                    f"Failed to open '{self._known_pkgs[pkgname][0]}': {e.strerror}"
                )
                continue
            except UndefinedVarError as e:
                errors.append(
                    f"Variable '{e}' not defined in '{self._known_pkgs[pkgname][0]}'"
                )
                continue
            result.append(
                (pkgname, pkg.properties["name"], pkg.properties["description"])
            )
        return result, errors

    def _init_search_dirs(self) -> None:
        # Append dirs in PKG_CONFIG_PATH
        if "config_path" in self.globals and self.globals["config_path"]:
            for d in self.globals["config_path"]:
                if not d or not isdir(d):
                    continue
                self._append_packages(d)
        # Append dirs in PKG_CONFIG_LIBDIR
        if "config_libdir" in self.globals and self.globals["config_libdir"]:
            for d in self.globals["config_libdir"]:
                if not d or not isdir(d):
                    continue
                self._append_packages(d)
        if sys.platform == "win32":
            key_path = "Software\\pkg-config\\PKG_CONFIG_PATH"
            for root in (
                (winreg.HKEY_CURRENT_USER, "HKEY_CURRENT_USER"),
                (winreg.HKEY_LOCAL_MACHINE, "HKEY_LOCAL_MACHINE"),
            ):
                try:
                    key = winreg.OpenKey(root[0], key_path)
                except WindowsError as e:
                    ErrorPrinter().debug_print(
                        f"Failed to add paths from {root[1]}\\{key_path}: {e}"
                    )
                    continue
                try:
                    num_subkeys, num_vals, modified = winreg.QueryInfoKey(key)
                    for ii in range(num_vals):
                        name, val, type = winreg.EnumValue(key, ii)
                        if type == winreg.REG_SZ and isdir(val):
                            self._append_packages(val)
                except WindowsError as e:
                    ErrorPrinter().debug_print(
                        f"Failed to add paths from {root[1]}\\{key_path}: {e}"
                    )
                finally:
                    winreg.CloseKey(key)
        # Default path: If a hard-coded path has been set, use that (excluding
        # paths that don't exist)
        if "prefix" in self.globals:
            prefix = self.globals["prefix"]
        else:
            prefix = sys.prefix
        if pc_path:
            for d in pc_path.split(self._split_char()):
                if d and isdir(d):
                    self._append_packages(d)
        # Default path: Else append prefix/lib/pkgconfig, prefix/share/pkgconfig
        else:
            if Options().get_option("is_64bit"):
                suffix = "64"
            else:
                suffix = ""
            dirs2check = (
                join(prefix, f"lib{suffix}"),
                join(prefix, "share"),
                join(prefix, "lib"),
            )
            for d in dirs2check:
                d = join(d, "pkgconfig")
                if isdir(d):
                    self._append_packages(d)
        for path in Options().get_option("search_paths"):
            if isdir(path):
                self._append_packages(path)

    def _append_packages(self, d: str) -> None:
        ErrorPrinter().debug_print(f"Adding .pc files from {d} to known packages")
        files = listdir(d)
        for filename in files:
            if filename.endswith(".pc"):
                # Test if the file can be opened (pkg-config glosses over,
                # e.g. links that are now dead, as if they were never there).
                full_path = join(d, filename)
                name = filename[:-3]
                if name in self._known_pkgs:
                    if full_path not in self._known_pkgs[name]:
                        self._known_pkgs[name].append(full_path)
                        ErrorPrinter().debug_print(
                            f"Package {name} has a duplicate file: {self._known_pkgs[name]}"
                        )
                else:
                    self._known_pkgs[name] = [full_path]

    def _split_char(self) -> str:
        # Get the character used to split a list of directories.
        if sys.platform == "win32":
            return ";"
        return ":"

    def _can_open_file(self, filename: str) -> bool:
        """Check if a file can be opened.

        Args:
            filename: The name of the file.

        Returns:
            A boolean indicating whether the file can be opened.

        """
        try:
            result = open(filename, "r")
        except IOError as e:
            ErrorPrinter().debug_print(f"Could not open {filename}")
            search_string = Options().get_option("search_string").split()
            if (
                not search_string and Options().get_option("command") == "list-all"
            ) or True in [
                p.startswith(split(filename)[-1].split(".")[0]) for p in search_string
            ]:
                ErrorPrinter().verbose_error(
                    f"Failed to open '{filename}': {e.strerror}"
                )
            return False
        return True


# vim: tw=79
