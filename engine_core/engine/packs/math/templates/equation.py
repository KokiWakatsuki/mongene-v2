"""一次方程式まわりの T1 テンプレート登録（実装設計 §7・§7.2）。

テンプレは TemplateContext の公開変数（given / sub_questions[].{label,asked,narrations}）
のみ参照できる。answer/params は属性として存在しないため参照不能（Q5 の構造防止）。
テンプレ名は FamilySpec の `text.template` と一致させる（spec_lint R1 が検査）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g1_l21.calculation: 等式の性質を使って解く
LF_SOLVE_EQUATION_PROPERTY_V1 = "等式の性質を使って、次の方程式を解け。\n{{ given.equation }}"
# g1_l22.calculation Lv1: 移項を使って解く
LF_SOLVE_EQUATION_TRANSPOSE_V1 = "移項を使って、次の方程式を解け。\n{{ given.equation }}"
# g1_l22.calculation Lv2 ほか: 一般の方程式を解く
LF_SOLVE_EQUATION_V1 = "次の方程式を解け。\n{{ given.equation }}"
# g1_l24.calculation: 比例式を解く（表示は比例式 a:b=c:x）
LF_SOLVE_PROPORTION_V1 = "次の比例式を解け。\n{{ given.equation }}"


def _register_all() -> None:
    REGISTRY.register_template("lf_solve_equation_property_v1", LF_SOLVE_EQUATION_PROPERTY_V1)
    REGISTRY.register_template("lf_solve_equation_transpose_v1", LF_SOLVE_EQUATION_TRANSPOSE_V1)
    REGISTRY.register_template("lf_solve_equation_v1", LF_SOLVE_EQUATION_V1)
    REGISTRY.register_template("lf_solve_proportion_v1", LF_SOLVE_PROPORTION_V1)


_register_all()


__all__ = [
    "LF_SOLVE_EQUATION_PROPERTY_V1",
    "LF_SOLVE_EQUATION_TRANSPOSE_V1",
    "LF_SOLVE_EQUATION_V1",
    "LF_SOLVE_PROPORTION_V1",
]
