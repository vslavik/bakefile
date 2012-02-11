#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2009-2012 Vaclav Slavik
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to
#  deal in the Software without restriction, including without limitation the
#  rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
#  sell copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
#  IN THE SOFTWARE.
#

"""
Targets for natively built binaries (executables, static and shared libraries).
"""

from bkl.api import TargetType, Property, FileType
from bkl.vartypes import *
from bkl.compilers import *
from bkl.expr import concat, PathExpr, ANCHOR_BUILDDIR

class NativeCompiledType(TargetType):
    """Base class for natively-compiled targets."""
    properties = [
            Property("sources",
                 type=ListType(PathType()),
                 default=[],
                 inheritable=False,
                 doc="Source files."),
            Property("headers",
                 type=ListType(PathType()),
                 default=[],
                 inheritable=False,
                 doc="Header files."),
            Property("defines",
                 type=ListType(StringType()),
                 default=[],
                 inheritable=True,
                 doc="List of preprocessor macros to define."),
            Property("includedirs",
                 type=ListType(PathType()),
                 default=[],
                 inheritable=True,
                 doc="Directories where to look for header files."),
            Property("cppflags",
                 type=ListType(StringType()),
                 default=[],
                 inheritable=True,
                 doc="""
                     Additional preprocessor flags. Wherever possible,
                     ``defines`` or ``includedirs`` properties should be used
                     instead. *Compiler* flags should be put in ``cflags`` or
                     ``cxxflags`` properties, don't confuse this property with
                     ``cxxflags``.

                     Note that the flags are compiler-specific and so this
                     property should only be set conditionally for particular
                     compilers that recognize the flags.
                     """),
            Property("cflags",
                 type=ListType(StringType()),
                 default=[],
                 inheritable=True,
                 doc="""
                     Additional flags for C compiler.

                     Note that the flags are compiler-specific and so this
                     property should only be set conditionally for particular
                     compilers that recognize the flags.
                     """),
            Property("cxxflags",
                 type=ListType(StringType()),
                 default=[],
                 inheritable=True,
                 doc="""
                     Additional flags for C++ compiler.

                     Note that the flags are compiler-specific and so this
                     property should only be set conditionally for particular
                     compilers that recognize the flags.
                     """),
            Property("win32-unicode",
                 type=BoolType(),
                 default=True,
                 inheritable=True,
                 doc="Compile win32 code in Unicode mode? If enabled, "
                     "``_UNICODE`` symbol is defined and the wide character "
                     "entry point (``WinMain``, ...) is used."),
        ]

    def target_file(self, toolset, target):
        """
        Returns main filename of the target.
        """
        return self._get_filename(toolset, target, self.basename_prop)

    # property with target's main name, overriden by derived classes
    basename_prop = None

    def _get_filename(self, toolset, target, propname):
        """
        Returns expression with filename of the target using given property
        (e.g. libname, exename) for use with given toolset.
        """
        tdir = dir(toolset)
        prefix = "%s_prefix" % propname
        ext = "%s_extension" % propname
        parts = []
        if prefix in tdir:
            parts.append(getattr(toolset, prefix))
        parts.append(target[propname])
        if ext in tdir:
            parts.append("." + getattr(toolset, ext))
        return PathExpr([concat(*parts)], ANCHOR_BUILDDIR)


class ExeType(NativeCompiledType):
    """
    Executable program.
    """
    name = "exe"

    properties = [
            Property("exename",
                 type=StringType(),
                 default="$(id)",
                 inheritable=False,
                 doc="""
                     Base name of the executable.

                     This is not full filename or even path, it's only its base part,
                     to which platform-specific extension is
                     added. By default, it's the same as target's ID, but it can be changed e.g.
                     if the filename should contain version number, which would be impractical
                     to use as target identifier in the bakefile.

                     .. code-block:: bkl

                        exe mytool {
                          // use mytool2.exe or /usr/bin/mytool2
                          exename = $(id)$(vermajor);
                        }
                     """),
            Property("ldflags",
                 type=ListType(StringType()),
                 default=[],
                 inheritable=True,
                 doc="""
                     Additional linker flags.

                     Note that the flags are compiler/linker-specific and so this
                     property should only be set conditionally for particular
                     compilers that recognize the flags.
                     """),
        ]

    basename_prop = "exename"

    def get_build_subgraph(self, toolset, target):
        return get_compilation_subgraph(
                        toolset,
                        target,
                        ft_to=NativeExeFileType.get(),
                        outfile=self.target_file(toolset, target))


class LibraryType(NativeCompiledType):
    """
    Static library.
    """
    name = "library"

    properties = [
            Property("libname",
                 type=StringType(),
                 default="$(id)",
                 inheritable=False,
                 doc="""
                     Library name.

                     This is not full filename or even path, it's only its base part,
                     to which platform-specific prefix (if applicable) and extension are
                     added. By default, it's the same as target's ID, but it can be changed e.g.
                     if the filename should contain version number, which would be impractical
                     to use as target identifier in the bakefile.

                     .. code-block:: bkl

                        library foo {
                          // use e.g. libfoo24.a on Unix and foo24.lib
                          libname = foo$(vermajor)$(verminor);
                        }
                     """),
        ]

    basename_prop = "libname"

    def get_build_subgraph(self, toolset, target):
        return get_compilation_subgraph(
                        toolset,
                        target,
                        ft_to=NativeLibFileType.get(),
                        outfile=self.target_file(toolset, target))
