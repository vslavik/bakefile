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

import os.path
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

    .. attribute:: pos

       Location of the expression in source tree.
    """

    def __init__(self):
        self.pos = None


    def as_py(self, ctxt=None):
        """
        Returns the expression as Python value (e.g. a list of strings) if it
        evaluates to a constant literal. Throws an exception if the expression
        cannot be evaluated at make-time (such expressions cannot be used in
        some situations, e.g. to specify output files). Paths are returned as
        native paths.

        Use :class:`bkl.expr.Formatter` if you need to format expressions
        into strings.

        :param ctxt: The :class:`bkl.expr.EvalContext` to evaluate the
            expression in.
        """
        raise NotImplementedError



class LiteralExpr(Expr):
    """
    Constant expression -- holds a literal.

    .. attribute:: value

       Value of the literal.
    """

    def __init__(self, value):
        super(LiteralExpr, self).__init__()
        self.value = value


    def as_py(self, ctxt=None):
        return self.value


    def __str__(self):
        return str(self.value)



class ListExpr(Expr):
    """
    List expression -- list of several values of the same type.
    """

    def __init__(self, items):
        super(ListExpr, self).__init__()
        self.items = items


    def as_py(self, ctxt=None):
        return [ i.as_py(ctxt) for i in self.items ]


    def __str__(self):
        return "[%s]" % ", ".join(str(x) for x in self.items)



class NullExpr(Expr):
    """
    Empty/unset value.
    """

    def as_py(self, ctxt=None):
        return None


    def __str__(self):
        return "null"



class ReferenceExpr(Expr):
    """
    Reference to a variable.

    .. attribute:: var

       Name of referenced variable.

    .. attribute:: context

       Context of the reference, i.e. the scope in which it was used. This is
       the appropriate :class:`bkl.model.ModelPart` instance (e.g. a target
       or a module).
    """

    def __init__(self, var, context):
        super(ReferenceExpr, self).__init__()
        self.var = var
        self.context = context


    def as_py(self, ctxt=None):
        raise NonConstError(self)


    def get_value(self):
        """
        Returns value of the referenced variable. Throws an exception if
        the reference couldn't be resolved.
        """
        try:
            return self.context.get_variable_value(self.var)
        except Error as e:
            if self.pos:
                e.pos = self.pos
            raise


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
        super(PathExpr, self).__init__()
        self.components = components
        self.anchor = anchor


    def as_py(self, ctxt=None):
        # FIXME: this code doesn't account for the anchor
        comp = (e.as_py() for e in self.components)
        return os.path.sep.join(comp)


    def __str__(self):
        return "%s/%s" % (self.anchor, "/".join(str(e) for e in self.components))



class EvalContext(object):
    """
    Evaluation context information.

    This structure is passed to some functions that work with :class:`Expr`
    and that need to know additional information in order to process the
    expression. For example, the :class:`bkl.expr.Formatter` class needs extra
    information to be able to format file paths using the right separator.

    All of the values may be ``None`` if they are not known yet.

    .. attribute:: dirsep

       Separator to separate path components ("/" on Unix and "\\" on Windows).

    .. attribute:: outdir

       Current output directory, i.e. the directory into which Bakefile is
       writing files at the moment the context is used, relative to the project
       root, in Unix syntax. This value may (and typically does) change during
       processing -- for example, it may be ``build/msvc2005`` when generating
       main library project for VC++ 2005, ``build/msvc2008`` when creating the
       same for VC++ 2008 and ``examples/build/msvc2008`` for a submodule).
    """

    def __init__(self):
        self.dirsep = None
        self.outdir = None



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
    elif isinstance(e, ReferenceExpr):
        return split(e.get_value(), sep)
    else:
        # FIXME: set pos
        raise Error("don't know how to split expression \"%s\"" % e)
