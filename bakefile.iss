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



[Files]
Source: src\*; DestDir: {app}\src; Flags: recursesubdirs; Components: base
Source: rules\*; DestDir: {app}\rules; Flags: recursesubdirs; Components: base
Source: output\*; DestDir: {app}\output; Flags: recursesubdirs; Components: base
Source: tests\*; DestDir: {app}\tests; Flags: recursesubdirs; Components: tests
Source: doc\*; DestDir: {app}\doc; Flags: recursesubdirs; Components: doc
Source: ..\minipython\*; DestDir: {app}; Flags: recursesubdirs; Components: base
Source: ..\minipython\scriptwrapper.exe; DestDir: {app}; DestName: bakefile.exe

[Registry]

[Icons]

[Run]

[_ISTool]
EnableISX=true
UseAbsolutePaths=false

[Dirs]

[_ISToolPreCompile]

[Components]
Name: base; Description: Required files; Flags: fixed; Types: custom compact full
Name: doc; Description: Documentation; Types: custom full
Name: tests; Description: Tests and examples; Types: custom full

[Messages]
BeveledLabel=Bakefile

[UninstallDelete]
Name: {app}\src; Type: filesandordirs
