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
Implementation of misc interpreter passes -- optimization, checking etc.
"""

import os.path

import logging
logger = logging.getLogger("bkl.pass")

import simplify
import bkl.vartypes
import bkl.error
import bkl.expr
from bkl.expr import Visitor


def detect_self_references(model):
    """
    Verifies that recursive self-referencing loops (e.g. "foo = $(foo)")
    don't exist.
    """
    logger.debug("checking for self-references")

    class SelfRefChecker(Visitor):
        def __init__(self):
            self.stack = []
            self.checked = set()

        literal = Visitor.noop
        bool_value = Visitor.noop
        null = Visitor.noop
        concat = Visitor.visit_children
        list = Visitor.visit_children
        path = Visitor.visit_children
        bool = Visitor.visit_children
        if_ = Visitor.visit_children

        def reference(self, e):
            var = e.context.get_variable(e.var)
            if var is None:
                # reference to default value of a property
                return
            if var in self.stack:
                # TODO: include complete stack of messages+positions
                raise bkl.error.Error('variable "%s" is defined recursively, references itself' % var.name,
                                      pos=e.pos)
            else:
                self.check(var)

        def check(self, var):
            if var in self.checked:
                return
            self.stack.append(var)
            try:
                self.visit(var.value)
            finally:
                self.stack.pop()
            self.checked.add(var)

    visitor = SelfRefChecker()

    for var in model.all_variables():
        visitor.check(var)


def normalize_and_validate_vars(model):
    """
    Normalizes variables' values with respect to their types. For example,
    changes non-list value expressions for lists into single-item lists.
    """
    logger.debug("checking boolean expressions")
    for var in model.all_variables():
        bkl.vartypes.normalize_and_validate_bool_subexpressions(var.value)

    logger.debug("normalizing variables")
    for var in model.all_variables():
        var.value = var.type.normalize(var.value)

    logger.debug("checking types of variables")
    for var in model.all_variables():
        var.type.validate(var.value)


def normalize_srcdir_paths(model):
    """
    Normalizes paths so that they are not relative to @srcdir: all such paths
    are rewritten in terms of @top_srcdir. This is needed so that cross-module
    variables and paths uses produce correct results.

    Performs the normalization in-place for the whole model.
    """
    logger.debug("translating @srcdir paths to @top_srcdir ones")

    class PathsNormalizer(Visitor):
        def __init__(self, prefix):
            if prefix == ".":
                self.prefix = None
            else:
                lst = prefix.split(os.path.sep)
                self.prefix = [bkl.expr.LiteralExpr(i) for i in lst]

        literal = Visitor.noop
        bool_value = Visitor.noop
        null = Visitor.noop
        reference = Visitor.noop
        concat = Visitor.visit_children
        list = Visitor.visit_children
        bool = Visitor.visit_children
        if_ = Visitor.visit_children

        def path(self, e):
            self.visit_children(e)
            if e.anchor == bkl.expr.ANCHOR_SRCDIR:
                if self.prefix is not None:
                    e.components = self.prefix + e.components
                e.anchor = bkl.expr.ANCHOR_TOP_SRCDIR

    top_srcdir = os.path.abspath(model.top_module.source_file)
    for module in model.modules:
        srcdir = os.path.abspath(module.source_file)
        prefix = os.path.relpath(srcdir, start=top_srcdir)
        norm = PathsNormalizer(prefix)
        for var in module.all_variables():
            norm.visit(var.value)


def simplify_exprs(model):
    """
    Simplify expressions in the model. This does "cheap" simplifications such
    as merging concatenated literals, recognizing always-false conditions,
    eliminating unnecessary variable references (turn ``foo=$(x);bar=$(foo)``
    into ``bar=$(x)``) etc.
    """
    logger.debug("simplifying expressions")
    simplifier = simplify.BasicSimplifier()
    for var in model.all_variables():
        var.value = simplifier.visit(var.value)


def eliminate_superfluous_conditionals(model):
    """
    Removes as much of conditional content as possible. This involves doing
    as many optimizations as possible, even if the calculation is relatively
    expensive (compared to simplify_exprs()).
    """
    iteration = 1
    simplifier = simplify.ConditionalsSimplifier()
    while True:
        logger.debug("removing superfluous conditional expressions: pass %i" % iteration)
        modified = False
        for var in model.all_variables():
            old = var.value
            var.value = simplifier.visit(var.value)
            if old is not var.value:
                modified = True
        if modified:
            iteration += 1
        else:
            break
