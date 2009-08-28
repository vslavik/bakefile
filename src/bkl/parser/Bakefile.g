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
    // Tokens used in the output AST, but not in lexer:
    PROGRAM;
    ID;
    ASSIGN;
    ASSIGNED_VALUE;
    VALUE;
    TARGET;
}

@lexer::init {
    # Bakefile grammar uses newlines to terminate statements, unlike C and like
    # e.g. Python. Like Python, it also treats newlines as any other whitespace
    # inside ( ... ) blocks such as this:
    #   sources += (foo.cpp
    #               bar.cpp)
    # This solution to the problem was strongly inspired by Terence Parr's and
    # Loring Craymer's ANTLR Python grammar.
    self.implicitLineJoiningLevel = 0
}

// ---------------------------------------------------------------------------
// Overall program structure
// ---------------------------------------------------------------------------

program: stmt* EOF -> ^(PROGRAM stmt*);

stmt
    : assignment_stmt
    | target_stmt
    | NEWLINE -> // empty statement
    ;


assignment_stmt
    : identifier '=' expression NEWLINE -> ^(ASSIGN identifier expression)
    ;


// ---------------------------------------------------------------------------
// Expressions
// ---------------------------------------------------------------------------

identifier: t=TEXT             -> ID[$t];

value
    : t=TEXT                   -> VALUE[$t]
    | t=QUOTED_TEXT            -> VALUE[$t, $t.text[1:-1\]]
    ;

// expression may span multiple lines, but only if enclosed in ( ... )
expression
    : element+                               -> ^(ASSIGNED_VALUE element+)
    | LPAREN expression RPAREN               -> expression
    ;

// single element of an expression
element: value -> value;


// ---------------------------------------------------------------------------
// Targets
// ---------------------------------------------------------------------------

// examples:
//
//     exe hello {}

target_stmt
    : type=identifier id=identifier '{' target_content* '}' NEWLINE -> ^(TARGET $type $id target_content*)
    ;

target_content
    : assignment_stmt
    | NEWLINE -> // empty statement
    ;


// ---------------------------------------------------------------------------
// Basic tokens
// ---------------------------------------------------------------------------

LPAREN: '(' {self.implicitLineJoiningLevel += 1};
RPAREN: ')' {self.implicitLineJoiningLevel -= 1};

QUOTED_TEXT: '"' (options{greedy=false;}:.)* '"';

// a chunk of simple text, used for identifiers, values etc.
TEXT: ('a'..'z' | 'A'..'Z' | '0'..'9' | '_')+;


// ---------------------------------------------------------------------------
// Comments:
// ---------------------------------------------------------------------------

COMMENT
    : '//' ~'\n'* { $channel = HIDDEN };

ML_COMMENT
    : '/*' (options{greedy=false;}:.)* '*/' { $channel = HIDDEN };


// ---------------------------------------------------------------------------
// Whitespace handling
// ---------------------------------------------------------------------------

WHITESPACE
    : (' ' | '\t')+  { $channel = HIDDEN };

NEWLINE
    : ('\n' | '\r')  { if self.implicitLineJoiningLevel > 0:
                           $channel = HIDDEN
                     };
