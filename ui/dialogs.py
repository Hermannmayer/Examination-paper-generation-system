"""系统文件对话框。

单独成模块是为了**可测试**：测试里 monkeypatch 本模块的函数即可，
不需要真的弹窗，也不需要 webview 实例。
"""

from __future__ import annotations

import os
from typing import Optional, Sequence

EXCEL_FILTERS = ("Excel 题库 (*.xlsx;*.xlsm)", "CSV 题库 (*.csv)", "所有文件 (*.*)")
EXCEL_FILTERS_WIDE = (
    "题库文件 (*.xlsx;*.xlsm;*.csv)",
    "Excel 题库 (*.xlsx;*.xlsm)",
    "CSV 题库 (*.csv)",
    "所有文件 (*.*)",
)
DOCX_FILTERS = ("Word 文档 (*.docx)",)
PDF_FILTERS = ("PDF 文档 (*.pdf)",)
TEMPLATE_FILTERS = ("模板文件 (*.json)",)

_window = None


def set_window(window) -> None:
    """由 ``main.py`` 在窗口创建后注入。"""
    global _window
    _window = window


def get_window():
    return _window


def _first(result) -> Optional[str]:
    if not result:
        return None
    if isinstance(result, str):
        return result
    paths = list(result)
    return paths[0] if paths else None


def pick_open_file(file_types: Sequence[str] = EXCEL_FILTERS_WIDE) -> Optional[str]:
    """选择单个已存在文件。取消返回 None。"""
    window = get_window()
    if window is None:
        return None
    import webview

    return _first(
        window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=tuple(file_types),
        )
    )


def pick_save_file(
    save_filename: str = "", file_types: Sequence[str] = DOCX_FILTERS
) -> Optional[str]:
    """选择保存路径。**取消返回 None** —— 调用方必须据此判断，
    不能像旧实现那样取消后还报「已成功生成」。"""
    window = get_window()
    if window is None:
        return None
    import webview

    chosen = _first(
        window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=save_filename,
            file_types=tuple(file_types),
        )
    )
    if not chosen:
        return None
    # 部分平台不自动补扩展名
    if not os.path.splitext(chosen)[1] and file_types:
        default_ext = _default_extension(file_types[0])
        if default_ext:
            chosen += default_ext
    return chosen


def pick_folder() -> Optional[str]:
    window = get_window()
    if window is None:
        return None
    import webview

    return _first(window.create_file_dialog(webview.FileDialog.FOLDER))


def _default_extension(filter_string: str) -> str:
    start = filter_string.find("*.")
    if start == -1:
        return ""
    end = filter_string.find(")", start)
    tail = filter_string[start + 1 : end if end != -1 else len(filter_string)]
    return tail.split(";")[0].strip()
