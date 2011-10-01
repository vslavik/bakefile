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
Foundation code for makefile-based toolsets.

All makefile-based toolsets should derive from MakefileToolset defined
in this module.
"""

import types
import os.path

import io
import expr
import utils
from bkl.api import Extension, Toolset, Property
from bkl.vartypes import PathType


class MakefileFormatter(Extension):
    """
    MakefileFormatter extensions are used to format makefiles content
    (i.e. targets and their commands) in the particular makefiles format.

    This includes things such as expressing conditional content, referencing
    variables and so on.

    Note that formatters do *not* handle platform- or compiler-specific things,
    e.g. path separators or compiler invocation. There are done by
    :class:`bkl.expr.Formatter` and :class:`bkl.api.FileCompiler` classes.

    This base class implements methods that are common for most make variants;
    derived classes can override them and they must implement the rest.
    """
    @staticmethod
    def comment(text):
        """
        Returns given (possibly multi-line) string formatted as a comment.

        :param text: text of the comment
        """
        return "\n".join("# %s" % s for s in text.split("\n"))

    @staticmethod
    def var_reference(var):
        """
        Returns string with code for referencing a variable.

        For most `make` implementations out there, `var_reference("FOO")`
        returns `"$(FOO)"`.

        :param var: string with name of the variable
        """
        return "$(%s)" % var

    @staticmethod
    def var_definition(var, value):
        """
        Returns string with definition of a variable value, typically
        `var = value`.

        :param var:   variable being defined
        :param value: value of the variable; this string is already formatted
                      to be in make's syntax (e.g. using var_reference()) and
                      may be multi-line
        """
        return "%s = %s" % (var, " \\\n\t".join(value.split("\n")))

    @staticmethod
    def target(name, deps, commands):
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
                         May be :const:`None`.
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


class _MakefileExprFormatter(expr.Formatter):
    def __init__(self, makefile_formatter, paths_info):
        super(_MakefileExprFormatter, self).__init__(paths_info)
        self.makefile_formatter = makefile_formatter

    def reference(self, e):
        # FIXME: don't do this for references to options or other stuff
        #        that isn't meant to be expanded
        return self.format(e.get_value())
        #return self.makefile_formatter.var_reference(e.var)


class MakefileToolset(Toolset):
    """
    Base class for makefile-based toolsets.
    """
    #: :class:`MakefileFormatter`-derived class for this toolset.
    Formatter = None

    #: Default filename from output makefile.
    default_makefile = None

    @classmethod
    def properties_module(cls):
        yield Property("%s.makefile" % cls.name,
                       type=PathType(),
                       default=cls.default_makefile,
                       inheritable=False,
                       doc="Name of output file for module's makefile.")

    def generate(self, project):
        for m in project.modules:
            self._gen_makefile(m)

    def _gen_makefile(self, module):
        output_value = module.get_variable_value("%s.makefile" % self.name)
        output = output_value.as_native_path_for_output(module)

        paths_info = expr.PathAnchorsInfo(
                dirsep="/", # FIXME - format-configurable
                outfile=output,
                builddir=os.path.dirname(output), # FIXME
                model=module)

        expr_fmt = _MakefileExprFormatter(self.Formatter, paths_info)

        f = io.OutputFile(output, io.EOL_UNIX)

        for v in module.variables:
            pass

        # We need to know build graphs of all targets so that we can generate
        # dependencies on produced files:
        build_graphs = utils.OrderedDict()
        for t in module.targets.itervalues():
            build_graphs[t] = t.type.get_build_subgraph(self, t)

        #FIXME: make this part of the formatter for (future) IdRefExpr
        def _format_dep(target_name):
            t = module.get_target(target_name)
            # FIXME: instead of using the first node, use some main_node
            g = build_graphs[t][0]
            if g.name:
                out = g.name
            else:
                # FIXME: handle multi-output nodes too
                assert len(g.outputs) == 1
                out = g.outputs[0]
            return expr_fmt.format(out)

        # Write the "all" target:
        all_targets = [_format_dep(t) for t in module.targets]
        f.write(self.Formatter.target(name="all", deps=all_targets, commands=None))

        for t in module.targets.itervalues():
            graph = build_graphs[t]
            for node in graph:
                if node.name:
                    out = node.name
                else:
                    # FIXME: handle multi-output nodes too
                    assert len(node.outputs) == 1
                    out = node.outputs[0]
                deps = [expr_fmt.format(i) for i in node.inputs]
                deps += [_format_dep(t) for t in t.get_variable_value("deps").as_py()]
                text = self.Formatter.target(
                        name=expr_fmt.format(out),
                        deps=deps,
                        commands=[expr_fmt.format(c) for c in node.commands])
                f.write(text)
                all_targets.append(expr_fmt.format(out))

        f.commit()
