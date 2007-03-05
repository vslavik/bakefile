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
#  MS eMbedded Visual C++ projects generator script
#

import msvc6prj, msvc_common
from msvc6prj import ProjectGeneratorMsvc6

class ProjectGeneratorEvc4(ProjectGeneratorMsvc6):
    
    # --------------------------------------------------------------------
    #   basic configuration
    # --------------------------------------------------------------------

    def getSolutionExtension(self):
        return 'vcw'
    def getProjectExtension(self):
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

    def makeSettingsCPP_MTL_RSC_BSC_LINK(self, cfg):
        txt = ''
        if cfg._type_nick in ['gui','dll']:
            txt += self.makeSettingsRSC(cfg)
        txt += self.makeSettingsCPP(cfg)
        if cfg._type_nick in ['gui','dll']:
            txt += self.makeSettingsMTL(cfg)
        if cfg._type_nick != 'lib':
            txt += self.makeSettingsBSC(cfg)
            txt += self.makeSettingsLINK(cfg)
        else:
            txt += self.makeSettingsLIB(cfg)
            txt += self.makeSettingsBSC(cfg)
        return txt

def run():
    msvc_common.__dict__.update(globals())
    msvc6prj.__dict__.update(globals())
    generator = ProjectGeneratorEvc4()
    generator.genWorkspaces()
