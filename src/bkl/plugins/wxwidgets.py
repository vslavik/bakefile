#
#  This file is part of Bakefile (http://bakefile.org)
#
#  Copyright (C) 2011-2013 Vaclav Slavik
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
wxWidgets library support.
"""

from bkl.api import FileCompiler, FileType
from bkl.compilers import CxxFileType
from bkl.expr import LiteralExpr, ConcatExpr, ReferenceExpr


class XRCFileType(FileType):
    name = "XRC"
    def __init__(self):
        FileType.__init__(self, extensions=["xrc"])


class WXRCCompiler(FileCompiler):
    """
    wxWidgets' WXRC compiler.
    """
    name = "WXRC"
    in_type = XRCFileType.get()
    out_type = CxxFileType.get()

    def commands(self, toolset, target, input, output):
        if target.resolve_variable("WXRC"):
            wxrc_expr = ReferenceExpr("WXRC", target)
        else:
            wxrc_expr = LiteralExpr("wxrc")

        # FIXME: make this easier to write with parsing
        cmd = ConcatExpr([
                    wxrc_expr,
                    LiteralExpr(" --cpp-code -o "),
                    output,
                    LiteralExpr(" "),
                    input
                    ])
        return [cmd]
