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
Targets for natively built binaries (executables, static and shared libraries).
"""

from bkl.api import TargetType, Property, FileType
from bkl.expr import ListExpr
from bkl.vartypes import ListType, PathType
from bkl.compilers import get_compilation_subgraph, NativeExeFileType


class ExeType(TargetType):
    """
    Executable program.
    """
    name = "exe"

    properties = [
            Property("sources",
                 type=ListType(PathType()),
                 default=ListExpr([]),
                 doc="Source files."),
        ]

    def get_build_subgraph(self, target):
        return get_compilation_subgraph(
                        ft_to=NativeExeFileType.get(),
                        outfile=target.get_variable_value("id"), # FIXME
                        sources=target.get_variable_value("sources"))
