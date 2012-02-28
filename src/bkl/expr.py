#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2008-2012 Vaclav Slavik
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
useful functions for evaluating and manipulating expressions.
"""

import os.path
import itertools
from abc import ABCMeta, abstractmethod

from error import NonConstError, CannotDetermineError, Error, error_context


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
    def __init__(self, pos=None):
        self.pos = pos
    
    def is_const(self):
        """
        Returns true if the expression is constant, i.e. can be evaluated
        at this time (bake-time), as opposed to expressions that depend on
        a setting that can only be determined at make-time.

        .. seealso:: :meth:`as_py()`
        """
        try:
            self.as_py()
            return True
        except NonConstError:
            return False

    def as_py(self):
        """
        Returns the expression as Python value (e.g. a list of strings) if it
        evaluates to a constant literal. Throws an exception if the expression
        cannot be evaluated at bake-time (such expressions cannot be used in
        some situations, e.g. to specify output files). Paths are returned as
        native paths.

        Use :class:`bkl.expr.Formatter` if you need to format expressions
        into strings.

        .. seealso:: :meth:`is_const()`
        """
        raise NotImplementedError

    def __nonzero__(self):
        # Derived expression classes should override this to make testing for
        # non-empty values ("if expr:") work without the need to call as_py().
        raise NotImplementedError


class LiteralExpr(Expr):
    """
    Constant expression -- holds a literal.

    .. attribute:: value

       Value of the literal.

    .. attribute:: pos

       Location of the expression in source tree.
    """
    def __init__(self, value, pos=None):
        super(LiteralExpr, self).__init__(pos)
        self.value = value

    def as_py(self):
        return self.value

    def __nonzero__(self):
        return bool(self.value)

    def __str__(self):
        return str(self.value)


class ListExpr(Expr):
    """
    List expression -- list of several values of the same type.
    """
    def __init__(self, items, pos=None):
        super(ListExpr, self).__init__(pos)
        self.items = items

    def as_py(self):
        return [ i.as_py() for i in self.items ]

    def __nonzero__(self):
        return bool(self.items)

    def __str__(self):
        return "[%s]" % ", ".join(str(x) for x in self.items)


class ConcatExpr(Expr):
    """
    Concatenation of several expression. Typically, used with LiteralExpr
    and ReferenceExpr to express values such as "$(foo).cpp".
    """
    def __init__(self, items, pos=None):
        super(ConcatExpr, self).__init__(pos)
        assert len(items) > 0
        self.items = items

    def as_py(self):
        return "".join(i.as_py() for i in self.items)

    def __nonzero__(self):
        for i in self.items:
            if i:
                return True
        return False

    def __str__(self):
        return "".join(str(i) for i in self.items)


class NullExpr(Expr):
    """
    Empty/unset value.
    """
    def as_py(self):
        return None

    def __nonzero__(self):
        return False

    def __str__(self):
        return "null"


class UndeterminedExpr(Expr):
    """
    This is a hack. It is used as placeholder for expressions with not yet known value.
    In particular, it is used for the "toolset" property before the model is split into
    toolset-specific copies, to allow partial evaluation common to all of them.
    """
    def as_py(self):
        raise NonConstError(self)


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
    def __init__(self, var, context, pos=None):
        super(ReferenceExpr, self).__init__(pos)
        self.var = var
        self.context = context

    def as_py(self):
        return self.get_value().as_py()

    def get_value(self):
        """
        Returns value of the referenced variable. Throws an exception if
        the reference couldn't be resolved.
        """
        with error_context(self):
            return self.context.get_variable_value(self.var)

    def __nonzero__(self):
        return bool(self.get_value())

    def __str__(self):
        return "$(%s)" % self.var


class BoolValueExpr(Expr):
    """
    Constant boolean value, i.e. true or false.

    .. attribute:: value

       Value of the literal, as (Python) boolean.
    """
    def __init__(self, value, pos=None):
        super(BoolValueExpr, self).__init__(pos)
        self.value = value

    def as_py(self):
        return self.value

    def __nonzero__(self):
        return self.value

    def __str__(self):
        return "true" if self.value else "false"


class BoolExpr(Expr):
    """
    Boolean expression.

    .. attribute:: operator

       Boolean operator of the node. The value is one of `BoolExpr` constants,
       e.g. `BoolExpr.AND`.

    .. attribute:: left

       Left (or in the case of NOT operator, only) operand.

    .. attribute:: right

       Right operand. Not set for the NOT operator.
    """

    #: And operator
    AND       = "&&"
    #: Or operator
    OR        = "||"
    #: Equality operator
    EQUAL     = "=="
    #: Inequality operator
    NOT_EQUAL = "!="
    #: Not operator; unlike others, this one is unary and has no right operand.
    NOT       = "!"

    def __init__(self, operator, left, right=None, pos=None):
        super(BoolExpr, self).__init__(pos)
        self.operator = operator
        self.left = left
        self.right = right
    
    def has_bool_operands(self):
        """
        Returns true if the operator is such that it requires boolean operands
        (i.e. NOT, AND, OR).
        """
        return (self.operator is BoolExpr.AND or
                self.operator is BoolExpr.OR or
                self.operator is BoolExpr.NOT)

    def as_py(self):
        op = self.operator
        if op == BoolExpr.AND:
            return self.left.as_py() and self.right.as_py()
        elif op == BoolExpr.OR:
            return self.left.as_py() or self.right.as_py()
        elif op == BoolExpr.EQUAL:
            try:
                return are_equal(self.left, self.right)
            except CannotDetermineError:
                raise CannotDetermineError('cannot evaluate bool expression "%s"' % self, self.pos)
        elif op == BoolExpr.NOT_EQUAL:
            try:
                return not are_equal(self.left, self.right)
            except CannotDetermineError:
                raise CannotDetermineError('cannot evaluate bool expression "%s"' % self, self.pos)
        elif op == BoolExpr.NOT:
            return not self.left.as_py()
        else:
            assert False, "invalid BoolExpr operator"

    def __nonzero__(self):
        left = bool(self.left)
        right = bool(self.right)
        op = self.operator
        if op == BoolExpr.AND:
            return left and right
        elif op == BoolExpr.OR:
            return left or right
        elif op == BoolExpr.NOT:
            return not left
        else:
            return self.as_py()

    def __str__(self):
        if self.operator == BoolExpr.NOT:
            return "!%s" % self.left
        else:
            return "(%s %s %s)" % (self.left, self.operator, self.right)


class IfExpr(Expr):
    """
    Conditional expression.

    .. attribute:: cond

       The condition expression.

    .. attribute:: value_yes

       Value of the expression if the condition evaluates to True.

    .. attribute:: value_no

       Value of the expression if the condition evaluates to False.
    """
    def __init__(self, cond, yes, no, pos=None):
        super(IfExpr, self).__init__(pos)
        self.cond = cond
        self.value_yes = yes
        self.value_no = no

    def as_py(self):
        if self.cond.as_py():
            return self.value_yes.as_py()
        else:
            return self.value_no.as_py()

    def get_value(self):
        """
        Returns value of the conditional expression, i.e. either
        :attr:`value_yes` or :attr:`value_no`, depending on what the condition
        evaluates to. Throws if the condition cannot be evaluated.
        """
        with error_context(self):
            return self.value_yes if self.cond.as_py() else self.value_no

    def __nonzero__(self):
        try:
            if self.cond.as_py():
                return bool(self.value_yes)
            else:
                return bool(self.value_no)
        except NonConstError:
            return bool(self.value_yes) or bool(self.value_no)

    def __str__(self):
        return "(%s ? %s : %s)" % (self.cond, self.value_yes, self.value_no)


# anchors -- special syntax first components of a path
ANCHOR_SRCDIR = "@srcdir"
ANCHOR_TOP_SRCDIR = "@top_srcdir"
ANCHOR_BUILDDIR = "@builddir"

# all possible anchors
ANCHORS = [ANCHOR_SRCDIR, ANCHOR_TOP_SRCDIR, ANCHOR_BUILDDIR]

class PathExpr(Expr):
    """
    Expression that holds a file or directory name, or part of it.

    .. attribute:: components

       List of path's components (as expressions). For example, components of
       path ``foo/bar/file.cpp`` are ``["foo", "bar", "file.cpp"]``.

    .. attribute:: anchor

       The point to which the path is relative to. This can be one of the
       following:

       * ``expr.ANCHOR_SRCDIR`` -- Path is relative to the directory where
         the input bakefile is (unless overriden in it).

       * ``expr.ANCHOR_TOP_SRCDIR`` -- Path is relative to the top
         source directory (where the toplevel ``.bkl`` file is, unless
         overriden in it).

       * ``expr.ANCHOR_BUILDDIR`` -- Path is relative to the build directory.
         This anchor should be used for all transient files (object files
         or other generated files).

    .. attribute:: pos

       Location of the expression in source tree.
    """
    def __init__(self, components, anchor=ANCHOR_SRCDIR, pos=None):
        super(PathExpr, self).__init__(pos)
        self.components = components
        self.anchor = anchor

    def as_py(self):
        raise NotImplementedError

    def __nonzero__(self):
        True

    def __str__(self):
        return "%s/%s" % (self.anchor, "/".join(str(e) for e in self.components))

    def as_native_path(self, paths_info):
        """
        Returns the path expressed as *absolute* native path. Requires complete
        :class:`bkl.expr.PathAnchorsInfo` information as its argument.

        Throws NonConstError if it cannot be done because of conditional
        subexpression.

        .. seealso:: :meth:`as_native_path_for_output()`
        """
        if self.anchor == ANCHOR_TOP_SRCDIR:
            base = paths_info.top_srcdir_abs
        elif self.anchor == ANCHOR_BUILDDIR:
            base = paths_info.builddir_abs
        else:
            assert False, "unsupported anchor in PathExpr.as_native_path()"
        comp = (e.as_py() for e in self.components)
        return os.path.abspath(os.path.join(base, os.path.sep.join(comp)))

    def as_native_path_for_output(self, model):
        """
        Specialized version of :meth:`as_native_path()` that only works with
        srcdir-based paths. It's useful for code that needs to obtain output
        file name (which happens *before* PathAnchorsInfo can be constructed).

        :param model:
                Any part of the model.
        """
        if self.anchor != ANCHOR_TOP_SRCDIR:
            raise Error('path "%s" is not srcdir-relative' % self, pos=self.pos)
        top_srcdir = os.path.dirname(model.project.top_module.source_file)
        comp = (e.as_py() for e in self.components)
        return os.path.join(top_srcdir, os.path.sep.join(comp))

    def get_basename(self):
        """
        Returns basename of the filename path (i.e. the name without directory
        or extension). Throws if it cannot be determined.
        """
        if not self.components:
            raise Error("cannot get basename of empty path", self.pos)

        last = self.components[-1]
        if isinstance(last, LiteralExpr):
            dot = last.value.rfind(".")
            if dot != -1:
                return last.value[:dot]
            else:
                return last.value

        raise Error("cannot determine basename of \"%s\"" % self, self.pos)

    def get_extension(self):
        """
        Returns extension of the filename path. Throws if it cannot be
        determined.
        """
        if not self.components:
            raise Error("cannot get extension of empty path", self.pos)

        last = self.components[-1]
        if isinstance(last, ConcatExpr):
            last = last.items[-1]
        if isinstance(last, LiteralExpr):
            dot = last.value.rfind(".")
            if dot != -1:
                return last.value[dot+1:]
            else:
                return ""

        raise Error("cannot determine extension of \"%s\"" % self, self.pos)

    def change_extension(self, newext):
        """
        Changes extension of the filename to *newext* and returns
        :class:`bkl.expr.PathExpr` with the new path.
        """
        if not self.components:
            raise Error("cannot change extension of empty path", self.pos)

        last = self.components[-1]
        if isinstance(last, ConcatExpr):
            last = last.items[-1]
        if not isinstance(last, LiteralExpr):
            raise Error("cannot change extension of \"%s\" to .%s" % (self, newext),
                        self.pos)

        dot = last.value.rfind(".")
        if dot != -1:
            tail = "%s.%s" % (last.value[:dot], newext)
        else:
            tail = "%s.%s" % (last.value, newext)

        comps = self.components[:-1] + [LiteralExpr(tail)]
        return PathExpr(comps, self.anchor, pos=self.pos)


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
    def null(self, e):
        """Called on :class:`NullExpr` expressions."""
        raise NotImplementedError

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

    @abstractmethod
    def bool_value(self, e):
        """Called on :class:`BoolValueExpr` expressions."""
        raise NotImplementedError

    @abstractmethod
    def bool(self, e):
        """Called on :class:`BoolExpr` expressions."""
        raise NotImplementedError

    @abstractmethod
    def if_(self, e):
        """Called on :class:`IfExpr` expressions."""
        raise NotImplementedError

    _dispatch = {
        NullExpr      : lambda self,e: self.null(e),
        LiteralExpr   : lambda self,e: self.literal(e),
        ListExpr      : lambda self,e: self.list(e),
        ConcatExpr    : lambda self,e: self.concat(e),
        ReferenceExpr : lambda self,e: self.reference(e),
        PathExpr      : lambda self,e: self.path(e),
        BoolValueExpr : lambda self,e: self.bool_value(e),
        BoolExpr      : lambda self,e: self.bool(e),
        IfExpr        : lambda self,e: self.if_(e),
    }

    #: Helper to quickly implement handler functions that do nothing.
    noop = lambda self, e: e

    def visit_children(self, e):
        """
        Helper to implement visitor methods that just need to recursively
        work on all children. Ignores return value for the children.
        """
        t = type(e)
        if t is ListExpr:
            for i in e.items: self.visit(i)
        elif t is ConcatExpr:
            for i in e.items: self.visit(i)
        elif t is PathExpr:
            for i in e.components: self.visit(i)
        elif t is BoolExpr:
            self.visit(e.left)
            if e.right is not None:
                self.visit(e.right)
        elif t is IfExpr:
            self.visit(e.cond)
            self.visit(e.value_yes)
            self.visit(e.value_no)


class PathAnchorsInfo(object):
    """
    Struct with information about real values for symbolic *anchors* of
    :class:`PathExpr` paths. These are needed in order to format path
    expression (using :class:`bkl.expr.Formatter` or otherwise).

    .. attribute:: dirsep

       Separator to separate path components ("/" on Unix and "\\" on Windows).

    .. attribute:: top_srcdir

       Path to the top source directory, as a list of components, relative
       to the output directory. Will be empty list if the paths are the same.

    .. attribute:: builddir

       Path to the build directory -- the directory where object files and
       other generated files are put -- as a list of components, relative
       to the output directory. Will be empty list if the paths are the same.

    .. attribute:: top_srcdir_abs

       Absolute native path to the top source directory.

    .. attribute:: outdir_abs

       Absolute native path to the output directory -- the directory where the
       project or makefile currently being generated is written to.

    .. attribute:: builddir_abs

       Absolute native path to the build directory.
    """
    def __init__(self, dirsep, outfile, builddir, model):
        """
        The constructor creates anchors information from native paths passed
        to it:

        :param dirsep:
                Path components separator, same as the :attr:`dirsep`
                attribute.

        :param outfile:
                (Native) path to the output file (project, makefile). Paths in
                the output will be typically formatted relatively to this path.
                The :attr:`outdir_abs` attribute is computed from this
                parameter.

        :param builddir:
                (Native) path to the build directory. May be None if
                builddir-relative paths make no sense in this context (e.g. for
                VS2010 solution files).

        :param model:
                Part of the model (:class:`bkl.model.Module` or
                :class:`bkl.model.Target`) that *outfile* corresponds to.
        """

        self.dirsep = dirsep
        outdir = os.path.dirname(os.path.abspath(outfile))
        self.outdir_abs = outdir

        top_srcdir = os.path.dirname(os.path.abspath(model.project.top_module.source_file))
        to_top_srcdir = os.path.relpath(top_srcdir, start=outdir)
        if to_top_srcdir == ".":
            self.top_srcdir = []
        else:
            self.top_srcdir = to_top_srcdir.split(os.path.sep)
        self.top_srcdir_abs = top_srcdir

        if builddir is not None:
            builddir = os.path.abspath(builddir)
            to_builddir = os.path.relpath(builddir, start=outdir)
            if to_builddir == ".":
                self.builddir = []
            else:
                self.builddir = to_builddir.split(os.path.sep)
            self.builddir_abs = builddir
        else:
            self.builddir = None
            self.builddir_abs = None


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

       :class:`PathAnchorsInfo` information object to use for formatting of paths.
    """
    list_sep = " "

    def __init__(self, paths_info):
        self.paths_info = paths_info

    def format(self, e):
        """
        Formats expression *e* into a string.
        """
        return self.visit(e)

    def null(self, e):
        return ""

    def literal(self, e):
        # FIXME: quote strings with whitespace in them
        return e.value

    def concat(self, e):
        # FIXME: quote strings with whitespace in them
        return "".join(self.format(e) for e in e.items)

    def list(self, e):
        return self.list_sep.join(self.format(e) for e in e.items)

    def path(self, e):
        pi = self.paths_info
        if e.anchor == ANCHOR_TOP_SRCDIR:
            base = pi.top_srcdir
            base_abs = pi.top_srcdir_abs
        elif e.anchor == ANCHOR_BUILDDIR:
            if pi.builddir is None:
                raise Error("%s anchor is unknown in this context (\"%s\")" % (e.anchor, e), pos=e.pos)
            base = pi.builddir
            base_abs = pi.builddir_abs
        else:
            assert False, "unknown path anchor (%s)" % e.anchor
        try:
            # Try to format the path without superfluous "..".
            abs_path = e.as_native_path(pi)
            rel_path = os.path.relpath(abs_path, start=pi.outdir_abs)
            return pi.dirsep.join(rel_path.split(os.path.sep))
        except NonConstError:
            # The path has some conditional elements, give up on formatting
            # it nicely.
            comps = [self.format(i) for i in e.components]
            return pi.dirsep.join(base + comps)

    def bool_value(self, e):
        raise NotImplementedError

    def bool(self, e):
        raise NotImplementedError

    def if_(self, e):
        # Default implementation evaluates the condition and prints
        # the value that the expression evals to, throwing if the condition
        # cannot be determined.
        return self.format(e.get_value())


