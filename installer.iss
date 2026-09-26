[Setup]
AppName=EasyQuestUpdater
AppVersion=1.0
AppPublisher=MartinInMotion
AppPublisherURL=https://github.com/MPavion/EasyQuestUpdater
AppSupportURL=https://github.com/MPavion/EasyQuestUpdater/issues
AppUpdatesURL=https://github.com/MPavion/EasyQuestUpdater
DefaultDirName={autopf}\EasyQuestUpdater
DefaultGroupName=EasyQuestUpdater
OutputDir=installer
OutputBaseFilename=EasyQuestUpdater-Setup
SetupIconFile=icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\EasyQuestUpdater.exe
UninstallDisplayName=EasyQuestUpdater

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\EasyQuestUpdater.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\EasyQuestUpdater\EasyQuestUpdater"; Filename: "{app}\EasyQuestUpdater.exe"
Name: "{autoprograms}\EasyQuestUpdater\Uninstall EasyQuestUpdater"; Filename: "{uninstallexe}"
Name: "{autodesktop}\EasyQuestUpdater"; Filename: "{app}\EasyQuestUpdater.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\EasyQuestUpdater.exe"; Description: "Launch EasyQuestUpdater now"; Flags: nowait postinstall skipifsilent
