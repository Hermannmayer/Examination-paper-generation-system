"""轻量设置存储（窗口尺寸、上次使用的目录、上次的配置）。

与历史记录一样放在 ``%APPDATA%/ExamPaperGen/``，原子写入、损坏不崩。
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict

from .history import app_data_dir

SETTINGS_FILENAME = "settings.json"

DEFAULTS: Dict[str, Any] = {
    "last_bank_path": "",
    "last_output_dir": "",
    "file_name": "",
    "window_width": 1280,
    "window_height": 860,
    "paper_size": "A4",
    "export_docx": True,
    "export_pdf": False,
    "export_card": False,
    "export_card_docx": False,
    "include_answers": False,
}


def settings_path() -> str:
    override = os.environ.get("EXAM_SETTINGS_PATH")
    if override:
        return override
    return os.path.join(app_data_dir(), SETTINGS_FILENAME)


def load() -> Dict[str, Any]:
    """读取设置。文件缺失或损坏时返回默认值，绝不抛异常。"""
    merged = dict(DEFAULTS)
    try:
        with open(settings_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return merged
    if isinstance(data, dict):
        merged.update(data)
    return merged


def save(values: Dict[str, Any]) -> Dict[str, Any]:
    """合并写入。返回写入后的完整设置。"""
    merged = load()
    if isinstance(values, dict):
        merged.update(values)

    path = settings_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".tmp",
        dir=os.path.dirname(path) or ".",
        delete=False,
    )
    try:
        with handle:
            json.dump(merged, handle, ensure_ascii=False, indent=2)
        os.replace(handle.name, path)
    except BaseException:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise
    return merged


def reset() -> Dict[str, Any]:
    return save(dict(DEFAULTS))
