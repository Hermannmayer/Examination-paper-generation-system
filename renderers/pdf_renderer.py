"""PDF 渲染（reportlab）。

## 为什么是 reportlab 而不是 fpdf2

* **许可**：reportlab 是 BSD；fpdf2 是 LGPL-3.0，静态打包成闭源 exe 有合规争议。
* **TTC 原生支持**：``TTFont(name, path, subfontIndex=...)`` 直接支持字体集合。
* **精确排版**：``platypus.Table`` 固定列宽，答题卡涂卡格对齐必需。

## A3 = 两张 A4 拼版

A3 横向（420×297mm）左半与右半各是一个**独立的 A4 纵向逻辑页**：
内容先填满左栏（第 1 页），再流到右栏（第 2 页），然后翻到下一张 A3。
对折或裁切后，每一半都是版心正常的 A4 试卷。

## 黑白打印友好（硬性约束）

1. 所有文字纯黑，强调只用**加粗 / 字号 / 实线**，绝不用颜色承载信息
2. 线宽 ≥ 0.6pt —— 更细的线在 300dpi 以下会丢失
3. 不使用浅灰填充 —— 复印后会变成噪点
4. 答案页单独起页并标注「教师用」，避免与试卷混印
"""

from __future__ import annotations

from typing import List, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    FrameBreak,
    PageBreak as RLPageBreak,
    PageTemplate,
    Paragraph as RLParagraph,
    Spacer as RLSpacer,
    Table,
    TableStyle,
)

from app.docmodel import (
    AnswerCardEssay,
    AnswerCardHead,
    AnswerCardSection,
    AnswerKey,
    Block,
    Heading,
    Instructions,
    PageBreak,
    Paragraph,
    QuestionBlock,
    SectionHeader,
    Spacer,
)

from .answer_card import bands
from .fonts import register_fonts

# 纸张（mm）
A4 = (210.0, 297.0)
A3_LANDSCAPE = (420.0, 297.0)

MARGIN_TOP = 15.0
MARGIN_BOTTOM = 15.0
MARGIN_LEFT = 20.0
MARGIN_RIGHT = 20.0

# 黑白打印的最小线宽
MIN_LINE_WIDTH = 0.6

MM = 72.0 / 25.4  # 1mm = 2.8346pt

_BLACK = colors.black
_HEADER_FONT_SIZE = 9


def _mm(value: float) -> float:
    return value * MM


# ── 样式 ─────────────────────────────────────────────────────────────


