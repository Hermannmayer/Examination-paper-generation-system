"""答题卡构造。

采用**填写式**（写 √/× 或 ABCD）而不是涂卡式：

* 本项目定位是本地小工具、人工批改，不做 OMR 机读 —— 涂卡圈除了占地方
  没有任何收益
* 涂卡圈要能涂，就得保证印刷精度对齐；填写式没有这个约束
* 同样题量下填写式占用面积不到一半：120 题能压进一页 A4，
  涂卡式要两三页

题号一律直接取自 ``Section.number_start / number_end``，
与答案页同一个约束：答题卡上的题号必须和试卷上的题号一致。
"""

from __future__ import annotations

from typing import List, Sequence

from app.constants import ESSAY_CARD_LINES, ESSAY_LABELS
from app.docmodel import (
    ANSWER_CARD_PER_ROW,
    AnswerCardEssay,
    AnswerCardHead,
    AnswerCardSection,
    Block,
    Heading,
    Instructions,
    PageBreak,
    Spacer,
)
from app.models import Paper, PaperConfig

HEADER_FIELDS = ("姓名", "考号", "班级", "座位号")

JUDGMENT_HINT = "√ / ×"
CHOICE_HINT = "A / B / C / D"

DEFAULT_INSTRUCTIONS = (
    "1. 答题前请先在答题卡上填写姓名、考号、班级、座位号，字迹须工整。",
    "2. 判断题填「√」或「×」；选择题填写选项字母，如单选填 A、多选填 ABD。",
    "3. 答案请填写在对应题号下方的空格内，不要写在题号上。",
    "4. 修改时请划掉原答案后在旁边重写，不要使用修正带或涂改液。",
    "5. 保持卷面整洁，不要折叠、污损答题卡。",
)


def hint_for(label: str) -> str:
    return JUDGMENT_HINT if label == "判断题" else CHOICE_HINT


def build_answer_card_blocks(
    paper: Paper,
    config: PaperConfig,
    paper_count: int = 1,
    fields: Sequence[str] = HEADER_FIELDS,
) -> List[Block]:
    """构造一份答题卡的 Block 列表。"""
    blocks: List[Block] = []

    blocks.append(
        AnswerCardHead(
            title=f"{config.exam_title} 答题卡",
            fields=tuple(fields),
            paper_type_label="试卷类型",
            paper_type_count=max(1, paper_count),
        )
    )
    blocks.append(Spacer(6))

    for section in paper.sections:
        if section.count == 0:
            continue

        if section.label in ESSAY_LABELS:
            blocks.append(
                Heading(
                    f"{section.label}（{section.number_start}-{section.number_end} 题，"
                    f"每题 {section.per_score} 分，请在横线上作答）",
                    level=2,
                )
            )
            blocks.append(
                AnswerCardEssay(
                    label=section.label,
                    numbers=tuple(
                        range(section.number_start, section.number_end + 1)
                    ),
                    lines_per_question=ESSAY_CARD_LINES,
                )
            )
            continue

        blocks.append(
            Heading(
                f"{section.label}（{section.number_start}-{section.number_end} 题，"
                f"每题 {section.per_score} 分，填 {hint_for(section.label)}）",
                level=2,
            )
        )
        blocks.append(
            AnswerCardSection(
                label=section.label,
                number_start=section.number_start,
                number_end=section.number_end,
                hint=hint_for(section.label),
            )
        )

    blocks.append(Spacer(8))
    blocks.append(Instructions(title="注意事项", lines=DEFAULT_INSTRUCTIONS))
    return blocks


def build_answer_card_document(
    papers: Sequence[Paper],
    config: PaperConfig,
) -> List[Block]:
    """把若干份试卷的答题卡拼成一个文档（每份之间分页）。"""
    blocks: List[Block] = []
    for index, paper in enumerate(papers):
        if index > 0:
            blocks.append(PageBreak())
        blocks.extend(build_answer_card_blocks(paper, config, paper_count=len(papers)))
    return blocks


def bands(number_start: int, number_end: int, per_row: int = ANSWER_CARD_PER_ROW):
    """把题号切成每行 ``per_row`` 个的组。"""
    current = number_start
    result = []
    while current <= number_end:
        result.append(list(range(current, min(current + per_row, number_end + 1))))
        current += per_row
    return result
