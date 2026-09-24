"""pandas → openpyxl 移植的差分验证。

把「旧版 pandas 读取」与「新版 openpyxl 读取」在**同一文件**上逐行比对，
确认移植没有改变读到的题目。

pandas 在 P5 打包阶段会被彻底移除，届时本测试自动跳过
（``importorskip``），不会变成阻碍。
"""

import pytest

openpyxl = pytest.importorskip("openpyxl")
pd = pytest.importorskip("pandas")

from app.loader import OPTION_LETTERS, load_question_bank  # noqa: E402
from conftest import make_bank  # noqa: E402


def _read_with_pandas(path):
    """复刻旧版 ``core.py:load_excel`` 的读取与归一化语义。"""
    df = pd.read_excel(path)
    rows = []
    for _, row in df.iterrows():
        qtype = str(row["题型"]).strip()
        stem = str(row["题目"]).strip()

        answer = str(row["正确答案"]).strip()
        if qtype == "判断题":
            if answer == "1":
                answer = "√"
            elif answer == "0":
                answer = "×"

        options = []
        for letter in OPTION_LETTERS:
            col = f"选项{letter}"
            if col in row and pd.notna(row[col]) and str(row[col]).strip():
                text = str(row[col]).strip()
                if len(text) > 2 and text[0] == "[" and text[2:3] == "]":
                    text = text[3:].strip()
                options.append((letter, text))

        rows.append((qtype, stem, answer, tuple(options)))
    return rows


def _read_with_new(path):
    result = load_question_bank(str(path))
    return [
        (q.qtype, q.stem, q.answer, tuple(q.options)) for q in result.questions
    ]


def test_parity_on_generated_bank(tmp_path):
    path = make_bank(tmp_path / "bank.xlsx", n_judgment=20, n_mcq=20, n_multi=8)
    assert _read_with_pandas(str(path)) == _read_with_new(str(path))


def test_parity_on_real_template():
    """对仓库自带的真实模板做同样比对。"""
    from pathlib import Path

    template = Path(__file__).resolve().parent.parent / "题库模板.xlsx"
    if not template.exists():
        pytest.skip("题库模板.xlsx 不存在")

    assert _read_with_pandas(str(template)) == _read_with_new(str(template))


def test_parity_judgment_answer_shapes(tmp_path):
    """判断题答案用字符串 '0'/'1' 时，新旧一致。"""
    path = make_bank(tmp_path / "j.xlsx", n_judgment=10, n_mcq=0, n_multi=0)
    old = _read_with_pandas(str(path))
    new = _read_with_new(str(path))

    assert [r[2] for r in old] == [r[2] for r in new]
    assert all(r[2] in ("√", "×") for r in new)
