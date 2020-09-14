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
Toolsets for Visual Studio 2003, 2005 and 2008.
"""

from bkl.plugins.vsbase import *
from bkl.expr import concat, format_string
from bkl.compilers import disambiguate_intermediate_file_names

# Misc constants for obscure numbers in the output format:
typeApplication         = 1
typeDynamicLibrary      = 2
typeStaticLibrary       = 4

linkIncrementalDefault  = 0
linkIncrementalNo       = 1
linkIncrementalYes      = 2

optReferencesDefault    = 0
optNoReferences         = 1
optReferences           = 2

optFoldingDefault       = 0
optNoFolding            = 1
optFolding              = 2

optimizeDisabled        = 0
optimizeMinSpace        = 1
optimizeMaxSpeed        = 2
optimizeFull            = 3
optimizeCustom          = 4

machineX86              = 1
machineARM              = 3
machineAMD64            = 17

subSystemNotSet         = 0
subSystemConsole        = 1
subSystemWindows        = 2

pchNone                 = 0
pchCreateUsingSpecific  = 1
pchGenerateAuto_VC7     = 2
pchUseUsingSpecificic_VC7 = 3
pchUseUsingSpecificic_VC89 = 2

rtMultiThreaded         = 0
rtMultiThreadedDebug    = 1
rtMultiThreadedDLL      = 2
rtMultiThreadedDebugDLL = 3
rtSingleThreaded        = 4
rtSingleThreadedDebug   = 5

debugDisabled           = 0
debugOldStyleInfo       = 1
debugLineInfoOnly       = 2
debugEnabled            = 3
debugEditAndContinue    = 4


VCPROJ_CHARSET = "Windows-1252"


class VS200xExprFormatter(VSExprFormatter):

    substs = {
                "config" : "$(ConfigurationName)",
                "arch"   : "$(PlatformName)",
             }

    def literal(self, e):
        if '"' in e.value:
            return e.value.replace('"', '\\"')
        else:
            return e.value

class VS200xXmlFormatter(XmlFormatter):
    """
    XmlFormatter for VS 200x output.
    """

    indent_step = "\t"
    ExprFormatter = VS200xExprFormatter
    elems_not_collapsed = set(["References",
                               "Globals",
                               "File",
                               "Filter",
                               "ToolFiles"])

    def __init__(self, settings, paths_info):
        super(VS200xXmlFormatter, self).__init__(settings, paths_info, charset=VCPROJ_CHARSET)

    # Override to insert line breaks before each attribute.
    def format_attrs(self, attrs, indent):
        s = ''
        for key, value in attrs:
            s += "\n%s\t%s=%s" % (indent, key, value)
        return s

    def format_end_tag_with_attrs(self, indent):
        return "\n%s\t>" % indent

    def format_end_empty_tag(self, indent):
        return "\n%s/>" % indent


# TODO: Put more content into these classes, use them properly
class VS200xProject(VSProjectBase):
    def __init__(self, name, guid, projectfile, deps, configs, platforms, source_pos=None):
        self.name = name
        self.guid = guid
        self.projectfile = projectfile
        self.dependencies = deps
        self.configurations = configs
        self.platforms = platforms
        self.source_pos = source_pos

class VS2003Project(VS200xProject):
    version = 7.1

class VS2005Project(VS200xProject):
    version = 8

class VS2008Project(VS200xProject):
    version = 9


class VS2003Solution(VSSolutionBase):
    format_version = "8.00"
    human_version = None

class VS2005Solution(VSSolutionBase):
    format_version = "9.00"
    human_version = "2005"

class VS2008Solution(VSSolutionBase):
    format_version = "10.00"
    human_version = "2008"



class VS200xToolsetBase(VSToolsetBase):
    """Base class for VS200{358} toolsets."""

    #: XML formatting class
    XmlFormatter = VS200xXmlFormatter

    #: Extension of format files
    proj_extension = "vcproj"

    #: Whether /MP switch is supported
    has_parallel_compilation = False
    #: Whether Detect64BitPortabilityProblems is supported
    detect_64bit_problems = True

    @classmethod
    def properties_target(cls):
        return cls.vsbase_target_properties()

    def gen_for_target(self, target, project):
        root = Node("VisualStudioProject")
        root["ProjectType"] = "Visual C++"
        root["Version"] = "%.2f" % self.version
        root["Name"] =  target.name
        root["ProjectGUID"] = "{%s}" % project.guid
        root["RootNamespace"] = target.name
        root["Keyword"] = "Win32Proj"
        self._add_extra_options_to_node(target, root)

        n_platforms = Node("Platforms")
        for p in self.get_platforms(target):
            n_platforms.add("Platform", Name=p)
        root.add(n_platforms)

        self._add_ToolFiles(root)

        n_configs = Node("Configurations")
        root.add(n_configs)
        for cfg in self.configs_and_platforms(target):
            n = Node("Configuration", Name="%s" % cfg.vs_name)
            n_configs.add(n)
            platform_str = "$(PlatformName)\\" if cfg.vs_platform != "Win32" else ""
            if target.is_variable_explicitly_set("outputdir"):
                n["OutputDirectory"] = concat(cfg["outputdir"], "\\")
            else:
                n["OutputDirectory"] = "$(SolutionDir)%s$(ConfigurationName)" % platform_str
            if self.needs_custom_intermediate_dir(target):
                n["IntermediateDirectory"] = "%s$(ConfigurationName)\\$(ProjectName)\\" % platform_str
            else:
                n["IntermediateDirectory"] = "%s$(ConfigurationName)" % platform_str
            if is_program(target):
                n["ConfigurationType"] = typeApplication
            elif is_library(target):
                n["ConfigurationType"] = typeStaticLibrary
            elif is_dll(target):
                n["ConfigurationType"] = typeDynamicLibrary
            else:
                assert False, "this code should only be called for supported target types"
            if cfg["win32-unicode"]:
                n["CharacterSet"] = 1
            self._add_extra_options_to_node(cfg, n)

            for tool in self.tool_functions:
                if hasattr(self, tool):
                    f_tool = getattr(self, tool)
                    n_tool = f_tool(target, cfg)
                else:
                    n_tool = Node("Tool", Name=tool)
                if n_tool:
                    self._add_extra_options_to_node(cfg, n_tool)
                    n.add(n_tool)

        root.add(Node("References"))

        root.add(self.build_files_list(target))

        root.add(Node("Globals"))

        filename = project.projectfile.as_native_path_for_output(target)
        paths_info = self.get_project_paths_info(target, project)

        f = OutputFile(filename, EOL_WINDOWS, charset=VCPROJ_CHARSET,
                       creator=self, create_for=target)
        f.write(self.XmlFormatter(target.project.settings, paths_info).format(root))
        f.commit()


    def _add_ToolFiles(self, root):
        root.add(Node("ToolFiles"))

    def VCPreBuildEventTool(self, target, cfg):
        n = Node("Tool", Name="VCPreBuildEventTool")
        n["CommandLine"] = VSList("\r\n", cfg["pre-build-commands"])
        return n

    def VCPostBuildEventTool(self, target, cfg):
        n = Node("Tool", Name="VCPostBuildEventTool")
        n["CommandLine"] = VSList("\r\n", cfg["post-build-commands"])
        return n

    def VCAppVerifierTool(self, target, cfg):
        return Node("Tool", Name="VCAppVerifierTool") if is_program(target) else None

    def VCWebDeploymentTool(self, target, cfg):
        return Node("Tool", Name="VCWebDeploymentTool") if is_program(target) else None


    def VCCLCompilerTool(self, target, cfg):
        n = Node("Tool", Name="VCCLCompilerTool")

        # Currently we don't make any distinction between preprocessor, C
        # and C++ flags as they're basically all the same at MSVS level
        # too and all go into the same place in the IDE and same
        # AdditionalOptions node in the project file.
        all_cflags = VSList(" ", cfg["compiler-options"],
                                 cfg["c-compiler-options"],
                                 cfg["cxx-compiler-options"])
        if self.has_parallel_compilation:
            all_cflags.append("/MP") # parallel compilation
        n["AdditionalOptions"] = all_cflags
        n["Optimization"] = optimizeDisabled if cfg.is_debug else optimizeMaxSpeed
        if not cfg.is_debug:
            n["EnableIntrinsicFunctions"] = True
        n["AdditionalIncludeDirectories"] = cfg["includedirs"]
        n["PreprocessorDefinitions"] = list(cfg["defines"]) + self.get_std_defines(target, cfg)

        if not self.has_parallel_compilation and cfg.is_debug:
            n["MinimalRebuild"] = True
        if cfg["win32-crt-linkage"] == "dll":
            n["RuntimeLibrary"] = rtMultiThreadedDebugDLL if cfg.is_debug else rtMultiThreadedDLL
        else:
            n["RuntimeLibrary"] = rtMultiThreadedDebug if cfg.is_debug else rtMultiThreaded

        if not cfg.is_debug:
            n["EnableFunctionLevelLinking"] = True
        n["UsePrecompiledHeader"] = pchNone
        n["WarningLevel"] = self.get_vs_warning_level(cfg)
        if self.detect_64bit_problems:
            n["Detect64BitPortabilityProblems"] = True
        if cfg.is_debug and cfg.vs_platform != "x64":
            n["DebugInformationFormat"] = debugEditAndContinue
        else:
            n["DebugInformationFormat"] = debugEnabled

        return n


    def VCResourceCompilerTool(self, target, cfg):
        n = Node("Tool", Name="VCResourceCompilerTool")
        std_defs = []
        if cfg["win32-unicode"]:
            std_defs.append("_UNICODE")
            std_defs.append("UNICODE")

        # Native Visual Studio projects don't define _DEBUG/NDEBUG for the
        # resource files but it's often convenient to be able to distinguish
        # between debug and release versions in the resources, notably in the
        # version information block, so we exceptionally deviate from the
        # general principle of generating projects as close to native ones as
        # possible and do define these standard MSVC C/C++ definitions to the
        # RC files too (this is also more consistent as we already apply the
        # user-specified C preprocessor definitions to RC files).
        std_defs.append("_DEBUG" if cfg.is_debug else "NDEBUG")
        n["PreprocessorDefinitions"] = list(cfg["defines"]) + std_defs
        n["AdditionalIncludeDirectories"] = cfg["includedirs"]

        return n


    def VCMIDLTool(self, target, cfg):
        n = Node("Tool", Name="VCMIDLTool")
        n["AdditionalIncludeDirectories"] = cfg["includedirs"]

        return n


    def VCLinkerTool(self, target, cfg):
        if is_library(target):
            return None
        n = Node("Tool", Name="VCLinkerTool")
        if is_module_dll(target):
            n["IgnoreImportLibrary"] = True
        n["AdditionalOptions"] = VSList(" ", target.type.get_link_options(cfg))
        libs = target.type.get_ldlibs(cfg)
        if libs:
            n["AdditionalDependencies"] = VSList(" ", ("%s.lib" % x.as_py() for x in libs if x))

        n["AdditionalLibraryDirectories"] = target.type.get_libdirs(cfg)

        targetname = cfg["basename"]
        if targetname != target.name or not target.is_variable_null("extension"):
            n["OutputFile"] = concat("$(OutDir)\\", targetname, target.type.target_file_extension(self, target))

        if cfg.is_debug:
            n["LinkIncremental"] = linkIncrementalYes
        else:
            n["LinkIncremental"] = linkIncrementalNo
        # VS: creates debug info for release too; TODO: make this configurable
        n["GenerateDebugInformation"] = True
        if is_program(target) and cfg["win32-subsystem"] == "console":
            n["SubSystem"] = subSystemConsole
        else:
            n["SubSystem"] = subSystemWindows
        if not cfg.is_debug:
            n["OptimizeReferences"] = optReferences
            n["EnableCOMDATFolding"] = optFolding
        if cfg.vs_platform == "x64":
            n["TargetMachine"] = machineAMD64
        else:
            n["TargetMachine"] = machineX86
        return n


    def VCLibrarianTool(self, target, cfg):
        if not is_library(target):
            return None
        n = Node("Tool", Name="VCLibrarianTool")
        targetname = cfg["basename"]
        if targetname != target.name or not target.is_variable_null("extension"):
            n["OutputFile"] = concat("$(OutDir)\\", targetname, target.type.target_file_extension(self, target))
        return n

    #: List of functions to call to generate <Configuration> children. Note
    #: that the order is slightly different for different VC versions and not
    #: all nodes are present in all versions.
    tool_functions = [
        "VCPreBuildEventTool",
        "VCCustomBuildTool",
        "VCXMLDataGeneratorTool",
        "VCWebServiceProxyGeneratorTool",
        "VCMIDLTool",
        "VCCLCompilerTool",
        "VCManagedResourceCompilerTool",
        "VCResourceCompilerTool",
        "VCPreLinkEventTool",
        "VCLibrarianTool",
        "VCLinkerTool",
        "VCALinkTool",
        "VCManifestTool",
        "VCXDCMakeTool",
        "VCBscMakeTool",
        "VCFxCopTool",
        "VCAppVerifierTool",
        "VCWebDeploymentTool",
        "VCPostBuildEventTool",
        ]


    def build_files_list(self, target):
        files = Node("Files")
        # TODO: use groups definition, filter into groups, add Resource Files

        sources = Node("Filter", Name="Source Files")
        sources["Filter"] = "cpp;c;cc;cxx;def;odl;idl;hpj;bat;asm;asmx"
        sources["UniqueIdentifier"] = "{4FC737F1-C7A5-4376-A066-2A32D752A2FF}"

        headers = Node("Filter", Name="Header Files")
        headers["Filter"] = "h;hpp;hxx;hm;inl;inc;xsd"
        headers["UniqueIdentifier"] = "{93995380-89BD-4b04-88EB-625FBE52EBFB}"

        resources = Node("Filter", Name="Resource Files")
        resources["Filter"] = "rc;ico;cur;bmp;dlg;rc2;rct;bin;rgs;gif;jpg;jpeg;jpe;resx;tiff;tif;png;wav"
        resources["UniqueIdentifier"] = "{67DA6AB6-F800-4c08-8B7A-83BB121AAD01}"

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
        cl_files_map = disambiguate_intermediate_file_names(cl_files)
        rc_files_map = disambiguate_intermediate_file_names(rc_files)

        for sfile in target.sources:
            if sfile["compile-commands"]:
                self._add_custom_build_file(sources, sfile)
            else:
                ext = sfile.filename.get_extension()
                # TODO: share this code with VS2010
                # FIXME: make this more solid
                if ext in ['cpp', 'cxx', 'cc', 'c', 'rc', 'idl']:
                    n_file = Node("File", RelativePath=sfile.filename)
                else:
                    # FIXME: handle both compilation into cpp and c files
                    genfiletype = bkl.compilers.CxxFileType.get()
                    genname = bkl.expr.PathExpr([bkl.expr.LiteralExpr(sfile.filename.get_basename())],
                                                bkl.expr.ANCHOR_BUILDDIR,
                                                pos=sfile.filename.pos).change_extension("cpp")

                    ft_from = bkl.compilers.get_file_type(ext)
                    compiler = bkl.compilers.get_compiler(self, ft_from, genfiletype)

                    n_file = Node("File", RelativePath=sfile.filename)
                    sources.add(n_file)
                    for cfg in self.configs_and_platforms(target):
                        n_cfg = Node("FileConfiguration", Name="%s" % cfg.vs_name)
                        tool = Node("Tool", Name="VCCustomBuildTool")
                        tool["CommandLine"] = VSList("\r\n", compiler.commands(self, target, sfile.filename, genname))
                        tool["Outputs"] = genname
                        n_cfg.add(tool)
                        n_file.add(n_cfg)
                    n_file = Node("File", RelativePath=genname)

                if ext == 'rc':
                    extras = None
                    if sfile in rc_files_map:
                        objfile = concat("$(IntDir)\\", rc_files_map[sfile], ".res")
                        extras = [("ResourceOutputFileName", objfile)]
                    self._add_per_file_options(sfile, n_file, "VCResourceCompilerTool", extras)
                    resources.add(n_file)
                else:
                    if ext == 'idl':
                        self._add_per_file_options(sfile, n_file, "VCMIDLTool", None)
                    else:
                        extras = None
                        if sfile in cl_files_map:
                            objfile = concat("$(IntDir)\\", cl_files_map[sfile], ".obj")
                            extras = [("ObjectFile", objfile)]
                        self._add_per_file_options(sfile, n_file, "VCCLCompilerTool", extras)
                    sources.add(n_file)

        for sfile in target.headers:
            if sfile["compile-commands"]:
                self._add_custom_build_file(headers, sfile)
            else:
                headers.add("File", RelativePath=sfile.filename)

        files.add(sources)
        files.add(headers)
        files.add(resources)
        return files


    def _add_custom_build_file(self, node, srcfile):
        n_file = Node("File", RelativePath=srcfile.filename)
        for cfg in self.configs_and_platforms(srcfile):
            outputs = cfg["outputs"]
            fmt_dict = {"in": srcfile.filename, "out": outputs}
            idx = 0
            for outN in outputs:
                fmt_dict["out%d" % idx] = outN
                idx += 1
            commands = VSList("\r\n", format_string(cfg["compile-commands"], fmt_dict))
            message = format_string(cfg["compile-message"], fmt_dict)

            n_cfg = Node("FileConfiguration", Name="%s" % cfg.vs_name)
            n_tool = Node("Tool", Name="VCCustomBuildTool")
            n_tool["Description"] = message if message else commands
            n_tool["CommandLine"] = commands
            n_tool["Outputs"] = outputs
            n_tool["AdditionalDependencies"] = cfg["dependencies"]
            n_cfg.add(n_tool)
            n_file.add(n_cfg)
        node.add(n_file)


    def _add_extra_options_to_node(self, target, node):
        """Add extra native options specified in vs200x.option.* properties."""
        if node.name == "VisualStudioProject":
            scope = ""
        elif node.name == "Configuration":
            scope = "Configuration"
        else:
            scope = node["Name"]
        for key, value in self.collect_extra_options_for_node(target, scope):
            node[key] = value


    def _add_per_file_options(self, srcfile, node, tool, additional_options):
        """Add options that are set on per-file basis."""
        # TODO: add regular options such as 'defines' here too, not just
        #       the vsXXXX.option.* overrides
        for cfg in self.configs_and_platforms(srcfile):
            excluded = not cfg.should_build()
            extras = list(self.collect_extra_options_for_node(srcfile, tool, inherit=False))
            if additional_options:
                extras = additional_options + extras
            if extras or excluded:
                n_cfg = Node("FileConfiguration", Name="%s" % cfg.vs_name)
                if excluded:
                    n_cfg["ExcludedFromBuild"] = True
                n_tool = Node("Tool", Name=tool)
                for key, value in extras:
                    n_tool[key] = value
                n_cfg.add(n_tool)
                node.add(n_cfg)


    def _order_configs_and_archs(self, configs_iter, archs_list):
        configs_list = list(configs_iter)
        for a in archs_list:
            for c in configs_list:
                yield (c, a)


    def get_vs_warning_level(self, cfg):
        """
        Return numeric MSVS warning level corresponding to the warning option
        in the specified config.
        """
        WARNING_LEVELS = { "no": 0,
                           "minimal": 1,
                           "default": 3,
                           "all": 4,
                           "max": 4,
                         }
        return WARNING_LEVELS[cfg["warnings"].as_py()]


class VS2008Toolset(VS200xToolsetBase):
    """
    Visual Studio 2008.


    Special properties
    ------------------
    In addition to the properties described below, it's possible to specify any
    of the ``vcproj`` properties directly in a bakefile. To do so, you have to
    set specially named variables on the target.

    The variables are prefixed with ``vs2008.option.``, followed by tool name and
    attribute name. For example:

      - ``vs2008.option.VCCLCompilerTool.EnableFunctionLevelLinking``
      - ``vs2008.option.VCLinkerTool.EnableCOMDATFolding``

    Additionally, the following are supported for non-tool nodes:

      - ``vs2008.option.*`` (attributes of the root ``VisualStudioProject`` node)
      - ``vs2008.option.Configuration.*`` (``Configuration`` node attributes)

    These variables can be used in several places in bakefiles:

      - In targets, to applied them as project's global settings.
      - In modules, to apply them to all projects in the module and its submodules.
      - On per-file basis, to modify file-specific settings.

    Examples:

    .. code-block:: bkl

        vs2008.option.VCCLCompilerTool.EnableFunctionLevelLinking = false;

        crashrpt.cpp::vs2008.option.VCCLCompilerTool.ExceptionHandling = 2;
    """
    name = "vs2008"

    version = 9
    proj_versions = [9]
    Solution = VS2008Solution
    Project = VS2008Project
    has_parallel_compilation = True
    detect_64bit_problems = False

    def VCWebDeploymentTool(self, target, cfg):
        # This tool was removed in 2008
        return None



class VS2005Toolset(VS200xToolsetBase):
    """
    Visual Studio 2005.

    Special properties
    ------------------
    This toolset supports the same special properties that
    :ref:`ref_toolset_vs2008`. The only difference is that they are prefixed
    with ``vs2005.option.`` instead of ``vs2008.option.``.
    """
    name = "vs2005"

    version = 8
    proj_versions = [8]
    Solution = VS2005Solution
    Project = VS2005Project
    has_parallel_compilation = False
    detect_64bit_problems = True



class VS2003ExprFormatter(VS200xExprFormatter):
    def bool_value(self, e):
        return "TRUE" if e.value else "FALSE"

class VS2003XmlFormatter(VS200xXmlFormatter):
    ExprFormatter = VS2003ExprFormatter

    # Override to get rid of the new lines which are not present in VS 2003
    def format_end_tag_with_attrs(self, indent):
        return ">"

    def format_end_empty_tag(self, indent):
        return "/>"

class VS2003Toolset(VS200xToolsetBase):
    """
    Visual Studio 2003.

    Special properties
    ------------------
    This toolset supports the same special properties that
    :ref:`ref_toolset_vs2008`. The only difference is that they are prefixed
    with ``vs2003.option.`` instead of ``vs2008.option.``.
    """
    name = "vs2003"

    version = 7.1
    proj_versions = [7.1]
    Solution = VS2003Solution
    Project = VS2003Project
    XmlFormatter = VS2003XmlFormatter
    has_parallel_compilation = False
    detect_64bit_problems = True

    tool_functions = [
        "VCCLCompilerTool",
        "VCCustomBuildTool",
        "VCLibrarianTool",
        "VCLinkerTool",
        "VCMIDLTool",
        "VCPostBuildEventTool",
        "VCPreBuildEventTool",
        "VCPreLinkEventTool",
        "VCResourceCompilerTool",
        "VCWebServiceProxyGeneratorTool",
        "VCXMLDataGeneratorTool",
        "VCWebDeploymentTool",
        "VCManagedWrapperGeneratorTool",
        "VCAuxiliaryManagedWrapperGeneratorTool",
        ]

    def _add_ToolFiles(self, root):
        pass
