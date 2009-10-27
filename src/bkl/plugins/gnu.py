#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2009 Vaclav Slavik
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

from bkl.api import FileCompiler
from bkl.makefile import MakefileToolset, MakefileFormatter
import bkl.compilers

# FIXME: shouldn't be needed later
from bkl.expr import ListExpr, LiteralExpr

class GnuCCompiler(FileCompiler):
    """
    GNU C compiler.
    """
    name = "GNU C"
    in_type = bkl.compilers.CFileType.get()
    out_type = bkl.compilers.ObjectFileType.get()

    def commands(self, input, output):
        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        return [ListExpr([
                  LiteralExpr("cc -c -o"),
                  output,
                  input
                ])]



class GnuLinker(FileCompiler):
    """
    GNU linker.
    """
    name = "GNU LD"
    in_type = bkl.compilers.ObjectFileType.get()
    out_type = bkl.compilers.NativeExeFileType.get()

    def commands(self, input, output):
        # FIXME: use a parser instead of constructing the expression manually
        #        in here
        return [ListExpr([
                  LiteralExpr("cc -o"),
                  output,
                  input
                ])]



class GnuMakefileFormatter(MakefileFormatter):
    """
    Formatter for the GNU Make syntax.
    """
    # The basics are common to all makes, nothing to add (yet)
    pass



class GnuToolset(MakefileToolset):
    """
    GNU toolset.
    """

    name = "gnu"

    Formatter = GnuMakefileFormatter
    default_makefile = "GNUmakefile"
