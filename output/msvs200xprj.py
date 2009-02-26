#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2006-2008 Vaclav Slavik, Kevin Powell, Steven Van Ingelgem,
#                          Kevin Ollivier, Aleksander Jaromin
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
#  $Id$
#
#  MS Visual Studio 2003/2005 project files generator script
#

import os, os.path
import errors, utils
from xml.dom.minidom import *

import msvc_common
from msvc_common import *

# ------------------------------------------------------------------------
#   misc .vcproj constants:
# ------------------------------------------------------------------------

# compiler options

rtMultiThreaded         = '0'
rtMultiThreadedDebug    = '1'
rtMultiThreadedDLL      = '2'
rtMultiThreadedDebugDLL = '3'
rtSingleThreaded        = '4'
rtSingleThreadedDebug   = '5'

debugDisabled           = '0'
debugOldStyleInfo       = '1'
debugLineInfoOnly       = '2'
debugEnabled            = '3'
debugEditAndContinue    = '4'

runtimeBasicCheckNone       = '0'
runtimeCheckStackFrame      = '1'
runtimeCheckUninitVariables = '2'
runtimeBasicCheckAll        = '3'

optimizeDisabled        = '0'
optimizeMinSpace        = '1'
optimizeMaxSpeed        = '2'
optimizeFull            = '3'
optimizeCustom          = '4'

pchNone                 = '0'
pchCreateUsingSpecific  = '1'

# linker options

linkIncrementalDefault  = '0'
linkIncrementalNo       = '1'
linkIncrementalYes      = '2'

optReferencesDefault    = '0'
optNoReferences         = '1'
optReferences           = '2'

# ------------------------------------------------------------------------
#   extended minidom classes to create XML file with specified attributes
#   order (VC2003 projet file must have attribute "Name" as first)
# ------------------------------------------------------------------------

class ElementSorted(Element):
    def __init__(self, tagName, namespaceURI=EMPTY_NAMESPACE,
                 prefix=None, localName=None):
        Element.__init__(self, tagName, namespaceURI, prefix, localName)
        self.order = []

    def setAttribute(self, attname, value):
        self.order.append(attname)
        Element.setAttribute(self, attname, value)

    def writexml(self, writer, indent="", addindent="", newl=""):
        # This specialization does two things differently:
        # 1) order of attributes is preserved
        # 2) attributes are placed each on its own line and indented
        #    so that the output looks more like MSVC's native files
        writer.write("%s<%s" % (indent, self.tagName))

        attrs = self._get_attributes()

        for attr in self.order:
            writer.write("\n%s%s%s=\"%s\"" % (
                         indent,
                         addindent,
                         attr,
                         attrs[attr].value.replace('&', '&amp;').
                                           replace('<', '&lt;').
                                           replace('>', '&gt;').
                                           replace('"', '&quot;')))

        if self.childNodes:
            if len(self.order) == 0:
                writer.write(">%s" % newl)
            else:
                if _MSVS_VCPROJ_VERSION == "7.10":
                    writer.write(">%s" % newl)
                else:
                    writer.write("%s%s%s>%s" % (newl, indent, addindent, newl))
            for node in self.childNodes:
                node.writexml(writer, indent + addindent, addindent, newl)
            writer.write("%s</%s>%s" % (indent, self.tagName, newl))
        else:
            # <File> is serialized differently, see the discussion in
            # http://www.bakefile.org/ticket/210
            if self.tagName == "File":
                if _MSVS_VCPROJ_VERSION == "7.10":
                    writer.write(">%s%s</%s>%s" % (newl, indent, self.tagName, newl))
                else:
                    writer.write("%s%s%s>%s%s</%s>%s" % (newl, indent, addindent, newl, indent, self.tagName, newl))
            else:
                if _MSVS_VCPROJ_VERSION == "7.10":
                    writer.write("/>%s" % newl)
                else:
                    writer.write("%s%s/>%s" % (newl, indent, newl))


class DocumentSorted(Document):
    def createElement(self, tagName):
        e = ElementSorted(tagName)
        e.ownerDocument = self
        return e

# ------------------------------------------------------------------------
#   helpers
# ------------------------------------------------------------------------

# this GUID is used by all solutions in the Project() entry:
GUID_SOLUTION = "{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}"

# UUID for Bakefile namespace when generating GUIDs
NAMESPACE_BAKEFILE_PROJ = "{b0c737d9-df87-4499-b156-418baa078a12}"
NAMESPACE_BAKEFILE_FILTERS = "{0e8f53b3-f09d-40b1-b248-66f80b72e654}"

