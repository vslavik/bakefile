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
    APPEND;
    LITERAL;
    TARGET;
    VAR_REFERENCE;
    LIST_OR_CONCAT;
    LIST;
    CONCAT;
    IF;
}

scope StmtScope {
    insideTarget;
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


program
scope StmtScope;
@init { $StmtScope::insideTarget = False }
    : stmt* EOF -> ^(PROGRAM stmt*);

stmt
    : assignment_stmt
    | {not $StmtScope::insideTarget}?=> target_stmt
    | if_stmt
    | NEWLINE -> // empty statement
    ;


assignment_stmt
    : identifier '=' expression NEWLINE    -> ^(ASSIGN identifier expression)
    | identifier '+=' expression NEWLINE   -> ^(APPEND identifier expression)
    ;


if_stmt
    : 'if' LPAREN expression RPAREN if_body      -> ^(IF expression if_body)
    ;

if_body
    : stmt
    | NEWLINE* '{' (stmt)* '}'  -> stmt*
    ;

// ---------------------------------------------------------------------------
// Expressions
// ---------------------------------------------------------------------------

// expression may span multiple lines, but only if enclosed in ( ... )
expression : expr_and;

expr_and
    : expr_or (AND^ expr_or)*
    ;

expr_or
    : expr_eq (OR^ expr_eq)*
    ;

expr_eq
    : expr_atom ((EQUAL | NOT_EQUAL)^ expr_atom)?
    ;

expr_atom
    : element
    | NOT expr_atom                                 -> ^(NOT expr_atom)
    | LPAREN expression RPAREN                      -> expression
    ;


// Single element of an expression. This can be either a single literal,
// a variable reference, or a concatenation of any combination of them.
// Note that a combination of two literals is possible too (e.g. foo"bar").
//
// Finally, notice that there's a difference between two concatenated elements
// without whitespace ("foo$(bar)") and with whitespace between them
// ("foo $(bar)") -- the former is a single value, the latter is a list. This
// grammar, however, does *NOT* differentiate between these two cases, that is
// done in the bkl.parser.ast._TreeAdaptor.rulePostProcessing() in Python code.
// 
// FIXME: It would be better to do it here, with backtrack=true and validating
//        predicates to build it directly, but bugs in ANTLR 3.4's Python
//        binding prevent it from working at the moment.
element
    : element_part
    | element_part element_part+           -> ^(LIST_OR_CONCAT element_part+)
    ;

element_part
    : literal                              -> literal
    | '$(' identifier ')'                  -> ^(VAR_REFERENCE identifier)
    ;

identifier: t=TEXT             -> ID[$t];

literal
    : t=TEXT                   -> LITERAL[$t]
    | t=QUOTED_TEXT            -> LITERAL[$t, $t.text[1:-1\]]
    ;

// ---------------------------------------------------------------------------
// Targets
// ---------------------------------------------------------------------------

// examples:
//
//     exe hello {}

target_stmt
scope StmtScope;
@init { $StmtScope::insideTarget = True }
    : type=identifier id=identifier NEWLINE* '{' target_content* '}' NEWLINE
                            -> ^(TARGET $type $id target_content*)
    ;

target_content : stmt;


// ---------------------------------------------------------------------------
// Basic tokens
// ---------------------------------------------------------------------------

AND:       '&&';
OR:        '||';
NOT:       '!';
EQUAL:     '==';
NOT_EQUAL: '!=';

LPAREN: '(' {self.implicitLineJoiningLevel += 1};
RPAREN: ')' {self.implicitLineJoiningLevel -= 1};

QUOTED_TEXT: '"' (options{greedy=false;}:.)* '"';

// a chunk of simple text, used for identifiers, values etc.
TEXT: ('a'..'z' | 'A'..'Z' | '0'..'9' | '_' | '.' | '/' | '@')+;

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

// Note that whitespace is intentionally NOT put on the hidden channel. This
// is because we need to distinguish between lists ("foo $(bar) zar") and
// concatenation ("foo$(bar)zar").
WS
    : (' ' | '\t')+ { $channel = HIDDEN };

NEWLINE
    : ('\n' | '\r')  { if self.implicitLineJoiningLevel > 0:
                               $channel = HIDDEN
                      };

// C-style continuations for escaping of newlines:
CONTINUATION
    : '\\' WS* NEWLINE { $channel = HIDDEN };
