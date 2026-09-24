"""考试试卷生成系统 —— 业务层。

本包与 ``renderers`` 包**必须保持零界面依赖**：
只允许 import 标准库 + openpyxl + python-docx + reportlab。
绝不 import tkinter / webview，绝不弹对话框、绝不自己读写用户选择的路径
（所有 I/O 路径由调用方传入）。

这条约束由 ``tests/test_no_ui_imports.py`` 强制执行。
"""
