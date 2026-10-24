; Inno Setup script: built by .github/workflows/release.yml (iscc /DAppVersion=x.y.z installer\wva.iss)
; Per-user install, no admin prompt. Updates run this same installer silently.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{8C2B6E4E-5D0B-4D7E-9F3B-6A1E2C9D4F10}
AppName=Windows Voice Agent
AppVersion={#AppVersion}
AppVerName=Windows Voice Agent {#AppVersion}
AppPublisher=Windows Voice Agent
AppPublisherURL=https://github.com/SuckerForTrouble/windows-voice-agent
DefaultDirName={localappdata}\Programs\Windows Voice Agent
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=WindowsVoiceAgent-Setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\WindowsVoiceAgent.exe
UninstallDisplayName=Windows Voice Agent
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Messages]
WelcomeLabel2=WARNING: this app is completely vibe coded. An AI wrote it and only a very small part of it has been reviewed by a human. It can close apps, press keys and shut down Windows when asked. Install it entirely at your own risk.%n%nThis installs Windows Voice Agent: hold F9, say what you want, let go. After installing it downloads its speech model once (about 550 MB), then shows a setup check and the list of things you can say.

[Tasks]
Name: "desktopicon"; Description: "Put a shortcut on the Desktop"; Flags: unchecked

[InstallDelete]
; old program files go first, so nothing from a previous version lingers (your settings live elsewhere)
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\whisper"
Type: filesandordirs; Name: "{app}\helpers"

[Files]
Source: "..\dist\WindowsVoiceAgent\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Windows Voice Agent"; Filename: "{app}\WindowsVoiceAgent.exe"
Name: "{autodesktop}\Windows Voice Agent"; Filename: "{app}\WindowsVoiceAgent.exe"; Tasks: desktopicon

[Registry]
; start with Windows (the tray menu can turn it off)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "WindowsVoiceAgent"; ValueData: """{app}\WindowsVoiceAgent.exe"""; Flags: uninsdeletevalue

[Run]
Filename: "{app}\WindowsVoiceAgent.exe"; Description: "Start Windows Voice Agent now"; Flags: nowait postinstall

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im WindowsVoiceAgent.exe"; Flags: runhidden; RunOnceId: "StopAgent"
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im whisper-server.exe"; Flags: runhidden; RunOnceId: "StopWhisper"
