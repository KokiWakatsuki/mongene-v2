"""正の数・負の数の四則まわりの T1 テンプレート登録（実装設計 §7・§7.2）。

テンプレは TemplateContext の公開変数（given / sub_questions[].{label,asked,narrations}）
のみ参照できる。answer/params は属性として存在しないため参照不能（Q5 の構造防止）。
テンプレ名は FamilySpec の `text.template` と一致させる（spec_lint R1 が検査）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g1 正負の数 calculation（加法・減法・乗法・除法・累乗・四則混合）: 数値式を計算する
LF_CALC_EVALUATE_V1 = "次の計算をせよ。\n{{ given.expression }}"

# g1_l9.calculation Lv3: 分配法則を使って工夫して計算する
LF_CALC_DISTRIBUTIVE_V1 = "分配法則を利用して、次の計算を工夫してせよ。\n{{ given.expression }}"

# g1_l2.calculation Lv1: 絶対値を求める
LF_CALC_ABS_V1 = "次の数の絶対値を求めよ。\n{{ given.expression }}"

# g1_l2.calculation Lv2: 複数の数を大小の順に並べる（given に順序の別まで含む）
LF_CALC_ORDER_V1 = "{{ given.expression }}。"

# g1_l11.calculation: 素因数分解して累乗の積で表す
LF_CALC_FACTORIZE_V1 = "次の数を素因数分解し、累乗を使って表せ。\n{{ given.expression }}"

# g1_l60.calculation Lv1: a×10ⁿ（a は1以上10未満）の形で表す
LF_CALC_SCI_NOTATION_V1 = (
    "次の数を、a×10ⁿ（a は1以上10未満の数）の形で表せ。\n{{ given.expression }}"
)

# g1_l60.calculation Lv2: 有効数字を指定して a×10ⁿ の形で表す
LF_CALC_SCI_SIGFIG_V1 = (
    "次の数を、有効数字{{ given.sig_figs }}桁として、"
    "a×10ⁿ（a は1以上10未満の数）の形で表せ。\n{{ given.expression }}"
)


def _register_all() -> None:
    REGISTRY.register_template("lf_calc_evaluate_v1", LF_CALC_EVALUATE_V1)
    REGISTRY.register_template("lf_calc_distributive_v1", LF_CALC_DISTRIBUTIVE_V1)
    REGISTRY.register_template("lf_calc_abs_v1", LF_CALC_ABS_V1)
    REGISTRY.register_template("lf_calc_order_v1", LF_CALC_ORDER_V1)
    REGISTRY.register_template("lf_calc_factorize_v1", LF_CALC_FACTORIZE_V1)
    REGISTRY.register_template("lf_calc_sci_notation_v1", LF_CALC_SCI_NOTATION_V1)
    REGISTRY.register_template("lf_calc_sci_sigfig_v1", LF_CALC_SCI_SIGFIG_V1)


_register_all()


__all__ = [
    "LF_CALC_EVALUATE_V1",
    "LF_CALC_DISTRIBUTIVE_V1",
    "LF_CALC_ABS_V1",
    "LF_CALC_ORDER_V1",
    "LF_CALC_FACTORIZE_V1",
    "LF_CALC_SCI_NOTATION_V1",
    "LF_CALC_SCI_SIGFIG_V1",
]
