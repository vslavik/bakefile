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


class Model(object):
    """
    Abstract model that completely describes state of loaded and processed
    Bakefile file(s).

    .. attribute: makefiles

       List of all makefiles included in the model.
    """
    def __init__(self):
        self.makefiles = []


class Makefile(object):
    """
    Representation of single compilation unit. Corresponds to one Bakefile
    input file (either specified on command line or imported using `import`
    command; files included using `include` from other files are *not*
    represented by Makefile object) and typically to one generated output file.

    .. attribute:: variables

       Dictionary of all variables defined in global scope in this makefile
    """
    # FIXME: terminology: would be better to use some term that means
    #        "makefile or solution/project file" for this class' name

    def __init__(self):
        self.variables = {}


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


    def add_variable(self, var):
        """Adds a new variable object."""
        assert var.name not in self.variables
        self.variables[var.name] = var


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

       Value of the variable, as :class:`Expr` object.
    """

    def __init__(self, name, value):
        self.name = name
        self.value = value


class Expr(object):
    """
    Value expression.

    Represents a value (typically assigned to a variable, but also expressions
    used somewhere else, e.g. as conditions) as tree of expression objects. In
    Bakefile, the expressions are kept in tree representation until the last
    possible moment, and are manipulated in this form.

    Note that expression objects are immutable: if you need to modify an
    expression, replace it with a new object.
    """
    # FIXME: type handling
    pass


class ConstExpr(Expr):
    """
    Constant expression -- holds a literal.
    """
    def __init__(self, value):
        self.value = value


class ListExpr(Expr):
    """
    List expression -- list of several values of the same type.
    """
    def __init__(self, items):
        self.items = items
