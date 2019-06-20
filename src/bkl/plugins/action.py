#
#  This file is part of Bakefile (http://bakefile.org)
#
#  Copyright (C) 2012-2013 Vaclav Slavik
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
Target for running arbitrary scripts.
"""

from bkl.api import TargetType, Property, BuildNode, BuildSubgraph
from bkl.vartypes import *
from bkl.expr import add_prefix


class ActionTargetType(TargetType):
    """
    Custom action script.

    *Action* targets execute arbitrary commands. They can be used to do various
    tasks that don't fit the model of compiling or creating files, such as
    packaging files, installing, uploading, running tests and so on.

    Actions are currently only supported by makefile-based toolsets. See the
    ``pre-build-commands`` and ``post-build-commands`` properties for another
    alternative that is supported by Visual Studio projects.

    The optional ``inputs`` property may be used to specify the list of file
    paths that the makefile target generated for this action should depend on.
    Notice that if the action depends on another target defined in the
    bakefile, this should be specified in ``deps``, as for any other kind of
    target and not in ``inputs``.

    If the optional ``outputs`` property is specified, the action is supposed
    to generate the files listed in this property. This means that other
    targets depending on this action will depend on these files in the
    generated makefile, instead of depending on the phony target for an action
    without outputs and also that these files will be cleaned up by the
    ``clean`` target of the generated makefile.

    .. code-block:: bkl

       action osx-bundle
       {
         deps = test;
         commands = "mkdir -p Test.app/Contents/MacOS"
                    "cp -f test Test.app/Contents/MacOS/test"
                    ;
       }
    """
    name = "action"

    properties = [
            Property("commands",
                 type=ListType(StringType()),
                 default=[],
                 inheritable=False,
                 doc="List of commands to run."),

            Property("inputs",
                 type=ListType(PathType()),
                 default=expr.NullExpr(),
                 inheritable=False,
                 doc="Extra input files this action depends on, if any."),

            Property("outputs",
                 type=ListType(PathType()),
                 default=expr.NullExpr(),
                 inheritable=False,
                 doc="Output files created by this action, if any."),
        ]

    def get_build_subgraph(self, toolset, target):
        # prefix each line with @ so that make doesn't output the commands:
        cmds_var = target["commands"]
        cmds = add_prefix("@", cmds_var)
        node = BuildNode(commands=list(cmds),
                         name=target["id"],
                         inputs=target["inputs"],
                         outputs=target["outputs"],
                         source_pos=cmds_var.pos)
        return BuildSubgraph(node)
