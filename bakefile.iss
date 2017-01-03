; This script was first created by ISTool
; http://www.lerstad.com/istool/

#define VERSION          "0.2.9.1"

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

OutputDir=.

Compression=lzma/ultra64

WindowShowCaption=true
WindowStartMaximized=false
FlatComponentsList=true
WindowResizable=false
ShowTasksTreeLines=false
DisableProgramGroupPage=true
LicenseFile=COPYING
SolidCompression=true
InternalCompressLevel=ultra64
ShowLanguageDialog=no
VersionInfoVersion={#VERSION}
PrivilegesRequired=none
AppSupportURL=http://www.bakefile.org
AppUpdatesURL=http://www.bakefile.org/download.html
AppVersion={#VERSION}
AppID={{AD092360-A98A-4CDC-BDAA-5CB09C593AC2}
AppContact=http://www.bakefile.org/wiki
UninstallDisplayName=Bakefile
ChangesEnvironment=true
UninstallFilesDir={app}\uninst

[Files]
Source: bakefile.exe; DestDir: {app}; Components: base
Source: bakefile_gen.exe; DestDir: {app}; Components: base
Source: src\*.py; DestDir: {app}\src; Components: base
Source: src\*.pyd; DestDir: {app}\src; Components: base
Source: src\empy\*; DestDir: {app}\src\empy; Flags: recursesubdirs; Components: base
Source: autoconf\*; DestDir: {app}\autoconf; Flags: recursesubdirs; Components: base
Source: rules\*; DestDir: {app}\rules; Flags: recursesubdirs; Components: base
Source: presets\*; DestDir: {app}\presets; Flags: recursesubdirs; Components: base
Source: output\*; DestDir: {app}\output; Flags: recursesubdirs; Components: base
Source: tests\*; DestDir: {app}\tests; Flags: recursesubdirs; Components: tests
Source: schema\*; DestDir: {app}\schema; Flags: recursesubdirs; Components: base
Source: doc\html\*; DestDir: {app}\doc; Flags: recursesubdirs; Components: doc
Source: py-runtime\*; DestDir: {app}; Flags: recursesubdirs; Components: python
Source: README; DestDir: {app}; Components: base
Source: NEWS; DestDir: {app}; Components: base; AfterInstall: InstallSetupPath
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

[InstallDelete]
; these are deprecated files from older Bakefile versions; some of
; them are just useless junk, some (datafiles, gettext) would cause
; conflicts and break Bakefile
Name: {app}\rules\datafiles.bkl; Type: files
Name: {app}\rules\gettext; Type: filesandordirs
Name: {app}\src\bakefile.exe; Type: files
Name: {app}\src\bakefile_gen.exe; Type: files
Name: {app}\src\python*; Type: files
Name: {app}\src\w9xpopen.exe; Type: files
Name: {app}\src\lib; Type: filesandordirs
Name: {app}\src\DLLs; Type: filesandordirs
Name: {app}\src\py25modules; Type: filesandordirs

[UninstallDelete]
Name: {app}\src; Type: filesandordirs
Name: {app}\output; Type: filesandordirs
Name: {app}\lib; Type: filesandordirs

[Tasks]
Name: addpath; Description: Add Bakefile to PATH environment variable; Flags: checkedonce

[Code]
// -----------------------------------------------------------------
//                    code for changing PATH
// -----------------------------------------------------------------

//
// Inno Setup Extensions Knowledge Base
// Article 44 - Native ISX procedures for PATH modification
// http://www13.brinkster.com/vincenzog/isxart.asp?idart=44
// Author: Thomas Vedel
//

// Version log:
// 03/31/2003: Initial release (thv@lr.dk)

const
  // Modification method
  pmAddToBeginning = $1;      // Add dir to beginning of Path
  pmAddToEnd = $2;            // Add dir to end of Path
  pmAddAllways = $4;          // Add also if specified dir is already included in existing path
  pmAddOnlyIfDirExists = $8;  // Add only if specified dir actually exists
  pmRemove = $10;             // Remove dir from path
  pmRemoveSubdirsAlso = $20;  // Remove dir and all subdirs from path

  // Scope
  psCurrentUser = 1;          // Modify path for current user
  psAllUsers = 2;             // Modify path for all users

  // Error results
  mpOK = 0;                   // No errors
  mpMissingRights = -1;       // User has insufficient rights
  mpAutoexecNoWriteacc = -2;  // Autoexec can not be written (may be readonly)
  mpBothAddAndRemove = -3;    // User has specified that dir should both be removed from and added to path


{ Helper procedure: Split a path environment variable into individual dirnames }
procedure SplitPath(Path: string; var Dirs: TStringList);
var
  pos: integer;
  s: string;
begin
  Dirs.Clear;
  s := '';
  pos := 1;
  while (pos<=Length(Path)) do
  begin
    if (Path[pos]<>';') then
      s := s + Path[pos];
    if ((Path[pos]=';') or (pos=Length(Path))) then
    begin
      s := Trim(s);
      s := RemoveQuotes(s);
      s := Trim(s);
      if (s <> '') then
        Dirs.Add(s);
      s := '';
    end;
    Pos := Pos + 1;
  end;
end; // procedure SplitPath


{ Helper procedure: Concatenate individual dirnames into a path environment variable }
procedure ConcatPath(Dirs: TStringList; Quotes: boolean; var Path: string);
var
  Index, MaxIndex: integer;
  s: string;
begin
  MaxIndex := Dirs.Count-1;
  Path := '';
  for Index := 0 to MaxIndex do
  begin
    s := Dirs.Strings[Index];
    if ((Quotes) and (pos(' ',s) > 0)) then
      s := AddQuotes(s);
    Path := Path + s;
    if (Index < MaxIndex) then
      Path := Path + ';'
  end;
end; // procedure ConcatPath


{ Helper function: Modifies path environment string }
procedure ModifyPathString(OldPath, DirName: string; Method: integer; Quotes: boolean; var ResultPath: string);
var
  Dirs: TStringList;
  DirNotInPath: Boolean;
  i: integer;
begin
  // Create Dirs variable
  Dirs := TStringList.Create;

  // Remove quotes form DirName
  DirName := Trim(DirName);
  DirName := RemoveQuotes(DirName);
  DirName := Trim(DirName);

  // Split old path in individual directory names
  SplitPath(OldPath, Dirs);

  // Check if dir is allready in path
  DirNotInPath := True;
  for i:=Dirs.Count-1 downto 0 do
  begin
    if (uppercase(Dirs.Strings[i]) = uppercase(DirName)) then
      DirNotInPath := False;
  end;

  // Should dir be removed from existing Path?
  if ((Method and (pmRemove or pmRemoveSubdirsAlso)) > 0) then
  begin
    for i:=Dirs.Count-1 downto 0 do
    begin
      if (((Method and pmRemoveSubdirsAlso) > 0) and (pos(uppercase(DirName)+'\', uppercase(Dirs.Strings[i])) = 1)) or
         (((Method and (pmRemove) or (pmRemoveSubdirsAlso)) > 0) and (uppercase(DirName) = uppercase(Dirs.Strings[i])))
      then
        Dirs.Delete(i);
    end;
  end;

  // Should dir be added to existing Path?
  if ((Method and (pmAddToBeginning or pmAddToEnd)) > 0) then
  begin
    // Add dir to path
    if (((Method and pmAddAllways) > 0) or DirNotInPath) then
    begin
      // Dir is not in path allready or should be added anyway
      if (((Method and pmAddOnlyIfDirExists) = 0) or (DirExists(DirName))) then
      begin
        // Dir actually exsists or should be added anyway
        if ((Method and pmAddToBeginning) > 0) then
          Dirs.Insert(0, DirName)
        else
          Dirs.Append(DirName);
      end;
    end;
  end;

  // Concatenate directory names into one single path variable
  ConcatPath(Dirs, Quotes, ResultPath);
  // Finally free Dirs object
  Dirs.Free;
end; // ModifyPathString


{ Helper function: Modify path on Windows 9x }
function ModifyPath9x(DirName: string; Method: integer): integer;
var
  AutoexecLines: TStringList;
  ActualLine: String;
  PathLineNos: TStringList;
  FirstPathLineNo: Integer;
  OldPath, ResultPath: String;
  LineNo, CharNo, Index: integer;

  TempString: String;
begin
  // Expect everything to be OK
  result := mpOK;

  // Create stringslists
  AutoexecLines := TStringList.Create;
  PathLineNos := TStringList.Create;

  // Read existing path
  OldPath := '';
  LoadStringFromFile('c:\Autoexec.bat', TempString);
  AutoexecLines.Text := TempString;
  PathLineNos.Clear;
  // Read Autoexec line by line
  for LineNo := 0 to AutoexecLines.Count - 1 do begin
    ActualLine := AutoexecLines.Strings[LineNo];
    // Check if line starts with "PATH=" after first stripping spaces and other "fill-chars"
    if Pos('=', ActualLine) > 0 then
    begin
      for CharNo := Pos('=', ActualLine)-1 downto 1 do
        if (ActualLine[CharNo]=' ') or (ActualLine[CharNo]=#9) then
          Delete(ActualLine, CharNo, 1);
      if Pos('@', ActualLine) = 1 then
        Delete(ActualLine, 1, 1);
      if (Pos('PATH=', uppercase(ActualLine))=1) or (Pos('SETPATH=', uppercase(ActualLine))=1) then
      begin
        // Remove 'PATH=' and add path to "OldPath" variable
        Delete(ActualLine, 1, pos('=', ActualLine));
        // Check if an earlier PATH variable is referenced, but there has been no previous PATH defined in Autoexec
        if (pos('%PATH%',uppercase(ActualLine))>0) and (PathLineNos.Count=0) then
          OldPath := ExpandConstant('{win}') + ';' + ExpandConstant('{win}')+'\COMMAND';
        if (pos('%PATH%',uppercase(ActualLine))>0) then
        begin
          ActualLine := Copy(ActualLine, 1, pos('%PATH%',uppercase(ActualLine))-1) +
                        OldPath +
                        Copy(ActualLine, pos('%PATH%',uppercase(ActualLine))+6, Length(ActualLine));
        end;
        OldPath := ActualLine;

        // Update list of line numbers holding path variables
        PathLineNos.Add(IntToStr(LineNo));
      end;
    end;
  end;

  // Save first line number in Autoexec.bat which modifies path environment variable
  if PathLineNos.Count > 0 then
    FirstPathLineNo := StrToInt(PathLineNos.Strings[0])
  else
    FirstPathLineNo := 0;

  // Modify path
  ModifyPathString(OldPath, DirName, Method, True, ResultPath);

  // Write Modified path back to Autoexec.bat
  // First delete all existing path references from Autoexec.bat
  Index := PathLineNos.Count-1;
  while (Index>=0) do
  begin
    AutoexecLines.Delete(StrToInt(PathLineNos.Strings[Index]));
    Index := Index-1;
  end;
  // Then insert new path variable into Autoexec.bat
  AutoexecLines.Insert(FirstPathLineNo, '@PATH='+ResultPath);
  // Delete old Autoexec.bat from disk
  if not DeleteFile('c:\Autoexec.bat') then
    result := mpAutoexecNoWriteAcc;
  Sleep(500);
  // And finally write Autoexec.bat back to disk
  if not (result=mpAutoexecNoWriteAcc) then
    SaveStringToFile('c:\Autoexec.bat', AutoexecLines.Text, false);

  // Free stringlists
  PathLineNos.Free;
  AutoexecLines.Free;
end; // ModifyPath9x


{ Helper function: Modify path on Windows NT, 2000 and XP }
function ModifyPathNT(DirName: string; Method, Scope: integer): integer;
var
  RegRootKey: integer;
  RegSubKeyName: string;
  RegValueName: string;
  OldPath, ResultPath: string;
  OK: boolean;
begin
  // Expect everything to be OK
  result := mpOK;

  // Initialize registry key and value names to reflect if changes should be global or local to current user only
  case Scope of
    psCurrentUser:
      begin
        RegRootKey := HKEY_CURRENT_USER;
        RegSubKeyName := 'Environment';
        RegValueName := 'Path';
      end;
    psAllUsers:
      begin
        RegRootKey := HKEY_LOCAL_MACHINE;
        RegSubKeyName := 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';
        RegValueName := 'Path';
      end;
  end;

  // Read current path value from registry
  OK := RegQueryStringValue(RegRootKey, RegSubKeyName, RegValueName, OldPath);
  if not OK then
  begin
    result := mpMissingRights;
    Exit;
  end;

  // Modify path
  ModifyPathString(OldPath, DirName, Method, False, ResultPath);

  // Write new path value to registry
  if not RegWriteStringValue(RegRootKey, RegSubKeyName, RegValueName, ResultPath) then
  begin
    result := mpMissingRights;
    Exit;

  end;
end; // ModifyPathNT


{ Main function: Modify path }
function ModifyPath(Path: string; Method, Scope: integer): integer;
begin
  // Check if both add and remove has been specified (= error!)
  if (Method and (pmAddToBeginning or pmAddToEnd) and (pmRemove or pmRemoveSubdirsAlso)) > 0 then
  begin
    result := mpBothAddAndRemove;
    Exit;
  end;

  // Perform directory constant expansion
  Path := ExpandConstantEx(Path, ' ', ' ');

  // Test if Win9x
  if InstallOnThisVersion('4,0','0,0') = irInstall then
    ModifyPath9x(Path, Method);

  // Test if WinNT, 2000 or XP
  if InstallOnThisVersion('0,4','0,0') = irInstall then
    ModifyPathNT(Path, Method, Scope);
end; // ModifyPath




// -----------------------------------------------------------------
//                     install script hooks
// -----------------------------------------------------------------

procedure SetupPATH;
var
  p : string;
  scope : integer;
begin
  p:= ExpandConstant('{app}');
  if IsAdminLoggedOn then
    scope:= psAllUsers
  else
    scope:= psCurrentUser;
  ModifyPath(p, pmAddToEnd, scope);
end;

procedure InstallSetupPath;
begin
    if IsTaskSelected('addpath') then
		SetupPATH;
end;
