"""题量分配的 property 测试。

核心不变量：``sum(largest_remainder(total, weights).values()) == total``。
旧实现在比例合计不等于 100 时会破坏这个不变量（把全部余数塞给最大项），
所以这里用大量随机输入反复验证。
"""

import random

import pytest

from app.allocation import allocate_two_axis, allocate_with_knowledge, largest_remainder


def test_known_case_is_proportional():
    """20:40:10 归一化后是 2:4:1，应得 29/57/14。

    旧实现会给出 {判断题:20, 单选题:70, 多选题:10} —— 设 40% 实得 70%。
    """
    result = largest_remainder(100, {"判断题": 20, "单选题": 40, "多选题": 10})
    assert result == {"判断题": 29, "单选题": 57, "多选题": 14}
    assert result["单选题"] != 70


def test_nothing_goes_entirely_to_largest():
    """余数按小数部分分配，不应全部堆给权重最大的那一项。"""
    result = largest_remainder(100, {"a": 40, "b": 30, "c": 30})
    assert result == {"a": 40, "b": 30, "c": 30}


def test_sums_to_total_invariant():
    rng = random.Random(20240101)
    for _ in range(1000):
        size = rng.randint(1, 6)
        weights = {f"k{i}": rng.randint(1, 200) for i in range(size)}
        total = rng.randint(1, 500)
        result = largest_remainder(total, weights)
        assert sum(result.values()) == total, (total, weights, result)
        assert all(v >= 0 for v in result.values())


def test_sums_to_total_with_remaining_zero_weights():
    """允许权重为 0 —— 该题型分不到题，但不变量仍要成立。"""
    rng = random.Random(7)
    for _ in range(200):
        weights = {"a": rng.randint(0, 50), "b": rng.randint(0, 50), "c": 0}
        total = rng.randint(1, 60)
        if sum(weights.values()) == 0:
            continue
        result = largest_remainder(total, weights)
        assert sum(result.values()) == total
        assert result["c"] == 0


def test_deterministic():
    """同输入必须同输出（用于保证"同 seed 同卷"）。"""
    weights = {"a": 1, "b": 1, "c": 1}
    first = largest_remainder(10, weights)
    for _ in range(20):
        assert largest_remainder(10, weights) == first


def test_edge_inputs():
    assert largest_remainder(0, {"a": 1}) == {"a": 0}
    assert largest_remainder(-5, {"a": 1}) == {"a": 0}
    assert largest_remainder(10, {}) == {}
    assert largest_remainder(10, {"a": 0, "b": 0}) == {"a": 0, "b": 0}


def test_two_axis_splits_within_type():
    plan = allocate_two_axis(10, {"judgment": 5, "mcq": 5}, {"易": 5, "中": 3, "难": 2})
    assert set(plan) == {"judgment", "mcq"}
    for qtype, buckets in plan.items():
        assert sum(buckets.values()) == 5, qtype


def test_two_axis_without_weights():
    plan = allocate_two_axis(10, {"judgment": 10}, {})
    assert plan == {"judgment": {None: 10}}


def test_knowledge_cover_first_gives_each_one_a_question():
    quota = allocate_with_knowledge(
        count=5,
        available_by_knowledge={"考点A": 50, "考点B": 50, "考点C": 1},
        selected=["考点A", "考点B", "考点C"],
        cover_first=True,
    )
    assert set(quota) == {"考点A", "考点B", "考点C"}
    assert all(v >= 1 for v in quota.values())
    assert sum(quota.values()) == 5


def test_knowledge_skips_unavailable():
    quota = allocate_with_knowledge(
        count=3,
        available_by_knowledge={"考点A": 10, "考点B": 0},
        selected=["考点A", "考点B"],
    )
    assert quota.get("考点B", 0) == 0
    assert sum(quota.values()) == 3
