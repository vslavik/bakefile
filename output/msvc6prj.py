# MS Visual C++ projects generator script

basename = os.path.splitext(os.path.basename(FILE))[0]
dirname = os.path.dirname(FILE)

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


def genDSP(t, filename, prjname):
    default_cfg = t.configs.keys()[0]
    dsp = """\
# Microsoft Developer Studio Project File - Name="%s" - Package Owner=<4>
# Microsoft Developer Studio Generated Build File, Format Version 6.00
# ** DO NOT EDIT **

# TARGTYPE %s %s

CFG=%s
""" % (t.id, t.__type, t.__type_code, default_cfg)
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
""" % (prjname, prjname, default_cfg)
    for c in t.configs:
        dsp += '!MESSAGE "%s" (based on %s)\n' % (c, t.configs[c].__type)
    dsp += """\
!MESSAGE 

# Begin Project
# PROP AllowPerConfigDependencies 0
# PROP Scc_ProjName ""
# PROP Scc_LocalPath ""
CPP=cl.exe
RSC=rc.exe

"""
    dsp+='x'
    print dsp
    writer.writeFile(filename, dsp)

genDSW()
