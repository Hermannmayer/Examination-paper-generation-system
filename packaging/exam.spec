# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（onedir）。

## 为什么用 onedir 而不是 onefile

实测启动耗时：onedir 约 0.5–0.9 秒，onefile 3–5 秒（慢约 6 倍）。
PyInstaller 官方文档说明了原因：onefile 每次启动都要把内容解压到
``_MEI{xxxxxx}`` 临时目录。

配合 Inno Setup 的 LZMA 压缩，onedir 同样能得到一个小体积的分发包，
且启动更快、杀软误报更少。

## 体积控制（实测）

site-packages 占用：pandas 60MB + numpy 31MB 是绝对主因。

**坑**：光删 ``import pandas`` 不够 —— openpyxl 自己会 import numpy
（``openpyxl/utils/dataframe.py``），所以必须显式 ``exclude`` numpy 与 pandas。
排除后 xlsx 读取仍然正常（有专门的回归测试覆盖）。
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ASSETS = os.path.join(PROJECT_ROOT, "ui", "assets")

# 这些体积大且本项目完全不用
EXCLUDES = [
    # 最大头：实测 91MB。
    # 注意：openpyxl 自己会 import numpy（openpyxl/utils/dataframe.py），
    # 所以光删 pandas 不够，必须把 numpy 一起排除。
    # 排除后 xlsx 读取仍正常 —— 已由 main.py 的打包自检在**产物上**验证。
    "numpy",
    "pandas",
    # 旧界面已删除，不再需要
    "tkinter",
    "_tkinter",
    # 科学计算 / 绘图 / 测试栈，一律不需要
    "matplotlib",
    "scipy",
    "IPython",
    "pytest",
    "setuptools",
    "pip",
    "pydoc_data",
    "test",
    "unittest",
    # reportlab 的可选绘图/编辑器组件
    "reportlab.graphics",

    # ── 以下**不能**排除，留作记录 ──────────────────────────────────
    # PIL / Pillow（约 10.4MB，其中 AVIF 编解码器单文件 7.5MB）：
    #   reportlab 在 reportlab/lib/utils.py 第 15 行就 `import PIL`，
    #   属于模块级硬依赖，排除后任何 PDF 渲染都会 ModuleNotFoundError。
    #   python-docx 确实不需要它，但 reportlab 需要，所以只能保留。
    #   这一点是打包自检在真实产物上抓出来的 —— 开发机上的模拟测试
    #   曾给出假通过（拦截器只实现了 Python 3.12 已废弃的 find_module）。
]

datas = [
    (ASSETS, "ui/assets"),
]
template = os.path.join(PROJECT_ROOT, "题库模板.xlsx")
if os.path.exists(template):
    datas.append((template, "."))

a = Analysis(
    [os.path.join(PROJECT_ROOT, "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # pywebview 在 Windows 上走 WinForms，PyInstaller 静态分析抓不到
        "webview.platforms.winforms",
        "clr_loader",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

icon_path = os.path.join(SPECPATH, "app.ico")

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ExamPaperGenerator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX 会显著提高杀软误报率，不值得为几十 MB 冒这个险
    console=False,      # 桌面程序，不弹黑窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path if os.path.exists(icon_path) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ExamPaperGenerator",
)
