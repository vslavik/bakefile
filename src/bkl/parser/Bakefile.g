/*
 *  This file is part of Bakefile (http://www.bakefile.org)
 *
 *  Copyright (C) 2008-2011 Vaclav Slavik
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
    LITERAL;
    TARGET;
    VAR_REFERENCE;
    CONCAT;
    LIST;
}

// Bakefile grammar uses newlines to terminate statements, unlike C and like
// e.g. Python. Like Python, it also treats newlines as any other whitespace
// inside ( ... ) blocks such as this:
//   sources += (foo.cpp
//               bar.cpp)
// This solution to the problem was strongly inspired by Terence Parr's and
// Loring Craymer's ANTLR Python grammar.
@lexer::init {
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
    : WS* identifier WS* '=' WS* expression NEWLINE
                                    -> ^(ASSIGN identifier expression)
    ;


// ---------------------------------------------------------------------------
// Expressions
// ---------------------------------------------------------------------------

identifier: t=TEXT             -> ID[$t];

literal
    : t=TEXT                   -> LITERAL[$t]
    | t=QUOTED_TEXT            -> LITERAL[$t, $t.text[1:-1\]]
    ;

// expression may span multiple lines, but only if enclosed in ( ... )
expression
    : element
    | element_list
    | LPAREN WS* expression WS* RPAREN     -> expression
    ;

element_list
    : (element WS+)+ element               -> ^(LIST element+)
    ;

// Single element of an expression. This can be either a single literal,
// a variable reference, or a concatenation of any combination of them.
// Note that a combination of two literals is possible too (e.g. foo"bar").
// Finally, notice that there's a difference between two concatenated elements
// without whitespace ("foo$(bar)") and with whitespace between them ("foo
// $(bar)") -- the former is a single element, the latter is a list.
element
    : element_part
    | element_part element_part+           -> ^(CONCAT element_part+)
    ;

element_part
    : literal                              -> literal
    | '$(' identifier ')'                  -> ^(VAR_REFERENCE identifier)
    ;


// ---------------------------------------------------------------------------
// Targets
// ---------------------------------------------------------------------------

// examples:
//
//     exe hello {}

target_stmt
    : WS* type=identifier WS* id=identifier any_ws '{' target_content* WS* '}' NEWLINE
                            -> ^(TARGET $type $id target_content*)
    ;

target_content
    : assignment_stmt
    | NEWLINE -> // empty statement
    ;


// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Any whitespace sequence, including newlines
any_ws : WS               ->
       | NEWLINE          ->
       | WS any_ws        ->
       | NEWLINE any_ws   ->
       ;

// ---------------------------------------------------------------------------
// Basic tokens
// ---------------------------------------------------------------------------

LPAREN: '(' {self.implicitLineJoiningLevel += 1};
RPAREN: ')' {self.implicitLineJoiningLevel -= 1};

QUOTED_TEXT: '"' (options{greedy=false;}:.)* '"';

// a chunk of simple text, used for identifiers, values etc.
TEXT: ('a'..'z' | 'A'..'Z' | '0'..'9' | '_' | '.' | '/' | '@')+;

// ---------------------------------------------------------------------------
// Comments:
// ---------------------------------------------------------------------------

COMMENT
    : WS* '//' ~'\n'* { $channel = HIDDEN };

ML_COMMENT
    : WS* '/*' (options{greedy=false;}:.)* '*/' { $channel = HIDDEN };


// ---------------------------------------------------------------------------
// Whitespace handling
// ---------------------------------------------------------------------------

// Note that whitespace is intentionally NOT put on the hidden channel. This
// is because we need to distinguish between lists ("foo $(bar) zar") and
// concatenation ("foo$(bar)zar").
WS
    : (' ' | '\t')+;

NEWLINE
    : WS* ('\n' | '\r')  { if self.implicitLineJoiningLevel > 0:
                               $channel = HIDDEN
                         };

// C-style continuations for escaping of newlines:
CONTINUATION
    : '\\' NEWLINE { $channel = HIDDEN };
