"""题库索引。

把 :class:`~app.loader.LoadResult` 包装成可按题型/难度/知识点快速检索的结构，
避免每次抽题都全表扫描（旧实现每抽一个题型就 ``df[df["题型"] == t].copy()`` 一次）。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .loader import LoadResult
from .models import Question


class QuestionPool:
    """只读的题库视图。"""

    def __init__(self, questions_or_result):
        if isinstance(questions_or_result, LoadResult):
            self.result: Optional[LoadResult] = questions_or_result
            questions = list(questions_or_result.questions)
        else:
            self.result = None
            questions = list(questions_or_result)

        self.questions: List[Question] = questions
        self._by_type: Dict[str, List[Question]] = {}
        for question in questions:
            self._by_type.setdefault(question.qtype, []).append(question)

    # ── 查询 ─────────────────────────────────────────────────────────

    @property
    def source(self) -> str:
        return self.result.source if self.result else ""

    def type_labels(self) -> List[str]:
        return list(self._by_type.keys())

    def by_type(self, label: str) -> List[Question]:
        return list(self._by_type.get(label, ()))

    def count(self, label: str) -> int:
        return len(self._by_type.get(label, ()))

    def all(self) -> List[Question]:
        return list(self.questions)

    def find(self, qid: str) -> Optional[Question]:
        for question in self.questions:
            if question.qid == qid:
                return question
        return None

    def difficulty_values(self) -> List[str]:
        return _ordered_values(q.difficulty for q in self.questions)

    def knowledge_values(self) -> List[str]:
        return _ordered_values(q.knowledge for q in self.questions)

    def knowledge_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for question in self.questions:
            if question.knowledge:
                counts[question.knowledge] = counts.get(question.knowledge, 0) + 1
        return counts

    def difficulty_counts(self, label: Optional[str] = None) -> Dict[str, int]:
        source = self.by_type(label) if label else self.questions
        counts: Dict[str, int] = {}
        for question in source:
            key = question.difficulty or "(未标注)"
            counts[key] = counts.get(key, 0) + 1
        return counts

    def count_by_type(self) -> Dict[str, int]:
        return {label: len(items) for label, items in self._by_type.items()}

    def __len__(self):
        return len(self.questions)

    def __repr__(self):
        return f"QuestionPool({len(self.questions)} 题, {len(self._by_type)} 种题型)"


def _ordered_values(values) -> List[str]:
    """按首次出现顺序去重，跳过空值。"""
    seen: List[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return seen
