#
#  This file is part of Bakefile (http://bakefile.org)
#
#  Copyright (C) 2009-2013 Vaclav Slavik
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

from bkl.api import TargetType, Property
from bkl.model import ConfigurationProxy
from bkl.vartypes import *
from bkl.compilers import *
from bkl.expr import concat, PathExpr, LiteralExpr, NullExpr, ANCHOR_BUILDDIR
from bkl.error import NonConstError, error_context
from bkl.utils import memoized

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
            Property("warnings",
                 type=EnumType("warnings", ["no", "minimal", "default", "all", "max"]),
                 default="default",
                 inheritable=True,
                 doc="""
                     Warning level for the compiler.

                     Use ``no`` to completely disable warning, ``minimal`` to
                     show only the most important warning messages, ``all``
                     to enable all warnings that usually don't result in false
                     positives and ``max`` to enable absolutely all warnings.
                     """),
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
            Property("libdirs",
                 type=ListType(PathType()),
                 default=[],
                 inheritable=True,
                 doc="""
                     Additional directories where to look for libraries.

                     When this list is non-empty on a
                     :ref:`ref_target_library`, it will be used when linking
                     executables that use the library.
                     """),
            Property("link-options",
                 type=ListType(StringType()),
                 default=[],
                 inheritable=True,
                 doc="""
                     Additional linker options.

                     Note that the options are compiler/linker-specific and so this
                     property should only be set conditionally for particular
                     compilers that recognize the options.

                     When this list is non-empty on a
                     :ref:`ref_target_library`, it will be used when linking
                     executables that use the library.
                     """),
            Property("archs",
                 type=ListType(EnumType("architecture", ["arm64", "x86", "x86_64"])),
                 default=NullExpr(),
                 inheritable=True,
                 doc="""
                     Architectures to compile for.

                     Adds support for building binaries for specified
                     architectures, if supported by the toolset. Support may
                     take the form of either multi-arch binaries (OS X) or
                     additional build configurations (Visual Studio).

                     The default empty value means to do whatever the default
                     behavior of the toolset is.

                     Currently only supported on OS X and in Visual Studio.
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
            Property("pic",
                 type=BoolType(),
                 default=lambda target: target.type.use_pic_by_default,
                 inheritable=True,
                 doc="""
                     Compile position-independent code.

                     By default, libraries (both shared and static, because the
                     latter could be linked into a shared lib too) are linked
                     with -fPIC and executables are not.
                     """),
            Property("allow-undefined",
                 type=BoolType(),
                 default=False,
                 inheritable=True,
                 doc="""
                     Allow undefined symbols when linking.

                     By default, all symbols must be defined when linking the
                     target (even if it is a shared library, for which
                     undefined symbols are traditionally allowed by default
                     under Unix), however loadable modules may need to contain
                     references to symbols in the program loading them that
                     can't be resolved at the link time and for them this
                     property may need to be set to ``false``.

                     Note that currently this property is only supported by
                     "gnu" toolset and is silently ignored by all the others.
                     """),
            Property("multithreading",
                 type=BoolType(),
                 default=True,
                 inheritable=True,
                 doc="""
                     Enable support for multithreading.

                     MT support is enabled by default, but can be disabled when
                     not needed.

                     On Unix, this option causes the use of pthreads library.
                     Visual Studio always uses MT-safe CRT, even if this
                     setting is disabled.
                     """),
        ]

    use_pic_by_default = True

    def target_file(self, toolset, target):
        """
        Returns main filename of the target.
        """
        return self._get_filename(toolset, target, "basename", self.name)

    def _get_filename(self, toolset, target, propname, fileclass):
        """
        Returns expression with filename of the target using given property
        (typically, "basename") for use with given toolset.
        """
        fileclass = fileclass.replace("-", "_")
        tdir = dir(toolset)
        prefix = "%s_prefix" % fileclass
        ext = "%s_extension" % fileclass
        parts = []
        if prefix in tdir:
            # This is normally used to prepend "lib" prefix automatically, but
            # we want to avoid doing this if the target name already starts
            # with "lib" as having "liblib" in the name is clearly undesirable
            # and working around this in application bakefiles is not simple
            # as it requires using platform-specific checks (assuming we do
            # want to have just the "lib" prefix under non-Unix platforms), so
            # do it here.
            prefix_value = getattr(toolset, prefix)
            if prefix_value and not target[propname].as_py().startswith(prefix_value):
                parts.append(prefix_value)
        parts.append(target[propname])
        if not target.is_variable_null("extension"):
            parts.append(target["extension"])
        elif ext in tdir:
            parts.append("." + getattr(toolset, ext))
        outdir = target["outputdir"]
        return PathExpr(outdir.components + [concat(*parts)], outdir.anchor, outdir.anchor_file)

    def target_file_extension(self, toolset, target):
        """
        Returns expression with extension of the target's filename (as returned
        by :meth:`target_file()`), including the leading dot.
        """
        if not target.is_variable_null("extension"):
            return target["extension"]
        else:
            try:
                fileclass = self.name.replace("-", "_")
                ext = "%s_extension" % fileclass
                return LiteralExpr(".%s" % getattr(toolset, ext))
            except AttributeError:
                return  NullExpr()


class NativeLinkedType(NativeCompiledType):
    """Base class for natively-linked targets."""

    def get_libfiles(self, toolset, target):
        """
        Returns list of internal libs (aka dependencies) to link with, as filenames.
        """
        deps = self.get_linkable_deps(target)
        return [dep.type.target_file(toolset, dep) for dep in deps]

    def get_ldlibs(self, target):
        """
        Returns list of external libs to link with.
        """
        return self._get_link_property(target, "libs")

    def get_libdirs(self, target):
        """
        Returns list of library search paths to use when linking.
        """
        return self._get_link_property(target, "libdirs")

    def get_link_options(self, target):
        """
        Returns list of linker options to use when linking.
        """
        return self._get_link_property(target, "link-options")

    def _get_link_property(self, target, propname):
        deps = self.get_linkable_deps(target)
        # flags used to link shared libraries should be skipped:
        deps = [x for x in deps if isinstance(x.type, LibraryType)]
        out = []
        out_bookkeeping = set()
        for t in [target] + deps:
            values = t[propname]
            if isinstance(target, ConfigurationProxy):
                values = target.apply_subst(values)
            for x in values:
                # TODO: use some ordered-set type and just merge them; this
                #       type would deal with duplicates identification with
                #       are_equal or as_symbolic as well
                x_sym = x.as_symbolic()
                try:
                    if x_sym not in out_bookkeeping and x not in out:
                        out.append(x)
                        out_bookkeeping.add(x_sym)
                except NonConstError:
                    # can't meaningfully check for duplicates -> just insert
                    out.append(x)
                    out_bookkeeping.add(x_sym)
        return out


    @memoized
    def get_linkable_deps(self, target):
        """
        Returns iterator over target objects that are (transitive) dependencies.

        The order is the order that should be used by Unix linkers.
        """
        found = []
        recursed = set()
        self._find_linkable_deps(target, found, recursed)
        # _find_linkable_deps() returns libs in reverse order, see below
        return list(reversed(found))

    def _find_linkable_deps(self, target, found, recursed):
        # Note: We must ensure that the dependencies are in the correct link
        #       order for Unix linkers. I.e. all dependencies of a library must
        #       be to the right side of it in the resulting list.
        #
        #       A simple way to accomplish this is to scan the dependencies
        #       backwards (because the 'deps' property must be ordered
        #       Unix-style) _and_ put the recursively found libraries in front
        #       of the parent/dependent one. The result will be in inverse order,
        #       but that's easily corrected by the caller.
        with error_context(target):
            if target in recursed:
                raise Error("circular dependency between targets")
            recursed.add(target)

            project = target.project
            deps = reversed([project.get_target(x.as_py()) for x in target["deps"]])
            todo = (x for x in deps if
                    isinstance(x.type, LibraryType) or isinstance(x.type, SharedLibraryType))
            for t in todo:
                if t in found:
                    continue
                if isinstance(t.type, LibraryType): # dependencies of shared libraries are not transitive
                    self._find_linkable_deps(t, found, recursed)
                found.append(t)



class ProgramType(NativeLinkedType):
    """
    Executable program.
    """
    name = "program"

    properties = [
            Property("basename",
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

                        program mytool {
                          // use mytool2.exe or /usr/bin/mytool2
                          basename = $(id)$(vermajor);
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

    use_pic_by_default = False

    def get_build_subgraph(self, toolset, target):
        return get_compilation_subgraph(
                        toolset,
                        target,
                        ft_to=NativeProgramFileType.get(),
                        outfile=self.target_file(toolset, target))


class LibraryType(NativeCompiledType):
    """
    Static library.
    """
    name = "library"

    properties = [
            Property("basename",
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
                          basename = foo$(vermajor)$(verminor);
                        }
                     """),
        ]

    def get_build_subgraph(self, toolset, target):
        return get_compilation_subgraph(
                        toolset,
                        target,
                        ft_to=NativeLibFileType.get(),
                        outfile=self.target_file(toolset, target))


