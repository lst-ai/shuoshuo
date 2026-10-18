; Inno Setup 安裝檔設定（GitHub Actions 會自動編譯）
#define AppVer GetEnv("APP_VERSION")
#if AppVer == ""
  #define AppVer "0.1.0"
#endif

[Setup]
AppId={{6B1F2E4A-5C3D-4E8F-9A10-5A0D0C5E7B21}
AppName=說說
AppVersion={#AppVer}
AppPublisher=雲林縣數位學習推動辦公室
DefaultDirName={localappdata}\Programs\ShuoShuo
DefaultGroupName=說說
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer
OutputBaseFilename=ShuoShuo-Setup-{#AppVer}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\ShuoShuo.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑"; GroupDescription: "其他選項："
Name: "autostart"; Description: "開機時自動啟動說說"; GroupDescription: "其他選項："

[Files]
Source: "dist\ShuoShuo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\說說"; Filename: "{app}\ShuoShuo.exe"
Name: "{group}\解除安裝說說"; Filename: "{uninstallexe}"
Name: "{userdesktop}\說說"; Filename: "{app}\ShuoShuo.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "ShuoShuo"; ValueData: """{app}\ShuoShuo.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\ShuoShuo.exe"; Description: "立即啟動說說"; Flags: nowait postinstall skipifsilent
