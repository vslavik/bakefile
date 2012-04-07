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
Toolsets for Visual Studio 2003, 2005 and 2008.
"""

from bkl.plugins.vsbase import *
from bkl.expr import concat

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
pchGenerateAuto         = 2
pchUseUsingSpecificic   = 3

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


class VS200xXmlFormatter(XmlFormatter):
    """
    XmlFormatter for VS 200x output.
    """

    indent_step = "\t"

    def __init__(self, paths_info):
        super(VS200xXmlFormatter, self).__init__(paths_info, charset=VCPROJ_CHARSET)

    # these are always written as <foo>\n<foo>, not <foo/>
    elems_not_collapsed = set(["References",
                               "Globals",
                               "File",
                               "Filter",
                               "ToolFiles"])

    def format_node(self, name, attrs, text, children_markup, indent):
        """
        Formats given Node instance, indented with *indent* text.
        Content is either *text* or *children_markup*; the other is None.
        """
        s = "%s<%s" % (indent, name)
        if attrs:
            for key, value in attrs:
                s += "\n%s\t%s=%s" % (indent, key, value)
        if text:
            s += ">%s</%s>\n" % (text, name)
        elif children_markup:
            if attrs:
                s += "\n%s\t" % indent
            s += ">\n%s%s</%s>\n" % (children_markup, indent, name)
        else:
            if name in self.elems_not_collapsed:
                if attrs:
                    s += "\n%s\t" % indent
                s += ">\n%s</%s>\n" % (indent, name)
            else:
                s += "\n%s/>\n" % indent
        return s


# TODO: Put more content into these classes, use them properly
class VS200xProject(VSProjectBase):
    def __init__(self, name, guid, projectfile, deps):
        self.name = name
        self.guid = guid
        self.projectfile = projectfile
        self.dependencies = deps

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

    #: Extension of format files
    proj_extension = "vcproj"

    def gen_for_target(self, target):
        projectfile = target["%s.projectfile" % self.name]
        filename = projectfile.as_native_path_for_output(target)

        paths_info = bkl.expr.PathAnchorsInfo(
                                    dirsep="\\",
                                    outfile=filename,
                                    builddir=self.get_builddir_for(target).as_native_path_for_output(target),
                                    model=target)

        guid = target["%s.guid" % self.name]
        configs = ["Debug", "Release"]

        root = Node("VisualStudioProject")
        root["ProjectType"] = "Visual C++"
        root["Version"] = "%.2f" % self.version
        root["Name"] =  target.name
        root["ProjectGUID"] = guid
        root["RootNamespace"] = target.name
        root["Keyword"] = "Win32Proj"
        root["TargetFrameworkVersion"] = 196613
        self._add_extra_options_to_node(target, root)

        n_platforms = Node("Platforms")
        n_platforms.add("Platform", Name="Win32")
        root.add(n_platforms)

        root.add(Node("ToolFiles"))

        n_configs = Node("Configurations")
        root.add(n_configs)
        for c in configs:
            n = Node("Configuration", Name="%s|Win32" % c)
            n_configs.add(n)
            # TODO: handle the defaults in a nicer way
            if target["outputdir"].as_native_path(paths_info) != paths_info.builddir_abs:
                n["OutputDirectory"] = target["outputdir"]
            else:
                n["OutputDirectory"] = "$(SolutionDir)$(ConfigurationName)"
            n["IntermediateDirectory"] = "$(ConfigurationName)"
            if is_exe(target):
                n["ConfigurationType"] = typeApplication
            elif is_library(target):
                n["ConfigurationType"] = typeStaticLibrary
            elif is_dll(target):
                n["ConfigurationType"] = typeDynamicLibrary
            else:
                return None
            if target["win32-unicode"]:
                n["CharacterSet"] = 1
            self._add_extra_options_to_node(target, n)

            for tool in self.tool_functions:
                if hasattr(self, tool):
                    f_tool = getattr(self, tool)
                    n_tool = f_tool(target, c)
                else:
                    n_tool = Node("Tool", Name=tool)
                if n_tool:
                    self._add_extra_options_to_node(target, n_tool)
                    n.add(n_tool)

        root.add(Node("References"))

        root.add(self.build_files_list(target, c))

        root.add(Node("Globals"))

        f = OutputFile(filename, EOL_WINDOWS, charset=VCPROJ_CHARSET,
                       creator=self, create_for=target)
        f.write(VS200xXmlFormatter(paths_info).format(root))
        f.commit()

        target_deps = target["deps"].as_py()
        return self.Project(target.name, guid, projectfile, target_deps)


    def VCPreBuildEventTool(self, target, cfg):
        n = Node("Tool", Name="VCPreBuildEventTool")
        n["CommandLine"] = VSList("\r\n", target["pre-build-commands"])
        return n

    def VCPostBuildEventTool(self, target, cfg):
        n = Node("Tool", Name="VCPostBuildEventTool")
        n["CommandLine"] = VSList("\r\n", target["post-build-commands"])
        return n

    def VCAppVerifierTool(self, target, cfg):
        return Node("Tool", Name="VCAppVerifierTool") if is_exe(target) else None


    def VCCLCompilerTool(self, target, cfg):
        n = Node("Tool", Name="VCCLCompilerTool")

        # Currently we don't make any distinction between preprocessor, C
        # and C++ flags as they're basically all the same at MSVS level
        # too and all go into the same place in the IDE and same
        # AdditionalOptions node in the project file.
        all_cflags = VSList(" ", target["compiler-options"],
                                 target["c-compiler-options"],
                                 target["cxx-compiler-options"])
        all_cflags.append("/MP") # parallel compilation
        n["AdditionalOptions"] = all_cflags
        n["Optimization"] = optimizeMaxSpeed if cfg == "Release" else optimizeDisabled
        if cfg == "Release":
            n["EnableIntrinsicFunctions"] = True
        n["AdditionalIncludeDirectories"] = target["includedirs"]
        n["PreprocessorDefinitions"] = list(target["defines"]) + self.get_std_defines(target, cfg)

        if target["win32-crt-linkage"] == "dll":
            n["RuntimeLibrary"] = rtMultiThreadedDebugDLL if cfg == "Debug" else rtMultiThreadedDLL
        else:
            n["RuntimeLibrary"] = rtMultiThreadedDebug if cfg == "Debug" else rtMultiThreaded

        if cfg == "Release":
            n["EnableFunctionLevelLinking"] = True
        n["UsePrecompiledHeader"] = pchNone
        n["WarningLevel"] = 3
        n["DebugInformationFormat"] = debugEditAndContinue if cfg == "Debug" else debugEnabled

        return n


    def VCLinkerTool(self, target, cfg):
        if is_library(target):
            return None
        n = Node("Tool", Name="VCLinkerTool")
        n["AdditionalOptions"] = VSList(" ", target["link-options"])
        libs = target["libs"]
        if libs:
            n["AdditionalDependencies"] = VSList(" ", ("%s.lib" % x.as_py() for x in libs))

        targetname = target[target.type.basename_prop]
        if targetname != target.name:
            n["OutputFile"] = concat("$(OutDir)\\", targetname, ".", target.type.target_file(self, target).get_extension())

        if cfg == "Debug":
            n["LinkIncremental"] = linkIncrementalYes
        else:
            n["LinkIncremental"] = linkIncrementalNo
        # VS: creates debug info for release too; TODO: make this configurable
        n["GenerateDebugInformation"] = True
        if is_exe(target) and target["win32-subsystem"] == "console":
            n["SubSystem"] = subSystemConsole
        else:
            n["SubSystem"] = subSystemWindows
        if cfg == "Release":
            n["OptimizeReferences"] = optReferences
            n["EnableCOMDATFolding"] = optFolding
        n["TargetMachine"] = machineX86
        return n


    def VCLibrarianTool(self, target, cfg):
        if not is_library(target):
            return None
        n = Node("Tool", Name="VCLibrarianTool")
        targetname = target[target.type.basename_prop]
        if targetname != target.name:
            n["OutputFile"] = concat("$(OutDir)\\", targetname, ".", target.type.target_file(self, target).get_extension())
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
        "VCPostBuildEventTool",
        ]


    def build_files_list(self, target, cfg):
        files = Node("Files")
        # TODO: use groups definition, filter into groups, add Resource Files

        sources = Node("Filter", Name="Source Files")
        sources["Filter"] = "cpp;c;cc;cxx;def;odl;idl;hpj;bat;asm;asmx"
        sources["UniqueIdentifier"] = "{4FC737F1-C7A5-4376-A066-2A32D752A2FF}"
        for sfile in target.sources:
            # TODO: implement custom builds for unsupported file types
            sources.add("File", RelativePath=sfile.filename)
        files.add(sources)

        headers = Node("Filter", Name="Header Files")
        headers["Filter"] = "h;hpp;hxx;hm;inl;inc;xsd"
        headers["UniqueIdentifier"] = "{93995380-89BD-4b04-88EB-625FBE52EBFB}"
        for sfile in target.headers:
            headers.add("File", RelativePath=sfile.filename)
        files.add(headers)

        resources = Node("Filter", Name="Resource Files")
        resources["Filter"] = "rc;ico;cur;bmp;dlg;rc2;rct;bin;rgs;gif;jpg;jpeg;jpe;resx;tiff;tif;png;wav"
        resources["UniqueIdentifier"] = "{67DA6AB6-F800-4c08-8B7A-83BB121AAD01}"
        files.add(resources)
        return files

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

    Additionally, the following are support for non-tool nodes:
    The following nodes are supported:

      - ``vs2008.option.*`` (attributes of the root ``VisualStudioProject`` node)
      - ``vs2008.option.Configuration.*`` (``Configuration`` node attributes)

    Examples:

    .. code-block:: bkl

        vs2008.option.VCCLCompilerTool.EnableFunctionLevelLinking = false;
    """
    name = "vs2008"

    version = 9
    proj_versions = [9]
    Solution = VS2008Solution
    Project = VS2008Project
