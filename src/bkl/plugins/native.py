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
            Property("compiler-options",
                 type=ListType(StringType()),
                 default=[],
                 inheritable=True,
                 doc="""
                     Additional compiler options common to all C-like compilers
                     (C, C++, Objective-C, Objective-C++).

                     Note that the options are compiler-specific and so this
                     property should only be set conditionally for particular
                     compilers that recognize the options.
                     """),
            Property("c-compiler-options",
                 type=ListType(StringType()),
                 default=[],
                 inheritable=True,
                 doc="""
                     Additional options for C compiler.

                     Note that the options are compiler-specific and so this
                     property should only be set conditionally for particular
                     compilers that recognize the options.
                     """),
            Property("cxx-compiler-options",
                 type=ListType(StringType()),
                 default=[],
                 inheritable=True,
                 doc="""
                     Additional options for C++ compiler.

                     Note that the options are compiler-specific and so this
                     property should only be set conditionally for particular
                     compilers that recognize the options.
                     """),
            Property("libs",
                 type=ListType(StringType()),
                 default=[],
                 inheritable=True,
                 doc="""
                     Additional libraries to link with.

                     Do not use this property to link with libraries built as
                     part of your project; use `deps` for that.

                     When this list is non-empty on a
                     :ref:`ref_target_library`, it will be used when linking
                     executables that use the library.
                     """),
            Property("archs",
                 type=ListType(EnumType("architecture", ["x86", "x86_64"])),
                 default=[], # TODO: should be toolset-specific values (?)
                 inheritable=True,
                 doc="""
                     Architectures to compile for.

                     Adds support for building binaries for specified
                     architectures, if supported by the toolset. Support may
                     take the form of either multi-arch binaries (OS X) or
                     additional build configurations (Visual Studio).

                     The default empty value means to do whatever the default
                     behavior of the toolset is.

                     Currently only supported on OS X.
                     """),
            Property("win32-crt-linkage",
                 type=EnumType("linkage", ["static", "dll"]),
                 default="dll",
                 inheritable=True,
                 doc="""
                     How to link against the C Runtime Library.

                     If ``dll`` (the default), the executable may depend on
                     some DLLs provided by the compiler. If ``static`` then a
                     static version of the CRT is linked directly into the
                     executable.
                     """),
            Property("win32-unicode",
                 type=BoolType(),
                 default=True,
                 inheritable=True,
                 doc="Compile win32 code in Unicode mode? If enabled, "
                     "``_UNICODE`` symbol is defined and the wide character "
                     "entry point (``WinMain``, ...) is used."),
            Property("outputdir",
                 type=PathType(),
                 default=PathExpr([],anchor=ANCHOR_BUILDDIR),
                 inheritable=True,
                 doc="""
                     Directory where final binaries are put.

                     Note that this is not the directory for intermediate files
                     such as object files -- these are put in ``@builddir``. By
                     default, output location is the same, ``@builddir``, but
                     can be overwritten to for example put all executables into
                     ``bin/`` subdirectory.
                     """),
        ]

    def target_file(self, toolset, target):
        """
        Returns main filename of the target.
        """
        return self._get_filename(toolset, target, self.basename_prop, self.name)

    # property with target's main name, overriden by derived classes
    basename_prop = None

    def _get_filename(self, toolset, target, propname, fileclass):
        """
        Returns expression with filename of the target using given property
        (e.g. libname, exename) for use with given toolset.
        """
        tdir = dir(toolset)
        prefix = "%s_prefix" % fileclass
        ext = "%s_extension" % fileclass
        parts = []
        if prefix in tdir:
            parts.append(getattr(toolset, prefix))
        parts.append(target[propname])
        if ext in tdir:
            parts.append("." + getattr(toolset, ext))
        outdir = target["outputdir"]
        return PathExpr(outdir.components + [concat(*parts)], outdir.anchor)

    def get_all_libs(self, toolset, target):
        """
        Returns a tuple of two lists: list of internal (aka dependencies) and
        external libraries to link with.
        Dependencies of these libs are returned as well.
        """
        visited = set()
        deplibs = []
        ldlibs = []
        self._collect_all_libs(toolset, target, visited, deplibs, ldlibs)
        return (deplibs, ldlibs)

    def _collect_all_libs(self, toolset, target, visited, deplibs, ldlibs):
        if target in visited:
            return
        visited.add(target)
        project = target.project
        deps = [project.get_target(x.as_py()) for x in target["deps"]]
        todo = [x for x in deps if
                isinstance(x.type, LibraryType) or isinstance(x.type, DllType)]
        for dep in todo:
            f = dep.type.target_file(toolset, dep)
            if f not in deplibs:
                deplibs.append(f)
        for lib in target["libs"]:
            # TODO: use some ordered-set type and just merge them
            if lib not in ldlibs:
                ldlibs.append(lib)
        for dep in todo:
            self._collect_all_libs(toolset, dep, visited, deplibs, ldlibs)


class NativeLinkedType(NativeCompiledType):
    properties = [
            Property("libdirs",
                 type=ListType(PathType()),
                 default=[],
                 inheritable=True,
                 doc="Additional directories where to look for libraries."),
            Property("link-options",
                 type=ListType(StringType()),
                 default=[],
                 inheritable=True,
                 doc="""
                     Additional linker options.

                     Note that the options are compiler/linker-specific and so this
                     property should only be set conditionally for particular
                     compilers that recognize the options.
                     """),
        ]


class ExeType(NativeLinkedType):
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
            Property("win32-subsystem",
                 type=EnumType("subsystem", ["console", "windows"]),
                 default="console",
                 inheritable=True,
                 doc="""
                     Windows subsystem the executable runs in. Must be set to
                     ``windows`` for console-less applications.
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


class DllType(NativeLinkedType):
    """
    Dynamically loaded library.
    """
    name = "dll"

    properties = [
            Property("libname",
                 type=StringType(),
                 default="$(id)",
                 inheritable=False,
                 doc="""
                     Base name of the library.

                     This is not full filename or even path, it's only its base part,
                     to which platform-specific prefix and/or extension are
                     added. By default, it's the same as target's ID, but it can be changed e.g.
                     if the filename should contain version number, which would be impractical
                     to use as target identifier in the bakefile.

                     .. code-block:: bkl

                        dll utils {
                          // use myapp_utils.lib, myapp_utils.dll, libmyapp_utils.so
                          libname = myapp_utils;
                        }
                     """),
            # TODO: add "dllname" for the name of the shared lib itself, when it differs from
            #       import library name
            # TODO: add libtool-style sonames support
        ]

    basename_prop = "libname"

    def get_build_subgraph(self, toolset, target):
        return get_compilation_subgraph(
                        toolset,
                        target,
                        ft_to=NativeDllFileType.get(),
                        outfile=self.target_file(toolset, target))
