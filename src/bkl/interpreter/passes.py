#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2008-2012 Vaclav Slavik
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
import bkl.expr
import bkl.model
from bkl.error import Error, NonConstError, TypeError, warning
from bkl.expr import Visitor
from bkl.utils import memoized


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
        placeholder = Visitor.noop

        def reference(self, e):
            var = e.context.get_variable(e.var)
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
        try:
            var.type.validate(var.value)
        except TypeError as err:
            # TODO: add this as a remark to the error object
            err.msg = "variable \"%s\" (%s): %s" % (var.name, var.type, err.msg)
            raise


def remove_disabled_model_parts(model, toolset):
    """
    Removes disabled targets, source files etc. from the model. Disabled parts
    are those with ``condition`` variable evaluating to false.
    """

    def _should_remove(part):
        if part.condition is None:
            return False
        try:
            return not part.condition.as_py()
        except NonConstError:
            cond = simplify.simplify(part.condition)
            raise Error("condition for building %s couldn't be resolved\n(condition \"%s\" set at %s)" %
                        (part, cond, cond.pos),
                        pos=part.source_pos)

    def _remove_from_list(parts):
        to_del = []
        for p in parts:
            if _should_remove(p):
                to_del.append(p)
        for p in to_del:
            logger.debug("removing disabled %s from %s", p, p.parent)
            parts.remove(p)

    for module in model.modules:
        targets_to_del = []
        for target in module.targets.itervalues():
            if _should_remove(target):
                targets_to_del.append(target)
                continue
            _remove_from_list(target.sources)
            _remove_from_list(target.headers)
        for target in targets_to_del:
            logger.debug("removing disabled %s", target)
            del module.targets[target.name]

    # remove any empty submodules:
    mods_to_del = []
    for module in model.modules:
        if module is model.top_module:
            continue
        if not list(module.submodules) and not module.targets:
            logger.debug("removing empty %s", module)
            mods_to_del.append(module)
        mod_toolsets = module.get_variable("toolsets")
        if mod_toolsets and toolset not in mod_toolsets.value.as_py():
            logger.debug("removing %s, because it isn't for toolset %s (is for: %s)",
                         module, toolset, mod_toolsets.value.as_py())
            mods_to_del.append(module)
    for module in mods_to_del:
        model.modules.remove(module)



class PathsNormalizer(Visitor):
    """
    Normalizes relative paths so that they are absolute. Paths relative to
    @srcdir are rewritten in terms of @top_srcdir. Paths relative to @builddir
    are translated in toolset-specific way. This is needed so that cross-module
    variables and paths uses produce correct results.

    You must call :meth:`set_context()` to associate a module or target before
    calling :meth:`visit()`.  Paths relative to @builddir can only be processed
    if the context was set to a target.

    Performs the normalization in-place.
    """
    def __init__(self, toolset=None):
        self.toolset = toolset
        self.module = self.target = None

    def set_context(self, context):
        """
        Sets context to perform the translation in. This is either a module or
        target from the model.

        Note that @builddir cannot be translated without a target context.
        """
        if isinstance(context, bkl.model.Target):
            self.module = context.parent
            self.target = context
        else:
            self.module = context
            self.target = None

    def visit_all(self, all):
        """Visits all items in the iterable."""
        for x in all:
            self.visit(x)

    @memoized
    def _src_prefix(self, module):
        top_srcdir = os.path.abspath(os.path.dirname(module.project.top_module.source_file))
        srcdir = os.path.abspath(os.path.dirname(module.source_file))
        prefix = os.path.relpath(srcdir, start=top_srcdir)
        logger.debug('translating paths from %s with prefix "%s"',
                     module.source_file, prefix)
        if prefix == ".":
            return None
        else:
            lst = prefix.split(os.path.sep)
            return [bkl.expr.LiteralExpr(i) for i in lst]

    @memoized
    def _builddir(self, target):
        builddir = self.toolset.get_builddir_for(target)
        assert builddir.anchor != bkl.expr.ANCHOR_BUILDDIR
        logger.debug('translating @builddir paths of %s into %s', target, builddir)
        return builddir

    literal = Visitor.noop
    bool_value = Visitor.noop
    null = Visitor.noop
    reference = Visitor.noop
    placeholder = Visitor.noop
    concat = Visitor.visit_children
    list = Visitor.visit_children
    bool = Visitor.visit_children
    if_ = Visitor.visit_children

    def path(self, e):
        self.visit_children(e)
        if e.anchor == bkl.expr.ANCHOR_BUILDDIR and self.toolset is not None:
            if self.target is None:
                raise Error("@builddir references are not allowed outside of targets", pos=e.pos)
            bdir = self._builddir(self.target)
            e.anchor = bdir.anchor
            e.components = bdir.components + e.components
        if e.anchor == bkl.expr.ANCHOR_SRCDIR:
            assert self.module is not None
            prefix = self._src_prefix(self.module)
            if prefix is not None:
                e.components = prefix + e.components
            e.anchor = bkl.expr.ANCHOR_TOP_SRCDIR


def normalize_paths_in_model(model, toolset):
    """
    Normalizes relative paths so that they are absolute. Paths relative to
    @srcdir are rewritten in terms of @top_srcdir. Paths relative to @builddir
    are translated in toolset-specific way. This is needed so that cross-module
    variables and paths uses produce correct results.

    Performs the normalization in-place for the whole model.
    """
    logger.debug("translating relative paths into absolute")

    if toolset is not None:
        toolset = bkl.api.Toolset.get(toolset)
    norm = PathsNormalizer(toolset)

    for module in model.modules:
        norm.set_context(module)
        norm.visit_all(var.value for var in module.variables.itervalues())
        for target in module.targets.itervalues():
            norm.set_context(target)
            norm.visit_all(var.value for var in target.all_variables())


def make_variables_for_missing_props(model, toolset):
    """
    Creates variables for properties that don't have variables set yet.
    """
    logger.debug("adding properties' default values")
    model.make_variables_for_missing_props(toolset)
    for m in model.modules:
        m.make_variables_for_missing_props(toolset)
        for t in m.targets.itervalues():
            t.make_variables_for_missing_props(toolset)


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
        logger.debug("removing superfluous conditional expressions: pass %i", iteration)
        modified = False
        for var in model.all_variables():
            old = var.value
            var.value = simplifier.visit(var.value)
            if old is not var.value:
                logger.debug("new pass triggered because of this change: {%s} -> {%s}", old, var.value)
                modified = True
        if modified:
            iteration += 1
        else:
            break