def _build_styles(fonts):
    base = ParagraphStyle(
        "ExamBase",
        fontName=fonts.body,
        fontSize=10.5,
        leading=15,
        alignment=TA_LEFT,
        textColor=_BLACK,
        spaceAfter=2,
    )
    return {
        "base": base,
        "title": ParagraphStyle(
            "ExamTitle",
            parent=base,
            fontName=fonts.title,
            fontSize=17,
            leading=24,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "ExamSubtitle",
            parent=base,
            fontName=fonts.title,
            fontSize=14,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "student": ParagraphStyle(
            "ExamStudent", parent=base, alignment=TA_CENTER, spaceAfter=3
        ),
        "time": ParagraphStyle(
            "ExamTime", parent=base, fontName=fonts.title, spaceAfter=4
        ),
        "section": ParagraphStyle(
            "ExamSection",
            parent=base,
            fontName=fonts.title,
            fontSize=11,
            leading=16,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "question": ParagraphStyle("ExamQuestion", parent=base, spaceAfter=1),
        "options": ParagraphStyle(
            "ExamOptions", parent=base, leftIndent=_mm(6), spaceAfter=4
        ),
        "answer": ParagraphStyle("ExamAnswer", parent=base, spaceAfter=3),
        # 简答题答案：缩进 + 放大行距，成段文字读起来才不挤
        "essay": ParagraphStyle(
            "ExamEssay",
            parent=base,
            leftIndent=_mm(6),
            leading=17,
            spaceAfter=7,
        ),
        "card_field": ParagraphStyle(
            "CardField", parent=base, fontSize=11, leading=24
        ),
    }


# ── 入口 ─────────────────────────────────────────────────────────────


def render_pdf(
    blocks: Sequence[Block],
    output_path: str,
    paper_size: str = "A4",
    header_text: str = "",
) -> str:
    """把 Block 列表渲染成 PDF，返回写入路径。"""
    fonts = register_fonts()
    styles = _build_styles(fonts)

    # A3 是"两张 A4 拼版"，一页里有两个半页帧。
    # 分页必须用 FrameBreak（前进到下一个半页），否则会跳到下一张物理纸，
    # 把右半页留成空白。A4 只有一个帧，FrameBreak 与 PageBreak 等价。
    break_flowable = FrameBreak if paper_size == "A3" else RLPageBreak

    # 版心宽度：两种纸张的每个帧都是"整幅 A4 减去左右页边距"，
    # 所以数值相同。答题卡要靠它反推每行能放几道题。
    # 留 2mm 安全余量，避免表格紧贴页边距。
    context = {
        "styles": styles,
        "break_flowable": break_flowable,
        "content_width": _mm(A4[0] - MARGIN_LEFT - MARGIN_RIGHT - 2.0),
    }

    story: List = []
    for block in blocks:
        story.extend(_block_to_flowables(block, context))

    if not story:
        story.append(RLParagraph("（无内容）", styles["base"]))

    doc = _build_doc_template(output_path, paper_size, header_text, fonts)
    doc.build(story)
    return output_path


def _build_doc_template(output_path, paper_size, header_text, fonts):
    if paper_size == "A3":
        page_width, page_height = A3_LANDSCAPE
        halves = [0.0, A4[0]]  # 左半起点、右半起点
    else:
        page_width, page_height = A4
        halves = [0.0]

    frames = [
        Frame(
            _mm(offset),
            _mm(0),
            _mm(A4[0]),
            _mm(A4[1]),
            leftPadding=_mm(MARGIN_LEFT),
            rightPadding=_mm(MARGIN_RIGHT),
            topPadding=_mm(MARGIN_TOP),
            bottomPadding=_mm(MARGIN_BOTTOM),
            id=f"half{index}",
        )
        for index, offset in enumerate(halves)
    ]

    doc = BaseDocTemplate(
        output_path,
        pagesize=(_mm(page_width), _mm(page_height)),
        title="试卷",
        author="考试试卷生成系统",
        subject="",
    )

    def draw_header(canvas, _doc):
        """页眉在**每个半页**各画一次 —— 裁切后两半都带着页眉。"""
        if not header_text:
            return
        canvas.saveState()
        canvas.setFillColor(_BLACK)
        canvas.setFont(fonts.body, _HEADER_FONT_SIZE)
        for offset in halves:
            canvas.drawCentredString(
                _mm(offset + A4[0] / 2.0),
                _mm(page_height - MARGIN_TOP * 0.55),
                header_text,
            )
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="main", frames=frames, onPage=draw_header)])
    return doc


# ── Block → flowable ─────────────────────────────────────────────────


def _block_to_flowables(block: Block, context) -> List:
    styles = context["styles"]

    if isinstance(block, PageBreak):
        return [context["break_flowable"]()]

    if isinstance(block, Spacer):
        return [RLSpacer(1, block.height)]

    if isinstance(block, Heading):
        style = styles["title"] if block.level == 1 else styles["subtitle"]
        return [RLParagraph(_escape(block.text), style)]

    if isinstance(block, SectionHeader):
        return [RLParagraph(_escape(block.text), styles["section"])]

    if isinstance(block, Paragraph):
        style = styles["student"] if block.align == "center" else styles["question"]
        text = _escape(block.text)
        if block.bold:
            text = f"<b>{text}</b>"
        return [RLParagraph(text, style)]

    if isinstance(block, QuestionBlock):
        return _question_flowables(block, styles)

    if isinstance(block, AnswerKey):
        out = [
            RLParagraph(
                f"<b>{_escape(group.label)}答案:</b> {_escape(group.span_text)}",
                styles["answer"],
            )
            for group in block.groups
        ]
        if block.essay:
            out.append(
                RLParagraph("<b>简答题参考答案:</b>", styles["section"])
            )
            for number, answer in block.essay:
                out.append(
                    RLParagraph(
                        f"<b>{number}.</b> {_escape(answer)}",
                        styles["essay"],
                    )
                )
        return out

    if isinstance(block, Instructions):
        out = []
        if block.title:
            out.append(RLParagraph(f"<b>{_escape(block.title)}</b>", styles["section"]))
        out.extend(RLParagraph(_escape(line), styles["answer"]) for line in block.lines)
        return out

    if isinstance(block, AnswerCardHead):
        return _answer_card_head(block, styles)

    if isinstance(block, AnswerCardSection):
        table = _answer_card_grid(block, styles, context["content_width"])
        return [table] if table is not None else []

    if isinstance(block, AnswerCardEssay):
        out = []
        for number in block.numbers:
            out.append(RLParagraph(f"<b>{number}.</b>", styles["question"]))
            out.append(_writing_lines(block.lines_per_question, styles))
            out.append(RLSpacer(1, _mm(4)))
        return out

    return []


