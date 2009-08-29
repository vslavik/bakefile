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

import io
from bkl.api import Extension, Toolset, Property
from bkl.vartypes import AnyType


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

        :param name:     name of the target
        :param deps:     list of its dependencies (as strings corresponding to
                         some target's name); may be empty
        :param commands: list of commands to execute to build the target; they
                         are already formatted to be in make's syntax and each
                         command in the list is single-line shell command
        """
        out = "%s:" % name
        if deps:
            out += " "
            out += " ".join(deps)
        if commands:
            for c in command:
                out += "\n\t%s" % c
        return out



class MakefileToolset(Toolset):
    """
    Base class for makefile-based toolsets.
    """

    #: :class:`MakefileFormatter` class for this toolset.
    Formatter = None

    properties = [
            Property("makefile",
                     type=AnyType(), # Make this a path!
                     doc="Name of output file for module's makefile."),
    ]


    def generate(self, project):
        for m in project.modules:
            self._gen_makefile(m)
        pass


    def _gen_makefile(self, module):
        output = module.get_variable_value("makefile").as_const()

        f = io.OutputFile(output)

        for v in module.variables:
            pass
        for t in module.targets:
            pass
        raise NotImplementedError # not fully, anyway

        f.commit()
