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

from antlr3.tree import CommonTree, CommonTreeAdaptor
import BakefileParser

class Node(CommonTree):
    """Base class for Bakefile AST tree node."""

    def _get_pos(self):
        if self.token is None:
            return None
        if self.line is None or self.charPositionInLine is None:
            return None
        return (self.line, self.charPositionInLine)

    # Position of the node in source code. Returns None if it cannot be
    # determined or (line,posInLine) tuple.
    # FIXME: change this to return string, include filename, line, posInLine
    # only if !=-1; if it doesn't have position, look at siblings in the tree
    # and return "near $foo.pos" for some foo parent or sibling
    pos = property(_get_pos)

    def __str__(self):
        return self.__class__.__name__

    # CommonTree methods:

    def toString(self):
        return str(self)

    def toStringTree(self, indent=''):
        s = self.toString()
        if not self.children:
            return s
        def _formatNode(n):
            r = n.toStringTree(indent + '    ')
            return '\n'.join('    %s' % x for x in r.split('\n'))
        return '%s\n%s' % (s, '\n'.join(_formatNode(c) for c in self.children))


class RootNode(Node):
    """Root node of loaded .bkl file."""
    pass


class NilNode(Node):
    """Empty node."""
    def __init__(self):
        Node.__init__(self, None)


class ValueNode(Node):
    """Single value, i.e. literal."""

    #: Text of the value, as string.
    text = property(lambda self: self.token.text)

    def __str__(self):
        return '%s "%s"' % (self.__class__.__name__, self.text)


class AssignedValueNode(Node):
    """
    Right side of variable assignment, contains list of values (ValueNode
    objects)."""

    #: List of values in the assignment. May be single value, maybe be
    #: multiple values, code using this must correctly interpret it and
    #: check values' types.
    values = property(lambda self: self.children)


class IdNode(Node):
    """Identifier (variable, target, template, ...)."""

    # Text of the identifier, as string.
    text = property(lambda self: self.token.text)

    def __str__(self):
        return '%s %s' % (self.__class__.__name__, self.text)


class AssignmentNode(Node):
    """Assignment of value to a variable."""

    var = property(lambda self: self.children[0],
                   doc="Variable assigning to")
    value = property(lambda self: self.children[1],
                     doc="Value being assigned, AssignedValueNode")


class TargetNode(Node):
    """Creation of a makefile target."""

    type = property(lambda self: self.children[0],
                    doc="Type of the target")
    name = property(lambda self: self.children[1],
                    doc="Name of the target")


class _TreeAdaptor(CommonTreeAdaptor):
    """Adaptor for ANTLR3 AST tree creation."""

    # mapping of token types to AST node classes
    TOKENS_MAP = {
        BakefileParser.PROGRAM        : RootNode,
        BakefileParser.VALUE          : ValueNode,
        BakefileParser.ID             : IdNode,
        BakefileParser.ASSIGNED_VALUE : AssignedValueNode,
        BakefileParser.ASSIGN         : AssignmentNode,
        BakefileParser.TARGET         : TargetNode,
    }

    def createWithPayload(self, payload):
        if payload is None:
            return NilNode()
        else:
            return self.TOKENS_MAP[payload.type](payload)
