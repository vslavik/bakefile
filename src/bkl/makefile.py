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
Foundation code for makefile-based toolsets.

All makefile-based toolsets should derive from MakefileToolset defined
in this module.
"""

import types
import os.path

import io
import expr
from bkl.api import Extension, Toolset, Property
from bkl.vartypes import PathType


class MakefileFormatter(Extension):
    """
    MakefileFormatter extensions are used to format makefiles content
    (i.e. targets and their commands) in the particular makefiles format.

    This includes things such as expressing conditional content, referencing
    variables and so on.

    Note that formatters do *not* handle platform- or compiler-specific things,
    e.g. path separators or compiler invocation. There are done by FIXME and
    FIXME respectively.

    This base class implements methods that are common for most make variants;
    derived classes can override them and they must implement the rest.
    """

    def comment(self, text):
        """
        Returns given (possibly multi-line) string formatted as a comment.

        :param text: text of the comment
        """
        return "\n".join("# %s" % s for s in text.split("\n"))


    def var_reference(self, var):
        """
        Returns string with code for referencing a variable.

        For most `make` implementations out there, `var_reference("FOO")`
        returns `"$(FOO)"`.

        :param var: string with name of the variable
        """
        return "$(%s)" % var


    def var_definition(self, var, value):
        """
        Returns string with definition of a variable value, typically
        `var = value`.

        :param var:   variable being defined
        :param value: value of the variable; this string is already formatted
                      to be in make's syntax (e.g. using var_reference()) and
                      may be multi-line
        """
        return "%s = %s" % (var, " \\\n\t".join(value.split("\n")))


    def target(self, name, deps, commands):
        """
        Returns string with target definition.

        :param name:     Name of the target.
        :param deps:     List of its dependencies. Items are strings
                         corresponding to some target's name (may be expressions
                         that reference a variable, in that case the string
                         must already be processed with :meth:`var_reference`).
                         May be empty.
        :param commands: List of commands to execute to build the target; they
                         are already formatted to be in make's syntax and each
                         command in the list is single-line shell command.
        """
        out = "%s:" % name
        if deps:
            out += " "
            out += " ".join(deps)
        if commands:
            for c in commands:
                out += "\n\t%s" % c
        out += "\n\n"
        return out


    def format_expr(self, e, ctxt):
        """
        Helper method to format a :class:`bkl.expr.Expr` expression into make's
        syntax. The expression may only reference variables that will be part
        of the output (no checks are done for this).
        """
        if isinstance(e, expr.ReferenceExpr):
            return self.var_reference(e.var)
        elif isinstance(e, expr.ListExpr):
            return " ".join([self.format_expr(i) for i in e.items])
        elif isinstance(e, types.ListType):
            return " ".join([self.format_expr(i) for i in e])
        elif isinstance(e, expr.LiteralExpr):
            return e.value
        elif isinstance(e, expr.PathExpr):
            # FIXME: doesn't handle relative directories, ignores
            #        @anchors
            return ctxt.dirsep.join(self.format_expr(i, ctxt)
                                    for i in e.components)
        elif isinstance(e, types.StringType):
            return e
        elif isinstance(e, types.UnicodeType):
            return str(e)
        else:
            assert False, "unrecognized expression type (%s)" % type(e)



class MakefileToolset(Toolset):
    """
    Base class for makefile-based toolsets.
    """

    #: :class:`MakefileFormatter` class for this toolset.
    Formatter = None

    #: Default filename from output makefile.
    default_makefile = None

    properties = [
            Property("makefile",
                     type=PathType(),
                     # FIXME: assign default value: if-expression evaluating
                     #        to every possibility
                     doc="Name of output file for module's makefile."),
    ]


    def generate(self, project):
        for m in project.modules:
            self._gen_makefile(m)


    def _gen_makefile(self, module):
        assert self.default_makefile is not None

        fmt = self.Formatter()

        ctxt = expr.EvalContext()
        ctxt.dirsep = "/" # FIXME - format-configurable
        # FIXME: topdir should be constant, this is akin to @srcdir
        ctxt.topdir = os.path.dirname(module.source_file)

        # FIXME: require the value, use get_variable_value(), set the default
        #        value instead
        output_var = module.get_variable("makefile")
        if output_var is None:
            # FIXME: instead of this, the default is supposed to be relative
            #        to @srcdir
            output = os.path.join(ctxt.topdir, self.default_makefile)
        else:
            output = output_var.value.as_py(ctxt)

        ctxt.outdir = os.path.dirname(output)

        f = io.OutputFile(output)

        for v in module.variables:
            pass
        for t in module.targets.itervalues():
            graph = t.type.get_build_subgraph(t)

            for node in graph:
                if node.name:
                    out = node.name
                else:
                    # FIXME: handle multi-output nodes too
                    assert len(node.outputs) == 1
                    out = node.outputs[0]
                text = fmt.target(
                        fmt.format_expr(out, ctxt),
                        [fmt.format_expr(i, ctxt) for i in node.inputs],
                        [fmt.format_expr(c, ctxt) for c in node.commands])
                f.write(text)

        f.commit()
