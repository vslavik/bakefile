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

"""
The :class:`Expr` class that represents a Bakefile expression (be it a
condition or variable value) is defined in this module, together with
useful functions for evaluating and simplifying expressions.
"""


#: Boolean value of "true".
TRUE = "true"
#: Boolean value of "false".
FALSE = "false"


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

    def is_const(self):
        """
        Returns True if the expression evaluates to a constant. If this method
        returns False, it means that the expression can only be evaluated
        at make-time. Such expressions cannot be used in some situations, e.g.
        to specify output files.
        """
        raise NotImplementedError



class ConstExpr(Expr):
    """
    Constant expression -- holds a literal.
    """
    def __init__(self, value):
        self.value = value

    def is_const(self):
        return True



class ListExpr(Expr):
    """
    List expression -- list of several values of the same type.
    """
    def __init__(self, items):
        self.items = items

    def is_const(self):
        for i in self.items:
            if not i.is_const():
                return False
        return True
