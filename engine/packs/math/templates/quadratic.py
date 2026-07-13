"""2次方程式まわりの T1 テンプレート登録（実装設計 §7・§7.2）。"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g3_l25〜l28.calculation: 2次方程式を解く（C3）
LF_QUADRATIC_SOLVE_V1 = "次の2次方程式を解け。\n{{ given.equation }}"

# g3_l24.calculation Lv1: 左辺に値を代入して値を求める（＝解かどうかの確認）
LF_QUADRATIC_EVALUATE_V1 = (
    "{{ given.input_value }} を、次の方程式の左辺に代入して値を求めよ。\n{{ given.equation }}"
)


def _register_all() -> None:
    REGISTRY.register_template("lf_quadratic_solve_v1", LF_QUADRATIC_SOLVE_V1)
    REGISTRY.register_template("lf_quadratic_evaluate_v1", LF_QUADRATIC_EVALUATE_V1)


_register_all()


__all__ = ["LF_QUADRATIC_SOLVE_V1", "LF_QUADRATIC_EVALUATE_V1"]
