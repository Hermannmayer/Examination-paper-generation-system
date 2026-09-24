"""生成历史与"避免重复出过的题"。

历史文件放在 ``%APPDATA%/ExamPaperGen/history.json``（用户可查、可清空）。

设计取舍：``qid`` 是**内容哈希**，所以老师改了题干就算作新题，
"避免重复出题"才真正跨会话成立；同时每条记录保留 ``source_row``，
需要人工判断时可以对照。

损坏的 JSON 不能让程序崩 —— 返回空历史并给出 warning。
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

from .models import Warning

APP_DIR_NAME = "ExamPaperGen"
HISTORY_FILENAME = "history.json"
MAX_ENTRIES = 500


def app_data_dir() -> str:
    """用户数据目录（Windows 为 ``%APPDATA%\\ExamPaperGen``）。"""
    base = (
        os.environ.get("APPDATA")
        or os.environ.get("XDG_DATA_HOME")
        or os.path.expanduser("~")
    )
    return os.path.join(base, APP_DIR_NAME)


def history_path() -> str:
    override = os.environ.get("EXAM_HISTORY_PATH")
    if override:
        return override
    return os.path.join(app_data_dir(), HISTORY_FILENAME)


@dataclass
class HistoryEntry:
    """一次生成的记录。"""

    id: str
    time: str
    exam_title: str = ""
    exam_count: int = 1
    seed: int = 0
    qids: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        data = asdict(self)
        # 历史列表里不必回传全部 qid，避免文件与响应急剧膨胀
        data["qid_count"] = len(self.qids)
        data.pop("qids", None)
        return data


def _read_raw() -> tuple:
    """返回 ``(entries, warning)``。损坏时 entries 为空。"""
    path = history_path()
    if not os.path.exists(path):
        return [], None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        return [], Warning(
            "HISTORY_CORRUPT",
            f"历史记录文件无法读取，已忽略：{os.path.basename(path)}",
            {"path": path, "reason": str(exc)},
        )

    if isinstance(data, dict):
        data = data.get("entries", [])
    if not isinstance(data, list):
        return [], Warning(
            "HISTORY_CORRUPT", "历史记录格式不正确，已忽略", {"path": path}
        )
    return [e for e in data if isinstance(e, dict)], None


def _write_raw(entries: List[Dict]) -> None:
    """原子写入：先写临时文件再替换，避免中途失败留下半个文件。"""
    path = history_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    payload = {"version": 1, "entries": entries[-MAX_ENTRIES:]}

    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".tmp",
        dir=os.path.dirname(path) or ".",
        delete=False,
    )
    try:
        with handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(handle.name, path)
    except BaseException:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise


def load_entries() -> List[Dict]:
    entries, _ = _read_raw()
    return entries


def list_entries() -> Dict:
    """给界面的历史列表（含 warning）。"""
    entries, warning = _read_raw()
    out = []
    for entry in reversed(entries):
        out.append(
            {
                "id": entry.get("id", ""),
                "time": entry.get("time", ""),
                "exam_title": entry.get("exam_title", ""),
                "exam_count": entry.get("exam_count", 1),
                "seed": entry.get("seed", 0),
                "qid_count": len(entry.get("qids") or []),
                "files": list(entry.get("files") or []),
            }
        )
    return {
        "path": history_path(),
        "entries": out,
        "warnings": [warning.to_dict()] if warning else [],
    }


def record(
    exam_title: str,
    exam_count: int,
    seed: int,
    qids,
    files=None,
    when: Optional[datetime] = None,
) -> HistoryEntry:
    """追加一条记录。"""
    stamp = when or datetime.now()
    entry = HistoryEntry(
        id=stamp.strftime("%Y%m%d%H%M%S%f"),
        time=stamp.isoformat(timespec="seconds"),
        exam_title=exam_title,
        exam_count=int(exam_count),
        seed=int(seed),
        qids=list(qids),
        files=list(files or []),
    )
    entries, _ = _read_raw()
    entries.append(
        {
            "id": entry.id,
            "time": entry.time,
            "exam_title": entry.exam_title,
            "exam_count": entry.exam_count,
            "seed": entry.seed,
            "qids": entry.qids,
            "files": entry.files,
        }
    )
    _write_raw(entries)
    return entry


def used_qids() -> Set[str]:
    """历史上出过的全部 qid —— 供 ``avoid_history`` 使用。"""
    entries, _ = _read_raw()
    collected: Set[str] = set()
    for entry in entries:
        collected.update(entry.get("qids") or ())
    return collected


def clear() -> None:
    _write_raw([])


def delete(ids) -> int:
    """按 id 删除若干条记录，返回删除数量。"""
    targets = set(ids or ())
    if not targets:
        return 0
    entries, _ = _read_raw()
    kept = [e for e in entries if e.get("id") not in targets]
    removed = len(entries) - len(kept)
    if removed:
        _write_raw(kept)
    return removed
