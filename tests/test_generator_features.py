"""组卷新功能测试：难度配比、知识点覆盖、题库耗尽策略、顺序模式语义。"""

import openpyxl
import pytest

from app.constants import (
    POOL_ERROR,
    POOL_SHRINK,
    POOL_WARN_AND_REUSE,
)
from app.errors import Codes, DomainError
from app.generator import generate
from app.loader import load_question_bank
from app.models import PaperConfig
from app.pool import QuestionPool
from conftest import base_config, question_tags


def make_tagged_bank(path, per_difficulty=10, difficulties=("易", "中", "难"),
                     knowledge=("第一章", "第二章"), difficulty_counts=None):
    """构造带难度与知识点标签的单选题库。

    ``difficulty_counts`` 形如 ``{"易": 2, "中": 10}``，用于刻意造出
    「某个难度题量不足」的场景。
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["题型", "题目", "正确答案", "难度", "知识点",
               "选项A", "选项B", "选项C", "选项D"])

    counter = 0
    if difficulty_counts:
        difficulties = tuple(difficulty_counts)
    for difficulty in difficulties:
        count = (
            difficulty_counts[difficulty] if difficulty_counts else per_difficulty
        )
        for _ in range(count):
            counter += 1
            topic = knowledge[counter % len(knowledge)]
            ws.append([
                "单选题", f"单选题{counter:03d}", "A",
                difficulty, topic,
                f"选项{counter}a", f"选项{counter}b",
                f"选项{counter}c", f"选项{counter}d",
            ])
    wb.save(path)
    return path


@pytest.fixture
def tagged(tmp_path):
    path = make_tagged_bank(tmp_path / "tagged.xlsx")
    return QuestionPool(load_question_bank(str(path))), path


def _config(pool, **overrides):
    defaults = dict(
        export_mode="随机抽取",
        include_judgment=False,
        include_mcq=True,
        include_mcq_multi=False,
        mcq_count=10,
        mcq_score=2,
    )
    defaults.update(overrides)
    return PaperConfig.from_legacy(base_config(**defaults))


# ── 难度配比 ─────────────────────────────────────────────────────────


def test_difficulty_weights_are_respected(tagged):
    pool, _ = tagged
    cfg = _config(pool, difficulty_weights={"易": 0.5, "中": 0.3, "难": 0.2})

    result = generate(cfg, pool)
    questions = result.papers[0].sections[0].questions

    counts = {}
    for question in questions:
        counts[question.difficulty] = counts.get(question.difficulty, 0) + 1

    assert counts == {"易": 5, "中": 3, "难": 2}, counts


def test_difficulty_weights_are_normalized(tagged):
    """权重之和不是 1 时按比例归一化，结果应与和为 1 时一致。"""
    pool, _ = tagged

    by_decimal = generate(
        _config(pool, difficulty_weights={"易": 0.5, "中": 0.3, "难": 0.2}), pool
    )
    by_integer = generate(
        _config(pool, difficulty_weights={"易": 5, "中": 3, "难": 2}), pool
    )

    assert [q.qid for q in by_decimal.papers[0].sections[0].questions] == [
        q.qid for q in by_integer.papers[0].sections[0].questions
    ]


def test_difficulty_shortage_warns_and_borrows(tmp_path):
    """某个难度不够时，从其他难度借调并给出警告，而不是静默少出题。

    题库里「易」只有 2 题，但配比要求 8 题 —— 必须借调并明确告知。
    """
    path = make_tagged_bank(
        tmp_path / "uneven.xlsx", difficulty_counts={"易": 2, "中": 20}
    )
    pool = QuestionPool(load_question_bank(str(path)))

    cfg = _config(pool, mcq_count=10, difficulty_weights={"易": 0.8, "中": 0.2})
    result = generate(cfg, pool)
    questions = result.papers[0].sections[0].questions

    assert len(questions) == 10, "借调后仍应出满 10 题"
    assert result.warnings, "某难度不足时应给出警告"


# ── 知识点 ───────────────────────────────────────────────────────────


def test_knowledge_cover_first_hits_every_selected_topic(tagged):
    pool, _ = tagged
    cfg = _config(
        pool,
        mcq_count=6,
        knowledge_include=["第一章", "第二章"],
        knowledge_cover_first=True,
    )

    result = generate(cfg, pool)
    topics = {q.knowledge for q in result.papers[0].sections[0].questions}
    assert topics == {"第一章", "第二章"}, topics


def test_knowledge_filter_excludes_other_topics(tagged):
    pool, _ = tagged
    cfg = _config(pool, mcq_count=5, knowledge_include=["第一章"])

    result = generate(cfg, pool)
    questions = result.papers[0].sections[0].questions
    assert all(q.knowledge == "第一章" for q in questions)


def test_unknown_knowledge_falls_back_with_warning(tagged):
    pool, _ = tagged
    cfg = _config(pool, mcq_count=4, knowledge_include=["不存在的章节"])

    result = generate(cfg, pool)
    assert len(result.papers[0].sections[0].questions) == 4
    assert any("知识点" in w.message for w in result.warnings)


# ── 题库耗尽策略 ─────────────────────────────────────────────────────


def _small_pool(tmp_path, count=6):
    path = make_tagged_bank(
        tmp_path / "small.xlsx", per_difficulty=count, difficulties=("易",)
    )
    return QuestionPool(load_question_bank(str(path)))


def test_pool_error_strategy_raises(tmp_path):
    pool = _small_pool(tmp_path, count=4)
    cfg = _config(pool, mcq_count=10, on_pool_exhausted=POOL_ERROR)

    with pytest.raises(DomainError) as excinfo:
        generate(cfg, pool)
    assert excinfo.value.code == Codes.POOL_EXHAUSTED
    assert "4" in excinfo.value.message


def test_pool_shrink_strategy_reduces_with_warning(tmp_path):
    pool = _small_pool(tmp_path, count=4)
    cfg = _config(pool, mcq_count=10, on_pool_exhausted=POOL_SHRINK)

    result = generate(cfg, pool)
    assert len(result.papers[0].sections[0].questions) == 4
    assert any(w.code == Codes.INSUFFICIENT_QUESTIONS for w in result.warnings)


def test_pool_warn_and_reuse_strategy_marks_reused(tmp_path):
    pool = _small_pool(tmp_path, count=4)
    cfg = _config(pool, mcq_count=10, on_pool_exhausted=POOL_WARN_AND_REUSE)

    result = generate(cfg, pool)
    paper = result.papers[0]
    assert len(paper.sections[0].questions) == 4, "只有 4 道可用题时无法凑出 10 道"
    assert any(w.code == Codes.INSUFFICIENT_QUESTIONS for w in result.warnings)


def test_reuse_happens_across_papers_when_pool_is_tight(tmp_path):
    """3 份卷 × 各 10 题，但题库只有 20 题 —— 第三份必须复用并明确记录。"""
    pool = _small_pool(tmp_path, count=20)
    cfg = _config(pool, mcq_count=10, on_pool_exhausted=POOL_WARN_AND_REUSE)
    cfg.exam_count = 3

    result = generate(cfg, pool)
    assert len(result.papers) == 3
    reused = [q for paper in result.papers for q in paper.reused_qids]
    assert reused, "题库不足时必须记录被迫复用的题"
    assert any(w.code == Codes.POOL_EXHAUSTED for w in result.warnings)


# ── 跨卷行为 ─────────────────────────────────────────────────────────


def test_unique_across_papers_can_be_disabled(tmp_path):
    """关闭跨卷去重后，各卷可以出现相同的题。"""
    pool = _small_pool(tmp_path, count=8)
    cfg = _config(pool, mcq_count=6, unique_across_papers=False)

    result = generate(cfg, pool)
    assert len(result.papers) >= 1
    assert not any(paper.reused_qids for paper in result.papers)


# ── 顺序模式语义 ─────────────────────────────────────────────────────


def test_sequential_count_comes_from_range_not_count_box(tagged):
    """顺序模式的题数由题号范围决定，「数量」框不参与。

    旧实现是 min(数量, 范围长度)，语义混乱 —— 用户改了范围却还受数量框限制。
    """
    pool, _ = tagged
    cfg = _config(
        pool,
        export_mode="顺序导出",
        mcq_count=3,  # 刻意设一个和范围无关的值
        mcq_score=2,
    )
    cfg.ranges["mcq"] = (5, 12)

    result = generate(cfg, pool)
    assert len(result.papers[0].sections[0].questions) == 8  # 12 - 5 + 1


def test_sequential_range_beyond_pool_is_truncated_with_warning(tagged):
    pool, _ = tagged  # 共 30 题
    cfg = _config(pool, export_mode="顺序导出")
    cfg.ranges["mcq"] = (25, 99)

    result = generate(cfg, pool)
    assert len(result.papers[0].sections[0].questions) == 6  # 25..30
    assert any(w.code == Codes.INSUFFICIENT_QUESTIONS for w in result.warnings)
