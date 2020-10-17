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

"""
Model analysis -- detecting problems etc.
"""

import logging
logger = logging.getLogger("bkl.analyze")

import bkl.vartypes
import bkl.expr
import bkl.model
import bkl.vartypes
from bkl.error import Error, warning, error_context
from bkl.expr import Visitor


def detect_self_references(model):
    """
    Verifies that recursive self-referencing loops (e.g. "foo = $(foo)")
    don't exist.
    """
    logger.debug("checking for self-references")

    class SelfRefChecker(Visitor):
        def __init__(self):
            super(SelfRefChecker, self).__init__()
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
        placeholder = Visitor.noop

        def reference(self, e):
            var = e.get_variable()
            if var is None:
                # reference to default value of a property
                return
            if var in self.stack:
                # TODO: include complete stack of messages+positions
                raise Error('variable "%s" is defined recursively, references itself' % var.name,
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


# Key usage tracking by not the variable object, but the source code position
# of its declaration. In practice, variable may be duplicated in non-obvious
# ways, e.g. at different submodules, or due to imported files. Using source
# code position does what is expected from unused variables warnings.
def _usage_id(var):
    return var.pos

class _UsedVariablesTracker(Visitor):
    def __init__(self):
        super(_UsedVariablesTracker, self).__init__()
        self.used_vars = set()

    literal = Visitor.noop
    bool_value = Visitor.noop
    null = Visitor.noop
    concat = Visitor.visit_children
    list = Visitor.visit_children
    path = Visitor.visit_children
    bool = Visitor.visit_children
    if_ = Visitor.visit_children
    placeholder = Visitor.noop

    def reference(self, e):
        var = e.get_variable()
        if var is not None and not var.is_property:
            self.used_vars.add(_usage_id(var))

    def is_used(self, var):
        """Returns if the variable is referenced somewhere."""
        return _usage_id(var) in self.used_vars

# Global list of all used variables
usage_tracker = _UsedVariablesTracker()

def mark_variable_as_used(var):
    usage_tracker.used_vars.add(_usage_id(var))

def mark_variables_in_expr_as_used(expression):
    """
    Marks all variables referenced in the expression as used.

    Should be manually called for expressions that don't end up in the created
    model (e.g. expressions used inside sources {...}) to prevent spurious
    unused variables warnings.
    """
    usage_tracker.visit(expression)


def detect_unused_vars(model):
    """
    Warns about unused variables -- they may indicate typos.
    """
    # First of all, iterate over all variables and mark their usage of other
    # variables. Notice that it's possible that some code explicitly marked
    # variables as used with mark_variables_in_expr_as_used() before this step.
    for var in model.all_variables():
        usage_tracker.visit(var.value)

    # Not emit warnings for unused variables.
    import re
    regex_vs_option = re.compile(r'(msvs|vs[0-9]+)\.option\.')

    for var in model.all_variables():
        if (not var.is_property and
                not usage_tracker.is_used(var) and
                # FIXME: Handle these cases properly. Have a properties group
                #        declaration similar to Property, with type checking and
                #        automated docs and all. Then test for it here as other
                #        properties are tested for.
                not regex_vs_option.match(var.name) and
                # FIXME: Handle this case properly.
                var.name != "configurations"):
            warning('variable "%s" is never used', var.name, pos=var.value.pos)


def detect_missing_generated_outputs(model):
    """
    Warns about generated source files not included in sources/headers.
    """
    for t in model.all_targets():
        for srcfile in t.all_source_files():
            with error_context(srcfile):
                if not srcfile["compile-commands"]:
                    continue
                sources = set(ch.name for ch in t.child_parts())
                outputs = set(i for c,i in bkl.expr.enum_possible_values(srcfile["outputs"]))
                for item in outputs:
                    partname = bkl.expr.get_model_name_from_path(item)
                    if partname not in sources:
                        warning("file %s generated from %s is not among sources or headers of target \"%s\"",
                                item, srcfile.filename, t.name, pos=item.pos)

