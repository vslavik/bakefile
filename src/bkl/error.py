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
This module contains helper classes for simple handling of errors. In
particular, the :exc:`Error` class keeps track of the position in source code
where the error occurred or to which it relates to.
"""

class Error(Exception):
    """
    Base class for all Bakefile errors.

    When converted to string, the message is formatted in the usual way of
    compilers, as ``file:line: error``.

    .. attribute:: msg

        Error message to show to the user.

    .. attribute:: pos

        :class:`bkl.parser.ast.Position` object with location of the error.
        May be :const:`None`.
    """
    def __init__(self, msg, pos=None):
        self.msg = msg
        self.pos = pos

    def __unicode__(self):
        return str(self)

    def __str__(self):
        if self.pos:
            return "%s: %s" % (self.pos, self.msg)
        else:
            return self.msg


class ParserError(Error):
    """
    Exception class for errors encountered by the Bakefile parser.
    """
    pass


class TypeError(Error):
    """
    Exception class for variable type errors.

    .. attribute:: detail

        Any extra details about the error or (usually) :const:`None`.

    .. seealso:: :class:`bkl.vartypes.Type`
    """
    def __init__(self, type, expr, msg=None, pos=None):
        """
        Convenience constructor creates error message appropriate for the
        type and expression test, in the form of ``expression expr is not
        type`` or ``expression expr is not type: msg`` if additional message is
        supplied.

        :param type: :class:`bkl.vartypes.Type` instance the error is related to.
        :param expr: :class:`bkl.expr.Expr` expression that caused the error.
        :param msg:  Optional error message detailing reasons for the error.
                     This will be stored as :attr:`detail` if provided.
        """
        text = 'expression "%s" is not a valid %s value' % (expr, type)
        if msg:
            text += ": %s" % msg
        if not pos:
            pos = expr.pos
        super(TypeError, self).__init__(text, pos)
        self.detail = msg


class NonConstError(Error):
    """
    Exception thrown when attempting to convert an expression into bake-time
    constant.
    """
    def __int__(self, expr, pos=None):
        """
        Convenience constructor creates error message appropriate for given
        expression *expr*.

        :param expr: :class:`bkl.expr.Expr` expression that caused the error.
        """
        text = "expression \"%s\" must evaluate to a constant" % expr
        if not pos:
            pos = expr.pos
        super(NonConstError, self).__init__(text, pos)


class UndefinedError(Error):
    """
    Exception thrown when a property or variable is undefined, i.e. doesn't
    have a value.
    """
    pass


class CannotDetermineError(Error):
    """
    Exception thrown when something (e.g. equality) cannot be determined.
    This usually signifies a weakness in Bakefile implementation that should
    be improved.
    """
    def __init__(self, msg=None, pos=None):
        super(CannotDetermineError, self).__init__(msg, pos)
