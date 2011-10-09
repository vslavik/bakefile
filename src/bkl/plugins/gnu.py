#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2009-2011 Vaclav Slavik
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

class GnuObjectFileType(FileType):
    name = "gnu-object"
    def __init__(self):
        FileType.__init__(self, extensions=["o"])


class GnuFileCompiler(FileCompiler):
    def is_supported(self, toolset):
        return toolset == GnuToolset.get()


class GnuCCompiler(GnuFileCompiler):
    """
    GNU C compiler.
    """
    name = "GNU C"
    in_type = bkl.compilers.CFileType.get()
    out_type = GnuObjectFileType.get()

    _compiler = "cc"

    def commands(self, target, input, output):
        cmd = [LiteralExpr("%s -c -o $@" % self._compiler)]
        # FIXME: evaluating the flags here every time is inefficient
        cmd += bkl.expr.add_prefix("-D", target["defines"]).items
        cmd += bkl.expr.add_prefix("-I", target["includedirs"]).items
        cmd += target["cppflags"].items
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


class GnuLinker(GnuFileCompiler):
    """
    GNU linker.
    """
    name = "GNU LD"
    in_type = GnuObjectFileType.get()
    out_type = bkl.compilers.NativeExeFileType.get()

    def commands(self, target, input, output):
        cmd = [LiteralExpr("c++ -o $@"), input]
        cmd += target["ldflags"].items
        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        return [ListExpr(cmd)]


class GnuLibLinker(GnuFileCompiler):
    """
    GNU library linker.
    """
    name = "AR"
    in_type = GnuObjectFileType.get()
    out_type = bkl.compilers.NativeLibFileType.get()

    def commands(self, target, input, output):
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
    GNU toolchain.

    This toolset generates makefiles for the GNU toolchain -- GNU Make, GCC compiler,
    GNU LD linker etc. -- running on Unix system.

    Currently, only Linux systems (or something sufficiently compatible) are supported.
    In particular, file extensions and linker behavior (symlinks, sonames) are assumed
    to be Linux ones.
    """
    name = "gnu"

    Formatter = GnuMakefileFormatter
    default_makefile = "GNUmakefile"

    object_type = GnuObjectFileType.get()
