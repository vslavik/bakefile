; This script was first created by ISTool
; http://www.lerstad.com/istool/

#define VERSION          "0.1.1"

[Setup]
OutputBaseFilename=bakefile-{#VERSION}-setup
AppName=Bakefile
AppVerName=Bakefile {#VERSION}

ChangesAssociations=false
AlwaysShowComponentsList=true
SourceDir=.
DefaultDirName={pf}\Bakefile

DefaultGroupName=Bakefile
AllowNoIcons=true
DisableAppendDir=false
UninstallStyle=modern
WizardStyle=modern

OutputDir=.

Compression=bzip

WindowShowCaption=true
WindowStartMaximized=false
FlatComponentsList=true
WindowResizable=false
ShowTasksTreeLines=false
DisableProgramGroupPage=true
LicenseFile=COPYING



[Files]
Source: src\*; DestDir: {app}\src; Flags: recursesubdirs; Components: base
Source: rules\*; DestDir: {app}\rules; Flags: recursesubdirs; Components: base
Source: output\*; DestDir: {app}\output; Flags: recursesubdirs; Components: base
Source: tests\*; DestDir: {app}\tests; Flags: recursesubdirs; Components: tests
Source: doc\*; DestDir: {app}\doc; Flags: recursesubdirs; Components: doc
Source: ..\minipython\*; DestDir: {app}\src; Flags: recursesubdirs; Components: python
Source: README; DestDir: {app}; Components: base
Source: THANKS; DestDir: {app}; Components: base
Source: COPYING; DestDir: {app}; Components: base
Source: AUTHORS; DestDir: {app}; Components: base

[Registry]

[Icons]

[Run]

[_ISTool]
EnableISX=true
UseAbsolutePaths=false

[Dirs]

[_ISToolPreCompile]

[Components]
Name: base; Description: Bakefile code; Flags: fixed; Types: custom compact full
Name: python; Description: Python runtime; Flags: fixed; Types: custom compact full
Name: doc; Description: Documentation; Types: custom full
Name: tests; Description: Tests and examples; Types: custom full

[Messages]
BeveledLabel=Bakefile

[UninstallDelete]
Name: {app}\src; Type: filesandordirs
