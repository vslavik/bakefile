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

"""
Classes for simplification of expressions.

The :class:`Expr` class that represents a Bakefile expression (be it a
condition or variable value) is defined in this module, together with
useful functions for evaluating and simplifying expressions.
"""

from bkl.expr import *
from bkl.error import NonConstError


class NoopSimplifier(Visitor):
    """
    This simplifier doesn't simplify anything.
    """
    def null(self, e):
        return e

    def literal(self, e):
        return e

    def list(self, e):
        return e

    def concat(self, e):
        return e

    def reference(self, e):
        return e

    def path(self, e):
        return e

    def bool_value(self, e):
        return e

    def bool(self, e):
        return e

    def if_(self, e):
        return e


class BasicSimplifier(NoopSimplifier):
    """
    Simplify expression *e*. This does "cheap" simplifications such
    as merging concatenated literals, recognizing always-false conditions,
    eliminating unnecessary variable references (turn ``foo=$(x);bar=$(foo)``
    into ``bar=$(x)``) etc.
    """
    def _visit_children(self, children, removeNulls=True):
        new = []
        changed = False
        for i in children:
            j = self.visit(i)
            if i is not j:
                changed = True
            if removeNulls and isinstance(j, NullExpr):
                changed = True
            else:
                new.append(j)
        if not changed:
            new = children
        return (new, changed)
    
    def list(self, e):
        new, changed = self._visit_children(e.items)
        if changed:
            return ListExpr(new, pos=e.pos)
        else:
            return e

    def concat(self, e):
        # merge concatenated literals:
        items, changed = self._visit_children(e.items)
        out = [items[0]]
        for i in items[1:]:
            if isinstance(i, LiteralExpr) and isinstance(out[-1], LiteralExpr):
                out[-1] = LiteralExpr(out[-1].value + i.value)
            else:
                out.append(i)
        if len(out) == 1:
            return out[0]
        else:
            return ConcatExpr(out, pos=e.pos)

    def reference(self, e):
        # Simple reference can be replaced with the referenced value. Do this
        # for (scalar) literals and other references only, though -- if the
        # value is e.g. a list, we want to keep it as a variable to avoid
        # duplication of large values.
        ref = e.get_value()
        if isinstance(ref, LiteralExpr) or isinstance(ref, ReferenceExpr):
            return self.visit(ref)
        else:
            return e

    def path(self, e):
        components, changed = self._visit_children(e.components, removeNulls=False)
        if changed:
            return PathExpr(components, e.anchor, pos=e.pos)
        else:
            return e

    def bool(self, e):
        left = self.visit(e.left)
        right = None if e.right is None else self.visit(e.right)
        if left is e.left and right is e.right:
            return e
        else:
            return BoolExpr(e.operator, left, right, pos=e.pos)

    def if_(self, e):
        cond = self.visit(e.cond)
        yes = self.visit(e.value_yes)
        no = self.visit(e.value_no)
        if cond is e.cond and yes is e.value_yes and no is e.value_no:
            return e
        else:
            return IfExpr(cond, yes, no, pos=e.pos)


class ConditionalsSimplifier(BasicSimplifier):
    """
    More advanced simplifier class, eliminates const boolean expressions
    and their consequences (such as null items in lists).
    """
    def bool(self, e):
        e = super(ConditionalsSimplifier, self).bool(e)
        op = e.operator
        try:
            # Note: any of the as_py() calls below may throw, because the
            # subexpression may be non-const. That's OK, it just means we
            # cannot simplify the expression yet, so we just catch that
            # particular exception, NonConstError, later.
            if op == BoolExpr.NOT:
                return BoolValueExpr(not e.left.as_py(), pos=e.pos)
            elif op == BoolExpr.AND:
                return BoolValueExpr(e.left.as_py() and e.right.as_py(), pos=e.pos)
            elif op == BoolExpr.OR:
                # We can simplify or expressions even if one part is undeterminable
                left = right = None
                try:
                    left = e.left.as_py()
                    if left:
                        return BoolValueExpr(True, pos=e.pos)
                except NonConstError:
                    pass
                try:
                    right = e.right.as_py()
                    if right:
                        return BoolValueExpr(True, pos=e.pos)
                except NonConstError:
                    pass
                if left is not None and right is not None:
                    assert (left or right) == False
                    return BoolValueExpr(False, pos=e.pos)
            elif op == BoolExpr.EQUAL: 
                return BoolValueExpr(e.left.as_py() == e.right.as_py())
            elif op == BoolExpr.NOT_EQUAL: 
                return BoolValueExpr(e.left.as_py() != e.right.as_py())
        except NonConstError:
            pass
        return e

    def if_(self, e):
        e = super(ConditionalsSimplifier, self).if_(e)
        try:
            if e.cond.as_py():
                return e.value_yes
            else:
                return e.value_no
        except NonConstError:
            return e
