"""平方根まわりの T1 テンプレート登録（実装設計 §7・§7.2）。"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g3_l14/l17〜l21/l23.calculation: 根号を含む式を計算・簡約する（C3）
LF_RADICAL_CALC_V1 = "次の式を計算せよ。\n{{ given.expression }}"

# g3_l23.find_value Lv2: 面積等の条件から1辺の長さを根号で求める（C3）
LF_RADICAL_FIND_VALUE_V1 = "{{ given.condition }}。"

# g3_l15.calculation Lv1: 2つの根号を含む数の大小を不等号で表す（C3）
LF_RADICAL_COMPARE_PAIR_V1 = "次の2つの数の大小を、不等号を使って表せ。\n{{ given.expression }}"

# g3_l15.calculation Lv2: 根号を含む数を小さい順に並べる（C3）
LF_RADICAL_COMPARE_ORDER_V1 = "次の数を小さい順に並べよ。\n{{ given.expression }}"


def _register_all() -> None:
    REGISTRY.register_template("lf_radical_calc_v1", LF_RADICAL_CALC_V1)
    REGISTRY.register_template("lf_radical_find_value_v1", LF_RADICAL_FIND_VALUE_V1)
    REGISTRY.register_template("lf_radical_compare_pair_v1", LF_RADICAL_COMPARE_PAIR_V1)
    REGISTRY.register_template("lf_radical_compare_order_v1", LF_RADICAL_COMPARE_ORDER_V1)


_register_all()


__all__ = [
    "LF_RADICAL_CALC_V1", "LF_RADICAL_FIND_VALUE_V1",
    "LF_RADICAL_COMPARE_PAIR_V1", "LF_RADICAL_COMPARE_ORDER_V1",
]
