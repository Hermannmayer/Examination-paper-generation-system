"""pytest 共用 fixture 与工具。

刻意使用 openpyxl 而非 pandas 来构造题库文件 —— pandas 已从运行依赖中移除，
conftest 不应成为阻碍。
"""

import re
import sys
from pathlib import Path

import openpyxl
import pytest

# 让测试能 import 项目根目录下的 app / renderers / ui
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 题库中题干的唯一标记，用于从生成结果里反查"这一卷抽到了哪些题"
# 注意：不能用 [判单多]选题 —— 判断题的第二个字是"断"，匹配不上
TAG_RE = re.compile(r"(?:判断题|单选题|多选题)\d{3}")

JUDGMENT = "判断题"
MCQ = "单选题"
MCQ_MULTI = "多选题"

HEADERS = ["题型", "题目", "正确答案", "选项A", "选项B", "选项C", "选项D"]
OPTION_LETTERS = ["A", "B", "C", "D"]


def make_bank(
    path,
    n_judgment=30,
    n_mcq=30,
    n_multi=10,
    sheet="Sheet1",
    headers=None,
    omit_column=None,
):
    """构造一个 xlsx 题库。

    题干形如 ``判断题001``，可被 :data:`TAG_RE` 提取，用于断言题目身份。
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet

    cols = list(headers if headers is not None else HEADERS)
    if omit_column:
        cols = [c for c in cols if c != omit_column]
    ws.append(cols)

    def row(qtype, tag, answer, options=None):
        values = {c: None for c in cols}
        values["题型"] = qtype
        values["题目"] = tag
        values["正确答案"] = answer
        for letter, text in (options or {}).items():
            values[f"选项{letter}"] = text
        ws.append([values[c] for c in cols])

    for i in range(1, n_judgment + 1):
        row(JUDGMENT, f"判断题{i:03d}", str(i % 2))

    for i in range(1, n_mcq + 1):
        row(
            MCQ,
            f"单选题{i:03d}",
            OPTION_LETTERS[i % 4],
            {L: f"单选{i:03d}选项{L}" for L in OPTION_LETTERS},
        )

    for i in range(1, n_multi + 1):
        row(
            MCQ_MULTI,
            f"多选题{i:03d}",
            "ABD",
            {L: f"多选{i:03d}选项{L}" for L in OPTION_LETTERS},
        )

    wb.save(path)
    return path


def question_tags(content):
    """从生成的试卷文本里提取题目标记，返回 set。"""
    return set(TAG_RE.findall(content))


def count_page_breaks(docx_path):
    """统计 docx 里显式分页符（add_page_break 产生的 w:br type=page）的数量。"""
    from docx import Document
    from docx.oxml.ns import qn

    doc = Document(str(docx_path))
    found = doc.element.body.findall(".//" + qn("w:br"))
    return sum(1 for b in found if b.get(qn("w:type")) == "page")


@pytest.fixture
def api_env(tmp_path, monkeypatch):
    """把历史与设置文件重定向到临时目录。

    ``ui.api.Api`` 在加载题库时会把「上次题库路径」写进设置，
    不隔离就会污染开发者真实的 %APPDATA%。
    """
    monkeypatch.setenv("EXAM_HISTORY_PATH", str(tmp_path / "history.json"))
    monkeypatch.setenv("EXAM_SETTINGS_PATH", str(tmp_path / "settings.json"))
    return tmp_path


@pytest.fixture
def bank_path(tmp_path):
    """30 判断 + 30 单选 + 10 多选 的标准题库。"""
    return make_bank(tmp_path / "bank.xlsx")


def base_config(**overrides):
    """一份能出卷的默认配置（旧版扁平字典形式，便于覆盖个别键）。"""
    cfg = {
        "export_mode": "随机抽取",
        "exam_title": "测试试卷",
        "student_name": "姓名：____",
        "exam_time": "",
        "include_answers": False,
        "include_judgment": True,
        "include_mcq": True,
        "include_mcq_multi": False,
        "judgment_count": 10,
        "mcq_count": 10,
        "mcq_multi_count": 0,
        "judgment_score": 1,
        "mcq_score": 1,
        "mcq_multi_score": 2,
        "random_order": True,
    }
    cfg.update(overrides)
    return cfg


def build_paper(bank_path, exam_count=1, **overrides):
    """跑一次新架构的组卷，返回 ``(GenerationResult, QuestionPool, PaperConfig)``。"""
    from app.generator import generate
    from app.loader import load_question_bank
    from app.models import PaperConfig
    from app.pool import QuestionPool

    pool = QuestionPool(load_question_bank(str(bank_path)))
    cfg = PaperConfig.from_legacy(base_config(**overrides))
    cfg.exam_count = exam_count
    return generate(cfg, pool), pool, cfg


@pytest.fixture
def paper_bundle(bank_path):
    return build_paper(bank_path)

