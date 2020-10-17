#
#  This file is part of Bakefile (http://bakefile.org)
#
#  Copyright (C) 2012-2013 Vaclav Slavik
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
from collections import defaultdict

import logging
logger = logging.getLogger("bkl.vsbase")

import bkl.expr
from bkl.utils import OrderedDict, OrderedSet, memoized
from bkl.error import error_context, warning, Error, CannotDetermineError
from bkl.api import Toolset, Property
from bkl.model import ConfigurationProxy
from bkl.vartypes import PathType, StringType, BoolType
from bkl.io import OutputFile, EOL_WINDOWS


# Namespace constants for the GUID function
NAMESPACE_PROJECT   = uuid.UUID("{D9BD5916-F055-4D77-8C69-9448E02BF433}")
NAMESPACE_SLN_GROUP = uuid.UUID("{2D0C29E0-512F-47BE-9AC4-F4CAE74AE16E}")
NAMESPACE_INTERNAL  = uuid.UUID("{BAA4019E-6D67-4EF1-B3CB-AE6CD82E4060}")

# Kinds of projects, as used in solution files
PROJECT_KIND_C      = "{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}"
PROJECT_KIND_NET    = "{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}"

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
        equivalent to creating a Node using the same arguments and then adding
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

    def add_with_default(self, name, value):
        """
        Add an element with the given value and the default element value.

        This produces output of the form "<Foo>our-value-of-foo;%(Foo)</Foo>"
        in the generated project file, which is desirable as it preserves any
        changes to this property in the previously included property sheets.

        Additionally, if the value is empty, this method doesn't do anything
        at all as using empty value followed by the current value of the
        property is equivalent to doing nothing in any case.
        """
        if not value:
            # If there is no value at all, there is no need to add anything.
            return

        if isinstance(value, VSList):
            value_with_def = VSList(value.list_sep, value.items)
        else:
            value_with_def = list(value)
        value_with_def.append('%%(%s)' % name)

        self.children.append((name, value_with_def))

    def add_or_replace(self, name, value):
        """
        Add a child to this node, replacing the existing child with the same
        name, if any.

        This is used to override the default options with the user-specified
        ones.
        """
        for n,c in enumerate(self.children):
            if c[0] == name:
                self.children[n] = (name, value)
                return

        self.children.append((name, value))

    def has_children(self):
        return len(self.children) > 0


class VSExprFormatter(bkl.expr.Formatter):
    list_sep = ";"

    # Substitution from placeholders ("config" etc.) to VS variables:
    substs = {
                "config" : "$(Configuration)",
                "arch"   : "$(Platform)",
             }

    def __init__(self, settings, paths_info):
        super(VSExprFormatter, self).__init__(paths_info)
        self.settings = settings

    def placeholder(self, e):
        try:
            return self.substs[e.var]
        except KeyError:
            try:
                # Just use the setting default value in VS output, we don't
                # allow to configure it yet (we'd need to generate a .props
                # file for this).
                return str(self.settings[e.var]["default"])
            except KeyError:
                assert False, 'Unexpectedly unexpanded reference "%s"' % e.var

    def bool_value(self, e):
        return "true" if e.value else "false"


