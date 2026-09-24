"""输出层（渲染）。

与 ``app`` 包一样**零界面依赖**：只允许 import 标准库 +
python-docx + reportlab + PIL。绝不 import tkinter / webview。

字体策略见 :mod:`renderers.fonts` —— 运行时读系统字体，
**绝不把字体文件打包进安装包**。
"""
