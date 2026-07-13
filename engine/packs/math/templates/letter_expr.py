"""文字式まわりの T1 テンプレート登録（実装設計 §7・§7.2）。

テンプレは TemplateContext の公開変数（given / sub_questions[].{label,asked,narrations}）
のみ参照できる。answer/params は属性として存在しないため参照不能（Q5 の構造防止）。
テンプレ名は FamilySpec の `text.template` と一致させる（spec_lint R1 が検査）。

一次式の計算（g1_l17/l18）は arithmetic の `lf_calc_evaluate_v1`（"次の計算をせよ"）を共有する。
本モジュールは代入（g1_l16）など専用の文言を登録する。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g1_l16.calculation Lv1/Lv2: 式に数を代入して式の値を求める
LF_SUBSTITUTE_VALUE_V1 = (
    "x = {{ given.input_value }} のとき、次の式の値を求めよ。\n{{ given.expression }}"
)
# g1_l13.calculation: 乗法の表し方のきまりに従って簡潔に表す
LF_NOTATION_PRODUCT_V1 = (
    "次の式を、乗法の表し方のきまりに従って簡潔に表せ。\n{{ given.expression }}"
)
# g1_l14.calculation: 除法の表し方のきまりに従って分数の形で表す
LF_NOTATION_QUOTIENT_V1 = (
    "次の式を、除法の表し方のきまりに従って分数の形で表せ。\n{{ given.expression }}"
)
# g1_l17/l19/l21.knowledge Lv1: 説明された対象の用語の名称を答える（用語想起）
LF_TERM_RECALL_V1 = "{{ given.statement }} を何といいますか。"
# g1_l21.knowledge Lv2: ある値が方程式の解かを判別する（verify）
LF_VERIFY_SOLUTION_V1 = "{{ given.statement }} は、この方程式の解であるといえますか。"
# g1_l2.knowledge Lv2: 2数の大小を判別する（verify）
LF_COMPARE_NUMBERS_V1 = "次の2つの数 {{ given.statement }} のうち、大きいのはどちらですか。"
# g1_l20.knowledge Lv1: 数量の大小の関係を表す不等号を選ぶ（記号想起）
LF_INEQUALITY_SYMBOL_V1 = (
    "次の数量の大小の関係を不等号で表すとき、あてはまる不等号はどれですか。"
    "\n{{ given.statement }}"
)
# g1_l22.knowledge Lv1: 規則（移項の定義・理由）の正しい記述を選ぶ（規則想起）
LF_RULE_RECALL_V1 = "{{ given.statement }}。正しく述べているものを1つ選びなさい。"
# g1_l1.knowledge Lv1: 符号のついた数を正の数・負の数に分類する
LF_CLASSIFY_SIGN_V1 = "次の数は、正の数・負の数のどちらですか。\n{{ given.statement }}"
# g1_l1.knowledge Lv2: 反対の性質をもつ量を符号を使って表す
LF_OPPOSITE_QUANTITY_V1 = "{{ given.statement }} を、符号を使って表しなさい。"
# g1_l10.knowledge Lv2: 数の集合が四則について閉じているかを判別する
LF_SET_CLOSURE_V1 = "{{ given.statement }}。あてはまるものを選びなさい。"


def _register_all() -> None:
    REGISTRY.register_template("lf_substitute_value_v1", LF_SUBSTITUTE_VALUE_V1)
    REGISTRY.register_template("lf_notation_product_v1", LF_NOTATION_PRODUCT_V1)
    REGISTRY.register_template("lf_notation_quotient_v1", LF_NOTATION_QUOTIENT_V1)
    REGISTRY.register_template("lf_term_recall_v1", LF_TERM_RECALL_V1)
    REGISTRY.register_template("lf_verify_solution_v1", LF_VERIFY_SOLUTION_V1)
    REGISTRY.register_template("lf_compare_numbers_v1", LF_COMPARE_NUMBERS_V1)
    REGISTRY.register_template("lf_inequality_symbol_v1", LF_INEQUALITY_SYMBOL_V1)
    REGISTRY.register_template("lf_rule_recall_v1", LF_RULE_RECALL_V1)
    REGISTRY.register_template("lf_classify_sign_v1", LF_CLASSIFY_SIGN_V1)
    REGISTRY.register_template("lf_opposite_quantity_v1", LF_OPPOSITE_QUANTITY_V1)
    REGISTRY.register_template("lf_set_closure_v1", LF_SET_CLOSURE_V1)


_register_all()


__all__ = [
    "LF_SUBSTITUTE_VALUE_V1",
    "LF_NOTATION_PRODUCT_V1",
    "LF_NOTATION_QUOTIENT_V1",
    "LF_TERM_RECALL_V1",
    "LF_VERIFY_SOLUTION_V1",
    "LF_COMPARE_NUMBERS_V1",
    "LF_INEQUALITY_SYMBOL_V1",
    "LF_RULE_RECALL_V1",
    "LF_CLASSIFY_SIGN_V1",
    "LF_OPPOSITE_QUANTITY_V1",
    "LF_SET_CLOSURE_V1",
]
