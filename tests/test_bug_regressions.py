"""9 个已修复 bug 的回归测试。

每个测试对应一个曾经真实存在、且经实测确认的缺陷 —— 各测试的 docstring 里
记录了缺陷现象与实测数据。修复前全部失败，现在全部通过，作用是防止回归。

测试打的是**真正的业务层**（``app`` + ``renderers`` + ``ui.api``），
不经过任何兼容层。
"""

import pytest

from app.allocation import largest_remainder
from app.errors import Codes, DomainError
from app.generator import generate
from app.models import PaperConfig
from conftest import (
    base_config,
    build_paper,
    count_page_breaks,
    make_bank,
    question_tags,
)


def _pool_of(bank_path):
    from app.loader import load_question_bank
    from app.pool import QuestionPool

    return QuestionPool(load_question_bank(str(bank_path)))


def _blocks(result, cfg):
    from app.docmodel import build_paper_blocks

    return build_paper_blocks(result.papers[0], cfg)


# ── bug 1：多份试卷去重彻底失效 ────────────────────────────────────────
def test_bug01_dedup_across_papers(bank_path):
    """3 卷 × (10 判断 + 10 单选)，题库恰好 30+30。

    正确实现下三卷应当把题库刚好用尽且两两无重复。
    旧实现把 ``{(题型, index)}`` 元组集合喂给 ``DataFrame.index.isin()``，
    元组永远匹配不上整数 index，去重 100% 失效 ——
    实测三卷两两交集为 5 / 10 / 4 题。
    """
    result, _pool, _cfg = build_paper(
        bank_path, exam_count=3, judgment_count=10, mcq_count=10
    )

    tags = [question_tags(paper.content) for paper in result.papers]
    assert len(result.papers) == 3

    for index, paper_tags in enumerate(tags):
        assert len(paper_tags) == 20, f"试卷{index + 1}题数应为 20，实际 {len(paper_tags)}"

    for i in range(3):
        for j in range(i + 1, 3):
            dup = tags[i] & tags[j]
            assert not dup, f"试卷{i + 1} 与试卷{j + 1} 重复 {len(dup)} 题: {sorted(dup)}"


# ── bug 2：按比例导出的尾数分配错误 ───────────────────────────────────
def test_bug02_ratio_remainder_is_proportional():
    """比例合计不等于 100 时也应按归一化后的比例分配。

    旧实现 ``int(total*ratio/100)`` 之后把**全部余数**塞给比例最大的题型，
    且未按合计归一化：设 {20,40,10}/总100 时单选题实得 70 题。
    """
    result = largest_remainder(100, {"判断题": 20, "单选题": 40, "多选题": 10})

    assert sum(result.values()) == 100
    assert result == {"判断题": 29, "单选题": 57, "多选题": 14}, result
    assert result["单选题"] != 70, "不应把全部余数塞给比例最大的题型"


def test_bug02_ratio_end_to_end(bank_path):
    """经由组卷流程验证：比例模式下各题型题数符合归一化比例。

    判断题 1 : 单选题 1，总题数 20 —— 应各得 10 题。
    """
    result, _pool, _cfg = build_paper(
        bank_path,
        export_mode="按比例导出",
        total_questions=20,
        judgment_ratio=50,
        mcq_ratio=50,
    )
    counts = {s.label: s.count for s in result.papers[0].sections}
    assert counts == {"判断题": 10, "单选题": 10}, counts


def test_bug02_zero_ratios_is_rejected(bank_path):
    """比例全为 0 时必须在校验期报错，而不是出一份空卷。"""
    from app.generator import generate

    cfg = PaperConfig.from_legacy(
        base_config(export_mode="按比例导出", total_questions=20)
    )
    with pytest.raises(DomainError) as excinfo:
        generate(cfg, _pool_of(bank_path))
    assert excinfo.value.code == Codes.RATIO_SUM_NOT_100


# ── bug 3：题库不足时静默降级 ─────────────────────────────────────────
def test_bug03_insufficient_questions_is_reported(bank_path):
    """题量超过题库时必须给出明确警告，而不是静默少出题。

    旧实现 ``if len(questions) < count: count = len(questions)``，
    用户填 999 却只出 30 题且毫无提示。
    """
    result, _pool, _cfg = build_paper(bank_path, judgment_count=999, mcq_count=10)

    assert result.warnings, "题库不足时应返回警告，而不是静默降级"
    said = [w for w in result.warnings if w.code == Codes.INSUFFICIENT_QUESTIONS]
    assert said, "应给出题目数量不足的警告"
    assert said[0].details.get("available") == 30, "警告里要说清题库实际有多少题"


# ── bug 4：顺序导出范围为空 → 静默 0 题 ───────────────────────────────
def test_bug04_empty_sequential_range_raises(bank_path):
    """顺序模式下范围未填写，应在校验期报错，而不是生成 0 题的空卷。

    旧实现 ``start=0, end=0`` 落到 ``iloc[0:0]``，预览显示 0 题且毫无提示。
    """
    cfg = PaperConfig.from_legacy(
        base_config(
            export_mode="顺序导出",
            judgment_start=0,
            judgment_end=0,
            mcq_start=0,
            mcq_end=0,
        )
    )
    with pytest.raises(DomainError) as excinfo:
        generate(cfg, _pool_of(bank_path))

    assert excinfo.value.code == Codes.EMPTY_SEQUENTIAL_RANGE
    assert "范围" in excinfo.value.message


def test_bug04_start_greater_than_end_raises(bank_path):
    cfg = PaperConfig.from_legacy(base_config(export_mode="顺序导出"))
    cfg.ranges["judgment"] = (20, 5)

    with pytest.raises(DomainError) as excinfo:
        generate(cfg, _pool_of(bank_path))
    assert excinfo.value.code == Codes.INVALID_RANGE


