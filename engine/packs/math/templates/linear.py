"""一次関数まわりの T1 テンプレート登録（実装設計 §7・§7.2）。

Jinja2 文字列を `registry.register_template(name, src)` で登録する。テンプレは
TemplateContext の公開変数（given / context_slots / sub_questions[].label / .asked /
.narrations）のみ参照できる。answer/srepr/params は属性として存在しないため
構文的に参照不能（Q5 の構造防止）。

テンプレ名は FamilySpec の `text.template` と一致させる（spec_lint R1 が検査）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# ---------------------------------------------------------------------------
# g2_l25.find_value: 2点から式を求める
# ---------------------------------------------------------------------------
LF_EXPR_TWO_POINTS_V1 = (
    "2点 {{ given.point_a }} と {{ given.point_b }} を通る直線の式を求めよ。"
)

# ---------------------------------------------------------------------------
# g2_l24.find_value Lv1: 傾きと1点から式を求める
# ---------------------------------------------------------------------------
LF_EXPR_SLOPE_POINT_V1 = (
    "傾きが {{ given.slope }} で、点 {{ given.point_a }} を通る直線の式を求めよ。"
)

# ---------------------------------------------------------------------------
# g2_l24.find_value Lv3: 平行条件から式を求める
# ---------------------------------------------------------------------------
LF_EXPR_PARALLEL_V1 = (
    "点 {{ given.point_a }} を通り、直線 {{ given.condition }} に平行な直線の式を求めよ。"
)

# ---------------------------------------------------------------------------
# g2_l25.graph_table Lv2: グラフ上の2格子点を読む
# ---------------------------------------------------------------------------
GRAPH_READ_TWO_POINTS_V1 = (
    "グラフ上の直線が通る2つの格子点の座標を読み取れ。"
)


# ---------------------------------------------------------------------------
# g2_l21.graph_table Lv1: グラフから傾きと切片を読む（横展開#4）
# given は空（式は提示せず図のみ）。answer/params は参照不能なので数値は本文に出ない。
# ---------------------------------------------------------------------------
GRAPH_READ_SLOPE_INTERCEPT_V1 = (
    "座標平面にかかれた直線のグラフから、この直線の傾きと切片を読み取れ。"
)


# ---------------------------------------------------------------------------
# g2_l26.calculation Lv1: ax+by=c を y=… に変形する（横展開#5・最初の calculation セル）
# ---------------------------------------------------------------------------
LF_SOLVE_FOR_Y_V1 = (
    "2元1次方程式 {{ given.equation }} を、y について解いた式（y = … の形）に変形せよ。"
)


# ---------------------------------------------------------------------------
# g2_l19.calculation Lv1: y=ax+b に x を代入して y を求める（横展開#6）
# ---------------------------------------------------------------------------
LF_EVALUATE_AT_X_V1 = (
    "1次関数 {{ given.expression }} について、{{ given.input_value }} のときの y の値を求めよ。"
)


# ---------------------------------------------------------------------------
# g2_l22.calculation Lv1: グラフが通る点を代入で求める（横展開#7・answer=coordinate）
# ---------------------------------------------------------------------------
LF_POINT_ON_LINE_V1 = (
    "1次関数 {{ given.expression }} のグラフが通る点のうち、"
    "x 座標が {{ given.input_value }} である点の座標を求めよ。"
)


# ---------------------------------------------------------------------------
# g2_l22.graph_table Lv1: y=ax+b のグラフをかく（横展開#8・「かく」capability）
# 問題図＝空の方眼。答えは GraphAnswer（特徴点）＋模範解答図。
# ---------------------------------------------------------------------------
LF_DRAW_GRAPH_V1 = (
    "1次関数 {{ given.expression }} のグラフを、座標平面にかけ。"
)


# ---------------------------------------------------------------------------
# g2_l20.find_value Lv1: 2点から変化の割合を求める（横展開の第1セル）
# ---------------------------------------------------------------------------
LF_RATE_OF_CHANGE_V1 = (
    "2点 {{ given.point_a }} と {{ given.point_b }} を通る1次関数について、変化の割合を求めよ。"
)

# ---------------------------------------------------------------------------
# g2_l27.find_value Lv2/Lv3: 2直線の交点の座標（横展開の第2セル・両レベル共用）
# ---------------------------------------------------------------------------
LF_INTERSECTION_V1 = (
    # 「2直線」ではなく「2つの直線」: 助数詞「つ」は G-Q5t 漏洩スキャンの除外対象で、
    # 先頭の "2" が答え座標の数値と衝突する偽陽性を避ける（graph_table と同種）。
    "2つの直線 {{ given.line_a }} と {{ given.line_b }} の交点の座標を求めよ。"
)

# ---------------------------------------------------------------------------
# g2_l23.find_value: 変域とグラフの端点（横展開#3）
# Lv2=順方向（関数+x変域→y変域）／Lv3=逆算（x変域+y変域+符号→式）
# ---------------------------------------------------------------------------
LF_Y_RANGE_V1 = (
    "1次関数 {{ given.expression }} について、"
    "x の変域が {{ given.x_domain }} のときの y の変域を求めよ。"
)
LF_EXPR_FROM_RANGE_V1 = (
    "1次関数 y = ax + b について、x の変域が {{ given.x_domain }} のとき "
    "y の変域が {{ given.y_range }} であった。{{ given.condition }}、この1次関数の式を求めよ。"
)


def _register_all() -> None:
    REGISTRY.register_template("lf_expr_two_points_v1", LF_EXPR_TWO_POINTS_V1)
    REGISTRY.register_template("lf_expr_slope_point_v1", LF_EXPR_SLOPE_POINT_V1)
    REGISTRY.register_template("lf_expr_parallel_v1", LF_EXPR_PARALLEL_V1)
    REGISTRY.register_template("graph_read_two_points_v1", GRAPH_READ_TWO_POINTS_V1)
    REGISTRY.register_template("graph_read_slope_intercept_v1", GRAPH_READ_SLOPE_INTERCEPT_V1)
    REGISTRY.register_template("lf_solve_for_y_v1", LF_SOLVE_FOR_Y_V1)
    REGISTRY.register_template("lf_evaluate_at_x_v1", LF_EVALUATE_AT_X_V1)
    REGISTRY.register_template("lf_point_on_line_v1", LF_POINT_ON_LINE_V1)
    REGISTRY.register_template("lf_draw_graph_v1", LF_DRAW_GRAPH_V1)
    REGISTRY.register_template("lf_rate_of_change_v1", LF_RATE_OF_CHANGE_V1)
    REGISTRY.register_template("lf_intersection_v1", LF_INTERSECTION_V1)
    REGISTRY.register_template("lf_y_range_v1", LF_Y_RANGE_V1)
    REGISTRY.register_template("lf_expr_from_range_v1", LF_EXPR_FROM_RANGE_V1)


_register_all()


__all__ = [
    "LF_EXPR_TWO_POINTS_V1",
    "LF_EXPR_SLOPE_POINT_V1",
    "LF_EXPR_PARALLEL_V1",
    "GRAPH_READ_TWO_POINTS_V1",
    "GRAPH_READ_SLOPE_INTERCEPT_V1",
    "LF_SOLVE_FOR_Y_V1",
    "LF_EVALUATE_AT_X_V1",
    "LF_POINT_ON_LINE_V1",
    "LF_DRAW_GRAPH_V1",
    "LF_RATE_OF_CHANGE_V1",
    "LF_INTERSECTION_V1",
    "LF_Y_RANGE_V1",
    "LF_EXPR_FROM_RANGE_V1",
]
