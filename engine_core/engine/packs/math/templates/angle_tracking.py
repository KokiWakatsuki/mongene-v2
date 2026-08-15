"""平行線・三角形・多角形の角まわりの T1 テンプレート登録（実装設計 §7・§7.2）。"""
from __future__ import annotations

from engine.core.registry import REGISTRY

LF_ANGLE_EQUALITY_V1 = "{{ given.condition }}。"
LF_ZIGZAG_ANGLE_SUM_V1 = "{{ given.condition }}。"
LF_JUDGE_PARALLEL_FROM_ANGLE_V1 = "{{ given.statement }}。"
LF_TRIANGLE_THIRD_ANGLE_V1 = "{{ given.condition }}。"
LF_POLYGON_INTERIOR_SUM_AND_ANGLE_V1 = "{{ given.condition }}。"
LF_POLYGON_SIDES_FROM_INTERIOR_SUM_V1 = "{{ given.condition }}。"
LF_REGULAR_POLYGON_EXTERIOR_ANGLE_V1 = "{{ given.condition }}。"
LF_POLYGON_SIDES_FROM_INTERIOR_ANGLE_V1 = "{{ given.condition }}。"


def _register_all() -> None:
    REGISTRY.register_template("lf_angle_equality_v1", LF_ANGLE_EQUALITY_V1)
    REGISTRY.register_template("lf_zigzag_angle_sum_v1", LF_ZIGZAG_ANGLE_SUM_V1)
    REGISTRY.register_template(
        "lf_judge_parallel_from_angle_v1", LF_JUDGE_PARALLEL_FROM_ANGLE_V1
    )
    REGISTRY.register_template("lf_triangle_third_angle_v1", LF_TRIANGLE_THIRD_ANGLE_V1)
    REGISTRY.register_template(
        "lf_polygon_interior_sum_and_angle_v1", LF_POLYGON_INTERIOR_SUM_AND_ANGLE_V1
    )
    REGISTRY.register_template(
        "lf_polygon_sides_from_interior_sum_v1", LF_POLYGON_SIDES_FROM_INTERIOR_SUM_V1
    )
    REGISTRY.register_template(
        "lf_regular_polygon_exterior_angle_v1", LF_REGULAR_POLYGON_EXTERIOR_ANGLE_V1
    )
    REGISTRY.register_template(
        "lf_polygon_sides_from_interior_angle_v1", LF_POLYGON_SIDES_FROM_INTERIOR_ANGLE_V1
    )


_register_all()


__all__ = [
    "LF_ANGLE_EQUALITY_V1",
    "LF_ZIGZAG_ANGLE_SUM_V1",
    "LF_JUDGE_PARALLEL_FROM_ANGLE_V1",
    "LF_TRIANGLE_THIRD_ANGLE_V1",
    "LF_POLYGON_INTERIOR_SUM_AND_ANGLE_V1",
    "LF_POLYGON_SIDES_FROM_INTERIOR_SUM_V1",
    "LF_REGULAR_POLYGON_EXTERIOR_ANGLE_V1",
    "LF_POLYGON_SIDES_FROM_INTERIOR_ANGLE_V1",
]
