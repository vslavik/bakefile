# MS eMbedded Visual C++ projects generator script
# $Id$

import msvc6prj
from msvc6prj import ProjectGeneratorMsvc6

class ProjectGeneratorEvc4(ProjectGeneratorMsvc6):
    
    # --------------------------------------------------------------------
    #   basic configuration
    # --------------------------------------------------------------------

    def getDswExtension(self):
        return 'vcw'
    def getDspExtension(self):
        return 'vcp'
    def getMakefileExtension(self):
        return 'vcn'
   

    def makeDswHeader(self):
        return """\
Microsoft eMbedded Visual Tools Workspace File, Format Version 4.00
# WARNING: DO NOT EDIT OR DELETE THIS WORKSPACE FILE!

###############################################################################
"""
    
    def makeDspHeader(self, id):
        return """\
# Microsoft eMbedded Visual Tools Project File - Name="%s" - Package Owner=<4>
# Microsoft eMbedded Visual Tools Generated Build File, Format Version 6.02
# ** DO NOT EDIT **

""" % id
    
    def makeBeginProject(self, t):
        return """\
# PROP AllowPerConfigDependencies 0
# PROP Scc_ProjName ""
# PROP Scc_LocalPath ""
# PROP ATL_Project 2
"""
    
    def makeCpuPlatformID(self, cfg):
        return """\
CPU_ID "%s"
Platform_ID "{8A9A2F80-6887-11D3-842E-005004848CBA}"
""" % cfg._CPU_ID
    
    def makeSettingsCPP(self, cfg):
        return ('CPP=%s\n' % cfg._COMPILER + 
                ProjectGeneratorMsvc6.makeSettingsCPP(self, cfg))

    def makeSettingsMTL(self, cfg):
        return ('MTL=midl.exe\n' + 
                self.mkFlags('ADD',
                             'MTL /nologo %s /mktyplib203 /o "NUL" /win32' % cfg._defines))

    def makeSettingsRSC(self, cfg):
        return ('RSC=rc.exe\n' +
                self.mkFlags('ADD', 'RSC %s /r' % cfg._win32rc_flags))

    def makeSettingsCPP_MTL_RSC(self, cfg):
        txt = self.makeSettingsRSC(cfg)
        txt += self.makeSettingsCPP(cfg)
        if cfg._type_nick in ['gui','dll']:
            txt += self.makeSettingsMTL(cfg)
        return txt

def run():
    msvc6prj.__dict__.update(globals())
    generator = ProjectGeneratorEvc4()
    generator.genWorkspaces()
