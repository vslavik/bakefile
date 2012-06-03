#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2011-2012 Vaclav Slavik
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

import codecs

import bkl.compilers
import bkl.expr
from bkl.io import OutputFile, EOL_WINDOWS

from bkl.plugins.vsbase import *


# TODO: Put more content into this class, use it properly
class VS2010Project(VSProjectBase):
    """
    """
    version = 10

    def __init__(self, name, guid, projectfile, deps, configs, source_pos=None):
        self.name = name
        self.guid = guid
        self.projectfile = projectfile
        self.dependencies = deps
        self.configurations = configs
        self.source_pos = source_pos



class VS201xToolsetBase(VSToolsetBase):
    """Base class for VS2010 and VS2012 toolsets."""

    #: Extension of format files
    proj_extension = "vcxproj"

    #: PlatformToolset property
    platform_toolset = None

    def gen_for_target(self, target):
        projectfile = target["%s.projectfile" % self.name]
        filename = projectfile.as_native_path_for_output(target)

        paths_info = bkl.expr.PathAnchorsInfo(
                                    dirsep="\\",
                                    outfile=filename,
                                    builddir=self.get_builddir_for(target).as_native_path_for_output(target),
                                    model=target)

        root = Node("Project")
        root["DefaultTargets"] = "Build"
        root["ToolsVersion"] = "4.0"
        root["xmlns"] = "http://schemas.microsoft.com/developer/msbuild/2003"

        guid = target["%s.guid" % self.name]

        n_configs = Node("ItemGroup", Label="ProjectConfigurations")
        for cfg in target.configurations:
            n = Node("ProjectConfiguration", Include="%s|Win32" % cfg.name)
            n.add("Configuration", cfg.name)
            n.add("Platform", "Win32")
            n_configs.add(n)
        root.add(n_configs)

        n_globals = Node("PropertyGroup", Label="Globals")
        self._add_extra_options_to_node(target, n_globals)
        n_globals.add("ProjectGuid", guid)
        n_globals.add("Keyword", "Win32Proj")
        n_globals.add("RootNamespace", target.name)
        self._add_VCTargetsPath(n_globals)
        root.add(n_globals)

        root.add("Import", Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props")

        for cfg in target.configurations:
            n = Node("PropertyGroup", Label="Configuration")
            self._add_extra_options_to_node(target, n)
            n["Condition"] = "'$(Configuration)|$(Platform)'=='%s|Win32'" % cfg.name
            if is_exe(target):
                n.add("ConfigurationType", "Application")
            elif is_library(target):
                n.add("ConfigurationType", "StaticLibrary")
            elif is_dll(target):
                n.add("ConfigurationType", "DynamicLibrary")
            else:
                return None

            n.add("UseDebugLibraries", cfg.is_debug)
            if cfg["win32-unicode"]:
                n.add("CharacterSet", "Unicode")
            else:
                n.add("CharacterSet", "MultiByte")
            if self.platform_toolset:
                n.add("PlatformToolset", self.platform_toolset)
            root.add(n)

        root.add("Import", Project="$(VCTargetsPath)\\Microsoft.Cpp.props")
        root.add("ImportGroup", Label="ExtensionSettings")

        for cfg in target.configurations:
            n = Node("ImportGroup", Label="PropertySheets")
            n["Condition"] = "'$(Configuration)|$(Platform)'=='%s|Win32'" % cfg.name
            n.add("Import",
                  Project="$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props",
                  Condition="exists('$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props')",
                  Label="LocalAppDataPlatform")
            root.add(n)

        root.add("PropertyGroup", Label="UserMacros")

        for cfg in target.configurations:
            n = Node("PropertyGroup")
            self._add_extra_options_to_node(target, n)
            if not is_library(target):
                n.add("LinkIncremental", cfg.is_debug)
            targetname = cfg[target.type.basename_prop]
            if targetname != target.name:
                n.add("TargetName", targetname)
            # TODO: handle the defaults in a nicer way
            if cfg["outputdir"].as_native_path(paths_info) != paths_info.builddir_abs:
                n.add("OutDir", cfg["outputdir"])
            if n.has_children():
                n["Condition"] = "'$(Configuration)|$(Platform)'=='%s|Win32'" % cfg.name
            root.add(n)

        for cfg in target.configurations:
            n = Node("ItemDefinitionGroup")
            n["Condition"] = "'$(Configuration)|$(Platform)'=='%s|Win32'" % cfg.name
            n_cl = Node("ClCompile")
            self._add_extra_options_to_node(target, n_cl)
            n_cl.add("WarningLevel", "Level3")
            if cfg.is_debug:
                n_cl.add("Optimization", "Disabled")
            else:
                n_cl.add("Optimization", "MaxSpeed")
                n_cl.add("FunctionLevelLinking", True)
                n_cl.add("IntrinsicFunctions", True)
            std_defs = self.get_std_defines(target, cfg)
            std_defs.append("%(PreprocessorDefinitions)")
            n_cl.add("PreprocessorDefinitions", list(cfg["defines"]) + std_defs)
            n_cl.add("MultiProcessorCompilation", True)
            n_cl.add("MinimalRebuild", False)
            n_cl.add("AdditionalIncludeDirectories", cfg["includedirs"])

            crt = "MultiThreaded"
            if cfg.is_debug:
                crt += "Debug"
            if cfg["win32-crt-linkage"] == "dll":
                crt += "DLL"
            n_cl.add("RuntimeLibrary", crt)

            # Currently we don't make any distinction between preprocessor, C
            # and C++ flags as they're basically all the same at MSVS level
            # too and all go into the same place in the IDE and same
            # AdditionalOptions node in the project file.
            all_cflags = VSList(" ", cfg["compiler-options"],
                                     cfg["c-compiler-options"],
                                     cfg["cxx-compiler-options"])
            if all_cflags:
                all_cflags.append("%(AdditionalOptions)")
                n_cl.add("AdditionalOptions", all_cflags)

            n.add(n_cl)
            n_link = Node("Link")
            self._add_extra_options_to_node(target, n_link)
            n.add(n_link)
            if is_exe(target) and target["win32-subsystem"] == "console":
                n_link.add("SubSystem", "Console")
            else:
                n_link.add("SubSystem", "Windows")
            n_link.add("GenerateDebugInformation", True)
            if not cfg.is_debug:
                n_link.add("EnableCOMDATFolding", True)
                n_link.add("OptimizeReferences", True)
            if not is_library(target):
                libdirs = VSList(";", cfg["libdirs"])
                if libdirs:
                    libdirs.append("%(AdditionalLibraryDirectories)")
                    n_link.add("AdditionalLibraryDirectories", libdirs)
                ldflags = VSList(" ", cfg["link-options"])
                if ldflags:
                    ldflags.append("%(AdditionalOptions)")
                    n_link.add("AdditionalOptions", ldflags)
            libs = cfg["libs"]
            if libs:
                addlibs = VSList(";", ("%s.lib" % x.as_py() for x in libs))
                addlibs.append("%(AdditionalDependencies)")
                if is_library(target):
                    n_lib = Node("Lib")
                    self._add_extra_options_to_node(target, n_lib)
                    n.add(n_lib)
                    n_lib.add("AdditionalDependencies", addlibs)
                else:
                    n_link.add("AdditionalDependencies", addlibs)
            pre_build = cfg["pre-build-commands"]
            if pre_build:
                n_script = Node("PreBuildEvent")
                n_script.add("Command", VSList("\n", pre_build))
                n.add(n_script)
            post_build = cfg["post-build-commands"]
            if post_build:
                n_script = Node("PostBuildEvent")
                n_script.add("Command", VSList("\n", post_build))
                n.add(n_script)
            root.add(n)

        # Source files:
        items = Node("ItemGroup")
        root.add(items)
        for sfile in target.sources:
            ext = sfile.filename.get_extension()
            # TODO: share this code with VS200x
            # FIXME: make this more solid
            if ext in ['cpp', 'cxx', 'cc', 'c']:
                items.add("ClCompile", Include=sfile.filename)
            else:
                # FIXME: handle both compilation into cpp and c files
                genfiletype = bkl.compilers.CxxFileType.get()
                genname = bkl.expr.PathExpr([bkl.expr.LiteralExpr(sfile.filename.get_basename())],
                                            bkl.expr.ANCHOR_BUILDDIR,
                                            pos=sfile.filename.pos).change_extension("cpp")

                ft_from = bkl.compilers.get_file_type(ext)
                compiler = bkl.compilers.get_compiler(self, ft_from, genfiletype)

                customBuild = Node("CustomBuild", Include=sfile.filename)
                customBuild.add("Command", compiler.commands(self, target, sfile.filename, genname))
                customBuild.add("Outputs", genname)
                items.add(customBuild)
                items.add("ClCompile", Include=genname)

        # Headers files:
        if target.headers:
            items = Node("ItemGroup")
            root.add(items)
            for sfile in target.headers:
                items.add("ClInclude", Include=sfile.filename)

        # Dependencies:
        target_deps = target["deps"].as_py()
        if target_deps:
            refs = Node("ItemGroup")
            root.add(refs)
            for dep_id in target_deps:
                dep = target.project.get_target(dep_id)
                depnode = Node("ProjectReference", Include=dep["%s.projectfile" % self.name])
                depnode.add("Project", dep["%s.guid" % self.name].as_py().lower())
                refs.add(depnode)

        root.add("Import", Project="$(VCTargetsPath)\\Microsoft.Cpp.targets")
        root.add("ImportGroup", Label="ExtensionTargets")

        f = OutputFile(filename, EOL_WINDOWS,
                       creator=self, create_for=target)
        f.write(codecs.BOM_UTF8)
        f.write(XmlFormatter(paths_info).format(root))
        f.commit()
        self._write_filters_file_for(filename)

        return self.Project(target.name,
                            guid,
                            projectfile,
                            target_deps,
                            [x.config for x in target.configurations],
                            target.source_pos)

    def _add_VCTargetsPath(self, node):
        pass

    def _add_extra_options_to_node(self, target, node):
        """Add extra native options specified in vs2010.option.* properties."""
        try:
            scope = node["Label"]
        except KeyError:
            if node.name == "PropertyGroup":
                scope = ""
            else:
                scope = node.name
        for key, value in self.collect_extra_options_for_node(target, scope):
            node.add(key, value)


    def _write_filters_file_for(self, filename):
        f = OutputFile(filename + ".filters", EOL_WINDOWS,
                       creator=self, create_for=filename)
        f.write("""\
<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemGroup>
    <Filter Include="Source Files">
      <UniqueIdentifier>{4FC737F1-C7A5-4376-A066-2A32D752A2FF}</UniqueIdentifier>
      <Extensions>cpp;c;cc;cxx;def;odl;idl;hpj;bat;asm;asmx</Extensions>
    </Filter>
    <Filter Include="Header Files">
      <UniqueIdentifier>{93995380-89BD-4b04-88EB-625FBE52EBFB}</UniqueIdentifier>
      <Extensions>h;hpp;hxx;hm;inl;inc;xsd</Extensions>
    </Filter>
    <Filter Include="Resource Files">
      <UniqueIdentifier>{67DA6AB6-F800-4c08-8B7A-83BB121AAD01}</UniqueIdentifier>
      <Extensions>rc;ico;cur;bmp;dlg;rc2;rct;bin;rgs;gif;jpg;jpeg;jpe;resx;tiff;tif;png;wav;mfcribbon-ms</Extensions>
    </Filter>
  </ItemGroup>
</Project>
""")
        f.commit()

    def get_builddir_for(self, target):
        prj = target["%s.projectfile" % self.name]
        # TODO: reference Configuration setting properly, as bkl setting, move this to vsbase
        return bkl.expr.PathExpr(prj.components[:-1] + [bkl.expr.LiteralExpr("$(Configuration)")], prj.anchor)




class VS2010Solution(VSSolutionBase):
    format_version = "11.00"
    human_version = "2010"

    def write_header(self, file):
        file.write(codecs.BOM_UTF8)
        file.write("\n")
        super(VS2010Solution, self).write_header(file)


class VS2010Toolset(VS201xToolsetBase):
    """
    Visual Studio 2010.


    Special properties
    ------------------
    In addition to the properties described below, it's possible to specify any
    of the ``vcxproj`` properties directly in a bakefile. To do so, you have to
    set specially named variables on the target.

    The variables are prefixed with ``vs2010.option.``, followed by node name and
    property name. The following nodes are supported:

      - ``vs2010.option.Globals.*``
      - ``vs2010.option.Configuration.*``
      - ``vs2010.option.*`` (this is the unnamed ``PropertyGroup`` with
        global settings such as ``TargetName``)
      - ``vs2010.option.ClCompile.*``
      - ``vs2010.option.Link.*``
      - ``vs2010.option.Lib.*``

    Examples:

    .. code-block:: bkl

        vs2010.option.GenerateManifest = false;
        vs2010.option.Link.CreateHotPatchableImage = Enabled;

    """
    name = "vs2010"

    version = 10
    proj_versions = [10]
    # don't set to "v100" because vs2010 doesn't explicitly set it by default:
    platform_toolset = None
    Solution = VS2010Solution
    Project = VS2010Project



class VS2012Solution(VS2010Solution):
    format_version = "12.00"
    human_version = "2012"


class VS2012Project(VS2010Project):
    version = 11


class VS2012Toolset(VS201xToolsetBase):
    """
    Visual Studio 2012.


    Special properties
    ------------------
    This toolset supports the same special properties that
    :ref:`ref_toolset_vs2010`. The only difference is that they are prefixed
    with ``vs2012.option.`` instead of ``vs2010.option.``, i.e. the nodes are:

      - ``vs2012.option.Globals.*``
      - ``vs2012.option.Configuration.*``
      - ``vs2012.option.*`` (this is the unnamed ``PropertyGroup`` with
        global settings such as ``TargetName``)
      - ``vs2012.option.ClCompile.*``
      - ``vs2012.option.Link.*``
      - ``vs2012.option.Lib.*``

    """

    name = "vs2012"

    version = 11
    proj_versions = [10, 11]
    platform_toolset = "v110"
    Solution = VS2012Solution
    Project = VS2012Project

    def _add_VCTargetsPath(self, node):
        node.add(Node("VCTargetsPath",
                      "$(VCTargetsPath11)",
                      Condition="'$(VCTargetsPath11)' != '' and '$(VSVersion)' == '' and $(VisualStudioVersion) == ''"))
