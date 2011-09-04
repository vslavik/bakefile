#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2008-2011 Vaclav Slavik
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
import itertools
from abc import ABCMeta, abstractmethod

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


    def as_py(self):
        """
        Returns the expression as Python value (e.g. a list of strings) if it
        evaluates to a constant literal. Throws an exception if the expression
        cannot be evaluated at make-time (such expressions cannot be used in
        some situations, e.g. to specify output files). Paths are returned as
        native paths.

        Use :class:`bkl.expr.Formatter` if you need to format expressions
        into strings.
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


    def as_py(self):
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


    def as_py(self):
        return [ i.as_py() for i in self.items ]


    def __str__(self):
        return "[%s]" % ", ".join(str(x) for x in self.items)



class ConcatExpr(Expr):
    """
    Concatenation of several expression. Typically, used with LiteralExpr
    and ReferenceExpr to express values such as "$(foo).cpp".
    """

    def __init__(self, items):
        super(ConcatExpr, self).__init__()
        assert len(items) > 0
        self.items = items


    def as_py(self):
        return "".join(i.as_py() for i in self.items)


    def __str__(self):
        return "".join(str(i) for i in self.items)



class NullExpr(Expr):
    """
    Empty/unset value.
    """

    def as_py(self):
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


    def as_py(self):
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
ANCHOR_TOP_SRCDIR = "@top_srcdir"
ANCHOR_BUILDDIR = "@builddir"

# all possible anchors
ANCHORS = [ANCHOR_TOP_SRCDIR, ANCHOR_BUILDDIR]

class PathExpr(Expr):
    """
    Expression that holds a file or directory name, or part of it.

    .. attribute:: components

       List of path's components (as expressions). For example, components of
       path ``foo/bar/file.cpp`` are ``["foo", "bar", "file.cpp"]``.

    .. attribute:: anchor

       The point to which the path is relative to. This can be one of the
       following:

       * ``expr.ANCHOR_TOP_SRCDIR`` -- Path is relative to the top
         source directory (where the toplevel ``.bkl`` file is, unless
         overriden in it).

       * ``expr.ANCHOR_BUILDDIR`` -- Path is relative to the build directory.
         This anchor should be used for all transient files (object files
         or other generated files).
    """

    def __init__(self, components, anchor=ANCHOR_TOP_SRCDIR):
        super(PathExpr, self).__init__()
        self.components = components
        self.anchor = anchor


    def as_py(self, top_srcdir=None):
        assert top_srcdir, \
               "PathExpr.as_py() can only be called with top_scrdir argument"
        assert self.anchor == ANCHOR_TOP_SRCDIR, \
               "PathExpr.as_py() can only be used with top_srcdir-relative paths"
        comp = (e.as_py() for e in self.components)
        return os.path.join(top_srcdir, os.path.sep.join(comp))


    def __str__(self):
        return "%s/%s" % (self.anchor, "/".join(str(e) for e in self.components))


    def get_extension(self):
        """
        Returns extension of the filename path. Throws if it cannot be
        determined.
        """
        if not self.components:
            raise Error("cannot get extension of empty path", self.pos)

        last = self.components[-1]
        if isinstance(last, LiteralExpr):
            dot = last.value.rfind(".")
            if dot != -1:
                return last.value[dot+1:]

        raise Error("cannot determine extension of \"%s\"" % self, self.pos)



    def change_extension(self, newext):
        """
        Changes extension of the filename to *newext* and returns
        :class:`bkl.expr.PathExpr` with the new path.
        """
        if not self.components:
            raise Error("cannot change extension of empty path", self.pos)

        last = self.components[-1]
        if not isinstance(last, LiteralExpr):
            raise Error("cannot change extension of \"%s\" to .%s" % (self, newext),
                        self.pos)

        dot = last.value.rfind(".")
        if dot != -1:
            tail = "%s.%s" % (last.value[:dot], newext)
        else:
            tail = "%s.%s" (last.value, newext)

        comps = self.components[:-1] + [LiteralExpr(tail)]
        return PathExpr(comps, self.anchor)



class Visitor(object):
    """
    Implements visitor pattern for :class:`Expr` expressions. This is abstract
    base class, derived classes must implement all of its methods except
    :meth:`visit()`. The way visitors are used is that the caller calls 
    :meth:`visit()` on the expression.
    """
    __metaclass__ = ABCMeta

    def visit(self, e):
        """
        Call this method to visit expression *e*. One of object's "callback"
        methods will be called, depending on *e*'s type.

        Return value is the value returned by the appropriate callback and
        is typically :const:`None`.
        """
        t = type(e)
        assert t in self._dispatch, "unknown expression type (%s)" % t
        func = self._dispatch[t]
        return func(self, e)


    @abstractmethod
    def literal(self, e):
        """Called on :class:`LiteralExpr` expressions."""
        raise NotImplementedError

    @abstractmethod
    def list(self, e):
        """Called on :class:`ListExpr` expressions."""
        raise NotImplementedError

    @abstractmethod
    def concat(self, e):
        """Called on :class:`ConcatExpr` expressions."""
        raise NotImplementedError

    @abstractmethod
    def reference(self, e):
        """Called on :class:`ReferenceExpr` expressions."""
        raise NotImplementedError

    @abstractmethod
    def path(self, e):
        """Called on :class:`PathExpr` expressions."""
        raise NotImplementedError

    _dispatch = {
        LiteralExpr   : lambda self,e: self.literal(e),
        ListExpr      : lambda self,e: self.list(e),
        ConcatExpr    : lambda self,e: self.concat(e),
        ReferenceExpr : lambda self,e: self.reference(e),
        PathExpr      : lambda self,e: self.path(e),
    }



class PathAnchors(object):
    """
    Struct with information about real values for symbolic *anchors* of
    :class:`PathExpr` paths. These are needed in order to format path
    expression (using :class:`bkl.expr.Formatter` or otherwise).

    .. attribute:: dirsep

       Separator to separate path components ("/" on Unix and "\\" on Windows).

    .. attribute:: outdir

       Current output directory, i.e. the directory into which Bakefile is
       writing files at the moment the context is used, relative to
       *top_srcdir* root, as a list of components. Will be empty list if the
       paths are the same.

       This value may (and typically does) change during processing -- for
       example, it may be ``build/msvc2005`` when generating main library
       project for VC++ 2005, ``build/msvc2008`` when creating the same for
       VC++ 2008 and ``examples/build/msvc2008`` for a submodule).

    .. attribute:: top_srcdir

       Path to the top source directory, as a list of components, relative
       to *outdir*. Will be empty list if the paths are the same.

    .. attribute:: builddir

       Path to the build directory -- the directory where object files and
       other generated files are put -- as a list of components, relative
       to *outdir*. Will be empty list if the paths are the same.
    """

    def __init__(self, dirsep, outpath, top_srcpath):
        """
        The constructor creates anchors information from native paths passed
        to it:

        :param dirsep:
                Path components separator, same as the :attr:`dirsep`
                attribute.

        :param outpath:
                (Native) path to the output directory. Paths in the output
                will be typically formatted relatively to this path.
                The :attr:`outdir` attribute is computed from this parameter.

        :param top_srcpath:
                (Native) path to the top of source tree.  The
                :attr:`top_srcdir` attribute is computed from this parameter.

        For example:

        >>> p = bkl.expr.PathAnchors(dirsep='/',
        ...                          outpath='/tmp/myprj/build/gnu',
        ...                          top_srcpath='/tmp/myprj/src')
        >>> p.outdir
        ['..', 'build', 'gnu']
        >>> p.top_srcdir
        ['..', '..', 'src']
        """
        out = os.path.split(os.path.abspath(outpath))
        top = os.path.split(os.path.abspath(top_srcpath))

        self.dirsep = dirsep
        self.outdir = _pathcomp_make_relative(out, to=top)
        self.top_srcdir = _pathcomp_make_relative(top, to=out)
        # FIXME: for now, make this settable
        self.builddir = [] # i.e. equal to outdir


def _pathcomp_make_relative(what, to):
    min_len = min(len(what), len(to))
    first_not_common = -1
    for i in xrange(0, min_len):
        if what[i] != to[i]:
            first_not_common = i
            break
    if first_not_common == -1:
        if len(what) == len(to):
            return [] # equivalent of "." path
        else:
            first_not_common = min_len
    return [".."] * (len(to) - first_not_common) + what2[first_not_common:]



class Formatter(Visitor):
    """
    Base class for expression formatters. A *formatter* is a class that
    formats the expression into a string in the way that is needed on the
    output. For example, it handles things such as path separators on
    different platforms, variable references, quoting of literals with
    whitespace in them and so on.

    The base class implements commonly used formatting, such as using
    whitespace for delimiting list items etc.

    Use the :meth:`format()` method to format an expression.

    .. attribute:: list_sep

       Separator for list items (by default, single space).

    .. attribute:: paths_info

       :class:`PathAnchors` information object to use for formatting of paths.
    """

    list_sep = " "

    def __init__(self, paths_info):
        self.paths_info = paths_info

    def format(self, e):
        """
        Formats expression *e* into a string.
        """
        return self.visit(e)

    def literal(self, e):
        # FIXME: quote strings with whitespace in them
        return e.value

    def concat(self, e):
        # FIXME: quote strings with whitespace in them
        return "".join(self.format(e) for e in e.items)

    def list(self, e):
        return self.list_sep.join(self.format(e) for e in e.items)

    def path(self, e):
        if e.anchor == ANCHOR_TOP_SRCDIR:
            base = self.paths_info.top_srcdir
        elif e.anchor == ANCHOR_BUILDDIR:
            base = self.paths_info.builddir
        else:
            assert False, "unknown path anchor (%s)" % e.anchor

        comps = [self.format(i) for i in e.components]
        return self.paths_info.dirsep.join(base + comps)



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

    elif isinstance(e, ConcatExpr):
        out = []
        for i in e.items:
            i_out = split(i, sep)
            if out:
                # Join the two lists on concatenation boundary. E.g. splitting
                # two concatenated strings "foo/bar" and "x/y" along "/" should
                # result in ["foo", "barx", "y"].
                out = ( out[:-1] +
                        [ConcatExpr([out[-1], i_out[0]])] +
                        i_out[1:] )
            else:
                out = i_out
        return out

    else:
        raise Error("don't know how to split expression \"%s\" with separator \"%s\""
                    % (e, sep),
                    pos = e.pos)



def simplify(e):
    """
    Simplify expression *e*. This does "cheap" simplifications such
    as merging concatenated literals, recognizing always-false conditions,
    eliminating unnecessary variable references (turn ``foo=$(x);bar=$(foo)``
    into ``bar=$(x)``) etc.
    """

    if isinstance(e, ListExpr):
        return ListExpr([simplify(i) for i in e.items])
    elif isinstance(e, PathExpr):
        return PathExpr([simplify(i) for i in e.components], e.anchor)

    elif isinstance(e, ConcatExpr):
        # merge concatenated literals:
        items = [simplify(i) for i in e.items]
        out = [items[0]]
        for i in items[1:]:
            if isinstance(i, LiteralExpr) and isinstance(out[-1], LiteralExpr):
                out[-1] = LiteralExpr(out[-1].value + i.value)
            else:
                out.append(i)
        return ConcatExpr(out)

    elif isinstance(e, ReferenceExpr):
        # Simple reference can be replaced with the referenced value. Do this
        # for (scalar) literals and other references only, though -- if the
        # value is e.g. a list, we want to keep it as a variable to avoid
        # duplication of large values.
        ref = e.get_value()
        if isinstance(e, LiteralExpr) or isinstance(e, ReferenceExpr):
            return ref

    # otherwise, there's nothing much to simplify:
    return e



def all_possible_values(e):
    """
    Given an expression *e*, returns a Python iterator over all its possible
    values, as :class:`bkl.expr.Expr` instances.

    Note that if called on a list, it returns a list of all possible lists,
    which is probably not something you want and
    :func:`bkl.expr.all_possible_elements()` is a better choice.
    """

    assert not isinstance(e, ListExpr), \
           "use all_possible_elements() with lists (%s)" % e

    if isinstance(e, LiteralExpr):
        yield e

    elif isinstance(e, ReferenceExpr):
        yield all_possible_values(e.get_value())

    elif isinstance(e, ConcatExpr):
        possibilities = [ all_possible_values(i) for i in e.items ]
        for i in itertools.product(*possibilities):
            yield ConcatExpr(list(i))

    elif isinstance(e, PathExpr):
        possibilities = [ all_possible_values(i) for i in e.components ]
        for i in itertools.product(*possibilities):
            yield PathExpr(list(i), e.anchor)

    else:
        raise Error("cannot determine all possible values of expression \"%s\"" % e,
                    pos = e.pos)



def all_possible_elements(e):
    """
    Given a list expression (:class:`bkl.expr.ListExpr`) *e*, returns a Python
    iterator of all possible values of the list, as :class:`bkl.expr.Expr`
    instances.
    """
    assert isinstance(e, ListExpr)

    # Keep track of duplicates; add str(e) to the set to easily detect
    # different instances of equal expressions.
    already_added = set()

    for i in e.items:
        # Go into a referenced variable. Note that this is intentionally done
        # before the assert below so that the test for nested lists is
        # performed both for literal nested lists (unlikely) and for references
        # to lists (typical: e.g. "sources = $(MY_SRC) $(YOUR_SRC)" before
        # flattening).
        if isinstance(i, ReferenceExpr):
            i = i.get_value()

        assert not isinstance(i, ListExpr), \
               "nested lists are supposed to be flattened by now"

        for v in all_possible_values(i):
            key = str(v)
            if key not in already_added:
                already_added.add(key)
                yield v
