"""平面図形まわりの T1 テンプレート登録（実装設計 §7・§7.2）。"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g1_l38/l39/l40.knowledge Lv1: 移動の不変性の判別
LF_JUDGE_TRANSFORMATION_INVARIANT_V1 = "{{ given.statement }}。"

# g1_l41/l42.knowledge Lv1: 作図の性質(等距離)の判別
LF_JUDGE_CONSTRUCTION_PROPERTY_V1 = "{{ given.statement }}。"

# g1_l37.knowledge Lv2: 「点と直線との距離」の意味の判別
LF_JUDGE_POINT_LINE_DISTANCE_MEANING_V1 = "{{ given.statement }}。"

# g1_l45.knowledge Lv2: 円の性質(比例・垂直性)の判別
LF_JUDGE_CIRCLE_PROPERTY_V1 = "{{ given.statement }}。"

# g1_l46.find_value Lv1: おうぎ形の弧の長さ/面積
LF_SECTOR_ARC_LENGTH_OR_AREA_V1 = "{{ given.condition }}。"

# g1_l46.find_value Lv2: 面積から中心角を逆算
LF_SECTOR_SOLVE_CENTRAL_ANGLE_V1 = "{{ given.condition }}。"


def _register_all() -> None:
    REGISTRY.register_template(
        "lf_judge_transformation_invariant_v1", LF_JUDGE_TRANSFORMATION_INVARIANT_V1
    )
    REGISTRY.register_template(
        "lf_judge_construction_property_v1", LF_JUDGE_CONSTRUCTION_PROPERTY_V1
    )
    REGISTRY.register_template(
        "lf_judge_point_line_distance_meaning_v1", LF_JUDGE_POINT_LINE_DISTANCE_MEANING_V1
    )
    REGISTRY.register_template("lf_judge_circle_property_v1", LF_JUDGE_CIRCLE_PROPERTY_V1)
    REGISTRY.register_template(
        "lf_sector_arc_length_or_area_v1", LF_SECTOR_ARC_LENGTH_OR_AREA_V1
    )
    REGISTRY.register_template(
        "lf_sector_solve_central_angle_v1", LF_SECTOR_SOLVE_CENTRAL_ANGLE_V1
    )


_register_all()


__all__ = [
    "LF_JUDGE_TRANSFORMATION_INVARIANT_V1",
    "LF_JUDGE_CONSTRUCTION_PROPERTY_V1",
    "LF_JUDGE_POINT_LINE_DISTANCE_MEANING_V1",
    "LF_JUDGE_CIRCLE_PROPERTY_V1",
    "LF_SECTOR_ARC_LENGTH_OR_AREA_V1",
    "LF_SECTOR_SOLVE_CENTRAL_ANGLE_V1",
]
