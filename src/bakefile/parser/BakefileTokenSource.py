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

import antlr3
import BakefileLexer

class BakefileTokenSource(antlr3.TokenSource):
    """
    This class is core part of parser for Python-style syntax with meaningful
    indentation. The Bakefile.g grammar doesn't work correctly without it.

    It takes tokens stream from lexer and watches for end of line and leading
    whitespace tokens (the lexer must correctly identify both of these, but it
    doesn't matter if it puts them into hidden or visible channel). When it
    encounters these tokens, it inserts "imaginary" INDENT or DEDENT tokens
    into the stream as needed.

    See the comment near LEADING_WS in Bakefile.g grammar for more details.
    """

    def __init__(self, lexer):
        self.lexer = lexer
        self.queue = []
        self.indent = [0]
        self.lastLine = 0

    def nextToken(self):
        if not self.queue:
            self._fetchMore()
        return self.queue.pop(0)

    def _fetchMore(self):
        ws = None
        while True:
            t = self.lexer.nextToken()
            if t.getLine():
                self.lastLine = t.getLine()

            if t == antlr3.tokens.EOF_TOKEN:
                self._dedentAll(t)
                self.queue.append(t)
                return

            # note: we have to watch for newlines too, not only LEADING_WS,
            # because if indentation goes back to zero, there's no LEADING_WS
            # token at the start of line
            if t.type == BakefileLexer.NEWLINE:
                self.queue.append(t)
                ws = t
                continue

            if t.type == BakefileLexer.LEADING_WS:
                self.queue.append(t)
                ws = t
                continue

            # non-whitespace token encountered
            if ws is not None:
                self._handleIndent(ws)
            self.queue.append(t)
            return

    def _handleIndent(self, t):
        assert self.indent, "indentation stack corrupted"
        if t.type == BakefileLexer.NEWLINE:
            ind = 0
        else:
            ind = len(t.text)
        current = self.indent[-1]
        if ind == current:
            return # indentation didn't change
        elif ind > current:
            self._addIndent(BakefileLexer.INDENT, t)
            self.indent.append(ind)
        elif ind < current:
            while ind < self.indent[-1]:
                self._addIndent(BakefileLexer.DEDENT, t)
                self.indent.pop()
            # FIXME: report this as proper error
            assert ind == self.indent[-1], "incorrect indentation"

    def _dedentAll(self, oldToken):
        while len(self.indent) > 1:
            self._addIndent(BakefileLexer.DEDENT, oldToken)
            self.indent.pop()

    def _addIndent(self, ttype, oldToken):
        if ttype == BakefileLexer.INDENT:
            desc = "<INDENT>"
        else:
            desc = "<DEDENT>"
        # pass in oldToken so that source code location is copied
        t = antlr3.ClassicToken(type=ttype, oldToken=oldToken, text=desc)
        if not t.getLine():
            # if the token doesn't have position information (e.g. EOF),
            # synthesize it from the last encountered location
            t.setLine(self.lastLine)
            t.setCharPositionInLine(0)
        self.queue.append(t)
