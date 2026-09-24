# 考试试卷生成系统 —— 打包脚本
#
# 用法（在项目根目录执行）：
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -SkipInstaller
#
# 产出：
#   dist\ExamPaperGenerator\            onedir 产物，双击其中的 exe 即可运行
#   dist\考试试卷生成系统-1.0.0-安装包.exe   Inno Setup 安装包（需已安装 Inno Setup 6）

[CmdletBinding()]
param(
    [switch]$SkipInstaller,   # 只构建 onedir，不生成安装包
    [switch]$SkipSelfTest     # 跳过打包后的冒烟自检
)

$ErrorActionPreference = 'Stop'

$PackagingDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot  = Split-Path -Parent $PackagingDir
Set-Location $ProjectRoot

$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) {
    throw "找不到虚拟环境解释器：$Python`n请先运行：python -m venv .venv"
}

function Write-Step($text) {
    Write-Host ""
    Write-Host "── $text " -ForegroundColor Cyan -NoNewline
    Write-Host ("─" * [Math]::Max(0, 50 - $text.Length)) -ForegroundColor DarkGray
}

# ── 1. 构建 onedir ──────────────────────────────────────────────────────
Write-Step "PyInstaller 构建 (onedir)"
& $Python -m PyInstaller --noconfirm --clean `
    --distpath dist --workpath build `
    (Join-Path $PackagingDir 'exam.spec')
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 构建失败" }

$BundleDir = Join-Path $ProjectRoot 'dist\ExamPaperGenerator'
$ExePath   = Join-Path $BundleDir 'ExamPaperGenerator.exe'
if (-not (Test-Path $ExePath)) { throw "未找到产物：$ExePath" }

$SizeMiB = [Math]::Round((Get-ChildItem $BundleDir -Recurse -File |
    Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host "  onedir 体积: $SizeMiB MiB" -ForegroundColor Green

# ── 2. 打包后冒烟自检 ───────────────────────────────────────────────────
# 关键：有些依赖只在运行时的冷路径上才被 import（例如 openpyxl 会 import
# numpy），开发机上的单元测试跑不到 —— 必须在**真实产物**上验一遍。
if (-not $SkipSelfTest) {
    Write-Step "打包产物冒烟自检"
    $Report = Join-Path $env:TEMP 'exampaper_selftest.txt'
    Remove-Item $Report -ErrorAction SilentlyContinue
    $env:EXAM_SELFTEST = $Report

    # 必须用 Start-Process -Wait：本程序是 GUI 应用（console=False），
    # PowerShell 用 & 调用 GUI 程序不会等待，报告来不及生成就返回了。
    $proc = Start-Process -FilePath $ExePath -Wait -PassThru
    $code = $proc.ExitCode
    Remove-Item Env:\EXAM_SELFTEST -ErrorAction SilentlyContinue

    if (Test-Path $Report) {
        Get-Content $Report -Encoding UTF8 | ForEach-Object { Write-Host "  $_" }
    } else {
        Write-Host "  自检没有生成报告文件" -ForegroundColor Red
        $code = 1
    }
    if ($code -ne 0) { throw "打包自检未通过（报告：$Report）" }
    Write-Host "  自检全部通过" -ForegroundColor Green
}

# ── 3. Inno Setup 安装包 ────────────────────────────────────────────────
if ($SkipInstaller) {
    Write-Host ""
    Write-Host "已跳过安装包生成。产物目录：$BundleDir" -ForegroundColor Yellow
    return
}

Write-Step "Inno Setup 安装包"

$Candidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe"
)
$Iscc = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Iscc) {
    Write-Host "  未找到 Inno Setup 编译器 (ISCC.exe)。" -ForegroundColor Yellow
    Write-Host "  请从 https://jrsoftware.org/isdl.php 安装 Inno Setup 6 后重跑，" -ForegroundColor Yellow
    Write-Host "  或安装完成后手动编译：packaging\installer.iss" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  onedir 产物已可用，可直接分发：$BundleDir" -ForegroundColor Green
    return
}

& $Iscc (Join-Path $PackagingDir 'installer.iss')
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 编译失败" }

$Installer = Get-ChildItem (Join-Path $ProjectRoot 'dist') -Filter 'ExamPaperGenerator-*-setup.exe' |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($Installer) {
    $Mb = [Math]::Round($Installer.Length / 1MB, 1)
    Write-Host ""
    Write-Host "  安装包: $($Installer.FullName)  ($Mb MiB)" -ForegroundColor Green
}
