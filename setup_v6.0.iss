[Setup]
AppName=Jhatpat Downloader
AppVersion=5.9
AppPublisher=Kakdamba
AppPublisherURL=https://github.com/kakdamba/Jhatpat-Downloader
AppSupportURL=https://github.com/kakdamba/Jhatpat-Downloader
AppUpdatesURL=https://github.com/kakdamba/Jhatpat-Downloader
DefaultDirName={pf}\Jhatpat Downloader
DefaultGroupName=Jhatpat Downloader
UninstallDisplayIcon={app}\icon.ico
ArchitecturesInstallIn64BitMode=x64
Compression=lzma2
SolidCompression=yes
OutputDir=InstallerOutput
OutputBaseFilename=JhatpatDownloader_v6.0_Setup
SetupIconFile=icon.ico

[Files]
Source: "dist\JhatpatDownloader_v6.0.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "ffmpeg\*"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Jhatpat_Scout\*"; DestDir: "{app}\Jhatpat_Scout"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Jhatpat Downloader"; Filename: "{app}\JhatpatDownloader_v6.0.exe"; IconFilename: "{app}\icon.ico"
Name: "{commondesktop}\Jhatpat Downloader"; Filename: "{app}\JhatpatDownloader_v6.0.exe"; IconFilename: "{app}\icon.ico"

[Run]
Filename: "{app}\JhatpatDownloader_v6.0.exe"; Description: "Launch Jhatpat Downloader"; Flags: nowait postinstall skipifsilent