class CondTrackingMixin:
    """
    Helper mixin class for tracking currently active condition.
    Useful for handling e.g. nested if statements.
    """

    active_if_cond = property(lambda self: self.if_stack[-1] if self.if_stack else None,
                              doc="Currently active condition, if any.")

    def __init__(self):
        self.if_stack = []

    def push_cond(self, cond):
        if self.active_if_cond is not None:
            # combine this condition with the outer 'if':
            cond = BoolExpr(BoolExpr.AND,
                            self.active_if_cond,
                            cond,
                            pos=cond.pos)
        self.if_stack.append(cond)

    def pop_cond(self):
        self.if_stack.pop()

    def reset_cond_stack(self):
        s = self.if_stack
        self.if_stack = []
        return s

    def restore_cond_stack(self, stack):
        assert not self.if_stack
        self.if_stack = stack


def split(e, sep):
    """
    Splits expression *e* into a list of expressions, using *sep* as the
    delimiter character. Works with conditional expressions and variable
    references too.
    """
    assert len(sep) == 1

    if isinstance(e, LiteralExpr):
        vals = e.value.split(sep)
        if len(vals) == 1:
            return [e]
        return [LiteralExpr(v, pos=e.pos) for v in vals]

    elif isinstance(e, ReferenceExpr):
        value_split = split(e.get_value(), sep)
        if len(value_split) == 1:
            return [e]
        else:
            return value_split

    elif isinstance(e, ConcatExpr):
        any_change = False
        out = []
        for i in e.items:
            i_out = split(i, sep)
            if i is not i_out:
                any_change = True
            if out:
                # Join the two lists on concatenation boundary. E.g. splitting
                # two concatenated strings "foo/bar" and "x/y" along "/" should
                # result in ["foo", "barx", "y"].
                out = ( out[:-1] +
                        [ConcatExpr([out[-1], i_out[0]])] +
                        i_out[1:] )
            else:
                out = i_out
        if any_change:
            return out
        else:
            return [e]

    elif isinstance(e, NullExpr) or isinstance(e, UndeterminedExpr):
        return [e]

    else:
        raise Error("don't know how to split expression \"%s\" with separator \"%s\""
                    % (e, sep),
                    pos = e.pos)


