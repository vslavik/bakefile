#
#  This file is part of Bakefile (http://bakefile.org)
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
from bkl.error import Error, CannotDetermineError, error_context
from bkl.api import Extension, Toolset, Property
from bkl.vartypes import PathType
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
    def comment(self, text):
        """
        Returns given (possibly multi-line) string formatted as a comment.

        :param text: text of the comment
        """
        return "%s\n" % "\n".join("# %s" % s for s in text.split("\n"))

    def var_definition(self, var, value):
        """
        Returns string with definition of a variable value, typically
        `var = value`.

        :param var:   variable being defined
        :param value: value of the variable; this string is already formatted
                      to be in make's syntax and may be multi-line
        """
        return "%s = %s\n" % (var, " \\\n\t".join(value.split("\n")))

    def target(self, name, deps, commands):
        """
        Returns string with target definition.

        :param name:     Name of the target.
        :param deps:     List of its dependencies. Items are strings
                         corresponding to some target's name (may be expressions
                         that reference a variable, in that case the string
                         must already be formatted with appropriate
                         :class:`bkl.expr.Formatter`).
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

    def multifile_target(self, outputs, outfiles, deps, commands):
        """
        Returns string with target definition for targets that produce multiple
        files. A typical example is Bison parser generator, which produces both
        .c and .h files.

        :param outputs:  List of output files of the rule, as objects.
        :param outfiles: List of output files of the rule, as strings.
        :param deps:     See target()
        :param commands: See target()
        """
        # TODO: Implement these. Could you pattern rules with GNU make,
        #       or stamp files.
        raise Error("rules with multiple output files not implemented yet (%s from %s)" % (outfiles, deps))


    def submake_command(self, directory, filename, target):
        """
        Returns string with command to invoke ``make`` in subdirectory
        *directory* on makefile *filename*, running *target*.
        """
        raise NotImplementedError


class MakefileExprFormatter(expr.Formatter):
    def __init__(self, toolset, paths_info):
        expr.Formatter.__init__(self, paths_info)
        self.toolset = toolset

    def literal(self, e):
        if '"' in e.value:
            return e.value.replace('"', '\\"')
        else:
            return e.value

    def path(self, e):
        if e.anchor in [expr.ANCHOR_BUILDDIR, expr.ANCHOR_TOP_BUILDDIR]:
            self.toolset.uses_builddir = True
        return super(MakefileExprFormatter, self).path(e)

    def placeholder(self, e):
        name = e.var
        if name == "arch":
            raise Error("multi-arch builds are not supported by makefiles ($(arch) referenced)", pos=e.pos)
        return "$(%s)" % name


class MakefileToolset(Toolset):
    """
    Base class for makefile-based toolsets.
    """
    #: :class:`MakefileFormatter`-derived class for this toolset.
    Formatter = None

    #: :class:`expr.Formatter`-derived class for this toolset.
    ExprFormatter = MakefileExprFormatter

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
        makefile = target["%s.makefile" % self.name]
        builddir = makefile.get_directory_path()
        return expr.PathExpr(builddir.components, expr.ANCHOR_TOP_BUILDDIR)

    def generate(self, project):
        # We need to know build graphs of all targets so that we can generate
        # dependencies on produced files. Worse yet, we need to have them for
        # all modules before generating the output, because of cross-module
        # dependencies.
        # TODO-MT: read only, can be ran in parallel
        from bkl.interpreter.passes import PathsNormalizer
        norm = PathsNormalizer(project)
        build_graphs = {}
        for t in project.all_targets():
            with error_context(t):
                if not t.should_build():
                    continue
                norm.set_context(t)
                graph = t.type.get_build_subgraph(self, t)
                for node in graph.all_nodes():
                    node.inputs = [norm.visit(e) for e in node.inputs]
                    node.outputs = [norm.visit(e) for e in node.outputs]
                    node.commands = [norm.visit(e) for e in node.commands]
                build_graphs[t] = graph

        for m in project.modules:
            with error_context(m):
                self._gen_makefile(build_graphs, m)

    def _gen_makefile(self, build_graphs, module):
        # Flag indicating whether this makefile actually builds anything.
        self.uses_builddir = False

        output_value = module.get_variable_value("%s.makefile" % self.name)
        output = output_value.as_native_path_for_output(module)

        paths_info = expr.PathAnchorsInfo(
                dirsep="/", # FIXME - format-configurable
                outfile=output,
                builddir=None,
                model=module)

        mk_fmt = self.Formatter()
        expr_fmt = self.ExprFormatter(self, paths_info)

        f = io.OutputFile(output, io.EOL_UNIX, creator=self, create_for=module)
        self.on_header(f, module)

        self._gen_settings(module, mk_fmt, expr_fmt, f)

        #FIXME: make this part of the formatter for (future) IdRefExpr
        def _format_dep(t):
            g = build_graphs[t].main
            if len(g.outputs) == 0:
                assert g.name
                if t.parent is not module:
                    raise Error("cross-module dependencies on phony targets (\"%s\") not supported yet" % t.name) # TODO
                out = g.name
            else:
                # FIXME: handle multi-output nodes too
                assert len(g.outputs) == 1
                out = g.outputs[0]
            return expr_fmt.format(out)

        def _get_submodule_deps(main, submodule):
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
                        if tmod is main:
                            mod_deps.add(_format_dep(tdep))
                        elif tmod.is_submodule_of(main):
                            while tmod.parent is not main:
                                tmod = tmod.parent
                            if tmod is not submodule:
                                mod_deps.add(tmod.name)
            return sorted(mod_deps)

        # Write the "all" target:
        all_targets = (
                      [_format_dep(t) for t in module.targets.itervalues()] +
                      [sub.name for sub in module.submodules]
                      )
        f.write(mk_fmt.target(name="all", deps=all_targets, commands=None))

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
                                 _get_submodule_deps(module, sub))
        for subname, subdir, subfile, subdeps in submakefiles.itervalues():
            subcmd = mk_fmt.submake_command(subdir, subfile, "all")
            f.write(mk_fmt.target(name=subname, deps=subdeps, commands=[subcmd]))
            phony_targets.append(subname)

        for t in module.targets.itervalues():
            with error_context(t):
                # collect target's dependencies
                target_deps = []
                for dep in t["deps"]:
                    tdep = module.project.get_target(dep.as_py())
                    tdepstr = _format_dep(tdep)
                    target_deps.append(tdepstr)
                    if tdep.parent is not module:
                        # link external dependencies with submodules to build them
                        tmod = tdep.parent
                        while tmod.parent is not None and tmod.parent is not module:
                            tmod = tmod.parent
                        if tmod in module.submodules:
                            targets_from_submodules[tdepstr] = tmod

                # generate code for the target's build graph:
                graph = build_graphs[t]
                for node in graph.all_nodes():
                    with error_context(node):
                        if node.outputs:
                            out = node.outputs
                        else:
                            out = [node.name]
                            phony_targets.append(expr_fmt.format(out[0]))

                        deps = [expr_fmt.format(i) for i in node.inputs]
                        if node is graph.main:
                            deps += target_deps

                        out_fmt = [expr_fmt.format(x) for x in out]
                        commands_fmt = [expr_fmt.format(c) for c in node.commands]
                        if len(out_fmt) == 1:
                            text = mk_fmt.target(name=out_fmt[0],
                                                 deps=deps,
                                                 commands=commands_fmt)
                        else:
                            text = mk_fmt.multifile_target(
                                                 outputs=out,
                                                 outfiles=out_fmt,
                                                 deps=deps,
                                                 commands=commands_fmt)
                        f.write(text)
                        all_targets += out_fmt

        # dependencies on submodules to build targets from them:
        if targets_from_submodules:
            f.write("# Targets from sub-makefiles:\n")
            for t, tsub in targets_from_submodules.iteritems():
                f.write(mk_fmt.target(name=t, deps=[submakefiles[tsub][0]], commands=None))

        # Write the "clean" target:
        clean_cmds = self._get_clean_commands(
                        mk_fmt, expr_fmt,
                        (build_graphs[t] for t in module.targets.itervalues()),
                        submakefiles.itervalues())
        f.write(mk_fmt.target(name="clean", deps=[], commands=clean_cmds))

        self.on_phony_targets(f, phony_targets)
        self.on_footer(f, module)

        f.commit()


    def _gen_settings(self, module, mk_fmt, expr_fmt, f):
        # TODO: only include settings used in this module _or_ its submodules
        #       (for recursive passing downwards)
        if not module.project.settings:
            return
        f.write("\n%s\n" % mk_fmt.comment("------------\nConfigurable settings:\n"))
        for setting in module.project.settings.itervalues():
            if setting["help"]:
                f.write(mk_fmt.comment(expr_fmt.format(setting["help"])))
            f.write(mk_fmt.var_definition(setting.name, expr_fmt.format(setting["default"])))
        f.write("\n%s\n" % mk_fmt.comment("------------"))

    def _get_clean_commands(self, mk_fmt, expr_fmt, graphs, submakefiles):
        if self.uses_builddir:
            for e in self.autoclean_extensions:
                p = expr.PathExpr([expr.LiteralExpr("*." + e)], expr.ANCHOR_BUILDDIR)
                yield "%s %s" % (self.del_command, expr_fmt.format(p))
        for g in graphs:
            for node in g.all_nodes():
                for f in node.outputs:
                    try:
                        if f.get_extension() not in self.autoclean_extensions:
                            yield "%s %s" % (self.del_command, expr_fmt.format(f))
                    except CannotDetermineError:
                        yield "%s %s" % (self.del_command, expr_fmt.format(f))

        for subname, subdir, subfile, subdeps in submakefiles:
            yield mk_fmt.submake_command(subdir, subfile, "clean")


    def on_header(self, file, module):
        """
        Called before starting generating the output to add any header text,
        typically used to pre-define any make variables.

        Call the base class version first to insert a warning about the file
        being auto-generated.
        """
        file.write("""\
# This file was automatically generated by bakefile.
#
# Any manual changes will be lost if it is regenerated,
# modify the source .bkl file instead if possible.
""")

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
