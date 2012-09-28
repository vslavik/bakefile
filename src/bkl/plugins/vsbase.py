#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2012 Vaclav Slavik
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
Base classes for all Visual Studio toolsets.
"""

import uuid
import types
from xml.sax.saxutils import escape, quoteattr
from functools import partial, update_wrapper

import logging
logger = logging.getLogger("bkl.vsbase")

import bkl.expr
from bkl.utils import OrderedDict
from bkl.error import error_context, warning, Error, CannotDetermineError
from bkl.api import Toolset, Property
from bkl.model import ConfigurationProxy
from bkl.vartypes import PathType, StringType, BoolType
from bkl.io import OutputFile, EOL_WINDOWS


# Namespace constants for the GUID function
NAMESPACE_PROJECT   = uuid.UUID("{D9BD5916-F055-4D77-8C69-9448E02BF433}")
NAMESPACE_SLN_GROUP = uuid.UUID("{2D0C29E0-512F-47BE-9AC4-F4CAE74AE16E}")
NAMESPACE_INTERNAL =  uuid.UUID("{BAA4019E-6D67-4EF1-B3CB-AE6CD82E4060}")

def GUID(namespace, solution, data):
    """
    Generates GUID in given namespace, for given solution (bkl project), with
    given data (typically, target ID).
    """
    g = uuid.uuid5(namespace, '%s/%s' % (str(solution), str(data)))
    return str(g).upper()


class Node(object):
    """
    Convenience representation of XML node for project file output. It provides
    two useful features:

      1. Ability to concisely specify attributes
      2. Values aren't limited to strings, they may be any Python objects
         convertible to strings. In particular, they may be
         :class:`bkl.expr.Expr` instances and they will be formatted correctly.

    Attributes are added to the node using keyword arguments to the constructor
    or using dictionary-like access:
    >>> node["Label"] = "PropertySheets"

    Child nodes are added using the :meth:`add()` method.
    """
    def __init__(self, name, text=None, **kwargs):
        """
        Creates an XML node with given element name. If provided, the text is
        used for its textual content. Any provided keyword arguments are used
        to add attributes to the node.

        Examples:

        >>> Node("ImportGroup", Label="PropertySheets", Foo="A")
            # creates <ImportGroup Label="PropertySheets" Foo="a"/>
        >>> Node("LinkIncremental", True)
            # creates <LinkIncremental>true</LinkIncremental>
        """
        self.name = name
        self.text = text
        self.attrs = OrderedDict()
        self.children = []
        for key in sorted(kwargs.keys()):
            self.attrs[key] = kwargs[key]

    def __setitem__(self, key, value):
        self.attrs[key] = value

    def __getitem__(self, key):
        return self.attrs[key]

    def add(self, *args, **kwargs):
        """
        Add a child to this node. There are several ways of invoking add():

        The argument may be another node:
        >>> n.add(Node("foo"))

        Or it may be key-value pair, where the value is bkl.expr.Expr or any
        Python value convertible to string; the first argument is name of child
        element and the second one is its textual value:
        >>> n.add("ProjectGuid", "{31DC1570-67C5-40FD-9130-C5F57BAEBA88}")
        >>> n.add("LinkIncremental", target["vs-incremental-link"])

        Or it can take the same arguments that Node constructor takes; this is
        equivalent to creating a Node using the same arguments and than adding
        it using the first form of add():
        >>> n.add("ImportGroup", Label="PropertySheets")
        """
        assert len(args) > 0
        arg0 = args[0]
        if len(args) == 1:
            if isinstance(arg0, Node):
                self.children.append((arg0.name, arg0))
                return
            elif isinstance(arg0, types.StringType):
                self.children.append((arg0, Node(arg0, **kwargs)))
                return
        elif len(args) == 2:
            if isinstance(arg0, types.StringType) and len(kwargs) == 0:
                    self.children.append((arg0, args[1]))
                    return
        assert 0, "add() is confused: what are you trying to do?"

    def has_children(self):
        return len(self.children) > 0


class VSExprFormatter(bkl.expr.Formatter):
    list_sep = ";"

    configuration_ref = "$(Configuration)"

    def reference(self, e):
        if e.var == "config":
            return self.configuration_ref
        else:
            assert False, "All references should be expanded in VS output"

    def bool_value(self, e):
        return "true" if e.value else "false"


class VSList(object):
    """
    Helper class for use with XmlFormatter to represent lists with different
    delimiters. It's constructor takes the delimiter character as its first argument,
    followed by any number of Python lists or ListExprs that will be joined.
    """
    def __init__(self, list_sep, *args):
        self.list_sep = list_sep
        self.items = []
        for a in args:
            self.items += list(a)

    def append(self, item):
        """Adds an item (not list!) to the list."""
        self.items.append(item)

    def __nonzero__(self):
        return bool(self.items)
    def __len__(self):
        return len(self.items)
    def __iter__(self):
        return iter(self.items)


XML_HEADER = """\
<?xml version="1.0" encoding="%(charset)s"?>
<!-- This file was generated by Bakefile (http://bakefile.org).
     Do not modify, all changes will be overwritten! -->
"""

class XmlFormatter(object):
    """
    Formats Node hierarchy into XML output that looks like Visual Studio's
    native format.
    """

    #: String used to increase indentation
    indent_step = "  "

    #: Class for expressions formatting
    ExprFormatter = VSExprFormatter

    def __init__(self, paths_info, charset="utf-8"):
        self.charset = charset
        self.expr_formatter = self.ExprFormatter(paths_info)

    def format(self, node):
        """
        Formats given node as an XML document and returns the document as a
        string.
        """
        return XML_HEADER % dict(charset=self.charset) + self._do_format_node(node, "")

    def _do_format_node(self, n, indent):
        attrs = self._get_quoted_nonempty_attrs(n)
        if n.children:
            children_markup = ""
            assert not n.text, "nodes with both text and children not implemented"
            subindent = indent + self.indent_step
            for key, value in n.children:
                if isinstance(value, Node):
                    assert key == value.name
                    children_markup += self._do_format_node(value, subindent)
                else:
                    try:
                        v = escape(self.format_value(value))
                        if v:
                            children_markup += "%s<%s>%s</%s>\n" % (subindent, key, v, key)
                        # else: empty value, don't write that
                    except CannotDetermineError as e:
                        raise Error("cannot set property \"%s\" to non-constant expression \"%s\" (%s)" %
                                    (key, value, e.msg), pos=value.pos)
        else:
            children_markup = None
        return self.format_node(n.name, attrs, n.text, children_markup, indent)

    def format_node(self, name, attrs, text, children_markup, indent):
        """
        Formats given Node instance, indented with *indent* text.

        Content is either *text* or *children_markup*; the other is None. All
        arguments already use properly escaped markup; values in *attrs* are
        quoted and escaped.
        """
        s = "%s<%s" % (indent, name)
        if attrs:
            for key, value in attrs:
                s += ' %s=%s' % (key, value)
        if text:
            s += ">%s</%s>\n" % (text, name)
        elif children_markup:
            s += ">\n%s%s</%s>\n" % (children_markup, indent, name)
        else:
            s += " />\n"
        return s

    def format_value(self, val):
        """
        Formats given value (of any type) into XML text.
        """
        if isinstance(val, bkl.expr.Expr):
            return self.expr_formatter.format(val)
        elif isinstance(val, types.BooleanType):
            return self.expr_formatter.bool_value(bkl.expr.BoolValueExpr(val))
        elif isinstance(val, types.ListType):
            return self.expr_formatter.list_sep.join(self._formatted_list_items(val))
        elif isinstance(val, VSList):
            return val.list_sep.join(self._formatted_list_items(val))
        else:
            return str(val)

    def _formatted_list_items(self, items):
        for x in items:
            f = self.format_value(x)
            if f:
                yield f

    def _get_quoted_nonempty_attrs(self, n):
        ret = []
        for key, value in n.attrs.iteritems():
            fv = self.format_value(value)
            if fv:
                ret.append((key, quoteattr(fv)))
        return ret


class VSProjectBase(object):
    """
    Base class for all Visual Studio projects.

    To be used by code that interfaces VS toolsets.
    """

    #: Version of the project.
    #: Uses the same format as toolsets name, so the returned value is a
    #: number, e.g. 2010.
    version = None

    #: Name of the project. Typically basename of the project file.
    name = None

    #: GUID of the project.
    guid = None

    #: Filename of the project, as :class:`bkl.expr.Expr`."""
    projectfile = None

    #: List of dependencies of this project, as names."""
    dependencies = []

    #: List of configuration objects."""
    configurations = []

    #: Location in the sources where the project originated from
    source_pos = None


class VSSolutionBase(object):
    """
    Base class for a representation of a Visual Studio solution file.

    Derived classes must set :attr:`format_version` and :attr:`human_version`
    and may override :meth:`write_header()`.
    """

    #: String with format version as used in the header
    format_version = None
    #: ...and in the comment under it (2005 and up)
    human_version = None

    def __init__(self, toolset, module):
        slnfile = module["%s.solutionfile" % toolset.name].as_native_path_for_output(module)
        self.name = module.name
        self.guid = GUID(NAMESPACE_SLN_GROUP, module.project.top_module.name, module.name)
        self.projects = OrderedDict()
        self.subsolutions = []
        self.parent_solution = None
        paths_info = bkl.expr.PathAnchorsInfo(
                                    dirsep="\\",
                                    outfile=slnfile,
                                    builddir=None,
                                    model=module)
        self.formatter = VSExprFormatter(paths_info)
        self.outf = OutputFile(slnfile, EOL_WINDOWS,
                               creator=toolset, create_for=module)

    def add_project(self, prj):
        """
        Adds a project (VSProjectBase-derived object) to the solution.
        """
        self.projects[prj.name] = prj

    def add_subsolution(self, solution):
        """
        Adds another solution as a subsolution of this one.
        """
        assert self.format_version == solution.format_version
        self.subsolutions.append(solution)
        solution.parent_solution = self

    def all_projects(self):
        for p in self.projects.itervalues():
            yield p
        for sln in self.subsolutions:
            for p in sln.all_projects():
                yield p

    def all_subsolutions(self):
        for sln in self.subsolutions:
            yield sln
            for s in sln.all_subsolutions():
                yield s

    def _get_project_by_id(self, id):
        try:
            return self.projects[id]
        except KeyError:
            for sln in self.subsolutions:
                p = sln._get_project_by_id(id)
                if p:
                    return p
            return None

    def additional_deps(self):
        """
        Returns additional projects to include, "external" deps e.g. from
        parents, in the same format all_projects() uses.
        """
        additional = []
        top = self
        while top.parent_solution:
            top = top.parent_solution
        if top is self:
            return additional

        included = set(x.name for x in self.all_projects())
        todo = set()
        for prj in self.all_projects():
            todo.update(prj.dependencies)

        prev_count = 0
        while prev_count != len(included):
            prev_count = len(included)
            todo = set(x for x in todo if x not in included)
            todo_new = set()
            for todo_item in todo:
                included.add(todo_item)
                prj = top._get_project_by_id(todo_item)
                todo_new.update(prj.dependencies)
                additional.append(prj)
            todo.update(todo_new)
        return additional

    def _find_target_guid_recursively(self, id):
        """Recursively search for the target in all submodules and return its GUID."""
        try:
            return self.projects[id].guid
        except KeyError:
            for sln in self.subsolutions:
                guid = sln._find_target_guid_recursively(id)
                if guid:
                    return guid
            return None

    def _get_target_guid(self, id):
        try:
            return self.projects[id].guid
        except KeyError:
            top = self
            while top.parent_solution:
                top = top.parent_solution
            guid = top._find_target_guid_recursively(id)
            assert guid, "can't find GUID of project '%s'" % id
            return guid

    def _get_matching_project_config(self, cfg, prj):
        with error_context(prj):
            if cfg in prj.configurations:
                return cfg

            # else: try to find a configuration closest to the given one, i.e.
            # the one from which it inherits via the minimal number of
            # intermediate configurations:
            compatibles = []
            for pc in prj.configurations:
                degree = cfg.derived_from(pc)
                if degree:
                    compatibles.append((degree, pc))

            if not compatibles:
                # if we don't have any project configurations from which this
                # one inherits, check if we have any which inherit from this
                # one themselves as they should be a reasonably good fallback:
                for pc in prj.configurations:
                    degree = pc.derived_from(cfg)
                    if degree:
                        compatibles.append((degree, pc))

            if compatibles:
                if len(compatibles) > 1:
                    compatibles.sort()
                    # It can happen that we have 2 project configurations
                    # inheriting from the solution configuration with the same
                    # degree. In this case there we can't really make the
                    # right choice automatically, so we must warn the user.
                    degree = compatibles[0][0]
                    if compatibles[1][0] == degree:
                        good_ones = [x[1].name for x in compatibles if x[0] == degree]
                        warning("project %s: no unambiguous choice of project configuration to use for the solution configuration \"%s\", equally good candidates are: \"%s\"",
                                prj.projectfile,
                                cfg.name,
                                '", "'.join(good_ones))

                degree, ret = compatibles[0]
                logger.debug("%s: solution config \"%s\" -> project %s config \"%s\" (dg %d)",
                             self.outf.filename, cfg.name, prj.projectfile, ret.name, degree)
                return ret

            # if all failed, just pick the first config, but at least try to match
            # debug/release setting:
            compatibles = [x for x in prj.configurations if x.is_debug == cfg.is_debug]
            if compatibles:
                ret = compatibles[0]
                warning("project %s: using unrelated project configuration \"%s\" for solution configuration \"%s\"",
                        prj.projectfile, ret.name, cfg.name)
                return ret
            else:
                ret = prj.configurations[0]
                warning("project %s: using incompatible project configuration \"%s\" for solution configuration \"%s\"",
                        prj.projectfile, ret.name, cfg.name)
                return ret

    def write_header(self, file):
        file.write("Microsoft Visual Studio Solution File, Format Version %s\n" % self.format_version)
        if self.human_version:
            file.write("# Visual Studio %s\n" % self.human_version)

    def write(self):
        """Writes the solution to the file."""
        outf = self.outf
        self.write_header(outf)

        # Projects:
        additional_deps = self.additional_deps()
        included_projects = list(self.all_projects()) + additional_deps

        if not included_projects:
            return # don't write empty solution files

        configurations = []
        for prj in included_projects:
            for cfg in prj.configurations:
                if cfg not in configurations:
                    configurations.append(cfg)

        for prj in included_projects:
            outf.write('Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "%s", "%s", "{%s}"\n' %
                       (prj.name, self.formatter.format(prj.projectfile), str(prj.guid)))
            if prj.dependencies:
                outf.write("\tProjectSection(ProjectDependencies) = postProject\n")
                for d in prj.dependencies:
                    outf.write("\t\t{%(g)s} = {%(g)s}\n" % {'g':self._get_target_guid(d)})
                outf.write("\tEndProjectSection\n")
            outf.write("EndProject\n")

        # Folders in the solution:
        all_folders = list(self.all_subsolutions())
        if additional_deps:
            class AdditionalDepsFolder: pass
            extras = AdditionalDepsFolder()
            extras.name = "Additional Dependencies"
            extras.guid = GUID(NAMESPACE_INTERNAL, self.name, extras.name)
            extras.projects = OrderedDict()
            for prj in additional_deps:
                extras.projects[prj.name] = prj
            extras.subsolutions = []
            extras.parent_solution = None
            all_folders.append(extras)
        for sln in all_folders:
            # don't have folders with just one item in them:
            sln.omit_from_tree = (sln.parent_solution and
                                  (len(sln.projects) + len(sln.subsolutions)) <= 1)
            if sln.omit_from_tree:
                continue
            outf.write('Project("{2150E333-8FDC-42A3-9474-1A3956D46DE8}") = "%s", "%s", "{%s}"\n' %
                       (sln.name, sln.name, sln.guid))
            outf.write("EndProject\n")
        all_folders = list(x for x in all_folders if not x.omit_from_tree)

        # Global settings:
        outf.write("Global\n")
        outf.write("\tGlobalSection(SolutionConfigurationPlatforms) = preSolution\n")
        for cfg in configurations:
            outf.write("\t\t%s|Win32 = %s|Win32\n" % (cfg.name, cfg.name))
        outf.write("\tEndGlobalSection\n")
        outf.write("\tGlobalSection(ProjectConfigurationPlatforms) = postSolution\n")
        for prj in included_projects:
            guid = prj.guid
            for cfg in configurations:
                cfgp = self._get_matching_project_config(cfg, prj)
                outf.write("\t\t{%s}.%s|Win32.ActiveCfg = %s|Win32\n" % (guid, cfg.name, cfgp.name))
                outf.write("\t\t{%s}.%s|Win32.Build.0 = %s|Win32\n" % (guid, cfg.name, cfgp.name))
        outf.write("\tEndGlobalSection\n")
        outf.write("\tGlobalSection(SolutionProperties) = preSolution\n")
        outf.write("\t\tHideSolutionNode = FALSE\n")
        outf.write("\tEndGlobalSection\n")

        # Nesting of projects and folders in the tree:
        if all_folders:
            outf.write("\tGlobalSection(NestedProjects) = preSolution\n")

            def _gather_folder_children(sln):
                prjs = [p for p in sln.projects.itervalues()]
                slns = []
                for s in slns:
                    if s.omit_from_tree:
                        p2, s2 = _gather_folder_children(s)
                        prjs += p2
                        slns += s2
                    else:
                        slns.append(s)
                return (prjs, slns)

            for sln in all_folders:
                prjs, subslns = _gather_folder_children(sln)
                for prj in prjs:
                    outf.write("\t\t{%s} = {%s}\n" % (prj.guid, sln.guid))
                for subsln in subslns:
                    outf.write("\t\t{%s} = {%s}\n" % (subsln.guid, sln.guid))
            outf.write("\tEndGlobalSection\n")

        outf.write("EndGlobal\n")
        outf.commit()



# TODO: Both of these should be done as an expression once proper functions
#       are implemented, as $(dirname(vs2010.solutionfile)/$(id).vcxproj)
def _default_solution_name(module):
    """same name as the module's bakefile, with ``.sln`` extension, in ``@srcdir``"""
    return bkl.expr.PathExpr([bkl.expr.LiteralExpr(module.name + ".sln")])

def _project_name_from_solution(toolset_class, target):
    """``$(id).vcxproj`` in the same directory as the ``.sln`` file"""
    sln = target["%s.solutionfile" % toolset_class.name]
    proj_ext = toolset_class.proj_extension
    return bkl.expr.PathExpr(sln.components[:-1] +
                             [bkl.expr.LiteralExpr("%s.%s" % (target.name, proj_ext))],
                             sln.anchor, sln.anchor_file)

def _default_guid_for_project(target):
    """automatically generated"""
    return '"%s"' % GUID(NAMESPACE_PROJECT, target.parent.name, target.name)


class VSToolsetBase(Toolset):
    """Base class for all Visual Studio toolsets."""

    #: Project files versions that are natively supported, sorted list
    proj_versions = None
    #: Extension of format files (vcproj, vcxproj)
    proj_extension = None
    #: Solution class for this VS version
    Solution = None
    #: Project class for this VS version
    Project = None

    exe_extension = "exe"
    library_extension = "lib"

    @classmethod
    def properties_target(cls):
        yield Property("%s.projectfile" % cls.name,
                       type=PathType(),
                       default=update_wrapper(partial(_project_name_from_solution, cls), _project_name_from_solution),
                       inheritable=False,
                       doc="File name of the project for the target.")
        yield Property("%s.guid" % cls.name,
                       # TODO: use custom GUID type, so that user-provided GUIDs can be validated
                       # TODO: make this vs.guid and share among VS toolsets
                       type=StringType(),
                       default=_default_guid_for_project,
                       inheritable=False,
                       doc="GUID of the project.")

    @classmethod
    def properties_module(cls):
        yield Property("%s.solutionfile" % cls.name,
                       type=PathType(),
                       default=_default_solution_name,
                       inheritable=False,
                       doc="File name of the solution file for the module.")
        yield Property("%s.generate-solution" % cls.name,
                       type=BoolType(),
                       default=True,
                       inheritable=True,
                       doc="""
                           Whether to generate solution file for the module. Set to
                           ``false`` if you want to omit the solution, e.g. for some
                           submodules with only a single target.
                           """)


    def generate(self, project):
        # generate vcxproj files and prepare solutions
        for m in project.modules:
            with error_context(m):
                self.gen_for_module(m)
        # Commit solutions; this must be done after processing all modules
        # because of inter-module dependencies and references.
        for m in project.modules:
            for sub in m.submodules:
                m.solution.add_subsolution(sub.solution)
        for m in project.modules:
            if m["%s.generate-solution" % self.name]:
                m.solution.write()


    def gen_for_module(self, module):
        # attach VS2010-specific data to the model
        module.solution = self.Solution(self, module)

        for t in module.targets.itervalues():
            with error_context(t):
                prj = self.gen_for_target(t)
                if not prj:
                    # Not natively supported; try if the TargetType has an implementation
                    try:
                        prj = t.type.vs_project(self, t)
                    except NotImplementedError:
                        # TODO: handle this as generic action target
                        warning("target type \"%s\" is not supported by the %s toolset, ignoring",
                                t.type.name, self.name)
                        continue
                if prj.name != t.name:
                    # TODO: This is only for the solution file; we should remap the name instead of
                    #       failure. Note that we don't always control prj.name, it may come from external
                    #       project file.
                    raise Error("project name (\"%s\") differs from target name (\"%s\"), they must be the same" %
                                (prj.name, t.name))
                if prj.version not in self.proj_versions:
                    if prj.version > self.proj_versions[-1]:
                        raise Error("project %s is for Visual Studio %.1f and will not work with %.1f" %
                                    (prj.projectfile, prj.version, self.version))
                    else:
                        warning("project %s is for Visual Studio %.1f, not %.1f, will be converted when built",
                                prj.projectfile, prj.version, self.version)
                module.solution.add_project(prj)


    def gen_for_target(self, target):
        raise NotImplementedError


    # Misc helpers for derived classes:

    def get_std_defines(self, target, cfg):
        """
        Returns list of predefined preprocessor symbols to use.
        """
        defs = ["WIN32"]
        defs.append("_DEBUG" if cfg.is_debug else "NDEBUG")
        if is_exe(target):
            defs.append("_CONSOLE")
        elif is_library(target):
            defs.append("_LIB")
        elif is_dll(target):
            defs.append("_USRDLL")
            defs.append("%s_EXPORTS" % target.name.upper())
        return defs

    def collect_extra_options_for_node(self, target, prefix):
        """
        Collects extra options from target variables. Extra options are those not supported
        directly by Bakefile, but expressed as specially-named variables, e.g.
        ``vs2010.option.GenerateManifest``.

        Yields tuples of (name, value) for collected values.

        :param target:  Target to collect variables from.
        :param prefix:  Prefix of the variables, without "<target>.option.". For example,
                        it may be "Link" to collect from e.g. ``vs2010.option.Link.*`` or
                        "" to collect from ``vs2010.option.*``.
        """
        if prefix:
            scope = "%s.option.%s" % (self.name, prefix)
        else:
            scope = "%s.option" % self.name

        if isinstance(target, ConfigurationProxy):
            scope_for_vars = target.model
        else:
            scope_for_vars = target

        already_found = set()
        while scope_for_vars is not None:
            for varname in scope_for_vars.variables.iterkeys():
                if varname in already_found:
                    continue
                split = varname.rsplit(".", 1)
                if len(split) == 2 and split[0] == scope:
                    yield (str(split[1]), target[varname])
            already_found.update(scope_for_vars.variables.iterkeys())
            scope_for_vars = scope_for_vars.parent


# Misc helpers:

def is_library(target):
    return target.type.name == "library"

def is_exe(target):
    return target.type.name == "exe"

def is_dll(target):
    return target.type.name == "dll"
