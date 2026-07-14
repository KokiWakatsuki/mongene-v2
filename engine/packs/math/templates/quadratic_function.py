"""関数 y=ax² まわりの T1 テンプレート登録（実装設計 §7・§7.2）。"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g3_l32.calculation Lv1: y=ax² に代入して y を求める
LF_QUADRATIC_FUNCTION_EVALUATE_V1 = (
    "関数 {{ given.expression }} について、{{ given.input_value }} のときの y の値を求めよ。"
)

# g3_l34.find_value Lv2/Lv3: y=ax² の変域を求める
LF_QUADRATIC_Y_RANGE_V1 = "{{ given.condition }}。"

# g3_l35.find_value Lv2/Lv3: y=ax² の変化の割合の順算・逆算・比較
LF_QUADRATIC_ROC_V1 = "{{ given.condition }}。"

# g3_l37.find_value Lv2/Lv3/Lv4: 放物線と直線の交点・線分長・面積・逆算
LF_QUADRATIC_INTERSECTION_V1 = "{{ given.condition }}。"

# g3_l38.find_value Lv2/Lv3: 動点による三角形 ABP の面積
LF_QUADRATIC_MOTION_AREA_V1 = "{{ given.condition }}。"


def _register_all() -> None:
    REGISTRY.register_template("lf_quadratic_function_evaluate_v1", LF_QUADRATIC_FUNCTION_EVALUATE_V1)
    REGISTRY.register_template("lf_quadratic_y_range_v1", LF_QUADRATIC_Y_RANGE_V1)
    REGISTRY.register_template("lf_quadratic_roc_v1", LF_QUADRATIC_ROC_V1)
    REGISTRY.register_template("lf_quadratic_intersection_v1", LF_QUADRATIC_INTERSECTION_V1)
    REGISTRY.register_template("lf_quadratic_motion_area_v1", LF_QUADRATIC_MOTION_AREA_V1)


_register_all()


__all__ = [
    "LF_QUADRATIC_FUNCTION_EVALUATE_V1",
    "LF_QUADRATIC_Y_RANGE_V1",
    "LF_QUADRATIC_ROC_V1",
    "LF_QUADRATIC_INTERSECTION_V1",
    "LF_QUADRATIC_MOTION_AREA_V1",
]
