; Clipper – Inno Setup installer script
; Build with: iscc clipper_installer.iss
; Requires: PyInstaller output in dist\Clipper\

#define AppName      "Clipper"
#define AppVersion   "1.0.0"
#define AppPublisher "Clipper"
#define AppExeName   "Clipper.exe"

[Setup]
AppId={{A3F2B8C1-4D7E-4F9A-B1C2-D3E4F5A6B7C8}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=installer_output
OutputBaseFilename=ClipperInstaller-v{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Uncomment if you add clipper.ico to the project root:
; SetupIconFile=clipper.ico
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; Include everything PyInstaller produced
Source: "dist\Clipper\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";       Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall Clipper"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
