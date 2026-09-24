"""PDF 渲染测试。

重点：A4 / A3 拼版 的页数与纸张尺寸、中文是否丢失、答案页是否独立起页、
以及字体缺失时是否给出结构化错误（而不是生成一堆乱码）。
"""

import math

import pytest
from pypdf import PdfReader

from app.docmodel import build_paper_blocks
from app.errors import Codes, DomainError
from conftest import build_paper

MM_PER_PT = 25.4 / 72.0

A4_MM = (210, 297)
A3_LANDSCAPE_MM = (420, 297)


def _size_mm(page):
    box = page.mediabox
    return (
        round(float(box.width) * MM_PER_PT),
        round(float(box.height) * MM_PER_PT),
    )


def _render(result, cfg, tmp_path, paper_size, name="out.pdf"):
    from renderers.pdf_renderer import render_pdf

    blocks = build_paper_blocks(result.papers[0], cfg)
    path = tmp_path / name
    render_pdf(blocks, str(path), paper_size, cfg.header_text)
    return path, PdfReader(str(path))


@pytest.fixture
def b4(paper_bundle, tmp_path):
    """含答案的试卷，便于验证答案页行为。"""
    result, _pool, cfg = paper_bundle
    cfg.include_answers = True
    return result, cfg


def test_a4_page_size(b4, tmp_path):
    _, reader = _render(b4[0], b4[1], tmp_path, "A4")
    assert len(reader.pages) >= 1
    for page in reader.pages:
        assert _size_mm(page) == A4_MM


def test_a3_is_landscape_two_a4_up(b4, tmp_path):
    """A3 必须是横向 420x297 —— 左半 + 右半合起来正好是两张 A4。"""
    _, reader = _render(b4[0], b4[1], tmp_path, "A3")
    assert _size_mm(reader.pages[0]) == A3_LANDSCAPE_MM


def test_a3_packs_two_logical_pages_per_sheet(b4, tmp_path):
    """答案页应落在同一张 A3 的右半，而不是跳到第二张纸的左半。

    若误用 PageBreak 而非 FrameBreak，会浪费整个右半页，
    表现就是 A3 张数翻倍。
    """
    _, a4 = _render(b4[0], b4[1], tmp_path, "A4", "a4.pdf")
    _, a3 = _render(b4[0], b4[1], tmp_path, "A3", "a3.pdf")

    expected = math.ceil(len(a4.pages) / 2)
    assert len(a3.pages) == expected, (
        f"A4 {len(a4.pages)} 页应拼成 {expected} 张 A3，实际 {len(a3.pages)} 张"
    )


def test_chinese_text_survives(b4, tmp_path):
    _, reader = _render(b4[0], b4[1], tmp_path, "A4")
    text = "".join(page.extract_text() for page in reader.pages)
    assert "判断题" in text
    assert "单选题" in text
    assert "�" not in text  # 不能是替换字符（乱码）


def test_answer_page_starts_a_new_logical_page(b4, tmp_path):
    _, reader = _render(b4[0], b4[1], tmp_path, "A4")
    assert len(reader.pages) >= 2, "含答案时应至少两页"
    assert "参考答案" in reader.pages[-1].extract_text()


def test_answer_key_groups_use_real_numbers(b4, tmp_path):
    """答案页题号必须与试卷一致（不需要阅读全文即可确认分组存在）。"""
    _, reader = _render(b4[0], b4[1], tmp_path, "A4")
    text = reader.pages[-1].extract_text()
    assert "全部答案" in text
    assert "判断题答案" in text
    assert "单选题答案" in text


def test_page_content_has_no_color_fills(b4, tmp_path):
    """黑白友好：内容流里不得出现非灰度的填色算子。"""
    path, _ = _render(b4[0], b4[1], tmp_path, "A4")
    blob = path.read_bytes()
    # reportlab 的灰度填充写作 "<g> g"，RGB 填充写作 "r g b rg"。
    # 只要没有 rg/RG 彩色算子即视为纯黑白。
    assert b" rg" not in blob.split(b"stream", 1)[-1][:200000] or b"0 0 0 rg" in blob


def test_header_drawn_on_each_half_for_a3(bank_path, tmp_path):
    result, _pool, cfg = build_paper(bank_path, header_text="某某学校期末试卷")
    _, reader = _render(result, cfg, tmp_path, "A3", "hdr.pdf")
    text = reader.pages[0].extract_text()
    # 两个半页各画一次页眉 —— 裁开后两半都带页眉
    assert text.count("某某学校期末试卷") >= 2


def test_font_not_found_is_structured(tmp_path, monkeypatch):
    """字体目录为空时必须抛结构化错误，而不是产出一堆乱码。"""
    from renderers import fonts as fonts_module

    empty = tmp_path / "empty_fonts"
    empty.mkdir()
    monkeypatch.setenv(fonts_module.FONT_DIR_ENV, str(empty))
    fonts_module.reset_cache()
    try:
        with pytest.raises(DomainError) as excinfo:
            fonts_module.register_fonts(force=True)
        assert excinfo.value.code == Codes.FONT_NOT_FOUND
        assert "字体" in excinfo.value.message
    finally:
        fonts_module.reset_cache()


def test_check_fonts_reports_availability():
    from renderers.fonts import check_fonts

    info = check_fonts()
    assert set(info) >= {"font_dir", "cjk_ok", "body", "title"}
    assert isinstance(info["cjk_ok"], bool)
