#coding: utf-8
#
#  This file is part of Bakefile (http://bakefile.org)
#
#  Copyright (C) 2008-2018 Vaclav Slavik
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
import re
from abc import ABCMeta, abstractmethod

from error import NonConstError, CannotDetermineError, ParserError, Error, error_context, warning


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

    def is_null(self):
        """
        Returns true if the expression evaluates to null, i.e. empty value.
        """
        try:
            py = self.as_py()
            return py is None or py == [] # [] is effectively None
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

    def as_symbolic(self):
        """
        Returns the value as a symbolic representation, see SymbolicFormatter.
        """
        return SymbolicFormatter().format(self)

    def __nonzero__(self):
        # Derived expression classes should override this to make testing for
        # non-empty values ("if expr:") work without the need to call as_py().
        raise NotImplementedError

    def __eq__(self, other):
        return are_equal(self, other)

    def __ne__(self, other):
        return not are_equal(self, other)


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

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

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
        items = (i.as_py() for i in self.items)
        return "".join(i for i in items if i is not None)

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

    def __len__(self):
        return 0

    def __iter__(self):
        return iter([])

    def __str__(self):
        return "null"


class PlaceholderExpr(Expr):
    """
    This is a hack. It is used as placeholder for expressions with not yet known value.
    In particular, it is used for the "toolset" property before the model is split into
    toolset-specific copies, to allow partial evaluation common to all of them.

    .. attribute:: var

       Name of referenced setting (e.g. "config" or "toolset").
    """
    def __init__(self, var, pos=None):
        super(PlaceholderExpr, self).__init__(pos)
        self.var = var

    def as_py(self):
        raise NonConstError(self)

    def __str__(self):
        return "${%s}" % self.var


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

    def get_variable(self):
        """
        Return the variable object this reference points to.

        Use this method only if necessary; whenever possible,
        :meth:`get_value()` should be used instead.

        Note that the returned value may be None, either if the referenced
        variable doesn't exist or when the reference is to a property that
        wasn't explicitly set and uses the default value.
        """
        with error_context(self):
            return self.context.resolve_variable(self.var)

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
                return are_equal(self.left, self.right, _inside_cond=True)
            except CannotDetermineError:
                raise CannotDetermineError('cannot evaluate bool expression "%s"' % self, self.pos)
        elif op == BoolExpr.NOT_EQUAL:
            try:
                return not are_equal(self.left, self.right, _inside_cond=True)
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
        return self.get_value().as_py()

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
            return bool(self.get_value())
        except NonConstError:
            return bool(self.value_yes) or bool(self.value_no)

    def __len__(self):
        return len(self.get_value())

    def __iter__(self):
        return iter(self.get_value())

    def __str__(self):
        return "(%s ? %s : %s)" % (self.cond, self.value_yes, self.value_no)


# anchors -- special syntax first components of a path
ANCHOR_SRCDIR = "@srcdir"
ANCHOR_TOP_SRCDIR = "@top_srcdir"
ANCHOR_BUILDDIR = "@builddir"
ANCHOR_TOP_BUILDDIR = "@top_builddir"