# ── bug 5：取消保存仍报成功 ──────────────────────────────────────────
def test_bug05_cancel_is_not_reported_as_success(api_env, bank_path):
    """用户在保存对话框取消时，必须回传"已取消"。

    旧实现 ``export_to_word`` 静默 ``return None``，而 ``gui.export_word``
    随后无条件 ``messagebox.showinfo("成功")`` —— 取消也报成功。
    现在对话框与应用层分离，对话框返回 None 时 API 明确回传 cancelled。
    """
    from ui.api import Api

    api = Api()
    api.load_excel(str(bank_path))

    # 未绑定窗口 -> dialogs 返回 None -> 视作用户取消
    reply = api.save_template(base_config())
    assert reply["ok"] is True
    assert reply["data"]["cancelled"] is True
    assert reply["data"]["path"] == ""


def test_bug05_export_without_output_dir_is_an_error(api_env, bank_path):
    """没有导出目录时不能"假装成功"，要明确报错。"""
    from ui.api import Api

    api = Api()
    api.load_excel(str(bank_path))

    reply = api.start_export({}, {"docx": True, "output_dir": ""})
    assert reply["ok"] is False
    assert reply["error"]["code"] == Codes.FILE_NOT_FOUND


# ── bug 6：不含答案时多出一张空白页 ──────────────────────────────────
def test_bug06_no_blank_page_when_answers_excluded(bank_path, tmp_path):
    """不勾选「包含答案」时，试卷末尾不应留分页符。

    旧实现无条件 ``doc.add_page_break()``，导致末尾多一张空白页。
    """
    from renderers.docx_renderer import render_docx

    result, _pool, cfg = build_paper(bank_path, include_answers=False)
    path = tmp_path / "no-answers.docx"
    render_docx(_blocks(result, cfg), str(path), "A4", "")

    assert path.exists()
    assert count_page_breaks(path) == 0, "不含答案时不应有分页符"


def test_bug06_page_break_present_when_answers_included(bank_path, tmp_path):
    from renderers.docx_renderer import render_docx

    result, _pool, cfg = build_paper(bank_path, include_answers=True)
    path = tmp_path / "with-answers.docx"
    render_docx(_blocks(result, cfg), str(path), "A4", "")

    assert count_page_breaks(path) == 1, "含答案时应恰好有一个分页符"


# ── bug 7：加载失败污染状态 ──────────────────────────────────────────
def test_bug07_load_failure_keeps_previous_state(api_env, bank_path, tmp_path):
    """加载不合格题库失败后，必须先前的题库原封不动。

    旧实现在列校验**之前**就写入了 ``self.exam_data``，
    于是失败后状态被污染成一个不合格的 DataFrame。
    """
    from ui.api import Api

    api = Api()
    api.load_excel(str(bank_path))
    before = api.get_bank_info()["data"]
    assert before["total"] == 70

    bad = make_bank(tmp_path / "bad.xlsx", omit_column="正确答案")
    reply = api.load_excel(str(bad))

    assert reply["ok"] is False
    assert reply["error"]["code"] == Codes.MISSING_COLUMNS

    after = api.get_bank_info()["data"]
    assert after["total"] == before["total"], "加载失败不应改动已加载的题库"
    assert after["source"] == before["source"]


# ── bug 8：预览与导出不是同一份卷 ────────────────────────────────────
def test_bug08_preview_is_reproducible(bank_path):
    """同一配置连续生成两次，内容必须一致。

    旧实现 ``DataFrame.sample()`` 不带随机种子，每次抽到的题都不同 ——
    用户看到的预览与导出的试卷根本不是同一份。
    """
    pool = _pool_of(bank_path)
    cfg = PaperConfig.from_legacy(base_config())

    first = generate(cfg, pool).papers[0].content
    second = generate(cfg, pool).papers[0].content
    assert first == second


def test_bug08_different_seed_gives_different_paper(bank_path):
    """换种子应当换一套题 —— 否则"重新抽题"没有意义。"""
    pool = _pool_of(bank_path)
    cfg = PaperConfig.from_legacy(base_config())

    cfg.seed = 1
    first = generate(cfg, pool).papers[0].content
    cfg.seed = 2
    second = generate(cfg, pool).papers[0].content
    assert first != second


# ── bug 9：答案分组编号与试卷实际题号不符 ────────────────────────────
def test_bug09_answer_groups_use_real_question_numbers(bank_path):
    """判断题占 1-5 时，单选题即 6-10；答案页必须按真实题号分组。

    旧实现 ``_format_answers`` 对每个题型都从 1 重新编号，
    于是试卷里明明是 6-10 题，答案页却写「单选题答案: 1-5」。
    """
    cfg = PaperConfig.from_legacy(
        base_config(judgment_count=5, mcq_count=5, include_answers=True)
    )
    paper = generate(cfg, _pool_of(bank_path)).papers[0]

    spans = {s.label: (s.number_start, s.number_end) for s in paper.sections}
    assert spans["判断题"] == (1, 5)
    assert spans["单选题"] == (6, 10)

    assert "单选题答案: 6-10" in paper.content
    assert "单选题答案: 1-5" not in paper.content


def test_bug09_numbering_is_continuous_across_sections(bank_path):
    """三个题型连排时题号必须连续，不重不漏。"""
    cfg = PaperConfig.from_legacy(
        base_config(judgment_count=3, mcq_count=4, include_answers=True)
    )
    cfg.include["mcq_multi"] = True
    cfg.counts["mcq_multi"] = 2

    paper = generate(cfg, _pool_of(bank_path)).papers[0]
    numbers = []
    for section in paper.sections:
        numbers.extend(range(section.number_start, section.number_end + 1))
    assert numbers == list(range(1, paper.total_count + 1))
