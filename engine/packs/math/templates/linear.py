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
# g2_l20.find_value Lv1: 2点から変化の割合を求める（横展開の第1セル）
# ---------------------------------------------------------------------------
LF_RATE_OF_CHANGE_V1 = (
    "2点 {{ given.point_a }} と {{ given.point_b }} を通る1次関数について、変化の割合を求めよ。"
)


def _register_all() -> None:
    REGISTRY.register_template("lf_expr_two_points_v1", LF_EXPR_TWO_POINTS_V1)
    REGISTRY.register_template("lf_expr_slope_point_v1", LF_EXPR_SLOPE_POINT_V1)
    REGISTRY.register_template("lf_expr_parallel_v1", LF_EXPR_PARALLEL_V1)
    REGISTRY.register_template("graph_read_two_points_v1", GRAPH_READ_TWO_POINTS_V1)
    REGISTRY.register_template("lf_rate_of_change_v1", LF_RATE_OF_CHANGE_V1)


_register_all()


__all__ = [
    "LF_EXPR_TWO_POINTS_V1",
    "LF_EXPR_SLOPE_POINT_V1",
    "LF_EXPR_PARALLEL_V1",
    "GRAPH_READ_TWO_POINTS_V1",
    "LF_RATE_OF_CHANGE_V1",
]
