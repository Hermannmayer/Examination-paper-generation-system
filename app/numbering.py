"""题号编排与答案分组。

承载 bug 9 的修复：旧实现按题型各自从 1 重新编号
（试卷里单选题是 6-10 题，答案页却写「单选题答案: 1-5」），
这里一律按**真实全局题号**分组。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .constants import ESSAY_LABELS, OBJECTIVE_LABELS
from .models import Section


def assign_numbers(sections: Sequence[Section], start: int = 1) -> None:
    """给各大题块填上全局题号区间（1-based 闭区间）。就地修改。"""
    current = start
    for section in sections:
        section.number_start = current
        section.number_end = current + section.count - 1
        current += section.count


def number_of(section: Section, offset: int) -> int:
    """section 内第 ``offset`` 题（0-based）的全局题号。"""
    return section.number_start + offset


def format_answer_value(answer) -> str:
    """多字符答案用方括号包裹以便区分（如多选 ``ABD`` → ``[ABD]``）。"""
    text = str(answer)
    return f"[{text}]" if len(text) > 1 else text


def format_answers_spans(
    numbers: Sequence[int], answers: Sequence[str], per_line: int = 5
) -> str:
    """按**真实题号**每 ``per_line`` 题一组。

    >>> format_answers_spans([6,7,8,9,10], ['A','B','C','D','A'])
    '6-10: A B C D A'
    """
    numbers = list(numbers)
    answers = list(answers)
    if not numbers:
        return ""

    chunks = []
    for start in range(0, len(numbers), per_line):
        nums = numbers[start : start + per_line]
        vals = [format_answer_value(a) for a in answers[start : start + per_line]]
        span = f"{nums[0]}-{nums[-1]}" if len(nums) > 1 else str(nums[0])
        chunks.append(f"{span}: {' '.join(vals)}")
    return "  ".join(chunks)


@dataclass
class AnswerGroup:
    """答案页上的一行。"""

    label: str  # "全部" / "判断题" / ...
    span_text: str  # "6-10: A B C D A"

    def to_dict(self):
        return {"label": self.label, "text": self.span_text}


def _section_answers(section: Section):
    """返回 (题号列表, 答案列表)，均按题号升序。"""
    numbers = list(range(section.number_start, section.number_end + 1))
    answers = [q.answer for q in section.questions]
    # 题库不足导致题数少于区间长度时，以实际题数为准
    return numbers[: len(answers)], answers


def build_answer_groups(
    sections: Sequence[Section], per_line: int = 5
) -> List[AnswerGroup]:
    """构造答案页的**客观题**部分：先「全部答案」，再按题型分组。

    全部使用真实题号。简答题不在这里 —— 它的答案是成段文字，
    压成「6-10: A B C」这种格式没有意义，见 :func:`build_essay_answers`。
    """
    sections = [
        s for s in sections if s.count > 0 and s.label in OBJECTIVE_LABELS
    ]
    if not sections:
        return []

    all_numbers: List[int] = []
    all_answers: List[str] = []
    for section in sections:
        nums, answers = _section_answers(section)
        all_numbers.extend(nums)
        all_answers.extend(answers)

    groups = [
        AnswerGroup("全部", format_answers_spans(all_numbers, all_answers, per_line))
    ]

    for label in OBJECTIVE_LABELS:
        for section in sections:
            if section.label != label:
                continue
            nums, answers = _section_answers(section)
            if answers:
                groups.append(
                    AnswerGroup(
                        label, format_answers_spans(nums, answers, per_line)
                    )
                )
    return groups


def build_essay_answers(sections: Sequence[Section]) -> List[Tuple[int, str]]:
    """简答题的参考答案：``[(题号, 答案全文), ...]``。

    成段文字必须逐题列出，不能沿用客观题的紧凑分组。
    """
    result: List[Tuple[int, str]] = []
    for section in sections:
        if section.label not in ESSAY_LABELS:
            continue
        for offset, question in enumerate(section.questions):
            answer = (question.answer or "").strip()
            if answer:
                result.append((number_of(section, offset), answer))
    return result


def build_answer_groups_from_pairs(pairs, per_line: int = 5) -> List[AnswerGroup]:
    """从 ``[(全局题号, 答案, 题型), ...]`` 构造答案分组。

    供渲染层使用（渲染层拿不到 Section 对象，只有这份平铺数据）。
    同样按**真实题号**分组，与 :func:`build_answer_groups` 结果一致。
    """
    pairs = sorted(pairs or (), key=lambda p: p[0])
    if not pairs:
        return []

    groups = [
        AnswerGroup(
            "全部",
            format_answers_spans(
                [p[0] for p in pairs], [p[1] for p in pairs], per_line
            ),
        )
    ]
    for label in ALL_LABELS:
        subset = [p for p in pairs if p[2] == label]
        if subset:
            groups.append(
                AnswerGroup(
                    label,
                    format_answers_spans(
                        [p[0] for p in subset], [p[1] for p in subset], per_line
                    ),
                )
            )
    return groups
