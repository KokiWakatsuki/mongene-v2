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

# --- graph_table（かく／読む）---
# 「読む」セル（g3_l33 Lv1・g3_l38 Lv2）: 場面と設問をまるごと given.situation_params に
# 入れる（式は与えない＝グラフから読む題材が計算で解けてしまうのを防ぐ）。
LF_PARABOLA_READ_POINTS_V1 = "{{ given.situation_params }}。"

# g3_l33.graph_table Lv2: 対応表から2本の放物線をかき、開き方を比べる
LF_PARABOLA_DRAW_PAIR_V1 = "関数 {{ given.expression }} について、{{ given.situation_params }}。"

# g3_l34.graph_table Lv2: 放物線をかき、変域に対応する部分をなぞって y の変域を読む
LF_PARABOLA_DOMAIN_GRAPH_V1 = (
    "関数 {{ given.expression }} のグラフをかき、x の変域が {{ given.x_domain }} "
    "に対応する部分を太くなぞって示し、そのときの y の変域をグラフから読み取れ。"
)

# g3_l36.graph_table Lv2: 身のまわりの現象の表からグラフをかく
LF_PHENOMENON_CURVE_V1 = (
    "{{ given.situation_params }}の関係を調べたところ、次の表のようになった。"
    "{{ given.data_table }}。表の値を座標としてとってグラフをかけ。"
)

# g3_l37.graph_table Lv2: 放物線と直線をかき、囲まれた部分を斜線で示す
LF_PARABOLA_LINE_REGION_V1 = (
    "放物線 {{ given.expression }} と直線 {{ given.line_a }} を同じ座標軸にかけ。"
    "また、{{ given.situation_params }}とき、この放物線と直線で囲まれた部分を斜線で示せ。"
)

# g3_l38.graph_table Lv3: 区間ごとに式が変わる面積のグラフ（折れ線）をかく
LF_PIECEWISE_AREA_GRAPH_V1 = "{{ given.condition }}。"


def _register_all() -> None:
    REGISTRY.register_template("lf_quadratic_function_evaluate_v1", LF_QUADRATIC_FUNCTION_EVALUATE_V1)
    REGISTRY.register_template("lf_quadratic_y_range_v1", LF_QUADRATIC_Y_RANGE_V1)
    REGISTRY.register_template("lf_quadratic_roc_v1", LF_QUADRATIC_ROC_V1)
    REGISTRY.register_template("lf_quadratic_intersection_v1", LF_QUADRATIC_INTERSECTION_V1)
    REGISTRY.register_template("lf_quadratic_motion_area_v1", LF_QUADRATIC_MOTION_AREA_V1)
    REGISTRY.register_template("lf_parabola_read_points_v1", LF_PARABOLA_READ_POINTS_V1)
    REGISTRY.register_template("lf_parabola_draw_pair_v1", LF_PARABOLA_DRAW_PAIR_V1)
    REGISTRY.register_template("lf_parabola_domain_graph_v1", LF_PARABOLA_DOMAIN_GRAPH_V1)
    REGISTRY.register_template("lf_phenomenon_curve_v1", LF_PHENOMENON_CURVE_V1)
    REGISTRY.register_template("lf_parabola_line_region_v1", LF_PARABOLA_LINE_REGION_V1)
    REGISTRY.register_template("lf_piecewise_area_graph_v1", LF_PIECEWISE_AREA_GRAPH_V1)


_register_all()


__all__ = [
    "LF_QUADRATIC_FUNCTION_EVALUATE_V1",
    "LF_QUADRATIC_Y_RANGE_V1",
    "LF_QUADRATIC_ROC_V1",
    "LF_QUADRATIC_INTERSECTION_V1",
    "LF_QUADRATIC_MOTION_AREA_V1",
    "LF_PARABOLA_READ_POINTS_V1",
    "LF_PARABOLA_DRAW_PAIR_V1",
    "LF_PARABOLA_DOMAIN_GRAPH_V1",
    "LF_PHENOMENON_CURVE_V1",
    "LF_PARABOLA_LINE_REGION_V1",
    "LF_PIECEWISE_AREA_GRAPH_V1",
]
