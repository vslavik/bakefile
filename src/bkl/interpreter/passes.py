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

import logging
logger = logging.getLogger("bkl.pass")

import simplify
import bkl.vartypes


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
