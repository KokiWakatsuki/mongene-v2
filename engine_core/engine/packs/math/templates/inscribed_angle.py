"""円周角の定理・その逆・弧の比例まわりの T1 テンプレート登録

（実装設計 §7・§7.2）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

LF_INSCRIBED_ANGLE_CONDITION_V1 = "{{ given.condition }}。"
LF_INSCRIBED_ANGLE_STATEMENT_V1 = "{{ given.statement }}。"


def _register_all() -> None:
    REGISTRY.register_template("lf_inscribed_angle_condition_v1", LF_INSCRIBED_ANGLE_CONDITION_V1)
    REGISTRY.register_template("lf_inscribed_angle_statement_v1", LF_INSCRIBED_ANGLE_STATEMENT_V1)


_register_all()


__all__ = [
    "LF_INSCRIBED_ANGLE_CONDITION_V1",
    "LF_INSCRIBED_ANGLE_STATEMENT_V1",
]
