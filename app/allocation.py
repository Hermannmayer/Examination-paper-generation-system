"""题量分配：纯函数，无副作用，便于 property 测试。

全部使用**最大余数法**。旧实现的错误是
``int(total * ratio / 100)`` 之后把全部余数塞给比例最大的题型，
导致设 40% 实得 70%；而且未按权重合计归一化，
比例合计不等于 100 时结果同样错误。
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Tuple

Number = float


def largest_remainder(total: int, weights: Mapping[str, Number]) -> Dict[str, int]:
    """按权重把 ``total`` 拆成整数份额。

    - 先按权重合计归一化（所以 ``{20,40,10}`` 与 ``{2,4,1}`` 等价）
    - 取整后，余数按**小数部分**从大到小分配
    - 并列时按 (权重降序, 键的字典序) 打破，保证确定性

    保证：``sum(result.values()) == total``（total > 0 且权重和 > 0 时）。
    """
    keys = list(weights.keys())
    result = {k: 0 for k in keys}

    if total <= 0 or not keys:
        return result

    weight_sum = sum(float(weights[k]) for k in keys)
    if weight_sum <= 0:
        return result

    ideals: List[Tuple[str, float]] = []
    allocated = 0
    for key in keys:
        ideal = total * float(weights[key]) / weight_sum
        base = int(ideal)  # 权重非负，int() 等价于 floor
        result[key] = base
        allocated += base
        ideals.append((key, ideal - base))

    remainder = total - allocated
    if remainder > 0:
        # 小数部分降序；并列时权重大的优先；再并列按键名，保证确定性
        ideals.sort(key=lambda item: (-item[1], -float(weights[item[0]]), item[0]))
        for key, _ in ideals[:remainder]:
            result[key] += 1

    assert sum(result.values()) == total, (
        f"分配结果合计 {sum(result.values())} != {total}"
    )
    return result


def allocate_two_axis(
    total: int,
    type_weights: Mapping[str, Number],
    difficulty_weights: Mapping[str, Number],
) -> Dict[str, Dict[str, int]]:
    """两级分配：先把总题数分到各题型，再在每种题型内按难度权重分。

    返回 ``{题型: {难度: 题数}}``。``difficulty_weights`` 为空时，
    该题型的全部额度放在 ``None`` 这个键下（表示不限难度）。
    """
    by_type = largest_remainder(total, type_weights)
    out: Dict[str, Dict[str, int]] = {}
    for qtype, count in by_type.items():
        if not difficulty_weights:
            out[qtype] = {None: count}
        else:
            out[qtype] = largest_remainder(count, difficulty_weights)
    return out


def allocate_with_knowledge(
    count: int,
    available_by_knowledge: Mapping[str, int],
    selected: List[str],
    cover_first: bool = True,
) -> Dict[str, int]:
    """在选定的知识点之间分配题数。

    ``cover_first=True`` 时每个可用知识点先保底 1 题，剩余额度再按可用量比例分配，
    避免某个冷门知识点被完全跳过。
    """
    usable = [k for k in selected if available_by_knowledge.get(k, 0) > 0]
    if not usable or count <= 0:
        return {}

    quota: Dict[str, int] = {k: 0 for k in usable}

    if cover_first and count >= len(usable):
        for key in usable:
            quota[key] = 1
        remaining = count - len(usable)
    else:
        remaining = count

    if remaining > 0:
        # 保底之后各知识点的剩余可用量，作为再分配的权重
        weights = {
            k: max(0, available_by_knowledge.get(k, 0) - quota[k]) for k in usable
        }
        if sum(weights.values()) > 0:
            extra = largest_remainder(remaining, weights)
            for key in usable:
                quota[key] += extra.get(key, 0)
        else:
            # 都不够再分，就按可用量比例兜底
            quota.update(largest_remainder(remaining, available_by_knowledge))

    return {k: v for k, v in quota.items() if v > 0}
