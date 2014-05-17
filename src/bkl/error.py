#
#  This file is part of Bakefile (http://bakefile.org)
#
#  Copyright (C) 2008-2013 Vaclav Slavik
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

import threading

import logging
logger = logging.getLogger("bkl.error")


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


class VersionError(Error):
    """
    Exception raised when Bakefile version is too old for the input.
    """
    pass


class UnsupportedError(Error):
    """
    Exception class for errors when something is unsupported, e.g. unrecognized
    file extension.
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


class CannotDetermineError(NonConstError):
    """
    Exception thrown when something (e.g. equality) cannot be determined.
    This usually signifies a weakness in Bakefile implementation that should
    be improved.
    """
    def __init__(self, msg=None, pos=None):
        Error.__init__(self, msg, pos)


class UndefinedError(Error):
    """
    Exception thrown when a property or variable is undefined, i.e. doesn't
    have a value.
    """
    pass


class NotFoundError(Error):
    """
    Exception thrown when a property or variable wasn't found at all.
    """
    pass


class _LocalContextStack(threading.local):
    """
    Helper class for keeping track of :class:`error_context` instances.
    """
    stack = []

    def push(self, ctx):
        if not self.stack:
            self.stack = [ctx]
        else:
            self.stack.append(ctx)

    def pop(self):
        self.stack.pop()

    @property
    def pos(self):
        for c in reversed(self.stack):
            p = c.pos
            if p: return p
        return None


_context_stack = _LocalContextStack()


class error_context:
    """
    Error context for adding positional information to exceptions thrown
    without one. This can happen in some situations when the particular
    expression causing the error isn't available. In such situations, it's much
    better to provide coarse position information (e.g. a target) instead of
    not providing any at all.

    Usage:

    .. code-block:: python

       with error_context(target):
          ...do something that may throw...

    .. attribute:: pos

        :class:`bkl.parser.ast.Position` object with location of the error.
        May be :const:`None`.
    """
    def __init__(self, context):
        self.context = context

    def __enter__(self):
        _context_stack.push(self)

    def __exit__(self, exc_type, exc_value, traceback):
        _context_stack.pop()
        if exc_value is not None:
            if isinstance(exc_value, Error) and exc_value.pos is None:
                exc_value.pos = self.pos

    @property
    def pos(self):
        c = self.context
        if hasattr(c, "source_pos"):
            return c.source_pos
        elif hasattr(c, "pos"):
            return c.pos
        else:
            return None


def warning(msg, *args, **kwargs):
    """
    Logs a warning.

    The function takes position arguments similarly to logging module's
    functions. It also accepts options *pos* argument with position information
    as :class:`bkl.parser.ast.Position`.

    Uses active :class:`error_context` instances to decorate the warning with
    position information if not provided.

    Usage:

    .. code-block:: python

       bkl.error.warning("target %s not supported", t.name, pos=t.source_pos)
    """
    text = msg % args
    e = {}
    try:
        e["pos"] = kwargs["pos"]
    except KeyError:
        e["pos"] = _context_stack.pos
    logger.warning(text, extra=e)