class _PossibleValuesVisitor(Visitor, CondTrackingMixin):
    def __init__(self):
        CondTrackingMixin.__init__(self)

    def null(self, e):
        return []

    def literal(self, e):
        return [(self.active_if_cond, e)]

    def bool_value(self, e):
        return [(self.active_if_cond, e)]

    def reference(self, e):
        return self.visit(e.get_value())

    def bool(self, e):
        assert False, "this should never be called"

    def if_(self, e):
        try:
            self.push_cond(e.cond)
            yes = self.visit(e.value_yes)
        finally:
            self.pop_cond()
        try:
            self.push_cond(BoolExpr(BoolExpr.NOT, e.cond, pos=e.cond.pos))
            no = self.visit(e.value_no)
        finally:
            self.pop_cond()
        return yes + no

    def list(self, e):
        # for lists, simply return the items, see enum_possible_values() docstring:
        items = []
        for x in e.items:
            items += self.visit(x)
        return items

    def _get_cond_for_list(self, lst):
            conds = [c for c,e in lst if c is not None]
            if conds:
                if len(conds) > 1:
                    raise ParserError("too complicated conditional expression, please report this as a bug", pos=e.pos)
                else:
                    return conds[0]
            else:
                return None

    def concat(self, e):
        items = [self.visit(x) for x in e.items]
        items = [x for x in items if x] # filter out nulls
        out = []
        for result in itertools.product(*items):
            cond = self._get_cond_for_list(result)
            out.append((cond, ConcatExpr([e for c,e in result], pos=e.pos)))
        return out

    def path(self, e):
        components = [self.visit(x) for x in e.components]
        components = [x for x in components if x] # filter out nulls
        out = []
        for result in itertools.product(*components):
            cond = self._get_cond_for_list(result)
            out.append((cond, PathExpr([e for c,e in result], anchor=e.anchor, pos=e.pos)))
        return out


