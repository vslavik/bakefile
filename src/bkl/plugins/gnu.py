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
GNU tools (GCC, GNU Make, ...) toolset.
"""

from bkl.api import FileCompiler, FileType
from bkl.makefile import MakefileToolset, MakefileFormatter
import bkl.compilers
import bkl.expr

# FIXME: shouldn't be needed later
from bkl.expr import ListExpr, LiteralExpr

# GCC flags for supported architectures:
OSX_ARCH_FLAGS = {
    'x86'    : '-arch i386',
    'x86_64' : '-arch x86_64',
}

class GnuObjectFileType(FileType):
    name = "gnu-object"
    def __init__(self):
        FileType.__init__(self, extensions=["o"])


class GnuFileCompiler(FileCompiler):
    """Base class for GNU compilers/linkers."""
    def is_supported(self, toolset):
        return isinstance(toolset, GnuToolset)

    # TODO: a hack, not exactly clean
    def _arch_flags(self, toolset, target):
        if isinstance(toolset, OSXGnuToolset):
            flags = []
            for a in target["archs"].as_py():
                if a in OSX_ARCH_FLAGS:
                    flags.append(LiteralExpr(OSX_ARCH_FLAGS[a]))
            return flags
        else:
            return []


class GnuCCompiler(GnuFileCompiler):
    """
    GNU C compiler.
    """
    name = "GNU C"
    in_type = bkl.compilers.CFileType.get()
    out_type = GnuObjectFileType.get()

    _compiler = "cc"
    _flags = "cflags"

    def commands(self, toolset, target, input, output):
        cmd = [LiteralExpr("%s -c -o $@" % self._compiler)]
        # FIXME: evaluating the flags here every time is inefficient
        cmd += self._arch_flags(toolset, target)
        cmd += bkl.expr.add_prefix("-D", target["defines"]).items
        cmd += bkl.expr.add_prefix("-I", target["includedirs"]).items
        cmd += target["cppflags"].items
        cmd += target[self._flags].items
        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        cmd.append(input)
        return [ListExpr(cmd)]


class GnuCXXompiler(GnuCCompiler):
    """
    GNU C++ compiler.
    """
    name = "GNU C++"
    in_type = bkl.compilers.CxxFileType.get()
    out_type = GnuObjectFileType.get()

    _compiler = "c++"
    _flags = "cxxflags"


class GnuLinker(GnuFileCompiler):
    """
    GNU executables linker.
    """
    name = "GNU LD"
    in_type = GnuObjectFileType.get()
    out_type = bkl.compilers.NativeExeFileType.get()

    def _linker_flags(self, toolset, target):
        cmd = self._arch_flags(toolset, target)
        libs, ldlibs = target.type.get_all_libs(toolset, target)
        cmd += libs
        cmd += bkl.expr.add_prefix("-l", ListExpr(ldlibs)).items
        cmd += target["ldflags"].items
        return cmd

    def commands(self, toolset, target, input, output):
        cmd = [LiteralExpr("c++ -o $@"), input]
        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        cmd += self._linker_flags(toolset, target)
        return [ListExpr(cmd)]


class GnuSharedLibLinker(GnuLinker):
    """
    GNU shared libraries linker.
    """
    name = "GNU shared LD"
    in_type = GnuObjectFileType.get()
    out_type = bkl.compilers.NativeDllFileType.get()

    def commands(self, toolset, target, input, output):
        cmd = [LiteralExpr("c++ -shared -o $@"), input]
        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        cmd += self._linker_flags(toolset, target)
        return [ListExpr(cmd)]


class GnuLibLinker(GnuFileCompiler):
    """
    GNU library linker.
    """
    name = "AR"
    in_type = GnuObjectFileType.get()
    out_type = bkl.compilers.NativeLibFileType.get()

    def commands(self, toolset, target, input, output):
        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        return [ListExpr([LiteralExpr("ar rcu $@"), input]),
                ListExpr([LiteralExpr("ranlib $@")])]


class GnuMakefileFormatter(MakefileFormatter):
    """
    Formatter for the GNU Make syntax.
    """
    @staticmethod
    def submake_command(directory, filename):
        return "$(MAKE) -C %s -f %s" % (directory, filename)


class GnuToolset(MakefileToolset):
    """
    GNU toolchain for Unix systems.

    This toolset generates makefiles for the GNU toolchain -- GNU Make, GCC compiler,
    GNU LD linker etc. -- running on Unix system.

    Currently, only Linux systems (or something sufficiently compatible) are supported.
    In particular, file extensions and linker behavior (symlinks, sonames) are assumed
    to be Linux ones.

    See :ref:`ref_toolset_gnu-osx` for OS X variant.
    """
    name = "gnu"

    Formatter = GnuMakefileFormatter
    default_makefile = "GNUmakefile"

    object_type = GnuObjectFileType.get()

    library_prefix = "lib"
    library_extension = "a"
    dll_prefix = "lib"
    dll_extension = "so"

    def on_phony_targets(self, file, targets):
        file.write(".PHONY: %s\n" % " ".join(targets))


class OSXGnuToolset(GnuToolset):
    """
    GNU toolchain for OS X.

    This toolset is for building on OS X using makefiles, not Xcode. It
    incorporates some of the oddities of OS X's toolchain and should be used
    instead of :ref:`ref_toolset_gnu`.
    """
    # FIXME: This is temporary solution, will be integrated into GnuToolset
    #        with runtime platform detection.
    name = "gnu-osx"

    default_makefile = "Makefile.osx"

    dll_extension = "dylib"
