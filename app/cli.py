"""命令行入口 —— 同时也是业务层的端到端验证入口。

界面层（``ui/``）只是 ``app`` + ``renderers`` 的一层薄壳，
所以这里的流程与图形界面走的完全是同一条代码路径。

用法::

    python -m app.cli --bank 题库模板.xlsx --out ./out --count 2 --pdf --card
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from .docmodel import build_paper_blocks
from .errors import DomainError
from .generator import generate
from .loader import load_question_bank
from .models import PaperConfig
from .pool import QuestionPool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="考试试卷生成系统 —— 命令行生成试卷",
    )
    parser.add_argument("--bank", required=True, help="Excel/CSV 题库路径")
    parser.add_argument("--out", default="./out", help="输出目录（默认 ./out）")
    parser.add_argument("--count", type=int, default=1, help="生成份数")
    parser.add_argument("--size", default="A4", choices=["A4", "A3"], help="纸张")
    parser.add_argument("--title", default="考试试卷", help="试卷标题")
    parser.add_argument("--seed", type=int, default=None, help="随机种子（复现同一份卷）")

    parser.add_argument("--judgment", type=int, default=0, help="判断题数量")
    parser.add_argument("--mcq", type=int, default=0, help="单选题数量")
    parser.add_argument("--multi", type=int, default=0, help="多选题数量")

    parser.add_argument("--answers", action="store_true", help="包含参考答案")
    parser.add_argument("--pdf", action="store_true", help="额外导出 PDF")
    parser.add_argument("--card", action="store_true", help="额外导出答题卡 PDF")
    parser.add_argument("--card-docx", action="store_true", help="额外导出答题卡 Word")
    parser.add_argument("--header", default="", help="页眉文字")
    parser.add_argument(
        "--avoid-history", action="store_true", help="排除历史出过的题"
    )
    return parser


def config_from_args(args) -> PaperConfig:
    return PaperConfig.from_legacy(
        {
            "export_mode": "随机抽取",
            "exam_title": args.title,
            "student_name": "姓名：__________  考号：__________",
            "header_text": args.header,
            "include_answers": args.answers,
            "include_judgment": args.judgment > 0,
            "include_mcq": args.mcq > 0,
            "include_mcq_multi": args.multi > 0,
            "judgment_count": args.judgment,
            "mcq_count": args.mcq,
            "mcq_multi_count": args.multi,
            "judgment_score": 1,
            "mcq_score": 2,
            "mcq_multi_score": 3,
            "seed": args.seed,
            "avoid_history": args.avoid_history,
            "paper_size": args.size,
        }
    )


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    if not (args.judgment or args.mcq or args.multi):
        print("请至少指定一种题型的数量（--judgment / --mcq / --multi）", file=sys.stderr)
        return 2

    started = time.time()
    try:
        pool = QuestionPool(load_question_bank(args.bank))
    except DomainError as error:
        print(f"[题库错误] {error.code}: {error.message}", file=sys.stderr)
        if error.hint:
            print(f"  {error.hint}", file=sys.stderr)
        return 1

    print(f"题库：{len(pool)} 题 {pool.count_by_type()}")
    if pool.difficulty_values():
        print(f"难度：{pool.difficulty_values()}")
    if pool.knowledge_values():
        print(f"知识点：{pool.knowledge_values()[:8]}")

    config = config_from_args(args)
    config.exam_count = args.count

    try:
        result = generate(config, pool)
    except DomainError as error:
        print(f"[组卷错误] {error.code}: {error.message}", file=sys.stderr)
        if error.hint:
            print(f"  {error.hint}", file=sys.stderr)
        return 1

    for warning in result.warnings:
        print(f"[提示] {warning.message}")

    os.makedirs(args.out, exist_ok=True)
    written = []

    from renderers.docx_renderer import render_docx

    for paper in result.papers:
        blocks = build_paper_blocks(paper, config)
        suffix = f"-{paper.exam_number}" if len(result.papers) > 1 else ""
        docx_path = os.path.join(args.out, f"试卷{suffix}.docx")
        render_docx(blocks, docx_path, args.size, config.header_text)
        written.append(docx_path)

        if args.pdf:
            from renderers.pdf_renderer import render_pdf

            pdf_path = os.path.join(args.out, f"试卷{suffix}.pdf")
            render_pdf(blocks, pdf_path, args.size, config.header_text)
            written.append(pdf_path)

    if args.card or args.card_docx:
        from renderers.answer_card import build_answer_card_document

        card_blocks = build_answer_card_document(result.papers, config)

        if args.card_docx:
            from renderers.docx_renderer import render_docx

            card_docx = os.path.join(args.out, "答题卡.docx")
            render_docx(card_blocks, card_docx, "A4", "")
            written.append(card_docx)

        if args.card:
            from renderers.pdf_renderer import render_pdf

            card_pdf = os.path.join(args.out, "答题卡.pdf")
            render_pdf(card_blocks, card_pdf, "A4", "")
            written.append(card_pdf)

    elapsed = time.time() - started
    print(
        f"完成：{len(result.papers)} 份试卷，"
        f"每份 {result.papers[0].total_count} 题 / {result.papers[0].total_score} 分，"
        f"用时 {elapsed:.2f}s"
    )
    for path in written:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
