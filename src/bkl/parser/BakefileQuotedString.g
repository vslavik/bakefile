/*
 *  This file is part of Bakefile (http://bakefile.org)
 *
 *  Copyright (C) 2012-2013 Vaclav Slavik
 *
 *  Permission is hereby granted, free of charge, to any person obtaining a
 *  copy of this software and associated documentation files (the "Software"),
 *  to deal in the Software without restriction, including without limitation
 *  the rights to use, copy, modify, merge, publish, distribute, sublicense,
 *  and/or sell copies of the Software, and to permit persons to whom the
 *  Software is furnished to do so, subject to the following conditions:
 *
 *  The above copyright notice and this permission notice shall be included in
 *  all copies or substantial portions of the Software.
 *
 *  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 *  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 *  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 *  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 *  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 *  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
 *  DEALINGS IN THE SOFTWARE.
 *
 */

// This is an island grammar for parsing double-quoted strings.
// It needs to be kept in sync with rules in the main Bakefile.g grammar!

grammar BakefileQuotedString;
options {
  language = Python;
  output = AST;
  ASTLabelType = CommonTree;
  tokenVocab = Bakefile;
}

@lexer::init {
self.inside_ref = 0
}

quoted_string: quoted_string_content EOF -> quoted_string_content;

quoted_string_content
    : quoted_string_component
    | quoted_string_component quoted_string_component+  -> ^(CONCAT quoted_string_component+)
    ;

quoted_string_component
    : literal_text
    | var_reference
    ;

var_reference
    : REF_OPEN identifier REF_CLOSE   -> ^(VAR_REFERENCE identifier)
    ;

literal_text: t=ANY_TEXT              -> LITERAL[$t, self.unescape($t, $t.text)];

identifier: t=ANY_TEXT                -> ID[$t];

REF_OPEN:    '$(' { self.inside_ref += 1 };
REF_CLOSE:   ')'  { self.inside_ref -= 1 };

ANY_TEXT
    : {self.inside_ref == 0}?=> TEXT_OUTSIDE
    | {self.inside_ref > 0 }?=> TEXT_INSIDE
    ;

fragment
TEXT_OUTSIDE: ( ESCAPE_SEQ | ~('\\' | '"' | '$') )*;

fragment
TEXT_INSIDE: ALLOWED_ID_CHARS+;

fragment
ESCAPE_SEQ: '\\' . ;

fragment
ALLOWED_ID_CHARS: ('a'..'z' | 'A'..'Z' | '0'..'9' | '-' | '_' | '.' | '/' | '@');
