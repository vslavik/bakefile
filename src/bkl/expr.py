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

from error import NonConstError, Error

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

    def as_const(self):
        """
        Returns the expression as Python value (e.g. a list of strings) if it
        evaluates to a constant literal. Throws an exception if the expression
        cannot be evaluated at make-time (such expressions cannot be used in
        some situations, e.g. to specify output files).
        """
        raise NotImplementedError



class LiteralExpr(Expr):
    """
    Constant expression -- holds a literal.

    .. attribute:: value

       Value of the literal.
    """

    def __init__(self, value):
        self.value = value


    def as_const(self):
        return self.value


    def __str__(self):
        return str(self.value)



class ListExpr(Expr):
    """
    List expression -- list of several values of the same type.
    """

    def __init__(self, items):
        self.items = items


    def as_const(self):
        return [ i.as_const() for i in self.items ]


    def __str__(self):
        return "[%s]" % ", ".join(str(x) for x in self.items)



class NullExpr(Expr):
    """
    Empty/unset value.
    """

    def as_const(self):
        return None


    def __str__(self):
        return "null"



class ReferenceExpr(Expr):
    """
    Reference to a variable.

    .. attribute:: var

       Name of referenced variable.
    """

    def __init__(self, var):
        # FIXME: use reference to variable object instead?
        self.var = var


    def as_const(self):
        raise NonConstError(self)


    def __str__(self):
        return "$(%s)" % self.var



# anchors -- special syntax first components of a path
ANCHOR_SRCDIR     = "@srcdir"
ANCHOR_TOP_SRCDIR = "@top_srcdir"

# all possible anchors
ANCHORS = [ANCHOR_SRCDIR, ANCHOR_TOP_SRCDIR]

class PathExpr(Expr):
    """
    Expression that holds a file or directory name, or part of it.

    .. attribute:: components

       List of path's components (as expressions). For example, components of
       path ``foo/bar/file.cpp`` are ``["foo", "bar", "file.cpp"]``.

    .. attribute:: anchor

       The point to which the path is relative to. This can be one of the
       following:

       * ``expr.ANCHOR_SRCDIR`` -- Path is relative to the source
         directory (where the ``.bkl`` file is, unless overriden in it).
       * ``expr.ANCHOR_TOP_SRCDIR`` -- Path is relative to the top
         source directory (where the toplevel ``.bkl`` file is, unless
         overriden in it).
    """

    def __init__(self, components, anchor=ANCHOR_SRCDIR):
        self.components = components
        self.anchor = anchor


    def as_const(self):
        # FIXME: this doesn't account for the anchor and platform
        return "/".join(e.as_const() for e in self.components)


    def __str__(self):
        return "%s/%s" % (self.anchor, "/".join(str(e) for e in self.components))



def split(e, sep):
    """
    Splits expression *e* into a list of expressions, using *sep* as the
    delimiter character. Works with conditional expressions and variable
    references too.
    """
    assert len(sep) == 1
    if isinstance(e, LiteralExpr):
        vals = e.value.split(sep)
        return [LiteralExpr(v) for v in vals]
    else:
        # FIXME: set pos
        raise Error("don't know how to split expression \"%s\"" % expr)
