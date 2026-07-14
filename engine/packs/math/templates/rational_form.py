"""分数⇔循環小数まわりの T1 テンプレート登録（実装設計 §7・§7.2）。"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g3_l16.calculation Lv1: 分数を循環小数の記号を用いて書く（C3）
LF_FRACTION_TO_DECIMAL_V1 = (
    "次の分数を小数で表し、循環小数の記号を用いて書け。\n{{ given.expression }}"
)

# g3_l16.calculation Lv2: 循環小数を分数で表す（C3）
LF_DECIMAL_TO_FRACTION_V1 = "次の循環小数を分数で表せ。\n{{ given.expression }}"


def _register_all() -> None:
    REGISTRY.register_template("lf_fraction_to_decimal_v1", LF_FRACTION_TO_DECIMAL_V1)
    REGISTRY.register_template("lf_decimal_to_fraction_v1", LF_DECIMAL_TO_FRACTION_V1)


_register_all()


__all__ = ["LF_FRACTION_TO_DECIMAL_V1", "LF_DECIMAL_TO_FRACTION_V1"]
