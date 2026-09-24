"""抽题：纯函数，``rng`` 显式注入（不碰全局 ``random``），便于测试与复现。

这里承载两处修复：

* **去重**（旧实现用 ``questions.index.isin(元组集合)``，元组永远匹配不上整数
  index，去重 100% 失效）。现在按 ``qid`` 过滤，跨卷、跨批次、跨会话共用一套机制。
* **题库不足不再是静默降级**，而是产出明确 warning，用户能看到到底少了多少。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .constants import POOL_ERROR, POOL_SHRINK, POOL_WARN_AND_REUSE
from .errors import Codes, DomainError
from .models import Question, Warning


@dataclass
class PickOutcome:
    """一次抽取的结果。"""

    picked: List[Question] = field(default_factory=list)
    warnings: List[Warning] = field(default_factory=list)
    reused: List[str] = field(default_factory=list)  # 被迫复用的 qid


def filter_candidates(
    questions: Sequence[Question],
    difficulty: Optional[str] = None,
    knowledge: Optional[str] = None,
) -> List[Question]:
    """按难度/知识点过滤。``None`` 表示不限制。"""
    out = list(questions)
    if difficulty is not None:
        out = [q for q in out if q.difficulty == difficulty]
    if knowledge is not None:
        out = [q for q in out if q.knowledge == knowledge]
    return out


def split_used(candidates: Sequence[Question], used_qids) -> tuple:
    """拆成 (未被用过的, 已被用过的)。"""
    used = used_qids or frozenset()
    fresh, stale = [], []
    for question in candidates:
        (stale if question.qid in used else fresh).append(question)
    return fresh, stale


def validate_range(start: int, end: int, available: int, label: str) -> None:
    """校验顺序模式的范围。校验期就要拦住，不能到生成时才静默出空卷。"""
    if start <= 0 or end <= 0:
        raise DomainError(
            Codes.EMPTY_SEQUENTIAL_RANGE,
            f"「{label}」尚未填写题目范围",
            hint="请在「顺序范围」中填写起止题号；若该题型不参与本次组卷，请取消勾选",
            details={"qtype": label, "start": start, "end": end},
        )
    if start > end:
        raise DomainError(
            Codes.INVALID_RANGE,
            f"「{label}」的范围不合法：起始题号 {start} 大于结束题号 {end}",
            details={"qtype": label, "start": start, "end": end},
        )
    if available <= 0:
        raise DomainError(
            Codes.EMPTY_SEQUENTIAL_RANGE,
            f"题库中没有「{label}」",
            hint="请检查题库内容或改用其他题型",
            details={"qtype": label},
        )
    if start > available:
        raise DomainError(
            Codes.INVALID_RANGE,
            f"「{label}」起始题号 {start} 超出题库范围（共 {available} 题）",
            details={"qtype": label, "start": start, "available": available},
        )


def pick_sequential(
    candidates: Sequence[Question], start: int, end: int
) -> tuple:
    """按该题型内的 1-based 闭区间取题。

    返回 ``(picked, warnings)``。结束题号超出题库时截断并给出 warning。
    """
    available = len(candidates)
    warnings: List[Warning] = []

    idx_start = max(0, start - 1)
    idx_end = min(available, end)

    if end > available:
        warnings.append(
            Warning(
                Codes.INSUFFICIENT_QUESTIONS,
                f"结束题号 {end} 超出题库（共 {available} 题），已截断到 {available}",
                {"requested_end": end, "available": available},
            )
        )

    return list(candidates[idx_start:idx_end]), warnings


def pick_random(candidates: Sequence[Question], needed: int, rng) -> List[Question]:
    """无放回随机抽取。``needed`` 超过候选数时返回全部（调用方负责警告）。"""
    pool = list(candidates)
    if needed <= 0:
        return []
    if needed >= len(pool):
        rng.shuffle(pool)
        return pool
    return rng.sample(pool, needed)


def pick_for_section(
    candidates: Sequence[Question],
    needed: int,
    used_qids,
    rng,
    strategy: str = POOL_WARN_AND_REUSE,
    label: str = "",
    random_order: bool = True,
) -> PickOutcome:
    """为一个题型/难度桶抽取 ``needed`` 道题。

    ``used_qids`` 是跨卷累计的已用题集合。候选不足时按 ``strategy`` 处理：

    * ``error``          —— 直接抛 POOL_EXHAUSTED
    * ``shrink``         —— 少出题，给出 warning
    * ``warn_and_reuse`` —— 复用已出过的题补齐，给出 warning 并记录 reused
    """
    outcome = PickOutcome()
    candidates = list(candidates)

    if needed <= 0:
        return outcome

    fresh, stale = split_used(candidates, used_qids)

    if len(fresh) >= needed:
        outcome.picked = pick_random(fresh, needed, rng)
        if not random_order:
            outcome.picked.sort(key=lambda q: q.source_row)
        return outcome

    # ── 候选不足 ───────────────────────────────────────────────────
    shortage = needed - len(fresh)
    total_available = len(candidates)

    if total_available < needed:
        outcome.warnings.append(
            Warning(
                Codes.INSUFFICIENT_QUESTIONS,
                f"「{label}」题库题量不足：需要 {needed} 题，题库仅 {total_available} 题",
                {
                    "qtype": label,
                    "requested": needed,
                    "available": total_available,
                },
            )
        )
    else:
        outcome.warnings.append(
            Warning(
                Codes.POOL_EXHAUSTED,
                f"「{label}」未出过的题已用完（剩 {len(fresh)} 题，还需 {shortage} 题）",
                {
                    "qtype": label,
                    "requested": needed,
                    "unused_available": len(fresh),
                    "shortage": shortage,
                },
            )
        )

    if strategy == POOL_ERROR:
        raise DomainError(
            Codes.POOL_EXHAUSTED,
            outcome.warnings[-1].message,
            hint="请减少题量、增加试卷份数上限，或扩充题库",
            details=outcome.warnings[-1].details,
        )

    if strategy == POOL_SHRINK:
        outcome.picked = pick_random(fresh, len(fresh), rng)
        if not random_order:
            outcome.picked.sort(key=lambda q: q.source_row)
        return outcome

    # POOL_WARN_AND_REUSE
    outcome.picked = pick_random(fresh, len(fresh), rng)
    if shortage > 0 and stale:
        reused = pick_random(stale, min(shortage, len(stale)), rng)
        outcome.picked.extend(reused)
        outcome.reused = [q.qid for q in reused]

    if not random_order:
        outcome.picked.sort(key=lambda q: q.source_row)
    return outcome


def pick_by_bucket(
    buckets: dict,
    quota: dict,
    used_qids,
    rng,
    strategy: str = POOL_WARN_AND_REUSE,
    label: str = "",
    random_order: bool = True,
) -> PickOutcome:
    """按 ``{桶: 题数}`` 逐桶抽取，跨桶借调补齐。

    ``buckets`` 形如 ``{"易": [Question, ...], "中": [...], None: [...]}``，
    ``quota`` 为同键的题数。某个桶不够时先从同题型的其他桶借调。
    """
    outcome = PickOutcome()
    leftovers: List[Question] = []

    for bucket, want in quota.items():
        candidates = buckets.get(bucket, [])
        got = pick_for_section(
            candidates,
            want,
            used_qids,
            rng,
            strategy=strategy,
            label=label,
            random_order=random_order,
        )
        outcome.picked.extend(got.picked)
        outcome.warnings.extend(got.warnings)
        outcome.reused.extend(got.reused)

        # 该桶没用上的题，留给后面的桶借调
        picked_ids = {q.qid for q in got.picked}
        leftovers.extend(q for q in candidates if q.qid not in picked_ids)

    # 借调：补齐因某个桶不足而缺的题数
    target = sum(quota.values())
    deficit = target - len(outcome.picked)
    if deficit > 0 and leftovers:
        borrowed = pick_for_section(
            leftovers,
            deficit,
            used_qids,
            rng,
            strategy=strategy,
            label=label,
            random_order=random_order,
        )
        outcome.picked.extend(borrowed.picked)
        outcome.reused.extend(borrowed.reused)
        # 借调本身不再重复报 warning（上面逐桶已经报过了）

    return outcome
