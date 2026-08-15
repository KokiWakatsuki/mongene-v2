"""合同な図形の対応関係まわりの T1 テンプレート登録（実装設計 §7・§7.2）。"""
from __future__ import annotations

from engine.core.registry import REGISTRY

LF_CONGRUENCE_TRANSFER_VALUES_V1 = "{{ given.condition }}。"
LF_CONGRUENCE_STATEMENT_V1 = "{{ given.statement }}。"


def _register_all() -> None:
    REGISTRY.register_template(
        "lf_congruence_transfer_values_v1", LF_CONGRUENCE_TRANSFER_VALUES_V1
    )
    REGISTRY.register_template("lf_congruence_statement_v1", LF_CONGRUENCE_STATEMENT_V1)


_register_all()


__all__ = [
    "LF_CONGRUENCE_TRANSFER_VALUES_V1",
    "LF_CONGRUENCE_STATEMENT_V1",
]
