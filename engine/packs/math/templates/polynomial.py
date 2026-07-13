"""多項式（式の計算）まわりの T1 テンプレート登録（実装設計 §7・§7.2）。

Jinja2 文字列を `registry.register_template(name, src)` で登録する。テンプレは
TemplateContext の公開変数（given / context_slots / sub_questions[].{label,asked,
narrations}）のみ参照できる。answer/params は属性として存在しないため構文的に
参照不能（Q5 の構造防止）。

テンプレ名は FamilySpec の `text.template` と一致させる（spec_lint R1 が検査）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# ---------------------------------------------------------------------------
# g2_l2.calculation Lv1/Lv2: 同類項をまとめる（C2 クラスタ初セル）
# ---------------------------------------------------------------------------
LF_COMBINE_LIKE_TERMS_V1 = "次の式の同類項をまとめよ。\n{{ given.expression }}"

# g2_l3.calculation Lv1/Lv2: 多項式の加減（かっこを外して整理する）
# ※ g2_l5（分配・除法）/ g2_l4（単項式乗除）も同文「次の計算をせよ」を再利用する。
LF_ADD_SUBTRACT_POLYNOMIALS_V1 = "次の計算をせよ。\n{{ given.expression }}"

# g2_l1.calculation Lv1: 単項式・多項式の次数を答える
LF_DEGREE_V1 = "次の式の次数を答えよ。\n{{ given.expression }}"

# g2_l9.calculation Lv1/Lv2/Lv3: 等式を指定された文字について解く
LF_SOLVE_FOR_VARIABLE_V1 = (
    "次の等式を {{ given.target_variable }} について解け。\n{{ given.equation }}"
)


def _register_all() -> None:
    REGISTRY.register_template("lf_combine_like_terms_v1", LF_COMBINE_LIKE_TERMS_V1)
    REGISTRY.register_template(
        "lf_add_subtract_polynomials_v1", LF_ADD_SUBTRACT_POLYNOMIALS_V1
    )
    REGISTRY.register_template("lf_degree_v1", LF_DEGREE_V1)
    REGISTRY.register_template("lf_solve_for_variable_v1", LF_SOLVE_FOR_VARIABLE_V1)


_register_all()


__all__ = [
    "LF_COMBINE_LIKE_TERMS_V1",
    "LF_ADD_SUBTRACT_POLYNOMIALS_V1",
    "LF_DEGREE_V1",
    "LF_SOLVE_FOR_VARIABLE_V1",
]