def enum_possible_values(e, global_cond=None):
    """
    Returns all values that are possible, together with their respective
    conditions, as an iteratable of (condition, value) tuples. The condition
    may be :const:`None` if the value is always there, otherwise it is a
    boolean :class:`bkl.expr.Expr`.

    Note that this function returns possible elements for lists. It skips null
    expressions as well.

    :param e:
            Expression to extract possible values from.
    :param global_cond:
            Optional condition expression (:class:`bkl.expr.Expr`) to apply to
            all items. If specified, then every tuple in returned list will
            have the condition set to either *global_cond* (for unconditional
            items) or its combination with per-item condition.
    """
    v = _PossibleValuesVisitor()
    if global_cond is not None:
        v.push_cond(global_cond)
    return v.visit(e)


def are_equal(a, b):
    """
    Compares two expressions for equality.

    Throws the CannotDetermineError exception if it cannot reliably
    determine equality.
    """
    try:
        # FIXME: This is not good enough, the comparison should be done
        #        symbolically as much as possible.
        return a.as_py() == b.as_py()
    except NonConstError:
        raise CannotDetermineError


def add_prefix(prefix, e):
    """
    Adds a *prefix* in front of the expression *e* or, if *e* is a list,
    in front of each of its elements.

    :param prefix:
            The prefix to add; either an :class:`bkl.expr.Expr` object or
            a string.

    :param e:
            The expression to add the prefix in front of.
    """
    if not isinstance(prefix, Expr):
        prefix = LiteralExpr(prefix)

    if isinstance(e, ListExpr):
        return ListExpr([add_prefix(prefix, i) for i in e.items], pos=e.pos)
    else:
        return ConcatExpr([prefix, e], pos=e.pos)


def concat(*parts):
    """
    Concatenates all arguments and returns :class:`bkl.expr.ConcatExpr`.
    The arguments may be expressions or string literals.
    """
    items = []
    for p in parts:
        if not isinstance(p, Expr):
            p = LiteralExpr(p)
        items.append(p)
    return ConcatExpr(items)
