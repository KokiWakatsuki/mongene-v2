"""三平方の定理・その逆まわりの T1 テンプレート登録（実装設計 §7・§7.2）。"""
from __future__ import annotations

from engine.core.registry import REGISTRY

LF_PYTHAGOREAN_CONDITION_V1 = "{{ given.condition }}。"
LF_PYTHAGOREAN_STATEMENT_V1 = "{{ given.statement }}。"


def _register_all() -> None:
    REGISTRY.register_template("lf_pythagorean_condition_v1", LF_PYTHAGOREAN_CONDITION_V1)
    REGISTRY.register_template("lf_pythagorean_statement_v1", LF_PYTHAGOREAN_STATEMENT_V1)


_register_all()


__all__ = [
    "LF_PYTHAGOREAN_CONDITION_V1",
    "LF_PYTHAGOREAN_STATEMENT_V1",
]
