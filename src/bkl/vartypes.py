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
This module defines types interface as well as basic types. The types -- i.e.
objects derived from :class:`bkl.vartypes.Type` -- are used to verify validity
of variable values and other expressions.
"""

import types
import expr
from error import TypeError


#: Boolean value of "true".
TRUE = "true"
#: Boolean value of "false".
FALSE = "false"


class Type(object):
    # FIXME: we ma want to derive this from api.Extension, but it only makes
    # sense if specifying types in the code ("e.g. foo as string = ... ")
    """
    Base class for all Bakefile types.

    .. attribute:: name

       Human-readable name of the type, e.g. "path" or "bool".
    """

    name = None

    def validate(self, e):
        """
        Validates if the expression *e* is of this type. If it isn't, throws
        :exc:`bkl.error.TypeError` with description of the error.
        """
        raise NotImplementedError



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
    allowed_values = [TRUE, FALSE]

    def validate(self, e):
        if isinstance(e, expr.ConstExpr):
            if e.value not in self.allowed_values:
                raise TypeError(self, e)
        else:
            # FIXME: boolean operations produce bools too
            # FIXME: allow references
            raise TypeError(self, e)



class IdType(Type):
    """
    Type for target IDs.
    """

    name = "id"

    def validate(self, e):
        if not isinstance(e, expr.ConstExpr):
            raise TypeError(self, e)
        # FIXME: allow references
        # FIXME: needs to check that the value is a known ID



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
        self.allowed_values = allowed_values


    def validate(self, e):
        if isinstance(e, expr.ConstExpr):
            if e.value not in self.allowed_values:
                raise TypeError(self, e,
                                msg="must be one of %s" % self.allowed_values)
        # FIXME: allow references
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


    def validate(self, e):
        if isinstance(e, expr.ListExpr):
            for i in e.items:
                self.item_type.validate(i)
        else:
            raise TypeError(self, e)
