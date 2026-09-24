"""中文字体定位与注册。

## 为什么不打包字体

系统自带的 CJK 字体体积很大（实测 msyh.ttc 19MB、simsun.ttc 18MB、simhei.ttf 10MB），
打进安装包会让体积翻倍。更重要的是**许可问题**：微软字体的 EULA 允许把字体
**嵌入文档**用于查看与打印，但**不允许再分发**字体文件本身。
所以这里只在运行时从系统字体目录读取，并让 reportlab 子集嵌入到生成的 PDF 中。

## 三个已知的坑

1. ``.ttc`` 是字体集合，必须指定 ``subfontIndex``，否则取错 face 或直接报错。
2. SimHei 没有独立的粗体文件 —— 必须用 ``registerFontFamily`` 把粗体映射到黑体，
   否则 ``<b>`` 不生效甚至报错。
3. 字体缺失必须在**导出之前**就发现（见 :func:`check_fonts`），
   否则用户会拿到一堆方框/乱码的 PDF 才发现。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.errors import Codes, DomainError

# 允许测试/特殊部署覆盖字体目录（模拟字体缺失场景）
FONT_DIR_ENV = "EXAM_FONT_DIR"

# (reportlab 字体名, 文件名, TTC 子字体索引)
# 顺序即优先级。宋体为正文字面，黑体为标题字面。
BODY_CANDIDATES: List[Tuple[str, str, Optional[int]]] = [
    ("SimSun", "simsun.ttc", 0),
    ("SimHei", "simhei.ttf", None),
    ("MSYH", "msyh.ttc", 0),
    ("DengXian", "Deng.ttf", None),
    ("SimKai", "simkai.ttf", None),
]

TITLE_CANDIDATES: List[Tuple[str, str, Optional[int]]] = [
    ("SimHei", "simhei.ttf", None),
    ("MSYH", "msyh.ttc", 0),
    ("DengXian", "Deng.ttf", None),
    ("SimSun", "simsun.ttc", 0),
]


@dataclass
class FontSet:
    """一组已注册的字体名。"""

    body: str
    title: str
    body_file: str = ""
    title_file: str = ""
    registered: bool = False

    def to_dict(self) -> Dict:
        return {
            "body": self.body,
            "title": self.title,
            "body_file": self.body_file,
            "title_file": self.title_file,
        }


_registered: Optional[FontSet] = None


def font_dir() -> str:
    """系统字体目录。"""
    override = os.environ.get(FONT_DIR_ENV)
    if override:
        return override
    windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot") or r"C:\Windows"
    return os.path.join(windir, "Fonts")


def _find_first(candidates, directory: str):
    """返回第一个存在的 (字体名, 绝对路径, subfontIndex)。"""
    for name, filename, index in candidates:
        path = os.path.join(directory, filename)
        if os.path.isfile(path):
            return name, path, index
    return None


def check_fonts() -> Dict:
    """**无副作用**的字体可用性预检。

    供界面层在加载时调用，提前禁用「导出 PDF」按钮，
    避免用户生成一堆乱码 PDF 之后才发现系统缺字体。
    """
    directory = font_dir()
    body = _find_first(BODY_CANDIDATES, directory)
    title = _find_first(TITLE_CANDIDATES, directory)
    return {
        "font_dir": directory,
        "exists": os.path.isdir(directory),
        "cjk_ok": body is not None,
        "body": body[0] if body else None,
        "body_file": body[1] if body else None,
        "title": title[0] if title else None,
        "title_file": title[1] if title else None,
    }


def register_fonts(force: bool = False) -> FontSet:
    """把系统 CJK 字体注册到 reportlab。幂等。

    找不到任何可用字体时抛 :class:`DomainError`（``FONT_NOT_FOUND``）。
    """
    global _registered
    if _registered is not None and not force:
        return _registered

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    directory = font_dir()
    body = _find_first(BODY_CANDIDATES, directory)
    if body is None:
        raise DomainError(
            Codes.FONT_NOT_FOUND,
            "系统中找不到可用的中文字体，无法生成 PDF",
            hint=(
                "PDF 导出需要系统安装宋体/黑体/微软雅黑之一。"
                "Windows 通常自带；若为精简版系统，请安装字体后重试。"
                "可改用 Word 导出（无需系统字体）。"
            ),
            details={"font_dir": directory, "checked": [c[1] for c in BODY_CANDIDATES]},
        )

    title = _find_first(TITLE_CANDIDATES, directory) or body

    _register_one(pdfmetrics, TTFont, body)
    if title[1] != body[1]:
        _register_one(pdfmetrics, TTFont, title)

    # 粗体映射：SimHei 没有独立的粗体文件，把 <b> 指向黑体字面
    pdfmetrics.registerFontFamily(
        body[0],
        normal=body[0],
        bold=title[0] if title[0] != body[0] else body[0],
        italic=body[0],
        boldItalic=title[0] if title[0] != body[0] else body[0],
    )

    _registered = FontSet(
        body=body[0],
        title=title[0],
        body_file=body[1],
        title_file=title[1],
        registered=True,
    )
    return _registered


def _register_one(pdfmetrics, TTFont, candidate):
    name, path, index = candidate
    try:
        if index is None:
            font = TTFont(name, path)
        else:
            font = TTFont(name, path, subfontIndex=index)
        pdfmetrics.registerFont(font)
    except Exception as exc:  # 字体文件损坏 / 子字体索引越界
        raise DomainError(
            Codes.FONT_NOT_FOUND,
            f"字体文件无法加载：{os.path.basename(path)}",
            hint="请确认该字体文件完好；必要时删除损坏字体后重试",
            details={"path": path, "subfont_index": index, "reason": str(exc)},
        ) from exc


def current_fonts() -> Optional[FontSet]:
    """已注册的字体集（未注册则为 None）。"""
    return _registered


def reset_cache() -> None:
    """清除缓存（测试用）。"""
    global _registered
    _registered = None
