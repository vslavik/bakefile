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

"""
Implementation of misc interpreter passes -- optimization, checking etc.
"""

import logging
logger = logging.getLogger("bkl.pass")


def normalize_vars(model):
    """
    Normalizes variables' values with respect to their types. For example,
    changes non-list value expressions for lists into single-item lists.
    """
    logger.debug("normalizing variables")
    for var in model.all_variables():
        var.value = var.type.normalize(var.value)



def check_var_types(model):
    """
    Validates that values assigned to variables correspond to their types.
    Inspects all variables in the model, including all modules and targets.
    """
    logger.debug("checking types of variables")
    for var in model.all_variables():
        var.type.validate(var.value)
