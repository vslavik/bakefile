/*
 *  This file is part of Bakefile (http://www.bakefile.org)
 *
 *  Copyright (C) 2008-2009 Vaclav Slavik
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

grammar Bakefile;
options {
  language = Python;
  output = AST;
  ASTLabelType = CommonTree;
}

tokens {
    // Imaginary tokens for indentation increase and indentation decrease.
    // These are not recognized by the lexer described in the grammar, but
    // are synthesized by BakefileTokenSource class, which *must* be plugged
    // in between the lexer and the parser. See the comments near LEADING_WS
    // below for more information.
    INDENT;
    DEDENT;

    // Tokens used in the output AST, but not in lexer:
    PROGRAM;
    ID;
    ASSIGN;
    ASSIGNED_VALUE;
    VALUE;
    TARGET;
}

// ---------------------------------------------------------------------------
// Overall program structure
// ---------------------------------------------------------------------------

program: stmt+ EOF -> ^(PROGRAM stmt+);

stmt
    : assignment_stmt
    | target_stmt
    ;


assignment_stmt
    : identifier '=' expression -> ^(ASSIGN identifier expression)
    ;


// ---------------------------------------------------------------------------
// Expressions
// ---------------------------------------------------------------------------

identifier: t=TEXT             -> ID[$t];

value
    : t=TEXT                   -> VALUE[$t]
    | t=QUOTED_TEXT            -> VALUE[$t, $t.text[1:-1\]]
    ;

// expression may span multiple lines, but with one indentation only
expression
    : element+                               -> ^(ASSIGNED_VALUE element+)
    | INDENT element+ DEDENT                 -> ^(ASSIGNED_VALUE element+)
    | a+=element+ INDENT b+=element+ DEDENT  -> ^(ASSIGNED_VALUE $a+ $b+)
    ;

// single element of an expression
element: value -> value;


// ---------------------------------------------------------------------------
// Targets
// ---------------------------------------------------------------------------

// examples:
//
//     exe hello:
//         pass

target_stmt
    : type=identifier id=identifier ':' INDENT target_content DEDENT -> ^(TARGET $type $id target_content)
    ;

target_content
    : EMPTY_BLOCK
    ;


// ---------------------------------------------------------------------------
// Basic tokens
// ---------------------------------------------------------------------------

EMPTY_BLOCK: 'pass';

QUOTED_TEXT: '"' ( ~('"') )* '"';

// a chunk of simple text, used for identifiers, values etc.
TEXT: ('a'..'z' | 'A'..'Z' | '0'..'9' | '_')+;

// ---------------------------------------------------------------------------
// Whitespace handling
// ---------------------------------------------------------------------------

// Bakefile uses Python-style meaningful indentation and this is impossible
// to handle nicely in LL(*) grammar without some help. So we use the same
// mechanism as used by Terence Parr's example Python grammar from ANTLR3
// distribution:
//
// The lexer only detects newlines and leading whitespace and doesn't do
// anything special about them (except for the predicate used to differentiate
// between leading and "ordinary" whitespace). Lexer's tokenized output is
// then passed through BakefileTokenSource filter, which uses LEADING_WS and
// NEWLINE tokens to detect indentation changes and inserts imaginary
// INDENT (indentation increased) and DEDENT (indentation decreased) tokens
// that the parser needs.

LEADING_WS
    : {self.getCharPositionInLine()==0}? => (' ' | '\t' )+ { $channel = HIDDEN };

WHITESPACE
    : (' ' | '\t')+ { $channel = HIDDEN };

NEWLINE
    : ('\n' | '\r')+ { $channel = HIDDEN };


// never-matched INDENT/DEDENT lexer rules to silence antlr warnings
INDENT: '<INDENT>';
DEDENT: '<DEDENT>';
