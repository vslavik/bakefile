#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2009-2013 Vaclav Slavik
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
Foundation code for makefile-based toolsets.

All makefile-based toolsets should derive from MakefileToolset defined
in this module.
"""

import os.path

import io
import expr
from bkl.error import Error, error_context
from bkl.api import Extension, Toolset, Property
from bkl.vartypes import PathType
from bkl.interpreter.passes import PathsNormalizer
from bkl.utils import OrderedDict


class MakefileFormatter(Extension):
    """
    MakefileFormatter extensions are used to format makefiles content
    (i.e. targets and their commands) in the particular makefiles format.

    This includes things such as expressing conditional content, referencing
    variables and so on.

    Note that formatters do *not* handle platform- or compiler-specific things,
    e.g. path separators or compiler invocation. There are done by
    :class:`bkl.expr.Formatter` and :class:`bkl.api.FileCompiler` classes.

    This base class implements methods that are common for most make variants;
    derived classes can override them and they must implement the rest.
    """
    @staticmethod
    def comment(text):
        """
        Returns given (possibly multi-line) string formatted as a comment.

        :param text: text of the comment
        """
        return "\n".join("# %s" % s for s in text.split("\n"))

    @staticmethod
    def var_reference(var):
        """
        Returns string with code for referencing a variable.

        For most `make` implementations out there, `var_reference("FOO")`
        returns `"$(FOO)"`.

        :param var: string with name of the variable
        """
        return "$(%s)" % var

    @staticmethod
    def var_definition(var, value):
        """
        Returns string with definition of a variable value, typically
        `var = value`.

        :param var:   variable being defined
        :param value: value of the variable; this string is already formatted
                      to be in make's syntax (e.g. using var_reference()) and
                      may be multi-line
        """
        return "%s = %s" % (var, " \\\n\t".join(value.split("\n")))

    @staticmethod
    def target(name, deps, commands):
        """
        Returns string with target definition.

        :param name:     Name of the target.
        :param deps:     List of its dependencies. Items are strings
                         corresponding to some target's name (may be expressions
                         that reference a variable, in that case the string
                         must already be processed with :meth:`var_reference`).
                         May be empty.
        :param commands: List of commands to execute to build the target; they
                         are already formatted to be in make's syntax and each
                         command in the list is single-line shell command.
                         May be :const:`None`.
        """
        out = "%s:" % name
        if deps:
            out += " "
            out += " ".join(deps)
        if commands:
            for c in commands:
                out += "\n\t%s" % c
        out += "\n\n"
        return out

    @staticmethod
    def multifile_target(outfiles, deps, commands):
        """
        Returns string with target definition for targets that produce multiple
        files. A typical example is Bison parser generator, which produces both
        .c and .h files.

        :param outfiles: List of output files of the rule, as strings.
        :param deps:     See target()
        :param commands: See target()
        """
        # TODO: Implement these. Could you pattern rules with GNU make,
        #       or stamp files.
        raise Error("rules with multiple output files not implemented yet (%s from %s)" % (outfiles, deps))


    @staticmethod
    def submake_command(directory, filename, target):
        """
        Returns string with command to invoke ``make`` in subdirectory
        *directory* on makefile *filename*, running *target*.
        """
        raise NotImplementedError


class _MakefileExprFormatter(expr.Formatter):
    def __init__(self, makefile_formatter, paths_info):
        super(_MakefileExprFormatter, self).__init__(paths_info)
        self.makefile_formatter = makefile_formatter

    def literal(self, e):
        if '"' in e.value:
            return e.value.replace('"', '\\"')
        else:
            return e.value

    def reference(self, e):
        # FIXME: don't do this for references to options or other stuff
        #        that isn't meant to be expanded
        return self.format(e.get_value())
        #return self.makefile_formatter.var_reference(e.var)


class MakefileToolset(Toolset):
    """
    Base class for makefile-based toolsets.
    """
    #: :class:`MakefileFormatter`-derived class for this toolset.
    Formatter = None

    #: Default filename from output makefile.
    default_makefile = None

    #: Files with extensions from this list will be automatically deleted
    #: by "make clean".
    autoclean_extensions = []

    #: Command used to delete files
    del_command = None

    @classmethod
    def properties_module(cls):
        yield Property("%s.makefile" % cls.name,
                       type=PathType(),
                       default=cls.default_makefile,
                       inheritable=False,
                       doc="Name of output file for module's makefile.")

    def get_builddir_for(self, target):
        # FIXME: use configurable build dir
        makefile = target.parent["%s.makefile" % self.name]
        return makefile.get_directory_path()

    def generate(self, project):
        # We need to know build graphs of all targets so that we can generate
        # dependencies on produced files. Worse yet, we need to have them for
        # all modules before generating the output, because of cross-module
        # dependencies.
        # TODO-MT: read only, can be ran in parallel
        build_graphs = {}
        norm = PathsNormalizer(project)
        for t in project.all_targets():
            with error_context(t):
                norm.set_context(t)
                graph = t.type.get_build_subgraph(self, t)
                assert len(graph) > 0, "Build graph for %s is empty" % t
                for node in graph:
                    node.inputs = [norm.visit(e) for e in node.inputs]
                    node.outputs = [norm.visit(e) for e in node.outputs]
                    node.commands = [norm.visit(e) for e in node.commands]
                build_graphs[t] = graph

        for m in project.modules:
            with error_context(m):
                self._gen_makefile(build_graphs, m)

    def _get_submodule_deps(self, main, submodule):
        """
        Return list of dependencies that 'submodule' has on other submodules of
        'main'.  Submodules have dependency if a target from one depends on a
        target from another.
        """
        mod_deps = set()
        project = main.project
        inspect = [submodule] + [p for p in project.modules if p.is_submodule_of(submodule)]
        for mod in inspect:
            for target in mod.targets.itervalues():
                for dep in target["deps"]:
                    tdep = project.get_target(dep.as_py())
                    tmod = tdep.parent
                    if tmod.is_submodule_of(main):
                        while tmod.parent is not main:
                            tmod = tmod.parent
                        if tmod is not submodule:
                            mod_deps.add(tmod.name)
        return sorted(mod_deps)

    def _gen_makefile(self, build_graphs, module):
        output_value = module.get_variable_value("%s.makefile" % self.name)
        output = output_value.as_native_path_for_output(module)

        paths_info = expr.PathAnchorsInfo(
                dirsep="/", # FIXME - format-configurable
                outfile=output,
                builddir=os.path.dirname(output), # FIXME: use configurable build dir
                model=module)

        expr_fmt = _MakefileExprFormatter(self.Formatter, paths_info)

        f = io.OutputFile(output, io.EOL_UNIX, creator=self, create_for=module)
        self.on_header(f, module)

        for v in module.variables:
            pass

        #FIXME: make this part of the formatter for (future) IdRefExpr
        def _format_dep(t):
            # FIXME: instead of using the first node, use some main_node
            g = build_graphs[t][0]
            if g.name:
                if t.parent is not module:
                    raise Error("cross-module dependencies on phony targets (\"%s\") not supported yet" % t.name) # TODO
                out = g.name
            else:
                # FIXME: handle multi-output nodes too
                assert len(g.outputs) == 1
                out = g.outputs[0]
            return expr_fmt.format(out)

        # Write the "all" target:
        all_targets = (
                      [_format_dep(t) for t in module.targets.itervalues()] +
                      [sub.name for sub in module.submodules]
                      )
        f.write(self.Formatter.target(name="all", deps=all_targets, commands=None))

        phony_targets = ["all", "clean"]

        targets_from_submodules = OrderedDict()
        submakefiles = OrderedDict()
        for sub in module.submodules:
            subpath = sub.get_variable_value("%s.makefile" % self.name)
            # FIXME: use $dirname(), $basename() functions, this is hacky
            subdir = subpath.get_directory_path()
            subfile = subpath.components[-1]
            submakefiles[sub] = (sub.name,
                                 expr_fmt.format(subdir),
                                 expr_fmt.format(subfile),
                                 self._get_submodule_deps(module, sub))
        for subname, subdir, subfile, subdeps in submakefiles.itervalues():
            subcmd = self.Formatter.submake_command(subdir, subfile, "all")
            f.write(self.Formatter.target(name=subname, deps=subdeps, commands=[subcmd]))
            phony_targets.append(subname)

        for t in module.targets.itervalues():
            with error_context(t):
                graph = build_graphs[t]
                for node in graph:
                    with error_context(node):
                        if node.name:
                            out = [node.name]
                            phony_targets.append(expr_fmt.format(out[0]))
                        else:
                            out = node.outputs

                        deps = [expr_fmt.format(i) for i in node.inputs]
                        for dep in t["deps"]:
                            tdep = module.project.get_target(dep.as_py())
                            tdepstr = _format_dep(tdep)
                            deps.append(tdepstr)
                            if tdep.parent is not module:
                                # link external dependencies with submodules to build them
                                tmod = tdep.parent
                                while tmod.parent is not None and tmod.parent is not module:
                                    tmod = tmod.parent
                                if tmod in module.submodules:
                                    targets_from_submodules[tdepstr] = tmod

                        out_fmt = [expr_fmt.format(x) for x in out]
                        commands_fmt = [expr_fmt.format(c) for c in node.commands]
                        if len(out_fmt) == 1:
                            text = self.Formatter.target(name=out_fmt[0],
                                                         deps=deps,
                                                         commands=commands_fmt)
                        else:
                            text = self.Formatter.multifile_target(
                                                         outfiles=out_fmt,
                                                         deps=deps,
                                                         commands=commands_fmt)
                        f.write(text)
                        all_targets += out_fmt

        # dependencies on submodules to build targets from them:
        if targets_from_submodules:
            f.write("# Targets from sub-makefiles:\n")
            for t, tsub in targets_from_submodules.iteritems():
                f.write(self.Formatter.target(name=t, deps=[submakefiles[tsub][0]], commands=None))

        # Write the "clean" target:
        clean_cmds = self._get_clean_commands(
                        expr_fmt,
                        (build_graphs[t] for t in module.targets.itervalues()),
                        submakefiles.itervalues())
        f.write(self.Formatter.target(name="clean", deps=[], commands=clean_cmds))

        self.on_phony_targets(f, phony_targets)
        self.on_footer(f, module)

        f.commit()

    def _get_clean_commands(self, expr_fmt, graphs, submakefiles):
        for e in self.autoclean_extensions:
            yield "%s *.%s" % (self.del_command, e)
        for g in graphs:
            for node in g:
                for f in node.outputs:
                    if f.get_extension() not in self.autoclean_extensions:
                        yield "%s %s" % (self.del_command, expr_fmt.format(f))
        for subname, subdir, subfile, subdeps in submakefiles:
            yield self.Formatter.submake_command(subdir, subfile, "clean")

    def on_header(self, file, module):
        """
        Called before starting generating the output to add any header text,
        typically used to insert a warning about the file being auto-generated.
        """
        pass

    def on_phony_targets(self, file, targets):
        """
        Called with a list of all phony (i.e. not producing actual files)
        targets (as their names as strings) when generating given file.
        """
        pass

    def on_footer(self, file, module):
        """
        Called at the end of generating the output to add any ending text, for
        example unconditional inclusion of dependencies tracking code.
        """
        pass
