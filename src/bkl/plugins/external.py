#
#  This file is part of Bakefile (http://www.bakefile.org)
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
Implementation of 'external' target type.
"""

from bkl.api import Extension, Property, TargetType, FileRecognizer
from bkl.vartypes import PathType
from bkl.error import Error, error_context
from bkl.plugins.vsbase import VSProjectBase, PROJECT_KIND_NET
from bkl.utils import memoized_property

import xml.etree.ElementTree
import re


class ExternalBuildHandler(Extension, FileRecognizer):
    """
    Extension type for handler of various external build systems.

    The methods are analogous to corresponding :class:`bkl.api.TargetType`
    methods.
    """

    def get_build_subgraph(self, toolset, target):
        raise NotImplementedError

    def vs_project(self, toolset, target):
        raise NotImplementedError


class ExternalTargetType(TargetType):
    """
    External build system.

    This target type is used to invoke makefiles or project files not
    implemented in Bakefile, for example to build 3rd party libraries.

    Currently, only Visual Studio projects (vcproj, vcxproj, csproj) are
    supported and only when using a Visual Studio toolset.
    """
    name = "external"

    properties = [
            Property("file",
                 type=PathType(),
                 inheritable=False,
                 doc="File name of the external makefile or project."),
        ]

    def get_build_subgraph(self, toolset, target):
        return self.get_handler(target).get_build_subgraph(toolset, target)

    def vs_project(self, toolset, target):
        return self.get_handler(target).vs_project(toolset, target)

    def get_handler(self, target):
        with error_context(target["file"]):
            return ExternalBuildHandler.get_for_file(target["file"].as_native_path_for_output(target))


# -----------------------------------------------------------------------
# Support for Visual Studio projects
# -----------------------------------------------------------------------

# TODO-PY26: use namespaces={...} argument to findtext() instead of using this
# to substitute %s (see git history)
XMLNS = {
    "ms" : "http://schemas.microsoft.com/developer/msbuild/2003"
}

class VSExternalProjectBase(VSProjectBase):
    """
    Wrapper around externally-provided project file, base class.
    """
    def __init__(self, target):
        self._known_configurations = target.project.configurations
        self.projectfile = target["file"]
        self.dependencies = []
        self.source_pos = target.source_pos
        xmldoc = xml.etree.ElementTree.parse(self.projectfile.as_native_path_for_output(target))
        self.xml = xmldoc.getroot()

    @memoized_property
    def configurations(self):
        known = self._known_configurations
        lst = []
        for name in self._extract_configurations_names():
            try:
                lst.append(known[name])
            except KeyError:
                if "Debug" in name:
                    base = known["Debug"]
                elif "Release" in name:
                    base = known["Release"]
                else:
                    raise Error("don't know whether the \"%s\" configuration from external %s is debug or release; please define it in your bakefile explicitly" % (name, self.projectfile),
                                pos=self.source_pos)
                lst.append(base.clone(name))
        return lst


class VSExternalProject200x(VSExternalProjectBase):
    """
    Wrapper around VS 200{3,5,8} project files.
    """
    @memoized_property
    def version(self):
        v = self.xml.get("Version")
        if v and "," in v:
            # vcproj files written under some locales (French, Czech) may use
            # ',' as decimal point character.
            v = v.replace(",", ".")
        if   v == "7.10": return 7.1
        elif v == "8.00": return 8
        elif v == "9.00": return 9
        else:
            raise Error("unrecognized version of Visual Studio project %s: Version=\"%s\"" % (
                        self.projectfile, v))

    @memoized_property
    def name(self):
        return self.xml.get("Name")

    @memoized_property
    def guid(self):
        return self.xml.get("ProjectGUID")[1:-1]

    def _extract_configurations_names(self):
        return [x.get("Name").partition("|")[0]
                for x in self.xml.findall("Configurations/Configuration")]


class VSExternalProject201x(VSExternalProjectBase):
    """
    Wrapper around VS 2010/2012 project files.
    """
    @memoized_property
    def version(self):
        v = self.xml.get("ToolsVersion")
        if v != "4.0":
            raise Error("unrecognized version of Visual Studio project %s: ToolsVersion=\"%s\"" %(
                        self.projectfile, v))
        # TODO-PY26: use "PropertyGroup[@Label='Configuration']"
        t = self.xml.findtext("{%(ms)s}PropertyGroup/{%(ms)s}PlatformToolset" % XMLNS)
        if t == "v110":
            return 11
        else:
            return 10

    @memoized_property
    def name(self):
        # TODO-PY26: use "PropertyGroup[@Label='Globals']"
        name = self.xml.findtext("{%(ms)s}PropertyGroup/{%(ms)s}ProjectName" % XMLNS)
        if name is None:
            name = self.projectfile.get_basename()
        return name

    @memoized_property
    def guid(self):
        # TODO-PY26: use "PropertyGroup[@Label='Globals']"
        return self.xml.findtext("{%(ms)s}PropertyGroup/{%(ms)s}ProjectGuid" % XMLNS)[1:-1]

    def _extract_configurations_names(self):
        # TODO-PY26: use "ItemGroup[@Label='ProjectConfigurations']"
        return [x.text for x in
                self.xml.findall("{%(ms)s}ItemGroup/{%(ms)s}ProjectConfiguration/{%(ms)s}Configuration" % XMLNS)]


class VSExternalProjectCSharp(VSExternalProjectBase):
    """
    Wrapper around VS C# project files.
    """

    kind = PROJECT_KIND_NET

    @memoized_property
    def version(self):
        # .csproj files are generally usable across VS versions
        return None

    @memoized_property
    def name(self):
        return self.projectfile.get_basename()

    @memoized_property
    def guid(self):
        # TODO-PY26: use "PropertyGroup[@Label='Globals']"
        return self.xml.findtext("{%(ms)s}PropertyGroup/{%(ms)s}ProjectGuid" % XMLNS)[1:-1]

    def _extract_configurations_names(self):
        found = []
        for n in self.xml.findall("{%(ms)s}PropertyGroup" % XMLNS):
            cond = n.get("Condition")
            if cond:
                m = re.match(r" *'\$\(Configuration\)\|\$\(Platform\)' *== '(.*)\|(.*)' *", cond)
                cfg = m.group(1) if m else None
                if cfg and cfg not in found:
                    found.append(cfg)
        return found


class VisualStudioHandler(ExternalBuildHandler):
    """
    Support for external Visual Studio projects.
    """
    name = "visual-studio"

    extensions = ["vcproj", "vcxproj", "csproj"]

    implementations = {
        "vcproj"  : VSExternalProject200x,
        "vcxproj" : VSExternalProject201x,
        "csproj"  : VSExternalProjectCSharp,
        }

    def get_build_subgraph(self, toolset, target):
        raise NotImplementedError # FIXME -- invoke msbuild on windows

    def vs_project(self, toolset, target):
        prj_class = self.implementations[target["file"].get_extension()]
        return prj_class(target)
