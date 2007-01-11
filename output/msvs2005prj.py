#
#  This file is part of Bakefile (http://bakefile.sourceforge.net)
#
#  Copyright (C) 2006-2007 Vaclav Slavik, Kevin Powell, Steven Van Ingelgem,
#                          Kevin Ollivier
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
#  MS Visual Studio 2005 project files generator script
#

import os, os.path
import errors, utils
from xml.dom.minidom import getDOMImplementation

import msvc_common
from msvc_common import *

# ------------------------------------------------------------------------
#   helpers
# ------------------------------------------------------------------------

# this GUID is used by all solutions in the Project() entry:
GUID_SOLUTION = "{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}"

# UUID for Bakefile namespace when generating GUIDs
NAMESPACE_BAKEFILE_PROJ = "{b0c737d9-df87-4499-b156-418baa078a12}"
NAMESPACE_BAKEFILE_FILTERS = "{0e8f53b3-f09d-40b1-b248-66f80b72e654}"

def mk_uuid(namespace, seed):
    # NB: we want to have the GUID strings be repeatable so, generate them
    #     from a repeatable seed
    try:
        from uuid import uuid5, UUID
    except ImportError:
        # the uuid module is only available since Python 2.5, so use
        # bundled version of the module:
        from py25modules.uuid import uuid5, UUID

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
                   extensions='',
                   uuid='{93995380-89BD-4b04-88EB-625FBE52EBFB}'),
    MsvsFilesGroup('Resource Files',
                   extensions='rc;ico;cur;bmp;dlg;rc2;rct;bin;rgs;gif;jpg;jpeg;jpe;resx;tiff;tif;png;wav',
                   uuid='{67DA6AB6-F800-4c08-8B7A-83BB121AAD01}')
]


# ------------------------------------------------------------------------
#                              Generator class
# ------------------------------------------------------------------------

