"""文档中间表示（Block）。

**这是排版层的唯一真相**：``renderers/docx_renderer`` 与 ``renderers/pdf_renderer``
都只是 Block 列表的消费者。

旧实现是「先生成纯文本，再由 docx 层用 ``line[0].isdigit()`` 反解析」——
那个反解析对**题干以数字开头的题**会误判，属于潜在缺陷。Block 从源头消除了它。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .constants import ESSAY_BLANK_LINES, ESSAY_LABELS
from .models import Paper, PaperConfig, Section
from .numbering import (
    AnswerGroup,
    build_answer_groups,
    build_essay_answers,
    number_of,
)


class Block:
    """所有块的基类。渲染层按类型分派。"""

    def to_dict(self) -> Dict[str, Any]:  # pragma: no cover - 便于调试
        return {"kind": type(self).__name__}


@dataclass
class Heading(Block):
    """试卷大标题。"""

    text: str
    level: int = 1
    align: str = "center"


@dataclass
class Paragraph(Block):
    """普通段落。"""

    text: str
    bold: bool = False
    align: str = "left"
    size: float = 10.5


@dataclass
class SectionHeader(Block):
    """大题标题，如「一、判断题（每题 1 分，共 10 分）」。"""

    text: str
    label: str = ""
    number_start: int = 0
    number_end: int = 0


@dataclass
class QuestionBlock(Block):
    """一道题。"""

    number: int
    stem: str
    label: str = ""
    options: Tuple[Tuple[str, str], ...] = ()
    # 判断题在题干后留一条作答横线
    answer_blank: bool = False
    # 简答题在题干后留若干条作答横线
    blank_lines: int = 0


@dataclass
class AnswerKey(Block):
    """参考答案页。

    客观题按题号压成紧凑的一行行；简答题的答案是成段文字，单独列出。
    """

    groups: List[AnswerGroup] = field(default_factory=list)
    essay: List[Tuple[int, str]] = field(default_factory=list)


@dataclass
class PageBreak(Block):
    pass


@dataclass
class AnswerCardHead(Block):
    """答题卡卡头。"""

    title: str = ""
    fields: Tuple[str, ...] = ()
    paper_type_label: str = ""
    paper_type_count: int = 0


@dataclass
class AnswerCardSection(Block):
    """答题卡上的一个作答区。

    采用**填写式**（写 √/× 或 ABCD）而非涂卡圈：

    * 本项目不做机读，涂卡圈没有收益，只占地方
    * 涂卡圈依赖印刷精度对齐，填写式没有这个问题
    * 同样题量下占用面积不到一半，120 题能压进一页

    每行放几道题由渲染层按版心宽度算出来，不在这里配置。
    """

    label: str = ""
    number_start: int = 0
    number_end: int = 0
    hint: str = ""  # 填写提示，如「√ / ×」


@dataclass
class AnswerCardEssay(Block):
    """答题卡上的简答题作答区。

    简答题不能像客观题那样排成格里填字母 —— 需要成行的书写空间。
    """

    label: str = ""
    numbers: Tuple[int, ...] = ()
    lines_per_question: int = 2


@dataclass
class Instructions(Block):
    """考试须知 / 填涂说明。"""

    title: str = ""
    lines: Tuple[str, ...] = ()


@dataclass
class Spacer(Block):
    height: float = 6.0


# 答题卡每行放几道题。两个渲染层共用，保证 Word 与 PDF 版式一致。
# 15 列在 A4 版心（168mm 可用宽）下每格约 11mm，足够手写「√」或「ABCD」。
ANSWER_CARD_PER_ROW = 15


# ── 从 Paper 构造 Blocks ─────────────────────────────────────────────


def _section_header_text(section: Section, index: int) -> str:
    prefix = "一二三四五六七八九十"
    ordinal = prefix[index] if index < len(prefix) else str(index + 1)
    return (
        f"{ordinal}、{section.label}"
        f"（每题{section.per_score}分，共{section.points}分）"
    )


def build_paper_blocks(paper: Paper, config: PaperConfig) -> List[Block]:
    """把一份试卷转成 Block 列表。"""
    blocks: List[Block] = []

    title = config.exam_title
    if config.exam_count > 1 or paper.exam_number > 1:
        title = f"{title}（试卷{paper.exam_number}）"
    blocks.append(Heading(title, level=1))

    if config.student_name:
        blocks.append(Paragraph(config.student_name, align="center", size=10))

    if config.exam_time:
        blocks.append(
            Paragraph(f"考试时间：{config.exam_time} 分钟", bold=True, size=10)
        )

    blocks.append(Spacer(4))

    # 已经出答题卡时，试卷上不再留任何作答空间 —— 学生写在答题卡上，
    # 试卷上的横线只是白占版面。判断题的作答线同理。
    needs_write_space = not config.include_answer_card

    for index, section in enumerate(paper.sections):
        if section.count == 0:
            continue
        blocks.append(SectionHeader(
            _section_header_text(section, index),
            label=section.label,
            number_start=section.number_start,
            number_end=section.number_end,
        ))
        for offset, question in enumerate(section.questions):
            is_essay = section.label in ESSAY_LABELS
            blocks.append(
                QuestionBlock(
                    number=number_of(section, offset),
                    stem=question.stem,
                    label=section.label,
                    options=question.options,
                    answer_blank=(section.label == "判断题" and needs_write_space),
                    blank_lines=(
                        ESSAY_BLANK_LINES if (is_essay and needs_write_space) else 0
                    ),
                )
            )

    if config.include_answers:
        groups = build_answer_groups(paper.sections)
        essays = build_essay_answers(paper.sections)
        if groups or essays:
            blocks.append(PageBreak())
            blocks.append(Heading("参考答案（教师用）", level=2))
            blocks.append(AnswerKey(groups=groups, essay=essays))

    return blocks


def build_blocks_for_docx(paper: Paper, config: PaperConfig) -> List[Block]:
    """docx 与 pdf 共用同一套 Block —— 目前语义完全一致，保留钩子便于日后分化。"""
    return build_paper_blocks(paper, config)
