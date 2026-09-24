"""界面层 —— **唯一**允许接触 pywebview 的地方。

只有本包的三个模块可以 ``import webview``：

* :mod:`ui.api`    —— JS ↔ Python 的唯一桥
* :mod:`ui.jobs`   —— 长任务的线程 / 进度 / 取消
* :mod:`ui.dialogs`—— 系统文件对话框

业务层（``app``）与输出层（``renderers``）不得反向依赖本包，
由 ``tests/test_no_ui_imports.py`` 强制保证。
"""
