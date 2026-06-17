"""Standards Alignment: 学年範囲外単元の検出（§12.5）"""
from __future__ import annotations

from typing import TYPE_CHECKING, Set

if TYPE_CHECKING:
    from apps.api.src.core.representation.middle_representation import MiddleRepresentation


# 学年ごとに使ってはいけないタグの簡易マップ
# Phase 1 では最小限。詳細は Phase 4 の prerequisite_graph で連鎖判定する
_GRADE_FORBIDDEN_TAGS: dict[int, Set[str]] = {
    1: {
        "square_root",
        "pythagorean",
        "quadratic_equation",
        "quadratic_function",
        "similarity",
        "inscribed_angle",
        "factorization",
        "sampling_survey",
    },
    2: {
        "square_root",
        "pythagorean",
        "quadratic_equation",
        "quadratic_function",
        "inscribed_angle",
        "sampling_survey",
    },
    3: set(),
}


def evaluate_standards_alignment(
    mr: "MiddleRepresentation",
    lesson_id: str,
    *,
    grade: int | None = None,
) -> bool:
    """生成された問題のタグがその学年の範囲内かを判定する"""
    if grade is None:
        grade = _grade_from_lesson_id(lesson_id)
    forbidden = _GRADE_FORBIDDEN_TAGS.get(grade, set())
    for tag in mr.selected_tags:
        if tag in forbidden:
            return False
    return True


def _grade_from_lesson_id(lesson_id: str) -> int:
    """`g{n}_l{m}` 形式から grade を取り出す"""
    if lesson_id.startswith("g") and "_" in lesson_id:
        head = lesson_id.split("_", 1)[0]
        try:
            return int(head[1:])
        except ValueError:
            pass
    return 3
