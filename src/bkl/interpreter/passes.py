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
from bkl.error import Error, NonConstError, NotFoundError, TypeError, warning, error_context
from bkl.expr import Visitor, RewritingVisitor
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



def detect_potential_problems(model):
    """
    Run several warnings-generating steps, to detect common problems.
    """
    detect_self_references(model)
    detect_unused_vars(model)
    detect_missing_generated_outputs(model)


def normalize_and_validate_bool_subexpressions(model):
    """
    Normalizes bool expressions, i.e. ensures the conditions are valid bools.
    variables' values with respect to their types.
    """
    logger.debug("checking boolean expressions")
    for var in model.all_variables():
        bkl.vartypes.normalize_and_validate_bool_subexpressions(var.value)


def normalize_vars(model):
    """
    Normalizes variables' values with respect to their types. For example,
    changes non-list value expressions for lists into single-item lists.
    """
    logger.debug("normalizing variables")
    for var in model.all_variables():
        var.value = var.type.normalize(var.value)


def validate_vars(model):
    """
    Validates variables' values with respect to their types, i.e. check
    the correctness of the values. It is assumed that normalize_vars() was
    executed beforehand.
    """
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
        mod_toolsets = module.get_variable_value("toolsets")
        if toolset not in mod_toolsets.as_py():
            logger.debug("removing %s, because it isn't for toolset %s (is for: %s)",
                         module, toolset, mod_toolsets.as_py())
            mods_to_del.append(module)
    for module in mods_to_del:
        model.modules.remove(module)



class PathsNormalizer(RewritingVisitor):
    """
    Normalizes relative paths so that they are absolute. Paths relative to
    @srcdir are rewritten in terms of @top_srcdir. Paths relative to @builddir
    are translated in toolset-specific way. This is needed so that cross-module
    variables and paths uses produce correct results.

    You must call :meth:`set_context()` to associate a module or target before
    calling :meth:`visit()`.  Paths relative to @builddir can only be processed
    if the context was set to a target.
    """
    def __init__(self, project, toolset=None):
        self.toolset = toolset
        self.project = project
        self.module = self.target = None
        self.top_srcdir = os.path.abspath(project.top_module.srcdir)

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

    @memoized
    def _src_prefix(self, source_file):
        srcdir = os.path.abspath(self.project.get_srcdir(source_file))
        prefix = os.path.relpath(srcdir, start=self.top_srcdir)
        logger.debug('translating paths from %s with prefix "%s"', source_file, prefix)
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

    def path(self, e):
        if e.anchor == bkl.expr.ANCHOR_BUILDDIR and self.toolset is not None:
            if self.target is None:
                raise Error("@builddir references are not allowed outside of targets", pos=e.pos)
            bdir = self._builddir(self.target)
            e = bkl.expr.PathExpr(bdir.components + e.components,
                                  bdir.anchor, bdir.anchor_file,
                                  pos=e.pos)
        if e.anchor == bkl.expr.ANCHOR_SRCDIR:
            assert self.module is not None
            if e.anchor_file:
                source_file = e.anchor_file
            elif e.pos and e.pos.filename:
                source_file = e.pos.filename
            else:
                source_file = self.module.source_file
            prefix = self._src_prefix(source_file)
            components = e.components
            if prefix is not None:
                components = prefix + components
            e = bkl.expr.PathExpr(components,
                                  bkl.expr.ANCHOR_TOP_SRCDIR, None,
                                  pos=e.pos)
        return e


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

    norm = PathsNormalizer(model, toolset)

    for module in model.modules:
        norm.set_context(module)
        for var in module.variables.itervalues():
            var.value = norm.visit(var.value)
        for target in module.targets.itervalues():
            norm.set_context(target)
            for var in target.all_variables():
                var.value = norm.visit(var.value)


def make_variables_for_missing_props(model, toolset):
    """
    Creates variables for properties that don't have variables set yet.
    """
    logger.debug("adding properties' default values (%s)" % model)
    model.make_variables_for_missing_props(toolset)
    for part in model.child_parts():
        make_variables_for_missing_props(part, toolset)


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
