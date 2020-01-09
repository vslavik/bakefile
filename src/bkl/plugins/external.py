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
Implementation of 'external' target type.
"""

from bkl.api import Extension, Property, TargetType, FileRecognizer
from bkl.vartypes import PathType
from bkl.error import Error, error_context
from bkl.plugins.vsbase import VSProjectBase, VSToolsetBase, PROJECT_KIND_NET
from bkl.utils import memoized_property, filter_duplicates
from bkl.vartypes import ListType, StringType

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
                 doc="File name of the external makefile or project.")
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
        self._project = target.project
        self.projectfile = target["file"]

        # Helper function to get the property value without inheriting it from
        # the parent: needed in order to allow specifying the properties below
        # in the external itself to override auto-detection (which is not 100%
        # reliable), but still auto-detecting them by default otherwise.
        def get_prop_value_from_here(target, propname):
            var = target.get_variable(propname)

            # Ignore the variables using the default value of the
            # corresponding property: they will exist but not be explicitly
            # set.
            if var is None or not var.is_explicitly_set:
                return []

            return var.value.as_py()

        self._archs = get_prop_value_from_here(target, "archs")
        self._configurations = get_prop_value_from_here(target, "configurations")
        self.dependencies = []
        self.source_pos = target.source_pos
        xmldoc = xml.etree.ElementTree.parse(self.projectfile.as_native_path_for_output(target))
        self.xml = xmldoc.getroot()

    @memoized_property
    def configurations(self):
        known = self._project.configurations
        lst = []
        vs_configurations = self._configurations
        if not vs_configurations:
            vs_configurations = filter_duplicates(self._extract_configurations_names())
        for name in vs_configurations:
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
                cfg = base.create_derived(name)
                self._project.add_configuration(cfg)
                lst.append(cfg)
        return lst

    @memoized_property
    def platforms(self):
        if self._archs:
            return [VSToolsetBase.ARCHS_MAPPING[a] for a in self._archs]
        else:
            return list(filter_duplicates(self._extract_platforms()))


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
        for x in self.xml.findall("Configurations/Configuration"):
            yield x.get("Name").partition("|")[0]

    def _extract_platforms(self):
        for x in self.xml.findall("Platforms/Platform"):
            yield x.get("Name")


class VSExternalProject201x(VSExternalProjectBase):
    """
    Wrapper around VS 201x project files.
    """
    @memoized_property
    def version(self):
        v = self.xml.get("ToolsVersion")
        if v == "16.0":
            return 16
        elif v == "15.0":
            return 15
        elif v == "14.0":
            return 14
        elif v == "12.0":
            return 12
        elif v != "4.0":
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
        for x in self.xml.findall("{%(ms)s}ItemGroup/{%(ms)s}ProjectConfiguration/{%(ms)s}Configuration" % XMLNS):
            yield x.text

    def _extract_platforms(self):
        # TODO-PY26: use "ItemGroup[@Label='ProjectConfigurations']"
        for x in self.xml.findall("{%(ms)s}ItemGroup/{%(ms)s}ProjectConfiguration/{%(ms)s}Platform" % XMLNS):
            yield x.text


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

    def _extract_configs_and_platforms(self):
        for n in self.xml.findall("{%(ms)s}PropertyGroup" % XMLNS):
            cond = n.get("Condition")
            if cond:
                m = re.match(r" *'\$\(Configuration\)\|\$\(Platform\)' *== '(.*)\|(.*)' *", cond)
                if m:
                    yield (m.group(1), m.group(2))

    def _extract_configurations_names(self):
        return (x[0] for x in self._extract_configs_and_platforms())

    def _extract_platforms(self):
        for x in filter_duplicates(self._extract_configs_and_platforms()):
            p = x[1]
            # .csproj files use "AnyCPU", but .sln files (which is what this is
            # for) use "Any CPU".
            if p == "AnyCPU": yield "Any CPU"
            else:             yield p



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