class ProjectGeneratorMsvc9:

    app_type_code = { 'console' : '1', 'gui' : '2' }
    
    def __init__(self):
        self.basename = os.path.splitext(os.path.basename(FILE))[0]
        self.dirname = os.path.dirname(FILE)
 
    # --------------------------------------------------------------------
    #   basic configuration
    # --------------------------------------------------------------------

    def getSolutionExtension(self):
        return 'sln'
    def getProjectExtension(self):
        return 'vcproj'
    def getMakefileExtension(self):
        return 'mak'

    # --------------------------------------------------------------------
    #   helpers
    # --------------------------------------------------------------------

    def mkConfigName(self, target, config):
        return '%s|%s' % (config, self.getPlatform())

    def getPlatform(self):
        # FIXME: should be configurable, so that other (embedded) platforms
        # can be supported by this format as well
        return "Win32"

    # --------------------------------------------------------------------
    #   DSW file
    # --------------------------------------------------------------------

    def makeDswHeader(self):
        return """\
Microsoft Visual Studio Solution File, Format Version 9.00
# Visual Studio 2005
"""

    def genDSW(self, dsw_targets, dsp_list, deps_translation):
        dsw = self.makeDswHeader()
        prj_base_string = 'Project("%s") = "%s", "%s", "%s"\n%sEndProject\n' 
        projects_section = "" #this string will hold the projects
        globals_section = "" #this string will hold the globals section

        if len(dsw_targets) == 0:
            return

        ## loop over the targets and assign everyone a guid
        guid_dict = {}
        for t in dsw_targets:
            guid_dict[t.id] = mk_proj_uuid(self.basename, t.id)

        # FIXME: this is taken from msvc6 and slightly modified, should be
        #        moved to common code
        single_target = (len(dsw_targets) == 1)
        for t in dsw_targets:
            deps = ''
            if single_target:
                dsp_name = self.basename
            else:
                dsp_name = '%s_%s' % (self.basename, t.id)
            deplist = t._deps.split()
            
            # add external dsp dependencies:
            for d in t._dsp_deps.split():
                deplist.append(d.split(':')[0])
            
            # write dependencies:
            deps_str = ""
            if len(deplist) != 0:
                deps_str = "\tProjectSection(ProjectDependencies) = postProject\n"

                for d in deplist:
                    if d in deps_translation:
                        d2 = deps_translation[d]
                    else:
                        d2 = d
                    guid = guid_dict[d]
                    deps_str += "\t\t%s = %s\n" % (guid, guid)
                deps_str += "\tEndProjectSection\n"

            guid = guid_dict[t.id]

            #build the projects section
            prj_str = prj_base_string % (GUID_SOLUTION, t.id, dsp_name + '.' + self.getProjectExtension(), guid, deps_str)
            dsw += prj_str
            
            dspfile = (t, 
                       os.path.join(self.dirname,
                                    dsp_name + '.' + self.getProjectExtension()),
                       dsp_name, guid)
            
            if dspfile not in dsp_list:
                dsp_list.append(dspfile)
            
        # end of FIXME

        # generate configurations listing:
        dsw += "Global\n"
        dsw += "\tGlobalSection(SolutionConfigurationPlatforms) = preSolution\n"
        for c in sortedKeys(configs):
            cfg = '%s|%s' % (c, self.getPlatform())
            dsw += "\t\t%s = %s\n" % (cfg,cfg)
        dsw += "\tEndGlobalSection\n"
        
        # ...and configurations binding to vcproj configurations:
        dsw += "\tGlobalSection(ProjectConfigurationPlatforms) = postSolution\n"

        for t in dsw_targets:
            guid = guid_dict[t.id]
            for c in sortedKeys(t.configs):
                cfg = '%s|%s' % (c, self.getPlatform())
                txt = "\t\t%(guid)s.%(cfg)s.%%s = %(cfg)s\n" % {'guid':guid, 'cfg':cfg}
                dsw += txt % 'ActiveCfg'
                dsw += txt % 'Build.0'

        
        dsw += "\tEndGlobalSection\n"
        dsw += "\tGlobalSection(SolutionProperties) = preSolution\n"
        dsw += "\t\tHideSolutionNode = FALSE\n"
        dsw += "\tEndGlobalSection\n"
        dsw += "EndGlobal\n"
        
        writer.writeFile('%s.%s' % (
            os.path.join(self.dirname, self.basename),
            self.getSolutionExtension()
            ), dsw)
   

    def genWorkspaces(self):
        dsp_list = []

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
                t.configs[c] = targets[tg2].configs[c]
            t.id = tgR
            projects.remove(targets[tg2])
            targets.append(tgR, t)
            del targets[tg1]
            del targets[tg2]
            deps_translation[tg1] = tgR
            deps_translation[tg2] = tgR
        
        self.genDSW(projects, dsp_list, deps_translation)
        for t, filename, prjname, guid in dsp_list:
            self.genDSP(t, filename, prjname, guid)
            
        # warn about <action> targets that we can't handle (yet):
        for t in [t for t in targets if t._kind == 'action']:
            print "warning: ignoring action target '%s'" % t.id


    # ------------------------------------------------------------------------
    #   DSP files
    # ------------------------------------------------------------------------

    def mapRTTI(self, val):
        if val == 'on':
            return 'true'
        else :
            return false


    #some helpers to build parts of the DSP file that change if you are doing PC vs WinCE
    def buildConfElement(self, doc, cfg, c, t):
        conf_name = self.mkConfigName(t.id, c)
        conf_el = doc.createElement("Configuration")
        conf_el.setAttribute("Name", conf_name)
        conf_el.setAttribute("OutputDirectory", ".\\%s" % cfg._targetdir[:-1])
        conf_el.setAttribute("IntermediateDirectory", ".\\%s\\%s" % (cfg._builddir, t.id) )
        conf_el.setAttribute("ConfigurationType", "%s" % cfg._type_code)
        conf_el.setAttribute("UseOfMFC", "0")
        conf_el.setAttribute("ATLMinimizesCRunTimeLibraryUsage", "false")
        return conf_el

    def buildIDLToolElement(self, doc, cfg, t):
        t5 = doc.createElement("Tool")
        t5.setAttribute("Name", "VCIDLTool")
        return t5

    def buildCompilerToolElement(self, doc, cfg, c, t):
        warnings_map = { 'no':'0', 'default':'1', 'max':'4'}
        t6 = doc.createElement("Tool")
        t6.setAttribute("Name", "VCCLCompilerTool")
       
        t6.setAttribute("Optimization", cfg._optimize)
        t6.setAttribute("InlineFunctionExpansion", "1")
        t6.setAttribute("AdditionalIncludeDirectories", ",".join(cfg._include_paths.split(" ")) )

        ## KLP -- this seems to cause wierd build behavior, omitting for now
        #t6.setAttribute("MinimalRebuild", "true")

        if cfg._cxx_exceptions == 'on':
            t6.setAttribute("ExceptionHandling", "1")
        else:
            t6.setAttribute("ExceptionHandling", "0")

        try:
            t6.setAttribute("EnableIntrinsicFunctions", cfg._intrinsic_functions)
        except:
            pass #prolly a name error, no big deal
        
        #handle the run time library -- note that only multi thread is supported
        rtl = '3'        # default to debug
        rtl_opt = ' /MT' # default to multithreaded
        if cfg._rtl_dbg == 'on':
            rtl_opt_debug = 'd'
        else:
            rtl_opt_debug = ''

        if cfg._rtl_type == 'dynamic':
            rtl_opt = ' /MD'
            if ( cfg._rtl_dbg != 'on' ):
                rtl = '2'
        elif cfg._rtl_type == 'static':
            if cfg._rtl_dbg == 'on':
                rtl = '1'
            else:
                rtl = '0'

        t6.setAttribute("AdditionalOptions", cfg._cppflags + rtl_opt + rtl_opt_debug)
        t6.setAttribute("RuntimeLibrary", rtl)

        t6.setAttribute("PreprocessorDefinitions", ";".join(cfg._defines.split()))
        
        if cfg._debug == '1':
            t6.setAttribute("BasicRuntimeChecks", "3")
            t6.setAttribute("DebugInformationFormat", "3")
            t6.setAttribute("Detect64BitPortabilityProblems", "true")
        else:
            t6.setAttribute("BasicRuntimeChecks", "0")
            t6.setAttribute("DebugInformationFormat", "0")
            t6.setAttribute("BufferSecurityCheck","false")
            
        t6.setAttribute("RuntimeTypeInfo", self.mapRTTI(cfg._cxx_rtti))

        if cfg._pch_use_pch == '1':
            t6.setAttribute("UsePrecompiledHeader","2")
            t6.setAttribute("PrecompiledHeaderThrough", cfg._pch_header)
            t6.setAttribute("PrecompiledHeaderFile", cfg._pch_file)
            
        t6.setAttribute("AssemblerListingLocation", ".\\%s\\%s\\" % (cfg._builddir, t.id) )
        t6.setAttribute("ObjectFile", ".\\%s\\%s\\" % (cfg._builddir, t.id) )
        t6.setAttribute("ProgramDataBaseFileName", cfg._pdbfile)
        if warnings_map.has_key(cfg._warnings):
            t6.setAttribute("WarningLevel", warnings_map[cfg._warnings])
        else:
            t6.setAttribute("WarningLevel", "1")
        t6.setAttribute("SuppressStartupBanner", "true")

        return t6

    def buildLinkerToolElement(self, doc, cfg, t):
        t10 = doc.createElement("Tool")
        t10.setAttribute("Name", "VCLinkerTool")
        t10.setAttribute("AdditionalDependencies", cfg._ldlibs)
        t10.setAttribute("AdditionalOptions", cfg._ldflags)
        t10.setAttribute("OutputFile", "%s%s" % (cfg._targetdir, cfg._targetname))

        if t.type == 'exe':
            t10.setAttribute("LinkIncremental", "2")
            t10.setAttribute("SubSystem", "%s" % self.app_type_code[cfg._type_nick] )
        elif t.type == 'dll':
            t10.setAttribute("LinkIncremental", "1")
            if cfg._importlib != "": implib = cfg._importlib
            else: implib = cfg._targetname.replace('.dll', '.lib')
            t10.setAttribute("ImportLibrary", ".\\%s\\%s" % (cfg._targetdir, implib))
            
        t10.setAttribute("SuppressStartupBanner", "true")
        t10.setAttribute("AdditionalLibraryDirectories", ",".join(cfg._lib_paths.split()))
        t10.setAttribute("GenerateManifest", "true")
        
        if cfg._debug == '1':
            t10.setAttribute("GenerateDebugInformation", "true")
            
        t10.setAttribute("ProgramDatabaseFile", cfg._pdbfile)
        t10.setAttribute("TargetMachine", "1")
        return t10

    def buildLibrarianToolElement(self, doc, cfg, t):
        t10 = doc.createElement("Tool")
        t10.setAttribute("Name", "VCLibrarianTool")
        t10.setAttribute("OutputFile","%s%s" % (cfg._targetdir, cfg._targetname) )
        t10.setAttribute("SuppressStartupBanner", "true")
        return t10

    def buildResourceCompilerToolElement(self, doc, cfg, t):
        t8 = doc.createElement("Tool")
        t8.setAttribute("Name", "VCResourceCompilerTool")
        t8.setAttribute("Culture", "1033")
        return t8

    def buildPlatformsElement(self,doc):
        #Platforms Node
        plats_el = doc.createElement("Platforms")
        plat_el = doc.createElement("Platform")
        plat_el.setAttribute("Name", self.getPlatform())
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
        #add all the tools
        t1 = doc.createElement("Tool")
        t1.setAttribute("Name", "VCPreBuildEventTool")
        conf_el.appendChild(t1)

        t2 = doc.createElement("Tool")
        t2.setAttribute("Name", "VCCustomBuildTool")
        conf_el.appendChild(t2)

        t3 = doc.createElement("Tool")
        t3.setAttribute("Name", "VCXMLDataGeneratorTool")
        conf_el.appendChild(t3)

        t4 = doc.createElement("Tool")
        t4.setAttribute("Name", "VCWebServiceProxyGeneratorTool")
        conf_el.appendChild(t4)

        t5 = self.buildIDLToolElement(doc, cfg, t)
        conf_el.appendChild(t5)

        t6 = self.buildCompilerToolElement(doc, cfg, c, t)

        conf_el.appendChild(t6)

        t7 = doc.createElement("Tool")
        t7.setAttribute("Name", "VCManagedResourceCompilerTool")
        conf_el.appendChild(t7)

        t8 = self.buildResourceCompilerToolElement(doc, cfg, t)
        conf_el.appendChild(t8)

        t9 = doc.createElement("Tool")
        t9.setAttribute("Name", "VCPreLinkEventTool")
        conf_el.appendChild(t9)

        if (t.type == 'lib'):
            t10 = self.buildLibrarianToolElement(doc, cfg, t)
            conf_el.appendChild(t10)
        elif ( (t.type == 'exe') or (t.type == 'dll') ):
            t10 = self.buildLinkerToolElement(doc, cfg, t)
            conf_el.appendChild(t10)

        t11 = doc.createElement("Tool")
        t11.setAttribute("Name", "VCALinkTool")
        conf_el.appendChild(t11)

        t12 = doc.createElement("Tool")
        t12.setAttribute("Name", "VCXDCMakeTool")
        conf_el.appendChild(t12)

        t13 = doc.createElement("Tool")
        t13.setAttribute("Name", "VCBscMakeTool")
        t13.setAttribute("OutputFile", ".\\%s%s.bsc" % (cfg._targetdir, prjname))
        t13.setAttribute("SuppressStartupBanner", "true")
        conf_el.appendChild(t13)

        t14 = doc.createElement("Tool")
        t14.setAttribute("Name", "VCFxCopTool")
        conf_el.appendChild(t14)

        if(t.type == 'exe'):
            t16 = doc.createElement("Tool")
            t16.setAttribute("Name", "VCAppVerifierTool")
            conf_el.appendChild(t16)
            t17 = doc.createElement("Tool")
            t17.setAttribute("Name", "VCWebDeploymentTool")
            conf_el.appendChild(t17)

        t15 = doc.createElement("Tool")
        t15.setAttribute("Name", "VCPostBuildEventTool")
        conf_el.appendChild(t15)

        #additional tools
        for ad_t in self.additionalTools(doc, cfg, t):
                conf_el.appendChild(ad_t)

        return conf_el
                
    #this is just for derived classes that may want to add more tools to the config
    def additionalTools(self, doc, cfg, t):
        return []

    def get_default_groups(self):
            return ['Source Files', 'Header Files', 'Resource Files']

    def get_group_defs(self):
        return {
            'Source Files'   : '*.cpp *.c *.cxx *.def *.r *.odl *.idl *.hpj *.bat',
            'Header Files'   : '*.h *.hpp *.hxx *.hm *.inl',
            'Resource Files' : '*.ico *.cur *.bmp *.dlg *.rc *.rc2 *.rct *.bin *.rgs *.gif *.jpg *.jpeg *.jpe',
            }
    
    def genDSP(self, t, filename, prjname, guid):        
        #start a new xml document
        impl = getDOMImplementation()
        doc = impl.createDocument(None, "VisualStudioProject", None)
        top_el = doc.documentElement

        #fill in the attributes of the top element
        top_el.setAttribute("ProjectType", "Visual C++")
        top_el.setAttribute("Version", "8.00")
        top_el.setAttribute("Name", t.id)
        top_el.setAttribute("ProjectGUID", "%s" % guid)

        top_el.appendChild(self.buildPlatformsElement(doc))
        
        top_el.appendChild(self.buildToolFilesElement(doc))

        top_el.appendChild(self.buildAllConfigurations(doc, prjname, t))

        refs_el = doc.createElement("References")
        refs_el.appendChild(doc.createTextNode(""))
        top_el.appendChild(refs_el)

        files_el = doc.createElement("Files")

        #munge the source files around so we can write them to the file
        sources, groups, files, filesWithCustomBuild = \
            organizeFilesIntoGroups(t, DEFAULT_FILE_GROUPS, groupClass=MsvsFilesGroup)
       
        ##define a local helper function for building the files area
        def makeFileConfig(t,cfg, c, src, group, sources):
            conf_name = self.mkConfigName(t.id, c)
            file_conf_el = doc.createElement("FileConfiguration")
            file_conf_el.setAttribute("Name", conf_name)

            if sources[src] != None and c not in sources[src]:
                file_conf_el.setAttribute("ExcludedFromBuild", "true")
                tool_el = None
            elif (src in filesWithCustomBuild.keys() and
                c in filesWithCustomBuild[src].keys()):
                #custom build for this file for this config
                
                strs = filesWithCustomBuild[src][c].split('|||')
                tool_el = doc.createElement("Tool")
                tool_el.setAttribute("Name", "VCCustomBuildTool")
                try:
                    tool_el.setAttribute('Description', strs[0])
                    tool_el.setAttribute('CommandLine', strs[1])
                    tool_el.setAttribute('Outputs', strs[2])
                except:
                    #keep going, even if we didn't set up the whole thing
                    pass
            elif cfg._pch_use_pch and src == cfg._pch_generator:
                tool_el = doc.createElement("Tool")
                tool_el.setAttribute("Name", "VCCLCompilerTool")
                tool_el.setAttribute("UsePrecompiledHeader", "1")
            else:
                tool_el = None
                file_conf_el = None

            if tool_el != None:
                file_conf_el.appendChild(tool_el)
            return file_conf_el
        
        for group in [g for g in groups if g.name in files]:
            lst = files[group.name]
            sortByBasename(lst)
            if len(lst) == 0: continue

            filt_el = doc.createElement("Filter")
            filt_el.setAttribute("Name", group.name)
            filt_el.setAttribute("UniqueIdentifier", group.uuid)
            if group.extensions != None:
                filt_el.setAttribute("Filter", group.extensions)

            for src in lst:
                file_el = doc.createElement("File")
                file_el.setAttribute("RelativePath", "%s\\%s" % (SRCDIR, src))
                   
                for c in sortedKeys(t.configs):
                    cfg = t.configs[c]
                    file_conf_el = makeFileConfig(t, cfg, c, src, group.name, sources)
                    if ( file_conf_el != None ):
                        file_el.appendChild(file_conf_el)
                    
                filt_el.appendChild(file_el)

            files_el.appendChild(filt_el)

        top_el.appendChild(files_el)

        globals_el = doc.createElement("Globals")
        globals_el.appendChild(doc.createTextNode(""))
        top_el.appendChild(globals_el)
            
        dsp = doc.toprettyxml()

        writer.writeFile(filename, dsp)
        
def run():
    msvc_common.__dict__.update(globals())
    generator = ProjectGeneratorMsvc9()
    generator.genWorkspaces()
