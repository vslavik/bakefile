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

from antlr3.tree import CommonTree, CommonTreeAdaptor

import BakefileParser


class Position(object):
    """
    Location of an error in input file.

    All of its attributes are optional and may be None. Convert the object
    to string to get human-readable output.

    .. attribute:: filename

       Name of the source file.

    .. attribute:: line

       Line number.

    .. attribute:: column

       Column on the line.
    """
    def __init__(self, filename=None, line=None, column=None):
        self.filename = filename
        self.line = line
        self.column = column


    def __str__(self):
        hdr = []
        if self.filename:
            hdr.append(self.filename)
        if self.line is not None:
            hdr.append(str(self.line))
        if self.column is not None:
            hdr.append(str(self.column))
        return ":".join(hdr)


class Node(CommonTree):
    """
    Base class for Bakefile AST tree node.
    """

    def _get_pos(self):
        pos = Position()
        pos.filename = self.filename
        if self.token:
            pos.line = self.line
            pos.column = self.charPositionInLine
        return pos

    # Position of the node in source code, as parser.Position object.
    # FIXME: if it doesn't have position, look at siblings in the tree
    # and return "near $foo.pos" for some foo parent or sibling
    pos = property(_get_pos, "position of the node in source code")

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
    def __init__(self, payload=None):
        Node.__init__(self, payload)


class LiteralNode(Node):
    """Single value, i.e. literal."""

    #: Text of the value, as string.
    text = property(lambda self: self.token.text)

    def __str__(self):
        return '%s "%s"' % (self.__class__.__name__, self.text)


class ListNode(Node):
    """
    Right side of variable assignment, contains list of values (LiteralNode,
    VarReferenceNode etc.).
    """
    #: List of values in the assignment. May be single value, maybe be
    #: multiple values, code using this must correctly interpret it and
    #: check values' types.
    values = property(lambda self: self.children)


class ConcatNode(Node):
    """
    Concatenation of several parts, to form single string.
    """
    #: List of fragments.
    values = property(lambda self: self.children)


class IdNode(Node):
    """Identifier (variable, target, template, ...)."""
    # Text of the identifier, as string.
    text = property(lambda self: self.token.text)

    def __str__(self):
        return '%s %s' % (self.__class__.__name__, self.text)


class AssignmentNode(Node):
    """Assignment of value to a variable."""
    var = property(lambda self: self.children[0].text,
                   doc="Variable assigning to")
    value = property(lambda self: self.children[1],
                     doc="Value being assigned.")


class AppendNode(AssignmentNode):
    pass


class VarReferenceNode(Node):
    """Reference to a variable."""
    var = property(lambda self: self.children[0].text,
                   doc="Referenced variable")


class TargetNode(Node):
    """Creation of a makefile target."""
    type = property(lambda self: self.children[0],
                    doc="Type of the target")
    name = property(lambda self: self.children[1],
                    doc="Name of the target")
    content = property(lambda self: self.children[2:],
                       doc="Other content: variables assignments and such")


class _TreeAdaptor(CommonTreeAdaptor):
    """Adaptor for ANTLR3 AST tree creation."""
    def __init__(self, filename):
        self.filename = filename

    # mapping of token types to AST node classes
    TOKENS_MAP = {
        BakefileParser.PROGRAM        : RootNode,
        BakefileParser.LITERAL        : LiteralNode,
        BakefileParser.ID             : IdNode,
        BakefileParser.LIST           : ListNode,
        BakefileParser.CONCAT         : ConcatNode,
        BakefileParser.ASSIGN         : AssignmentNode,
        BakefileParser.APPEND         : AppendNode,
        BakefileParser.VAR_REFERENCE  : VarReferenceNode,
        BakefileParser.TARGET         : TargetNode,
    }

    def createWithPayload(self, payload):
        if payload is None:
            return NilNode()
        else:
            n = self.TOKENS_MAP[payload.type](payload)
            n.filename = self.filename
            return n
