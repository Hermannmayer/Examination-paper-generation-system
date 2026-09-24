"""业务数据模型。

所有模型都提供 ``to_dict()`` —— 返回值会经 pywebview 的 ``json.dumps`` 序列化，
因此**绝不能**包含 datetime / Path / 自定义对象等非 JSON 类型。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .constants import (
    DEFAULT_EXAM_TITLE,
    DEFAULT_STUDENT_INFO,
    EXPORT_MODE_RANDOM,
    KEY_BY_LABEL,
    POOL_WARN_AND_REUSE,
    QUESTION_TYPES,
)


def make_qid(qtype: str, stem: str, answer: str, options) -> str:
    """题目身份 = 内容哈希。

    用内容而非行号，跨会话、跨文件重排都稳定，"避免重复出过的题"才真正成立。
    代价：老师改了题干就算作新题（此时 source_row 可辅助人工判断）。
    """
    opt_repr = "|".join(f"{k}={v}" for k, v in options)
    payload = f"{qtype}\x01{stem}\x01{answer}\x01{opt_repr}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Question:
    """一道题。不可变，可哈希（``options`` 用元组而非 dict）。"""

    qid: str
    qtype: str  # 中文标签，如 "判断题"（与既有代码/配置键保持一致）
    stem: str
    answer_raw: str  # 题库原值，如 "1" / "ABD"
    answer: str  # 归一化后，如 "√" / "ABD"
    options: Tuple[Tuple[str, str], ...] = ()  # (("A", "选项内容"), ...)
    difficulty: Optional[str] = None
    knowledge: Optional[str] = None
    source_row: int = 0  # xlsx 中的行号（1-based，含表头），用于报错定位
    source_sheet: str = ""

    @property
    def key(self) -> str:
        """题型配置键，如 ``judgment``。"""
        return KEY_BY_LABEL.get(self.qtype, self.qtype)

    @property
    def options_dict(self) -> Dict[str, str]:
        return dict(self.options)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "qid": self.qid,
            "qtype": self.qtype,
            "key": self.key,
            "stem": self.stem,
            "answer": self.answer,
            "options": [{"letter": k, "text": v} for k, v in self.options],
            "difficulty": self.difficulty,
            "knowledge": self.knowledge,
            "source_row": self.source_row,
            "source_sheet": self.source_sheet,
        }


@dataclass
class Warning:
    """面向用户的可展示提示。是**数据不是弹窗**。"""

    code: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


@dataclass
class PaperConfig:
    """组卷配置。

    字段刻意沿用 ``gui.py:_build_config`` 的键名语义，以保证已有 JSON 模板继续可用
    （见 :meth:`from_legacy` / :meth:`to_legacy_dict`）。
    """

    export_mode: str = EXPORT_MODE_RANDOM
    include_answers: bool = False
    include_answer_card: bool = False
    exam_title: str = DEFAULT_EXAM_TITLE
    student_name: str = DEFAULT_STUDENT_INFO
    exam_time: str = ""
    paper_size: str = "A4"
    header_text: str = ""
    random_order: bool = True

    # 题型顺序（配置键，如 ["judgment", "mcq"]）；None 表示用注册表默认顺序
    question_order: Optional[List[str]] = None

    include: Dict[str, bool] = field(default_factory=dict)
    counts: Dict[str, int] = field(default_factory=dict)
    scores: Dict[str, int] = field(default_factory=dict)
    ratios: Dict[str, int] = field(default_factory=dict)
    ranges: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    total_questions: int = 100

    # 难度 / 知识点
    difficulty_weights: Dict[str, float] = field(default_factory=dict)
    knowledge_include: List[str] = field(default_factory=list)
    knowledge_cover_first: bool = True

    # 去重 / 复现
    seed: Optional[int] = None
    unique_across_papers: bool = True
    avoid_history: bool = False
    on_pool_exhausted: str = POOL_WARN_AND_REUSE
    exam_count: int = 1

    # ── 兼容层：与旧版扁平字典互转 ──────────────────────────────────

    @classmethod
    def from_legacy(cls, cfg: Dict[str, Any]) -> "PaperConfig":
        """从 ``gui.py:_build_config`` 产出的扁平字典构造。

        兼容旧键：``include_{key}`` / ``{key}_count`` / ``{key}_score`` /
        ``{key}_ratio`` / ``{key}_start`` / ``{key}_end``。
        """
        cfg = cfg or {}
        self = cls()

        self.export_mode = cfg.get("export_mode") or EXPORT_MODE_RANDOM
        self.include_answers = bool(cfg.get("include_answers", False))
        self.include_answer_card = bool(cfg.get("include_answer_card", False))
        self.exam_title = cfg.get("exam_title", DEFAULT_EXAM_TITLE)
        self.student_name = cfg.get("student_name", DEFAULT_STUDENT_INFO)
        self.exam_time = cfg.get("exam_time", "")
        self.paper_size = cfg.get("paper_size", "A4")
        self.header_text = (cfg.get("header_text") or "").strip()
        self.random_order = bool(cfg.get("random_order", True))
        self.question_order = list(cfg["question_order"]) if cfg.get("question_order") else None
        self.total_questions = _as_int(cfg.get("total_questions"), 100)

        self.difficulty_weights = dict(cfg.get("difficulty_weights") or {})
        self.knowledge_include = list(cfg.get("knowledge_include") or [])
        self.knowledge_cover_first = bool(cfg.get("knowledge_cover_first", True))
        self.seed = cfg.get("seed")
        self.unique_across_papers = bool(cfg.get("unique_across_papers", True))
        self.avoid_history = bool(cfg.get("avoid_history", False))
        self.on_pool_exhausted = cfg.get("on_pool_exhausted", POOL_WARN_AND_REUSE)
        self.exam_count = _as_int(cfg.get("exam_count"), 1)

        for key in _discover_type_keys(cfg):
            self.include[key] = bool(cfg.get(f"include_{key}", False))
            self.counts[key] = _as_int(cfg.get(f"{key}_count"), 0)
            default_score = _default_score(key)
            self.scores[key] = _as_int(cfg.get(f"{key}_score"), default_score)
            if f"{key}_ratio" in cfg:
                self.ratios[key] = _as_int(cfg.get(f"{key}_ratio"), 0)
            if f"{key}_start" in cfg or f"{key}_end" in cfg:
                self.ranges[key] = (
                    _as_int(cfg.get(f"{key}_start"), 0),
                    _as_int(cfg.get(f"{key}_end"), 0),
                )
        return self

    def _all_type_keys(self) -> List[str]:
        """注册表里的题型键 + 本配置里实际出现过的额外键。"""
        keys = [qt["key"] for qt in QUESTION_TYPES]
        for mapping in (self.include, self.counts, self.scores, self.ratios, self.ranges):
            for k in mapping:
                if k not in keys:
                    keys.append(k)
        return keys

    def to_legacy_dict(self) -> Dict[str, Any]:
        """还原为旧版扁平字典（供界面层与模板保存使用）。"""
        out: Dict[str, Any] = {
            "export_mode": self.export_mode,
            "include_answers": self.include_answers,
            "include_answer_card": self.include_answer_card,
            "exam_title": self.exam_title,
            "student_name": self.student_name,
            "exam_time": self.exam_time,
            "paper_size": self.paper_size,
            "header_text": self.header_text,
            "random_order": self.random_order,
            "question_order": list(self.question_order) if self.question_order else None,
            "total_questions": self.total_questions,
            "seed": self.seed,
            "unique_across_papers": self.unique_across_papers,
            "avoid_history": self.avoid_history,
            "on_pool_exhausted": self.on_pool_exhausted,
            "exam_count": self.exam_count,
            "difficulty_weights": dict(self.difficulty_weights),
            "knowledge_include": list(self.knowledge_include),
            "knowledge_cover_first": self.knowledge_cover_first,
        }
        for key in self._all_type_keys():
            out[f"include_{key}"] = self.include.get(key, False)
            out[f"{key}_count"] = self.counts.get(key, 0)
            out[f"{key}_score"] = self.scores.get(key, _default_score(key))
            if key in self.ratios:
                out[f"{key}_ratio"] = self.ratios[key]
            if key in self.ranges:
                out[f"{key}_start"], out[f"{key}_end"] = self.ranges[key]
        return out

    def template_dict(self) -> Dict[str, Any]:
        """保存模板用：剔除顺序范围（旧实现 ``_extract_template_data`` 的行为）。"""
        cfg = self.to_legacy_dict()
        for key in list(cfg.keys()):
            if key.endswith("_start") or key.endswith("_end"):
                cfg.pop(key, None)
        cfg.pop("seed", None)
        return cfg


@dataclass
class Section:
    """试卷中的一个大题块。"""

    label: str
    per_score: int
    questions: List[Question] = field(default_factory=list)
    number_start: int = 0
    number_end: int = 0

    @property
    def key(self) -> str:
        return KEY_BY_LABEL.get(self.label, self.label)

    @property
    def count(self) -> int:
        return len(self.questions)

    @property
    def points(self) -> int:
        return self.count * self.per_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "key": self.key,
            "per_score": self.per_score,
            "count": self.count,
            "points": self.points,
            "number_start": self.number_start,
            "number_end": self.number_end,
            "questions": [q.to_dict() for q in self.questions],
        }


@dataclass
class Paper:
    """一份试卷。"""

    exam_number: int
    sections: List[Section] = field(default_factory=list)
    content: str = ""  # 纯文本渲染（预览与 docx 的既有输入）
    all_answers: List[Tuple] = field(default_factory=list)  # [(q_num, answer, label)]
    total_count: int = 0
    total_score: int = 0
    seed: int = 0
    reused_qids: List[str] = field(default_factory=list)
    warnings: List[Warning] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exam_number": self.exam_number,
            "content": self.content,
            "total_count": self.total_count,
            "total_score": self.total_score,
            "seed": self.seed,
            "reused_qids": list(self.reused_qids),
            "sections": [s.to_dict() for s in self.sections],
            "warnings": [w.to_dict() for w in self.warnings],
        }

    def to_legacy_dict(self, config: "PaperConfig") -> Dict[str, Any]:
        """旧版 ``generate_exam_datas`` 的字典结构，保证 gui/docx 层不用改。"""
        return {
            "exam_title": config.exam_title,
            "student_name": config.student_name,
            "exam_time": config.exam_time,
            "include_answers": config.include_answers,
            "all_answers": list(self.all_answers),
            "total_count": self.total_count,
            "exam_content": self.content,
            "exam_number": self.exam_number,
            "warnings": [w.to_dict() for w in self.warnings],
        }


@dataclass
class GenerationResult:
    """一次组卷的完整结果。"""

    papers: List[Paper] = field(default_factory=list)
    warnings: List[Warning] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "papers": [p.to_dict() for p in self.papers],
            "warnings": [w.to_dict() for w in self.warnings],
            "stats": self.stats,
        }


# ── 内部工具 ─────────────────────────────────────────────────────────


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _default_score(key):
    from .constants import TYPE_BY_KEY

    return TYPE_BY_KEY.get(key, {}).get("score", 1)


def _discover_type_keys(cfg):
    """从扁平字典里发现出现过哪些题型键（含注册表之外的额外题型）。"""
    keys = [qt["key"] for qt in QUESTION_TYPES]
    for name in cfg:
        if name.startswith("include_"):
            extra = name[len("include_") :]
            if extra and extra not in keys:
                keys.append(extra)
    return keys