class SharedLibraryType(NativeLinkedType):
    """
    Dynamically loaded library.
    """
    name = "shared-library"

    properties = [
            Property("basename",
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

                        shared-library utils {
                          // use myapp_utils.lib, myapp_utils.dll, libmyapp_utils.so
                          basename = myapp_utils;
                        }
                     """),
            # TODO: add "libname" for the name of the import lib itself, when it differs from
            #       DLL name
            # TODO: add libtool-style sonames support
        ]

    def get_build_subgraph(self, toolset, target):
        return get_compilation_subgraph(
                        toolset,
                        target,
                        ft_to=NativeSharedLibraryFileType.get(),
                        outfile=self.target_file(toolset, target))


class LoadableModuleType(NativeLinkedType):
    """
    Runtime-loaded dynamic module (plugin).
    """
    name = "loadable-module"

    properties = [
            Property("basename",
                 type=StringType(),
                 default="$(id)",
                 inheritable=False,
                 doc="""
                     Base name of the loadable module.

                     This is not full filename or even path, it's only its base part,
                     to which platform-specific prefix and/or extension are
                     added. By default, it's the same as target's ID, but it can be changed e.g.
                     if the filename should contain version number, which would be impractical
                     to use as target identifier in the bakefile.

                     .. code-block:: bkl

                        loadable-module myplugin {
                          basename = myplugin-v1;
                        }
                     """),
            Property("extension",
                 type=StringType(),
                 default=NullExpr(),
                 inheritable=False,
                 doc="""
                     File extension of the module, including the leading dot.

                     By default, native extension for shared libraries (e.g.
                     ".dll" on Windows) is used.

                     .. code-block:: bkl

                        loadable-module excel_plugin {
                          extension = .xll;
                        }
                     """),
        ]

    def get_build_subgraph(self, toolset, target):
        return get_compilation_subgraph(
                        toolset,
                        target,
                        ft_to=NativeLoadableModuleFileType.get(),
                        outfile=self.target_file(toolset, target))
