# MS Visual C++ projects generator script
# $Id$

import fnmatch, re
import errors, utils

basename = os.path.splitext(os.path.basename(FILE))[0]
dirname = os.path.dirname(FILE)


# ------------------------------------------------------------------------
#   helpers
# ------------------------------------------------------------------------

def sortedKeys(dic):
    l = []
    for c in configs_order:
        if c in dic:
            l.append(c)
    return l

def mkConfigName(target, config):
    return '%s - Win32 %s' % (target, config)

def filterGroups(groups, groupDefs, files):
    """Returns dictionary with files sorted into groups (key: group name).
       Groups are given in 'groups' list of names and 'groupDefs' directory
       as ;-separated wildcards."""
    ret = {}
    used = {}
    for g in groups:
        ret[g] = []
        wildcards = groupDefs[g].split()
        for w in wildcards:
            for f in files:
                if f in used: continue
                if fnmatch.fnmatch(f, w):
                    used[f] = 1
                    ret[g].append(f)
    ret[None] = []
    for f in files:
        if f in used: continue
        ret[None].append(f)
    return ret

def fixFlagsQuoting(text):
    """Replaces e.g. /DFOO with /D "FOO" and /DFOO=X with /D FOO=X."""
    return re.sub(r'\/([DIid]) ([^ \"=]+)([ $])', r'/\1 "\2"\3',
           re.sub(r'\/([DIid]) ([^ \"=]+)=([^ \"]*)([ $])', r'/\1 \2=\3\4', text))
    

def sortByBasename(files):
    def __sort(x1, x2):
        f1 = x1.split('\\')[-1]
        f2 = x2.split('\\')[-1]
        if f1 == f2: return 0
        elif f1 < f2: return -1
        else: return 1
    files.sort(__sort)



# ------------------------------------------------------------------------
#   DSW file
# ------------------------------------------------------------------------

def genDSW(dsw_targets, dsp_list):
    dsw = """\
Microsoft Developer Studio Workspace File, Format Version 6.00
# WARNING: DO NOT EDIT OR DELETE THIS WORKSPACE FILE!

###############################################################################"""

    project = """
Project: "%s"=%s.dsp - Package Owner=<4>

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
            dsp_name = basename
        else:
            dsp_name = '%s_%s' % (basename, t.id)
        for d in t.__deps.split():
           deps += """\
Begin Project Dependency
Project_Dep_Name %s
End Project Dependency
""" % d     
        dsw += project % (t.id, dsp_name, deps)
        dspfile = (t, os.path.join(dirname, dsp_name+'.dsp'), dsp_name)
        if dspfile not in dsp_list:
            dsp_list.append(dspfile)
    writer.writeFile('%s.dsw' % (os.path.join(dirname,basename)), dsw)



def genWorkspaces():
    dsp_list = []
    genDSW([t for t in targets if t.__kind == 'project'], dsp_list)
    for t, filename, prjname in dsp_list:
        genDSP(t, filename, prjname)
    # warn about <action> targets that we can't handle (yet):
    for t in [t for t in targets if t.__kind == 'action']:
        print "warning: ignoring action target '%s'" % t.id


# ------------------------------------------------------------------------
#   DSP files
# ------------------------------------------------------------------------

def mkFlags(keyword, lines):
    result = []
    splitted = lines.splitlines();
    splitted2 = [fixFlagsQuoting(' '.join(x.split())) for x in splitted]
    for l in splitted2:
        result.append('# %s BASE %s' % (keyword, l))
    for l in splitted2:
        result.append('# %s %s' % (keyword, l))
    return '\n'.join(result)+'\n'


def genDSP(t, filename, prjname):
    # Create header and list of configurations:
    
    default_cfg = t.configs.keys()[0]
    dsp = """\
# Microsoft Developer Studio Project File - Name="%s" - Package Owner=<4>
# Microsoft Developer Studio Generated Build File, Format Version 6.00
# ** DO NOT EDIT **

# TARGTYPE %s %s

CFG=%s
""" % (t.id, t.__type, t.__type_code, mkConfigName(t.id, default_cfg))
    dsp += """\
!MESSAGE This is not a valid makefile. To build this project using NMAKE,
!MESSAGE use the Export Makefile command and run
!MESSAGE 
!MESSAGE NMAKE /f "%s.mak".
!MESSAGE 
!MESSAGE You can specify a configuration when running NMAKE
!MESSAGE by defining the macro CFG on the command line. For example:
!MESSAGE 
!MESSAGE NMAKE /f "%s.mak" CFG="%s"
!MESSAGE 
!MESSAGE Possible choices for configuration are:
!MESSAGE 
""" % (prjname, prjname, mkConfigName(t.id, default_cfg))
    for c in sortedKeys(t.configs):
        dsp += '!MESSAGE "%s" (based on %s)\n' % (mkConfigName(t.id, c), t.configs[c].__type)
    dsp += """\
!MESSAGE 

