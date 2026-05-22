[Setup]
AppName=Jhatpat Downloader
AppVersion=5.8
AppPublisher=Kakdamba
DefaultDirName={pf}\Jhatpat Downloader
DefaultGroupName=Jhatpat Downloader
UninstallDisplayIcon={app}\JhatpatDownloader_v5.8.exe
Compression=lzma2
SolidCompression=yes
OutputDir=InstallerOutput
OutputBaseFilename=JhatpatDownloader_v5.8_Setup
SetupIconFile=D:\Vibe Code\Jhatpat Softwear\MyDownloader\icon.ico
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main Executable
Source: "D:\Vibe Code\Jhatpat Softwear\MyDownloader\dist\JhatpatDownloader_v5.8.exe"; DestDir: "{app}"; Flags: ignoreversion

; App Icon
Source: "D:\Vibe Code\Jhatpat Softwear\MyDownloader\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

; FFmpeg Folder (Copy everything inside ffmpeg to a subfolder named ffmpeg)
Source: "D:\Vibe Code\Jhatpat Softwear\MyDownloader\ffmpeg\*"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion recursesubdirs createallsubdirs

; Jhatpat Scout Extension Folder (Copy everything inside Jhatpat_Scout to a subfolder named Jhatpat_Scout)
Source: "D:\Vibe Code\Jhatpat Softwear\MyDownloader\Jhatpat_Scout\*"; DestDir: "{app}\Jhatpat_Scout"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Jhatpat Downloader"; Filename: "{app}\JhatpatDownloader_v5.8.exe"; IconFilename: "{app}\icon.ico"
Name: "{commondesktop}\Jhatpat Downloader"; Filename: "{app}\JhatpatDownloader_v5.8.exe"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\JhatpatDownloader_v5.8.exe"; Description: "{cm:LaunchProgram,Jhatpat Downloader}"; Flags: nowait postinstall skipifsilent
