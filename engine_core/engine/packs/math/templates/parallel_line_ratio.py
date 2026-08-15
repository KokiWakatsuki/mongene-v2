"""平行線と線分の比の定理・その逆・中点連結定理まわりの T1 テンプレート登録

（実装設計 §7・§7.2）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

LF_PARALLEL_LINE_RATIO_CONDITION_V1 = "{{ given.condition }}。"


def _register_all() -> None:
    REGISTRY.register_template(
        "lf_parallel_line_ratio_condition_v1", LF_PARALLEL_LINE_RATIO_CONDITION_V1
    )


_register_all()


__all__ = [
    "LF_PARALLEL_LINE_RATIO_CONDITION_V1",
]
