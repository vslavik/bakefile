#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2008-2009 Vaclav Slavik
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

import error


class Project(object):
    """
    Abstract model that completely describes state of loaded and processed
    Bakefile file(s) within the project.

    .. attribute: modules

       List of all modules included in the project.
    """
    def __init__(self):
        self.modules = []



class Module(object):
    """
    Representation of single compilation unit. Corresponds to one Bakefile
    input file (either specified on command line or imported using `import`
    command; files included using `include` from other files are *not*
    represented by Module object) and typically to one generated output file.

    .. attribute:: variables

       Dictionary of all variables defined in global scope in this module

    .. attribute:: targets

       Dictionary of all targets defined in this module
    """

    def __init__(self):
        self.variables = {}
        self.targets = {}


    def get_variable(self, name):
        """
        Returns variable object for given variable or None if it is not
        defined.
        """
        # FIXME: implement recursive lookup
        if name in self.variables:
            return self.variables[name]
        else:
            return None


    def get_variable_value(self, name):
        """
        Similar to get_variable(), but returns the expression with variable's
        value. Throws and exception if the variable isn't defined.
        """
        var = self.get_variable(name)
        if not var:
            raise error.Error(None, "unknown variable \"%s\"" % name)
        return var.value


    def add_variable(self, var):
        """Adds a new variable object."""
        assert var.name not in self.variables
        self.variables[var.name] = var


    def add_target(self, target):
        """Adds a new target object."""
        assert target.name not in self.targets
        self.targets[target.name] = target



class Variable(object):
    """
    A Bakefile variable.

    Variables can be either global or target-specific. Value held by a variable
    is stored as expression tree, it isn't evaluated into string form until
    the final stage of processing, when output is generated.

    Variables are typed.

    .. attribute:: name

       Name of the variable.

    .. attribute:: value

       Value of the variable, as :class:`bkl.expr.Expr` object.
    """

    def __init__(self, name, value):
        self.name = name
        self.value = value



class Target(object):
    """
    A Bakefile target.

    Variables are typed.

    .. attribute:: name

       Name of the target.

    .. attribute:: type

       Type of the target, as api.TargetType instance.
    """

    def __init__(self, name, type):
        """
        Target constructor.

        :param name: name (ID) of the target; this must be unique in the
            entire project
        :param type: api.TargetType instance identifying the type
        """
        self.name = name
        self.type = type
