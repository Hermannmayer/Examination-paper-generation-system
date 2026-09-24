"""组卷编排：``PaperConfig`` + ``QuestionPool`` → ``GenerationResult``。

原则：**先校验、后生成**。任何配置错误都在动手之前抛出来，
不产生"生成了半份卷才发现不对"的中间状态。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from .allocation import allocate_with_knowledge, largest_remainder
from .constants import (
    ESSAY_BLANK_LINES,
    ESSAY_LABELS,
    EXPORT_MODE_RATIO,
    EXPORT_MODE_SEQUENTIAL,
    POOL_WARN_AND_REUSE,
    QUESTION_TYPES,
    TYPE_BY_KEY,
)
from .errors import Codes, DomainError
from .models import GenerationResult, Paper, PaperConfig, Section, Warning
from .numbering import (
    assign_numbers,
    build_answer_groups,
    build_essay_answers,
    number_of,
)
from .pool import QuestionPool
from .selection import (
    pick_by_bucket,
    pick_for_section,
    pick_sequential,
    validate_range,
)
from .loader import _clean_option_text

# 未指定 seed 时使用的固定值 —— 保证"同一配置两次预览结果一致"
DEFAULT_SEED = 20240101

ProgressFn = Callable[[float, str], None]


@dataclass
class SectionPlan:
    """一个大题块的抽取计划。"""

    label: str
    key: str
    per_score: int
    count: int
    mode: str
    span: Optional[tuple] = None  # 顺序模式的 (start, end)
    difficulty_quota: Optional[Dict] = None  # {难度: 题数}
    knowledge_quota: Optional[Dict] = None  # {知识点: 题数}


# ── 校验 ─────────────────────────────────────────────────────────────


def validate_config(config: PaperConfig, pool: QuestionPool) -> None:
    """在生成之前把所有可预期的配置错误拦下来。"""
    if pool is None or len(pool) == 0:
        raise DomainError(Codes.NOT_LOADED, "请先加载题库")

    selected = [k for k, on in config.include.items() if on]
    if not selected:
        raise DomainError(
            Codes.NO_TYPE_SELECTED,
            "请至少选择一种题型",
            hint="在左侧勾选需要参与组卷的题型",
        )

    if config.export_mode == EXPORT_MODE_SEQUENTIAL:
        for key in selected:
            label = TYPE_BY_KEY.get(key, {}).get("label", key)
            start, end = config.ranges.get(key, (0, 0))
            validate_range(start, end, pool.count(label), label)

    elif config.export_mode == EXPORT_MODE_RATIO:
        ratios = {k: config.ratios.get(k, 0) for k in selected}
        if sum(ratios.values()) <= 0:
            raise DomainError(
                Codes.RATIO_SUM_NOT_100,
                "按比例导出：各题型比例合计为 0",
                hint="请为至少一个题型填写大于 0 的比例",
                details={"ratios": ratios},
            )

    else:
        planned = {k: config.counts.get(k, 0) for k in selected}
        if sum(planned.values()) <= 0:
            raise DomainError(
                Codes.NO_TYPE_SELECTED,
                "请至少为一种题型填写抽取数量",
                details={"counts": planned},
            )


# ── 计划 ─────────────────────────────────────────────────────────────


def build_section_plans(config: PaperConfig, pool: QuestionPool) -> List[SectionPlan]:
    """把配置展开成「每个大题块抽多少题」。"""
    order = config.question_order or [qt["key"] for qt in QUESTION_TYPES]
    selected = [k for k in order if config.include.get(k)]
    # 补上不在 order 里但被勾选的题型
    for key, on in config.include.items():
        if on and key not in selected:
            selected.append(key)

    plans: List[SectionPlan] = []

    if config.export_mode == EXPORT_MODE_RATIO:
        ratios = {k: config.ratios.get(k, 0) for k in selected}
        allocation = largest_remainder(config.total_questions, ratios)
        for key in selected:
            label = TYPE_BY_KEY.get(key, {}).get("label", key)
            plans.append(
                SectionPlan(
                    label=label,
                    key=key,
                    per_score=config.scores.get(key, 1),
                    count=allocation.get(key, 0),
                    mode=config.export_mode,
                )
            )

    elif config.export_mode == EXPORT_MODE_SEQUENTIAL:
        for key in selected:
            label = TYPE_BY_KEY.get(key, {}).get("label", key)
            start, end = config.ranges.get(key, (0, 0))
            available = pool.count(label)
            count = max(0, min(available, end) - start + 1)
            plans.append(
                SectionPlan(
                    label=label,
                    key=key,
                    per_score=config.scores.get(key, 1),
                    count=count,
                    mode=config.export_mode,
                    span=(start, end),
                )
            )

    else:
        for key in selected:
            label = TYPE_BY_KEY.get(key, {}).get("label", key)
            plans.append(
                SectionPlan(
                    label=label,
                    key=key,
                    per_score=config.scores.get(key, 1),
                    count=config.counts.get(key, 0),
                    mode=config.export_mode,
                )
            )

    plans = [p for p in plans if p.count > 0]
    _attach_quotas(plans, config, pool)
    return plans


def _attach_quotas(plans: List[SectionPlan], config: PaperConfig, pool: QuestionPool) -> None:
    """给每个大题块挂上难度/知识点配额（就地修改）。

    优先级：知识点覆盖 > 难度配比。两者同时配置时以知识点为准 ——
    「每个考点都覆盖到」是更强的约束，三维同时约束会让结果难以解释。
    顺序导出模式不做配额（题号范围已经确定了抽哪几道）。
    """
    difficulty_weights = {
        str(k): float(v) for k, v in (config.difficulty_weights or {}).items()
    }
    knowledge = [k for k in (config.knowledge_include or []) if k]

    for plan in plans:
        if plan.mode == EXPORT_MODE_SEQUENTIAL:
            continue

        if knowledge and config.knowledge_cover_first:
            available: Dict[str, int] = {}
            for question in pool.by_type(plan.label):
                if question.knowledge in knowledge:
                    available[question.knowledge] = (
                        available.get(question.knowledge, 0) + 1
                    )
            quota = allocate_with_knowledge(plan.count, available, knowledge, True)
            if quota:
                plan.knowledge_quota = quota
                continue

        if difficulty_weights:
            plan.difficulty_quota = largest_remainder(plan.count, difficulty_weights)


# ── 抽取 ─────────────────────────────────────────────────────────────


def _pick_section(
    plan: SectionPlan,
    pool: QuestionPool,
    rng: random.Random,
    excluded,
    config: PaperConfig,
) -> tuple:
    """返回 (questions, warnings, reused_qids)。"""
    candidates = pool.by_type(plan.label)
    warnings: List[Warning] = []

    if plan.mode == EXPORT_MODE_SEQUENTIAL:
        picked, seq_warnings = pick_sequential(candidates, plan.span[0], plan.span[1])
        return _ordered(picked, config), warnings + seq_warnings, []

    # 知识点筛选：只保留选中的考点
    if config.knowledge_include:
        allowed = set(config.knowledge_include)
        filtered = [q for q in candidates if q.knowledge in allowed]
        if filtered:
            candidates = filtered
        elif candidates:
            warnings.append(
                Warning(
                    Codes.INSUFFICIENT_QUESTIONS,
                    f"「{plan.label}」中没有属于所选知识点的题，已忽略知识点筛选",
                    {"qtype": plan.label, "knowledge": list(allowed)},
                )
            )

    if plan.knowledge_quota:
        buckets: Dict = {}
        for question in candidates:
            buckets.setdefault(question.knowledge, []).append(question)
        outcome = pick_by_bucket(
            buckets,
            plan.knowledge_quota,
            excluded,
            rng,
            strategy=config.on_pool_exhausted,
            label=plan.label,
            random_order=config.random_order,
        )
        return (
            _ordered(outcome.picked, config),
            warnings + outcome.warnings,
            outcome.reused,
        )

    if plan.difficulty_quota:
        # 候选按实际难度分桶（包含未配置配比的难度，供借调时使用）
        buckets = {}
        for question in candidates:
            buckets.setdefault(question.difficulty, []).append(question)
        outcome = pick_by_bucket(
            buckets,
            plan.difficulty_quota,
            excluded,
            rng,
            strategy=config.on_pool_exhausted,
            label=plan.label,
            random_order=config.random_order,
        )
        return (
            _ordered(outcome.picked, config),
            warnings + outcome.warnings,
            outcome.reused,
        )

    outcome = pick_for_section(
        candidates,
        plan.count,
        excluded,
        rng,
        strategy=config.on_pool_exhausted,
        label=plan.label,
        random_order=config.random_order,
    )
    return outcome.picked, warnings + outcome.warnings, outcome.reused


def _ordered(picked, config: PaperConfig):
    """关闭随机排序时按题库原始顺序排列。"""
    if config.random_order:
        return list(picked)
    return sorted(picked, key=lambda q: q.source_row)


def _render_question(number: int, question, label: str, write_space: bool = True) -> str:
    """单题的纯文本渲染。

    ``write_space`` 为 False 时不留作答空间（已经出答题卡了）。
    """
    if label == "判断题":
        blank = " __________" if write_space else ""
        return f"{number}. {question.stem}{blank}\n"

    if label in ESSAY_LABELS:
        lines = "\n" * ESSAY_BLANK_LINES if write_space else "\n"
        return f"{number}. {question.stem}\n{lines}"

    text = f"{number}. {question.stem} [{label}]\n"
    if question.options:
        rendered = [f"{letter}. {_clean_option_text(text_)}" for letter, text_ in question.options]
        text += "   " + "    ".join(rendered) + "\n"
    return text


def _render_content(config: PaperConfig, sections: Sequence[Section]) -> str:
    """整份试卷的纯文本渲染。"""
    content = f"试卷标题: {config.exam_title}\n"
    content += f"考生信息: {config.student_name}\n\n"
    if config.exam_time:
        content += f"考试时间: {config.exam_time} 分钟\n\n"

    # 与 Block 渲染保持同一条规则：出了答题卡就不在试卷上留作答空间
    write_space = not config.include_answer_card

    for section in sections:
        # 用实际题数而非计划题数 —— 否则题库不足时卷头分数与题目数对不上
        content += (
            f"    {section.label}（每题{section.per_score}分，"
            f"共{section.points}分）\n\n"
        )
        for offset, question in enumerate(section.questions):
            content += _render_question(
                number_of(section, offset), question, section.label, write_space
            )
        content += "\n"

    return content


def _render_answer_section(sections: Sequence[Section]) -> str:
    """参考答案页。

    客观题压成「6-10: A B C D」式的紧凑行；简答题答案是成段文字，
    必须逐题列出 —— 混进紧凑行里既放不下也读不了。
    """
    groups = build_answer_groups(sections)
    essays = build_essay_answers(sections)
    if not groups and not essays:
        return ""

    result = "\n===== 参考答案 =====\n"
    if groups:
        result += f"全部答案: {groups[0].span_text}\n"
        result += "\n按题型分组答案:\n"
        for group in groups[1:]:
            result += f"{group.label}答案: {group.span_text}\n"

    if essays:
        result += "\n简答题参考答案:\n"
        for number, answer in essays:
            result += f"{number}. {answer}\n"
    return result


# ── 入口 ─────────────────────────────────────────────────────────────


def generate(
    config: PaperConfig,
    pool: QuestionPool,
    history_qids=None,
    progress: Optional[ProgressFn] = None,
) -> GenerationResult:
    """生成 ``config.exam_count`` 份试卷。"""
    validate_config(config, pool)

    base_seed = config.seed if config.seed is not None else DEFAULT_SEED
    exam_count = max(1, int(config.exam_count or 1))

    # 跨会话的"已出过的题"
    history_set = set(history_qids or ()) if config.avoid_history else set()
    accumulated = set(history_set)

    result = GenerationResult()
    if history_set:
        result.stats["history_reused"] = len(history_set)

    for index in range(exam_count):
        if progress:
            progress(
                index / exam_count,
                f"正在生成第 {index + 1}/{exam_count} 份试卷",
            )

        # 每份卷用独立但确定的种子：同 seed 同卷，不同卷不同题
        rng = random.Random(base_seed + index)

        excluded = accumulated if config.unique_across_papers else history_set

        plans = build_section_plans(config, pool)
        sections: List[Section] = []
        paper_reused: List[str] = []
        paper_warnings: List[Warning] = []

        for plan in plans:
            picked, warnings, reused = _pick_section(plan, pool, rng, excluded, config)
            section = Section(
                label=plan.label,
                per_score=plan.per_score,
                questions=picked,
            )
            sections.append(section)
            paper_reused.extend(reused)
            paper_warnings.extend(warnings)
            for warning in warnings:
                if warning not in result.warnings:
                    result.warnings.append(warning)

        assign_numbers(sections)

        if config.unique_across_papers:
            for section in sections:
                for question in section.questions:
                    accumulated.add(question.qid)

        all_answers = []
        for section in sections:
            for offset, question in enumerate(section.questions):
                all_answers.append(
                    (number_of(section, offset), question.answer, section.label)
                )

        content = _render_content(config, sections)
        if config.include_answers:
            content += _render_answer_section(sections)

        paper = Paper(
            exam_number=index + 1,
            sections=sections,
            content=content,
            all_answers=all_answers,
            total_count=sum(s.count for s in sections),
            total_score=sum(s.points for s in sections),
            seed=base_seed + index,
            reused_qids=paper_reused,
            warnings=paper_warnings,
        )
        result.papers.append(paper)

    if progress:
        progress(1.0, "完成")

    result.stats["by_type"] = [
        {
            "label": section.label,
            "count": section.count,
            "per_score": section.per_score,
            "points": section.points,
        }
        for section in (result.papers[0].sections if result.papers else [])
    ]
    if result.papers:
        result.stats["total_count"] = result.papers[0].total_count
        result.stats["total_score"] = result.papers[0].total_score
    result.stats["seed"] = base_seed
    return result