class VSList(object):
    """
    Helper class for use with XmlFormatter to represent lists with different
    delimiters. Its constructor takes the delimiter character as its first argument,
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

    def __str__(self):
        return " ".join(str(x) for x in self.items)

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

    #: Elements which are written in full form when empty.
    elems_not_collapsed = set()

    def __init__(self, settings, paths_info, charset="utf-8"):
        self.charset = charset
        self.expr_formatter = self.ExprFormatter(settings, paths_info)

    def format(self, node):
        """
        Formats given node as an XML document and returns the document as a
        string.
        """
        return XML_HEADER % dict(charset=self.charset) + self._do_format_node(node, "")

    def _do_format_node(self, n, indent):
        attrs = self._get_quoted_nonempty_attrs(n)
        if n.children:
            children_markup = []
            assert not n.text, "nodes with both text and children not implemented"
            subindent = indent + self.indent_step
            for key, value in n.children:
                if isinstance(value, Node):
                    assert key == value.name
                    children_markup.append(self._do_format_node(value, subindent))
                else:
                    try:
                        v = escape(self.format_value(value))
                        if v:
                            children_markup.append("%s<%s>%s</%s>\n" % (subindent, key, v, key))
                        # else: empty value, don't write that
                    except CannotDetermineError as e:
                        with error_context(value):
                            raise Error("cannot set property \"%s\" to non-constant expression \"%s\" (%s)" %
                                        (key, value, e.msg))
            children_markup = "".join(children_markup)
        else:
            children_markup = None
        text = self.format_value(n.text) if n.text else None
        return self.format_node(n.name, attrs, text, children_markup, indent)

    def format_node(self, name, attrs, text, children_markup, indent):
        """
        Formats given Node instance, indented with *indent* text.

        Content is either *text* or *children_markup*; the other is None. All
        arguments already use properly escaped markup; values in *attrs* are
        quoted and escaped.
        """
        s = "%s<%s" % (indent, name)
        if attrs:
            # Different versions put attributes on the same or different
            # lines, so do this in a separate method to allow overriding it.
            s += self.format_attrs(attrs, indent)

            if text or children_markup:
                # Moreover, different versions may or not put a new line
                # before the closing angle bracket, so we need a method here
                # too.
                s += self.format_end_tag_with_attrs(indent)
            else: # An empty element
                # Some empty elements are output as "<foo/>" while others as
                # "<foo>\n</foo>".
                if name not in self.elems_not_collapsed:
                    # And different versions close an empty tag differently,
                    # so abstract it into a separate method as well.
                    s += self.format_end_empty_tag(indent)

                    # Skip the closing tag addition below.
                    s += "\n"
                    return s

                s += self.format_end_tag_with_attrs(indent)
                s += "\n"
                s += indent
        else:
            if text or children_markup:
                s += ">"
            else:
                s += ">\n"
                s += indent

        if text:
            s += text
        elif children_markup:
            s += "\n"
            s += children_markup
            s += indent

        s += "</%s>\n" % name

        return s

    def format_value(self, val):
        # This trick is necessary, because 'val' may be of many types -- in
        # particular, it may be an integer or a boolean. Python's bool type is
        # a specialization of int and dictionaries don't differentiate between
        # them and so @memoized format_value() would incorrectly return the
        # same value (e.g. "1") for both True and 1. The dummy 'valtype'
        # argument disambiguates these cases, with no noticeable loss of
        # performance.
        return self._format_value(val, type(val))

    def format_attrs(self, attrs, indent):
        """
        Returns the list containing formatted attributes.

        Parameters of this method are a subset of format_node() parameters.
        """
        s = ''
        for key, value in attrs:
            s += ' %s=%s' % (key, value)
        return s

    def format_end_tag_with_attrs(self, indent):
        """
        Returns the string at the end of the opening tag with attributes.
        """
        return ">"

    def format_end_empty_tag(self, indent):
        """
        Returns the string at the end of an empty tag.

        This method only exists because MSVS 2003 doesn't insert an extra
        space here while all the other formats do.
        """
        return " />"

    @memoized
    def _format_value(self, val, valtype):
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

    #: GUID of the kind of the project for use in solution files
    kind = PROJECT_KIND_C

    #: Filename of the project, as :class:`bkl.expr.Expr`."""
    projectfile = None

    #: List of dependencies of this project, as names."""
    dependencies = []

    #: List of configuration objects."""
    configurations = []

    #: List of configurations objects for which building the project is disabled.
    disabled_configurations = []

    #: List of platforms ("Win32", "x64")."""
    platforms = []

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

    def __init__(self, toolset, module, slnprop):
        slnfile = slnprop.as_native_path_for_output(module)
        self.name = module.name
        # unlike targets, modules' names aren't globally unique, so use the fully qualified name, which is
        self.guid = GUID(NAMESPACE_SLN_GROUP, module.project.top_module.name, module.fully_qualified_name)
        self.projects = OrderedDict()
        self.subsolutions = []
        self.parent_solution = None
        paths_info = bkl.expr.PathAnchorsInfo(
                                    dirsep="\\",
                                    outfile=slnfile,
                                    builddir=None,
                                    model=module)
        self.formatter = VSExprFormatter(module.project.settings, paths_info)
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
            if prj.dependencies:
                todo.update(prj.dependencies)

        prev_count = 0
        while prev_count != len(included):
            prev_count = len(included)
            todo = set(x for x in todo if x not in included)
            todo_new = set()
            for todo_item in sorted(todo):
                included.add(todo_item)
                prj = top._get_project_by_id(todo_item)
                if prj.dependencies:
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

    def write_header(self, file):
        file.write("Microsoft Visual Studio Solution File, Format Version %s\n" % self.format_version)
        if self.human_version:
            file.write("# Visual Studio %s\n" % self.human_version)

    def write(self):
        """Writes the solution to the file."""
        outf = self.outf
        self.write_header(outf)

        # Projects:
        all_own_projects = list(self.all_projects())
        additional_deps = self.additional_deps()
        included_projects = all_own_projects + additional_deps

        if not included_projects:
            return # don't write empty solution files

        configurations_set = set()
        for prj in all_own_projects:
            configurations_set.update(prj.configurations)

        # MSVS own projects always list configurations in alphabetical order,
        # so do the same thing as it does.
        configurations = sorted(configurations_set, key=lambda c: c.name.lower())

        platforms = OrderedSet()
        for prj in all_own_projects:
            platforms.update(prj.platforms)
        # HACK: Don't use Any CPU for solution config if there are native ones:
        if "Any CPU" in platforms and len(platforms) > 1:
            platforms.remove("Any CPU")

        for prj in included_projects:
            outf.write('Project("%s") = "%s", "%s", "{%s}"\n' %
                       (prj.kind, prj.name, self.formatter.format(prj.projectfile), str(prj.guid)))
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
            for plat in platforms:
                outf.write("\t\t%s|%s = %s|%s\n" % (cfg.name, plat, cfg.name, plat))
        outf.write("\tEndGlobalSection\n")
        outf.write("\tGlobalSection(ProjectConfigurationPlatforms) = postSolution\n")
        for prj in included_projects:
            guid = prj.guid
            for cfg in configurations:
                cfgp = _get_matching_project_config(cfg, prj)
                for plat in platforms:
                    platp = _get_matching_project_platform(plat, prj)
                    if platp is None:
                        # Can't build in this solution config. Just use any project platform
                        # and omit the Build.0 node -- VS does the same in this case.
                        platp = prj.platforms[0]
                        outf.write("\t\t{%s}.%s|%s.ActiveCfg = %s|%s\n" % (guid, cfg.name, plat, cfgp.name, platp))
                    else:
                        outf.write("\t\t{%s}.%s|%s.ActiveCfg = %s|%s\n" % (guid, cfg.name, plat, cfgp.name, platp))
                        if cfg not in prj.disabled_configurations:
                            outf.write("\t\t{%s}.%s|%s.Build.0 = %s|%s\n" % (guid, cfg.name, plat, cfgp.name, platp))
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
                for s in sln.subsolutions:
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
    sln = toolset_class.get_solutionfile_path(target)
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

    #: XML formatting class
    XmlFormatter = XmlFormatter

    program_extension = "exe"
    library_extension = "lib"
    shared_library_extension = "dll"
    loadable_module_extension = "dll"

    @classmethod
    def vsbase_target_properties(cls):
        yield Property("%s.projectfile" % cls.name,
                       type=PathType(),
                       default=update_wrapper(partial(_project_name_from_solution, cls), _project_name_from_solution),
                       inheritable=False,
                       doc="File name of the project for the target.")
        yield Property("%s.guid" % cls.name,
                       # TODO: use custom GUID type, so that user-provided GUIDs can be validated (and upper-cased)
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
                       inheritable=False,
                       doc="""
                           Whether to generate solution file for the module. Set to
                           ``false`` if you want to omit the solution, e.g. for some
                           submodules with only a single target.
                           """)

    @classmethod
    def get_solutionfile_path(cls, target):
        """
        Get the value of the ``solutionfile`` property for the toolset.
        """
        return target["%s.solutionfile" % cls.name]


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
            if m.generate_solution:
                m.solution.write()


    def create_solution(self, module):
        return self.Solution(self, module, module["%s.solutionfile" % self.name])

    def gen_for_module(self, module):
        # Note that we need to create the solution object even if we're not
        # generating the solution file, to make projects included in this
        # solution part of the global projects tree.
        module.generate_solution = module["%s.generate-solution" % self.name]
        module.solution = self.create_solution(module)

        for t in module.targets.itervalues():
            with error_context(t):
                prj = self.get_project_object(t)
                if prj is None:
                    # TODO: see the TODO in get_project_object()
                    continue
                if prj.name != t.name:
                    # TODO: This is only for the solution file; we should remap the name instead of
                    #       failure. Note that we don't always control prj.name, it may come from external
                    #       project file.
                    raise Error("project name (\"%s\") differs from target name (\"%s\"), they must be the same" %
                                (prj.name, t.name))
                if prj.version and prj.version not in self.proj_versions:
                    if prj.version > self.proj_versions[-1]:
                        raise Error("project %s is for Visual Studio %.1f and will not work with %.1f" %
                                    (prj.projectfile, prj.version, self.version))
                    else:
                        warning("project %s is for Visual Studio %.1f, not %.1f, will be converted when built",
                                prj.projectfile, prj.version, self.version)

                if self.is_natively_supported(t):
                    self.gen_for_target(t, prj)

                module.solution.add_project(prj)


    def is_natively_supported(self, target):
        return is_program(target) or is_library(target) or is_dll(target)

    @memoized
    def get_project_paths_info(self, target, project):
        filename = project.projectfile.as_native_path_for_output(target)
        return bkl.expr.PathAnchorsInfo(
                            dirsep="\\",
                            outfile=filename,
                            builddir=self.get_builddir_for(target).as_native_path_for_output(target),
                            model=target)

    @memoized
    def get_project_object(self, target):
        if self.is_natively_supported(target):
            proj = self.Project(target.name,
                                target["%s.guid" % self.name].as_py(),
                                target["%s.projectfile" % self.name],
                                target["deps"].as_py(),
                                [x.config for x in target.configurations],
                                self.get_platforms(target),
                                target.source_pos)
        else:
            # Not natively supported; try if the TargetType has an implementation
            try:
                proj = target.type.vs_project(self, target)
            except NotImplementedError:
                # TODO: handle this as generic action target
                warning("target type \"%s\" is not supported by the %s toolset, ignoring",
                        target.type.name, self.name)
                return None

        # See which configurations this target is explicitly disabled in.
        # Notice that we must check _all_ configurations visible in the solution,
        # not just the ones used by this target.
        all_global_configs = (ConfigurationProxy(target, x)
                              for x in target.project.configurations.itervalues())
        proj.disabled_configurations = [x.config for x in all_global_configs
                                        if not x.should_build()]
        return proj


    def get_builddir_for(self, target):
        prj = target["%s.projectfile" % self.name]
        configuration_ref = "$(IntDir)"
        return bkl.expr.PathExpr(prj.components[:-1] + [bkl.expr.LiteralExpr(configuration_ref)], prj.anchor, prj.anchor_file)


    def gen_for_target(self, target, project):
        """
        Generates output for natively supported target types.
        """
        raise NotImplementedError


    # Misc helpers for derived classes:

    def get_std_defines(self, target, cfg):
        """
        Returns list of predefined preprocessor symbols to use.
        """
        defs = ["WIN32"]
        defs.append("_DEBUG" if cfg.is_debug else "NDEBUG")
        if is_program(target) and target["win32-subsystem"] == "console":
            defs.append("_CONSOLE")
        elif is_library(target):
            defs.append("_LIB")
        elif is_dll(target):
            defs.append("%s_EXPORTS" % target.name.upper())
        return defs

    def collect_extra_options_for_node(self, target, prefix, inherit=True):
        """
        Collects extra options from target variables. Extra options are those not supported
        directly by Bakefile, but expressed as specially-named variables, e.g.
        ``vs2010.option.GenerateManifest``.

        Yields tuples of (name, value) for collected values.

        :param target:  Target to collect variables from.
        :param prefix:  Prefix of the variables, without "<target>.option.". For example,
                        it may be "Link" to collect from e.g. ``vs2010.option.Link.*`` or
                        "" to collect from ``vs2010.option.*``.
        :param inherit: Should values be inherited from the higher scopes (e.g. module)?
                        Should be True for targets and modules, false for source files
                        when used to output per-file settings.
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
                    value = target[varname]
                    if not value.is_null():
                        yield (str(split[1]), value)
            already_found.update(scope_for_vars.variables.iterkeys())
            if inherit:
                scope_for_vars = scope_for_vars.parent
            else:
                break


    def needs_custom_intermediate_dir(self, target):
        """
        Returns true if the project needs customized intermediate directory.

        Visual Studio (especially 2010+ with its .tlog files) has issues with
        building multiple projects in the same intermediate directory. The
        safest route to avoid these problems is to simply not do that, so we
        use e.g. Debug/$(id)/ intermediate directory instead of Debug as soon
        as there's more than one project file in the same directory.
        """
        builddir = self.get_builddir_for(target).as_native_path_for_output(target)
        dir_usage = self._project_dirs_usage(target.project)
        return dir_usage[builddir] > 1

    @memoized
    def _project_dirs_usage(self, project):
        """
        Returns a map with keys being names of directories where project files
        are stored and value being usage count.
        """
        d = defaultdict(int) # TODO-PY26: Use 2.7's Counter
        for target in project.all_targets():
            builddir = self.get_builddir_for(target).as_native_path_for_output(target)
            d[builddir] += 1
        return d


    ARCHS_MAPPING = { "x86": "Win32", "x86_64": "x64" }

    def get_archs(self, target):
        if target.is_variable_null("archs"):
            return ["x86"]
        else:
            return target["archs"].as_py()

    def get_platforms(self, target):
        return [self.ARCHS_MAPPING[a] for a in self.get_archs(target)]

    def _order_configs_and_archs(self, configs_iter, archs_list):
        raise NotImplementedError

    def configs_and_platforms(self, target):
        """
        Yields ConfigurationProxy instances for all of target's configurations
        *and* architectures (platforms).

        Compared to standard ConfigurationProxy objects, these are modified to
        contain additional variables:

          - "vs_platform" with the platform name used by VS (Win32, x64)
          - "vs_name" with the name used by VS (e.g. "Debug|Win32" or "Release|x64")
        """
        configs = target.configurations
        archs = self.get_archs(target)
        for cfg in target.configurations:
            for cfg, arch in self._order_configs_and_archs(configs, archs):
                p = self.ARCHS_MAPPING[arch]
                cfg.vs_platform = p
                cfg.vs_name = "%s|%s" % (cfg.name, p)
                cfg._visitor.mapping["arch"] = arch
                yield cfg

# Internal helper functions:

@memoized
def _get_matching_project_config(cfg, prj):
    """
    Returns best match project configuration for given solution configuration.
    """
    with error_context(prj):
        # If the project doesn't have any configurations, it means that we
        # failed to parse it properly, presumably because it defines its
        # configurations (and platforms, see _get_matching_project_platform()
        # too) in a separately imported file. Ideal would be to follow the
        # import chain, but this is not trivial, e.g. we would need to parse
        # and evaluate MSBuild functions to find the full path of the file
        # being imported, so for now we just optimistically assume that the
        # project supports all solution configurations because it's the only
        # thing we can do, the only alternative would be to refuse to use it
        # completely.
        if cfg in prj.configurations or not prj.configurations:
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
            logger.debug("solution config \"%s\" -> project %s config \"%s\" (dg %d)",
                         cfg.name, prj.projectfile, ret.name, degree)
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


@memoized
def _get_matching_project_platform(platform, prj):
    """
    Returns best matching platform in the project or None if none found.
    """
    # As with the configurations above, assume that all solution platforms are
    # supported by the project if we failed to find which ones it really has.
    if platform in prj.platforms or not prj.platforms:
        return platform
    elif "Any CPU" in prj.platforms:
        return "Any CPU"
    else:
        return None



# Misc helpers:

def is_library(target):
    return target.type.name == "library"

def is_program(target):
    return target.type.name == "program"

def is_dll(target):
    return target.type.name == "shared-library" or target.type.name == "loadable-module"

def is_module_dll(target):
    return target.type.name == "loadable-module"
