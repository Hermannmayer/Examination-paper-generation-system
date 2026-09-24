"""题库读取测试。

重点覆盖 pandas → openpyxl 移植最容易出问题的语义差异：
dtype 漂移（``1``(int) / ``1.0``(float) / ``"1"``(str)）、
空值判定（``notna`` → ``_is_blank``）、表头 BOM。
"""

import openpyxl
import pytest

from app.errors import Codes, DomainError
from app.loader import cell_to_text, load_question_bank, normalize_answer


# ── 单元格与答案归一化 ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "value,expected",
    [
        (1, "1"),
        (1.0, "1"),  # 关键：不能变成 "1.0"
        (0.0, "0"),
        ("1", "1"),
        (True, "TRUE"),
        (None, ""),
        ("  题干  ", "题干"),
        (2.5, "2.5"),
    ],
)
def test_cell_to_text(value, expected):
    assert cell_to_text(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (1, "√"),
        (1.0, "√"),  # 旧实现只认字符串 "1"，这里会漏成 "1.0"
        ("1", "√"),
        ("√", "√"),
        ("对", "√"),
        ("正确", "√"),
        (True, "√"),
        (0, "×"),
        (0.0, "×"),
        ("0", "×"),
        ("×", "×"),
        ("错", "×"),
        (False, "×"),
        ("", ""),
    ],
)
def test_normalize_answer_judgment(value, expected):
    assert normalize_answer(value, "判断题") == expected


def test_normalize_answer_other_types_untouched():
    assert normalize_answer("ABD", "多选题") == "ABD"
    assert normalize_answer("a", "单选题") == "a"
    assert normalize_answer(1, "单选题") == "1"


# ── 文件级 ──────────────────────────────────────────────────────────


def test_missing_columns_reports_which_ones(tmp_path):
    from conftest import make_bank

    bad = make_bank(tmp_path / "bad.xlsx", omit_column="正确答案")
    with pytest.raises(DomainError) as excinfo:
        load_question_bank(str(bad))

    error = excinfo.value
    assert error.code == Codes.MISSING_COLUMNS
    assert "正确答案" in error.message
    assert error.details["missing"] == ["正确答案"]


def test_unsupported_xls(tmp_path):
    path = tmp_path / "old.xls"
    path.write_bytes(b"\xd0\xcf\x11\xe0")  # 假的 OLE 头
    with pytest.raises(DomainError) as excinfo:
        load_question_bank(str(path))
    assert excinfo.value.code == Codes.UNSUPPORTED_FORMAT
    assert ".xls" in excinfo.value.message


def test_unsupported_extension(tmp_path):
    path = tmp_path / "data.pdf"
    path.write_bytes(b"%PDF-1.4")
    with pytest.raises(DomainError) as excinfo:
        load_question_bank(str(path))
    assert excinfo.value.code == Codes.UNSUPPORTED_FORMAT


def test_file_not_found(tmp_path):
    with pytest.raises(DomainError) as excinfo:
        load_question_bank(str(tmp_path / "nope.xlsx"))
    assert excinfo.value.code == Codes.FILE_NOT_FOUND


def test_empty_bank_raises(tmp_path):
    path = tmp_path / "empty.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["题型", "题目", "正确答案"])
    wb.save(path)

    with pytest.raises(DomainError) as excinfo:
        load_question_bank(str(path))
    assert excinfo.value.code == Codes.EMPTY_SHEET


def test_numeric_judgment_answers_from_real_excel(tmp_path):
    """真实 Excel 里用户输入 1/0 会存成数字 —— 必须仍归一化为 √/×。"""
    path = tmp_path / "numeric.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["题型", "题目", "正确答案"])
    ws.append(["判断题", "题干一", 1])  # int
    ws.append(["判断题", "题干二", 0])  # int
    wb.save(path)

    result = load_question_bank(str(path))
    answers = {q.stem: q.answer for q in result.questions}
    assert answers == {"题干一": "√", "题干二": "×"}


def test_header_with_bom_and_spaces(tmp_path):
    """Excel 导出的 CSV 常带 BOM，且表头可能有空格。"""
    path = tmp_path / "bom.csv"
    path.write_text(
        "﻿题型 ,题目,正确答案\n判断题,题干一,1\n",
        encoding="utf-8-sig",
    )
    result = load_question_bank(str(path))
    assert len(result.questions) == 1
    assert result.questions[0].answer == "√"


def test_gbk_csv(tmp_path):
    path = tmp_path / "gbk.csv"
    path.write_bytes("题型,题目,正确答案\n判断题,中文题干,1\n".encode("gbk"))

    result = load_question_bank(str(path))
    assert result.questions[0].stem == "中文题干"
    assert result.questions[0].answer == "√"
    assert any(w.code == "ENCODING_FALLBACK" for w in result.warnings)


def test_option_prefix_is_stripped(tmp_path):
    path = tmp_path / "opt.csv"
    path.write_text(
        "题型,题目,正确答案,选项A,选项B\n单选题,题干,A,[A] 甲选项,乙选项\n",
        encoding="utf-8",
    )
    result = load_question_bank(str(path))
    options = dict(result.questions[0].options)
    assert options["A"] == "甲选项"
    assert options["B"] == "乙选项"


def test_optional_difficulty_and_knowledge(tmp_path):
    path = tmp_path / "tags.csv"
    path.write_text(
        "题型,题目,正确答案,难度,知识点\n"
        "判断题,题干一,1,易,第一章\n"
        "判断题,题干二,0,难,第二章\n",
        encoding="utf-8",
    )
    result = load_question_bank(str(path))
    assert result.difficulty_values == ["易", "难"]
    assert result.knowledge_values == ["第一章", "第二章"]


def test_duplicate_questions_are_collapsed(tmp_path):
    """完全相同的题只保留一条，避免同一份卷里出现两道一样的题。"""
    path = tmp_path / "dup.csv"
    path.write_text(
        "题型,题目,正确答案\n判断题,同一道题,1\n判断题,同一道题,1\n",
        encoding="utf-8",
    )
    result = load_question_bank(str(path))
    assert len(result.questions) == 1


def test_qid_is_content_based_and_stable(tmp_path):
    from conftest import make_bank

    path = make_bank(tmp_path / "a.xlsx", n_judgment=3, n_mcq=0, n_multi=0)
    first = load_question_bank(str(path))
    second = load_question_bank(str(path))
    assert [q.qid for q in first.questions] == [q.qid for q in second.questions]
    assert len({q.qid for q in first.questions}) == 3


def test_source_row_points_at_real_excel_row(tmp_path):
    """报错定位用：``source_row`` 应是含表头的真实行号。"""
    path = tmp_path / "rows.csv"
    path.write_text(
        "题型,题目,正确答案\n判断题,第一题,1\n判断题,第二题,0\n",
        encoding="utf-8",
    )
    result = load_question_bank(str(path))
    assert [q.source_row for q in result.questions] == [2, 3]
