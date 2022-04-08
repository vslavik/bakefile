#
#  This file is part of Bakefile (http://bakefile.org)
#
#  Copyright (C) 2011-2013 Vaclav Slavik
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
from bkl.expr import concat, format_string
from bkl.vartypes import ListType, PathType


class VS201xXmlFormatter(XmlFormatter):
    """
    XmlFormatter for VS 201x output.
    """

    elems_not_collapsed = set(["ImportGroup"])

    def __init__(self, settings, paths_info):
        super(VS201xXmlFormatter, self).__init__(settings, paths_info)

# TODO: Put more content into this class, use it properly
class VS2010Project(VSProjectBase):
    """
    """
    version = 10

    def __init__(self, name, guid, projectfile, deps, configs, platforms, source_pos=None):
        self.name = name
        self.guid = guid
        self.projectfile = projectfile
        self.dependencies = deps
        self.configurations = configs
        self.platforms = platforms
        self.source_pos = source_pos



class VS201xToolsetBase(VSToolsetBase):
    """Base class for VS2010, VS2012, VS2013, VS2015, VS2017, VS2019 and VS2022 toolsets."""

    #: XML formatting class
    XmlFormatter = VS201xXmlFormatter

    #: Extension of format files
    proj_extension = "vcxproj"

    #: PlatformToolset property
    platform_toolset = None

    #: ToolsVersion property
    tools_version = "4.0"

    vs201x_target_properties = [
            Property("vs.property-sheets",
                     type=ListType(PathType()),
                     default=bkl.expr.NullExpr(),
                     inheritable=True,
                     doc="""
                         May contain paths to one or more property sheets files
                         that will be imported from the generated project if they
                         exist.
                         """)
        ]

    @classmethod
    def properties_target(cls):
        for p in cls.vsbase_target_properties():
            yield p
        for p in cls.vs201x_target_properties:
            yield p

    def gen_for_target(self, target, project):
        rc_files = []
        cl_files = []
        idl_files = []
        for sfile in target.sources:
            ext = sfile.filename.get_extension()
            # TODO: share this code with VS200x
            # FIXME: make this more solid
            if ext == 'rc':
                rc_files.append(sfile)
            elif ext == 'idl':
                idl_files.append(sfile)
            else:
                cl_files.append(sfile)

        root = Node("Project")
        root["DefaultTargets"] = "Build"
        root["ToolsVersion"] = self.tools_version
        root["xmlns"] = "http://schemas.microsoft.com/developer/msbuild/2003"

        n_configs = Node("ItemGroup", Label="ProjectConfigurations")
        for cfg in self.configs_and_platforms(target):
            n = Node("ProjectConfiguration", Include="%s" % cfg.vs_name)
            n.add("Configuration", cfg.name)
            n.add("Platform", cfg.vs_platform)
            n_configs.add(n)
        root.add(n_configs)

        n_globals = Node("PropertyGroup", Label="Globals")
        n_globals.add("ProjectGuid", "{%s}" % project.guid)
        n_globals.add("Keyword", "Win32Proj")
        n_globals.add("RootNamespace", target.name)
        n_globals.add("ProjectName", target.name)
        self._add_extra_options_to_node(target, n_globals)
        root.add(n_globals)

        root.add("Import", Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props")

        for cfg in self.configs_and_platforms(target):
            n = Node("PropertyGroup", Label="Configuration")
            n["Condition"] = "'$(Configuration)|$(Platform)'=='%s'" % cfg.vs_name
            if is_program(target):
                n.add("ConfigurationType", "Application")
            elif is_library(target):
                n.add("ConfigurationType", "StaticLibrary")
            elif is_dll(target):
                n.add("ConfigurationType", "DynamicLibrary")
            else:
                assert False, "this code should only be called for supported target types"

            n.add("UseDebugLibraries", cfg.is_debug)
            if cfg["win32-unicode"]:
                n.add("CharacterSet", "Unicode")
            else:
                n.add("CharacterSet", "MultiByte")
            if self.platform_toolset:
                # Special case of "msvs" toolset, which means to set the
                # platform toolset appropriately depending on the MSVS version.
                if self.platform_toolset == 'msvs':
                    for v in all_versions:
                        toolset_ver = all_versions[v]

                        # This happens for MSVS 2010 which doesn't specify the
                        # toolset explicitly.
                        if not toolset_ver.platform_toolset:
                            continue

                        node_toolset = Node("PlatformToolset", toolset_ver.platform_toolset)
                        node_toolset["Condition"] = "'$(VisualStudioVersion)'=='%s'" % toolset_ver.version
                        n.add(node_toolset)
                else:
                    n.add("PlatformToolset", self.platform_toolset)

            self._add_extra_options_to_node(cfg, n)
            root.add(n)

        root.add("Import", Project="$(VCTargetsPath)\\Microsoft.Cpp.props")
        root.add("ImportGroup", Label="ExtensionSettings")

        for cfg in self.configs_and_platforms(target):
            n = Node("ImportGroup", Label="PropertySheets")
            n["Condition"] = "'$(Configuration)|$(Platform)'=='%s'" % cfg.vs_name
            n.add("Import",
                  Project="$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props",
                  Condition="exists('$(UserRootDir)\\Microsoft.Cpp.$(Platform).user.props')",
                  Label="LocalAppDataPlatform")

            for property_sheet in cfg["vs.property-sheets"]:
                # For now, always add exists() condition unconditionally as
                # it's often useful to have it, but we don't provide any way
                # to request it explicitly and not having it would be more
                # problematic than using it unnecessarily (which is not really
                # a problem in practice).
                n.add("Import",
                      Project=property_sheet,
                      Condition=concat("exists('", property_sheet, "')"))

            root.add(n)

        root.add("PropertyGroup", Label="UserMacros")

        for cfg in self.configs_and_platforms(target):
            n = Node("PropertyGroup")
            if not is_library(target):
                n.add("LinkIncremental", cfg.is_debug)
            targetname = cfg["basename"]
            if targetname != target.name:
                n.add("TargetName", targetname)
            if not target.is_variable_null("extension"):
                n.add("TargetExt", target["extension"])
            if is_module_dll(target):
                n.add("IgnoreImportLibrary", True)
            if target.is_variable_explicitly_set("outputdir"):
                n.add("OutDir", concat(cfg["outputdir"], "\\"))
            if self.needs_custom_intermediate_dir(target):
                if cfg.vs_platform != "Win32":
                    intdir = "$(Platform)\\$(Configuration)\\$(ProjectName)\\"
                else:
                    intdir = "$(Configuration)\\$(ProjectName)\\"
                n.add("IntDir", intdir)
            if n.has_children():
                n["Condition"] = "'$(Configuration)|$(Platform)'=='%s'" % cfg.vs_name
            self._add_extra_options_to_node(cfg, n)
            root.add(n)

        for cfg in self.configs_and_platforms(target):
            n = Node("ItemDefinitionGroup")
            n["Condition"] = "'$(Configuration)|$(Platform)'=='%s'" % cfg.vs_name
            n_cl = Node("ClCompile")
            n_cl.add("WarningLevel", self.get_vs_warning_level(cfg))
            if cfg.is_debug:
                n_cl.add("Optimization", "Disabled")
            else:
                n_cl.add("Optimization", "MaxSpeed")
                n_cl.add("FunctionLevelLinking", True)
                n_cl.add("IntrinsicFunctions", True)
            std_defs = self.get_std_defines(target, cfg)
            n_cl.add_with_default("PreprocessorDefinitions", list(cfg["defines"]) + std_defs)
            n_cl.add("MultiProcessorCompilation", True)
            n_cl.add("MinimalRebuild", False)
            n_cl.add_with_default("AdditionalIncludeDirectories", cfg["includedirs"])

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
            n_cl.add_with_default("AdditionalOptions", all_cflags)

            self._add_extra_options_to_node(cfg, n_cl)
            n.add(n_cl)

            if rc_files:
                n_res = Node("ResourceCompile")
                n_res.add_with_default("AdditionalIncludeDirectories", cfg["includedirs"])
                std_defs = []
                if cfg["win32-unicode"]:
                    std_defs.append("_UNICODE")
                    std_defs.append("UNICODE")
                # See the comment in VCResourceCompilerTool in vs200x.py for
                # the explanation of why do we do this even though the native
                # projects don't define _DEBUG/NDEBUG for the RC files.
                std_defs.append("_DEBUG" if cfg.is_debug else "NDEBUG")
                n_res.add_with_default("PreprocessorDefinitions", list(cfg["defines"]) + std_defs)
                self._add_extra_options_to_node(cfg, n_res)
                n.add(n_res)

            if idl_files:
                n_idl = Node("Midl")
                n_idl.add_with_default("AdditionalIncludeDirectories", cfg["includedirs"])
                self._add_extra_options_to_node(cfg, n_idl)
                n.add(n_idl)

            n_link = Node("Link")
            if is_program(target) and target["win32-subsystem"] == "console":
                n_link.add("SubSystem", "Console")
            else:
                n_link.add("SubSystem", "Windows")
            n_link.add("GenerateDebugInformation", True)
            if not cfg.is_debug:
                n_link.add("EnableCOMDATFolding", True)
                n_link.add("OptimizeReferences", True)
            if not is_library(target):
                libdirs = VSList(";", target.type.get_libdirs(cfg))
                n_link.add_with_default("AdditionalLibraryDirectories", libdirs)
                ldflags = VSList(" ", target.type.get_link_options(cfg))
                n_link.add_with_default("AdditionalOptions", ldflags)
                libs = target.type.get_ldlibs(cfg)
                if libs:
                    addlibs = VSList(";", ("%s.lib" % x.as_py() for x in libs if x))
                    if is_library(target):
                        n_lib = Node("Lib")
                        self._add_extra_options_to_node(cfg, n_lib)
                        n.add(n_lib)
                        n_lib.add_with_default("AdditionalDependencies", addlibs)
                    else:
                        n_link.add_with_default("AdditionalDependencies", addlibs)
            self._add_extra_options_to_node(cfg, n_link)
            n.add(n_link)

            n_manifest = Node("Manifest")
            self._add_extra_options_to_node(cfg, n_manifest)
            if n_manifest.has_children():
                n.add(n_manifest)

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
        if cl_files:
            items = Node("ItemGroup")
            root.add(items)
            cl_files_map = bkl.compilers.disambiguate_intermediate_file_names(cl_files)
            for sfile in cl_files:
                if sfile["compile-commands"]:
                    self._add_custom_build_file(items, sfile)
                else:
                    ext = sfile.filename.get_extension()
                    # TODO: share this code with VS200x
                    # FIXME: make this more solid
                    if ext in ['cpp', 'cxx', 'cc', 'c']:
                        n_cl_compile = Node("ClCompile", Include=sfile.filename)
                    else:
                        # FIXME: handle both compilation into cpp and c files
                        genfiletype = bkl.compilers.CxxFileType.get()
                        genname = bkl.expr.PathExpr([bkl.expr.LiteralExpr(sfile.filename.get_basename())],
                                                    bkl.expr.ANCHOR_BUILDDIR,
                                                    pos=sfile.filename.pos).change_extension("cpp")

                        ft_from = bkl.compilers.get_file_type(ext)
                        compiler = bkl.compilers.get_compiler(self, ft_from, genfiletype)

                        customBuild = Node("CustomBuild", Include=sfile.filename)
                        customBuild.add("Command", VSList("\n", compiler.commands(self, target, sfile.filename, genname)))
                        customBuild.add("Outputs", genname)
                        items.add(customBuild)
                        n_cl_compile = Node("ClCompile", Include=genname)
                    # Handle files with custom object name:
                    if sfile in cl_files_map:
                        n_cl_compile.add("ObjectFileName",
                                         concat("$(IntDir)\\", cl_files_map[sfile], ".obj"))
                    self._add_per_file_options(sfile, n_cl_compile)
                    items.add(n_cl_compile)

        # Headers files:
        if target.headers:
            items = Node("ItemGroup")
            root.add(items)
            for sfile in target.headers:
                if sfile["compile-commands"]:
                    self._add_custom_build_file(items, sfile)
                else:
                    items.add("ClInclude", Include=sfile.filename)

        # Resources:
        if rc_files:
            items = Node("ItemGroup")
            root.add(items)
            rc_files_map = bkl.compilers.disambiguate_intermediate_file_names(rc_files)
            for sfile in rc_files:
                n_rc_compile = Node("ResourceCompile", Include=sfile.filename)
                # Handle files with custom object name:
                if sfile in rc_files_map:
                    n_rc_compile.add("ResourceOutputFileName",
                                     concat("$(IntDir)\\", rc_files_map[sfile], ".res"))
                self._add_per_file_options(sfile, n_rc_compile)
                items.add(n_rc_compile)

        # IDL files:
        if idl_files:
            items = Node("ItemGroup")
            root.add(items)
            for sfile in idl_files:
                n_midl = Node("Midl", Include=sfile.filename)
                self._add_per_file_options(sfile, n_midl)
                items.add(n_midl)

        # Dependencies:
        target_deps = self._get_references(target)
        if target_deps:
            refs = Node("ItemGroup")
            root.add(refs)
            for dep in target_deps:
                dep_prj = self.get_project_object(dep)
                depnode = Node("ProjectReference", Include=dep_prj.projectfile)
                depnode.add("Project", "{%s}" % dep_prj.guid.lower())
                refs.add(depnode)

        root.add("Import", Project="$(VCTargetsPath)\\Microsoft.Cpp.targets")
        root.add("ImportGroup", Label="ExtensionTargets")

        filename = project.projectfile.as_native_path_for_output(target)
        paths_info = self.get_project_paths_info(target, project)

        formatter = self.XmlFormatter(target.project.settings, paths_info)
        f = OutputFile(filename, EOL_WINDOWS,
                       creator=self, create_for=target)
        f.write(codecs.BOM_UTF8)
        f.write(formatter.format(root))
        f.commit()
        self._write_filters_file_for(filename, formatter,
                                     target.headers, cl_files, idl_files, rc_files)


    def _add_custom_build_file(self, node, srcfile):
        n = Node("CustomBuild", Include=srcfile.filename)
        for cfg in self.configs_and_platforms(srcfile):
            outputs = cfg["outputs"]
            fmt_dict = {"in": srcfile.filename, "out": outputs}
            idx = 0
            for outN in outputs:
                fmt_dict["out%d" % idx] = outN
                idx += 1
            commands = format_string(cfg["compile-commands"], fmt_dict)
            message = format_string(cfg["compile-message"], fmt_dict)

            cond = "'$(Configuration)|$(Platform)'=='%s'" % cfg.vs_name
            n.add(Node("Command", VSList("\n", commands), Condition=cond))
            n.add(Node("Outputs", outputs, Condition=cond))
            dependencies = cfg["dependencies"]
            if dependencies:
                n.add(Node("AdditionalInputs", dependencies, Condition=cond))
            n.add(Node("Message", message if message else commands, Condition=cond))
        node.add(n)


    def _get_references(self, target):
        if not target["deps"]:
            return None

        # In addition to explicit dependencies, add dependencies of static libraries
        # linked into target to the list of references.
        prj = target.project
        deps = [prj.get_target(t) for t in target["deps"].as_py()]
        try:
            more = [t for t in target.type.get_linkable_deps(target) if t not in deps]
            deps.extend(more)
        except AttributeError:
            pass
        return deps


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
            node.add_or_replace(key, value)


    def _add_per_file_options(self, srcfile, node):
        """Add options that are set on per-file basis."""
        # TODO: add regular options such as 'defines' here too, not just
        #       the vsXXXX.option.* overrides
        for cfg in self.configs_and_platforms(srcfile):
            cond = "'$(Configuration)|$(Platform)'=='%s'" % cfg.vs_name
            if not cfg.should_build():
                node.add(Node("ExcludedFromBuild", True, Condition=cond))
            for key, value in self.collect_extra_options_for_node(srcfile, node.name, inherit=False):
                node.add(Node(key, value, Condition=cond))


    def _write_filters_file_for(self, filename, formatter,
                                hdr_files, cl_files, idl_files, rc_files):
        root = Node("Project")
        root["ToolsVersion"] = "4.0" # even if tools_version is different (VS2013)
        root["xmlns"] = "http://schemas.microsoft.com/developer/msbuild/2003"
        filters = Node("ItemGroup")
        root.add(filters)
        f = Node("Filter", Include="Source Files")
        filters.add(f)
        f.add("UniqueIdentifier", "{4FC737F1-C7A5-4376-A066-2A32D752A2FF}")
        f.add("Extensions", "cpp;c;cc;cxx;def;odl;idl;hpj;bat;asm;asmx")
        f = Node("Filter", Include="Header Files")
        filters.add(f)
        f.add("UniqueIdentifier", "{93995380-89BD-4b04-88EB-625FBE52EBFB}")
        f.add("Extensions", "h;hpp;hxx;hm;inl;inc;xsd")
        f = Node("Filter", Include="Resource Files")
        filters.add(f)
        f.add("UniqueIdentifier", "{67DA6AB6-F800-4c08-8B7A-83BB121AAD01}")
        f.add("Extensions", "rc;ico;cur;bmp;dlg;rc2;rct;bin;rgs;gif;jpg;jpeg;jpe;resx;tiff;tif;png;wav;mfcribbon-ms")

        if hdr_files:
            group = Node("ItemGroup")
            root.add(group)
            for sfile in hdr_files:
                n = Node("ClInclude", Include=sfile.filename)
                group.add(n)
                n.add("Filter", "Header Files")

        if cl_files or idl_files:
            group = Node("ItemGroup")
            root.add(group)
            for sfile in cl_files:
                n = Node("ClCompile", Include=sfile.filename)
                group.add(n)
                n.add("Filter", "Source Files")
            for sfile in idl_files:
                n = Node("Midl", Include=sfile.filename)
                group.add(n)
                n.add("Filter", "Source Files")

        if rc_files:
            group = Node("ItemGroup")
            root.add(group)
            for sfile in rc_files:
                n = Node("ResourceCompile", Include=sfile.filename)
                group.add(n)
                n.add("Filter", "Resource Files")

        f = OutputFile(filename + ".filters", EOL_WINDOWS,
                       creator=self, create_for=filename)
        f.write(codecs.BOM_UTF8)
        f.write(formatter.format(root))
        f.commit()


    def _order_configs_and_archs(self, configs_iter, archs_list):
        for c in configs_iter:
            for a in archs_list:
                yield (c, a)


    def get_vs_warning_level(self, cfg):
        """
        Return MSVS warning level option value corresponding to the warning
        option in the specified config.
        """
        WARNING_LEVELS = { "no": "TurnOffAllWarnings",
                           "minimal": "Level1",
                           "default": "Level3",
                           "all": "Level4",
                           "max": "EnableAllWarnings",
        }
        return WARNING_LEVELS[cfg["warnings"].as_py()]



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
      - ``vs2010.option.ResourceCompile.*``
      - ``vs2010.option.Link.*``
      - ``vs2010.option.Lib.*``
      - ``vs2010.option.Manifest.*``

    These variables can be used in several places in bakefiles:

      - In targets, to applied them as project's global settings.
      - In modules, to apply them to all projects in the module and its submodules.
      - On per-file basis, to modify file-specific settings.

    Examples:

    .. code-block:: bkl

        vs2010.option.GenerateManifest = false;
        vs2010.option.Link.CreateHotPatchableImage = Enabled;

        crashrpt.cpp::vs2010.option.ClCompile.ExceptionHandling = Async;
    """
    name = "vs2010"

    version = 10
    msvs_version = "2010"
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
      - ``vs2012.option.ResourceCompile.*``
      - ``vs2012.option.Link.*``
      - ``vs2012.option.Lib.*``
      - ``vs2012.option.Manifest.*``

    """

    name = "vs2012"

    version = 11
    msvs_version = "2012"
    proj_versions = [10, 11]
    platform_toolset = "v110"
    Solution = VS2012Solution
    Project = VS2012Project


class VS2013Solution(VS2010Solution):
    format_version = "12.00" # not a typo - same as VS2010
    human_version = "2013"

    def write_header(self, file):
        super(VS2013Solution, self).write_header(file)
        file.write("VisualStudioVersion = 12.0.21005.1\n")
        file.write("MinimumVisualStudioVersion = 10.0.40219.1\n")


class VS2013Project(VS2010Project):
    version = 12


class VS2013Toolset(VS201xToolsetBase):
    """
    Visual Studio 2013.


    Special properties
    ------------------
    This toolset supports the same special properties that
    :ref:`ref_toolset_vs2010`. The only difference is that they are prefixed
    with ``vs2013.option.`` instead of ``vs2010.option.``, i.e. the nodes are:

      - ``vs2013.option.Globals.*``
      - ``vs2013.option.Configuration.*``
      - ``vs2013.option.*`` (this is the unnamed ``PropertyGroup`` with
        global settings such as ``TargetName``)
      - ``vs2013.option.ClCompile.*``
      - ``vs2013.option.ResourceCompile.*``
      - ``vs2013.option.Link.*``
      - ``vs2013.option.Lib.*``
      - ``vs2013.option.Manifest.*``

    """

    name = "vs2013"

    version = 12
    msvs_version = "2013"
    proj_versions = [10, 11, 12]
    platform_toolset = "v120"
    tools_version = "12.0"
    Solution = VS2013Solution
    Project = VS2013Project


class VS2015Solution(VS2010Solution):
    format_version = "12.00"
    # Unlike the previous versions, this one uses the numeric version and not
    # the year in the comment in the solution files.
    human_version = "14"

    def write_header(self, file):
        super(VS2015Solution, self).write_header(file)
        file.write("VisualStudioVersion = 14.0.23107.0\n")
        file.write("MinimumVisualStudioVersion = 10.0.40219.1\n")


class VS2015Project(VS2010Project):
    version = 14


class VS2015Toolset(VS201xToolsetBase):
    """
    Visual Studio 2015.


    Special properties
    ------------------
    This toolset supports the same special properties that
    :ref:`ref_toolset_vs2010`. The only difference is that they are prefixed
    with ``vs2015.option.`` instead of ``vs2010.option.``, i.e. the nodes are:

      - ``vs2015.option.Globals.*``
      - ``vs2015.option.Configuration.*``
      - ``vs2015.option.*`` (this is the unnamed ``PropertyGroup`` with
        global settings such as ``TargetName``)
      - ``vs2015.option.ClCompile.*``
      - ``vs2015.option.ResourceCompile.*``
      - ``vs2015.option.Link.*``
      - ``vs2015.option.Lib.*``
      - ``vs2015.option.Manifest.*``

    """

    name = "vs2015"

    version = 14
    msvs_version = "2015"
    proj_versions = [10, 11, 12, 14]
    platform_toolset = "v140"
    tools_version = "14.0"
    Solution = VS2015Solution
    Project = VS2015Project


class VS2017Solution(VS2010Solution):
    format_version = "12.00"
    human_version = "15"

    def write_header(self, file):
        super(VS2017Solution, self).write_header(file)
        file.write("VisualStudioVersion = 15.0.27130.2003\n")
        file.write("MinimumVisualStudioVersion = 10.0.40219.1\n")


class VS2017Project(VS2010Project):
    version = 15


class VS2017Toolset(VS201xToolsetBase):
    """
    Visual Studio 2017.


    Special properties
    ------------------
    This toolset supports the same special properties that
    :ref:`ref_toolset_vs2010`. The only difference is that they are prefixed
    with ``vs2017.option.`` instead of ``vs2010.option.``, i.e. the nodes are:

      - ``vs2017.option.Globals.*``
      - ``vs2017.option.Configuration.*``
      - ``vs2017.option.*`` (this is the unnamed ``PropertyGroup`` with
        global settings such as ``TargetName``)
      - ``vs2017.option.ClCompile.*``
      - ``vs2017.option.ResourceCompile.*``
      - ``vs2017.option.Link.*``
      - ``vs2017.option.Lib.*``
      - ``vs2017.option.Manifest.*``

    """

    name = "vs2017"

    version = 15
    msvs_version = "2017"
    proj_versions = [10, 11, 12, 14, 15]
    platform_toolset = "v141"
    tools_version = "15.0"
    Solution = VS2017Solution
    Project = VS2017Project


class VS2019Solution(VS2010Solution):
    format_version = "12.00"
    human_version = "16"

    def write_header(self, file):
        super(VS2019Solution, self).write_header(file)
        file.write("VisualStudioVersion = 16.0.29020.237\n")
        file.write("MinimumVisualStudioVersion = 10.0.40219.1\n")


class VS2019Project(VS2010Project):
    version = 16


class VS2019Toolset(VS201xToolsetBase):
    """
    Visual Studio 2019.


    Special properties
    ------------------
    This toolset supports the same special properties that
    :ref:`ref_toolset_vs2010`. The only difference is that they are prefixed
    with ``vs2019.option.`` instead of ``vs2010.option.``, i.e. the nodes are:

      - ``vs2019.option.Globals.*``
      - ``vs2019.option.Configuration.*``
      - ``vs2019.option.*`` (this is the unnamed ``PropertyGroup`` with
        global settings such as ``TargetName``)
      - ``vs2019.option.ClCompile.*``
      - ``vs2019.option.ResourceCompile.*``
      - ``vs2019.option.Link.*``
      - ``vs2019.option.Lib.*``
      - ``vs2019.option.Manifest.*``

    """

    name = "vs2019"

    version = 16
    msvs_version = "2019"
    proj_versions = [10, 11, 12, 14, 15, 16]
    platform_toolset = "v142"
    tools_version = "16.0"
    Solution = VS2019Solution
    Project = VS2019Project


class VS2022Solution(VS2010Solution):
    format_version = "12.00"
    human_version = "17"

    def write_header(self, file):
        super(VS2022Solution, self).write_header(file)
        file.write("VisualStudioVersion = 17.0.31919.166\n")
        file.write("MinimumVisualStudioVersion = 10.0.40219.1\n")


class VS2022Project(VS2010Project):
    version = 17


class VS2022Toolset(VS201xToolsetBase):
    """
    Visual Studio 2022.


    Special properties
    ------------------
    This toolset supports the same special properties that
    :ref:`ref_toolset_vs2010`. The only difference is that they are prefixed
    with ``vs2022.option.`` instead of ``vs2010.option.``, i.e. the nodes are:

      - ``vs2022.option.Globals.*``
      - ``vs2022.option.Configuration.*``
      - ``vs2022.option.*`` (this is the unnamed ``PropertyGroup`` with
        global settings such as ``TargetName``)
      - ``vs2022.option.ClCompile.*``
      - ``vs2022.option.ResourceCompile.*``
      - ``vs2022.option.Link.*``
      - ``vs2022.option.Lib.*``
      - ``vs2022.option.Manifest.*``

    """

    name = "vs2022"

    version = 17
    msvs_version = "2022"
    proj_versions = [10, 11, 12, 14, 15, 16, 17]
    platform_toolset = "v143"
    tools_version = "17.0"
    Solution = VS2022Solution
    Project = VS2022Project


all_versions = {
        10: VS2010Toolset,
        11: VS2012Toolset,
        12: VS2013Toolset,
        14: VS2015Toolset,
        15: VS2017Toolset,
        16: VS2019Toolset,
        17: VS2022Toolset,
    }

class MSVSSolutionsBundle(object):
    """
    Representation of one or more MSVS solution files.

    ``MSVSToolset`` can generate several solution files for different MSVS
    versions, depending on which msvsNNNN.solutionfile options are specified.
    """

    def __init__(self, toolset, module):
        self.solutions = {}
        for v in all_versions:
            toolset_ver = all_versions[v]
            sln = module["%s%s.solutionfile" % (toolset.name, toolset_ver.msvs_version)]
            if sln:
                self.solutions[v] = toolset_ver.Solution(toolset, module, sln)

        if not self.solutions:
            # If no version-specific solutions are specified, create a
            # version-independent solution file which will be opened by the
            # latest installed version.
            sln = module["%s.solutionfile" % toolset.name]
            self.solutions[17] = VS2022Solution(toolset, module, sln)

    def add_project(self, prj):
        for s in self.solutions.values():
            s.add_project(prj)

    def add_subsolution(self, subsol):
        for v in self.solutions:
            if not v in subsol.solutions:
                continue

            self.solutions[v].add_subsolution(subsol.solutions[v])

    def write(self):
        for s in self.solutions.values():
            s.write()


class MSVSToolset(VS201xToolsetBase):
    """
    Any Microsoft Visual Studio version using MSBuild projects.

    Files generated by this toolset can be used with any Microsoft Visual
    Studio version from 2010 to 2022.


    Special properties
    ------------------

    In addition to the properties described below, it's possible to specify any
    of the ``vcxproj`` properties directly in a bakefile. To do so, you have to
    set specially named variables on the target.

    The variables are prefixed with ``msvs.option.``, followed by node name and
    property name. The following nodes are supported:

      - ``msvs.option.Globals.*``
      - ``msvs.option.Configuration.*``
      - ``msvs.option.*`` (this is the unnamed ``PropertyGroup`` with
        global settings such as ``TargetName``)
      - ``msvs.option.ClCompile.*``
      - ``msvs.option.ResourceCompile.*``
      - ``msvs.option.Link.*``
      - ``msvs.option.Lib.*``
      - ``msvs.option.Manifest.*``

    These variables can be used in several places in bakefiles:

      - In targets, to applied them as project's global settings.
      - In modules, to apply them to all projects in the module and its submodules.
      - On per-file basis, to modify file-specific settings.

    Examples:

    .. code-block:: bkl

        msvs.option.GenerateManifest = false;
        msvs.option.Link.CreateHotPatchableImage = Enabled;

        crashrpt.cpp::msvs.option.ClCompile.ExceptionHandling = Async;
    """

    name = "msvs"

    # There is no specific version associated with this toolset, it is
    # determined by the version of MSVS used for actual building.
    version = None

    # This toolset is handled specially in VS201xToolsetBase, see there.
    platform_toolset = 'msvs'

    # This is used in VSToolsetBase to check for version compatibility.
    proj_versions = all_versions.keys()

    # This tools version is supported by MSVS 2010 and still works just fine
    # for MSVS 2022.
    tools_version = "4.0"

    # We use a special multi-solution class, but just the same plain project
    # class as all the other MSVS 201x toolsets.
    Solution = MSVSSolutionsBundle
    Project = VS2010Project

    # Augment the base class method with version-dependent solution files
    # properties: it may still make sense to have those even if the projects
    # version-independent to make it possible to directly open the solution in
    # the desired MSVS version (the version-independent solution file would be
    # always opened in the latest installed one).
    @classmethod
    def properties_module(cls):
        for p in super(cls, cls).properties_module():
            yield p

        for v in cls.proj_versions:
            yield Property("%s%s.solutionfile" % (cls.name, all_versions[v].msvs_version),
                           type=PathType(),
                           default=bkl.expr.NullExpr(),
                           inheritable=False,
                           doc="""
                               File name of the solution file for the specified version.

                               If any of versioned solution file properties are specified,
                               the version-independent solution file generated by default
                               is not generated, as if ``msvs.generate-solution`` were set
                               to ``false``.
                               """)

    @classmethod
    def get_solutionfile_path(cls, module):
        # Choose the first solution file path, but check that any other ones
        # that are specified are consistent with it.
        slnpath = None

        # Consider both version-specific and version-independent solutions here.
        for ver_str in [''] + [all_versions[v].msvs_version for v in all_versions]:
            slnprop = "%s%s.solutionfile" % (cls.name, ver_str)

            if not module.is_variable_explicitly_set(slnprop):
                continue

            slnpath2 = module[slnprop]
            if not slnpath2:
                continue

            if slnpath is None:
                slnpath = slnpath2
                continue

            if slnpath.components[:-1] != slnpath2.components[:-1] or \
                   slnpath.anchor != slnpath2.anchor or \
                       slnpath.anchor_file != slnpath2.anchor_file:
               raise Error(("can't deduce default project path " +
                            "(solution files \"%s\" and \"%s\" don't use " +
                            "the same path), specify it explicitly") %
                           (slnpath, slnpath2))

        if slnpath is None:
            # If no solution file paths are specified, just use the default.
            slnpath = bkl.expr.PathExpr([bkl.expr.LiteralExpr(module.name + ".sln")])

        return slnpath

    # Override base class method to create our solution in a different way
    # because we may have more than one of them.
    def create_solution(self, module):
        return self.Solution(self, module)
