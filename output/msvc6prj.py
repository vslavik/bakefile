#
#  This file is part of Bakefile (http://www.bakefile.org)
#
#  Copyright (C) 2003-2007 Vaclav Slavik
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
#  MS Visual C++ projects generator script
#

import os, os.path
import errors, utils

import msvc_common
from msvc_common import *
        
        
DEFAULT_FILE_GROUPS = [
    FilesGroup('Source Files',
               '*.cpp *.c *.cxx *.rc *.def *.r *.odl *.idl *.hpj *.bat'),
    FilesGroup('Header Files',
               '*.h *.hpp *.hxx *.hm *.inl'),
    FilesGroup('Resource Files',
               '*.ico *.cur *.bmp *.dlg *.rc2 *.rct *.bin *.rgs *.gif *.jpg *.jpeg *.jpe')
]

# ------------------------------------------------------------------------
#                              Generator class
# ------------------------------------------------------------------------

class ProjectGeneratorMsvc6:

    def __init__(self):
        self.basename = os.path.splitext(os.path.basename(FILE))[0]
        self.dirname = os.path.dirname(FILE)
 
    # --------------------------------------------------------------------
    #   basic configuration
    # --------------------------------------------------------------------

    def getSolutionExtension(self):
        return 'dsw'
    def getProjectExtension(self):
        return 'dsp'
    def getMakefileExtension(self):
        return 'mak'

    # --------------------------------------------------------------------
    #   helpers
    # --------------------------------------------------------------------

    def mkConfigName(self, target, config):
        return '%s - Win32 %s' % (target, config)

    def makeDependency(self, prj_id):
        return """\
Begin Project Dependency
Project_Dep_Name %s
End Project Dependency
""" % prj_id


    # --------------------------------------------------------------------
    #   DSW file
    # --------------------------------------------------------------------

    def makeDswHeader(self):
        return """\
Microsoft Developer Studio Workspace File, Format Version 6.00
# WARNING: DO NOT EDIT OR DELETE THIS WORKSPACE FILE!

###############################################################################"""

    def genDSW(self, dsw_targets, dsp_list, deps_translation):
        dsw = self.makeDswHeader()
        project = """
Project: "%s"=%s.""" + self.getProjectExtension() + """ - Package Owner=<4>

Package=<5>
{{{
}}}

Package=<4>
{{{
%s}}}

###############################################################################
"""

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
            for d in deplist:
                if d in deps_translation:
                    d2 = deps_translation[d]
                else:
                    d2 = d
                deps += self.makeDependency(d2)

            dsw += project % (t.id, dsp_name, deps)
            dspfile = (t, 
                       os.path.join(self.dirname,
                                    dsp_name + '.' + self.getProjectExtension()),
                       dsp_name)
            if dspfile not in dsp_list:
                dsp_list.append(dspfile)
        
        # add external dsp deps (we put them after bakefile's own targets so
        # that the active project when you first open the workspace is something
        # meaningful and not a mere dependency):
        extern_deps = []
        for t in dsw_targets:
            for d in t._dsp_deps.split():
                if d not in extern_deps:
                    extern_deps.append(d)
        for d in extern_deps:
            deps = ''
            d_components = d.split(':')
            if len(d_components) == 3:
                for d_dep in d_components[2].split(','):
                    deps += self.makeDependency(d_dep)
            dsw += project % (d_components[0],
                              os.path.splitext(d_components[1])[0], deps)

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
                assert c not in t.configs # otherwise not mutually exclusive
                t.configs[c] = targets[tg2].configs[c]
            t.id = tgR
            projects.remove(targets[tg2])
            targets.append(tgR, t)
            del targets[tg1]
            del targets[tg2]
            deps_translation[tg1] = tgR
            deps_translation[tg2] = tgR
        
        self.genDSW(projects, dsp_list, deps_translation)
        for t, filename, prjname in dsp_list:
            self.genDSP(t, filename, prjname)
            
        # warn about <action> targets that we can't handle (yet):
        for t in [t for t in targets if t._kind == 'action']:
            print "warning: ignoring action target '%s'" % t.id


    # ------------------------------------------------------------------------
    #   DSP files
    # ------------------------------------------------------------------------

    def mkFlags(self, keyword, lines):
        result = []
        splitted = lines.splitlines();
        splitted2 = [fixFlagsQuoting(' '.join(x.split())) for x in splitted]
        for l in splitted2:
            result.append('# %s BASE %s' % (keyword, l))
        for l in splitted2:
            result.append('# %s %s' % (keyword, l))
        return '\n'.join(result)+'\n'


    def makeDspHeader(self, id):
        return """\
# Microsoft Developer Studio Project File - Name="%s" - Package Owner=<4>
# Microsoft Developer Studio Generated Build File, Format Version 6.00
# ** DO NOT EDIT **

""" % id
        
    def makeBeginProject(self, t):
        txt = """\
# PROP AllowPerConfigDependencies 0
# PROP Scc_ProjName ""
# PROP Scc_LocalPath ""
CPP=cl.exe
"""
        if t._type_nick in ['gui','dll']:
            txt += 'MTL=midl.exe\n'
        txt += 'RSC=rc.exe\n'
        return txt
       
    def makeCpuPlatformID(self, cfg):
        return ''
    
    def makeSettingsCPP(self, cfg):
        return self.mkFlags('ADD',
                            'CPP /nologo %s %s /c' % (cfg._cppflags, cfg._defines))
    def makeSettingsMTL(self, cfg):
        return self.mkFlags('ADD',
                            'MTL /nologo %s /mktyplib203 /win32' % cfg._defines)

    def makeSettingsRSC(self, cfg):
        return self.mkFlags('ADD', 'RSC %s' % cfg._win32rc_flags)
    
    def makeSettingsBSC(self, cfg):
        return """\
BSC32=bscmake.exe
# ADD BASE BSC32 /nologo
# ADD BSC32 /nologo
"""
    def makeSettingsLIB(self, cfg):
            txt = 'LIB32=link.exe -lib\n'
            txt += self.mkFlags('ADD','LIB32 /nologo %s' % cfg._outflag)
            return txt
    
    def makeSettingsLINK(self, cfg):
            txt = 'LINK32=link.exe\n'
            txt += self.mkFlags('ADD','LINK32 %s /nologo %s' % (cfg._ldlibs, cfg._ldflags))
            return txt

    def makeSettingsCPP_MTL_RSC_BSC_LINK(self, cfg):
        txt = self.makeSettingsCPP(cfg)
        if cfg._type_nick in ['gui','dll']:
            txt += self.makeSettingsMTL(cfg)
        txt += self.makeSettingsRSC(cfg)
        txt += self.makeSettingsBSC(cfg)
        if cfg._type_nick != 'lib':
            txt += self.makeSettingsLINK(cfg)
        else:
            txt += self.makeSettingsLIB(cfg)
        return txt

    def genDSP(self, t, filename, prjname):
        # Create header and list of configurations:
        
        default_cfg = sortedKeys(t.configs)[-1]
        dsp = self.makeDspHeader(prjname)
        targ_types = []
        for c in t.configs:
            targ = '%s %s' % (t.configs[c]._type, t.configs[c]._type_code)
            if targ not in targ_types:
                targ_types.append(targ)
        for tt in targ_types:
            dsp += '# TARGTYPE %s\n' % tt
            
        dsp += '\nCFG=%s\n' % self.mkConfigName(t.id, default_cfg)
        dsp += """\
!MESSAGE This is not a valid makefile. To build this project using NMAKE,
!MESSAGE use the Export Makefile command and run
!MESSAGE 
!MESSAGE NMAKE /f "%s.%s".
!MESSAGE 
!MESSAGE You can specify a configuration when running NMAKE
!MESSAGE by defining the macro CFG on the command line. For example:
!MESSAGE 
!MESSAGE NMAKE /f "%s.%s" CFG="%s"
!MESSAGE 
!MESSAGE Possible choices for configuration are:
!MESSAGE 
""" % (prjname, self.getMakefileExtension(),
       prjname, self.getMakefileExtension(),
       self.mkConfigName(t.id, default_cfg))
        for c in sortedKeys(t.configs):
            dsp += '!MESSAGE "%s" (based on %s)\n' % (self.mkConfigName(t.id, c), t.configs[c]._type)
        dsp += """\
!MESSAGE 

# Begin Project
"""
        dsp += self.makeBeginProject(t)
        dsp += '\n'

        # Output settings for all configurations:
        flags = []
        for c in sortedKeys(t.configs):
            cfg = t.configs[c]
            fl = '  "$(CFG)" == "%s"' % self.mkConfigName(t.id, c) + '\n\n'
            fl += self.mkFlags('PROP',"""\
Use_MFC 0
Use_Debug_Libraries """ + cfg._debug + """
Output_Dir "%s"
Intermediate_Dir "%s\\%s"
%sTarget_Dir ""
""" % (cfg._targetdir[:-1], cfg._builddir, t.id,
       self.makeCpuPlatformID(cfg)))
            fl += self.makeSettingsCPP_MTL_RSC_BSC_LINK(cfg)
            fl += '\n'
            flags.append(fl)
        dsp += '!IF' + '!ELSEIF'.join(flags) + '!ENDIF'

        dsp += '\n\n# Begin Target\n\n'

        # Output list of configs one more:
        for c in sortedKeys(t.configs):
            dsp += '# Name "%s"\n' % self.mkConfigName(t.id, c)
        
        # Write source files:

        sources, groups, files, filesWithCustomBuild = \
            organizeFilesIntoGroups(t, DEFAULT_FILE_GROUPS)

        # (some files-related settings:)
        pchExcluded = t._pch_excluded.split()

        # (write them)
        for group in [g.name for g in groups if g.name in files]:
            lst = files[group]
            sortByBasename(lst)
            if len(lst) == 0: continue
            if group != None:
                dsp += """\
# Begin Group "%s"

# PROP Default_Filter ""
""" % group
            for src in lst:
                dsp += """\
# Begin Source File

SOURCE=%s\\%s
""" % (SRCDIR.replace('/','\\'),src)
                file_flags = ''
                if src == t._pch_generator:
                    file_flags += '# ADD BASE CPP /Yc"%s"\n' % t._pch_header
                    file_flags += '# ADD CPP /Yc"%s"\n' % t._pch_header
                if src in pchExcluded:
                    file_flags += '# SUBTRACT CPP /YX /Yc /Yu\n'
                
                # the file is either disabled in some configurations or has
                # custom build step associated with it:
                if sources[src] != None or src in filesWithCustomBuild:
                    flags = []
                    old_file_flags = file_flags
                    for c in sortedKeys(t.configs):
                        if sources[src] != None and c not in sources[src]:
                            file_flags += '# PROP Exclude_From_Build 1\n'
                        if src in filesWithCustomBuild:
                            file_flags += \
                              '# Begin Custom Build - %s\n\n# End Custom Build\n' %\
                               filesWithCustomBuild[src][c]
                        flags.append('  "$(CFG)" == "%s"' % self.mkConfigName(t.id, c) +
                                     '\n\n' + file_flags + '\n')
                        file_flags = old_file_flags
                    dsp += '\n!IF' + '!ELSEIF'.join(flags) + '!ENDIF\n\n'
                else:
                    dsp += file_flags
                dsp += '# End Source File\n'
            if group != None:
                dsp += '# End Group\n'

        # Write footer:
        dsp += """\
# End Target
# End Project
"""

        writer.writeFile(filename, dsp)

def run():
    msvc_common.__dict__.update(globals())
    generator = ProjectGeneratorMsvc6()
    generator.genWorkspaces()