def mk_uuid(namespace, seed):
    # NB: we want to have the GUID strings be repeatable, so generate them
    #     from a repeatable seed
    from uuid import uuid5, UUID

    guid = uuid5(UUID(namespace), seed)
    return '{%s}' % str(guid).upper() # MSVS uses upper-case strings for GUIDs

def mk_proj_uuid(basename, proj_id):
    return mk_uuid(NAMESPACE_BAKEFILE_PROJ, '%s/%s' % (basename, proj_id))

def mk_filter_uuid(name, wildcards):
    return mk_uuid(NAMESPACE_BAKEFILE_FILTERS, '%s:%s' % (name, wildcards))

class MsvsFilesGroup(FilesGroup):
    def __init__(self, name, files=None, extensions=None, uuid=None):
        assert files != None or extensions != None
        if files == None:
            files = ' '.join(['*.%s' % x for x in extensions.split(';')])
        if uuid == None:
            uuid = mk_filter_uuid(name, files)

        FilesGroup.__init__(self, name, files)
        self.uuid = uuid
        self.extensions = extensions

DEFAULT_FILE_GROUPS = [
    MsvsFilesGroup('Source Files',
                   extensions='cpp;c;cc;cxx;def;odl;idl;hpj;bat;asm;asmx',
                   uuid='{4FC737F1-C7A5-4376-A066-2A32D752A2FF}'),
    MsvsFilesGroup('Header Files',
                   extensions='h;hpp;hxx;hm;inl;inc;xsd',
                   uuid='{93995380-89BD-4b04-88EB-625FBE52EBFB}'),
    MsvsFilesGroup('Resource Files',
                   extensions='rc;ico;cur;bmp;dlg;rc2;rct;bin;rgs;gif;jpg;jpeg;jpe;resx;tiff;tif;png;wav',
                   uuid='{67DA6AB6-F800-4c08-8B7A-83BB121AAD01}')
]

def mk_list(list):
    # remove empty items from the list:
    return ";".join([x for x in list.split(";") if len(x) > 0])

def bool2vcstr(value):
    """Returns "true"/"false" or "TRUE"/"FALSE" string depending on format
       version."""
    if value:
        s = 'true'
    else:
        s = 'false'
    if _MSVS_VCPROJ_VERSION == "7.10":
        return s.upper()
    else:
        return s

# ------------------------------------------------------------------------
#                              Generator class
# ------------------------------------------------------------------------

