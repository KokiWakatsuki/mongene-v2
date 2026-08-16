"""比例・反比例まわりの T1 テンプレート登録（実装設計 §7・§7.2）。

Jinja2 文字列を `registry.register_template(name, src)` で登録する。テンプレは
TemplateContext の公開変数（given / context_slots / sub_questions[].label / .asked /
.narrations）のみ参照できる。

テンプレ名は FamilySpec の `text.template` と一致させる（spec_lint R1 が検査）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# ---------------------------------------------------------------------------
# g1_l29.calculation: 比例 y=ax に x を代入して y を求める
# ---------------------------------------------------------------------------
PROP_EVALUATE_DIRECT_V1 = (
    "比例の式 {{ given.expression }} について、{{ given.input_value }} のときの y の値を求めよ。"
)

# ---------------------------------------------------------------------------
# g1_l33.calculation: 反比例 y=a/x に x を代入して y を求める（またはその逆）
# ---------------------------------------------------------------------------
# **問う文字を名指しする。** 「もう一方の値を求めよ」は実物には無い言い方で、
# 何を答えるのかが読み取りにくい。与えられたのが x なら y を、y なら x を問う
# （`input_value` は "x = 6" / "y = -1" の形なので、先頭の文字で決まる）。
PROP_EVALUATE_INVERSE_V1 = (
    "反比例の式 {{ given.expression }} について、{{ given.input_value }} のときの "
    "{% if given.input_value.startswith('x') %}y{% else %}x{% endif %} の値を求めよ。"
)

# ---------------------------------------------------------------------------
# g1_l28.knowledge Lv2: 2量の関係が関数関係かを判別する
# ---------------------------------------------------------------------------
PROP_JUDGE_FUNCTIONAL_V1 = (
    "{{ given.statement }} について、y は x の関数であるといえるか答えよ。"
)

# ---------------------------------------------------------------------------
# g1_l29.knowledge Lv2: 表のx,yの対応が比例かを判別する
# ---------------------------------------------------------------------------
PROP_JUDGE_DIRECT_TABLE_V1 = (
    "次の表は x と y の対応を表している。y は x に比例するといえるか答えよ。\n{{ given.statement }}"
)

# ---------------------------------------------------------------------------
# g1_l33.knowledge Lv2: 表のx,yの対応が反比例かを判別する
# ---------------------------------------------------------------------------
PROP_JUDGE_INVERSE_TABLE_V1 = (
    "次の表は x と y の対応を表している。y は x に反比例するといえるか答えよ。\n{{ given.statement }}"
)

# ---------------------------------------------------------------------------
# g1_l32.find_value: 比例が通る1点から式を決める
# ---------------------------------------------------------------------------
PROP_SOLVE_DIRECT_FROM_POINT_V1 = "{{ given.condition }}。"

# ---------------------------------------------------------------------------
# g1_l35.find_value: 反比例が通る1点から式を決める
# ---------------------------------------------------------------------------
PROP_SOLVE_INVERSE_FROM_POINT_V1 = "{{ given.condition }}。"

# ---------------------------------------------------------------------------
# g1_l31.knowledge Lv1: 比例グラフの向きを判別する
# ---------------------------------------------------------------------------
PROP_JUDGE_GRAPH_DIRECTION_V1 = "{{ given.statement }}。"

# ---------------------------------------------------------------------------
# g1_l34.knowledge Lv1: 双曲線がどの象限にあるかを判別する
# ---------------------------------------------------------------------------
PROP_JUDGE_HYPERBOLA_QUADRANTS_V1 = "{{ given.statement }}。"


def _register_all() -> None:
    REGISTRY.register_template("prop_evaluate_direct_v1", PROP_EVALUATE_DIRECT_V1)
    REGISTRY.register_template("prop_evaluate_inverse_v1", PROP_EVALUATE_INVERSE_V1)
    REGISTRY.register_template("prop_judge_functional_v1", PROP_JUDGE_FUNCTIONAL_V1)
    REGISTRY.register_template("prop_judge_direct_table_v1", PROP_JUDGE_DIRECT_TABLE_V1)
    REGISTRY.register_template("prop_judge_inverse_table_v1", PROP_JUDGE_INVERSE_TABLE_V1)
    REGISTRY.register_template("prop_solve_direct_from_point_v1", PROP_SOLVE_DIRECT_FROM_POINT_V1)
    REGISTRY.register_template("prop_solve_inverse_from_point_v1", PROP_SOLVE_INVERSE_FROM_POINT_V1)
    REGISTRY.register_template("prop_judge_graph_direction_v1", PROP_JUDGE_GRAPH_DIRECTION_V1)
    REGISTRY.register_template(
        "prop_judge_hyperbola_quadrants_v1", PROP_JUDGE_HYPERBOLA_QUADRANTS_V1
    )


_register_all()


__all__ = [
    "PROP_EVALUATE_DIRECT_V1",
    "PROP_EVALUATE_INVERSE_V1",
    "PROP_JUDGE_FUNCTIONAL_V1",
    "PROP_JUDGE_DIRECT_TABLE_V1",
    "PROP_JUDGE_INVERSE_TABLE_V1",
    "PROP_SOLVE_DIRECT_FROM_POINT_V1",
    "PROP_SOLVE_INVERSE_FROM_POINT_V1",
    "PROP_JUDGE_GRAPH_DIRECTION_V1",
    "PROP_JUDGE_HYPERBOLA_QUADRANTS_V1",
]