# all possible anchors
ANCHORS = [ANCHOR_SRCDIR, ANCHOR_TOP_SRCDIR, ANCHOR_BUILDDIR, ANCHOR_TOP_BUILDDIR]

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
         the input bakefile is (unless overridden in it).

       * ``expr.ANCHOR_TOP_SRCDIR`` -- Path is relative to the top
         source directory (where the toplevel ``.bkl`` file is, unless
         overridden in it).

       * ``expr.ANCHOR_BUILDDIR`` -- Path is relative to the build directory.
         Either this anchor or ``expr.ANCHOR_TOP_BUILDDIR`` should be used for
         all transient files (object files or other generated files).

       * ``expr.ANCHOR_TOP_BUILDDIR`` -- Path is relative to the top build
         directory. This is currently only used by makefile backends where the
         build directory for a sub-makefile is different from the top one.

    .. attribute:: anchor_file

       Name of the file the anchor was written in. This is important for @srcdir,
       which is relative to this place.

    .. attribute:: pos

       Location of the expression in source tree.
    """
    def __init__(self, components, anchor=ANCHOR_SRCDIR, anchor_file=None, pos=None):
        super(PathExpr, self).__init__(pos)
        if anchor_file is None and pos is not None:
            anchor_file = pos.filename
        self.components = components
        self.anchor = anchor
        self.anchor_file = anchor_file

    def as_py(self):
        # We can't represent a path as something natively useful (e.g. native
        # path), so let's return a representation in bakefile language,
        # with explicit anchor:
        return "%s/%s" % (self.anchor, "/".join(x.as_py() for x in self.components))

    def __nonzero__(self):
        return bool(self.components)

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
        comp = (e.as_py().encode('utf-8') for e in self.components)
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
        top_srcdir = model.project.top_module.srcdir
        comp = (e.as_py() for e in self.components)
        return os.path.join(top_srcdir, os.path.sep.join(comp))

    def get_directory_path(self):
        """
        Returns PathExpr with the directory component.
        """
        return PathExpr(self.components[:-1], anchor=self.anchor, anchor_file=self.anchor_file)

    def get_basename(self):
        """
        Returns basename of the filename path (i.e. the name without directory
        or extension). Throws if it cannot be determined.
        """
        if not self.components:
            raise Error("cannot get basename of empty path", self.pos)

        last = self.components[-1]
        try:
            value = last.as_py()
            dot = value.rfind(".")
            return value[:dot] if dot != -1 else value
        except NonConstError:
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

        raise CannotDetermineError("cannot determine extension of \"%s\"" % self, self.pos)

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
        return PathExpr(comps, self.anchor, self.anchor_file, pos=self.pos)

    def is_external_absolute(self):
        """
        Returns true if the path is to be treated as an absolute path provided
        externally (i.e. via an user setting) when the makefile was invoked.

        TODO: add a @absdir anchor instead?
        """
        if self.anchor in [ANCHOR_BUILDDIR, ANCHOR_TOP_BUILDDIR] or not self.components:
            return False
        first = self.components[0]
        return isinstance(first, PlaceholderExpr)


class Visitor(object):
    """
    Implements visitor pattern for :class:`Expr` expressions. This is abstract
    base class, derived classes must implement all of its methods except
    :meth:`visit()`. The way visitors are used is that the caller calls
    :meth:`visit()` on the expression.
    """
    __metaclass__ = ABCMeta

    def __init__(self):
        self._dispatch = {
            NullExpr         : self.null,
            LiteralExpr      : self.literal,
            ListExpr         : self.list,
            ConcatExpr       : self.concat,
            ReferenceExpr    : self.reference,
            PlaceholderExpr  : self.placeholder,
            PathExpr         : self.path,
            BoolValueExpr    : self.bool_value,
            BoolExpr         : self.bool,
            IfExpr           : self.if_,
        }

    def visit(self, e):
        """
        Call this method to visit expression *e*. One of object's "callback"
        methods will be called, depending on *e*'s type.

        Return value is the value returned by the appropriate callback and
        is typically :const:`None`.
        """
        return self._dispatch[type(e)](e)

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
    def placeholder(self, e):
        """Called on :class:`PlaceholderExpr` expressions."""
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


class RewritingVisitor(Visitor):
    """
    Base class for visitors that perform some changes to the expression.

    RewritingVisitor is smart about the rewrites and if nothing changes,
    returns the same instance, instead of creating an identical copy.

    It also implements all Visitor methods to do the right thing by default, so
    you only need to override the ones that are of interest. Default
    implementations of the others will do the right thing: for example, if an
    item in the list is rewritten, the list() method will detect it and return
    a new list.
    """

    def _process_children(self, children):
        """
        Process all items from the *children* list. Returns a tuple of two
        items: the first one is the new list of items, the second one is a
        boolean value indicating whether anything changed.
        """
        new = []
        changed = False
        for i in children:
            j = self.visit(i)
            if i is not j:
                changed = True
            if isinstance(j, NullExpr):
                changed = True
            else:
                new.append(j)
        if not changed:
            new = children
        return (new, changed)

    bool_value = Visitor.noop
    literal = Visitor.noop
    null = Visitor.noop
    reference = Visitor.noop
    placeholder = Visitor.noop

    def list(self, e):
        new, changed = self._process_children(e.items)
        if not changed:
            return e
        return ListExpr(new, pos=e.pos)

    def concat(self, e):
        # merge concatenated literals:
        items, changed = self._process_children(e.items)
        if not changed:
            return e
        return ConcatExpr(items, pos=e.pos)

    def path(self, e):
        components, changed = self._process_children(e.components)
        if not changed:
            return e
        return PathExpr(components, e.anchor, e.anchor_file, pos=e.pos)

    def bool(self, e):
        left = self.visit(e.left)
        right = None if e.right is None else self.visit(e.right)
        if left is e.left and right is e.right:
            return e
        return BoolExpr(e.operator, left, right, pos=e.pos)

    def if_(self, e):
        cond = self.visit(e.cond)
        yes = self.visit(e.value_yes)
        no = self.visit(e.value_no)
        if cond is e.cond and yes is e.value_yes and no is e.value_no:
            return e
        return IfExpr(cond, yes, no, pos=e.pos)


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
        outdir = os.path.dirname(os.path.abspath(outfile.encode('utf-8')))
        self.outdir_abs = outdir

        top_srcdir = os.path.abspath(model.project.top_module.srcdir)
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
        super(Formatter, self).__init__()
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
        if e.is_external_absolute():
            # The path is absolute and begins with a reference, so we don't
            # need to determine a "nice" relative path for it.
            return pi.dirsep.join([self.format(i) for i in e.components])
        if e.anchor == ANCHOR_TOP_SRCDIR:
            base = pi.top_srcdir
        elif e.anchor == ANCHOR_BUILDDIR:
            if pi.builddir is None:
                raise Error("%s anchor is unknown in this context (\"%s\")" % (e.anchor, e), pos=e.pos)
            base = pi.builddir
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

    def reference(self, e):
        return self.format(e.get_value())


class SymbolicFormatter(Formatter):
    """
    Formats into unambiguous symbolic representation of the expression.
    """
    def __init__(self):
        super(SymbolicFormatter, self).__init__(None)

    def null(self, e):
        return "Null()"

    def literal(self, e):
        return "Literal(\"%s\")" % e.value

    def concat(self, e):
        return "Concat(%s)" % ",".join(self.format(x) for x in e.items)

    def list(self, e):
        return "List(%s)" % ",".join(self.format(x) for x in e.items)

    def path(self, e):
        return "Path(%s,%s)" % (e.anchor, ",".join(self.format(x) for x in e.components))

    def bool_value(self, e):
        return "True()" if e.value else "False()"

    def bool(self, e):
        if e.right is None:
            return "Bool(%s%s)" % (e.operator, self.format(e.left))
        else:
            return "Bool(%s %s %s)" % (self.format(e.left), e.operator, self.format(e.right))

    def if_(self, e):
        return "If(%s,%s,%s)" % (self.format(e.cond), self.format(e.value_yes), self.format(e.value_no))

    def placeholder(self, e):
        return "Placeholder(%s)" % e.var


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



class _SplitVisitor(Visitor):
    """
    Helper for the split() function.
    """
    def __init__(self, sep):
        super(_SplitVisitor, self).__init__()
        self.sep = sep

    bool = lambda self, e: [e]
    bool_value = lambda self, e: [e]
    null = lambda self, e: [e]
    placeholder = lambda self, e: [e]

    def literal(self, e):
        vals = e.value.split(self.sep)
        if len(vals) == 1:
            return [e]
        return [LiteralExpr(v, pos=e.pos) for v in vals]

    def reference(self, e):
        vals = self.visit(e.get_value())
        if len(vals) == 1:
            return [e]
        else:
            return vals

    def list(self, e):
        new = [self.visit(x) for x in e.items]
        return ListExpr(new, pos=e.pos)

    def concat(self, e):
        any_change = False
        out = []
        for i in e.items:
            i_out = self.visit(i)
            if i is not i_out:
                any_change = True
            if out:
                # Join the two lists on concatenation boundary. E.g. splitting
                # two concatenated strings "foo/bar" and "x/y" along "/" should
                # result in ["foo", "barx", "y"].
                middle_1 = out[-1]
                middle_2 = i_out[0]
                middle = []
                if not (isinstance(middle_1, LiteralExpr) and not middle_1):
                    middle.append(middle_1)
                if not (isinstance(middle_2, LiteralExpr) and not middle_2):
                    middle.append(middle_2)
                if len(middle) > 1:
                    middle = [ConcatExpr(middle)]
                out = out[:-1] + middle + i_out[1:]
            else:
                out = i_out
        if any_change:
            return out
        else:
            return [e]

    def path(self, e):
        raise Error("can't split a path", pos=e.pos)

    def if_(self, e):
        yes = self.visit(e.value_yes)
        no = self.visit(e.value_no)
        if len(yes) == 1 and len(no) == 1:
            return [e]
        elif len(yes) == len(no):
            return [IfExpr(e.cond, yes[i], no[i], pos=e.pos) for i in xrange(0, len(yes))]
        else:
            raise Error("conditional value \"%s\" cannot be split with \"%s\", true and false branches have different lengths" % (e, self.sep))


def split(e, sep):
    """
    Splits expression *e* into a list of expressions, using *sep* as the
    delimiter character. Works with conditional expressions and variable
    references too.
    """
    assert len(sep) == 1
    with error_context(e):
        return _SplitVisitor(sep).visit(e)


class _SplitIntoPathVisitor(_SplitVisitor):
    """
    Helper for the split_into_path() function.
    """
    def __init__(self):
        super(_SplitIntoPathVisitor, self).__init__('/')
        self.anchor = ANCHOR_SRCDIR
        self.anchor_file = None
        self.anchor_set = False

    def literal(self, e):
        if '\\' in e.value:
            warning("'\\' is not path separator in bakefiles (use '/')", pos=e.pos)
        return super(_SplitIntoPathVisitor, self).literal(e)

    def list(self, e):
        raise Error("list can't be a part of a path")

    def path(self, e):
        if not self.anchor_set:
            self.anchor = e.anchor
            self.anchor_file = e.anchor_file
            self.anchor_set = True
            return e.components
        else:
            raise Error("can't embed a path in another")

    def reference(self, e):
        had_anchor = self.anchor_set
        vals = self.visit(e.get_value())
        if not had_anchor and self.anchor_set:
            # referenced path must be always substituted, can't have
            # a PathExpr as a component
            return vals
        elif len(vals) == 1:
            return [e]
        else:
            return vals


def split_into_path(e):
    """
    Splits expression *e* into a list of expressions, using '/' as the
    delimiter character. Returns a PathExpr.  Works with conditional
    expressions and variable references too.
    """
    with error_context(e):
        visitor = _SplitIntoPathVisitor()
        components = visitor.visit(e)
        # filter out empty components (e.g. "foo//bar.c")
        components = [x for x in components
                      if not isinstance(x, LiteralExpr) or x.value]
        return PathExpr(components,
                        anchor=visitor.anchor, anchor_file=visitor.anchor_file,
                        pos=e.pos)


class _ModelNameFromPathVisitor(Visitor):
    """
    Helper for the get_model_name_from_path() function.
    """
    bool = Visitor.noop
    bool_value = Visitor.noop
    null = Visitor.noop

    def placeholder(self, e):
        raise NotImplementedError

    def literal(self, e):
        return e.value

    def reference(self, e):
        return self.visit(e.get_value())

    def list(self, e):
        raise NotImplementedError

    def concat(self, e):
        return "".join(self.visit(x) for x in e.items)

    def path(self, e):
        p = "/".join(self.visit(x) for x in e.components)
        if e.anchor == ANCHOR_SRCDIR:
            return p
        else:
            return "%s/%s" % (e.anchor, p)

    def if_(self, e):
        return self.visit(e.get_value())


def get_model_name_from_path(e):
    """
    Give an expression representing filename, return name suitable for
    model.SourceFile.name.
    """
    with error_context(e):
        return _ModelNameFromPathVisitor().visit(e)


class _KeepPossibleValuesUnexpandedVisitor(Visitor):
    """
    Visitor determining if a reference should be expanded when determining its
    possible values.

    The rule is that anything inside the reference expansion that doesn't end
    up being a simple value should result in the top level visit() returning
    :const:`False`.
    """
    def null(self, e):
        return True

    def literal(self, e):
        return True

    def list(self, e):
        return False

    def concat(self, e):
        for x in e.items:
            if not self.visit(x):
                return False
        return True

    def reference(self, e):
        return self.visit(e.get_value())

    def placeholder(self, e):
        return False

    def path(self, e):
        for x in e.components:
            if not self.visit(x):
                return False
        return True

    def bool_value(self, e):
        return True

    def bool(self, e):
        return True

    def if_(self, e):
        return False

def keep_possible_values_unexpanded(e):
    """
    Determines if the given reference value should be expanded or not.

    This is a helper of enum_possible_values() and is used to decide whether
    a value returned by that function is fully expanded or kept in its
    original form, with variable references in it. The latter is useful when
    dealing with the source files containing variables as it prevents them
    from being expanded too early, before the variable value for the current
    target is really known.

    However anything not representing a simple single value should still be
    expanded and this function task is to check whether the argument is a
    reference to such simple single value or not.
    """
    v = _KeepPossibleValuesUnexpandedVisitor()
    return v.visit(e)


class _PossibleValuesVisitor(Visitor, CondTrackingMixin):
    def __init__(self):
        Visitor.__init__(self)
        CondTrackingMixin.__init__(self)
        self.inside_a_value = 0

    def null(self, e):
        return []

    def literal(self, e):
        return [(self.active_if_cond, e)]

    def bool_value(self, e):
        return [(self.active_if_cond, e)]

    def reference(self, e):
        if keep_possible_values_unexpanded(e):
            return [(self.active_if_cond, e)]
        return self.visit(e.get_value())

    def placeholder(self, e):
        return [(self.active_if_cond, e)]

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

    def _get_cond_for_list_without_current(self, lst):
            conds = set(c for c,e in lst if c is not None)
            if conds:
                if len(conds) > 1:
                    # construct intersection of all the conditions
                    combined = BoolExpr(BoolExpr.AND, conds.pop(), conds.pop())
                    while conds:
                        combined = BoolExpr(BoolExpr.AND, combined, conds.pop())
                    return combined
                else:
                    return conds.pop()
            else:
                return None

    def _get_cond_for_list(self, lst):
            c = self._get_cond_for_list_without_current(lst)
            if c is None:
                return self.active_if_cond
            else:
                try:
                    self.push_cond(c)
                    return self.active_if_cond
                finally:
                    self.pop_cond()

    def concat(self, e):
        try:
            self.inside_a_value += 1
            items = [self.visit(x) for x in e.items]
            items = [x for x in items if x] # filter out nulls
            out = []
            for result in itertools.product(*items):
                cond = self._get_cond_for_list(result)
                out.append((cond, ConcatExpr([x for c,x in result], pos=e.pos)))
            return out
        finally:
            self.inside_a_value -= 1

    def path(self, e):
        try:
            self.inside_a_value += 1
            components = [self.visit(x) for x in e.components]
            components = [x for x in components if x] # filter out nulls
            out = []
            for result in itertools.product(*components):
                cond = self._get_cond_for_list(result)
                out.append((cond, PathExpr([x for c,x in result], anchor=e.anchor, anchor_file=e.anchor_file, pos=e.pos)))
            return out
        finally:
            self.inside_a_value -= 1

    def list(self, e):
        # for lists, simply return the items, see enum_possible_values() docstring,
        # but not when they are used in some sort of a literal (e.g. inside a command
        # string, i.e. within ConcatExpr):
        if self.inside_a_value:
            items = [self.visit(x) for x in e.items]
            items = [x for x in items if x] # filter out nulls
            out = []
            for result in itertools.product(*items):
                cond = self._get_cond_for_list(result)
                out.append((cond, ListExpr([x for c,x in result], pos=e.pos)))
            return out
        else:
            items = []
            for x in e.items:
                items += self.visit(x)
            return items


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



class _PrepForAsPyComparisonVisitor(RewritingVisitor):
    # Prepares the expression for are_equal()'s comparison.
    # FIXME: This is a hack in absence of symbolic comparison. The problem is
    #        that as_py() will throw on PlaceholderExpr (such as "$(config)")
    #        and not even enum_possible_values() would help.
    #        A good enough (for now at least) solution is to mark the
    #        placeholders up with something highly unusual and not likely to
    #        ever appear -- such as lenticular brackets Unicode characters.
    def __init__(self):
        super(_PrepForAsPyComparisonVisitor, self).__init__()
        self.inside_cond = 0

    def placeholder(self, e):
        if self.inside_cond:
            return e
        else:
            return LiteralExpr(u"〖%s〗" % e.var)

    def reference(self, e):
        return self.visit(e.get_value())

    def if_(self, e):
        try:
            self.inside_cond += 1
            cond = self.visit(e.cond)
        finally:
            self.inside_cond -= 1
        yes = self.visit(e.value_yes)
        no = self.visit(e.value_no)
        if cond is e.cond and yes is e.value_yes and no is e.value_no:
            return e
        return IfExpr(cond, yes, no, pos=e.pos)


def are_equal(a, b, _inside_cond=False):
    """
    Compares two expressions for equality.

    Throws the CannotDetermineError exception if it cannot reliably
    determine equality.
    """
    a_is_expr = isinstance(a, Expr)
    b_is_expr = isinstance(b, Expr)
    try:
        # FIXME: This is not good enough, the comparison should be done
        #        symbolically as much as possible.
        vis = _PrepForAsPyComparisonVisitor()
        if _inside_cond:
            vis.inside_cond += 1
        a2 = vis.visit(a).as_py() if a_is_expr else a
        b2 = vis.visit(b).as_py() if b_is_expr else b
        return a2 == b2
    except NonConstError:
        if a_is_expr and b_is_expr and a.as_symbolic() == b.as_symbolic():
            return True
        # else: inconclusive
        # TODO: Try exploding with enum_possible_values()
        raise CannotDetermineError("cannot determine whether the following two expressions are equal: \"%s\" and \"%s\"; please report this as a bug." % (a,b))


class _AddPrefixVisitor(RewritingVisitor):
    def __init__(self, prefix):
        super(_AddPrefixVisitor, self).__init__()
        self.prefix = prefix

    def _add(self, e):
        return ConcatExpr([self.prefix, e], pos=e.pos)

    placeholder = _add
    literal = _add
    path = _add
    bool_value = _add

    def null(self, e):
        return e # don't add prefix to empty string

    def reference(self, e):
        return self.visit(e.get_value())

    def if_(self, e):
        yes = self.visit(e.value_yes)
        no = self.visit(e.value_no)
        return IfExpr(e.cond, yes, no, pos=e.pos)

    def concat(self, e):
        return ConcatExpr([self.prefix] + e.items, pos=e.pos)

    def bool(self, e):
        raise NotImplementedError


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
        return _AddPrefixVisitor(prefix).visit(e)


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


class _FormatStringVisitor(RewritingVisitor):
    def __init__(self, values):
        super(_FormatStringVisitor, self).__init__()
        self.values = values

    def literal(self, expr):
        # Find %(...) substrings in the literal and split the string into
        # components. The resulting list will start with (possibly empty)
        # string that should be preserved verbatim, followed by the name of the
        # variable to be substituted, followed by verbatim string and so on.
        #
        # For example:
        #  input: '%(in) and %(out) arguments'
        #  parts = ['', 'in', ' and ', 'out', ' arguments']
        if not expr.value:
            return expr
        parts = re.split(r'%\(([^)]*)\)', expr.value)
        out = []
        is_subst = False
        for part in parts:
            if is_subst:
                try:
                    repl = self.values[part]
                    if not isinstance(repl, Expr):
                        repl = LiteralExpr(repl)
                    out.append(repl)
                except KeyError:
                    raise Error("unknown substitution key \"%s\" in format string" % part, expr.pos)
            elif part:
                out.append(LiteralExpr(part))
            is_subst = not is_subst
        return ConcatExpr(out, pos=expr.pos)

def format_string(format, values):
    """
    Substitutes occurrences of "%(varname)" in the *format* string with values
    from the dictionary *values*, similarly to the '%' operator. Values in the
    dictionary may be either Expr objects or strings.

    Note that there's currently no way to escape "%" in such expressions.
    """
    return _FormatStringVisitor(values).visit(format)
