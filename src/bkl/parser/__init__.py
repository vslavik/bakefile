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

try:
    import antlr3
except ImportError:
    import os.path
    antlr_path = os.path.join(os.path.dirname(__file__),
                              "../../../3rdparty/antlr3/python-runtime")
    if os.path.isdir(antlr_path):
        import sys
        sys.path.append(os.path.abspath(antlr_path))
        import antlr3
    else:
        raise

import ast
from BakefileLexer import BakefileLexer
from BakefileParser import BakefileParser, LITERAL
from BakefileQuotedStringLexer import BakefileQuotedStringLexer
from BakefileQuotedStringParser import BakefileQuotedStringParser

from bkl.error import ParserError, VersionError, warning
from bkl.utils import memoized


# Helper to implement errors handling in a way we prefer
class _BakefileErrorsMixin(object):
    def displayRecognitionError(self, tokenNames, e):
        msg = self.getErrorMessage(e, tokenNames)
        pos = self._get_position(e)
        raise ParserError(msg, pos=pos)

    def getTokenErrorDisplay(self, t):
        # workaround for an ugly behavior in ANTLRv3's Python bindings: it
        # formats tokens as e.g. u'program', we prefer 'program':
        s = t.text
        if s is None:
            return str(super(Parser, self).getTokenErrorDisplay(t))
        else:
            return repr(str(s))

    def _get_position(self, e):
        pos = ast.Position()
        pos.filename = self.filename
        pos.line = e.line
        if e.charPositionInLine != -1:
            pos.column = e.charPositionInLine
        return pos


# Helper for misc things common to the main parser and island grammars:
class _BakefileParserMixin(object):
    def unescape(self, token, text):
        """Removes \\ escapes from the text."""
        out = ""
        start = 0
        while True:
            pos = text.find('\\', start)
            if pos == -1:
                out += text[start:]
                break
            else:
                out += text[start:pos]
                c = text[pos+1]
                out += c
                start = pos+2
                if c != '"' and c != '\\' and c != '$':
                    source_pos = self._get_position(token)
                    source_pos.column += pos+1
                    warning("unnecessary escape sequence '\\%s' (did you mean '\\\\%s'?)" % (c, c),
                            pos=source_pos)
        return out


# The lexer and parser used to parse .bkl files.
# Do not use directly, use parse() function instead.

class _ParserQuotedString(_BakefileErrorsMixin, _BakefileParserMixin, BakefileQuotedStringParser):
    pass

class _LexerQuotedString(_BakefileErrorsMixin, BakefileQuotedStringLexer):
    pass


class _Lexer(_BakefileErrorsMixin, BakefileLexer):
    pass

class _Parser(_BakefileErrorsMixin, _BakefileParserMixin, BakefileParser):

    def check_version(self, token):
        """Checks Bakefile version, throwing if too old."""
        try:
            from bkl.version import check_version
            check_version(token.text)
        except VersionError as e:
            e.pos = self._get_position(token)
            raise

    def parse_quoted_str(self, token):
        text = token.text[1:-1]
        if not text:
            return self._adaptor.create(LITERAL, token, "")

        stream = antlr3.StringStream(text)
        stream.setLine(token.line)
        stream.setCharPositionInLine(token.charPositionInLine + 1)
        lexer = _LexerQuotedString(stream)
        parser = _ParserQuotedString(antlr3.CommonTokenStream(lexer))
        lexer.filename = parser.filename = self.filename
        parser.adaptor = self.adaptor
        return parser.quoted_string().tree


def get_parser(code, filename=None):
    """
    Prepares Bakefile parser for parsing given Bakefile code from string
    argument passed in. The optional filename argument allows specifying input
    file name for the purpose of errors reporting.
    """
    if code and code[-1] != "\n":
        code += "\n"

    cStream = antlr3.StringStream(code)
    lexer = _Lexer(cStream)
    lexer.filename = filename

    tStream = antlr3.CommonTokenStream(lexer)
    parser = _Parser(tStream)
    parser.filename = filename
    parser.adaptor = ast._TreeAdaptor(filename)

    return parser


def parse(code, filename=None, detect_compatibility_errors=True):
    """
    Reads Bakefile code from string argument passed in and returns parsed AST.
    The optional filename argument allows specifying input file name for the purpose
    of errors reporting.
    """
    parser = get_parser(code, filename)
    try:
        return parser.program().tree
    except ParserError as err:
        if not detect_compatibility_errors:
            raise
        # Report usage of bkl-ng with old bkl files in user-friendly way:
        if code.startswith("<?xml"):
            raise ParserError("this file is incompatible with new Bakefile versions; please use Bakefile 0.2.x to process it",
                              pos=ast.Position(filename))
        else:
            # Another possible problem is that that this version of Bakefile
            # may be too old and doesn't recognize some newly introduced
            # syntax. Try to report that nicely too.
            code_lines = code.splitlines()
            for idx in xrange(0, len(code_lines)):
                ln = code_lines[idx]
                if "requires" in ln:
                    try:
                        parse(ln, detect_compatibility_errors=False)
                    except VersionError as e:
                        e.pos.filename = filename
                        e.pos.line = idx+1
                        raise
                    except ParserError as e:
                        pass
            raise err


@memoized
def parse_file(filename):
    """
    Reads Bakefile code from given file returns parsed AST.
    """
    with file(filename, "rt") as f:
        return parse(f.read(), filename)


# for testing of AST construction, make this script runnable:
if __name__ == "__main__":
    import sys
    t = parse_file(sys.argv[1])
    print t.toStringTree()
