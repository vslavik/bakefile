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
This module contains the very core of Bakefile -- the interpreter,
:class:`bkl.interpreter.Interpreter`, and its supporting classes.
"""

from copy import deepcopy
import logging

import bkl.parser
import bkl.model
import bkl.api
import bkl.expr
import passes
from builder import Builder
from bkl.error import Error
from bkl.parser import parse_file

logger = logging.getLogger("bkl.interpreter")


class Interpreter(object):
    """
    The interpreter is responsible for doing everything necessary to
    "translate" input ``.bkl`` files into generated native makefiles. This
    includes building a project model from the input, checking it for
    correctness, optimizing it and creating outputs for all enabled toolsets.

    :class:`Interpreter` provides both high-level interface for single-call
    usage (see :meth:`process`) and other methods with finer granularity that
    allows you to inspect individual steps (most useful for the test suite).

    .. attribute: model

       Model of the project, as :class:`bkl.model.Project`. It's state always
       reflects current state of processing.
    """

    def __init__(self):
        self.model = bkl.model.Project()


    def process(self, ast):
        """
        Interprets input file and generates the outputs.

        :param ast: AST of the input file, as returned by
               :func:`bkl.parser.parse_file`.

        Processing is done in several phases:

        1. Basic model is built (see :class:`bkl.interpreter.builder.Builder`).
           No optimizations or checks are performed at this point.

        2. Several generic optimization and checking passes are run on the
           model.  Among other things, types correctness and other constraints
           are checked, variables are substituted and evaluated.

        3. The model is split into several copies, one per output toolset.

        4. Further optimization passes are done.

        5. Output files are generated.

        Step 1 is done by :meth:`add_module`. Steps 2-4 are done by
        :meth:`finalize` and step 5 is implemented in :meth:`generate`.
        """
        self.add_module(ast, self.model)
        self.finalize()
        self.generate()


    def process_file(self, filename):
        """Like :meth:`process()`, but takes filename as its argument."""
        self.process(parse_file(filename))


    def add_module(self, ast, parent):
        """
        Adds parsed AST to the model, without doing any optimizations. May be
        called more than once, with different parsed files.

        :param ast: AST of the input file, as returned by
               :func:`bkl.parser.parse_file`.
        """
        logger.info("processing %s", ast.filename)

        submodules = []
        b = Builder(on_submodule=lambda fn, pos: submodules.append((fn,pos)))

        module = b.create_model(ast, parent)

        while submodules:
            sub_filename, sub_pos = submodules[0]
            submodules.pop(0)
            try:
                sub_ast = parse_file(sub_filename)
            except IOError as e:
                if e.filename:
                    msg = "%s: %s" % (e.strerror, e.filename)
                else:
                    msg = e.strerror
                raise Error(msg, pos=sub_pos)
            self.add_module(sub_ast, module)


    def finalize(self):
        """
        Finalizes the model, i.e. checks it for validity, optimizes, creates
        per-toolset models etc.
        """
        logger.debug("finalizing the model")
        passes.detect_self_references(self.model)
        passes.detect_unused_vars(self.model)
        passes.normalize_and_validate_vars(self.model)
        passes.normalize_paths_in_model(self.model, toolset=None)
        passes.simplify_exprs(self.model)


    def finalize_for_toolset(self, toolset_model, toolset):
        """
        Finalizes after "toolset" variable was set.
        """
        # TODO: do this in finalize() instead
        passes.make_variables_for_missing_props(toolset_model, toolset)

        passes.eliminate_superfluous_conditionals(toolset_model)

        # This is done second time here (in addition to finalize()) to deal
        # with paths added by make_variables_for_missing_props() and paths with
        # @builddir (which is toolset specific and couldn't be resolved
        # earlier).  Ideally we wouldn't do it, but hopefully it's not all that
        # inefficient, as no real work is done for paths that are already
        # normalized:
        passes.normalize_paths_in_model(toolset_model, toolset)


    def make_toolset_specific_model(self, toolset):
        """
        Returns toolset-specific model, i.e. one that works only with
        *toolset*, has the ``toolset`` property set to it. The caller
        still needs to call finalize_for_toolset() on it.
        """
        model = deepcopy(self.model)
        # don't use Variable.from_property(), because it's read-only
        model.add_variable(bkl.model.Variable.from_property(
                                              model.get_prop("toolset"),
                                              bkl.expr.LiteralExpr(toolset)))
        return model


    def generate(self):
        """
        Generates output files.
        """
        # collect all requested toolsets:
        toolsets = set()
        for module in self.model.modules:
            module_toolsets = module.get_variable_value("toolsets").as_py()
            toolsets.update(module_toolsets)
        logger.debug("toolsets to generate for: %s", list(toolsets))

        if not toolsets:
            raise Error("nothing to generate, \"toolsets\" property is empty")

        # and generate the outputs:
        for toolset in toolsets:
            self.generate_for_toolset(toolset)


    def generate_for_toolset(self, toolset):
        """
        Generates output for given *toolset*.
        """
        logger.debug("preparing model for toolset %s", toolset)
        model = self.make_toolset_specific_model(toolset)
        self.finalize_for_toolset(model, toolset)

        logger.debug("generating for toolset %s", toolset)
        bkl.api.Toolset.get(toolset).generate(model)
