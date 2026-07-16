"""相似比から面積比・表面積比・体積比を求めるまわりの T1 テンプレート登録

（実装設計 §7・§7.2）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

LF_SIMILARITY_SCALE_RATIO_CONDITION_V1 = "{{ given.condition }}。"


def _register_all() -> None:
    REGISTRY.register_template(
        "lf_similarity_scale_ratio_condition_v1", LF_SIMILARITY_SCALE_RATIO_CONDITION_V1
    )


_register_all()


__all__ = [
    "LF_SIMILARITY_SCALE_RATIO_CONDITION_V1",
]
