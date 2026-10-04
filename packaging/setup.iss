; Inno Setup script for NOVA-Legenden. Build: iscc /DAppVersion=0.1.0 packaging\setup.iss
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6C1C3E0B-7E2A-4B8D-9E55-3F1B7A1D4C20}
AppName=NOVA-Legenden
AppVersion={#AppVersion}
AppPublisher=edeco
DefaultDirName={localappdata}\Programs\NOVA-Legenden
DefaultGroupName=NOVA-Legenden
DisableProgramGroupPage=yes
; Install per user: no administrator rights needed
PrivilegesRequired=lowest
OutputDir=..\dist-installer
OutputBaseFilename=NOVA-Legenden-Setup-{#AppVersion}
SetupIconFile=app.ico
UninstallDisplayIcon={app}\NOVA-Legenden.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Symbol auf dem Desktop anlegen"; GroupDescription: "Zusätzliche Symbole:"

[Files]
Source: "..\dist\NOVA-Legenden\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\NOVA-Legenden"; Filename: "{app}\NOVA-Legenden.exe"
Name: "{userdesktop}\NOVA-Legenden"; Filename: "{app}\NOVA-Legenden.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\NOVA-Legenden.exe"; Description: "NOVA-Legenden jetzt starten"; Flags: nowait postinstall skipifsilent
; After a silent update started from the program: restart it
Filename: "{app}\NOVA-Legenden.exe"; Flags: nowait; Check: WizardSilent
