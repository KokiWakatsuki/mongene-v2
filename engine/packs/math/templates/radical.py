"""平方根まわりの T1 テンプレート登録（実装設計 §7・§7.2）。"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g3_l14/l17〜l21.calculation: 根号を含む式を計算・簡約する（C3）
LF_RADICAL_CALC_V1 = "次の式を計算せよ。\n{{ given.expression }}"


def _register_all() -> None:
    REGISTRY.register_template("lf_radical_calc_v1", LF_RADICAL_CALC_V1)


_register_all()


__all__ = ["LF_RADICAL_CALC_V1"]
