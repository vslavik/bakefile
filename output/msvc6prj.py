# MS Visual C++ projects generator script
# $Id$

basename = os.path.splitext(os.path.basename(FILE))[0]
dirname = os.path.dirname(FILE)

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

CFG=%s - %s
""" % (t.id, t.__type, t.__type_code, t.id, default_cfg)
    dsp += """\
!MESSAGE This is not a valid makefile. To build this project using NMAKE,
!MESSAGE use the Export Makefile command and run
!MESSAGE 
!MESSAGE NMAKE /f "%s.mak".
!MESSAGE 
!MESSAGE You can specify a configuration when running NMAKE
!MESSAGE by defining the macro CFG on the command line. For example:
!MESSAGE 
!MESSAGE NMAKE /f "%s.mak" CFG="%s - %s"
!MESSAGE 
!MESSAGE Possible choices for configuration are:
!MESSAGE 
""" % (prjname, prjname, t.id, default_cfg)
    for c in t.configs:
        dsp += '!MESSAGE "%s - %s" (based on %s)\n' % (t.id, c, t.configs[c].__type)
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
        flags.append('  "$(CFG)" == "%s - %s"' % (t.id, c) + '\n\n' +
                mkFlags('PROP',"""\
Use_MFC 0
Use_Debug_Libraries """ + cfg.__debug + """
Output_Dir "%s"
Intermediate_Dir "%s\\%s"
Target_Dir ""
""" % (cfg.__targetdir, cfg.__builddir, t.id)) + """\
# ADD BASE CPP /nologo /W3 /GX /O2 /D "WIN32" /D "NDEBUG" /D "_CONSOLE" /D "_MBCS" /Yu"stdafx.h" /FD /c
# ADD CPP /nologo /W3 /GX /O2 /D "WIN32" /D "NDEBUG" /D "_CONSOLE" /D "_MBCS" /Yu"stdafx.h" /FD /c
# ADD BASE RSC /l 0x405 /d "NDEBUG"
# ADD RSC /l 0x405 /d "NDEBUG"
BSC32=bscmake.exe
# ADD BASE BSC32 /nologo
# ADD BSC32 /nologo
LINK32=link.exe
# ADD BASE LINK32 kernel32.lib user32.lib gdi32.lib winspool.lib comdlg32.lib advapi32.lib shell32.lib ole32.lib oleaut32.lib uuid.lib odbc32.lib odbccp32.lib  kernel32.lib user32.lib gdi32.lib winspool.lib comdlg32.lib advapi32.lib shell32.lib ole32.lib oleaut32.lib uuid.lib odbc32.lib odbccp32.lib /nologo /subsystem:console /machine:I386
# ADD LINK32 kernel32.lib user32.lib gdi32.lib winspool.lib comdlg32.lib advapi32.lib shell32.lib ole32.lib oleaut32.lib uuid.lib odbc32.lib odbccp32.lib  kernel32.lib user32.lib gdi32.lib winspool.lib comdlg32.lib advapi32.lib shell32.lib ole32.lib oleaut32.lib uuid.lib odbc32.lib odbccp32.lib /nologo /subsystem:console /machine:I386

""")
    dsp += '!IF' + '!ELSEIF'.join(flags) + '!ENDIF'

    print dsp
    writer.writeFile(filename, dsp)

genDSW()