class ProjectGeneratorMsvc9:

    app_type_code = { 'console' : '1', 'gui' : '2' }

    def __init__(self):
        self.basename, ext = os.path.splitext(os.path.basename(FILE))
        self.dirname = os.path.dirname(FILE)
        if ext.lower() == '.vcproj':
            self.onlyProject = True
        else:
            if ext.lower() != '.sln' and ext != '':
                print 'warning: ignoring extension "%s"' % ext[1:] # drop dot
            self.onlyProject = False

    # --------------------------------------------------------------------
    #   basic configuration
    # --------------------------------------------------------------------

    def getSolutionExtension(self):
        return 'sln'
    def getProjectExtension(self):
        return 'vcproj'

    # --------------------------------------------------------------------
    #   helpers
    # --------------------------------------------------------------------

    def splitConfigName(self, config):
        idx = config.index('|')
        platform = config[:idx]
        name = config[idx+2:]
        if name == '':
            name = 'Default'
        return (platform, name)

    def mkConfigName(self, config):
        # config name always contains the platform followed by "| " at the
        # beginning of the string, so extract it and transform into
        # "ConfigName|Platform":
        platform, name = self.splitConfigName(config)
        return '%s|%s' % (name, platform)

    def sortConfigsForSLN(self, configs):
        # .sln files have configs grouped, all platforms for one config
        # are together, but our "natural" sort order is different:
        sortedConfigs = []
        todo = [c for c in sortedKeys(configs)]
        while len(todo) > 0:
            c = todo.pop(0)
            if c in sortedConfigs:
                continue
            plat, nm = self.splitConfigName(c)
            sortedConfigs.append(c)
            for c2 in todo:
                if c2 in sortedConfigs:
                    continue
                plat2, nm2 = self.splitConfigName(c2)
                if nm == nm2:
                    sortedConfigs.append(c2)
        return sortedConfigs

    def isEmbeddedConfig(self, config):
        """Returns true if given config targets embedded device."""
        cfg = configs[config][0]['MSVS_PLATFORM']
        return cfg == 'pocketpc2003'


    def assignGUIDs(self, sln_targets):
        """Returns the dictionary containing GUIDs indexed by target ids."""
        guid_dict = {}
        for t in sln_targets:
            if '_msvc_guid' in t.__dict__:
                guid_dict[t.id] = '{%s}' % t._msvc_guid.upper()
            else:
                guid_dict[t.id] = mk_proj_uuid(self.basename, t.id)
        return guid_dict

    def createVCProjList(self, sln_targets, guid_dict, vcproj_list, deps_translation):
        """Fills the project list and also returns the SLN projects sections as
           a side effect."""
        sln = ''
        single_target = (len(sln_targets) == 1)
        for t in sln_targets:
            deps = ''
            if single_target:
                vcproj_name = self.basename
            else:
                vcproj_name = '%s_%s' % (self.basename, t.id)
            deplist = t._deps.split()

            # add external project dependencies:
            for d in t._dsp_deps.split():
                deplist.append(d.split(':')[0])

            # create the dependencies section, if any:
            deps_str = ""
            if len(deplist) != 0:
                deps_str = "\tProjectSection(ProjectDependencies) = postProject\n"

                for d in deplist:
                    if d in deps_translation:
                        d2 = deps_translation[d]
                    else:
                        d2 = d
                    guid = guid_dict[d2]
                    deps_str += "\t\t%s = %s\n" % (guid, guid)
                deps_str += "\tEndProjectSection\n"

            guid = guid_dict[t.id]

            # create the project section:
            sln += 'Project("%s") = "%s", "%s", "%s"\n' % (
                        GUID_SOLUTION,
                        t.id,
                        vcproj_name + '.' + self.getProjectExtension(),
                        guid
                    )
            sln += deps_str
            sln += 'EndProject\n'

            vcproj_file = (t,
                       os.path.join(self.dirname,
                                    vcproj_name + '.' + self.getProjectExtension()),
                       vcproj_name, guid)

            if vcproj_file not in vcproj_list:
                vcproj_list.append(vcproj_file)

        return sln


    # --------------------------------------------------------------------
    #   Solution file (.sln)
    # --------------------------------------------------------------------

    def makeSlnHeader(self):
        if _MSVS_SLN_VERSION == "8.00":
            return """\
Microsoft Visual Studio Solution File, Format Version 8.00
"""
        elif _MSVS_SLN_VERSION == "9.00":
            return """\
Microsoft Visual Studio Solution File, Format Version 9.00
# Visual Studio 2005
"""
        elif _MSVS_SLN_VERSION == "10.00":
            return """\
Microsoft Visual Studio Solution File, Format Version 10.00
# Visual Studio 2008
"""
        else:
            import errors
            raise errors.Error("unexpected MSVS format version")

    def genSln(self, sln_targets, guid_dict, vcproj_list, deps_translation):
        if len(sln_targets) == 0:
            return

        sln = self.makeSlnHeader()

        sln += self.createVCProjList(sln_targets, guid_dict, vcproj_list, deps_translation)

        sortedConfigs = self.sortConfigsForSLN(configs)

        # generate configurations listing:
        sln += "Global\n"
        sln += "\tGlobalSection(SolutionConfigurationPlatforms) = preSolution\n"
        for c in sortedConfigs:
            cfg = self.mkConfigName(c)
            sln += "\t\t%s = %s\n" % (cfg,cfg)
        sln += "\tEndGlobalSection\n"

        # ...and configurations binding to vcproj configurations:
        sln += "\tGlobalSection(ProjectConfigurationPlatforms) = postSolution\n"

        for t in sln_targets:
            guid = guid_dict[t.id]
            for c in sortedConfigs:
                cfg = self.mkConfigName(c)
                txt = "\t\t%(guid)s.%(cfg)s.%%s = %(cfg)s\n" % {'guid':guid, 'cfg':cfg}
                sln += txt % 'ActiveCfg'
                if c in t.configs:
                    sln += txt % 'Build.0'
                    if self.isEmbeddedConfig(c):
                        sln += txt % 'Deploy.0'


        sln += "\tEndGlobalSection\n"
        sln += "\tGlobalSection(SolutionProperties) = preSolution\n"
        sln += "\t\tHideSolutionNode = FALSE\n"
        sln += "\tEndGlobalSection\n"
        sln += "EndGlobal\n"

        writer.writeFile('%s.%s' % (
            os.path.join(self.dirname, self.basename),
            self.getSolutionExtension()
            ), sln)


    def genWorkspaces(self):
        vcproj_list = []

        # find all projects. Beware ugly hack here: MSVC6PRJ_MERGED_TARGETS is
        # used to create fake targets as a merge of two (mutually exclusive)
        # targets. This is sometimes useful, e.g. when you want to build both
        # DLL and static lib of something.
        deps_translation = {}
        projects = [t for t in targets if t._kind == 'project']
        for mergeInfo in MSVC6PRJ_MERGED_TARGETS.split():
            split1 = mergeInfo.split('=')
            split2 = split1[1].split('+')
            tgR = split1[0]
            tg1 = split2[0]
            tg2 = split2[1]

            # the targets may be disabled by some (weak) condition:
            if tg1 not in targets and tg2 not in targets:
                continue

            t = targets[tg1]
            for c in targets[tg2].configs:
                assert c not in t.configs # otherwise not mutually exclusive
                t.configs[c] = targets[tg2].configs[c]
            t.id = tgR
            projects.remove(targets[tg2])
            targets.append(tgR, t)
            del targets[tg1]
            del targets[tg2]
            deps_translation[tg1] = tgR
            deps_translation[tg2] = tgR

        guid_dict = self.assignGUIDs(projects)
        if self.onlyProject:
            self.createVCProjList(projects, guid_dict, vcproj_list, deps_translation)
            if len(vcproj_list) != 1:
                raise errors.Error("Single project name specified for multiple targets.")
        else:
            self.genSln(projects, guid_dict, vcproj_list, deps_translation)
        for t, filename, prjname, guid in vcproj_list:
            self.genVCProj(t, filename, prjname, guid)

        # warn about <action> targets that we can't handle (yet):
        for t in [t for t in targets if t._kind == 'action']:
            print "warning: ignoring action target '%s'" % t.id


    # ------------------------------------------------------------------------
    #   Project files (.vcproj)
    # ------------------------------------------------------------------------

    # some helpers to build parts of the project file that change if you are
    # doing PC vs WinCE
    def buildConfElement(self, doc, cfg, c, t):
        conf_name = self.mkConfigName(c)
        conf_el = doc.createElement("Configuration")
        conf_el.setAttribute("Name", conf_name)
        conf_el.setAttribute("OutputDirectory", "%s" % cfg._targetdir[:-1])
        conf_el.setAttribute("IntermediateDirectory", "%s\\%s" % (cfg._builddir, t.id) )
        conf_el.setAttribute("ConfigurationType", "%s" % cfg._type_code)
        conf_el.setAttribute("UseOfMFC", "0")
        conf_el.setAttribute("ATLMinimizesCRunTimeLibraryUsage", bool2vcstr(False))

        # allow specifying CharacterSet value, it's not really clear what is
        # the difference between specifying it as 0 (not specified), 2 (MBCS)
        # or not using it at all, let the user decide
        if globals().has_key('MSVS_CHARACTER_SET'):
            conf_el.setAttribute("CharacterSet", MSVS_CHARACTER_SET)
        # VC++ 2008 needs CharacterSet set, definining _UNICODE is not enough,
        # see http://comments.gmane.org/gmane.comp.sysutils.bakefile.devel/1145
        elif "_UNICODE" in cfg._defines.split(";"):
            conf_el.setAttribute("CharacterSet", "1")

        return conf_el


    def buildBscMakeToolElement(self, tool, prjname, cfg, c, t):
        tool.setAttribute("OutputFile", "%s%s.bsc" % (cfg._targetdir, prjname))
        tool.setAttribute("SuppressStartupBanner", bool2vcstr(True))


    def buildCompilerToolElement(self, tool, prjname, cfg, c, t):
        # the order of attributes here is the same as used in the projects
        # created by MSVS itself

        if _MSVS_VCPROJ_VERSION not in ["7.10", "8.00"]:
            extra_cppflags = "/MP" # parallel compilation
            if cfg._cppflags:
                extra_cppflags = "%s %s" % (extra_cppflags, cfg._cppflags)
        else:
            extra_cppflags = cfg._cppflags
        if extra_cppflags:
            tool.setAttribute("AdditionalOptions", extra_cppflags)

        tool.setAttribute("Optimization", cfg._optimize)
        tool.setAttribute("AdditionalIncludeDirectories", mk_list(cfg._include_paths))
        tool.setAttribute("PreprocessorDefinitions", mk_list(cfg._defines))

        if cfg._optimize == "0" and cfg._debug == '1':
            # VC2008 projects use /MP switch, which is incompatible with
            # MinimalRebuild; /MP is more useful, so omit MinimalRebuild:
            if _MSVS_VCPROJ_VERSION in ["7.10", "8.00"]:
                tool.setAttribute("MinimalRebuild", bool2vcstr(True))

        # this property type has changed from int to bool since VC7
        eh = cfg._cxx_exceptions == 'on'
        if _MSVS_VCPROJ_VERSION == "7.10":
            eh = bool2vcstr(eh)     # True/False -> 'TRUE'/'FALSE'
        else:
            eh = str(int(eh))       # True/False -> '1'/'0'
        tool.setAttribute("ExceptionHandling", eh)

        if cfg._rtl_dbg == 'on':
            tool.setAttribute("BasicRuntimeChecks", runtimeBasicCheckAll)

        # choose runtime library
        if cfg._rtl_threading == 'multi':
            if cfg._rtl_dbg == 'on':
                if cfg._rtl_type == 'static':
                    rtl = rtMultiThreadedDebug
                else:
                    rtl = rtMultiThreadedDebugDLL
            else: # debug off
                if cfg._rtl_type == 'static':
                    rtl = rtMultiThreaded
                else:
                    rtl = rtMultiThreadedDLL
        else: # single-threaded
            if cfg._rtl_type == 'dynamic':
                print "warning: single-threaded dynamic runtime doesn't exist, using static"
            if cfg._rtl_dbg == 'on':
                rtl = rtSingleThreadedDebug
            else:
                rtl = rtSingleThreaded
        tool.setAttribute("RuntimeLibrary", rtl)

        if cfg._optimize == "0":
            tool.setAttribute("BufferSecurityCheck",bool2vcstr(True))

        if cfg._cxx_rtti == 'on':
            tool.setAttribute("RuntimeTypeInfo", bool2vcstr(True))
        else:
            tool.setAttribute("RuntimeTypeInfo", bool2vcstr(False))

        # the values of this enum changed in VC8 where pchGenerateAuto simply
        # disappeared (and so the value of subsequent element shifted), so
        # define separate constants for VC7 ...
        if _MSVS_VCPROJ_VERSION == "7.10":
            pchGenerateAuto     = '2'
            pchUseUsingSpecific = '3'
        else:
        # ... and for the later versions
            pchUseUsingSpecific = '2'

        if cfg._pch_use_pch == '1':
            do_use_pch = True
            if cfg._pch_generator:
                tool.setAttribute("UsePrecompiledHeader", pchUseUsingSpecific)
            else:
                if _MSVS_VCPROJ_VERSION == "7.10":
                    tool.setAttribute("UsePrecompiledHeader", pchGenerateAuto)
                else:
                    # automatic PCH support (/YX option) was removed in VC8, so
                    # disable the use of PCH completely when this option is
                    # specified (what else can we do?)
                    do_use_pch = False

            if do_use_pch:
                tool.setAttribute("PrecompiledHeaderThrough", cfg._pch_header)
                tool.setAttribute("PrecompiledHeaderFile", cfg._pch_file)


        tool.setAttribute("AssemblerListingLocation", "%s\\%s\\" % (cfg._builddir, t.id) )
        tool.setAttribute("ObjectFile", "%s\\%s\\" % (cfg._builddir, t.id) )
        tool.setAttribute("ProgramDataBaseFileName", cfg._pdbfile)

        warnings_map = { 'no':'0', 'default':'3', 'max':'4'}
        if warnings_map.has_key(cfg._warnings):
            tool.setAttribute("WarningLevel", warnings_map[cfg._warnings])
        else:
            tool.setAttribute("WarningLevel", warnings_map['default'])

        tool.setAttribute("SuppressStartupBanner", bool2vcstr(True))

        # Detect64BitPortabilityProblems is deprecated in VS2008 and will
        # be removed in the future:
        if _MSVS_VCPROJ_VERSION in ["7.10", "8.00"]:
            tool.setAttribute("Detect64BitPortabilityProblems", bool2vcstr(True))

        if cfg._debug == '1':
            if cfg._debug_edit_and_continue == '1':
                tool.setAttribute("DebugInformationFormat", debugEditAndContinue)
            else:
                tool.setAttribute("DebugInformationFormat", debugEnabled)
        else:
            tool.setAttribute("DebugInformationFormat", debugDisabled)


    def buildLinkerToolElement(self, tool, prjname, cfg, c, t):
        ldlibs = cfg._ldlibs
        if cfg._cxx_rtti == 'on' and self.isEmbeddedConfig(c):
            ldlibs += ' ccrtrtti.lib'

        tool.setAttribute("AdditionalOptions", cfg._ldflags)
        tool.setAttribute("AdditionalDependencies", ldlibs)
        tool.setAttribute("OutputFile", "%s%s" % (cfg._targetdir, cfg._targetname))

        if cfg._debug == '1':
            tool.setAttribute("LinkIncremental", linkIncrementalYes)
        else:
            tool.setAttribute("LinkIncremental", linkIncrementalNo)

        if cfg._type_nick == 'dll':
            if cfg._importlib != "":
                implib = cfg._importlib
                tool.setAttribute("ImportLibrary",
                                 "%s%s" % (cfg._targetdir, implib))

        tool.setAttribute("SuppressStartupBanner", bool2vcstr(True))
        tool.setAttribute("AdditionalLibraryDirectories", mk_list(cfg._lib_paths))
        if _MSVS_VCPROJ_VERSION != "7.10":
            tool.setAttribute("GenerateManifest", bool2vcstr(True))

        if cfg._debug == '1':
            tool.setAttribute("GenerateDebugInformation", bool2vcstr(True))

        tool.setAttribute("ProgramDatabaseFile", cfg._pdbfile)

        if cfg._type_nick != 'dll':
            tool.setAttribute("SubSystem",
                             "%s" % self.app_type_code[cfg._type_nick])

        if self.isEmbeddedConfig(c):
            tool.setAttribute("TargetMachine", "3")
            tool.setAttribute("DelayLoadDLLs", "$(NOINHERIT)")
            if cfg._debug == '0':
                tool.setAttribute("OptimizeReferences", optReferences)
                tool.setAttribute("EnableCOMDATFolding", "2")
        else:
            tool.setAttribute("TargetMachine", "1")


    def buildLibrarianToolElement(self, tool, prjname, cfg, c, t):
        tool.setAttribute("OutputFile","%s%s" % (cfg._targetdir, cfg._targetname) )
        tool.setAttribute("SuppressStartupBanner", bool2vcstr(True))


    def buildResourceCompilerToolElement(self, tool, prjname, cfg, c, t):
        tool.setAttribute("PreprocessorDefinitions", mk_list(cfg._res_defines))
        tool.setAttribute("Culture", "1033")
        tool.setAttribute("AdditionalIncludeDirectories", mk_list(cfg._res_include_paths))


    def buildIdlToolElement(self, tool, prjname, cfg, c, t):
        tool.setAttribute("PreprocessorDefinitions", mk_list(cfg._defines))
        tool.setAttribute("AdditionalIncludeDirectories", mk_list(cfg._include_paths))


    def buildPlatformsElement(self, doc):
        #Platforms Node
        plats_el = doc.createElement("Platforms")
        for p in MSVS_PLATFORMS_DESC.split(','):
            plat_el = doc.createElement("Platform")
            plat_el.setAttribute("Name", p)
            plats_el.appendChild(plat_el)
        return plats_el

    def buildToolFilesElement(self, doc):
        #ToolFiles Node
        tf_el = doc.createElement("ToolFiles")
        tf_el.appendChild(doc.createTextNode(""))
        return tf_el

    def buildAllConfigurations(self, doc, prjname, t):
        #Configurations Node
        confs_el = doc.createElement("Configurations")
        for c in sortedKeys(t.configs):
            cfg = t.configs[c]
            confs_el.appendChild(self.buildSingleConfiguration(doc, prjname, cfg, c, t))
        return confs_el

    def buildSingleConfiguration(self, doc, prjname, cfg, c, t):
        conf_el = self.buildConfElement(doc, cfg, c, t)

        # this dict is indexed by the names of the tools which need special
        # treatment, i.e. should be non-empty in the generated file: the value
        # of the corresponding dict element is our method which is called with
        # tool itself as well as prjname, cfg, c and t as parameters and should
        # fill in the tool with contents
        #
        # NB: order here doesn't matter so we sort tools alphabetically, the
        #     order in the file is determined by the tools list below
        toolHandlers = {
                         'VCBscMakeTool'    : self.buildBscMakeToolElement,
                         'VCCLCompilerTool' : self.buildCompilerToolElement,
                         'VCIDLTool'        : self.buildIdlToolElement, 
                         'VCMIDLTool'       : self.buildIdlToolElement, 
                         'VCLibrarianTool'  : self.buildLibrarianToolElement,
                         'VCLinkerTool'     : self.buildLinkerToolElement,
                         'VCResourceCompilerTool'
                                            : self.buildResourceCompilerToolElement,
                       }

        if cfg._type_nick == 'lib':
            linkTool = 'VCLibrarianTool'
        else:
            linkTool = 'VCLinkerTool'

        # this list contains the tools in the order appropriate for the current
        # project file version
        if _MSVS_VCPROJ_VERSION == "7.10":
            tools = [
                        'VCCLCompilerTool',
                        'VCCustomBuildTool',
                        linkTool,
                        'VCMIDLTool',
                        'VCPostBuildEventTool',
                        'VCPreBuildEventTool',
                        'VCPreLinkEventTool',
                        'VCResourceCompilerTool',
                        'VCWebServiceProxyGeneratorTool',
                        'VCXMLDataGeneratorTool',
                        'VCWebDeploymentTool',
                        'VCManagedWrapperGeneratorTool',
                        'VCAuxiliaryManagedWrapperGeneratorTool',
                    ]
        else:
            if _MSVS_VCPROJ_VERSION == "8.00":
                idlTool = "VCMIDLTool"
            else:
                idlTool = "VCIDLTool"
            tools = [
                        'VCPreBuildEventTool',
                        'VCCustomBuildTool',
                        'VCXMLDataGeneratorTool',
                        'VCWebServiceProxyGeneratorTool',
                        idlTool,
                        'VCCLCompilerTool',
                        'VCManagedResourceCompilerTool',
                        'VCResourceCompilerTool',
                        'VCPreLinkEventTool',
                        linkTool,
                        'VCALinkTool',
                        'VCManifestTool',
                        'VCXDCMakeTool',
                        'VCBscMakeTool',
                        'VCFxCopTool',
                        'VCAppVerifierTool',
                        'VCWebDeploymentTool',
                        'VCPostBuildEventTool',
                    ]

            if cfg._type_nick not in ['gui', 'console']:
                # these tools only make sense for the applications, not libraries
                tools.remove('VCAppVerifierTool')
                tools.remove('VCWebDeploymentTool')
            else:
                if _MSVS_VCPROJ_VERSION != "8.00":
                    # this tool was removed in VS 2008
                    tools.remove('VCWebDeploymentTool')

        # add all the tools
        for tool in tools:
            node = doc.createElement("Tool")
            node.setAttribute("Name", tool)
            if tool in toolHandlers:
                toolHandlers[tool](node, prjname, cfg, c, t)
            conf_el.appendChild(node)


        # additional tools
        if self.isEmbeddedConfig(c):
            self.buildEmbeddedTools(doc, conf_el)

        return conf_el

    def buildCustomBuildElement(self, doc, data):
        # parse MSVC6-style custom build element code (FIXME: this is for
        # compatibility, will be replaced with <action> handling in the
        # future):
        lines = data.split('\n')
        description = lines[0]
        assert lines[1].startswith('InputPath=')
        assert lines[2] == ''
        delim = lines[3].index(' : ')
        output = lines[3][:delim].strip(' "')
        deps = lines[3][delim+3:].strip()
        cmdline = lines[4].strip()

        # build the output:
        el = doc.createElement("Tool")
        el.setAttribute("Name", "VCCustomBuildTool")
        el.setAttribute('Description', description)
        el.setAttribute('CommandLine', cmdline)
        el.setAttribute('Outputs', output)
        if len(deps) > 0:
            # FIXME: remove this hack once custom build steps are
            #        implemented properly
            # these are VC6-specific things that VC7+ doesn't recognize
            if deps.startswith('"$(SOURCE)" '):
                deps = deps[len('"$(SOURCE)" '):]
            elif deps.startswith('$(SOURCE) '):
                deps = deps[len('$(SOURCE) '):]

            el.setAttribute('AdditionalDependencies', deps)
        return el


    def buildEmbeddedTools(self, doc, conf_el):
        deployment_tool_el = doc.createElement("DeploymentTool")
        deployment_tool_el.setAttribute("ForceDirty", "-1")
        deployment_tool_el.setAttribute("RemoteDirectory", "")
        deployment_tool_el.setAttribute("RegisterOutput", "0")
        deployment_tool_el.setAttribute("AdditionalFiles", "")
        conf_el.appendChild(deployment_tool_el)

        debugger_tool_el = doc.createElement("DebuggerTool")
        conf_el.appendChild(debugger_tool_el)

    def genVCProj(self, t, filename, prjname, guid):
        #start a new xml document
        doc = DocumentSorted()
        top_el = doc.createElement("VisualStudioProject")
        doc.appendChild(top_el)
        comment = doc.createComment("""

  This makefile was generated by
  Bakefile %s (http://www.bakefile.org)
  Do not modify, all changes will be overwritten!

""" % BAKEFILE_VERSION)
        doc.insertBefore(comment, top_el)

        #fill in the attributes of the top element
        top_el.setAttribute("ProjectType", "Visual C++")
        top_el.setAttribute("Version", _MSVS_VCPROJ_VERSION)
        top_el.setAttribute("Name", t.id)
        top_el.setAttribute("ProjectGUID", "%s" % guid)

        top_el.appendChild(self.buildPlatformsElement(doc))

        if _MSVS_VCPROJ_VERSION != "7.10":
            top_el.appendChild(self.buildToolFilesElement(doc))

        top_el.appendChild(self.buildAllConfigurations(doc, prjname, t))

        # MSVC insists on having these tags even though they are empty and
        # moreover, it wants to have "<References>\n</References>" and not
        # just "<References/>" so we need to add a dummy text element in the
        # middle to make it closer, although still not perfect because it
        # results in an extra one line which native project files don't have
        # (TODO: is there a way to avoid this extra blank line?)
        refs_el = doc.createElement("References")
        refs_el.appendChild(doc.createTextNode(""))
        top_el.appendChild(refs_el)

        files_el = doc.createElement("Files")

        #munge the source files around so we can write them to the file
        sources, groups, files, filesWithCustomBuild = \
            organizeFilesIntoGroups(t, DEFAULT_FILE_GROUPS, groupClass=MsvsFilesGroup)

        ##define a local helper function for building the files area
        def makeFileConfig(t, cfg, c, src, group, sources, pchExcluded):
            conf_name = self.mkConfigName(c)
            file_conf_el = doc.createElement("FileConfiguration")
            file_conf_el.setAttribute("Name", conf_name)

            if sources[src] != None and c not in sources[src]:
                file_conf_el.setAttribute("ExcludedFromBuild", bool2vcstr(True))
                tool_el = None
            elif (src in filesWithCustomBuild.keys() and
                c in filesWithCustomBuild[src].keys()):
                #custom build for this file for this config
                data = filesWithCustomBuild[src][c]
                if data != '':
                    tool_el = self.buildCustomBuildElement(doc, data)
                else:
                    tool_el = None
            elif (cfg._pch_use_pch and
                  (src == cfg._pch_generator or src in pchExcluded)):
                tool_el = doc.createElement("Tool")
                tool_el.setAttribute("Name", "VCCLCompilerTool")
                if src == cfg._pch_generator:
                    tool_el.setAttribute("UsePrecompiledHeader", pchCreateUsingSpecific)
                elif src in pchExcluded:
                    tool_el.setAttribute("UsePrecompiledHeader", pchNone)
            else:
                tool_el = None
                file_conf_el = None

            if tool_el != None:
                file_conf_el.appendChild(tool_el)
            return file_conf_el

        pchExcluded = t._pch_excluded.split()

        for group in [g for g in groups if g.name in files]:
            lst = files[group.name]
            sortByBasename(lst)
            if len(lst) == 0: continue

            filt_el = doc.createElement("Filter")
            filt_el.setAttribute("Name", group.name)
            if group.extensions != None:
                filt_el.setAttribute("Filter", group.extensions)
            filt_el.setAttribute("UniqueIdentifier", group.uuid)

            for src in lst:
                file_el = doc.createElement("File")
                relpath = "%s\\%s" % (SRCDIR.replace('/','\\'), src)
                if relpath.startswith(".\\..\\"):
                    relpath = relpath[2:]
                file_el.setAttribute("RelativePath", relpath)

                for c in sortedKeys(t.configs):
                    cfg = t.configs[c]
                    file_conf_el = makeFileConfig(t, cfg, c, src, group.name,
                                                  sources, pchExcluded)
                    if ( file_conf_el != None ):
                        file_el.appendChild(file_conf_el)

                filt_el.appendChild(file_el)

            files_el.appendChild(filt_el)

        top_el.appendChild(files_el)

        # see comment for refs_el above
        globals_el = doc.createElement("Globals")
        globals_el.appendChild(doc.createTextNode(""))
        top_el.appendChild(globals_el)

        vcprojText = doc.toprettyxml(encoding="Windows-1252")

        writer.writeFile(filename, vcprojText)

def run():
    msvc_common.__dict__.update(globals())
    generator = ProjectGeneratorMsvc9()
    generator.genWorkspaces()
