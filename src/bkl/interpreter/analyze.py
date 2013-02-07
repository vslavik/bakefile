#
#  This file is part of Bakefile (http://www.bakefile.org)
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


def detect_unused_vars(model):
    """
    Warns about unused variables -- they may indicate typos.
    """
    import re
    regex_vs_option = re.compile(r'vs[0-9]+\.option\.')

    class VariablesChecker(Visitor):
        def __init__(self):
            super(VariablesChecker, self).__init__()
            self.found = set()

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
                self.found.add(id(var))

    visitor = VariablesChecker()
    for var in model.all_variables():
        visitor.visit(var.value)
    used_vars = visitor.found
    for var in model.all_variables():
        if (id(var) not in used_vars and
                not var.is_property and
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

