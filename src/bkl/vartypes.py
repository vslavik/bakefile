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
This module defines types interface as well as basic types. The types -- i.e.
objects derived from :class:`bkl.vartypes.Type` -- are used to verify validity
of variable values and other expressions.
"""

import types

import expr
from error import TypeError


class Type(object):
    # FIXME: we may want to derive this from api.Extension, but it only makes
    # sense if specifying types in the code ("e.g. foo as string = ... ")
    """
    Base class for all Bakefile types.

    .. attribute:: name

       Human-readable name of the type, e.g. "path" or "bool".
    """
    name = None

    def normalize(self, e):
        """
        Normalizes the expression *e* to be of this type, if it can be done.
        If it cannot be, does nothing.

        Returns *e* if no normalization was done or a new expression with
        normalized form of *e*.
        """
        if isinstance(e, expr.IfExpr):
            yes = self.normalize(e.value_yes)
            no = self.normalize(e.value_no)
            if yes is e.value_yes and no is e.value_no:
                return e
            else:
                return expr.IfExpr(e.cond, yes, no, pos=e.pos)
        else:
            return self._normalize_impl(e)

    def _normalize_impl(self, e):
        # Implementation of normalize(), to be overriden in derived classes.
        # Conditional expressions are handled transparently by normalize().
        # by default, no normalization is done:
        return e

    def validate(self, e):
        """
        Validates if the expression *e* is of this type. If it isn't, throws
        :exc:`bkl.error.TypeError` with description of the error.

        Note that this method transparently handles references and conditional
        expressions.
        """
        try:
            if isinstance(e, expr.NullExpr):
                # Null expression is rarely a valid value, but it can happen all
                # over the place due to conditional processing
                pass
            elif isinstance(e, expr.ReferenceExpr):
                try:
                    # FIXME: Compare referenced var's type with self, do this only if
                    #        it is AnyType. Need to handle type promotion then as well.
                    self.validate(e.get_value())
                except TypeError as err:
                    # If the error happened in a referenced variable, then
                    # it's location is not interesting -- we want to report
                    # the error at the place where validation was requested.
                    # FIXME: push the old location on a stack instead?
                    err.pos = None
                    raise
            elif isinstance(e, expr.IfExpr):
                self.validate(e.value_yes)
                self.validate(e.value_no)
            elif isinstance(e, expr.UndeterminedExpr):
                raise TypeError(self, e, "value not determinable")
            else:
                # finally, perform actual type-specific validation:
                self._validate_impl(e)
        except TypeError as err:
            if e.pos and not err.pos:
                err.pos = e.pos
            raise

    def _validate_impl(self, e):
        # Implementation of validate(), to be overriden in derived classes.
        # Conditonal expressions and references are handled transparently by
        # Type.validate(), so you don't have to worry about that when
        # implementing _validate_impl().
        raise NotImplementedError

    def __str__(self):
        return self.name


class AnyType(Type):
    """
    A fallback type that allows any value at all.
    """
    name = "any"

    def validate(self, e):
        pass # anything is valid


class BoolType(Type):
    """
    Boolean value type. May be product of a boolean expression or one of the
    following literals with obvious meanings: "true" or "false".
    """
    name = "bool"

    TRUE  = "true"
    FALSE = "false"
    allowed_values = [TRUE, FALSE]

    def _normalize_impl(self, e):
        if isinstance(e, expr.LiteralExpr):
            return expr.BoolValueExpr(e.value == self.TRUE)
        else:
            return e

    def _validate_impl(self, e):
        if isinstance(e, expr.LiteralExpr):
            if e.value not in self.allowed_values:
                raise TypeError(self, e)
        elif isinstance(e, expr.BoolExpr):
            return
        elif isinstance(e, expr.BoolValueExpr):
            return
        else:
            raise TypeError(self, e)


class StringType(Type):
    """
    Any string value.
    """
    name = "string"

    def _validate_impl(self, e):
        if isinstance(e, expr.ConcatExpr):
            # concatenation of strings is a string
            for x in e.items:
                self.validate(x)
        elif not isinstance(e, expr.LiteralExpr):
            raise TypeError(self, e)


class IdType(Type):
    """
    Type for target IDs.
    """
    name = "id"

    def _validate_impl(self, e):
        if not isinstance(e, expr.LiteralExpr):
            raise TypeError(self, e)
        # FIXME: needs to check that the value is a known ID


class PathType(Type):
    """
    A file or directory name.
    """
    name = "path"

    def _normalize_impl(self, e):
        if isinstance(e, expr.PathExpr):
            return e

        components = expr.split(e, "/")
        if not components:
            return e # empty path = invalid
        first = components[0]
        if (isinstance(first, expr.LiteralExpr) and
                first.value and first.value[0] == "@"):
            anchor = first.value
            return expr.PathExpr(components[1:], anchor, pos=e.pos)
        else:
            return expr.PathExpr(components, pos=e.pos)

    def _validate_impl(self, e):
        if not isinstance(e, expr.PathExpr):
            raise TypeError(self, e)
        else:
            if e.anchor not in expr.ANCHORS:
                raise TypeError(self, e,
                                msg='invalid anchor "%s"' % e.anchor)
            component_type = StringType()
            for c in e.components:
                component_type.validate(c)


class EnumType(Type):
    """
    Enum type. The value must be one of allowed values passed to the
    constructor.

    .. attribute:: allowed_values

       List of allowed values (strings).
    """
    name = "enum"

    def __init__(self, allowed_values):
        assert allowed_values, "list of values cannot be empty"
        self.allowed_values = [unicode(x) for x in allowed_values]

    def _validate_impl(self, e):
        if isinstance(e, expr.LiteralExpr):
            assert isinstance(e.value, types.UnicodeType)
            if e.value not in self.allowed_values:
                raise TypeError(self, e,
                                msg="must be one of %s" %
                                [str(x) for x in self.allowed_values])
        else:
            raise TypeError(self, e)


class ListType(Type):
    """
    Type for a list of items of homogeneous type.

    .. attribute:: item_type

       Type of items stored in the list (:class:`bkl.vartypes.Type` instance).
    """
    def __init__(self, item_type):
        self.item_type = item_type
        self.name = "list of %s" % item_type.name

    def _normalize_impl(self, e):
        # A non-list expression with single value is a special case of list
        # for convenience, we translate it into single-item list automagically:
        if isinstance(e, expr.ListExpr):
            return expr.ListExpr([self.item_type.normalize(i) for i in e.items], pos=e.pos)
        else:
            return expr.ListExpr([self.item_type.normalize(e)], pos=e.pos)

    def _validate_impl(self, e):
        if isinstance(e, expr.ListExpr):
            for i in e.items:
                self.item_type.validate(i)
        else:
            raise TypeError(self, e)


def guess_expr_type(e):
    """
    Attempts to guess type of the expression if it's possible.
    Returns AnyType type if unsure.
    """
    if isinstance(e, expr.PathExpr):
        return PathType()
    if isinstance(e, expr.ListExpr):
        return ListType(AnyType())
    return AnyType()


class _BoolNormalizer(expr.Visitor):
    literal = expr.Visitor.noop
    bool_value = expr.Visitor.noop
    null = expr.Visitor.noop
    reference = expr.Visitor.noop

    concat = expr.Visitor.visit_children
    list = expr.Visitor.visit_children
    path = expr.Visitor.visit_children

    _bool_type = BoolType()
    
    def bool(self, e):
        self.visit_children(e)
        if e.has_bool_operands():
            e.left = self._bool_type.normalize(e.left)
            self._bool_type.validate(e.left)
            if e.right is not None:
                e.right = self._bool_type.normalize(e.right)
                self._bool_type.validate(e.right)

    def if_(self, e):
        self.visit_children(e)
        e.cond = self._bool_type.normalize(e.cond)
        self._bool_type.validate(e.cond)


def normalize_and_validate_bool_subexpressions(e):
    """
    Performs type normalization and validation steps for typed subexpressions,
    namely for IfExpr conditions and boolean expressions.
    """
    _BoolNormalizer().visit(e)