# Begin Project
# PROP AllowPerConfigDependencies 0
# PROP Scc_ProjName ""
# PROP Scc_LocalPath ""
CPP=cl.exe
"""
    if t.__type_code in [__MSVC_TYPECODE_GUI,__MSVC_TYPECODE_DLL]:
        dsp += 'MTL=midl.exe\n'

    dsp += 'RSC=rc.exe\n\n'

    # Output settings for all configurations:
    flags = []
    for c in sortedKeys(t.configs):
        cfg = t.configs[c]
        fl = '  "$(CFG)" == "%s"' % mkConfigName(t.id, c) + '\n\n'
        fl += mkFlags('PROP',"""\
Use_MFC 0
Use_Debug_Libraries """ + cfg.__debug + """
Output_Dir "%s"
Intermediate_Dir "%s\\%s"
Target_Dir ""
""" % (cfg.__targetdir[:-1], cfg.__builddir, t.id)) +  \
              mkFlags('ADD','CPP /nologo %s %s /c' % (cfg.__cppflags, cfg.__defines))
        if cfg.__type_code in [__MSVC_TYPECODE_GUI,__MSVC_TYPECODE_DLL]:
            fl += mkFlags('ADD','MTL /nologo %s /mktyplib203 /win32' % cfg.__defines)
        fl += mkFlags('ADD', 'RSC /l 0x405 %s' % cfg.__win32rc_flags)
        fl += """\
BSC32=bscmake.exe
# ADD BASE BSC32 /nologo
# ADD BSC32 /nologo
"""
        if cfg.__type_code != __MSVC_TYPECODE_LIB:
            fl += 'LINK32=link.exe\n'
            fl += mkFlags('ADD','LINK32 %s /nologo %s' % (cfg.__ldlibs, cfg.__ldflags))
        else:
            fl += 'LIB32=link.exe -lib\n'
            fl += mkFlags('ADD','LIB32 /nologo %s' % cfg.__outflag)
        fl += '\n'
        flags.append(fl)
    dsp += '!IF' + '!ELSEIF'.join(flags) + '!ENDIF'

    dsp += '\n\n# Begin Target\n\n'

    # Output list of configs one more:
    for c in sortedKeys(t.configs):
        dsp += '# Name "%s"\n' % mkConfigName(t.id, c)
    
    # Write source files:

    # (find files from all configs, identify files not in all configs)
    sources = {}
    for c in sortedKeys(t.configs):
        for s in t.configs[c].__sources.split():
            snat = utils.nativePaths(s)
            if snat not in sources:
                sources[snat] = [c]
            else:
                sources[snat].append(c)
    for s in sources:
        if len(sources[s]) == len(t.configs):
            sources[s] = None

    # Add more files that are part of the project but are not built (e.g. 
    # headers, READMEs etc.). They are included unconditionally to save some
    # space.
    for c in sortedKeys(t.configs):
        for s in t.configs[c].__more_files.split():
            snat = utils.nativePaths(s)
            if snat not in sources:
                sources[snat] = None

    # Find files with custom build associated with them and retrieve
    # custom build's code
    filesWithCustomBuild = {}
    for c in sortedKeys(t.configs):
        cbf = t.configs[c].__custom_build_files
        if len(cbf) == 0 or cbf.isspace(): continue
        for f in cbf.split():
            filesWithCustomBuild[f] = {}
    for f in filesWithCustomBuild:
        fname = f.replace('.','_').replace('\\','_')
        for c in sortedKeys(t.configs):
            filesWithCustomBuild[f][c] = \
                   eval ('t.configs[c].__custom_build_%s' % fname)

    # (sort the files into groups)
    groups = []
    groups_default= ['Source Files', 'Header Files', 'Resource Files']
    group_defs = {
        'Source Files'   : '*.cpp *.c *.cxx *.rc *.def *.r *.odl *.idl *.hpj *.bat',
        'Header Files'   : '*.h *.hpp *.hxx *.hm *.inl',
        'Resource Files' : '*.ico *.cur *.bmp *.dlg *.rc2 *.rct *.bin *.rgs *.gif *.jpg *.jpeg *.jpe',
    }
    if t.__file_groups != '' and not t.__file_groups.isspace():
        for gr in t.__file_groups.split('\n'):
            grdef = gr.split(':')
            groups.append(grdef[0])
            group_defs[grdef[0]] = grdef[1]
    groups += groups_default
    
    files = filterGroups(groups, group_defs, sources.keys())

    # (some files-related settings:)
    pchExcluded = t.__pch_excluded.split()

    # (write them)
    for group in [g for g in groups if g in files]:
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

SOURCE=%s\%s
""" % (SRCDIR,src)
            file_flags = ''
            if src == t.__pch_generator:
                file_flags += '# ADD BASE CPP /Yc"%s"\n' % t.__pch_header
                file_flags += '# ADD CPP /Yc"%s"\n' % t.__pch_header
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
                    flags.append('  "$(CFG)" == "%s"' % mkConfigName(t.id, c) +
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


genWorkspaces()
