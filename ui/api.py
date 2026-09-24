"""JS ↔ Python 的**唯一**桥。

## 统一返回信封

每个方法都返回同一结构，前端只需处理一种形状：

* 成功：``{"ok": True,  "data": ..., "warnings": [...], "error": None}``
* 失败：``{"ok": False, "data": None, "warnings": [...], "error": {...}}``

``warnings`` 是**数据不是弹窗** —— 前端渲染成信息条列表。
``error`` 渲染成内联提示。这替代了旧实现里散落各处的 ``messagebox``，
也从根上修掉了"用户取消保存却弹『已成功生成』"那类误报。

## 线程

pywebview 把 js_api 调用派发到工作线程，所以本类会被并发调用：
共享状态（``_pool`` / 配置 / 历史）一律走 ``self._lock``。
"""

from __future__ import annotations

import functools
import os
import re
import subprocess
import sys
import threading
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from app import history as history_store
from app import settings as settings_store
from app.constants import (
    DEFAULT_EXAM_TITLE,
    DEFAULT_STUDENT_INFO,
    EXPORT_MODES,
    QUESTION_TYPES,
    VERSION,
)
from app.docmodel import build_paper_blocks
from app.errors import Codes, DomainError
from app.generator import generate
from app.loader import load_question_bank
from app.models import PaperConfig, Warning
from app.numbering import build_answer_groups
from app.pool import QuestionPool

from . import dialogs
from .jobs import JobManager, check_cancelled


@dataclass
class Reply:
    """带 warning 的成功返回。"""

    data: Any = None
    warnings: List[Warning] = field(default_factory=list)


def _split(result):
    if isinstance(result, Reply):
        return result.data, list(result.warnings)
    return result, []


def expose(fn: Callable) -> Callable:
    """把所有异常收敛成结构化信封，绝不让异常抛穿到 JS 层。"""

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            result = fn(self, *args, **kwargs)
            data, warnings = _split(result)
            return {
                "ok": True,
                "data": json_safe(data),
                "warnings": [w.to_dict() for w in warnings],
                "error": None,
            }
        except DomainError as error:
            return {
                "ok": False,
                "data": None,
                "warnings": [],
                "error": error.to_dict(),
            }
        except Exception as exc:  # noqa: BLE001 - 这里就是要兜住一切
            return {
                "ok": False,
                "data": None,
                "warnings": [],
                "error": {
                    "code": Codes.INTERNAL,
                    "message": str(exc) or exc.__class__.__name__,
                    "hint": "这是未预期的错误，请把下方详情反馈给开发者",
                    "details": {"traceback": traceback.format_exc()[-2000:]},
                },
            }

    return wrapper


def _is_paper_blocks(blocks) -> bool:
    """判断这批 Block 是试卷还是答题卡。

    两者的纸张策略不同：试卷跟随用户选的纸张（A4，或 A3 两张 A4 拼版），
    答题卡固定 A4 —— 它的版式（每行几题、列宽）是按 A4 版心算出来的，
    套到 A3 上会错乱。
    """
    from app.docmodel import AnswerCardHead

    return not any(isinstance(block, AnswerCardHead) for block in blocks)


def _safe_filename(name: str, fallback: str = "试卷") -> str:
    """把用户输入的文件名清洗成合法的 Windows 文件名。

    Windows 不允许 \\ / : * ? " < > | 以及结尾的点和空格；
    留空则用兜底值，避免生成 ".docx" 这种无名文件。
    """
    cleaned = re.sub(r'[\\/:*?"<>|\r\n\t]', "", str(name or "")).strip().rstrip(".")
    return cleaned or fallback


def json_safe(value):
    """pywebview 用 ``json.dumps`` 序列化返回值，这里兜住非 JSON 类型。"""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    if isinstance(value, os.PathLike):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "to_dict"):
        return json_safe(value.to_dict())
    return str(value)


