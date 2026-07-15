"""exam（入試対策・T1融合）まわりの T1 テンプレート登録（実装設計 §7・§7.2）。"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# exam_l5.calculation Lv2: 場合の数から確率
LF_EXAM_PROBABILITY_FROM_COUNTS_V1 = "{{ given.expressions }}。"

# exam_l7.calculation Lv2: 相対度数・比率
LF_EXAM_RELATIVE_FREQUENCY_V1 = "{{ given.expressions }}。"

# exam_l7.find_value Lv3: 四分位数・範囲
LF_EXAM_QUARTILES_FULL_SUMMARY_V1 = "{{ given.condition }}。"


def _register_all() -> None:
    REGISTRY.register_template(
        "lf_exam_probability_from_counts_v1", LF_EXAM_PROBABILITY_FROM_COUNTS_V1
    )
    REGISTRY.register_template("lf_exam_relative_frequency_v1", LF_EXAM_RELATIVE_FREQUENCY_V1)
    REGISTRY.register_template(
        "lf_exam_quartiles_full_summary_v1", LF_EXAM_QUARTILES_FULL_SUMMARY_V1
    )


_register_all()


__all__ = [
    "LF_EXAM_PROBABILITY_FROM_COUNTS_V1",
    "LF_EXAM_RELATIVE_FREQUENCY_V1",
    "LF_EXAM_QUARTILES_FULL_SUMMARY_V1",
]
