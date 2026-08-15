"""三角形の合同条件・二等辺三角形・正三角形まわりの T1 テンプレート登録

（実装設計 §7・§7.2）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

LF_ISOSCELES_BASE_ANGLE_V1 = "{{ given.condition }}。"
LF_EQUILATERAL_TRIANGLE_PROPERTIES_V1 = "{{ given.condition }}。"
LF_JUDGE_ISOSCELES_FROM_ANGLE_V1 = "{{ given.statement }}。"
LF_JUDGE_EQUILATERAL_FROM_CONDITION_V1 = "{{ given.statement }}。"


def _register_all() -> None:
    REGISTRY.register_template("lf_isosceles_base_angle_v1", LF_ISOSCELES_BASE_ANGLE_V1)
    REGISTRY.register_template(
        "lf_equilateral_triangle_properties_v1", LF_EQUILATERAL_TRIANGLE_PROPERTIES_V1
    )
    REGISTRY.register_template(
        "lf_judge_isosceles_from_angle_v1", LF_JUDGE_ISOSCELES_FROM_ANGLE_V1
    )
    REGISTRY.register_template(
        "lf_judge_equilateral_from_condition_v1", LF_JUDGE_EQUILATERAL_FROM_CONDITION_V1
    )


_register_all()


__all__ = [
    "LF_ISOSCELES_BASE_ANGLE_V1",
    "LF_EQUILATERAL_TRIANGLE_PROPERTIES_V1",
    "LF_JUDGE_ISOSCELES_FROM_ANGLE_V1",
    "LF_JUDGE_EQUILATERAL_FROM_CONDITION_V1",
]