def _question_flowables(block: QuestionBlock, styles) -> List:
    stem = _escape(block.stem)
    if block.answer_blank:
        head = f"<b>{block.number}.</b> {stem} ________"
    else:
        head = f"<b>{block.number}.</b> {stem} [{_escape(block.label)}]"

    out = [RLParagraph(head, styles["question"])]

    if block.options:
        rendered = "&nbsp;&nbsp;&nbsp;&nbsp;".join(
            f"{letter}. {_escape(text)}" for letter, text in block.options
        )
        out.append(RLParagraph(rendered, styles["options"]))

    if block.blank_lines:
        out.append(_writing_lines(block.blank_lines, styles))
    return out


def _writing_lines(count: int, styles) -> Table:
    """简答题的作答横线。

    用「只有下边框的表格」而不是一串下划线字符：线是连续的，不会因字体
    的字距出现断口，黑白打印时也稳定。
    """
    table = Table(
        [[""] for _ in range(count)],
        colWidths=[_mm(168)],
        rowHeights=[_mm(9)] * count,
    )
    table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 0.6, _BLACK),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    table.hAlign = "LEFT"
    return table


def _answer_card_head(block: AnswerCardHead, styles) -> List:
    out = []
    if block.title:
        out.append(RLParagraph(_escape(block.title), styles["title"]))
    if block.fields:
        out.append(
            RLParagraph(
                "　　　　".join(f"{_escape(f)}：__________" for f in block.fields),
                styles["card_field"],
            )
        )
    if block.paper_type_label and block.paper_type_count > 0:
        boxes = "　".join(f"[ ] {i + 1}" for i in range(block.paper_type_count))
        out.append(
            RLParagraph(f"{_escape(block.paper_type_label)}：{boxes}", styles["card_field"])
        )
    return out


def _answer_card_grid(block: AnswerCardSection, styles, content_width: float):
    """填写式作答区。

    版式：每行放 ``ANSWER_CARD_PER_ROW`` 题，**两行一组** ——
    上面一行是题号，下面一行留白供填写。这样比涂卡圈省一半以上高度，
    120 题能压进一页 A4。

    列宽显式计算：表格一旦宽过版心，reportlab 无法收缩只能溢出页面
    （实测曾出现文本 x = -7.9pt，即跑到纸张左边之外）。
    """
    if block.number_end < block.number_start:
        return None

    questions = bands(block.number_start, block.number_end)
    if not questions:
        return None

    column_count = max(len(band) for band in questions)
    column_width = content_width / column_count

    rows = []
    for band in questions:
        row_numbers = [str(n) for n in band]
        row_numbers += [""] * (column_count - len(band))
        rows.append(row_numbers)
        rows.append([""] * column_count)  # 留白作答行

    # 交替行高：题号行矮、作答行高，给手写留出空间
    row_heights = [_mm(6.5) if index % 2 == 0 else _mm(9.0) for index in range(len(rows))]

    table = Table(
        rows,
        colWidths=[column_width] * column_count,
        rowHeights=row_heights,
    )
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), MIN_LINE_WIDTH, _BLACK),
                ("FONTNAME", (0, 0), (-1, -1), styles["answer"].fontName),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    table.hAlign = "LEFT"
    return table


def _escape(text) -> str:
    """转义 reportlab Paragraph 的标记字符。"""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
