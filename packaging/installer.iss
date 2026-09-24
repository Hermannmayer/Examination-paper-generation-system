; ============================================================================
; 考试试卷生成系统 —— Inno Setup 安装包脚本
; ============================================================================
;
; 用法：
;   1. 先跑 PyInstaller 生成 dist\ExamPaperGenerator\
;   2. 用 Inno Setup 6 编译本文件
;
; 关于向导语言：Inno 6 默认**不**附带中文语言文件（ChineseSimplified.isl
; 属于 Unofficial 下载）。为了让本脚本开箱即可编译，默认使用英文向导界面，
; 但应用名、快捷方式、安装目录都是中文。若要中文向导，见文件末尾的说明。
;
; WebView2：程序界面依赖 WebView2 运行时。Win11 必然自带；
; 绝大多数 Win10 也已具备。缺失时安装器会自动补装（需要联网），
; 因此离线部署请把 MicrosoftEdgeWebview2Setup.exe 放到 packaging\webview2\。

#define AppName "考试试卷生成系统"
#define AppVersion "1.0.0"
#define AppExe "ExamPaperGenerator.exe"
#define AppId "{{8F3A7C21-4B6D-4E52-9A18-5C2E7D91F0B4}"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
; 安装器自身的图标。可执行文件的图标由 PyInstaller 从 exam.spec 打进 exe，
; 快捷方式会自动沿用，所以这里只需管安装程序。
SetupIconFile=app.ico
OutputDir=..\dist
OutputBaseFilename={#AppName}-{#AppVersion}-安装包
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
DisableDirPage=no
AllowNoIcons=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; 声明需要已有 WebView2 才能"完全无感"运行，但缺失时由 [Run] 段补装
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："; Flags: unchecked

[Files]
; PyInstaller 产出的整个目录
Source: "..\dist\ExamPaperGenerator\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs
; WebView2 离线引导程序（可选：文件不存在时自动跳过）
Source: "webview2\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; \
    Flags: deleteafterinstall skipifsourcedoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; 仅在缺失且引导程序存在时补装 WebView2
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; \
    StatusMsg: "正在安装 WebView2 运行时（首次安装需要联网）…"; \
    Flags: waituntilterminated; Check: ShouldInstallWebView2
Filename: "{app}\{#AppExe}"; Description: "立即启动 {#AppName}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 安装器自身产生的日志之类，若有则一并清理
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
const
  WebView2ClientKey = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

{ 查询某个注册表位置下的 WebView2 版本号，没有则返回空串 }
function QueryWebView2Version(RootKey: Integer; const SubKey: String): String;
var
  Version: String;
begin
  Result := '';
  if RegQueryStringValue(RootKey, SubKey, 'pv', Version) then
    Result := Version;
end;

{ WebView2 运行时是否已安装（三处注册表任一命中即可）}
function WebView2Installed: Boolean;
begin
  Result :=
    (QueryWebView2Version(HKLM,
      'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WebView2ClientKey) <> '') or
    (QueryWebView2Version(HKLM,
      'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WebView2ClientKey) <> '') or
    (QueryWebView2Version(HKCU,
      'Software\Microsoft\EdgeUpdate\Clients\' + WebView2ClientKey) <> '');
end;

{ 缺运行时 **且** 离线引导程序确实随包提供了，才去补装 }
function ShouldInstallWebView2: Boolean;
begin
  Result := (not WebView2Installed) and
            FileExists(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'));
end;

{ 装完后若 WebView2 仍缺失，给出可操作的提示而不是让用户对着白屏发呆 }
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not WebView2Installed) then
  begin
    if MsgBox('未检测到 WebView2 运行时，程序界面可能无法显示。' + #13#10 +
              '可从 Microsoft 官网下载安装后重试：' + #13#10 +
              'https://developer.microsoft.com/microsoft-edge/webview2/' + #13#10#13#10 +
              '是否现在打开该下载页面？', mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://developer.microsoft.com/microsoft-edge/webview2/',
                '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
  end;
end;

{ ============================================================================
  想要中文向导界面？
  1. 从 https://jrsoftware.org/files/istrans/ 下载 ChineseSimplified.isl
  2. 放到 Inno Setup 安装目录的 Languages\ 子目录下
  3. 在本文件 [Setup] 段之后加上：

     [Languages]
     Name: "chinese"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

  未加是因为该文件不随 Inno 6 默认分发，直接引用会导致编译失败。
  ============================================================================ }