class Api:
    """``js_api`` 的实现。**不需要 webview 实例即可构造**，便于测试。"""

    def __init__(self, window=None):
        self._lock = threading.RLock()
        self._pool: Optional[QuestionPool] = None
        self._load_result = None
        self._pool_source = ""
        self._jobs = JobManager()
        self._window = window

    def attach_window(self, window) -> None:
        self._window = window
        dialogs.set_window(window)

    # ── 环境 ─────────────────────────────────────────────────────────

    @expose
    def get_app_info(self):
        from renderers.fonts import check_fonts

        fonts = check_fonts()
        return {
            "version": VERSION,
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "paper_sizes": ["A4", "A3"],
            "export_modes": EXPORT_MODES,
            "question_types": [
                {
                    "key": qt["key"],
                    "label": qt["label"],
                    "score": qt["score"],
                    "default": qt["default"],
                }
                for qt in QUESTION_TYPES
            ],
            "fonts": fonts,
            "history_path": history_store.history_path(),
            "settings_path": settings_store.settings_path(),
            "default_exam_title": DEFAULT_EXAM_TITLE,
            "default_student_info": DEFAULT_STUDENT_INFO,
        }

    @expose
    def get_default_config(self):
        return PaperConfig().to_legacy_dict()

    @expose
    def load_settings(self):
        return settings_store.load()

    @expose
    def save_settings(self, values):
        return settings_store.save(values or {})

    # ── 题库 ─────────────────────────────────────────────────────────

    @expose
    def pick_bank_file(self):
        path = dialogs.pick_open_file(dialogs.EXCEL_FILTERS_WIDE)
        if not path:
            return {"cancelled": True, "path": ""}
        return {"cancelled": False, "path": path}

    @expose
    def load_excel(self, path):
        return self._load_excel_impl(path)

    @expose
    def load_bundled_template(self):
        """加载随程序分发的示例题库。"""
        path = _bundled_template_path()
        if not os.path.exists(path):
            raise DomainError(
                Codes.FILE_NOT_FOUND,
                "示例题库文件不存在",
                hint="请改用「浏览」选择你自己的题库文件",
                details={"expected": path},
            )
        return self._load_excel_impl(path)

    @expose
    def clear_bank(self):
        """卸掉当前题库，方便接着选下一个科目的题。

        题库是纯内存状态，清掉即可；预览栏由前端重置。
        """
        with self._lock:
            self._pool = None
            self._load_result = None
            self._pool_source = ""
        self._save_settings_quietly({"last_bank_path": ""})
        return {"cleared": True}

    def _save_settings_quietly(self, values) -> None:
        """把设置写盘，失败也不影响主流程。

        %APPDATA% 在企业锁定的机器上可能是只读的 —— 那种环境下
        「记不住上次目录」是可以接受的，但整个功能不可用不行。
        用户主动点「保存设置」时才需要把错误报出来（见 :meth:`save_settings`）。
        """
        try:
            settings_store.save(values)
        except OSError:
            pass

    def _load_excel_impl(self, path):
        """**不加 @expose** —— 被装饰的方法会返回信封而非数据，
        内部彼此调用必须走这个私有实现，否则会出现双层信封。"""
        result = load_question_bank(path)
        new_pool = QuestionPool(result)
        if len(new_pool) == 0:
            raise DomainError(Codes.EMPTY_SHEET, "题库中没有可用的题目")

        with self._lock:
            self._pool = new_pool
            self._load_result = result
            self._pool_source = path

        self._save_settings_quietly({"last_bank_path": path})
        return Reply(data=self._bank_summary(), warnings=list(result.warnings))

    @expose
    def get_bank_info(self):
        with self._lock:
            if self._pool is None:
                return None
            return self._bank_summary()

    def _bank_summary(self):
        pool = self._pool
        result = self._load_result
        return {
            "source": self._pool_source,
            "filename": os.path.basename(self._pool_source or ""),
            "total": len(pool),
            "counts_by_type": pool.count_by_type(),
            "difficulty_values": pool.difficulty_values(),
            "difficulty_counts": pool.difficulty_counts(),
            "knowledge_values": pool.knowledge_values(),
            "knowledge_counts": pool.knowledge_counts(),
            "warnings": [w.to_dict() for w in (result.warnings if result else [])],
        }

    # ── 预览 ─────────────────────────────────────────────────────────

    @expose
    def preview(self, config, target="paper"):
        """生成预览。

        ``target`` 决定预览哪个：``"paper"`` 试卷 / ``"card"`` 答题卡。

        返回里带 ``pdf_base64`` —— 那是**真正要导出的那个 PDF**，
        前端用内嵌的 pdf.js 渲染出来。之前预览是另做一套 HTML 列表，
        和实际导出文件的分页、换行对不上，用户一眼能看出不一致。
        """
        cfg = self._config(config)
        cfg.exam_count = 1
        target = "card" if target == "card" else "paper"

        with self._lock:
            pool = self._pool
        if pool is None or len(pool) == 0:
            raise DomainError(Codes.NOT_LOADED, "请先加载题库")

        result = generate(cfg, pool, history_qids=self._history_qids(cfg))
        paper = result.papers[0]

        if target == "card":
            from renderers.answer_card import build_answer_card_document

            blocks = build_answer_card_document([paper], cfg)
        else:
            from app.docmodel import build_paper_blocks

            blocks = build_paper_blocks(paper, cfg)

        data = {
            "target": target,
            "exam_number": paper.exam_number,
            "sections": [section.to_dict() for section in paper.sections],
            "answer_groups": [
                group.to_dict() for group in build_answer_groups(paper.sections)
            ]
            if cfg.include_answers
            else [],
            "total_count": paper.total_count,
            "total_score": paper.total_score,
            "stats": result.stats,
            "seed": paper.seed,
            "reused_count": len(paper.reused_qids),
            "paper_size": cfg.paper_size,
            "pdf_base64": None,
        }
        warnings = list(result.warnings)

        pdf_payload, font_error = self._render_preview_pdf(blocks, cfg)
        if pdf_payload is not None:
            data["pdf_base64"] = pdf_payload
        elif font_error is not None:
            # 缺中文字体时 PDF 渲染不了，但预览的其余部分仍然可用
            warnings.append(font_error)

        return Reply(data=data, warnings=warnings)

    @expose
    def open_preview_pdf(self, config, target="paper"):
        """把预览 PDF 写到临时文件并用系统默认程序打开。

        这是内嵌 pdf.js 渲染失败时的兜底 —— 保证用户总有一条路能看到
        真实文件，而不是对着空白预览栏无从下手。
        """
        import tempfile

        from renderers.pdf_renderer import render_pdf

        cfg = self._config(config)
        cfg.exam_count = 1
        target = "card" if target == "card" else "paper"

        with self._lock:
            pool = self._pool
        if pool is None or len(pool) == 0:
            raise DomainError(Codes.NOT_LOADED, "请先加载题库")

        result = generate(cfg, pool, history_qids=self._history_qids(cfg))
        paper = result.papers[0]

        if target == "card":
            from renderers.answer_card import build_answer_card_document

            blocks = build_answer_card_document([paper], cfg)
        else:
            from app.docmodel import build_paper_blocks

            blocks = build_paper_blocks(paper, cfg)

        out_dir = os.path.join(tempfile.gettempdir(), "ExamPaperGen")
        os.makedirs(out_dir, exist_ok=True)
        name = "答题卡预览.pdf" if target == "card" else "试卷预览.pdf"
        path = os.path.join(out_dir, name)

        render_pdf(
            blocks,
            path,
            cfg.paper_size if _is_paper_blocks(blocks) else "A4",
            cfg.header_text,
        )
        return self._open_path_impl(path)

    def _render_preview_pdf(self, blocks, cfg):
        """把 Block 列表渲染成 PDF，返回 ``(base64, 失败原因)``。

        渲染进内存而不是临时文件：预览会随配置频繁刷新，
        不该在磁盘上留下垃圾。
        """
        import base64
        import io

        from app.errors import DomainError
        from renderers.pdf_renderer import render_pdf

        buffer = io.BytesIO()
        try:
            # 答题卡固定 A4：它的版式是按 A4 版心算的，用 A3 会排版错乱
            paper_size = cfg.paper_size if _is_paper_blocks(blocks) else "A4"
            render_pdf(blocks, buffer, paper_size, cfg.header_text)
        except DomainError as error:
            return None, error
        except Exception as error:  # noqa: BLE001 - 预览失败不应中断整个预览
            return None, Warning(Codes.INTERNAL, f"预览渲染失败：{error}", {})

        return base64.b64encode(buffer.getvalue()).decode("ascii"), None

    @expose
    def reroll(self, seed=None):
        """换一个随机种子（前端拿到后重新 preview）。"""
        import random as _random

        return {"seed": int(seed) if seed is not None else _random.randint(1, 10**9)}

    # ── 导出（长任务） ───────────────────────────────────────────────

    @expose
    def pick_output_dir(self):
        path = dialogs.pick_folder()
        if not path:
            return {"cancelled": True, "path": ""}
        self._save_settings_quietly({"last_output_dir": path})
        return {"cancelled": False, "path": path}

    @expose
    def start_export(self, config, options):
        """立刻返回 job_id；前端轮询 :meth:`get_job` 拿进度。"""
        options = dict(options or {})
        output_dir = options.get("output_dir") or settings_store.load().get(
            "last_output_dir"
        ) or ""
        if not output_dir:
            raise DomainError(
                Codes.FILE_NOT_FOUND,
                "请先选择导出目录",
                hint="点击「选择导出目录」按钮",
            )
        if not any(
            options.get(key)
            for key in ("docx", "pdf", "card", "card_docx")
        ):
            raise DomainError(
                Codes.UNSUPPORTED_FORMAT,
                "请至少选择一种导出格式",
                hint="勾选试卷 Word / 试卷 PDF / 答题卡 Word / 答题卡 PDF",
            )

        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as exc:
            raise DomainError(
                Codes.FILE_NOT_FOUND,
                f"无法创建导出目录：{exc}",
                details={"output_dir": output_dir},
            ) from exc

        job_id = self._jobs.start(
            "export",
            lambda progress, cancel: self._export_job(
                config, options, output_dir, progress, cancel
            ),
        )
        return {"job_id": job_id}

    @expose
    def get_job(self, job_id):
        job = self._jobs.get(job_id)
        if job is None:
            raise DomainError(Codes.NOT_LOADED, "任务不存在或已过期")
        return job

    @expose
    def cancel_job(self, job_id):
        return {"cancelling": self._jobs.cancel(job_id)}

    @expose
    def list_jobs(self):
        return self._jobs.list()

    def _export_job(self, config, options, output_dir, progress, cancel_event):
        cfg = self._config(config)
        cfg.exam_count = max(1, int(options.get("exam_count") or 1))
        cfg.include_answers = bool(options.get("include_answers", False))
        # 以**实际勾选的格式**为准，而不是前端传的配置：
        # 出了答题卡，试卷上就不该再留作答横线（学生写在卡上）。
        cfg.include_answer_card = bool(
            options.get("card") or options.get("card_docx")
        )

        with self._lock:
            pool = self._pool
        if pool is None or len(pool) == 0:
            raise DomainError(Codes.NOT_LOADED, "请先加载题库")

        progress(0.02, "正在组卷…")
        result = generate(
            cfg,
            pool,
            history_qids=self._history_qids(cfg),
            progress=lambda fraction, message: progress(0.02 + fraction * 0.35, message),
        )
        check_cancelled(cancel_event)

        total = len(result.papers)
        written: List[str] = []
        want_docx = bool(options.get("docx"))
        want_pdf = bool(options.get("pdf"))

        # 文件名由用户指定。固定成「试卷」会让不同批次互相覆盖，
        # 用户分不清磁盘上哪个文件是刚生成的那份。
        base = _safe_filename(options.get("file_prefix"), "试卷")

        for index, paper in enumerate(result.papers):
            check_cancelled(cancel_event)
            share = 0.35 + 0.5 * (index / max(1, total))
            progress(share, f"正在导出第 {index + 1}/{total} 份试卷")

            # 多份时才编号，单份保持干净的文件名
            suffix = f"-{paper.exam_number}" if total > 1 else ""
            blocks = build_paper_blocks(paper, cfg)

            if want_docx:
                from renderers.docx_renderer import render_docx

                path = os.path.join(output_dir, f"{base}{suffix}.docx")
                render_docx(blocks, path, cfg.paper_size, cfg.header_text)
                written.append(path)

            if want_pdf:
                from renderers.pdf_renderer import render_pdf

                path = os.path.join(output_dir, f"{base}{suffix}.pdf")
                render_pdf(blocks, path, cfg.paper_size, cfg.header_text)
                written.append(path)

        want_card_pdf = bool(options.get("card"))
        want_card_docx = bool(options.get("card_docx"))

        if want_card_pdf or want_card_docx:
            check_cancelled(cancel_event)
            progress(0.88, "正在生成答题卡")
            from renderers.answer_card import build_answer_card_document

            card_blocks = build_answer_card_document(result.papers, cfg)

            if want_card_docx:
                from renderers.docx_renderer import render_docx

                path = os.path.join(output_dir, f"{base}-答题卡.docx")
                render_docx(card_blocks, path, "A4", "")
                written.append(path)

            if want_card_pdf:
                from renderers.pdf_renderer import render_pdf

                path = os.path.join(output_dir, f"{base}-答题卡.pdf")
                render_pdf(card_blocks, path, "A4", "")
                written.append(path)

        progress(0.95, "正在记录历史")
        try:
            history_store.record(
                exam_title=cfg.exam_title,
                exam_count=len(result.papers),
                seed=result.stats.get("seed", 0),
                qids=[
                    question.qid
                    for paper in result.papers
                    for section in paper.sections
                    for question in section.questions
                ],
                files=written,
            )
        except OSError:
            pass  # 历史写不进去不应让导出失败

        progress(1.0, "完成")
        return {
            "files": written,
            "output_dir": output_dir,
            "total_count": result.papers[0].total_count,
            "total_score": result.papers[0].total_score,
            "exam_count": len(result.papers),
        }

    # ── 打开产物 ─────────────────────────────────────────────────────

    @expose
    def open_path(self, path):
        return self._open_path_impl(path)

    @expose
    def reveal_in_explorer(self, path):
        if not path or not os.path.exists(path):
            raise DomainError(Codes.FILE_NOT_FOUND, f"路径不存在：{path}")
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            return {"revealed": str(path)}
        # 非 Windows 没有"选中文件"的概念，退化为打开父目录
        return self._open_path_impl(os.path.dirname(path))

    def _open_path_impl(self, path):
        """用系统默认程序打开文件或目录。**不加 @expose**（同上）。"""
        if not path or not os.path.exists(path):
            raise DomainError(
                Codes.FILE_NOT_FOUND, f"路径不存在：{path}", details={"path": path}
            )
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606 - 本地桌面应用，打开的是用户自己选的路径
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return {"opened": str(path)}

    # ── 模板 ─────────────────────────────────────────────────────────

    @expose
    def save_template(self, config):
        path = dialogs.pick_save_file("试卷模板.json", dialogs.TEMPLATE_FILTERS)
        if not path:
            return {"cancelled": True, "path": ""}
        import json

        cfg = self._config(config)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(cfg.template_dict(), handle, ensure_ascii=False, indent=2)
        return {"cancelled": False, "path": path}

    @expose
    def load_template(self):
        path = dialogs.pick_open_file(dialogs.TEMPLATE_FILTERS)
        if not path:
            return {"cancelled": True, "config": None}
        import json

        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise DomainError(
                Codes.UNSUPPORTED_FORMAT, "模板文件格式不正确", details={"path": path}
            )
        return {"cancelled": False, "path": path, "config": data}

    # ── 历史 ─────────────────────────────────────────────────────────

    @expose
    def history_list(self):
        return history_store.list_entries()

    @expose
    def history_clear(self):
        history_store.clear()
        return {"cleared": True}

    @expose
    def history_delete(self, ids):
        return {"removed": history_store.delete(ids)}

    # ── 内部 ─────────────────────────────────────────────────────────

    def _config(self, config) -> PaperConfig:
        if isinstance(config, PaperConfig):
            return config
        return PaperConfig.from_legacy(config or {})

    def _history_qids(self, cfg: PaperConfig):
        if not cfg.avoid_history:
            return frozenset()
        try:
            return history_store.used_qids()
        except Exception:
            return frozenset()


def _bundled_template_path() -> str:
    """示例题库的位置。

    打包后 ``__file__`` 指向临时解压目录，必须优先用 ``sys._MEIPASS``。
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidate = os.path.join(base, "题库模板.xlsx")
        if os.path.exists(candidate):
            return candidate
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, "题库模板.xlsx")
