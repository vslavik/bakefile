# MS Visual C++ projects generator script
# $Id$

import fnmatch

basename = os.path.splitext(os.path.basename(FILE))[0]
dirname = os.path.dirname(FILE)


# ------------------------------------------------------------------------
#   helpers
# ------------------------------------------------------------------------

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


# ------------------------------------------------------------------------
#   DSW file
# ------------------------------------------------------------------------

def genDSW():
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

    for t in targets:
        deps = ''
        dsp_name = '%s_%s' % (basename, t.id)
        for d in t.__deps.split():
           deps += """\
Begin Project Dependency
Project_Dep_Name %s
End Project Dependency
""" % d     
        dsw += project % (t.id, dsp_name, deps)
        genDSP(t, os.path.join(dirname, dsp_name+'.dsp'), dsp_name)
    writer.writeFile(FILE, dsw)



# ------------------------------------------------------------------------
#   DSP files
# ------------------------------------------------------------------------

def mkFlags(keyword, lines):
    result = []
    splitted = lines.splitlines();
    for l in splitted:
        result.append('# %s BASE %s' % (keyword, l))
    for l in splitted:
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
    for c in t.configs:
        dsp += '!MESSAGE "%s" (based on %s)\n' % (mkConfigName(t.id, c), t.configs[c].__type)
    dsp += """\
!MESSAGE 

# Begin Project
# PROP AllowPerConfigDependencies 0
# PROP Scc_ProjName ""
# PROP Scc_LocalPath ""
CPP=cl.exe
RSC=rc.exe

"""

    # Output settings for all configurations:
    flags = []
    for c in t.configs:
        cfg = t.configs[c]
        flags.append('  "$(CFG)" == "%s"' % mkConfigName(t.id, c) + '\n\n' +
                mkFlags('PROP',"""\
Use_MFC 0
Use_Debug_Libraries """ + cfg.__debug + """
Output_Dir "%s"
Intermediate_Dir "%s\\%s"
Target_Dir ""
""" % (cfg.__targetdir, cfg.__builddir, t.id)) + 
                mkFlags('ADD','CPP /nologo %s %s' % (cfg.__cppflags, cfg.__defines))+"""\
# ADD BASE RSC /l 0x405 /d "NDEBUG"
# ADD RSC /l 0x405 /d "NDEBUG"
BSC32=bscmake.exe
# ADD BASE BSC32 /nologo
# ADD BSC32 /nologo
LINK32=link.exe
""" + mkFlags('ADD','LINK32 %s /nologo %s' % (cfg.__ldlibs, cfg.__ldflags)) + """\

""")
    dsp += '!IF' + '!ELSEIF'.join(flags) + '!ENDIF'

    dsp += '\n\n# Begin Target\n\n'

    # Output list of configs one more:
    for c in t.configs:
        dsp += '# Name "%s"\n' % mkConfigName(t.id, c)
    
    # Write source files:

    # (find files from all configs, identify files not in all configs)
    sources = {}
    for c in t.configs:
        for s in t.configs[c].__sources.split():
            if s not in sources:
                sources[s] = [c]
            else:
                sources[s].append(c)
    for s in sources:
        if len(sources[s]) == len(t.configs):
            sources[s] = None

    # (sort the files into groups)
    groups = ['Source Files', 'Header Files', 'Resource Files']
    group_defs = {
        'Source Files'   : '*.cpp *.c *.cxx *.rc *.def *.r *.odl *.idl *.hpj *.bat',
        'Header Files'   : '*.h *.hpp *.hxx *.hm *.inl',
        'Resource Files' : '*.ico *.cur *.bmp *.dlg *.rc2 *.rct *.bin *.rgs *.gif *.jpg *.jpeg *.jpe',
    }
    files = filterGroups(groups, group_defs, sources.keys())

    # (write them)
    for group in files:
        lst = files[group]
        if len(lst) == 0: continue
        if group != None:
            dsp += """\
# Begin Group "%s"

# PROP Default_Filter ""
""" % group
        for src in lst:
            dsp += """\
# Begin Source File

SOURCE=%s
""" % src
            if sources[src] != None:
                # the file is disabled in some configurations:
                flags = []
                for c in t.configs:
                    if c in sources[src]:
                        file_flags = ''
                    else:
                        file_flags = '\n# PROP Exclude_From_Build 1\n'
                    flags.append('  "$(CFG)" == "%s"' % mkConfigName(t.id, c) +
                                 '\n' + file_flags + '\n')
                dsp += '\n!IF' + '!ELSEIF'.join(flags) + '!ENDIF\n\n'
            dsp += '# End  Source File\n'
        if group != None:
            dsp += '# End Group\n'

    # Write footer:
    dsp += """\
# End Target
# End Project
"""

    writer.writeFile(filename, dsp)

genDSW()
